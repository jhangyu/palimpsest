"""
---
name: llm_gemini_provider
description: "Google Gemini LLM provider: generateContent API, budget and level thinking modes, model listing with supportedGenerationMethods filter"
type: core
target:
  layer: backend
  domain: llm
spec_doc: null
test_file: tests/stage1/test_llm_gemini_provider.py
functions:
  - name: GeminiProvider.list_models
    line: 45
    purpose: "Fetch model list from /v1beta/models, filter by generateContent support, map to ModelInfo"
  - name: GeminiProvider.generate
    line: 80
    purpose: "POST to generateContent endpoint; configure thinkingConfig for budget or level mode"
  - name: GeminiProvider.test_connection
    line: 141
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
    THINKING_BUDGETS,
    UNKNOWN_CAPABILITIES,
    _optional_string,
    require_nonempty_text,
    require_model,
    require_thinking_support,
    response_shape_error,
    sorted_models,
)
from .endpoints import (
    GEMINI_MODELS_PATH,
    canonicalize_gemini_model,
    gemini_generation_path,
    join_api_path,
)
from .models import (
    LLMGenerationRequest,
    LLMProtocol,
    LLMResponse,
    ModelInfo,
    ProviderCapabilities,
    ProviderConfig,
    ProviderHealth,
)


GEMINI_25_MODEL_PATTERN = re.compile(
    r"^gemini-2\.5-(?:pro|flash(?:-lite)?)(?:-(?:preview|latest|\d{2}-\d{4}))?$"
)
GEMINI_3_MODEL_PATTERN = re.compile(
    r"^gemini-3(?:\.\d+)?-(?:pro|flash)(?:-(?:preview|latest|\d{2}-\d{4}))?$"
)


class GeminiProvider(BaseHTTPProvider):
    protocol = LLMProtocol.GEMINI

    async def list_models(
        self, config: ProviderConfig, api_key: str
    ) -> list[ModelInfo]:
        data = await self._request_json(
            method="GET",
            url=join_api_path(config.base_url, GEMINI_MODELS_PATH),
            headers=self._headers(api_key),
            config=config,
            operation="list_models",
        )
        items = data.get("models")
        if not isinstance(items, list):
            raise response_shape_error()
        models = []
        for item in items:
            if not isinstance(item, dict):
                continue
            methods = item.get("supportedGenerationMethods")
            name = item.get("name")
            if (
                not isinstance(methods, list)
                or "generateContent" not in methods
                or not isinstance(name, str)
            ):
                continue
            model_id = canonicalize_gemini_model(name)
            models.append(
                ModelInfo(
                    id=model_id,
                    display_name=str(item.get("displayName") or model_id),
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
        model = canonicalize_gemini_model(request.model)
        generation_config: dict[str, Any] = {
            "maxOutputTokens": request.max_tokens,
        }
        if capabilities.thinking_mode == "gemini_budget":
            generation_config["thinkingConfig"] = {
                "thinkingBudget": (
                    THINKING_BUDGETS[request.effort]
                    if request.thinking
                    else _gemini_disabled_budget(model)
                )
            }
        elif capabilities.thinking_mode == "gemini_level":
            generation_config["thinkingConfig"] = {
                "thinkingLevel": request.effort if request.thinking else "minimal"
            }
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        payload = {
            "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
            "generationConfig": generation_config,
        }
        data = await self._request_json(
            method="POST",
            url=join_api_path(config.base_url, gemini_generation_path(model)),
            headers=self._headers(api_key),
            config=config,
            operation="generate",
            payload=payload,
        )
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise response_shape_error()
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise response_shape_error()
        content = candidate.get("content")
        if not isinstance(content, dict) or not isinstance(content.get("parts"), list):
            raise response_shape_error()
        parts = [
            part.get("text", "")
            for part in content["parts"]
            if isinstance(part, dict)
        ]
        text = require_nonempty_text(
            "".join(part for part in parts if isinstance(part, str)).strip()
        )
        return LLMResponse(
            text=text,
            model=model,
            finish_reason=_optional_string(candidate.get("finishReason")),
        )

    async def test_connection(
        self, config: ProviderConfig, api_key: str
    ) -> ProviderHealth:
        model = canonicalize_gemini_model(require_model(config))
        await self.generate(
            LLMGenerationRequest(
                prompt="Respond with OK.",
                model=model,
                max_tokens=1,
            ),
            config,
            api_key,
        )
        return ProviderHealth(ok=True, protocol=self.protocol, model=model)

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }


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
                thinking_mode="gemini_budget",
            )
        return config.capabilities
    normalized = canonicalize_gemini_model(model).lower()
    if GEMINI_25_MODEL_PATTERN.fullmatch(normalized):
        return ProviderCapabilities(
            supports_thinking=True,
            supports_effort=True,
            thinking_disable_mode=(
                "minimized" if normalized.startswith("gemini-2.5-pro") else "disabled"
            ),
            thinking_mode="gemini_budget",
        )
    if GEMINI_3_MODEL_PATTERN.fullmatch(normalized):
        return ProviderCapabilities(
            supports_thinking=True,
            supports_effort=True,
            thinking_disable_mode="minimized",
            thinking_mode="gemini_level",
        )
    return UNKNOWN_CAPABILITIES


def _gemini_disabled_budget(model: str) -> int:
    return 128 if model.lower().startswith("gemini-2.5-pro") else 0
