"""
---
name: test_endpoints_coverage
description: "Endpoint coverage tests — 401 unauthenticated gates, analytics overview, notifications list, AI provider 404"
stage: stage1
type: pytest
target:
  layer: backend
  domain: endpoints
spec_doc: null
test_file: tests/stage1/test_endpoints_coverage.py
functions:
  - name: test_unauthenticated_get_users_me
    line: 37
    purpose: "GET /users/me without auth → 401"
    fixtures: [client]
  - name: test_unauthenticated_list_sites
    line: 43
    purpose: "GET /sites/ without auth → 401"
    fixtures: [client]
  - name: test_unauthenticated_admin_list_users
    line: 50
    purpose: "GET /admin/users without auth → 401 or 403"
    fixtures: [client]
  - name: test_unauthenticated_ai_providers
    line: 57
    purpose: "GET /settings/ai-providers without auth → 401"
    fixtures: [client]
  - name: test_analytics_overview
    line: 64
    purpose: "GET /analytics/overview as authenticated user → 200 with dict response"
    fixtures: [auth_client]
  - name: test_notifications_list
    line: 75
    purpose: "GET /api/notifications as authenticated user → 200 returns list"
    fixtures: [auth_client]
  - name: test_ai_provider_test_not_found
    line: 95
    purpose: "POST /settings/ai-providers/99999/test → 404 for non-existent provider"
    fixtures: [kek_auth_client]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_endpoints_coverage.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# 401 — Unauthenticated access (bare client, no session cookie)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_unauthenticated_get_users_me(client):
    """GET /users/me without auth → 401."""
    resp = await client.get("/users/me")
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio(loop_scope="session")
async def test_unauthenticated_list_sites(client):
    """GET /sites/ without auth → 401."""
    resp = await client.get("/sites/")
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio(loop_scope="session")
async def test_unauthenticated_admin_list_users(client):
    """GET /admin/users without auth → 401 or 403."""
    resp = await client.get("/admin/users")
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio(loop_scope="session")
async def test_unauthenticated_ai_providers(client):
    """GET /settings/ai-providers without auth → 401."""
    resp = await client.get("/settings/ai-providers")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Analytics — authenticated overview
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_analytics_overview(auth_client):
    """GET /analytics/overview as auth_client → 200, expected shape."""
    resp = await auth_client.get("/analytics/overview")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # Response should be a dict (overview object)
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Notifications — authenticated list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_notifications_list(auth_client):
    """GET /api/notifications as auth_client → 200, returns a list."""
    resp = await auth_client.get("/api/notifications")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# AI provider — 404 for non-existent provider (requires KEK)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_ai_provider_test_not_found(kek_auth_client):
    """POST /settings/ai-providers/99999/test → 404 for non-existent provider."""
    csrf = kek_auth_client.cookies.get("csrf_token", "")
    resp = await kek_auth_client.post(
        "/settings/ai-providers/99999/test",
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 404, resp.text
