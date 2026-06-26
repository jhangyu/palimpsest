"""
---
name: ai_providers
description: "AI provider CRUD: create/read/update/delete configs with DEK-encrypted API keys, optimistic-concurrency reorder, toggle, health test, model discovery"
type: core
target:
  layer: backend
  domain: ai-provider
spec_doc: null
test_file: tests/stage1/test_ai_provider_api.py
functions:
  - name: list_user_providers
    line: 221
    purpose: "Return all providers for a user ordered by (priority, id), masked metadata only"
  - name: create_provider
    line: 234
    purpose: "Insert new AI provider record with DEK-encrypted API key via vault"
  - name: update_provider
    line: 320
    purpose: "Patch provider fields with revision-based optimistic concurrency; re-encrypt key if AAD changes"
  - name: delete_provider
    line: 451
    purpose: "Delete provider with ownership and revision check"
  - name: reorder_providers
    line: 478
    purpose: "Atomic priority reorder: validate all IDs match user set, no duplicates, bump revisions"
  - name: discover_models
    line: 534
    purpose: "Discover available models from a provider endpoint using stored or supplied API key"
  - name: test_provider_connection
    line: 586
    purpose: "Test live connection using stored credentials and update health metadata"
  - name: reveal_api_key
    line: 647
    purpose: "Decrypt and return full API key; caller is responsible for rate-limit and audit"
  - name: toggle_provider_enabled
    line: 670
    purpose: "Enable or disable a provider and return updated masked record"
  - name: get_runtime_status
    line: 694
    purpose: "Return enabled provider chain plus environment fallback status"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import sqlalchemy
from sqlalchemy.exc import IntegrityError

from .ai_provider_migrations import AIProviderTables, bootstrap_user_secret_key
from .llm.service import build_environment_fallback
from .llm.base import LLMProvider as LLMProviderProtocol
from .llm.key_backends import KeyEncryptionBackend, WrappedKey
from .llm.models import ProviderConfig, ProviderError
from .llm.registry import create_provider as create_llm_adapter
from .llm.vault import (
    CredentialAuthenticationError,
    CredentialEnvelope,
    UserKeyEnvelope,
    decrypt_provider_credential,
    encrypt_provider_credential,
    unwrap_user_dek,
)


VALID_PROTOCOLS = ("openai", "anthropic", "gemini")
VALID_EFFORTS = ("low", "medium", "high")


# ---------------------------------------------------------------------------
# Token display helpers (crypto.py no longer exports these after #24 removal)
# ---------------------------------------------------------------------------

def get_token_last4(token: str) -> str | None:
    """Return last 4 characters of an API token for display."""
    return token[-4:] if token and len(token) >= 4 else None


def mask_token(token: str) -> str | None:
    """Return masked API token showing only last 4 characters."""
    if not token or len(token) < 4:
        return None
    return "*" * min(len(token) - 4, 8) + token[-4:]


# ---------------------------------------------------------------------------
# Custom errors
# ---------------------------------------------------------------------------


class ProviderNotFoundError(Exception):
    """Raised when a provider row does not exist."""


class ProviderRevisionConflictError(Exception):
    """Raised on optimistic-concurrency mismatch."""


class ProviderLabelConflictError(Exception):
    """Raised when UNIQUE(user_id, label) is violated."""


class ProviderOwnershipError(Exception):
    """Raised on cross-user access attempt."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SENTINEL = object()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_key_envelope(row) -> UserKeyEnvelope:
    """Build a ``UserKeyEnvelope`` from a ``user_secret_keys`` DB row."""
    return UserKeyEnvelope(
        user_id=row["user_id"],
        wrapped_key=WrappedKey(
            ciphertext=row["encrypted_dek"],
            nonce=row["dek_nonce"],
            algorithm=row["algorithm"],
            kek_version=row["kek_version"],
        ),
    )


def _credential_envelope(row) -> CredentialEnvelope:
    """Build a ``CredentialEnvelope`` from a ``user_ai_providers`` DB row."""
    return CredentialEnvelope(
        ciphertext=row["encrypted_api_key"],
        nonce=row["credential_nonce"],
        algorithm="AES-256-GCM",
        credential_version=row["credential_version"],
    )


async def _get_user_dek(db, tables: AIProviderTables, backend: KeyEncryptionBackend, *, user_id: int) -> bytes:
    """Fetch and unwrap the user's DEK, bootstrapping if needed."""
    key_row = (await db.execute(
        sqlalchemy.select(tables.user_secret_keys).where(
            tables.user_secret_keys.c.user_id == user_id
        )
    )).mappings().first()
    if key_row is None:
        await bootstrap_user_secret_key(db, tables.user_secret_keys, backend, user_id=user_id)
        key_row = (await db.execute(
            sqlalchemy.select(tables.user_secret_keys).where(
                tables.user_secret_keys.c.user_id == user_id
            )
        )).mappings().first()
    if key_row is None:
        raise ProviderNotFoundError("user secret key could not be initialized")
    try:
        return await unwrap_user_dek(backend, _user_key_envelope(key_row))
    except CredentialAuthenticationError:
        # KEK was regenerated — check if user has any encrypted providers
        provider_count = (await db.execute(
            sqlalchemy.select(sqlalchemy.func.count()).select_from(tables.user_ai_providers).where(
                tables.user_ai_providers.c.user_id == user_id
            )
        )).scalar()
        if provider_count and provider_count > 0:
            raise  # Re-raise — encrypted providers would be lost
        # No providers — safe to re-bootstrap with current KEK
        await db.execute(
            tables.user_secret_keys.delete().where(
                tables.user_secret_keys.c.user_id == user_id
            )
        )
        await db.commit()
        await bootstrap_user_secret_key(db, tables.user_secret_keys, backend, user_id=user_id)
        key_row = (await db.execute(
            sqlalchemy.select(tables.user_secret_keys).where(
                tables.user_secret_keys.c.user_id == user_id
            )
        )).mappings().first()
        if key_row is None:
            raise ProviderNotFoundError("user secret key could not be re-initialized")
        return await unwrap_user_dek(backend, _user_key_envelope(key_row))


async def _fetch_provider(db, tables: AIProviderTables, *, provider_id: int) -> Any:
    """Fetch a single provider row or raise ``ProviderNotFoundError``."""
    row = (await db.execute(
        sqlalchemy.select(tables.user_ai_providers).where(
            tables.user_ai_providers.c.id == provider_id
        )
    )).mappings().first()
    if row is None:
        raise ProviderNotFoundError("provider not found")
    return row


def _check_ownership(row, *, user_id: int) -> None:
    if row["user_id"] != user_id:
        raise ProviderOwnershipError("access denied")


def _check_revision(row, *, revision: int) -> None:
    if row["revision"] != revision:
        raise ProviderRevisionConflictError(
            f"expected revision {revision}, found {row['revision']}"
        )


def _mask_provider(row) -> dict:
    """Return a provider dict with masked key fields, no encrypted data."""
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "label": row["label"],
        "protocol": row["protocol"],
        "base_url": row["base_url"],
        "model": row["model"],
        "temperature": row["temperature"],
        "max_tokens": row["max_tokens"],
        "thinking": row["thinking"],
        "effort": row["effort"],
        "api_key_last4": row["api_key_last4"],
        "api_key_mask": row["api_key_mask"],
        "priority": row["priority"],
        "enabled": row["enabled"],
        "health_status": row["health_status"],
        "last_tested_at": row["last_tested_at"],
        "last_success_at": row["last_success_at"],
        "last_failure_at": row["last_failure_at"],
        "last_failure_code": row["last_failure_code"],
        "revision": row["revision"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def _next_priority(db, tables: AIProviderTables, *, user_id: int) -> int:
    """Return the next available priority value for the user."""
    result = (await db.execute(
        sqlalchemy.select(
            sqlalchemy.func.coalesce(
                sqlalchemy.func.max(tables.user_ai_providers.c.priority), -1
            )
            + 1
        ).where(tables.user_ai_providers.c.user_id == user_id)
    )).scalar()
    return int(result)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def list_user_providers(db, tables: AIProviderTables, *, user_id: int) -> dict:
    """List user's providers ordered by (priority, id). Masked metadata only."""
    rows = (await db.execute(
        sqlalchemy.select(tables.user_ai_providers)
        .where(tables.user_ai_providers.c.user_id == user_id)
        .order_by(
            tables.user_ai_providers.c.priority.asc(),
            tables.user_ai_providers.c.id.asc(),
        )
    )).mappings().all()
    return {"providers": [_mask_provider(r) for r in rows]}


async def create_provider(
    db,
    tables: AIProviderTables,
    backend: KeyEncryptionBackend,
    *,
    user_id: int,
    label: str,
    protocol: str,
    base_url: str,
    model: str,
    api_key: str,
    temperature: float | None = None,
    max_tokens: int = 4096,
    thinking: bool = False,
    effort: str = "low",
) -> dict:
    """Create a new provider profile. Encrypt API key via vault."""
    if protocol not in VALID_PROTOCOLS:
        raise ValueError(f"invalid protocol: {protocol}")
    if effort not in VALID_EFFORTS:
        raise ValueError(f"invalid effort: {effort}")

    dek = await _get_user_dek(db, tables, backend, user_id=user_id)
    priority = await _next_priority(db, tables, user_id=user_id)
    now = _now()

    # We need a provider_id before encryption (it's part of AAD).
    # Use the sequence to allocate one.
    provider_id = int(
        (await db.execute(
            sqlalchemy.select(
                sqlalchemy.Sequence("user_ai_providers_id_seq").next_value()
            )
        )).scalar()
    )

    credential = encrypt_provider_credential(
        api_key,
        dek=dek,
        user_id=user_id,
        provider_id=provider_id,
        protocol=protocol,
        base_url=base_url,
    )
    values = {
        "id": provider_id,
        "user_id": user_id,
        "label": label,
        "protocol": protocol,
        "base_url": base_url,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "thinking": thinking,
        "effort": effort,
        "encrypted_api_key": credential.ciphertext,
        "credential_nonce": credential.nonce,
        "credential_version": credential.credential_version,
        "api_key_last4": get_token_last4(api_key),
        "api_key_mask": mask_token(api_key),
        "priority": priority,
        "enabled": True,
        "health_status": "unknown",
        "last_tested_at": None,
        "last_success_at": None,
        "last_failure_at": None,
        "last_failure_code": None,
        "revision": 1,
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db.execute(tables.user_ai_providers.insert().values(**values))
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "uq_user_ai_providers_user_label" in str(exc).lower():
            raise ProviderLabelConflictError(
                f"label '{label}' already exists"
            ) from None
        raise

    row = await _fetch_provider(db, tables, provider_id=provider_id)
    return _mask_provider(row)


async def update_provider(
    db,
    tables: AIProviderTables,
    backend: KeyEncryptionBackend,
    *,
    user_id: int,
    provider_id: int,
    revision: int,
    label: str | None = None,
    protocol: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = _SENTINEL,  # type: ignore[assignment]
    temperature: float | None = _SENTINEL,  # type: ignore[assignment]
    max_tokens: int | None = None,
    thinking: bool | None = None,
    effort: str | None = None,
) -> dict:
    """Update provider with revision-based optimistic concurrency."""
    row = await _fetch_provider(db, tables, provider_id=provider_id)
    _check_ownership(row, user_id=user_id)
    _check_revision(row, revision=revision)

    updates: dict[str, Any] = {}
    now = _now()

    if label is not None:
        updates["label"] = label
    if model is not None:
        updates["model"] = model
    if max_tokens is not None:
        updates["max_tokens"] = max_tokens
    if thinking is not None:
        updates["thinking"] = thinking
    if effort is not None:
        updates["effort"] = effort
    if temperature is not _SENTINEL:
        updates["temperature"] = temperature

    # Determine effective protocol/base_url (after update)
    new_protocol = protocol if protocol is not None else row["protocol"]
    new_base_url = base_url if base_url is not None else row["base_url"]
    aad_changed = (new_protocol != row["protocol"]) or (new_base_url != row["base_url"])

    if protocol is not None:
        updates["protocol"] = protocol
    if base_url is not None:
        updates["base_url"] = base_url

    # Handle API key: only re-encrypt if a non-empty key is provided
    # or if AAD-relevant fields changed
    has_new_key = api_key is not _SENTINEL and api_key not in (None, "")

    if has_new_key:
        dek = await _get_user_dek(db, tables, backend, user_id=user_id)
        credential = encrypt_provider_credential(
            api_key,  # type: ignore[arg-type]
            dek=dek,
            user_id=user_id,
            provider_id=provider_id,
            protocol=new_protocol,
            base_url=new_base_url,
        )
        updates["encrypted_api_key"] = credential.ciphertext
        updates["credential_nonce"] = credential.nonce
        updates["credential_version"] = credential.credential_version
        updates["api_key_last4"] = get_token_last4(api_key)  # type: ignore[arg-type]
        updates["api_key_mask"] = mask_token(api_key)  # type: ignore[arg-type]
    elif aad_changed:
        # Re-encrypt existing key with new AAD
        dek = await _get_user_dek(db, tables, backend, user_id=user_id)
        old_envelope = _credential_envelope(row)
        plaintext_key = decrypt_provider_credential(
            old_envelope,
            dek=dek,
            user_id=user_id,
            provider_id=provider_id,
            protocol=row["protocol"],
            base_url=row["base_url"],
        )
        credential = encrypt_provider_credential(
            plaintext_key,
            dek=dek,
            user_id=user_id,
            provider_id=provider_id,
            protocol=new_protocol,
            base_url=new_base_url,
        )
        updates["encrypted_api_key"] = credential.ciphertext
        updates["credential_nonce"] = credential.nonce
        updates["credential_version"] = credential.credential_version

    if "protocol" in updates and updates["protocol"] not in VALID_PROTOCOLS:
        raise ValueError(f"invalid protocol: {updates['protocol']}")
    if "effort" in updates and updates["effort"] not in VALID_EFFORTS:
        raise ValueError(f"invalid effort: {updates['effort']}")

    if not updates:
        return _mask_provider(row)

    updates["updated_at"] = now
    updates["revision"] = row["revision"] + 1

    try:
        result = await db.execute(
            tables.user_ai_providers.update()
            .where(
                (tables.user_ai_providers.c.id == provider_id)
                & (tables.user_ai_providers.c.revision == revision)
            )
            .values(**updates)
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "uq_user_ai_providers_user_label" in str(exc).lower():
            raise ProviderLabelConflictError(
                f"label '{label}' already exists"
            ) from None
        raise

    if result.rowcount == 0:
        raise ProviderRevisionConflictError(
            f"provider {provider_id} was concurrently modified"
            f" (expected revision {revision})"
        )

    updated = await _fetch_provider(db, tables, provider_id=provider_id)
    return _mask_provider(updated)


async def delete_provider(
    db,
    tables: AIProviderTables,
    *,
    user_id: int,
    provider_id: int,
    revision: int,
) -> None:
    """Delete provider with ownership and revision check."""
    row = await _fetch_provider(db, tables, provider_id=provider_id)
    _check_ownership(row, user_id=user_id)
    _check_revision(row, revision=revision)

    result = await db.execute(
        tables.user_ai_providers.delete().where(
            (tables.user_ai_providers.c.id == provider_id)
            & (tables.user_ai_providers.c.revision == revision)
        )
    )
    await db.commit()
    if result.rowcount == 0:
        raise ProviderRevisionConflictError(
            f"provider {provider_id} was concurrently modified"
            f" (expected revision {revision})"
        )


async def reorder_providers(
    db,
    tables: AIProviderTables,
    *,
    user_id: int,
    ordered_ids: list[int],
    revision: int,
) -> dict:
    """Atomic reorder: validate all IDs belong to user, no duplicates, no missing."""
    # Validate no duplicates
    if len(ordered_ids) != len(set(ordered_ids)):
        raise ValueError("duplicate provider IDs in reorder list")

    # Fetch all user providers
    rows = (await db.execute(
        sqlalchemy.select(tables.user_ai_providers).where(
            tables.user_ai_providers.c.user_id == user_id
        )
    )).mappings().all()
    existing_ids = {r["id"] for r in rows}

    # Check no missing and no extra
    ordered_set = set(ordered_ids)
    if ordered_set != existing_ids:
        missing = existing_ids - ordered_set
        extra = ordered_set - existing_ids
        parts = []
        if missing:
            parts.append(f"missing IDs: {sorted(missing)}")
        if extra:
            parts.append(f"unknown IDs: {sorted(extra)}")
        raise ValueError(f"reorder list mismatch: {'; '.join(parts)}")

    # Verify revision on all rows
    for r in rows:
        if r["revision"] != revision:
            raise ProviderRevisionConflictError(
                f"provider {r['id']} revision mismatch: "
                f"expected {revision}, found {r['revision']}"
            )

    now = _now()
    for priority, pid in enumerate(ordered_ids):
        row = next(r for r in rows if r["id"] == pid)
        await db.execute(
            tables.user_ai_providers.update()
            .where(
                (tables.user_ai_providers.c.id == pid)
                & (tables.user_ai_providers.c.user_id == user_id)
            )
            .values(priority=priority, updated_at=now, revision=row["revision"] + 1)
        )

    return await list_user_providers(db, tables, user_id=user_id)


async def discover_models(
    db,
    tables: AIProviderTables,
    backend: KeyEncryptionBackend,
    *,
    user_id: int,
    protocol: str,
    base_url: str,
    api_key: str | None = None,
    provider_id: int | None = None,
) -> dict:
    """Discover models from a provider endpoint."""
    if provider_id is not None:
        row = await _fetch_provider(db, tables, provider_id=provider_id)
        _check_ownership(row, user_id=user_id)
        dek = await _get_user_dek(db, tables, backend, user_id=user_id)
        api_key = decrypt_provider_credential(
            _credential_envelope(row),
            dek=dek,
            user_id=user_id,
            provider_id=provider_id,
            protocol=row["protocol"],
            base_url=row["base_url"],
        )
    if not api_key:
        raise ValueError("api_key is required when provider_id is not given")

    adapter: LLMProviderProtocol = create_llm_adapter(protocol)
    config = ProviderConfig(base_url=base_url)

    warning: str | None = None
    try:
        models = await adapter.list_models(config, api_key)
    except ProviderError as exc:
        if exc.code == "model_discovery_unavailable":
            return {
                "models": [],
                "manual_entry_allowed": True,
                "warning": exc.message,
            }
        raise

    return {
        "models": [
            {"id": m.id, "display_name": m.display_name}
            for m in models
        ],
        "manual_entry_allowed": True,
        "warning": warning,
    }


async def test_provider_connection(
    db,
    tables: AIProviderTables,
    backend: KeyEncryptionBackend,
    *,
    user_id: int,
    provider_id: int,
) -> dict:
    """Test connection using stored credentials. Update health metadata."""
    row = await _fetch_provider(db, tables, provider_id=provider_id)
    _check_ownership(row, user_id=user_id)

    dek = await _get_user_dek(db, tables, backend, user_id=user_id)
    api_key = decrypt_provider_credential(
        _credential_envelope(row),
        dek=dek,
        user_id=user_id,
        provider_id=provider_id,
        protocol=row["protocol"],
        base_url=row["base_url"],
    )

    adapter: LLMProviderProtocol = create_llm_adapter(row["protocol"])
    config = ProviderConfig(base_url=row["base_url"], model=row["model"])

    now = _now()
    health_updates: dict[str, Any] = {"last_tested_at": now}

    try:
        health = await adapter.test_connection(config, api_key)
        health_updates["health_status"] = "ok" if health.ok else "error"
        if health.ok:
            health_updates["last_success_at"] = now
            health_updates["last_failure_code"] = None
        else:
            health_updates["last_failure_at"] = now
            health_updates["last_failure_code"] = "test_failed"
    except ProviderError as exc:
        health_updates["health_status"] = "error"
        health_updates["last_failure_at"] = now
        health_updates["last_failure_code"] = exc.code

    # Compare-by-timestamp: only update if new timestamp > existing
    existing_tested = row["last_tested_at"]
    if existing_tested is None or now >= existing_tested:
        health_updates["updated_at"] = now
        await db.execute(
            tables.user_ai_providers.update()
            .where(tables.user_ai_providers.c.id == provider_id)
            .values(**health_updates)
        )
        await db.commit()

    return {
        "provider_id": provider_id,
        "health_status": health_updates["health_status"],
        "last_tested_at": now.isoformat(),
        "last_failure_code": health_updates.get("last_failure_code"),
    }


async def reveal_api_key(
    db,
    tables: AIProviderTables,
    backend: KeyEncryptionBackend,
    *,
    user_id: int,
    provider_id: int,
) -> str:
    """Decrypt and return the full API key. Caller handles rate limit/audit."""
    row = await _fetch_provider(db, tables, provider_id=provider_id)
    _check_ownership(row, user_id=user_id)

    dek = await _get_user_dek(db, tables, backend, user_id=user_id)
    return decrypt_provider_credential(
        _credential_envelope(row),
        dek=dek,
        user_id=user_id,
        provider_id=provider_id,
        protocol=row["protocol"],
        base_url=row["base_url"],
    )


async def toggle_provider_enabled(
    db,
    tables: AIProviderTables,
    *,
    user_id: int,
    provider_id: int,
    enabled: bool,
) -> dict:
    """Enable/disable provider. Return updated provider (masked)."""
    row = await _fetch_provider(db, tables, provider_id=provider_id)
    _check_ownership(row, user_id=user_id)

    now = _now()
    await db.execute(
        tables.user_ai_providers.update()
        .where(tables.user_ai_providers.c.id == provider_id)
        .values(enabled=enabled, updated_at=now)
    )
    await db.commit()

    updated = await _fetch_provider(db, tables, provider_id=provider_id)
    return _mask_provider(updated)


async def get_runtime_status(
    db,
    tables: AIProviderTables,
    backend: KeyEncryptionBackend | None = None,
    *,
    user_id: int,
) -> dict:
    """Return runtime status: enabled profiles chain + environment fallback."""
    rows = (await db.execute(
        sqlalchemy.select(tables.user_ai_providers)
        .where(
            (tables.user_ai_providers.c.user_id == user_id)
            & (tables.user_ai_providers.c.enabled == True)  # noqa: E712
        )
        .order_by(
            tables.user_ai_providers.c.priority.asc(),
            tables.user_ai_providers.c.id.asc(),
        )
    )).mappings().all()

    chain = [
        {
            "id": r["id"],
            "label": r["label"],
            "protocol": r["protocol"],
            "model": r["model"],
            "health_status": r["health_status"],
        }
        for r in rows
    ]

    env_profile = build_environment_fallback()
    environment_fallback = None
    if env_profile is not None:
        environment_fallback = {
            "enabled": True,
            "protocol": str(env_profile.protocol),
            "model": env_profile.model,
            "label": env_profile.label,
        }

    return {
        "profiles_enabled": len(chain) > 0,
        "chain": chain,
        "environment_fallback": environment_fallback,
    }
