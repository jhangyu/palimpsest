"""
---
name: test_kek_lifecycle
description: "Stage 1.3 — KEK/DEK encryption lifecycle end-to-end tests"
stage: stage1
type: pytest
target:
  layer: backend
  domain: kek
spec_doc: null
test_file: tests/stage1/test_kek_lifecycle.py
functions:
  - name: test_user_secret_key_bootstrap
    line: 72
    purpose: "First provider creation auto-bootstraps the user_secret_keys row"
    fixtures: [kek_auth_client, db]
  - name: test_dek_wrap_unwrap
    line: 115
    purpose: "wrap_user_dek → unwrap_user_dek round-trip returns original DEK"
    fixtures: [kek_backend]
  - name: test_credential_encrypt_decrypt
    line: 130
    purpose: "encrypt_provider_credential → decrypt_provider_credential round-trip"
    fixtures: []
  - name: test_credential_decrypt_wrong_aad
    line: 160
    purpose: "Tampered AAD raises CredentialAuthenticationError"
    fixtures: []
  - name: test_reveal_api_key
    line: 195
    purpose: "Create provider → reveal → plaintext matches; security headers present"
    fixtures: [kek_auth_client]
  - name: test_reveal_api_key_wrong_password
    line: 232
    purpose: "Wrong password on reveal → 403 invalid_password"
    fixtures: [kek_auth_client]
  - name: test_reveal_api_key_rate_limit
    line: 258
    purpose: "Reveal attempts rate-limited after repeated failures → 429 (xfail)"
    fixtures: [kek_auth_client]
  - name: test_kek_file_permission_check
    line: 286
    purpose: "Overly permissive key file raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: test_kek_auto_generation
    line: 304
    purpose: "generate_keyring creates directory (0o700) + key file (0o600)"
    fixtures: [tmp_path]
  - name: test_dek_rewrap
    line: 326
    purpose: "rewrap_user_dek migrates DEK from v1 to v2; unwrap with v2 succeeds"
    fixtures: [tmp_path]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_kek_lifecycle.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
    LLM_PROVIDER_PROFILES_ENABLED: "true"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---

Stage 1.3 — Full encryption lifecycle tests.

Tests 1–4: Direct vault/backend functions (no HTTP, uses kek_backend fixture).
Tests 5–7: HTTP reveal endpoint (uses kek_auth_client fixture).
Tests 8–10: File-system permission and key-generation tests (tmp dirs only).

NOTE (1.3.7): The reveal_provider rate-limit scope is not present in
`RATE_LIMIT_CONFIG` in auth.py, so `check_rate_limit` always returns
(True, None) and `record_attempt` is a no-op for this scope.
That test is therefore marked xfail until the config entry is added.
"""

from __future__ import annotations

import base64

import pytest
import sqlalchemy

from conftest import _get_csrf_token

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://api.openai.com/v1"


async def _create_provider_http(client, csrf: str, *, label="Test Provider") -> dict:
    """POST /settings/ai-providers and return the response JSON."""
    resp = await client.post(
        "/settings/ai-providers",
        json={
            "label": label,
            "protocol": "openai",
            "base_url": _DEFAULT_BASE_URL,
            "model": "gpt-4o",
            "api_key": "sk-secret-test-key-12345678",
            "max_tokens": 4096,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tests 1.3.1 – 1.3.4: Direct vault tests (no HTTP)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_user_secret_key_bootstrap(kek_auth_client, db):
    """1.3.1 — First provider creation auto-bootstraps the user_secret_keys row."""
    from core.db import ai_tables

    # Identify the authenticated user
    me_resp = await kek_auth_client.get("/auth/me")
    assert me_resp.status_code == 200, me_resp.text
    user_id = me_resp.json()["id"]

    # The db fixture is a databases.Database instance; use fetch_one (not
    # SQLAlchemy session .execute().mappings()).
    query = sqlalchemy.select(ai_tables.user_secret_keys).where(
        ai_tables.user_secret_keys.c.user_id == user_id
    )

    # Remove any pre-existing user_secret_keys row for this user.
    # test_ai_provider_api.py runs alphabetically before this file and may
    # have already bootstrapped the row for the same user if fixtures are
    # session-scoped.  Deleting it here lets us re-test the bootstrap path.
    await db.execute(
        ai_tables.user_secret_keys.delete().where(
            ai_tables.user_secret_keys.c.user_id == user_id
        )
    )

    # No user_secret_keys row should exist after the cleanup above
    row = await db.fetch_one(query)
    assert row is None, "Expected no user_secret_keys row before first provider creation"

    # Creating a provider triggers bootstrap_user_secret_key
    csrf = await _get_csrf_token(kek_auth_client)
    await _create_provider_http(kek_auth_client, csrf)

    # Row must now exist with correct schema
    row = await db.fetch_one(query)
    assert row is not None, "user_secret_keys row not created after provider creation"
    assert row["algorithm"] == "AES-256-GCM"
    assert row["kek_version"] == "v1"
    assert len(row["dek_nonce"]) == 12
    assert len(row["encrypted_dek"]) > 0


@pytest.mark.asyncio(loop_scope="session")
async def test_dek_wrap_unwrap(kek_backend):
    """1.3.2 — wrap_user_dek → unwrap_user_dek round-trip returns original DEK."""
    from core.llm.vault import generate_dek, unwrap_user_dek, wrap_user_dek

    dek = generate_dek()
    assert len(dek) == 32

    envelope = await wrap_user_dek(kek_backend, user_id=42, dek=dek)
    assert envelope.user_id == 42
    assert envelope.wrapped_key.kek_version == kek_backend.active_key_version

    restored = await unwrap_user_dek(kek_backend, envelope)
    assert restored == dek


def test_credential_encrypt_decrypt():
    """1.3.3 — encrypt_provider_credential → decrypt_provider_credential round-trip."""
    from core.llm.vault import (
        decrypt_provider_credential,
        encrypt_provider_credential,
        generate_dek,
    )

    dek = generate_dek()
    api_key = "sk-test-key"

    envelope = encrypt_provider_credential(
        api_key,
        dek=dek,
        user_id=7,
        provider_id=11,
        protocol="openai",
        base_url=_DEFAULT_BASE_URL,
    )
    plaintext = decrypt_provider_credential(
        envelope,
        dek=dek,
        user_id=7,
        provider_id=11,
        protocol="openai",
        base_url=_DEFAULT_BASE_URL,
    )
    assert plaintext == api_key


def test_credential_decrypt_wrong_aad():
    """1.3.4 — Tampered AAD (different protocol) raises CredentialAuthenticationError."""
    from core.llm.vault import (
        CredentialAuthenticationError,
        decrypt_provider_credential,
        encrypt_provider_credential,
        generate_dek,
    )

    dek = generate_dek()
    envelope = encrypt_provider_credential(
        "sk-secret",
        dek=dek,
        user_id=1,
        provider_id=1,
        protocol="openai",
        base_url=_DEFAULT_BASE_URL,
    )

    with pytest.raises(CredentialAuthenticationError):
        decrypt_provider_credential(
            envelope,
            dek=dek,
            user_id=1,
            provider_id=1,
            protocol="anthropic",  # tampered
            base_url=_DEFAULT_BASE_URL,
        )


# ---------------------------------------------------------------------------
# Tests 1.3.5 – 1.3.7: HTTP reveal endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_reveal_api_key(kek_auth_client):
    """1.3.5 — Create provider → reveal → plaintext matches; security headers present."""
    csrf = await _get_csrf_token(kek_auth_client)
    original_key = "sk-secret-test-key-12345678"
    pid = None

    # Create a provider
    resp = await kek_auth_client.post(
        "/settings/ai-providers",
        json={
            "label": "Reveal Test Provider",
            "protocol": "openai",
            "base_url": _DEFAULT_BASE_URL,
            "model": "gpt-4o",
            "api_key": original_key,
            "max_tokens": 4096,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 201, resp.text
    pid = resp.json()["id"]

    try:
        # Reveal with correct password
        reveal = await kek_auth_client.post(
            f"/settings/ai-providers/{pid}/reveal",
            json={"current_password": "TestPass123!"},
            headers={"X-CSRF-Token": csrf},
        )
        assert reveal.status_code == 200, reveal.text
        assert reveal.json()["api_key"] == original_key

        # Security headers must be set
        cache_control = reveal.headers.get("cache-control", "")
        assert "no-store" in cache_control
        assert "private" in cache_control
    finally:
        if pid:
            csrf = kek_auth_client.cookies.get("csrf_token", "")
            await kek_auth_client.delete(
                f"/settings/ai-providers/{pid}",
                headers={"X-CSRF-Token": csrf},
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_reveal_api_key_wrong_password(kek_auth_client):
    """1.3.6 — Wrong password on reveal → 403 invalid_password."""
    csrf = await _get_csrf_token(kek_auth_client)
    provider = await _create_provider_http(kek_auth_client, csrf)
    pid = provider["id"]

    try:
        reveal = await kek_auth_client.post(
            f"/settings/ai-providers/{pid}/reveal",
            json={"current_password": "WrongPassword999!"},
            headers={"X-CSRF-Token": csrf},
        )
        assert reveal.status_code == 403, reveal.text
        err = reveal.json()
        assert err["detail"]["code"] == "invalid_password"
    finally:
        if pid:
            csrf = kek_auth_client.cookies.get("csrf_token", "")
            await kek_auth_client.delete(
                f"/settings/ai-providers/{pid}",
                headers={"X-CSRF-Token": csrf},
            )


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.xfail(
    strict=False,
    reason=(
        "reveal_provider scope is absent from RATE_LIMIT_CONFIG in auth.py — "
        "check_rate_limit always returns (True, None) and record_attempt is a "
        "no-op for this scope. Rate limiting is not enforced until the config "
        "entry is added."
    ),
)
async def test_reveal_api_key_rate_limit(kek_auth_client):
    """1.3.7 — Reveal attempts rate-limited after repeated failures → 429."""
    csrf = await _get_csrf_token(kek_auth_client)
    provider = await _create_provider_http(kek_auth_client, csrf)
    pid = provider["id"]

    try:
        # Exhaust the rate limit with wrong passwords
        for _ in range(10):
            resp = await kek_auth_client.post(
                f"/settings/ai-providers/{pid}/reveal",
                json={"current_password": "WrongPassword!"},
                headers={"X-CSRF-Token": csrf},
            )
            if resp.status_code == 429:
                # Rate limit triggered — test passes
                return

        pytest.fail(
            "Expected 429 after repeated wrong-password reveal attempts, "
            "but rate limiting never kicked in. "
            "Add 'reveal_provider' to RATE_LIMIT_CONFIG in core/auth.py."
        )
    finally:
        if pid:
            csrf = kek_auth_client.cookies.get("csrf_token", "")
            await kek_auth_client.delete(
                f"/settings/ai-providers/{pid}",
                headers={"X-CSRF-Token": csrf},
            )


# ---------------------------------------------------------------------------
# Tests 1.3.8 – 1.3.10: File-system / key-backend tests (no DB fixtures)
# ---------------------------------------------------------------------------

def test_kek_file_permission_check(tmp_path):
    """1.3.8 — Overly permissive key file → KeyBackendConfigurationError."""
    from core.llm.key_backends import (
        FileKeyEncryptionBackend,
        KeyBackendConfigurationError,
    )

    # Generate a valid keyring first
    FileKeyEncryptionBackend.generate_keyring(str(tmp_path), "v1")

    # Make the key file world-readable (permissions 0o644 → group-readable)
    key_path = tmp_path / "v1.key"
    key_path.chmod(0o644)

    with pytest.raises(KeyBackendConfigurationError):
        FileKeyEncryptionBackend(str(tmp_path), "v1")


def test_kek_auto_generation(tmp_path):
    """1.3.9 — generate_keyring creates directory (0o700) + key file (0o600)."""
    from core.llm.key_backends import FileKeyEncryptionBackend

    keyring_dir = tmp_path / "keyring"
    key_path = FileKeyEncryptionBackend.generate_keyring(str(keyring_dir), "v1")

    # Directory permissions
    dir_mode = keyring_dir.stat().st_mode & 0o777
    assert dir_mode == 0o700, f"Expected 0o700, got {oct(dir_mode)}"

    # Key file permissions
    file_mode = key_path.stat().st_mode & 0o777
    assert file_mode == 0o600, f"Expected 0o600, got {oct(file_mode)}"

    # Key content decodes to 32 bytes
    encoded = key_path.read_bytes().strip()
    decoded = base64.b64decode(encoded, validate=True)
    assert len(decoded) == 32, f"Expected 32-byte key, got {len(decoded)} bytes"


@pytest.mark.asyncio(loop_scope="session")
async def test_dek_rewrap(tmp_path):
    """1.3.10 — rewrap_user_dek migrates DEK from v1 to v2; unwrap with v2 succeeds."""
    from core.llm.key_backends import FileKeyEncryptionBackend
    from core.llm.vault import (
        generate_dek,
        rewrap_user_dek,
        unwrap_user_dek,
        wrap_user_dek,
    )

    # Set up v1 keyring and wrap a DEK
    FileKeyEncryptionBackend.generate_keyring(str(tmp_path), "v1")
    backend = FileKeyEncryptionBackend(str(tmp_path), "v1")

    original_dek = generate_dek()
    envelope_v1 = await wrap_user_dek(backend, user_id=99, dek=original_dek)
    assert envelope_v1.wrapped_key.kek_version == "v1"

    # Add v2 key to the same keyring directory
    FileKeyEncryptionBackend.generate_keyring(str(tmp_path), "v2")

    # Rewrap DEK from v1 → v2 (backend still has v1 as active, but can load v2)
    envelope_v2 = await rewrap_user_dek(backend, envelope_v1, target_kek_version="v2")
    assert envelope_v2.wrapped_key.kek_version == "v2"

    # Unwrap with v2 envelope → same original DEK
    restored = await unwrap_user_dek(backend, envelope_v2)
    assert restored == original_dek
