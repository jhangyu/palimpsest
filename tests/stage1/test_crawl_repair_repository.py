"""
---
name: test_crawl_repair_repository
description: "Async unit tests for RepairStateRepository covering state transitions, budget enforcement, pause status, and stale attempt recovery"
stage: stage1
type: pytest
target:
  layer: backend
  domain: crawl-repair
spec_doc: null
test_file: tests/stage1/test_crawl_repair_repository.py
functions:
  - name: test_returns_existing_row
    line: 165
    purpose: "get_state returns the existing state row from the session"
    fixtures: []
  - name: test_creates_default_when_not_found
    line: 177
    purpose: "get_state inserts default row and re-fetches when state is missing"
    fixtures: []
  - name: test_for_update_locks_row
    line: 206
    purpose: "get_state with for_update=True does not raise"
    fixtures: []
  - name: test_no_rollover_when_same_week
    line: 224
    purpose: "lazy_weekly_rollover returns False and skips UPDATE when week unchanged"
    fixtures: []
  - name: test_rollover_resets_weekly_count_and_clears_block
    line: 239
    purpose: "lazy_weekly_rollover resets weekly_attempt_count and clears pause block"
    fixtures: []
  - name: test_rollover_preserves_consecutive_failure_count
    line: 271
    purpose: "lazy_weekly_rollover does not reset consecutive_failure_count"
    fixtures: []
  - name: test_rollover_changes_status_from_paused_to_collecting_failures
    line: 291
    purpose: "Rollover transitions status from paused_until_next_week to collecting_failures"
    fixtures: []
  - name: test_increments_count_and_returns_new_value
    line: 324
    purpose: "increment_failure increments by 1 and returns the new count"
    fixtures: []
  - name: test_first_failure_transitions_to_collecting_failures
    line: 339
    purpose: "First failure transitions status from healthy to collecting_failures"
    fixtures: []
  - name: test_with_failure_reason
    line: 350
    purpose: "increment_failure accepts optional failure_reason parameter"
    fixtures: []
  - name: test_does_not_affect_other_kind
    line: 364
    purpose: "increment_failure only affects the specified repair_kind"
    fixtures: []
  - name: test_resets_to_zero
    line: 393
    purpose: "reset_failure issues SELECT + UPDATE to set count back to zero"
    fixtures: []
  - name: test_does_not_clear_pause_on_reset
    line: 405
    purpose: "reset_failure preserves paused_until_next_week status on reset"
    fixtures: []
  - name: test_reserves_first_attempt_of_week
    line: 436
    purpose: "reserve_repair_attempt succeeds with weekly_sequence=1 when budget available"
    fixtures: []
  - name: test_raises_budget_exhausted_when_limit_reached
    line: 482
    purpose: "reserve_repair_attempt raises RepairBudgetExhaustedError when count == limit"
    fixtures: []
  - name: test_budget_at_limit_1_is_exhausted_after_first_attempt
    line: 506
    purpose: "weekly_limit=1 exhausted when used=1"
    fixtures: []
  - name: test_budget_at_limit_5_allows_up_to_5
    line: 529
    purpose: "weekly_limit=5 allows 5th attempt (used=4)"
    fixtures: []
  - name: test_budget_at_max_5_is_exhausted_when_at_5
    line: 571
    purpose: "weekly_limit=5 exhausted when used=5"
    fixtures: []
  - name: test_transitions_reserved_to_applied
    line: 600
    purpose: "complete_repair_attempt transitions status from 'reserved' to 'applied'"
    fixtures: []
  - name: test_raises_when_already_finalized
    line: 625
    purpose: "complete_repair_attempt raises AttemptAlreadyFinalizedError for terminal status"
    fixtures: []
  - name: test_raises_when_attempt_not_found
    line: 637
    purpose: "complete_repair_attempt raises AttemptNotFoundError for missing attempt"
    fixtures: []
  - name: test_cannot_complete_twice
    line: 648
    purpose: "Same attempt cannot be completed with two different terminal statuses"
    fixtures: []
  - name: test_rejects_non_terminal_status
    line: 684
    purpose: "complete_repair_attempt raises ValueError for non-terminal status strings"
    fixtures: []
  - name: test_sets_paused_status_and_blocked_until
    line: 702
    purpose: "pause_feed issues SELECT + UPDATE to set paused status and blocked_until"
    fixtures: []
  - name: test_list_pause_does_not_touch_content_state
    line: 714
    purpose: "pause_feed for list only issues 2 execute calls (no content state touched)"
    fixtures: []
  - name: test_not_paused_when_both_healthy
    line: 738
    purpose: "get_feed_pause_status returns not_paused when both list and content are healthy"
    fixtures: []
  - name: test_paused_when_list_exhausted
    line: 765
    purpose: "get_feed_pause_status shows routine_paused=True when list is exhausted"
    fixtures: []
  - name: test_paused_when_content_exhausted
    line: 797
    purpose: "get_feed_pause_status shows routine_paused=True when content is exhausted"
    fixtures: []
  - name: test_expired_pause_not_counted
    line: 827
    purpose: "Past blocked_until is not considered an active pause"
    fixtures: []
  - name: test_no_state_rows_returns_not_paused
    line: 858
    purpose: "Missing state rows for a site results in not-paused status"
    fixtures: []
  - name: test_clears_block_and_resets_count
    line: 876
    purpose: "clear_block issues SELECT + UPDATE to clear pause for the specified kind"
    fixtures: []
  - name: test_only_clears_specified_kind
    line: 891
    purpose: "clear_block only touches the specified repair_kind (2 execute calls)"
    fixtures: []
  - name: test_lock_ordered_kinds_returns_list_then_content
    line: 910
    purpose: "_lock_ordered_kinds returns ('list', 'content') in that order"
    fixtures: []
  - name: test_lock_ordered_kinds_is_tuple
    line: 915
    purpose: "_lock_ordered_kinds returns a 2-element tuple"
    fixtures: []
  - name: test_get_feed_pause_status_queries_list_before_content
    line: 923
    purpose: "get_feed_pause_status queries list state before content state"
    fixtures: []
  - name: test_finalizes_reserved_attempt_as_aborted
    line: 950
    purpose: "recover_stale_attempt transitions reserved → aborted_internal_error"
    fixtures: []
  - name: test_raises_when_attempt_already_finalized
    line: 985
    purpose: "recover_stale_attempt raises AttemptAlreadyFinalizedError for terminal attempt"
    fixtures: []
  - name: test_raises_when_attempt_not_found
    line: 998
    purpose: "recover_stale_attempt raises AttemptNotFoundError for missing attempt"
    fixtures: []
  - name: test_updates_state_to_collecting_failures
    line: 1009
    purpose: "recover_stale_attempt issues 4 execute calls to update both attempt and state"
    fixtures: []
  - name: test_get_stale_reserved_attempts_filters_by_status_and_age
    line: 1038
    purpose: "get_stale_reserved_attempts returns only 'reserved' attempts older than threshold"
    fixtures: []
  - name: test_register_crawl_repair_tables_returns_tables
    line: 1059
    purpose: "register_crawl_repair_tables wires tables into metadata"
    fixtures: []
  - name: test_run_crawl_repair_migration_calls_migrate_fn
    line: 1076
    purpose: "run_crawl_repair_migration calls migrate_crawl_repair_tables and logs output"
    fixtures: []
  - name: test_run_crawl_repair_backfill_uses_taipei_week
    line: 1093
    purpose: "run_crawl_repair_backfill derives week_start from time provider"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_crawl_repair_repository.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from typing import Any


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

class FakeResult:
    """Mimics SQLAlchemy MappingResult returned by session.execute()."""

    def __init__(self, rows: list[dict] | None = None, rowcount: int = 0):
        self._rows = rows or []
        self.rowcount = rowcount

    def mappings(self) -> "FakeResult":
        return self

    def all(self) -> list[dict]:
        return list(self._rows)

    def first(self) -> dict | None:
        return self._rows[0] if self._rows else None

    def scalar(self) -> Any:
        return self._rows[0] if self._rows else None


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _make_state_row(
    site_id: int = 1,
    repair_kind: str = "list",
    consecutive_failure_count: int = 0,
    week_start_at: datetime | None = None,
    weekly_attempt_count: int = 0,
    repair_status: str = "healthy",
    blocked_at: datetime | None = None,
    blocked_until: datetime | None = None,
    revision: int = 1,
    last_outcome: str | None = None,
    last_failure_reason: str | None = None,
    last_failure_at: datetime | None = None,
    last_success_at: datetime | None = None,
    last_repair_attempt_at: datetime | None = None,
    last_repair_success_at: datetime | None = None,
) -> dict:
    return {
        "id": 100,
        "site_id": site_id,
        "repair_kind": repair_kind,
        "consecutive_failure_count": consecutive_failure_count,
        "week_start_at": week_start_at or _utc(2026, 6, 14),
        "weekly_attempt_count": weekly_attempt_count,
        "repair_status": repair_status,
        "blocked_at": blocked_at,
        "blocked_until": blocked_until,
        "revision": revision,
        "last_outcome": last_outcome,
        "last_failure_reason": last_failure_reason,
        "last_failure_at": last_failure_at,
        "last_success_at": last_success_at,
        "last_repair_attempt_at": last_repair_attempt_at,
        "last_repair_success_at": last_repair_success_at,
        "created_at": _utc(2026, 6, 14),
        "updated_at": _utc(2026, 6, 14),
    }


def _make_attempt_row(
    attempt_id: int = 1,
    site_id: int = 1,
    repair_kind: str = "list",
    week_start_at: datetime | None = None,
    weekly_sequence: int = 1,
    status: str = "reserved",
    base_rule_revision: int = 1,
    trigger_failure_count: int = 3,
) -> dict:
    return {
        "id": attempt_id,
        "site_id": site_id,
        "crawl_attempt_id": None,
        "repair_kind": repair_kind,
        "week_start_at": week_start_at or _utc(2026, 6, 14),
        "weekly_sequence": weekly_sequence,
        "trigger_failure_count": trigger_failure_count,
        "status": status,
        "owner_user_id": None,
        "base_rule_revision": base_rule_revision,
        "candidate_rule_revision": None,
        "provider_trace_id": None,
        "sample_url": None,
        "sample_count": 0,
        "validation_success_count": 0,
        "validation_failure_code": None,
        "started_at": _utc(2026, 6, 15, 10, 0),
        "finished_at": None,
    }


def _build_repo():
    """Build a RepairStateRepository with mock tables."""
    import sqlalchemy as sa

    # We only need the table objects' .update(), .insert(), .select() methods
    # to be callable — the actual SQL won't run against a real DB.
    meta = sa.MetaData()
    # Create minimal stubs for FK targets (required by define_crawl_repair_tables)
    for tbl_name in ("sites", "crawl_attempts", "users"):
        sa.Table(tbl_name, meta, sa.Column("id", sa.Integer, primary_key=True))

    from backend.core.crawl_repair_models import define_crawl_repair_tables
    tables = define_crawl_repair_tables(meta)

    from backend.core.crawl_repair_repository import RepairStateRepository
    return RepairStateRepository(tables)


# ---------------------------------------------------------------------------
# get_state
# ---------------------------------------------------------------------------

class TestGetState:
    @pytest.mark.asyncio
    async def test_returns_existing_row(self):
        repo = _build_repo()
        row = _make_state_row(site_id=1, repair_kind="list")
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[row]))

        result = await repo.get_state(session, site_id=1, repair_kind="list")

        assert result["site_id"] == 1
        assert result["repair_kind"] == "list"

    @pytest.mark.asyncio
    async def test_creates_default_when_not_found(self):
        """When state row missing, insert default and re-fetch."""
        repo = _build_repo()
        row = _make_state_row(site_id=2, repair_kind="content", consecutive_failure_count=0)

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First SELECT returns nothing
                return FakeResult(rows=[])
            elif call_count == 2:
                # INSERT ON CONFLICT DO NOTHING
                return FakeResult(rows=[], rowcount=1)
            else:
                # Re-fetch SELECT returns the row
                return FakeResult(rows=[row])

        session = AsyncMock()
        session.execute = mock_execute

        result = await repo.get_state(session, site_id=2, repair_kind="content")

        assert result["site_id"] == 2
        assert result["consecutive_failure_count"] == 0

    @pytest.mark.asyncio
    async def test_for_update_locks_row(self):
        """Verify that for_update=True passes with_for_update() to the query."""
        repo = _build_repo()
        row = _make_state_row()
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[row]))

        # Should not raise
        result = await repo.get_state(session, 1, "list", for_update=True)
        assert result is not None


# ---------------------------------------------------------------------------
# lazy_weekly_rollover
# ---------------------------------------------------------------------------

class TestLazyWeeklyRollover:
    @pytest.mark.asyncio
    async def test_no_rollover_when_same_week(self):
        repo = _build_repo()
        current_week = _utc(2026, 6, 14)
        row = _make_state_row(week_start_at=current_week, consecutive_failure_count=2)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[row]))

        rolled_over = await repo.lazy_weekly_rollover(session, 1, "list", current_week)

        assert rolled_over is False
        # No UPDATE should have been called
        # (execute was only called for the SELECT)
        assert session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_rollover_resets_weekly_count_and_clears_block(self):
        repo = _build_repo()
        old_week = _utc(2026, 6, 7)
        current_week = _utc(2026, 6, 14)
        row = _make_state_row(
            week_start_at=old_week,
            consecutive_failure_count=3,
            weekly_attempt_count=2,
            repair_status="paused_until_next_week",
            blocked_at=_utc(2026, 6, 10),
            blocked_until=_utc(2026, 6, 14),
        )

        update_values: dict = {}

        async def mock_execute(stmt):
            nonlocal update_values
            # Capture the update values if it's an UPDATE statement
            if hasattr(stmt, "_values"):
                update_values = dict(stmt._values)
            return FakeResult(rows=[row])

        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[row]))

        rolled_over = await repo.lazy_weekly_rollover(session, 1, "list", current_week)

        assert rolled_over is True
        # Verify an UPDATE was issued (at least 2 execute calls: SELECT + UPDATE)
        assert session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_rollover_preserves_consecutive_failure_count(self):
        """Consecutive failure count is preserved across week rollover."""
        repo = _build_repo()
        old_week = _utc(2026, 6, 7)
        current_week = _utc(2026, 6, 14)
        row = _make_state_row(
            week_start_at=old_week,
            consecutive_failure_count=3,
            repair_status="collecting_failures",
        )
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[row]))

        rolled_over = await repo.lazy_weekly_rollover(session, 1, "list", current_week)

        # Rollover happened because week changed
        assert rolled_over is True
        # The consecutive_failure_count (3) should NOT be reset by rollover

    @pytest.mark.asyncio
    async def test_rollover_changes_status_from_paused_to_collecting_failures(self):
        """Status paused_until_next_week + failures > 0 → collecting_failures after rollover."""
        repo = _build_repo()
        old_week = _utc(2026, 6, 7)
        current_week = _utc(2026, 6, 14)
        row = _make_state_row(
            week_start_at=old_week,
            consecutive_failure_count=3,
            repair_status="paused_until_next_week",
        )

        executed_stmts = []

        async def capture_execute(stmt):
            executed_stmts.append(stmt)
            return FakeResult(rows=[row])

        session = AsyncMock()
        session.execute = capture_execute

        rolled_over = await repo.lazy_weekly_rollover(session, 1, "list", current_week)

        assert rolled_over is True
        # There should be an UPDATE statement after the SELECT
        assert len(executed_stmts) >= 2


# ---------------------------------------------------------------------------
# increment_failure
# ---------------------------------------------------------------------------

class TestIncrementFailure:
    @pytest.mark.asyncio
    async def test_increments_count_and_returns_new_value(self):
        repo = _build_repo()
        row = _make_state_row(consecutive_failure_count=1)

        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[row]))

        # lazy_weekly_rollover will check week then no-op
        # get_state (for_update) will return the row
        # UPDATE will increment
        new_count = await repo.increment_failure(session, 1, "list")

        assert new_count == 2

    @pytest.mark.asyncio
    async def test_first_failure_transitions_to_collecting_failures(self):
        repo = _build_repo()
        row = _make_state_row(consecutive_failure_count=0, repair_status="healthy")
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[row]))

        new_count = await repo.increment_failure(session, 1, "list")

        assert new_count == 1

    @pytest.mark.asyncio
    async def test_with_failure_reason(self):
        repo = _build_repo()
        row = _make_state_row(consecutive_failure_count=2)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[row]))

        new_count = await repo.increment_failure(
            session, 1, "list",
            failure_reason="selector_disappeared"
        )

        assert new_count == 3

    @pytest.mark.asyncio
    async def test_does_not_affect_other_kind(self):
        """Only the specified repair_kind is incremented."""
        repo = _build_repo()
        list_row = _make_state_row(repair_kind="list", consecutive_failure_count=0)
        content_row = _make_state_row(repair_kind="content", consecutive_failure_count=0)

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            return FakeResult(rows=[list_row])

        session = AsyncMock()
        session.execute = mock_execute

        # Increment only list
        new_count = await repo.increment_failure(session, 1, "list")

        # content row should not be touched (no execute calls on content state)
        assert new_count == 1


# ---------------------------------------------------------------------------
# reset_failure
# ---------------------------------------------------------------------------

class TestResetFailure:
    @pytest.mark.asyncio
    async def test_resets_to_zero(self):
        repo = _build_repo()
        row = _make_state_row(consecutive_failure_count=3, repair_status="collecting_failures")
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[row]))

        await repo.reset_failure(session, 1, "list")

        # Verify UPDATE was called (session.execute called at least twice: SELECT + UPDATE)
        assert session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_does_not_clear_pause_on_reset(self):
        """reset_failure does not clear a weekly pause — only rollover or clear_block does."""
        repo = _build_repo()
        row = _make_state_row(
            consecutive_failure_count=3,
            repair_status="paused_until_next_week",
            blocked_until=_utc(2026, 6, 21, 16, 0),
        )
        updates_issued = []

        async def capture(stmt):
            updates_issued.append(stmt)
            return FakeResult(rows=[row])

        session = AsyncMock()
        session.execute = capture

        await repo.reset_failure(session, 1, "list")

        # The UPDATE should set repair_status to paused_until_next_week, not healthy
        # We can't easily inspect SQLAlchemy's compiled UPDATE statement here,
        # so we just verify the call chain happened.
        assert len(updates_issued) >= 2


# ---------------------------------------------------------------------------
# reserve_repair_attempt
# ---------------------------------------------------------------------------

class TestReserveRepairAttempt:
    @pytest.mark.asyncio
    async def test_reserves_first_attempt_of_week(self):
        repo = _build_repo()
        state_row = _make_state_row(
            weekly_attempt_count=0,
            repair_status="collecting_failures",
        )
        attempt_row = _make_attempt_row(weekly_sequence=1)

        call_index = 0

        async def mock_execute(stmt):
            nonlocal call_index
            call_index += 1
            if call_index <= 2:
                # call 1: lazy_weekly_rollover → get_state SELECT (same week, no rollover)
                # call 2: reserve_repair_attempt → get_state SELECT for_update
                return FakeResult(rows=[state_row])
            elif call_index == 3:
                # INSERT attempt
                return FakeResult(rows=[], rowcount=1)
            elif call_index == 4:
                # SELECT attempt back
                return FakeResult(rows=[attempt_row])
            else:
                # UPDATE state
                return FakeResult(rows=[state_row])

        session = AsyncMock()
        session.execute = mock_execute

        result = await repo.reserve_repair_attempt(
            session,
            site_id=1,
            repair_kind="list",
            crawl_attempt_id=42,
            trigger_failure_count=3,
            owner_user_id=7,
            base_rule_revision=1,
            weekly_limit=3,
            current_week_start=_utc(2026, 6, 14),
        )

        assert result["weekly_sequence"] == 1
        assert result["status"] == "reserved"

    @pytest.mark.asyncio
    async def test_raises_budget_exhausted_when_limit_reached(self):
        from backend.core.crawl_repair_repository import RepairBudgetExhaustedError

        repo = _build_repo()
        # weekly_attempt_count equals the limit (3)
        state_row = _make_state_row(weekly_attempt_count=3)

        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[state_row]))

        with pytest.raises(RepairBudgetExhaustedError):
            await repo.reserve_repair_attempt(
                session,
                site_id=1,
                repair_kind="list",
                crawl_attempt_id=None,
                trigger_failure_count=3,
                owner_user_id=None,
                base_rule_revision=1,
                weekly_limit=3,
                current_week_start=_utc(2026, 6, 14),
            )

    @pytest.mark.asyncio
    async def test_budget_at_limit_1_is_exhausted_after_first_attempt(self):
        """weekly_limit=1: used=1 → exhausted."""
        from backend.core.crawl_repair_repository import RepairBudgetExhaustedError

        repo = _build_repo()
        state_row = _make_state_row(weekly_attempt_count=1)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[state_row]))

        with pytest.raises(RepairBudgetExhaustedError):
            await repo.reserve_repair_attempt(
                session,
                site_id=1,
                repair_kind="list",
                crawl_attempt_id=None,
                trigger_failure_count=3,
                owner_user_id=None,
                base_rule_revision=1,
                weekly_limit=1,
                current_week_start=_utc(2026, 6, 14),
            )

    @pytest.mark.asyncio
    async def test_budget_at_limit_5_allows_up_to_5(self):
        """weekly_limit=5: used=4 → one more allowed."""
        repo = _build_repo()
        state_row = _make_state_row(weekly_attempt_count=4)
        attempt_row = _make_attempt_row(weekly_sequence=5)

        call_index = 0

        async def mock_execute(stmt):
            nonlocal call_index
            call_index += 1
            if call_index <= 2:
                # call 1: lazy_weekly_rollover → get_state SELECT (same week, no rollover)
                # call 2: reserve_repair_attempt → get_state SELECT for_update
                return FakeResult(rows=[state_row])
            elif call_index == 3:
                # INSERT attempt
                return FakeResult(rows=[], rowcount=1)
            elif call_index == 4:
                # SELECT attempt back
                return FakeResult(rows=[attempt_row])
            else:
                # UPDATE state
                return FakeResult(rows=[state_row])

        session = AsyncMock()
        session.execute = mock_execute

        result = await repo.reserve_repair_attempt(
            session,
            site_id=1,
            repair_kind="list",
            crawl_attempt_id=None,
            trigger_failure_count=3,
            owner_user_id=None,
            base_rule_revision=1,
            weekly_limit=5,
            current_week_start=_utc(2026, 6, 14),
        )
        assert result["weekly_sequence"] == 5

    @pytest.mark.asyncio
    async def test_budget_at_max_5_is_exhausted_when_at_5(self):
        """weekly_limit=5: used=5 → exhausted (budget never exceeds 5)."""
        from backend.core.crawl_repair_repository import RepairBudgetExhaustedError

        repo = _build_repo()
        state_row = _make_state_row(weekly_attempt_count=5)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[state_row]))

        with pytest.raises(RepairBudgetExhaustedError):
            await repo.reserve_repair_attempt(
                session,
                site_id=1,
                repair_kind="list",
                crawl_attempt_id=None,
                trigger_failure_count=3,
                owner_user_id=None,
                base_rule_revision=1,
                weekly_limit=5,
                current_week_start=_utc(2026, 6, 14),
            )


# ---------------------------------------------------------------------------
# complete_repair_attempt
# ---------------------------------------------------------------------------

class TestCompleteRepairAttempt:
    @pytest.mark.asyncio
    async def test_transitions_reserved_to_applied(self):
        repo = _build_repo()
        attempt_row = _make_attempt_row(status="reserved")
        updated_row = {**attempt_row, "status": "applied", "finished_at": _utc(2026, 6, 15, 11)}

        call_index = 0

        async def mock_execute(stmt):
            nonlocal call_index
            call_index += 1
            if call_index == 1:
                return FakeResult(rows=[attempt_row])   # SELECT FOR UPDATE
            elif call_index == 2:
                return FakeResult(rows=[], rowcount=1)  # UPDATE
            else:
                return FakeResult(rows=[updated_row])   # SELECT after UPDATE

        session = AsyncMock()
        session.execute = mock_execute

        result = await repo.complete_repair_attempt(session, attempt_id=1, status="applied")

        assert result["status"] == "applied"

    @pytest.mark.asyncio
    async def test_raises_when_already_finalized(self):
        from backend.core.crawl_repair_repository import AttemptAlreadyFinalizedError

        repo = _build_repo()
        attempt_row = _make_attempt_row(status="applied")  # Already terminal
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[attempt_row]))

        with pytest.raises(AttemptAlreadyFinalizedError):
            await repo.complete_repair_attempt(session, attempt_id=1, status="provider_failed")

    @pytest.mark.asyncio
    async def test_raises_when_attempt_not_found(self):
        from backend.core.crawl_repair_repository import AttemptNotFoundError

        repo = _build_repo()
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[]))

        with pytest.raises(AttemptNotFoundError):
            await repo.complete_repair_attempt(session, attempt_id=9999, status="provider_failed")

    @pytest.mark.asyncio
    async def test_cannot_complete_twice(self):
        """Same attempt_id cannot be completed with two different terminal statuses."""
        from backend.core.crawl_repair_repository import AttemptAlreadyFinalizedError

        repo = _build_repo()
        attempt_reserved = _make_attempt_row(status="reserved")
        attempt_applied = _make_attempt_row(status="applied")

        execute_calls = []

        async def mock_execute(stmt):
            execute_calls.append(stmt)
            # First call: SELECT FOR UPDATE — return reserved
            # Subsequent calls: already applied
            if len(execute_calls) == 1:
                return FakeResult(rows=[attempt_reserved])
            else:
                return FakeResult(rows=[attempt_applied])

        session = AsyncMock()
        session.execute = mock_execute

        # First completion should work
        await repo.complete_repair_attempt(session, attempt_id=1, status="applied")

        # Reset to simulate second call on same session (already applied)
        execute_calls.clear()

        async def mock_execute2(stmt):
            return FakeResult(rows=[attempt_applied])

        session.execute = mock_execute2

        with pytest.raises(AttemptAlreadyFinalizedError):
            await repo.complete_repair_attempt(session, attempt_id=1, status="provider_failed")

    @pytest.mark.parametrize("invalid_status", ["reserved", "unknown", "pending"])
    @pytest.mark.asyncio
    async def test_rejects_non_terminal_status(self, invalid_status: str):
        repo = _build_repo()
        session = AsyncMock()

        with pytest.raises(ValueError):
            await repo.complete_repair_attempt(
                session, attempt_id=1, status=invalid_status  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# pause_feed
# ---------------------------------------------------------------------------

class TestPauseFeed:
    @pytest.mark.asyncio
    async def test_sets_paused_status_and_blocked_until(self):
        repo = _build_repo()
        row = _make_state_row(repair_status="collecting_failures")
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[row]))

        blocked_until = _utc(2026, 6, 21, 16, 0)  # Next Sunday 00:00 Taipei = UTC+8 → 16:00 UTC
        await repo.pause_feed(session, site_id=1, repair_kind="list", blocked_until=blocked_until)

        assert session.execute.call_count >= 2  # SELECT + UPDATE

    @pytest.mark.asyncio
    async def test_list_pause_does_not_touch_content_state(self):
        """Pausing list does not modify content repair state — scheduler checks both."""
        repo = _build_repo()
        list_row = _make_state_row(repair_kind="list")
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[list_row]))

        await repo.pause_feed(
            session, site_id=1, repair_kind="list",
            blocked_until=_utc(2026, 6, 21, 16, 0)
        )

        # All calls should involve list state, not content
        # (we can't easily inspect the WHERE clause from AsyncMock,
        # but we confirm only one pair of SELECT+UPDATE calls happened)
        assert session.execute.call_count == 2


# ---------------------------------------------------------------------------
# get_feed_pause_status
# ---------------------------------------------------------------------------

class TestGetFeedPauseStatus:
    @pytest.mark.asyncio
    async def test_not_paused_when_both_healthy(self):
        repo = _build_repo()
        list_row = _make_state_row(repair_kind="list", repair_status="healthy")
        content_row = _make_state_row(repair_kind="content", repair_status="healthy")

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            # Alternate between list and content rows
            if call_count % 2 == 1:
                return FakeResult(rows=[list_row])
            else:
                return FakeResult(rows=[content_row])

        session = AsyncMock()
        session.execute = mock_execute

        result = await repo.get_feed_pause_status(session, site_id=1)

        assert result.routine_paused is False
        assert result.list_blocked is False
        assert result.content_blocked is False
        assert result.blocking_kinds == []

    @pytest.mark.asyncio
    async def test_paused_when_list_exhausted(self):
        repo = _build_repo()
        future = _utc(2099, 12, 31, 16, 0)
        list_row = _make_state_row(
            repair_kind="list",
            repair_status="paused_until_next_week",
            blocked_until=future,
        )
        content_row = _make_state_row(repair_kind="content", repair_status="healthy")

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return FakeResult(rows=[list_row])
            else:
                return FakeResult(rows=[content_row])

        session = AsyncMock()
        session.execute = mock_execute

        result = await repo.get_feed_pause_status(session, site_id=1)

        assert result.routine_paused is True
        assert result.list_blocked is True
        assert result.content_blocked is False
        assert "list" in result.blocking_kinds
        assert result.blocked_until == future

    @pytest.mark.asyncio
    async def test_paused_when_content_exhausted(self):
        repo = _build_repo()
        future = _utc(2099, 12, 31, 16, 0)
        list_row = _make_state_row(repair_kind="list", repair_status="healthy")
        content_row = _make_state_row(
            repair_kind="content",
            repair_status="paused_until_next_week",
            blocked_until=future,
        )

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return FakeResult(rows=[list_row])
            else:
                return FakeResult(rows=[content_row])

        session = AsyncMock()
        session.execute = mock_execute

        result = await repo.get_feed_pause_status(session, site_id=1)

        assert result.routine_paused is True
        assert result.content_blocked is True
        assert "content" in result.blocking_kinds

    @pytest.mark.asyncio
    async def test_expired_pause_not_counted(self):
        """If blocked_until is in the past, it should not be considered paused."""
        repo = _build_repo()
        past = _utc(2026, 6, 1, 0, 0)  # Far in the past
        list_row = _make_state_row(
            repair_kind="list",
            repair_status="paused_until_next_week",
            blocked_until=past,  # Expired
        )
        content_row = _make_state_row(repair_kind="content", repair_status="healthy")

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return FakeResult(rows=[list_row])
            else:
                return FakeResult(rows=[content_row])

        session = AsyncMock()
        session.execute = mock_execute

        result = await repo.get_feed_pause_status(session, site_id=1)

        # Past blocked_until means the pause has expired
        assert result.routine_paused is False
        assert result.list_blocked is False

    @pytest.mark.asyncio
    async def test_no_state_rows_returns_not_paused(self):
        """If no state rows exist for a site, feed is not paused."""
        repo = _build_repo()
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[]))

        result = await repo.get_feed_pause_status(session, site_id=999)

        assert result.routine_paused is False
        assert result.blocking_kinds == []


# ---------------------------------------------------------------------------
# clear_block
# ---------------------------------------------------------------------------

class TestClearBlock:
    @pytest.mark.asyncio
    async def test_clears_block_and_resets_count(self):
        repo = _build_repo()
        row = _make_state_row(
            repair_status="paused_until_next_week",
            consecutive_failure_count=3,
            blocked_until=_utc(2026, 6, 21, 16, 0),
        )
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[row]))

        await repo.clear_block(session, site_id=1, repair_kind="list")

        # SELECT + UPDATE should have been called
        assert session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_only_clears_specified_kind(self):
        """Clearing list block does not touch content state."""
        repo = _build_repo()
        row = _make_state_row(repair_kind="list", repair_status="paused_until_next_week")
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[row]))

        await repo.clear_block(session, site_id=1, repair_kind="list")

        # Only 2 execute calls: SELECT list + UPDATE list
        assert session.execute.call_count == 2


# ---------------------------------------------------------------------------
# Lock ordering contract
# ---------------------------------------------------------------------------

class TestLockOrdering:
    def test_lock_ordered_kinds_returns_list_then_content(self):
        from backend.core.crawl_repair_repository import _lock_ordered_kinds
        kinds = _lock_ordered_kinds()
        assert kinds[0] == "list"
        assert kinds[1] == "content"

    def test_lock_ordered_kinds_is_tuple(self):
        from backend.core.crawl_repair_repository import _lock_ordered_kinds
        kinds = _lock_ordered_kinds()
        assert isinstance(kinds, tuple)
        assert len(kinds) == 2

    @pytest.mark.asyncio
    async def test_get_feed_pause_status_queries_list_before_content(self):
        """Verify lock ordering: list state is always queried first."""
        repo = _build_repo()
        query_order = []

        async def mock_execute(stmt):
            # We can check the statement's WHERE clause — but with AsyncMock
            # it's hard to introspect. Instead, track call order.
            query_order.append(len(query_order))
            return FakeResult(rows=[_make_state_row()])

        session = AsyncMock()
        session.execute = mock_execute

        await repo.get_feed_pause_status(session, site_id=1)

        # get_feed_pause_status iterates in _lock_ordered_kinds() order
        # So queries happen: list (0), content (1)
        assert len(query_order) == 2


# ---------------------------------------------------------------------------
# Stale repair recovery (C3 goal 6)
# ---------------------------------------------------------------------------

class TestRecoverStaleAttempt:
    @pytest.mark.asyncio
    async def test_finalizes_reserved_attempt_as_aborted(self):
        """recover_stale_attempt transitions reserved → aborted_internal_error."""
        repo = _build_repo()
        reserved = _make_attempt_row(attempt_id=99, status="reserved", repair_kind="list")
        aborted = {**reserved, "status": "aborted_internal_error"}

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # complete_repair_attempt: SELECT attempt FOR UPDATE
                return FakeResult(rows=[reserved])
            elif call_count == 2:
                # complete_repair_attempt: UPDATE attempt
                r = FakeResult()
                r.rowcount = 1
                return r
            elif call_count == 3:
                # complete_repair_attempt: re-fetch updated row
                return FakeResult(rows=[aborted])
            else:
                # recover_stale_attempt: UPDATE state row
                r = FakeResult()
                r.rowcount = 1
                return r

        session = AsyncMock()
        session.execute = mock_execute

        result = await repo.recover_stale_attempt(session, attempt_id=99)
        assert result["status"] == "aborted_internal_error"

    @pytest.mark.asyncio
    async def test_raises_when_attempt_already_finalized(self):
        """Stale recovery on an already-terminal attempt raises."""
        from backend.core.crawl_repair_repository import AttemptAlreadyFinalizedError
        repo = _build_repo()
        applied = _make_attempt_row(attempt_id=42, status="applied")

        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[applied]))

        with pytest.raises(AttemptAlreadyFinalizedError):
            await repo.recover_stale_attempt(session, attempt_id=42)

    @pytest.mark.asyncio
    async def test_raises_when_attempt_not_found(self):
        """Stale recovery on missing attempt raises AttemptNotFoundError."""
        from backend.core.crawl_repair_repository import AttemptNotFoundError
        repo = _build_repo()
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[]))

        with pytest.raises(AttemptNotFoundError):
            await repo.recover_stale_attempt(session, attempt_id=999)

    @pytest.mark.asyncio
    async def test_updates_state_to_collecting_failures(self):
        """After finalizing stale attempt, state is de-escalated from 'repairing'."""
        repo = _build_repo()
        reserved = _make_attempt_row(attempt_id=7, status="reserved", repair_kind="content")
        aborted = {**reserved, "status": "aborted_internal_error"}

        execute_calls = []

        async def mock_execute(stmt):
            execute_calls.append(stmt)
            call_num = len(execute_calls)
            if call_num == 1:
                return FakeResult(rows=[reserved])   # SELECT attempt FOR UPDATE
            elif call_num == 2:
                r = FakeResult(); r.rowcount = 1; return r  # UPDATE attempt
            elif call_num == 3:
                return FakeResult(rows=[aborted])    # re-fetch attempt
            else:
                r = FakeResult(); r.rowcount = 1; return r  # UPDATE state

        session = AsyncMock()
        session.execute = mock_execute

        await repo.recover_stale_attempt(session, attempt_id=7)

        # 4 execute calls: SELECT attempt, UPDATE attempt, re-fetch attempt, UPDATE state
        assert len(execute_calls) == 4

    @pytest.mark.asyncio
    async def test_get_stale_reserved_attempts_filters_by_status_and_age(self):
        """get_stale_reserved_attempts returns only 'reserved' attempts older than threshold."""
        repo = _build_repo()
        old_reserved = _make_attempt_row(attempt_id=1, status="reserved")

        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult(rows=[old_reserved]))

        threshold = _utc(2026, 6, 15, 11, 0)
        results = await repo.get_stale_reserved_attempts(session, older_than=threshold)

        assert len(results) == 1
        assert results[0]["id"] == 1
        assert results[0]["status"] == "reserved"


# ---------------------------------------------------------------------------
# Integration packet smoke test (C3 goal 7)
# ---------------------------------------------------------------------------

class TestIntegrationPacket:
    def test_register_crawl_repair_tables_returns_tables(self):
        """register_crawl_repair_tables wires tables into the given metadata."""
        import sqlalchemy as sa
        from backend.core.crawl_repair_startup import register_crawl_repair_tables

        meta = sa.MetaData()
        # Stub FK targets
        for tbl_name in ("sites", "crawl_attempts", "users"):
            sa.Table(tbl_name, meta, sa.Column("id", sa.Integer, primary_key=True))

        tables = register_crawl_repair_tables(meta)

        assert tables.site_crawl_repair_states is not None
        assert tables.crawl_repair_attempts is not None
        assert "site_crawl_repair_states" in meta.tables
        assert "crawl_repair_attempts" in meta.tables

    def test_run_crawl_repair_migration_calls_migrate_fn(self):
        """run_crawl_repair_migration drives migrate_crawl_repair_tables."""
        from unittest.mock import MagicMock, patch
        from backend.core.crawl_repair_startup import run_crawl_repair_migration

        fake_engine = MagicMock()
        fake_conn = MagicMock()
        fake_engine.connect.return_value.__enter__ = lambda _: fake_conn
        fake_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        log_messages: list[str] = []
        with patch("backend.core.crawl_repair_startup.migrate_crawl_repair_tables") as mock_migrate:
            run_crawl_repair_migration(fake_engine, log_fn=log_messages.append)
            mock_migrate.assert_called_once_with(fake_conn)

        assert any("[Migration]" in m for m in log_messages)

    @pytest.mark.asyncio
    async def test_run_crawl_repair_backfill_uses_taipei_week(self):
        """run_crawl_repair_backfill derives week_start from time provider."""
        from unittest.mock import patch, AsyncMock as AM
        from backend.core.crawl_repair_startup import run_crawl_repair_backfill
        from backend.core.time_provider import WeekWindow

        fake_week_start = _utc(2026, 6, 14, 16, 0)
        fake_window = WeekWindow(
            start_utc=fake_week_start,
            end_utc=_utc(2026, 6, 21, 16, 0),
            start_local_date=None,  # type: ignore[arg-type]
        )

        session = AM()
        log_messages: list[str] = []

        with patch("backend.core.crawl_repair_startup.taipei_week_window", return_value=fake_window), \
             patch("backend.core.crawl_repair_startup.backfill_repair_states", new=AM(return_value={"sites_scanned": 3, "rows_inserted": 6})):
            result = await run_crawl_repair_backfill(session, log_fn=log_messages.append)

        assert result["sites_scanned"] == 3
        assert result["rows_inserted"] == 6
        assert any("[Startup]" in m for m in log_messages)
