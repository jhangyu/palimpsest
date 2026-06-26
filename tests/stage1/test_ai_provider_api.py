"""
---
name: test_ai_provider_api
description: "HTTP API endpoint tests for AI provider management (Stage 1.2)"
stage: stage1
type: pytest
target:
  layer: backend
  domain: ai-provider
spec_doc: null
test_file: tests/stage1/test_ai_provider_api.py
functions:
  - name: test_create_ai_provider
    line: 128
    purpose: "POST /settings/ai-providers → 201, masked API key, revision=1"
    fixtures: [kek_auth_client]
  - name: test_list_ai_providers
    line: 150
    purpose: "GET /settings/ai-providers → 200, array with masked keys, ordered by priority"
    fixtures: [kek_auth_client]
  - name: test_update_ai_provider
    line: 197
    purpose: "PUT /settings/ai-providers/{id} → 200, label updated and revision incremented"
    fixtures: [kek_auth_client]
  - name: test_update_ai_provider_revision_conflict
    line: 217
    purpose: "Stale revision on PUT → 409 with revision_conflict code"
    fixtures: [kek_auth_client]
  - name: test_update_ai_provider_new_api_key
    line: 244
    purpose: "Updating api_key re-encrypts; reveal endpoint confirms new plaintext key"
    fixtures: [kek_auth_client]
  - name: test_update_provider_reencrypt_on_base_url_change
    line: 273
    purpose: "Changing base_url triggers re-encryption with new AAD; key survives round-trip"
    fixtures: [kek_auth_client]
  - name: test_delete_ai_provider
    line: 300
    purpose: "DELETE /settings/ai-providers/{id} → 204, provider removed from list"
    fixtures: [kek_auth_client]
  - name: test_delete_ai_provider_wrong_owner
    line: 322
    purpose: "Cross-user deletion attempt is blocked → 403"
    fixtures: [kek_auth_client, kek_client, db]
  - name: test_create_ai_provider_duplicate_label
    line: 354
    purpose: "Duplicate label for same user → 409 with label_conflict code"
    fixtures: [kek_auth_client]
  - name: test_reorder_ai_providers
    line: 367
    purpose: "PUT /settings/ai-providers/order atomically reorders providers"
    fixtures: [kek_auth_client]
  - name: test_toggle_ai_provider_enabled
    line: 392
    purpose: "PUT /settings/ai-providers/{id}/enabled toggles provider enabled state correctly"
    fixtures: [kek_auth_client]
  - name: test_ai_provider_runtime_status
    line: 420
    purpose: "GET /settings/ai-providers/runtime-status returns only enabled providers in chain"
    fixtures: [kek_auth_client]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_ai_provider_api.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import uuid

import pytest

from conftest import (
    _delete_user,
    _get_csrf_token,
    _login_client,
    _seed_user,
)

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_API_KEY = "sk-test1234567890abcdef"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _create_provider(
    client,
    csrf: str,
    *,
    label: str = "Test OpenAI",
    protocol: str = "openai",
    base_url: str = _DEFAULT_BASE_URL,
    model: str = "gpt-4o",
    api_key: str = _DEFAULT_API_KEY,
    temperature: float = 0.7,
    max_tokens: int = 4096,
):
    """POST /settings/ai-providers and return the response."""
    return await client.post(
        "/settings/ai-providers",
        json={
            "label": label,
            "protocol": protocol,
            "base_url": base_url,
            "model": model,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        headers={"X-CSRF-Token": csrf},
    )


# ---------------------------------------------------------------------------
# Tests 1.2.1 – 1.2.12
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_create_ai_provider(kek_auth_client):
    """1.2.1 — POST /settings/ai-providers → 201, masked key, revision=1."""
    csrf = await _get_csrf_token(kek_auth_client)
    resp = await _create_provider(kek_auth_client, csrf, api_key="sk-test1234567890abcdef")

    assert resp.status_code == 201, resp.text
    data = resp.json()
    pid = data.get("id")

    try:
        assert "id" in data
        assert data["label"] == "Test OpenAI"
        assert data["protocol"] == "openai"
        # Last 4 of "sk-test1234567890abcdef" is "cdef"
        assert data["api_key_last4"] == "cdef"
        assert data["api_key_mask"] is not None
        assert "cdef" in data["api_key_mask"]
        # No raw encrypted bytes in response
        assert "encrypted_api_key" not in data
        assert data["revision"] == 1
        assert data["enabled"] is True
    finally:
        if pid:
            await kek_auth_client.request(
                "DELETE",
                f"/settings/ai-providers/{pid}",
                json={"revision": 1},
                headers={"X-CSRF-Token": csrf},
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_list_ai_providers(kek_auth_client):
    """1.2.2 — GET /settings/ai-providers → 200, array, masked, ordered by priority."""
    csrf = await _get_csrf_token(kek_auth_client)

    r1 = await _create_provider(kek_auth_client, csrf, label="Provider Alpha")
    r2 = await _create_provider(kek_auth_client, csrf, label="Provider Beta")
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text
    pid1 = r1.json()["id"]
    pid2 = r2.json()["id"]

    try:
        resp = await kek_auth_client.get("/settings/ai-providers")
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert "providers" in data
        providers = data["providers"]

        for p in providers:
            assert "api_key_mask" in p
            assert "encrypted_api_key" not in p

        # Check that both providers are present (other tests may have created
        # additional providers for the same user, so we avoid an exact count).
        labels = [p["label"] for p in providers]
        assert "Provider Alpha" in labels
        assert "Provider Beta" in labels

        # Alpha was created before Beta → must appear earlier in priority order
        alpha_idx = labels.index("Provider Alpha")
        beta_idx = labels.index("Provider Beta")
        assert alpha_idx < beta_idx, (
            f"Expected Provider Alpha before Provider Beta, got order: {labels}"
        )
    finally:
        # Clean up to prevent label accumulation that could affect other tests
        for pid in (pid1, pid2):
            await kek_auth_client.request(
                "DELETE",
                f"/settings/ai-providers/{pid}",
                json={"revision": 1},
                headers={"X-CSRF-Token": csrf},
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_update_ai_provider(kek_auth_client):
    """1.2.3 — PUT /settings/ai-providers/{id} → 200, revision incremented."""
    csrf = await _get_csrf_token(kek_auth_client)
    r = await _create_provider(kek_auth_client, csrf)
    assert r.status_code == 201, r.text
    provider = r.json()
    pid = provider["id"]
    current_revision = 1

    try:
        resp = await kek_auth_client.put(
            f"/settings/ai-providers/{pid}",
            json={"revision": 1, "label": "Updated Label"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["label"] == "Updated Label"
        assert data["revision"] == 2
        current_revision = data["revision"]
    finally:
        if pid:
            await kek_auth_client.request(
                "DELETE",
                f"/settings/ai-providers/{pid}",
                json={"revision": current_revision},
                headers={"X-CSRF-Token": csrf},
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_update_ai_provider_revision_conflict(kek_auth_client):
    """1.2.4 — Stale revision → 409 revision_conflict."""
    csrf = await _get_csrf_token(kek_auth_client)
    r = await _create_provider(kek_auth_client, csrf)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    current_revision = 1

    try:
        # First update (revision 1 → 2) succeeds
        r1 = await kek_auth_client.put(
            f"/settings/ai-providers/{pid}",
            json={"revision": 1, "label": "First Update"},
            headers={"X-CSRF-Token": csrf},
        )
        assert r1.status_code == 200, r1.text
        current_revision = r1.json()["revision"]

        # Second update with stale revision=1 → 409
        r2 = await kek_auth_client.put(
            f"/settings/ai-providers/{pid}",
            json={"revision": 1, "label": "Stale Update"},
            headers={"X-CSRF-Token": csrf},
        )
        assert r2.status_code == 409, r2.text
        err = r2.json()
        assert err["detail"]["code"] == "revision_conflict"
    finally:
        if pid:
            await kek_auth_client.request(
                "DELETE",
                f"/settings/ai-providers/{pid}",
                json={"revision": current_revision},
                headers={"X-CSRF-Token": csrf},
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_update_ai_provider_new_api_key(kek_auth_client):
    """1.2.5 — Updating api_key re-encrypts with new nonce; reveal confirms."""
    csrf = await _get_csrf_token(kek_auth_client)
    r = await _create_provider(kek_auth_client, csrf, api_key="sk-oldkey1234567890abcdef")
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    old_last4 = r.json()["api_key_last4"]  # "cdef"
    current_revision = 1

    try:
        resp = await kek_auth_client.put(
            f"/settings/ai-providers/{pid}",
            json={"revision": 1, "api_key": "sk-newkey1234567890wxyz"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["api_key_last4"] != old_last4
        assert data["api_key_last4"] == "wxyz"
        current_revision = data["revision"]

        # Reveal should return the new key
        reveal = await kek_auth_client.post(
            f"/settings/ai-providers/{pid}/reveal",
            json={"current_password": "TestPass123!"},
            headers={"X-CSRF-Token": csrf},
        )
        assert reveal.status_code == 200, reveal.text
        assert reveal.json()["api_key"] == "sk-newkey1234567890wxyz"
    finally:
        if pid:
            await kek_auth_client.request(
                "DELETE",
                f"/settings/ai-providers/{pid}",
                json={"revision": current_revision},
                headers={"X-CSRF-Token": csrf},
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_update_provider_reencrypt_on_base_url_change(kek_auth_client):
    """1.2.6 — Changing base_url re-encrypts with new AAD; key survives round-trip."""
    csrf = await _get_csrf_token(kek_auth_client)
    original_key = "sk-persistent-key-1234567890abcdef"
    r = await _create_provider(kek_auth_client, csrf, api_key=original_key)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    current_revision = 1

    try:
        # Update base_url only — existing key must be re-encrypted under new AAD
        resp = await kek_auth_client.put(
            f"/settings/ai-providers/{pid}",
            json={"revision": 1, "base_url": "https://custom.openai.com/v1"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        current_revision = resp.json()["revision"]

        # Reveal → key survives AAD migration
        reveal = await kek_auth_client.post(
            f"/settings/ai-providers/{pid}/reveal",
            json={"current_password": "TestPass123!"},
            headers={"X-CSRF-Token": csrf},
        )
        assert reveal.status_code == 200, reveal.text
        assert reveal.json()["api_key"] == original_key
    finally:
        if pid:
            await kek_auth_client.request(
                "DELETE",
                f"/settings/ai-providers/{pid}",
                json={"revision": current_revision},
                headers={"X-CSRF-Token": csrf},
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_ai_provider(kek_auth_client):
    """1.2.7 — DELETE /settings/ai-providers/{id} → 204, provider gone from list."""
    csrf = await _get_csrf_token(kek_auth_client)
    r = await _create_provider(kek_auth_client, csrf)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    resp = await kek_auth_client.request(
        "DELETE",
        f"/settings/ai-providers/{pid}",
        json={"revision": 1},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 204, resp.text

    list_resp = await kek_auth_client.get("/settings/ai-providers")
    assert list_resp.status_code == 200
    providers = list_resp.json()["providers"]
    assert all(p["id"] != pid for p in providers)


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_ai_provider_wrong_owner(kek_auth_client, kek_client, db):
    """1.2.8 — Cross-user deletion is blocked → 403."""
    csrf = await _get_csrf_token(kek_auth_client)
    r = await _create_provider(kek_auth_client, csrf)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    # Seed a second user and authenticate as them
    sfx = uuid.uuid4().hex[:8]
    user_b = await _seed_user(
        db,
        email=f"userb_{sfx}@test.local",
        username=f"userb{sfx}",
        password="TestPass123!",
    )
    ac_b, csrf_b = await _login_client(
        kek_client, email=user_b["email"], password="TestPass123!"
    )
    try:
        resp = await ac_b.request(
            "DELETE",
            f"/settings/ai-providers/{pid}",
            json={"revision": 1},
            headers={"X-CSRF-Token": csrf_b},
        )
        assert resp.status_code == 403, resp.text
    finally:
        await ac_b.aclose()
        await _delete_user(db, user_b["id"])


@pytest.mark.asyncio(loop_scope="session")
async def test_create_ai_provider_duplicate_label(kek_auth_client):
    """1.2.9 — Duplicate label for same user → 409 label_conflict."""
    csrf = await _get_csrf_token(kek_auth_client)
    r = await _create_provider(kek_auth_client, csrf, label="MyProvider")
    assert r.status_code == 201, r.text

    r2 = await _create_provider(kek_auth_client, csrf, label="MyProvider")
    assert r2.status_code == 409, r2.text
    err = r2.json()
    assert err["detail"]["code"] == "label_conflict"


@pytest.mark.asyncio(loop_scope="session")
async def test_reorder_ai_providers(kek_auth_client):
    """1.2.10 — PUT /settings/ai-providers/order reorders providers atomically."""
    csrf = await _get_csrf_token(kek_auth_client)

    ra = await _create_provider(kek_auth_client, csrf, label="Alpha")
    rb = await _create_provider(kek_auth_client, csrf, label="Beta")
    rc = await _create_provider(kek_auth_client, csrf, label="Gamma")
    assert ra.status_code == rb.status_code == rc.status_code == 201

    id_a = ra.json()["id"]
    id_b = rb.json()["id"]
    id_c = rc.json()["id"]

    try:
        # Reorder: Gamma first, Alpha second, Beta third
        resp = await kek_auth_client.put(
            "/settings/ai-providers/order",
            json={"ordered_ids": [id_c, id_a, id_b], "revision": 1},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        providers = resp.json()["providers"]
        assert [p["id"] for p in providers] == [id_c, id_a, id_b]
    finally:
        for pid in (id_a, id_b, id_c):
            if pid:
                await kek_auth_client.request(
                    "DELETE",
                    f"/settings/ai-providers/{pid}",
                    json={"revision": 1},
                    headers={"X-CSRF-Token": csrf},
                )


@pytest.mark.asyncio(loop_scope="session")
async def test_toggle_ai_provider_enabled(kek_auth_client):
    """1.2.11 — PUT /settings/ai-providers/{id}/enabled toggles correctly."""
    csrf = await _get_csrf_token(kek_auth_client)
    r = await _create_provider(kek_auth_client, csrf)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["enabled"] is True

    try:
        # Disable
        resp = await kek_auth_client.put(
            f"/settings/ai-providers/{pid}/enabled",
            json={"enabled": False},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["enabled"] is False

        # Re-enable
        resp2 = await kek_auth_client.put(
            f"/settings/ai-providers/{pid}/enabled",
            json={"enabled": True},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp2.status_code == 200, resp2.text
        assert resp2.json()["enabled"] is True
    finally:
        if pid:
            await kek_auth_client.request(
                "DELETE",
                f"/settings/ai-providers/{pid}",
                json={"revision": 1},
                headers={"X-CSRF-Token": csrf},
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_ai_provider_runtime_status(kek_auth_client):
    """1.2.12 — GET /settings/ai-providers/runtime-status returns correct chain."""
    csrf = await _get_csrf_token(kek_auth_client)

    r1 = await _create_provider(kek_auth_client, csrf, label="Enabled Provider")
    assert r1.status_code == 201, r1.text
    pid1 = r1.json()["id"]

    r2 = await _create_provider(kek_auth_client, csrf, label="Disabled Provider")
    assert r2.status_code == 201, r2.text
    pid2 = r2.json()["id"]

    try:
        # Disable the second provider
        await kek_auth_client.put(
            f"/settings/ai-providers/{pid2}/enabled",
            json={"enabled": False},
            headers={"X-CSRF-Token": csrf},
        )

        resp = await kek_auth_client.get("/settings/ai-providers/runtime-status")
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # Only enabled providers appear in the chain
        assert data["profiles_enabled"] is True
        chain_ids = [p["id"] for p in data["chain"]]
        assert pid1 in chain_ids
        assert pid2 not in chain_ids
        assert len(data["chain"]) == 1
    finally:
        for pid in (pid1, pid2):
            if pid:
                await kek_auth_client.request(
                    "DELETE",
                    f"/settings/ai-providers/{pid}",
                    json={"revision": 1},
                    headers={"X-CSRF-Token": csrf},
                )
