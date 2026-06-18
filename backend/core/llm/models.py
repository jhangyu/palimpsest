from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


Effort = Literal["low", "medium", "high"]
ThinkingDisableMode = Literal["disabled", "minimized", "omitted"]
ThinkingMode = Literal[
    "openai_effort",
    "anthropic_adaptive",
    "anthropic_budget",
    "gemini_budget",
    "gemini_level",
]


class LLMProtocol(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class ErrorDisposition(StrEnum):
    FALLBACK = "fallback"
    STOP = "stop"
    CREDENTIAL_FALLBACK = "credential_fallback"
    VAULT_STOP = "vault_stop"


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_thinking: bool
    supports_effort: bool
    thinking_disable_mode: ThinkingDisableMode
    thinking_mode: ThinkingMode | None = None


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    model: str | None = None
    timeout_seconds: float = 30.0
    max_response_bytes: int = 1_048_576
    max_models: int = 500
    capabilities: ProviderCapabilities | None = None

    def __post_init__(self) -> None:
        from .endpoints import normalize_base_url

        object.__setattr__(self, "base_url", normalize_base_url(self.base_url))
        if self.model is not None:
            model = self.model.strip()
            object.__setattr__(self, "model", model or None)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        if self.max_models <= 0:
            raise ValueError("max_models must be positive")


@dataclass(frozen=True)
class LLMGenerationRequest:
    prompt: str
    model: str
    max_tokens: int
    temperature: float | None = None
    thinking: bool = False
    effort: Effort = "low"

    def __post_init__(self) -> None:
        if not self.prompt:
            raise ValueError("prompt is required")
        if not self.model.strip():
            raise ValueError("model is required")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if self.effort not in ("low", "medium", "high"):
            raise ValueError("effort must be low, medium, or high")


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str
    capabilities: ProviderCapabilities


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    finish_reason: str | None = None


@dataclass(frozen=True)
class ProviderHealth:
    ok: bool
    protocol: LLMProtocol
    model: str


class ProviderError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int | None = None,
        disposition: ErrorDisposition = ErrorDisposition.STOP,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.disposition = disposition

    @property
    def retryable(self) -> bool:
        return self.disposition == ErrorDisposition.FALLBACK

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
