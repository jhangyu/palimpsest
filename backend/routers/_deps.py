"""Shared dependencies and helper functions for all routers.

Extracted from backend/main.py — every function is a verbatim copy of the
original logic.
"""

import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select as sa_select, func as sa_func, text

from core.auth import (
    validate_csrf,
    generate_session_token,
    hash_token,
    generate_csrf_token,
    set_session_cookie,
    set_csrf_cookie,
    _session_cache,
)
from core.db import (
    users,
    roles,
    user_roles,
    auth_sessions,
    sites,
    get_db,
)
from core.llm.key_backends import FileKeyEncryptionBackend

# ---------------------------------------------------------------------------
# Timestamped logging helper
# ---------------------------------------------------------------------------

def log_with_time(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


# ---------------------------------------------------------------------------
# Timezone / constants
# ---------------------------------------------------------------------------

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

# Color palette for feed chart datasets (DD-15: module-level constant)
FEED_COLORS = [
    "#1ABB9C", "#7533f9", "#198754", "#ffc107", "#dc3545",
    "#0d6efd", "#6610f2", "#fd7e14", "#20c997", "#6f42c1",
    "#d63384", "#0dcaf0", "#adb5bd", "#e35d6a", "#6ea8fe",
]

# Frontend origin for constructing links
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5174")

# ---------------------------------------------------------------------------
# Auth dependencies (DI-based)
# ---------------------------------------------------------------------------


async def get_current_user(request: Request, db=Depends(get_db)) -> dict | None:
    """Resolve current user from session cookie. Returns None if no valid session."""
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None

    token_hash_val = hash_token(session_token)

    # Check TTL cache before hitting DB (DPERF-002).
    cached = _session_cache.get(token_hash_val)
    if cached is not None:
        return cached

    now = datetime.now(timezone.utc)

    rows = (await db.execute(
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

    first_row = dict(rows[0])
    session_id = first_row.pop("session_id")
    first_row.pop("role_name", None)
    role_names = [row["role_name"] for row in rows if row["role_name"] is not None]

    result = {**first_row, "roles": role_names, "_session_id": session_id}
    _session_cache[token_hash_val] = result
    return result


async def require_user(user: dict | None = Depends(get_current_user)) -> dict:
    """Require authenticated user (raises 401)."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_admin(user: dict = Depends(require_user)) -> dict:
    """Require admin role (raises 403)."""
    if "admin" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------------------------------------------------------------------------
# Session TTL
# ---------------------------------------------------------------------------

def _session_ttl_hours() -> int:
    return int(os.getenv("SESSION_TTL_HOURS", "24"))


# ---------------------------------------------------------------------------
# KEK guard (DI-based)
# ---------------------------------------------------------------------------

async def require_kek(request: Request) -> FileKeyEncryptionBackend:
    """FastAPI dependency: require KEK backend to be available."""
    kek = request.app.state.kek_backend
    if kek is None:
        raise HTTPException(status_code=503, detail="AI provider encryption not configured")
    return kek


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def normalize_site_name(name: str) -> str:
    """將網站名稱標準化為 URL 友好的格式"""
    # 替換空白為底線
    name = name.replace(' ', '_')
    # 移除非英文數字底線的字元
    name = re.sub(r'[^a-zA-Z0-9_\-]', '', name)
    # 轉小寫
    name = name.lower()
    return name


async def get_site_by_name_or_id(site_identifier: str, db):
    """根據名稱或 ID 查詢網站 (DD-14: SELECT only id, name, url)

    F-M013: Uses SQL WHERE clauses instead of fetching all rows (O(1) vs O(N)).
    """
    _rss_cols = [sites.c.id, sites.c.name, sites.c.url]
    # 先嘗試當作 ID 查詢
    try:
        site_id = int(site_identifier)
        row = (await db.execute(
            sa_select(*_rss_cols).where(sites.c.id == site_id)
        )).mappings().first()
        if row:
            return row
    except (ValueError, TypeError):
        pass

    # 嘗試當作名稱查詢 (SQL case-insensitive + space-normalisation; O(1) with index)
    # normalize_site_name: spaces→'_', strip non-alnum, lowercase.
    # Replicate space→'_' and lowercase in SQL; non-alnum removal is an edge-case
    # not representable portably, but site names are expected to be clean.
    normalized = normalize_site_name(site_identifier)
    row = (await db.execute(
        sa_select(*_rss_cols).where(
            sa_func.lower(sa_func.replace(sites.c.name, ' ', '_')) == normalized
        )
    )).mappings().first()
    if row:
        return row
    return None


# --- Auth Helper: create session and set cookies ---
async def _create_session_and_cookies(response: Response, request: Request, user_id: int, db) -> str:
    """Create a session, set session + CSRF cookies. Returns the session token."""
    now = datetime.now(timezone.utc)
    session_token = generate_session_token()
    token_hash_val = hash_token(session_token)
    csrf_token = generate_csrf_token()

    await db.execute(
        auth_sessions.insert().values(
            user_id=user_id,
            token_hash=token_hash_val,
            user_agent=request.headers.get("user-agent", "")[:500],
            ip_address=request.client.host if request.client else None,
            created_at=now,
            expires_at=now + timedelta(hours=_session_ttl_hours()),
        )
    )
    await db.commit()

    set_session_cookie(response, session_token)
    set_csrf_cookie(response, csrf_token)
    return session_token


def _user_to_response(user_row: dict, user_roles_list: list[str]) -> dict:
    """Convert a user DB row to a response dict."""
    return {
        "id": user_row["id"],
        "email": user_row["email"],
        "username": user_row["username"],
        "full_name": user_row["full_name"],
        "status": user_row["status"],
        "email_verified_at": user_row["email_verified_at"].isoformat() if user_row["email_verified_at"] else None,
        "avatar_source": user_row["avatar_source"] or "none",
        "avatar_hash": user_row["avatar_hash"],
        "created_at": user_row["created_at"].isoformat() if user_row["created_at"] else None,
        "updated_at": user_row["updated_at"].isoformat() if user_row["updated_at"] else None,
        "last_login_at": user_row["last_login_at"].isoformat() if user_row["last_login_at"] else None,
        "roles": user_roles_list,
    }


def _user_to_me_response(user_row: dict, user_roles_list: list[str]) -> dict:
    """Convert a user DB row to a 'me' response dict (includes pending_email, preferences)."""
    resp = _user_to_response(user_row, user_roles_list)
    resp["pending_email"] = user_row.get("pending_email")
    resp["preferences"] = user_row.get("preferences") or {}
    return resp


async def _get_user_roles(user_id: int, db) -> list[str]:
    """Fetch role names for a user."""
    role_rows = (await db.execute(
        user_roles.select().where(user_roles.c.user_id == user_id)
    )).mappings().all()
    role_ids = [r["role_id"] for r in role_rows]
    if not role_ids:
        return []
    from sqlalchemy import select
    all_roles = (await db.execute(
        select(roles).where(roles.c.id.in_(role_ids))
    )).mappings().all()
    return [r["name"] for r in all_roles]


# --- CSRF dependency for state-changing endpoints ---
async def _csrf_dependency(request: Request):
    """CSRF validation dependency for state-changing routes."""
    validate_csrf(request)
