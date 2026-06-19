"""Database connection, metadata, and all SQLAlchemy table definitions.

Extracted from backend/main.py to serve as the single source of truth
for schema objects shared across routers.
"""

import os

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from core.ai_provider_migrations import define_ai_provider_tables

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://palimpsest:palimpsest@db:5432/palimpsest")
# Ensure asyncpg driver for SQLAlchemy 2.0 async
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=15)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
metadata = sqlalchemy.MetaData()

# ---------------------------------------------------------------------------
# Database Schema
# ---------------------------------------------------------------------------
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
    sqlalchemy.Column("published_at", sqlalchemy.DateTime(timezone=True), nullable=True),
    # Analytics columns
    sqlalchemy.Column("created_at", sqlalchemy.DateTime(timezone=True), nullable=True),
    sqlalchemy.Column("updated_at", sqlalchemy.DateTime(timezone=True), nullable=True),
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

schema_versions = sqlalchemy.Table(
    "schema_versions", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("version", sqlalchemy.String, nullable=False, unique=True),
    sqlalchemy.Column("description", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("applied_at", sqlalchemy.DateTime(timezone=True), nullable=False),
)

# --- AI Provider Tables ---
ai_tables = define_ai_provider_tables(metadata)

# ---------------------------------------------------------------------------
# FastAPI Depends functions (DI layer)
# ---------------------------------------------------------------------------

from fastapi import Request  # noqa: E402


async def get_db(request: Request):
    """FastAPI dependency: inject AsyncSession from session factory."""
    async with async_session_factory() as session:
        yield session


async def get_kek_dep(request: Request):
    """FastAPI dependency: inject KEK backend from app.state."""
    return request.app.state.kek_backend


async def get_llm_profiles_enabled_dep(request: Request) -> bool:
    """FastAPI dependency: inject LLM profiles enabled flag from app.state."""
    return request.app.state.llm_profiles_enabled
