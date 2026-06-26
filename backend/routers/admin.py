"""
---
name: admin_router
description: "Admin API routes: user management (CRUD, role assignment) and site ownership transfer"
type: router
target:
  layer: backend
  domain: admin
spec_doc: null
test_file: tests/stage1/test_admin.py
functions:
  - name: admin_list_users
    line: 66
    purpose: "GET /admin/users — paginated user list with roles (single JOIN, no N+1)"
  - name: admin_create_user
    line: 103
    purpose: "POST /admin/users — create user with invite-link password-reset flow (no plaintext password)"
  - name: admin_get_user
    line: 185
    purpose: "GET /admin/users/{user_id} — return full user detail by ID"
  - name: admin_update_user
    line: 196
    purpose: "PUT /admin/users/{user_id} — update full_name or status; revoke sessions on block"
  - name: admin_delete_user
    line: 237
    purpose: "DELETE /admin/users/{user_id} — soft-block user, revoke sessions; gate on feed ownership"
  - name: admin_update_user_roles
    line: 279
    purpose: "PUT /admin/users/{user_id}/roles — replace user roles (delete-then-insert)"
  - name: admin_list_roles
    line: 306
    purpose: "GET /admin/roles — list all roles with per-role user counts"
  - name: update_site_owner
    line: 328
    purpose: "PUT /admin/sites/{site_id}/owner — transfer site ownership to another active user"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from core.db import get_db, users, roles, user_roles, auth_sessions, sites, password_reset_tokens
from routers._deps import (
    require_admin, _csrf_dependency,
    _user_to_response, _get_user_roles,
)
from core.security_models import (
    AdminCreateUserRequest, AdminUpdateUserRequest, AdminUpdateRolesRequest,
)
from core.auth import (
    validate_username, normalize_username, normalize_email,
    generate_reset_token, hash_token, invalidate_session_cache,
)
from core.email import get_email_sender
from core.ownership import ownership_transfer_gate, verify_transfer_target
import os

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5174")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def admin_list_users(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    """List all users with pagination."""
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size

    total_row = (await db.execute(text("SELECT COUNT(*) as cnt FROM users"))).mappings().first()
    total = total_row["cnt"] if total_row else 0

    # Single JOIN query replaces N+1 _get_user_roles() calls
    join_q = text("""
        SELECT u.*, array_agg(r.name) FILTER (WHERE r.name IS NOT NULL) AS role_names
        FROM users u
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        LEFT JOIN roles r ON r.id = ur.role_id
        GROUP BY u.id
        ORDER BY u.id
        LIMIT :lim OFFSET :off
    """)
    rows = (await db.execute(join_q, {"lim": page_size, "off": offset})).mappings().all()

    user_list = []
    for row in rows:
        row_dict = dict(row)
        role_names = row_dict.pop("role_names", None) or []
        user_list.append(_user_to_response(row_dict, list(role_names)))

    return {"users": user_list, "total": total, "page": page, "page_size": page_size}


@router.post("/users", dependencies=[Depends(_csrf_dependency)])
async def admin_create_user(req: AdminCreateUserRequest, request: Request, current_user: dict = Depends(require_admin), db=Depends(get_db)):
    """Admin create user: no plaintext password. Sends invite link."""
    # Validate
    valid, err = validate_username(req.username)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    email_norm = normalize_email(req.email)
    username_norm = normalize_username(req.username)

    # Check email uniqueness
    existing = (await db.execute(
        users.select().where(users.c.email_normalized == email_norm)
    )).mappings().first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Check username uniqueness
    existing = (await db.execute(
        users.select().where(users.c.username_normalized == username_norm)
    )).mappings().first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    now = datetime.now(timezone.utc)

    # Create user with known-invalid hash placeholder (user must reset via invite link)
    temp_hash = "!INVITE_PENDING"

    result = await db.execute(
        users.insert().values(
            email=req.email.strip(),
            email_normalized=email_norm,
            username=username_norm,
            username_normalized=username_norm,
            full_name=req.full_name,
            password_hash=temp_hash,
            status="active",
            avatar_source="none",
            preferences={},
            created_at=now,
            updated_at=now,
        )
    )
    user_id = result.inserted_primary_key[0]
    await db.commit()

    # Pre-fetch all roles in one query, then use dict lookup (avoids N+1)
    all_roles_rows = (await db.execute(roles.select())).mappings().all()
    role_map = {r["name"]: r["id"] for r in all_roles_rows}
    for role_name in req.roles:
        if role_name in role_map:
            await db.execute(user_roles.insert().values(user_id=user_id, role_id=role_map[role_name]))
    await db.commit()

    # Create invite/reset token
    token = generate_reset_token()
    token_hash_val = hash_token(token)
    expires_at = now + timedelta(hours=4)

    await db.execute(
        password_reset_tokens.insert().values(
            user_id=user_id,
            token_hash=token_hash_val,
            created_at=now,
            expires_at=expires_at,
        )
    )
    await db.commit()

    invite_link = f"{FRONTEND_ORIGIN}/authentication/modern/new-password?token={token}"
    email_sender = get_email_sender()
    await email_sender.send_invite_email(req.email.strip(), invite_link)

    user_row = (await db.execute(users.select().where(users.c.id == user_id))).mappings().first()
    if user_row is None:
        raise HTTPException(status_code=500, detail="User not found after creation")
    role_list = await _get_user_roles(user_id, db)
    return _user_to_response(dict(user_row), role_list)


@router.get("/users/{user_id}")
async def admin_get_user(user_id: int, request: Request, current_user: dict = Depends(require_admin), db=Depends(get_db)):
    """Get user details by ID."""
    user_row = (await db.execute(users.select().where(users.c.id == user_id))).mappings().first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    role_list = await _get_user_roles(user_id, db)
    return _user_to_response(dict(user_row), role_list)


@router.put("/users/{user_id}", dependencies=[Depends(_csrf_dependency)])
async def admin_update_user(user_id: int, req: AdminUpdateUserRequest, request: Request, current_user: dict = Depends(require_admin), db=Depends(get_db)):
    """Admin update user (full_name, status)."""
    user_row = (await db.execute(users.select().where(users.c.id == user_id))).mappings().first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)
    values: dict = {"updated_at": now}

    if req.full_name is not None:
        values["full_name"] = req.full_name.strip() if req.full_name else None

    if req.status is not None:
        if req.status not in ("active", "inactive", "blocked"):
            raise HTTPException(status_code=400, detail="Status must be active, inactive, or blocked")
        values["status"] = req.status

        # If blocking, revoke all sessions
        if req.status == "blocked":
            await db.execute(
                auth_sessions.update()
                .where(
                    (auth_sessions.c.user_id == user_id) &
                    (auth_sessions.c.revoked_at.is_(None))
                )
                .values(revoked_at=now)
            )

    await db.execute(
        users.update().where(users.c.id == user_id).values(**values)
    )
    await db.commit()

    user_row = (await db.execute(users.select().where(users.c.id == user_id))).mappings().first()
    if user_row is None:
        raise HTTPException(status_code=404, detail="User not found")
    role_list = await _get_user_roles(user_id, db)
    return _user_to_response(dict(user_row), role_list)


@router.delete("/users/{user_id}", dependencies=[Depends(_csrf_dependency)])
async def admin_delete_user(user_id: int, request: Request, current_user: dict = Depends(require_admin), db=Depends(get_db)):
    """Soft block a user (set status=blocked, revoke sessions)."""
    user_row = (await db.execute(users.select().where(users.c.id == user_id))).mappings().first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-block
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot block yourself")

    owned_sites = await ownership_transfer_gate(db, user_id)
    if owned_sites:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "User owns feeds that must be transferred first",
                "owned_sites": owned_sites,
            },
        )

    now = datetime.now(timezone.utc)

    await db.execute(
        users.update().where(users.c.id == user_id).values(status="blocked", updated_at=now)
    )

    # Revoke sessions
    await db.execute(
        auth_sessions.update()
        .where(
            (auth_sessions.c.user_id == user_id) &
            (auth_sessions.c.revoked_at.is_(None))
        )
        .values(revoked_at=now)
    )
    await db.commit()
    invalidate_session_cache()

    return {"status": "ok", "message": "User blocked"}


@router.put("/users/{user_id}/roles", dependencies=[Depends(_csrf_dependency)])
async def admin_update_user_roles(user_id: int, req: AdminUpdateRolesRequest, request: Request, current_user: dict = Depends(require_admin), db=Depends(get_db)):
    """Assign roles to a user (replaces existing roles)."""
    user_row = (await db.execute(users.select().where(users.c.id == user_id))).mappings().first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate role names (pre-fetch all roles once, reuse for both validation and insert)
    all_roles = (await db.execute(roles.select())).mappings().all()
    role_map_update = {r["name"]: r["id"] for r in all_roles}
    for role_name in req.roles:
        if role_name not in role_map_update:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role_name}")

    # Remove existing roles
    await db.execute(user_roles.delete().where(user_roles.c.user_id == user_id))
    await db.commit()

    # Add new roles using pre-fetched role_map (no per-role DB query)
    for role_name in req.roles:
        if role_name in role_map_update:
            await db.execute(user_roles.insert().values(user_id=user_id, role_id=role_map_update[role_name]))
    await db.commit()

    return {"status": "ok", "roles": req.roles}


@router.get("/roles")
async def admin_list_roles(request: Request, current_user: dict = Depends(require_admin), db=Depends(get_db)):
    """List all roles with user counts."""
    all_roles = (await db.execute(roles.select().order_by(roles.c.id))).mappings().all()

    result = []
    for role_row in all_roles:
        count_row = (await db.execute(
            text("SELECT COUNT(*) as cnt FROM user_roles WHERE role_id = :rid"),
            {"rid": role_row["id"]},
        )).mappings().first()
        result.append({
            "id": role_row["id"],
            "name": role_row["name"],
            "description": role_row["description"],
            "created_at": role_row["created_at"].isoformat() if role_row["created_at"] else None,
            "user_count": count_row["cnt"] if count_row else 0,
        })

    return {"roles": result}


@router.put("/sites/{site_id}/owner", dependencies=[Depends(_csrf_dependency)])
async def update_site_owner(site_id: int, request: Request, current_user: dict = Depends(require_admin), db=Depends(get_db)):
    body = await request.json()
    new_owner_id = body.get("owner_user_id")
    if not new_owner_id or not isinstance(new_owner_id, int):
        raise HTTPException(status_code=400, detail="owner_user_id is required and must be an integer")

    # Verify site exists
    site = (await db.execute(
        sites.select().where(sites.c.id == site_id)
    )).mappings().first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    target = await verify_transfer_target(db, new_owner_id)
    if not target:
        raise HTTPException(status_code=400, detail="Target user not found or not active")

    # Update owner
    await db.execute(
        sites.update().where(sites.c.id == site_id).values(owner_user_id=new_owner_id)
    )
    await db.commit()
    return {"site_id": site_id, "owner_user_id": new_owner_id}
