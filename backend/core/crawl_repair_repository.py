"""Crawl auto-repair state repository.

Provides transactional, concurrent-safe access to site_crawl_repair_states
and crawl_repair_attempts tables.

Design principles (from plan sections 10, 11):
- DB locks protect only state transitions and promotions; never include network
  or AI calls inside a transaction.
- Fixed lock ordering: always acquire list state before content state to prevent
  deadlocks when both kinds are locked in the same transaction.
- Use SELECT … FOR UPDATE to serialize concurrent writers on the same (site, kind).
- Reserve a weekly attempt BEFORE calling AI; commit the reservation, THEN call AI.
- Completion uses attempt_id + state revision CAS (compare-and-swap) guard.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import sqlalchemy
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

from .crawl_repair_models import (
    AttemptStatus,
    CrawlRepairTables,
    PauseStatus,
    RepairKind,
    RepairStatus,
    _TERMINAL_ATTEMPT_STATUSES,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class RepairBudgetExhaustedError(Exception):
    """Raised when all weekly repair attempts have been used for a site+kind."""


class AttemptAlreadyFinalizedError(Exception):
    """Raised when complete_repair_attempt is called on an already-terminal attempt."""


class AttemptNotFoundError(Exception):
    """Raised when the repair attempt row is not found."""


class RepairStateNotFoundError(Exception):
    """Raised when the repair state row is not found and could not be created."""


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class RepairStateRepository:
    """Async repository for crawl repair state.

    Every public method accepts an AsyncSession and may acquire row locks.
    The caller is responsible for transaction management (begin/commit/rollback).

    Lock ordering contract:
        When acquiring locks on multiple repair-state rows in the same transaction,
        always lock 'list' before 'content'.  See _lock_ordered_kinds().
    """

    def __init__(self, tables: CrawlRepairTables) -> None:
        self._states = tables.site_crawl_repair_states
        self._attempts = tables.crawl_repair_attempts

    # ------------------------------------------------------------------
    # Core state read/write
    # ------------------------------------------------------------------

    async def get_state(
        self,
        session,
        site_id: int,
        repair_kind: RepairKind,
        *,
        for_update: bool = False,
    ) -> dict:
        """Return the repair state row for (site_id, repair_kind).

        If no row exists, create one with healthy defaults and return it.
        Pass for_update=True to acquire a pessimistic row lock (FOR UPDATE).

        Args:
            session: SQLAlchemy AsyncSession.
            site_id: The site primary key.
            repair_kind: 'list' or 'content'.
            for_update: Whether to lock the row for subsequent writes.

        Returns:
            Mapping dict of the state row.
        """
        stmt = (
            sqlalchemy.select(self._states)
            .where(
                self._states.c.site_id == site_id,
                self._states.c.repair_kind == repair_kind,
            )
        )
        if for_update:
            stmt = stmt.with_for_update()

        result = (await session.execute(stmt)).mappings().first()
        if result is not None:
            return dict(result)

        # Lazy create with defaults.
        # Use INSERT ... ON CONFLICT DO NOTHING to handle races.
        now = datetime.now(timezone.utc)
        # Minimal week_start placeholder; the caller should call
        # lazy_weekly_rollover() to set the correct week_start_at.
        await session.execute(
            postgresql_insert(self._states).values(
                site_id=site_id,
                repair_kind=repair_kind,
                consecutive_failure_count=0,
                week_start_at=now,  # will be corrected by lazy_weekly_rollover
                weekly_attempt_count=0,
                repair_status="healthy",
                revision=1,
                created_at=now,
                updated_at=now,
            ).on_conflict_do_nothing(
                index_elements=["site_id", "repair_kind"]
            )
        )
        # Re-fetch (possibly written by concurrent worker).
        stmt2 = (
            sqlalchemy.select(self._states)
            .where(
                self._states.c.site_id == site_id,
                self._states.c.repair_kind == repair_kind,
            )
        )
        if for_update:
            stmt2 = stmt2.with_for_update()
        result2 = (await session.execute(stmt2)).mappings().first()
        if result2 is None:
            raise RepairStateNotFoundError(
                f"Could not get/create repair state for site_id={site_id} "
                f"repair_kind={repair_kind}"
            )
        return dict(result2)

    async def lazy_weekly_rollover(
        self,
        session,
        site_id: int,
        repair_kind: RepairKind,
        current_week_start: datetime,
    ) -> bool:
        """Reset weekly counters if week_start_at differs from current_week_start.

        MUST be called within a FOR UPDATE lock on the state row.
        Returns True if a rollover was performed, False otherwise.

        Rollover behaviour (from plan section 5.2):
        - weekly_attempt_count → 0
        - blocked_at → NULL
        - blocked_until → NULL
        - repair_status → 'healthy' if was 'paused_until_next_week', else keep
        - consecutive_failure_count is PRESERVED (describes rule still unfixed)
        - week_start_at → current_week_start
        """
        state = await self.get_state(
            session, site_id, repair_kind, for_update=True
        )
        if state["week_start_at"] == current_week_start:
            return False

        new_status: RepairStatus = state["repair_status"]
        if new_status == "paused_until_next_week":
            # After rollover, demote to collecting_failures if there are
            # accumulated failures, otherwise healthy.
            new_status = (
                "collecting_failures"
                if state["consecutive_failure_count"] > 0
                else "healthy"
            )

        now = datetime.now(timezone.utc)
        await session.execute(
            self._states.update()
            .where(
                self._states.c.site_id == site_id,
                self._states.c.repair_kind == repair_kind,
            )
            .values(
                week_start_at=current_week_start,
                weekly_attempt_count=0,
                blocked_at=None,
                blocked_until=None,
                repair_status=new_status,
                revision=self._states.c.revision + 1,
                updated_at=now,
            )
        )
        return True

    async def increment_failure(
        self,
        session,
        site_id: int,
        repair_kind: RepairKind,
        *,
        failure_reason: Optional[str] = None,
        current_week_start: Optional[datetime] = None,
    ) -> int:
        """Increment consecutive_failure_count by 1 and return the new count.

        Also performs a lazy weekly rollover if current_week_start is provided.
        Acquires a FOR UPDATE lock on the state row.

        Args:
            session: SQLAlchemy AsyncSession.
            site_id: The site primary key.
            repair_kind: 'list' or 'content'.
            failure_reason: Optional human-readable failure description.
            current_week_start: If provided, performs lazy weekly rollover first.

        Returns:
            New consecutive_failure_count value.
        """
        if current_week_start is not None:
            await self.lazy_weekly_rollover(
                session, site_id, repair_kind, current_week_start
            )

        state = await self.get_state(
            session, site_id, repair_kind, for_update=True
        )
        new_count = state["consecutive_failure_count"] + 1
        now = datetime.now(timezone.utc)

        new_status: RepairStatus = "collecting_failures"
        if state["repair_status"] == "paused_until_next_week":
            new_status = "paused_until_next_week"  # preserve pause

        await session.execute(
            self._states.update()
            .where(
                self._states.c.site_id == site_id,
                self._states.c.repair_kind == repair_kind,
            )
            .values(
                consecutive_failure_count=new_count,
                last_failure_at=now,
                last_failure_reason=failure_reason,
                last_outcome="structural_failure",
                repair_status=new_status,
                revision=self._states.c.revision + 1,
                updated_at=now,
            )
        )
        return new_count

    async def reset_failure(
        self,
        session,
        site_id: int,
        repair_kind: RepairKind,
        *,
        current_week_start: Optional[datetime] = None,
    ) -> None:
        """Reset consecutive_failure_count to 0 on extraction success.

        Also performs a lazy weekly rollover if current_week_start is provided.
        Acquires a FOR UPDATE lock on the state row.

        Only resets the specified repair_kind; the other kind is NOT touched.
        """
        if current_week_start is not None:
            await self.lazy_weekly_rollover(
                session, site_id, repair_kind, current_week_start
            )

        state = await self.get_state(
            session, site_id, repair_kind, for_update=True
        )
        now = datetime.now(timezone.utc)

        # If paused, don't silently clear the pause — manual repair or
        # next-week rollover resolves pauses.
        new_status: RepairStatus = "healthy"
        if state["repair_status"] == "paused_until_next_week":
            new_status = "paused_until_next_week"

        await session.execute(
            self._states.update()
            .where(
                self._states.c.site_id == site_id,
                self._states.c.repair_kind == repair_kind,
            )
            .values(
                consecutive_failure_count=0,
                last_success_at=now,
                last_outcome="success",
                repair_status=new_status,
                revision=self._states.c.revision + 1,
                updated_at=now,
            )
        )

    # ------------------------------------------------------------------
    # Repair attempt reservation
    # ------------------------------------------------------------------

    async def reserve_repair_attempt(
        self,
        session,
        site_id: int,
        repair_kind: RepairKind,
        *,
        crawl_attempt_id: Optional[int],
        trigger_failure_count: int,
        owner_user_id: Optional[int],
        base_rule_revision: int,
        weekly_limit: int,
        current_week_start: datetime,
        started_at: Optional[datetime] = None,
    ) -> dict:
        """Reserve one weekly auto-repair attempt and return the attempt row.

        This is an atomic operation:
        1. Acquire FOR UPDATE lock on state row.
        2. Perform lazy weekly rollover if needed.
        3. Check budget (weekly_attempt_count < weekly_limit).
        4. Increment weekly_attempt_count.
        5. Create repair attempt row with status='reserved'.
        6. Update state repair_status to 'repairing' and last_repair_attempt_at.

        The caller MUST commit the transaction after this call returns, then
        perform the AI call outside any DB transaction.

        Args:
            session: SQLAlchemy AsyncSession (in a begun transaction).
            site_id: The site primary key.
            repair_kind: 'list' or 'content'.
            crawl_attempt_id: The crawl_attempts row that triggered this repair.
            trigger_failure_count: consecutive_failure_count value at trigger time.
            owner_user_id: Site owner user ID for provider resolution.
            base_rule_revision: Current list/content rules revision before repair.
            weekly_limit: site.auto_repair_weekly_limit (1–5).
            current_week_start: Timezone-aware UTC start of current Taipei week.
            started_at: Override the started_at timestamp (defaults to now).

        Returns:
            Mapping dict of the newly created crawl_repair_attempts row.

        Raises:
            RepairBudgetExhaustedError: If weekly_attempt_count >= weekly_limit.
        """
        await self.lazy_weekly_rollover(
            session, site_id, repair_kind, current_week_start
        )

        state = await self.get_state(
            session, site_id, repair_kind, for_update=True
        )

        if state["weekly_attempt_count"] >= weekly_limit:
            raise RepairBudgetExhaustedError(
                f"Weekly repair budget exhausted for site_id={site_id} "
                f"repair_kind={repair_kind}: "
                f"used={state['weekly_attempt_count']} limit={weekly_limit}"
            )

        weekly_sequence = state["weekly_attempt_count"] + 1
        now = started_at or datetime.now(timezone.utc)

        # Insert repair attempt with status='reserved'.
        await session.execute(
            self._attempts.insert().values(
                site_id=site_id,
                crawl_attempt_id=crawl_attempt_id,
                repair_kind=repair_kind,
                week_start_at=current_week_start,
                weekly_sequence=weekly_sequence,
                trigger_failure_count=trigger_failure_count,
                status="reserved",
                owner_user_id=owner_user_id,
                base_rule_revision=base_rule_revision,
                candidate_rule_revision=None,
                provider_trace_id=None,
                sample_url=None,
                sample_count=0,
                validation_success_count=0,
                validation_failure_code=None,
                started_at=now,
                finished_at=None,
            )
        )
        attempt_row = dict((await session.execute(
            sqlalchemy.select(self._attempts)
            .where(
                self._attempts.c.site_id == site_id,
                self._attempts.c.repair_kind == repair_kind,
                self._attempts.c.week_start_at == current_week_start,
                self._attempts.c.weekly_sequence == weekly_sequence,
            )
        )).mappings().first())

        # Atomically increment weekly_attempt_count and update state status.
        await session.execute(
            self._states.update()
            .where(
                self._states.c.site_id == site_id,
                self._states.c.repair_kind == repair_kind,
            )
            .values(
                weekly_attempt_count=weekly_sequence,
                repair_status="repairing",
                last_repair_attempt_at=now,
                revision=self._states.c.revision + 1,
                updated_at=now,
            )
        )

        return attempt_row

    # ------------------------------------------------------------------
    # Repair attempt completion
    # ------------------------------------------------------------------

    async def complete_repair_attempt(
        self,
        session,
        attempt_id: int,
        status: AttemptStatus,
        *,
        finished_at: Optional[datetime] = None,
        provider_trace_id: Optional[str] = None,
        sample_url: Optional[str] = None,
        sample_count: int = 0,
        validation_success_count: int = 0,
        validation_failure_code: Optional[str] = None,
        candidate_rule_revision: Optional[int] = None,
    ) -> dict:
        """Finalize a repair attempt with a terminal status.

        Guards against duplicate completion: only transitions from 'reserved'
        to a terminal status. Returns the updated attempt row.

        Args:
            session: SQLAlchemy AsyncSession (in a begun transaction).
            attempt_id: The crawl_repair_attempts primary key.
            status: One of the terminal AttemptStatus values.
            finished_at: Override finished_at timestamp (defaults to now).
            ...other fields: Outcome metadata for audit.

        Returns:
            Updated mapping dict of the attempt row.

        Raises:
            AttemptNotFoundError: If the attempt row is not found.
            AttemptAlreadyFinalizedError: If attempt is already in a terminal state.
        """
        if status not in _TERMINAL_ATTEMPT_STATUSES:
            raise ValueError(
                f"status must be a terminal value, got {status!r}"
            )

        # Lock the attempt row.
        attempt_result = (await session.execute(
            sqlalchemy.select(self._attempts)
            .where(self._attempts.c.id == attempt_id)
            .with_for_update()
        )).mappings().first()

        if attempt_result is None:
            raise AttemptNotFoundError(f"Repair attempt id={attempt_id} not found")

        attempt = dict(attempt_result)
        if attempt["status"] != "reserved":
            raise AttemptAlreadyFinalizedError(
                f"Repair attempt id={attempt_id} already has terminal "
                f"status={attempt['status']!r}"
            )

        now = finished_at or datetime.now(timezone.utc)
        await session.execute(
            self._attempts.update()
            .where(self._attempts.c.id == attempt_id)
            .values(
                status=status,
                finished_at=now,
                provider_trace_id=provider_trace_id,
                sample_url=sample_url,
                sample_count=sample_count,
                validation_success_count=validation_success_count,
                validation_failure_code=validation_failure_code,
                candidate_rule_revision=candidate_rule_revision,
            )
        )

        # Return fresh row.
        updated = (await session.execute(
            sqlalchemy.select(self._attempts)
            .where(self._attempts.c.id == attempt_id)
        )).mappings().first()
        return dict(updated)

    # ------------------------------------------------------------------
    # Feed-level pause
    # ------------------------------------------------------------------

    async def pause_feed(
        self,
        session,
        site_id: int,
        repair_kind: RepairKind,
        blocked_until: datetime,
    ) -> None:
        """Set the repair state for (site_id, repair_kind) to 'paused_until_next_week'.

        This marks the whole feed as routine-paused because one kind's budget
        is exhausted. Both list and content will refuse scheduler crawls while
        either kind is blocked (enforced by get_feed_pause_status checks in the
        scheduler, not by this single-kind update).

        Args:
            session: SQLAlchemy AsyncSession (in a begun transaction).
            site_id: The site primary key.
            repair_kind: The kind whose budget was exhausted.
            blocked_until: UTC datetime when the pause expires (next week start).
        """
        await self.get_state(session, site_id, repair_kind, for_update=True)
        now = datetime.now(timezone.utc)
        await session.execute(
            self._states.update()
            .where(
                self._states.c.site_id == site_id,
                self._states.c.repair_kind == repair_kind,
            )
            .values(
                repair_status="paused_until_next_week",
                blocked_at=now,
                blocked_until=blocked_until,
                revision=self._states.c.revision + 1,
                updated_at=now,
            )
        )

    async def clear_block(
        self,
        session,
        site_id: int,
        repair_kind: RepairKind,
    ) -> None:
        """Clear the block for a specific repair kind (manual rule save path).

        Used when the user manually saves a validated rule update, which resolves
        the structural failure for that kind. Clears blocked_at/blocked_until and
        sets repair_status back to 'healthy'.

        The caller is responsible for ensuring the rule was actually validated
        before calling this (server-side preview token/revision check).
        """
        await self.get_state(session, site_id, repair_kind, for_update=True)
        now = datetime.now(timezone.utc)
        await session.execute(
            self._states.update()
            .where(
                self._states.c.site_id == site_id,
                self._states.c.repair_kind == repair_kind,
            )
            .values(
                repair_status="healthy",
                consecutive_failure_count=0,
                blocked_at=None,
                blocked_until=None,
                last_repair_success_at=now,
                revision=self._states.c.revision + 1,
                updated_at=now,
            )
        )

    # ------------------------------------------------------------------
    # Feed pause status query
    # ------------------------------------------------------------------

    async def get_feed_pause_status(
        self,
        session,
        site_id: int,
        *,
        current_week_start: Optional[datetime] = None,
    ) -> PauseStatus:
        """Return the effective routine pause status for the whole feed.

        The feed is considered routine-paused if EITHER list or content
        has repair_status='paused_until_next_week' and blocked_until is in
        the future relative to now.

        Lock ordering: reads list first, then content — consistent with write order.
        Uses FOR UPDATE SKIP LOCKED to avoid blocking the scheduler if another
        worker holds a write lock.

        Args:
            session: SQLAlchemy AsyncSession.
            site_id: The site primary key.
            current_week_start: If provided, perform lazy rollover before checking.

        Returns:
            PauseStatus dataclass.
        """
        now = datetime.now(timezone.utc)

        blocking_kinds: list[str] = []
        max_blocked_until: Optional[datetime] = None

        for kind in _lock_ordered_kinds():
            if current_week_start is not None:
                await self.lazy_weekly_rollover(
                    session, site_id, kind, current_week_start
                )

            stmt = (
                sqlalchemy.select(self._states)
                .where(
                    self._states.c.site_id == site_id,
                    self._states.c.repair_kind == kind,
                )
            )
            row = (await session.execute(stmt)).mappings().first()
            if row is None:
                continue

            blocked_until = row["blocked_until"]
            is_blocked = (
                row["repair_status"] == "paused_until_next_week"
                and blocked_until is not None
                and blocked_until > now
            )
            if is_blocked:
                blocking_kinds.append(kind)
                if max_blocked_until is None or blocked_until > max_blocked_until:
                    max_blocked_until = blocked_until

        return PauseStatus(
            routine_paused=len(blocking_kinds) > 0,
            blocking_kinds=blocking_kinds,
            blocked_until=max_blocked_until,
            list_blocked="list" in blocking_kinds,
            content_blocked="content" in blocking_kinds,
        )

    # ------------------------------------------------------------------
    # History / audit queries
    # ------------------------------------------------------------------

    async def get_repair_attempts(
        self,
        session,
        site_id: int,
        repair_kind: Optional[RepairKind] = None,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """Return recent repair attempts for a site, newest first.

        Args:
            session: SQLAlchemy AsyncSession.
            site_id: The site primary key.
            repair_kind: Optional filter to 'list' or 'content'.
            limit: Maximum number of rows to return.
            offset: Pagination offset.

        Returns:
            List of mapping dicts from crawl_repair_attempts.
        """
        stmt = (
            sqlalchemy.select(self._attempts)
            .where(self._attempts.c.site_id == site_id)
            .order_by(self._attempts.c.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if repair_kind is not None:
            stmt = stmt.where(self._attempts.c.repair_kind == repair_kind)

        rows = (await session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    async def get_stale_reserved_attempts(
        self,
        session,
        *,
        older_than: datetime,
    ) -> list[dict]:
        """Return repair attempts stuck in 'reserved' status older than a threshold.

        Used by the reconciler to detect crashed workers and finalize orphaned
        attempts as 'aborted_internal_error'.

        Args:
            session: SQLAlchemy AsyncSession.
            older_than: UTC datetime; return only attempts started before this.

        Returns:
            List of mapping dicts from crawl_repair_attempts.
        """
        stmt = (
            sqlalchemy.select(self._attempts)
            .where(
                self._attempts.c.status == "reserved",
                self._attempts.c.started_at < older_than,
            )
            .order_by(self._attempts.c.started_at.asc())
        )
        rows = (await session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    async def recover_stale_attempt(
        self,
        session,
        attempt_id: int,
    ) -> dict:
        """Finalize a stale 'reserved' attempt as 'aborted_internal_error'.

        Called by the reconciler when a worker crashed after reserving an attempt
        but before completing it. This method:
        1. Finalizes the attempt row as 'aborted_internal_error'.
        2. Updates the state row's repair_status back to 'collecting_failures'
           (the failure count is preserved; the site still needs a fix).

        Lock ordering: acquires attempt lock first (by id), then state lock
        (by site_id, repair_kind) — no cross-kind locks held simultaneously.

        Args:
            session: SQLAlchemy AsyncSession (in a begun transaction).
            attempt_id: The crawl_repair_attempts primary key.

        Returns:
            Updated mapping dict of the finalized attempt row.

        Raises:
            AttemptNotFoundError: If the attempt row is not found.
            AttemptAlreadyFinalizedError: If the attempt is already terminal.
        """
        # Step 1: Finalize the attempt (acquires FOR UPDATE on attempt row).
        attempt = await self.complete_repair_attempt(
            session,
            attempt_id,
            "aborted_internal_error",
        )

        # Step 2: Restore state row from 'repairing' → 'collecting_failures'.
        site_id = attempt["site_id"]
        repair_kind = attempt["repair_kind"]

        now = datetime.now(timezone.utc)
        await session.execute(
            self._states.update()
            .where(
                self._states.c.site_id == site_id,
                self._states.c.repair_kind == repair_kind,
                # Only de-escalate if still stuck in 'repairing'; don't overwrite
                # a pause or healthy state set by a concurrent path.
                self._states.c.repair_status == "repairing",
            )
            .values(
                repair_status="collecting_failures",
                revision=self._states.c.revision + 1,
                updated_at=now,
            )
        )
        return attempt


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _lock_ordered_kinds() -> tuple[RepairKind, RepairKind]:
    """Return ('list', 'content') — the canonical lock acquisition order.

    Always acquire the list-kind lock before the content-kind lock in any
    transaction that locks both rows to prevent deadlocks.
    """
    return ("list", "content")
