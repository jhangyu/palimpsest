"""Crawl auto-repair integration packet for main.py (A0).

This module provides the three hooks that A0 needs to wire crawl auto-repair
into the application startup lifecycle:

    register_crawl_repair_tables(metadata)  → CrawlRepairTables
    run_crawl_repair_migration(sync_engine, log_fn)
    run_crawl_repair_backfill(session, log_fn)

Wiring example (backend/main.py):
----------------------------------------------------------------------
from core.crawl_repair_startup import (
    register_crawl_repair_tables,
    run_crawl_repair_migration,
    run_crawl_repair_backfill,
)
from core.crawl_repair_repository import RepairStateRepository

# ── Module-level initialisation (before lifespan) ──────────────────
_repair_tables = register_crawl_repair_tables(metadata)
repair_repo    = RepairStateRepository(_repair_tables)

# ── Inside lifespan (after sync_engine is created) ─────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_engine = sqlalchemy.create_engine(sync_url)

    await asyncio.to_thread(metadata.create_all, sync_engine)
    await asyncio.to_thread(_run_schema_migration, sync_engine)
    await asyncio.to_thread(run_crawl_repair_migration, sync_engine, log_with_time)

    async with async_session_factory() as session:
        result = await run_crawl_repair_backfill(session, log_with_time)
        log_with_time(f"[Startup] Crawl repair backfill: {result}")

    yield
----------------------------------------------------------------------

Export / import (pg_dump / pg_restore):
    Tables added by this module:
        site_crawl_repair_states
        crawl_repair_attempts
    Columns added to existing tables:
        sites.auto_repair_enabled
        sites.auto_repair_weekly_limit
        sites.list_rules_revision
        sites.content_rules_revision
        crawl_attempts.owner_user_id
        crawl_attempts.routine_skip_reason
        crawl_attempts.list_outcome / content_outcome
        crawl_attempts.list_structural_failure / content_structural_failure
        crawl_attempts.content_parse_eligible / succeeded / structural_failed
        crawl_attempts.auto_repair_kind / auto_repair_attempt_id

    All new columns have DEFAULT values or are nullable, so a pg_dump
    taken before this migration is fully restorable against a schema that
    includes these columns (Release A backward-compat guarantee).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

import sqlalchemy

from .crawl_repair_models import (
    CrawlRepairTables,
    define_crawl_repair_tables,
    migrate_crawl_repair_tables,
    backfill_repair_states,
)
from .time_provider import taipei_week_window

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_crawl_repair_tables(metadata: sqlalchemy.MetaData) -> CrawlRepairTables:
    """Register crawl repair table declarations onto the shared metadata.

    Call once at module import time, before the SQLAlchemy engine is created.
    Returns the CrawlRepairTables dataclass so it can be passed to
    RepairStateRepository.

    Args:
        metadata: The shared sqlalchemy.MetaData object used by the application.

    Returns:
        CrawlRepairTables with .site_crawl_repair_states and
        .crawl_repair_attempts Table objects bound to the metadata.
    """
    return define_crawl_repair_tables(metadata)


def run_crawl_repair_migration(
    sync_engine: sqlalchemy.Engine,
    log_fn: Optional[Callable[[str], None]] = None,
) -> None:
    """Run the idempotent Release-A DDL migration for crawl auto-repair tables.

    This is safe to call on every startup — all statements use IF NOT EXISTS
    or PL/pgSQL DO blocks that skip existing constraints.

    Intended to run in a thread via asyncio.to_thread() since it uses a sync
    connection (matching the pattern used for _run_schema_migration).

    Args:
        sync_engine: Synchronous SQLAlchemy engine (no +asyncpg).
        log_fn: Optional callable(message: str) for startup log output.
                Defaults to logging.getLogger(__name__).info.
    """
    _emit = log_fn or _log.info

    with sync_engine.connect() as conn:
        try:
            migrate_crawl_repair_tables(conn)
            _emit("[Migration] Crawl repair schema expansion completed.")
        except Exception as exc:
            # migrate_crawl_repair_tables commits per-statement with per-statement
            # try/except; this outer guard is a belt-and-suspenders catch-all.
            _emit(f"[Migration] Crawl repair schema expansion error: {exc}")


async def run_crawl_repair_backfill(
    session,
    log_fn: Optional[Callable[[str], None]] = None,
) -> dict:
    """Backfill site_crawl_repair_states rows for all existing sites.

    Creates two rows per site (list + content) with healthy defaults.
    Idempotent: ON CONFLICT DO NOTHING skips already-existing rows.

    Uses the C1 time provider to derive the current Taipei-week start,
    ensuring the bucket key is consistent with runtime computation.

    Args:
        session: SQLAlchemy AsyncSession.
        log_fn: Optional log callback; defaults to logging.

    Returns:
        Dict with keys 'sites_scanned' and 'rows_inserted'.
    """
    _emit = log_fn or _log.info

    now_utc = datetime.now(timezone.utc)
    week_window = taipei_week_window(now_utc)
    current_week_start = week_window.start_utc

    try:
        result = await backfill_repair_states(
            session, current_week_start=current_week_start
        )
        _emit(
            f"[Startup] Crawl repair backfill: "
            f"scanned={result['sites_scanned']} inserted={result['rows_inserted']}"
        )
        return result
    except Exception as exc:
        _emit(f"[Startup] Crawl repair backfill note: {exc}")
        return {"sites_scanned": 0, "rows_inserted": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Re-exports for A0 convenience
# ---------------------------------------------------------------------------

__all__ = [
    "register_crawl_repair_tables",
    "run_crawl_repair_migration",
    "run_crawl_repair_backfill",
    # Re-export CrawlRepairTables so A0 only needs one import line
    "CrawlRepairTables",
]
