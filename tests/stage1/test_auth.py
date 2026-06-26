"""
---
name: test_auth
description: "Auth flow tests: first-run setup, login, logout, CSRF, rate limiting, session validation"
stage: stage1
type: pytest
target:
  layer: backend
  domain: auth
spec_doc: null
test_file: tests/stage1/test_auth.py
functions:
  - name: test_first_run_setup
    line: 34
    purpose: "Validates first admin user creation when users table is empty"
    fixtures: [client, db]
  - name: test_first_run_setup_already_done
    line: 106
    purpose: "POST /auth/first-run-setup when users exist → 409 Conflict"
    fixtures: [client, regular_user]
  - name: test_first_run_check
    line: 129
    purpose: "GET /auth/first-run-check reports needs_setup=False when users exist"
    fixtures: [client, regular_user]
  - name: test_login_success
    line: 149
    purpose: "POST /auth/login with valid credentials → 200, cookies set"
    fixtures: [client, regular_user]
  - name: test_login_wrong_password
    line: 171
    purpose: "Wrong password → 401 Unauthorized"
    fixtures: [client, regular_user]
  - name: test_login_blocked_user
    line: 187
    purpose: "Blocked user with correct password → 403 Forbidden"
    fixtures: [client, blocked_user]
  - name: test_login_rate_limit
    line: 203
    purpose: "max_attempts consecutive failed logins → next attempt is 429"
    fixtures: [client, db]
  - name: test_auth_me_authenticated
    line: 243
    purpose: "GET /auth/me with a valid session → 200, user data returned"
    fixtures: [auth_client, regular_user]
  - name: test_auth_me_unauthenticated
    line: 259
    purpose: "GET /auth/me without a session cookie → 401 Unauthorized"
    fixtures: [client]
  - name: test_logout
    line: 272
    purpose: "POST /auth/logout → 200; subsequent /auth/me returns 401"
    fixtures: [auth_client, csrf_token]
  - name: test_csrf_missing_token
    line: 300
    purpose: "POST to CSRF-protected endpoint without X-CSRF-Token → 403"
    fixtures: [auth_client]
  - name: test_csrf_mismatch
    line: 314
    purpose: "POST with an incorrect X-CSRF-Token value → 403 CSRF mismatch"
    fixtures: [auth_client, csrf_token]
  - name: test_register_success
    line: 332
    purpose: "POST /auth/register with public registration enabled → 200"
    fixtures: [client, db]
  - name: test_register_disabled
    line: 374
    purpose: "POST /auth/register when public registration is disabled → 403"
    fixtures: [client]
  - name: test_forgot_password
    line: 403
    purpose: "POST /auth/forgot-password always returns 200 (anti-enumeration)"
    fixtures: [client, regular_user]
  - name: test_reset_password
    line: 432
    purpose: "Insert a reset token directly, POST /auth/reset-password → 200, password changed"
    fixtures: [client, db]
  - name: test_register_duplicate_email
    line: 502
    purpose: "POST /auth/register with an email already in use → 409 Conflict"
    fixtures: [client, db]
  - name: test_register_duplicate_username
    line: 536
    purpose: "POST /auth/register with a username already in use → 409 Conflict"
    fixtures: [client, db]
  - name: test_verify_email
    line: 570
    purpose: "POST /auth/verify-email with a valid token → 200, email verified (skipped: requires SMTP stub)"
    fixtures: [client, regular_user, db]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_auth.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from conftest import _delete_user, _seed_user, REAL_ADMIN_EMAIL


# ────────────────────────────────────────────────────────────────────────────
# 1.1.1  First-run setup on empty DB
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_first_run_setup(client, db):
    """1.1.1 — POST /auth/first-run-setup on empty DB → 200, session cookies, admin role."""
    from core.db import users, user_roles, roles as roles_table

    # --- Save the real admin before wiping so we can restore it afterwards ---
    real_admin_row = await db.fetch_one(
        users.select().where(users.c.email == REAL_ADMIN_EMAIL)
    )
    real_admin_roles: list = []
    if real_admin_row:
        real_admin_roles = await db.fetch_all(
            user_roles.select().where(user_roles.c.user_id == real_admin_row["id"])
        )

    # Wipe all existing users so we have a clean slate for first-run setup.
    # _delete_user handles cascade deletion of sessions, role assignments, etc.
    all_users = await db.fetch_all(users.select())
    for u in all_users:
        await _delete_user(db, u["id"])

    created_id = None
    try:
        resp = await client.post(
            "/auth/first-run-setup",
            json={
                "email": "firstadmin@test.local",
                "username": "firstadmin",
                "password": "AdminPass1!",
                "full_name": "First Admin",
            },
        )
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert data.get("status") == "ok"
        assert "user_id" in data
        created_id = data["user_id"]

        # Both session and CSRF cookies must be present in the response
        assert "session_token" in resp.cookies, "session_token cookie missing"
        assert "csrf_token" in resp.cookies, "csrf_token cookie missing"

        # Admin role must be assigned in the DB
        role_rows = await db.fetch_all(
            user_roles.select().where(user_roles.c.user_id == created_id)
        )
        role_ids = [r["role_id"] for r in role_rows]
        assert role_ids, "No roles assigned to first admin"

        role_name_rows = await db.fetch_all(
            roles_table.select().where(roles_table.c.id.in_(role_ids))
        )
        role_names = {r["name"] for r in role_name_rows}
        assert "admin" in role_names, f"admin role not found in {role_names}"
    finally:
        # Delete the ephemeral test admin created by first-run-setup.
        if created_id:
            await _delete_user(db, created_id)

        # Re-insert the real admin account that was wiped above.
        if real_admin_row:
            await db.execute(users.insert().values(dict(real_admin_row._mapping)))
            for role in real_admin_roles:
                await db.execute(user_roles.insert().values(dict(role._mapping)))


# ────────────────────────────────────────────────────────────────────────────
# 1.1.2  First-run setup already done
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_first_run_setup_already_done(client, regular_user):
    """1.1.2 — POST /auth/first-run-setup when users exist → 409 Conflict."""
    # regular_user fixture is injected purely to ensure a user exists in the DB.
    assert regular_user["id"] > 0
    resp = await client.post(
        "/auth/first-run-setup",
        json={
            "email": "another@test.local",
            "username": "anotheruser",
            "password": "SomePass1!",
            "full_name": "Another User",
        },
    )
    assert resp.status_code == 409, (
        f"Expected 409 (setup already done), got {resp.status_code}: {resp.text}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 1.1.3  First-run check endpoint
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_first_run_check(client, regular_user):
    """1.1.3 — GET /auth/first-run-check reports needs_setup=False when users exist.

    NOTE: We only test the False case here. Testing needs_setup=True would
    require deleting ALL existing users (including the session-scoped
    regular_user fixture), which would break every subsequent test that
    depends on regular_user being present.
    """
    # Ensure at least one user exists (regular_user is injected for this purpose)
    assert regular_user["id"] > 0
    resp = await client.get("/auth/first-run-check")
    assert resp.status_code == 200
    assert resp.json()["needs_setup"] is False


# ────────────────────────────────────────────────────────────────────────────
# 1.1.4  Login success
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_login_success(client, regular_user):
    """1.1.4 — POST /auth/login with valid credentials → 200, cookies set."""
    resp = await client.post(
        "/auth/login",
        json={"email": regular_user["email"], "password": "TestPass123!"},
    )
    assert resp.status_code == 200, f"Login failed ({resp.status_code}): {resp.text}"

    data = resp.json()
    assert "id" in data
    assert data["id"] == regular_user["id"]

    # Both cookies must be issued on login
    assert "session_token" in resp.cookies
    assert "csrf_token" in resp.cookies


# ────────────────────────────────────────────────────────────────────────────
# 1.1.5  Login wrong password
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_login_wrong_password(client, regular_user):
    """1.1.5 — Wrong password → 401 Unauthorized."""
    resp = await client.post(
        "/auth/login",
        json={"email": regular_user["email"], "password": "ThisIsWrong99!"},
    )
    assert resp.status_code == 401, (
        f"Expected 401 (wrong password), got {resp.status_code}: {resp.text}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 1.1.6  Login blocked user
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_login_blocked_user(client, blocked_user):
    """1.1.6 — Blocked user with correct password → 403 Forbidden."""
    resp = await client.post(
        "/auth/login",
        json={"email": blocked_user["email"], "password": "TestPass123!"},
    )
    assert resp.status_code == 403, (
        f"Expected 403 (account blocked), got {resp.status_code}: {resp.text}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 1.1.7  Login rate limit
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_login_rate_limit(client, db):
    """1.1.7 — max_attempts consecutive failed logins → next attempt is 429."""
    from core.db import auth_rate_limits
    from core.auth import normalize_email, RATE_LIMIT_CONFIG

    unique_email = f"ratelimit_{uuid.uuid4().hex[:8]}@test.local"
    max_attempts = RATE_LIMIT_CONFIG["login"]["max_attempts"]  # 5

    # Exhaust the allowed window with bad-password attempts (all must be 401)
    for i in range(max_attempts):
        resp = await client.post(
            "/auth/login",
            json={"email": unique_email, "password": "BadPass!"},
        )
        assert resp.status_code == 401, (
            f"Attempt {i + 1}/{max_attempts}: expected 401, got {resp.status_code}"
        )

    # The next attempt must be locked out
    resp = await client.post(
        "/auth/login",
        json={"email": unique_email, "password": "BadPass!"},
    )
    assert resp.status_code == 429, (
        f"Expected 429 after {max_attempts} failures, got {resp.status_code}: {resp.text}"
    )

    # Cleanup: remove the rate-limit record for this unique email
    email_norm = normalize_email(unique_email)
    subject_hash = hashlib.sha256(f"login:{email_norm}".encode()).hexdigest()
    await db.execute(
        auth_rate_limits.delete().where(auth_rate_limits.c.subject_hash == subject_hash)
    )


# ────────────────────────────────────────────────────────────────────────────
# 1.1.8  /auth/me — authenticated
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_auth_me_authenticated(auth_client, regular_user):
    """1.1.8 — GET /auth/me with a valid session → 200, user data returned."""
    resp = await auth_client.get("/auth/me")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    data = resp.json()
    assert data["id"] == regular_user["id"]
    assert data["email"] == regular_user["email"]
    assert "roles" in data


# ────────────────────────────────────────────────────────────────────────────
# 1.1.9  /auth/me — unauthenticated
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_auth_me_unauthenticated(client):
    """1.1.9 — GET /auth/me without a session cookie → 401 Unauthorized."""
    resp = await client.get("/auth/me")
    assert resp.status_code == 401, (
        f"Expected 401 (no session), got {resp.status_code}: {resp.text}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 1.1.10  Logout
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_logout(auth_client, csrf_token):
    """1.1.10 — POST /auth/logout → 200; subsequent /auth/me returns 401."""
    resp = await auth_client.post(
        "/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 200, f"Logout failed ({resp.status_code}): {resp.text}"
    assert resp.json().get("status") == "ok"

    # The logout response clears the session cookie (Max-Age=0).
    # httpx ASGITransport does not honour Set-Cookie directives automatically,
    # so we manually remove the session cookie and clear the in-process cache
    # to mirror what a real browser would do.
    auth_client.cookies.delete("session_token")
    from core.auth import invalidate_session_cache
    invalidate_session_cache()

    me_resp = await auth_client.get("/auth/me")
    assert me_resp.status_code == 401, (
        f"Expected 401 after logout, got {me_resp.status_code}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 1.1.11  CSRF — missing token
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_csrf_missing_token(auth_client):
    """1.1.11 — POST to CSRF-protected endpoint without X-CSRF-Token → 403."""
    # /auth/logout requires CSRF — omit the header entirely
    resp = await auth_client.post("/auth/logout")
    assert resp.status_code == 403, (
        f"Expected 403 (CSRF missing), got {resp.status_code}: {resp.text}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 1.1.12  CSRF — token mismatch
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_csrf_mismatch(auth_client, csrf_token):
    """1.1.12 — POST with an incorrect X-CSRF-Token value → 403 CSRF mismatch."""
    # Reverse the valid token to create an invalid but same-length value
    wrong_token = csrf_token[::-1]
    resp = await auth_client.post(
        "/auth/logout",
        headers={"X-CSRF-Token": wrong_token},
    )
    assert resp.status_code == 403, (
        f"Expected 403 (CSRF mismatch), got {resp.status_code}: {resp.text}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 1.1.13  Register — public registration enabled
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_register_success(client, db):
    """1.1.13 — POST /auth/register with public registration enabled → 200."""
    sfx = uuid.uuid4().hex[:8].translate(str.maketrans('0123456789', 'qrstuvwxyz'))
    # Username must be lowercase letters only, 1-20 chars, non-reserved
    username = f"tester{sfx}"[:20]
    payload = {
        "email": f"newuser_{sfx}@test.local",
        "username": username,
        "password": "RegPass1234",
        "full_name": "New User",
    }

    original_env = os.environ.get("AUTH_ALLOW_PUBLIC_REGISTRATION")
    os.environ["AUTH_ALLOW_PUBLIC_REGISTRATION"] = "true"
    registered_id = None
    try:
        resp = await client.post("/auth/register", json=payload)
        assert resp.status_code == 200, (
            f"Expected 200 (register), got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "id" in data
        registered_id = data["id"]
        assert data["email"] == payload["email"]
        assert "session_token" in resp.cookies
        assert "csrf_token" in resp.cookies
    finally:
        # Restore original env value
        if original_env is None:
            os.environ.pop("AUTH_ALLOW_PUBLIC_REGISTRATION", None)
        else:
            os.environ["AUTH_ALLOW_PUBLIC_REGISTRATION"] = original_env
        # Remove the registered user from the DB
        if registered_id:
            await _delete_user(db, registered_id)


# ────────────────────────────────────────────────────────────────────────────
# 1.1.14  Register — public registration disabled
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_register_disabled(client):
    """1.1.14 — POST /auth/register when public registration is disabled → 403."""
    original_env = os.environ.get("AUTH_ALLOW_PUBLIC_REGISTRATION")
    os.environ["AUTH_ALLOW_PUBLIC_REGISTRATION"] = "false"
    try:
        resp = await client.post(
            "/auth/register",
            json={
                "email": "blocked_reg@test.local",
                "username": "blockedreg",
                "password": "SomePass1!",
                "full_name": "Blocked Reg",
            },
        )
        assert resp.status_code == 403, (
            f"Expected 403 (registration disabled), got {resp.status_code}: {resp.text}"
        )
    finally:
        if original_env is None:
            os.environ.pop("AUTH_ALLOW_PUBLIC_REGISTRATION", None)
        else:
            os.environ["AUTH_ALLOW_PUBLIC_REGISTRATION"] = original_env


# ────────────────────────────────────────────────────────────────────────────
# 1.1.15  Forgot password — no user enumeration
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_forgot_password(client, regular_user):
    """1.1.15 — POST /auth/forgot-password always returns 200 (anti-enumeration)."""
    # Case A: real user email
    resp = await client.post(
        "/auth/forgot-password",
        json={"email": regular_user["email"]},
    )
    assert resp.status_code == 200, (
        f"Expected 200 for real email, got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert data.get("status") == "ok"

    # Case B: completely nonexistent email — must also return 200
    resp2 = await client.post(
        "/auth/forgot-password",
        json={"email": f"nobody_{uuid.uuid4().hex[:8]}@nowhere.invalid"},
    )
    assert resp2.status_code == 200, (
        f"Expected 200 for nonexistent email, got {resp2.status_code}: {resp2.text}"
    )
    assert resp2.json().get("status") == "ok"


# ────────────────────────────────────────────────────────────────────────────
# 1.1.16  Reset password using a valid token
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_reset_password(client, db):
    """1.1.16 — Insert a reset token directly, POST /auth/reset-password → 200, password changed.

    Uses a dedicated ephemeral user so that resetting the password does NOT
    affect the session-scoped regular_user (whose password is relied upon by
    auth_client and other fixtures).
    """
    from core.auth import generate_reset_token, hash_token
    from core.db import password_reset_tokens

    sfx = uuid.uuid4().hex[:8]
    temp_user = await _seed_user(
        db,
        email=f"resettest_{sfx}@test.local",
        username=f"resettest{sfx}",
        password="TestPass123!",
        full_name="Reset Test User",
    )
    try:
        # Generate a raw token and store its hash in the DB (mimics the forgot-password flow)
        raw_token = generate_reset_token()
        token_hash = hash_token(raw_token)
        now = datetime.now(timezone.utc)

        await db.execute(
            password_reset_tokens.insert().values(
                user_id=temp_user["id"],
                token_hash=token_hash,
                created_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )

        new_password = "ChangedPass99"

        resp = await client.post(
            "/auth/reset-password",
            json={"token": raw_token, "new_password": new_password},
        )
        assert resp.status_code == 200, (
            f"Expected 200 (reset password), got {resp.status_code}: {resp.text}"
        )
        assert resp.json().get("status") == "ok"

        # Verify the old password is rejected for the temp user
        old_login = await client.post(
            "/auth/login",
            json={"email": temp_user["email"], "password": "TestPass123!"},
        )
        assert old_login.status_code == 401, (
            f"Old password should be rejected after reset, got {old_login.status_code}"
        )

        # Verify the new password works for the temp user
        new_login = await client.post(
            "/auth/login",
            json={"email": temp_user["email"], "password": new_password},
        )
        assert new_login.status_code == 200, (
            f"New password should succeed after reset, got {new_login.status_code}: {new_login.text}"
        )
    finally:
        await _delete_user(db, temp_user["id"])


# ────────────────────────────────────────────────────────────────────────────
# 1.1.17  Register — duplicate email
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_register_duplicate_email(client, db):
    """1.1.17 — POST /auth/register with an email already in use → 409 Conflict."""
    original_env = os.environ.get("AUTH_ALLOW_PUBLIC_REGISTRATION")
    os.environ["AUTH_ALLOW_PUBLIC_REGISTRATION"] = "true"
    sfx = uuid.uuid4().hex[:8].translate(str.maketrans('0123456789', 'qrstuvwxyz'))
    email = f"dupemail_{sfx}@test.local"
    username = f"dupemail{sfx}"
    existing = await _seed_user(db, email=email, username=username)
    try:
        resp = await client.post(
            "/auth/register",
            json={
                "email": email,
                "username": f"other{sfx}",
                "password": "RegPass1234!",
                "full_name": "Duplicate Email User",
            },
        )
        assert resp.status_code == 409, (
            f"Expected 409 (duplicate email), got {resp.status_code}: {resp.text}"
        )
    finally:
        await _delete_user(db, existing["id"])
        if original_env is None:
            os.environ.pop("AUTH_ALLOW_PUBLIC_REGISTRATION", None)
        else:
            os.environ["AUTH_ALLOW_PUBLIC_REGISTRATION"] = original_env


# ────────────────────────────────────────────────────────────────────────────
# 1.1.18  Register — duplicate username
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_register_duplicate_username(client, db):
    """1.1.18 — POST /auth/register with a username already in use → 409 Conflict."""
    original_env = os.environ.get("AUTH_ALLOW_PUBLIC_REGISTRATION")
    os.environ["AUTH_ALLOW_PUBLIC_REGISTRATION"] = "true"
    sfx = uuid.uuid4().hex[:8].translate(str.maketrans('0123456789', 'qrstuvwxyz'))
    username = f"dupuser{sfx}"
    existing = await _seed_user(db, email=f"dupuser_{sfx}@test.local", username=username)
    try:
        resp = await client.post(
            "/auth/register",
            json={
                "email": f"newuser_{sfx}@test.local",
                "username": username,
                "password": "RegPass1234!",
                "full_name": "Duplicate Username User",
            },
        )
        assert resp.status_code == 409, (
            f"Expected 409 (duplicate username), got {resp.status_code}: {resp.text}"
        )
    finally:
        await _delete_user(db, existing["id"])
        if original_env is None:
            os.environ.pop("AUTH_ALLOW_PUBLIC_REGISTRATION", None)
        else:
            os.environ["AUTH_ALLOW_PUBLIC_REGISTRATION"] = original_env


# ────────────────────────────────────────────────────────────────────────────
# 1.1.19  Verify email — skipped (requires SMTP stub)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="Email verification requires SMTP stub - optional")
@pytest.mark.asyncio(loop_scope="session")
async def test_verify_email(client, regular_user, db):
    """1.1.19 — POST /auth/verify-email with a valid token → 200, email verified.

    This test is skipped because the send-verification flow requires an SMTP
    stub to deliver the token.  The test body shows WHAT would be tested:
    insert a token directly, call /auth/verify-email, confirm email_verified_at
    is set in the DB.
    """
    from core.auth import generate_reset_token, hash_token
    from core.db import email_verification_tokens, users

    raw_token = generate_reset_token()
    token_hash = hash_token(raw_token)
    now = datetime.now(timezone.utc)

    await db.execute(
        email_verification_tokens.insert().values(
            user_id=regular_user["id"],
            token_hash=token_hash,
            email=regular_user["email"],
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
    )

    resp = await client.post(
        "/auth/verify-email",
        json={"token": raw_token},
    )
    assert resp.status_code == 200, (
        f"Expected 200 (email verified), got {resp.status_code}: {resp.text}"
    )
    assert resp.json().get("status") == "ok"

    # Confirm email_verified_at is now set in the DB
    user_row = await db.fetch_one(users.select().where(users.c.id == regular_user["id"]))
    assert user_row["email_verified_at"] is not None, (
        "email_verified_at should be non-null after successful verification"
    )
