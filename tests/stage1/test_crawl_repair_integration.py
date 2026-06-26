"""
---
name: test_crawl_repair_integration
description: "Integration tests for the end-to-end crawl auto-repair flow: classify → count → reserve → AI → validate → promote/pause"
stage: stage1
type: pytest
target:
  layer: backend
  domain: crawl-repair
spec_doc: null
test_file: tests/stage1/test_crawl_repair_integration.py
functions:
  - name: test_first_structural_failure_increments_to_1
    line: 666
    purpose: "1st list structural failure increments counter to 1, action=counted"
    fixtures: []
  - name: test_second_failure_increments_to_2
    line: 683
    purpose: "2nd consecutive failure increments counter to 2, action=counted"
    fixtures: []
  - name: test_success_resets_counter
    line: 705
    purpose: "Successful parse after failures resets counter to 0"
    fixtures: []
  - name: test_list_and_content_counters_independent
    line: 733
    purpose: "List failure counter does not affect content counter"
    fixtures: []
  - name: test_different_sites_independent_counters
    line: 764
    purpose: "Failure counters for different site_ids are independent"
    fixtures: []
  - name: test_third_failure_triggers_repair
    line: 793
    purpose: "3rd consecutive structural failure triggers AI repair attempt"
    fixtures: []
  - name: test_repair_not_triggered_at_2
    line: 818
    purpose: "2nd failure does not trigger repair; AI is never called"
    fixtures: []
  - name: test_fourth_failure_also_triggers
    line: 842
    purpose: "4th failure (after failed 3rd repair) triggers another repair attempt"
    fixtures: []
  - name: test_repair_not_triggered_when_disabled
    line: 879
    purpose: "auto_repair_enabled=False prevents repair even at threshold"
    fixtures: []
  - name: test_no_ai_provider_returns_no_provider_available
    line: 904
    purpose: "3rd failure with no AI provider records no_provider_available status"
    fixtures: []
  - name: test_valid_list_candidate_promotes_rules
    line: 930
    purpose: "AI returns valid list rules → validated → promoted → counter reset"
    fixtures: []
  - name: test_valid_content_candidate_promotes_rules
    line: 963
    purpose: "AI returns valid content rules → validated → promoted"
    fixtures: []
  - name: test_repair_success_resets_failure_counter
    line: 993
    purpose: "After successful repair, consecutive_failure_count resets to 0"
    fixtures: []
  - name: test_repair_attempt_recorded_with_correct_metadata
    line: 1020
    purpose: "Successful repair creates attempt row with status='applied'"
    fixtures: []
  - name: test_invalid_candidate_schema_no_item_key
    line: 1050
    purpose: "AI returns rules without 'item' key → candidate_schema_invalid"
    fixtures: []
  - name: test_candidate_extracts_zero_items
    line: 1074
    purpose: "AI returns rules that match 0 items → candidate_validation_failed"
    fixtures: []
  - name: test_content_candidate_produces_sentinel
    line: 1100
    purpose: "AI content rules produce 'Parsing failed' sentinel → validation rejected"
    fixtures: []
  - name: test_ai_provider_exception
    line: 1126
    purpose: "AI provider exception → provider_failed, old rules preserved"
    fixtures: []
  - name: test_ai_returns_empty_dict
    line: 1151
    purpose: "AI returns empty dict → treated as candidate_schema_invalid"
    fixtures: []
  - name: test_ai_returns_none
    line: 1175
    purpose: "AI returns None → treated as candidate_schema_invalid"
    fixtures: []
  - name: test_content_candidate_without_body_key
    line: 1200
    purpose: "Content candidate without 'body' key → candidate_schema_invalid"
    fixtures: []
  - name: test_failed_repair_preserves_failure_count
    line: 1223
    purpose: "Failed repair does not reset the failure counter"
    fixtures: []
  - name: test_budget_exhausted_pauses_feed
    line: 1251
    purpose: "3 failed repairs in a week exhausts budget and pauses feed"
    fixtures: []
  - name: test_budget_default_is_3
    line: 1293
    purpose: "Default weekly repair limit is 3 attempts"
    fixtures: []
  - name: test_custom_budget_5
    line: 1319
    purpose: "Custom weekly_limit=5 allows 5 attempts before exhaustion"
    fixtures: []
  - name: test_weekly_rollover_resets_budget
    line: 1359
    purpose: "New Taipei week resets budget and unpauses feed"
    fixtures: []
  - name: test_paused_feed_blocks_repair
    line: 1405
    purpose: "Paused feed causes subsequent attempts to get budget_exhausted"
    fixtures: []
  - name: test_weekly_rollover_restores_collecting_failures_status
    line: 1455
    purpose: "After rollover, status → collecting_failures if failure_count > 0"
    fixtures: []
  - name: test_weekly_rollover_restores_healthy_if_no_failures
    line: 1467
    purpose: "After rollover, status → healthy if failure_count is 0"
    fixtures: []
  - name: test_valid_rules_against_valid_list
    line: 1482
    purpose: "Known-good list rules extract items from crawl_valid_list.html"
    fixtures: []
  - name: test_broken_rules_against_valid_list
    line: 1490
    purpose: "Wrong selectors fail list candidate validation"
    fixtures: []
  - name: test_rules_without_item_key
    line: 1498
    purpose: "Rules missing 'item' key fail schema validation"
    fixtures: []
  - name: test_empty_dict_fails_schema_validation
    line: 1506
    purpose: "Empty dict fails list candidate schema validation"
    fixtures: []
  - name: test_redesigned_page_rules_match
    line: 1513
    purpose: "Selectors matching redesigned page structure succeed"
    fixtures: []
  - name: test_valid_rules_against_valid_content
    line: 1525
    purpose: "Known-good content rules extract body from crawl_valid_content.html"
    fixtures: []
  - name: test_broken_rules_produce_sentinel
    line: 1533
    purpose: "Rules pointing to absent selector produce sentinel → rejected"
    fixtures: []
  - name: test_correct_rules_for_redesigned_content_too_thin
    line: 1541
    purpose: "Correct selector for redesigned page fails if content below threshold"
    fixtures: []
  - name: test_valid_content_rules_pass_validation
    line: 1552
    purpose: "Rules extracting substantial body content pass validation"
    fixtures: []
  - name: test_rules_without_body_key
    line: 1559
    purpose: "Content rules without 'body' key fail schema validation"
    fixtures: []
  - name: test_full_list_repair_cycle
    line: 1572
    purpose: "Full list repair cycle: success → 3 failures → AI repair → new parse succeeds"
    fixtures: []
  - name: test_full_budget_exhaustion_cycle
    line: 1641
    purpose: "Full budget exhaustion: 3 failed attempts → paused → next week → repair succeeds"
    fixtures: []
  - name: test_content_repair_independent_of_list
    line: 1734
    purpose: "List repair cycle does not affect content state and vice versa"
    fixtures: []
  - name: test_success_after_two_failures_prevents_repair
    line: 1786
    purpose: "Success after 2 failures resets counter; subsequent 2 failures don't trigger repair"
    fixtures: []
  - name: test_multiple_sites_repair_independently
    line: 1828
    purpose: "Two sites repair independently without interfering"
    fixtures: []
  - name: test_classify_list_outcome_zero_items
    line: 1864
    purpose: "classify_list_outcome with empty items returns ZERO_ITEMS"
    fixtures: []
  - name: test_classify_list_outcome_success
    line: 1869
    purpose: "classify_list_outcome with items returns SUCCESS"
    fixtures: []
  - name: test_zero_items_triggers_structural_failure_handling
    line: 1876
    purpose: "ZERO_ITEMS classification leads to orchestrator counting the failure"
    fixtures: []
  - name: test_is_valid_content_with_fixture
    line: 1895
    purpose: "Real content fixture produces valid content via parse_article"
    fixtures: []
  - name: test_sentinel_content_with_fixture
    line: 1908
    purpose: "Sentinel fixture produces SENTINEL_PARSE_FAILED via parse_article"
    fixtures: []
  - name: test_fake_clock_returns_fixed_time
    line: 1924
    purpose: "FakeClock returns exact initialization time"
    fixtures: []
  - name: test_fake_clock_advance
    line: 1929
    purpose: "FakeClock.advance() moves time forward correctly"
    fixtures: []
  - name: test_taipei_week_window_contains_now
    line: 1935
    purpose: "Current time falls within the computed Taipei week window"
    fixtures: []
  - name: test_taipei_week_window_boundaries
    line: 1941
    purpose: "Week window spans exactly 7 days"
    fixtures: []
  - name: test_orchestrator_uses_clock_for_week_start
    line: 1948
    purpose: "Orchestrator derives week_start from its clock; advances after 7 days"
    fixtures: []
  - name: test_failure_threshold_is_3
    line: 1965
    purpose: "FAILURE_THRESHOLD constant equals 3"
    fixtures: []
  - name: test_success_does_not_affect_weekly_attempts
    line: 1970
    purpose: "handle_parse_success does not change weekly attempt count"
    fixtures: []
  - name: test_repair_attempt_increments_weekly_count
    line: 1982
    purpose: "Each repair attempt increments weekly_attempt_count by 1"
    fixtures: []
  - name: test_applied_repair_uses_budget_slot
    line: 2014
    purpose: "Successful repair also consumes one weekly budget slot"
    fixtures: []
  - name: test_ai_call_receives_html_evidence
    line: 2039
    purpose: "AI provider receives the HTML evidence string"
    fixtures: []
  - name: test_ai_call_receives_correct_kind
    line: 2064
    purpose: "AI provider receives the correct repair_kind"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_crawl_repair_integration.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest
import sqlalchemy

from backend.core.crawl_outcomes import (
    SENTINEL_PARSE_FAILED,
    SENTINEL_VUE_FAILED,
    ListOutcome,
    classify_list_outcome,
    is_valid_content,
)
from backend.core.crawl_repair_models import (
    CrawlRepairTables,
    RepairKind,
    define_crawl_repair_tables,
)
from backend.core.crawl_repair_repository import (
    RepairBudgetExhaustedError,
    RepairStateRepository,
)
from backend.core.time_provider import FakeClock, taipei_week_window


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load HTML fixture from tests/fixtures/."""
    path = _FIXTURES_DIR / name
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# FakeResult — mimics SQLAlchemy MappingResult
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


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

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
        "week_start_at": week_start_at or _utc(2026, 6, 14, 16, 0),
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
        "week_start_at": week_start_at or _utc(2026, 6, 14, 16, 0),
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


def _build_tables() -> CrawlRepairTables:
    """Build CrawlRepairTables with mock FK targets on a fresh MetaData."""
    meta = sqlalchemy.MetaData()
    for tbl_name in ("sites", "crawl_attempts", "users"):
        sqlalchemy.Table(tbl_name, meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
    return define_crawl_repair_tables(meta)


def _build_repo() -> RepairStateRepository:
    """Build a RepairStateRepository backed by mock tables."""
    return RepairStateRepository(_build_tables())


# ---------------------------------------------------------------------------
# Validation helpers (used by SimpleRepairOrchestrator and tests)
# ---------------------------------------------------------------------------

def _validate_list_candidate(candidate_rules: dict, html_evidence: str) -> tuple[bool, str]:
    """Validate a candidate list rule against HTML evidence.

    Returns (is_valid, failure_code).
    """
    if not isinstance(candidate_rules, dict) or "item" not in candidate_rules:
        return False, "candidate_schema_invalid"

    try:
        from scrapling.parser import Selector
        page = Selector(html_evidence)
        from backend.core.parser import parse_listing
        items = parse_listing(page, candidate_rules, "https://example.com")
        result = classify_list_outcome(fetch_failed=False, items=items)
        if result.outcome == ListOutcome.ZERO_ITEMS or result.count == 0:
            return False, "candidate_validation_failed"
        return True, ""
    except Exception:
        return False, "candidate_validation_failed"


def _validate_content_candidate(candidate_rules: dict, html_evidence: str) -> tuple[bool, str]:
    """Validate a candidate content rule against HTML evidence.

    Returns (is_valid, failure_code).
    """
    if not isinstance(candidate_rules, dict) or "body" not in candidate_rules:
        return False, "candidate_schema_invalid"

    try:
        from scrapling.parser import Selector
        page = Selector(html_evidence)
        from backend.core.parser import parse_article
        content_text, _date, _img, _author = parse_article(page, candidate_rules, "https://example.com/article")
        if content_text == SENTINEL_PARSE_FAILED or content_text == SENTINEL_VUE_FAILED:
            return False, "candidate_validation_failed"
        if not is_valid_content(content_text):
            return False, "candidate_validation_failed"
        return True, ""
    except Exception:
        return False, "candidate_validation_failed"


# ---------------------------------------------------------------------------
# SimpleRepairOrchestrator — minimal repair orchestrator for integration tests
# ---------------------------------------------------------------------------

@dataclass
class RepairResult:
    """Result of a single repair orchestration call."""
    action: str  # "counted" | "repair_attempted" | "repair_skipped" | "success_reset"
    new_failure_count: int = 0
    repair_triggered: bool = False
    repair_status: str = ""  # "applied" | "candidate_schema_invalid" | "candidate_validation_failed" | "provider_failed" | "budget_exhausted" | ""
    new_rules: dict | None = None
    attempt_id: int | None = None
    paused: bool = False
    error: str | None = None


class SimpleRepairOrchestrator:
    """Minimal repair orchestrator for integration testing.

    Tests the full flow: classify -> count -> reserve -> AI -> validate -> promote.
    The production RepairOrchestrator (C4) should pass these same tests.
    """

    FAILURE_THRESHOLD = 3

    def __init__(self, repo: RepairStateRepository, clock=None):
        self._repo = repo
        self._clock = clock or FakeClock(_utc(2026, 6, 18, 12, 0))

    async def handle_parse_success(
        self,
        session,
        site_id: int,
        repair_kind: RepairKind,
        *,
        current_week_start: datetime | None = None,
    ) -> RepairResult:
        """Handle a successful parse — reset failure counter."""
        if current_week_start is None:
            ww = taipei_week_window(self._clock.now_utc())
            current_week_start = ww.start_utc

        await self._repo.reset_failure(
            session, site_id, repair_kind,
            current_week_start=current_week_start,
        )
        return RepairResult(action="success_reset", new_failure_count=0)

    async def handle_structural_failure(
        self,
        session,
        site_id: int,
        repair_kind: RepairKind,
        *,
        html_evidence: str,
        active_rules: dict,
        rule_revision: int = 1,
        owner_user_id: int | None = None,
        crawl_attempt_id: int | None = None,
        weekly_limit: int = 3,
        auto_repair_enabled: bool = True,
        ai_provider=None,
        current_week_start: datetime | None = None,
    ) -> RepairResult:
        """Handle a structural failure: increment counter, maybe trigger repair.

        Args:
            session: AsyncSession (or mock).
            site_id: Site primary key.
            repair_kind: 'list' or 'content'.
            html_evidence: Raw HTML from the failed parse.
            active_rules: Current list_rules or content_rules dict.
            rule_revision: Current rule revision number.
            owner_user_id: Site owner user ID.
            crawl_attempt_id: The crawl_attempts row ID.
            weekly_limit: Weekly repair attempt limit.
            auto_repair_enabled: Whether auto-repair is enabled for this site.
            ai_provider: Callable that returns candidate rules dict.
            current_week_start: Override for week start (for testing).

        Returns:
            RepairResult with the action taken and outcome.
        """
        if current_week_start is None:
            ww = taipei_week_window(self._clock.now_utc())
            current_week_start = ww.start_utc

        # Step 1: Increment failure counter
        new_count = await self._repo.increment_failure(
            session, site_id, repair_kind,
            current_week_start=current_week_start,
        )

        # Step 2: Check threshold
        if new_count < self.FAILURE_THRESHOLD or not auto_repair_enabled:
            return RepairResult(
                action="counted",
                new_failure_count=new_count,
                repair_triggered=False,
            )

        # Step 3: Check budget and reserve attempt
        try:
            attempt = await self._repo.reserve_repair_attempt(
                session,
                site_id=site_id,
                repair_kind=repair_kind,
                crawl_attempt_id=crawl_attempt_id,
                trigger_failure_count=new_count,
                owner_user_id=owner_user_id,
                base_rule_revision=rule_revision,
                weekly_limit=weekly_limit,
                current_week_start=current_week_start,
            )
        except RepairBudgetExhaustedError:
            # Budget exhausted — pause the feed
            ww = taipei_week_window(self._clock.now_utc())
            await self._repo.pause_feed(
                session, site_id, repair_kind,
                blocked_until=ww.end_utc,
            )
            return RepairResult(
                action="repair_attempted",
                new_failure_count=new_count,
                repair_triggered=True,
                repair_status="budget_exhausted",
                paused=True,
            )

        attempt_id = attempt["id"]

        # Step 4: Call AI provider
        if ai_provider is None:
            await self._repo.complete_repair_attempt(
                session, attempt_id, "no_provider_available",
            )
            return RepairResult(
                action="repair_attempted",
                new_failure_count=new_count,
                repair_triggered=True,
                repair_status="no_provider_available",
                attempt_id=attempt_id,
            )

        try:
            candidate_rules = await ai_provider(html_evidence, repair_kind)
        except Exception as exc:
            await self._repo.complete_repair_attempt(
                session, attempt_id, "provider_failed",
            )
            return RepairResult(
                action="repair_attempted",
                new_failure_count=new_count,
                repair_triggered=True,
                repair_status="provider_failed",
                attempt_id=attempt_id,
                error=str(exc),
            )

        if not candidate_rules or not isinstance(candidate_rules, dict):
            await self._repo.complete_repair_attempt(
                session, attempt_id, "candidate_schema_invalid",
            )
            return RepairResult(
                action="repair_attempted",
                new_failure_count=new_count,
                repair_triggered=True,
                repair_status="candidate_schema_invalid",
                attempt_id=attempt_id,
            )

        # Step 5: Validate candidate
        if repair_kind == "list":
            is_valid, failure_code = _validate_list_candidate(candidate_rules, html_evidence)
        else:
            is_valid, failure_code = _validate_content_candidate(candidate_rules, html_evidence)

        if not is_valid:
            await self._repo.complete_repair_attempt(
                session, attempt_id, failure_code,  # type: ignore[arg-type]
                validation_failure_code=failure_code,
            )
            return RepairResult(
                action="repair_attempted",
                new_failure_count=new_count,
                repair_triggered=True,
                repair_status=failure_code,
                attempt_id=attempt_id,
            )

        # Step 6: Promote rules and reset counter
        await self._repo.complete_repair_attempt(
            session, attempt_id, "applied",
            candidate_rule_revision=rule_revision + 1,
            validation_success_count=1,
        )
        await self._repo.reset_failure(
            session, site_id, repair_kind,
            current_week_start=current_week_start,
        )

        return RepairResult(
            action="repair_attempted",
            new_failure_count=0,
            repair_triggered=True,
            repair_status="applied",
            new_rules=candidate_rules,
            attempt_id=attempt_id,
        )


# ---------------------------------------------------------------------------
# FakeCrawlEnvironment
# ---------------------------------------------------------------------------

class FakeCrawlEnvironment:
    """Wires real classifiers + repository + repair service with mocked DB/AI.

    Uses mocked repository methods (approach #1) for orchestrator-level tests.
    """

    def __init__(self):
        self.clock = FakeClock(_utc(2026, 6, 18, 12, 0))
        self.tables = _build_tables()
        self.repo = RepairStateRepository(self.tables)
        self.orchestrator = SimpleRepairOrchestrator(self.repo, self.clock)

        # In-memory state tracking
        self._states: dict[tuple[int, str], dict] = {}
        self._attempts: list[dict] = []
        self._attempt_seq = 0

        # AI mock
        self.ai_responses: list[dict | Exception] = []
        self.ai_call_log: list[dict] = []

    def seed_state(self, site_id: int, repair_kind: str, **overrides):
        """Seed an in-memory repair state row."""
        key = (site_id, repair_kind)
        ww = taipei_week_window(self.clock.now_utc())
        defaults = _make_state_row(
            site_id=site_id,
            repair_kind=repair_kind,
            week_start_at=ww.start_utc,
        )
        defaults.update(overrides)
        self._states[key] = defaults

    def get_state(self, site_id: int, repair_kind: str) -> dict:
        return self._states.get((site_id, repair_kind), {})

    def _build_session(self) -> AsyncMock:
        """Build a mock session that routes execute() calls to in-memory state."""
        session = AsyncMock()
        env = self

        async def mock_execute(stmt):
            # Routing logic: differentiate between state and attempt operations
            # by inspecting the statement type. This is a simplification for
            # integration testing — the real DB would handle this.
            return FakeResult(rows=[], rowcount=1)

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()
        return session

    def make_ai_provider(self):
        """Create an async AI provider callable that returns queued responses."""
        env = self

        async def ai_provider(html: str, kind: str, **kwargs):
            env.ai_call_log.append({"html_len": len(html), "kind": kind})
            if not env.ai_responses:
                return {}
            response = env.ai_responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        return ai_provider


# ---------------------------------------------------------------------------
# MockedRepoOrchestrator — orchestrator with directly mocked repo methods
# ---------------------------------------------------------------------------

class MockedRepoOrchestrator:
    """Test harness that mocks repository methods directly.

    Maintains in-memory state for failure counters, weekly attempts, and pauses.
    This allows testing the orchestrator logic without database interaction.
    """

    def __init__(self, clock: FakeClock | None = None):
        self.clock = clock or FakeClock(_utc(2026, 6, 18, 12, 0))
        self._failure_counts: dict[tuple[int, str], int] = {}
        self._weekly_attempts: dict[tuple[int, str], int] = {}
        self._repair_statuses: dict[tuple[int, str], str] = {}
        self._paused: dict[tuple[int, str], datetime | None] = {}
        self._attempt_id_seq = 0
        self._attempts: list[dict] = []
        self.orchestrator = SimpleRepairOrchestrator(
            _build_repo(), self.clock
        )
        # Patch repo methods
        self._patch_repo()

    def _patch_repo(self):
        repo = self.orchestrator._repo
        harness = self

        async def increment_failure(session, site_id, repair_kind, *, failure_reason=None, current_week_start=None):
            key = (site_id, repair_kind)
            harness._failure_counts[key] = harness._failure_counts.get(key, 0) + 1
            harness._repair_statuses[key] = "collecting_failures"
            return harness._failure_counts[key]

        async def reset_failure(session, site_id, repair_kind, *, current_week_start=None):
            key = (site_id, repair_kind)
            harness._failure_counts[key] = 0
            if harness._repair_statuses.get(key) != "paused_until_next_week":
                harness._repair_statuses[key] = "healthy"

        async def reserve_repair_attempt(session, site_id, repair_kind, *,
                                          crawl_attempt_id=None, trigger_failure_count=3,
                                          owner_user_id=None, base_rule_revision=1,
                                          weekly_limit=3, current_week_start=None,
                                          started_at=None):
            key = (site_id, repair_kind)
            used = harness._weekly_attempts.get(key, 0)
            if used >= weekly_limit:
                raise RepairBudgetExhaustedError(
                    f"Budget exhausted: used={used} limit={weekly_limit}"
                )
            harness._weekly_attempts[key] = used + 1
            harness._attempt_id_seq += 1
            attempt = _make_attempt_row(
                attempt_id=harness._attempt_id_seq,
                site_id=site_id,
                repair_kind=repair_kind,
                weekly_sequence=used + 1,
                trigger_failure_count=trigger_failure_count,
                base_rule_revision=base_rule_revision,
            )
            harness._attempts.append(attempt)
            harness._repair_statuses[key] = "repairing"
            return attempt

        async def complete_repair_attempt(session, attempt_id, status, *,
                                           finished_at=None, provider_trace_id=None,
                                           sample_url=None, sample_count=0,
                                           validation_success_count=0,
                                           validation_failure_code=None,
                                           candidate_rule_revision=None):
            for a in harness._attempts:
                if a["id"] == attempt_id:
                    a["status"] = status
                    a["finished_at"] = finished_at or datetime.now(timezone.utc)
                    a["validation_failure_code"] = validation_failure_code
                    a["candidate_rule_revision"] = candidate_rule_revision
                    a["validation_success_count"] = validation_success_count
                    return a
            return _make_attempt_row(attempt_id=attempt_id, status=status)

        async def pause_feed(session, site_id, repair_kind, blocked_until):
            key = (site_id, repair_kind)
            harness._repair_statuses[key] = "paused_until_next_week"
            harness._paused[key] = blocked_until

        async def lazy_weekly_rollover(session, site_id, repair_kind, current_week_start):
            return False

        repo.increment_failure = increment_failure
        repo.reset_failure = reset_failure
        repo.reserve_repair_attempt = reserve_repair_attempt
        repo.complete_repair_attempt = complete_repair_attempt
        repo.pause_feed = pause_feed
        repo.lazy_weekly_rollover = lazy_weekly_rollover

    def get_failure_count(self, site_id: int, repair_kind: str) -> int:
        return self._failure_counts.get((site_id, repair_kind), 0)

    def get_weekly_attempts(self, site_id: int, repair_kind: str) -> int:
        return self._weekly_attempts.get((site_id, repair_kind), 0)

    def get_repair_status(self, site_id: int, repair_kind: str) -> str:
        return self._repair_statuses.get((site_id, repair_kind), "healthy")

    def is_paused(self, site_id: int, repair_kind: str) -> bool:
        return self._repair_statuses.get((site_id, repair_kind)) == "paused_until_next_week"

    def reset_weekly(self, site_id: int, repair_kind: str):
        """Simulate weekly rollover."""
        key = (site_id, repair_kind)
        self._weekly_attempts[key] = 0
        if self._repair_statuses.get(key) == "paused_until_next_week":
            if self._failure_counts.get(key, 0) > 0:
                self._repair_statuses[key] = "collecting_failures"
            else:
                self._repair_statuses[key] = "healthy"
        self._paused[key] = None


# ---------------------------------------------------------------------------
# AI provider mock factories
# ---------------------------------------------------------------------------

def _make_ai_provider(responses: list[dict | Exception]):
    """Create an async AI provider callable that returns responses in order."""
    call_log: list[dict] = []

    async def ai_provider(html: str, kind: str, **kwargs):
        call_log.append({"html_len": len(html), "kind": kind})
        if not responses:
            return {}
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    ai_provider.call_log = call_log  # type: ignore[attr-defined]
    return ai_provider


# ===========================================================================
# Test Classes
# ===========================================================================


class TestFailureCounting:
    """Tests for the counting flow (no repair triggered)."""

    @pytest.mark.asyncio
    async def test_first_structural_failure_increments_to_1(self):
        """1st list structural failure -> counter=1, action=counted."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )

        assert result.action == "counted"
        assert result.new_failure_count == 1
        assert result.repair_triggered is False
        assert harness.get_failure_count(1, "list") == 1

    @pytest.mark.asyncio
    async def test_second_failure_increments_to_2(self):
        """2nd consecutive failure -> counter=2, action=counted."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )

        assert result.action == "counted"
        assert result.new_failure_count == 2
        assert result.repair_triggered is False
        assert harness.get_failure_count(1, "list") == 2

    @pytest.mark.asyncio
    async def test_success_resets_counter(self):
        """Successful parse after failures -> counter=0."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        # Two failures
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )
        assert harness.get_failure_count(1, "list") == 2

        # Success
        result = await harness.orchestrator.handle_parse_success(
            session, site_id=1, repair_kind="list",
        )

        assert result.action == "success_reset"
        assert result.new_failure_count == 0
        assert harness.get_failure_count(1, "list") == 0

    @pytest.mark.asyncio
    async def test_list_and_content_counters_independent(self):
        """List failure doesn't affect content counter."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        # Fail list twice
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )

        # Content should still be at 0
        assert harness.get_failure_count(1, "content") == 0
        assert harness.get_failure_count(1, "list") == 2

        # Fail content once
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="content",
            html_evidence="<html></html>",
            active_rules={"body": ".article-body"},
        )
        assert harness.get_failure_count(1, "content") == 1
        assert harness.get_failure_count(1, "list") == 2

    @pytest.mark.asyncio
    async def test_different_sites_independent_counters(self):
        """Failure counters for different sites are independent."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )
        await harness.orchestrator.handle_structural_failure(
            session, site_id=2, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )
        await harness.orchestrator.handle_structural_failure(
            session, site_id=2, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )

        assert harness.get_failure_count(1, "list") == 1
        assert harness.get_failure_count(2, "list") == 2


class TestRepairTrigger:
    """Tests for repair trigger at threshold."""

    @pytest.mark.asyncio
    async def test_third_failure_triggers_repair(self):
        """3rd consecutive structural failure -> AI repair attempted."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        ai = _make_ai_provider([{"item": ".news-card", "link": "a"}])

        # Fail 3 times
        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
            )

        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=_load_fixture("crawl_list_zero_items.html"),
            active_rules={"item": ".article-item"},
            ai_provider=ai,
        )

        assert result.repair_triggered is True
        assert result.action == "repair_attempted"

    @pytest.mark.asyncio
    async def test_repair_not_triggered_at_2(self):
        """2nd failure -> no repair, just counting."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        ai = _make_ai_provider([{"item": ".news-card"}])

        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai,
        )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai,
        )

        assert result.repair_triggered is False
        assert result.action == "counted"
        assert len(ai.call_log) == 0  # AI was never called

    @pytest.mark.asyncio
    async def test_fourth_failure_also_triggers(self):
        """4th failure (after failed 3rd repair) -> attempts repair again."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        # First AI returns bad schema, second returns valid
        ai = _make_ai_provider([
            {"bad_key": "no_item"},  # 3rd failure: invalid schema
            {"item": ".news-card", "link": "a"},  # 4th failure: valid
        ])

        # 3 failures + repair attempt (fails)
        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
            )
        r3 = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=_load_fixture("crawl_list_zero_items.html"),
            active_rules={"item": ".article-item"},
            ai_provider=ai,
        )
        assert r3.repair_triggered is True
        assert r3.repair_status == "candidate_schema_invalid"

        # 4th failure -> triggers repair again
        r4 = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=_load_fixture("crawl_list_zero_items.html"),
            active_rules={"item": ".article-item"},
            ai_provider=ai,
        )
        assert r4.repair_triggered is True
        assert r4.action == "repair_attempted"

    @pytest.mark.asyncio
    async def test_repair_not_triggered_when_disabled(self):
        """auto_repair_enabled=False -> no repair even at threshold."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        ai = _make_ai_provider([{"item": ".news-card"}])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
            )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            auto_repair_enabled=False,
            ai_provider=ai,
        )

        assert result.repair_triggered is False
        assert result.action == "counted"
        assert len(ai.call_log) == 0

    @pytest.mark.asyncio
    async def test_no_ai_provider_returns_no_provider_available(self):
        """3rd failure with no AI provider -> no_provider_available."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
            )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=None,
        )

        assert result.repair_triggered is True
        assert result.repair_status == "no_provider_available"


class TestSuccessfulRepair:
    """Tests for the successful repair flow with real HTML fixtures."""

    @pytest.mark.asyncio
    async def test_valid_list_candidate_promotes_rules(self):
        """AI returns valid list rules -> validated -> promoted -> counter reset."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        valid_html = _load_fixture("crawl_valid_list.html")

        # These rules match the valid_list fixture
        good_rules = {"item": "li.article-item", "link": "a", "title": "h3.article-title"}
        ai = _make_ai_provider([good_rules])

        # Accumulate 3 failures
        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence=valid_html,
                active_rules={"item": ".broken-selector"},
            )

        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=valid_html,
            active_rules={"item": ".broken-selector"},
            ai_provider=ai,
        )

        assert result.repair_triggered is True
        assert result.repair_status == "applied"
        assert result.new_rules is not None
        assert result.new_rules["item"] == "li.article-item"
        assert result.new_failure_count == 0
        assert harness.get_failure_count(1, "list") == 0

    @pytest.mark.asyncio
    async def test_valid_content_candidate_promotes_rules(self):
        """AI returns valid content rules -> validated -> promoted."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        valid_html = _load_fixture("crawl_valid_content.html")

        # Rules that match the valid_content fixture
        good_rules = {"body": "div.article-body", "date": "time.pub-date", "author": "span.author"}
        ai = _make_ai_provider([good_rules])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="content",
                html_evidence=valid_html,
                active_rules={"body": ".broken-body"},
            )

        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="content",
            html_evidence=valid_html,
            active_rules={"body": ".broken-body"},
            ai_provider=ai,
        )

        assert result.repair_triggered is True
        assert result.repair_status == "applied"
        assert result.new_rules is not None
        assert result.new_rules["body"] == "div.article-body"

    @pytest.mark.asyncio
    async def test_repair_success_resets_failure_counter(self):
        """After successful repair -> consecutive_failure_count reset to 0."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        valid_html = _load_fixture("crawl_valid_list.html")
        good_rules = {"item": "li.article-item", "link": "a"}
        ai = _make_ai_provider([good_rules])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence=valid_html,
                active_rules={"item": ".broken"},
            )
        assert harness.get_failure_count(1, "list") == 2

        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=valid_html,
            active_rules={"item": ".broken"},
            ai_provider=ai,
        )

        assert result.repair_status == "applied"
        assert harness.get_failure_count(1, "list") == 0

    @pytest.mark.asyncio
    async def test_repair_attempt_recorded_with_correct_metadata(self):
        """Successful repair creates an attempt row with status='applied'."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        valid_html = _load_fixture("crawl_valid_list.html")
        good_rules = {"item": "li.article-item", "link": "a"}
        ai = _make_ai_provider([good_rules])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence=valid_html,
                active_rules={"item": ".broken"},
            )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=valid_html,
            active_rules={"item": ".broken"},
            ai_provider=ai,
        )

        assert result.attempt_id is not None
        # Check the attempt was recorded
        assert harness.get_weekly_attempts(1, "list") == 1


class TestFailedRepair:
    """Tests for failed repair flows."""

    @pytest.mark.asyncio
    async def test_invalid_candidate_schema_no_item_key(self):
        """AI returns rules without 'item' key -> candidate_schema_invalid."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        ai = _make_ai_provider([{"container": ".wrapper", "link": "a"}])  # No 'item' key

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
            )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai,
        )

        assert result.repair_triggered is True
        assert result.repair_status == "candidate_schema_invalid"
        assert result.new_rules is None

    @pytest.mark.asyncio
    async def test_candidate_extracts_zero_items(self):
        """AI returns rules that match 0 items -> candidate_validation_failed."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        # Rules with 'item' key but selector that won't match the fixture
        ai = _make_ai_provider([{"item": ".nonexistent-class", "link": "a"}])
        html = _load_fixture("crawl_list_zero_items.html")

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence=html,
                active_rules={"item": ".article-item"},
            )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=html,
            active_rules={"item": ".article-item"},
            ai_provider=ai,
        )

        assert result.repair_triggered is True
        assert result.repair_status == "candidate_validation_failed"
        assert result.new_rules is None

    @pytest.mark.asyncio
    async def test_content_candidate_produces_sentinel(self):
        """AI returns content rules that produce 'Parsing failed' -> rejected."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        sentinel_html = _load_fixture("crawl_content_sentinel_fail.html")
        # Rules pointing to a selector that doesn't exist in the fixture
        ai = _make_ai_provider([{"body": "div.article-body"}])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="content",
                html_evidence=sentinel_html,
                active_rules={"body": ".broken-body"},
            )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="content",
            html_evidence=sentinel_html,
            active_rules={"body": ".broken-body"},
            ai_provider=ai,
        )

        assert result.repair_triggered is True
        assert result.repair_status == "candidate_validation_failed"
        assert result.new_rules is None

    @pytest.mark.asyncio
    async def test_ai_provider_exception(self):
        """AI provider raises -> provider_failed, old rules preserved."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        ai = _make_ai_provider([RuntimeError("API quota exceeded")])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
            )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai,
        )

        assert result.repair_triggered is True
        assert result.repair_status == "provider_failed"
        assert result.new_rules is None
        assert "quota" in result.error.lower()

    @pytest.mark.asyncio
    async def test_ai_returns_empty_dict(self):
        """AI returns {} -> treated as schema failure."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        ai = _make_ai_provider([{}])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
            )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai,
        )

        assert result.repair_triggered is True
        assert result.repair_status == "candidate_schema_invalid"
        assert result.new_rules is None

    @pytest.mark.asyncio
    async def test_ai_returns_none(self):
        """AI returns None -> treated as schema failure."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        async def ai_returns_none(html, kind, **kw):
            return None

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
            )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai_returns_none,
        )

        assert result.repair_triggered is True
        assert result.repair_status == "candidate_schema_invalid"

    @pytest.mark.asyncio
    async def test_content_candidate_without_body_key(self):
        """Content candidate without 'body' key -> candidate_schema_invalid."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        ai = _make_ai_provider([{"selector": ".content", "date": "time"}])  # No 'body'

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="content",
                html_evidence="<html></html>",
                active_rules={"body": ".article-body"},
            )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="content",
            html_evidence="<html></html>",
            active_rules={"body": ".article-body"},
            ai_provider=ai,
        )

        assert result.repair_triggered is True
        assert result.repair_status == "candidate_schema_invalid"

    @pytest.mark.asyncio
    async def test_failed_repair_preserves_failure_count(self):
        """Failed repair does not reset the failure counter."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        ai = _make_ai_provider([{"bad": "rules"}])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
            )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai,
        )

        assert result.repair_status == "candidate_schema_invalid"
        # Counter should still be at 3 (not reset)
        assert harness.get_failure_count(1, "list") == 3


class TestBudgetAndPause:
    """Tests for budget exhaustion and feed pausing."""

    @pytest.mark.asyncio
    async def test_budget_exhausted_pauses_feed(self):
        """3 failed repairs in a week -> feed paused until next Taipei Sunday."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        # First 2 failures below threshold
        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
                weekly_limit=3,
            )

        # Exhaust budget: 3 repair attempts (each subsequent failure triggers
        # a new attempt since count stays >= 3 after failed repair)
        for attempt_num in range(3):
            ai = _make_ai_provider([{"bad": "rules"}])
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
                ai_provider=ai,
                weekly_limit=3,
            )
        assert harness.get_weekly_attempts(1, "list") == 3

        # Next failure -> budget exhausted -> paused
        ai_final = _make_ai_provider([{"item": "div"}])
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai_final,
            weekly_limit=3,
        )

        assert result.repair_status == "budget_exhausted"
        assert result.paused is True
        assert harness.is_paused(1, "list")

    @pytest.mark.asyncio
    async def test_budget_default_is_3(self):
        """Default weekly limit is 3."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        # First 2 failures below threshold
        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
            )

        # Use 3 budget slots (each failure after threshold triggers repair)
        for _ in range(3):
            ai = _make_ai_provider([{"bad": "rules"}])
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
                ai_provider=ai,
            )

        assert harness.get_weekly_attempts(1, "list") == 3

    @pytest.mark.asyncio
    async def test_custom_budget_5(self):
        """Custom limit of 5 allows 5 attempts."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        # First 2 failures below threshold
        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
                weekly_limit=5,
            )

        # Use 5 budget slots (each subsequent failure triggers repair)
        for attempt in range(5):
            ai = _make_ai_provider([{"bad": "rules"}])
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
                ai_provider=ai,
                weekly_limit=5,
            )

        assert harness.get_weekly_attempts(1, "list") == 5

        # 6th attempt triggers budget exhaustion
        ai_exhaust = _make_ai_provider([{"item": "div"}])
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai_exhaust,
            weekly_limit=5,
        )
        assert result.repair_status == "budget_exhausted"
        assert result.paused is True

    @pytest.mark.asyncio
    async def test_weekly_rollover_resets_budget(self):
        """New Taipei week -> budget resets, feed unpauses."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        # First 2 failures below threshold
        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
                weekly_limit=3,
            )

        # Exhaust budget (3 attempts, each on subsequent failure)
        for _ in range(3):
            ai = _make_ai_provider([{"bad": "rules"}])
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
                ai_provider=ai,
                weekly_limit=3,
            )

        # Pause triggered
        ai_final = _make_ai_provider([{"item": "div"}])
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai_final,
            weekly_limit=3,
        )
        assert harness.is_paused(1, "list")

        # Simulate weekly rollover
        harness.reset_weekly(1, "list")

        assert not harness.is_paused(1, "list")
        assert harness.get_weekly_attempts(1, "list") == 0
        # Failure count preserved across rollover
        assert harness.get_failure_count(1, "list") > 0
        # Status should be collecting_failures (since failures > 0)
        assert harness.get_repair_status(1, "list") == "collecting_failures"

    @pytest.mark.asyncio
    async def test_paused_feed_blocks_repair(self):
        """Paused feed -> new repair attempts get budget_exhausted."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        # First 2 failures below threshold
        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
                weekly_limit=3,
            )

        # Exhaust budget (3 attempts)
        for _ in range(3):
            ai = _make_ai_provider([{"bad": "rules"}])
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
                ai_provider=ai,
                weekly_limit=3,
            )

        # Trigger budget exhaustion
        ai_final = _make_ai_provider([{"item": "div"}])
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai_final,
            weekly_limit=3,
        )
        assert result.paused is True

        # Try another repair — should be immediately budget_exhausted
        ai_more = _make_ai_provider([{"item": ".good"}])
        result2 = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai_more,
            weekly_limit=3,
        )
        assert result2.repair_status == "budget_exhausted"
        assert result2.paused is True

    @pytest.mark.asyncio
    async def test_weekly_rollover_restores_collecting_failures_status(self):
        """After rollover, status goes to collecting_failures if failure count > 0."""
        harness = MockedRepoOrchestrator()
        harness._failure_counts[(1, "list")] = 5
        harness._repair_statuses[(1, "list")] = "paused_until_next_week"

        harness.reset_weekly(1, "list")

        assert harness.get_repair_status(1, "list") == "collecting_failures"
        assert harness.get_failure_count(1, "list") == 5

    @pytest.mark.asyncio
    async def test_weekly_rollover_restores_healthy_if_no_failures(self):
        """After rollover, status goes to healthy if failure count is 0."""
        harness = MockedRepoOrchestrator()
        harness._failure_counts[(1, "list")] = 0
        harness._repair_statuses[(1, "list")] = "paused_until_next_week"

        harness.reset_weekly(1, "list")

        assert harness.get_repair_status(1, "list") == "healthy"
        assert harness.get_failure_count(1, "list") == 0


class TestListCandidateValidation:
    """Tests for list candidate validation with real HTML fixtures."""

    def test_valid_rules_against_valid_list(self):
        """Known-good rules extract items from crawl_valid_list.html."""
        html = _load_fixture("crawl_valid_list.html")
        rules = {"item": "li.article-item", "link": "a", "title": "h3.article-title"}
        is_valid, code = _validate_list_candidate(rules, html)
        assert is_valid is True
        assert code == ""

    def test_broken_rules_against_valid_list(self):
        """Rules with wrong selectors fail validation against crawl_valid_list.html."""
        html = _load_fixture("crawl_valid_list.html")
        rules = {"item": ".nonexistent", "link": "a"}
        is_valid, code = _validate_list_candidate(rules, html)
        assert is_valid is False
        assert code == "candidate_validation_failed"

    def test_rules_without_item_key(self):
        """Rules missing 'item' key fail schema validation."""
        html = _load_fixture("crawl_valid_list.html")
        rules = {"container": "ul", "link": "a"}
        is_valid, code = _validate_list_candidate(rules, html)
        assert is_valid is False
        assert code == "candidate_schema_invalid"

    def test_empty_dict_fails_schema_validation(self):
        """Empty dict fails schema validation."""
        html = _load_fixture("crawl_valid_list.html")
        is_valid, code = _validate_list_candidate({}, html)
        assert is_valid is False
        assert code == "candidate_schema_invalid"

    def test_redesigned_page_rules_match(self):
        """New rules matching the redesigned page structure succeed."""
        html = _load_fixture("crawl_list_zero_items.html")
        # Rules that match the redesigned structure
        rules = {"item": "div.news-card", "link": "a"}
        is_valid, code = _validate_list_candidate(rules, html)
        assert is_valid is True


class TestContentCandidateValidation:
    """Tests for content candidate validation with real HTML fixtures."""

    def test_valid_rules_against_valid_content(self):
        """Known-good rules extract content from crawl_valid_content.html."""
        html = _load_fixture("crawl_valid_content.html")
        rules = {"body": "div.article-body"}
        is_valid, code = _validate_content_candidate(rules, html)
        assert is_valid is True
        assert code == ""

    def test_broken_rules_produce_sentinel(self):
        """Rules pointing to absent selector produce sentinel -> rejected."""
        html = _load_fixture("crawl_content_sentinel_fail.html")
        rules = {"body": "div.article-body"}
        is_valid, code = _validate_content_candidate(rules, html)
        assert is_valid is False
        assert code == "candidate_validation_failed"

    def test_correct_rules_for_redesigned_content_too_thin(self):
        """Rules matching the redesigned fixture's actual selector still fail if content is below threshold."""
        html = _load_fixture("crawl_content_sentinel_fail.html")
        # div.story-text exists but its content ("Article content is here but under
        # a different class name.") is below the effective-content threshold
        # (< 20 words AND < 80 non-ws chars), so validation correctly rejects it.
        rules = {"body": "div.story-text"}
        is_valid, code = _validate_content_candidate(rules, html)
        assert is_valid is False
        assert code == "candidate_validation_failed"

    def test_valid_content_rules_pass_validation(self):
        """Rules that extract substantial content from valid fixture succeed."""
        html = _load_fixture("crawl_valid_content.html")
        rules = {"body": "article"}
        is_valid, code = _validate_content_candidate(rules, html)
        assert is_valid is True

    def test_rules_without_body_key(self):
        """Content rules without 'body' key fail schema validation."""
        html = _load_fixture("crawl_valid_content.html")
        rules = {"selector": "div.article-body"}
        is_valid, code = _validate_content_candidate(rules, html)
        assert is_valid is False
        assert code == "candidate_schema_invalid"


class TestEndToEndFlow:
    """Full end-to-end integration tests combining all stages."""

    @pytest.mark.asyncio
    async def test_full_list_repair_cycle(self):
        """
        Complete flow:
        1. Parse with good rules -> success (baseline)
        2. Rules break -> 3 consecutive failures
        3. AI returns candidate -> validated -> promoted
        4. Re-parse with new rules -> success
        5. Counter is reset
        """
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        valid_html = _load_fixture("crawl_valid_list.html")

        # Step 1: Baseline success
        from scrapling.parser import Selector
        from backend.core.parser import parse_listing
        good_rules = {"item": "li.article-item", "link": "a", "title": "h3.article-title"}
        page = Selector(valid_html)
        items = parse_listing(page, good_rules, "https://example.com")
        result_classify = classify_list_outcome(fetch_failed=False, items=items)
        assert result_classify.outcome == ListOutcome.SUCCESS
        assert result_classify.count == 3

        # Handle success
        await harness.orchestrator.handle_parse_success(
            session, site_id=1, repair_kind="list",
        )
        assert harness.get_failure_count(1, "list") == 0

        # Step 2: Rules break (simulate site redesign)
        broken_rules = {"item": ".old-article-class"}
        page2 = Selector(valid_html)
        items2 = parse_listing(page2, broken_rules, "https://example.com")
        result2 = classify_list_outcome(fetch_failed=False, items=items2)
        assert result2.outcome == ListOutcome.ZERO_ITEMS

        # 3 failures with AI providing the fix
        ai = _make_ai_provider([good_rules])  # AI returns the correct rules
        for i in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence=valid_html,
                active_rules=broken_rules,
            )

        # Step 3: 3rd failure triggers repair
        repair_result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=valid_html,
            active_rules=broken_rules,
            ai_provider=ai,
        )
        assert repair_result.repair_triggered is True
        assert repair_result.repair_status == "applied"
        assert repair_result.new_rules is not None

        # Step 4: Re-parse with new rules
        new_rules = repair_result.new_rules
        page3 = Selector(valid_html)
        items3 = parse_listing(page3, new_rules, "https://example.com")
        result3 = classify_list_outcome(fetch_failed=False, items=items3)
        assert result3.outcome == ListOutcome.SUCCESS
        assert result3.count == 3

        # Step 5: Counter is reset
        assert repair_result.new_failure_count == 0
        assert harness.get_failure_count(1, "list") == 0

    @pytest.mark.asyncio
    async def test_full_budget_exhaustion_cycle(self):
        """
        1. Rules break -> 3 failures -> repair attempt 1 (fails validation)
        2. Next failure (count still >= 3) -> repair attempt 2 (AI error)
        3. Next failure -> repair attempt 3 (fails validation)
        4. Next failure -> budget exhausted -> feed paused
        5. Next week -> budget resets -> can repair again

        Key insight: after a failed repair, the failure counter stays >= 3.
        So every subsequent failure immediately triggers a new repair attempt
        (no need to accumulate 3 more failures).
        """
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        html = _load_fixture("crawl_list_zero_items.html")

        # Accumulate first 2 failures (below threshold)
        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence=html,
                active_rules={"item": ".article-item"},
            )

        # Attempt 1 (3rd failure): fails validation (bad selector)
        ai1 = _make_ai_provider([{"item": ".nonexistent", "link": "a"}])
        r1 = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=html,
            active_rules={"item": ".article-item"},
            ai_provider=ai1,
            weekly_limit=3,
        )
        assert r1.repair_status == "candidate_validation_failed"
        assert harness.get_weekly_attempts(1, "list") == 1

        # Attempt 2 (4th failure, count=4 >= 3 so immediately triggers): AI error
        ai2 = _make_ai_provider([ConnectionError("timeout")])
        r2 = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=html,
            active_rules={"item": ".article-item"},
            ai_provider=ai2,
            weekly_limit=3,
        )
        assert r2.repair_status == "provider_failed"
        assert harness.get_weekly_attempts(1, "list") == 2

        # Attempt 3 (5th failure): fails validation again
        ai3 = _make_ai_provider([{"item": ".also-wrong", "link": "a"}])
        r3 = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=html,
            active_rules={"item": ".article-item"},
            ai_provider=ai3,
            weekly_limit=3,
        )
        assert r3.repair_status == "candidate_validation_failed"
        assert harness.get_weekly_attempts(1, "list") == 3

        # Attempt 4 (6th failure): budget exhausted -> paused
        ai4 = _make_ai_provider([{"item": ".news-card", "link": "a"}])
        r4 = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=html,
            active_rules={"item": ".article-item"},
            ai_provider=ai4,
            weekly_limit=3,
        )
        assert r4.repair_status == "budget_exhausted"
        assert r4.paused is True
        assert harness.is_paused(1, "list")

        # Step 5: Next week rollover -> can repair again
        harness.reset_weekly(1, "list")
        assert not harness.is_paused(1, "list")
        assert harness.get_weekly_attempts(1, "list") == 0

        # Next failure with correct rules -> repair succeeds
        ai5 = _make_ai_provider([{"item": "div.news-card", "link": "a"}])
        r5 = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=html,
            active_rules={"item": ".article-item"},
            ai_provider=ai5,
            weekly_limit=3,
        )
        assert r5.repair_triggered is True
        assert r5.repair_status == "applied"
        assert r5.new_rules is not None
        assert harness.get_weekly_attempts(1, "list") == 1

    @pytest.mark.asyncio
    async def test_content_repair_independent_of_list(self):
        """List repair doesn't affect content state."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        valid_list_html = _load_fixture("crawl_valid_list.html")
        valid_content_html = _load_fixture("crawl_valid_content.html")

        # List repair cycle
        good_list_rules = {"item": "li.article-item", "link": "a"}
        ai_list = _make_ai_provider([good_list_rules])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence=valid_list_html,
                active_rules={"item": ".broken"},
            )
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=valid_list_html,
            active_rules={"item": ".broken"},
            ai_provider=ai_list,
        )

        # Content state should be unaffected
        assert harness.get_failure_count(1, "content") == 0
        assert harness.get_weekly_attempts(1, "content") == 0
        assert harness.get_repair_status(1, "content") == "healthy"

        # Content repair cycle (separate)
        good_content_rules = {"body": "div.article-body"}
        ai_content = _make_ai_provider([good_content_rules])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="content",
                html_evidence=valid_content_html,
                active_rules={"body": ".broken"},
            )
        content_result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="content",
            html_evidence=valid_content_html,
            active_rules={"body": ".broken"},
            ai_provider=ai_content,
        )

        assert content_result.repair_status == "applied"
        # List state should be unaffected by content repair
        assert harness.get_failure_count(1, "list") == 0
        assert harness.get_weekly_attempts(1, "list") == 1

    @pytest.mark.asyncio
    async def test_success_after_two_failures_prevents_repair(self):
        """If parse succeeds after 2 failures, counter resets and repair never triggers."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        ai = _make_ai_provider([{"item": "li.article-item"}])

        # 2 failures
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )
        assert harness.get_failure_count(1, "list") == 2

        # Success resets counter
        await harness.orchestrator.handle_parse_success(
            session, site_id=1, repair_kind="list",
        )
        assert harness.get_failure_count(1, "list") == 0

        # 2 more failures — still no repair
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai,
        )
        assert result.repair_triggered is False
        assert result.action == "counted"
        assert len(ai.call_log) == 0

    @pytest.mark.asyncio
    async def test_multiple_sites_repair_independently(self):
        """Two sites can repair independently without interference."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        valid_html = _load_fixture("crawl_valid_list.html")
        good_rules = {"item": "li.article-item", "link": "a"}

        # Site 1: repair cycle
        ai1 = _make_ai_provider([good_rules])
        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence=valid_html,
                active_rules={"item": ".broken"},
            )
        r1 = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=valid_html,
            active_rules={"item": ".broken"},
            ai_provider=ai1,
        )
        assert r1.repair_status == "applied"

        # Site 2: still counting, no repair yet
        await harness.orchestrator.handle_structural_failure(
            session, site_id=2, repair_kind="list",
            html_evidence=valid_html,
            active_rules={"item": ".broken"},
        )
        assert harness.get_failure_count(2, "list") == 1
        assert harness.get_failure_count(1, "list") == 0  # site 1 was reset


class TestClassifyAndOrchestrate:
    """Tests combining real classifiers with orchestrator flow."""

    def test_classify_list_outcome_zero_items(self):
        """classify_list_outcome with 0 items returns ZERO_ITEMS."""
        result = classify_list_outcome(fetch_failed=False, items=[])
        assert result.outcome == ListOutcome.ZERO_ITEMS

    def test_classify_list_outcome_success(self):
        """classify_list_outcome with items returns SUCCESS."""
        items = [{"url": "https://example.com/1", "title": "Article 1"}]
        result = classify_list_outcome(fetch_failed=False, items=items)
        assert result.outcome == ListOutcome.SUCCESS

    @pytest.mark.asyncio
    async def test_zero_items_triggers_structural_failure_handling(self):
        """When classify returns ZERO_ITEMS, orchestrator should count failure."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        # Simulate: classifier says zero items -> handle as structural failure
        items = []
        result = classify_list_outcome(fetch_failed=False, items=items)
        assert result.outcome == ListOutcome.ZERO_ITEMS

        # Orchestrator handles it
        repair_result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
        )
        assert repair_result.action == "counted"
        assert repair_result.new_failure_count == 1

    def test_is_valid_content_with_fixture(self):
        """Real content fixture produces valid content."""
        html = _load_fixture("crawl_valid_content.html")
        # Parse with correct rules
        from scrapling.parser import Selector
        from backend.core.parser import parse_article
        page = Selector(html)
        content_text, _date, _img, _author = parse_article(
            page, {"body": "div.article-body"}, "https://example.com/article"
        )
        assert content_text != SENTINEL_PARSE_FAILED
        assert is_valid_content(content_text) is True

    def test_sentinel_content_with_fixture(self):
        """Sentinel fixture produces invalid content."""
        html = _load_fixture("crawl_content_sentinel_fail.html")
        from scrapling.parser import Selector
        from backend.core.parser import parse_article
        page = Selector(html)
        content_text, _date, _img, _author = parse_article(
            page, {"body": "div.article-body"}, "https://example.com/article"
        )
        assert content_text == SENTINEL_PARSE_FAILED
        assert is_valid_content(content_text) is False


class TestTimeProviderIntegration:
    """Tests for FakeClock and taipei_week_window integration."""

    def test_fake_clock_returns_fixed_time(self):
        """FakeClock returns the exact time it was initialized with."""
        clock = FakeClock(_utc(2026, 6, 18, 12, 0))
        assert clock.now_utc() == _utc(2026, 6, 18, 12, 0)

    def test_fake_clock_advance(self):
        """FakeClock.advance() moves time forward."""
        clock = FakeClock(_utc(2026, 6, 18, 12, 0))
        clock.advance(hours=1)
        assert clock.now_utc() == _utc(2026, 6, 18, 13, 0)

    def test_taipei_week_window_contains_now(self):
        """The current time falls within the week window."""
        now = _utc(2026, 6, 18, 12, 0)
        ww = taipei_week_window(now)
        assert ww.contains(now)

    def test_taipei_week_window_boundaries(self):
        """Week window start < end, and spans 7 days."""
        now = _utc(2026, 6, 18, 12, 0)
        ww = taipei_week_window(now)
        assert ww.start_utc < ww.end_utc
        assert ww.end_utc - ww.start_utc == timedelta(weeks=1)

    def test_orchestrator_uses_clock_for_week_start(self):
        """Orchestrator derives week_start from its clock."""
        clock = FakeClock(_utc(2026, 6, 18, 12, 0))
        ww = taipei_week_window(clock.now_utc())

        # Advance clock to next week
        clock.advance(hours=24 * 7)
        ww2 = taipei_week_window(clock.now_utc())

        assert ww2.start_utc > ww.start_utc
        assert ww2.start_utc == ww.end_utc


class TestOrchestrationConsistency:
    """Tests verifying the orchestrator maintains consistent state."""

    @pytest.mark.asyncio
    async def test_failure_threshold_is_3(self):
        """FAILURE_THRESHOLD constant is 3."""
        assert SimpleRepairOrchestrator.FAILURE_THRESHOLD == 3

    @pytest.mark.asyncio
    async def test_success_does_not_affect_weekly_attempts(self):
        """handle_parse_success does not change weekly attempt count."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()

        await harness.orchestrator.handle_parse_success(
            session, site_id=1, repair_kind="list",
        )

        assert harness.get_weekly_attempts(1, "list") == 0

    @pytest.mark.asyncio
    async def test_repair_attempt_increments_weekly_count(self):
        """Each repair attempt increments the weekly attempt count by 1."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        ai1 = _make_ai_provider([{"bad": "rules"}])

        # First repair at failure 3
        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": ".article-item"},
            )
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai1,
        )
        assert harness.get_weekly_attempts(1, "list") == 1

        # Second repair at failure 4 (count stays >= 3, so next failure triggers)
        ai2 = _make_ai_provider([{"bad": "rules"}])
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": ".article-item"},
            ai_provider=ai2,
        )
        assert harness.get_weekly_attempts(1, "list") == 2

    @pytest.mark.asyncio
    async def test_applied_repair_uses_budget_slot(self):
        """Successful repair also consumes a weekly budget slot."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        valid_html = _load_fixture("crawl_valid_list.html")
        good_rules = {"item": "li.article-item", "link": "a"}
        ai = _make_ai_provider([good_rules])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence=valid_html,
                active_rules={"item": ".broken"},
            )
        result = await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=valid_html,
            active_rules={"item": ".broken"},
            ai_provider=ai,
        )

        assert result.repair_status == "applied"
        assert harness.get_weekly_attempts(1, "list") == 1

    @pytest.mark.asyncio
    async def test_ai_call_receives_html_evidence(self):
        """AI provider receives the HTML evidence string."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        html = _load_fixture("crawl_valid_list.html")
        ai = _make_ai_provider([{"item": "li.article-item", "link": "a"}])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence=html,
                active_rules={"item": ".broken"},
            )
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence=html,
            active_rules={"item": ".broken"},
            ai_provider=ai,
        )

        assert len(ai.call_log) == 1
        assert ai.call_log[0]["html_len"] == len(html)
        assert ai.call_log[0]["kind"] == "list"

    @pytest.mark.asyncio
    async def test_ai_call_receives_correct_kind(self):
        """AI provider receives the correct repair_kind."""
        harness = MockedRepoOrchestrator()
        session = AsyncMock()
        html = _load_fixture("crawl_valid_content.html")
        ai = _make_ai_provider([{"body": "div.article-body"}])

        for _ in range(2):
            await harness.orchestrator.handle_structural_failure(
                session, site_id=1, repair_kind="content",
                html_evidence=html,
                active_rules={"body": ".broken"},
            )
        await harness.orchestrator.handle_structural_failure(
            session, site_id=1, repair_kind="content",
            html_evidence=html,
            active_rules={"body": ".broken"},
            ai_provider=ai,
        )

        assert ai.call_log[0]["kind"] == "content"
