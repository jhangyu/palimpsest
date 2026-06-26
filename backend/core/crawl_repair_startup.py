"""
---
name: crawl_repair_startup
description: "Integration packet for main.py (A0): three startup hooks to wire crawl auto-repair — register tables, run DDL migration, and backfill repair state rows"
type: core
target:
  layer: backend
  domain: crawl
spec_doc: null
test_file: tests/stage1/test_crawl_repair_startup.py
functions:
  - name: register_crawl_repair_tables
    line: 83
    purpose: "Register crawl repair table declarations onto shared SQLAlchemy metadata; call once at module import"
  - name: run_crawl_repair_migration
    line: 100
    purpose: "Run idempotent Release-A DDL migration (IF NOT EXISTS / PL/pgSQL DO blocks)"
  - name: run_crawl_repair_backfill
    line: 129
    purpose: "Backfill site_crawl_repair_states rows for all sites (ON CONFLICT DO NOTHING)"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
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
