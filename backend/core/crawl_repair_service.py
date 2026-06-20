"""Crawl auto-repair orchestrator service.

RepairOrchestrator coordinates the complete repair flow:
  failure counting → AI analyze → candidate validation → atomic rule promotion.

Design principles:
  - Delegates all DB access to RepairStateRepository (no raw SQL here).
  - Delegates AI calls to an AIAnalyzeProvider protocol (keeps service testable).
  - AI calls are NEVER held inside a DB transaction.
  - Candidate rules must pass evidence-based validation before promotion.
  - Old rules are preserved on any failure path.
  - Budget enforcement is delegated to the repository layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Optional, Protocol

from .crawl_outcomes import is_valid_content
from .crawl_repair_models import CrawlRepairTables
from .crawl_repair_repository import RepairBudgetExhaustedError, RepairStateRepository
from .time_provider import Clock, SystemClock, taipei_week_window

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AI provider protocol
# ---------------------------------------------------------------------------

class AIAnalyzeProvider(Protocol):
    """Protocol for AI analyze calls -- keeps service testable."""

    async def analyze_structure(
        self,
        html: str,
        kind: Literal["list", "content"],
        user_id: Optional[int],
        db_session,
        ai_tables,
        kek_backend,
    ) -> dict:
        """Return candidate rules dict, or empty dict on failure."""
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RepairResult:
    """Outcome of a handle_structural_failure() call."""

    action: str  # "counted" | "repair_triggered" | "repaired" | "repair_failed" | "budget_exhausted" | "paused" | "disabled"
    failure_count: int = 0
    new_rules: Optional[dict] = None
    attempt_id: Optional[int] = None
    error_code: Optional[str] = None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class RepairOrchestrator:
    """Central coordination for the crawl auto-repair flow.

    Usage::

        orchestrator = RepairOrchestrator(repair_tables, clock)
        result = await orchestrator.handle_structural_failure(session, ...)
    """

    def __init__(
        self,
        repair_tables: CrawlRepairTables,
        clock: Optional[Clock] = None,
    ) -> None:
        self._repo = RepairStateRepository(repair_tables)
        self._clock = clock or SystemClock()

    # ------------------------------------------------------------------
    # handle_structural_failure
    # ------------------------------------------------------------------

    async def handle_structural_failure(
        self,
        session,  # AsyncSession
        site_id: int,
        repair_kind: Literal["list", "content"],
        html_evidence: str,  # HTML that failed to parse
        active_rules: dict,  # current list_rules or content_rules
        rule_revision: int,  # current revision number
        owner_user_id: Optional[int] = None,
        crawl_attempt_id: Optional[int] = None,
        weekly_limit: int = 3,
        auto_repair_enabled: bool = True,
        ai_provider: Optional[AIAnalyzeProvider] = None,
        ai_tables=None,
        kek_backend=None,
    ) -> RepairResult:
        """Orchestrate the full repair flow for a structural failure.

        Steps:
        1. If auto-repair disabled -> return disabled.
        2. Weekly rollover + increment failure counter.
        3. If count < 3 -> return counted.
        4. If count >= 3 and ai_provider available:
           a. Reserve attempt (or handle budget exhaustion).
           b. Commit transaction, then call AI outside DB transaction.
           c. Validate candidate against HTML evidence.
           d. Complete attempt with appropriate status.
        5. If count >= 3 but no ai_provider -> return counted.
        """
        if not auto_repair_enabled:
            return RepairResult(action="disabled")

        # Determine current week window
        week_window = taipei_week_window(self._clock.now_utc())

        # Weekly rollover + increment failure
        await self._repo.lazy_weekly_rollover(
            session, site_id, repair_kind, week_window.start_utc,
        )
        failure_count = await self._repo.increment_failure(
            session, site_id, repair_kind,
        )

        if failure_count < 3:
            return RepairResult(action="counted", failure_count=failure_count)

        if ai_provider is None:
            return RepairResult(action="counted", failure_count=failure_count)

        # ── Count >= 3 and AI provider available: attempt repair ──

        # Reserve an attempt slot (budget check inside)
        try:
            attempt = await self._repo.reserve_repair_attempt(
                session,
                site_id=site_id,
                repair_kind=repair_kind,
                crawl_attempt_id=crawl_attempt_id,
                trigger_failure_count=failure_count,
                owner_user_id=owner_user_id,
                base_rule_revision=rule_revision,
                weekly_limit=weekly_limit,
                current_week_start=week_window.start_utc,
            )
        except RepairBudgetExhaustedError:
            await self._repo.pause_feed(
                session, site_id, repair_kind,
                blocked_until=week_window.end_utc,
            )
            return RepairResult(action="paused", failure_count=failure_count)

        attempt_id = attempt["id"]

        # Commit the reservation BEFORE calling AI (AI must not be inside a txn)
        await session.commit()

        # ── Call AI provider (outside DB transaction) ──
        try:
            candidate = await ai_provider.analyze_structure(
                html=html_evidence,
                kind=repair_kind,
                user_id=owner_user_id,
                db_session=session,
                ai_tables=ai_tables,
                kek_backend=kek_backend,
            )
        except Exception:
            logger.exception(
                "AI provider failed for site_id=%s repair_kind=%s",
                site_id, repair_kind,
            )
            await self._repo.complete_repair_attempt(
                session, attempt_id, "provider_failed",
            )
            return RepairResult(
                action="repair_failed",
                failure_count=failure_count,
                attempt_id=attempt_id,
                error_code="provider_failed",
            )

        # ── Validate candidate schema ──
        if not candidate or not isinstance(candidate, dict):
            await self._repo.complete_repair_attempt(
                session, attempt_id, "candidate_schema_invalid",
            )
            return RepairResult(
                action="repair_failed",
                failure_count=failure_count,
                attempt_id=attempt_id,
                error_code="candidate_schema_invalid",
            )

        # ── Validate candidate against HTML evidence ──
        if repair_kind == "list":
            is_valid, error_code = self.validate_list_candidate(
                candidate, html_evidence, base_url="https://example.com",
            )
        else:
            # For content validation, wrap single HTML in a list
            is_valid, error_code = self.validate_content_candidate(
                candidate, [html_evidence],
            )

        if not is_valid:
            await self._repo.complete_repair_attempt(
                session, attempt_id, "candidate_validation_failed",
                validation_failure_code=error_code,
            )
            return RepairResult(
                action="repair_failed",
                failure_count=failure_count,
                attempt_id=attempt_id,
                error_code=error_code,
            )

        # ── Candidate is valid: promote ──
        await self._repo.complete_repair_attempt(
            session, attempt_id, "applied",
            candidate_rule_revision=rule_revision + 1,
        )
        await self._repo.reset_failure(session, site_id, repair_kind)

        return RepairResult(
            action="repaired",
            failure_count=failure_count,
            new_rules=candidate,
            attempt_id=attempt_id,
        )

    # ------------------------------------------------------------------
    # handle_success
    # ------------------------------------------------------------------

    async def handle_success(
        self,
        session,
        site_id: int,
        repair_kind: Literal["list", "content"],
    ) -> None:
        """Reset consecutive failure counter on successful parse."""
        await self._repo.reset_failure(session, site_id, repair_kind)

    # ------------------------------------------------------------------
    # Candidate validators
    # ------------------------------------------------------------------

    def validate_list_candidate(
        self,
        candidate_rules: dict,
        html_evidence: str,
        base_url: str,
    ) -> tuple[bool, Optional[str]]:
        """Validate list candidate by re-parsing HTML with proposed rules.

        Returns:
            (is_valid, error_code) — error_code is None on success.
        """
        if "item" not in candidate_rules:
            return False, "missing_item_selector"

        from .parser import parse_listing

        try:
            items = parse_listing(html_evidence, candidate_rules, base_url)
        except Exception:
            logger.exception("parse_listing failed during list candidate validation")
            return False, "parse_error"

        if len(items) >= 1:
            return True, None
        return False, "zero_items"

    def validate_content_candidate(
        self,
        candidate_rules: dict,
        article_html_evidence: list[str],
    ) -> tuple[bool, Optional[str]]:
        """Validate content candidate by re-parsing article HTMLs.

        Returns:
            (is_valid, error_code) — error_code is None on success.
        """
        if "body" not in candidate_rules:
            return False, "missing_body_selector"

        from .parser import parse_article

        valid_count = 0
        for html in article_html_evidence:
            try:
                content_text, _pub_date, _image_url, _author = parse_article(
                    html, candidate_rules, "https://example.com/article",
                )
            except Exception:
                continue

            if is_valid_content(content_text):
                valid_count += 1

        if valid_count >= 1:
            return True, None
        return False, "no_valid_content"
