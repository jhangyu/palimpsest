"""Initial schema migration."""
from .registry import Migration, MIGRATIONS


def up(connection) -> None:
    """Apply initial schema DDL."""
    from sqlalchemy import text as sa_text
    from datetime import datetime, timezone as _tz

    # --- Articles columns ---
    for col, col_type in [("created_at", "VARCHAR"), ("updated_at", "VARCHAR"), ("word_count", "INTEGER")]:
        try:
            connection.execute(sa_text(f"ALTER TABLE articles ADD COLUMN IF NOT EXISTS {col} {col_type}"))
        except Exception as e:
            print(f"[Migration v0.1.0] note: articles.{col}: {e}")

    # --- Articles timestamptz migration ---
    for col in ("published_at", "created_at", "updated_at"):
        try:
            connection.execute(sa_text(
                f"ALTER TABLE articles ALTER COLUMN {col} TYPE TIMESTAMPTZ "
                f"USING {col}::timestamptz"
            ))
        except Exception as e:
            err_str = str(e).lower()
            if "already" not in err_str and "same type" not in err_str:
                print(f"[Migration v0.1.0] note: articles.{col} TIMESTAMPTZ: {e}")

    # --- Auth tables ---
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
            print(f"[Migration v0.1.0] note: auth table: {e}")

    # --- Indexes ---
    index_stmts = [
        "CREATE INDEX IF NOT EXISTS idx_articles_site_id ON articles(site_id)",
        "CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at)",
        "CREATE INDEX IF NOT EXISTS idx_rss_query_events_requested_at ON rss_query_events(requested_at)",
        "CREATE INDEX IF NOT EXISTS idx_crawl_attempts_started_at ON crawl_attempts(started_at)",
        "CREATE INDEX IF NOT EXISTS idx_crawl_attempts_site_started ON crawl_attempts(site_id, started_at)",
        "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_expires ON auth_sessions(user_id, expires_at, revoked_at)",
        "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user ON password_reset_tokens(user_id, expires_at, used_at)",
        "CREATE INDEX IF NOT EXISTS idx_email_verification_tokens_user ON email_verification_tokens(user_id, expires_at, used_at)",
        "CREATE INDEX IF NOT EXISTS idx_auth_rate_limits_scope_locked ON auth_rate_limits(scope, locked_until)",
    ]

    for stmt in index_stmts:
        try:
            connection.execute(sa_text(stmt))
        except Exception as e:
            print(f"[Migration v0.1.0] note: index: {e}")

    # --- Partial unique indexes ---
    partial_idx_stmts = [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_pending_email_normalized ON users(pending_email_normalized) WHERE pending_email_normalized IS NOT NULL",
    ]
    for stmt in partial_idx_stmts:
        try:
            connection.execute(sa_text(stmt))
        except Exception as e:
            print(f"[Migration v0.1.0] note: partial unique index: {e}")

    # --- Roles seeding ---
    try:
        now_ts = datetime.now(_tz.utc)
        connection.execute(sa_text(
            "INSERT INTO roles (name, description, created_at) VALUES (:name, :desc, :ts) ON CONFLICT (name) DO NOTHING"
        ), {"name": "admin", "desc": "Administrator role with full access", "ts": now_ts})
        connection.execute(sa_text(
            "INSERT INTO roles (name, description, created_at) VALUES (:name, :desc, :ts) ON CONFLICT (name) DO NOTHING"
        ), {"name": "user", "desc": "Standard user role", "ts": now_ts})
    except Exception as e:
        print(f"[Migration v0.1.0] note: role seeding: {e}")

    # --- Sites columns (post-commit block) ---
    # filter_rules
    try:
        connection.execute(sa_text("ALTER TABLE sites ADD COLUMN IF NOT EXISTS filter_rules JSONB"))
    except Exception as e:
        print(f"[Migration v0.1.0] note: filter_rules: {e}")

    # auto crawl frequency columns
    auto_frequency_statements = [
        "ALTER TABLE sites ADD COLUMN IF NOT EXISTS refresh_frequency_mode VARCHAR NOT NULL DEFAULT 'manual'",
        "ALTER TABLE sites ADD COLUMN IF NOT EXISTS auto_refresh_frequency_minutes DOUBLE PRECISION",
        "ALTER TABLE sites ADD COLUMN IF NOT EXISTS next_crawl_at TIMESTAMPTZ",
        "ALTER TABLE sites ADD COLUMN IF NOT EXISTS last_crawled_at TIMESTAMPTZ",
        "CREATE INDEX IF NOT EXISTS idx_sites_next_crawl_at ON sites(next_crawl_at)",
        """
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_sites_refresh_frequency_mode') THEN
        ALTER TABLE sites ADD CONSTRAINT ck_sites_refresh_frequency_mode CHECK (refresh_frequency_mode IN ('manual', 'auto'));
    END IF;
END $$
""",
    ]
    for stmt in auto_frequency_statements:
        try:
            connection.execute(sa_text(stmt))
        except Exception as e:
            print(f"[Migration v0.1.0] note: auto crawl frequency: {e}")

    # RSS input source columns
    try:
        connection.execute(sa_text(
            "ALTER TABLE sites ADD COLUMN IF NOT EXISTS source_type VARCHAR NOT NULL DEFAULT 'html'"
        ))
    except Exception as e:
        print(f"[Migration v0.1.0] note: source_type: {e}")

    try:
        connection.execute(sa_text(
            "ALTER TABLE sites ADD COLUMN IF NOT EXISTS rss_full_content BOOLEAN NOT NULL DEFAULT FALSE"
        ))
    except Exception as e:
        print(f"[Migration v0.1.0] note: rss_full_content: {e}")

    try:
        connection.execute(sa_text(
            "ALTER TABLE sites ADD COLUMN IF NOT EXISTS website_url VARCHAR"
        ))
    except Exception as e:
        print(f"[Migration v0.1.0] note: website_url: {e}")

    # RSS source constraints
    try:
        connection.execute(sa_text("""
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_sites_source_type') THEN
        ALTER TABLE sites ADD CONSTRAINT ck_sites_source_type CHECK (source_type IN ('html', 'rss'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_sites_rss_full_content') THEN
        ALTER TABLE sites ADD CONSTRAINT ck_sites_rss_full_content CHECK (rss_full_content = FALSE OR source_type = 'rss');
    END IF;
END $$
"""))
    except Exception as e:
        print(f"[Migration v0.1.0] note: RSS source constraints: {e}")

    print("[Migration v0.1.0] completed.")


migration = Migration(
    version="0.1.0",
    description="Initial schema: articles, auth tables, sites columns, indexes, roles",
    up=up,
)
MIGRATIONS.append(migration)
