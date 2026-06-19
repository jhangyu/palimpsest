from fastapi import APIRouter, HTTPException, Response, Request, Depends
from datetime import datetime, timedelta, timezone
import os

from sqlalchemy import text
from core.db import get_db, users, roles, user_roles, auth_sessions, password_reset_tokens, email_verification_tokens, auth_rate_limits
from core.auth import (
    hash_password, verify_password, needs_rehash,
    generate_session_token, hash_token,
    generate_csrf_token, check_origin,
    set_session_cookie, clear_session_cookie, set_csrf_cookie, clear_csrf_cookie,
    generate_reset_token,
    validate_username, normalize_username, validate_password, normalize_email,
    check_rate_limit, record_attempt, clear_rate_limit,
    make_get_current_user,
)
from core.email import get_email_sender
from core.security_models import (
    FirstRunSetupRequest, LoginRequest, RegisterRequest,
    ForgotPasswordRequest, ResetPasswordRequest, VerifyEmailRequest,
    ResendVerificationRequest,
)
from routers._deps import (
    require_user, require_admin, _csrf_dependency,
    _session_ttl_hours, log_with_time,
    _user_to_response, _user_to_me_response, _get_user_roles,
    _create_session_and_cookies, FRONTEND_ORIGIN,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/first-run-setup")
async def first_run_setup(req: FirstRunSetupRequest, request: Request, response: Response, db=Depends(get_db)):
    """Create the first admin user. Only works when users table is empty."""
    check_origin(request)

    user_count = (await db.execute(text("SELECT COUNT(*) as cnt FROM users"))).mappings().first()
    if user_count and user_count["cnt"] > 0:
        raise HTTPException(status_code=409, detail="Setup already completed. Users exist.")

    # Validate
    valid, err = validate_username(req.username)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    valid, err = validate_password(req.password)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    email_norm = normalize_email(req.email)
    username_norm = normalize_username(req.username)
    now = datetime.now(timezone.utc)

    pw_hash = await hash_password(req.password)

    async with db.begin():
        result = await db.execute(
            users.insert().values(
                email=req.email.strip(),
                email_normalized=email_norm,
                username=username_norm,
                username_normalized=username_norm,
                full_name=req.full_name,
                password_hash=pw_hash,
                status="active",
                email_verified_at=now,
                avatar_source="none",
                preferences={},
                created_at=now,
                updated_at=now,
            )
        )
        user_id = result.inserted_primary_key[0]

        # Assign admin role
        admin_role = (await db.execute(roles.select().where(roles.c.name == "admin"))).mappings().first()
        if admin_role:
            await db.execute(user_roles.insert().values(user_id=user_id, role_id=admin_role["id"]))
        # Also assign user role
        user_role = (await db.execute(roles.select().where(roles.c.name == "user"))).mappings().first()
        if user_role:
            await db.execute(user_roles.insert().values(user_id=user_id, role_id=user_role["id"]))

    # Create session (outside begin block to avoid nested commit conflict)
    await _create_session_and_cookies(response, request, user_id, db)

    log_with_time(f"[Auth] First-run admin created: {username_norm}")
    return {"status": "ok", "message": "Admin account created", "user_id": user_id}


@router.post("/login")
async def auth_login(req: LoginRequest, request: Request, response: Response, db=Depends(get_db)):
    """Authenticate user and create session."""
    check_origin(request)

    email_norm = normalize_email(req.email)

    # Rate limit check
    allowed, retry_after = await check_rate_limit(db, auth_rate_limits, "login", email_norm)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many attempts. Try again in {retry_after} seconds.")

    # Find user
    user = (await db.execute(
        users.select().where(users.c.email_normalized == email_norm)
    )).mappings().first()

    if not user or not await verify_password(req.password, user["password_hash"]):
        await record_attempt(db, auth_rate_limits, "login", email_norm)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user["status"] != "active":
        raise HTTPException(status_code=403, detail="Account is not active")

    # Clear rate limit on success
    await clear_rate_limit(db, auth_rate_limits, "login", email_norm)

    # Rehash if needed
    if needs_rehash(user["password_hash"]):
        new_hash = await hash_password(req.password)
        await db.execute(
            users.update().where(users.c.id == user["id"]).values(password_hash=new_hash)
        )

    # Update last_login_at
    now = datetime.now(timezone.utc)
    await db.execute(
        users.update().where(users.c.id == user["id"]).values(last_login_at=now)
    )
    await db.commit()

    # Create session
    await _create_session_and_cookies(response, request, user["id"], db)

    user_roles_list = await _get_user_roles(user["id"], db)
    return _user_to_me_response(dict(user), user_roles_list)


@router.post("/logout", dependencies=[Depends(_csrf_dependency)])
async def auth_logout(request: Request, response: Response, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Logout: revoke current session."""
    session_id = current_user.get("_session_id")
    if session_id:
        now = datetime.now(timezone.utc)
        await db.execute(
            auth_sessions.update().where(auth_sessions.c.id == session_id).values(revoked_at=now)
        )
        await db.commit()

    clear_session_cookie(response)
    clear_csrf_cookie(response)
    return {"status": "ok", "message": "Logged out"}


@router.get("/me")
async def auth_me(request: Request, user: dict | None = Depends(get_current_user)):
    """Get current user info. Returns 401 if not authenticated."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _user_to_me_response(user, user.get("roles", []))


@router.post("/register")
async def auth_register(req: RegisterRequest, request: Request, response: Response, db=Depends(get_db)):
    """Register a new user (only if public registration is enabled)."""
    check_origin(request)

    allow_registration = os.getenv("AUTH_ALLOW_PUBLIC_REGISTRATION", "false").lower() in ("true", "1", "yes")
    if not allow_registration:
        raise HTTPException(status_code=403, detail="Public registration is disabled")

    # Validate
    valid, err = validate_username(req.username)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    valid, err = validate_password(req.password)
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
    pw_hash = await hash_password(req.password)

    result = await db.execute(
        users.insert().values(
            email=req.email.strip(),
            email_normalized=email_norm,
            username=username_norm,
            username_normalized=username_norm,
            full_name=req.full_name,
            password_hash=pw_hash,
            status="active",
            avatar_source="none",
            preferences={},
            created_at=now,
            updated_at=now,
        )
    )
    user_id = result.inserted_primary_key[0]
    await db.commit()

    # Assign user role
    user_role = (await db.execute(roles.select().where(roles.c.name == "user"))).mappings().first()
    if user_role:
        await db.execute(user_roles.insert().values(user_id=user_id, role_id=user_role["id"]))
        await db.commit()

    # Create session
    await _create_session_and_cookies(response, request, user_id, db)

    user_row = (await db.execute(users.select().where(users.c.id == user_id))).mappings().first()
    if user_row is None:
        raise HTTPException(status_code=500, detail="User not found after creation")
    user_roles_list = await _get_user_roles(user_id, db)
    return _user_to_me_response(dict(user_row), user_roles_list)


@router.post("/forgot-password")
async def auth_forgot_password(req: ForgotPasswordRequest, request: Request, db=Depends(get_db)):
    """Request a password reset. Always returns success (generic response)."""
    check_origin(request)

    email_norm = normalize_email(req.email)

    # Rate limit
    allowed, retry_after = await check_rate_limit(db, auth_rate_limits, "forgot_password", email_norm)
    if not allowed:
        # Still return generic success to avoid enumeration
        return {"status": "ok", "message": "If an account exists, a reset link has been sent."}

    await record_attempt(db, auth_rate_limits, "forgot_password", email_norm)

    user = (await db.execute(
        users.select().where(users.c.email_normalized == email_norm)
    )).mappings().first()

    if user and user["status"] == "active":
        # Revoke any existing unused reset tokens for this user
        now = datetime.now(timezone.utc)
        await db.execute(
            password_reset_tokens.update()
            .where(
                (password_reset_tokens.c.user_id == user["id"]) &
                (password_reset_tokens.c.used_at.is_(None))
            )
            .values(used_at=now)
        )

        # Generate new token
        token = generate_reset_token()
        token_hash_val = hash_token(token)
        expires_at = now + timedelta(hours=4)

        await db.execute(
            password_reset_tokens.insert().values(
                user_id=user["id"],
                token_hash=token_hash_val,
                created_at=now,
                expires_at=expires_at,
            )
        )
        await db.commit()

        # Send email (dev mode: log)
        reset_link = f"{FRONTEND_ORIGIN}/authentication/modern/new-password?token={token}"
        email_sender = get_email_sender()
        await email_sender.send_reset_email(user["email"], reset_link)

    # Always return generic success
    return {"status": "ok", "message": "If an account exists, a reset link has been sent."}


@router.post("/reset-password")
async def auth_reset_password(req: ResetPasswordRequest, request: Request, db=Depends(get_db)):
    """Reset password using a valid token."""
    check_origin(request)

    # Rate limit
    allowed, retry_after = await check_rate_limit(db, auth_rate_limits, "reset_password", req.token[:16])
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many attempts. Try again in {retry_after} seconds.")

    # Validate new password
    valid, err = validate_password(req.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    token_hash_val = hash_token(req.token)
    now = datetime.now(timezone.utc)

    # Find valid token
    token_row = (await db.execute(
        password_reset_tokens.select().where(
            (password_reset_tokens.c.token_hash == token_hash_val) &
            (password_reset_tokens.c.expires_at > now) &
            (password_reset_tokens.c.used_at.is_(None))
        )
    )).mappings().first()

    if not token_row:
        await record_attempt(db, auth_rate_limits, "reset_password", req.token[:16])
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    # Mark token as used
    await db.execute(
        password_reset_tokens.update()
        .where(password_reset_tokens.c.id == token_row["id"])
        .values(used_at=now)
    )

    # Update password
    new_hash = await hash_password(req.new_password)
    await db.execute(
        users.update()
        .where(users.c.id == token_row["user_id"])
        .values(password_hash=new_hash, updated_at=now)
    )

    # Revoke all sessions for this user
    await db.execute(
        auth_sessions.update()
        .where(
            (auth_sessions.c.user_id == token_row["user_id"]) &
            (auth_sessions.c.revoked_at.is_(None))
        )
        .values(revoked_at=now)
    )
    await db.commit()

    return {"status": "ok", "message": "Password has been reset. Please login."}


@router.post("/verify-email")
async def auth_verify_email(req: VerifyEmailRequest, request: Request, db=Depends(get_db)):
    """Verify a pending email change using a verification token."""
    check_origin(request)

    token_hash_val = hash_token(req.token)
    now = datetime.now(timezone.utc)

    # Find valid token
    token_row = (await db.execute(
        email_verification_tokens.select().where(
            (email_verification_tokens.c.token_hash == token_hash_val) &
            (email_verification_tokens.c.expires_at > now) &
            (email_verification_tokens.c.used_at.is_(None))
        )
    )).mappings().first()

    if not token_row:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    # Mark token as used
    await db.execute(
        email_verification_tokens.update()
        .where(email_verification_tokens.c.id == token_row["id"])
        .values(used_at=now)
    )
    await db.commit()

    # Promote pending email to primary email
    user = (await db.execute(
        users.select().where(users.c.id == token_row["user_id"])
    )).mappings().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_email = token_row["email"]
    new_email_norm = normalize_email(new_email)

    # Check if this email is already taken by another user
    existing = (await db.execute(
        users.select().where(
            (users.c.email_normalized == new_email_norm) &
            (users.c.id != user["id"])
        )
    )).mappings().first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use by another account")

    await db.execute(
        users.update()
        .where(users.c.id == user["id"])
        .values(
            email=new_email.strip(),
            email_normalized=new_email_norm,
            pending_email=None,
            pending_email_normalized=None,
            email_verified_at=now,
            updated_at=now,
        )
    )
    await db.commit()

    return {"status": "ok", "message": "Email verified and updated"}


@router.post("/resend-verification", dependencies=[Depends(_csrf_dependency)])
async def auth_resend_verification(req: ResendVerificationRequest, request: Request, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Resend email verification for pending email change."""
    email_norm = normalize_email(req.email)

    # Rate limit
    allowed, retry_after = await check_rate_limit(db, auth_rate_limits, "resend_verification", email_norm)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many attempts. Try again in {retry_after} seconds.")

    await record_attempt(db, auth_rate_limits, "resend_verification", email_norm)

    # Only allow if user has a pending email that matches
    if not current_user.get("pending_email_normalized") or current_user["pending_email_normalized"] != email_norm:
        raise HTTPException(status_code=400, detail="No pending email change for this address")

    now = datetime.now(timezone.utc)

    # Revoke existing unused verification tokens for this user
    await db.execute(
        email_verification_tokens.update()
        .where(
            (email_verification_tokens.c.user_id == current_user["id"]) &
            (email_verification_tokens.c.used_at.is_(None))
        )
        .values(used_at=now)
    )
    await db.commit()

    # Generate new token
    token = generate_reset_token()
    token_hash_val = hash_token(token)
    expires_at = now + timedelta(hours=4)

    await db.execute(
        email_verification_tokens.insert().values(
            user_id=current_user["id"],
            token_hash=token_hash_val,
            email=current_user["pending_email"],
            created_at=now,
            expires_at=expires_at,
        )
    )
    await db.commit()

    verify_link = f"{FRONTEND_ORIGIN}/authentication/modern/verify-email?token={token}"
    email_sender = get_email_sender()
    await email_sender.send_verification_email(current_user["pending_email"], verify_link)

    return {"status": "ok", "message": "Verification email sent"}
