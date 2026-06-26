"""
---
name: test_llm_model_discovery
description: "Tests for LLM provider model discovery, response validation, and error handling"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-model-discovery
spec_doc: null
test_file: tests/stage1/test_llm_model_discovery.py
functions:
  - name: test_gemini_discovery_filters_canonicalizes_deduplicates_and_sorts
    line: 82
    purpose: "Verifies Gemini list_models filters non-generative models, deduplicates, and sorts alphabetically"
    fixtures: []
  - name: test_model_discovery_respects_model_limit
    line: 124
    purpose: "Verifies OpenAI list_models truncates results to max_models from ProviderConfig"
    fixtures: []
  - name: test_unsupported_thinking_is_not_silently_ignored
    line: 144
    purpose: "Verifies ProviderError is raised if generate() is called with thinking=True on an unsupported provider"
    fixtures: []
  - name: test_response_size_cap_raises_typed_error
    line: 175
    purpose: "Verifies response_too_large ProviderError is raised when response exceeds max_response_bytes"
    fixtures: []
  - name: test_invalid_content_length_is_typed_fallback_error
    line: 197
    purpose: "Verifies invalid Content-Length header values result in a FALLBACK ProviderError"
    fixtures: [content_length]
  - name: test_timeout_raises_typed_sanitized_error
    line: 219
    purpose: "Verifies ReadTimeout results in a provider_timeout ProviderError with API key scrubbed from traceback"
    fixtures: []
  - name: test_credential_error_does_not_expose_provider_body_or_key
    line: 239
    purpose: "Verifies 401 response yields credential_error ProviderError without exposing the API key"
    fixtures: []
  - name: test_http_status_disposition_contract
    line: 268
    purpose: "Verifies BaseHTTPProvider maps HTTP status codes to correct ErrorDisposition values"
    fixtures: [status_code, expected]
  - name: test_invalid_json_and_shape_are_fallback_errors
    line: 279
    purpose: "Verifies invalid JSON and unexpected JSON shapes from provider both yield FALLBACK ProviderError"
    fixtures: []
  - name: test_network_policy_error_is_typed_stop
    line: 300
    purpose: "Verifies NetworkPolicyError is converted to a STOP ProviderError with API key scrubbed from traceback"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_model_discovery.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import httpx
import pytest
import traceback

from core.llm.gemini_provider import GeminiProvider
from core.llm.base import BaseHTTPProvider
from core.llm.models import (
    ErrorDisposition,
    LLMGenerationRequest,
    ProviderCapabilities,
    ProviderConfig,
    ProviderError,
)
from core.llm.openai_provider import OpenAIProvider
from core.llm.network_policy import NetworkPolicyError


@pytest.mark.asyncio
async def test_gemini_discovery_filters_canonicalizes_deduplicates_and_sorts() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/z-model",
                        "displayName": "Z",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/embedding-only",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                    {
                        "name": "models/a-model",
                        "displayName": "A",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/a-model",
                        "displayName": "Duplicate",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await GeminiProvider(client=client).list_models(
            ProviderConfig(base_url="https://api.example.com"),
            "secret",
        )

    assert [(model.id, model.display_name) for model in models] == [
        ("a-model", "A"),
        ("z-model", "Z"),
    ]


@pytest.mark.asyncio
async def test_model_discovery_respects_model_limit() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"id": f"model-{index}"} for index in range(4)]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await OpenAIProvider(client=client).list_models(
            ProviderConfig(
                base_url="https://api.example.com",
                max_models=2,
            ),
            "secret",
        )

    assert len(models) == 2


@pytest.mark.asyncio
async def test_unsupported_thinking_is_not_silently_ignored() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("request must not be sent")

    config = ProviderConfig(
        base_url="https://api.example.com",
        capabilities=ProviderCapabilities(
            supports_thinking=False,
            supports_effort=False,
            thinking_disable_mode="omitted",
        ),
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as exc_info:
            await OpenAIProvider(client=client).generate(
                LLMGenerationRequest(
                    prompt="prompt",
                    model="model",
                    max_tokens=8,
                    thinking=True,
                ),
                config,
                "secret",
            )

    assert exc_info.value.code == "unsupported_parameter"
    assert "secret" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_response_size_cap_raises_typed_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'{"data": [{"id": "model-with-a-long-name"}]}',
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as exc_info:
            await OpenAIProvider(client=client).list_models(
                ProviderConfig(
                    base_url="https://api.example.com",
                    max_response_bytes=16,
                ),
                "secret",
            )

    assert exc_info.value.code == "response_too_large"


@pytest.mark.asyncio
@pytest.mark.parametrize("content_length", ["not-a-number", "-1"])
async def test_invalid_content_length_is_typed_fallback_error(
    content_length: str,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-length": content_length},
            content=b'{"data": []}',
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as exc_info:
            await OpenAIProvider(client=client).list_models(
                ProviderConfig(base_url="https://api.example.com"),
                "secret",
            )

    assert exc_info.value.code == "provider_response_error"
    assert exc_info.value.disposition == ErrorDisposition.FALLBACK


@pytest.mark.asyncio
async def test_timeout_raises_typed_sanitized_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timeout with sk-secret", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as exc_info:
            await OpenAIProvider(client=client).list_models(
                ProviderConfig(base_url="https://api.example.com"),
                "sk-secret",
            )

    assert exc_info.value.code == "provider_timeout"
    assert exc_info.value.disposition == ErrorDisposition.FALLBACK
    assert "sk-secret" not in str(exc_info.value)
    assert "sk-secret" not in "".join(
        traceback.format_exception(exc_info.value)
    )


@pytest.mark.asyncio
async def test_credential_error_does_not_expose_provider_body_or_key() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"message": "invalid sk-secret"}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as exc_info:
            await OpenAIProvider(client=client).list_models(
                ProviderConfig(base_url="https://api.example.com"),
                "sk-secret",
            )

    assert exc_info.value.code == "credential_error"
    assert exc_info.value.disposition == ErrorDisposition.CREDENTIAL_FALLBACK
    assert "sk-secret" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, ErrorDisposition.STOP),
        (401, ErrorDisposition.CREDENTIAL_FALLBACK),
        (403, ErrorDisposition.CREDENTIAL_FALLBACK),
        (429, ErrorDisposition.FALLBACK),
        (500, ErrorDisposition.FALLBACK),
    ],
)
def test_http_status_disposition_contract(
    status_code: int,
    expected: ErrorDisposition,
) -> None:
    with pytest.raises(ProviderError) as exc_info:
        BaseHTTPProvider._raise_for_status(status_code, "generate")

    assert exc_info.value.disposition == expected


@pytest.mark.asyncio
async def test_invalid_json_and_shape_are_fallback_errors() -> None:
    responses = iter(
        [
            httpx.Response(200, content=b"not-json"),
            httpx.Response(200, json=[]),
        ]
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIProvider(client=client)
        config = ProviderConfig(base_url="https://api.example.com")
        for _ in range(2):
            with pytest.raises(ProviderError) as exc_info:
                await provider.list_models(config, "secret")
            assert exc_info.value.disposition == ErrorDisposition.FALLBACK


@pytest.mark.asyncio
async def test_network_policy_error_is_typed_stop() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise NetworkPolicyError("blocked URL with sk-secret")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as exc_info:
            await OpenAIProvider(client=client).list_models(
                ProviderConfig(base_url="https://api.example.com"),
                "sk-secret",
            )

    assert exc_info.value.code == "network_policy_error"
    assert exc_info.value.disposition == ErrorDisposition.STOP
    formatted = "".join(traceback.format_exception(exc_info.value))
    assert "sk-secret" not in formatted
