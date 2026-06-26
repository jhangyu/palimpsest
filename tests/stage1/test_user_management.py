"""
---
name: test_user_management
description: "Stage 1.5 — User profile, password, email, avatar integration tests"
stage: stage1
type: pytest
target:
  layer: backend
  domain: user-management
spec_doc: null
test_file: tests/stage1/test_user_management.py
functions:
  - name: test_get_user_profile
    line: 64
    purpose: "GET /users/me → 200, all profile fields present"
    fixtures: [auth_client, regular_user]
  - name: test_update_profile
    line: 86
    purpose: "PUT /users/me → 200, full_name updated in response"
    fixtures: [auth_client, regular_user]
  - name: test_change_password
    line: 106
    purpose: "PUT /users/me/password → 200; old session invalidated, new session usable"
    fixtures: [client, auth_client, regular_user]
  - name: test_change_password_wrong_current
    line: 157
    purpose: "PUT /users/me/password with wrong current_password → 400"
    fixtures: [auth_client]
  - name: test_update_email
    line: 174
    purpose: "PUT /users/me/email → 200, pending_email set in DB"
    fixtures: [auth_client, regular_user, db]
  - name: test_update_username
    line: 201
    purpose: "PUT /users/me/username → 200, username_normalized updated in DB"
    fixtures: [auth_client, regular_user, db]
  - name: test_update_preferences
    line: 228
    purpose: "PUT /users/me/preferences → 200, preferences JSON stored and returned"
    fixtures: [auth_client]
  - name: test_avatar_upload
    line: 249
    purpose: "PUT /users/me/avatar (multipart PNG) → 200, avatar_hash returned; GET serves image bytes"
    fixtures: [auth_client]
  - name: test_avatar_delete
    line: 287
    purpose: "DELETE /users/me/avatar → 200; subsequent GET returns 404"
    fixtures: [auth_client]
  - name: test_set_avatar_source
    line: 317
    purpose: "PUT /users/me/avatar-source → 200, source updated"
    fixtures: [auth_client]
  - name: test_update_email_wrong_password
    line: 334
    purpose: "PUT /users/me/email with wrong password → 401 (skipped: optional)"
    fixtures: [auth_client]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_user_management.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
expected:
  pass: 9
  output: "PASS/FAIL per user management test case"
---

Stage 1.5 User Management integration tests.

Covers: profile GET/PUT, password change (session rotation), email change
(pending + verification flow), username change, preferences, avatar
upload and delete.
"""

from __future__ import annotations

import struct
import uuid
import zlib

import pytest


# ---------------------------------------------------------------------------
# Helper: minimal 1×1 PNG
# ---------------------------------------------------------------------------

def _make_test_png() -> bytes:
    """Construct a minimal 1×1 RGB PNG file entirely in memory (no deps)."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        body = tag + data
        crc = struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        return length + body + crc

    signature = b"\x89PNG\r\n\x1a\n"
    # IHDR: width=1, height=1, bit-depth=8, colour-type=2 (RGB), compress=0, filter=0, interlace=0
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)
    # IDAT: raw scanline = filter-byte(0) + R G B  (red pixel)
    idat = _chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
    iend = _chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


# ---------------------------------------------------------------------------
# 1.5.1  Get user profile
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_get_user_profile(auth_client, regular_user):
    """GET /users/me → 200, all profile fields present."""
    resp = await auth_client.get("/users/me")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["id"] == regular_user["id"]
    assert data["email"] == regular_user["email"]
    assert "username" in data
    assert "roles" in data
    assert isinstance(data["roles"], list)
    # me-specific fields
    assert "pending_email" in data
    assert "preferences" in data
    assert isinstance(data["preferences"], dict)


# ---------------------------------------------------------------------------
# 1.5.2  Update profile (full_name)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_update_profile(auth_client, regular_user):
    """PUT /users/me → 200, full_name updated in response."""
    csrf = auth_client.cookies.get("csrf_token", "")
    new_name = f"Updated Name {uuid.uuid4().hex[:6]}"

    resp = await auth_client.put(
        "/users/me",
        json={"full_name": new_name},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["full_name"] == new_name


# ---------------------------------------------------------------------------
# 1.5.3  Change password (session rotation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_change_password(client, auth_client, regular_user):
    """PUT /users/me/password → 200; old session invalidated, new session usable."""
    from httpx import AsyncClient, ASGITransport
    from main import app

    # Capture old session token before the change
    old_session_token = auth_client.cookies.get("session_token", "")
    assert old_session_token, "auth_client must have a session_token cookie"

    # Create a stale client that holds only the old session token
    stale_client = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"session_token": old_session_token},
    )

    csrf = auth_client.cookies.get("csrf_token", "")
    new_password = "NewTestPass789!"

    try:
        resp = await auth_client.put(
            "/users/me/password",
            json={"current_password": "TestPass123!", "new_password": new_password},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        assert "Password changed" in resp.json().get("message", "")

        # Old session should now be revoked
        stale_resp = await stale_client.get("/auth/me")
        assert stale_resp.status_code == 401, (
            "Old session token should be invalidated after password change"
        )

        # Verify login works with new password
        login_resp = await client.post(
            "/auth/login",
            json={"email": regular_user["email"], "password": new_password},
        )
        assert login_resp.status_code == 200, (
            f"Login with new password failed: {login_resp.text}"
        )
    finally:
        await stale_client.aclose()


# ---------------------------------------------------------------------------
# 1.5.4  Change password — wrong current password
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_change_password_wrong_current(auth_client):
    """PUT /users/me/password with wrong current_password → 400."""
    csrf = auth_client.cookies.get("csrf_token", "")

    resp = await auth_client.put(
        "/users/me/password",
        json={"current_password": "WrongPassword999!", "new_password": "NewPass456!"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 400, resp.text


# ---------------------------------------------------------------------------
# 1.5.5  Update email (pending email set)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_update_email(auth_client, regular_user, db):
    """PUT /users/me/email → 200, pending_email set in DB."""
    from core.db import users

    csrf = auth_client.cookies.get("csrf_token", "")
    sfx = uuid.uuid4().hex[:6]
    new_email = f"newemail_{sfx}@test.local"

    resp = await auth_client.put(
        "/users/me/email",
        json={"new_email": new_email, "password": "TestPass123!"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    assert "Verification email sent" in resp.json().get("message", "")

    # Verify pending_email set in DB
    row = await db.fetch_one(users.select().where(users.c.id == regular_user["id"]))
    assert row is not None
    assert row["pending_email"] == new_email


# ---------------------------------------------------------------------------
# 1.5.6  Update username
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_update_username(auth_client, regular_user, db):
    """PUT /users/me/username → 200, username_normalized updated in DB."""
    from core.db import users

    csrf = auth_client.cookies.get("csrf_token", "")
    sfx = uuid.uuid4().hex[:6].translate(str.maketrans('0123456789', 'qrstuvwxyz'))
    new_username = f"newname{sfx}"

    resp = await auth_client.put(
        "/users/me/username",
        json={"new_username": new_username},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("status") == "ok"

    # Verify username updated in DB
    row = await db.fetch_one(users.select().where(users.c.id == regular_user["id"]))
    assert row is not None
    assert row["username_normalized"] == new_username.lower().strip()


# ---------------------------------------------------------------------------
# 1.5.7  Update preferences
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_update_preferences(auth_client):
    """PUT /users/me/preferences → 200, preferences JSON stored and returned."""
    csrf = auth_client.cookies.get("csrf_token", "")
    prefs = {"theme": "dark", "language": "zh-TW", "pageSize": 25}

    resp = await auth_client.put(
        "/users/me/preferences",
        json={"preferences": prefs},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert data["preferences"] == prefs


# ---------------------------------------------------------------------------
# 1.5.8  Avatar upload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_avatar_upload(auth_client):
    """PUT /users/me/avatar (multipart PNG) → 200, avatar_hash returned;
    GET /users/me/avatar serves image bytes."""
    csrf = auth_client.cookies.get("csrf_token", "")
    png_bytes = _make_test_png()

    upload_resp = await auth_client.put(
        "/users/me/avatar",
        files={"file": ("test.png", png_bytes, "image/png")},
        headers={"X-CSRF-Token": csrf},
    )
    assert upload_resp.status_code == 200, upload_resp.text
    data = upload_resp.json()
    assert "avatar_hash" in data
    assert "avatar_size" in data
    assert data["avatar_size"] > 0

    # Invalidate session cache so require_user re-reads updated user row
    # (with avatar_source="upload" and avatar_bytes set) from the DB.
    from core.auth import invalidate_session_cache
    invalidate_session_cache()

    # Retrieve the avatar
    get_resp = await auth_client.get("/users/me/avatar")
    assert get_resp.status_code == 200
    assert "image/" in get_resp.headers.get("content-type", "")

    # Cleanup — delete avatar so fixture teardown is clean
    await auth_client.delete(
        "/users/me/avatar", headers={"X-CSRF-Token": csrf}
    )


# ---------------------------------------------------------------------------
# 1.5.9  Avatar delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_avatar_delete(auth_client):
    """DELETE /users/me/avatar → 200; subsequent GET returns 404."""
    csrf = auth_client.cookies.get("csrf_token", "")

    # First upload an avatar so there is something to delete
    png_bytes = _make_test_png()
    upload_resp = await auth_client.put(
        "/users/me/avatar",
        files={"file": ("test.png", png_bytes, "image/png")},
        headers={"X-CSRF-Token": csrf},
    )
    assert upload_resp.status_code == 200, upload_resp.text

    # Delete avatar
    del_resp = await auth_client.delete(
        "/users/me/avatar", headers={"X-CSRF-Token": csrf}
    )
    assert del_resp.status_code == 200, del_resp.text
    assert del_resp.json().get("status") == "ok"

    # Subsequent GET should return 404 (no avatar)
    get_resp = await auth_client.get("/users/me/avatar")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# 1.5.10  Set avatar source
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_set_avatar_source(auth_client):
    """PUT /users/me/avatar-source → 200, source updated."""
    csrf = auth_client.cookies.get("csrf_token", "")
    resp = await auth_client.put(
        "/users/me/avatar-source",
        json={"source": "none"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 1.5.11  Email change — wrong password (error path)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Email error paths - optional")
@pytest.mark.asyncio(loop_scope="session")
async def test_update_email_wrong_password(auth_client):
    """PUT /users/me/email with wrong password → 401."""
    csrf = auth_client.cookies.get("csrf_token", "")
    sfx = uuid.uuid4().hex[:6]
    resp = await auth_client.put(
        "/users/me/email",
        json={"new_email": f"newemail_{sfx}@test.local", "password": "WrongPassword999!"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 401
