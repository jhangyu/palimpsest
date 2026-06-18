"""Key-encryption backends for LLM provider credentials."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import os
from pathlib import Path
import stat
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class KeyBackendError(Exception):
    """Sanitized key backend failure."""


class KeyBackendConfigurationError(KeyBackendError):
    """The keyring is missing or unsafe."""


class KeyVersionNotFoundError(KeyBackendError):
    """The requested KEK version is unavailable."""


@dataclass(frozen=True)
class WrappedKey:
    ciphertext: bytes
    nonce: bytes
    algorithm: str
    kek_version: str


class KeyEncryptionBackend(Protocol):
    @property
    def active_key_version(self) -> str: ...

    async def wrap_key(
        self,
        plaintext_dek: bytes,
        *,
        aad: bytes,
        kek_version: str | None = None,
    ) -> WrappedKey: ...

    async def unwrap_key(self, wrapped: WrappedKey, *, aad: bytes) -> bytes: ...


class FileKeyEncryptionBackend:
    """Read versioned 256-bit KEKs from a Docker Secret/read-only directory."""

    algorithm = "AES-256-GCM"

    def __init__(self, keyring_dir: str | Path, active_key_version: str) -> None:
        self._keyring_dir = Path(keyring_dir)
        self._active_key_version = self._validate_version(active_key_version)
        self._validate_directory()
        self._load_key(self._active_key_version)

    @property
    def active_key_version(self) -> str:
        return self._active_key_version

    def available_versions(self) -> tuple[str, ...]:
        if not self._keyring_dir.is_dir():
            return ()
        return tuple(sorted(path.stem for path in self._keyring_dir.glob("*.key")))

    async def wrap_key(
        self,
        plaintext_dek: bytes,
        *,
        aad: bytes,
        kek_version: str | None = None,
    ) -> WrappedKey:
        if len(plaintext_dek) != 32:
            raise KeyBackendConfigurationError("DEK must be 32 bytes")
        version = (
            self._active_key_version
            if kek_version is None
            else self._validate_version(kek_version)
        )
        nonce = os.urandom(12)
        key = self._load_key(version)
        return WrappedKey(
            ciphertext=AESGCM(key).encrypt(nonce, plaintext_dek, aad),
            nonce=nonce,
            algorithm=self.algorithm,
            kek_version=version,
        )

    async def unwrap_key(self, wrapped: WrappedKey, *, aad: bytes) -> bytes:
        if wrapped.algorithm != self.algorithm:
            raise KeyBackendConfigurationError("unsupported wrapped-key algorithm")
        if len(wrapped.nonce) != 12:
            raise KeyBackendError("wrapped key has invalid nonce")
        key = self._load_key(wrapped.kek_version)
        try:
            plaintext = AESGCM(key).decrypt(wrapped.nonce, wrapped.ciphertext, aad)
        except Exception:
            raise KeyBackendError("wrapped key authentication failed") from None
        if len(plaintext) != 32:
            raise KeyBackendError("wrapped key has invalid plaintext length")
        return plaintext

    def _validate_directory(self) -> None:
        try:
            info = self._keyring_dir.stat()
        except OSError:
            raise KeyBackendConfigurationError("KEK keyring directory is unavailable") from None
        if not stat.S_ISDIR(info.st_mode):
            raise KeyBackendConfigurationError("KEK keyring path is not a directory")
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise KeyBackendConfigurationError("KEK keyring directory is writable by group or others")

    def _load_key(self, version: str) -> bytes:
        version = self._validate_version(version)
        path = self._keyring_dir / f"{version}.key"
        try:
            info = path.lstat()
        except OSError:
            raise KeyVersionNotFoundError("KEK version is unavailable") from None
        if not stat.S_ISREG(info.st_mode):
            raise KeyBackendConfigurationError("KEK file is not a regular file")
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise KeyBackendConfigurationError("KEK file is writable by group or others")
        try:
            payload = path.read_bytes()
        except OSError:
            raise KeyBackendConfigurationError("KEK file cannot be read") from None
        return self._decode_key(payload)

    @staticmethod
    def _validate_version(version: str) -> str:
        if not version or not all(char.isalnum() or char in "._-" for char in version):
            raise KeyBackendConfigurationError("invalid KEK version")
        if version in {".", ".."}:
            raise KeyBackendConfigurationError("invalid KEK version")
        return version

    @staticmethod
    def _decode_key(payload: bytes) -> bytes:
        if len(payload) == 32:
            return payload
        encoded = payload.strip()
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise KeyBackendConfigurationError("KEK must be 32 raw bytes or strict base64") from None
        if len(decoded) != 32:
            raise KeyBackendConfigurationError("KEK must decode to 32 bytes")
        return decoded
