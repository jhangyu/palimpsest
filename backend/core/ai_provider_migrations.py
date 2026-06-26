"""
---
name: ai_provider_migrations
description: "Schema definitions, migration SQL, and legacy token migration helpers for per-user AI provider settings"
type: core
target:
  layer: backend
  domain: ai-provider
spec_doc: null
test_file: tests/stage1/test_ai_provider_migrations.py
functions:
  - name: define_ai_provider_tables
    line: 64
    purpose: "Declare SQLAlchemy Table objects for user_secret_keys and user_ai_providers"
  - name: bootstrap_user_secret_key
    line: 310
    purpose: "Create one wrapped DEK for a user; idempotent via ON CONFLICT DO NOTHING"
  - name: backfill_existing_user_secret_keys
    line: 345
    purpose: "Backfill missing user DEKs across all existing users"
  - name: backfill_site_owners
    line: 382
    purpose: "Assign null site owners to the lowest-id active admin"
  - name: migrate_legacy_ai_token
    line: 603
    purpose: "One-shot migration of a legacy PBKDF2 token into the vault-encrypted provider table"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol

import sqlalchemy
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

from .auth import verify_password
# NOTE: decrypt_token / get_token_last4 / mask_token were removed from crypto.py
# in the #24 ai_tokens deprecation. The legacy migration path below (PostgresLegacyMigrationStore
# / migrate_legacy_ai_token) is dead code since routers/ai_tokens.py was deleted.


def get_token_last4(token: str) -> str | None:
    """Return last 4 characters of an API token for display."""
    return token[-4:] if token and len(token) >= 4 else None


def mask_token(token: str) -> str | None:
    """Return masked API token showing only last 4 characters."""
    if not token or len(token) < 4:
        return None
    return "*" * min(len(token) - 4, 8) + token[-4:]


def decrypt_token(encrypted_token: str, password: str, user_id: int, salt: str) -> str:
    """Legacy PBKDF2+AES-GCM token decryption — deprecated with #24 ai_tokens removal."""
    raise NotImplementedError(
        "decrypt_token was removed in #24 ai_tokens deprecation; "
        "this legacy migration path is no longer supported"
    )
from .llm.key_backends import KeyEncryptionBackend, WrappedKey
from .llm.vault import (
    CredentialEnvelope,
    UserKeyEnvelope,
    encrypt_provider_credential,
    generate_dek,
    unwrap_user_dek,
    wrap_user_dek,
)


LEGACY_MINIMAX_BASE_URL = "https://api.minimax.io/v1"
LEGACY_MINIMAX_MODEL = "MiniMax-M3"
LEGACY_SOURCE_TYPE = "legacy_ai_token"
_LEGACY_LOCK_NAMESPACE = 1_347_177_011


@dataclass(frozen=True)
class AIProviderTables:
    user_secret_keys: sqlalchemy.Table
    user_ai_providers: sqlalchemy.Table


def define_ai_provider_tables(metadata: sqlalchemy.MetaData) -> AIProviderTables:
    """Return declarations that ``backend.main`` can register on its metadata."""

    user_secret_keys = sqlalchemy.Table(
        "user_secret_keys",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column(
            "user_id",
            sqlalchemy.Integer,
            sqlalchemy.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sqlalchemy.Column("encrypted_dek", sqlalchemy.LargeBinary, nullable=False),
        sqlalchemy.Column("dek_nonce", sqlalchemy.LargeBinary, nullable=False),
        sqlalchemy.Column("algorithm", sqlalchemy.String, nullable=False),
        sqlalchemy.Column("kek_version", sqlalchemy.String, nullable=False),
        sqlalchemy.Column(
            "created_at", sqlalchemy.DateTime(timezone=True), nullable=False
        ),
        sqlalchemy.Column(
            "updated_at", sqlalchemy.DateTime(timezone=True), nullable=False
        ),
        sqlalchemy.CheckConstraint(
            "octet_length(dek_nonce) = 12", name="ck_user_secret_keys_nonce"
        ),
    )

    user_ai_providers = sqlalchemy.Table(
        "user_ai_providers",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column(
            "user_id",
            sqlalchemy.Integer,
            sqlalchemy.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sqlalchemy.Column("label", sqlalchemy.String, nullable=False),
        sqlalchemy.Column("protocol", sqlalchemy.String, nullable=False),
        sqlalchemy.Column("base_url", sqlalchemy.Text, nullable=False),
        sqlalchemy.Column("model", sqlalchemy.String, nullable=False),
        sqlalchemy.Column("temperature", sqlalchemy.Float, nullable=True),
        sqlalchemy.Column("max_tokens", sqlalchemy.Integer, nullable=False),
        sqlalchemy.Column(
            "thinking", sqlalchemy.Boolean, nullable=False, server_default="false"
        ),
        sqlalchemy.Column(
            "effort", sqlalchemy.String, nullable=False, server_default="low"
        ),
        sqlalchemy.Column("encrypted_api_key", sqlalchemy.LargeBinary, nullable=False),
        sqlalchemy.Column("credential_nonce", sqlalchemy.LargeBinary, nullable=False),
        sqlalchemy.Column(
            "credential_version",
            sqlalchemy.Integer,
            nullable=False,
            server_default="1",
        ),
        sqlalchemy.Column("api_key_last4", sqlalchemy.String, nullable=True),
        sqlalchemy.Column("api_key_mask", sqlalchemy.String, nullable=True),
        sqlalchemy.Column(
            "priority", sqlalchemy.Integer, nullable=False, server_default="0"
        ),
        sqlalchemy.Column(
            "enabled", sqlalchemy.Boolean, nullable=False, server_default="true"
        ),
        sqlalchemy.Column(
            "health_status",
            sqlalchemy.String,
            nullable=False,
            server_default="unknown",
        ),
        sqlalchemy.Column(
            "last_tested_at", sqlalchemy.DateTime(timezone=True), nullable=True
        ),
        sqlalchemy.Column(
            "last_success_at", sqlalchemy.DateTime(timezone=True), nullable=True
        ),
        sqlalchemy.Column(
            "last_failure_at", sqlalchemy.DateTime(timezone=True), nullable=True
        ),
        sqlalchemy.Column("last_failure_code", sqlalchemy.String, nullable=True),
        sqlalchemy.Column("source_type", sqlalchemy.String, nullable=True),
        sqlalchemy.Column("source_id", sqlalchemy.Integer, nullable=True),
        sqlalchemy.Column(
            "revision", sqlalchemy.Integer, nullable=False, server_default="1"
        ),
        sqlalchemy.Column(
            "created_at", sqlalchemy.DateTime(timezone=True), nullable=False
        ),
        sqlalchemy.Column(
            "updated_at", sqlalchemy.DateTime(timezone=True), nullable=False
        ),
        sqlalchemy.UniqueConstraint(
            "user_id", "label", name="uq_user_ai_providers_user_label"
        ),
        sqlalchemy.CheckConstraint(
            "protocol IN ('openai', 'anthropic', 'gemini')",
            name="ck_user_ai_providers_protocol",
        ),
        sqlalchemy.CheckConstraint(
            "temperature IS NULL OR (temperature >= 0 AND temperature <= 2)",
            name="ck_user_ai_providers_temperature",
        ),
        sqlalchemy.CheckConstraint(
            "max_tokens > 0 AND max_tokens <= 1000000",
            name="ck_user_ai_providers_max_tokens",
        ),
        sqlalchemy.CheckConstraint(
            "effort IN ('low', 'medium', 'high')",
            name="ck_user_ai_providers_effort",
        ),
        sqlalchemy.CheckConstraint(
            "priority >= 0", name="ck_user_ai_providers_priority"
        ),
        sqlalchemy.CheckConstraint(
            "revision >= 1", name="ck_user_ai_providers_revision"
        ),
        sqlalchemy.CheckConstraint(
            "(source_type IS NULL AND source_id IS NULL) OR "
            "(source_type IS NOT NULL AND source_id IS NOT NULL)",
            name="ck_user_ai_providers_source_pair",
        ),
        sqlalchemy.CheckConstraint(
            "octet_length(credential_nonce) = 12",
            name="ck_user_ai_providers_nonce",
        ),
    )
    sqlalchemy.Index(
        "idx_user_ai_providers_user_priority",
        user_ai_providers.c.user_id,
        user_ai_providers.c.priority,
        user_ai_providers.c.id,
    )
    sqlalchemy.Index(
        "uq_user_ai_providers_legacy_source",
        user_ai_providers.c.user_id,
        user_ai_providers.c.source_type,
        user_ai_providers.c.source_id,
        unique=True,
        postgresql_where=sqlalchemy.and_(
            user_ai_providers.c.source_type.is_not(None),
            user_ai_providers.c.source_id.is_not(None),
        ),
    )
    return AIProviderTables(user_secret_keys, user_ai_providers)


SCHEMA_EXPANSION_STATEMENTS = (
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
)


OWNER_RELEASE_B_CONTRACT_STATEMENTS = (
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'fk_sites_owner_user_id'
        ) THEN
            ALTER TABLE sites
            ADD CONSTRAINT fk_sites_owner_user_id
            FOREIGN KEY (owner_user_id)
            REFERENCES users(id)
            ON DELETE RESTRICT
            NOT VALID;
        END IF;
    END
    $$
    """,
    "ALTER TABLE sites VALIDATE CONSTRAINT fk_sites_owner_user_id",
    "ALTER TABLE sites ALTER COLUMN owner_user_id SET NOT NULL",
)


async def bootstrap_user_secret_key(
    db,
    user_secret_keys: sqlalchemy.Table,
    backend: KeyEncryptionBackend,
    *,
    user_id: int,
    now: datetime | None = None,
) -> bool:
    """Create one wrapped DEK; return False when another writer already did."""

    timestamp = now or datetime.now(timezone.utc)
    envelope = await wrap_user_dek(
        backend, user_id=user_id, dek=generate_dek()
    )
    wrapped = envelope.wrapped_key
    statement = (
        postgresql_insert(user_secret_keys)
        .values(
            user_id=user_id,
            encrypted_dek=wrapped.ciphertext,
            dek_nonce=wrapped.nonce,
            algorithm=wrapped.algorithm,
            kek_version=wrapped.kek_version,
            created_at=timestamp,
            updated_at=timestamp,
        )
        .on_conflict_do_nothing(index_elements=["user_id"])
        .returning(user_secret_keys.c.user_id)
    )
    result = await db.execute(statement)
    row = result.mappings().first()
    await db.commit()
    return row is not None


async def backfill_existing_user_secret_keys(
    db,
    users: sqlalchemy.Table,
    user_secret_keys: sqlalchemy.Table,
    backend: KeyEncryptionBackend,
) -> dict[str, int]:
    """Backfill missing user DEKs. The unique user_id key makes retries safe."""

    rows = (await db.execute(
        sqlalchemy.select(users.c.id)
        .outerjoin(
            user_secret_keys, user_secret_keys.c.user_id == users.c.id
        )
        .where(user_secret_keys.c.user_id.is_(None))
        .order_by(users.c.id.asc())
    )).mappings().all()
    created = 0
    for row in rows:
        if await bootstrap_user_secret_key(
            db, user_secret_keys, backend, user_id=row["id"]
        ):
            created += 1
    return {"scanned": len(rows), "created": created}


class OwnerBackfillStatus(StrEnum):
    COMPLETE = "complete"
    NO_ACTIVE_ADMIN = "no_active_admin"


@dataclass(frozen=True)
class OwnerBackfillResult:
    status: OwnerBackfillStatus
    owner_user_id: int | None
    updated_count: int


async def backfill_site_owners(db) -> OwnerBackfillResult:
    """Assign null owners to the lowest-id active admin."""

    null_count = (await db.execute(
        sqlalchemy.text(
            "SELECT COUNT(*) FROM sites WHERE owner_user_id IS NULL"
        )
    )).scalar()
    if not null_count:
        return OwnerBackfillResult(OwnerBackfillStatus.COMPLETE, None, 0)

    owner_user_id = (await db.execute(
        sqlalchemy.text(
            """
            SELECT MIN(u.id)
            FROM users u
            JOIN user_roles ur ON ur.user_id = u.id
            JOIN roles r ON r.id = ur.role_id
            WHERE u.status = 'active' AND r.name = 'admin'
            """
        )
    )).scalar()
    if owner_user_id is None:
        return OwnerBackfillResult(
            OwnerBackfillStatus.NO_ACTIVE_ADMIN, None, 0
        )

    await db.execute(
        sqlalchemy.text(
            """
            UPDATE sites
            SET owner_user_id = :owner_user_id
            WHERE owner_user_id IS NULL
            """
        ),
        {"owner_user_id": owner_user_id},
    )
    await db.commit()
    return OwnerBackfillResult(
        OwnerBackfillStatus.COMPLETE, owner_user_id, int(null_count)
    )


class OwnerContractPreconditionError(RuntimeError):
    """Release B cannot run while ownership data is incomplete."""


async def validate_owner_release_b_preconditions(db) -> None:
    null_count = (await db.execute(
        sqlalchemy.text(
            "SELECT COUNT(*) FROM sites WHERE owner_user_id IS NULL"
        )
    )).scalar()
    orphan_count = (await db.execute(
        sqlalchemy.text(
            """
            SELECT COUNT(*)
            FROM sites s
            LEFT JOIN users u ON u.id = s.owner_user_id
            WHERE s.owner_user_id IS NOT NULL AND u.id IS NULL
            """
        )
    )).scalar()
    if null_count or orphan_count:
        raise OwnerContractPreconditionError(
            "site ownership backfill or referential repair is incomplete"
        )


class LegacyMigrationStatus(StrEnum):
    MIGRATED = "migrated"
    ALREADY_MIGRATED = "already_migrated"
    NEEDS_REENTRY = "needs_reentry"


@dataclass(frozen=True)
class LegacyMigrationResult:
    token_id: int
    status: LegacyMigrationStatus
    provider_id: int | None = None


class LegacyMigrationError(RuntimeError):
    """Sanitized legacy migration failure."""


class LegacyMigrationAuthenticationError(LegacyMigrationError):
    """Current password cannot authenticate/decrypt the legacy credential."""


class LegacyMigrationNotFoundError(LegacyMigrationError):
    """Legacy row does not exist or belongs to another user."""


class LegacyMigrationStore(Protocol):
    def transaction(self): ...

    async def acquire_lock(self, token_id: int) -> None: ...

    async def get_legacy_for_update(
        self, token_id: int, user_id: int
    ): ...

    async def find_provider_by_source(
        self, user_id: int, source_id: int
    ): ...

    async def mark_legacy_migrated(
        self, token_id: int, migrated_at: datetime
    ) -> None: ...

    async def get_password_hash(self, user_id: int) -> str | None: ...

    async def get_user_key_for_update(self, user_id: int): ...

    async def allocate_provider_id(self) -> int: ...

    async def next_priority(self, user_id: int) -> int: ...

    async def insert_provider(self, values: dict) -> None: ...


class PostgresLegacyMigrationStore:
    """PostgreSQL implementation with transaction-scoped and row locks."""

    def __init__(
        self,
        db,
        *,
        users: sqlalchemy.Table,
        user_secret_keys: sqlalchemy.Table,
        user_ai_tokens: sqlalchemy.Table,
        user_ai_providers: sqlalchemy.Table,
    ) -> None:
        self.db = db
        self.users = users
        self.user_secret_keys = user_secret_keys
        self.user_ai_tokens = user_ai_tokens
        self.user_ai_providers = user_ai_providers

    def transaction(self):
        return self.db.begin()

    async def acquire_lock(self, token_id: int) -> None:
        await self.db.execute(
            sqlalchemy.text(
                "SELECT pg_advisory_xact_lock(:namespace, :token_id)"
            ),
            {"namespace": _LEGACY_LOCK_NAMESPACE, "token_id": token_id},
        )

    async def get_legacy_for_update(self, token_id: int, user_id: int):
        return (await self.db.execute(
            sqlalchemy.select(self.user_ai_tokens)
            .where(
                (self.user_ai_tokens.c.id == token_id)
                & (self.user_ai_tokens.c.user_id == user_id)
            )
            .with_for_update()
        )).mappings().first()

    async def find_provider_by_source(self, user_id: int, source_id: int):
        return (await self.db.execute(
            sqlalchemy.select(self.user_ai_providers.c.id).where(
                (self.user_ai_providers.c.user_id == user_id)
                & (
                    self.user_ai_providers.c.source_type
                    == LEGACY_SOURCE_TYPE
                )
                & (self.user_ai_providers.c.source_id == source_id)
            )
        )).mappings().first()

    async def mark_legacy_migrated(
        self, token_id: int, migrated_at: datetime
    ) -> None:
        await self.db.execute(
            self.user_ai_tokens.update()
            .where(self.user_ai_tokens.c.id == token_id)
            .values(migrated_at=migrated_at)
        )

    async def get_password_hash(self, user_id: int) -> str | None:
        return (await self.db.execute(
            sqlalchemy.select(self.users.c.password_hash).where(
                self.users.c.id == user_id
            )
        )).scalar()

    async def get_user_key_for_update(self, user_id: int):
        return (await self.db.execute(
            sqlalchemy.select(self.user_secret_keys)
            .where(self.user_secret_keys.c.user_id == user_id)
            .with_for_update()
        )).mappings().first()

    async def allocate_provider_id(self) -> int:
        sequence = sqlalchemy.Sequence("user_ai_providers_id_seq")
        return int(
            (await self.db.execute(sqlalchemy.select(sequence.next_value()))).scalar()
        )

    async def next_priority(self, user_id: int) -> int:
        return int(
            (await self.db.execute(
                sqlalchemy.select(
                    sqlalchemy.func.coalesce(
                        sqlalchemy.func.max(
                            self.user_ai_providers.c.priority
                        ),
                        -1,
                    )
                    + 1
                ).where(self.user_ai_providers.c.user_id == user_id)
            )).scalar()
        )

    async def insert_provider(self, values: dict) -> None:
        await self.db.execute(self.user_ai_providers.insert().values(**values))


async def migrate_legacy_ai_token(
    store: LegacyMigrationStore,
    backend: KeyEncryptionBackend,
    *,
    user_id: int,
    token_id: int,
    current_password: str,
    now: datetime | None = None,
) -> LegacyMigrationResult:
    """Migrate one legacy token without making any provider HTTP request."""

    timestamp = now or datetime.now(timezone.utc)
    async with store.transaction():
        await store.acquire_lock(token_id)
        legacy = await store.get_legacy_for_update(token_id, user_id)
        if legacy is None:
            raise LegacyMigrationNotFoundError("legacy token not found")

        existing = await store.find_provider_by_source(user_id, token_id)
        if existing is not None:
            if legacy["migrated_at"] is None:
                await store.mark_legacy_migrated(token_id, timestamp)
            return LegacyMigrationResult(
                token_id,
                LegacyMigrationStatus.ALREADY_MIGRATED,
                int(existing["id"]),
            )
        if legacy["migrated_at"] is not None:
            raise LegacyMigrationError(
                "legacy migration marker has no provider source mapping"
            )
        if legacy["needs_reentry"]:
            return LegacyMigrationResult(
                token_id, LegacyMigrationStatus.NEEDS_REENTRY
            )

        password_hash = await store.get_password_hash(user_id)
        if not password_hash or not verify_password(
            current_password, password_hash
        ):
            raise LegacyMigrationAuthenticationError("invalid current password")
        try:
            plaintext_api_key = decrypt_token(
                legacy["encrypted_token"],
                current_password,
                user_id,
                legacy["token_salt"],
            )
        except ValueError:
            raise LegacyMigrationAuthenticationError(
                "legacy credential decryption failed"
            ) from None

        key_row = await store.get_user_key_for_update(user_id)
        if key_row is None:
            raise LegacyMigrationError("user secret key is not initialized")
        user_key = UserKeyEnvelope(
            user_id=user_id,
            wrapped_key=WrappedKey(
                ciphertext=key_row["encrypted_dek"],
                nonce=key_row["dek_nonce"],
                algorithm=key_row["algorithm"],
                kek_version=key_row["kek_version"],
            ),
        )
        dek = await unwrap_user_dek(backend, user_key)
        provider_id = await store.allocate_provider_id()
        priority = await store.next_priority(user_id)
        credential = encrypt_provider_credential(
            plaintext_api_key,
            dek=dek,
            user_id=user_id,
            provider_id=provider_id,
            protocol="openai",
            base_url=LEGACY_MINIMAX_BASE_URL,
        )
        await store.insert_provider(
            _legacy_provider_values(
                legacy=legacy,
                user_id=user_id,
                provider_id=provider_id,
                priority=priority,
                credential=credential,
                plaintext_api_key=plaintext_api_key,
                timestamp=timestamp,
            )
        )
        await store.mark_legacy_migrated(token_id, timestamp)
        return LegacyMigrationResult(
            token_id, LegacyMigrationStatus.MIGRATED, provider_id
        )


def _legacy_provider_values(
    *,
    legacy,
    user_id: int,
    provider_id: int,
    priority: int,
    credential: CredentialEnvelope,
    plaintext_api_key: str,
    timestamp: datetime,
) -> dict:
    return {
        "id": provider_id,
        "user_id": user_id,
        "label": legacy["label"],
        "protocol": "openai",
        "base_url": LEGACY_MINIMAX_BASE_URL,
        "model": LEGACY_MINIMAX_MODEL,
        "temperature": None,
        "max_tokens": 4096,
        "thinking": False,
        "effort": "low",
        "encrypted_api_key": credential.ciphertext,
        "credential_nonce": credential.nonce,
        "credential_version": credential.credential_version,
        "api_key_last4": get_token_last4(plaintext_api_key),
        "api_key_mask": mask_token(plaintext_api_key),
        "priority": priority,
        "enabled": True,
        "health_status": "unknown",
        "last_tested_at": None,
        "last_success_at": None,
        "last_failure_at": None,
        "last_failure_code": None,
        "source_type": LEGACY_SOURCE_TYPE,
        "source_id": legacy["id"],
        "revision": 1,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
