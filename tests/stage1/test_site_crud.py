"""
---
name: test_site_crud
description: "Site CRUD and RSS integration tests — create, list, get, update, delete, duplicate, RSS feed"
stage: stage1
type: pytest
target:
  layer: backend
  domain: site
spec_doc: null
test_file: tests/stage1/test_site_crud.py
functions:
  - name: test_create_site
    line: 76
    purpose: "POST /sites/ → 200, owner_user_id set correctly in DB"
    fixtures: [auth_client, regular_user, db]
  - name: test_list_sites
    line: 110
    purpose: "GET /sites/ → 200, created sites appear with lightweight fields only"
    fixtures: [auth_client]
  - name: test_get_site
    line: 144
    purpose: "GET /sites/{id} as owner → 200, full site data including rules"
    fixtures: [auth_client]
  - name: test_get_site_wrong_owner
    line: 168
    purpose: "GET /sites/{id} by non-owner non-admin → 403"
    fixtures: [client, db, auth_client]
  - name: test_update_site
    line: 196
    purpose: "PUT /sites/{id} → 200, site settings updated"
    fixtures: [auth_client]
  - name: test_delete_site
    line: 221
    purpose: "DELETE /sites/{id} → 200; subsequent GET returns 404"
    fixtures: [auth_client]
  - name: test_duplicate_site
    line: 243
    purpose: "POST /sites/{id}/duplicate → 200, new ID, name prefixed with '[Copy] '"
    fixtures: [auth_client]
  - name: test_rss_feed
    line: 279
    purpose: "GET /rss/{site_name} → 200, application/xml, full content not truncated"
    fixtures: [client, auth_client, db]
  - name: test_trigger_crawl_not_found
    line: 326
    purpose: "POST /crawl/99999 → 404 for non-existent site"
    fixtures: [auth_client]
  - name: test_rss_feed_not_found
    line: 338
    purpose: "GET /rss/nonexistent → 404; rss_query_events row logged with status_code=404"
    fixtures: [client, db]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_site_crud.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from conftest import _delete_user, _login_client, _seed_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _site_payload(name: str, url: str = "https://example.com") -> dict:
    """Build the embedded JSON body for POST /sites/."""
    return {
        "site": {
            "url": url,
            "name": name,
            "refresh_frequency": 60,
            "scrape_method": "scrapling",
        },
        "rules": {"list_rules": {}, "content_rules": {}},
    }


async def _create_site(auth_client, name: str, url: str = "https://example.com") -> int:
    """Helper: create a site and return its ID."""
    csrf = auth_client.cookies.get("csrf_token", "")
    resp = await auth_client.post(
        "/sites/",
        json=_site_payload(name, url=url),
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, f"create_site failed: {resp.text}"
    return resp.json()["id"]


async def _delete_site(auth_client, site_id: int) -> None:
    """Helper: delete a site using the authenticated client."""
    csrf = auth_client.cookies.get("csrf_token", "")
    await auth_client.delete(f"/sites/{site_id}", headers={"X-CSRF-Token": csrf})


# ---------------------------------------------------------------------------
# 1.4.1  Create site
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_create_site(auth_client, regular_user, db):
    """POST /sites/ → 200, owner_user_id set correctly in DB."""
    from core.db import sites

    csrf = auth_client.cookies.get("csrf_token", "")
    sfx = uuid.uuid4().hex[:6]
    name = f"CreateTest_{sfx}"

    resp = await auth_client.post(
        "/sites/",
        json=_site_payload(name),
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "id" in data
    assert data["status"] == "created and crawling started"

    site_id = data["id"]
    try:
        # Verify ownership in DB
        row = await db.fetch_one(sites.select().where(sites.c.id == site_id))
        assert row is not None
        assert row["owner_user_id"] == regular_user["id"]
        assert row["name"] == name
    finally:
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# 1.4.2  List sites
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_list_sites(auth_client):
    """GET /sites/ → 200, created sites appear in array (lightweight fields)."""
    sfx = uuid.uuid4().hex[:6]
    id_a = await _create_site(auth_client, f"ListA_{sfx}")
    id_b = await _create_site(auth_client, f"ListB_{sfx}")

    try:
        resp = await auth_client.get("/sites/")
        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert isinstance(items, list)

        ids_in_response = {item["id"] for item in items}
        assert id_a in ids_in_response
        assert id_b in ids_in_response

        # Lightweight fields only — no list_rules / content_rules in listing
        for item in items:
            assert "id" in item
            assert "name" in item
            assert "url" in item
            assert "owner_user_id" in item
            assert "list_rules" not in item
            assert "content_rules" not in item
    finally:
        await _delete_site(auth_client, id_a)
        await _delete_site(auth_client, id_b)


# ---------------------------------------------------------------------------
# 1.4.3  Get site (owner)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_get_site(auth_client):
    """GET /sites/{id} as owner → 200, full site data (includes rules)."""
    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_site(auth_client, f"GetTest_{sfx}")

    try:
        resp = await auth_client.get(f"/sites/{site_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == site_id
        # Full data includes rules fields
        assert "list_rules" in data
        assert "content_rules" in data
        assert "url" in data
        assert "name" in data
    finally:
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# 1.4.4  Get site — wrong owner (403)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_get_site_wrong_owner(client, db, auth_client):
    """GET /sites/{id} by non-owner non-admin → 403."""
    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_site(auth_client, f"OwnerTest_{sfx}")

    # Seed a second user and login as them
    sfx2 = uuid.uuid4().hex[:6]
    other_user = await _seed_user(
        db,
        email=f"other_{sfx2}@test.local",
        username=f"other{sfx2}",
    )
    other_client, _ = await _login_client(client, other_user["email"], "TestPass123!")

    try:
        resp = await other_client.get(f"/sites/{site_id}")
        assert resp.status_code == 403, resp.text
    finally:
        await other_client.aclose()
        await _delete_user(db, other_user["id"])
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# 1.4.5  Update site
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_update_site(auth_client):
    """PUT /sites/{id} → 200, site settings updated."""
    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_site(auth_client, f"UpdateTest_{sfx}")

    try:
        csrf = auth_client.cookies.get("csrf_token", "")
        resp = await auth_client.put(
            f"/sites/{site_id}",
            json={"name": f"Updated_{sfx}", "refresh_frequency": 120},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "updated"
        assert data["site_id"] == site_id
    finally:
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# 1.4.6  Delete site (cascade verified)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_delete_site(auth_client):
    """DELETE /sites/{id} → 200; subsequent GET returns 404."""
    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_site(auth_client, f"DeleteTest_{sfx}")

    csrf = auth_client.cookies.get("csrf_token", "")
    del_resp = await auth_client.delete(
        f"/sites/{site_id}", headers={"X-CSRF-Token": csrf}
    )
    assert del_resp.status_code == 200, del_resp.text
    assert del_resp.json()["status"] == "deleted"

    # Subsequent GET should return 404
    get_resp = await auth_client.get(f"/sites/{site_id}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# 1.4.7  Duplicate site
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_site(auth_client):
    """POST /sites/{id}/duplicate → 200, new ID, name prefixed with '[Copy] '."""
    sfx = uuid.uuid4().hex[:6]
    original_name = f"DupTest_{sfx}"
    site_id = await _create_site(auth_client, original_name)

    csrf = auth_client.cookies.get("csrf_token", "")
    dup_resp = await auth_client.post(
        f"/sites/{site_id}/duplicate",
        headers={"X-CSRF-Token": csrf},
    )

    new_id: int | None = None
    try:
        assert dup_resp.status_code == 200, dup_resp.text
        dup_data = dup_resp.json()
        assert "id" in dup_data
        new_id = dup_data["id"]
        assert new_id != site_id
        assert dup_data["status"] == "duplicated"

        # Verify duplicated site name
        detail_resp = await auth_client.get(f"/sites/{new_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["name"] == f"[Copy] {original_name}"
    finally:
        await _delete_site(auth_client, site_id)
        if new_id is not None:
            await _delete_site(auth_client, new_id)


# ---------------------------------------------------------------------------
# 1.4.8  RSS feed (valid site with articles)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_rss_feed(client, auth_client, db):
    """GET /rss/{site_name} → 200, application/xml, items match inserted articles."""
    from core.db import articles

    sfx = uuid.uuid4().hex[:6]
    site_name = f"RSSTest{sfx}"
    site_id = await _create_site(auth_client, site_name, url="https://example.com")

    # Insert an article directly (bypass crawl)
    now = datetime.now(timezone.utc)
    art_url = f"https://example.com/article/{sfx}"
    art_title = f"Test Article {sfx}"
    art_content = "Full article content for RSS test — must not be truncated."
    await db.execute(
        articles.insert().values(
            site_id=site_id,
            title=art_title,
            url=art_url,
            content=art_content,
            published_at=now,
            created_at=now,
            updated_at=now,
        )
    )

    try:
        # site_name normalized: lowercase, spaces→underscore, non-alnum removed
        normalized = site_name.lower().replace(" ", "_")
        rss_resp = await client.get(f"/rss/{normalized}")
        assert rss_resp.status_code == 200, rss_resp.text
        ct = rss_resp.headers.get("content-type", "")
        assert "xml" in ct, f"Expected XML content-type, got: {ct}"

        body = rss_resp.text
        assert art_title in body, "Article title should appear in RSS"
        assert art_content in body, "Full content should appear in RSS (not truncated)"
        assert art_url in body, "Article URL should appear in RSS"
    finally:
        await db.execute(articles.delete().where(articles.c.site_id == site_id))
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# 1.4.10  Crawl trigger — site not found (404)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_trigger_crawl_not_found(auth_client):
    """POST /crawl/99999 → 404 for non-existent site."""
    csrf = auth_client.cookies.get("csrf_token", "")
    resp = await auth_client.post("/crawl/99999", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 1.4.9  RSS feed — site not found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_rss_feed_not_found(client, db):
    """GET /rss/nonexistent → 404; rss_query_events row logged with status_code=404."""
    from core.db import rss_query_events

    unique_slug = f"nonexistent_{uuid.uuid4().hex[:8]}"
    resp = await client.get(f"/rss/{unique_slug}")
    assert resp.status_code == 404, resp.text

    try:
        # Verify event logged
        event_row = await db.fetch_one(
            rss_query_events.select().where(
                (rss_query_events.c.site_identifier == unique_slug)
                & (rss_query_events.c.status_code == 404)
            )
        )
        assert event_row is not None, "Expected rss_query_events row for 404"
        assert event_row["status_code"] == 404
    finally:
        await db.execute(
            "DELETE FROM rss_query_events WHERE site_identifier = :si",
            {"si": unique_slug},
        )
