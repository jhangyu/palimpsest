"""
---
name: test-ai-provider-migrations
description: "AI provider schema migration tests"
type: test-suite
target:
  layer: backend
  domain: llm
run:
  command: "PYTHONPATH=.:backend:tests python -m pytest tests/test_ai_provider_migrations.py -v"
  env: {}
  prerequisites:
    - "Python deps installed"
expected:
  pass: all
  output: "PASS/FAIL per migration test case"
---

AI provider schema migration tests.
"""

from __future__ import annotations

import os

import pytest
import sqlalchemy

from backend.core.ai_provider_migrations import (
    OWNER_RELEASE_B_CONTRACT_STATEMENTS,
    SCHEMA_EXPANSION_STATEMENTS,
    OwnerBackfillStatus,
    OwnerContractPreconditionError,
    backfill_existing_user_secret_keys,
    backfill_site_owners,
    bootstrap_user_secret_key,
    define_ai_provider_tables,
    validate_owner_release_b_preconditions,
)
from backend.core.llm.key_backends import FileKeyEncryptionBackend


class FakeResult:
    def __init__(self, rows=None, rowcount=0, scalar_val=None):
        self._rows = rows or []
        self.rowcount = rowcount
        self._scalar = scalar_val

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._scalar


class _BootstrapDB:
    def __init__(self):
        self.rows = []

    async def execute(self, statement):
        # Simulate INSERT … ON CONFLICT DO NOTHING … RETURNING user_id
        params = statement.compile().params
        user_id = params["user_id"]
        if any(row["user_id"] == user_id for row in self.rows):
            return FakeResult(rows=[])  # conflict → nothing returned
        self.rows.append(
            {
                "user_id": user_id,
                "encrypted_dek": params["encrypted_dek"],
                "dek_nonce": params["dek_nonce"],
            }
        )
        return FakeResult(rows=[{"user_id": user_id}])

    async def commit(self):
        pass


class _BackfillDB(_BootstrapDB):
    def __init__(self, user_ids):
        super().__init__()
        self.user_ids = user_ids

    async def execute(self, statement):
        from sqlalchemy import Select as _SASelect
        if isinstance(statement, _SASelect):
            # SELECT from backfill_existing_user_secret_keys
            existing = {row["user_id"] for row in self.rows}
            return FakeResult(rows=[
                {"id": uid}
                for uid in self.user_ids
                if uid not in existing
            ])
        # INSERT from bootstrap_user_secret_key
        return await super().execute(statement)


class _OwnerDB:
    def __init__(self, *, null_count, admin_id=None, orphan_count=0):
        # _scalars: two sequential scalar return values consumed in order.
        # admin_id doubles as the second scalar for validate_owner_release_b_preconditions
        # (orphan_count), since both functions make exactly two scalar queries.
        self._scalars = [null_count, admin_id]
        self.executed = []

    async def execute(self, statement, values=None):
        if self._scalars:
            return FakeResult(scalar_val=self._scalars.pop(0))
        # Mutation (UPDATE) after scalars exhausted
        self.executed.append((str(statement), values))
        return FakeResult()

    async def commit(self):
        pass


def _metadata():
    metadata = sqlalchemy.MetaData()
    sqlalchemy.Table(
        "users",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    )
    return metadata


def _backend(tmp_path):
    tmp_path.chmod(0o700)
    key = tmp_path / "v1.key"
    key.write_bytes(os.urandom(32))
    key.chmod(0o400)
    return FileKeyEncryptionBackend(tmp_path, "v1")


def test_table_declarations_match_frozen_defaults_and_constraints():
    tables = define_ai_provider_tables(_metadata())
    providers = tables.user_ai_providers

    assert set(providers.c.keys()) == {
        "id", "user_id", "label", "protocol", "base_url", "model",
        "temperature", "max_tokens", "thinking", "effort",
        "encrypted_api_key", "credential_nonce", "credential_version",
        "api_key_last4", "api_key_mask", "priority", "enabled",
        "health_status", "last_tested_at", "last_success_at",
        "last_failure_at", "last_failure_code", "source_type", "source_id",
        "revision", "created_at", "updated_at",
    }
    assert providers.c.thinking.server_default.arg == "false"
    assert providers.c.effort.server_default.arg == "low"
    assert providers.c.priority.server_default.arg == "0"
    assert providers.c.revision.server_default.arg == "1"
    assert {
        constraint.name for constraint in providers.constraints
    } >= {
        "uq_user_ai_providers_user_label",
        "ck_user_ai_providers_source_pair",
        "ck_user_ai_providers_effort",
    }
    assert any(
        index.name == "uq_user_ai_providers_legacy_source"
        and index.unique
        for index in providers.indexes
    )


def test_schema_sql_is_idempotent_and_release_b_is_separate():
    sql = "\n".join(SCHEMA_EXPANSION_STATEMENTS)
    assert "CREATE TABLE IF NOT EXISTS user_secret_keys" in sql
    assert "CREATE TABLE IF NOT EXISTS user_ai_providers" in sql
    assert "ADD COLUMN IF NOT EXISTS owner_user_id" in sql
    assert "SET NOT NULL" not in sql
    assert "SET NOT NULL" in "\n".join(OWNER_RELEASE_B_CONTRACT_STATEMENTS)


@pytest.mark.asyncio
async def test_user_secret_bootstrap_is_idempotent(tmp_path):
    db = _BootstrapDB()
    tables = define_ai_provider_tables(_metadata())
    backend = _backend(tmp_path)

    assert await bootstrap_user_secret_key(
        db, tables.user_secret_keys, backend, user_id=7
    )
    assert not await bootstrap_user_secret_key(
        db, tables.user_secret_keys, backend, user_id=7
    )
    assert len(db.rows) == 1
    assert len(db.rows[0]["dek_nonce"]) == 12


@pytest.mark.asyncio
async def test_existing_user_key_backfill_is_empty_safe_and_rerunnable(tmp_path):
    tables = define_ai_provider_tables(_metadata())
    backend = _backend(tmp_path)
    db = _BackfillDB([])

    assert await backfill_existing_user_secret_keys(
        db,
        _metadata().tables["users"],
        tables.user_secret_keys,
        backend,
    ) == {"scanned": 0, "created": 0}

    db.user_ids = [1, 2]
    first = await backfill_existing_user_secret_keys(
        db,
        _metadata().tables["users"],
        tables.user_secret_keys,
        backend,
    )
    second = await backfill_existing_user_secret_keys(
        db,
        _metadata().tables["users"],
        tables.user_secret_keys,
        backend,
    )
    assert first == {"scanned": 2, "created": 2}
    assert second == {"scanned": 0, "created": 0}
    assert [row["user_id"] for row in db.rows] == [1, 2]


@pytest.mark.asyncio
async def test_owner_backfill_uses_deterministic_active_admin():
    db = _OwnerDB(null_count=3, admin_id=2)
    result = await backfill_site_owners(db)

    assert result.status is OwnerBackfillStatus.COMPLETE
    assert result.owner_user_id == 2
    assert result.updated_count == 3
    assert db.executed[0][1] == {"owner_user_id": 2}


@pytest.mark.asyncio
async def test_owner_backfill_without_admin_is_explicit_and_non_destructive():
    db = _OwnerDB(null_count=2, admin_id=None)
    result = await backfill_site_owners(db)

    assert result.status is OwnerBackfillStatus.NO_ACTIVE_ADMIN
    assert result.updated_count == 0
    assert db.executed == []


@pytest.mark.asyncio
async def test_release_b_precondition_rejects_null_or_orphan_owner():
    db = _OwnerDB(null_count=1, orphan_count=0)
    with pytest.raises(OwnerContractPreconditionError):
        await validate_owner_release_b_preconditions(db)

    db = _OwnerDB(null_count=0, admin_id=1)
    with pytest.raises(OwnerContractPreconditionError):
        await validate_owner_release_b_preconditions(db)
