"""
---
name: llm_base
description: "Shared LLM HTTP provider base: LLMProvider protocol, BaseHTTPProvider with client caching, error normalization, response-size enforcement"
type: core
target:
  layer: backend
  domain: llm
spec_doc: null
test_file: null
functions:
  - name: LLMProvider
    line: 48
    purpose: "Structural Protocol defining list_models, generate, and test_connection interface"
  - name: BaseHTTPProvider
    line: 65
    purpose: "Abstract base for HTTP-backed providers: manages client lifecycle, enforces size limits, maps HTTP errors to ProviderError"
  - name: sorted_models
    line: 278
    purpose: "Deduplicate and sort model list up to max_models limit"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import json
from typing import Any, AsyncIterator, Callable, Protocol

import httpx

from .models import (
    ErrorDisposition,
    LLMGenerationRequest,
    LLMResponse,
    ModelInfo,
    ProviderCapabilities,
    ProviderConfig,
    ProviderError,
    ProviderHealth,
)
from .network_policy import NetworkPolicyError


# ---------------------------------------------------------------------------
# Shared constants and helpers used by all provider implementations
# ---------------------------------------------------------------------------

UNKNOWN_CAPABILITIES = ProviderCapabilities(
    supports_thinking=False,
    supports_effort=False,
    thinking_disable_mode="omitted",
)

THINKING_BUDGETS: dict[str, int] = {"low": 1024, "medium": 4096, "high": 8192}

# Connection tests must leave room for reasoning/thinking models that spend
# internal tokens before emitting visible text. max_tokens=1 commonly yields
# an HTTP 200 with empty content and surfaces as provider_empty_response.
CONNECTION_TEST_PROMPT = "Respond with OK."
CONNECTION_TEST_MAX_TOKENS = 32


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


# ---------------------------------------------------------------------------

ClientFactory = Callable[[ProviderConfig], httpx.AsyncClient]

# Module-level cache for httpx.AsyncClient instances to avoid TLS handshake
# overhead on every request. Clients are keyed by base_url and timeout_seconds.
_client_cache: dict[str, httpx.AsyncClient] = {}


class LLMProvider(Protocol):
    async def list_models(
        self, config: ProviderConfig, api_key: str
    ) -> list[ModelInfo]: ...

    async def generate(
        self,
        request: LLMGenerationRequest,
        config: ProviderConfig,
        api_key: str,
    ) -> LLMResponse: ...

    async def test_connection(
        self, config: ProviderConfig, api_key: str
    ) -> ProviderHealth: ...


class BaseHTTPProvider:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        if client is not None and client_factory is not None:
            raise ValueError("provide either client or client_factory, not both")
        if client is None and client_factory is None:
            raise ValueError("a secure client factory or explicit test client is required")
        self._client = client
        self._client_factory = client_factory

    @asynccontextmanager
    async def _get_client(
        self, config: ProviderConfig
    ) -> AsyncIterator[httpx.AsyncClient]:
        # Testing escape hatch: if client is pre-injected, use it directly
        if self._client is not None:
            yield self._client
            return

        if self._client_factory is None:
            raise RuntimeError("client factory is not configured")

        # Generate cache key from config properties
        cache_key = f"{config.base_url}:{config.timeout_seconds}"

        # Check if client already exists in cache
        if cache_key not in _client_cache:
            _client_cache[cache_key] = self._client_factory(config)

        # Yield cached client without closing it to allow reuse
        yield _client_cache[cache_key]

    async def _request_json(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        config: ProviderConfig,
        operation: str,
        payload: dict | None = None,
    ) -> dict:
        try:
            async with self._get_client(config) as client:
                async with client.stream(
                    method,
                    url,
                    headers=headers,
                    json=payload,
                    timeout=httpx.Timeout(config.timeout_seconds),
                    follow_redirects=False,
                ) as response:
                    self._raise_for_status(response.status_code, operation)
                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            declared_size = int(content_length)
                        except ValueError:
                            raise _invalid_content_length() from None
                        if declared_size < 0:
                            raise _invalid_content_length()
                        if declared_size > config.max_response_bytes:
                            raise _response_too_large()

                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > config.max_response_bytes:
                            raise _response_too_large()
                        chunks.append(chunk)
        except ProviderError:
            raise
        except NetworkPolicyError:
            raise ProviderError(
                code="network_policy_error",
                message="Provider destination is blocked by network policy.",
                disposition=ErrorDisposition.STOP,
            ) from None
        except httpx.TimeoutException:
            raise ProviderError(
                code="provider_timeout",
                message="Provider request timed out.",
                disposition=ErrorDisposition.FALLBACK,
            ) from None
        except httpx.RequestError:
            raise ProviderError(
                code="provider_connection_error",
                message="Could not connect to the provider.",
                disposition=ErrorDisposition.FALLBACK,
            ) from None

        try:
            data = json.loads(b"".join(chunks))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ProviderError(
                code="provider_response_error",
                message="Provider returned an invalid JSON response.",
                disposition=ErrorDisposition.FALLBACK,
            ) from None
        if not isinstance(data, dict):
            raise ProviderError(
                code="provider_response_error",
                message="Provider returned an unexpected response shape.",
                disposition=ErrorDisposition.FALLBACK,
            )
        return data

    @staticmethod
    def _raise_for_status(status_code: int, operation: str) -> None:
        if status_code < 400:
            return
        if status_code in (401, 403):
            raise ProviderError(
                code="credential_error",
                message="Provider rejected the API credential.",
                status_code=status_code,
                disposition=ErrorDisposition.CREDENTIAL_FALLBACK,
            )
        if status_code == 404 and operation == "list_models":
            raise ProviderError(
                code="model_discovery_unavailable",
                message="Provider does not expose a compatible models endpoint.",
                status_code=status_code,
            )
        if status_code == 429:
            raise ProviderError(
                code="provider_rate_limited",
                message="Provider rate limit exceeded.",
                status_code=status_code,
                disposition=ErrorDisposition.FALLBACK,
            )
        if status_code >= 500:
            raise ProviderError(
                code="provider_unavailable",
                message="Provider is temporarily unavailable.",
                status_code=status_code,
                disposition=ErrorDisposition.FALLBACK,
            )
        raise ProviderError(
            code="provider_request_error",
            message="Provider rejected the request.",
            status_code=status_code,
        )


def _response_too_large() -> ProviderError:
    return ProviderError(
        code="response_too_large",
        message="Provider response exceeded the configured size limit.",
        disposition=ErrorDisposition.FALLBACK,
    )


def _invalid_content_length() -> ProviderError:
    return ProviderError(
        code="provider_response_error",
        message="Provider returned an invalid Content-Length header.",
        disposition=ErrorDisposition.FALLBACK,
    )


def require_model(config: ProviderConfig) -> str:
    if not config.model:
        raise ProviderError(
            code="invalid_configuration",
            message="A model is required to test the provider connection.",
        )
    return config.model


def require_thinking_support(
    request: LLMGenerationRequest,
    capabilities,
) -> None:
    if request.thinking and not capabilities.supports_thinking:
        raise ProviderError(
            code="unsupported_parameter",
            message="The selected provider/model does not support thinking.",
        )
    if (
        request.thinking
        and request.effort != "low"
        and not capabilities.supports_effort
    ):
        raise ProviderError(
            code="unsupported_parameter",
            message="The selected provider/model does not support thinking effort.",
        )


def response_shape_error() -> ProviderError:
    return ProviderError(
        code="provider_response_error",
        message="Provider returned an unexpected response shape.",
        disposition=ErrorDisposition.FALLBACK,
    )


def require_nonempty_text(text: str) -> str:
    if not text:
        raise ProviderError(
            code="provider_empty_response",
            message="Provider returned an empty text response.",
            disposition=ErrorDisposition.FALLBACK,
        )
    return text


def sorted_models(
    models: list[ModelInfo], max_models: int
) -> list[ModelInfo]:
    deduplicated: dict[str, ModelInfo] = {}
    for model in models:
        if model.id and model.id not in deduplicated:
            deduplicated[model.id] = model
    return sorted(deduplicated.values(), key=lambda item: item.id)[:max_models]
