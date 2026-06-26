# backend/core/auth.py
"""
---
name: auth
description: "Authentication core: Argon2id password hashing, session/CSRF/reset token generation, cookie helpers, CSRF validation, DB-backed rate limiting, FastAPI dependency factories"
type: core
target:
  layer: backend
  domain: auth
spec_doc: null
test_file: tests/stage1/test_auth.py
functions:
  - name: hash_password
    line: 42
    purpose: "Hash plaintext password with Argon2id (async, thread pool executor)"
  - name: verify_password
    line: 52
    purpose: "Verify plaintext against Argon2id hash; returns True/False"
  - name: generate_session_token
    line: 74
    purpose: "Generate 256-bit URL-safe random session token"
  - name: hash_token
    line: 79
    purpose: "SHA-256 hash a token for DB storage"
  - name: generate_csrf_token
    line: 86
    purpose: "Generate URL-safe CSRF token"
  - name: generate_reset_token
    line: 93
    purpose: "Generate URL-safe password reset / verification token"
  - name: validate_csrf
    line: 161
    purpose: "Validate CSRF double-submit: cookie vs X-CSRF-Token header"
  - name: check_origin
    line: 186
    purpose: "Check Origin/Referer header against configured allowlist"
  - name: validate_username
    line: 235
    purpose: "Validate username: lowercase English, 1-20 chars, not reserved"
  - name: validate_password
    line: 259
    purpose: "Validate password: 8-20 chars"
  - name: check_rate_limit
    line: 291
    purpose: "DB-backed rate limit check; returns (allowed, retry_after_seconds)"
  - name: record_attempt
    line: 347
    purpose: "Record a failed auth attempt for rate limiting"
  - name: clear_rate_limit
    line: 404
    purpose: "Clear rate limit record on successful auth"
  - name: cleanup_expired_sessions
    line: 420
    purpose: "Delete expired/revoked auth sessions; returns count deleted"
  - name: make_get_current_user
    line: 471
    purpose: "Factory: create get_current_user FastAPI dependency (TTL-cached session JOIN)"
  - name: make_require_user
    line: 524
    purpose: "Factory: create require_user FastAPI dependency (raises 401 if unauthenticated)"
  - name: make_require_admin
    line: 534
    purpose: "Factory: create require_admin FastAPI dependency (raises 403 if not admin)"
  # Total: ~29 functions/helpers; main public API listed above
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

import asyncio
import secrets
import hashlib
import re
import os
from datetime import datetime, timedelta, timezone
from functools import partial
from cachetools import TTLCache

from argon2 import PasswordHasher, Type as Argon2Type
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from fastapi import Request, Response, HTTPException, Depends
from sqlalchemy import text


# --- Password Hashing (Argon2id) ---

_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=1,
    hash_len=32,
    type=Argon2Type.ID,  # Argon2id
)


async def hash_password(password: str) -> str:
    """Hash a password using Argon2id. Returns PHC string.

    Runs in a thread pool executor to avoid blocking the async event loop
    (Argon2id with memory_cost=65536 takes ~150-250ms). (DPERF-001)
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _ph.hash, password)


async def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against an Argon2id hash. Returns True/False.

    Runs in a thread pool executor to avoid blocking the async event loop
    (Argon2id with memory_cost=65536 takes ~150-250ms). (DPERF-001)
    """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None, partial(_ph.verify, password_hash, password)
        )
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Check if the hash needs to be rehashed with updated parameters."""
    return _ph.check_needs_rehash(password_hash)


# --- Session Token ---

def generate_session_token() -> str:
    """Generate a 256-bit random session token (URL-safe base64, 32 bytes)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token using SHA-256 for storage. Returns hex digest."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- CSRF Token ---

def generate_csrf_token() -> str:
    """Generate a CSRF token (URL-safe base64, 32 bytes)."""
    return secrets.token_urlsafe(32)


# --- Reset / Verification Token ---

def generate_reset_token() -> str:
    """Generate a reset/verification token (URL-safe base64, 48 bytes)."""
    return secrets.token_urlsafe(48)


# --- Cookie Helpers ---

def _is_secure_cookie() -> bool:
    """Determine if cookies should use Secure flag based on env."""
    return os.getenv("SESSION_COOKIE_SECURE", "true").lower() in ("true", "1", "yes")


def _session_ttl_seconds() -> int:
    """Get session TTL in seconds from env (default 24 hours)."""
    hours = int(os.getenv("SESSION_TTL_HOURS", "24"))
    return hours * 3600


def set_session_cookie(response: Response, token: str) -> None:
    """Set the session cookie on a response."""
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=_is_secure_cookie(),
        samesite="lax",
        path="/",
        max_age=_session_ttl_seconds(),
    )


def clear_session_cookie(response: Response) -> None:
    """Clear the session cookie."""
    response.delete_cookie(
        key="session_token",
        httponly=True,
        secure=_is_secure_cookie(),
        samesite="lax",
        path="/",
    )


def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    """Set the CSRF cookie (readable by JS, not HttpOnly)."""
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # JS must read this
        secure=_is_secure_cookie(),
        samesite="lax",
        path="/",
        max_age=_session_ttl_seconds(),
    )


def clear_csrf_cookie(response: Response) -> None:
    """Clear the CSRF cookie."""
    response.delete_cookie(
        key="csrf_token",
        httponly=False,
        secure=_is_secure_cookie(),
        samesite="lax",
        path="/",
    )


# --- CSRF Validation ---

def validate_csrf(request: Request) -> None:
    """Validate CSRF double-submit: cookie value must match X-CSRF-Token header.

    Raises HTTPException 403 if invalid.
    """
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("x-csrf-token")

    if not cookie_token or not header_token:
        raise HTTPException(status_code=403, detail="CSRF token missing")

    if not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="CSRF token mismatch")


# --- Origin / Referer Allowlist ---

def _get_allowed_origins() -> list[str]:
    """Get allowed origins from env. Returns empty list if not set."""
    raw = os.getenv("ALLOWED_ORIGINS", "")
    if not raw.strip():
        return []
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def check_origin(request: Request) -> None:
    """Check Origin/Referer header against allowlist.

    Raises HTTPException 403 if the origin is not in the allowlist.
    If no allowlist is configured, allows all (dev mode).
    """
    allowed = _get_allowed_origins()
    if not allowed:
        # No allowlist configured — allow all (development mode)
        return

    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")

    if origin:
        origin_clean = origin.rstrip("/")
        if origin_clean in allowed:
            return
    elif referer:
        # Extract origin from referer
        from urllib.parse import urlparse
        parsed = urlparse(referer)
        referer_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        if referer_origin in allowed:
            return

    # If neither origin nor referer present (e.g., same-origin navigation), allow
    if not origin and not referer:
        return

    raise HTTPException(status_code=403, detail="Origin not allowed")


# --- Username Validation ---

RESERVED_USERNAMES = frozenset([
    "admin", "root", "api", "rss", "settings", "auth", "system",
    "user", "users", "login", "logout", "register", "signup",
    "password", "reset", "verify", "health", "status", "test",
    "null", "undefined", "none", "true", "false",
    "moderator", "mod", "administrator", "superuser", "super",
    "support", "help", "info", "contact", "about",
    "dashboard", "analytics", "crawl", "feeds", "articles",
    "config", "configuration", "profile", "account",
])

_USERNAME_PATTERN = re.compile(r"^[a-z]{1,20}$")


def validate_username(username: str) -> tuple[bool, str]:
    """Validate username: lowercase English only, 1-20 chars, not reserved.

    Returns (is_valid, error_message).
    """
    if not username:
        return False, "Username is required"

    if not _USERNAME_PATTERN.match(username):
        return False, "Username must be 1-20 lowercase English letters only (a-z)"

    if username in RESERVED_USERNAMES:
        return False, "This username is reserved"

    return True, ""


def normalize_username(username: str) -> str:
    """Normalize username: lowercase + strip."""
    return username.lower().strip()


# --- Password Validation ---

def validate_password(password: str) -> tuple[bool, str]:
    """Validate password: 8-20 chars, no composition rules.

    Returns (is_valid, error_message).
    """
    if not password:
        return False, "Password is required"
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if len(password) > 20:
        return False, "Password must be at most 20 characters"
    return True, ""


# --- Email Normalization ---

def normalize_email(email: str) -> str:
    """Normalize email: lowercase + strip."""
    return email.lower().strip()


# --- Rate Limiting (DB-backed) ---

# Configuration
RATE_LIMIT_CONFIG = {
    "login": {"max_attempts": 5, "window_seconds": 300, "lockout_seconds": 900},
    "forgot_password": {"max_attempts": 3, "window_seconds": 600, "lockout_seconds": 1800},
    "reset_password": {"max_attempts": 5, "window_seconds": 600, "lockout_seconds": 1800},
    "resend_verification": {"max_attempts": 3, "window_seconds": 600, "lockout_seconds": 1800},
}


async def check_rate_limit(
    database, auth_rate_limits, scope: str, subject: str
) -> tuple[bool, int | None]:
    """Check if a rate limit applies.

    Args:
        database: AsyncSession instance
        auth_rate_limits: the SQLAlchemy Table
        scope: e.g. 'login', 'forgot_password'
        subject: the subject identifier (email, IP, etc.)

    Returns:
        (is_allowed, retry_after_seconds or None)
    """
    config = RATE_LIMIT_CONFIG.get(scope)
    if not config:
        return True, None

    subject_hash = hashlib.sha256(f"{scope}:{subject}".encode()).hexdigest()
    now = datetime.now(timezone.utc)

    row = (await database.execute(
        auth_rate_limits.select().where(
            (auth_rate_limits.c.scope == scope) &
            (auth_rate_limits.c.subject_hash == subject_hash)
        )
    )).mappings().first()

    if not row:
        return True, None

    # Check lockout
    if row["locked_until"] and row["locked_until"] > now:
        remaining = int((row["locked_until"] - now).total_seconds())
        return False, remaining

    # Check window
    window_start = row["window_started_at"]
    if window_start and (now - window_start).total_seconds() > config["window_seconds"]:
        # Window expired — reset will happen on next record_attempt
        return True, None

    if row["attempts"] >= config["max_attempts"]:
        # Lock out
        locked_until = now + timedelta(seconds=config["lockout_seconds"])
        await database.execute(
            auth_rate_limits.update()
            .where(auth_rate_limits.c.id == row["id"])
            .values(locked_until=locked_until, updated_at=now)
        )
        await database.commit()
        return False, config["lockout_seconds"]

    return True, None


async def record_attempt(
    database, auth_rate_limits, scope: str, subject: str
) -> None:
    """Record a failed attempt for rate limiting."""
    config = RATE_LIMIT_CONFIG.get(scope)
    if not config:
        return

    subject_hash = hashlib.sha256(f"{scope}:{subject}".encode()).hexdigest()
    now = datetime.now(timezone.utc)

    row = (await database.execute(
        auth_rate_limits.select().where(
            (auth_rate_limits.c.scope == scope) &
            (auth_rate_limits.c.subject_hash == subject_hash)
        )
    )).mappings().first()

    if not row:
        await database.execute(
            auth_rate_limits.insert().values(
                scope=scope,
                subject_hash=subject_hash,
                attempts=1,
                window_started_at=now,
                locked_until=None,
                updated_at=now,
            )
        )
        await database.commit()
    else:
        window_start = row["window_started_at"]
        if window_start and (now - window_start).total_seconds() > config["window_seconds"]:
            # Window expired — reset
            await database.execute(
                auth_rate_limits.update()
                .where(auth_rate_limits.c.id == row["id"])
                .values(
                    attempts=1,
                    window_started_at=now,
                    locked_until=None,
                    updated_at=now,
                )
            )
            await database.commit()
        else:
            await database.execute(
                auth_rate_limits.update()
                .where(auth_rate_limits.c.id == row["id"])
                .values(
                    attempts=row["attempts"] + 1,
                    updated_at=now,
                )
            )
            await database.commit()


async def clear_rate_limit(
    database, auth_rate_limits, scope: str, subject: str
) -> None:
    """Clear rate limit on success (e.g., successful login)."""
    subject_hash = hashlib.sha256(f"{scope}:{subject}".encode()).hexdigest()
    await database.execute(
        auth_rate_limits.delete().where(
            (auth_rate_limits.c.scope == scope) &
            (auth_rate_limits.c.subject_hash == subject_hash)
        )
    )
    await database.commit()


# --- Session Cleanup ---

async def cleanup_expired_sessions(database, auth_sessions) -> int:
    """Delete expired and revoked sessions. Returns count deleted."""
    now = datetime.now(timezone.utc)
    result = await database.execute(
        auth_sessions.delete().where(
            (auth_sessions.c.expires_at < now) | (auth_sessions.c.revoked_at.isnot(None))
        )
    )
    await database.commit()
    return result.rowcount


async def cleanup_expired_tokens(database, password_reset_tokens, email_verification_tokens) -> int:
    """Delete expired or used reset/verification tokens. Returns count deleted."""
    now = datetime.now(timezone.utc)
    r1 = await database.execute(
        password_reset_tokens.delete().where(
            (password_reset_tokens.c.expires_at < now) | (password_reset_tokens.c.used_at.isnot(None))
        )
    )
    await database.commit()
    r2 = await database.execute(
        email_verification_tokens.delete().where(
            (email_verification_tokens.c.expires_at < now) | (email_verification_tokens.c.used_at.isnot(None))
        )
    )
    await database.commit()
    return r1.rowcount + r2.rowcount


# --- Session Cache (DPERF-002) ---

_session_cache: TTLCache = TTLCache(maxsize=256, ttl=60)


def invalidate_session_cache(token_hash: str | None = None) -> None:
    """Invalidate cached session entry.

    Call on password change, logout, or session revocation.
    If token_hash is given, removes only that entry; otherwise clears all.
    """
    if token_hash:
        _session_cache.pop(token_hash, None)
    else:
        _session_cache.clear()


# --- FastAPI Dependencies ---
# These are created as factories that take the DB and table objects,
# because the tables are defined in main.py.

def make_get_current_user(database, users_table, user_roles_table, roles_table, auth_sessions):
    """Create the get_current_user dependency.

    Returns an async function that resolves the current user from the session cookie.
    Returns None if no valid session.
    """
    async def get_current_user(request: Request) -> dict | None:
        session_token = request.cookies.get("session_token")
        if not session_token:
            return None

        token_hash_val = hash_token(session_token)

        # Check TTL cache before hitting DB (DPERF-002).
        cached = _session_cache.get(token_hash_val)
        if cached is not None:
            return cached

        now = datetime.now(timezone.utc)

        # Single JOIN replaces 3-4 sequential queries (DPERF-002).
        # May return multiple rows when a user has multiple roles.
        rows = (await database.execute(
            text(
                "SELECT u.*, r.name AS role_name, s.id AS session_id "
                "FROM auth_sessions s "
                "JOIN users u ON u.id = s.user_id "
                "LEFT JOIN user_roles ur ON ur.user_id = u.id "
                "LEFT JOIN roles r ON r.id = ur.role_id "
                "WHERE s.token_hash = :hash "
                "  AND s.expires_at > :now "
                "  AND s.revoked_at IS NULL "
                "  AND u.status = 'active'"
            ),
            {"hash": token_hash_val, "now": now},
        )).mappings().all()

        if not rows:
            return None

        # Aggregate: all rows share the same user/session data; collect role names.
        first_row = dict(rows[0])
        session_id = first_row.pop("session_id")
        first_row.pop("role_name", None)
        role_names = [row["role_name"] for row in rows if row["role_name"] is not None]

        result = {**first_row, "roles": role_names, "_session_id": session_id}
        _session_cache[token_hash_val] = result
        return result

    return get_current_user


def make_require_user(get_current_user_dep):
    """Create require_user dependency (raises 401 if not authenticated)."""
    async def require_user(request: Request) -> dict:
        user = await get_current_user_dep(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        return user
    return require_user


def make_require_admin(require_user_dep):
    """Create require_admin dependency (raises 403 if not admin)."""
    async def require_admin(request: Request) -> dict:
        user = await require_user_dep(request)
        if "admin" not in user.get("roles", []):
            raise HTTPException(status_code=403, detail="Admin access required")
        return user
    return require_admin
