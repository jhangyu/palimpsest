"""
---
name: test_database_router
description: "Database management endpoint tests — GET /settings/database/status and /export, admin-only access"
stage: stage1
type: pytest
target:
  layer: backend
  domain: database
spec_doc: null
test_file: tests/stage1/test_database_router.py
functions:
  - name: test_database_status_admin
    line: 35
    purpose: "GET /settings/database/status as admin → 200 with status payload"
    fixtures: [admin_client]
  - name: test_database_status_non_admin
    line: 53
    purpose: "GET /settings/database/status as regular user → 403 Forbidden"
    fixtures: [client, db]
  - name: test_database_export_admin
    line: 80
    purpose: "GET /settings/database/export as admin → 200, file download with attachment header"
    fixtures: [admin_client]
  - name: test_database_export_non_admin
    line: 98
    purpose: "GET /settings/database/export as regular user → 403 Forbidden"
    fixtures: [client, db]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_database_router.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""
import uuid

import pytest

from conftest import (
    _delete_user,
    _login_client,
    _seed_user,
)


# ────────────────────────────────────────────────────────────────────────────
# 1.4.1  GET /settings/database/status — admin access
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_database_status_admin(admin_client):
    """1.4.1 — GET /settings/database/status as admin → 200 with status payload."""
    resp = await admin_client.get("/settings/database/status")
    assert resp.status_code == 200, (
        f"Expected 200 (database status as admin), got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    # Response must contain the standard status shape
    assert "app_version" in data or "schema_version" in data or "tables" in data, (
        f"Unexpected status response shape: {data}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 1.4.2  GET /settings/database/status — non-admin access (403)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_database_status_non_admin(client, db):
    """1.4.2 — GET /settings/database/status as a regular (non-admin) user → 403 Forbidden."""
    sfx = uuid.uuid4().hex[:8]
    temp_user = await _seed_user(
        db,
        email=f"dbrouter_{sfx}@test.local",
        username=f"dbrouter{sfx}",
        password="TestPass123!",
        full_name="DB Router Test User",
        is_admin=False,
    )
    ac, _csrf = await _login_client(client, email=temp_user["email"], password="TestPass123!")
    try:
        resp = await ac.get("/settings/database/status")
        assert resp.status_code == 403, (
            f"Expected 403 (non-admin blocked), got {resp.status_code}: {resp.text}"
        )
    finally:
        await ac.aclose()
        await _delete_user(db, temp_user["id"])


# ────────────────────────────────────────────────────────────────────────────
# 1.4.3  GET /settings/database/export — admin access
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_database_export_admin(admin_client):
    """1.4.3 — GET /settings/database/export as admin → 200, file download."""
    resp = await admin_client.get("/settings/database/export?format=json&tables=sites")
    assert resp.status_code == 200, (
        f"Expected 200 (database export as admin), got {resp.status_code}: {resp.text}"
    )
    # Must be returned as a downloadable attachment
    content_disposition = resp.headers.get("content-disposition", "")
    assert "attachment" in content_disposition, (
        f"Expected attachment header, got: {content_disposition}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 1.4.4  GET /settings/database/export — non-admin access (403)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_database_export_non_admin(client, db):
    """1.4.4 — GET /settings/database/export as a regular (non-admin) user → 403 Forbidden."""
    sfx = uuid.uuid4().hex[:8]
    temp_user = await _seed_user(
        db,
        email=f"dbexport_{sfx}@test.local",
        username=f"dbexport{sfx}",
        password="TestPass123!",
        full_name="DB Export Test User",
        is_admin=False,
    )
    ac, _csrf = await _login_client(client, email=temp_user["email"], password="TestPass123!")
    try:
        resp = await ac.get("/settings/database/export")
        assert resp.status_code == 403, (
            f"Expected 403 (non-admin blocked), got {resp.status_code}: {resp.text}"
        )
    finally:
        await ac.aclose()
        await _delete_user(db, temp_user["id"])
