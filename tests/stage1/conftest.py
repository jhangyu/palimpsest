"""
---
name: conftest
description: "Shared pytest fixtures"
type: test-utility
target:
  layer: backend
  domain: auth
run:
  command: "PYTHONPATH=.:backend:tests python -m pytest tests/test_auth.py -v --co"
  env: {}
  prerequisites:
    - "Python deps installed"
expected:
  pass: 0
  output: "Fixture collection output"
---

Pytest configuration and shared fixtures for auth/security test suite.

Provides real integration fixtures that connect to a PostgreSQL database
when DATABASE_URL (or TEST_DATABASE_URL) is set.  Falls back to
``pytest.skip`` when no database is available, keeping unit-only runs green.
"""
import os
import re
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Auto-load test-env.sh so tests work without manual `source test-env.sh`
# ---------------------------------------------------------------------------
_test_env_path = Path(__file__).resolve().parent.parent / "scripts" / "test-env.sh"
if _test_env_path.exists():
    for _line in _test_env_path.read_text().splitlines():
        _m = re.match(r'^export\s+(\w+)="(.+)"', _line)
        if _m and _m.group(1) not in os.environ:
            _val = re.sub(r'\$\{(\w+)\}', lambda g: os.environ.get(g.group(1), ''), _m.group(2))
            os.environ[_m.group(1)] = _val

# ---------------------------------------------------------------------------
# Real admin guard — tests must NEVER delete or modify this account.
# ---------------------------------------------------------------------------
REAL_ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", "jhangyu@gmail.com")

# ---------------------------------------------------------------------------
# Environment setup — MUST run before any app imports so that core.db picks
# up the correct DATABASE_URL at module-import time.
# ---------------------------------------------------------------------------

# Allow a dedicated test DB; fall back to the app default.
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

_resolved_url = os.environ.get("DATABASE_URL", "")
if ":5432/" in _resolved_url and "/palimpsest_test" not in _resolved_url:
    import warnings
    warnings.warn(
        "DATABASE_URL appears to point at the production database (port 5432, not palimpsest_test). "
        "Set TEST_DATABASE_URL to a test database to avoid polluting production data.",
        stacklevel=1,
    )

# Disable LLM-provider-profile subsystem to avoid requiring a KEK keyring.
os.environ.setdefault("LLM_PROVIDER_PROFILES_ENABLED", "false")

# httpx ASGITransport does not use HTTPS — disable Secure cookie flag.
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")


def _require_db():
    """Skip the calling fixture/test when no database URL is configured."""
    if not os.environ.get("DATABASE_URL"):
        pytest.skip(
            "No database configured (set DATABASE_URL or TEST_DATABASE_URL)"
        )


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_db_url():
    """Return a test-specific PostgreSQL database URL.

    Reads TEST_DATABASE_URL first, then DATABASE_URL, then a sensible default
    for local development.
    """
    return os.environ.get(
        "TEST_DATABASE_URL",
        os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://palimpsest:testpass123@localhost:5433/palimpsest_test",
        ),
    )


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def cleanup_test_database():
    """Wipe test data at session START and END.

    Runs before any other session fixtures create data (no dependencies),
    and again after all session fixtures have torn down.  Uses its own
    engine so it is independent of the ``db`` fixture lifecycle.

    Tables are deleted in FK-safe order; missing tables are silently ignored.
    The ``roles`` table is intentionally preserved — it is seeded by the
    ``db`` fixture and must survive for the whole session.
    """
    db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        yield
        return

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    # Deletion order respects FK constraints (child tables before parents).
    _TABLES = [
        "rss_query_events",       # → sites
        "articles",               # → sites
        "crawl_repair_attempts",  # → crawl_repair_states / sites
        "crawl_repair_states",    # → sites
        "crawl_attempts",         # → sites
        "sites",
        "user_secret_keys",       # → users
        "user_ai_providers",      # → users / ai_providers
        "ai_providers",
        "auth_sessions",          # → users  (CASCADE)
        "password_reset_tokens",  # → users  (CASCADE)
        "email_verification_tokens",  # → users  (CASCADE)
        "auth_rate_limits",
        "user_roles",             # → users, roles  (CASCADE)
        "users",
    ]

    async def _cleanup(eng):
        async with eng.begin() as conn:
            for table in _TABLES:
                try:
                    await conn.execute(text(f"DELETE FROM {table}"))
                except Exception:
                    pass  # Table may not exist yet or FK violation — skip

    _engine = create_async_engine(db_url)
    try:
        await _cleanup(_engine)
    except Exception:
        pass

    yield

    try:
        await _cleanup(_engine)
    except Exception:
        pass
    finally:
        await _engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db(test_db_url):
    """Provide an async ``databases.Database`` connection bound to the test DB.

    Creates all tables via SQLAlchemy ``metadata.create_all`` and seeds the
    ``admin`` / ``user`` roles that the auth subsystem expects.

    The connection is shared across the entire session for efficiency.
    """
    _require_db()

    import sqlalchemy
    from datetime import datetime, timezone
    from core.db import database, metadata, DATABASE_URL

    # --- Create tables using a synchronous engine ---
    sync_url = DATABASE_URL.replace("+asyncpg", "")
    engine = sqlalchemy.create_engine(sync_url)
    metadata.create_all(engine)

    # Run the AI-provider schema expansion too (idempotent DDL).
    from core.ai_provider_migrations import SCHEMA_EXPANSION_STATEMENTS
    from sqlalchemy import text as sa_text
    with engine.connect() as conn:
        for stmt in SCHEMA_EXPANSION_STATEMENTS:
            try:
                conn.execute(sa_text(stmt))
            except Exception:
                pass
        conn.commit()
    engine.dispose()

    # --- Connect the async ``databases`` driver ---
    if not database.is_connected:
        await database.connect()

    # --- Seed roles (idempotent) ---
    now = datetime.now(timezone.utc)
    for role_name in ("admin", "user"):
        existing = await database.fetch_one(
            "SELECT id FROM roles WHERE name = :name",
            {"name": role_name},
        )
        if not existing:
            await database.execute(
                "INSERT INTO roles (name, description, created_at) "
                "VALUES (:name, :desc, :ts)",
                {"name": role_name, "desc": f"{role_name.title()} role", "ts": now},
            )

    yield database

    if database.is_connected:
        await database.disconnect()


# ---------------------------------------------------------------------------
# HTTP client fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(loop_scope="session")
async def client(db):
    """Async HTTPX test client pointed at the FastAPI app.

    The app lifespan is *not* triggered (httpx ASGITransport only sends HTTP
    scopes).  Instead, ``app.state`` is manually configured so that
    ``Depends(get_db)`` and related DI functions work correctly.
    """
    from main import app
    from httpx import AsyncClient, ASGITransport
    from core.db import set_kek_backend, set_llm_profiles_enabled

    # Inject state normally set by the lifespan handler.
    app.state.database = db
    app.state.kek_backend = None
    app.state.llm_profiles_enabled = False
    set_kek_backend(None)
    set_llm_profiles_enabled(False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _unique_suffix() -> str:
    """Return a short random suffix to avoid collisions across parallel runs."""
    return uuid.uuid4().hex[:8]


async def _seed_user(
    db,
    *,
    email: str,
    username: str,
    password: str = "TestPass123!",
    full_name: str = "Test User",
    status: str = "active",
    is_admin: bool = False,
) -> dict:
    """Insert a user directly into the database and return its row as a dict.

    Also assigns roles (``user`` always, ``admin`` when *is_admin* is True).
    """
    from datetime import datetime, timezone
    from core.auth import hash_password, normalize_email
    from core.db import users, roles, user_roles

    now = datetime.now(timezone.utc)
    pw_hash = await hash_password(password)
    email_norm = normalize_email(email)
    username_norm = username.lower().strip()

    user_id = await db.execute(
        users.insert().values(
            email=email,
            email_normalized=email_norm,
            username=username_norm,
            username_normalized=username_norm,
            full_name=full_name,
            password_hash=pw_hash,
            status=status,
            avatar_source="none",
            preferences={},
            created_at=now,
            updated_at=now,
        )
    )

    # Assign the ``user`` role.
    user_role = await db.fetch_one(
        "SELECT id FROM roles WHERE name = 'user'"
    )
    if user_role:
        await db.execute(
            user_roles.insert().values(user_id=user_id, role_id=user_role["id"])
        )

    # Optionally assign the ``admin`` role.
    if is_admin:
        admin_role = await db.fetch_one(
            "SELECT id FROM roles WHERE name = 'admin'"
        )
        if admin_role:
            await db.execute(
                user_roles.insert().values(user_id=user_id, role_id=admin_role["id"])
            )

    row = await db.fetch_one(users.select().where(users.c.id == user_id))
    return dict(row)


async def _delete_user(db, user_id: int) -> None:
    """Remove a seeded user and all dependent rows (sessions, roles, etc.)."""
    from core.db import auth_sessions, user_roles, users

    # Clean up AI provider data (written by KEK/provider tests)
    try:
        await db.execute("DELETE FROM user_ai_providers WHERE owner_user_id = :uid", {"uid": user_id})
    except Exception:
        pass  # Table may not exist in minimal test setups
    try:
        await db.execute("DELETE FROM user_secret_keys WHERE user_id = :uid", {"uid": user_id})
    except Exception:
        pass  # Table may not exist in minimal test setups

    await db.execute(
        auth_sessions.delete().where(auth_sessions.c.user_id == user_id)
    )
    await db.execute(
        user_roles.delete().where(user_roles.c.user_id == user_id)
    )
    await db.execute(
        users.delete().where(users.c.id == user_id)
    )


async def _login_client(client, email: str, password: str):
    """POST ``/auth/login`` and return a *new* client that carries the session
    and CSRF cookies from the login response.

    Returns ``(authed_client, csrf_token)``.
    """
    from httpx import AsyncClient, ASGITransport
    from main import app

    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, (
        f"Login failed ({resp.status_code}): {resp.text}"
    )

    # Collect cookies from the response.
    cookies = {}
    for name in ("session_token", "csrf_token"):
        val = resp.cookies.get(name)
        if val:
            cookies[name] = val

    # Build a fresh client that carries those cookies.
    ac = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies=cookies,
    )
    csrf = cookies.get("csrf_token", "")
    return ac, csrf


# ---------------------------------------------------------------------------
# User seed fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(loop_scope="session")
async def regular_user(db):
    """Seed and return a regular (non-admin) user record.

    The user is deleted after the test completes.
    """
    sfx = _unique_suffix()
    user = await _seed_user(
        db,
        email=f"regular_{sfx}@test.local",
        username=f"regular{sfx}",
        full_name="Regular User",
        status="active",
        is_admin=False,
    )
    yield user
    await _delete_user(db, user["id"])


@pytest_asyncio.fixture(loop_scope="session")
async def admin_user(db):
    """Seed and return an admin user record.

    The user is deleted after the test completes.
    """
    sfx = _unique_suffix()
    user = await _seed_user(
        db,
        email=f"admin_{sfx}@test.local",
        username=f"adminu{sfx}",
        full_name="Admin User",
        status="active",
        is_admin=True,
    )
    yield user
    await _delete_user(db, user["id"])


@pytest_asyncio.fixture(loop_scope="session")
async def blocked_user(db):
    """Seed and return a user with status='blocked'.

    The user is deleted after the test completes.
    """
    sfx = _unique_suffix()
    user = await _seed_user(
        db,
        email=f"blocked_{sfx}@test.local",
        username=f"blocked{sfx}",
        full_name="Blocked User",
        status="blocked",
        is_admin=False,
    )
    yield user
    await _delete_user(db, user["id"])


# ---------------------------------------------------------------------------
# Authenticated client fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(loop_scope="session")
async def auth_client(client, regular_user):
    """HTTPX client with a valid authenticated session cookie (regular user).

    Logs in via ``POST /auth/login`` using the seeded *regular_user*'s
    credentials.
    """
    ac, _csrf = await _login_client(
        client,
        email=regular_user["email"],
        password="TestPass123!",
    )
    yield ac
    await ac.aclose()


@pytest_asyncio.fixture(loop_scope="session")
async def admin_client(client, admin_user):
    """HTTPX client authenticated as an admin user.

    Logs in via ``POST /auth/login`` using the seeded *admin_user*'s
    credentials.
    """
    ac, _csrf = await _login_client(
        client,
        email=admin_user["email"],
        password="TestPass123!",
    )
    yield ac
    await ac.aclose()


# ---------------------------------------------------------------------------
# CSRF helper
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(loop_scope="session")
async def csrf_token(auth_client):
    """Return a valid CSRF token extracted from the authenticated client's
    cookies.

    The CSRF token is set as a readable cookie (``csrf_token``) during login;
    endpoints that require CSRF validate it via the ``X-CSRF-Token`` header.
    """
    token = auth_client.cookies.get("csrf_token", "")
    if not token:
        # Fallback: hit /auth/me which may refresh cookies.
        resp = await auth_client.get("/auth/me")
        token = resp.cookies.get("csrf_token", "")
    assert token, "Failed to obtain CSRF token from authenticated client"
    return token


# ---------------------------------------------------------------------------
# CSRF helper (reusable non-fixture function)
# ---------------------------------------------------------------------------

async def _get_csrf_token(client) -> str:
    """Extract CSRF token from an authenticated client's cookies."""
    token = client.cookies.get("csrf_token", "")
    if not token:
        resp = await client.get("/auth/me")
        token = resp.cookies.get("csrf_token", "")
    return token


# ---------------------------------------------------------------------------
# KEK (Key Encryption Key) fixtures for AI provider encryption tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def kek_backend(tmp_path_factory):
    """Provide a FileKeyEncryptionBackend with a temp keyring for encryption tests."""
    keyring_dir = tmp_path_factory.mktemp("kek")
    from core.llm.key_backends import FileKeyEncryptionBackend
    FileKeyEncryptionBackend.generate_keyring(str(keyring_dir), "v1")
    return FileKeyEncryptionBackend(str(keyring_dir), "v1")


@pytest_asyncio.fixture(loop_scope="session")
async def kek_client(db, kek_backend):
    """Async HTTPX test client with LLM profiles ENABLED and KEK backend injected.
    Use this for AI provider CRUD tests that need encryption."""
    from main import app
    from httpx import AsyncClient, ASGITransport
    from core.db import set_kek_backend, set_llm_profiles_enabled

    app.state.database = db
    app.state.kek_backend = kek_backend
    app.state.llm_profiles_enabled = True
    set_kek_backend(kek_backend)
    set_llm_profiles_enabled(True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Reset state
    app.state.kek_backend = None
    app.state.llm_profiles_enabled = False
    set_kek_backend(None)
    set_llm_profiles_enabled(False)


@pytest_asyncio.fixture(loop_scope="session")
async def kek_auth_client(kek_client, regular_user):
    """Authenticated client with KEK enabled. For AI provider tests."""
    ac, _csrf = await _login_client(
        kek_client,
        email=regular_user["email"],
        password="TestPass123!",
    )
    yield ac
    await ac.aclose()


@pytest_asyncio.fixture(loop_scope="session")
async def kek_admin_client(kek_client, admin_user):
    """Authenticated admin client with KEK enabled."""
    ac, _csrf = await _login_client(
        kek_client,
        email=admin_user["email"],
        password="TestPass123!",
    )
    yield ac
    await ac.aclose()
