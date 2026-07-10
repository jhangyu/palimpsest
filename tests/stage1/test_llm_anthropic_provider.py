"""
---
name: test_llm_anthropic_provider
description: "Unit tests for the Anthropic LLM provider adapter covering generation, thinking modes, model listing, error handling, and connection testing"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-anthropic
spec_doc: null
test_file: tests/stage1/test_llm_anthropic_provider.py
functions:
  - name: test_anthropic_models_generation_and_headers
    line: 35
    purpose: "Verifies model listing is sorted, generation concatenates text parts, auth header is set, and thinking budget applies for explicit thinking requests"
    fixtures: []
  - name: test_anthropic_adaptive_thinking_and_unknown_omission
    line: 86
    purpose: "Verifies adaptive thinking mode is used for claude-sonnet-4-6 with effort param, and unknown models omit thinking/output_config fields"
    fixtures: []
  - name: test_anthropic_model_family_requires_explicit_boundary
    line: 137
    purpose: "Verifies models with names only partially matching known families do not receive thinking injection (boundary matching)"
    fixtures: []
  - name: test_anthropic_empty_text_is_fallback_error
    line: 163
    purpose: "Verifies empty content response raises ProviderError with provider_empty_response code and fallback disposition"
    fixtures: []
  - name: test_anthropic_malformed_model_list_is_typed_fallback_error
    line: 184
    purpose: "Verifies malformed model list response raises ProviderError with provider_response_error code and fallback disposition"
    fixtures: []
  - name: test_anthropic_test_connection_uses_required_max_tokens
    line: 200
    purpose: "Verifies test_connection sends max_tokens=32 without thinking fields and returns ok=True"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_anthropic_provider.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import json

import httpx
import pytest

from core.llm.anthropic_provider import AnthropicProvider
from core.llm.models import LLMGenerationRequest, ProviderConfig, ProviderError


@pytest.mark.asyncio
async def test_anthropic_models_generation_and_headers() -> None:
    bodies: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "anthropic-secret"
        assert request.headers["anthropic-version"]
        assert "anthropic-secret" not in str(request.url)
        if request.method == "GET":
            assert request.url.path == "/anthropic/v1/models"
            return httpx.Response(
                200,
                json={"data": [{"id": "claude-z"}, {"id": "claude-a"}]},
            )
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "first"}, {"type": "text", "text": " second"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = AnthropicProvider(client=client)
        config = ProviderConfig(base_url="https://api.example.com/anthropic/v1")
        models = await provider.list_models(config, "anthropic-secret")
        response = await provider.generate(
            LLMGenerationRequest(
                prompt="prompt",
                model="claude-3-7-sonnet-latest",
                max_tokens=2048,
            ),
            config,
            "anthropic-secret",
        )
        await provider.generate(
            LLMGenerationRequest(
                prompt="prompt",
                model="claude-3-7-sonnet-latest",
                max_tokens=4096,
                thinking=True,
                effort="low",
            ),
            config,
            "anthropic-secret",
        )

    assert [model.id for model in models] == ["claude-a", "claude-z"]
    assert response.text == "first second"
    assert "thinking" not in bodies[0]
    assert bodies[1]["thinking"] == {"type": "enabled", "budget_tokens": 1024}


@pytest.mark.asyncio
async def test_anthropic_adaptive_thinking_and_unknown_omission() -> None:
    bodies: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "OK"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = AnthropicProvider(client=client)
        config = ProviderConfig(base_url="https://api.example.com")
        await provider.generate(
            LLMGenerationRequest(
                prompt="prompt",
                model="vendor-claude-compatible",
                max_tokens=8,
            ),
            config,
            "secret",
        )
        await provider.generate(
            LLMGenerationRequest(
                prompt="prompt",
                model="claude-sonnet-4-6",
                max_tokens=2048,
                temperature=0.2,
                thinking=True,
                effort="low",
            ),
            config,
            "secret",
        )

    assert "thinking" not in bodies[0]
    assert "output_config" not in bodies[0]
    assert bodies[1]["thinking"] == {"type": "adaptive"}
    assert bodies[1]["output_config"] == {"effort": "low"}
    assert "temperature" not in bodies[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model",
    [
        "claude-opus-4evil",
        "claude-opus-4-evil",
        "claude-sonnet-4-6evil",
    ],
)
async def test_anthropic_model_family_requires_explicit_boundary(model: str) -> None:
    body: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "OK"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await AnthropicProvider(client=client).generate(
            LLMGenerationRequest(
                prompt="prompt",
                model=model,
                max_tokens=8,
            ),
            ProviderConfig(base_url="https://api.example.com"),
            "secret",
        )

    assert "thinking" not in body
    assert "output_config" not in body


@pytest.mark.asyncio
async def test_anthropic_empty_text_is_fallback_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as exc_info:
            await AnthropicProvider(client=client).generate(
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


@pytest.mark.asyncio
async def test_anthropic_malformed_model_list_is_typed_fallback_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": "invalid"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as exc_info:
            await AnthropicProvider(client=client).list_models(
                ProviderConfig(base_url="https://api.example.com"),
                "secret",
            )

    assert exc_info.value.code == "provider_response_error"
    assert exc_info.value.disposition == "fallback"


@pytest.mark.asyncio
async def test_anthropic_test_connection_uses_required_max_tokens() -> None:
    body: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "OK"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        health = await AnthropicProvider(client=client).test_connection(
            ProviderConfig(
                base_url="https://api.example.com",
                model="claude-a",
            ),
            "anthropic-secret",
        )

    assert health.ok is True
    assert body["max_tokens"] == 32
    assert "thinking" not in body
