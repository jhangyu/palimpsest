# backend/main.py
"""
---
name: main
description: "FastAPI application entry-point: lifespan (migrations, KEK, scheduler), CORS/logging middleware, router registration"
type: entry_point
target:
  layer: backend
  domain: app
spec_doc: null
test_file: null
functions:
  - name: _run_all_migrations
    line: 96
    purpose: "Run all DDL migrations via versioned runner (core.migrations)"
  - name: _run_startup_backfills
    line: 318
    purpose: "Non-critical startup backfills (user secret keys, site owners, repair states) as background task"
  - name: _backfill_articles
    line: 353
    purpose: "Backfill NULL created_at / updated_at / word_count for existing articles (500 rows/run)"
  - name: scheduled_crawl_job
    line: 422
    purpose: "Scheduler job — crawl all sites in parallel with semaphore(5)"
  - name: _cleanup_job
    line: 460
    purpose: "Scheduler job — remove expired auth sessions and password-reset tokens"
  - name: lifespan
    line: 475
    purpose: "FastAPI lifespan context: migrations, KEK init, scheduler lock, backfill tasks, graceful shutdown"
  - name: global_exception_handler
    line: 656
    purpose: "Global 500 exception handler — returns JSON error with CORS headers for credentialed origins"
  - name: request_logging_middleware
    line: 697
    purpose: "HTTP middleware — logs method, path, status code, and duration for every request"
  - name: health_check
    line: 738
    purpose: "GET /health — DB connectivity probe for container orchestration (returns 503 on error)"
  - name: serve_frontend
    line: 752
    purpose: "GET /{full_path:path} — serve built Astro SPA from FRONTEND_DIR with path-traversal guard"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
from dotenv import load_dotenv

# Load .env file
load_dotenv()

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, text, update
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from dateutil import parser as dateutil_parser

# --- Core module imports ---
from core.auth import cleanup_expired_sessions, cleanup_expired_tokens
from core.ai_provider_migrations import (
    backfill_existing_user_secret_keys,
    backfill_site_owners,
)
from core.crawler import compute_visible_word_count
from core.llm.key_backends import FileKeyEncryptionBackend
from core.ownership import get_sites_with_owner_status
from scheduler import create_scheduler, setup_jobs, acquire_scheduler_lock, release_scheduler_lock

# --- Foundation / router imports ---
from core.db import (
    engine, async_session_factory, metadata, DATABASE_URL,
    users, auth_sessions, password_reset_tokens, email_verification_tokens,
    articles, schema_versions, ai_tables,
)
from routers._deps import log_with_time
from routers.sites import _record_crawl_attempt, _background_tasks

# ---------------------------------------------------------------------------


async def _run_all_migrations() -> None:
    """Run all DDL migrations using the existing async engine.

    On a fresh database (no schema_versions table), metadata.create_all seeds
    every table first so the versioned migrations have a base to work from.
    On subsequent starts create_all is skipped — the migration runner and
    crawl_repair phase are idempotent, and checking/applying only unapplied
    versions avoids ~35 redundant DB round-trips per start.
    """
    from core.migrations import run_migrations

    # ------------------------------------------------------------------
    # Phase 0: is this a fresh database?
    # ------------------------------------------------------------------
    async with engine.connect() as check_conn:
        def _has_schema_versions(sync_conn):
            result = sync_conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables "
                "WHERE table_name = 'schema_versions')"
            ))
            return result.scalar()
        is_fresh = not await check_conn.run_sync(_has_schema_versions)

    if is_fresh:
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        log_with_time("[Migration] Fresh database — tables created from metadata.")

    # ------------------------------------------------------------------
    # Phase 1: versioned migrations (skips already-applied versions)
    # ------------------------------------------------------------------
    async with engine.begin() as conn:
        await conn.run_sync(run_migrations)

    # ------------------------------------------------------------------
    # Phase 2: crawl_repair (commits internally, tracked via schema_versions)
    # ------------------------------------------------------------------
    async with engine.connect() as conn2:
        def _crawl_repair_applied(sync_conn):
            result = sync_conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM schema_versions WHERE version = '0.3.0')"
            ))
            return result.scalar()
        already_applied = await conn2.run_sync(_crawl_repair_applied)

        if not already_applied:
            from core.crawl_repair_models import migrate_crawl_repair_tables

            await conn2.run_sync(migrate_crawl_repair_tables)

            now = datetime.now(timezone.utc)
            await conn2.execute(text(
                "INSERT INTO schema_versions (version, description, applied_at) "
                "VALUES (:v, :d, :ts)"
                " ON CONFLICT (version) DO NOTHING"
            ), {
                "v": "0.3.0",
                "d": "Crawl repair tables, auto-repair site columns, attempt outcome columns, constraints",
                "ts": now,
            })
            await conn2.commit()
            log_with_time("[Migration] crawl_repair (v0.3.0) applied.")
        else:
            log_with_time("[Migration] crawl_repair (v0.3.0) already applied, skipping.")

    log_with_time("[Migration] All migrations completed.")


# ---------------------------------------------------------------------------
# _run_startup_backfills  (non-critical; runs as background task)
# ---------------------------------------------------------------------------

async def _run_startup_backfills(kek_backend) -> None:
    """Non-critical backfills — deferred to background so server is ready immediately.

    Equivalent to _backfill_articles: runs after yield, does not block readiness.
    All operations are idempotent (ON CONFLICT DO NOTHING / upsert semantics).
    """
    if kek_backend is not None:
        async with async_session_factory() as session:
            try:
                await backfill_existing_user_secret_keys(session, users, ai_tables.user_secret_keys, kek_backend)
                log_with_time("[Backfill] User secret key backfill completed.")
            except Exception as e:
                log_with_time(f"[Backfill] User secret key backfill note: {e}")
            try:
                result = await backfill_site_owners(session)
                log_with_time(f"[Backfill] Site owner backfill: {result.status.value}")
            except Exception as e:
                log_with_time(f"[Backfill] Site owner backfill note: {e}")

    async with async_session_factory() as session:
        try:
            from core.crawl_repair_models import backfill_repair_states
            from core.time_provider import taipei_week_window, SystemClock
            _clock = SystemClock()
            _week = taipei_week_window(_clock.now_utc())
            result = await backfill_repair_states(session, current_week_start=_week.start_utc)
            log_with_time(f"[Backfill] Crawl repair state backfill: scanned={result['sites_scanned']}, inserted={result['rows_inserted']}")
        except Exception as e:
            log_with_time(f"[Backfill] Crawl repair state backfill note: {e}")


# ---------------------------------------------------------------------------
# _backfill_articles  (runs once at startup as a background task)
# ---------------------------------------------------------------------------

async def _backfill_articles():
    """Backfill created_at, updated_at, word_count for existing articles with NULL values."""
    log_with_time("[Backfill] Starting article backfill...")

    # Backfill created_at / updated_at
    # DD-10: published_at is now TIMESTAMPTZ; row value is a datetime object
    async with async_session_factory() as session:
        rows = (await session.execute(
            select(articles.c.id, articles.c.published_at)
            .where(articles.c.created_at == None)  # noqa: E711
            .limit(500)
        )).mappings().all()
        if rows:
            log_with_time(f"[Backfill] Backfilling created_at/updated_at for {len(rows)} articles...")
            for row in rows:
                ts = None
                if row['published_at']:
                    try:
                        val = row['published_at']
                        if isinstance(val, datetime):
                            ts = val if val.tzinfo else val.replace(tzinfo=timezone.utc)
                        elif isinstance(val, str):
                            parsed = dateutil_parser.parse(val)
                            ts = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
                    except Exception:
                        pass
                if ts is None:
                    ts = datetime.now(timezone.utc)
                try:
                    await session.execute(
                        update(articles)
                        .where(articles.c.id == row['id'])
                        .where(articles.c.created_at == None)  # noqa: E711
                        .values(created_at=ts, updated_at=ts)
                    )
                except Exception as e:
                    log_with_time(f"[Backfill] Warning: failed to backfill article {row['id']}: {e}")
            await session.commit()

    # Backfill word_count
    async with async_session_factory() as session:
        wc_rows = (await session.execute(
            select(articles.c.id, articles.c.content)
            .where(articles.c.word_count == None)  # noqa: E711
            .where(articles.c.content != None)  # noqa: E711
            .limit(500)
        )).mappings().all()
        if wc_rows:
            log_with_time(f"[Backfill] Backfilling word_count for {len(wc_rows)} articles...")
            for row in wc_rows:
                try:
                    wc = compute_visible_word_count(row['content'])
                    await session.execute(
                        update(articles)
                        .where(articles.c.id == row['id'])
                        .where(articles.c.word_count == None)  # noqa: E711
                        .values(word_count=wc)
                    )
                except Exception as e:
                    log_with_time(f"[Backfill] Warning: failed to compute word_count for article {row['id']}: {e}")
            await session.commit()

    log_with_time("[Backfill] Article backfill completed.")


# ---------------------------------------------------------------------------
# scheduled_crawl_job
# ---------------------------------------------------------------------------

async def scheduled_crawl_job():
    """Scheduled crawl job: crawl only feeds whose next crawl time is due."""
    print("[Scheduler] Running scheduled crawl...")
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        all_sites = await get_sites_with_owner_status(session)
    due_sites = [
        site for site in all_sites
        if site.get('next_crawl_at') is None or site['next_crawl_at'] <= now
    ]
    print(f"[Scheduler] {len(due_sites)} of {len(all_sites)} site(s) are due.")
    semaphore = asyncio.Semaphore(5)

    async def crawl_with_limit(site):
        async with semaphore:
            try:
                _raw_filter = site.get('filter_rules')
                filter_rules = (
                    _raw_filter if isinstance(_raw_filter, dict)
                    else json.loads(_raw_filter) if isinstance(_raw_filter, str)
                    else None
                )
                await _record_crawl_attempt(
                    site_id=site['id'],
                    trigger_type="scheduled",
                    url=site['url'],
                    list_rules=site['list_rules'] if isinstance(site['list_rules'], dict) else json.loads(site['list_rules']),
                    content_rules=site['content_rules'] if isinstance(site['content_rules'], dict) else json.loads(site['content_rules']),
                    filter_rules=filter_rules,
                    force_update=False,
                    scrape_method=site['scrape_method'] if site['scrape_method'] else "scrapling",
                    owner_user_id=site.get("owner_user_id"),
                    kek_backend=app.state.kek_backend,
                    source_type=site.get('source_type', 'html'),
                    rss_full_content=site.get('rss_full_content', False),
                )
            except Exception as e:
                print(f"[Scheduler] Error crawling site {site['id']}: {e}")

    await asyncio.gather(*[crawl_with_limit(s) for s in due_sites])


# ---------------------------------------------------------------------------
# _cleanup_job
# ---------------------------------------------------------------------------

async def _cleanup_job():
    try:
        async with async_session_factory() as session:
            s_count = await cleanup_expired_sessions(session, auth_sessions)
            t_count = await cleanup_expired_tokens(session, password_reset_tokens, email_verification_tokens)
            if s_count or t_count:
                log_with_time(f"[Cleanup] Removed {s_count} expired sessions, {t_count} expired tokens")
    except Exception as e:
        log_with_time(f"[Cleanup] Error: {e}")


# ---------------------------------------------------------------------------
# Lifespan (Startup / Shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run all DDL migrations using the existing async engine (no sync driver needed).
    await _run_all_migrations()

    # --- LLM Provider Profiles feature flag ---
    _llm_profiles_enabled = os.getenv("LLM_PROVIDER_PROFILES_ENABLED", "true").lower() in ("true", "1", "yes")
    app.state.llm_profiles_enabled = _llm_profiles_enabled

    if _llm_profiles_enabled:
        kek_path = os.getenv("LLM_KEK_PATH", "/run/secrets/llm_kek")
        kek_version = os.getenv("LLM_KEK_VERSION", "v1")
        app.state.kek_backend = None
        try:
            _kek_backend = FileKeyEncryptionBackend(kek_path, kek_version)
            app.state.kek_backend = _kek_backend
            log_with_time(f"[Startup] KEK backend initialized from {kek_path} (version={kek_version})")
        except Exception as e:
            # Try fallback path before auto-generating
            fallback_kek_path = os.path.join(os.getcwd(), "data", "kek")
            if fallback_kek_path != kek_path:
                try:
                    _kek_backend = FileKeyEncryptionBackend(fallback_kek_path, kek_version)
                    app.state.kek_backend = _kek_backend
                    kek_path = fallback_kek_path
                    log_with_time(f"[Startup] KEK backend initialized from fallback {fallback_kek_path} (version={kek_version})")
                except Exception:
                    pass  # Fall through to existing logic

            if app.state.kek_backend is None:
                # Check if any providers exist that require vault
                provider_count = None
                has_secret_keys = False
                try:
                    async with async_session_factory() as session:
                        result = await session.execute(
                            text("SELECT COUNT(*) as cnt FROM user_ai_providers")
                        )
                        provider_count = result.mappings().first()
                        sk_result = await session.execute(
                            text("SELECT COUNT(*) as cnt FROM user_secret_keys")
                        )
                        sk_count = sk_result.mappings().first()
                        has_secret_keys = sk_count is not None and sk_count["cnt"] > 0
                    has_providers = provider_count and provider_count["cnt"] > 0
                except Exception as db_exc:
                    raise RuntimeError(
                        f"[FATAL] KEK unavailable ({e}) and provider count check failed ({db_exc}). "
                        "Cannot determine safe startup state. Refusing to start."
                    ) from db_exc

                # Orphaned secret keys without providers — clear before auto-generating
                if not has_providers and has_secret_keys:
                    try:
                        async with async_session_factory() as cleanup_session:
                            stale = await cleanup_session.execute(
                                text("DELETE FROM user_secret_keys RETURNING user_id")
                            )
                            deleted_rows = stale.fetchall()
                            await cleanup_session.commit()
                            if deleted_rows:
                                log_with_time(f"[Startup] Cleared {len(deleted_rows)} orphaned user secret key(s) (no providers exist)")
                    except Exception as cleanup_exc:
                        log_with_time(f"[Startup] Warning: could not clear orphaned user secret keys: {cleanup_exc}")

                if has_providers:
                    cnt = provider_count["cnt"] if provider_count else "unknown"
                    raise RuntimeError(
                        f"[FATAL] KEK backend unavailable ({e}) but {cnt} "
                        "provider(s) exist. Cannot start without KEK. "
                        "Set LLM_PROVIDER_PROFILES_ENABLED=false for environment-only mode, "
                        "or provide a valid KEK keyring at LLM_KEK_PATH."
                    )
                else:
                    # First-time setup: auto-generate KEK
                    log_with_time(f"[Startup] KEK not found; auto-generating keyring...")
                    _generated = False
                    for candidate_path in [kek_path, os.path.join(os.getcwd(), "data", "kek")]:
                        try:
                            FileKeyEncryptionBackend.generate_keyring(candidate_path, kek_version)
                            _kek_backend = FileKeyEncryptionBackend(candidate_path, kek_version)
                            app.state.kek_backend = _kek_backend
                            kek_path = candidate_path
                            log_with_time(f"[Startup] KEK keyring auto-generated at {candidate_path}")
                            # Clean up any stale user_secret_keys from previous KEK
                            try:
                                async with async_session_factory() as cleanup_session:
                                    stale = await cleanup_session.execute(
                                        text("DELETE FROM user_secret_keys RETURNING user_id")
                                    )
                                    deleted_rows = stale.fetchall()
                                    await cleanup_session.commit()
                                    if deleted_rows:
                                        log_with_time(f"[Startup] Cleared {len(deleted_rows)} stale user secret key(s) from previous KEK")
                            except Exception as cleanup_exc:
                                log_with_time(f"[Startup] Warning: could not clear stale user secret keys: {cleanup_exc}")
                            _generated = True
                            break
                        except Exception as gen_exc:
                            log_with_time(f"[Startup] Cannot generate KEK at {candidate_path}: {gen_exc}")
                    if not _generated:
                        log_with_time("[Startup] KEK auto-generation failed; continuing without encryption")
                        app.state.kek_backend = None
    else:
        log_with_time("[Startup] LLM provider profiles disabled (LLM_PROVIDER_PROFILES_ENABLED=false); using environment fallback only")
        app.state.kek_backend = None

    # Seed initial schema version if not exists
    async with async_session_factory() as session:
        try:
            existing_version = (await session.execute(
                schema_versions.select().where(schema_versions.c.version == "0.1.0")
            )).mappings().first()
            if not existing_version:
                await session.execute(
                    schema_versions.insert().values(
                        version="0.1.0",
                        description="Initial schema",
                        applied_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()
                log_with_time("[Startup] Seeded initial schema version 0.1.0")
        except Exception as e:
            log_with_time(f"[Startup] Schema version seeding note: {e}")

    # First-run check
    async with async_session_factory() as session:
        user_count = (await session.execute(
            select(func.count().label("cnt")).select_from(users)
        )).mappings().first()
    if user_count and user_count["cnt"] == 0:
        log_with_time("[Startup] First-run setup required: no users found. POST /auth/first-run-setup to create admin.")

    # Start scheduler only if this worker acquires the advisory lock (prevents thundering herd)
    # Use a persistent connection for the advisory lock (session-level in PostgreSQL)
    # Scheduler is created lazily here — no module-level engine is wasted when lock is not acquired.
    lock_conn = await engine.connect()
    _scheduler_lock_acquired = await acquire_scheduler_lock(lock_conn)
    _scheduler = None
    if _scheduler_lock_acquired:
        _scheduler = create_scheduler(DATABASE_URL)
        setup_jobs(_scheduler, scheduled_crawl_job, _cleanup_job)
        _scheduler.start()
        print("[Startup] Database connected, scheduler started (lock acquired).")
    else:
        print("[Startup] Database connected, scheduler skipped (another worker holds lock).")

    # Schedule non-critical backfills as background task (secret keys, site owners, repair states)
    _bt2 = asyncio.create_task(_run_startup_backfills(app.state.kek_backend))
    _background_tasks.add(_bt2)
    _bt2.add_done_callback(_background_tasks.discard)

    # Schedule article backfill as background task so server starts immediately
    _bt = asyncio.create_task(_backfill_articles())
    _background_tasks.add(_bt)
    _bt.add_done_callback(_background_tasks.discard)

    yield

    # --- Graceful shutdown: cancel tracked background tasks ---
    for task in list(_background_tasks):
        task.cancel()
    if _background_tasks:
        await asyncio.wait(_background_tasks, timeout=5.0)

    if _scheduler_lock_acquired and _scheduler is not None:
        _scheduler.shutdown()
        await release_scheduler_lock(lock_conn)
    await lock_conn.close()
    await engine.dispose()
    print("[Shutdown] Database engine disposed.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(lifespan=lifespan)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    origin = request.headers.get("origin", "")
    headers = {}
    if origin in _allowed_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": str(exc)},
        headers=headers,
    )


# --- CORS: credentialed requests require explicit origins ---
_allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
_default_allowed_origins = [
    os.getenv("FRONTEND_ORIGIN", "http://localhost:5174").rstrip("/"),
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:8088",
    "http://127.0.0.1:8088",
]
_allowed_origins = (
    [o.strip().rstrip("/") for o in _allowed_origins_raw.split(",") if o.strip()]
    if _allowed_origins_raw.strip()
    else _default_allowed_origins
)
_allowed_origins = list(dict.fromkeys(_allowed_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# A-11: Lightweight request logging middleware
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    log_with_time(f"{request.method} {request.url.path} → {response.status_code} ({duration_ms:.0f}ms)")
    return response


# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------

from routers.auth import router as auth_router
from routers.users import router as users_router
from routers.admin import router as admin_router
from routers.ai_providers import router as ai_providers_router
from routers.database import router as database_router
from routers.sites import router as sites_router
from routers.analytics import router as analytics_router
from routers.notifications import router as notifications_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(ai_providers_router)
app.include_router(database_router)
app.include_router(sites_router)
app.include_router(analytics_router)
app.include_router(notifications_router, prefix="/api")


# ---------------------------------------------------------------------------
# Frontend serving & health check (remain on app directly)
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(
    os.getenv("PALIMPSEST_FRONTEND_DIR", Path(__file__).resolve().parent.parent / "frontend-astro")
).resolve()


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "healthy", "db": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "db": str(e)},
        )


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    """Serve the built Astro frontend when packaged in the Docker image."""
    if not FRONTEND_DIR.is_dir():
        raise HTTPException(status_code=404, detail="Frontend not built")

    safe_path = full_path.strip("/")
    # Block path traversal before any path resolution
    if ".." in safe_path:
        raise HTTPException(status_code=403, detail="Forbidden")

    candidates = []

    if safe_path:
        path_parts = safe_path.split("/")
        for part in path_parts:
            if part == ".." or part.startswith("."):
                raise HTTPException(status_code=403, detail="Forbidden")

        requested = FRONTEND_DIR / safe_path
        if requested.is_file():
            candidates.append(requested)
        # Astro format:'file' outputs page.html — try .html suffix
        html_suffixed = requested.parent / (requested.name + ".html")
        if html_suffixed.is_file():
            candidates.append(html_suffixed)
        if (requested / "index.html").is_file():
            candidates.append(requested / "index.html")
        # Try under pages/ subdirectory (bare paths without /pages prefix)
        pages_requested = FRONTEND_DIR / "pages" / safe_path
        if pages_requested.is_file():
            candidates.append(pages_requested)
        pages_html = pages_requested.parent / (pages_requested.name + ".html")
        if pages_html.is_file():
            candidates.append(pages_html)
        if (pages_requested / "index.html").is_file():
            candidates.append(pages_requested / "index.html")

        first_segment = safe_path.split("/", 1)[0]
        if first_segment and (FRONTEND_DIR / first_segment / "index.html").is_file():
            candidates.append(FRONTEND_DIR / first_segment / "index.html")

    if (FRONTEND_DIR / "index.html").is_file():
        candidates.append(FRONTEND_DIR / "index.html")

    for candidate in candidates:
        # Final safety check - ensure resolved path is within FRONTEND_DIR
        if candidate.resolve().is_relative_to(FRONTEND_DIR):
            return FileResponse(candidate)

    raise HTTPException(status_code=404, detail="Frontend asset not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)
