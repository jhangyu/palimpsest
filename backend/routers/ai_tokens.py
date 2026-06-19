from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import JSONResponse
import json

from core.db import get_db, users, user_ai_tokens, auth_rate_limits
from routers._deps import (
    require_user, _csrf_dependency, log_with_time,
)
from core.security_models import (
    CreateTokenRequest, UpdateTokenRequest, RevealTokenRequest, TestTokenRequest,
)
from core.auth import verify_password, check_rate_limit, record_attempt
from core.ai_tokens import (
    list_user_tokens,
    create_user_token,
    update_user_token,
    delete_user_token,
    reveal_user_token,
    test_user_token,
    set_default_token,
)

# DD-4: Deprecation notice and headers for legacy /settings/ai-tokens/* endpoints
_DEPRECATION_NOTICE = (
    "The /ai-tokens API is deprecated and will be removed in a future release. "
    "Migrate to /ai-providers for envelope-encrypted provider management."
)

# DD-4: Standard HTTP deprecation headers (RFC 8594 / IETF draft-ietf-httpapi-deprecation-header)
_DEPRECATED_HEADERS = {
    "X-Deprecated": "true",
    "Deprecation": "true",
    "Sunset": "2026-12-31",
    "Link": '</ai-providers>; rel="successor-version"',
}

router = APIRouter(
    prefix="/settings/ai-tokens",
    tags=["ai-tokens (deprecated)"],
    deprecated=True,  # DD-4: marks all endpoints deprecated in OpenAPI docs
)


@router.get("/")
async def settings_list_ai_tokens(current_user: dict = Depends(require_user), db=Depends(get_db)):
    """List current user's AI tokens (masked values only). [DEPRECATED — use /settings/ai-providers]"""
    log_with_time(f"[DEPRECATED] /ai-tokens GET accessed by user {current_user['id']} — migrate to /ai-providers")
    tokens = await list_user_tokens(db, user_ai_tokens, current_user["id"])
    return JSONResponse({"tokens": tokens, "_deprecated": _DEPRECATION_NOTICE}, headers=_DEPRECATED_HEADERS)


@router.post("/", dependencies=[Depends(_csrf_dependency)])
async def settings_create_ai_token(req: CreateTokenRequest, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Create a new AI token for the current user. Requires current_password to encrypt. [DEPRECATED]"""
    log_with_time(f"[DEPRECATED] /ai-tokens POST accessed by user {current_user['id']} — migrate to /ai-providers")
    # Verify current password
    user_row = await db.fetch_one(
        users.select().where(users.c.id == current_user["id"])
    )
    if not user_row or not await verify_password(req.current_password, user_row["password_hash"]):
        raise HTTPException(status_code=403, detail="Invalid password")

    try:
        token_resp = await create_user_token(
            db, user_ai_tokens,
            user_id=current_user["id"],
            provider=req.provider,
            label=req.label,
            plaintext_token=req.token,
            password=req.current_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token_resp["_deprecated"] = _DEPRECATION_NOTICE
    return JSONResponse(token_resp, headers=_DEPRECATED_HEADERS)


@router.put("/{token_id}", dependencies=[Depends(_csrf_dependency)])
async def settings_update_ai_token(token_id: int, req: UpdateTokenRequest, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Update (overwrite) an existing AI token. Requires current_password to re-encrypt. [DEPRECATED]"""
    log_with_time(f"[DEPRECATED] /ai-tokens PUT /{token_id} accessed by user {current_user['id']} — migrate to /ai-providers")
    # Verify current password
    user_row = await db.fetch_one(
        users.select().where(users.c.id == current_user["id"])
    )
    if not user_row or not await verify_password(req.current_password, user_row["password_hash"]):
        raise HTTPException(status_code=403, detail="Invalid password")

    try:
        token_resp = await update_user_token(
            db, user_ai_tokens,
            token_id=token_id,
            user_id=current_user["id"],
            plaintext_token=req.token,
            password=req.current_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token_resp["_deprecated"] = _DEPRECATION_NOTICE
    return JSONResponse(token_resp, headers=_DEPRECATED_HEADERS)


@router.delete("/{token_id}", dependencies=[Depends(_csrf_dependency)])
async def settings_delete_ai_token(token_id: int, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Delete an AI token for the current user. [DEPRECATED]"""
    log_with_time(f"[DEPRECATED] /ai-tokens DELETE /{token_id} accessed by user {current_user['id']} — migrate to /ai-providers")
    try:
        await delete_user_token(db, user_ai_tokens, token_id, current_user["id"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return JSONResponse({"status": "deleted", "token_id": token_id, "_deprecated": _DEPRECATION_NOTICE}, headers=_DEPRECATED_HEADERS)


@router.post("/{token_id}/test", dependencies=[Depends(_csrf_dependency)])
async def settings_test_ai_token(token_id: int, req: TestTokenRequest, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Test an AI token's connectivity by making a test API call. Requires current_password to decrypt. [DEPRECATED]"""
    log_with_time(f"[DEPRECATED] /ai-tokens POST /{token_id}/test accessed by user {current_user['id']} — migrate to /ai-providers")
    # Verify current password
    user_row = await db.fetch_one(
        users.select().where(users.c.id == current_user["id"])
    )
    if not user_row or not await verify_password(req.current_password, user_row["password_hash"]):
        raise HTTPException(status_code=403, detail="Invalid password")

    try:
        result = await test_user_token(
            db, user_ai_tokens,
            token_id=token_id,
            user_id=current_user["id"],
            password=req.current_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    result["_deprecated"] = _DEPRECATION_NOTICE
    return JSONResponse(result, headers=_DEPRECATED_HEADERS)


@router.post("/{token_id}/reveal", dependencies=[Depends(_csrf_dependency)])
async def settings_reveal_ai_token(token_id: int, req: RevealTokenRequest, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Reveal the plaintext AI token. Requires current_password to decrypt. [DEPRECATED]

    The plaintext is ONLY returned in this response — never logged or stored in debug artifacts.
    """
    log_with_time(f"[DEPRECATED] /ai-tokens POST /{token_id}/reveal accessed by user {current_user['id']} — migrate to /ai-providers")
    # Rate limit check
    rate_key = f"reveal_token:{current_user['id']}"
    allowed, retry_after = await check_rate_limit(db, auth_rate_limits, "reveal_token", rate_key)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many reveal attempts. Try again in {retry_after} seconds.")

    # Verify current password
    user_row = await db.fetch_one(
        users.select().where(users.c.id == current_user["id"])
    )
    if not user_row or not await verify_password(req.current_password, user_row["password_hash"]):
        await record_attempt(db, auth_rate_limits, "reveal_token", rate_key)
        raise HTTPException(status_code=403, detail="Invalid password")

    try:
        plaintext = await reveal_user_token(
            db, user_ai_tokens,
            token_id=token_id,
            user_id=current_user["id"],
            password=req.current_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return Response(
        content=json.dumps({"token": plaintext, "_deprecated": _DEPRECATION_NOTICE}),
        media_type="application/json",
        headers={"Cache-Control": "no-store, private", "Pragma": "no-cache", **_DEPRECATED_HEADERS},
    )


@router.put("/{token_id}/default", dependencies=[Depends(_csrf_dependency)])
async def settings_set_default_ai_token(token_id: int, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """Set an AI token as the default for its provider. [DEPRECATED]"""
    log_with_time(f"[DEPRECATED] /ai-tokens PUT /{token_id}/default accessed by user {current_user['id']} — migrate to /ai-providers")
    # Fetch token to get provider
    token_row = await db.fetch_one(
        user_ai_tokens.select().where(
            (user_ai_tokens.c.id == token_id)
            & (user_ai_tokens.c.user_id == current_user["id"])
        )
    )
    if not token_row:
        raise HTTPException(status_code=404, detail="Token not found or access denied")

    try:
        token_resp = await set_default_token(
            db, user_ai_tokens,
            token_id=token_id,
            user_id=current_user["id"],
            provider=token_row["provider"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token_resp["_deprecated"] = _DEPRECATION_NOTICE
    return JSONResponse(token_resp, headers=_DEPRECATED_HEADERS)
