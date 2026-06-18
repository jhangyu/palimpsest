from __future__ import annotations

import re
from typing import Any

from .base import (
    BaseHTTPProvider,
    require_nonempty_text,
    require_model,
    require_thinking_support,
    response_shape_error,
    sorted_models,
)
from .endpoints import (
    ANTHROPIC_GENERATION_PATH,
    ANTHROPIC_MODELS_PATH,
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


UNKNOWN_CAPABILITIES = ProviderCapabilities(
    supports_thinking=False,
    supports_effort=False,
    thinking_disable_mode="omitted",
)
THINKING_BUDGETS = {"low": 1024, "medium": 4096, "high": 8192}
MODEL_SUFFIX_PATTERN = r"(?:-(?:latest|\d{8}))?"
ADAPTIVE_MODEL_PATTERN = re.compile(
    rf"^claude-(?:opus-4-(?:6|7|8)|sonnet-4-6|(?:fable|mythos)-5)"
    rf"{MODEL_SUFFIX_PATTERN}$"
)
BUDGET_MODEL_PATTERN = re.compile(
    rf"^(?:claude-3-7-sonnet|claude-(?:opus|sonnet)-4|claude-haiku-4-5)"
    rf"{MODEL_SUFFIX_PATTERN}$"
)


class AnthropicProvider(BaseHTTPProvider):
    protocol = LLMProtocol.ANTHROPIC
    anthropic_version = "2023-06-01"

    async def list_models(
        self, config: ProviderConfig, api_key: str
    ) -> list[ModelInfo]:
        data = await self._request_json(
            method="GET",
            url=join_api_path(config.base_url, ANTHROPIC_MODELS_PATH),
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
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
        }
        if request.temperature is not None and not request.thinking:
            payload["temperature"] = request.temperature
        if request.thinking:
            if capabilities.thinking_mode == "anthropic_adaptive":
                payload["thinking"] = {"type": "adaptive"}
                payload["output_config"] = {"effort": request.effort}
            else:
                budget = THINKING_BUDGETS[request.effort]
                if request.max_tokens <= budget:
                    raise ProviderError(
                        code="invalid_parameter",
                        message="Anthropic max_tokens must exceed the thinking budget.",
                    )
                payload["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": budget,
                }

        data = await self._request_json(
            method="POST",
            url=join_api_path(config.base_url, ANTHROPIC_GENERATION_PATH),
            headers=self._headers(api_key),
            config=config,
            operation="generate",
            payload=payload,
        )
        content = data.get("content")
        if not isinstance(content, list):
            raise response_shape_error()
        parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        text = require_nonempty_text(
            "".join(part for part in parts if isinstance(part, str)).strip()
        )
        return LLMResponse(
            text=text,
            model=request.model,
            finish_reason=_optional_string(data.get("stop_reason")),
        )

    async def test_connection(
        self, config: ProviderConfig, api_key: str
    ) -> ProviderHealth:
        model = require_model(config)
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

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "x-api-key": api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
        }


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


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
                thinking_mode=(
                    "anthropic_adaptive"
                    if config.capabilities.supports_effort
                    else "anthropic_budget"
                ),
            )
        return config.capabilities
    normalized = model.lower()
    if ADAPTIVE_MODEL_PATTERN.fullmatch(normalized):
        return ProviderCapabilities(
            supports_thinking=True,
            supports_effort=True,
            thinking_disable_mode="omitted",
            thinking_mode="anthropic_adaptive",
        )
    if BUDGET_MODEL_PATTERN.fullmatch(normalized):
        return ProviderCapabilities(
            supports_thinking=True,
            supports_effort=False,
            thinking_disable_mode="omitted",
            thinking_mode="anthropic_budget",
        )
    return UNKNOWN_CAPABILITIES
