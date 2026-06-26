"""
---
name: llm_service
description: "LLM service layer: resolve per-user provider chain from DB + env fallback, execute generation with deadline-aware provider fallback"
type: core
target:
  layer: backend
  domain: llm
spec_doc: null
test_file: tests/stage1/test_llm_baseline_contract.py
functions:
  - name: resolve_chain
    line: 98
    purpose: "Build ordered list of RuntimeProfiles: decrypt user providers, append environment fallback if configured"
  - name: build_environment_fallback
    line: 213
    purpose: "Construct synthetic RuntimeProfile from LLM_FALLBACK_* env vars or legacy MINIMAX_API_KEY"
  - name: execute_with_fallback
    line: 286
    purpose: "Iterate provider chain; stop on STOP disposition, skip on FALLBACK; raise NoProviderAvailableError if all fail"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import time
from typing import TYPE_CHECKING, cast

import sqlalchemy

from .models import (
    Effort,
    ErrorDisposition,
    LLMGenerationRequest,
    LLMProtocol,
    LLMResponse,
    ProviderConfig,
    ProviderError,
)
from .registry import create_provider
from .vault import (
    CredentialAuthenticationError,
    CredentialEnvelope,
    UserKeyEnvelope,
    VaultError,
    decrypt_provider_credential,
    unwrap_user_dek,
)

if TYPE_CHECKING:
    from ..ai_provider_migrations import AIProviderTables
    from .key_backends import KeyEncryptionBackend

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RuntimeProfile:
    """A resolved, ready-to-use provider profile."""

    provider_id: int | None  # None for environment fallback
    label: str
    protocol: LLMProtocol
    base_url: str
    model: str
    temperature: float | None
    max_tokens: int
    thinking: bool
    effort: str
    api_key: str  # plaintext, only lives in memory
    is_environment_fallback: bool = False


@dataclass(frozen=True)
class FallbackAttempt:
    """Record of one provider attempt."""

    provider_id: int | None
    label: str
    protocol: str
    model: str
    duration_seconds: float
    success: bool
    error_code: str | None = None
    error_disposition: str | None = None


@dataclass(frozen=True)
class LLMServiceResult:
    """Result of execute_with_fallback."""

    response: LLMResponse
    provider_id: int | None
    label: str
    protocol: str
    model: str
    attempts: list[FallbackAttempt]


class NoProviderAvailableError(Exception):
    """No provider in the chain could fulfill the request."""

    def __init__(self, attempts: list[FallbackAttempt]) -> None:
        self.attempts = attempts
        super().__init__("no provider available")


# ---------------------------------------------------------------------------
# Chain resolution
# ---------------------------------------------------------------------------

async def resolve_chain(
    db,
    tables: AIProviderTables,
    backend: KeyEncryptionBackend,
    *,
    user_id: int,
) -> list[RuntimeProfile]:
    """Build ordered chain of runtime profiles for a user.

    1. Query user's enabled providers ordered by (priority, id).
    2. Decrypt each API key via vault; skip on vault/KEK failure.
    3. Append synthetic environment fallback profile if configured.
    """
    profiles: list[RuntimeProfile] = []

    # Fetch user providers
    t = tables.user_ai_providers
    rows = (await db.execute(
        sqlalchemy.select(t)
        .where(
            (t.c.user_id == user_id) & (t.c.enabled == True)  # noqa: E712
        )
        .order_by(t.c.priority.asc(), t.c.id.asc())
    )).mappings().all()

    if rows:
        # Attempt to unwrap user DEK once
        dek: bytes | None = None
        try:
            key_row = (await db.execute(
                sqlalchemy.select(tables.user_secret_keys).where(
                    tables.user_secret_keys.c.user_id == user_id
                )
            )).mappings().first()
            if key_row is not None:
                from .key_backends import WrappedKey

                envelope = UserKeyEnvelope(
                    user_id=user_id,
                    wrapped_key=WrappedKey(
                        ciphertext=key_row["encrypted_dek"],
                        nonce=key_row["dek_nonce"],
                        algorithm=key_row["algorithm"],
                        kek_version=key_row["kek_version"],
                    ),
                )
                dek = await unwrap_user_dek(backend, envelope)
            else:
                logger.warning(
                    "no secret key for user_id=%d; skipping user providers",
                    user_id,
                )
        except VaultError as exc:
            logger.warning(
                "vault unwrap failed for user_id=%d: %s; skipping user providers",
                user_id,
                exc,
            )
        except Exception:
            logger.exception(
                "unexpected error during DEK unwrap for user_id=%d; skipping user providers",
                user_id,
            )

        if dek is not None:
            for row in rows:
                try:
                    cred_envelope = CredentialEnvelope(
                        ciphertext=row["encrypted_api_key"],
                        nonce=row["credential_nonce"],
                        algorithm="AES-256-GCM",
                        credential_version=row["credential_version"],
                    )
                    api_key = decrypt_provider_credential(
                        cred_envelope,
                        dek=dek,
                        user_id=user_id,
                        provider_id=row["id"],
                        protocol=row["protocol"],
                        base_url=row["base_url"],
                    )
                    profiles.append(
                        RuntimeProfile(
                            provider_id=row["id"],
                            label=row["label"],
                            protocol=LLMProtocol(row["protocol"]),
                            base_url=row["base_url"],
                            model=row["model"],
                            temperature=row["temperature"],
                            max_tokens=row["max_tokens"],
                            thinking=row["thinking"],
                            effort=row["effort"],
                            api_key=api_key,
                        )
                    )
                except (VaultError, CredentialAuthenticationError) as exc:
                    logger.warning(
                        "credential decrypt failed for provider_id=%d user_id=%d: %s",
                        row["id"],
                        user_id,
                        exc,
                    )

    # Append environment fallback
    env_profile = build_environment_fallback()
    if env_profile is not None:
        profiles.append(env_profile)

    return profiles


# ---------------------------------------------------------------------------
# Environment fallback
# ---------------------------------------------------------------------------

def build_environment_fallback() -> RuntimeProfile | None:
    """Build synthetic profile from LLM_FALLBACK_* environment variables.

    Returns None if disabled or required variables are missing.
    Falls back to legacy MINIMAX_API_KEY as lowest-priority option.
    """
    enabled = os.environ.get("LLM_FALLBACK_ENABLED", "true").lower()
    if enabled not in ("true", "1", "yes"):
        return None

    protocol_str = os.environ.get("LLM_FALLBACK_PROTOCOL", "openai")
    base_url = os.environ.get("LLM_FALLBACK_BASE_URL", "")
    api_key = os.environ.get("LLM_FALLBACK_API_KEY", "")
    model = os.environ.get("LLM_FALLBACK_MODEL", "")

    # If primary env vars are complete, use them
    if base_url and api_key and model:
        temperature_str = os.environ.get("LLM_FALLBACK_TEMPERATURE")
        try:
            temperature = float(temperature_str) if temperature_str else None
            max_tokens = int(os.environ.get("LLM_FALLBACK_MAX_TOKENS", "4096"))
        except (ValueError, TypeError):
            return None
        thinking = os.environ.get("LLM_FALLBACK_THINKING", "false").lower() in (
            "true",
            "1",
            "yes",
        )
        effort = os.environ.get("LLM_FALLBACK_EFFORT", "low")

        try:
            protocol = LLMProtocol(protocol_str)
        except ValueError:
            return None

        return RuntimeProfile(
            provider_id=None,
            label="environment-fallback",
            protocol=protocol,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking=thinking,
            effort=effort,
            api_key=api_key,
            is_environment_fallback=True,
        )

    # Legacy MINIMAX_API_KEY fallback
    minimax_key = os.environ.get("MINIMAX_API_KEY", "")
    if minimax_key:
        return RuntimeProfile(
            provider_id=None,
            label="minimax-legacy-fallback",
            protocol=LLMProtocol.OPENAI,
            base_url="https://api.minimax.io/v1",
            model="MiniMax-M3",
            temperature=None,
            max_tokens=4096,
            thinking=False,
            effort="low",
            api_key=minimax_key,
            is_environment_fallback=True,
        )

    return None


# ---------------------------------------------------------------------------
# Fallback execution
# ---------------------------------------------------------------------------

async def execute_with_fallback(
    chain: list[RuntimeProfile],
    request: LLMGenerationRequest,
    *,
    total_deadline_seconds: float = 180.0,
) -> LLMServiceResult:
    """Iterate chain, attempting each provider at most once.

    Fallback rules based on ``ProviderError.disposition``:
    - FALLBACK: try next provider
    - CREDENTIAL_FALLBACK: mark credential error, try next
    - STOP / VAULT_STOP: stop chain immediately

    A shared deadline (default 180 s) is enforced across all attempts.
    Raises ``NoProviderAvailableError`` when every provider fails.
    """
    if not chain:
        raise NoProviderAvailableError([])

    attempts: list[FallbackAttempt] = []
    deadline = time.monotonic() + total_deadline_seconds

    for profile in chain:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            attempts.append(
                FallbackAttempt(
                    provider_id=profile.provider_id,
                    label=profile.label,
                    protocol=str(profile.protocol),
                    model=profile.model,
                    duration_seconds=0.0,
                    success=False,
                    error_code="deadline_exceeded",
                    error_disposition=ErrorDisposition.STOP,
                )
            )
            break

        # Build per-attempt request with profile overrides
        attempt_request = LLMGenerationRequest(
            prompt=request.prompt,
            model=profile.model,
            max_tokens=profile.max_tokens,
            temperature=profile.temperature if profile.temperature is not None else request.temperature,
            thinking=profile.thinking,
            effort=cast(Effort, profile.effort),
        )

        attempt_timeout = min(remaining, 30.0)  # default provider timeout
        config = ProviderConfig(
            base_url=profile.base_url,
            model=profile.model,
            timeout_seconds=attempt_timeout,
        )

        t0 = time.monotonic()
        try:
            adapter = create_provider(profile.protocol)
            response = await adapter.generate(attempt_request, config, profile.api_key)

            duration = time.monotonic() - t0
            attempts.append(
                FallbackAttempt(
                    provider_id=profile.provider_id,
                    label=profile.label,
                    protocol=str(profile.protocol),
                    model=profile.model,
                    duration_seconds=duration,
                    success=True,
                )
            )
            return LLMServiceResult(
                response=response,
                provider_id=profile.provider_id,
                label=profile.label,
                protocol=str(profile.protocol),
                model=profile.model,
                attempts=attempts,
            )

        except ProviderError as exc:
            duration = time.monotonic() - t0
            attempts.append(
                FallbackAttempt(
                    provider_id=profile.provider_id,
                    label=profile.label,
                    protocol=str(profile.protocol),
                    model=profile.model,
                    duration_seconds=duration,
                    success=False,
                    error_code=exc.code,
                    error_disposition=str(exc.disposition),
                )
            )
            logger.warning(
                "provider attempt failed: provider_id=%s label=%s protocol=%s "
                "code=%s disposition=%s duration=%.3fs",
                profile.provider_id,
                profile.label,
                profile.protocol,
                exc.code,
                exc.disposition,
                duration,
            )

            if exc.disposition in (ErrorDisposition.STOP, ErrorDisposition.VAULT_STOP):
                break
            # FALLBACK and CREDENTIAL_FALLBACK: continue to next
            continue

        except Exception as exc:
            duration = time.monotonic() - t0
            attempts.append(
                FallbackAttempt(
                    provider_id=profile.provider_id,
                    label=profile.label,
                    protocol=str(profile.protocol),
                    model=profile.model,
                    duration_seconds=duration,
                    success=False,
                    error_code="unexpected_error",
                    error_disposition=ErrorDisposition.FALLBACK,
                )
            )
            logger.exception(
                "unexpected error from provider_id=%s label=%s",
                profile.provider_id,
                profile.label,
            )
            continue

    raise NoProviderAvailableError(attempts)
