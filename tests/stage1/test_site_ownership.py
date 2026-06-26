"""
---
name: test_site_ownership
description: "Site ownership authorization unit tests — owner/admin access control and transfer utilities"
stage: stage1
type: pytest
target:
  layer: backend
  domain: site
spec_doc: null
test_file: tests/stage1/test_site_ownership.py
functions:
  - name: test_release_a_is_backward_compatible_and_release_b_is_contract_only
    line: 62
    purpose: "Verifies SCHEMA_EXPANSION (nullable owner) vs OWNER_RELEASE_B (NOT NULL + FK) migration contract"
    fixtures: []
  - name: test_owner_can_access_own_site
    line: 82
    purpose: "check_site_owner_or_admin returns True when user_id matches owner_user_id"
    fixtures: []
  - name: test_non_owner_non_admin_rejected
    line: 87
    purpose: "check_site_owner_or_admin returns False for non-owner non-admin user"
    fixtures: []
  - name: test_admin_can_access_any_site
    line: 92
    purpose: "check_site_owner_or_admin returns True for admin regardless of ownership"
    fixtures: []
  - name: test_null_owner_admin_only
    line: 97
    purpose: "Sites with null owner_user_id are accessible by admin only"
    fixtures: []
  - name: test_user_with_owned_sites_returns_sites
    line: 108
    purpose: "ownership_transfer_gate returns list of owned sites for a user"
    fixtures: []
  - name: test_user_with_no_sites_returns_empty
    line: 121
    purpose: "ownership_transfer_gate returns empty list when user owns no sites"
    fixtures: []
  - name: test_returns_sites_with_owner_status
    line: 136
    purpose: "get_sites_with_owner_status returns rows with owner_status field populated"
    fixtures: []
  - name: test_active_user_returns_row
    line: 155
    purpose: "verify_transfer_target returns user row for active user"
    fixtures: []
  - name: test_blocked_user_returns_none
    line: 165
    purpose: "verify_transfer_target returns None when no matching active user row"
    fixtures: []
  - name: test_nonexistent_user_returns_none
    line: 175
    purpose: "verify_transfer_target returns None for nonexistent user ID"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_site_ownership.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "Python deps installed (pytest-asyncio)"
---
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock


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

from backend.core.ai_provider_migrations import (
    OWNER_RELEASE_B_CONTRACT_STATEMENTS,
    SCHEMA_EXPANSION_STATEMENTS,
)
from backend.core.ownership import (
    check_site_owner_or_admin,
    get_sites_with_owner_status,
    ownership_transfer_gate,
    verify_transfer_target,
)


# ---------------------------------------------------------------------------
# Existing Release A/B compatibility test (keep intact)
# ---------------------------------------------------------------------------

def test_release_a_is_backward_compatible_and_release_b_is_contract_only():
    release_a = "\n".join(SCHEMA_EXPANSION_STATEMENTS)
    release_b = "\n".join(OWNER_RELEASE_B_CONTRACT_STATEMENTS)

    assert "owner_user_id INTEGER" in release_a
    assert "owner_user_id INTEGER NOT NULL" not in release_a
    assert "REFERENCES users(id)" not in release_a.split(
        "owner_user_id INTEGER", 1
    )[1].splitlines()[0]
    assert "ON DELETE RESTRICT" in release_b
    assert "VALIDATE CONSTRAINT" in release_b
    assert release_b.rstrip().endswith(
        "ALTER TABLE sites ALTER COLUMN owner_user_id SET NOT NULL"
    )


# ---------------------------------------------------------------------------
# check_site_owner_or_admin — pure function, no mocks needed
# ---------------------------------------------------------------------------

def test_owner_can_access_own_site():
    site = {"id": 10, "owner_user_id": 5}
    assert check_site_owner_or_admin(site, user_id=5, is_admin=False) is True


def test_non_owner_non_admin_rejected():
    site = {"id": 10, "owner_user_id": 5}
    assert check_site_owner_or_admin(site, user_id=99, is_admin=False) is False


def test_admin_can_access_any_site():
    site = {"id": 10, "owner_user_id": 5}
    assert check_site_owner_or_admin(site, user_id=99, is_admin=True) is True


def test_null_owner_admin_only():
    site = {"id": 10, "owner_user_id": None}
    assert check_site_owner_or_admin(site, user_id=1, is_admin=True) is True
    assert check_site_owner_or_admin(site, user_id=1, is_admin=False) is False


# ---------------------------------------------------------------------------
# ownership_transfer_gate — async, mock db
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_with_owned_sites_returns_sites():
    db = AsyncMock()
    owned = [
        {"id": 1, "title": "Site A", "owner_user_id": 7},
        {"id": 2, "title": "Site B", "owner_user_id": 7},
    ]
    db.execute = AsyncMock(return_value=FakeResult(rows=owned))

    result = await ownership_transfer_gate(db, user_id=7)

    assert result == owned


@pytest.mark.asyncio
async def test_user_with_no_sites_returns_empty():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=FakeResult(rows=[]))

    result = await ownership_transfer_gate(db, user_id=42)

    assert result == []


# ---------------------------------------------------------------------------
# get_sites_with_owner_status — async, mock db
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_sites_with_owner_status():
    db = AsyncMock()
    rows = [
        {"id": 1, "title": "Site A", "owner_user_id": 3, "owner_status": "active"},
        {"id": 2, "title": "Site B", "owner_user_id": 4, "owner_status": "blocked"},
    ]
    db.execute = AsyncMock(return_value=FakeResult(rows=rows))

    result = await get_sites_with_owner_status(db)

    assert result == rows
    assert all("owner_status" in row for row in result)


# ---------------------------------------------------------------------------
# verify_transfer_target — async, mock db
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_active_user_returns_row():
    db = AsyncMock()
    user_row = {"id": 3, "status": "active", "username": "alice"}
    db.execute = AsyncMock(return_value=FakeResult(rows=[user_row]))

    result = await verify_transfer_target(db, new_owner_id=3)

    assert result == user_row


@pytest.mark.asyncio
async def test_blocked_user_returns_none():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=FakeResult(rows=[]))

    result = await verify_transfer_target(db, new_owner_id=5)

    assert result is None


@pytest.mark.asyncio
async def test_nonexistent_user_returns_none():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=FakeResult(rows=[]))

    result = await verify_transfer_target(db, new_owner_id=9999)

    assert result is None
