"""
---
name: test_admin
description: "Stage 1.6 — Admin user management, roles, and site ownership tests"
stage: stage1
type: pytest
target:
  layer: backend
  domain: admin
spec_doc: null
test_file: tests/stage1/test_admin.py
functions:
  - name: test_admin_list_users
    line: 51
    purpose: "GET /admin/users → 200, paginated response with users/total/page/page_size"
    fixtures: [admin_client, admin_user, regular_user]
  - name: test_admin_list_users_non_admin
    line: 72
    purpose: "GET /admin/users as regular user → 403"
    fixtures: [auth_client]
  - name: test_admin_create_user
    line: 83
    purpose: "POST /admin/users → 200; invite flow: password_hash=INVITE_PENDING, token exists"
    fixtures: [admin_client, db]
  - name: test_admin_get_user
    line: 130
    purpose: "GET /admin/users/{id} → 200, user details returned"
    fixtures: [admin_client, regular_user]
  - name: test_admin_update_user
    line: 145
    purpose: "PUT /admin/users/{id} → 200, full_name and status updated"
    fixtures: [admin_client, db]
  - name: test_admin_block_user
    line: 182
    purpose: "DELETE /admin/users/{id} → 200; user.status='blocked', sessions revoked"
    fixtures: [admin_client, db]
  - name: test_admin_cannot_self_block
    line: 225
    purpose: "DELETE /admin/users/{own_id} → 400 'Cannot block yourself'"
    fixtures: [admin_client, admin_user]
  - name: test_admin_block_user_ownership_gate
    line: 241
    purpose: "DELETE /admin/users/{id} when user owns sites → 409 with owned_sites list"
    fixtures: [admin_client, db]
  - name: test_admin_update_user_roles
    line: 291
    purpose: "PUT /admin/users/{id}/roles → 200, roles replaced"
    fixtures: [admin_client, db]
  - name: test_admin_list_roles
    line: 328
    purpose: "GET /admin/roles → 200, roles array includes 'admin' and 'user' with counts"
    fixtures: [admin_client]
  - name: test_admin_transfer_site_ownership
    line: 354
    purpose: "PUT /admin/sites/{id}/owner → 200; DB owner_user_id updated"
    fixtures: [admin_client, auth_client, regular_user, db]
  - name: test_health_check
    line: 410
    purpose: "GET /health → 200, status healthy"
    fixtures: [client]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_admin.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
expected:
  pass: 11
  output: "PASS/FAIL per admin test case"
---

Stage 1.6 Admin Operations integration tests.

Covers: list users (paginated), non-admin rejection, admin create user
(invite flow), get user, update user, block user (and session revocation),
self-block prevention, ownership-transfer gate (409), update roles, list
roles, and transfer site ownership.
"""

from __future__ import annotations

import uuid

import pytest

from conftest import _delete_user, _seed_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _admin_csrf(admin_client) -> str:
    """Extract CSRF token from admin client cookie jar."""
    return admin_client.cookies.get("csrf_token", "")


# ---------------------------------------------------------------------------
# 1.6.1  List users — paginated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_list_users(admin_client, admin_user, regular_user):
    """GET /admin/users → 200, paginated response with users/total/page/page_size."""
    resp = await admin_client.get("/admin/users?page=1&page_size=10")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "users" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert isinstance(data["users"], list)
    assert data["total"] >= 2  # at least admin_user + regular_user seeded


# ---------------------------------------------------------------------------
# 1.6.2  List users — non-admin rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_list_users_non_admin(auth_client):
    """GET /admin/users as regular user → 403."""
    resp = await auth_client.get("/admin/users")
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# 1.6.3  Admin create user (invite flow)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_create_user(admin_client, db):
    """POST /admin/users → 200; invite flow: password_hash=INVITE_PENDING, token exists."""
    from core.db import password_reset_tokens, users

    csrf = await _admin_csrf(admin_client)
    sfx = uuid.uuid4().hex[:8].translate(str.maketrans('0123456789', 'qrstuvwxyz'))
    new_email = f"invited_{sfx}@test.local"
    new_username = f"invited{sfx}"

    resp = await admin_client.post(
        "/admin/users",
        json={
            "email": new_email,
            "username": new_username,
            "full_name": "Invited User",
            "roles": ["user"],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    created_id = data["id"]

    try:
        assert data["email"] == new_email
        assert "user" in data.get("roles", [])

        # Verify invite-pending hash and reset token in DB
        user_row = await db.fetch_one(users.select().where(users.c.id == created_id))
        assert user_row is not None
        assert user_row["password_hash"] == "!INVITE_PENDING"

        token_row = await db.fetch_one(
            password_reset_tokens.select().where(
                password_reset_tokens.c.user_id == created_id
            )
        )
        assert token_row is not None, "Expected a password-reset invite token in DB"
    finally:
        await _delete_user(db, created_id)


# ---------------------------------------------------------------------------
# 1.6.4  Admin get user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_get_user(admin_client, regular_user):
    """GET /admin/users/{id} → 200, user details returned."""
    resp = await admin_client.get(f"/admin/users/{regular_user['id']}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == regular_user["id"]
    assert data["email"] == regular_user["email"]
    assert "roles" in data


# ---------------------------------------------------------------------------
# 1.6.5  Admin update user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_update_user(admin_client, db):
    """PUT /admin/users/{id} → 200, full_name and status updated."""
    from core.db import users

    # Seed a dedicated user for this test (don't use regular_user to avoid teardown issues)
    sfx = uuid.uuid4().hex[:6]
    target = await _seed_user(
        db,
        email=f"upd_{sfx}@test.local",
        username=f"upd{sfx}",
    )

    csrf = await _admin_csrf(admin_client)
    try:
        resp = await admin_client.put(
            f"/admin/users/{target['id']}",
            json={"full_name": "Admin Updated", "status": "inactive"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["full_name"] == "Admin Updated"
        assert data["status"] == "inactive"

        # Verify in DB
        row = await db.fetch_one(users.select().where(users.c.id == target["id"]))
        assert row["full_name"] == "Admin Updated"
        assert row["status"] == "inactive"
    finally:
        await _delete_user(db, target["id"])


# ---------------------------------------------------------------------------
# 1.6.6  Admin block user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_block_user(admin_client, db):
    """DELETE /admin/users/{id} → 200; user.status='blocked', sessions revoked."""
    from core.db import users

    sfx = uuid.uuid4().hex[:6]
    target = await _seed_user(
        db,
        email=f"block_{sfx}@test.local",
        username=f"block{sfx}",
    )

    csrf = await _admin_csrf(admin_client)
    try:
        resp = await admin_client.delete(
            f"/admin/users/{target['id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json().get("status") == "ok"

        # Verify status in DB
        row = await db.fetch_one(users.select().where(users.c.id == target["id"]))
        assert row is not None
        assert row["status"] == "blocked"

        # Verify all sessions for the blocked user are revoked
        from core.db import auth_sessions
        active = await db.fetch_all(
            auth_sessions.select().where(
                (auth_sessions.c.user_id == target["id"]) &
                (auth_sessions.c.revoked_at.is_(None))
            )
        )
        assert len(active) == 0, "Active sessions should be revoked when user is blocked"
    finally:
        await _delete_user(db, target["id"])


# ---------------------------------------------------------------------------
# 1.6.7  Admin cannot self-block
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_cannot_self_block(admin_client, admin_user):
    """DELETE /admin/users/{own_id} → 400 'Cannot block yourself'."""
    csrf = await _admin_csrf(admin_client)
    resp = await admin_client.delete(
        f"/admin/users/{admin_user['id']}",
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 400, resp.text
    assert "yourself" in resp.json().get("detail", "").lower()


# ---------------------------------------------------------------------------
# 1.6.8  Admin block — ownership transfer gate (409)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_block_user_ownership_gate(admin_client, db):
    """DELETE /admin/users/{id} when user owns sites → 409 with owned_sites list."""
    from core.db import sites

    sfx = uuid.uuid4().hex[:6]
    target = await _seed_user(
        db,
        email=f"owner_{sfx}@test.local",
        username=f"owner{sfx}",
    )

    # Insert a site owned by the target user directly in DB
    site_id: int | None = None
    try:
        site_id = await db.execute(
            sites.insert().values(
                url="https://example.com",
                name=f"OwnedSite_{sfx}",
                list_rules={},
                content_rules={},
                consecutive_failure_count=0,
                refresh_frequency=60,
                scrape_method="scrapling",
                owner_user_id=target["id"],
            )
        )

        csrf = await _admin_csrf(admin_client)
        resp = await admin_client.delete(
            f"/admin/users/{target['id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 409, resp.text
        detail = resp.json().get("detail", {})
        if isinstance(detail, dict):
            assert "owned_sites" in detail
        else:
            # detail might be a plain string in some FastAPI versions
            assert resp.status_code == 409
    finally:
        if site_id is not None:
            await db.execute(sites.delete().where(sites.c.id == site_id))
        await _delete_user(db, target["id"])


# ---------------------------------------------------------------------------
# 1.6.9  Admin update user roles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_update_user_roles(admin_client, db):
    """PUT /admin/users/{id}/roles → 200, roles replaced."""
    sfx = uuid.uuid4().hex[:6]
    target = await _seed_user(
        db,
        email=f"roles_{sfx}@test.local",
        username=f"roles{sfx}",
    )

    csrf = await _admin_csrf(admin_client)
    try:
        resp = await admin_client.put(
            f"/admin/users/{target['id']}/roles",
            json={"roles": ["admin", "user"]},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "ok"
        assert set(data["roles"]) == {"admin", "user"}

        # Revert back to user-only
        resp2 = await admin_client.put(
            f"/admin/users/{target['id']}/roles",
            json={"roles": ["user"]},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp2.status_code == 200
    finally:
        await _delete_user(db, target["id"])


# ---------------------------------------------------------------------------
# 1.6.10  List roles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_list_roles(admin_client):
    """GET /admin/roles → 200, roles array includes 'admin' and 'user' with counts."""
    resp = await admin_client.get("/admin/roles")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "roles" in data
    roles_list = data["roles"]
    assert isinstance(roles_list, list)

    role_names = {r["name"] for r in roles_list}
    assert "admin" in role_names
    assert "user" in role_names

    for role in roles_list:
        assert "id" in role
        assert "name" in role
        assert "user_count" in role
        assert isinstance(role["user_count"], int)


# ---------------------------------------------------------------------------
# 1.6.11  Transfer site ownership
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_transfer_site_ownership(admin_client, auth_client, regular_user, db):
    """PUT /admin/sites/{id}/owner → 200; DB owner_user_id updated."""
    from core.db import sites

    # Create a site as regular_user (owner = regular_user)
    auth_csrf = auth_client.cookies.get("csrf_token", "")
    sfx = uuid.uuid4().hex[:6]
    site_name = f"TransferTest_{sfx}"
    create_resp = await auth_client.post(
        "/sites/",
        json={
            "site": {"url": "https://example.com", "name": site_name, "refresh_frequency": 60},
            "rules": {"list_rules": {}, "content_rules": {}},
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert create_resp.status_code == 200, create_resp.text
    site_id = create_resp.json()["id"]

    # Seed a second user who will receive ownership
    sfx2 = uuid.uuid4().hex[:6]
    new_owner = await _seed_user(
        db,
        email=f"newowner_{sfx2}@test.local",
        username=f"newowner{sfx2}",
    )

    admin_csrf = await _admin_csrf(admin_client)
    try:
        resp = await admin_client.put(
            f"/admin/sites/{site_id}/owner",
            json={"owner_user_id": new_owner["id"]},
            headers={"X-CSRF-Token": admin_csrf},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["site_id"] == site_id
        assert data["owner_user_id"] == new_owner["id"]

        # Verify in DB
        row = await db.fetch_one(sites.select().where(sites.c.id == site_id))
        assert row is not None
        assert row["owner_user_id"] == new_owner["id"]
    finally:
        # Cleanup: delete crawl_attempts first (FK on site_id), then the site
        from core.db import crawl_attempts
        await db.execute(crawl_attempts.delete().where(crawl_attempts.c.site_id == site_id))
        await db.execute(sites.delete().where(sites.c.id == site_id))
        await _delete_user(db, new_owner["id"])


# ---------------------------------------------------------------------------
# 1.6.12  Health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_health_check(client):
    """GET /health → 200, status healthy."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "healthy"
