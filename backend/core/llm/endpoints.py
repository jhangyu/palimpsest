"""
---
name: llm_endpoints
description: "Provider endpoint constants and URL utilities: base URL normalization, API path joining, Gemini model canonicalization"
type: core
target:
  layer: backend
  domain: llm
spec_doc: null
test_file: tests/stage1/test_llm_endpoints.py
functions:
  - name: normalize_base_url
    line: 14
    purpose: "Canonicalize a provider base URL: strip trailing slashes, lowercase scheme/host, reject credentials/query/fragment"
  - name: join_api_path
    line: 60
    purpose: "Join a normalized base URL with an API path, deduplicating overlapping path segments"
  - name: canonicalize_gemini_model
    line: 73
    purpose: "Strip leading 'models/' prefix and whitespace from a Gemini model string"
  - name: gemini_generation_path
    line: 82
    purpose: "Build the Gemini generateContent API path for a given model"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
from __future__ import annotations

import unicodedata
from urllib.parse import urlsplit, urlunsplit


OPENAI_MODELS_PATH = "/v1/models"
OPENAI_GENERATION_PATH = "/v1/chat/completions"
ANTHROPIC_MODELS_PATH = "/v1/models"
ANTHROPIC_GENERATION_PATH = "/v1/messages"
GEMINI_MODELS_PATH = "/v1beta/models"


def normalize_base_url(base_url: str) -> str:
    if (
        "\\" in base_url
        or any(unicodedata.category(char).startswith("C") for char in base_url)
    ):
        raise ValueError("invalid base_url")
    value = base_url.strip()
    if not value:
        raise ValueError("invalid base_url")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("invalid base_url") from None

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError("base_url must use http or https")
    if not hostname:
        raise ValueError("base_url must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("base_url must not include credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("base_url must not include query or fragment")
    if parsed.netloc.endswith(":"):
        raise ValueError("base_url must not include an empty port")
    if "%" in hostname:
        raise ValueError("base_url hostname must not be percent-encoded")
    if any(char.isspace() for char in hostname):
        raise ValueError("base_url hostname must not include whitespace")

    hostname = hostname.rstrip(".").lower()
    if not hostname:
        raise ValueError("base_url must include a hostname")
    canonical_host = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if scheme == "https" else 80
    netloc = (
        canonical_host
        if port is None or port == default_port
        else f"{canonical_host}:{port}"
    )
    path = parsed.path.rstrip("/")
    return urlunsplit((scheme, netloc, path, "", ""))


def join_api_path(base_url: str, api_path: str) -> str:
    root = normalize_base_url(base_url)
    parsed = urlsplit(root)
    base_parts = [part for part in parsed.path.split("/") if part]
    api_parts = [part for part in api_path.split("/") if part]

    if base_parts and api_parts and base_parts[-1] == api_parts[0]:
        api_parts = api_parts[1:]

    path = "/" + "/".join([*base_parts, *api_parts])
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def canonicalize_gemini_model(model: str) -> str:
    value = model.strip().lstrip("/")
    if value.startswith("models/"):
        value = value[len("models/") :]
    if not value:
        raise ValueError("Gemini model is required")
    return value


def gemini_generation_path(model: str) -> str:
    return f"/v1beta/models/{canonicalize_gemini_model(model)}:generateContent"
