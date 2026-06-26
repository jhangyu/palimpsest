"""
---
name: test_llm_baseline_contract
description: "Baseline contract checks for LLM selector prompts and mock provider server routing"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-contract
spec_doc: null
test_file: tests/stage1/test_llm_baseline_contract.py
functions:
  - name: test_selector_contract_fixture
    line: 61
    purpose: "Verifies JSON fixture matches expected contract version and selector rule structure"
    fixtures: []
  - name: test_current_prompt_implementation_matches_fixture
    line: 77
    purpose: "Verifies result_parser.py contains all required prompt fragments from the contract fixture"
    fixtures: []
  - name: test_mock_provider_routes
    line: 117
    purpose: "Verifies MockProviderServer responds correctly to OpenAI, Anthropic, and Gemini protocol routes"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_baseline_contract.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
    - "Fixture data at tests/stage1/fixtures/ai_provider/"
---
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from llm_mock_provider import MockProviderServer


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ai_provider"
CURRENT_AI_IMPLEMENTATION = Path(__file__).parents[2] / "backend" / "core" / "llm" / "result_parser.py"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("fixture_name", "expected_keys"),
    [
        ("list_contract.json", {"container", "item", "title", "link"}),
        ("content_contract.json", {"title", "body", "date", "image", "author"}),
    ],
)
def test_selector_contract_fixture(fixture_name: str, expected_keys: set[str]) -> None:
    fixture = _load(fixture_name)
    rules = fixture["normalized_rules"]

    assert fixture["contract_version"] == 1
    assert set(rules) == expected_keys
    assert all(isinstance(value, str) for value in rules.values())
    assert fixture["route_response"]["rules"] == rules
    assert fixture["prompt"]["input_html"]
    assert all(fixture["prompt"]["required_fragments"])
    print(f"[Contract] PASS {fixture['mode']} selector fixture")


@pytest.mark.parametrize(
    "fixture_name", ["list_contract.json", "content_contract.json"]
)
def test_current_prompt_implementation_matches_fixture(fixture_name: str) -> None:
    fixture = _load(fixture_name)
    implementation = CURRENT_AI_IMPLEMENTATION.read_text(encoding="utf-8")

    missing = [
        fragment
        for fragment in fixture["prompt"]["required_fragments"]
        if fragment not in implementation
    ]
    assert not missing, f"prompt contract fragments missing from current implementation: {missing}"
    print(f"[Contract] PASS {fixture['mode']} prompt baseline")


def _request_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=2) as response:
        return json.load(response)


@pytest.mark.parametrize(
    ("method", "path", "response_path"),
    [
        ("GET", "/v1/models", ("openai", "models")),
        ("POST", "/v1/chat/completions", ("openai", "generation")),
        ("GET", "/anthropic/v1/models", ("anthropic", "models")),
        ("POST", "/anthropic/v1/messages", ("anthropic", "generation")),
        ("GET", "/v1beta/models?key=test-key", ("gemini", "models")),
        (
            "POST",
            "/v1beta/models/mock-fast-model:generateContent?key=test-key",
            ("gemini", "generation"),
        ),
    ],
)
def test_mock_provider_routes(
    method: str, path: str, response_path: tuple[str, str]
) -> None:
    fixtures = _load("protocol_responses.json")
    payload = {"model": "mock-fast-model"} if method == "POST" else None

    with MockProviderServer() as server:
        actual = _request_json(server.base_url + path, method=method, payload=payload)
        expected = fixtures[response_path[0]][response_path[1]]

        assert actual == expected
        assert server.requests[-1].method == method
        assert server.requests[-1].json_body == payload
        print(f"[Contract] PASS mock {method} {server.requests[-1].path}")
