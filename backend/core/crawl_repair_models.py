"""Schema declarations, migration helpers, and Pydantic models for crawl auto-repair.

This module intentionally does not import from or modify backend/main.py.
The application entrypoint (A0) owns wiring these declarations into startup.

Pattern: mirrors core/ai_provider_migrations.py — define tables separately,
provide idempotent DDL expansion statements, and expose backfill helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

import sqlalchemy
from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# Literal enums (shared with repository + service layers)
# ---------------------------------------------------------------------------

RepairKind = Literal["list", "content"]

# repair_status values for site_crawl_repair_states
RepairStatus = Literal[
    "healthy",
    "collecting_failures",
    "repairing",
    "repair_failed_budget_remaining",
    "paused_until_next_week",
]

# status values for crawl_repair_attempts
AttemptStatus = Literal[
    "reserved",
    "provider_failed",
    "no_provider_available",
    "candidate_schema_invalid",
    "candidate_validation_failed",
    "stale_rule_revision",
    "applied",
    "aborted_internal_error",
]

_TERMINAL_ATTEMPT_STATUSES: frozenset[str] = frozenset({
    "provider_failed",
    "no_provider_available",
    "candidate_schema_invalid",
    "candidate_validation_failed",
    "stale_rule_revision",
    "applied",
    "aborted_internal_error",
})


# ---------------------------------------------------------------------------
# SQLAlchemy table declarations
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CrawlRepairTables:
    site_crawl_repair_states: sqlalchemy.Table
    crawl_repair_attempts: sqlalchemy.Table


def define_crawl_repair_tables(metadata: sqlalchemy.MetaData) -> CrawlRepairTables:
    """Define and return crawl-repair table declarations bound to *metadata*.

    The caller (typically core/db.py or main.py, owned by A0) must include
    the returned tables so that SQLAlchemy metadata.create_all() picks them up.

    Tables reference existing FK targets (sites, crawl_attempts, users) by name;
    those tables must be declared on the same metadata object before this call.
    """

    site_crawl_repair_states = sqlalchemy.Table(
        "site_crawl_repair_states",
        metadata,
        # Primary key
        sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
        # Identity
        sqlalchemy.Column(
            "site_id",
            sqlalchemy.Integer,
            sqlalchemy.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sqlalchemy.Column(
            "repair_kind",
            sqlalchemy.String,
            nullable=False,
        ),
        # Failure tracking
        sqlalchemy.Column(
            "consecutive_failure_count",
            sqlalchemy.Integer,
            nullable=False,
            server_default="0",
        ),
        # Weekly budget
        sqlalchemy.Column(
            "week_start_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=False,
        ),
        sqlalchemy.Column(
            "weekly_attempt_count",
            sqlalchemy.SmallInteger,
            nullable=False,
            server_default="0",
        ),
        # Pause / block fields
        sqlalchemy.Column(
            "blocked_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=True,
        ),
        sqlalchemy.Column(
            "blocked_until",
            sqlalchemy.DateTime(timezone=True),
            nullable=True,
        ),
        # Outcome audit
        sqlalchemy.Column("last_outcome", sqlalchemy.String, nullable=True),
        sqlalchemy.Column("last_failure_reason", sqlalchemy.String, nullable=True),
        sqlalchemy.Column(
            "last_failure_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=True,
        ),
        sqlalchemy.Column(
            "last_success_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=True,
        ),
        sqlalchemy.Column(
            "last_repair_attempt_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=True,
        ),
        sqlalchemy.Column(
            "last_repair_success_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=True,
        ),
        # State machine status
        sqlalchemy.Column(
            "repair_status",
            sqlalchemy.String,
            nullable=False,
            server_default="healthy",
        ),
        # Optimistic locking revision
        sqlalchemy.Column(
            "revision",
            sqlalchemy.Integer,
            nullable=False,
            server_default="1",
        ),
        # Timestamps
        sqlalchemy.Column(
            "created_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=False,
        ),
        sqlalchemy.Column(
            "updated_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=False,
        ),
        # Constraints
        sqlalchemy.UniqueConstraint(
            "site_id", "repair_kind",
            name="uq_site_crawl_repair_states_site_kind",
        ),
        sqlalchemy.CheckConstraint(
            "repair_kind IN ('list', 'content')",
            name="ck_site_crawl_repair_states_repair_kind",
        ),
        sqlalchemy.CheckConstraint(
            "consecutive_failure_count >= 0",
            name="ck_site_crawl_repair_states_consecutive_failure_count",
        ),
        sqlalchemy.CheckConstraint(
            "weekly_attempt_count >= 0 AND weekly_attempt_count <= 5",
            name="ck_site_crawl_repair_states_weekly_attempt_count",
        ),
        sqlalchemy.CheckConstraint(
            "repair_status IN ("
            "'healthy', 'collecting_failures', 'repairing', "
            "'repair_failed_budget_remaining', 'paused_until_next_week')",
            name="ck_site_crawl_repair_states_repair_status",
        ),
        sqlalchemy.CheckConstraint(
            "revision >= 1",
            name="ck_site_crawl_repair_states_revision",
        ),
    )
    sqlalchemy.Index(
        "idx_site_crawl_repair_states_site_id",
        site_crawl_repair_states.c.site_id,
    )
    sqlalchemy.Index(
        "idx_site_crawl_repair_states_blocked_until",
        site_crawl_repair_states.c.blocked_until,
        postgresql_where=site_crawl_repair_states.c.blocked_until.is_not(None),
    )

    crawl_repair_attempts = sqlalchemy.Table(
        "crawl_repair_attempts",
        metadata,
        # Primary key
        sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
        # Identity
        sqlalchemy.Column(
            "site_id",
            sqlalchemy.Integer,
            sqlalchemy.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sqlalchemy.Column(
            "crawl_attempt_id",
            sqlalchemy.BigInteger,
            sqlalchemy.ForeignKey("crawl_attempts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sqlalchemy.Column(
            "repair_kind",
            sqlalchemy.String,
            nullable=False,
        ),
        # Weekly budget tracking
        sqlalchemy.Column(
            "week_start_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=False,
        ),
        sqlalchemy.Column(
            "weekly_sequence",
            sqlalchemy.SmallInteger,
            nullable=False,
        ),
        # Trigger context
        sqlalchemy.Column(
            "trigger_failure_count",
            sqlalchemy.Integer,
            nullable=False,
        ),
        # Status
        sqlalchemy.Column(
            "status",
            sqlalchemy.String,
            nullable=False,
        ),
        # Owner / provider context (no credential stored here)
        sqlalchemy.Column(
            "owner_user_id",
            sqlalchemy.Integer,
            sqlalchemy.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Rule revision tracking
        sqlalchemy.Column(
            "base_rule_revision",
            sqlalchemy.Integer,
            nullable=False,
        ),
        sqlalchemy.Column(
            "candidate_rule_revision",
            sqlalchemy.Integer,
            nullable=True,
        ),
        # Provider traceability (sanitized — no raw API key, prompt, or response)
        sqlalchemy.Column("provider_trace_id", sqlalchemy.String, nullable=True),
        # Sample tracking
        sqlalchemy.Column("sample_url", sqlalchemy.String, nullable=True),
        sqlalchemy.Column(
            "sample_count",
            sqlalchemy.SmallInteger,
            nullable=False,
            server_default="0",
        ),
        sqlalchemy.Column(
            "validation_success_count",
            sqlalchemy.SmallInteger,
            nullable=False,
            server_default="0",
        ),
        sqlalchemy.Column(
            "validation_failure_code",
            sqlalchemy.String,
            nullable=True,
        ),
        # Timestamps
        sqlalchemy.Column(
            "started_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=False,
        ),
        sqlalchemy.Column(
            "finished_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=True,
        ),
        # Constraints
        sqlalchemy.UniqueConstraint(
            "site_id", "repair_kind", "week_start_at", "weekly_sequence",
            name="uq_crawl_repair_attempts_site_kind_week_seq",
        ),
        sqlalchemy.CheckConstraint(
            "repair_kind IN ('list', 'content')",
            name="ck_crawl_repair_attempts_repair_kind",
        ),
        sqlalchemy.CheckConstraint(
            "weekly_sequence >= 1",
            name="ck_crawl_repair_attempts_weekly_sequence",
        ),
        sqlalchemy.CheckConstraint(
            "trigger_failure_count >= 1",
            name="ck_crawl_repair_attempts_trigger_failure_count",
        ),
        sqlalchemy.CheckConstraint(
            "status IN ("
            "'reserved', 'provider_failed', 'no_provider_available', "
            "'candidate_schema_invalid', 'candidate_validation_failed', "
            "'stale_rule_revision', 'applied', 'aborted_internal_error')",
            name="ck_crawl_repair_attempts_status",
        ),
        sqlalchemy.CheckConstraint(
            "sample_count >= 0",
            name="ck_crawl_repair_attempts_sample_count",
        ),
        sqlalchemy.CheckConstraint(
            "validation_success_count >= 0",
            name="ck_crawl_repair_attempts_validation_success_count",
        ),
        sqlalchemy.CheckConstraint(
            "base_rule_revision >= 1",
            name="ck_crawl_repair_attempts_base_rule_revision",
        ),
        sqlalchemy.CheckConstraint(
            "candidate_rule_revision IS NULL OR candidate_rule_revision >= 1",
            name="ck_crawl_repair_attempts_candidate_rule_revision",
        ),
    )
    sqlalchemy.Index(
        "idx_crawl_repair_attempts_site_kind",
        crawl_repair_attempts.c.site_id,
        crawl_repair_attempts.c.repair_kind,
    )
    sqlalchemy.Index(
        "idx_crawl_repair_attempts_site_kind_week",
        crawl_repair_attempts.c.site_id,
        crawl_repair_attempts.c.repair_kind,
        crawl_repair_attempts.c.week_start_at,
    )
    sqlalchemy.Index(
        "idx_crawl_repair_attempts_status",
        crawl_repair_attempts.c.status,
    )

    return CrawlRepairTables(
        site_crawl_repair_states=site_crawl_repair_states,
        crawl_repair_attempts=crawl_repair_attempts,
    )


# ---------------------------------------------------------------------------
# Idempotent DDL expansion statements (Release A — expand)
# Used by A0 in startup migration, mirroring SCHEMA_EXPANSION_STATEMENTS pattern.
# ---------------------------------------------------------------------------

CRAWL_REPAIR_EXPANSION_STATEMENTS: tuple[str, ...] = (
    # --- New tables ---
    """
    CREATE TABLE IF NOT EXISTS site_crawl_repair_states (
        id BIGSERIAL PRIMARY KEY,
        site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
        repair_kind VARCHAR NOT NULL CHECK (repair_kind IN ('list', 'content')),
        consecutive_failure_count INTEGER NOT NULL DEFAULT 0
            CHECK (consecutive_failure_count >= 0),
        week_start_at TIMESTAMPTZ NOT NULL,
        weekly_attempt_count SMALLINT NOT NULL DEFAULT 0
            CHECK (weekly_attempt_count >= 0 AND weekly_attempt_count <= 5),
        blocked_at TIMESTAMPTZ,
        blocked_until TIMESTAMPTZ,
        last_outcome VARCHAR,
        last_failure_reason VARCHAR,
        last_failure_at TIMESTAMPTZ,
        last_success_at TIMESTAMPTZ,
        last_repair_attempt_at TIMESTAMPTZ,
        last_repair_success_at TIMESTAMPTZ,
        repair_status VARCHAR NOT NULL DEFAULT 'healthy'
            CHECK (repair_status IN (
                'healthy', 'collecting_failures', 'repairing',
                'repair_failed_budget_remaining', 'paused_until_next_week'
            )),
        revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        CONSTRAINT uq_site_crawl_repair_states_site_kind UNIQUE (site_id, repair_kind)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_site_crawl_repair_states_site_id
        ON site_crawl_repair_states(site_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_site_crawl_repair_states_blocked_until
        ON site_crawl_repair_states(blocked_until)
        WHERE blocked_until IS NOT NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS crawl_repair_attempts (
        id BIGSERIAL PRIMARY KEY,
        site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
        crawl_attempt_id BIGINT REFERENCES crawl_attempts(id) ON DELETE SET NULL,
        repair_kind VARCHAR NOT NULL CHECK (repair_kind IN ('list', 'content')),
        week_start_at TIMESTAMPTZ NOT NULL,
        weekly_sequence SMALLINT NOT NULL CHECK (weekly_sequence >= 1),
        trigger_failure_count INTEGER NOT NULL CHECK (trigger_failure_count >= 1),
        status VARCHAR NOT NULL CHECK (status IN (
            'reserved', 'provider_failed', 'no_provider_available',
            'candidate_schema_invalid', 'candidate_validation_failed',
            'stale_rule_revision', 'applied', 'aborted_internal_error'
        )),
        owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        base_rule_revision INTEGER NOT NULL CHECK (base_rule_revision >= 1),
        candidate_rule_revision INTEGER CHECK (candidate_rule_revision IS NULL OR candidate_rule_revision >= 1),
        provider_trace_id VARCHAR,
        sample_url VARCHAR,
        sample_count SMALLINT NOT NULL DEFAULT 0 CHECK (sample_count >= 0),
        validation_success_count SMALLINT NOT NULL DEFAULT 0
            CHECK (validation_success_count >= 0),
        validation_failure_code VARCHAR,
        started_at TIMESTAMPTZ NOT NULL,
        finished_at TIMESTAMPTZ,
        CONSTRAINT uq_crawl_repair_attempts_site_kind_week_seq
            UNIQUE (site_id, repair_kind, week_start_at, weekly_sequence)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_crawl_repair_attempts_site_kind
        ON crawl_repair_attempts(site_id, repair_kind)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_crawl_repair_attempts_site_kind_week
        ON crawl_repair_attempts(site_id, repair_kind, week_start_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_crawl_repair_attempts_status
        ON crawl_repair_attempts(status)
    """,
    # --- sites table additions ---
    "ALTER TABLE sites ADD COLUMN IF NOT EXISTS auto_repair_enabled BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE sites ADD COLUMN IF NOT EXISTS auto_repair_weekly_limit SMALLINT NOT NULL DEFAULT 3",
    "ALTER TABLE sites ADD COLUMN IF NOT EXISTS list_rules_revision INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE sites ADD COLUMN IF NOT EXISTS content_rules_revision INTEGER NOT NULL DEFAULT 1",
    # --- crawl_attempts table additions ---
    "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS owner_user_id INTEGER",
    "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS routine_skip_reason VARCHAR",
    "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS list_outcome VARCHAR",
    "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS content_outcome VARCHAR",
    "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS list_structural_failure BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS content_structural_failure BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS content_parse_eligible INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS content_parse_succeeded INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS content_parse_structural_failed INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS auto_repair_kind VARCHAR",
    "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS auto_repair_attempt_id BIGINT",
)

# Constraint DDL for sites additions — applied separately (NOT idempotent in all PG versions
# without PL/pgSQL DO block; A0 wraps in try/except same as SCHEMA_EXPANSION_STATEMENTS).
CRAWL_REPAIR_SITE_CONSTRAINTS: tuple[str, ...] = (
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_sites_auto_repair_weekly_limit'
        ) THEN
            ALTER TABLE sites ADD CONSTRAINT ck_sites_auto_repair_weekly_limit
                CHECK (auto_repair_weekly_limit BETWEEN 1 AND 5);
        END IF;
    END
    $$
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_sites_list_rules_revision'
        ) THEN
            ALTER TABLE sites ADD CONSTRAINT ck_sites_list_rules_revision
                CHECK (list_rules_revision >= 1);
        END IF;
    END
    $$
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_sites_content_rules_revision'
        ) THEN
            ALTER TABLE sites ADD CONSTRAINT ck_sites_content_rules_revision
                CHECK (content_rules_revision >= 1);
        END IF;
    END
    $$
    """,
)


# ---------------------------------------------------------------------------
# Sync migration function — wired by A0 into startup (like _run_schema_migration)
# ---------------------------------------------------------------------------

def migrate_crawl_repair_tables(conn) -> None:
    """Idempotent DDL for crawl auto-repair schema.

    Accepts a synchronous SQLAlchemy connection (same as _run_schema_migration).
    Safe to run on both fresh DBs and existing ones.
    A0 must call this from the lifespan handler after other migrations.
    """
    from sqlalchemy import text as sa_text

    for stmt in CRAWL_REPAIR_EXPANSION_STATEMENTS:
        try:
            conn.execute(sa_text(stmt))
        except Exception as exc:
            # Log but do not abort — mirrors existing migration pattern.
            # Caller (A0) logs with log_with_time.
            _migration_warn(f"crawl_repair expansion note: {exc}")

    for stmt in CRAWL_REPAIR_SITE_CONSTRAINTS:
        try:
            conn.execute(sa_text(stmt))
        except Exception as exc:
            _migration_warn(f"crawl_repair constraint note: {exc}")

    conn.commit()


def _migration_warn(msg: str) -> None:
    """Minimal fallback logger for migration notes (avoids import cycle)."""
    import sys
    print(f"[Migration][crawl_repair] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Async backfill — wired by A0 in startup (like backfill_site_owners)
# ---------------------------------------------------------------------------

async def backfill_repair_states(session, *, current_week_start: datetime) -> dict:
    """Insert default list/content repair state rows for every site that lacks them.

    Uses INSERT … ON CONFLICT DO NOTHING — safe to run multiple times.

    Args:
        session: SQLAlchemy AsyncSession.
        current_week_start: timezone-aware UTC datetime representing the start
            of the current Taipei week window (computed by C1 time helper).

    Returns:
        Dict with keys 'sites_scanned', 'rows_inserted'.
    """
    from sqlalchemy import text as sa_text

    # Fetch all site IDs
    result = await session.execute(sa_text("SELECT id FROM sites ORDER BY id"))
    site_ids = [row[0] for row in result]

    inserted = 0
    now = datetime.now(timezone.utc)

    for site_id in site_ids:
        for repair_kind in ("list", "content"):
            try:
                r = await session.execute(
                    sa_text(
                        """
                        INSERT INTO site_crawl_repair_states
                            (site_id, repair_kind, consecutive_failure_count,
                             week_start_at, weekly_attempt_count,
                             repair_status, revision, created_at, updated_at)
                        VALUES
                            (:site_id, :repair_kind, 0,
                             :week_start_at, 0,
                             'healthy', 1, :now, :now)
                        ON CONFLICT (site_id, repair_kind) DO NOTHING
                        """
                    ),
                    {
                        "site_id": site_id,
                        "repair_kind": repair_kind,
                        "week_start_at": current_week_start,
                        "now": now,
                    },
                )
                inserted += r.rowcount
            except Exception as exc:
                _migration_warn(
                    f"backfill_repair_states site_id={site_id} "
                    f"repair_kind={repair_kind}: {exc}"
                )

    await session.commit()
    return {"sites_scanned": len(site_ids), "rows_inserted": inserted}


# ---------------------------------------------------------------------------
# Pydantic API schemas
# ---------------------------------------------------------------------------

class RepairKindStatusSchema(BaseModel):
    """Status for a single repair kind (list or content) within one weekly window."""

    consecutive_failures: int
    weekly_attempts_used: int
    weekly_attempts_limit: int
    blocked: bool
    blocked_until: Optional[datetime] = None
    repair_status: str
    last_outcome: Optional[str] = None
    last_failure_reason: Optional[str] = None
    last_failure_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_repair_attempt_at: Optional[datetime] = None
    last_repair_success_at: Optional[datetime] = None


class FeedRepairStatusSchema(BaseModel):
    """Aggregated repair status for a feed (both list and content)."""

    timezone: str = "Asia/Taipei"
    week_start_at: datetime
    next_reset_at: datetime
    routine_paused: bool
    blocking_kinds: list[str]
    list: RepairKindStatusSchema
    content: RepairKindStatusSchema


class SiteAutoRepairConfigSchema(BaseModel):
    """Auto-repair configuration settable per site."""

    auto_repair_enabled: bool = True
    auto_repair_weekly_limit: int = 3

    @field_validator("auto_repair_weekly_limit")
    @classmethod
    def validate_weekly_limit(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("auto_repair_weekly_limit must be between 1 and 5")
        return v


class RepairAttemptSchema(BaseModel):
    """Summary of a single repair attempt (sanitized — no credential or raw HTML)."""

    id: int
    site_id: int
    crawl_attempt_id: Optional[int] = None
    repair_kind: str
    week_start_at: datetime
    weekly_sequence: int
    trigger_failure_count: int
    status: str
    base_rule_revision: int
    candidate_rule_revision: Optional[int] = None
    provider_trace_id: Optional[str] = None
    sample_url: Optional[str] = None
    sample_count: int
    validation_success_count: int
    validation_failure_code: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None


class PauseStatus(BaseModel):
    """Feed-level routine pause status returned by get_feed_pause_status."""

    routine_paused: bool
    blocking_kinds: list[str]
    blocked_until: Optional[datetime] = None
    list_blocked: bool
    content_blocked: bool
