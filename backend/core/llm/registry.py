from __future__ import annotations

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider
from .gemini_provider import GeminiProvider
from .models import LLMProtocol
from .network_transport import create_secure_client_factory
from .openai_provider import OpenAIProvider


PROVIDER_TYPES = {
    LLMProtocol.OPENAI: OpenAIProvider,
    LLMProtocol.ANTHROPIC: AnthropicProvider,
    LLMProtocol.GEMINI: GeminiProvider,
}


def create_provider(protocol: LLMProtocol | str, **kwargs) -> LLMProvider:
    try:
        normalized = LLMProtocol(protocol)
    except ValueError as exc:
        raise ValueError(f"unsupported LLM protocol: {protocol}") from exc
    if "client" not in kwargs and "client_factory" not in kwargs:
        kwargs["client_factory"] = create_secure_client_factory()
    return PROVIDER_TYPES[normalized](**kwargs)
