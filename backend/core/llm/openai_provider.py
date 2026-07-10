"""
---
name: llm_openai_provider
description: "OpenAI-compatible LLM provider: chat completions, model listing, reasoning model capability detection (o-series, gpt-5)"
type: core
target:
  layer: backend
  domain: llm
spec_doc: null
test_file: tests/stage1/test_llm_openai_provider.py
functions:
  - name: OpenAIProvider.list_models
    line: 44
    purpose: "Fetch model list from /v1/models and map to ModelInfo with capability detection"
  - name: OpenAIProvider.generate
    line: 72
    purpose: "POST to /v1/chat/completions; select max_completion_tokens vs max_tokens based on reasoning model detection"
  - name: OpenAIProvider.test_connection
    line: 121
    purpose: "Send minimal generation request to verify credentials and connectivity"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
from __future__ import annotations

import re
from typing import Any

from .base import (
    BaseHTTPProvider,
    CONNECTION_TEST_MAX_TOKENS,
    CONNECTION_TEST_PROMPT,
    UNKNOWN_CAPABILITIES,
    _optional_string,
    require_nonempty_text,
    require_model,
    require_thinking_support,
    response_shape_error,
    sorted_models,
)
from .endpoints import (
    OPENAI_GENERATION_PATH,
    OPENAI_MODELS_PATH,
    join_api_path,
)
from .models import (
    LLMGenerationRequest,
    LLMProtocol,
    LLMResponse,
    ModelInfo,
    ProviderCapabilities,
    ProviderConfig,
    ProviderError,
    ProviderHealth,
)


REASONING_MODEL_PATTERN = re.compile(
    r"^(?:"
    r"o(?:1|3|4)(?:-(?:mini|pro|preview|latest|\d{4}-\d{2}-\d{2}))?"
    r"|gpt-5(?:\.\d+)?(?:-(?:mini|nano|pro|chat|codex|preview|latest|\d{4}-\d{2}-\d{2}))?"
    r")$"
)


class OpenAIProvider(BaseHTTPProvider):
    protocol = LLMProtocol.OPENAI

    async def list_models(
        self, config: ProviderConfig, api_key: str
    ) -> list[ModelInfo]:
        data = await self._request_json(
            method="GET",
            url=join_api_path(config.base_url, OPENAI_MODELS_PATH),
            headers=self._headers(api_key),
            config=config,
            operation="list_models",
        )
        items = data.get("data")
        if not isinstance(items, list):
            raise response_shape_error()
        models = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            model_id = item["id"].strip()
            if model_id:
                models.append(
                    ModelInfo(
                        id=model_id,
                        display_name=str(item.get("display_name") or model_id),
                        capabilities=_capabilities_for_model(model_id, config),
                    )
                )
        return sorted_models(models, config.max_models)

    async def generate(
        self,
        request: LLMGenerationRequest,
        config: ProviderConfig,
        api_key: str,
    ) -> LLMResponse:
        capabilities = _capabilities_for_model(request.model, config)
        require_thinking_support(request, capabilities)
        if request.thinking and not capabilities.supports_effort:
            raise ProviderError(
                code="unsupported_parameter",
                message="OpenAI-compatible thinking requires reasoning effort support.",
            )
        reasoning_model = capabilities.thinking_mode == "openai_effort"
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        payload[
            "max_completion_tokens" if reasoning_model else "max_tokens"
        ] = request.max_tokens
        if request.temperature is not None and not reasoning_model:
            payload["temperature"] = request.temperature
        if reasoning_model:
            payload["reasoning_effort"] = request.effort if request.thinking else "low"

        data = await self._request_json(
            method="POST",
            url=join_api_path(config.base_url, OPENAI_GENERATION_PATH),
            headers=self._headers(api_key),
            config=config,
            operation="generate",
            payload=payload,
        )
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise response_shape_error()
        choice = choices[0]
        if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
            raise response_shape_error()
        text = require_nonempty_text(_openai_message_text(choice["message"]))
        return LLMResponse(
            text=text,
            model=request.model,
            finish_reason=_optional_string(choice.get("finish_reason")),
        )

    async def test_connection(
        self, config: ProviderConfig, api_key: str
    ) -> ProviderHealth:
        model = require_model(config)
        await self.generate(
            LLMGenerationRequest(
                prompt=CONNECTION_TEST_PROMPT,
                model=model,
                max_tokens=CONNECTION_TEST_MAX_TOKENS,
            ),
            config,
            api_key,
        )
        return ProviderHealth(ok=True, protocol=self.protocol, model=model)

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }


def _openai_content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type in (None, "text", "output_text"):
                text = part.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
            elif isinstance(part.get("content"), str) and part["content"]:
                parts.append(part["content"])
        return "".join(parts).strip()
    raise response_shape_error()


def _openai_message_text(message: dict[str, Any]) -> str:
    """Extract visible text from OpenAI-compatible chat message payloads.

    Some gateways/models return null/empty ``content`` while still providing
    usable text via ``output_text``, ``refusal``, or content part arrays.
    """
    for key in ("content", "output_text", "refusal", "text"):
        if key not in message:
            continue
        try:
            text = _openai_content_text(message.get(key))
        except ProviderError:
            continue
        if text:
            return text
    return ""


def _capabilities_for_model(
    model: str,
    config: ProviderConfig,
) -> ProviderCapabilities:
    if config.capabilities is not None:
        if (
            config.capabilities.supports_thinking
            and config.capabilities.thinking_mode is None
        ):
            return ProviderCapabilities(
                supports_thinking=True,
                supports_effort=config.capabilities.supports_effort,
                thinking_disable_mode=config.capabilities.thinking_disable_mode,
                thinking_mode="openai_effort",
            )
        return config.capabilities
    normalized = model.lower()
    if REASONING_MODEL_PATTERN.fullmatch(normalized):
        return ProviderCapabilities(
            supports_thinking=True,
            supports_effort=True,
            thinking_disable_mode="minimized",
            thinking_mode="openai_effort",
        )
    return UNKNOWN_CAPABILITIES
