"""
---
name: test_crawl_repair_models
description: "Unit tests for crawl repair SQLAlchemy table definitions, DDL expansion statements, and Pydantic schemas"
stage: stage1
type: pytest
target:
  layer: backend
  domain: crawl-repair
spec_doc: null
test_file: tests/stage1/test_crawl_repair_models.py
functions:
  - name: test_returns_crawl_repair_tables_dataclass
    line: 56
    purpose: "define_crawl_repair_tables returns a CrawlRepairTables dataclass"
    fixtures: []
  - name: test_site_crawl_repair_states_has_expected_columns
    line: 70
    purpose: "site_crawl_repair_states table includes all required column names"
    fixtures: []
  - name: test_crawl_repair_attempts_has_expected_columns
    line: 92
    purpose: "crawl_repair_attempts table includes all required column names"
    fixtures: []
  - name: test_site_crawl_repair_states_unique_constraint
    line: 115
    purpose: "uq_site_crawl_repair_states_site_kind unique constraint is declared"
    fixtures: []
  - name: test_crawl_repair_attempts_unique_constraint
    line: 127
    purpose: "uq_crawl_repair_attempts_site_kind_week_seq unique constraint is declared"
    fixtures: []
  - name: test_check_constraints_present
    line: 139
    purpose: "Key check constraints (repair_kind, failure_count, weekly_attempt_count, repair_status) present"
    fixtures: []
  - name: test_is_non_empty_tuple
    line: 163
    purpose: "CRAWL_REPAIR_EXPANSION_STATEMENTS is a non-empty tuple"
    fixtures: []
  - name: test_creates_site_crawl_repair_states_table
    line: 167
    purpose: "Expansion DDL contains CREATE TABLE IF NOT EXISTS site_crawl_repair_states"
    fixtures: []
  - name: test_creates_crawl_repair_attempts_table
    line: 171
    purpose: "Expansion DDL contains CREATE TABLE IF NOT EXISTS crawl_repair_attempts"
    fixtures: []
  - name: test_release_a_sites_columns_nullable_or_with_default
    line: 175
    purpose: "New sites columns have server-side DEFAULT in expansion DDL"
    fixtures: []
  - name: test_crawl_attempts_new_columns_added
    line: 188
    purpose: "Expected ALTER TABLE ADD COLUMN statements present for crawl_attempts"
    fixtures: []
  - name: test_all_add_column_statements_are_idempotent
    line: 196
    purpose: "All ADD COLUMN statements use IF NOT EXISTS"
    fixtures: []
  - name: test_all_create_table_statements_are_idempotent
    line: 204
    purpose: "All CREATE TABLE statements use IF NOT EXISTS"
    fixtures: []
  - name: test_all_create_index_statements_are_idempotent
    line: 212
    purpose: "All CREATE INDEX statements use IF NOT EXISTS"
    fixtures: []
  - name: test_repair_kind_check_constraint_in_table_ddl
    line: 220
    purpose: "DDL contains repair_kind IN ('list', 'content') check"
    fixtures: []
  - name: test_status_check_constraint_in_attempts_ddl
    line: 224
    purpose: "DDL contains 'reserved' and 'applied' in status check constraint"
    fixtures: []
  - name: test_state_repair_status_check_constraint
    line: 229
    purpose: "DDL contains 'healthy' and 'paused_until_next_week' in repair_status check"
    fixtures: []
  - name: test_contains_weekly_limit_constraint
    line: 238
    purpose: "CRAWL_REPAIR_SITE_CONSTRAINTS contains auto_repair_weekly_limit BETWEEN 1 AND 5"
    fixtures: []
  - name: test_contains_list_rules_revision_constraint
    line: 242
    purpose: "CRAWL_REPAIR_SITE_CONSTRAINTS contains list_rules_revision >= 1"
    fixtures: []
  - name: test_contains_content_rules_revision_constraint
    line: 246
    purpose: "CRAWL_REPAIR_SITE_CONSTRAINTS contains content_rules_revision >= 1"
    fixtures: []
  - name: test_all_constraints_are_idempotent_via_do_block
    line: 250
    purpose: "All site constraint statements use idempotent DO $$ ... $$ block with IF NOT EXISTS"
    fixtures: []
  - name: test_reserved_is_not_terminal
    line: 264
    purpose: "'reserved' is not in _TERMINAL_ATTEMPT_STATUSES"
    fixtures: []
  - name: test_applied_is_terminal
    line: 267
    purpose: "'applied' is in _TERMINAL_ATTEMPT_STATUSES"
    fixtures: []
  - name: test_all_expected_terminal_statuses_present
    line: 270
    purpose: "_TERMINAL_ATTEMPT_STATUSES matches the expected set of 7 statuses"
    fixtures: []
  - name: test_valid_weekly_limits
    line: 291
    purpose: "SiteAutoRepairConfigSchema accepts weekly limits 1-5"
    fixtures: []
  - name: test_default_weekly_limit_is_3
    line: 295
    purpose: "Default auto_repair_weekly_limit is 3"
    fixtures: []
  - name: test_default_auto_repair_enabled_is_true
    line: 299
    purpose: "Default auto_repair_enabled is True"
    fixtures: []
  - name: test_invalid_weekly_limits_rejected
    line: 303
    purpose: "Limits outside 1-5 raise ValidationError with 'between 1 and 5' message"
    fixtures: []
  - name: test_limit_0_explicitly_rejected
    line: 309
    purpose: "Limit 0 raises ValidationError (use enabled=False to disable)"
    fixtures: []
  - name: test_limit_6_explicitly_rejected
    line: 314
    purpose: "Limit 6 exceeds maximum and raises ValidationError"
    fixtures: []
  - name: test_auto_repair_disabled
    line: 319
    purpose: "auto_repair_enabled=False is accepted alongside any valid limit"
    fixtures: []
  - name: test_boundary_limit_1
    line: 323
    purpose: "Boundary value 1 is accepted"
    fixtures: []
  - name: test_boundary_limit_5
    line: 327
    purpose: "Boundary value 5 is accepted"
    fixtures: []
  - name: test_valid_construction
    line: 335
    purpose: "RepairKindStatusSchema stores consecutive_failures and weekly_attempts_used"
    fixtures: []
  - name: test_optional_fields_default_to_none
    line: 347
    purpose: "Optional RepairKindStatusSchema fields default to None"
    fixtures: []
  - name: test_valid_construction
    line: 379
    purpose: "FeedRepairStatusSchema stores timezone, routine_paused, blocking_kinds"
    fixtures: []
  - name: test_paused_with_blocking_kind
    line: 394
    purpose: "FeedRepairStatusSchema captures paused=True with blocking_kinds=['list']"
    fixtures: []
  - name: test_not_paused
    line: 412
    purpose: "PauseStatus with routine_paused=False has blocked_until=None"
    fixtures: []
  - name: test_paused_by_list
    line: 422
    purpose: "PauseStatus blocked by list sets list_blocked=True and blocked_until"
    fixtures: []
  - name: test_paused_by_content
    line: 437
    purpose: "PauseStatus blocked by content includes 'content' in blocking_kinds"
    fixtures: []
  - name: test_valid_reserved_attempt
    line: 453
    purpose: "RepairAttemptSchema with status='reserved' has finished_at=None"
    fixtures: []
  - name: test_applied_attempt_with_all_fields
    line: 473
    purpose: "RepairAttemptSchema stores all fields for an 'applied' attempt"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_crawl_repair_models.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.core.crawl_repair_models import (
    CRAWL_REPAIR_EXPANSION_STATEMENTS,
    CRAWL_REPAIR_SITE_CONSTRAINTS,
    CrawlRepairTables,
    FeedRepairStatusSchema,
    PauseStatus,
    RepairAttemptSchema,
    RepairKindStatusSchema,
    SiteAutoRepairConfigSchema,
    _TERMINAL_ATTEMPT_STATUSES,
    define_crawl_repair_tables,
)


# ---------------------------------------------------------------------------
# Table definition structure
# ---------------------------------------------------------------------------

class TestDefineRepairTables:
    """Tests for define_crawl_repair_tables()."""

    def test_returns_crawl_repair_tables_dataclass(self):
        import sqlalchemy
        meta = sqlalchemy.MetaData()
        # Need base tables to satisfy FK references
        sqlalchemy.Table("sites", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
        sqlalchemy.Table("crawl_attempts", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
        sqlalchemy.Table("users", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))

        tables = define_crawl_repair_tables(meta)

        assert isinstance(tables, CrawlRepairTables)
        assert tables.site_crawl_repair_states is not None
        assert tables.crawl_repair_attempts is not None

    def test_site_crawl_repair_states_has_expected_columns(self):
        import sqlalchemy
        meta = sqlalchemy.MetaData()
        sqlalchemy.Table("sites", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
        sqlalchemy.Table("crawl_attempts", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
        sqlalchemy.Table("users", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))

        tables = define_crawl_repair_tables(meta)
        col_names = {c.name for c in tables.site_crawl_repair_states.columns}

        required_columns = {
            "id", "site_id", "repair_kind", "consecutive_failure_count",
            "week_start_at", "weekly_attempt_count",
            "blocked_at", "blocked_until",
            "last_outcome", "last_failure_reason", "last_failure_at",
            "last_success_at", "last_repair_attempt_at", "last_repair_success_at",
            "repair_status", "revision", "created_at", "updated_at",
        }
        assert required_columns.issubset(col_names), (
            f"Missing columns: {required_columns - col_names}"
        )

    def test_crawl_repair_attempts_has_expected_columns(self):
        import sqlalchemy
        meta = sqlalchemy.MetaData()
        sqlalchemy.Table("sites", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
        sqlalchemy.Table("crawl_attempts", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
        sqlalchemy.Table("users", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))

        tables = define_crawl_repair_tables(meta)
        col_names = {c.name for c in tables.crawl_repair_attempts.columns}

        required_columns = {
            "id", "site_id", "crawl_attempt_id", "repair_kind",
            "week_start_at", "weekly_sequence",
            "trigger_failure_count", "status", "owner_user_id",
            "base_rule_revision", "candidate_rule_revision",
            "provider_trace_id", "sample_url",
            "sample_count", "validation_success_count", "validation_failure_code",
            "started_at", "finished_at",
        }
        assert required_columns.issubset(col_names), (
            f"Missing columns: {required_columns - col_names}"
        )

    def test_site_crawl_repair_states_unique_constraint(self):
        import sqlalchemy
        meta = sqlalchemy.MetaData()
        sqlalchemy.Table("sites", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
        sqlalchemy.Table("crawl_attempts", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
        sqlalchemy.Table("users", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))

        tables = define_crawl_repair_tables(meta)
        constraints = {c.name for c in tables.site_crawl_repair_states.constraints}

        assert "uq_site_crawl_repair_states_site_kind" in constraints

    def test_crawl_repair_attempts_unique_constraint(self):
        import sqlalchemy
        meta = sqlalchemy.MetaData()
        sqlalchemy.Table("sites", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
        sqlalchemy.Table("crawl_attempts", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
        sqlalchemy.Table("users", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))

        tables = define_crawl_repair_tables(meta)
        constraints = {c.name for c in tables.crawl_repair_attempts.constraints}

        assert "uq_crawl_repair_attempts_site_kind_week_seq" in constraints

    def test_check_constraints_present(self):
        import sqlalchemy
        meta = sqlalchemy.MetaData()
        sqlalchemy.Table("sites", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
        sqlalchemy.Table("crawl_attempts", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))
        sqlalchemy.Table("users", meta, sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True))

        tables = define_crawl_repair_tables(meta)
        constraint_names = {c.name for c in tables.site_crawl_repair_states.constraints}

        # Key check constraints
        assert "ck_site_crawl_repair_states_repair_kind" in constraint_names
        assert "ck_site_crawl_repair_states_consecutive_failure_count" in constraint_names
        assert "ck_site_crawl_repair_states_weekly_attempt_count" in constraint_names
        assert "ck_site_crawl_repair_states_repair_status" in constraint_names


# ---------------------------------------------------------------------------
# DDL expansion statements
# ---------------------------------------------------------------------------

class TestExpansionStatements:
    """Tests for CRAWL_REPAIR_EXPANSION_STATEMENTS."""

    def test_is_non_empty_tuple(self):
        assert isinstance(CRAWL_REPAIR_EXPANSION_STATEMENTS, tuple)
        assert len(CRAWL_REPAIR_EXPANSION_STATEMENTS) > 0

    def test_creates_site_crawl_repair_states_table(self):
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "CREATE TABLE IF NOT EXISTS site_crawl_repair_states" in ddl

    def test_creates_crawl_repair_attempts_table(self):
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "CREATE TABLE IF NOT EXISTS crawl_repair_attempts" in ddl

    def test_release_a_sites_columns_nullable_or_with_default(self):
        """Release A expand: new sites columns must have DEFAULT (not NOT NULL without default)
        so old binary can coexist without writing them."""
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        # auto_repair_enabled: BOOLEAN NOT NULL DEFAULT TRUE is OK (has default)
        assert "auto_repair_enabled BOOLEAN NOT NULL DEFAULT TRUE" in ddl
        # auto_repair_weekly_limit: SMALLINT NOT NULL DEFAULT 3 is OK
        assert "auto_repair_weekly_limit SMALLINT NOT NULL DEFAULT 3" in ddl
        # list_rules_revision: INTEGER NOT NULL DEFAULT 1 is OK
        assert "list_rules_revision INTEGER NOT NULL DEFAULT 1" in ddl
        # content_rules_revision: INTEGER NOT NULL DEFAULT 1 is OK
        assert "content_rules_revision INTEGER NOT NULL DEFAULT 1" in ddl

    def test_crawl_attempts_new_columns_added(self):
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS list_outcome" in ddl
        assert "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS content_outcome" in ddl
        assert "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS list_structural_failure" in ddl
        assert "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS content_structural_failure" in ddl
        assert "ALTER TABLE crawl_attempts ADD COLUMN IF NOT EXISTS auto_repair_attempt_id" in ddl

    def test_all_add_column_statements_are_idempotent(self):
        """Verify all ALTER TABLE ADD COLUMN use IF NOT EXISTS."""
        for stmt in CRAWL_REPAIR_EXPANSION_STATEMENTS:
            if "ALTER TABLE" in stmt and "ADD COLUMN" in stmt:
                assert "IF NOT EXISTS" in stmt, (
                    f"ALTER TABLE ADD COLUMN statement is not idempotent:\n{stmt}"
                )

    def test_all_create_table_statements_are_idempotent(self):
        """Verify all CREATE TABLE use IF NOT EXISTS."""
        for stmt in CRAWL_REPAIR_EXPANSION_STATEMENTS:
            if "CREATE TABLE" in stmt:
                assert "IF NOT EXISTS" in stmt, (
                    f"CREATE TABLE statement is not idempotent:\n{stmt}"
                )

    def test_all_create_index_statements_are_idempotent(self):
        """Verify all CREATE INDEX use IF NOT EXISTS."""
        for stmt in CRAWL_REPAIR_EXPANSION_STATEMENTS:
            if "CREATE INDEX" in stmt:
                assert "IF NOT EXISTS" in stmt, (
                    f"CREATE INDEX statement is not idempotent:\n{stmt}"
                )

    def test_repair_kind_check_constraint_in_table_ddl(self):
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "repair_kind IN ('list', 'content')" in ddl

    def test_status_check_constraint_in_attempts_ddl(self):
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "'reserved'" in ddl
        assert "'applied'" in ddl

    def test_state_repair_status_check_constraint(self):
        ddl = "\n".join(CRAWL_REPAIR_EXPANSION_STATEMENTS)
        assert "'healthy'" in ddl
        assert "'paused_until_next_week'" in ddl


class TestSiteConstraintStatements:
    """Tests for CRAWL_REPAIR_SITE_CONSTRAINTS."""

    def test_contains_weekly_limit_constraint(self):
        ddl = "\n".join(CRAWL_REPAIR_SITE_CONSTRAINTS)
        assert "auto_repair_weekly_limit BETWEEN 1 AND 5" in ddl

    def test_contains_list_rules_revision_constraint(self):
        ddl = "\n".join(CRAWL_REPAIR_SITE_CONSTRAINTS)
        assert "list_rules_revision >= 1" in ddl

    def test_contains_content_rules_revision_constraint(self):
        ddl = "\n".join(CRAWL_REPAIR_SITE_CONSTRAINTS)
        assert "content_rules_revision >= 1" in ddl

    def test_all_constraints_are_idempotent_via_do_block(self):
        """Verify constraints use DO $$ ... $$ blocks to be idempotent."""
        for stmt in CRAWL_REPAIR_SITE_CONSTRAINTS:
            assert "DO $$" in stmt, (
                f"Constraint stmt should use idempotent DO block:\n{stmt}"
            )
            assert "IF NOT EXISTS" in stmt


# ---------------------------------------------------------------------------
# Terminal attempt statuses
# ---------------------------------------------------------------------------

class TestTerminalAttemptStatuses:
    def test_reserved_is_not_terminal(self):
        assert "reserved" not in _TERMINAL_ATTEMPT_STATUSES

    def test_applied_is_terminal(self):
        assert "applied" in _TERMINAL_ATTEMPT_STATUSES

    def test_all_expected_terminal_statuses_present(self):
        expected = {
            "provider_failed",
            "no_provider_available",
            "candidate_schema_invalid",
            "candidate_validation_failed",
            "stale_rule_revision",
            "applied",
            "aborted_internal_error",
        }
        assert expected == _TERMINAL_ATTEMPT_STATUSES


# ---------------------------------------------------------------------------
# Pydantic schema validation
# ---------------------------------------------------------------------------

class TestSiteAutoRepairConfigSchema:
    """Tests for SiteAutoRepairConfigSchema validation."""

    @pytest.mark.parametrize("limit", [1, 2, 3, 4, 5])
    def test_valid_weekly_limits(self, limit: int):
        config = SiteAutoRepairConfigSchema(auto_repair_weekly_limit=limit)
        assert config.auto_repair_weekly_limit == limit

    def test_default_weekly_limit_is_3(self):
        config = SiteAutoRepairConfigSchema()
        assert config.auto_repair_weekly_limit == 3

    def test_default_auto_repair_enabled_is_true(self):
        config = SiteAutoRepairConfigSchema()
        assert config.auto_repair_enabled is True

    @pytest.mark.parametrize("limit", [0, -1, 6, 10, 100])
    def test_invalid_weekly_limits_rejected(self, limit: int):
        with pytest.raises(ValidationError) as exc_info:
            SiteAutoRepairConfigSchema(auto_repair_weekly_limit=limit)
        assert "between 1 and 5" in str(exc_info.value).lower()

    def test_limit_0_explicitly_rejected(self):
        """Limit 0 is not valid — use auto_repair_enabled=False to disable."""
        with pytest.raises(ValidationError):
            SiteAutoRepairConfigSchema(auto_repair_weekly_limit=0)

    def test_limit_6_explicitly_rejected(self):
        """Limit 6 exceeds maximum."""
        with pytest.raises(ValidationError):
            SiteAutoRepairConfigSchema(auto_repair_weekly_limit=6)

    def test_auto_repair_disabled(self):
        config = SiteAutoRepairConfigSchema(auto_repair_enabled=False, auto_repair_weekly_limit=3)
        assert config.auto_repair_enabled is False

    def test_boundary_limit_1(self):
        config = SiteAutoRepairConfigSchema(auto_repair_weekly_limit=1)
        assert config.auto_repair_weekly_limit == 1

    def test_boundary_limit_5(self):
        config = SiteAutoRepairConfigSchema(auto_repair_weekly_limit=5)
        assert config.auto_repair_weekly_limit == 5


class TestRepairKindStatusSchema:
    """Tests for RepairKindStatusSchema."""

    def test_valid_construction(self):
        status = RepairKindStatusSchema(
            consecutive_failures=2,
            weekly_attempts_used=1,
            weekly_attempts_limit=3,
            blocked=False,
            repair_status="collecting_failures",
            last_outcome="structural_failure",
        )
        assert status.consecutive_failures == 2
        assert status.weekly_attempts_used == 1

    def test_optional_fields_default_to_none(self):
        status = RepairKindStatusSchema(
            consecutive_failures=0,
            weekly_attempts_used=0,
            weekly_attempts_limit=3,
            blocked=False,
            repair_status="healthy",
        )
        assert status.blocked_until is None
        assert status.last_outcome is None
        assert status.last_failure_reason is None


def _make_kind_status(
    consecutive_failures: int = 0,
    weekly_attempts_used: int = 0,
    weekly_attempts_limit: int = 3,
    blocked: bool = False,
    repair_status: str = "healthy",
) -> RepairKindStatusSchema:
    return RepairKindStatusSchema(
        consecutive_failures=consecutive_failures,
        weekly_attempts_used=weekly_attempts_used,
        weekly_attempts_limit=weekly_attempts_limit,
        blocked=blocked,
        repair_status=repair_status,
    )


class TestFeedRepairStatusSchema:
    """Tests for FeedRepairStatusSchema."""

    def test_valid_construction(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        status = FeedRepairStatusSchema(
            week_start_at=now,
            next_reset_at=now,
            routine_paused=False,
            blocking_kinds=[],
            list=_make_kind_status(),
            content=_make_kind_status(),
        )
        assert status.timezone == "Asia/Taipei"
        assert status.routine_paused is False
        assert status.blocking_kinds == []

    def test_paused_with_blocking_kind(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        status = FeedRepairStatusSchema(
            week_start_at=now,
            next_reset_at=now,
            routine_paused=True,
            blocking_kinds=["list"],
            list=_make_kind_status(blocked=True, repair_status="paused_until_next_week"),
            content=_make_kind_status(),
        )
        assert status.routine_paused is True
        assert "list" in status.blocking_kinds


class TestPauseStatus:
    """Tests for PauseStatus model."""

    def test_not_paused(self):
        status = PauseStatus(
            routine_paused=False,
            blocking_kinds=[],
            list_blocked=False,
            content_blocked=False,
        )
        assert status.routine_paused is False
        assert status.blocked_until is None

    def test_paused_by_list(self):
        from datetime import datetime, timezone
        until = datetime(2026, 6, 21, 16, 0, 0, tzinfo=timezone.utc)
        status = PauseStatus(
            routine_paused=True,
            blocking_kinds=["list"],
            blocked_until=until,
            list_blocked=True,
            content_blocked=False,
        )
        assert status.routine_paused is True
        assert status.list_blocked is True
        assert status.content_blocked is False
        assert status.blocked_until == until

    def test_paused_by_content(self):
        from datetime import datetime, timezone
        until = datetime(2026, 6, 21, 16, 0, 0, tzinfo=timezone.utc)
        status = PauseStatus(
            routine_paused=True,
            blocking_kinds=["content"],
            blocked_until=until,
            list_blocked=False,
            content_blocked=True,
        )
        assert "content" in status.blocking_kinds


class TestRepairAttemptSchema:
    """Tests for RepairAttemptSchema."""

    def test_valid_reserved_attempt(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        attempt = RepairAttemptSchema(
            id=1,
            site_id=10,
            crawl_attempt_id=None,
            repair_kind="list",
            week_start_at=now,
            weekly_sequence=1,
            trigger_failure_count=3,
            status="reserved",
            base_rule_revision=5,
            sample_count=0,
            validation_success_count=0,
            started_at=now,
        )
        assert attempt.status == "reserved"
        assert attempt.finished_at is None

    def test_applied_attempt_with_all_fields(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        attempt = RepairAttemptSchema(
            id=2,
            site_id=10,
            crawl_attempt_id=42,
            repair_kind="content",
            week_start_at=now,
            weekly_sequence=2,
            trigger_failure_count=3,
            status="applied",
            base_rule_revision=5,
            candidate_rule_revision=6,
            provider_trace_id="trace_abc123",
            sample_url="https://example.com/article/1",
            sample_count=3,
            validation_success_count=2,
            started_at=now,
            finished_at=now,
        )
        assert attempt.status == "applied"
        assert attempt.candidate_rule_revision == 6
        assert attempt.validation_success_count == 2
