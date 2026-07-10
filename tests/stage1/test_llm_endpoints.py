"""
---
name: test_llm_endpoints
description: "Endpoint URL normalization, model config, and error sanitization tests"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-endpoints
spec_doc: null
test_file: tests/stage1/test_llm_endpoints.py
functions:
  - name: test_join_api_path_does_not_duplicate_version
    line: 83
    purpose: "Verifies join_api_path avoids duplicating version segments in URLs"
    fixtures: []
  - name: test_normalize_base_url_trims_and_rejects_unsafe_url_parts
    line: 89
    purpose: "Verifies normalize_base_url trims whitespace and rejects unsafe URL patterns"
    fixtures: []
  - name: test_canonicalize_gemini_model
    line: 126
    purpose: "Verifies canonicalize_gemini_model strips the models/ prefix correctly"
    fixtures: []
  - name: test_generation_defaults_are_fast
    line: 130
    purpose: "Verifies LLMGenerationRequest defaults to non-thinking low-effort mode"
    fixtures: []
  - name: test_provider_config_normalizes_base_url
    line: 137
    purpose: "Verifies ProviderConfig normalizes base_url on construction"
    fixtures: []
  - name: test_provider_config_uses_strict_shared_base_url_normalizer
    line: 155
    purpose: "Verifies ProviderConfig rejects unsafe base URLs using strict normalizer"
    fixtures: []
  - name: test_provider_error_string_is_sanitized
    line: 162
    purpose: "Verifies ProviderError string representation does not leak sensitive data"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_endpoints.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import pytest

from core.llm.endpoints import (
    canonicalize_gemini_model,
    join_api_path,
    normalize_base_url,
)
from core.llm.models import (
    LLMGenerationRequest,
    ProviderConfig,
    ProviderError,
)


@pytest.mark.parametrize(
    ("base_url", "path", "expected"),
    [
        ("https://api.example.com/", "/v1/models", "https://api.example.com/v1/models"),
        ("https://api.example.com/v1", "/v1/models", "https://api.example.com/v1/models"),
        (
            "https://api.example.com/proxy/v1/",
            "/v1/chat/completions",
            "https://api.example.com/proxy/v1/chat/completions",
        ),
        (
            "https://generativelanguage.googleapis.com/v1beta",
            "/v1beta/models",
            "https://generativelanguage.googleapis.com/v1beta/models",
        ),
        # Users often paste full generation/model URLs as "base URL".
        (
            "https://llmapi.example.com/v1/chat/completions",
            "/v1/models",
            "https://llmapi.example.com/v1/models",
        ),
        (
            "https://llmapi.example.com/v1/chat/completions",
            "/v1/chat/completions",
            "https://llmapi.example.com/v1/chat/completions",
        ),
        (
            "https://api.anthropic.com/v1/messages",
            "/v1/models",
            "https://api.anthropic.com/v1/models",
        ),
        (
            "https://generativelanguage.googleapis.com/v1beta/models",
            "/v1beta/models",
            "https://generativelanguage.googleapis.com/v1beta/models",
        ),
    ],
)
def test_join_api_path_does_not_duplicate_version(
    base_url: str, path: str, expected: str
) -> None:
    assert join_api_path(base_url, path) == expected


def test_normalize_base_url_trims_and_rejects_unsafe_url_parts() -> None:
    assert normalize_base_url("  HTTPS://API.Example.COM:443/root///  ") == (
        "https://api.example.com/root"
    )
    assert normalize_base_url("http://API.Example.COM:80/") == (
        "http://api.example.com"
    )
    assert normalize_base_url("https://API.Example.COM:8443/") == (
        "https://api.example.com:8443"
    )

    for value in (
        "ftp://api.example.com",
        "https://user:pass@api.example.com",
        "https://api.example.com#fragment",
        "https://api.example.com?key=secret",
        "https://api.example.com\\@127.0.0.1",
        "https://%61pi.example.com",
        "https://api.example.com/\x00secret",
        "https://api\u202e.example.com",
        "\nhttps://api.example.com",
        "https://api.example.com:",
        "https://api.example.com:invalid",
        "https://api.example.com:65536",
    ):
        with pytest.raises(ValueError):
            normalize_base_url(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("models/gemini-2.5-flash", "gemini-2.5-flash"),
        ("/models/gemini-2.5-flash", "gemini-2.5-flash"),
        ("gemini-2.5-flash", "gemini-2.5-flash"),
    ],
)
def test_canonicalize_gemini_model(value: str, expected: str) -> None:
    assert canonicalize_gemini_model(value) == expected


def test_generation_defaults_are_fast() -> None:
    request = LLMGenerationRequest(prompt="hello", model="test", max_tokens=8)

    assert request.thinking is False
    assert request.effort == "low"


def test_provider_config_normalizes_base_url() -> None:
    config = ProviderConfig(base_url=" HTTPS://API.Example.COM:443/v1/ ")

    assert config.base_url == "https://api.example.com/v1"


def test_provider_config_strips_generation_endpoint_from_base_url() -> None:
    config = ProviderConfig(
        base_url="https://llmapi.example.com/v1/chat/completions"
    )

    # Strip the generation path; adapters re-append /v1/models etc.
    assert config.base_url == "https://llmapi.example.com"
    assert join_api_path(config.base_url, "/v1/models") == (
        "https://llmapi.example.com/v1/models"
    )
    assert join_api_path(config.base_url, "/v1/chat/completions") == (
        "https://llmapi.example.com/v1/chat/completions"
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://api.example.com\\@127.0.0.1",
        "https://%61pi.example.com",
        "https://api.example.com/\x1fsecret",
        "https://user:secret@api.example.com",
        "https://api.example.com?key=secret",
        "https://api.example.com#secret",
        "https://api.example.com:invalid",
    ],
)
def test_provider_config_uses_strict_shared_base_url_normalizer(
    base_url: str,
) -> None:
    with pytest.raises(ValueError):
        ProviderConfig(base_url=base_url)


def test_provider_error_string_is_sanitized() -> None:
    error = ProviderError(
        code="provider_response_error",
        message="Provider returned an invalid response.",
        status_code=500,
    )

    assert str(error) == "provider_response_error: Provider returned an invalid response."
    assert "sk-secret" not in str(error)
