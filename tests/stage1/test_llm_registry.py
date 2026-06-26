"""
---
name: test_llm_registry
description: "Protocol adapter registry tests — verifies secure transport and explicit client injection"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-registry
spec_doc: null
test_file: tests/stage1/test_llm_registry.py
functions:
  - name: test_create_provider_uses_secure_transport_by_default
    line: 39
    purpose: "Verifies that create_provider uses VerifiedIPTransport by default for security"
    fixtures: []
  - name: test_create_provider_allows_explicit_test_client
    line: 48
    purpose: "Verifies that an explicit httpx client can be injected into the provider"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_registry.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import httpx

from core.llm.models import LLMProtocol, ProviderConfig
from core.llm.network_transport import VerifiedIPTransport
from core.llm.registry import create_provider


def test_create_provider_uses_secure_transport_by_default() -> None:
    provider = create_provider(LLMProtocol.OPENAI)
    client = provider._client_factory(
        ProviderConfig(base_url="https://api.example.com")
    )

    assert isinstance(client._transport, VerifiedIPTransport)


def test_create_provider_allows_explicit_test_client() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: None))
    provider = create_provider(LLMProtocol.OPENAI, client=client)

    assert provider._client is client
