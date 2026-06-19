# backend/main.py
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

import sqlalchemy
from sqlalchemy import func, select, update
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from dateutil import parser as dateutil_parser

# --- Core module imports ---
from core.auth import cleanup_expired_sessions, cleanup_expired_tokens
from core.ai_provider_migrations import (
    SCHEMA_EXPANSION_STATEMENTS,
    backfill_existing_user_secret_keys,
    backfill_site_owners,
)
from core.crawler import compute_visible_word_count
from core.llm.key_backends import FileKeyEncryptionBackend
from core.ownership import get_sites_with_owner_status
from scheduler import create_scheduler, setup_jobs, acquire_scheduler_lock, release_scheduler_lock

# --- Foundation / router imports ---
from core.db import (
    database, metadata, DATABASE_URL,
    users, auth_sessions, password_reset_tokens, email_verification_tokens,
    articles, schema_versions, ai_tables,
)
from routers._deps import log_with_time
from routers.database import _run_schema_migration, APP_VERSION, MIGRATIONS
from routers.sites import _record_crawl_attempt, _background_tasks

# --- Scheduler ---
scheduler = create_scheduler(DATABASE_URL)


# ---------------------------------------------------------------------------
# _backfill_articles  (runs once at startup as a background task)
# ---------------------------------------------------------------------------

async def _backfill_articles():
    """Backfill created_at, updated_at, word_count for existing articles with NULL values."""
    log_with_time("[Backfill] Starting article backfill...")

    # Backfill created_at / updated_at
    # DD-10: published_at is now TIMESTAMPTZ; row value is a datetime object
    rows = await database.fetch_all(
        select(articles.c.id, articles.c.published_at)
        .where(articles.c.created_at == None)  # noqa: E711
        .limit(500)
    )
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
                await database.execute(
                    update(articles)
                    .where(articles.c.id == row['id'])
                    .where(articles.c.created_at == None)  # noqa: E711
                    .values(created_at=ts, updated_at=ts)
                )
            except Exception as e:
                log_with_time(f"[Backfill] Warning: failed to backfill article {row['id']}: {e}")

    # Backfill word_count
    wc_rows = await database.fetch_all(
        select(articles.c.id, articles.c.content)
        .where(articles.c.word_count == None)  # noqa: E711
        .where(articles.c.content != None)  # noqa: E711
        .limit(500)
    )
    if wc_rows:
        log_with_time(f"[Backfill] Backfilling word_count for {len(wc_rows)} articles...")
        for row in wc_rows:
            try:
                wc = compute_visible_word_count(row['content'])
                await database.execute(
                    update(articles)
                    .where(articles.c.id == row['id'])
                    .where(articles.c.word_count == None)  # noqa: E711
                    .values(word_count=wc)
                )
            except Exception as e:
                log_with_time(f"[Backfill] Warning: failed to compute word_count for article {row['id']}: {e}")

    log_with_time("[Backfill] Article backfill completed.")


# ---------------------------------------------------------------------------
# scheduled_crawl_job
# ---------------------------------------------------------------------------

async def scheduled_crawl_job():
    """排程任務：取出所有網站並並行執行爬蟲（最多 5 個同時進行）"""
    print("[Scheduler] Running scheduled crawl...")
    all_sites = await get_sites_with_owner_status(database)
    semaphore = asyncio.Semaphore(5)

    async def crawl_with_limit(site):
        async with semaphore:
            try:
                await _record_crawl_attempt(
                    site_id=site['id'],
                    trigger_type="scheduled",
                    url=site['url'],
                    list_rules=site['list_rules'] if isinstance(site['list_rules'], dict) else json.loads(site['list_rules']),
                    content_rules=site['content_rules'] if isinstance(site['content_rules'], dict) else json.loads(site['content_rules']),
                    force_update=False,
                    scrape_method=site['scrape_method'] if site['scrape_method'] else "scrapling",
                    owner_user_id=site.get("owner_user_id"),
                    kek_backend=app.state.kek_backend,
                )
            except Exception as e:
                print(f"[Scheduler] Error crawling site {site['id']}: {e}")

    await asyncio.gather(*[crawl_with_limit(s) for s in all_sites])


# ---------------------------------------------------------------------------
# Lifespan (Startup / Shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    app.state.database = database
    # Create tables if not exist
    sync_url = DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql://")
    engine = sqlalchemy.create_engine(sync_url)

    await asyncio.to_thread(metadata.create_all, engine)

    # Run idempotent migration for existing DBs
    await asyncio.to_thread(_run_schema_migration, engine)

    # --- AI Provider schema expansion ---
    from sqlalchemy import text as sa_text_ai
    with engine.connect() as conn:
        for stmt in SCHEMA_EXPANSION_STATEMENTS:
            try:
                conn.execute(sa_text_ai(stmt))
            except Exception as e:
                log_with_time(f"[Migration] AI provider schema expansion note: {e}")
        conn.commit()
    log_with_time("[Migration] AI provider schema expansion completed.")

    # --- LLM Provider Profiles feature flag ---
    _llm_profiles_enabled = os.getenv("LLM_PROVIDER_PROFILES_ENABLED", "true").lower() in ("true", "1", "yes")
    app.state.llm_profiles_enabled = _llm_profiles_enabled

    if _llm_profiles_enabled:
        kek_path = os.getenv("LLM_KEK_PATH", "/run/secrets/llm_kek")
        kek_version = os.getenv("LLM_KEK_VERSION", "v1")
        try:
            _kek_backend = FileKeyEncryptionBackend(kek_path, kek_version)
            app.state.kek_backend = _kek_backend
            log_with_time(f"[Startup] KEK backend initialized from {kek_path} (version={kek_version})")
        except Exception as e:
            # Check if any providers exist that require vault
            provider_count = None
            try:
                provider_count = await database.fetch_one(
                    "SELECT COUNT(*) as cnt FROM user_ai_providers"
                )
                has_providers = provider_count and provider_count["cnt"] > 0
            except Exception as db_exc:
                raise RuntimeError(
                    f"[FATAL] KEK unavailable ({e}) and provider count check failed ({db_exc}). "
                    "Cannot determine safe startup state. Refusing to start."
                ) from db_exc

            if has_providers:
                cnt = provider_count["cnt"] if provider_count else "unknown"
                raise RuntimeError(
                    f"[FATAL] KEK backend unavailable ({e}) but {cnt} "
                    "provider(s) exist. Cannot start without KEK. "
                    "Set LLM_PROVIDER_PROFILES_ENABLED=false for environment-only mode, "
                    "or provide a valid KEK keyring at LLM_KEK_PATH."
                )
            else:
                log_with_time(f"[Startup] KEK backend unavailable ({e}); no providers configured, continuing in environment-only mode")
                app.state.kek_backend = None
    else:
        log_with_time("[Startup] LLM provider profiles disabled (LLM_PROVIDER_PROFILES_ENABLED=false); using environment fallback only")
        app.state.kek_backend = None

    # --- Backfill user secret keys and site owners ---
    if app.state.kek_backend is not None:
        try:
            await backfill_existing_user_secret_keys(database, users, ai_tables.user_secret_keys, app.state.kek_backend)
            log_with_time("[Startup] User secret key backfill completed.")
        except Exception as e:
            log_with_time(f"[Startup] User secret key backfill note: {e}")
        try:
            result = await backfill_site_owners(database)
            log_with_time(f"[Startup] Site owner backfill: {result.status.value}")
        except Exception as e:
            log_with_time(f"[Startup] Site owner backfill note: {e}")

    # Seed initial schema version if not exists
    try:
        existing_version = await database.fetch_one(
            schema_versions.select().where(schema_versions.c.version == "0.1.0")
        )
        if not existing_version:
            await database.execute(
                schema_versions.insert().values(
                    version="0.1.0",
                    description="Initial schema",
                    applied_at=datetime.now(timezone.utc),
                )
            )
            log_with_time("[Startup] Seeded initial schema version 0.1.0")
    except Exception as e:
        log_with_time(f"[Startup] Schema version seeding note: {e}")

    # First-run check
    user_count = await database.fetch_one(
        select(func.count().label("cnt")).select_from(users)
    )
    if user_count and user_count["cnt"] == 0:
        log_with_time("[Startup] First-run setup required: no users found. POST /auth/first-run-setup to create admin.")

    # Add session/token cleanup job (daily)
    async def _cleanup_job():
        try:
            s_count = await cleanup_expired_sessions(database, auth_sessions)
            t_count = await cleanup_expired_tokens(database, password_reset_tokens, email_verification_tokens)
            if s_count or t_count:
                log_with_time(f"[Cleanup] Removed {s_count} expired sessions, {t_count} expired tokens")
        except Exception as e:
            log_with_time(f"[Cleanup] Error: {e}")

    # Start scheduler only if this worker acquires the advisory lock (prevents thundering herd)
    _scheduler_lock_acquired = await acquire_scheduler_lock(database)
    if _scheduler_lock_acquired:
        setup_jobs(scheduler, scheduled_crawl_job, _cleanup_job)
        scheduler.start()
        print("[Startup] Database connected, scheduler started (lock acquired).")
    else:
        print("[Startup] Database connected, scheduler skipped (another worker holds lock).")

    # Schedule backfill as background task so server starts immediately
    _bt = asyncio.create_task(_backfill_articles())
    _background_tasks.add(_bt)
    _bt.add_done_callback(_background_tasks.discard)

    yield

    # --- Graceful shutdown: cancel tracked background tasks ---
    for task in list(_background_tasks):
        task.cancel()
    if _background_tasks:
        await asyncio.wait(_background_tasks, timeout=5.0)

    if _scheduler_lock_acquired:
        scheduler.shutdown()
        await release_scheduler_lock(database)
    await database.disconnect()
    print("[Shutdown] Database disconnected.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(lifespan=lifespan)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": str(exc)},
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
from routers.ai_tokens import router as ai_tokens_router
from routers.ai_providers import router as ai_providers_router
from routers.database import router as database_router
from routers.sites import router as sites_router
from routers.analytics import router as analytics_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(ai_tokens_router)
app.include_router(ai_providers_router)
app.include_router(database_router)
app.include_router(sites_router)
app.include_router(analytics_router)


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
        await database.execute(sqlalchemy.text("SELECT 1"))
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
        # Validate path components before constructing candidates
        path_parts = safe_path.split("/")
        for part in path_parts:
            if part == ".." or part.startswith("."):
                raise HTTPException(status_code=403, detail="Forbidden")

        requested = FRONTEND_DIR / safe_path
        if requested.is_file():
            candidates.append(requested)
        if (requested / "index.html").is_file():
            candidates.append(requested / "index.html")

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
