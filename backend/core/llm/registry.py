"""
---
name: llm_registry
description: "Provider factory registry: maps LLMProtocol enum to provider class, wires secure SSRF-safe client factory by default"
type: core
target:
  layer: backend
  domain: llm
spec_doc: null
test_file: tests/stage1/test_llm_registry.py
functions:
  - name: create_provider
    line: 18
    purpose: "Instantiate the correct provider class for a given LLMProtocol; inject secure client factory unless overridden"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
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
