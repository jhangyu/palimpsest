"""
---
name: test_analyze_routes
description: "Route validation and forwarding tests for POST /analyze/list and /analyze/content"
stage: stage1
type: pytest
target:
  layer: backend
  domain: analyze
spec_doc: null
test_file: tests/stage1/test_analyze_routes.py
functions:
  - name: test_analyze_list_invalid_url
    line: 58
    purpose: "POST /analyze/list with missing http/https → 422"
  - name: test_analyze_list_empty_url
    line: 64
    purpose: "POST /analyze/list with empty url → 422"
  - name: test_analyze_list_no_auth
    line: 70
    purpose: "POST /analyze/list without auth → 401"
  - name: test_analyze_list_prompt_hint_too_long
    line: 86
    purpose: "POST /analyze/list with 4001 char prompt_hint → 422"
  - name: test_analyze_list_prompt_hint_boundary
    line: 96
    purpose: "POST /analyze/list with 4000 char prompt_hint passes validation (503 KEK)"
  - name: test_analyze_content_prompt_hint_unicode_multiline
    line: 117
    purpose: "POST /analyze/content with Unicode/multiline prompt_hint passes validation (503 KEK)"
  - name: test_analyze_list_empty_prompt_hint
    line: 138
    purpose: "POST /analyze/list with empty prompt_hint passes validation (503 KEK)"
  - name: test_analyze_list_forwarding
    line: 166
    purpose: "POST /analyze/list propagates prompt_hint to analyze_with_providers"
  - name: test_analyze_content_forwarding
    line: 224
    purpose: "POST /analyze/content propagates prompt_hint to analyze_with_providers"
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_analyze_routes.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import unittest.mock

import pytest


# ============================================================================
# Validation tests (body validation happens before Depends, so these work
# without auth or KEK)
# ============================================================================

@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_list_invalid_url_no_scheme(client):
    """URL without http:// or https:// prefix → 422."""
    resp = await client.post("/analyze/list", json={"url": "example.com"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    errors = detail if isinstance(detail, list) else [detail]
    assert any("http://" in str(e.get("msg", "")) or "http://" in str(e).lower() for e in errors)


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_list_invalid_url_empty(client):
    """Empty URL → 422."""
    resp = await client.post("/analyze/list", json={"url": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_list_no_auth(client):
    """Unauthenticated request → 401 (body validation passes first, then require_user fires)."""
    resp = await client.post("/analyze/list", json={"url": "https://example.com"})
    assert resp.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_content_no_auth(client):
    """Unauthenticated request → 401 for /analyze/content."""
    resp = await client.post("/analyze/content", json={"url": "https://example.com"})
    assert resp.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_list_prompt_hint_too_long(client):
    """prompt_hint > 4000 chars → 422 (validated before auth/KEK)."""
    resp = await client.post(
        "/analyze/list",
        json={"url": "https://example.com", "prompt_hint": "x" * 4001},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    errors = detail if isinstance(detail, list) else [detail]
    assert any("4000" in str(e.get("msg", "")).lower() for e in errors)


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_list_prompt_hint_boundary_4000(client):
    """prompt_hint at exactly 4000 chars passes body validation (then fails 401 — no auth)."""
    resp = await client.post(
        "/analyze/list",
        json={"url": "https://example.com", "prompt_hint": "x" * 4000},
    )
    # Body validation passes; next dependency is require_user → 401
    assert resp.status_code == 401


# ============================================================================
# Authenticated-without-KEK tests (require_kek → 503)
# These prove body validation + auth pass and the request reaches the KEK gate.
# ============================================================================

@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_list_auth_no_kek(auth_client):
    """Authenticated but no KEK → 503 (proves body validation + auth passed)."""
    resp = await auth_client.post(
        "/analyze/list",
        json={"url": "https://example.com"},
    )
    assert resp.status_code == 503


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_content_auth_no_kek(auth_client):
    """Authenticated but no KEK → 503 for /analyze/content."""
    resp = await auth_client.post(
        "/analyze/content",
        json={"url": "https://example.com"},
    )
    assert resp.status_code == 503


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_list_unicode_multiline_passes_validation(auth_client):
    """Unicode and multiline prompt_hint passes body validation (then 503)."""
    hint = "第一行\n第二行 🎉\nThird line with \"quotes\" and 'apostrophes'"
    resp = await auth_client.post(
        "/analyze/list",
        json={"url": "https://example.com", "prompt_hint": hint},
    )
    # Body validation + auth passed; KEK missing → 503
    assert resp.status_code == 503


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_list_empty_prompt_hint_passes_validation(auth_client):
    """Empty prompt_hint is accepted (then 503 KEK)."""
    resp = await auth_client.post(
        "/analyze/list",
        json={"url": "https://example.com", "prompt_hint": ""},
    )
    assert resp.status_code == 503


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_list_whitespace_prompt_hint_trimmed(auth_client):
    """Whitespace-only prompt_hint is trimmed to empty (then 503 KEK)."""
    resp = await auth_client.post(
        "/analyze/list",
        json={"url": "https://example.com", "prompt_hint": "   \t\n  "},
    )
    assert resp.status_code == 503


# ============================================================================
# Forwarding tests — verify prompt_hint reaches analyze_with_providers.
# Uses kek_client + auth + mock to bypass real AI/network.
# ============================================================================

@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_list_forwards_prompt_hint(kek_client, kek_auth_client):
    """prompt_hint is forwarded from route through _run_analyze into analyze_with_providers."""
    from unittest.mock import AsyncMock, patch
    from core.ai import analyze_with_providers as real_analyze

    captured_kwargs = {}

    async def fake_analyze(html_content, mode, *, user_id, db, tables, kek_backend,
                           url="", debug_writer=None, prompt_hint=""):
        captured_kwargs["prompt_hint"] = prompt_hint
        captured_kwargs["mode"] = mode
        captured_kwargs["url"] = url
        return {"container": "ul", "item": "li", "title": "a.title", "link": "a.title"}

    with patch("routers.sites.fetch_page", new=AsyncMock(return_value=type(
        "FakePage", (), {"html_content": "<html><ul><li><a class='title' href='/a'>T</a></li></ul></html>"}
    )())):
        with patch("routers.sites.analyze_with_providers", side_effect=fake_analyze):
            resp = await kek_auth_client.post(
                "/analyze/list",
                json={
                    "url": "https://example.com",
                    "debug": False,
                    "prompt_hint": (
                        "請以標題文字「Allume」作為定位錨點，找到它所在的文章卡片，"
                        "並據此推導適用於整個文章列表的 CSS selectors"
                    ),
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["rules"] is not None
    assert data["error"] is None
    assert captured_kwargs["prompt_hint"] == (
        "請以標題文字「Allume」作為定位錨點，找到它所在的文章卡片，"
        "並據此推導適用於整個文章列表的 CSS selectors"
    )
    assert captured_kwargs["mode"] == "list"
    assert captured_kwargs["url"] == "https://example.com"


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_content_forwards_prompt_hint(kek_client, kek_auth_client):
    """prompt_hint is forwarded for /analyze/content."""
    from unittest.mock import AsyncMock, patch

    captured_kwargs = {}

    async def fake_analyze(html_content, mode, *, user_id, db, tables, kek_backend,
                           url="", debug_writer=None, prompt_hint=""):
        captured_kwargs["prompt_hint"] = prompt_hint
        captured_kwargs["mode"] = mode
        captured_kwargs["url"] = url
        return {"body": "div.content", "title": "", "date": "", "image": "", "author": ""}

    with patch("routers.sites.fetch_page", new=AsyncMock(return_value=type(
        "FakePage", (), {"html_content": "<html><div class='content'>Hello</div></html>"}
    )())):
        with patch("routers.sites.analyze_with_providers", side_effect=fake_analyze):
            resp = await kek_auth_client.post(
                "/analyze/content",
                json={
                    "url": "https://example.com/article",
                    "debug": False,
                    "prompt_hint": "Content hint: hero image in data-src attribute",
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["rules"] is not None
    assert data["error"] is None
    assert captured_kwargs["prompt_hint"] == "Content hint: hero image in data-src attribute"
    assert captured_kwargs["mode"] == "content"
    assert captured_kwargs["url"] == "https://example.com/article"


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_list_empty_prompt_hint_forwarded(kek_client, kek_auth_client):
    """Empty prompt_hint is forwarded as empty string (no crash)."""
    from unittest.mock import AsyncMock, patch

    captured_kwargs = {}

    async def fake_analyze(html_content, mode, *, user_id, db, tables, kek_backend,
                           url="", debug_writer=None, prompt_hint=""):
        captured_kwargs["prompt_hint"] = prompt_hint
        return {"container": "ul", "item": "li", "title": "a.title", "link": "a.title"}

    with patch("routers.sites.fetch_page", new=AsyncMock(return_value=type(
        "FakePage", (), {"html_content": "<html><ul><li><a class='title' href='/a'>T</a></li></ul></html>"}
    )())):
        with patch("routers.sites.analyze_with_providers", side_effect=fake_analyze):
            resp = await kek_auth_client.post(
                "/analyze/list",
                json={"url": "https://example.com", "prompt_hint": ""},
            )

    assert resp.status_code == 200
    assert captured_kwargs["prompt_hint"] == ""


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_list_missing_prompt_hint_uses_default(kek_client, kek_auth_client):
    """Missing prompt_hint field defaults to empty string."""
    from unittest.mock import AsyncMock, patch

    captured_kwargs = {}

    async def fake_analyze(html_content, mode, *, user_id, db, tables, kek_backend,
                           url="", debug_writer=None, prompt_hint=""):
        captured_kwargs["prompt_hint"] = prompt_hint
        return {"container": "ul", "item": "li", "title": "a.title", "link": "a.title"}

    with patch("routers.sites.fetch_page", new=AsyncMock(return_value=type(
        "FakePage", (), {"html_content": "<html><ul><li><a class='title' href='/a'>T</a></li></ul></html>"}
    )())):
        with patch("routers.sites.analyze_with_providers", side_effect=fake_analyze):
            resp = await kek_auth_client.post(
                "/analyze/list",
                json={"url": "https://example.com"},
            )

    assert resp.status_code == 200
    assert captured_kwargs["prompt_hint"] == ""
