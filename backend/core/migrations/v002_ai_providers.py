"""AI provider schema migration."""
from .registry import Migration, MIGRATIONS


def up(connection) -> None:
    """Apply AI provider tables, user secret keys, and owner_user_id column."""
    from sqlalchemy import text as sa_text

    statements = [
        """
        CREATE TABLE IF NOT EXISTS user_secret_keys (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            encrypted_dek BYTEA NOT NULL,
            dek_nonce BYTEA NOT NULL CHECK (octet_length(dek_nonce) = 12),
            algorithm VARCHAR NOT NULL,
            kek_version VARCHAR NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_ai_providers (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            label VARCHAR NOT NULL,
            protocol VARCHAR NOT NULL CHECK (
                protocol IN ('openai', 'anthropic', 'gemini')
            ),
            base_url TEXT NOT NULL,
            model VARCHAR NOT NULL,
            temperature DOUBLE PRECISION CHECK (
                temperature IS NULL OR (temperature >= 0 AND temperature <= 2)
            ),
            max_tokens INTEGER NOT NULL CHECK (
                max_tokens > 0 AND max_tokens <= 1000000
            ),
            thinking BOOLEAN NOT NULL DEFAULT false,
            effort VARCHAR NOT NULL DEFAULT 'low' CHECK (
                effort IN ('low', 'medium', 'high')
            ),
            encrypted_api_key BYTEA NOT NULL,
            credential_nonce BYTEA NOT NULL CHECK (
                octet_length(credential_nonce) = 12
            ),
            credential_version INTEGER NOT NULL DEFAULT 1,
            api_key_last4 VARCHAR,
            api_key_mask VARCHAR,
            priority INTEGER NOT NULL DEFAULT 0 CHECK (priority >= 0),
            enabled BOOLEAN NOT NULL DEFAULT true,
            health_status VARCHAR NOT NULL DEFAULT 'unknown',
            last_tested_at TIMESTAMPTZ,
            last_success_at TIMESTAMPTZ,
            last_failure_at TIMESTAMPTZ,
            last_failure_code VARCHAR,
            source_type VARCHAR,
            source_id INTEGER,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT uq_user_ai_providers_user_label UNIQUE (user_id, label),
            CONSTRAINT ck_user_ai_providers_source_pair CHECK (
                (source_type IS NULL AND source_id IS NULL) OR
                (source_type IS NOT NULL AND source_id IS NOT NULL)
            )
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_user_ai_providers_user_priority
        ON user_ai_providers(user_id, priority, id)
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_user_ai_providers_legacy_source
        ON user_ai_providers(user_id, source_type, source_id)
        WHERE source_type IS NOT NULL AND source_id IS NOT NULL
        """,
        "ALTER TABLE sites ADD COLUMN IF NOT EXISTS owner_user_id INTEGER",
        "CREATE INDEX IF NOT EXISTS idx_sites_owner_user_id ON sites(owner_user_id)",
    ]

    for stmt in statements:
        try:
            connection.execute(sa_text(stmt))
        except Exception as e:
            print(f"[Migration v0.2.0] note: {e}")

    print("[Migration v0.2.0] completed.")


migration = Migration(
    version="0.2.0",
    description="AI provider tables, user secret keys, owner_user_id",
    up=up,
)
MIGRATIONS.append(migration)
