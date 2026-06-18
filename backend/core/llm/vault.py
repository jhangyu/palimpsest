"""Envelope encryption primitives for per-user LLM provider credentials."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .endpoints import normalize_base_url
from .key_backends import KeyBackendError, KeyEncryptionBackend, WrappedKey


class VaultError(Exception):
    """Sanitized credential-vault failure."""


class CredentialAuthenticationError(VaultError):
    """Ciphertext or its bound metadata failed authentication."""


@dataclass(frozen=True)
class CredentialEnvelope:
    ciphertext: bytes
    nonce: bytes
    algorithm: str
    credential_version: int


@dataclass(frozen=True)
class UserKeyEnvelope:
    user_id: int
    wrapped_key: WrappedKey


def generate_dek() -> bytes:
    return os.urandom(32)


def canonicalize_base_url(base_url: str) -> str:
    try:
        return normalize_base_url(base_url)
    except ValueError:
        raise VaultError("invalid provider base URL") from None


def wrapped_dek_aad(
    *, user_id: int, algorithm: str, kek_version: str
) -> bytes:
    return _aad(
        "palimpsest.llm.wrapped-dek.v1",
        user_id=user_id,
        algorithm=algorithm,
        kek_version=kek_version,
    )


def provider_credential_aad(
    *,
    user_id: int,
    provider_id: int,
    protocol: str,
    base_url: str,
    credential_version: int,
) -> bytes:
    return _aad(
        "palimpsest.llm.provider-credential.v1",
        user_id=user_id,
        provider_id=provider_id,
        protocol=protocol.lower(),
        base_url=canonicalize_base_url(base_url),
        credential_version=credential_version,
    )


async def wrap_user_dek(
    backend: KeyEncryptionBackend,
    *,
    user_id: int,
    dek: bytes,
    kek_version: str | None = None,
) -> UserKeyEnvelope:
    version = (
        backend.active_key_version
        if kek_version is None
        else kek_version
    )
    aad = wrapped_dek_aad(
        user_id=user_id,
        algorithm="AES-256-GCM",
        kek_version=version,
    )
    try:
        wrapped = await backend.wrap_key(
            dek,
            aad=aad,
            kek_version=kek_version,
        )
    except KeyBackendError:
        raise VaultError("unable to wrap user key") from None
    if wrapped.kek_version != version:
        raise VaultError("key backend returned an unexpected KEK version")
    return UserKeyEnvelope(user_id=user_id, wrapped_key=wrapped)


async def unwrap_user_dek(
    backend: KeyEncryptionBackend, envelope: UserKeyEnvelope
) -> bytes:
    wrapped = envelope.wrapped_key
    aad = wrapped_dek_aad(
        user_id=envelope.user_id,
        algorithm=wrapped.algorithm,
        kek_version=wrapped.kek_version,
    )
    try:
        return await backend.unwrap_key(wrapped, aad=aad)
    except KeyBackendError:
        raise CredentialAuthenticationError("user key authentication failed") from None


def encrypt_provider_credential(
    api_key: str,
    *,
    dek: bytes,
    user_id: int,
    provider_id: int,
    protocol: str,
    base_url: str,
    credential_version: int = 1,
) -> CredentialEnvelope:
    if len(dek) != 32:
        raise VaultError("DEK must be 32 bytes")
    nonce = os.urandom(12)
    aad = provider_credential_aad(
        user_id=user_id,
        provider_id=provider_id,
        protocol=protocol,
        base_url=base_url,
        credential_version=credential_version,
    )
    return CredentialEnvelope(
        ciphertext=AESGCM(dek).encrypt(nonce, api_key.encode("utf-8"), aad),
        nonce=nonce,
        algorithm="AES-256-GCM",
        credential_version=credential_version,
    )


def decrypt_provider_credential(
    envelope: CredentialEnvelope,
    *,
    dek: bytes,
    user_id: int,
    provider_id: int,
    protocol: str,
    base_url: str,
) -> str:
    if (
        envelope.algorithm != "AES-256-GCM"
        or len(dek) != 32
        or len(envelope.nonce) != 12
    ):
        raise CredentialAuthenticationError("credential authentication failed")
    aad = provider_credential_aad(
        user_id=user_id,
        provider_id=provider_id,
        protocol=protocol,
        base_url=base_url,
        credential_version=envelope.credential_version,
    )
    try:
        plaintext = AESGCM(dek).decrypt(envelope.nonce, envelope.ciphertext, aad)
        return plaintext.decode("utf-8")
    except Exception:
        raise CredentialAuthenticationError("credential authentication failed") from None


class RotationState(StrEnum):
    PREPARE = "prepare"
    REWRAP = "rewrap"
    VERIFY = "verify"
    ACTIVATE = "activate"
    RETIRE = "retire"


_ROTATION_TRANSITIONS = {
    RotationState.PREPARE: RotationState.REWRAP,
    RotationState.REWRAP: RotationState.VERIFY,
    RotationState.VERIFY: RotationState.ACTIVATE,
    RotationState.ACTIVATE: RotationState.RETIRE,
}


async def rewrap_user_dek(
    backend: KeyEncryptionBackend,
    envelope: UserKeyEnvelope,
    *,
    target_kek_version: str,
) -> UserKeyEnvelope:
    """Rewrap one row for a target KEK; already-target rows are unchanged."""

    if envelope.wrapped_key.kek_version == target_kek_version:
        return envelope
    dek = await unwrap_user_dek(backend, envelope)
    return await wrap_user_dek(
        backend,
        user_id=envelope.user_id,
        dek=dek,
        kek_version=target_kek_version,
    )


async def verify_user_dek_rotation(
    backend: KeyEncryptionBackend,
    envelope: UserKeyEnvelope,
    *,
    target_kek_version: str,
) -> None:
    """Verify that a row uses and authenticates under the target KEK."""

    if envelope.wrapped_key.kek_version != target_kek_version:
        raise VaultError("wrapped user key has not reached target KEK version")
    await unwrap_user_dek(backend, envelope)


def validate_kek_retirement(
    envelopes: Iterable[UserKeyEnvelope],
    *,
    retiring_kek_version: str,
) -> None:
    """Reject retirement while any supplied row still references the KEK."""

    if any(
        envelope.wrapped_key.kek_version == retiring_kek_version
        for envelope in envelopes
    ):
        raise VaultError("cannot retire KEK while wrapped keys still use it")


def validate_rotation_transition(
    current: RotationState, target: RotationState, *, old_version_rows: int = 0
) -> None:
    if _ROTATION_TRANSITIONS.get(current) != target:
        raise VaultError("invalid KEK rotation transition")
    if target is RotationState.RETIRE and old_version_rows:
        raise VaultError("cannot retire KEK while wrapped keys still use it")


def _aad(domain: str, **fields: object) -> bytes:
    return json.dumps(
        {"domain": domain, **fields},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
