"""
---
name: test_llm_provider_crud
description: "Unit tests for AI provider CRUD service (create, list, update, delete, reorder, reveal, toggle, status)"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-provider
spec_doc: null
test_file: tests/stage1/test_llm_provider_crud.py
functions:
  - name: TestListUserProviders.test_empty_list
    line: 626
    purpose: "list_user_providers returns empty dict when no providers exist"
    fixtures: [db, tables]
  - name: TestListUserProviders.test_sorted_by_priority
    line: 631
    purpose: "Providers are returned sorted by priority ascending"
    fixtures: [db, tables]
  - name: TestListUserProviders.test_masked_no_encrypted_fields
    line: 641
    purpose: "Response exposes api_key_mask/last4 but excludes encrypted_api_key"
    fixtures: [db, tables]
  - name: TestListUserProviders.test_includes_revision
    line: 651
    purpose: "Response includes revision field for OCC"
    fixtures: [db, tables]
  - name: TestListUserProviders.test_filters_by_user
    line: 657
    purpose: "Providers are filtered by user_id, not shared across users"
    fixtures: [db, tables]
  - name: TestCreateProvider.test_creates_and_encrypts
    line: 667
    purpose: "create_provider stores encrypted key and returns masked response with revision=1"
    fixtures: [seeded_db, tables, backend]
  - name: TestCreateProvider.test_auto_increments_priority
    line: 685
    purpose: "Second provider gets priority=1 (auto-incremented from max+1)"
    fixtures: [seeded_db, tables, backend]
  - name: TestCreateProvider.test_label_conflict
    line: 701
    purpose: "Duplicate label raises ProviderLabelConflictError"
    fixtures: [seeded_db, tables, backend]
  - name: TestUpdateProvider.test_update_label
    line: 719
    purpose: "update_provider changes label and increments revision"
    fixtures: [seeded_db, tables, backend]
  - name: TestUpdateProvider.test_revision_mismatch
    line: 735
    purpose: "Wrong revision raises ProviderRevisionConflictError"
    fixtures: [seeded_db, tables, backend]
  - name: TestUpdateProvider.test_reencrypt_on_protocol_change
    line: 750
    purpose: "Changing protocol triggers re-encryption with new AAD; key remains correct"
    fixtures: [seeded_db, tables, backend]
  - name: TestUpdateProvider.test_update_with_new_api_key
    line: 773
    purpose: "Providing a new api_key re-encrypts and updates api_key_last4"
    fixtures: [seeded_db, tables, backend]
  - name: TestUpdateProvider.test_cross_user_update_denied
    line: 788
    purpose: "Updating another user's provider raises ProviderOwnershipError"
    fixtures: [seeded_db, tables, backend]
  - name: TestUpdateProvider.test_update_with_stale_revision_raises_conflict
    line: 803
    purpose: "OCC: second update with stale revision raises ProviderRevisionConflictError"
    fixtures: [seeded_db, tables, backend]
  - name: TestDeleteProvider.test_delete_success
    line: 825
    purpose: "delete_provider removes the provider and list returns empty"
    fixtures: [seeded_db, tables, backend]
  - name: TestDeleteProvider.test_delete_wrong_user
    line: 840
    purpose: "Deleting another user's provider raises ProviderOwnershipError"
    fixtures: [seeded_db, tables, backend]
  - name: TestDeleteProvider.test_delete_revision_mismatch
    line: 854
    purpose: "Delete with wrong revision raises ProviderRevisionConflictError"
    fixtures: [seeded_db, tables, backend]
  - name: TestDeleteProvider.test_delete_nonexistent
    line: 868
    purpose: "Delete of non-existent provider raises ProviderNotFoundError"
    fixtures: [db, tables]
  - name: TestReorderProviders.test_reorder_success
    line: 878
    purpose: "reorder_providers repositions providers and returns them in new order"
    fixtures: [seeded_db, tables, backend]
  - name: TestReorderProviders.test_reorder_duplicate_ids
    line: 899
    purpose: "Duplicate IDs in ordered_ids raise ValueError with 'duplicate'"
    fixtures: [seeded_db, tables, backend]
  - name: TestReorderProviders.test_reorder_missing_id
    line: 913
    purpose: "Omitting a provider's ID from ordered_ids raises ValueError with 'mismatch'"
    fixtures: [seeded_db, tables, backend]
  - name: TestReorderProviders.test_reorder_unknown_id
    line: 934
    purpose: "Including an unknown ID in ordered_ids raises ValueError with 'mismatch'"
    fixtures: [seeded_db, tables, backend]
  - name: TestReorderProviders.test_reorder_revision_mismatch
    line: 948
    purpose: "Stale revision in reorder raises ProviderRevisionConflictError"
    fixtures: [seeded_db, tables, backend]
  - name: TestRevealApiKey.test_reveal_decrypts
    line: 964
    purpose: "reveal_api_key decrypts and returns the original plaintext API key"
    fixtures: [seeded_db, tables, backend]
  - name: TestRevealApiKey.test_reveal_cross_user_denied
    line: 978
    purpose: "Revealing another user's API key raises ProviderOwnershipError"
    fixtures: [seeded_db, tables, backend]
  - name: TestRevealApiKey.test_reveal_nonexistent
    line: 992
    purpose: "Revealing a non-existent provider raises ProviderNotFoundError"
    fixtures: [db, tables, backend]
  - name: TestToggleProviderEnabled.test_disable
    line: 1002
    purpose: "toggle_provider_enabled sets enabled=False correctly"
    fixtures: [seeded_db, tables, backend]
  - name: TestToggleProviderEnabled.test_enable
    line: 1017
    purpose: "toggle_provider_enabled sets enabled=True after being disabled"
    fixtures: [seeded_db, tables, backend]
  - name: TestToggleProviderEnabled.test_toggle_cross_user_denied
    line: 1035
    purpose: "Toggling another user's provider raises ProviderOwnershipError"
    fixtures: [seeded_db, tables, backend]
  - name: TestGetRuntimeStatus.test_empty
    line: 1051
    purpose: "get_runtime_status with no providers returns profiles_enabled=False and empty chain"
    fixtures: [db, tables, backend]
  - name: TestGetRuntimeStatus.test_with_enabled_providers
    line: 1058
    purpose: "Enabled providers appear in chain with profiles_enabled=True"
    fixtures: [seeded_db, tables, backend]
  - name: TestGetRuntimeStatus.test_disabled_not_in_chain
    line: 1072
    purpose: "Disabled provider is excluded from chain; profiles_enabled=False"
    fixtures: [seeded_db, tables, backend]
  - name: TestGetRuntimeStatus.test_env_fallback
    line: 1088
    purpose: "LLM_FALLBACK_* env vars populate environment_fallback field"
    fixtures: [db, tables, backend]
  - name: TestGetRuntimeStatus.test_no_env_fallback
    line: 1103
    purpose: "Without LLM_FALLBACK_* vars environment_fallback is None"
    fixtures: [db, tables, backend]
  - name: TestProviderConnectionTest.test_successful_connection
    line: 1111
    purpose: "test_provider_connection stores health_status=ok on successful adapter call"
    fixtures: [seeded_db, tables, backend]
  - name: TestProviderConnectionTest.test_failed_connection
    line: 1133
    purpose: "ProviderError from adapter results in health_status=error with failure code"
    fixtures: [seeded_db, tables, backend]
  - name: TestProviderConnectionTest.test_connection_cross_user_denied
    line: 1159
    purpose: "Testing another user's provider raises ProviderOwnershipError"
    fixtures: [seeded_db, tables, backend]
  - name: TestDiscoverModels.test_discover_with_api_key
    line: 1175
    purpose: "discover_models with api_key returns model list and manual_entry_allowed=True"
    fixtures: [db, tables, backend]
  - name: TestDiscoverModels.test_discover_unavailable
    line: 1201
    purpose: "model_discovery_unavailable error returns empty list with warning"
    fixtures: [db, tables, backend]
  - name: TestDiscoverModels.test_discover_no_key_raises
    line: 1225
    purpose: "discover_models without api_key or provider_id raises ValueError"
    fixtures: [db, tables, backend]
  - name: TestDiscoverModels.test_discover_models_with_provider_id
    line: 1236
    purpose: "discover_models using provider_id retrieves and uses stored encrypted key"
    fixtures: [seeded_db, tables, backend]
  - name: TestDiscoverModels.test_discover_models_rejects_cross_user
    line: 1268
    purpose: "Discovering with another user's provider_id raises ProviderOwnershipError"
    fixtures: [seeded_db, tables, backend]
  - name: TestCrossUserAccess.test_update_cross_user
    line: 1289
    purpose: "Cross-user update blocked → ProviderOwnershipError"
    fixtures: [seeded_db, tables, backend]
  - name: TestCrossUserAccess.test_delete_cross_user
    line: 1303
    purpose: "Cross-user delete blocked → ProviderOwnershipError"
    fixtures: [seeded_db, tables, backend]
  - name: TestCrossUserAccess.test_reveal_cross_user
    line: 1317
    purpose: "Cross-user reveal blocked → ProviderOwnershipError"
    fixtures: [seeded_db, tables, backend]
  - name: TestCrossUserAccess.test_toggle_cross_user
    line: 1331
    purpose: "Cross-user toggle blocked → ProviderOwnershipError"
    fixtures: [seeded_db, tables, backend]
  - name: TestCrossUserAccess.test_connection_cross_user
    line: 1345
    purpose: "Cross-user connection test blocked → ProviderOwnershipError"
    fixtures: [seeded_db, tables, backend]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_provider_crud.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import sqlalchemy

from core.ai_providers import (
    ProviderLabelConflictError,
    ProviderNotFoundError,
    ProviderOwnershipError,
    ProviderRevisionConflictError,
    create_provider,
    delete_provider,
    discover_models,
    get_runtime_status,
    list_user_providers,
    reorder_providers,
    reveal_api_key,
    test_provider_connection as do_test_provider_connection,
    toggle_provider_enabled,
    update_provider,
)
from core.ai_provider_migrations import define_ai_provider_tables
from core.llm.key_backends import WrappedKey
from core.llm.vault import generate_dek, wrap_user_dek
from core.llm.models import ModelInfo, ProviderCapabilities, ProviderError, ProviderHealth


# ---------------------------------------------------------------------------
# Shared test fixtures / fakes
# ---------------------------------------------------------------------------


def _sa_metadata():
    metadata = sqlalchemy.MetaData()
    sqlalchemy.Table(
        "users", metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    )
    return metadata


def _tables():
    return define_ai_provider_tables(_sa_metadata())


class FakeKeyBackend:
    """In-memory key encryption backend for tests."""

    def __init__(self):
        self._kek = os.urandom(32)

    @property
    def active_key_version(self) -> str:
        return "v1"

    async def wrap_key(self, plaintext_dek: bytes, *, aad: bytes, kek_version: str | None = None) -> WrappedKey:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = os.urandom(12)
        ct = AESGCM(self._kek).encrypt(nonce, plaintext_dek, aad)
        return WrappedKey(ciphertext=ct, nonce=nonce, algorithm="AES-256-GCM", kek_version=kek_version or "v1")

    async def unwrap_key(self, wrapped: WrappedKey, *, aad: bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return AESGCM(self._kek).decrypt(wrapped.nonce, wrapped.ciphertext, aad)


def _eval_clause(row: dict, clause) -> bool:
    """Recursively evaluate a SQLAlchemy clause element against a dict row."""
    if clause is None:
        return True

    # BooleanClauseList (AND/OR)
    if hasattr(clause, 'clauses') and hasattr(clause, 'operator'):
        op_name = getattr(clause.operator, '__name__', '')
        if op_name == 'and_':
            return all(_eval_clause(row, c) for c in clause.clauses)
        if op_name == 'or_':
            return any(_eval_clause(row, c) for c in clause.clauses)

    # Binary expression (col == value)
    if hasattr(clause, 'left') and hasattr(clause, 'right'):
        col_name = str(clause.left).split(".")[-1]
        right = clause.right
        if isinstance(right, sqlalchemy.sql.elements.True_):
            value = True
        elif isinstance(right, sqlalchemy.sql.elements.False_):
            value = False
        elif hasattr(right, 'effective_value'):
            value = right.effective_value
        elif hasattr(right, 'value'):
            value = right.value
        else:
            return True
        if col_name in row:
            return row[col_name] == value
    return True


def _get_where(statement):
    """Extract WHERE clause from a statement."""
    for attr in ('_whereclause', 'whereclause'):
        clause = getattr(statement, attr, None)
        if clause is not None:
            return clause
    return None


def _get_insert_values(statement) -> dict:
    """Extract the VALUES dict from an INSERT statement."""
    # SQLAlchemy core: statement.compile().params gives us the bound params
    compiled = statement.compile()
    return dict(compiled.params)


def _table_from_sql(statement) -> str:
    """Determine table name by inspecting statement structure."""
    if hasattr(statement, 'table'):
        return str(statement.table.name)
    # For select, check froms
    sql_str = str(statement)
    if "user_secret_keys" in sql_str and "user_ai_providers" not in sql_str:
        return "user_secret_keys"
    if "user_ai_providers" in sql_str:
        return "user_ai_providers"
    return "unknown"


class FakeResult:
    """Mimics SQLAlchemy 2.0's Result / MappingResult proxy."""

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

    def scalar_one_or_none(self):
        return self._scalar


class FakeTransaction:
    """Async context manager returned by FakeDB.begin()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class FakeDB:
    """In-memory fake database that supports SQLAlchemy 2.0 async API."""

    def __init__(self):
        self._user_secret_keys: list[dict] = []
        self._providers: list[dict] = []
        self._id_seq = 0

    def _get_store(self, table_name: str) -> list[dict]:
        if table_name == "user_secret_keys":
            return self._user_secret_keys
        if table_name == "user_ai_providers":
            return self._providers
        return []

    # ------------------------------------------------------------------
    # Legacy helpers kept for backward compatibility (not used by new API)
    # ------------------------------------------------------------------

    async def fetch_one(self, statement) -> dict | None:
        table_name = _table_from_sql(statement)
        where = _get_where(statement)
        for r in self._get_store(table_name):
            if _eval_clause(r, where):
                return r
        return None

    async def fetch_all(self, statement) -> list[dict]:
        table_name = _table_from_sql(statement)
        where = _get_where(statement)
        results = [r for r in self._get_store(table_name) if _eval_clause(r, where)]
        results.sort(key=lambda r: (r.get("priority", 0), r.get("id", 0)))
        return results

    async def fetch_val(self, statement) -> Any:
        sql = str(statement)
        if "user_ai_providers_id_seq" in sql or "nextval" in sql:
            self._id_seq += 1
            return self._id_seq
        if "coalesce" in sql.lower() and "priority" in sql.lower():
            where = _get_where(statement)
            user_providers = [p for p in self._providers if _eval_clause(p, where)]
            if not user_providers:
                return 0
            return max(p["priority"] for p in user_providers) + 1
        return None

    # ------------------------------------------------------------------
    # SQLAlchemy 2.0 AsyncSession-compatible API
    # ------------------------------------------------------------------

    async def execute(self, statement, values=None) -> FakeResult:
        sql_str = str(statement)

        # ----- SELECT -----
        if hasattr(statement, 'is_select') and statement.is_select:
            # Sequence next_value() — allocate a new provider ID
            if "user_ai_providers_id_seq" in sql_str or "nextval" in sql_str:
                self._id_seq += 1
                return FakeResult(scalar_val=self._id_seq)

            # Aggregate: coalesce(max(priority), -1) + 1
            if ("coalesce" in sql_str.lower()
                    and "max" in sql_str.lower()
                    and "priority" in sql_str.lower()):
                where = _get_where(statement)
                user_providers = [
                    p for p in self._providers if _eval_clause(p, where)
                ]
                if not user_providers:
                    return FakeResult(scalar_val=0)
                return FakeResult(
                    scalar_val=max(p["priority"] for p in user_providers) + 1
                )

            # Regular table SELECT
            table_name = _table_from_sql(statement)
            store = self._get_store(table_name)
            where = _get_where(statement)
            rows = [r for r in store if _eval_clause(r, where)]
            # Preserve default sort order to match ORDER BY (priority, id)
            if table_name == "user_ai_providers":
                rows.sort(key=lambda r: (r.get("priority", 0), r.get("id", 0)))
            return FakeResult(rows=rows)

        # ----- INSERT -----
        elif hasattr(statement, 'is_insert') and statement.is_insert:
            params = _get_insert_values(statement)
            table_name = str(statement.table.name)
            if table_name == "user_secret_keys":
                for existing in self._user_secret_keys:
                    if existing["user_id"] == params["user_id"]:
                        # on_conflict_do_nothing → empty result
                        return FakeResult(rows=[], rowcount=0)
                self._user_secret_keys.append(params)
                # Simulate RETURNING user_id for bootstrap_user_secret_key
                return FakeResult(rows=[params], rowcount=1)
            elif table_name == "user_ai_providers":
                for existing in self._providers:
                    if (existing["user_id"] == params["user_id"]
                            and existing["label"] == params["label"]):
                        from sqlalchemy.exc import IntegrityError
                        raise IntegrityError(
                            "uq_user_ai_providers_user_label",
                            params, Exception()
                        )
                self._providers.append(params)
                return FakeResult(rowcount=1)
            return FakeResult(rowcount=0)

        # ----- UPDATE -----
        elif hasattr(statement, 'is_update') and statement.is_update:
            params = _get_insert_values(statement)
            where = _get_where(statement)
            table_name = str(statement.table.name)
            if table_name == "user_ai_providers":
                count = 0
                for row in self._providers:
                    if _eval_clause(row, where):
                        if "label" in params:
                            for other in self._providers:
                                if (other["id"] != row["id"]
                                        and other["user_id"] == row["user_id"]
                                        and other["label"] == params["label"]):
                                    from sqlalchemy.exc import IntegrityError
                                    raise IntegrityError(
                                        "uq_user_ai_providers_user_label",
                                        params, Exception()
                                    )
                        row.update(params)
                        count += 1
                return FakeResult(rowcount=count)
            return FakeResult(rowcount=0)

        # ----- DELETE -----
        elif hasattr(statement, 'is_delete') and statement.is_delete:
            where = _get_where(statement)
            table_name = str(statement.table.name)
            if table_name == "user_ai_providers":
                before = len(self._providers)
                self._providers = [
                    r for r in self._providers
                    if not _eval_clause(r, where)
                ]
                return FakeResult(rowcount=before - len(self._providers))
            return FakeResult(rowcount=0)

        return FakeResult()

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    def begin(self) -> FakeTransaction:
        return FakeTransaction()

    def add_provider(self, **kwargs) -> dict:
        """Helper: directly insert a provider row for test setup."""
        self._id_seq += 1
        defaults = {
            "id": self._id_seq,
            "user_id": 1,
            "label": f"Test Provider {self._id_seq}",
            "protocol": "openai",
            "base_url": "https://api.openai.com",
            "model": "gpt-4",
            "temperature": None,
            "max_tokens": 4096,
            "thinking": False,
            "effort": "low",
            "encrypted_api_key": b"fake_encrypted",
            "credential_nonce": os.urandom(12),
            "credential_version": 1,
            "api_key_last4": "st-1",
            "api_key_mask": "***st-1",
            "priority": self._id_seq - 1,
            "enabled": True,
            "health_status": "unknown",
            "last_tested_at": None,
            "last_success_at": None,
            "last_failure_at": None,
            "last_failure_code": None,
            "source_type": None,
            "source_id": None,
            "revision": 1,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        defaults.update(kwargs)
        self._providers.append(defaults)
        return defaults

    def add_user_key(self, *, user_id: int, encrypted_dek: bytes, dek_nonce: bytes,
                     algorithm: str = "AES-256-GCM", kek_version: str = "v1") -> dict:
        """Helper: directly insert a user secret key row."""
        row = {
            "id": len(self._user_secret_keys) + 1,
            "user_id": user_id,
            "encrypted_dek": encrypted_dek,
            "dek_nonce": dek_nonce,
            "algorithm": algorithm,
            "kek_version": kek_version,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self._user_secret_keys.append(row)
        return row


@pytest.fixture
def tables():
    return _tables()


@pytest.fixture
def backend():
    return FakeKeyBackend()


@pytest.fixture
def db():
    return FakeDB()


@pytest_asyncio.fixture
async def seeded_db(db, backend):
    """DB pre-seeded with a user key for user_id=1."""
    dek = generate_dek()
    envelope = await wrap_user_dek(backend, user_id=1, dek=dek)
    wk = envelope.wrapped_key
    db.add_user_key(
        user_id=1,
        encrypted_dek=wk.ciphertext,
        dek_nonce=wk.nonce,
        algorithm=wk.algorithm,
        kek_version=wk.kek_version,
    )
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListUserProviders:
    @pytest.mark.asyncio
    async def test_empty_list(self, db, tables):
        result = await list_user_providers(db, tables, user_id=1)
        assert result == {"providers": []}

    @pytest.mark.asyncio
    async def test_sorted_by_priority(self, db, tables):
        db.add_provider(user_id=1, priority=2, label="C")
        db.add_provider(user_id=1, priority=0, label="A")
        db.add_provider(user_id=1, priority=1, label="B")

        result = await list_user_providers(db, tables, user_id=1)
        labels = [p["label"] for p in result["providers"]]
        assert labels == ["A", "B", "C"]

    @pytest.mark.asyncio
    async def test_masked_no_encrypted_fields(self, db, tables):
        db.add_provider(user_id=1, api_key_last4="xyz9", api_key_mask="****xyz9")
        result = await list_user_providers(db, tables, user_id=1)
        provider = result["providers"][0]
        assert provider["api_key_last4"] == "xyz9"
        assert provider["api_key_mask"] == "****xyz9"
        assert "encrypted_api_key" not in provider
        assert "credential_nonce" not in provider

    @pytest.mark.asyncio
    async def test_includes_revision(self, db, tables):
        db.add_provider(user_id=1, revision=3)
        result = await list_user_providers(db, tables, user_id=1)
        assert result["providers"][0]["revision"] == 3

    @pytest.mark.asyncio
    async def test_filters_by_user(self, db, tables):
        db.add_provider(user_id=1, label="Mine")
        db.add_provider(user_id=2, label="Theirs")
        result = await list_user_providers(db, tables, user_id=1)
        assert len(result["providers"]) == 1
        assert result["providers"][0]["label"] == "Mine"


class TestCreateProvider:
    @pytest.mark.asyncio
    async def test_creates_and_encrypts(self, seeded_db, tables, backend):
        result = await create_provider(
            seeded_db, tables, backend,
            user_id=1,
            label="My OpenAI",
            protocol="openai",
            base_url="https://api.openai.com",
            model="gpt-4",
            api_key="sk-test1234567890abcdef",
        )
        assert result["label"] == "My OpenAI"
        assert result["api_key_last4"] == "cdef"
        assert result["api_key_mask"] == "********cdef"
        assert result["priority"] == 0
        assert result["revision"] == 1
        assert "encrypted_api_key" not in result

    @pytest.mark.asyncio
    async def test_auto_increments_priority(self, seeded_db, tables, backend):
        await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="First", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        result = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Second", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-dddd3333eeee4444ffff",
        )
        assert result["priority"] == 1

    @pytest.mark.asyncio
    async def test_label_conflict(self, seeded_db, tables, backend):
        await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Dup", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderLabelConflictError):
            await create_provider(
                seeded_db, tables, backend,
                user_id=1, label="Dup", protocol="openai",
                base_url="https://api.openai.com", model="gpt-4",
                api_key="sk-dddd3333eeee4444ffff",
            )


class TestUpdateProvider:
    @pytest.mark.asyncio
    async def test_update_label(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Old", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        result = await update_provider(
            seeded_db, tables, backend,
            user_id=1, provider_id=created["id"], revision=1,
            label="New",
        )
        assert result["label"] == "New"
        assert result["revision"] == 2

    @pytest.mark.asyncio
    async def test_revision_mismatch(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Test", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderRevisionConflictError):
            await update_provider(
                seeded_db, tables, backend,
                user_id=1, provider_id=created["id"], revision=99,
                label="Fail",
            )

    @pytest.mark.asyncio
    async def test_reencrypt_on_protocol_change(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Switch", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        result = await update_provider(
            seeded_db, tables, backend,
            user_id=1, provider_id=created["id"], revision=1,
            protocol="anthropic",
            base_url="https://api.anthropic.com",
        )
        assert result["protocol"] == "anthropic"
        assert result["base_url"] == "https://api.anthropic.com"
        # The key should still be decryptable with new AAD
        key = await reveal_api_key(
            seeded_db, tables, backend,
            user_id=1, provider_id=created["id"],
        )
        assert key == "sk-aaaa1111bbbb2222cccc"

    @pytest.mark.asyncio
    async def test_update_with_new_api_key(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="KeyChange", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-oldkey1234567890abcd",
        )
        result = await update_provider(
            seeded_db, tables, backend,
            user_id=1, provider_id=created["id"], revision=1,
            api_key="sk-newkey9876543210wxyz",
        )
        assert result["api_key_last4"] == "wxyz"

    @pytest.mark.asyncio
    async def test_cross_user_update_denied(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Test", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderOwnershipError):
            await update_provider(
                seeded_db, tables, backend,
                user_id=999, provider_id=created["id"], revision=1,
                label="Hacked",
            )

    @pytest.mark.asyncio
    async def test_update_with_stale_revision_raises_conflict(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="OCCTest", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        await update_provider(
            seeded_db, tables, backend,
            user_id=1, provider_id=created["id"], revision=1,
            label="Updated",
        )
        with pytest.raises(ProviderRevisionConflictError):
            await update_provider(
                seeded_db, tables, backend,
                user_id=1, provider_id=created["id"], revision=1,
                label="Stale",
            )


class TestDeleteProvider:
    @pytest.mark.asyncio
    async def test_delete_success(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="ToDelete", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        await delete_provider(
            seeded_db, tables,
            user_id=1, provider_id=created["id"], revision=1,
        )
        result = await list_user_providers(seeded_db, tables, user_id=1)
        assert len(result["providers"]) == 0

    @pytest.mark.asyncio
    async def test_delete_wrong_user(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Mine", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderOwnershipError):
            await delete_provider(
                seeded_db, tables,
                user_id=999, provider_id=created["id"], revision=1,
            )

    @pytest.mark.asyncio
    async def test_delete_revision_mismatch(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Versioned", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderRevisionConflictError):
            await delete_provider(
                seeded_db, tables,
                user_id=1, provider_id=created["id"], revision=42,
            )

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db, tables):
        with pytest.raises(ProviderNotFoundError):
            await delete_provider(
                db, tables,
                user_id=1, provider_id=99999, revision=1,
            )


class TestReorderProviders:
    @pytest.mark.asyncio
    async def test_reorder_success(self, seeded_db, tables, backend):
        p1 = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="A", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        p2 = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="B", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-dddd3333eeee4444ffff",
        )
        result = await reorder_providers(
            seeded_db, tables,
            user_id=1, ordered_ids=[p2["id"], p1["id"]], revision=1,
        )
        labels = [p["label"] for p in result["providers"]]
        assert labels == ["B", "A"]

    @pytest.mark.asyncio
    async def test_reorder_duplicate_ids(self, seeded_db, tables, backend):
        p1 = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="A", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ValueError, match="duplicate"):
            await reorder_providers(
                seeded_db, tables,
                user_id=1, ordered_ids=[p1["id"], p1["id"]], revision=1,
            )

    @pytest.mark.asyncio
    async def test_reorder_missing_id(self, seeded_db, tables, backend):
        p1 = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="A", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="B", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-dddd3333eeee4444ffff",
        )
        # Only provide one of two
        with pytest.raises(ValueError, match="mismatch"):
            await reorder_providers(
                seeded_db, tables,
                user_id=1, ordered_ids=[p1["id"]], revision=1,
            )

    @pytest.mark.asyncio
    async def test_reorder_unknown_id(self, seeded_db, tables, backend):
        p1 = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="A", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ValueError, match="mismatch"):
            await reorder_providers(
                seeded_db, tables,
                user_id=1, ordered_ids=[p1["id"], 99999], revision=1,
            )

    @pytest.mark.asyncio
    async def test_reorder_revision_mismatch(self, seeded_db, tables, backend):
        p1 = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="A", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderRevisionConflictError):
            await reorder_providers(
                seeded_db, tables,
                user_id=1, ordered_ids=[p1["id"]], revision=99,
            )


class TestRevealApiKey:
    @pytest.mark.asyncio
    async def test_reveal_decrypts(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Reveal", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-secret-key-12345678",
        )
        key = await reveal_api_key(
            seeded_db, tables, backend,
            user_id=1, provider_id=created["id"],
        )
        assert key == "sk-secret-key-12345678"

    @pytest.mark.asyncio
    async def test_reveal_cross_user_denied(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Mine", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderOwnershipError):
            await reveal_api_key(
                seeded_db, tables, backend,
                user_id=999, provider_id=created["id"],
            )

    @pytest.mark.asyncio
    async def test_reveal_nonexistent(self, db, tables, backend):
        with pytest.raises(ProviderNotFoundError):
            await reveal_api_key(
                db, tables, backend,
                user_id=1, provider_id=99999,
            )


class TestToggleProviderEnabled:
    @pytest.mark.asyncio
    async def test_disable(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Toggle", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        assert created["enabled"] is True
        result = await toggle_provider_enabled(
            seeded_db, tables,
            user_id=1, provider_id=created["id"], enabled=False,
        )
        assert result["enabled"] is False

    @pytest.mark.asyncio
    async def test_enable(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Toggle2", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        await toggle_provider_enabled(
            seeded_db, tables,
            user_id=1, provider_id=created["id"], enabled=False,
        )
        result = await toggle_provider_enabled(
            seeded_db, tables,
            user_id=1, provider_id=created["id"], enabled=True,
        )
        assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_toggle_cross_user_denied(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="NoTouch", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderOwnershipError):
            await toggle_provider_enabled(
                seeded_db, tables,
                user_id=999, provider_id=created["id"], enabled=False,
            )


class TestGetRuntimeStatus:
    @pytest.mark.asyncio
    async def test_empty(self, db, tables, backend):
        # Override all fallback-related env vars to ensure environment_fallback
        # is None regardless of what is set on the host machine.
        with patch.dict(os.environ, {
            "MINIMAX_API_KEY": "",
            "LLM_FALLBACK_ENABLED": "false",
            "LLM_FALLBACK_PROTOCOL": "",
            "LLM_FALLBACK_BASE_URL": "",
            "LLM_FALLBACK_API_KEY": "",
            "LLM_FALLBACK_MODEL": "",
        }):
            result = await get_runtime_status(db, tables, backend, user_id=1)
        assert result["profiles_enabled"] is False
        assert result["chain"] == []
        assert result["environment_fallback"] is None

    @pytest.mark.asyncio
    async def test_with_enabled_providers(self, seeded_db, tables, backend):
        await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Active", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        result = await get_runtime_status(seeded_db, tables, backend, user_id=1)
        assert result["profiles_enabled"] is True
        assert len(result["chain"]) == 1
        assert result["chain"][0]["label"] == "Active"
        assert result["chain"][0]["protocol"] == "openai"

    @pytest.mark.asyncio
    async def test_disabled_not_in_chain(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Disabled", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        await toggle_provider_enabled(
            seeded_db, tables,
            user_id=1, provider_id=created["id"], enabled=False,
        )
        result = await get_runtime_status(seeded_db, tables, backend, user_id=1)
        assert result["profiles_enabled"] is False
        assert result["chain"] == []

    @pytest.mark.asyncio
    async def test_env_fallback(self, db, tables, backend):
        env_patch = {
            "LLM_FALLBACK_PROTOCOL": "anthropic",
            "LLM_FALLBACK_MODEL": "claude-3-haiku",
            "LLM_FALLBACK_BASE_URL": "https://api.anthropic.com",
            "LLM_FALLBACK_API_KEY": "test-key-123",
        }
        with patch.dict(os.environ, env_patch):
            result = await get_runtime_status(db, tables, backend, user_id=1)
        assert result["environment_fallback"] is not None
        assert result["environment_fallback"]["enabled"] is True
        assert result["environment_fallback"]["protocol"] == "anthropic"
        assert result["environment_fallback"]["model"] == "claude-3-haiku"

    @pytest.mark.asyncio
    async def test_no_env_fallback(self, db, tables, backend):
        with patch.dict(os.environ, {}, clear=True):
            result = await get_runtime_status(db, tables, backend, user_id=1)
        assert result["environment_fallback"] is None


class TestProviderConnectionTest:
    @pytest.mark.asyncio
    async def test_successful_connection(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="HealthCheck", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )

        mock_health = ProviderHealth(ok=True, protocol="openai", model="gpt-4")
        mock_adapter = AsyncMock()
        mock_adapter.test_connection = AsyncMock(return_value=mock_health)

        with patch("core.ai_providers.create_llm_adapter", return_value=mock_adapter):
            result = await do_test_provider_connection(
                seeded_db, tables, backend,
                user_id=1, provider_id=created["id"],
            )

        assert result["health_status"] == "ok"
        assert result["last_failure_code"] is None

    @pytest.mark.asyncio
    async def test_failed_connection(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="FailCheck", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )

        mock_adapter = AsyncMock()
        mock_adapter.test_connection = AsyncMock(
            side_effect=ProviderError(
                code="provider_timeout",
                message="timed out",
            )
        )

        with patch("core.ai_providers.create_llm_adapter", return_value=mock_adapter):
            result = await do_test_provider_connection(
                seeded_db, tables, backend,
                user_id=1, provider_id=created["id"],
            )

        assert result["health_status"] == "error"
        assert result["last_failure_code"] == "provider_timeout"

    @pytest.mark.asyncio
    async def test_connection_cross_user_denied(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="NoTest", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderOwnershipError):
            await do_test_provider_connection(
                seeded_db, tables, backend,
                user_id=999, provider_id=created["id"],
            )


class TestDiscoverModels:
    @pytest.mark.asyncio
    async def test_discover_with_api_key(self, db, tables, backend):
        mock_models = [
            ModelInfo(
                id="gpt-4", display_name="GPT-4",
                capabilities=ProviderCapabilities(
                    supports_thinking=False, supports_effort=False,
                    thinking_disable_mode="disabled",
                ),
            )
        ]
        mock_adapter = AsyncMock()
        mock_adapter.list_models = AsyncMock(return_value=mock_models)

        with patch("core.ai_providers.create_llm_adapter", return_value=mock_adapter):
            result = await discover_models(
                db, tables, backend,
                user_id=1,
                protocol="openai",
                base_url="https://api.openai.com",
                api_key="sk-aaaa1111bbbb2222cccc",
            )

        assert len(result["models"]) == 1
        assert result["models"][0]["id"] == "gpt-4"
        assert result["manual_entry_allowed"] is True

    @pytest.mark.asyncio
    async def test_discover_unavailable(self, db, tables, backend):
        mock_adapter = AsyncMock()
        mock_adapter.list_models = AsyncMock(
            side_effect=ProviderError(
                code="model_discovery_unavailable",
                message="Not supported",
                status_code=404,
            )
        )

        with patch("core.ai_providers.create_llm_adapter", return_value=mock_adapter):
            result = await discover_models(
                db, tables, backend,
                user_id=1,
                protocol="openai",
                base_url="https://api.openai.com",
                api_key="sk-aaaa1111bbbb2222cccc",
            )

        assert result["models"] == []
        assert result["manual_entry_allowed"] is True
        assert result["warning"] is not None

    @pytest.mark.asyncio
    async def test_discover_no_key_raises(self, db, tables, backend):
        with pytest.raises(ValueError, match="api_key is required"):
            await discover_models(
                db, tables, backend,
                user_id=1,
                protocol="openai",
                base_url="https://api.openai.com",
            )

    @pytest.mark.asyncio
    async def test_discover_models_with_provider_id(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="DiscoverMe", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        mock_models = [
            ModelInfo(
                id="gpt-4", display_name="GPT-4",
                capabilities=ProviderCapabilities(
                    supports_thinking=False, supports_effort=False,
                    thinking_disable_mode="disabled",
                ),
            )
        ]
        mock_adapter = AsyncMock()
        mock_adapter.list_models = AsyncMock(return_value=mock_models)

        with patch("core.ai_providers.create_llm_adapter", return_value=mock_adapter):
            result = await discover_models(
                seeded_db, tables, backend,
                user_id=1,
                protocol="openai",
                base_url="https://api.openai.com",
                provider_id=created["id"],
            )

        assert len(result["models"]) == 1
        assert result["models"][0]["id"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_discover_models_rejects_cross_user(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="CrossUser", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderOwnershipError):
            await discover_models(
                seeded_db, tables, backend,
                user_id=2,
                protocol="openai",
                base_url="https://api.openai.com",
                provider_id=created["id"],
            )


class TestCrossUserAccess:
    """Verify cross-user access is denied for all operations."""

    @pytest.mark.asyncio
    async def test_update_cross_user(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="X", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderOwnershipError):
            await update_provider(
                seeded_db, tables, backend,
                user_id=2, provider_id=created["id"], revision=1,
            )

    @pytest.mark.asyncio
    async def test_delete_cross_user(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Y", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderOwnershipError):
            await delete_provider(
                seeded_db, tables,
                user_id=2, provider_id=created["id"], revision=1,
            )

    @pytest.mark.asyncio
    async def test_reveal_cross_user(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="Z", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderOwnershipError):
            await reveal_api_key(
                seeded_db, tables, backend,
                user_id=2, provider_id=created["id"],
            )

    @pytest.mark.asyncio
    async def test_toggle_cross_user(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="W", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderOwnershipError):
            await toggle_provider_enabled(
                seeded_db, tables,
                user_id=2, provider_id=created["id"], enabled=False,
            )

    @pytest.mark.asyncio
    async def test_connection_cross_user(self, seeded_db, tables, backend):
        created = await create_provider(
            seeded_db, tables, backend,
            user_id=1, label="V", protocol="openai",
            base_url="https://api.openai.com", model="gpt-4",
            api_key="sk-aaaa1111bbbb2222cccc",
        )
        with pytest.raises(ProviderOwnershipError):
            await do_test_provider_connection(
                seeded_db, tables, backend,
                user_id=2, provider_id=created["id"],
            )
