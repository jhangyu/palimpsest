# backend/core/crypto.py
"""AES-GCM encryption/decryption for AI token vault.

Key derivation uses PBKDF2-HMAC-SHA256 with (user_id + token_salt + password).
No env-based master key is required.
"""

import os
import hashlib
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


# KDF iterations — sufficient for PBKDF2 with AES-GCM vault (not primary password store)
_KDF_ITERATIONS = 100_000
_KEY_LENGTH = 32  # 256-bit AES key
_NONCE_LENGTH = 12  # 96-bit nonce for AES-GCM


def _derive_key(password: str, user_id: int, salt: str) -> bytes:
    """Derive a 256-bit AES key from (password, user_id, salt) via PBKDF2."""
    # Combine user_id + salt as the KDF salt material
    combined_salt = f"{user_id}:{salt}".encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_LENGTH,
        salt=combined_salt,
        iterations=_KDF_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def generate_token_salt() -> str:
    """Generate a random salt for token encryption (base64-encoded, 16 bytes)."""
    return base64.urlsafe_b64encode(os.urandom(16)).decode("ascii")


def encrypt_token(plaintext: str, password: str, user_id: int, salt: str) -> str:
    """Encrypt a plaintext API token using AES-GCM.

    Returns base64url-encoded (nonce + ciphertext + tag).
    """
    key = _derive_key(password, user_id, salt)
    nonce = os.urandom(_NONCE_LENGTH)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # nonce (12) + ciphertext+tag
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_token(ciphertext_b64: str, password: str, user_id: int, salt: str) -> str:
    """Decrypt an AES-GCM encrypted token.

    Raises ValueError on decryption failure (wrong password, tampered data, etc.).
    """
    try:
        raw = base64.urlsafe_b64decode(ciphertext_b64)
    except Exception as e:
        raise ValueError("Invalid ciphertext encoding") from e

    if len(raw) < _NONCE_LENGTH + 16:  # nonce + minimum tag
        raise ValueError("Ciphertext too short")

    nonce = raw[:_NONCE_LENGTH]
    ct_and_tag = raw[_NONCE_LENGTH:]
    key = _derive_key(password, user_id, salt)
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ct_and_tag, None)
    except Exception as e:
        raise ValueError("Decryption failed — wrong password or corrupted data") from e
    return plaintext.decode("utf-8")


def mask_token(plaintext: str) -> str:
    """Mask a token showing only the last 4 characters.

    Example: 'sk-abc123xyz9876' -> '***********9876'
    """
    if len(plaintext) <= 4:
        return "****"
    return "*" * (len(plaintext) - 4) + plaintext[-4:]


def get_token_last4(plaintext: str) -> str:
    """Get the last 4 characters of a token for display."""
    if len(plaintext) <= 4:
        return plaintext
    return plaintext[-4:]


async def re_encrypt_all_user_tokens(
    database, user_ai_tokens_table, user_id: int, old_password: str, new_password: str
) -> bool:
    """Re-encrypt all AI tokens for a user from old_password to new_password.

    This MUST be called BEFORE updating the password_hash.
    Returns True on success. Raises on failure (caller should abort password change).

    This function reads all user tokens, decrypts with old password, re-encrypts
    with new password, and updates all rows. If any token fails, no changes are
    committed (caller wraps in transaction).
    """
    from sqlalchemy import select

    query = select(user_ai_tokens_table).where(
        user_ai_tokens_table.c.user_id == user_id
    )
    tokens = await database.fetch_all(query)

    if not tokens:
        return True

    updates = []
    for token_row in tokens:
        if token_row["needs_reentry"]:
            # Skip tokens that already need re-entry (e.g., after password reset)
            continue

        try:
            plaintext = decrypt_token(
                token_row["encrypted_token"],
                old_password,
                user_id,
                token_row["token_salt"],
            )
        except ValueError:
            raise ValueError(
                f"Failed to decrypt token id={token_row['id']} with old password. "
                "Password change aborted to prevent data loss."
            )

        new_salt = generate_token_salt()
        new_ciphertext = encrypt_token(plaintext, new_password, user_id, new_salt)
        updates.append({
            "token_id": token_row["id"],
            "encrypted_token": new_ciphertext,
            "token_salt": new_salt,
        })

    # Apply all updates
    for upd in updates:
        await database.execute(
            user_ai_tokens_table.update()
            .where(user_ai_tokens_table.c.id == upd["token_id"])
            .values(
                encrypted_token=upd["encrypted_token"],
                token_salt=upd["token_salt"],
            )
        )

    return True
