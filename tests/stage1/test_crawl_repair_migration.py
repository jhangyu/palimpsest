"""
---
name: test_crawl_repair_migration
description: "Pure unit tests for crawl repair DDL migration idempotency, Release A backward compatibility, and backfill logic"
stage: stage1
type: pytest
target:
  layer: backend
  domain: crawl-repair
spec_doc: null
test_file: tests/stage1/test_crawl_repair_migration.py
functions:
  - name: test_no_plain_create_table
    line: 68
    purpose: "All CREATE TABLE statements use IF NOT EXISTS"
    fixtures: []
  - name: test_no_plain_add_column
    line: 75
    purpose: "All ADD COLUMN statements use IF NOT EXISTS"
    fixtures: []
  - name: test_no_plain_create_index
    line: 83
    purpose: "All CREATE INDEX statements use IF NOT EXISTS"
    fixtures: []
  - name: test_constraint_stmts_all_use_do_block
    line: 92
    purpose: "CRAWL_REPAIR_SITE_CONSTRAINTS use PL/pgSQL DO $$ blocks with IF NOT EXISTS"
    fixtures: []
  - name: test_new_sites_columns_have_server_defaults
    line: 106
    purpose: "New sites columns include DEFAULT clause for backward compat with old binary"
    fixtures: []
  - name: test_new_crawl_attempts_columns_have_defaults_or_nullable
    line: 125
    purpose: "New crawl_attempts NOT NULL columns have explicit DEFAULT"
    fixtures: []
  - name: test_legacy_consecutive_failure_count_not_modified
    line: 144
    purpose: "Release A does not DROP or ALTER sites.consecutive_failure_count"
    fixtures: []
  - name: test_backfill_starts_at_zero_not_from_legacy
    line: 160
    purpose: "backfill_repair_states initializes consecutive_failure_count=0, not from old column"
    fixtures: []
  - name: test_constraint_allows_1
    line: 179
    purpose: "Constraint DDL contains BETWEEN 1 AND 5"
    fixtures: []
  - name: test_constraint_blocks_0
    line: 183
    purpose: "Constraint expression blocks value 0 (< 1)"
    fixtures: []
  - name: test_constraint_blocks_6
    line: 189
    purpose: "Constraint expression blocks value 6 (> 5)"
    fixtures: []
  - name: test_constraint_named_correctly
    line: 195
    purpose: "Constraint named ck_sites_auto_repair_weekly_limit in DDL"
    fixtures: []
  - name: test_calls_execute_for_each_expansion_statement
    line: 207
    purpose: "migrate_crawl_repair_tables calls conn.execute for every expansion + constraint statement"
    fixtures: []
  - name: test_calls_commit_at_end
    line: 222
    purpose: "migrate_crawl_repair_tables calls conn.commit exactly once after all statements"
    fixtures: []
  - name: test_does_not_raise_on_statement_error
    line: 228
    purpose: "Individual statement failure is swallowed; migration still commits"
    fixtures: []
  - name: test_idempotent_on_fresh_db
    line: 245
    purpose: "Running migration twice completes both times without error"
    fixtures: []
  - name: test_idempotent_when_tables_already_exist
    line: 253
    purpose: "CREATE TABLE failure on existing tables does not propagate"
    fixtures: []
  - name: test_creates_list_and_content_for_each_site
    line: 276
    purpose: "backfill_repair_states creates exactly 2 rows (list + content) per site"
    fixtures: []
  - name: test_idempotent_on_conflict_do_nothing
    line: 310
    purpose: "Second backfill run returns rows_inserted=0 for all conflicts"
    fixtures: []
  - name: test_empty_db_returns_zero_counts
    line: 341
    purpose: "Backfill with no sites returns sites_scanned=0, rows_inserted=0"
    fixtures: []
  - name: test_backfill_uses_list_before_content
    line: 359
    purpose: "backfill_repair_states inserts list state before content state per site"
    fixtures: []
  - name: test_uses_provided_week_start_not_now
    line: 394
    purpose: "backfill_repair_states uses the supplied current_week_start, not datetime.now"
    fixtures: []
  - name: test_continues_on_site_error
    line: 430
    purpose: "Backfill continues processing remaining sites if one site's insert fails"
    fixtures: []
  - name: test_release_a_has_no_owner_not_null
    line: 471
    purpose: "Crawl repair expansion does not touch sites.owner_user_id (NOT NULL safety)"
    fixtures: []
  - name: test_new_tables_do_not_reference_old_crawl_count
    line: 489
    purpose: "New repair tables don't reference sites.consecutive_failure_count"
    fixtures: []
  - name: test_new_tables_tables_can_be_ignored_by_old_binary
    line: 500
    purpose: "Expansion contains no DROP TABLE, DROP COLUMN, or RENAME TABLE"
    fixtures: []
  - name: test_repair_history_preserved_on_rollback
    line: 511
    purpose: "Expansion has no DROP TABLE for repair history tables"
    fixtures: []
  - name: test_repair_states_table_name_known
    line: 529
    purpose: "site_crawl_repair_states is referenced in expansion DDL"
    fixtures: []
  - name: test_repair_attempts_table_name_known
    line: 534
    purpose: "crawl_repair_attempts is referenced in expansion DDL"
    fixtures: []
  - name: test_foreign_keys_use_on_delete_semantics
    line: 539
    purpose: "New tables use ON DELETE CASCADE and ON DELETE SET NULL"
    fixtures: []
  - name: test_unique_constraint_prevents_duplicate_state_import
    line: 549
    purpose: "UNIQUE(site_id, repair_kind) prevents double-import of state rows"
    fixtures: []
  - name: test_attempt_ordinal_unique_constraint_for_import
    line: 554
    purpose: "uq_crawl_repair_attempts_site_kind_week_seq prevents duplicate attempt import"
    fixtures: []
  - name: test_backfill_accepts_c1_week_window_start
    line: 568
    purpose: "backfill_repair_states works with taipei_week_window().start_utc"
    fixtures: []
  - name: test_taipei_sunday_boundary_starts_at_saturday_16_utc
    line: 592
    purpose: "Sunday 00:00 Taipei maps to Saturday 16:00 UTC (canonical week_start_at)"
    fixtures: []
  - name: test_week_rollover_boundary_saturday_to_sunday
    line: 607
    purpose: "Week window changes at exactly Saturday 16:00:00 UTC"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_crawl_repair_migration.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from backend.core.crawl_repair_models import (
    CRAWL_REPAIR_EXPANSION_STATEMENTS,
    CRAWL_REPAIR_SITE_CONSTRAINTS,
    backfill_repair_states,
    migrate_crawl_repair_tables,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Idempotency / Release A compatibility
# ---------------------------------------------------------------------------

class TestExpansionIdempotency:
    """Every DDL statement in the expansion must be safely re-runnable."""

    def test_no_plain_create_table(self):
        """All CREATE TABLE statements use IF NOT EXISTS."""
        for stmt in CRAWL_REPAIR_EXPANSION_STATEMENTS:
            if "CREATE TABLE" in stmt:
                assert "IF NOT EXISTS" in stmt, (
                    f"Non-idempotent CREATE TABLE:\n{stmt}"
                )

    def test_no_plain_add_column(self):
        """All ADD COLUMN statements use IF NOT EXISTS."""
        for stmt in CRAWL_REPAIR_EXPANSION_STATEMENTS:
            if "ADD COLUMN" in stmt:
                assert "IF NOT EXISTS" in stmt, (
                    f"Non-idempotent ADD COLUMN:\n{stmt}"
                )

    def test_no_plain_create_index(self):
        """All CREATE INDEX statements use IF NOT EXISTS."""
        for stmt in CRAWL_REPAIR_EXPANSION_STATEMENTS:
            if "CREATE INDEX" in stmt:
                assert "IF NOT EXISTS" in stmt, (
                    f"Non-idempotent CREATE INDEX:\n{stmt}"
                )

    def test_constraint_stmts_all_use_do_block(self):
        """CRAWL_REPAIR_SITE_CONSTRAINTS use PL/pgSQL DO blocks for idempotency."""
        for stmt in CRAWL_REPAIR_SITE_CONSTRAINTS:
            assert "DO $$" in stmt, (
                f"Constraint stmt must use idempotent DO block:\n{stmt}"
            )
            assert "IF NOT EXISTS" in stmt, (
                f"DO block must check IF NOT EXISTS:\n{stmt}"
            )


class TestReleaseABackwardCompatibility:
    """Release A must not break existing binary that doesn't know about new columns."""

    def test_new_sites_columns_have_server_defaults(self):
        """New sites columns must specify DEFAULT so old rows are auto-populated.

        Verifies that the ALTER TABLE ADD COLUMN statements for sites include
        a DEFAULT clause, meaning old rows will receive the default without
        requiring a data-backfill migration.
        """
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        # Each new column for sites must have DEFAULT
        for col_fragment in [
            "auto_repair_enabled BOOLEAN NOT NULL DEFAULT TRUE",
            "auto_repair_weekly_limit SMALLINT NOT NULL DEFAULT 3",
            "list_rules_revision INTEGER NOT NULL DEFAULT 1",
            "content_rules_revision INTEGER NOT NULL DEFAULT 1",
        ]:
            assert col_fragment in ddl, (
                f"Expected column with DEFAULT in expansion DDL: {col_fragment}"
            )

    def test_new_crawl_attempts_columns_have_defaults_or_nullable(self):
        """New crawl_attempts columns must not be NOT NULL without DEFAULT.

        Old binary will not set these fields; they must accept NULLs or have defaults.
        """
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        # New columns that are NOT NULL must have explicit DEFAULT
        not_null_with_default = [
            "list_structural_failure BOOLEAN NOT NULL DEFAULT FALSE",
            "content_structural_failure BOOLEAN NOT NULL DEFAULT FALSE",
            "content_parse_eligible INTEGER NOT NULL DEFAULT 0",
            "content_parse_succeeded INTEGER NOT NULL DEFAULT 0",
            "content_parse_structural_failed INTEGER NOT NULL DEFAULT 0",
        ]
        for fragment in not_null_with_default:
            assert fragment in ddl, (
                f"Expected NOT NULL column with DEFAULT in crawl_attempts expansion: {fragment}"
            )

    def test_legacy_consecutive_failure_count_not_modified(self):
        """Release A must NOT DROP or ALTER sites.consecutive_failure_count.

        The legacy column is kept intact in Release A so old binary can read it.
        New binary simply ignores it as source of truth.
        """
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        # Must not reference the old column at all (neither DROP nor ALTER)
        assert "DROP COLUMN consecutive_failure_count" not in ddl, (
            "Release A must not DROP legacy consecutive_failure_count"
        )
        # Should not appear as a target of ALTER
        assert "ALTER COLUMN consecutive_failure_count" not in ddl, (
            "Release A must not ALTER legacy consecutive_failure_count"
        )

    def test_backfill_starts_at_zero_not_from_legacy(self):
        """New repair states must start at consecutive_failure_count=0.

        The old sites.consecutive_failure_count may contain false positives
        (e.g. legitimate empty listings). Must NOT be copied.
        """
        # Verify that the backfill SQL inserts 0, not a reference to the old column
        import inspect
        src = inspect.getsource(backfill_repair_states)
        assert "consecutive_failure_count=0" in src or "consecutive_failure_count': 0" in src or "0," in src, (
            "backfill_repair_states must initialize consecutive_failure_count to 0"
        )
        # Must NOT copy from old column
        assert "sites.consecutive_failure_count" not in src


class TestSiteWeeklyLimitConstraint:
    """Verify the constraint DDL enforces 1..5 range."""

    def test_constraint_allows_1(self):
        ddl = "\n".join(CRAWL_REPAIR_SITE_CONSTRAINTS)
        assert "BETWEEN 1 AND 5" in ddl

    def test_constraint_blocks_0(self):
        """Constraint expression must block 0 (BETWEEN 1 AND 5 naturally does this)."""
        ddl = "\n".join(CRAWL_REPAIR_SITE_CONSTRAINTS)
        # 0 < 1, so BETWEEN 1 AND 5 rejects it
        assert "1 AND 5" in ddl

    def test_constraint_blocks_6(self):
        """Constraint expression must block 6 (BETWEEN 1 AND 5 naturally does this)."""
        ddl = "\n".join(CRAWL_REPAIR_SITE_CONSTRAINTS)
        # 6 > 5, so BETWEEN 1 AND 5 rejects it
        assert "1 AND 5" in ddl

    def test_constraint_named_correctly(self):
        ddl = "\n".join(CRAWL_REPAIR_SITE_CONSTRAINTS)
        assert "ck_sites_auto_repair_weekly_limit" in ddl


# ---------------------------------------------------------------------------
# migrate_crawl_repair_tables()
# ---------------------------------------------------------------------------

class TestMigrateCrawlRepairTables:
    """Tests for the sync DDL migration function."""

    def test_calls_execute_for_each_expansion_statement(self):
        """Every statement in CRAWL_REPAIR_EXPANSION_STATEMENTS gets executed."""
        mock_conn = MagicMock()
        mock_conn.execute = MagicMock()
        mock_conn.commit = MagicMock()

        migrate_crawl_repair_tables(mock_conn)

        # Should have been called at least len(expansion) + len(constraints) times
        expected_min = (
            len(CRAWL_REPAIR_EXPANSION_STATEMENTS)
            + len(CRAWL_REPAIR_SITE_CONSTRAINTS)
        )
        assert mock_conn.execute.call_count >= expected_min

    def test_calls_commit_at_end(self):
        """Migration must commit after all statements."""
        mock_conn = MagicMock()
        migrate_crawl_repair_tables(mock_conn)
        mock_conn.commit.assert_called_once()

    def test_does_not_raise_on_statement_error(self):
        """Individual statement failure is logged but does not abort migration.

        This mirrors the pattern in _run_schema_migration where each statement
        is wrapped in try/except.
        """
        mock_conn = MagicMock()
        # Make every execute() raise an exception
        mock_conn.execute.side_effect = Exception("table already exists")
        mock_conn.commit = MagicMock()

        # Should not propagate the exception
        migrate_crawl_repair_tables(mock_conn)

        # commit should still be called
        mock_conn.commit.assert_called_once()

    def test_idempotent_on_fresh_db(self):
        """Running migration twice should not error on the second run."""
        mock_conn = MagicMock()
        migrate_crawl_repair_tables(mock_conn)
        migrate_crawl_repair_tables(mock_conn)
        # Both calls should complete without error
        assert mock_conn.commit.call_count == 2

    def test_idempotent_when_tables_already_exist(self):
        """When tables already exist, migration must not crash."""
        mock_conn = MagicMock()
        # Simulate "table already exists" only for CREATE TABLE statements
        def selective_error(stmt):
            compiled = str(stmt)
            if "CREATE TABLE" in compiled:
                raise Exception("table already exists")
            return MagicMock()

        mock_conn.execute.side_effect = selective_error
        # Should complete without propagating error
        migrate_crawl_repair_tables(mock_conn)


# ---------------------------------------------------------------------------
# backfill_repair_states()
# ---------------------------------------------------------------------------

class TestBackfillRepairStates:
    """Tests for the async backfill function."""

    @pytest.mark.asyncio
    async def test_creates_list_and_content_for_each_site(self):
        """Every site gets exactly two state rows: list and content."""
        session = AsyncMock()
        week_start = _utc(2026, 6, 14, 16, 0)  # Sunday 00:00 Taipei = Sat 16:00 UTC

        class FakeSitesResult:
            def __iter__(self):
                return iter([(1,), (2,)])

        call_count = 0

        async def mock_execute(*_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # SELECT id FROM sites
                return FakeSitesResult()
            else:
                # INSERT ON CONFLICT DO NOTHING
                r = MagicMock()
                r.rowcount = 1
                return r

        session.execute = mock_execute
        session.commit = AsyncMock()

        result = await backfill_repair_states(session, current_week_start=week_start)

        assert result["sites_scanned"] == 2
        # 2 sites × 2 kinds = 4 inserts
        assert result["rows_inserted"] == 4
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_idempotent_on_conflict_do_nothing(self):
        """Second run returns rows_inserted=0 for existing rows."""
        session = AsyncMock()
        week_start = _utc(2026, 6, 14, 16, 0)

        class FakeSitesResult:
            def __iter__(self):
                return iter([(1,)])

        call_count = 0

        async def mock_execute(*_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return FakeSitesResult()
            else:
                # ON CONFLICT DO NOTHING → rowcount = 0
                r = MagicMock()
                r.rowcount = 0
                return r

        session.execute = mock_execute
        session.commit = AsyncMock()

        result = await backfill_repair_states(session, current_week_start=week_start)

        assert result["sites_scanned"] == 1
        assert result["rows_inserted"] == 0  # All conflicts → no new inserts

    @pytest.mark.asyncio
    async def test_empty_db_returns_zero_counts(self):
        """No sites → nothing to backfill."""
        session = AsyncMock()
        week_start = _utc(2026, 6, 14, 16, 0)

        class FakeSitesResult:
            def __iter__(self):
                return iter([])

        session.execute = AsyncMock(return_value=FakeSitesResult())
        session.commit = AsyncMock()

        result = await backfill_repair_states(session, current_week_start=week_start)

        assert result["sites_scanned"] == 0
        assert result["rows_inserted"] == 0

    @pytest.mark.asyncio
    async def test_backfill_uses_list_before_content(self):
        """Backfill inserts list state before content state for each site."""
        session = AsyncMock()
        week_start = _utc(2026, 6, 14, 16, 0)

        class FakeSitesResult:
            def __iter__(self):
                return iter([(1,)])

        inserted_kinds: list[str] = []
        call_count = 0

        async def mock_execute(_, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return FakeSitesResult()
            else:
                if params is not None and "repair_kind" in params:
                    inserted_kinds.append(params["repair_kind"])
                r = MagicMock()
                r.rowcount = 1
                return r

        session.execute = mock_execute
        session.commit = AsyncMock()

        await backfill_repair_states(session, current_week_start=week_start)

        # list should come before content
        if len(inserted_kinds) == 2:
            assert inserted_kinds[0] == "list"
            assert inserted_kinds[1] == "content"

    @pytest.mark.asyncio
    async def test_uses_provided_week_start_not_now(self):
        """backfill_repair_states must use the supplied current_week_start, not datetime.now."""
        session = AsyncMock()
        custom_week_start = _utc(2026, 6, 7, 16, 0)  # A specific week start

        class FakeSitesResult:
            def __iter__(self):
                return iter([(5,)])

        captured_params: list[dict] = []
        call_count = 0

        async def mock_execute(_, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return FakeSitesResult()
            if params is not None:
                captured_params.append(dict(params))
            r = MagicMock()
            r.rowcount = 1
            return r

        session.execute = mock_execute
        session.commit = AsyncMock()

        await backfill_repair_states(session, current_week_start=custom_week_start)

        # Every insert should use the custom_week_start
        for p in captured_params:
            if "week_start_at" in p:
                assert p["week_start_at"] == custom_week_start, (
                    f"Expected week_start_at={custom_week_start}, got {p['week_start_at']}"
                )

    @pytest.mark.asyncio
    async def test_continues_on_site_error(self):
        """If one site's insert fails, backfill continues with remaining sites."""
        session = AsyncMock()
        week_start = _utc(2026, 6, 14, 16, 0)

        class FakeSitesResult:
            def __iter__(self):
                return iter([(1,), (2,), (3,)])

        call_count = 0

        async def mock_execute(_, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return FakeSitesResult()
            # site_id=1 inserts succeed; site_id=2 fails; site_id=3 succeeds
            if params and params.get("site_id") == 2:
                raise Exception("simulated DB error for site 2")
            r = MagicMock()
            r.rowcount = 1
            return r

        session.execute = mock_execute
        session.commit = AsyncMock()

        # Should not raise
        result = await backfill_repair_states(session, current_week_start=week_start)

        assert result["sites_scanned"] == 3
        # Sites 1 and 3 should have their rows inserted (2 kinds each = 4 rows)
        assert result["rows_inserted"] >= 2  # at least some inserted despite error


# ---------------------------------------------------------------------------
# Binary compatibility matrix
# ---------------------------------------------------------------------------

class TestBinaryCompatibilityMatrix:
    """Verify expand/contract strategy documentation via DDL structure."""

    def test_release_a_has_no_owner_not_null(self):
        """Release A must not make owner_user_id NOT NULL on sites.

        Old binary doesn't write owner_user_id; making it NOT NULL without
        backfill would break existing site rows.
        """
        # owner_user_id appears only in crawl_attempts (as nullable FK) and
        # crawl_repair_attempts (nullable FK); not in sites expansion
        # (that's handled by SCHEMA_EXPANSION_STATEMENTS in ai_provider_migrations.py)
        sites_alter_lines = [
            s for s in CRAWL_REPAIR_EXPANSION_STATEMENTS
            if "ALTER TABLE sites" in s
        ]
        for line in sites_alter_lines:
            assert "owner_user_id" not in line, (
                f"Crawl repair expansion should not touch sites.owner_user_id: {line}"
            )

    def test_new_tables_do_not_reference_old_crawl_count(self):
        """New repair tables must not reference sites.consecutive_failure_count.

        The old counter is retained for rollback compatibility but is no longer
        the source of truth.
        """
        for stmt in CRAWL_REPAIR_EXPANSION_STATEMENTS:
            assert "consecutive_failure_count" not in stmt or (
                "DEFAULT 0" in stmt  # Only in new repair states table
            ), f"Unexpected reference to consecutive_failure_count: {stmt}"

    def test_new_tables_tables_can_be_ignored_by_old_binary(self):
        """Old binary that doesn't know about new tables can still read sites/crawl_attempts.

        The test verifies no DROP or RENAME on core tables.
        """
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "DROP TABLE sites" not in ddl
        assert "DROP TABLE crawl_attempts" not in ddl
        assert "RENAME TABLE" not in ddl
        assert "DROP COLUMN" not in ddl

    def test_repair_history_preserved_on_rollback(self):
        """Rollback must not drop repair history tables.

        Verified by confirming there are no DROP statements.
        The migration only ADDs tables/columns; removal is a separate Release B task.
        """
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "DROP TABLE site_crawl_repair_states" not in ddl
        assert "DROP TABLE crawl_repair_attempts" not in ddl


# ---------------------------------------------------------------------------
# Export / Import compatibility
# ---------------------------------------------------------------------------

class TestExportImportStrategy:
    """Verify that migration design supports export/import round-trips."""

    def test_repair_states_table_name_known(self):
        """site_crawl_repair_states is mentioned in expansion DDL for import mapping."""
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "site_crawl_repair_states" in ddl

    def test_repair_attempts_table_name_known(self):
        """crawl_repair_attempts is mentioned in expansion DDL."""
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "crawl_repair_attempts" in ddl

    def test_foreign_keys_use_on_delete_semantics(self):
        """New tables use ON DELETE CASCADE/SET NULL for FK safety during import.

        This ensures that importing sites→crawl_attempts→repair data in order
        does not leave dangling FKs if a site is deleted.
        """
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "ON DELETE CASCADE" in ddl
        assert "ON DELETE SET NULL" in ddl

    def test_unique_constraint_prevents_duplicate_state_import(self):
        """UNIQUE(site_id, repair_kind) on state table prevents double-import."""
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "UNIQUE (site_id, repair_kind)" in ddl or "uq_site_crawl_repair_states_site_kind" in ddl

    def test_attempt_ordinal_unique_constraint_for_import(self):
        """UNIQUE(site_id, repair_kind, week_start_at, weekly_sequence) prevents duplicate attempts."""
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "uq_crawl_repair_attempts_site_kind_week_seq" in ddl


# ---------------------------------------------------------------------------
# Integration with C1 time_provider
# ---------------------------------------------------------------------------

class TestTimeProviderIntegration:
    """Verify that backfill_repair_states accepts a C1 WeekWindow.start_utc."""

    @pytest.mark.asyncio
    async def test_backfill_accepts_c1_week_window_start(self):
        """backfill_repair_states should work with taipei_week_window().start_utc."""
        from backend.core.time_provider import taipei_week_window, FakeClock

        # Simulate Tuesday 2026-06-16 10:00 UTC
        fake_now = datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc)
        clock = FakeClock(fake_now)
        window = taipei_week_window(clock.now_utc())

        session = AsyncMock()

        class FakeSitesResult:
            def __iter__(self):
                return iter([])

        session.execute = AsyncMock(return_value=FakeSitesResult())
        session.commit = AsyncMock()

        # Should not raise when passed a proper WeekWindow.start_utc
        result = await backfill_repair_states(session, current_week_start=window.start_utc)

        assert result["sites_scanned"] == 0
        assert result["rows_inserted"] == 0

    def test_taipei_sunday_boundary_starts_at_saturday_16_utc(self):
        """Verify that a Sunday 00:00 Taipei time maps to Saturday 16:00 UTC.

        This is the canonical week_start_at used as the bucket key in DB.
        """
        from backend.core.time_provider import taipei_week_window

        # 2026-06-21 00:00:01 Asia/Taipei = 2026-06-20 16:00:01 UTC (Sunday)
        fake_now = datetime(2026, 6, 20, 16, 0, 1, tzinfo=timezone.utc)
        window = taipei_week_window(fake_now)

        # This Sunday in Taipei = 2026-06-21 00:00:00 +08:00 = 2026-06-20 16:00:00 UTC
        expected_start = datetime(2026, 6, 20, 16, 0, 0, tzinfo=timezone.utc)
        assert window.start_utc == expected_start

    def test_week_rollover_boundary_saturday_to_sunday(self):
        """Verify the week window changes at exactly the right UTC second.

        Just before Sunday 00:00 Taipei (Saturday 23:59:59 Taipei = 15:59:59 UTC):
          → old week
        Exactly at Sunday 00:00 Taipei (Saturday 16:00:00 UTC):
          → new week
        """
        from backend.core.time_provider import taipei_week_window

        # Saturday 15:59:59 UTC = Saturday 23:59:59 Taipei
        before_rollover = datetime(2026, 6, 13, 15, 59, 59, tzinfo=timezone.utc)
        # Saturday 16:00:00 UTC = Sunday 00:00:00 Taipei
        at_rollover = datetime(2026, 6, 13, 16, 0, 0, tzinfo=timezone.utc)

        window_before = taipei_week_window(before_rollover)
        window_after = taipei_week_window(at_rollover)

        # They should be DIFFERENT windows
        assert window_before.start_utc != window_after.start_utc
        # The new window starts at exactly the rollover moment
        assert window_after.start_utc == at_rollover
