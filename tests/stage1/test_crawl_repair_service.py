"""
---
name: test_crawl_repair_service
description: "Unit tests for RepairOrchestrator covering counting flow, AI repair dispatch, candidate validation, and budget/pause logic"
stage: stage1
type: pytest
target:
  layer: backend
  domain: crawl-repair
spec_doc: null
test_file: tests/stage1/test_crawl_repair_service.py
functions:
  - name: test_first_failure_returns_counted
    line: 137
    purpose: "1st structural failure returns action='counted' with count=1"
    fixtures: []
  - name: test_second_failure_returns_counted
    line: 154
    purpose: "2nd structural failure returns action='counted' with count=2"
    fixtures: []
  - name: test_third_failure_with_valid_candidate_returns_repaired
    line: 179
    purpose: "3rd failure with AI provider and valid candidate returns action='repaired'"
    fixtures: []
  - name: test_third_failure_commits_before_ai_call
    line: 210
    purpose: "session.commit() is called before AI provider.analyze_structure()"
    fixtures: []
  - name: test_repaired_result_has_new_rules
    line: 255
    purpose: "Successful repair result contains new_rules dict and attempt_id"
    fixtures: []
  - name: test_repaired_calls_complete_with_applied_status
    line: 282
    purpose: "complete_repair_attempt is called with status='applied' on success"
    fixtures: []
  - name: test_empty_dict_from_ai_returns_repair_failed
    line: 316
    purpose: "AI returning empty dict triggers repair_failed with candidate_schema_invalid"
    fixtures: []
  - name: test_none_from_ai_returns_repair_failed
    line: 339
    purpose: "AI returning None triggers repair_failed with candidate_schema_invalid"
    fixtures: []
  - name: test_list_validation_failure_returns_repair_failed
    line: 370
    purpose: "List candidate that matches zero items triggers repair_failed"
    fixtures: []
  - name: test_content_validation_failure_returns_repair_failed
    line: 394
    purpose: "Content candidate failing validation triggers repair_failed"
    fixtures: []
  - name: test_budget_exhausted_returns_paused
    line: 426
    purpose: "RepairBudgetExhaustedError from reserve leads to action='paused'"
    fixtures: []
  - name: test_pause_uses_week_end_as_blocked_until
    line: 450
    purpose: "pause_feed receives the Taipei week-end UTC as blocked_until"
    fixtures: []
  - name: test_disabled_returns_disabled_action
    line: 483
    purpose: "auto_repair_enabled=False returns action='disabled' without DB calls"
    fixtures: []
  - name: test_no_provider_at_count_3_returns_counted
    line: 506
    purpose: "No AI provider at count=3 still returns action='counted'"
    fixtures: []
  - name: test_no_provider_at_count_10_returns_counted
    line: 524
    purpose: "No AI provider at high count returns action='counted'"
    fixtures: []
  - name: test_provider_exception_returns_repair_failed
    line: 550
    purpose: "AI provider raising exception returns action='repair_failed' with error_code='provider_failed'"
    fixtures: []
  - name: test_provider_exception_completes_attempt_as_provider_failed
    line: 574
    purpose: "On AI exception, complete_repair_attempt is called with status='provider_failed'"
    fixtures: []
  - name: test_success_calls_reset_failure
    line: 604
    purpose: "handle_success calls reset_failure on the repo"
    fixtures: []
  - name: test_success_resets_content_kind
    line: 615
    purpose: "handle_success with repair_kind='content' resets the content counter"
    fixtures: []
  - name: test_valid_candidate_with_matching_items
    line: 633
    purpose: "validate_list_candidate passes when selectors match items in HTML"
    fixtures: []
  - name: test_zero_items_when_selector_mismatch
    line: 650
    purpose: "validate_list_candidate fails with zero_items when selectors don't match"
    fixtures: []
  - name: test_missing_item_key_returns_error
    line: 668
    purpose: "validate_list_candidate fails with missing_item_selector when 'item' key absent"
    fixtures: []
  - name: test_valid_candidate_with_redesigned_selectors
    line: 679
    purpose: "validate_list_candidate passes when selectors match redesigned page structure"
    fixtures: []
  - name: test_valid_content_with_body_selector
    line: 704
    purpose: "validate_content_candidate passes for HTML with substantial article body"
    fixtures: []
  - name: test_sentinel_content_returns_no_valid_content
    line: 716
    purpose: "validate_content_candidate fails when selector returns sentinel parse failure"
    fixtures: []
  - name: test_missing_body_key_returns_error
    line: 729
    purpose: "validate_content_candidate fails with missing_body_selector when 'body' absent"
    fixtures: []
  - name: test_valid_content_among_multiple_articles
    line: 740
    purpose: "validate_content_candidate passes if at least one article has valid content"
    fixtures: []
  - name: test_all_sentinel_articles_returns_no_valid_content
    line: 754
    purpose: "validate_content_candidate fails when all articles produce sentinel text"
    fixtures: []
  - name: test_content_candidate_with_correct_selectors_for_redesigned_page
    line: 767
    purpose: "Thin content below threshold fails validate_content_candidate"
    fixtures: []
  - name: test_base_rule_revision_passed_to_reserve
    line: 795
    purpose: "rule_revision is forwarded as base_rule_revision to reserve_repair_attempt"
    fixtures: []
  - name: test_candidate_rule_revision_incremented_on_success
    line: 825
    purpose: "candidate_rule_revision is base+1 in complete_repair_attempt on success"
    fixtures: []
  - name: test_content_kind_uses_content_validator
    line: 864
    purpose: "repair_kind='content' routes to validate_content_candidate, not list"
    fixtures: []
  - name: test_default_values
    line: 900
    purpose: "RepairResult defaults: failure_count=0, new_rules=None, attempt_id=None, error_code=None"
    fixtures: []
  - name: test_all_fields
    line: 907
    purpose: "RepairResult stores all fields when explicitly set"
    fixtures: []
  - name: test_weekly_rollover_called_before_increment
    line: 927
    purpose: "lazy_weekly_rollover is invoked before increment_failure"
    fixtures: []
  - name: test_high_failure_count_no_provider_still_counted
    line: 953
    purpose: "Very high failure count with no provider still returns action='counted'"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_crawl_repair_service.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from core.crawl_repair_service import AIAnalyzeProvider, RepairOrchestrator, RepairResult
from core.crawl_repair_repository import RepairBudgetExhaustedError
from core.time_provider import FakeClock, WeekWindow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# Fixed time: Wednesday 2026-06-17 10:00 UTC = 2026-06-17 18:00 Taipei
# Week window: Sunday 2026-06-14 00:00 Taipei = 2026-06-13 16:00 UTC
#            → Sunday 2026-06-21 00:00 Taipei = 2026-06-20 16:00 UTC
FIXED_UTC = _utc(2026, 6, 17, 10, 0)
WEEK_START = _utc(2026, 6, 13, 16, 0)
WEEK_END = _utc(2026, 6, 20, 16, 0)


def _make_clock() -> FakeClock:
    return FakeClock(FIXED_UTC)


def _make_attempt_row(attempt_id: int = 1, status: str = "reserved") -> dict:
    return {
        "id": attempt_id,
        "site_id": 1,
        "crawl_attempt_id": None,
        "repair_kind": "list",
        "week_start_at": WEEK_START,
        "weekly_sequence": 1,
        "trigger_failure_count": 3,
        "status": status,
        "owner_user_id": None,
        "base_rule_revision": 1,
        "candidate_rule_revision": None,
        "provider_trace_id": None,
        "sample_url": None,
        "sample_count": 0,
        "validation_success_count": 0,
        "validation_failure_code": None,
        "started_at": FIXED_UTC,
        "finished_at": None,
    }


def _build_orchestrator(clock=None):
    """Build a RepairOrchestrator with real table objects."""
    import sqlalchemy as sa

    meta = sa.MetaData()
    for tbl_name in ("sites", "crawl_attempts", "users"):
        sa.Table(tbl_name, meta, sa.Column("id", sa.Integer, primary_key=True))

    from core.crawl_repair_models import define_crawl_repair_tables
    tables = define_crawl_repair_tables(meta)

    return RepairOrchestrator(tables, clock=clock or _make_clock())


def _make_ai_provider(candidate: dict | None = None, raises: Exception | None = None):
    """Create an AsyncMock AI provider."""
    provider = AsyncMock(spec=AIAnalyzeProvider)
    if raises is not None:
        provider.analyze_structure = AsyncMock(side_effect=raises)
    else:
        provider.analyze_structure = AsyncMock(return_value=candidate or {})
    return provider


def _read_fixture(filename: str) -> str:
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# handle_structural_failure: counting flow
# ---------------------------------------------------------------------------

class TestCountingFlow:
    """1st and 2nd failures return action='counted'."""

    @pytest.mark.asyncio
    async def test_first_failure_returns_counted(self):
        orch = _build_orchestrator()
        session = AsyncMock()

        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=1)):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
            )

        assert result.action == "counted"
        assert result.failure_count == 1

    @pytest.mark.asyncio
    async def test_second_failure_returns_counted(self):
        orch = _build_orchestrator()
        session = AsyncMock()

        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=2)):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
            )

        assert result.action == "counted"
        assert result.failure_count == 2


# ---------------------------------------------------------------------------
# handle_structural_failure: 3rd failure triggers repair
# ---------------------------------------------------------------------------

class TestThirdFailureTriggersRepair:
    """3rd failure with AI provider triggers the repair flow."""

    @pytest.mark.asyncio
    async def test_third_failure_with_valid_candidate_returns_repaired(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        attempt_row = _make_attempt_row(attempt_id=42)

        valid_candidate = {
            "item": ".article-item",
            "link": "a",
            "title": ".article-title",
        }
        ai_provider = _make_ai_provider(candidate=valid_candidate)

        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "complete_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "reset_failure", new=AsyncMock()), \
             patch.object(orch, "validate_list_candidate", return_value=(True, None)):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
                ai_provider=ai_provider,
            )

        assert result.action == "repaired"
        assert result.new_rules == valid_candidate
        assert result.attempt_id == 42

    @pytest.mark.asyncio
    async def test_third_failure_commits_before_ai_call(self):
        """session.commit() is called before AI provider.analyze_structure()."""
        orch = _build_orchestrator()
        session = AsyncMock()
        session.commit = AsyncMock()
        attempt_row = _make_attempt_row()

        call_order = []

        async def mock_commit():
            call_order.append("commit")

        async def mock_analyze(**kwargs):
            call_order.append("ai_call")
            return {"item": ".x"}

        session.commit = mock_commit
        ai_provider = AsyncMock(spec=AIAnalyzeProvider)
        ai_provider.analyze_structure = mock_analyze

        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "complete_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "reset_failure", new=AsyncMock()), \
             patch.object(orch, "validate_list_candidate", return_value=(True, None)):
            await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
                ai_provider=ai_provider,
            )

        assert call_order == ["commit", "ai_call"]


# ---------------------------------------------------------------------------
# Successful repair
# ---------------------------------------------------------------------------

class TestSuccessfulRepair:
    """AI returns valid candidate, validation passes -> repaired."""

    @pytest.mark.asyncio
    async def test_repaired_result_has_new_rules(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        attempt_row = _make_attempt_row(attempt_id=10)
        candidate = {"item": ".new-item", "link": "a"}
        ai_provider = _make_ai_provider(candidate=candidate)

        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=5)), \
             patch.object(orch._repo, "reserve_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "complete_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "reset_failure", new=AsyncMock()) as mock_reset, \
             patch.object(orch, "validate_list_candidate", return_value=(True, None)):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=5,
                ai_provider=ai_provider,
            )

        assert result.action == "repaired"
        assert result.new_rules == candidate
        assert result.attempt_id == 10
        mock_reset.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_repaired_calls_complete_with_applied_status(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        attempt_row = _make_attempt_row(attempt_id=7)
        ai_provider = _make_ai_provider(candidate={"item": ".x"})

        mock_complete = AsyncMock(return_value=attempt_row)
        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "complete_repair_attempt", mock_complete), \
             patch.object(orch._repo, "reset_failure", new=AsyncMock()), \
             patch.object(orch, "validate_list_candidate", return_value=(True, None)):
            await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=3,
                ai_provider=ai_provider,
            )

        mock_complete.assert_awaited_once()
        call_args = mock_complete.call_args
        assert call_args[0][2] == "applied"  # status


# ---------------------------------------------------------------------------
# Invalid candidate schema
# ---------------------------------------------------------------------------

class TestInvalidCandidateSchema:
    """AI returns empty or non-dict -> repair_failed with candidate_schema_invalid."""

    @pytest.mark.asyncio
    async def test_empty_dict_from_ai_returns_repair_failed(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        attempt_row = _make_attempt_row(attempt_id=5)
        ai_provider = _make_ai_provider(candidate={})

        mock_complete = AsyncMock(return_value=attempt_row)
        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "complete_repair_attempt", mock_complete):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
                ai_provider=ai_provider,
            )

        assert result.action == "repair_failed"
        assert result.error_code == "candidate_schema_invalid"

    @pytest.mark.asyncio
    async def test_none_from_ai_returns_repair_failed(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        attempt_row = _make_attempt_row()
        ai_provider = _make_ai_provider(candidate=None)

        mock_complete = AsyncMock(return_value=attempt_row)
        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "complete_repair_attempt", mock_complete):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
                ai_provider=ai_provider,
            )

        assert result.action == "repair_failed"
        assert result.error_code == "candidate_schema_invalid"


# ---------------------------------------------------------------------------
# Candidate validation failure
# ---------------------------------------------------------------------------

class TestCandidateValidationFailure:
    """AI returns syntactically valid but functionally broken rules."""

    @pytest.mark.asyncio
    async def test_list_validation_failure_returns_repair_failed(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        attempt_row = _make_attempt_row(attempt_id=8)
        ai_provider = _make_ai_provider(candidate={"item": ".nonexistent"})

        mock_complete = AsyncMock(return_value=attempt_row)
        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "complete_repair_attempt", mock_complete), \
             patch.object(orch, "validate_list_candidate", return_value=(False, "zero_items")):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
                ai_provider=ai_provider,
            )

        assert result.action == "repair_failed"
        assert result.error_code == "zero_items"

    @pytest.mark.asyncio
    async def test_content_validation_failure_returns_repair_failed(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        attempt_row = _make_attempt_row(attempt_id=9)
        ai_provider = _make_ai_provider(candidate={"body": ".nonexistent-body"})

        mock_complete = AsyncMock(return_value=attempt_row)
        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "complete_repair_attempt", mock_complete), \
             patch.object(orch, "validate_content_candidate", return_value=(False, "no_valid_content")):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="content",
                html_evidence="<html></html>",
                active_rules={"body": "article"},
                rule_revision=1,
                ai_provider=ai_provider,
            )

        assert result.action == "repair_failed"
        assert result.error_code == "no_valid_content"


# ---------------------------------------------------------------------------
# Budget exhaustion
# ---------------------------------------------------------------------------

class TestBudgetExhaustion:
    """Weekly budget exhausted -> paused."""

    @pytest.mark.asyncio
    async def test_budget_exhausted_returns_paused(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        ai_provider = _make_ai_provider(candidate={"item": ".x"})

        mock_pause = AsyncMock()
        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt",
                          new=AsyncMock(side_effect=RepairBudgetExhaustedError("exhausted"))), \
             patch.object(orch._repo, "pause_feed", mock_pause):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
                ai_provider=ai_provider,
            )

        assert result.action == "paused"
        assert result.failure_count == 3
        mock_pause.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pause_uses_week_end_as_blocked_until(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        ai_provider = _make_ai_provider(candidate={"item": ".x"})

        pause_calls = []

        async def capture_pause(session, site_id, repair_kind, blocked_until):
            pause_calls.append(blocked_until)

        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt",
                          new=AsyncMock(side_effect=RepairBudgetExhaustedError("exhausted"))), \
             patch.object(orch._repo, "pause_feed", side_effect=capture_pause):
            await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
                ai_provider=ai_provider,
            )

        assert len(pause_calls) == 1
        assert pause_calls[0] == WEEK_END


# ---------------------------------------------------------------------------
# Auto-repair disabled
# ---------------------------------------------------------------------------

class TestAutoRepairDisabled:
    @pytest.mark.asyncio
    async def test_disabled_returns_disabled_action(self):
        orch = _build_orchestrator()
        session = AsyncMock()

        result = await orch.handle_structural_failure(
            session, site_id=1, repair_kind="list",
            html_evidence="<html></html>",
            active_rules={"item": "li"},
            rule_revision=1,
            auto_repair_enabled=False,
        )

        assert result.action == "disabled"


# ---------------------------------------------------------------------------
# No AI provider
# ---------------------------------------------------------------------------

class TestNoAIProvider:
    """No AI provider -> action='counted' even at count >= 3."""

    @pytest.mark.asyncio
    async def test_no_provider_at_count_3_returns_counted(self):
        orch = _build_orchestrator()
        session = AsyncMock()

        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
                ai_provider=None,
            )

        assert result.action == "counted"
        assert result.failure_count == 3

    @pytest.mark.asyncio
    async def test_no_provider_at_count_10_returns_counted(self):
        orch = _build_orchestrator()
        session = AsyncMock()

        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=10)):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
                ai_provider=None,
            )

        assert result.action == "counted"
        assert result.failure_count == 10


# ---------------------------------------------------------------------------
# AI provider failure (exception)
# ---------------------------------------------------------------------------

class TestAIProviderFailure:
    """AI provider raises exception -> repair_failed with error_code=provider_failed."""

    @pytest.mark.asyncio
    async def test_provider_exception_returns_repair_failed(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        attempt_row = _make_attempt_row(attempt_id=20)
        ai_provider = _make_ai_provider(raises=RuntimeError("API timeout"))

        mock_complete = AsyncMock(return_value=attempt_row)
        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "complete_repair_attempt", mock_complete):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
                ai_provider=ai_provider,
            )

        assert result.action == "repair_failed"
        assert result.error_code == "provider_failed"
        assert result.attempt_id == 20

    @pytest.mark.asyncio
    async def test_provider_exception_completes_attempt_as_provider_failed(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        attempt_row = _make_attempt_row(attempt_id=21)
        ai_provider = _make_ai_provider(raises=ConnectionError("network down"))

        mock_complete = AsyncMock(return_value=attempt_row)
        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=4)), \
             patch.object(orch._repo, "reserve_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "complete_repair_attempt", mock_complete):
            await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
                ai_provider=ai_provider,
            )

        mock_complete.assert_awaited_once()
        call_args = mock_complete.call_args
        assert call_args[0][2] == "provider_failed"


# ---------------------------------------------------------------------------
# handle_success resets counter
# ---------------------------------------------------------------------------

class TestHandleSuccess:
    @pytest.mark.asyncio
    async def test_success_calls_reset_failure(self):
        orch = _build_orchestrator()
        session = AsyncMock()

        mock_reset = AsyncMock()
        with patch.object(orch._repo, "reset_failure", mock_reset):
            await orch.handle_success(session, site_id=1, repair_kind="list")

        mock_reset.assert_awaited_once_with(session, 1, "list")

    @pytest.mark.asyncio
    async def test_success_resets_content_kind(self):
        orch = _build_orchestrator()
        session = AsyncMock()

        mock_reset = AsyncMock()
        with patch.object(orch._repo, "reset_failure", mock_reset):
            await orch.handle_success(session, site_id=5, repair_kind="content")

        mock_reset.assert_awaited_once_with(session, 5, "content")


# ---------------------------------------------------------------------------
# List candidate validation (with HTML fixtures)
# ---------------------------------------------------------------------------

class TestValidateListCandidate:
    """Uses fixtures from tests/fixtures/."""

    def test_valid_candidate_with_matching_items(self):
        orch = _build_orchestrator()
        html = _read_fixture("crawl_valid_list.html")
        candidate = {
            "container": "ul.article-list",
            "item": "li.article-item",
            "link": "a",
            "title": "h3.article-title",
        }

        is_valid, error_code = orch.validate_list_candidate(
            candidate, html, "https://example.com",
        )

        assert is_valid is True
        assert error_code is None

    def test_zero_items_when_selector_mismatch(self):
        orch = _build_orchestrator()
        html = _read_fixture("crawl_list_zero_items.html")
        # These selectors don't match the redesigned page
        candidate = {
            "container": "ul.article-list",
            "item": "li.article-item",
            "link": "a",
            "title": "h3.article-title",
        }

        is_valid, error_code = orch.validate_list_candidate(
            candidate, html, "https://example.com",
        )

        assert is_valid is False
        assert error_code == "zero_items"

    def test_missing_item_key_returns_error(self):
        orch = _build_orchestrator()
        candidate = {"link": "a", "title": "h3"}  # no "item" key

        is_valid, error_code = orch.validate_list_candidate(
            candidate, "<html></html>", "https://example.com",
        )

        assert is_valid is False
        assert error_code == "missing_item_selector"

    def test_valid_candidate_with_redesigned_selectors(self):
        """The zero-items fixture has .news-card items; matching selectors should work."""
        orch = _build_orchestrator()
        html = _read_fixture("crawl_list_zero_items.html")
        candidate = {
            "container": "section.news-feed",
            "item": "div.news-card",
            "link": "a",
        }

        is_valid, error_code = orch.validate_list_candidate(
            candidate, html, "https://example.com",
        )

        assert is_valid is True
        assert error_code is None


# ---------------------------------------------------------------------------
# Content candidate validation (with HTML fixtures)
# ---------------------------------------------------------------------------

class TestValidateContentCandidate:
    """Uses fixtures from tests/fixtures/."""

    def test_valid_content_with_body_selector(self):
        orch = _build_orchestrator()
        html = _read_fixture("crawl_valid_content.html")
        candidate = {"body": "div.article-body"}

        is_valid, error_code = orch.validate_content_candidate(
            candidate, [html],
        )

        assert is_valid is True
        assert error_code is None

    def test_sentinel_content_returns_no_valid_content(self):
        orch = _build_orchestrator()
        html = _read_fixture("crawl_content_sentinel_fail.html")
        # This selector matches nothing -> parse_article returns "Parsing failed"
        candidate = {"body": "div.article-body"}

        is_valid, error_code = orch.validate_content_candidate(
            candidate, [html],
        )

        assert is_valid is False
        assert error_code == "no_valid_content"

    def test_missing_body_key_returns_error(self):
        orch = _build_orchestrator()
        candidate = {"date": "time"}  # no "body" key

        is_valid, error_code = orch.validate_content_candidate(
            candidate, ["<html></html>"],
        )

        assert is_valid is False
        assert error_code == "missing_body_selector"

    def test_valid_content_among_multiple_articles(self):
        """If at least one article has valid content, validation passes."""
        orch = _build_orchestrator()
        good_html = _read_fixture("crawl_valid_content.html")
        bad_html = _read_fixture("crawl_content_sentinel_fail.html")
        candidate = {"body": "div.article-body"}

        is_valid, error_code = orch.validate_content_candidate(
            candidate, [bad_html, good_html],
        )

        assert is_valid is True
        assert error_code is None

    def test_all_sentinel_articles_returns_no_valid_content(self):
        """All articles returning sentinel -> validation fails."""
        orch = _build_orchestrator()
        bad_html = _read_fixture("crawl_content_sentinel_fail.html")
        candidate = {"body": "div.article-body"}

        is_valid, error_code = orch.validate_content_candidate(
            candidate, [bad_html, bad_html, bad_html],
        )

        assert is_valid is False
        assert error_code == "no_valid_content"

    def test_content_candidate_with_correct_selectors_for_redesigned_page(self):
        """Correct selectors for the redesigned page should produce valid content
        (if body element has enough text)."""
        orch = _build_orchestrator()
        html = _read_fixture("crawl_content_sentinel_fail.html")
        # The sentinel fixture has div.story-text with real content
        candidate = {"body": "div.story-text"}

        is_valid, error_code = orch.validate_content_candidate(
            candidate, [html],
        )

        # div.story-text has a short paragraph — may or may not pass the threshold
        # The fixture text is: "Article content is here but under a different class name."
        # That's 10 words, < 20 word threshold. Non-ws chars: ~50, < 80.
        # So it should be invalid.
        assert is_valid is False
        assert error_code == "no_valid_content"


# ---------------------------------------------------------------------------
# Revision CAS pass-through
# ---------------------------------------------------------------------------

class TestRevisionCAS:
    """Ensure rule_revision is passed through for atomic promotion."""

    @pytest.mark.asyncio
    async def test_base_rule_revision_passed_to_reserve(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        attempt_row = _make_attempt_row()
        ai_provider = _make_ai_provider(candidate={"item": ".x"})

        reserve_calls = []

        async def capture_reserve(session, **kwargs):
            reserve_calls.append(kwargs)
            return attempt_row

        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt", side_effect=capture_reserve), \
             patch.object(orch._repo, "complete_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "reset_failure", new=AsyncMock()), \
             patch.object(orch, "validate_list_candidate", return_value=(True, None)):
            await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=42,
                ai_provider=ai_provider,
            )

        assert len(reserve_calls) == 1
        assert reserve_calls[0]["base_rule_revision"] == 42

    @pytest.mark.asyncio
    async def test_candidate_rule_revision_incremented_on_success(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        attempt_row = _make_attempt_row()
        ai_provider = _make_ai_provider(candidate={"item": ".x"})

        complete_calls = []

        async def capture_complete(session, attempt_id, status, **kwargs):
            complete_calls.append({"attempt_id": attempt_id, "status": status, **kwargs})
            return attempt_row

        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "complete_repair_attempt", side_effect=capture_complete), \
             patch.object(orch._repo, "reset_failure", new=AsyncMock()), \
             patch.object(orch, "validate_list_candidate", return_value=(True, None)):
            await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=7,
                ai_provider=ai_provider,
            )

        assert len(complete_calls) == 1
        assert complete_calls[0]["status"] == "applied"
        assert complete_calls[0]["candidate_rule_revision"] == 8  # 7 + 1


# ---------------------------------------------------------------------------
# Content repair flow (end-to-end with content kind)
# ---------------------------------------------------------------------------

class TestContentRepairFlow:
    """Validate that repair_kind='content' routes to validate_content_candidate."""

    @pytest.mark.asyncio
    async def test_content_kind_uses_content_validator(self):
        orch = _build_orchestrator()
        session = AsyncMock()
        attempt_row = _make_attempt_row()
        ai_provider = _make_ai_provider(candidate={"body": ".article-body"})

        validate_content_calls = []

        def capture_validate(candidate_rules, article_html_evidence):
            validate_content_calls.append(candidate_rules)
            return True, None

        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=3)), \
             patch.object(orch._repo, "reserve_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "complete_repair_attempt", new=AsyncMock(return_value=attempt_row)), \
             patch.object(orch._repo, "reset_failure", new=AsyncMock()), \
             patch.object(orch, "validate_content_candidate", side_effect=capture_validate):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="content",
                html_evidence="<article>content</article>",
                active_rules={"body": "article"},
                rule_revision=2,
                ai_provider=ai_provider,
            )

        assert result.action == "repaired"
        assert len(validate_content_calls) == 1
        assert validate_content_calls[0]["body"] == ".article-body"


# ---------------------------------------------------------------------------
# RepairResult dataclass
# ---------------------------------------------------------------------------

class TestRepairResult:
    def test_default_values(self):
        r = RepairResult(action="counted")
        assert r.failure_count == 0
        assert r.new_rules is None
        assert r.attempt_id is None
        assert r.error_code is None

    def test_all_fields(self):
        r = RepairResult(
            action="repaired",
            failure_count=3,
            new_rules={"item": ".x"},
            attempt_id=42,
            error_code=None,
        )
        assert r.action == "repaired"
        assert r.failure_count == 3
        assert r.new_rules == {"item": ".x"}
        assert r.attempt_id == 42


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_weekly_rollover_called_before_increment(self):
        """Ensures lazy_weekly_rollover is called before increment_failure."""
        orch = _build_orchestrator()
        session = AsyncMock()
        call_order = []

        async def mock_rollover(*args, **kwargs):
            call_order.append("rollover")
            return False

        async def mock_increment(*args, **kwargs):
            call_order.append("increment")
            return 1

        with patch.object(orch._repo, "lazy_weekly_rollover", side_effect=mock_rollover), \
             patch.object(orch._repo, "increment_failure", side_effect=mock_increment):
            await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
            )

        assert call_order == ["rollover", "increment"]

    @pytest.mark.asyncio
    async def test_high_failure_count_no_provider_still_counted(self):
        """Even at very high failure counts, no provider means counted."""
        orch = _build_orchestrator()
        session = AsyncMock()

        with patch.object(orch._repo, "lazy_weekly_rollover", new=AsyncMock(return_value=False)), \
             patch.object(orch._repo, "increment_failure", new=AsyncMock(return_value=100)):
            result = await orch.handle_structural_failure(
                session, site_id=1, repair_kind="list",
                html_evidence="<html></html>",
                active_rules={"item": "li"},
                rule_revision=1,
                ai_provider=None,
            )

        assert result.action == "counted"
        assert result.failure_count == 100
