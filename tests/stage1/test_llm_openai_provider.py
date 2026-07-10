"""
---
name: test_llm_openai_provider
description: "Unit tests for the OpenAI-compatible LLM provider adapter covering model listing, generation, reasoning effort, error handling, and connection testing"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-openai
spec_doc: null
test_file: tests/stage1/test_llm_openai_provider.py
functions:
  - name: test_openai_list_models_and_auth_header
    line: 37
    purpose: "Verifies model listing is sorted, Bearer auth header is set, and API key is not leaked in URL"
    fixtures: []
  - name: test_openai_generate_maps_thinking_and_response
    line: 57
    purpose: "Verifies reasoning_effort mapping, max_completion_tokens usage, temperature omission for o-series, and response text extraction"
    fixtures: []
  - name: test_openai_test_connection_uses_minimal_generation
    line: 101
    purpose: "Verifies test_connection sends max_tokens=32 without reasoning_effort and returns ok=True"
    fixtures: []
  - name: test_openai_unknown_model_omits_reasoning_fields
    line: 126
    purpose: "Verifies vendor/unknown models use max_tokens instead of max_completion_tokens and omit reasoning_effort"
    fixtures: []
  - name: test_openai_model_family_requires_explicit_boundary
    line: 156
    purpose: "Verifies models only partially matching known families (gpt-5, o3) do not receive reasoning field injection"
    fixtures: []
  - name: test_openai_malformed_model_list_is_typed_fallback_error
    line: 183
    purpose: "Verifies malformed model list response raises ProviderError with provider_response_error code and fallback disposition"
    fixtures: []
  - name: test_openai_empty_text_is_fallback_error
    line: 199
    purpose: "Verifies whitespace-only response text raises ProviderError with provider_empty_response code and fallback disposition"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_openai_provider.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import httpx
import pytest

from core.llm.models import LLMGenerationRequest, ProviderConfig, ProviderError
from core.llm.openai_provider import OpenAIProvider


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_openai_list_models_and_auth_header() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        assert request.headers["authorization"] == "Bearer sk-secret"
        assert "sk-secret" not in str(request.url)
        return httpx.Response(
            200,
            json={"data": [{"id": "z-model"}, {"id": "a-model"}]},
        )

    async with _client(handler) as client:
        models = await OpenAIProvider(client=client).list_models(
            ProviderConfig(base_url="https://api.example.com/v1"),
            "sk-secret",
        )

    assert [model.id for model in models] == ["a-model", "z-model"]


@pytest.mark.asyncio
async def test_openai_generate_maps_thinking_and_response() -> None:
    bodies: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(__import__("json").loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "normalized text"}}]},
        )

    async with _client(handler) as client:
        provider = OpenAIProvider(client=client)
        response = await provider.generate(
            LLMGenerationRequest(
                prompt="prompt",
                model="o3-mini",
                temperature=0.2,
                max_tokens=32,
            ),
            ProviderConfig(base_url="https://api.example.com"),
            "sk-secret",
        )
        await provider.generate(
            LLMGenerationRequest(
                prompt="prompt",
                model="o3-mini",
                max_tokens=32,
                thinking=True,
                effort="high",
            ),
            ProviderConfig(base_url="https://api.example.com"),
            "sk-secret",
        )

    assert response.text == "normalized text"
    assert bodies[0]["reasoning_effort"] == "low"
    assert "temperature" not in bodies[0]
    assert bodies[0]["max_completion_tokens"] == 32
    assert "max_tokens" not in bodies[0]
    assert bodies[1]["reasoning_effort"] == "high"
    assert "sk-secret" not in str(bodies)


@pytest.mark.asyncio
async def test_openai_test_connection_uses_minimal_generation() -> None:
    body: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body.update(__import__("json").loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}}]},
        )

    async with _client(handler) as client:
        health = await OpenAIProvider(client=client).test_connection(
            ProviderConfig(
                base_url="https://api.example.com",
                model="test-model",
            ),
            "sk-secret",
        )

    assert health.ok is True
    assert body["max_tokens"] == 32
    assert "reasoning_effort" not in body


@pytest.mark.asyncio
async def test_openai_unknown_model_omits_reasoning_fields() -> None:
    body: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body.update(__import__("json").loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}}]},
        )

    async with _client(handler) as client:
        await OpenAIProvider(client=client).generate(
            LLMGenerationRequest(
                prompt="prompt",
                model="vendor-custom-model",
                max_tokens=8,
            ),
            ProviderConfig(base_url="https://api.example.com"),
            "secret",
        )

    assert "reasoning_effort" not in body
    assert body["max_tokens"] == 8


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model",
    ["gpt-5evil", "gpt-5-evil", "o3evil", "o3-evil", "gpt-5/evil"],
)
async def test_openai_model_family_requires_explicit_boundary(model: str) -> None:
    body: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body.update(__import__("json").loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}}]},
        )

    async with _client(handler) as client:
        await OpenAIProvider(client=client).generate(
            LLMGenerationRequest(
                prompt="prompt",
                model=model,
                max_tokens=8,
            ),
            ProviderConfig(base_url="https://api.example.com"),
            "secret",
        )

    assert "reasoning_effort" not in body
    assert body["max_tokens"] == 8
    assert "max_completion_tokens" not in body


@pytest.mark.asyncio
async def test_openai_malformed_model_list_is_typed_fallback_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": "invalid"})

    async with _client(handler) as client:
        with pytest.raises(ProviderError) as exc_info:
            await OpenAIProvider(client=client).list_models(
                ProviderConfig(base_url="https://api.example.com"),
                "secret",
            )

    assert exc_info.value.code == "provider_response_error"
    assert exc_info.value.disposition == "fallback"


@pytest.mark.asyncio
async def test_openai_empty_text_is_fallback_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "  "}}]},
        )

    async with _client(handler) as client:
        with pytest.raises(ProviderError) as exc_info:
            await OpenAIProvider(client=client).generate(
                LLMGenerationRequest(
                    prompt="prompt",
                    model="custom-model",
                    max_tokens=8,
                ),
                ProviderConfig(base_url="https://api.example.com"),
                "secret",
            )

    assert exc_info.value.code == "provider_empty_response"
    assert exc_info.value.disposition == "fallback"
