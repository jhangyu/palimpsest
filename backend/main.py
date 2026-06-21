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

from sqlalchemy import func, select, text, update
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
    engine, async_session_factory, metadata, DATABASE_URL,
    users, auth_sessions, password_reset_tokens, email_verification_tokens,
    articles, schema_versions, ai_tables,
)
from routers._deps import log_with_time
from routers.sites import _record_crawl_attempt, _background_tasks

# ---------------------------------------------------------------------------
# _run_all_migrations  (async, uses existing async engine via run_sync)
# ---------------------------------------------------------------------------


def _run_schema_migration_on_conn(connection) -> None:
    """Adapter: runs _run_schema_migration DDL on an existing sync connection.

    _run_schema_migration() expects an engine and opens its own connection.
    This wrapper provides the same DDL logic but on a pre-existing connection,
    for use with async engine's conn.run_sync().
    """
    from sqlalchemy import text as sa_text
    from datetime import datetime, timezone as _tz

    # Add new columns to articles if they don't exist
    for col, col_type in [("created_at", "VARCHAR"), ("updated_at", "VARCHAR"), ("word_count", "INTEGER")]:
        try:
            connection.execute(sa_text(f"ALTER TABLE articles ADD COLUMN IF NOT EXISTS {col} {col_type}"))
        except Exception as e:
            log_with_time(f"[Migration] Column articles.{col} migration note: {e}")

    # DD-10: Migrate articles timestamp columns from VARCHAR to TIMESTAMPTZ
    for col in ("published_at", "created_at", "updated_at"):
        try:
            connection.execute(sa_text(
                f"ALTER TABLE articles ALTER COLUMN {col} TYPE TIMESTAMPTZ "
                f"USING {col}::timestamptz"
            ))
        except Exception as e:
            # Column may already be TIMESTAMPTZ — safe to ignore
            err_str = str(e).lower()
            if "already" not in err_str and "same type" not in err_str:
                log_with_time(f"[Migration] articles.{col} TIMESTAMPTZ migration note: {e}")

    # --- Auth tables (CREATE TABLE IF NOT EXISTS) ---
    auth_table_stmts = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR NOT NULL UNIQUE,
            email_normalized VARCHAR NOT NULL UNIQUE,
            pending_email VARCHAR,
            pending_email_normalized VARCHAR,
            username VARCHAR NOT NULL UNIQUE,
            username_normalized VARCHAR NOT NULL UNIQUE,
            full_name VARCHAR,
            password_hash TEXT NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'active',
            email_verified_at TIMESTAMPTZ,
            avatar_mime_type VARCHAR,
            avatar_bytes BYTEA,
            avatar_size_bytes INTEGER,
            avatar_hash VARCHAR,
            avatar_source VARCHAR NOT NULL DEFAULT 'none',
            avatar_updated_at TIMESTAMPTZ,
            preferences JSON NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            last_login_at TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMPTZ NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, role_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            token_hash VARCHAR NOT NULL UNIQUE,
            user_agent TEXT,
            ip_address VARCHAR,
            created_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            token_hash VARCHAR NOT NULL UNIQUE,
            created_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS email_verification_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            token_hash VARCHAR NOT NULL UNIQUE,
            email VARCHAR NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS auth_rate_limits (
            id SERIAL PRIMARY KEY,
            scope VARCHAR NOT NULL,
            subject_hash VARCHAR NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            window_started_at TIMESTAMPTZ NOT NULL,
            locked_until TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL,
            UNIQUE(scope, subject_hash)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS schema_versions (
            id SERIAL PRIMARY KEY,
            version VARCHAR NOT NULL UNIQUE,
            description VARCHAR NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL
        )
        """,
    ]

    for stmt in auth_table_stmts:
        try:
            connection.execute(sa_text(stmt))
        except Exception as e:
            log_with_time(f"[Migration] Auth table creation note: {e}")

    # Create indexes if not exist
    index_stmts = [
        # Existing indexes
        "CREATE INDEX IF NOT EXISTS idx_articles_site_id ON articles(site_id)",
        "CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at)",
        "CREATE INDEX IF NOT EXISTS idx_rss_query_events_requested_at ON rss_query_events(requested_at)",
        "CREATE INDEX IF NOT EXISTS idx_crawl_attempts_started_at ON crawl_attempts(started_at)",
        "CREATE INDEX IF NOT EXISTS idx_crawl_attempts_site_started ON crawl_attempts(site_id, started_at)",
        # Auth indexes
        "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_expires ON auth_sessions(user_id, expires_at, revoked_at)",
        "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user ON password_reset_tokens(user_id, expires_at, used_at)",
        "CREATE INDEX IF NOT EXISTS idx_email_verification_tokens_user ON email_verification_tokens(user_id, expires_at, used_at)",
        "CREATE INDEX IF NOT EXISTS idx_auth_rate_limits_scope_locked ON auth_rate_limits(scope, locked_until)",
    ]

    for stmt in index_stmts:
        try:
            connection.execute(sa_text(stmt))
        except Exception as e:
            log_with_time(f"[Migration] Index creation note: {e}")

    # Partial unique indexes (PostgreSQL-specific)
    partial_idx_stmts = [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_pending_email_normalized ON users(pending_email_normalized) WHERE pending_email_normalized IS NOT NULL",
    ]
    for stmt in partial_idx_stmts:
        try:
            connection.execute(sa_text(stmt))
        except Exception as e:
            log_with_time(f"[Migration] Partial unique index note: {e}")

    # Seed roles if not exist
    try:
        now_ts = datetime.now(_tz.utc)
        connection.execute(sa_text(
            "INSERT INTO roles (name, description, created_at) VALUES (:name, :desc, :ts) ON CONFLICT (name) DO NOTHING"
        ), {"name": "admin", "desc": "Administrator role with full access", "ts": now_ts})
        connection.execute(sa_text(
            "INSERT INTO roles (name, description, created_at) VALUES (:name, :desc, :ts) ON CONFLICT (name) DO NOTHING"
        ), {"name": "user", "desc": "Standard user role", "ts": now_ts})
    except Exception as e:
        log_with_time(f"[Migration] Role seeding note: {e}")

    log_with_time("[Migration] Schema migration completed.")


async def _run_all_migrations() -> None:
    """Run all DDL migrations using the existing async engine.

    Uses conn.run_sync() to run sync DDL functions within the async engine's
    connection, eliminating the need for a separate sync PostgreSQL driver.
    """
    async with engine.begin() as conn:
        # Create tables if not exist
        await conn.run_sync(metadata.create_all)

        # Run schema migration (ALTER TABLE statements, auth tables, indexes, role seeding)
        await conn.run_sync(_run_schema_migration_on_conn)

        # AI provider schema expansion
        for stmt_text in SCHEMA_EXPANSION_STATEMENTS:
            try:
                await conn.execute(text(stmt_text))
            except Exception as e:
                log_with_time(f"[Migration] AI provider schema expansion note: {e}")
        log_with_time("[Migration] AI provider schema expansion completed.")

        # Crawl repair tables
        from core.crawl_repair_models import migrate_crawl_repair_tables
        await conn.run_sync(migrate_crawl_repair_tables)
        log_with_time("[Migration] Crawl repair schema expansion completed.")

        # Filter rules column
        try:
            await conn.execute(text("ALTER TABLE sites ADD COLUMN IF NOT EXISTS filter_rules JSONB"))
        except Exception as e:
            log_with_time(f"[Migration] filter_rules column note: {e}")
        log_with_time("[Migration] Filter rules schema migration completed.")

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
    """排程任務：取出所有網站並並行執行爬蟲（最多 5 個同時進行）"""
    print("[Scheduler] Running scheduled crawl...")
    async with async_session_factory() as session:
        all_sites = await get_sites_with_owner_status(session)
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
                )
            except Exception as e:
                print(f"[Scheduler] Error crawling site {site['id']}: {e}")

    await asyncio.gather(*[crawl_with_limit(s) for s in all_sites])


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
