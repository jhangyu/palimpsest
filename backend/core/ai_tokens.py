# backend/core/ai_tokens.py
"""AI Token Vault repository — CRUD, reveal, test, default selection, token resolution.

All encryption uses password-derived keys (see core.crypto).
Only 'minimax' provider is supported in v1.
"""

import os
from datetime import datetime, timezone
from typing import Optional

from core.crypto import (
    encrypt_token,
    decrypt_token,
    generate_token_salt,
    mask_token,
    get_token_last4,
)

# Supported providers (v1: only minimax)
SUPPORTED_PROVIDERS = {"minimax"}


def _validate_provider(provider: str) -> None:
    """Raise ValueError if provider is not supported."""
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}. Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}")


def _token_row_to_response(row) -> dict:
    """Convert a DB row to a safe response dict (masked, no ciphertext)."""
    return {
        "id": row["id"],
        "provider": row["provider"],
        "label": row["label"],
        "token_mask": row["token_mask"],
        "token_last4": row["token_last4"],
        "needs_reentry": row["needs_reentry"],
        "is_default": row["is_default"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "last_used_at": row["last_used_at"].isoformat() if row["last_used_at"] else None,
    }


async def list_user_tokens(db, user_ai_tokens_table, user_id: int) -> list[dict]:
    """List all AI tokens for a user with masked values only."""
    rows = await db.fetch_all(
        user_ai_tokens_table.select().where(
            user_ai_tokens_table.c.user_id == user_id
        ).order_by(user_ai_tokens_table.c.created_at.asc())
    )
    return [_token_row_to_response(row) for row in rows]


async def create_user_token(
    db,
    user_ai_tokens_table,
    user_id: int,
    provider: str,
    label: str,
    plaintext_token: str,
    password: str,
) -> dict:
    """Encrypt and store a new AI token. Returns the created token response (masked)."""
    _validate_provider(provider)

    if not label or not label.strip():
        raise ValueError("Label is required")
    label = label.strip()

    if not plaintext_token or not plaintext_token.strip():
        raise ValueError("Token value is required")
    plaintext_token = plaintext_token.strip()

    now = datetime.now(timezone.utc)
    salt = generate_token_salt()
    encrypted = encrypt_token(plaintext_token, password, user_id, salt)
    masked = mask_token(plaintext_token)
    last4 = get_token_last4(plaintext_token)

    token_id = await db.execute(
        user_ai_tokens_table.insert().values(
            user_id=user_id,
            provider=provider,
            label=label,
            encrypted_token=encrypted,
            token_salt=salt,
            token_last4=last4,
            token_mask=masked,
            needs_reentry=False,
            is_default=False,
            created_at=now,
            updated_at=now,
            last_used_at=None,
        )
    )

    # Fetch the newly created row
    row = await db.fetch_one(
        user_ai_tokens_table.select().where(user_ai_tokens_table.c.id == token_id)
    )
    return _token_row_to_response(row)


async def update_user_token(
    db,
    user_ai_tokens_table,
    token_id: int,
    user_id: int,
    plaintext_token: str,
    password: str,
) -> dict:
    """Overwrite-encrypt an existing AI token. Returns updated token response (masked)."""
    row = await db.fetch_one(
        user_ai_tokens_table.select().where(
            (user_ai_tokens_table.c.id == token_id)
            & (user_ai_tokens_table.c.user_id == user_id)
        )
    )
    if not row:
        raise ValueError("Token not found or access denied")

    if not plaintext_token or not plaintext_token.strip():
        raise ValueError("Token value is required")
    plaintext_token = plaintext_token.strip()

    now = datetime.now(timezone.utc)
    salt = generate_token_salt()
    encrypted = encrypt_token(plaintext_token, password, user_id, salt)
    masked = mask_token(plaintext_token)
    last4 = get_token_last4(plaintext_token)

    await db.execute(
        user_ai_tokens_table.update()
        .where(user_ai_tokens_table.c.id == token_id)
        .values(
            encrypted_token=encrypted,
            token_salt=salt,
            token_last4=last4,
            token_mask=masked,
            needs_reentry=False,
            updated_at=now,
        )
    )

    updated_row = await db.fetch_one(
        user_ai_tokens_table.select().where(user_ai_tokens_table.c.id == token_id)
    )
    return _token_row_to_response(updated_row)


async def delete_user_token(
    db, user_ai_tokens_table, token_id: int, user_id: int
) -> bool:
    """Delete a user's AI token. Returns True if deleted, raises if not found."""
    row = await db.fetch_one(
        user_ai_tokens_table.select().where(
            (user_ai_tokens_table.c.id == token_id)
            & (user_ai_tokens_table.c.user_id == user_id)
        )
    )
    if not row:
        raise ValueError("Token not found or access denied")

    await db.execute(
        user_ai_tokens_table.delete().where(user_ai_tokens_table.c.id == token_id)
    )
    return True


async def reveal_user_token(
    db,
    user_ai_tokens_table,
    token_id: int,
    user_id: int,
    password: str,
) -> str:
    """Decrypt and return the plaintext token. ONLY in response, never log."""
    row = await db.fetch_one(
        user_ai_tokens_table.select().where(
            (user_ai_tokens_table.c.id == token_id)
            & (user_ai_tokens_table.c.user_id == user_id)
        )
    )
    if not row:
        raise ValueError("Token not found or access denied")

    if row["needs_reentry"]:
        raise ValueError("This token requires re-entry after password reset. Please update the token value.")

    plaintext = decrypt_token(
        row["encrypted_token"], password, user_id, row["token_salt"]
    )
    return plaintext


async def test_user_token(
    db,
    user_ai_tokens_table,
    token_id: int,
    user_id: int,
    password: str,
) -> dict:
    """Decrypt the token and make a test API call to the provider.

    Returns {"success": bool, "message": str}.
    """
    import httpx

    row = await db.fetch_one(
        user_ai_tokens_table.select().where(
            (user_ai_tokens_table.c.id == token_id)
            & (user_ai_tokens_table.c.user_id == user_id)
        )
    )
    if not row:
        raise ValueError("Token not found or access denied")

    if row["needs_reentry"]:
        return {"success": False, "message": "This token requires re-entry after password reset."}

    try:
        plaintext = decrypt_token(
            row["encrypted_token"], password, user_id, row["token_salt"]
        )
    except ValueError:
        return {"success": False, "message": "Failed to decrypt token. Wrong password?"}

    provider = row["provider"]
    if provider == "minimax":
        try:
            headers = {
                "Authorization": f"Bearer {plaintext}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "MiniMax-M3",
                "messages": [{"role": "user", "content": "Say 'ok' in one word."}],
                "max_tokens": 5,
                "thinking": {"type": "disabled"},
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.minimax.io/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )
            if resp.status_code == 200:
                return {"success": True, "message": "MiniMax API connection successful."}
            elif resp.status_code == 401:
                return {"success": False, "message": "MiniMax API returned 401 Unauthorized. Token may be invalid."}
            else:
                return {"success": False, "message": f"MiniMax API returned HTTP {resp.status_code}."}
        except httpx.TimeoutException:
            return {"success": False, "message": "MiniMax API request timed out."}
        except Exception as e:
            return {"success": False, "message": f"Connection error: {type(e).__name__}"}
    else:
        return {"success": False, "message": f"Test not implemented for provider: {provider}"}


async def set_default_token(
    db, user_ai_tokens_table, token_id: int, user_id: int, provider: str
) -> dict:
    """Set a token as the default for its provider. Unsets other defaults for same provider/user."""
    _validate_provider(provider)

    row = await db.fetch_one(
        user_ai_tokens_table.select().where(
            (user_ai_tokens_table.c.id == token_id)
            & (user_ai_tokens_table.c.user_id == user_id)
        )
    )
    if not row:
        raise ValueError("Token not found or access denied")

    if row["provider"] != provider:
        raise ValueError(f"Token provider mismatch: expected {provider}, got {row['provider']}")

    now = datetime.now(timezone.utc)

    # Unset other defaults for same provider/user
    await db.execute(
        user_ai_tokens_table.update()
        .where(
            (user_ai_tokens_table.c.user_id == user_id)
            & (user_ai_tokens_table.c.provider == provider)
            & (user_ai_tokens_table.c.id != token_id)
        )
        .values(is_default=False, updated_at=now)
    )

    # Set this token as default
    await db.execute(
        user_ai_tokens_table.update()
        .where(user_ai_tokens_table.c.id == token_id)
        .values(is_default=True, updated_at=now)
    )

    updated_row = await db.fetch_one(
        user_ai_tokens_table.select().where(user_ai_tokens_table.c.id == token_id)
    )
    return _token_row_to_response(updated_row)


async def resolve_minimax_token(
    db, user_ai_tokens_table, user_id: int
) -> Optional[str]:
    """Resolve the MiniMax API key for a user.

    Priority: user's default MiniMax token (if available and not needs_reentry)
    Fallback: os.getenv("MINIMAX_API_KEY")

    Returns the plaintext API key or None if neither is available.
    Note: This function cannot decrypt — it returns the global fallback
    unless we have a way to get the user's password at call time.
    For user token usage, the caller must pass the decrypted key directly.

    In practice, we update last_used_at when the user's token is resolved
    via the analyze endpoints (which already have the user context).
    """
    # Check if user has a default minimax token that is not needs_reentry
    row = await db.fetch_one(
        user_ai_tokens_table.select().where(
            (user_ai_tokens_table.c.user_id == user_id)
            & (user_ai_tokens_table.c.provider == "minimax")
            & (user_ai_tokens_table.c.is_default == True)
            & (user_ai_tokens_table.c.needs_reentry == False)
        )
    )

    if row:
        # We cannot decrypt without the user's password at this point.
        # The analyze endpoints should resolve the token before calling AI.
        # For background/scheduled crawl, fall back to global key.
        # Return None to signal "user has a token but we can't decrypt it here"
        # The caller (analyze endpoint) should handle this case.
        pass

    # Fallback to global key
    global_key = os.getenv("MINIMAX_API_KEY", "").strip()
    return global_key if global_key else None


async def get_user_default_token_row(
    db, user_ai_tokens_table, user_id: int, provider: str = "minimax"
):
    """Get the user's default token row for a provider (for decrypt by caller)."""
    return await db.fetch_one(
        user_ai_tokens_table.select().where(
            (user_ai_tokens_table.c.user_id == user_id)
            & (user_ai_tokens_table.c.provider == provider)
            & (user_ai_tokens_table.c.is_default == True)
            & (user_ai_tokens_table.c.needs_reentry == False)
        )
    )


async def update_last_used(db, user_ai_tokens_table, token_id: int) -> None:
    """Update last_used_at timestamp for a token."""
    now = datetime.now(timezone.utc)
    await db.execute(
        user_ai_tokens_table.update()
        .where(user_ai_tokens_table.c.id == token_id)
        .values(last_used_at=now)
    )
