"""
---
name: test_llm_vault
description: "KEK/DEK envelope encryption vault tests — wrap/unwrap, credential AAD, rotation, error safety"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-vault
spec_doc: null
test_file: tests/stage1/test_llm_vault.py
functions:
  - name: test_envelope_roundtrip_and_password_independence
    line: 67
    purpose: "Full wrap/unwrap DEK + credential encrypt/decrypt round-trip"
    fixtures: [tmp_path]
  - name: test_wrapped_dek_rejects_user_or_ciphertext_swapping
    line: 92
    purpose: "Swapping user_id or ciphertext raises CredentialAuthenticationError"
    fixtures: [tmp_path]
  - name: test_wrapped_dek_rejects_nonce_swapping_and_invalid_length
    line: 104
    purpose: "Swapped or short nonce raises CredentialAuthenticationError"
    fixtures: [tmp_path]
  - name: test_credential_aad_rejects_metadata_tampering
    line: 138
    purpose: "Tampered AAD field raises CredentialAuthenticationError (parametrized)"
    fixtures: []
  - name: test_credential_aad_uses_strict_shared_base_url_normalizer
    line: 172
    purpose: "Malformed base_url raises VaultError (parametrized)"
    fixtures: []
  - name: test_keyring_accepts_strict_base64_and_rejects_unsafe_files
    line: 184
    purpose: "Key file with lax permissions raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: test_keyring_rejects_symlink_and_invalid_material
    line: 192
    purpose: "Symlink or invalid key material raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: test_rotation_can_rewrap_before_active_version_switch
    line: 206
    purpose: "rewrap_user_dek produces v2 envelope while active version is still v1"
    fixtures: [tmp_path]
  - name: test_rotation_is_idempotent_after_interrupted_batch_rerun
    line: 231
    purpose: "Re-running rewrap after simulated failure is idempotent"
    fixtures: [tmp_path]
  - name: test_rotation_verify_and_retire_reject_old_rows
    line: 295
    purpose: "verify_user_dek_rotation and validate_kek_retirement reject old-version rows"
    fixtures: [tmp_path]
  - name: test_rotation_state_machine_and_retire_guard
    line: 326
    purpose: "validate_rotation_transition enforces allowed state transitions"
    fixtures: []
  - name: test_errors_do_not_expose_key_material
    line: 341
    purpose: "CredentialAuthenticationError traceback does not contain plaintext secret"
    fixtures: [tmp_path]
  - name: test_vault_error_traceback_does_not_chain_backend_secret
    line: 368
    purpose: "VaultError traceback does not chain backend secret detail"
    fixtures: []
  - name: test_key_backend_error_traceback_does_not_chain_os_secret
    line: 389
    purpose: "KeyBackendConfigurationError traceback does not expose OS error secret"
    fixtures: [tmp_path, monkeypatch]
  - name: test_credential_rejects_nonce_swapping_tampering_and_invalid_length
    line: 406
    purpose: "Credential envelope with swapped/short nonce or flipped bit raises error"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_vault.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---

KEK/DEK envelope encryption vault tests.
"""

from __future__ import annotations

import base64
from dataclasses import replace
import os
import traceback

import pytest

from backend.core.llm.key_backends import (
    FileKeyEncryptionBackend,
    KeyBackendConfigurationError,
    WrappedKey,
)
from backend.core.llm.vault import (
    CredentialAuthenticationError,
    RotationState,
    VaultError,
    decrypt_provider_credential,
    encrypt_provider_credential,
    generate_dek,
    rewrap_user_dek,
    unwrap_user_dek,
    validate_kek_retirement,
    validate_rotation_transition,
    verify_user_dek_rotation,
    wrap_user_dek,
)


def _write_key(tmp_path, version: str, *, raw: bool = True):
    tmp_path.chmod(0o700)
    key = os.urandom(32)
    payload = key if raw else base64.b64encode(key) + b"\n"
    path = tmp_path / f"{version}.key"
    path.write_bytes(payload)
    path.chmod(0o400)


def _keyring(tmp_path, *, raw: bool = True):
    _write_key(tmp_path, "v1", raw=raw)
    return FileKeyEncryptionBackend(tmp_path, "v1")


@pytest.mark.asyncio
async def test_envelope_roundtrip_and_password_independence(tmp_path):
    backend = _keyring(tmp_path)
    dek = generate_dek()
    user_key = await wrap_user_dek(backend, user_id=7, dek=dek)
    restored = await unwrap_user_dek(backend, user_key)
    credential = encrypt_provider_credential(
        "secret-api-key",
        dek=restored,
        user_id=7,
        provider_id=11,
        protocol="openai",
        base_url="https://example.com/v1/",
    )

    assert decrypt_provider_credential(
        credential,
        dek=restored,
        user_id=7,
        provider_id=11,
        protocol="openai",
        base_url="https://example.com/v1",
    ) == "secret-api-key"


@pytest.mark.asyncio
async def test_wrapped_dek_rejects_user_or_ciphertext_swapping(tmp_path):
    backend = _keyring(tmp_path)
    first = await wrap_user_dek(backend, user_id=1, dek=generate_dek())
    second = await wrap_user_dek(backend, user_id=2, dek=generate_dek())

    with pytest.raises(CredentialAuthenticationError):
        await unwrap_user_dek(backend, replace(first, user_id=2))
    swapped = replace(first, wrapped_key=replace(first.wrapped_key, ciphertext=second.wrapped_key.ciphertext))
    with pytest.raises(CredentialAuthenticationError):
        await unwrap_user_dek(backend, swapped)


@pytest.mark.asyncio
async def test_wrapped_dek_rejects_nonce_swapping_and_invalid_length(tmp_path):
    backend = _keyring(tmp_path)
    first = await wrap_user_dek(backend, user_id=1, dek=generate_dek())
    second = await wrap_user_dek(backend, user_id=1, dek=generate_dek())

    swapped = replace(
        first,
        wrapped_key=replace(
            first.wrapped_key,
            nonce=second.wrapped_key.nonce,
        ),
    )
    with pytest.raises(CredentialAuthenticationError):
        await unwrap_user_dek(backend, swapped)
    with pytest.raises(CredentialAuthenticationError):
        await unwrap_user_dek(
            backend,
            replace(
                first,
                wrapped_key=replace(first.wrapped_key, nonce=b"short"),
            ),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", 8),
        ("provider_id", 12),
        ("protocol", "anthropic"),
        ("base_url", "https://other.example/v1"),
    ],
)
def test_credential_aad_rejects_metadata_tampering(field, value):
    dek = generate_dek()
    envelope = encrypt_provider_credential(
        "secret",
        dek=dek,
        user_id=7,
        provider_id=11,
        protocol="openai",
        base_url="https://example.com/v1",
    )
    kwargs = {
        "dek": dek,
        "user_id": 7,
        "provider_id": 11,
        "protocol": "openai",
        "base_url": "https://example.com/v1",
    }
    kwargs[field] = value
    with pytest.raises(CredentialAuthenticationError):
        decrypt_provider_credential(envelope, **kwargs)


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user:pass@example.com/v1",
        "https://example.com/v1?key=secret",
        "https://example.com/v1#fragment",
        "https://example.com\\@127.0.0.1",
        "https://%65xample.com/v1",
        "https://example.com/\x00secret",
        "https://example.com:invalid",
    ],
)
def test_credential_aad_uses_strict_shared_base_url_normalizer(base_url):
    with pytest.raises(VaultError):
        encrypt_provider_credential(
            "secret",
            dek=generate_dek(),
            user_id=7,
            provider_id=11,
            protocol="openai",
            base_url=base_url,
        )


def test_keyring_accepts_strict_base64_and_rejects_unsafe_files(tmp_path):
    _keyring(tmp_path, raw=False)
    path = tmp_path / "v1.key"
    path.chmod(0o622)
    with pytest.raises(KeyBackendConfigurationError):
        FileKeyEncryptionBackend(tmp_path, "v1")


def test_keyring_rejects_symlink_and_invalid_material(tmp_path):
    tmp_path.chmod(0o700)
    target = tmp_path / "target"
    target.write_bytes(os.urandom(32))
    (tmp_path / "v1.key").symlink_to(target)
    with pytest.raises(KeyBackendConfigurationError):
        FileKeyEncryptionBackend(tmp_path, "v1")
    (tmp_path / "v1.key").unlink()
    (tmp_path / "v1.key").write_text("not-a-key")
    with pytest.raises(KeyBackendConfigurationError):
        FileKeyEncryptionBackend(tmp_path, "v1")


@pytest.mark.asyncio
async def test_rotation_can_rewrap_before_active_version_switch(tmp_path):
    backend = _keyring(tmp_path)
    _write_key(tmp_path, "v2")
    original = await wrap_user_dek(
        backend,
        user_id=7,
        dek=generate_dek(),
    )

    rotated = await rewrap_user_dek(
        backend,
        original,
        target_kek_version="v2",
    )

    assert backend.active_key_version == "v1"
    assert rotated.wrapped_key.kek_version == "v2"
    await verify_user_dek_rotation(
        backend,
        rotated,
        target_kek_version="v2",
    )


@pytest.mark.asyncio
async def test_rotation_is_idempotent_after_interrupted_batch_rerun(tmp_path):
    backend = _keyring(tmp_path)
    _write_key(tmp_path, "v2")
    rows = [
        await wrap_user_dek(
            backend,
            user_id=user_id,
            dek=generate_dek(),
        )
        for user_id in (1, 2, 3)
    ]

    original_wrap_key = backend.wrap_key
    target_wrap_calls = 0

    async def fail_second_target_wrap(
        plaintext_dek,
        *,
        aad,
        kek_version=None,
    ):
        nonlocal target_wrap_calls
        if kek_version == "v2":
            target_wrap_calls += 1
            if target_wrap_calls == 2:
                raise KeyBackendConfigurationError("simulated wrap failure")
        return await original_wrap_key(
            plaintext_dek,
            aad=aad,
            kek_version=kek_version,
        )

    backend.wrap_key = fail_second_target_wrap
    rows[0] = await rewrap_user_dek(
        backend,
        rows[0],
        target_kek_version="v2",
    )
    with pytest.raises(VaultError):
        await rewrap_user_dek(
            backend,
            rows[1],
            target_kek_version="v2",
        )
    rerun = [
        await rewrap_user_dek(
            backend,
            row,
            target_kek_version="v2",
        )
        for row in rows
    ]

    assert rerun[0] is rows[0]
    assert {row.wrapped_key.kek_version for row in rerun} == {"v2"}
    for row in rerun:
        await verify_user_dek_rotation(
            backend,
            row,
            target_kek_version="v2",
        )


@pytest.mark.asyncio
async def test_rotation_verify_and_retire_reject_old_rows(tmp_path):
    backend = _keyring(tmp_path)
    _write_key(tmp_path, "v2")
    old_row = await wrap_user_dek(
        backend,
        user_id=1,
        dek=generate_dek(),
    )
    new_row = await rewrap_user_dek(
        backend,
        old_row,
        target_kek_version="v2",
    )

    with pytest.raises(VaultError):
        await verify_user_dek_rotation(
            backend,
            old_row,
            target_kek_version="v2",
        )
    with pytest.raises(VaultError):
        validate_kek_retirement(
            (old_row, new_row),
            retiring_kek_version="v1",
        )
    validate_kek_retirement(
        (new_row,),
        retiring_kek_version="v1",
    )


def test_rotation_state_machine_and_retire_guard():
    validate_rotation_transition(RotationState.PREPARE, RotationState.REWRAP)
    validate_rotation_transition(RotationState.REWRAP, RotationState.VERIFY)
    validate_rotation_transition(RotationState.VERIFY, RotationState.ACTIVATE)
    validate_rotation_transition(
        RotationState.ACTIVATE, RotationState.RETIRE, old_version_rows=0
    )
    with pytest.raises(VaultError):
        validate_rotation_transition(RotationState.PREPARE, RotationState.ACTIVATE)
    with pytest.raises(VaultError):
        validate_rotation_transition(
            RotationState.ACTIVATE, RotationState.RETIRE, old_version_rows=1
        )


def test_errors_do_not_expose_key_material(tmp_path):
    secret = "credential-that-must-not-leak"
    dek = generate_dek()
    envelope = encrypt_provider_credential(
        secret,
        dek=dek,
        user_id=1,
        provider_id=1,
        protocol="openai",
        base_url="https://example.com",
    )
    with pytest.raises(CredentialAuthenticationError) as captured:
        decrypt_provider_credential(
            replace(envelope, ciphertext=envelope.ciphertext[:-1] + b"x"),
            dek=dek,
            user_id=1,
            provider_id=1,
            protocol="openai",
            base_url="https://example.com",
        )
    assert secret not in str(captured.value)
    assert secret not in "".join(
        traceback.format_exception(captured.value)
    )


@pytest.mark.asyncio
async def test_vault_error_traceback_does_not_chain_backend_secret():
    secret = "TOP-SECRET-BACKEND-DETAIL"

    class FailingBackend:
        active_key_version = "v1"

        async def wrap_key(self, plaintext_dek, *, aad, kek_version=None):
            raise KeyBackendConfigurationError(secret)

    with pytest.raises(VaultError) as captured:
        await wrap_user_dek(
            FailingBackend(),
            user_id=1,
            dek=generate_dek(),
        )

    assert secret not in "".join(
        traceback.format_exception(captured.value)
    )


def test_key_backend_error_traceback_does_not_chain_os_secret(
    tmp_path, monkeypatch
):
    secret = "TOP-SECRET-OS-DETAIL"

    def fail_stat(self):
        raise OSError(secret)

    monkeypatch.setattr(type(tmp_path), "stat", fail_stat)
    with pytest.raises(KeyBackendConfigurationError) as captured:
        FileKeyEncryptionBackend(tmp_path, "v1")

    assert secret not in "".join(
        traceback.format_exception(captured.value)
    )


def test_credential_rejects_nonce_swapping_tampering_and_invalid_length():
    dek = generate_dek()
    kwargs = {
        "dek": dek,
        "user_id": 1,
        "provider_id": 1,
        "protocol": "openai",
        "base_url": "https://example.com",
    }
    first = encrypt_provider_credential("first", **kwargs)
    second = encrypt_provider_credential("second", **kwargs)

    invalid_envelopes = (
        replace(first, nonce=second.nonce),
        replace(first, nonce=b"short"),
        replace(
            first,
            ciphertext=first.ciphertext[:-1]
            + bytes([first.ciphertext[-1] ^ 1]),
        ),
    )
    for envelope in invalid_envelopes:
        with pytest.raises(CredentialAuthenticationError):
            decrypt_provider_credential(envelope, **kwargs)
