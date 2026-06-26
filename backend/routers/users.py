"""
---
name: users_router
description: "User self-service API routes: profile, email/username/password update, avatar management"
type: router
target:
  layer: backend
  domain: users
spec_doc: null
test_file: tests/stage1/test_user_management.py
functions:
  - name: get_current_user_profile
    line: 90
    purpose: "GET /users/me — return full current user profile"
  - name: update_current_user_profile
    line: 96
    purpose: "PUT /users/me — update current user's full_name"
  - name: update_current_user_email
    line: 115
    purpose: "PUT /users/me/email — set pending email and send verification link"
  - name: update_current_user_username
    line: 183
    purpose: "PUT /users/me/username — change current user's username (uniqueness check)"
  - name: update_current_user_password
    line: 219
    purpose: "PUT /users/me/password — change password, revoke all other sessions, rotate current session"
  - name: update_current_user_preferences
    line: 265
    purpose: "PUT /users/me/preferences — update current user's preferences JSON blob"
  - name: update_current_user_avatar
    line: 279
    purpose: "PUT /users/me/avatar — upload avatar (max 512KB, JPEG/PNG/WebP; Pillow re-encode)"
  - name: delete_current_user_avatar
    line: 338
    purpose: "DELETE /users/me/avatar — clear avatar bytes and reset source to 'none'"
  - name: get_current_user_avatar
    line: 357
    purpose: "GET /users/me/avatar — serve uploaded avatar bytes or redirect to Gravatar"
  - name: update_avatar_source
    line: 379
    purpose: "PUT /users/me/avatar-source — set avatar source to 'none' or 'gravatar'"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
from fastapi import APIRouter, HTTPException, Response, Request, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from datetime import datetime, timedelta, timezone
import hashlib
import io

from core.db import get_db, users, auth_sessions, email_verification_tokens, auth_rate_limits
from core.auth import (
    hash_password, verify_password,
    hash_token,
    generate_reset_token,
    validate_username, normalize_username, validate_password, normalize_email,
    check_rate_limit, record_attempt,
    invalidate_session_cache,
)
from core.email import get_email_sender
from core.security_models import (
    UpdateProfileRequest, UpdateEmailRequest, UpdateUsernameRequest,
    ChangePasswordRequest, UpdatePreferencesRequest,
)
from routers._deps import (
    require_user, require_admin, _csrf_dependency,
    _session_ttl_hours, log_with_time,
    _user_to_response, _user_to_me_response, _get_user_roles,
    _create_session_and_cookies, FRONTEND_ORIGIN,
)


class UpdateAvatarSourceRequest(BaseModel):
    source: str

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in ("none", "gravatar"):
            raise ValueError("source must be 'none' or 'gravatar'")
        return v


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_current_user_profile(request: Request, current_user: dict = Depends(require_user)):
    """Get full current user profile."""
    return _user_to_me_response(current_user, current_user.get("roles", []))


@router.put("/me", dependencies=[Depends(_csrf_dependency)])
async def update_current_user_profile(req: UpdateProfileRequest, request: Request, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Update current user's full_name."""
    now = datetime.now(timezone.utc)
    values: dict = {"updated_at": now}
    if req.full_name is not None:
        values["full_name"] = req.full_name.strip() if req.full_name else None

    await db.execute(
        users.update().where(users.c.id == current_user["id"]).values(**values)
    )
    await db.commit()

    user_row = (await db.execute(users.select().where(users.c.id == current_user["id"]))).mappings().first()
    if user_row is None:
        raise HTTPException(status_code=500, detail="User not found after update")
    return _user_to_me_response(dict(user_row), current_user.get("roles", []))


@router.put("/me/email", dependencies=[Depends(_csrf_dependency)])
async def update_current_user_email(req: UpdateEmailRequest, request: Request, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Set pending email and send verification."""
    # Verify current password
    if not await verify_password(req.password, current_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect password")

    new_email_norm = normalize_email(req.new_email)

    # Check if same as current
    if new_email_norm == current_user["email_normalized"]:
        raise HTTPException(status_code=400, detail="New email is the same as current email")

    # Check uniqueness
    existing = (await db.execute(
        users.select().where(
            (users.c.email_normalized == new_email_norm) &
            (users.c.id != current_user["id"])
        )
    )).mappings().first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use")

    now = datetime.now(timezone.utc)

    # Generate verification token before transaction
    token = generate_reset_token()
    token_hash_val = hash_token(token)
    expires_at = now + timedelta(hours=4)

    # Set pending email
    await db.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            pending_email=req.new_email.strip(),
            pending_email_normalized=new_email_norm,
            updated_at=now,
        )
    )

    # Revoke existing verification tokens
    await db.execute(
        email_verification_tokens.update()
        .where(
            (email_verification_tokens.c.user_id == current_user["id"]) &
            (email_verification_tokens.c.used_at.is_(None))
        )
        .values(used_at=now)
    )

    # Insert new verification token
    await db.execute(
        email_verification_tokens.insert().values(
            user_id=current_user["id"],
            token_hash=token_hash_val,
            email=req.new_email.strip(),
            created_at=now,
            expires_at=expires_at,
        )
    )
    await db.commit()

    verify_link = f"{FRONTEND_ORIGIN}/authentication/modern/verify-email?token={token}"
    email_sender = get_email_sender()
    await email_sender.send_verification_email(req.new_email.strip(), verify_link)

    return {"status": "ok", "message": "Verification email sent to new address"}


@router.put("/me/username", dependencies=[Depends(_csrf_dependency)])
async def update_current_user_username(req: UpdateUsernameRequest, request: Request, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Update current user's username."""
    username_norm = normalize_username(req.new_username)

    valid, err = validate_username(username_norm)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    # Check if same as current
    if username_norm == current_user["username_normalized"]:
        raise HTTPException(status_code=400, detail="New username is the same as current username")

    # Check uniqueness
    existing = (await db.execute(
        users.select().where(
            (users.c.username_normalized == username_norm) &
            (users.c.id != current_user["id"])
        )
    )).mappings().first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    now = datetime.now(timezone.utc)
    await db.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            username=username_norm,
            username_normalized=username_norm,
            updated_at=now,
        )
    )
    await db.commit()

    return {"status": "ok", "message": "Username updated"}


@router.put("/me/password", dependencies=[Depends(_csrf_dependency)])
async def update_current_user_password(req: ChangePasswordRequest, request: Request, response: Response, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Change password: update hash, revoke other sessions, rotate current session."""
    # Verify current password
    if not await verify_password(req.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    # Validate new password
    valid, err = validate_password(req.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    if req.current_password == req.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    now = datetime.now(timezone.utc)
    new_hash = await hash_password(req.new_password)

    # Update password hash
    await db.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            password_hash=new_hash,
            updated_at=now,
        )
    )

    # Revoke ALL sessions for this user
    await db.execute(
        auth_sessions.update()
        .where(
            (auth_sessions.c.user_id == current_user["id"]) &
            (auth_sessions.c.revoked_at.is_(None))
        )
        .values(revoked_at=now)
    )
    await db.commit()

    # Invalidate in-memory session cache for all revoked sessions
    invalidate_session_cache()

    # Create a new session (rotate)
    await _create_session_and_cookies(response, request, current_user["id"], db)

    return {"status": "ok", "message": "Password changed. Other sessions have been revoked."}


@router.put("/me/preferences", dependencies=[Depends(_csrf_dependency)])
async def update_current_user_preferences(req: UpdatePreferencesRequest, request: Request, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Update current user's preferences JSON."""
    now = datetime.now(timezone.utc)
    await db.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            preferences=req.preferences,
            updated_at=now,
        )
    )
    await db.commit()
    return {"status": "ok", "preferences": req.preferences}


@router.put("/me/avatar", dependencies=[Depends(_csrf_dependency)])
async def update_current_user_avatar(request: Request, current_user: dict = Depends(require_user), file: UploadFile = File(...), db=Depends(get_db)):
    """Upload avatar image (max 512KB, JPEG/PNG/WebP, decode+re-encode)."""
    # Read file
    contents = await file.read()

    # Check size (512 KB)
    if len(contents) > 512 * 1024:
        raise HTTPException(status_code=400, detail="Avatar must be under 512 KB")

    # Validate and re-encode using Pillow
    try:
        from PIL import Image
        import hashlib as hl

        img = Image.open(io.BytesIO(contents))
        img_format = img.format

        if img_format not in ("JPEG", "PNG", "WEBP"):
            raise HTTPException(status_code=400, detail="Avatar must be JPEG, PNG, or WebP")

        # Re-encode to strip metadata and validate
        output = io.BytesIO()
        if img_format == "JPEG":
            img = img.convert("RGB")
            img.save(output, format="JPEG", quality=85)
            mime = "image/jpeg"
        elif img_format == "PNG":
            img.save(output, format="PNG")
            mime = "image/png"
        else:  # WEBP
            img.save(output, format="WEBP", quality=85)
            mime = "image/webp"

        sanitized_bytes = output.getvalue()
        avatar_hash = hl.sha256(sanitized_bytes).hexdigest()[:16]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {e}")

    now = datetime.now(timezone.utc)
    await db.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            avatar_bytes=sanitized_bytes,
            avatar_mime_type=mime,
            avatar_size_bytes=len(sanitized_bytes),
            avatar_hash=avatar_hash,
            avatar_source="upload",
            avatar_updated_at=now,
            updated_at=now,
        )
    )
    await db.commit()

    return {"status": "ok", "avatar_hash": avatar_hash, "avatar_size": len(sanitized_bytes)}


@router.delete("/me/avatar", dependencies=[Depends(_csrf_dependency)])
async def delete_current_user_avatar(request: Request, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Delete current user's avatar."""
    now = datetime.now(timezone.utc)
    await db.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            avatar_bytes=None,
            avatar_mime_type=None,
            avatar_size_bytes=None,
            avatar_hash=None,
            avatar_source="none",
            avatar_updated_at=now,
            updated_at=now,
        )
    )
    await db.commit()
    return {"status": "ok", "message": "Avatar deleted"}


@router.get("/me/avatar")
async def get_current_user_avatar(request: Request, current_user: dict = Depends(require_user)):
    """Serve current user's avatar bytes, or redirect to Gravatar."""
    source = current_user.get("avatar_source", "none")

    if source == "upload" and current_user.get("avatar_bytes"):
        return Response(
            content=current_user["avatar_bytes"],
            media_type=current_user.get("avatar_mime_type", "image/jpeg"),
            headers={"Cache-Control": "private, max-age=3600"},
        )

    if source == "gravatar":
        email = (current_user.get("email") or "").strip().lower()
        email_hash = hashlib.md5(email.encode("utf-8")).hexdigest()
        gravatar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=200"
        from starlette.responses import RedirectResponse
        return RedirectResponse(url=gravatar_url, status_code=302)

    raise HTTPException(status_code=404, detail="No avatar")


@router.put("/me/avatar-source", dependencies=[Depends(_csrf_dependency)])
async def update_avatar_source(req: UpdateAvatarSourceRequest, request: Request, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Update avatar source (none or gravatar). Use PUT /users/me/avatar for upload."""
    now = datetime.now(timezone.utc)
    await db.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            avatar_source=req.source,
            updated_at=now,
        )
    )
    await db.commit()
    return {"status": "ok", "avatar_source": req.source}
