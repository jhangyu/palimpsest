"""
---
name: test_llm_gemini_provider
description: "Unit tests for the Gemini LLM provider adapter covering generation, thinking budget/level, model listing, error handling, and connection testing"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-gemini
spec_doc: null
test_file: tests/stage1/test_llm_gemini_provider.py
functions:
  - name: test_gemini_generate_uses_bare_model_and_header_key
    line: 35
    purpose: "Verifies bare model name in URL path, x-goog-api-key header, response text concatenation, and thinkingBudget mapping per effort level"
    fixtures: []
  - name: test_gemini_test_connection_is_minimal_and_thinking_off
    line: 85
    purpose: "Verifies test_connection sends maxOutputTokens=32 without thinkingConfig and returns ok=True"
    fixtures: []
  - name: test_gemini_3_uses_thinking_level_and_unknown_omits_thinking
    line: 111
    purpose: "Verifies gemini-3 models use thinkingLevel field with effort, and unknown models omit thinkingConfig entirely"
    fixtures: []
  - name: test_gemini_model_family_requires_explicit_boundary
    line: 162
    purpose: "Verifies models only partially matching known families do not receive thinkingConfig injection (boundary matching)"
    fixtures: []
  - name: test_gemini_malformed_model_list_is_typed_fallback_error
    line: 187
    purpose: "Verifies malformed model list response raises ProviderError with provider_response_error code and fallback disposition"
    fixtures: []
  - name: test_gemini_empty_text_is_fallback_error
    line: 203
    purpose: "Verifies empty parts list in response raises ProviderError with provider_empty_response code and fallback disposition"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_gemini_provider.py -v"
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

from core.llm.gemini_provider import GeminiProvider
from core.llm.models import LLMGenerationRequest, ProviderConfig, ProviderError


@pytest.mark.asyncio
async def test_gemini_generate_uses_bare_model_and_header_key() -> None:
    bodies: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1beta/models/gemini-2.5-flash:generateContent"
        assert request.headers["x-goog-api-key"] == "gemini-secret"
        assert request.url.query == b""
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "one"}, {"text": " two"}]}}
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiProvider(client=client)
        response = await provider.generate(
            LLMGenerationRequest(
                prompt="prompt",
                model="models/gemini-2.5-flash",
                max_tokens=64,
            ),
            ProviderConfig(
                base_url="https://generativelanguage.googleapis.com/v1beta"
            ),
            "gemini-secret",
        )
        await provider.generate(
            LLMGenerationRequest(
                prompt="prompt",
                model="gemini-2.5-flash",
                max_tokens=64,
                thinking=True,
                effort="medium",
            ),
            ProviderConfig(
                base_url="https://generativelanguage.googleapis.com"
            ),
            "gemini-secret",
        )

    assert response.text == "one two"
    assert bodies[0]["generationConfig"]["thinkingConfig"]["thinkingBudget"] == 0
    assert bodies[1]["generationConfig"]["thinkingConfig"]["thinkingBudget"] == 4096


@pytest.mark.asyncio
async def test_gemini_test_connection_is_minimal_and_thinking_off() -> None:
    body: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "OK"}]}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        health = await GeminiProvider(client=client).test_connection(
            ProviderConfig(
                base_url="https://api.example.com",
                model="models/vendor-custom",
            ),
            "gemini-secret",
        )

    assert health.ok is True
    config = body["generationConfig"]
    assert config["maxOutputTokens"] == 32
    assert "thinkingConfig" not in config


@pytest.mark.asyncio
async def test_gemini_3_uses_thinking_level_and_unknown_omits_thinking() -> None:
    bodies: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "OK"}]}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiProvider(client=client)
        config = ProviderConfig(base_url="https://api.example.com")
        await provider.generate(
            LLMGenerationRequest(
                prompt="prompt",
                model="vendor-custom",
                max_tokens=8,
            ),
            config,
            "secret",
        )
        await provider.generate(
            LLMGenerationRequest(
                prompt="prompt",
                model="gemini-3-flash",
                max_tokens=8,
                thinking=True,
                effort="high",
            ),
            config,
            "secret",
        )

    assert "thinkingConfig" not in bodies[0]["generationConfig"]
    assert bodies[1]["generationConfig"]["thinkingConfig"] == {
        "thinkingLevel": "high"
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model",
    [
        "gemini-3evil",
        "gemini-3-evil",
        "gemini-3-flash-evil",
        "gemini-2.5-evil",
        "gemini-2.5-flash-evil",
    ],
)
async def test_gemini_model_family_requires_explicit_boundary(model: str) -> None:
    body: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "OK"}]}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await GeminiProvider(client=client).generate(
            LLMGenerationRequest(
                prompt="prompt",
                model=model,
                max_tokens=8,
            ),
            ProviderConfig(base_url="https://api.example.com"),
            "secret",
        )

    assert "thinkingConfig" not in body["generationConfig"]


@pytest.mark.asyncio
async def test_gemini_malformed_model_list_is_typed_fallback_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": "invalid"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as exc_info:
            await GeminiProvider(client=client).list_models(
                ProviderConfig(base_url="https://api.example.com"),
                "secret",
            )

    assert exc_info.value.code == "provider_response_error"
    assert exc_info.value.disposition == "fallback"


@pytest.mark.asyncio
async def test_gemini_empty_text_is_fallback_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": []}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as exc_info:
            await GeminiProvider(client=client).generate(
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
