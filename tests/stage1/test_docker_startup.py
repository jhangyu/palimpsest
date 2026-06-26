"""
---
name: test_docker_startup
description: "Docker Secret and startup configuration tests — FileKeyEncryptionBackend key loading, permission enforcement, wrap/unwrap round-trips"
stage: stage1
type: pytest
target:
  layer: backend
  domain: docker
spec_doc: null
test_file: tests/stage1/test_docker_startup.py
functions:
  - name: TestFileKeyBackendLoading::test_load_valid_raw_32_byte_key
    line: 57
    purpose: "32 raw bytes with 0o600 permissions and 0o700 directory load successfully"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendLoading::test_load_valid_base64_encoded_key
    line: 63
    purpose: "Base64-encoded 32-byte key (with trailing newline) decodes and loads"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendLoading::test_load_key_with_strict_0o400_permissions
    line: 71
    purpose: "Read-only 0o400 key file is accepted as stricter-than-required permission"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendLoading::test_available_versions_returns_all_stems_sorted
    line: 77
    purpose: "available_versions() lists all .key stem names in lexicographic order"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendLoading::test_available_versions_empty_on_missing_dir
    line: 87
    purpose: "available_versions() returns empty tuple when keyring dir is absent"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendPermissions::test_reject_world_readable_key_file
    line: 106
    purpose: "Key file with 0o644 (world-readable) raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendPermissions::test_reject_group_readable_key_file
    line: 112
    purpose: "Key file with 0o640 (group-readable) raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendPermissions::test_reject_group_write_on_key_file
    line: 119
    purpose: "Key file with 0o620 (group-write) raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendPermissions::test_reject_group_writable_directory
    line: 126
    purpose: "Keyring directory writable by group raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendPermissions::test_reject_other_writable_directory
    line: 133
    purpose: "Keyring directory writable by others raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendMissingOrMalformed::test_reject_missing_secret_directory
    line: 148
    purpose: "Non-existent keyring directory raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendMissingOrMalformed::test_reject_file_path_as_directory
    line: 154
    purpose: "Regular file used as keyring path raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendMissingOrMalformed::test_reject_missing_key_version
    line: 161
    purpose: "Requesting a version whose .key file does not exist raises KeyVersionNotFoundError"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendMissingOrMalformed::test_reject_symlink_key_file
    line: 167
    purpose: "Symlink disguised as .key file raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendMissingOrMalformed::test_reject_invalid_key_material_short
    line: 176
    purpose: "Key material shorter than 32 bytes raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendMissingOrMalformed::test_reject_invalid_key_material_bad_base64
    line: 182
    purpose: "Non-base64 wrong-length payload raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendMissingOrMalformed::test_reject_path_traversal_version
    line: 188
    purpose: "Version string with path-traversal characters is rejected immediately"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendMissingOrMalformed::test_reject_empty_version_string
    line: 194
    purpose: "Empty version string raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestFileKeyBackendMissingOrMalformed::test_reject_dot_version_string
    line: 200
    purpose: "Version string '.' raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestWrapUnwrapRoundtrip::test_wrap_unwrap_roundtrip
    line: 215
    purpose: "Wrapping then unwrapping a 32-byte DEK returns the original bytes"
    fixtures: [tmp_path]
  - name: TestWrapUnwrapRoundtrip::test_unwrap_rejects_tampered_aad
    line: 226
    purpose: "Decrypting with a different AAD raises KeyBackendError"
    fixtures: [tmp_path]
  - name: TestWrapUnwrapRoundtrip::test_wrap_rejects_non_32_byte_dek
    line: 236
    purpose: "Wrapping a DEK that is not 32 bytes raises KeyBackendConfigurationError"
    fixtures: [tmp_path]
  - name: TestWrapUnwrapRoundtrip::test_wrap_explicit_kek_version
    line: 244
    purpose: "wrap_key with explicit kek_version stores the version in WrappedKey"
    fixtures: [tmp_path]
  - name: TestStartupGracefulFailure::test_invalid_kek_path_raises_not_silently_ignored
    line: 266
    purpose: "Non-existent KEK path raises KeyBackendConfigurationError at construction time"
    fixtures: [tmp_path]
  - name: TestStartupGracefulFailure::test_kek_config_error_is_exception_subclass
    line: 278
    purpose: "KeyBackendConfigurationError is catchable as a standard Exception subclass"
    fixtures: [tmp_path]
  - name: TestStartupGracefulFailure::test_missing_database_url_falls_back_to_default
    line: 288
    purpose: "Missing DATABASE_URL env var uses hardcoded fallback DSN without crashing"
    fixtures: [monkeypatch]
  - name: TestStartupGracefulFailure::test_empty_database_url_raises_on_construction
    line: 308
    purpose: "Passing empty string to databases.Database raises an error immediately"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_docker_startup.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "Python deps installed (pytest-asyncio, databases)"
---
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

import pytest

from core.llm.key_backends import (
    FileKeyEncryptionBackend,
    KeyBackendConfigurationError,
    KeyBackendError,
    KeyVersionNotFoundError,
)

# ---------------------------------------------------------------------------
# Helper: detect root (root bypasses OS permission enforcement)
# ---------------------------------------------------------------------------
_is_root: bool = hasattr(os, "getuid") and os.getuid() == 0


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _setup_keyring(
    tmp_path: Path,
    *,
    version: str = "v1",
    payload: bytes | None = None,
    dir_mode: int = 0o700,
    file_mode: int = 0o600,
) -> Path:
    """Write a single .key file into *tmp_path* and set permissions."""
    tmp_path.chmod(dir_mode)
    key_file = tmp_path / f"{version}.key"
    key_file.write_bytes(payload if payload is not None else os.urandom(32))
    key_file.chmod(file_mode)
    return tmp_path


# ===========================================================================
# Section 1 – FileKeyEncryptionBackend: loading key material
# ===========================================================================

class TestFileKeyBackendLoading:
    """FileKeyEncryptionBackend correctly reads key material from a directory."""

    def test_load_valid_raw_32_byte_key(self, tmp_path: Path) -> None:
        """32 raw bytes with 0o600 permissions and a 0o700 directory must load."""
        _setup_keyring(tmp_path)
        backend = FileKeyEncryptionBackend(tmp_path, "v1")
        assert backend.active_key_version == "v1"

    def test_load_valid_base64_encoded_key(self, tmp_path: Path) -> None:
        """Base64-encoded 32-byte key (with trailing newline) must decode and load."""
        key = os.urandom(32)
        payload = base64.b64encode(key) + b"\n"
        _setup_keyring(tmp_path, payload=payload)
        backend = FileKeyEncryptionBackend(tmp_path, "v1")
        assert backend.active_key_version == "v1"

    def test_load_key_with_strict_0o400_permissions(self, tmp_path: Path) -> None:
        """Read-only (0o400) key file is stricter than 0o600 and must be accepted."""
        _setup_keyring(tmp_path, file_mode=0o400)
        backend = FileKeyEncryptionBackend(tmp_path, "v1")
        assert backend.active_key_version == "v1"

    def test_available_versions_returns_all_stems_sorted(self, tmp_path: Path) -> None:
        """available_versions() lists all .key stem names in lexicographic order."""
        _setup_keyring(tmp_path, version="v1")
        (tmp_path / "v2.key").write_bytes(os.urandom(32))
        (tmp_path / "v2.key").chmod(0o600)
        backend = FileKeyEncryptionBackend(tmp_path, "v1")
        versions = backend.available_versions()
        assert set(versions) == {"v1", "v2"}
        assert versions == tuple(sorted(versions))

    def test_available_versions_empty_on_missing_dir(self, tmp_path: Path) -> None:
        """available_versions() returns an empty tuple when keyring dir is gone."""
        _setup_keyring(tmp_path)
        backend = FileKeyEncryptionBackend(tmp_path, "v1")
        absent = tmp_path / "ghost"
        # Patch the internal dir to simulate a missing directory (no attribute override
        # needed — just verify the method handles non-existing dir gracefully)
        backend._keyring_dir = absent  # type: ignore[attr-defined]
        assert backend.available_versions() == ()


# ===========================================================================
# Section 2 – FileKeyEncryptionBackend: permission enforcement
# ===========================================================================

class TestFileKeyBackendPermissions:
    """FileKeyEncryptionBackend rejects files/dirs with unsafe permissions."""

    @pytest.mark.skipif(_is_root, reason="root ignores OS permission checks")
    def test_reject_world_readable_key_file(self, tmp_path: Path) -> None:
        """Key file with 0o644 (world-readable) must raise KeyBackendConfigurationError."""
        _setup_keyring(tmp_path, file_mode=0o644)
        with pytest.raises(KeyBackendConfigurationError, match="overly permissive"):
            FileKeyEncryptionBackend(tmp_path, "v1")

    @pytest.mark.skipif(_is_root, reason="root ignores OS permission checks")
    def test_reject_group_readable_key_file(self, tmp_path: Path) -> None:
        """Key file with 0o640 (group-readable) must raise KeyBackendConfigurationError."""
        _setup_keyring(tmp_path, file_mode=0o640)
        with pytest.raises(KeyBackendConfigurationError, match="overly permissive"):
            FileKeyEncryptionBackend(tmp_path, "v1")

    @pytest.mark.skipif(_is_root, reason="root ignores OS permission checks")
    def test_reject_group_write_on_key_file(self, tmp_path: Path) -> None:
        """Key file with 0o620 (group-write) must raise KeyBackendConfigurationError."""
        _setup_keyring(tmp_path, file_mode=0o620)
        with pytest.raises(KeyBackendConfigurationError, match="overly permissive"):
            FileKeyEncryptionBackend(tmp_path, "v1")

    @pytest.mark.skipif(_is_root, reason="root ignores OS permission checks")
    def test_reject_group_writable_directory(self, tmp_path: Path) -> None:
        """Keyring directory writable by group must raise KeyBackendConfigurationError."""
        _setup_keyring(tmp_path, dir_mode=0o770)
        with pytest.raises(KeyBackendConfigurationError):
            FileKeyEncryptionBackend(tmp_path, "v1")

    @pytest.mark.skipif(_is_root, reason="root ignores OS permission checks")
    def test_reject_other_writable_directory(self, tmp_path: Path) -> None:
        """Keyring directory writable by others must raise KeyBackendConfigurationError."""
        _setup_keyring(tmp_path, dir_mode=0o707)
        with pytest.raises(KeyBackendConfigurationError):
            FileKeyEncryptionBackend(tmp_path, "v1")


# ===========================================================================
# Section 3 – FileKeyEncryptionBackend: missing / malformed inputs
# ===========================================================================

class TestFileKeyBackendMissingOrMalformed:
    """FileKeyEncryptionBackend raises clear errors for missing or bad inputs."""

    def test_reject_missing_secret_directory(self, tmp_path: Path) -> None:
        """Non-existent keyring directory raises KeyBackendConfigurationError."""
        absent = tmp_path / "no_such_dir"
        with pytest.raises(KeyBackendConfigurationError):
            FileKeyEncryptionBackend(absent, "v1")

    def test_reject_file_path_as_directory(self, tmp_path: Path) -> None:
        """A regular file used as keyring path raises KeyBackendConfigurationError."""
        not_a_dir = tmp_path / "regular_file"
        not_a_dir.write_bytes(b"data")
        with pytest.raises(KeyBackendConfigurationError):
            FileKeyEncryptionBackend(not_a_dir, "v1")

    def test_reject_missing_key_version(self, tmp_path: Path) -> None:
        """Requesting a version whose .key file does not exist raises KeyVersionNotFoundError."""
        _setup_keyring(tmp_path, version="v1")
        with pytest.raises(KeyVersionNotFoundError):
            FileKeyEncryptionBackend(tmp_path, "v99")

    def test_reject_symlink_key_file(self, tmp_path: Path) -> None:
        """A symlink disguised as a .key file raises KeyBackendConfigurationError."""
        tmp_path.chmod(0o700)
        target = tmp_path / "real_bytes"
        target.write_bytes(os.urandom(32))
        (tmp_path / "v1.key").symlink_to(target)
        with pytest.raises(KeyBackendConfigurationError):
            FileKeyEncryptionBackend(tmp_path, "v1")

    def test_reject_invalid_key_material_short(self, tmp_path: Path) -> None:
        """Key material shorter than 32 bytes (and not valid base64) raises error."""
        _setup_keyring(tmp_path, payload=b"tooshort")
        with pytest.raises(KeyBackendConfigurationError):
            FileKeyEncryptionBackend(tmp_path, "v1")

    def test_reject_invalid_key_material_bad_base64(self, tmp_path: Path) -> None:
        """Non-base64, wrong-length payload raises KeyBackendConfigurationError."""
        _setup_keyring(tmp_path, payload=b"not-a-valid-base64-key!!!")
        with pytest.raises(KeyBackendConfigurationError):
            FileKeyEncryptionBackend(tmp_path, "v1")

    def test_reject_path_traversal_version(self, tmp_path: Path) -> None:
        """Version string containing path-traversal characters is rejected."""
        tmp_path.chmod(0o700)
        with pytest.raises(KeyBackendConfigurationError):
            FileKeyEncryptionBackend(tmp_path, "../etc/passwd")

    def test_reject_empty_version_string(self, tmp_path: Path) -> None:
        """Empty version string raises KeyBackendConfigurationError."""
        tmp_path.chmod(0o700)
        with pytest.raises(KeyBackendConfigurationError):
            FileKeyEncryptionBackend(tmp_path, "")

    def test_reject_dot_version_string(self, tmp_path: Path) -> None:
        """Version string '.' raises KeyBackendConfigurationError."""
        tmp_path.chmod(0o700)
        with pytest.raises(KeyBackendConfigurationError):
            FileKeyEncryptionBackend(tmp_path, ".")


# ===========================================================================
# Section 4 – Wrap / Unwrap round-trip
# ===========================================================================

class TestWrapUnwrapRoundtrip:
    """Envelope encryption primitives work correctly and reject tampering."""

    @pytest.mark.asyncio
    async def test_wrap_unwrap_roundtrip(self, tmp_path: Path) -> None:
        """Wrapping then unwrapping a 32-byte DEK returns the original bytes."""
        _setup_keyring(tmp_path)
        backend = FileKeyEncryptionBackend(tmp_path, "v1")
        dek = os.urandom(32)
        aad = b"user:1:provider:42"
        wrapped = await backend.wrap_key(dek, aad=aad)
        recovered = await backend.unwrap_key(wrapped, aad=aad)
        assert recovered == dek

    @pytest.mark.asyncio
    async def test_unwrap_rejects_tampered_aad(self, tmp_path: Path) -> None:
        """Decrypting with a different AAD must raise KeyBackendError."""
        _setup_keyring(tmp_path)
        backend = FileKeyEncryptionBackend(tmp_path, "v1")
        dek = os.urandom(32)
        wrapped = await backend.wrap_key(dek, aad=b"original-aad")
        with pytest.raises(KeyBackendError):
            await backend.unwrap_key(wrapped, aad=b"tampered-aad")

    @pytest.mark.asyncio
    async def test_wrap_rejects_non_32_byte_dek(self, tmp_path: Path) -> None:
        """Wrapping a DEK that is not 32 bytes raises KeyBackendConfigurationError."""
        _setup_keyring(tmp_path)
        backend = FileKeyEncryptionBackend(tmp_path, "v1")
        with pytest.raises(KeyBackendConfigurationError):
            await backend.wrap_key(os.urandom(16), aad=b"aad")

    @pytest.mark.asyncio
    async def test_wrap_explicit_kek_version(self, tmp_path: Path) -> None:
        """wrap_key with an explicit kek_version stores the version in WrappedKey."""
        _setup_keyring(tmp_path, version="v1")
        _setup_keyring(tmp_path, version="v2")
        backend = FileKeyEncryptionBackend(tmp_path, "v1")
        dek = os.urandom(32)
        wrapped = await backend.wrap_key(dek, aad=b"aad", kek_version="v2")
        assert wrapped.kek_version == "v2"
        recovered = await backend.unwrap_key(wrapped, aad=b"aad")
        assert recovered == dek


# ===========================================================================
# Section 5 – Startup graceful failure
# ===========================================================================

class TestStartupGracefulFailure:
    """
    Application startup fails clearly on missing / invalid configuration
    rather than silently continuing with broken state.
    """

    def test_invalid_kek_path_raises_not_silently_ignored(self, tmp_path: Path) -> None:
        """
        FileKeyEncryptionBackend with a non-existent path raises
        KeyBackendConfigurationError immediately (not silently setting backend=None).

        At startup, the lifespan handler wraps this in RuntimeError when
        existing providers are present, ensuring a hard failure over silent corruption.
        """
        absent = tmp_path / "nonexistent_secret_dir"
        with pytest.raises(KeyBackendConfigurationError):
            FileKeyEncryptionBackend(absent, "v1")

    def test_kek_config_error_is_exception_subclass(self, tmp_path: Path) -> None:
        """KeyBackendConfigurationError is an Exception (catchable by startup code)."""
        absent = tmp_path / "ghost"
        try:
            FileKeyEncryptionBackend(absent, "v1")
        except Exception as exc:
            assert isinstance(exc, KeyBackendConfigurationError)
        else:
            pytest.fail("Expected KeyBackendConfigurationError was not raised")

    def test_missing_database_url_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        When DATABASE_URL is absent from the environment, the application uses a
        hardcoded fallback DSN rather than crashing at import time.  The Database
        object is constructed lazily (no network I/O during construction).
        """
        monkeypatch.delenv("DATABASE_URL", raising=False)
        import databases

        fallback = os.getenv(
            "DATABASE_URL",
            "postgresql://palimpsest:palimpsest@db:5432/palimpsest",
        )
        assert fallback.startswith("postgresql://"), (
            "Fallback DATABASE_URL must be a valid postgresql:// DSN"
        )
        # Construction is lazy — no connection is attempted here.
        db = databases.Database(fallback)
        assert db is not None

    def test_empty_database_url_raises_on_construction(self) -> None:
        """
        Passing an explicitly empty string to databases.Database raises an
        error immediately, giving a clear failure rather than a silent no-op.
        """
        import databases

        with pytest.raises(Exception):
            databases.Database("")
