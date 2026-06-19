# backend/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks, Response, Request, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel, field_validator
import databases
import sqlalchemy
from typing import Optional
import json
import os
import asyncio
import re
import time
import statistics
import hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import zipfile
import io
from dotenv import load_dotenv
from dateutil import parser as dateutil_parser

# Load .env file
load_dotenv()

# Fixed imports: use core module
from core.ai import analyze_with_providers
from core.crawler import crawl_site_logic, get_page_content, compute_visible_word_count, _utcnow_iso as _utcnow_iso_impl
from core.scraper import fetch_page
from core.debug import create_debug_writer

# Auth imports
from core.auth import (
    hash_password, verify_password, needs_rehash,
    generate_session_token, hash_token,
    generate_csrf_token, validate_csrf, check_origin,
    set_session_cookie, clear_session_cookie, set_csrf_cookie, clear_csrf_cookie,
    generate_reset_token,
    validate_username, normalize_username, validate_password, normalize_email,
    check_rate_limit, record_attempt, clear_rate_limit,
    cleanup_expired_sessions, cleanup_expired_tokens,
    make_get_current_user, make_require_user, make_require_admin,
)
from core.crypto import (
    encrypt_token as crypto_encrypt_token,
    decrypt_token as crypto_decrypt_token,
    generate_token_salt, mask_token, get_token_last4,
    re_encrypt_all_user_tokens,
)
from core.email import get_email_sender
from core.security_models import (
    LoginRequest, RegisterRequest, FirstRunSetupRequest,
    ForgotPasswordRequest, ResetPasswordRequest, VerifyEmailRequest,
    ResendVerificationRequest,
    UpdateProfileRequest, UpdateEmailRequest, UpdateUsernameRequest,
    ChangePasswordRequest, UpdatePreferencesRequest,
    UserResponse, UserMeResponse,
    AdminCreateUserRequest, AdminUpdateUserRequest, AdminUserListResponse,
    AdminUpdateRolesRequest,
    CreateTokenRequest, UpdateTokenRequest, RevealTokenRequest, TestTokenRequest,
    TokenResponse,
)
from core.ai_tokens import (
    list_user_tokens,
    create_user_token,
    update_user_token,
    delete_user_token,
    reveal_user_token,
    test_user_token,
    set_default_token,
    resolve_minimax_token,
)
from core.ai_providers import (
    list_user_providers,
    create_provider,
    update_provider,
    delete_provider,
    reorder_providers,
    discover_models,
    test_provider_connection,
    reveal_api_key,
    toggle_provider_enabled,
    get_runtime_status,
    ProviderNotFoundError,
    ProviderRevisionConflictError,
    ProviderLabelConflictError,
    ProviderOwnershipError,
)
from core.ai_provider_migrations import (
    define_ai_provider_tables,
    SCHEMA_EXPANSION_STATEMENTS,
    bootstrap_user_secret_key,
    backfill_existing_user_secret_keys,
    backfill_site_owners,
)
from core.llm.key_backends import FileKeyEncryptionBackend
from core.llm.service import NoProviderAvailableError
from core.ownership import (
    check_site_owner_or_admin,
    ownership_transfer_gate,
    get_sites_with_owner_status,
    verify_transfer_target,
)

# Helper for timestamped logging
def log_with_time(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

# Shared helpers imported from core.crawler (canonical location)
_utcnow_iso = _utcnow_iso_impl



from apscheduler.schedulers.asyncio import AsyncIOScheduler
from rfeed import Item, Feed

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://palimpsest:palimpsest@db:5432/palimpsest")
database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

# --- Database Schema ---
sites = sqlalchemy.Table(
    "sites", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("url", sqlalchemy.String),
    sqlalchemy.Column("name", sqlalchemy.String),
    sqlalchemy.Column("list_rules", sqlalchemy.JSON),
    sqlalchemy.Column("content_rules", sqlalchemy.JSON),
    # NEW: For self-healing mechanism
    sqlalchemy.Column("consecutive_failure_count", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("refresh_frequency", sqlalchemy.Integer, default=60), # In minutes
    sqlalchemy.Column("scrape_method", sqlalchemy.String, default="scrapling"),
)

articles = sqlalchemy.Table(
    "articles", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("site_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("sites.id")),
    sqlalchemy.Column("title", sqlalchemy.String),
    sqlalchemy.Column("url", sqlalchemy.String, unique=True),
    sqlalchemy.Column("content", sqlalchemy.Text),
    sqlalchemy.Column("image_url", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("author", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("published_at", sqlalchemy.String),
    # Analytics columns
    sqlalchemy.Column("created_at", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("updated_at", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("word_count", sqlalchemy.Integer, nullable=True),
)

rss_query_events = sqlalchemy.Table(
    "rss_query_events", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("site_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("sites.id"), nullable=True),
    sqlalchemy.Column("site_identifier", sqlalchemy.String),
    sqlalchemy.Column("requested_at", sqlalchemy.String),
    sqlalchemy.Column("limit_param", sqlalchemy.Integer),
    sqlalchemy.Column("status_code", sqlalchemy.Integer),
)

crawl_attempts = sqlalchemy.Table(
    "crawl_attempts", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("site_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("sites.id")),
    sqlalchemy.Column("started_at", sqlalchemy.String),
    sqlalchemy.Column("finished_at", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("trigger_type", sqlalchemy.String),  # manual / scheduled
    sqlalchemy.Column("status", sqlalchemy.String),  # success / fail / running
    sqlalchemy.Column("articles_found", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("articles_saved", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("articles_updated", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("articles_failed", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("content_fetch_failed", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("parse_failed", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("error_message", sqlalchemy.Text, nullable=True),
)

# --- Auth / User / Role Tables ---

users = sqlalchemy.Table(
    "users", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("email", sqlalchemy.String, nullable=False, unique=True),
    sqlalchemy.Column("email_normalized", sqlalchemy.String, nullable=False, unique=True),
    sqlalchemy.Column("pending_email", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("pending_email_normalized", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("username", sqlalchemy.String, nullable=False, unique=True),
    sqlalchemy.Column("username_normalized", sqlalchemy.String, nullable=False, unique=True),
    sqlalchemy.Column("full_name", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("password_hash", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column("status", sqlalchemy.String, nullable=False, server_default="active"),
    sqlalchemy.Column("email_verified_at", sqlalchemy.DateTime(timezone=True), nullable=True),
    sqlalchemy.Column("avatar_mime_type", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("avatar_bytes", sqlalchemy.LargeBinary, nullable=True),
    sqlalchemy.Column("avatar_size_bytes", sqlalchemy.Integer, nullable=True),
    sqlalchemy.Column("avatar_hash", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("avatar_source", sqlalchemy.String, nullable=False, server_default="none"),
    sqlalchemy.Column("avatar_updated_at", sqlalchemy.DateTime(timezone=True), nullable=True),
    sqlalchemy.Column("preferences", sqlalchemy.JSON, nullable=False, server_default="{}"),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column("updated_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column("last_login_at", sqlalchemy.DateTime(timezone=True), nullable=True),
)

roles = sqlalchemy.Table(
    "roles", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String, nullable=False, unique=True),
    sqlalchemy.Column("description", sqlalchemy.Text, nullable=True),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime(timezone=True), nullable=False),
)

user_roles = sqlalchemy.Table(
    "user_roles", metadata,
    sqlalchemy.Column("user_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    sqlalchemy.Column("role_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

auth_sessions = sqlalchemy.Table(
    "auth_sessions", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("user_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id", ondelete="CASCADE")),
    sqlalchemy.Column("token_hash", sqlalchemy.String, nullable=False, unique=True),
    sqlalchemy.Column("user_agent", sqlalchemy.Text, nullable=True),
    sqlalchemy.Column("ip_address", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column("expires_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column("revoked_at", sqlalchemy.DateTime(timezone=True), nullable=True),
)

password_reset_tokens = sqlalchemy.Table(
    "password_reset_tokens", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("user_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id", ondelete="CASCADE")),
    sqlalchemy.Column("token_hash", sqlalchemy.String, nullable=False, unique=True),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column("expires_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column("used_at", sqlalchemy.DateTime(timezone=True), nullable=True),
)

email_verification_tokens = sqlalchemy.Table(
    "email_verification_tokens", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("user_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id", ondelete="CASCADE")),
    sqlalchemy.Column("token_hash", sqlalchemy.String, nullable=False, unique=True),
    sqlalchemy.Column("email", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column("expires_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column("used_at", sqlalchemy.DateTime(timezone=True), nullable=True),
)

auth_rate_limits = sqlalchemy.Table(
    "auth_rate_limits", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("scope", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("subject_hash", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("attempts", sqlalchemy.Integer, nullable=False, server_default="0"),
    sqlalchemy.Column("window_started_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column("locked_until", sqlalchemy.DateTime(timezone=True), nullable=True),
    sqlalchemy.Column("updated_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.UniqueConstraint("scope", "subject_hash", name="uq_rate_limits_scope_subject"),
)

user_ai_tokens = sqlalchemy.Table(
    "user_ai_tokens", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("user_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id", ondelete="CASCADE")),
    sqlalchemy.Column("provider", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("label", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("encrypted_token", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column("token_salt", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("token_last4", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("token_mask", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("needs_reentry", sqlalchemy.Boolean, nullable=False, server_default="false"),
    sqlalchemy.Column("is_default", sqlalchemy.Boolean, nullable=False, server_default="false"),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column("updated_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column("last_used_at", sqlalchemy.DateTime(timezone=True), nullable=True),
    sqlalchemy.UniqueConstraint("user_id", "provider", "label", name="uq_user_ai_tokens_user_provider_label"),
)

schema_versions = sqlalchemy.Table(
    "schema_versions", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("version", sqlalchemy.String, nullable=False, unique=True),
    sqlalchemy.Column("description", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("applied_at", sqlalchemy.DateTime(timezone=True), nullable=False),
)

# --- AI Provider Tables ---
_ai_tables = define_ai_provider_tables(metadata)

_kek_backend: FileKeyEncryptionBackend | None = None

# --- App Version & Migration Registry ---
APP_VERSION = "0.1.0"

MIGRATIONS = [
    # {"version": "0.2.0", "description": "Add xyz column", "up": async_migration_fn},
]

# --- Scheduler ---
scheduler = AsyncIOScheduler()

async def _record_crawl_attempt(site_id: int, trigger_type: str, url: str, list_rules: dict, content_rules: dict, force_update: bool, scrape_method: str, debug_writer=None, owner_user_id=None):
    """Wrapper that records a crawl attempt around crawl_site_logic."""
    attempt_id = None
    try:
        attempt_id = await database.execute(
            crawl_attempts.insert().values(
                site_id=site_id,
                started_at=_utcnow_iso(),
                trigger_type=trigger_type,
                status="running",
                articles_found=0, articles_saved=0, articles_updated=0,
                articles_failed=0, content_fetch_failed=0, parse_failed=0,
            )
        )
    except Exception as e:
        log_with_time(f"[CrawlAttempt] Failed to create attempt record: {e}")

    crawl_result = await crawl_site_logic(
        site_id=site_id,
        url=url,
        list_rules=list_rules,
        content_rules=content_rules,
        db=database,
        debug_writer=debug_writer,
        force_update=force_update,
        scrape_method=scrape_method,
        owner_user_id=owner_user_id,
        ai_tables=_ai_tables,
        kek_backend=_kek_backend,
    )

    if crawl_result is None:
        crawl_result = {"status": "fail", "articles_found": 0, "articles_saved": 0,
                        "articles_updated": 0, "articles_failed": 0,
                        "content_fetch_failed": 0, "parse_failed": 0,
                        "error_message": "crawl_site_logic returned None"}

    if attempt_id is not None:
        try:
            await database.execute(
                crawl_attempts.update().where(crawl_attempts.c.id == attempt_id).values(
                    finished_at=_utcnow_iso(),
                    status=crawl_result.get("status", "fail"),
                    articles_found=crawl_result.get("articles_found", 0),
                    articles_saved=crawl_result.get("articles_saved", 0),
                    articles_updated=crawl_result.get("articles_updated", 0),
                    articles_failed=crawl_result.get("articles_failed", 0),
                    content_fetch_failed=crawl_result.get("content_fetch_failed", 0),
                    parse_failed=crawl_result.get("parse_failed", 0),
                    error_message=crawl_result.get("error_message"),
                )
            )
        except Exception as e:
            log_with_time(f"[CrawlAttempt] Failed to update attempt record: {e}")

    return crawl_result

async def scheduled_crawl_job():
    """排程任務：取出所有網站並執行爬蟲（排程模式：只更新時間改變的文章）"""
    print("[Scheduler] Running scheduled crawl...")
    all_sites = await get_sites_with_owner_status(database)
    for site in all_sites:
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
            )
        except Exception as e:
            print(f"[Scheduler] Error crawling site {site['id']}: {e}")

# --- Schema Migration Helpers ---
def _run_schema_migration(engine):
    """Idempotent schema upgrade for existing databases."""
    from sqlalchemy import text as sa_text

    with engine.connect() as conn:
        # Add new columns to articles if they don't exist
        for col, col_type in [("created_at", "VARCHAR"), ("updated_at", "VARCHAR"), ("word_count", "INTEGER")]:
            try:
                conn.execute(sa_text(f"ALTER TABLE articles ADD COLUMN IF NOT EXISTS {col} {col_type}"))
            except Exception as e:
                log_with_time(f"[Migration] Column articles.{col} migration note: {e}")

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
            CREATE TABLE IF NOT EXISTS user_ai_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                provider VARCHAR NOT NULL,
                label VARCHAR NOT NULL,
                encrypted_token TEXT NOT NULL,
                token_salt VARCHAR NOT NULL,
                token_last4 VARCHAR,
                token_mask VARCHAR,
                needs_reentry BOOLEAN NOT NULL DEFAULT false,
                is_default BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                last_used_at TIMESTAMPTZ,
                UNIQUE(user_id, provider, label)
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
                conn.execute(sa_text(stmt))
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
            "CREATE INDEX IF NOT EXISTS idx_user_ai_tokens_user_provider ON user_ai_tokens(user_id, provider)",
        ]

        for stmt in index_stmts:
            try:
                conn.execute(sa_text(stmt))
            except Exception as e:
                log_with_time(f"[Migration] Index creation note: {e}")

        # Partial unique indexes (PostgreSQL-specific)
        partial_idx_stmts = [
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_pending_email_normalized ON users(pending_email_normalized) WHERE pending_email_normalized IS NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_ai_tokens_default ON user_ai_tokens(user_id, provider) WHERE is_default = true",
        ]
        for stmt in partial_idx_stmts:
            try:
                conn.execute(sa_text(stmt))
            except Exception as e:
                log_with_time(f"[Migration] Partial unique index note: {e}")

        # Seed roles if not exist
        try:
            now_str = datetime.now(timezone.utc).isoformat()
            conn.execute(sa_text(
                "INSERT INTO roles (name, description, created_at) VALUES (:name, :desc, :ts) ON CONFLICT (name) DO NOTHING"
            ), {"name": "admin", "desc": "Administrator role with full access", "ts": now_str})
            conn.execute(sa_text(
                "INSERT INTO roles (name, description, created_at) VALUES (:name, :desc, :ts) ON CONFLICT (name) DO NOTHING"
            ), {"name": "user", "desc": "Standard user role", "ts": now_str})
        except Exception as e:
            log_with_time(f"[Migration] Role seeding note: {e}")

        conn.commit()
    log_with_time("[Migration] Schema migration completed.")

async def _backfill_articles():
    """Backfill created_at, updated_at, word_count for existing articles with NULL values."""
    log_with_time("[Backfill] Starting article backfill...")

    # Backfill created_at / updated_at
    rows = await database.fetch_all("SELECT id, published_at FROM articles WHERE created_at IS NULL LIMIT 500")
    if rows:
        log_with_time(f"[Backfill] Backfilling created_at/updated_at for {len(rows)} articles...")
        for row in rows:
            ts = None
            if row['published_at']:
                try:
                    parsed = dateutil_parser.parse(row['published_at'])
                    ts = parsed.isoformat()
                    if not parsed.tzinfo:
                        ts = ts + "Z"
                except Exception:
                    pass
            if ts is None:
                ts = _utcnow_iso()
            try:
                await database.execute(
                    "UPDATE articles SET created_at = :ts, updated_at = :ts WHERE id = :id AND created_at IS NULL",
                    values={"ts": ts, "id": row['id']}
                )
            except Exception as e:
                log_with_time(f"[Backfill] Warning: failed to backfill article {row['id']}: {e}")

    # Backfill word_count
    wc_rows = await database.fetch_all("SELECT id, content FROM articles WHERE word_count IS NULL AND content IS NOT NULL LIMIT 500")
    if wc_rows:
        log_with_time(f"[Backfill] Backfilling word_count for {len(wc_rows)} articles...")
        for row in wc_rows:
            try:
                wc = compute_visible_word_count(row['content'])
                await database.execute(
                    "UPDATE articles SET word_count = :wc WHERE id = :id AND word_count IS NULL",
                    values={"wc": wc, "id": row['id']}
                )
            except Exception as e:
                log_with_time(f"[Backfill] Warning: failed to compute word_count for article {row['id']}: {e}")

    log_with_time("[Backfill] Article backfill completed.")


# --- Lifespan (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    # Create tables if not exist
    sync_url = DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql://")
    engine = sqlalchemy.create_engine(sync_url)

    metadata.create_all(engine)

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

    # --- KEK backend init ---
    global _kek_backend
    kek_path = os.getenv("LLM_KEK_PATH", "/run/secrets/llm_kek")
    kek_version = os.getenv("LLM_KEK_VERSION", "v1")
    try:
        _kek_backend = FileKeyEncryptionBackend(kek_path, kek_version)
        log_with_time(f"[Startup] KEK backend initialized from {kek_path} (version={kek_version})")
    except Exception as e:
        log_with_time(f"[Startup] KEK backend unavailable ({e}); AI provider features disabled")
        _kek_backend = None

    # --- Backfill user secret keys and site owners ---
    if _kek_backend is not None:
        try:
            await backfill_existing_user_secret_keys(database, users, _ai_tables.user_secret_keys, _kek_backend)
            log_with_time("[Startup] User secret key backfill completed.")
        except Exception as e:
            log_with_time(f"[Startup] User secret key backfill note: {e}")
        try:
            result = await backfill_site_owners(database)
            log_with_time(f"[Startup] Site owner backfill: {result.status.value}")
        except Exception as e:
            log_with_time(f"[Startup] Site owner backfill note: {e}")

    # Backfill existing articles
    await _backfill_articles()

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
    user_count = await database.fetch_one("SELECT COUNT(*) as cnt FROM users")
    if user_count and user_count["cnt"] == 0:
        log_with_time("[Startup] First-run setup required: no users found. POST /auth/first-run-setup to create admin.")

    # Start scheduler with stagger to prevent thundering herd
    scheduler.add_job(scheduled_crawl_job, 'interval', hours=1, jitter=300)
    # Add session/token cleanup job (daily)
    async def _cleanup_job():
        try:
            s_count = await cleanup_expired_sessions(database, auth_sessions)
            t_count = await cleanup_expired_tokens(database, password_reset_tokens, email_verification_tokens)
            if s_count or t_count:
                log_with_time(f"[Cleanup] Removed {s_count} expired sessions, {t_count} expired tokens")
        except Exception as e:
            log_with_time(f"[Cleanup] Error: {e}")
    scheduler.add_job(_cleanup_job, 'interval', hours=24, jitter=3600)
    scheduler.start()
    print("[Startup] Database connected, scheduler started.")
    yield
    scheduler.shutdown()
    await database.disconnect()
    print("[Shutdown] Database disconnected.")

app = FastAPI(lifespan=lifespan)

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

FRONTEND_DIR = Path(
    os.getenv("PALIMPSEST_FRONTEND_DIR", Path(__file__).resolve().parent.parent / "frontend-astro")
).resolve()

# --- Auth Dependencies ---
_get_current_user = make_get_current_user(database, users, user_roles, roles, auth_sessions)
_require_user = make_require_user(_get_current_user)
_require_admin = make_require_admin(_require_user)

# Frontend origin for constructing links
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5174")

# Session TTL
def _session_ttl_hours() -> int:
    return int(os.getenv("SESSION_TTL_HOURS", "24"))


def _require_kek() -> FileKeyEncryptionBackend:
    if _kek_backend is None:
        raise HTTPException(status_code=503, detail="AI provider encryption not configured")
    return _kek_backend


# --- Helper Functions ---
def normalize_site_name(name: str) -> str:
    """將網站名稱標準化為 URL 友好的格式"""
    # 替換空白為底線
    name = name.replace(' ', '_')
    # 移除非英文數字底線的字元
    name = re.sub(r'[^a-zA-Z0-9_\-]', '', name)
    # 轉小寫
    name = name.lower()
    return name

async def get_site_by_name_or_id(site_identifier: str, database):
    """根據名稱或 ID 查詢網站"""
    # 先嘗試當作 ID 查詢
    try:
        site_id = int(site_identifier)
        query = sites.select().where(sites.c.id == site_id)
        site = await database.fetch_one(query)
        if site:
            return site
    except ValueError:
        pass

    # 嘗試當作名稱查詢
    normalized = normalize_site_name(site_identifier)
    query = sites.select()
    all_sites = await database.fetch_all(query)
    for site in all_sites:
        if normalize_site_name(site['name']) == normalized:
            return site
    return None

# --- Auth Helper: create session and set cookies ---
async def _create_session_and_cookies(response: Response, request: Request, user_id: int) -> str:
    """Create a session, set session + CSRF cookies. Returns the session token."""
    now = datetime.now(timezone.utc)
    session_token = generate_session_token()
    token_hash_val = hash_token(session_token)
    csrf_token = generate_csrf_token()

    await database.execute(
        auth_sessions.insert().values(
            user_id=user_id,
            token_hash=token_hash_val,
            user_agent=request.headers.get("user-agent", "")[:500],
            ip_address=request.client.host if request.client else None,
            created_at=now,
            expires_at=now + timedelta(hours=_session_ttl_hours()),
        )
    )

    set_session_cookie(response, session_token)
    set_csrf_cookie(response, csrf_token)
    return session_token


def _user_to_response(user_row: dict, user_roles_list: list[str]) -> dict:
    """Convert a user DB row to a response dict."""
    return {
        "id": user_row["id"],
        "email": user_row["email"],
        "username": user_row["username"],
        "full_name": user_row["full_name"],
        "status": user_row["status"],
        "email_verified_at": user_row["email_verified_at"].isoformat() if user_row["email_verified_at"] else None,
        "avatar_source": user_row["avatar_source"] or "none",
        "avatar_hash": user_row["avatar_hash"],
        "created_at": user_row["created_at"].isoformat() if user_row["created_at"] else None,
        "updated_at": user_row["updated_at"].isoformat() if user_row["updated_at"] else None,
        "last_login_at": user_row["last_login_at"].isoformat() if user_row["last_login_at"] else None,
        "roles": user_roles_list,
    }


def _user_to_me_response(user_row: dict, user_roles_list: list[str]) -> dict:
    """Convert a user DB row to a 'me' response dict (includes pending_email, preferences)."""
    resp = _user_to_response(user_row, user_roles_list)
    resp["pending_email"] = user_row.get("pending_email")
    resp["preferences"] = user_row.get("preferences") or {}
    return resp


async def _get_user_roles(user_id: int) -> list[str]:
    """Fetch role names for a user."""
    role_rows = await database.fetch_all(
        user_roles.select().where(user_roles.c.user_id == user_id)
    )
    role_ids = [r["role_id"] for r in role_rows]
    if not role_ids:
        return []
    from sqlalchemy import select
    all_roles = await database.fetch_all(
        select(roles).where(roles.c.id.in_(role_ids))
    )
    return [r["name"] for r in all_roles]


# --- CSRF dependency for state-changing endpoints ---
async def _csrf_dependency(request: Request):
    """CSRF validation dependency for state-changing routes."""
    validate_csrf(request)


# --- Pydantic Models (existing) ---
class SiteCreate(BaseModel):
    url: str
    name: str
    refresh_frequency: Optional[int] = 60
    scrape_method: Optional[str] = "scrapling"

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

class SiteUpdate(BaseModel):
    url: Optional[str] = None
    name: Optional[str] = None
    refresh_frequency: Optional[int] = None
    list_rules: Optional[dict] = None
    content_rules: Optional[dict] = None
    scrape_method: Optional[str] = None

class RulesInput(BaseModel):
    list_rules: dict
    content_rules: dict

class PreviewRequest(BaseModel):
    url: str
    list_rules: dict
    content_rules: dict
    mode: Optional[str] = "both"  # "list", "content", or "both"
    target_url: Optional[str] = None  # 用於 content 模式下的單篇文章測試
    debug: Optional[bool] = False
    scrape_method: Optional[str] = "scrapling"

# --- AI Provider Request Models ---
class CreateProviderRequest(BaseModel):
    label: str
    protocol: str
    base_url: str
    model: str
    api_key: str
    temperature: float | None = None
    max_tokens: int = 4096
    thinking: bool = False
    effort: str = "low"

class UpdateProviderRequest(BaseModel):
    revision: int
    label: str | None = None
    protocol: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    thinking: bool | None = None
    effort: str | None = None

class DeleteProviderRequest(BaseModel):
    revision: int

class ReorderProvidersRequest(BaseModel):
    ordered_ids: list[int]
    revision: int

class ToggleProviderEnabledRequest(BaseModel):
    enabled: bool

class DiscoverModelsRequest(BaseModel):
    protocol: str
    base_url: str
    api_key: str | None = None
    provider_id: int | None = None

class RevealProviderKeyRequest(BaseModel):
    current_password: str

# --- Analytics Helpers ---

def _parse_iso_to_taipei_date(iso_str: str) -> str | None:
    """Parse an ISO timestamp string and return its Asia/Taipei date as YYYY-MM-DD."""
    if not iso_str:
        return None
    try:
        dt = dateutil_parser.parse(iso_str)
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        taipei_dt = dt.astimezone(TAIPEI_TZ)
        return taipei_dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def _get_date_range(days: int) -> list[str]:
    """Generate a list of YYYY-MM-DD strings for the past N days in Asia/Taipei timezone."""
    today = datetime.now(TAIPEI_TZ).date()
    return [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

def _get_week_boundaries():
    """Get ISO week start (Monday) and end for this week and last week in Asia/Taipei."""
    now_taipei = datetime.now(TAIPEI_TZ)
    today = now_taipei.date()
    # This week: Monday to today
    this_week_start = today - timedelta(days=today.weekday())
    # Last week
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start - timedelta(days=1)
    return this_week_start, today, last_week_start, last_week_end


# ============================================================
# AUTH ENDPOINTS
# ============================================================

@app.post("/auth/first-run-setup")
async def first_run_setup(req: FirstRunSetupRequest, request: Request, response: Response):
    """Create the first admin user. Only works when users table is empty."""
    check_origin(request)

    user_count = await database.fetch_one("SELECT COUNT(*) as cnt FROM users")
    if user_count and user_count["cnt"] > 0:
        raise HTTPException(status_code=409, detail="Setup already completed. Users exist.")

    # Validate
    valid, err = validate_username(req.username)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    valid, err = validate_password(req.password)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    email_norm = normalize_email(req.email)
    username_norm = normalize_username(req.username)
    now = datetime.now(timezone.utc)

    pw_hash = hash_password(req.password)

    user_id = await database.execute(
        users.insert().values(
            email=req.email.strip(),
            email_normalized=email_norm,
            username=username_norm,
            username_normalized=username_norm,
            full_name=req.full_name,
            password_hash=pw_hash,
            status="active",
            email_verified_at=now,
            avatar_source="none",
            preferences={},
            created_at=now,
            updated_at=now,
        )
    )

    # Assign admin role
    admin_role = await database.fetch_one(roles.select().where(roles.c.name == "admin"))
    if admin_role:
        await database.execute(user_roles.insert().values(user_id=user_id, role_id=admin_role["id"]))
    # Also assign user role
    user_role = await database.fetch_one(roles.select().where(roles.c.name == "user"))
    if user_role:
        await database.execute(user_roles.insert().values(user_id=user_id, role_id=user_role["id"]))

    # Create session
    await _create_session_and_cookies(response, request, user_id)

    log_with_time(f"[Auth] First-run admin created: {username_norm}")
    return {"status": "ok", "message": "Admin account created", "user_id": user_id}


@app.post("/auth/login")
async def auth_login(req: LoginRequest, request: Request, response: Response):
    """Authenticate user and create session."""
    check_origin(request)

    email_norm = normalize_email(req.email)

    # Rate limit check
    allowed, retry_after = await check_rate_limit(database, auth_rate_limits, "login", email_norm)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many attempts. Try again in {retry_after} seconds.")

    # Find user
    user = await database.fetch_one(
        users.select().where(users.c.email_normalized == email_norm)
    )

    if not user or not verify_password(req.password, user["password_hash"]):
        await record_attempt(database, auth_rate_limits, "login", email_norm)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user["status"] != "active":
        raise HTTPException(status_code=403, detail="Account is not active")

    # Clear rate limit on success
    await clear_rate_limit(database, auth_rate_limits, "login", email_norm)

    # Rehash if needed
    if needs_rehash(user["password_hash"]):
        new_hash = hash_password(req.password)
        await database.execute(
            users.update().where(users.c.id == user["id"]).values(password_hash=new_hash)
        )

    # Update last_login_at
    now = datetime.now(timezone.utc)
    await database.execute(
        users.update().where(users.c.id == user["id"]).values(last_login_at=now)
    )

    # Create session
    await _create_session_and_cookies(response, request, user["id"])

    user_roles_list = await _get_user_roles(user["id"])
    return _user_to_me_response(dict(user), user_roles_list)


@app.post("/auth/logout", dependencies=[Depends(_csrf_dependency)])
async def auth_logout(request: Request, response: Response, current_user: dict = Depends(_require_user)):
    """Logout: revoke current session."""
    session_id = current_user.get("_session_id")
    if session_id:
        now = datetime.now(timezone.utc)
        await database.execute(
            auth_sessions.update().where(auth_sessions.c.id == session_id).values(revoked_at=now)
        )

    clear_session_cookie(response)
    clear_csrf_cookie(response)
    return {"status": "ok", "message": "Logged out"}


@app.get("/auth/me")
async def auth_me(request: Request):
    """Get current user info. Returns 401 if not authenticated."""
    user = await _get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _user_to_me_response(user, user.get("roles", []))


@app.post("/auth/register")
async def auth_register(req: RegisterRequest, request: Request, response: Response):
    """Register a new user (only if public registration is enabled)."""
    check_origin(request)

    allow_registration = os.getenv("AUTH_ALLOW_PUBLIC_REGISTRATION", "false").lower() in ("true", "1", "yes")
    if not allow_registration:
        raise HTTPException(status_code=403, detail="Public registration is disabled")

    # Validate
    valid, err = validate_username(req.username)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    valid, err = validate_password(req.password)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    email_norm = normalize_email(req.email)
    username_norm = normalize_username(req.username)

    # Check email uniqueness
    existing = await database.fetch_one(
        users.select().where(users.c.email_normalized == email_norm)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Check username uniqueness
    existing = await database.fetch_one(
        users.select().where(users.c.username_normalized == username_norm)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    now = datetime.now(timezone.utc)
    pw_hash = hash_password(req.password)

    user_id = await database.execute(
        users.insert().values(
            email=req.email.strip(),
            email_normalized=email_norm,
            username=username_norm,
            username_normalized=username_norm,
            full_name=req.full_name,
            password_hash=pw_hash,
            status="active",
            avatar_source="none",
            preferences={},
            created_at=now,
            updated_at=now,
        )
    )

    # Assign user role
    user_role = await database.fetch_one(roles.select().where(roles.c.name == "user"))
    if user_role:
        await database.execute(user_roles.insert().values(user_id=user_id, role_id=user_role["id"]))

    # Create session
    await _create_session_and_cookies(response, request, user_id)

    user_row = await database.fetch_one(users.select().where(users.c.id == user_id))
    if user_row is None:
        raise HTTPException(status_code=500, detail="User not found after creation")
    user_roles_list = await _get_user_roles(user_id)
    return _user_to_me_response(dict(user_row), user_roles_list)


@app.post("/auth/forgot-password")
async def auth_forgot_password(req: ForgotPasswordRequest, request: Request):
    """Request a password reset. Always returns success (generic response)."""
    check_origin(request)

    email_norm = normalize_email(req.email)

    # Rate limit
    allowed, retry_after = await check_rate_limit(database, auth_rate_limits, "forgot_password", email_norm)
    if not allowed:
        # Still return generic success to avoid enumeration
        return {"status": "ok", "message": "If an account exists, a reset link has been sent."}

    await record_attempt(database, auth_rate_limits, "forgot_password", email_norm)

    user = await database.fetch_one(
        users.select().where(users.c.email_normalized == email_norm)
    )

    if user and user["status"] == "active":
        # Revoke any existing unused reset tokens for this user
        now = datetime.now(timezone.utc)
        await database.execute(
            password_reset_tokens.update()
            .where(
                (password_reset_tokens.c.user_id == user["id"]) &
                (password_reset_tokens.c.used_at.is_(None))
            )
            .values(used_at=now)
        )

        # Generate new token
        token = generate_reset_token()
        token_hash_val = hash_token(token)
        expires_at = now + timedelta(hours=4)

        await database.execute(
            password_reset_tokens.insert().values(
                user_id=user["id"],
                token_hash=token_hash_val,
                created_at=now,
                expires_at=expires_at,
            )
        )

        # Send email (dev mode: log)
        reset_link = f"{FRONTEND_ORIGIN}/authentication/modern/new-password?token={token}"
        email_sender = get_email_sender()
        await email_sender.send_reset_email(user["email"], reset_link)

    # Always return generic success
    return {"status": "ok", "message": "If an account exists, a reset link has been sent."}


@app.post("/auth/reset-password")
async def auth_reset_password(req: ResetPasswordRequest, request: Request):
    """Reset password using a valid token."""
    check_origin(request)

    # Rate limit
    allowed, retry_after = await check_rate_limit(database, auth_rate_limits, "reset_password", req.token[:16])
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many attempts. Try again in {retry_after} seconds.")

    # Validate new password
    valid, err = validate_password(req.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    token_hash_val = hash_token(req.token)
    now = datetime.now(timezone.utc)

    # Find valid token
    token_row = await database.fetch_one(
        password_reset_tokens.select().where(
            (password_reset_tokens.c.token_hash == token_hash_val) &
            (password_reset_tokens.c.expires_at > now) &
            (password_reset_tokens.c.used_at.is_(None))
        )
    )

    if not token_row:
        await record_attempt(database, auth_rate_limits, "reset_password", req.token[:16])
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    # Mark token as used
    await database.execute(
        password_reset_tokens.update()
        .where(password_reset_tokens.c.id == token_row["id"])
        .values(used_at=now)
    )

    # Update password
    new_hash = hash_password(req.new_password)
    await database.execute(
        users.update()
        .where(users.c.id == token_row["user_id"])
        .values(password_hash=new_hash, updated_at=now)
    )

    # Mark AI tokens as needs_reentry (password reset cannot re-encrypt since old password is unknown)
    await database.execute(
        user_ai_tokens.update()
        .where(user_ai_tokens.c.user_id == token_row["user_id"])
        .values(needs_reentry=True, updated_at=now)
    )

    # Revoke all sessions for this user
    await database.execute(
        auth_sessions.update()
        .where(
            (auth_sessions.c.user_id == token_row["user_id"]) &
            (auth_sessions.c.revoked_at.is_(None))
        )
        .values(revoked_at=now)
    )

    return {"status": "ok", "message": "Password has been reset. Please login."}


@app.post("/auth/verify-email")
async def auth_verify_email(req: VerifyEmailRequest, request: Request):
    """Verify a pending email change using a verification token."""
    check_origin(request)

    token_hash_val = hash_token(req.token)
    now = datetime.now(timezone.utc)

    # Find valid token
    token_row = await database.fetch_one(
        email_verification_tokens.select().where(
            (email_verification_tokens.c.token_hash == token_hash_val) &
            (email_verification_tokens.c.expires_at > now) &
            (email_verification_tokens.c.used_at.is_(None))
        )
    )

    if not token_row:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    # Mark token as used
    await database.execute(
        email_verification_tokens.update()
        .where(email_verification_tokens.c.id == token_row["id"])
        .values(used_at=now)
    )

    # Promote pending email to primary email
    user = await database.fetch_one(
        users.select().where(users.c.id == token_row["user_id"])
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_email = token_row["email"]
    new_email_norm = normalize_email(new_email)

    # Check if this email is already taken by another user
    existing = await database.fetch_one(
        users.select().where(
            (users.c.email_normalized == new_email_norm) &
            (users.c.id != user["id"])
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use by another account")

    await database.execute(
        users.update()
        .where(users.c.id == user["id"])
        .values(
            email=new_email.strip(),
            email_normalized=new_email_norm,
            pending_email=None,
            pending_email_normalized=None,
            email_verified_at=now,
            updated_at=now,
        )
    )

    return {"status": "ok", "message": "Email verified and updated"}


@app.post("/auth/resend-verification", dependencies=[Depends(_csrf_dependency)])
async def auth_resend_verification(req: ResendVerificationRequest, request: Request, current_user: dict = Depends(_require_user)):
    """Resend email verification for pending email change."""
    email_norm = normalize_email(req.email)

    # Rate limit
    allowed, retry_after = await check_rate_limit(database, auth_rate_limits, "resend_verification", email_norm)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many attempts. Try again in {retry_after} seconds.")

    await record_attempt(database, auth_rate_limits, "resend_verification", email_norm)

    # Only allow if user has a pending email that matches
    if not current_user.get("pending_email_normalized") or current_user["pending_email_normalized"] != email_norm:
        raise HTTPException(status_code=400, detail="No pending email change for this address")

    now = datetime.now(timezone.utc)

    # Revoke existing unused verification tokens for this user
    await database.execute(
        email_verification_tokens.update()
        .where(
            (email_verification_tokens.c.user_id == current_user["id"]) &
            (email_verification_tokens.c.used_at.is_(None))
        )
        .values(used_at=now)
    )

    # Generate new token
    token = generate_reset_token()
    token_hash_val = hash_token(token)
    expires_at = now + timedelta(hours=4)

    await database.execute(
        email_verification_tokens.insert().values(
            user_id=current_user["id"],
            token_hash=token_hash_val,
            email=current_user["pending_email"],
            created_at=now,
            expires_at=expires_at,
        )
    )

    verify_link = f"{FRONTEND_ORIGIN}/authentication/modern/verify-email?token={token}"
    email_sender = get_email_sender()
    await email_sender.send_verification_email(current_user["pending_email"], verify_link)

    return {"status": "ok", "message": "Verification email sent"}


# ============================================================
# CURRENT USER ENDPOINTS
# ============================================================

@app.get("/users/me")
async def get_current_user_profile(request: Request, current_user: dict = Depends(_require_user)):
    """Get full current user profile."""
    return _user_to_me_response(current_user, current_user.get("roles", []))


@app.put("/users/me", dependencies=[Depends(_csrf_dependency)])
async def update_current_user_profile(req: UpdateProfileRequest, request: Request, current_user: dict = Depends(_require_user)):
    """Update current user's full_name."""
    now = datetime.now(timezone.utc)
    values: dict = {"updated_at": now}
    if req.full_name is not None:
        values["full_name"] = req.full_name.strip() if req.full_name else None

    await database.execute(
        users.update().where(users.c.id == current_user["id"]).values(**values)
    )

    user_row = await database.fetch_one(users.select().where(users.c.id == current_user["id"]))
    if user_row is None:
        raise HTTPException(status_code=500, detail="User not found after update")
    return _user_to_me_response(dict(user_row), current_user.get("roles", []))


@app.put("/users/me/email", dependencies=[Depends(_csrf_dependency)])
async def update_current_user_email(req: UpdateEmailRequest, request: Request, current_user: dict = Depends(_require_user)):
    """Set pending email and send verification."""
    # Verify current password
    if not verify_password(req.password, current_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect password")

    new_email_norm = normalize_email(req.new_email)

    # Check if same as current
    if new_email_norm == current_user["email_normalized"]:
        raise HTTPException(status_code=400, detail="New email is the same as current email")

    # Check uniqueness
    existing = await database.fetch_one(
        users.select().where(
            (users.c.email_normalized == new_email_norm) &
            (users.c.id != current_user["id"])
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use")

    now = datetime.now(timezone.utc)

    # Set pending email
    await database.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            pending_email=req.new_email.strip(),
            pending_email_normalized=new_email_norm,
            updated_at=now,
        )
    )

    # Revoke existing verification tokens
    await database.execute(
        email_verification_tokens.update()
        .where(
            (email_verification_tokens.c.user_id == current_user["id"]) &
            (email_verification_tokens.c.used_at.is_(None))
        )
        .values(used_at=now)
    )

    # Generate verification token
    token = generate_reset_token()
    token_hash_val = hash_token(token)
    expires_at = now + timedelta(hours=4)

    await database.execute(
        email_verification_tokens.insert().values(
            user_id=current_user["id"],
            token_hash=token_hash_val,
            email=req.new_email.strip(),
            created_at=now,
            expires_at=expires_at,
        )
    )

    verify_link = f"{FRONTEND_ORIGIN}/authentication/modern/verify-email?token={token}"
    email_sender = get_email_sender()
    await email_sender.send_verification_email(req.new_email.strip(), verify_link)

    return {"status": "ok", "message": "Verification email sent to new address"}


@app.put("/users/me/username", dependencies=[Depends(_csrf_dependency)])
async def update_current_user_username(req: UpdateUsernameRequest, request: Request, current_user: dict = Depends(_require_user)):
    """Update current user's username."""
    username_norm = normalize_username(req.new_username)

    valid, err = validate_username(username_norm)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    # Check if same as current
    if username_norm == current_user["username_normalized"]:
        raise HTTPException(status_code=400, detail="New username is the same as current username")

    # Check uniqueness
    existing = await database.fetch_one(
        users.select().where(
            (users.c.username_normalized == username_norm) &
            (users.c.id != current_user["id"])
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    now = datetime.now(timezone.utc)
    await database.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            username=username_norm,
            username_normalized=username_norm,
            updated_at=now,
        )
    )

    return {"status": "ok", "message": "Username updated"}


@app.put("/users/me/password", dependencies=[Depends(_csrf_dependency)])
async def update_current_user_password(req: ChangePasswordRequest, request: Request, response: Response, current_user: dict = Depends(_require_user)):
    """Change password: verify current, re-encrypt AI tokens, update hash, rotate session."""
    # Verify current password
    if not verify_password(req.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect current password")

    # Validate new password
    valid, err = validate_password(req.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    if req.current_password == req.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    now = datetime.now(timezone.utc)

    # Re-encrypt AI tokens BEFORE updating password hash
    try:
        await re_encrypt_all_user_tokens(
            database, user_ai_tokens, current_user["id"],
            req.current_password, req.new_password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail="Failed to re-encrypt AI tokens. Password change aborted."
        )

    # Update password hash
    new_hash = hash_password(req.new_password)
    await database.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            password_hash=new_hash,
            updated_at=now,
        )
    )

    # Revoke ALL sessions for this user
    await database.execute(
        auth_sessions.update()
        .where(
            (auth_sessions.c.user_id == current_user["id"]) &
            (auth_sessions.c.revoked_at.is_(None))
        )
        .values(revoked_at=now)
    )

    # Create a new session (rotate)
    await _create_session_and_cookies(response, request, current_user["id"])

    return {"status": "ok", "message": "Password changed. Other sessions have been revoked."}


@app.put("/users/me/preferences", dependencies=[Depends(_csrf_dependency)])
async def update_current_user_preferences(req: UpdatePreferencesRequest, request: Request, current_user: dict = Depends(_require_user)):
    """Update current user's preferences JSON."""
    now = datetime.now(timezone.utc)
    await database.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            preferences=req.preferences,
            updated_at=now,
        )
    )
    return {"status": "ok", "preferences": req.preferences}


@app.put("/users/me/avatar", dependencies=[Depends(_csrf_dependency)])
async def update_current_user_avatar(request: Request, current_user: dict = Depends(_require_user), file: UploadFile = File(...)):
    """Upload avatar image (max 512KB, JPEG/PNG/WebP, decode+re-encode)."""
    # Read file
    contents = await file.read()

    # Check size (512 KB)
    if len(contents) > 512 * 1024:
        raise HTTPException(status_code=400, detail="Avatar must be under 512 KB")

    # Validate and re-encode using Pillow
    try:
        from PIL import Image
        import io
        import hashlib as hl

        img = Image.open(io.BytesIO(contents))
        img_format = img.format

        if img_format not in ("JPEG", "PNG", "WEBP"):
            raise HTTPException(status_code=400, detail="Avatar must be JPEG, PNG, or WebP")

        # Re-encode to strip metadata and validate
        output = io.BytesIO()
        if img_format == "JPEG":
            img = img.convert("RGB")
            img.save(output, format="JPEG", quality=85)
            mime = "image/jpeg"
        elif img_format == "PNG":
            img.save(output, format="PNG")
            mime = "image/png"
        else:  # WEBP
            img.save(output, format="WEBP", quality=85)
            mime = "image/webp"

        sanitized_bytes = output.getvalue()
        avatar_hash = hl.sha256(sanitized_bytes).hexdigest()[:16]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {e}")

    now = datetime.now(timezone.utc)
    await database.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            avatar_bytes=sanitized_bytes,
            avatar_mime_type=mime,
            avatar_size_bytes=len(sanitized_bytes),
            avatar_hash=avatar_hash,
            avatar_source="upload",
            avatar_updated_at=now,
            updated_at=now,
        )
    )

    return {"status": "ok", "avatar_hash": avatar_hash, "avatar_size": len(sanitized_bytes)}


@app.delete("/users/me/avatar", dependencies=[Depends(_csrf_dependency)])
async def delete_current_user_avatar(request: Request, current_user: dict = Depends(_require_user)):
    """Delete current user's avatar."""
    now = datetime.now(timezone.utc)
    await database.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            avatar_bytes=None,
            avatar_mime_type=None,
            avatar_size_bytes=None,
            avatar_hash=None,
            avatar_source="none",
            avatar_updated_at=now,
            updated_at=now,
        )
    )
    return {"status": "ok", "message": "Avatar deleted"}


@app.get("/users/me/avatar")
async def get_current_user_avatar(request: Request, current_user: dict = Depends(_require_user)):
    """Serve current user's avatar bytes, or redirect to Gravatar."""
    source = current_user.get("avatar_source", "none")

    if source == "upload" and current_user.get("avatar_bytes"):
        return Response(
            content=current_user["avatar_bytes"],
            media_type=current_user.get("avatar_mime_type", "image/jpeg"),
            headers={"Cache-Control": "private, max-age=3600"},
        )

    if source == "gravatar":
        email = (current_user.get("email") or "").strip().lower()
        email_hash = hashlib.md5(email.encode("utf-8")).hexdigest()
        gravatar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=200"
        from starlette.responses import RedirectResponse
        return RedirectResponse(url=gravatar_url, status_code=302)

    raise HTTPException(status_code=404, detail="No avatar")


@app.put("/users/me/avatar-source", dependencies=[Depends(_csrf_dependency)])
async def update_avatar_source(request: Request, current_user: dict = Depends(_require_user)):
    """Update avatar source (none or gravatar). Use PUT /users/me/avatar for upload."""
    body = await request.json()
    source = body.get("source", "none")
    if source not in ("none", "gravatar"):
        raise HTTPException(status_code=400, detail="source must be 'none' or 'gravatar'")

    now = datetime.now(timezone.utc)
    await database.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            avatar_source=source,
            updated_at=now,
        )
    )
    return {"status": "ok", "avatar_source": source}


# ============================================================
# ADMIN ENDPOINTS
# ============================================================

@app.get("/admin/users")
async def admin_list_users(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(_require_admin),
):
    """List all users with pagination."""
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size

    total_row = await database.fetch_one("SELECT COUNT(*) as cnt FROM users")
    total = total_row["cnt"] if total_row else 0

    rows = await database.fetch_all(
        users.select().order_by(users.c.id).limit(page_size).offset(offset)
    )

    user_list = []
    for row in rows:
        role_list = await _get_user_roles(row["id"])
        user_list.append(_user_to_response(dict(row), role_list))

    return {"users": user_list, "total": total, "page": page, "page_size": page_size}


@app.post("/admin/users", dependencies=[Depends(_csrf_dependency)])
async def admin_create_user(req: AdminCreateUserRequest, request: Request, current_user: dict = Depends(_require_admin)):
    """Admin create user: no plaintext password. Sends invite link."""
    # Validate
    valid, err = validate_username(req.username)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    email_norm = normalize_email(req.email)
    username_norm = normalize_username(req.username)

    # Check email uniqueness
    existing = await database.fetch_one(
        users.select().where(users.c.email_normalized == email_norm)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Check username uniqueness
    existing = await database.fetch_one(
        users.select().where(users.c.username_normalized == username_norm)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    now = datetime.now(timezone.utc)

    # Create user with a random unusable password (user sets it via invite link)
    import secrets as _secrets
    temp_hash = hash_password(_secrets.token_urlsafe(32))

    user_id = await database.execute(
        users.insert().values(
            email=req.email.strip(),
            email_normalized=email_norm,
            username=username_norm,
            username_normalized=username_norm,
            full_name=req.full_name,
            password_hash=temp_hash,
            status="active",
            avatar_source="none",
            preferences={},
            created_at=now,
            updated_at=now,
        )
    )

    # Assign roles
    for role_name in req.roles:
        role_row = await database.fetch_one(roles.select().where(roles.c.name == role_name))
        if role_row:
            await database.execute(user_roles.insert().values(user_id=user_id, role_id=role_row["id"]))

    # Create invite/reset token
    token = generate_reset_token()
    token_hash_val = hash_token(token)
    expires_at = now + timedelta(hours=4)

    await database.execute(
        password_reset_tokens.insert().values(
            user_id=user_id,
            token_hash=token_hash_val,
            created_at=now,
            expires_at=expires_at,
        )
    )

    invite_link = f"{FRONTEND_ORIGIN}/authentication/modern/new-password?token={token}"
    email_sender = get_email_sender()
    await email_sender.send_invite_email(req.email.strip(), invite_link)

    user_row = await database.fetch_one(users.select().where(users.c.id == user_id))
    if user_row is None:
        raise HTTPException(status_code=500, detail="User not found after creation")
    role_list = await _get_user_roles(user_id)
    return _user_to_response(dict(user_row), role_list)


@app.get("/admin/users/{user_id}")
async def admin_get_user(user_id: int, request: Request, current_user: dict = Depends(_require_admin)):
    """Get user details by ID."""
    user_row = await database.fetch_one(users.select().where(users.c.id == user_id))
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    role_list = await _get_user_roles(user_id)
    return _user_to_response(dict(user_row), role_list)


@app.put("/admin/users/{user_id}", dependencies=[Depends(_csrf_dependency)])
async def admin_update_user(user_id: int, req: AdminUpdateUserRequest, request: Request, current_user: dict = Depends(_require_admin)):
    """Admin update user (full_name, status)."""
    user_row = await database.fetch_one(users.select().where(users.c.id == user_id))
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)
    values: dict = {"updated_at": now}

    if req.full_name is not None:
        values["full_name"] = req.full_name.strip() if req.full_name else None

    if req.status is not None:
        if req.status not in ("active", "inactive", "blocked"):
            raise HTTPException(status_code=400, detail="Status must be active, inactive, or blocked")
        values["status"] = req.status

        # If blocking, revoke all sessions
        if req.status == "blocked":
            await database.execute(
                auth_sessions.update()
                .where(
                    (auth_sessions.c.user_id == user_id) &
                    (auth_sessions.c.revoked_at.is_(None))
                )
                .values(revoked_at=now)
            )

    await database.execute(
        users.update().where(users.c.id == user_id).values(**values)
    )

    user_row = await database.fetch_one(users.select().where(users.c.id == user_id))
    if user_row is None:
        raise HTTPException(status_code=404, detail="User not found")
    role_list = await _get_user_roles(user_id)
    return _user_to_response(dict(user_row), role_list)


@app.delete("/admin/users/{user_id}", dependencies=[Depends(_csrf_dependency)])
async def admin_delete_user(user_id: int, request: Request, current_user: dict = Depends(_require_admin)):
    """Soft block a user (set status=blocked, revoke sessions)."""
    user_row = await database.fetch_one(users.select().where(users.c.id == user_id))
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-block
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot block yourself")

    owned_sites = await ownership_transfer_gate(database, user_id)
    if owned_sites:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "User owns feeds that must be transferred first",
                "owned_sites": owned_sites,
            },
        )

    now = datetime.now(timezone.utc)

    await database.execute(
        users.update().where(users.c.id == user_id).values(status="blocked", updated_at=now)
    )

    # Revoke sessions
    await database.execute(
        auth_sessions.update()
        .where(
            (auth_sessions.c.user_id == user_id) &
            (auth_sessions.c.revoked_at.is_(None))
        )
        .values(revoked_at=now)
    )

    return {"status": "ok", "message": "User blocked"}


@app.put("/admin/users/{user_id}/roles", dependencies=[Depends(_csrf_dependency)])
async def admin_update_user_roles(user_id: int, req: AdminUpdateRolesRequest, request: Request, current_user: dict = Depends(_require_admin)):
    """Assign roles to a user (replaces existing roles)."""
    user_row = await database.fetch_one(users.select().where(users.c.id == user_id))
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate role names
    all_roles = await database.fetch_all(roles.select())
    valid_role_names = {r["name"] for r in all_roles}
    for role_name in req.roles:
        if role_name not in valid_role_names:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role_name}")

    # Remove existing roles
    await database.execute(user_roles.delete().where(user_roles.c.user_id == user_id))

    # Add new roles
    for role_name in req.roles:
        role_row = await database.fetch_one(roles.select().where(roles.c.name == role_name))
        if role_row:
            await database.execute(user_roles.insert().values(user_id=user_id, role_id=role_row["id"]))

    return {"status": "ok", "roles": req.roles}


@app.get("/admin/roles")
async def admin_list_roles(request: Request, current_user: dict = Depends(_require_admin)):
    """List all roles with user counts."""
    all_roles = await database.fetch_all(roles.select().order_by(roles.c.id))

    result = []
    for role_row in all_roles:
        count_row = await database.fetch_one(
            "SELECT COUNT(*) as cnt FROM user_roles WHERE role_id = :rid",
            values={"rid": role_row["id"]},
        )
        result.append({
            "id": role_row["id"],
            "name": role_row["name"],
            "description": role_row["description"],
            "created_at": role_row["created_at"].isoformat() if role_row["created_at"] else None,
            "user_count": count_row["cnt"] if count_row else 0,
        })

    return {"roles": result}


@app.put("/admin/sites/{site_id}/owner", dependencies=[Depends(_csrf_dependency)])
async def update_site_owner(site_id: int, request: Request, current_user: dict = Depends(_require_admin)):
    body = await request.json()
    new_owner_id = body.get("owner_user_id")
    if not new_owner_id or not isinstance(new_owner_id, int):
        raise HTTPException(status_code=400, detail="owner_user_id is required and must be an integer")

    # Verify site exists
    site = await database.fetch_one(
        sites.select().where(sites.c.id == site_id)
    )
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    target = await verify_transfer_target(database, new_owner_id)
    if not target:
        raise HTTPException(status_code=400, detail="Target user not found or not active")

    # Update owner
    await database.execute(
        sites.update().where(sites.c.id == site_id).values(owner_user_id=new_owner_id)
    )
    return {"site_id": site_id, "owner_user_id": new_owner_id}


# ============================================================
# AI TOKEN VAULT ENDPOINTS
# ============================================================

@app.get("/settings/ai-tokens")
async def settings_list_ai_tokens(current_user: dict = Depends(_require_user)):
    """List current user's AI tokens (masked values only)."""
    tokens = await list_user_tokens(database, user_ai_tokens, current_user["id"])
    return {"tokens": tokens}


@app.post("/settings/ai-tokens", dependencies=[Depends(_csrf_dependency)])
async def settings_create_ai_token(req: CreateTokenRequest, current_user: dict = Depends(_require_user)):
    """Create a new AI token for the current user. Requires current_password to encrypt."""
    # Verify current password
    user_row = await database.fetch_one(
        users.select().where(users.c.id == current_user["id"])
    )
    if not user_row or not verify_password(req.current_password, user_row["password_hash"]):
        raise HTTPException(status_code=403, detail="Invalid password")

    try:
        token_resp = await create_user_token(
            database, user_ai_tokens,
            user_id=current_user["id"],
            provider=req.provider,
            label=req.label,
            plaintext_token=req.token,
            password=req.current_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return token_resp


@app.put("/settings/ai-tokens/{token_id}", dependencies=[Depends(_csrf_dependency)])
async def settings_update_ai_token(token_id: int, req: UpdateTokenRequest, current_user: dict = Depends(_require_user)):
    """Update (overwrite) an existing AI token. Requires current_password to re-encrypt."""
    # Verify current password
    user_row = await database.fetch_one(
        users.select().where(users.c.id == current_user["id"])
    )
    if not user_row or not verify_password(req.current_password, user_row["password_hash"]):
        raise HTTPException(status_code=403, detail="Invalid password")

    try:
        token_resp = await update_user_token(
            database, user_ai_tokens,
            token_id=token_id,
            user_id=current_user["id"],
            plaintext_token=req.token,
            password=req.current_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return token_resp


@app.delete("/settings/ai-tokens/{token_id}", dependencies=[Depends(_csrf_dependency)])
async def settings_delete_ai_token(token_id: int, current_user: dict = Depends(_require_user)):
    """Delete an AI token for the current user."""
    try:
        await delete_user_token(database, user_ai_tokens, token_id, current_user["id"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"status": "deleted", "token_id": token_id}


@app.post("/settings/ai-tokens/{token_id}/test", dependencies=[Depends(_csrf_dependency)])
async def settings_test_ai_token(token_id: int, req: TestTokenRequest, current_user: dict = Depends(_require_user)):
    """Test an AI token's connectivity by making a test API call. Requires current_password to decrypt."""
    # Verify current password
    user_row = await database.fetch_one(
        users.select().where(users.c.id == current_user["id"])
    )
    if not user_row or not verify_password(req.current_password, user_row["password_hash"]):
        raise HTTPException(status_code=403, detail="Invalid password")

    try:
        result = await test_user_token(
            database, user_ai_tokens,
            token_id=token_id,
            user_id=current_user["id"],
            password=req.current_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result


@app.post("/settings/ai-tokens/{token_id}/reveal", dependencies=[Depends(_csrf_dependency)])
async def settings_reveal_ai_token(token_id: int, req: RevealTokenRequest, current_user: dict = Depends(_require_user)):
    """Reveal the plaintext AI token. Requires current_password to decrypt.

    The plaintext is ONLY returned in this response — never logged or stored in debug artifacts.
    """
    # Verify current password
    user_row = await database.fetch_one(
        users.select().where(users.c.id == current_user["id"])
    )
    if not user_row or not verify_password(req.current_password, user_row["password_hash"]):
        raise HTTPException(status_code=403, detail="Invalid password")

    try:
        plaintext = await reveal_user_token(
            database, user_ai_tokens,
            token_id=token_id,
            user_id=current_user["id"],
            password=req.current_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"token": plaintext}


@app.put("/settings/ai-tokens/{token_id}/default", dependencies=[Depends(_csrf_dependency)])
async def settings_set_default_ai_token(token_id: int, current_user: dict = Depends(_require_user)):
    """Set an AI token as the default for its provider."""
    # Fetch token to get provider
    token_row = await database.fetch_one(
        user_ai_tokens.select().where(
            (user_ai_tokens.c.id == token_id)
            & (user_ai_tokens.c.user_id == current_user["id"])
        )
    )
    if not token_row:
        raise HTTPException(status_code=404, detail="Token not found or access denied")

    try:
        token_resp = await set_default_token(
            database, user_ai_tokens,
            token_id=token_id,
            user_id=current_user["id"],
            provider=token_row["provider"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return token_resp


# ============================================================
# AI PROVIDER ROUTES
# ============================================================

@app.get("/settings/ai-providers")
async def list_ai_providers(current_user: dict = Depends(_require_user)):
    result = await list_user_providers(database, _ai_tables, user_id=current_user["id"])
    return result

@app.get("/settings/ai-providers/runtime-status")
async def get_ai_provider_runtime_status(current_user: dict = Depends(_require_user)):
    result = await get_runtime_status(
        database, _ai_tables, _kek_backend,
        user_id=current_user["id"],
    )
    return result

@app.post("/settings/ai-providers/actions/discover-models", dependencies=[Depends(_csrf_dependency)])
async def discover_ai_models(req: DiscoverModelsRequest, current_user: dict = Depends(_require_user)):
    kek = _require_kek()
    try:
        result = await discover_models(
            database, _ai_tables, kek,
            user_id=current_user["id"],
            protocol=req.protocol,
            base_url=req.base_url,
            api_key=req.api_key,
            provider_id=req.provider_id,
        )
        return result
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")
    except ProviderOwnershipError:
        raise HTTPException(status_code=403, detail="Access denied")

@app.put("/settings/ai-providers/order", dependencies=[Depends(_csrf_dependency)])
async def reorder_ai_providers(req: ReorderProvidersRequest, current_user: dict = Depends(_require_user)):
    kek = _require_kek()
    try:
        result = await reorder_providers(
            database, _ai_tables,
            user_id=current_user["id"],
            ordered_ids=req.ordered_ids,
            revision=req.revision,
        )
        return result
    except ProviderRevisionConflictError:
        raise HTTPException(status_code=409, detail={"code": "revision_conflict", "message": "Provider settings changed; reload and retry."})
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "invalid_order", "message": str(e)})

@app.post("/settings/ai-providers", dependencies=[Depends(_csrf_dependency)])
async def create_ai_provider(req: CreateProviderRequest, current_user: dict = Depends(_require_user)):
    kek = _require_kek()
    try:
        result = await create_provider(
            database, _ai_tables, kek,
            user_id=current_user["id"],
            label=req.label,
            protocol=req.protocol,
            base_url=req.base_url,
            model=req.model,
            api_key=req.api_key,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            thinking=req.thinking,
            effort=req.effort,
        )
        return Response(
            content=json.dumps(result, default=str),
            status_code=201,
            media_type="application/json",
        )
    except ProviderLabelConflictError:
        raise HTTPException(status_code=409, detail={"code": "label_conflict", "message": "A provider with this label already exists."})

@app.put("/settings/ai-providers/{provider_id}", dependencies=[Depends(_csrf_dependency)])
async def update_ai_provider(provider_id: int, req: UpdateProviderRequest, current_user: dict = Depends(_require_user)):
    kek = _require_kek()
    kwargs = {}
    for field in ("label", "protocol", "base_url", "model", "temperature", "max_tokens", "thinking", "effort"):
        if field in req.model_fields_set:
            kwargs[field] = getattr(req, field)
    if "api_key" in req.model_fields_set and req.api_key is not None:
        kwargs["api_key"] = req.api_key
    try:
        result = await update_provider(
            database, _ai_tables, kek,
            user_id=current_user["id"],
            provider_id=provider_id,
            revision=req.revision,
            **kwargs,
        )
        return result
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")
    except ProviderRevisionConflictError:
        raise HTTPException(status_code=409, detail={"code": "revision_conflict", "message": "Provider settings changed; reload and retry."})
    except ProviderOwnershipError:
        raise HTTPException(status_code=403, detail="Access denied")

@app.delete("/settings/ai-providers/{provider_id}", dependencies=[Depends(_csrf_dependency)])
async def delete_ai_provider(provider_id: int, req: DeleteProviderRequest, current_user: dict = Depends(_require_user)):
    kek = _require_kek()
    try:
        await delete_provider(
            database, _ai_tables,
            user_id=current_user["id"],
            provider_id=provider_id,
            revision=req.revision,
        )
        return Response(status_code=204)
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")
    except ProviderRevisionConflictError:
        raise HTTPException(status_code=409, detail={"code": "revision_conflict", "message": "Provider settings changed; reload and retry."})
    except ProviderOwnershipError:
        raise HTTPException(status_code=403, detail="Access denied")

@app.post("/settings/ai-providers/{provider_id}/test", dependencies=[Depends(_csrf_dependency)])
async def test_ai_provider(provider_id: int, current_user: dict = Depends(_require_user)):
    kek = _require_kek()
    try:
        result = await test_provider_connection(
            database, _ai_tables, kek,
            user_id=current_user["id"],
            provider_id=provider_id,
        )
        return result
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")
    except ProviderOwnershipError:
        raise HTTPException(status_code=403, detail="Access denied")

@app.post("/settings/ai-providers/{provider_id}/reveal", dependencies=[Depends(_csrf_dependency)])
async def reveal_ai_provider_key(provider_id: int, req: RevealProviderKeyRequest, current_user: dict = Depends(_require_user)):
    kek = _require_kek()
    if not verify_password(req.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=403, detail={"code": "invalid_password", "message": "Invalid password."})
    try:
        api_key = await reveal_api_key(
            database, _ai_tables, kek,
            user_id=current_user["id"],
            provider_id=provider_id,
        )
        return Response(
            content=json.dumps({"api_key": api_key}),
            status_code=200,
            media_type="application/json",
            headers={"Cache-Control": "no-store, private", "Pragma": "no-cache"},
        )
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")
    except ProviderOwnershipError:
        raise HTTPException(status_code=403, detail="Access denied")

@app.put("/settings/ai-providers/{provider_id}/enabled", dependencies=[Depends(_csrf_dependency)])
async def toggle_ai_provider_enabled(provider_id: int, req: ToggleProviderEnabledRequest, current_user: dict = Depends(_require_user)):
    try:
        result = await toggle_provider_enabled(
            database, _ai_tables,
            user_id=current_user["id"],
            provider_id=provider_id,
            enabled=req.enabled,
        )
        return result
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")
    except ProviderOwnershipError:
        raise HTTPException(status_code=403, detail="Access denied")


# ============================================================
# DATABASE MANAGEMENT ENDPOINTS
# ============================================================

# Import file size limits
_MAX_IMPORT_FILE_SIZE = 50 * 1024 * 1024  # 50MB
_MAX_IMPORT_UNCOMPRESSED_SIZE = 500 * 1024 * 1024  # 500MB

# Tables safe to export (never export auth/security tables)
_EXPORTABLE_TABLES = {"sites", "articles", "crawl_attempts", "rss_query_events", "users", "roles", "user_roles"}
_AUDIT_TABLES = {"crawl_attempts", "rss_query_events"}
# System tables excluded from status row counts
_SYSTEM_TABLES = {"schema_versions", "alembic_version"}
# FK import order: parents before children
_IMPORT_ORDER = ["roles", "users", "user_roles", "sites", "articles", "crawl_attempts", "rss_query_events"]

# Table object lookup for exportable tables
_TABLE_MAP = {
    "sites": sites,
    "articles": articles,
    "crawl_attempts": crawl_attempts,
    "rss_query_events": rss_query_events,
    "users": users,
    "roles": roles,
    "user_roles": user_roles,
}

# Columns to exclude per-table during export (sensitive or derived fields)
_EXPORT_EXCLUDED_COLUMNS = {
    "users": {
        "avatar_bytes",
        "email_normalized",
        "username_normalized",
        "pending_email",
        "pending_email_normalized",
    },
}


def _serialize_row_for_export(row_dict: dict) -> dict:
    """Serialize a database row for JSON export, handling datetime and bytes."""
    result = {}
    for key, value in row_dict.items():
        if isinstance(value, bytes):
            continue  # Skip binary columns (e.g. avatar_bytes)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


@app.get("/settings/database/status")
async def database_status(current_user: dict = Depends(_require_admin)):
    """Return database status: schema version, table row counts, pending migrations."""
    # Current schema version
    latest_version = await database.fetch_one(
        "SELECT version, applied_at FROM schema_versions ORDER BY applied_at DESC LIMIT 1"
    )
    current_version = latest_version["version"] if latest_version else "unknown"
    last_migration_at = (
        latest_version["applied_at"].isoformat()
        if latest_version and latest_version["applied_at"]
        else None
    )

    # Table row counts (exclude system tables)
    table_names = [
        t.name for t in metadata.sorted_tables if t.name not in _SYSTEM_TABLES
    ]
    tables_info = []
    for name in table_names:
        try:
            row = await database.fetch_one(f'SELECT COUNT(*) AS cnt FROM "{name}"')
            tables_info.append({"name": name, "row_count": row["cnt"] if row else 0})
        except Exception:
            tables_info.append({"name": name, "row_count": -1})

    # Pending migrations
    applied_rows = await database.fetch_all(schema_versions.select())
    applied_versions = {r["version"] for r in applied_rows}
    pending = [
        {"version": m["version"], "description": m["description"]}
        for m in MIGRATIONS
        if m["version"] not in applied_versions
    ]

    return {
        "schema_version": current_version,
        "app_version": APP_VERSION,
        "tables": tables_info,
        "pending_migrations": pending,
        "last_migration_at": last_migration_at,
    }


@app.post("/settings/database/migrate", dependencies=[Depends(_csrf_dependency)])
async def database_migrate(current_user: dict = Depends(_require_admin)):
    """Execute all pending schema migrations in a transaction."""
    applied_rows = await database.fetch_all(schema_versions.select())
    applied_versions = {r["version"] for r in applied_rows}

    pending = [m for m in MIGRATIONS if m["version"] not in applied_versions]
    if not pending:
        return {"applied": [], "message": "No pending migrations"}

    applied = []
    async with database.transaction():
        for migration in pending:
            try:
                await migration["up"](database)
                await database.execute(
                    schema_versions.insert().values(
                        version=migration["version"],
                        description=migration["description"],
                        applied_at=datetime.now(timezone.utc),
                    )
                )
                applied.append({
                    "version": migration["version"],
                    "description": migration["description"],
                })
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Migration {migration['version']} failed: {str(e)}",
                )

    return {"applied": applied, "message": f"Applied {len(applied)} migration(s)"}


@app.get("/settings/database/export")
async def database_export(
    tables: str = "sites,articles",
    include_audit: bool = False,
    format: str = "zip",
    current_user: dict = Depends(_require_admin),
):
    """Export database tables as a ZIP (default) or JSON file download.

    Use format=json for plain JSON, format=zip (default) for a ZIP archive.
    """
    requested_tables = [t.strip() for t in tables.split(",") if t.strip()]

    # Validate table names
    invalid = [t for t in requested_tables if t not in _EXPORTABLE_TABLES]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Non-exportable table(s): {', '.join(invalid)}",
        )

    # Filter out audit tables unless include_audit
    if not include_audit:
        requested_tables = [t for t in requested_tables if t not in _AUDIT_TABLES]

    if not requested_tables:
        raise HTTPException(status_code=400, detail="No valid tables to export")

    # Current schema version
    latest_version = await database.fetch_one(
        "SELECT version FROM schema_versions ORDER BY applied_at DESC LIMIT 1"
    )
    current_version = latest_version["version"] if latest_version else APP_VERSION

    # Export data
    data = {}
    table_counts = {}
    for t_name in requested_tables:
        tbl = _TABLE_MAP[t_name]
        rows = await database.fetch_all(tbl.select())
        excluded_cols = _EXPORT_EXCLUDED_COLUMNS.get(t_name, set())
        serialized = []
        for r in rows:
            row_dict = dict(r)
            for col in excluded_cols:
                row_dict.pop(col, None)
            serialized.append(_serialize_row_for_export(row_dict))
        data[t_name] = serialized
        table_counts[t_name] = len(serialized)

    export_payload = {
        "metadata": {
            "export_time": datetime.now(timezone.utc).isoformat(),
            "schema_version": current_version,
            "app_version": APP_VERSION,
            "tables": table_counts,
        },
        "data": data,
    }

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    if format == "json":
        filename = f"palimpsest-export-{date_str}.json"
        json_content = json.dumps(export_payload, ensure_ascii=False, indent=2)
        return Response(
            content=json_content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:
        # Default: ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            json_str = json.dumps(export_payload, ensure_ascii=False, indent=2)
            zf.writestr('palimpsest-export.json', json_str)
        zip_buffer.seek(0)
        return Response(
            content=zip_buffer.read(),
            media_type='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename="palimpsest-export-{date_str}.zip"'
            }
        )


@app.post("/settings/database/import/preview", dependencies=[Depends(_csrf_dependency)])
async def database_import_preview(
    current_user: dict = Depends(_require_admin),
    file: UploadFile = File(...),
):
    """Preview an import: validate format, check conflicts, return counts.

    Accepts both .json and .zip files.
    """
    try:
        file_content = await file.read()
        if len(file_content) > _MAX_IMPORT_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large (max {_MAX_IMPORT_FILE_SIZE // (1024*1024)}MB)")
        if file.filename and file.filename.lower().endswith('.zip'):
            zip_buffer = io.BytesIO(file_content)
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > _MAX_IMPORT_UNCOMPRESSED_SIZE:
                    raise HTTPException(status_code=400, detail="ZIP uncompressed size exceeds limit")
                json_files = [n for n in zf.namelist() if n.endswith('.json')]
                if not json_files:
                    raise HTTPException(status_code=400, detail="ZIP file contains no JSON files")
                json_content = zf.read(json_files[0])
                import_data = json.loads(json_content)
        else:
            import_data = json.loads(file_content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid file: {str(e)}")

    if "metadata" not in import_data or "data" not in import_data:
        raise HTTPException(
            status_code=400,
            detail="Invalid export format: missing 'metadata' or 'data'",
        )

    warnings: list[str] = []

    # Schema compatibility check
    import_version = import_data["metadata"].get("schema_version", "unknown")
    latest_version = await database.fetch_one(
        "SELECT version FROM schema_versions ORDER BY applied_at DESC LIMIT 1"
    )
    current_version = latest_version["version"] if latest_version else APP_VERSION
    compatible = True
    if import_version != current_version:
        warnings.append(
            f"Schema version mismatch: import={import_version}, current={current_version}"
        )

    tables_result = []
    for t_name, rows in import_data["data"].items():
        if t_name not in _EXPORTABLE_TABLES:
            warnings.append(f"Skipping non-exportable table: {t_name}")
            continue

        total = len(rows)
        new_count = 0
        conflict_count = 0

        if t_name == "articles":
            for row in rows:
                url = row.get("url")
                if url:
                    existing = await database.fetch_one(
                        articles.select().where(articles.c.url == url)
                    )
                    if existing:
                        conflict_count += 1
                    else:
                        new_count += 1
                else:
                    new_count += 1
        elif t_name == "sites":
            for row in rows:
                url = row.get("url")
                if url:
                    existing = await database.fetch_one(
                        sites.select().where(sites.c.url == url)
                    )
                    if existing:
                        conflict_count += 1
                    else:
                        new_count += 1
                else:
                    new_count += 1
        elif t_name == "users":
            for row in rows:
                email = row.get("email")
                if email:
                    existing = await database.fetch_one(
                        users.select().where(users.c.email == email)
                    )
                    if existing:
                        conflict_count += 1
                    else:
                        new_count += 1
                else:
                    new_count += 1
        elif t_name == "roles":
            for row in rows:
                name = row.get("name")
                if name:
                    existing = await database.fetch_one(
                        roles.select().where(roles.c.name == name)
                    )
                    if existing:
                        conflict_count += 1
                    else:
                        new_count += 1
                else:
                    new_count += 1
        else:
            # crawl_attempts, rss_query_events, user_roles — no standalone unique key, all treated as new
            new_count = total

        tables_result.append({
            "name": t_name,
            "total": total,
            "new": new_count,
            "conflicts": conflict_count,
        })

    return {
        "compatible": compatible,
        "warnings": warnings,
        "tables": tables_result,
    }


@app.post("/settings/database/import", dependencies=[Depends(_csrf_dependency)])
async def database_import(
    mode: str = "skip",
    current_user: dict = Depends(_require_admin),
    file: UploadFile = File(...),
):
    """Import data from a JSON or ZIP export file. mode='skip' or 'overwrite'."""
    if mode not in ("skip", "overwrite"):
        raise HTTPException(status_code=400, detail="mode must be 'skip' or 'overwrite'")

    try:
        file_content = await file.read()
        if len(file_content) > _MAX_IMPORT_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large (max {_MAX_IMPORT_FILE_SIZE // (1024*1024)}MB)")
        if file.filename and file.filename.lower().endswith('.zip'):
            zip_buffer = io.BytesIO(file_content)
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > _MAX_IMPORT_UNCOMPRESSED_SIZE:
                    raise HTTPException(status_code=400, detail="ZIP uncompressed size exceeds limit")
                json_files = [n for n in zf.namelist() if n.endswith('.json')]
                if not json_files:
                    raise HTTPException(status_code=400, detail="ZIP file contains no JSON files")
                json_content = zf.read(json_files[0])
                import_data = json.loads(json_content)
        else:
            import_data = json.loads(file_content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid file: {str(e)}")

    if "metadata" not in import_data or "data" not in import_data:
        raise HTTPException(status_code=400, detail="Invalid export format")

    results = []

    # ID remapping: old export id -> new DB id
    site_id_map: dict[int, int] = {}
    role_id_map: dict[int, int] = {}
    user_id_map: dict[int, int] = {}

    async with database.transaction():
        for t_name in _IMPORT_ORDER:
            if t_name not in import_data.get("data", {}):
                continue
            if t_name not in _EXPORTABLE_TABLES:
                continue

            rows = import_data["data"][t_name]
            tbl = _TABLE_MAP[t_name]
            valid_columns = {c.name for c in tbl.columns}

            imported = 0
            skipped = 0
            overwritten = 0

            for row in rows:
                old_id = row.get("id")

                # --- roles ---
                if t_name == "roles":
                    row_data = {
                        k: v for k, v in row.items()
                        if k != "id" and k in valid_columns
                    }
                    name = row.get("name")
                    existing = (
                        await database.fetch_one(
                            roles.select().where(roles.c.name == name)
                        )
                        if name
                        else None
                    )
                    if existing:
                        if old_id is not None:
                            role_id_map[old_id] = existing["id"]
                        if mode == "skip":
                            skipped += 1
                        else:
                            update_vals = {}
                            if row_data.get("description") is not None:
                                update_vals["description"] = row_data["description"]
                            if update_vals:
                                await database.execute(
                                    roles.update()
                                    .where(roles.c.id == existing["id"])
                                    .values(**update_vals)
                                )
                            overwritten += 1
                    else:
                        new_id = await database.execute(
                            roles.insert().values(**row_data)
                        )
                        if old_id is not None:
                            role_id_map[old_id] = new_id
                        imported += 1

                # --- users ---
                elif t_name == "users":
                    row_data = {
                        k: v for k, v in row.items()
                        if k != "id" and k in valid_columns
                    }
                    email = row.get("email")
                    existing = (
                        await database.fetch_one(
                            users.select().where(users.c.email == email)
                        )
                        if email
                        else None
                    )
                    if existing:
                        if old_id is not None:
                            user_id_map[old_id] = existing["id"]
                        if mode == "skip":
                            skipped += 1
                        else:
                            # Overwrite: update allowed fields only (not avatar_bytes)
                            update_vals = {}
                            for field in ("full_name", "status", "preferences", "password_hash"):
                                if field in row_data:
                                    update_vals[field] = row_data[field]
                            if update_vals:
                                now = datetime.now(timezone.utc)
                                update_vals["updated_at"] = now
                                await database.execute(
                                    users.update()
                                    .where(users.c.id == existing["id"])
                                    .values(**update_vals)
                                )
                            overwritten += 1
                    else:
                        # Ensure required derived fields exist
                        if "email_normalized" not in row_data and email:
                            row_data["email_normalized"] = normalize_email(email)
                        if "username_normalized" not in row_data and row_data.get("username"):
                            row_data["username_normalized"] = normalize_username(row_data["username"])
                        if "avatar_source" not in row_data:
                            row_data["avatar_source"] = "none"
                        if "preferences" not in row_data:
                            row_data["preferences"] = {}
                        if "status" not in row_data:
                            row_data["status"] = "active"
                        now = datetime.now(timezone.utc)
                        if "created_at" not in row_data:
                            row_data["created_at"] = now
                        if "updated_at" not in row_data:
                            row_data["updated_at"] = now
                        new_id = await database.execute(
                            users.insert().values(**row_data)
                        )
                        if old_id is not None:
                            user_id_map[old_id] = new_id
                        imported += 1

                # --- user_roles ---
                elif t_name == "user_roles":
                    old_user_id = row.get("user_id")
                    old_role_id = row.get("role_id")
                    # Remap IDs
                    new_user_id = user_id_map.get(old_user_id) if old_user_id is not None else None
                    new_role_id = role_id_map.get(old_role_id) if old_role_id is not None else None
                    if new_user_id is None or new_role_id is None:
                        skipped += 1
                        continue
                    # Check for duplicate
                    existing = await database.fetch_one(
                        user_roles.select().where(
                            (user_roles.c.user_id == new_user_id) &
                            (user_roles.c.role_id == new_role_id)
                        )
                    )
                    if existing:
                        skipped += 1
                    else:
                        await database.execute(
                            user_roles.insert().values(user_id=new_user_id, role_id=new_role_id)
                        )
                        imported += 1

                # --- sites ---
                elif t_name == "sites":
                    row_data = {
                        k: v for k, v in row.items()
                        if k != "id" and k in valid_columns
                    }
                    url = row.get("url")
                    existing = (
                        await database.fetch_one(
                            sites.select().where(sites.c.url == url)
                        )
                        if url
                        else None
                    )
                    if existing:
                        if old_id is not None:
                            site_id_map[old_id] = existing["id"]
                        if mode == "skip":
                            skipped += 1
                        else:
                            await database.execute(
                                sites.update()
                                .where(sites.c.id == existing["id"])
                                .values(**row_data)
                            )
                            overwritten += 1
                    else:
                        new_id = await database.execute(
                            sites.insert().values(**row_data)
                        )
                        if old_id is not None:
                            site_id_map[old_id] = new_id
                        imported += 1

                # --- articles ---
                elif t_name == "articles":
                    row_data = {
                        k: v for k, v in row.items()
                        if k != "id" and k in valid_columns
                    }
                    # Remap site_id FK
                    old_site_id = row_data.get("site_id")
                    if old_site_id is not None and old_site_id in site_id_map:
                        row_data["site_id"] = site_id_map[old_site_id]
                    url = row.get("url")
                    existing = (
                        await database.fetch_one(
                            articles.select().where(articles.c.url == url)
                        )
                        if url
                        else None
                    )
                    if existing:
                        if mode == "skip":
                            skipped += 1
                        else:
                            await database.execute(
                                articles.update()
                                .where(articles.c.id == existing["id"])
                                .values(**row_data)
                            )
                            overwritten += 1
                    else:
                        await database.execute(
                            articles.insert().values(**row_data)
                        )
                        imported += 1

                else:
                    # crawl_attempts, rss_query_events — always insert, remap site_id
                    row_data = {
                        k: v for k, v in row.items()
                        if k != "id" and k in valid_columns
                    }
                    old_site_id = row_data.get("site_id")
                    if old_site_id is not None and old_site_id in site_id_map:
                        row_data["site_id"] = site_id_map[old_site_id]
                    await database.execute(tbl.insert().values(**row_data))
                    imported += 1

            results.append({
                "name": t_name,
                "imported": imported,
                "skipped": skipped,
                "overwritten": overwritten,
            })

    return {"tables": results}


# ============================================================
# EXISTING API ENDPOINTS (with auth protection)
# ============================================================

@app.post("/analyze/list")
async def analyze_list_structure(url: str, debug: bool = False, current_user: dict = Depends(_require_user)):
    """Parse website list page structure (calls AI)"""
    start_time = time.time()
    log_with_time(f"[Analyze List] Starting analysis for: {url}")

    fetch_start = time.time()
    page = await fetch_page(url)
    fetch_duration = time.time() - fetch_start
    log_with_time(f"[Analyze List] fetch_page completed: {fetch_duration:.2f}s")

    if page is None:
        return {"rules": None, "error": "Failed to fetch page content. The website may be blocking crawlers or taking too long to load."}
    html = page.html_content

    dw = create_debug_writer(debug, "analyze_list", url.replace("https://", "").replace("http://", "").split("/")[0][:30])
    if debug:
        dw.save("01", "raw_html.html", html)

    ai_start = time.time()
    try:
        rules = await analyze_with_providers(
            html, "list",
            user_id=current_user["id"],
            db=database,
            tables=_ai_tables,
            kek_backend=_kek_backend,
            url=url,
            debug_writer=dw,
        )
    except NoProviderAvailableError:
        return {"rules": None, "error": "No AI provider available. Configure a provider in AI Service settings."}
    ai_duration = time.time() - ai_start
    log_with_time(f"[Analyze List] analyze completed: {ai_duration:.2f}s")

    if not rules:
        return {"rules": None, "error": "AI analysis failed. Check backend logs for details."}

    response = {"rules": rules, "preview_html": html[:500], "error": None}
    if debug:
        response["debug_dir"] = dw.debug_dir

    total_duration = time.time() - start_time
    log_with_time(f"[Analyze List] Total duration: {total_duration:.2f}s")
    return response

@app.post("/analyze/content")
async def analyze_content_structure(url: str, debug: bool = False, current_user: dict = Depends(_require_user)):
    """解析網站內容頁結構 (呼叫 AI)"""
    start_time = time.time()
    log_with_time(f"[Analyze Content] Starting analysis for: {url}")

    fetch_start = time.time()
    page = await fetch_page(url)
    fetch_duration = time.time() - fetch_start
    log_with_time(f"[Analyze Content] fetch_page completed: {fetch_duration:.2f}s")

    if page is None:
        raise HTTPException(status_code=500, detail="Failed to fetch page content")
    html = page.html_content

    dw = create_debug_writer(debug, "analyze_content", url.replace("https://", "").replace("http://", "").split("/")[0][:30])
    if debug:
        dw.save("01", "raw_html.html", html)

    ai_start = time.time()
    try:
        rules = await analyze_with_providers(
            html, "content",
            user_id=current_user["id"],
            db=database,
            tables=_ai_tables,
            kek_backend=_kek_backend,
            url=url,
            debug_writer=dw,
        )
    except NoProviderAvailableError:
        raise HTTPException(status_code=503, detail="No AI provider available. Configure a provider in AI Service settings.")
    ai_duration = time.time() - ai_start
    log_with_time(f"[Analyze Content] analyze completed: {ai_duration:.2f}s")

    response: dict = {"rules": rules}
    if debug:
        response["debug_dir"] = dw.debug_dir

    total_duration = time.time() - start_time
    log_with_time(f"[Analyze Content] Total duration: {total_duration:.2f}s")
    return response

@app.post("/crawl/preview")
async def preview_crawl(req: PreviewRequest, current_user: dict = Depends(_require_user)):
    """乾跑預覽爬蟲，支援 list / content / both 模式"""
    from core.crawler import test_crawl_logic

    dw = create_debug_writer(req.debug or False, "preview", req.url.replace("https://", "").replace("http://", "").split("/")[0][:30])

    results = await test_crawl_logic(
        req.url,
        req.list_rules,
        req.content_rules,
        mode=req.mode or "both",
        target_url=req.target_url,
        debug_writer=dw,
        scrape_method=req.scrape_method or "scrapling",
    )

    response = {"status": "success", "data": results}
    if req.debug:
        response["debug_dir"] = dw.debug_dir
    return response

@app.post("/sites/", dependencies=[Depends(_csrf_dependency)])
async def create_site(
    site: SiteCreate,
    rules: RulesInput,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(_require_user),
):
    """新增網站並開始背景爬取"""
    query = sites.insert().values(
        url=site.url,
        name=site.name,
        list_rules=rules.list_rules,
        content_rules=rules.content_rules,
        consecutive_failure_count=0,
        refresh_frequency=site.refresh_frequency,
        scrape_method=site.scrape_method or "scrapling",
        owner_user_id=current_user["id"],
    )
    site_id = await database.execute(query)
    # 背景觸發爬蟲（初始抓取視為手動重爬），with attempt recording
    background_tasks.add_task(
        _record_crawl_attempt,
        site_id=site_id,
        trigger_type="manual",
        url=site.url,
        list_rules=rules.list_rules,
        content_rules=rules.content_rules,
        force_update=True,
        scrape_method=site.scrape_method or "scrapling",
        owner_user_id=current_user["id"],
    )
    return {"id": site_id, "status": "created and crawling started"}

@app.get("/sites/{site_id}")
async def get_site(site_id: int, current_user: dict = Depends(_require_user)):
    """取得特定網站資詳細資料"""
    query = sites.select().where(sites.c.id == site_id)
    row = await database.fetch_one(query)
    if not row:
        raise HTTPException(status_code=404, detail="Site not found")
    return dict(row)

@app.put("/sites/{site_id}", dependencies=[Depends(_csrf_dependency)])
async def update_site(site_id: int, update_data: SiteUpdate, current_user: dict = Depends(_require_user)):
    """更新網站設定"""
    query = sites.select().where(sites.c.id == site_id)
    site = await database.fetch_one(query)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    is_admin = "admin" in current_user.get("roles", [])
    if not check_site_owner_or_admin(site, current_user["id"], is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to modify this site")

    values = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not values:
        return {"status": "no change"}

    query = sites.update().where(sites.c.id == site_id).values(**values)
    await database.execute(query)
    return {"status": "updated", "site_id": site_id}

@app.post("/sites/{site_id}/duplicate", dependencies=[Depends(_csrf_dependency)])
async def duplicate_site(site_id: int, current_user: dict = Depends(_require_user)):
    """複製網站設定 (不含文章，不自動爬取)"""
    query = sites.select().where(sites.c.id == site_id)
    site = await database.fetch_one(query)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    new_query = sites.insert().values(
        url=site['url'],
        name=f"[Copy] {site['name']}",
        list_rules=site['list_rules'],
        content_rules=site['content_rules'],
        refresh_frequency=site['refresh_frequency'],
        consecutive_failure_count=0,
        scrape_method=site['scrape_method'] or "scrapling",
        owner_user_id=current_user["id"],
    )
    new_id = await database.execute(new_query)
    return {"id": new_id, "status": "duplicated"}

@app.get("/sites/")
async def list_sites(current_user: dict = Depends(_require_user)):
    """列出所有網站"""
    query = sites.select()
    rows = await database.fetch_all(query)
    return [dict(row) for row in rows]

@app.delete("/sites/{site_id}", dependencies=[Depends(_csrf_dependency)])
async def delete_site(site_id: int, current_user: dict = Depends(_require_user)):
    """刪除指定網站及其所有文章與相關事件"""
    site = await database.fetch_one(sites.select().where(sites.c.id == site_id))
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    is_admin = "admin" in current_user.get("roles", [])
    if not check_site_owner_or_admin(site, current_user["id"], is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to modify this site")

    # 刪除相關 crawl attempts 和 RSS query events
    await database.execute(crawl_attempts.delete().where(crawl_attempts.c.site_id == site_id))
    await database.execute(rss_query_events.delete().where(rss_query_events.c.site_id == site_id))

    # 刪除該網站的所有文章
    query = articles.delete().where(articles.c.site_id == site_id)
    await database.execute(query)

    # 刪除該網站
    query = sites.delete().where(sites.c.id == site_id)
    await database.execute(query)

    return {"status": "deleted", "site_id": site_id}

@app.get("/rss/{site_identifier}")
async def get_rss(site_identifier: str, limit: int = 10):
    """取得指定網站的 RSS Feed

    Args:
        site_identifier: 網站名稱（會被標準化）或 ID
        limit: 回傳文章數量上限，預設10，範圍5-30
    """
    # 限制 limit 範圍
    limit = max(5, min(30, limit))

    site = await get_site_by_name_or_id(site_identifier, database)
    if not site:
        # Record 404 RSS query event
        try:
            await database.execute(
                rss_query_events.insert().values(
                    site_id=None,
                    site_identifier=site_identifier,
                    requested_at=_utcnow_iso(),
                    limit_param=limit,
                    status_code=404,
                )
            )
        except Exception as e:
            log_with_time(f"[RSS] Failed to record 404 query event: {e}")
        raise HTTPException(status_code=404, detail="Site not found")

    site_name_normalized = normalize_site_name(site['name'])

    query = articles.select().where(articles.c.site_id == site['id']).order_by(articles.c.id.desc()).limit(limit)
    rows = await database.fetch_all(query)

    items = []
    for row in rows:
        pub_date = row['published_at']
        # Convert string to datetime if needed
        if isinstance(pub_date, str):
            try:
                pub_date = dateutil_parser.parse(pub_date)
            except Exception:
                pub_date = datetime.now()

        items.append(Item(
            title=row['title'],
            link=row['url'],
            description=row['content'],
            author=row['author'] or None,
            pubDate=pub_date
        ))

    feed = Feed(
        title=site['name'],
        link=site['url'],
        description=f"RSS feed for {site['name']}",
        items=items
    )

    # Record 200 RSS query event
    try:
        await database.execute(
            rss_query_events.insert().values(
                site_id=site['id'],
                site_identifier=site_identifier,
                requested_at=_utcnow_iso(),
                limit_param=limit,
                status_code=200,
            )
        )
    except Exception as e:
        log_with_time(f"[RSS] Failed to record 200 query event: {e}")

    return Response(content=feed.rss(), media_type="application/xml")

@app.post("/crawl/{site_id}", dependencies=[Depends(_csrf_dependency)])
async def trigger_crawl(site_id: int, background_tasks: BackgroundTasks, debug: bool = False, current_user: dict = Depends(_require_user)):
    """手動觸發指定網站爬取"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [API] trigger_crawl called for site {site_id}")
    query = sites.select().where(sites.c.id == site_id)
    site = await database.fetch_one(query)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    list_rules = site['list_rules'] if isinstance(site['list_rules'], dict) else json.loads(site['list_rules'])
    content_rules = site['content_rules'] if isinstance(site['content_rules'], dict) else json.loads(site['content_rules'])

    dw = create_debug_writer(debug, "crawl", site['name'][:30])

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [API] list_rules: {list_rules}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [API] content_rules: {content_rules}")

    background_tasks.add_task(
        _record_crawl_attempt,
        site_id=site['id'],
        trigger_type="manual",
        url=site['url'],
        list_rules=list_rules,
        content_rules=content_rules,
        force_update=True,
        scrape_method=site['scrape_method'] if site['scrape_method'] else "scrapling",
        debug_writer=dw,
        owner_user_id=current_user["id"],
    )
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [API] Background task added")

    response: dict = {"status": "crawl started"}
    if debug:
        response["debug_dir"] = dw.debug_dir
    return response


# --- Analytics API ---

@app.get("/analytics/overview")
async def get_analytics_overview(days: int = 30, current_user: dict = Depends(_require_user)):
    """Aggregated analytics overview for the dashboard.

    Returns summary metrics, chart datasets, and latest articles.
    All daily bucketing uses Asia/Taipei timezone.
    """
    # Clamp days to 7-90
    days = max(7, min(90, days))

    date_labels = _get_date_range(days)
    this_week_start, today, last_week_start, last_week_end = _get_week_boundaries()

    # --- Fetch all articles with analytics columns ---
    all_articles = await database.fetch_all(
        "SELECT id, site_id, published_at, created_at, word_count FROM articles"
    )

    # --- Fetch all sites for name mapping ---
    all_sites_rows = await database.fetch_all("SELECT id, name FROM sites")
    site_name_map = {row['id']: row['name'] for row in all_sites_rows}

    # --- Summary ---
    total_article_scrap = len(all_articles)

    # Per-article: parse created_at to Taipei date
    article_taipei_dates = []
    for a in all_articles:
        d = _parse_iso_to_taipei_date(a['created_at'])
        article_taipei_dates.append(d)

    # New articles this week / last week
    new_articles_this_week = 0
    new_articles_last_week = 0
    for d_str in article_taipei_dates:
        if d_str is None:
            continue
        try:
            from datetime import date as _date_cls
            d = _date_cls.fromisoformat(d_str)
        except Exception:
            continue
        if this_week_start <= d <= today:
            new_articles_this_week += 1
        if last_week_start <= d <= last_week_end:
            new_articles_last_week += 1

    # Weekly change pct
    new_articles_weekly_change_pct = None
    if new_articles_last_week > 0:
        new_articles_weekly_change_pct = round(
            ((new_articles_this_week - new_articles_last_week) / new_articles_last_week) * 100, 1
        )

    # --- Median feed update minutes ---
    # Group articles by site_id, sort by published_at, compute intervals
    from collections import defaultdict
    site_articles_times: dict[int, list[datetime]] = defaultdict(list)
    for a in all_articles:
        if a['published_at'] and a['site_id']:
            try:
                dt = dateutil_parser.parse(a['published_at'])
                site_articles_times[a['site_id']].append(dt)
            except Exception:
                pass

    feed_avg_intervals = []
    for sid, times in site_articles_times.items():
        if len(times) < 2:
            continue
        times.sort()
        diffs = [(times[i+1] - times[i]).total_seconds() / 60.0 for i in range(len(times) - 1)]
        diffs = [d for d in diffs if d > 0]  # skip zero/negative diffs
        if diffs:
            avg_interval = sum(diffs) / len(diffs)
            feed_avg_intervals.append(avg_interval)

    median_feed_update_minutes = None
    if feed_avg_intervals:
        median_feed_update_minutes = round(statistics.median(feed_avg_intervals), 1)

    # Median feed update change pct (simplified: compare overall, not weekly, as insufficient data is common)
    median_feed_update_change_pct = None

    # --- Median article word count ---
    word_counts = [a['word_count'] for a in all_articles if a['word_count'] is not None and a['word_count'] > 0]
    median_article_word_count = None
    if word_counts:
        median_article_word_count = round(statistics.median(word_counts))

    summary = {
        "total_article_scrap": total_article_scrap,
        "new_articles_last_week": new_articles_last_week,
        "new_articles_this_week": new_articles_this_week,
        "new_articles_weekly_change_pct": new_articles_weekly_change_pct,
        "median_feed_update_minutes": median_feed_update_minutes,
        "median_feed_update_change_pct": median_feed_update_change_pct,
        "median_article_word_count": median_article_word_count,
        "median_article_word_count_trend_label": "Across all stored articles",
    }

    # --- Articles counts overview (daily new by feed source) ---
    # Build: date -> site_id -> count
    daily_feed_counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for a, d_str in zip(all_articles, article_taipei_dates):
        if d_str and d_str in date_labels:
            sid = a['site_id']
            daily_feed_counts[d_str][sid] += 1

    # Collect unique site_ids that appear in window
    active_site_ids = set()
    for d_str in date_labels:
        for sid in daily_feed_counts.get(d_str, {}):
            active_site_ids.add(sid)
    active_site_ids = sorted(active_site_ids)

    # Color palette for feeds
    FEED_COLORS = [
        "#1ABB9C", "#7533f9", "#198754", "#ffc107", "#dc3545",
        "#0d6efd", "#6610f2", "#fd7e14", "#20c997", "#6f42c1",
        "#d63384", "#0dcaf0", "#adb5bd", "#e35d6a", "#6ea8fe",
    ]

    articles_counts_overview = {
        "labels": date_labels,
        "datasets": [
            {
                "label": site_name_map.get(sid, f"Feed #{sid}"),
                "data": [daily_feed_counts.get(d, {}).get(sid, 0) for d in date_labels],
                "color": FEED_COLORS[i % len(FEED_COLORS)],
            }
            for i, sid in enumerate(active_site_ids)
        ]
    }

    # --- Feeds distribution (past 30 days) ---
    feed_dist: dict[int, int] = defaultdict(int)
    for a, d_str in zip(all_articles, article_taipei_dates):
        if d_str and d_str in date_labels:
            feed_dist[a['site_id']] += 1

    feeds_distribution = {
        "items": [
            {
                "name": site_name_map.get(sid, f"Feed #{sid}"),
                "value": count,
                "color": FEED_COLORS[i % len(FEED_COLORS)],
            }
            for i, (sid, count) in enumerate(sorted(feed_dist.items(), key=lambda x: -x[1]))
        ]
    }

    # --- Traffic metrics: RSS query ---
    rss_events = await database.fetch_all("SELECT requested_at, status_code FROM rss_query_events")
    daily_rss_counts: dict[str, int] = defaultdict(int)
    for evt in rss_events:
        d = _parse_iso_to_taipei_date(evt['requested_at'])
        if d and d in date_labels:
            daily_rss_counts[d] += 1

    rss_query_dataset = {
        "labels": date_labels,
        "datasets": [{"label": "RSS Queries", "data": [daily_rss_counts.get(d, 0) for d in date_labels]}]
    }

    # --- Traffic metrics: Article scrap (from crawl_attempts) ---
    crawl_rows = await database.fetch_all(
        "SELECT started_at, articles_saved, articles_updated, articles_failed FROM crawl_attempts"
    )
    daily_scrap_success: dict[str, int] = defaultdict(int)
    daily_scrap_fail: dict[str, int] = defaultdict(int)
    for cr in crawl_rows:
        d = _parse_iso_to_taipei_date(cr['started_at'])
        if d and d in date_labels:
            daily_scrap_success[d] += (cr['articles_saved'] or 0) + (cr['articles_updated'] or 0)
            daily_scrap_fail[d] += (cr['articles_failed'] or 0)

    article_scrap_dataset = {
        "labels": date_labels,
        "datasets": [
            {"label": "Success", "data": [daily_scrap_success.get(d, 0) for d in date_labels]},
            {"label": "Fail", "data": [daily_scrap_fail.get(d, 0) for d in date_labels]},
        ]
    }

    traffic_metrics = {
        "rss_query": rss_query_dataset,
        "article_scrap": article_scrap_dataset,
    }

    # --- Article growth (cumulative) ---
    # Sort all articles by created_at Taipei date, compute cumulative by day
    sorted_dates = sorted([d for d in article_taipei_dates if d is not None])
    cumulative = 0
    date_cumulative: dict[str, int] = {}
    date_idx = 0
    for d in date_labels:
        while date_idx < len(sorted_dates) and sorted_dates[date_idx] <= d:
            cumulative += 1
            date_idx += 1
        date_cumulative[d] = cumulative

    article_growth = {
        "labels": date_labels,
        "datasets": [{"label": "Total Articles", "data": [date_cumulative.get(d, 0) for d in date_labels]}]
    }

    # --- Latest articles ---
    latest_rows = await database.fetch_all(
        "SELECT a.site_id, a.title, a.url, a.created_at, a.word_count "
        "FROM articles a ORDER BY a.created_at DESC NULLS LAST LIMIT 10"
    )
    latest_articles = [
        {
            "feed_name": site_name_map.get(row['site_id'], f"Feed #{row['site_id']}"),
            "article_title": row['title'],
            "update_time": row['created_at'] or "",
            "word_count": row['word_count'] or 0,
            "ori_url": row['url'],
        }
        for row in latest_rows
    ]

    return {
        "summary": summary,
        "articles_counts_overview": articles_counts_overview,
        "feeds_distribution": feeds_distribution,
        "traffic_metrics": traffic_metrics,
        "article_growth": article_growth,
        "daily_rss_query": rss_query_dataset,
        "latest_articles": latest_articles,
    }


@app.get("/articles/list")
async def list_articles(
    filter: str = "all",
    search: str = "",
    page: int = 1,
    page_size: int = 100,
    current_user: dict = Depends(_require_user),
):
    """List articles with time filtering, search, and pagination.

    filter: today | week | month | all
    search: optional text search against title and feed name
    page / page_size: pagination (1-based page index)
    """
    from datetime import timezone as _tz

    # Sanitize inputs
    page = max(1, page)
    page_size = max(1, min(500, page_size))
    if filter not in ("today", "week", "month", "all"):
        filter = "all"

    # --- Fetch site name map (same pattern as analytics_overview) ---
    all_sites_rows = await database.fetch_all("SELECT id, name FROM sites")
    site_name_map = {row['id']: row['name'] for row in all_sites_rows}

    # --- Compute time boundaries in Taipei timezone ---
    now_taipei = datetime.now(TAIPEI_TZ)
    today_start = datetime(now_taipei.year, now_taipei.month, now_taipei.day, 0, 0, 0, tzinfo=TAIPEI_TZ)
    today_end = today_start + timedelta(days=1)
    week_start = today_start - timedelta(days=6)
    month_start = today_start - timedelta(days=29)

    today_start_utc = today_start.astimezone(_tz.utc)
    today_end_utc = today_end.astimezone(_tz.utc)
    week_start_utc = week_start.astimezone(_tz.utc)
    month_start_utc = month_start.astimezone(_tz.utc)

    # --- Build search condition ---
    search_sql = ""
    search_params: dict = {}
    if search.strip():
        search_sql = (
            " AND (a.title ILIKE :search_pat"
            " OR a.site_id IN (SELECT id FROM sites WHERE name ILIKE :search_pat))"
        )
        search_params["search_pat"] = f"%{search.strip()}%"

    # --- filter_counts: compute counts for all 4 time ranges ---
    async def _count(extra_time_sql: str, extra_time_params: dict) -> int:
        sql = "SELECT COUNT(*) AS cnt FROM articles a WHERE 1=1" + search_sql + extra_time_sql
        row = await database.fetch_one(sql, values={**search_params, **extra_time_params})
        return row['cnt'] if row else 0

    today_count = await _count(
        " AND CAST(a.created_at AS TIMESTAMPTZ) >= :t_from"
        " AND CAST(a.created_at AS TIMESTAMPTZ) < :t_to",
        {"t_from": today_start_utc, "t_to": today_end_utc},
    )
    week_count = await _count(
        " AND CAST(a.created_at AS TIMESTAMPTZ) >= :t_from",
        {"t_from": week_start_utc},
    )
    month_count = await _count(
        " AND CAST(a.created_at AS TIMESTAMPTZ) >= :t_from",
        {"t_from": month_start_utc},
    )
    all_count = await _count("", {})

    filter_counts = {
        "today": today_count,
        "week": week_count,
        "month": month_count,
        "all": all_count,
    }

    # --- Build time condition for the main paginated query ---
    time_sql = ""
    time_params: dict = {}
    if filter == "today":
        time_sql = (
            " AND CAST(a.created_at AS TIMESTAMPTZ) >= :main_from"
            " AND CAST(a.created_at AS TIMESTAMPTZ) < :main_to"
        )
        time_params = {"main_from": today_start_utc, "main_to": today_end_utc}
    elif filter == "week":
        time_sql = " AND CAST(a.created_at AS TIMESTAMPTZ) >= :main_from"
        time_params = {"main_from": week_start_utc}
    elif filter == "month":
        time_sql = " AND CAST(a.created_at AS TIMESTAMPTZ) >= :main_from"
        time_params = {"main_from": month_start_utc}
    # "all" → no time condition

    total = filter_counts[filter]

    # --- Paginated main query ---
    offset = (page - 1) * page_size
    main_sql = (
        "SELECT a.site_id, a.title, a.url, a.image_url, a.author, a.created_at, a.word_count "
        "FROM articles a WHERE 1=1"
        + search_sql
        + time_sql
        + " ORDER BY a.created_at DESC NULLS LAST"
        " LIMIT :lim OFFSET :off"
    )
    all_params = {**search_params, **time_params, "lim": page_size, "off": offset}
    rows = await database.fetch_all(main_sql, values=all_params)

    article_list = [
        {
            "article_title": row['title'],
            "image_url": row['image_url'],
            "feed_name": site_name_map.get(row['site_id'], f"Feed #{row['site_id']}"),
            "word_count": row['word_count'] or 0,
            "update_time": row['created_at'] or "",
            "ori_url": row['url'],
            "author": row['author'],
        }
        for row in rows
    ]

    return {
        "articles": article_list,
        "filter_counts": filter_counts,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    try:
        await database.execute("SELECT 1")
        return {"status": "healthy", "db": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "db": str(e)}

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
