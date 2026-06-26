"""
---
name: test_site_rss
description: "RSS input feature CRUD tests — RS-01 through RS-14"
stage: stage1
type: pytest
target:
  layer: backend
  domain: site
spec_doc: null
test_file: tests/stage1/test_site_rss.py
functions:
  - name: test_create_rss_site
    line: 96
    purpose: "RS-01: POST /sites/ with source_type='rss' → 200"
    fixtures: [auth_client]
  - name: test_create_rss_site_full_content
    line: 116
    purpose: "RS-02: POST /sites/ with rss_full_content=True, source_type='rss' → 200"
    fixtures: [auth_client]
  - name: test_create_html_site_full_content_rejected
    line: 141
    purpose: "RS-03: POST /sites/ with source_type='html', rss_full_content=True → 422"
    fixtures: [auth_client]
  - name: test_list_sites_includes_source_type
    line: 160
    purpose: "RS-04: GET /sites/ → each item has source_type"
    fixtures: [auth_client]
  - name: test_get_rss_site_detail
    line: 186
    purpose: "RS-05: GET /sites/{id} → has source_type, rss_full_content, website_url"
    fixtures: [auth_client]
  - name: test_update_site_switch_to_rss
    line: 207
    purpose: "RS-06: PUT /sites/{id} with source_type='rss' → 200"
    fixtures: [auth_client]
  - name: test_update_site_switch_to_html_clears_full_content
    line: 232
    purpose: "RS-07: PUT with source_type='html' → rss_full_content forced False"
    fixtures: [auth_client]
  - name: test_duplicate_rss_site
    line: 266
    purpose: "RS-08: POST /sites/{id}/duplicate → copy has same source_type"
    fixtures: [auth_client]
  - name: test_delete_rss_site
    line: 299
    purpose: "RS-09: DELETE /sites/{id} → 200"
    fixtures: [auth_client]
  - name: test_feed_parse_endpoint
    line: 318
    purpose: "RS-10: POST /feed/parse with valid RSS URL (mocked) → 200 with metadata"
    fixtures: [auth_client]
  - name: test_feed_parse_requires_auth
    line: 343
    purpose: "RS-11: POST /feed/parse without session → 401"
    fixtures: [client]
  - name: test_feed_parse_invalid_url
    line: 355
    purpose: "RS-12: POST /feed/parse with non-feed URL (mocked error) → 422"
    fixtures: [auth_client]
  - name: test_rss_output_website_url
    line: 374
    purpose: "RS-13: GET /rss/{name} for RSS site with website_url → channel link = website_url"
    fixtures: [auth_client, client]
  - name: test_preview_rss_mode
    line: 406
    purpose: "RS-14: POST /crawl/preview with source_type='rss' → returns feed items"
    fixtures: [auth_client]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_site_rss.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rss_site_payload(name: str, url: str = "https://example.com/feed.xml", **extra) -> dict:
    """Build request body for POST /sites/ with source_type='rss'."""
    site: dict = {
        "url": url,
        "name": name,
        "refresh_frequency": 60,
        "scrape_method": "scrapling",
        "source_type": "rss",
        **extra,
    }
    return {
        "site": site,
        "rules": {"list_rules": {}, "content_rules": {}},
    }


def _html_site_payload(name: str, url: str = "https://example.com", **extra) -> dict:
    """Build request body for POST /sites/ with source_type='html'."""
    site: dict = {
        "url": url,
        "name": name,
        "refresh_frequency": 60,
        "scrape_method": "scrapling",
        "source_type": "html",
        **extra,
    }
    return {
        "site": site,
        "rules": {"list_rules": {}, "content_rules": {}},
    }


async def _create_rss_site(auth_client, name: str, url: str = "https://example.com/feed.xml", **extra) -> int:
    """Create an RSS site and return its ID."""
    csrf = auth_client.cookies.get("csrf_token", "")
    resp = await auth_client.post(
        "/sites/",
        json=_rss_site_payload(name, url=url, **extra),
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, f"create_rss_site failed: {resp.text}"
    return resp.json()["id"]


async def _create_html_site(auth_client, name: str) -> int:
    """Create an HTML site and return its ID."""
    csrf = auth_client.cookies.get("csrf_token", "")
    resp = await auth_client.post(
        "/sites/",
        json=_html_site_payload(name),
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, f"create_html_site failed: {resp.text}"
    return resp.json()["id"]


async def _delete_site(auth_client, site_id: int) -> None:
    """Delete a site."""
    csrf = auth_client.cookies.get("csrf_token", "")
    await auth_client.delete(f"/sites/{site_id}", headers={"X-CSRF-Token": csrf})


def _mock_feed_result(items=None):
    """Create a fake FeedParseResult for mocking fetch_and_parse_feed."""
    from core.feed_parser import FeedParseResult, FeedItem
    if items is None:
        items = [
            FeedItem(
                title="Test Article",
                url="https://example.com/article/1",
                pub_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                author="Test Author",
                content="Article content here.",
            )
        ]
    return FeedParseResult(
        feed_title="Test Feed",
        feed_link="https://example.com",
        items=items,
        has_full_content=False,
        item_count=len(items),
    )


# ---------------------------------------------------------------------------
# RS-01: Create RSS site
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_create_rss_site(auth_client):
    """RS-01: POST /sites/ with source_type='rss' → 200"""
    sfx = uuid.uuid4().hex[:6]
    name = f"RssCreate_{sfx}"
    csrf = auth_client.cookies.get("csrf_token", "")

    resp = await auth_client.post(
        "/sites/",
        json=_rss_site_payload(name),
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    site_id = data["id"]
    try:
        assert "id" in data
        assert data["status"] == "created and crawling started"
    finally:
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# RS-02: Create RSS site with full content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_create_rss_site_full_content(auth_client):
    """RS-02: POST /sites/ with source_type='rss', rss_full_content=True → 200"""
    sfx = uuid.uuid4().hex[:6]
    name = f"RssFullContent_{sfx}"
    csrf = auth_client.cookies.get("csrf_token", "")

    resp = await auth_client.post(
        "/sites/",
        json=_rss_site_payload(name, rss_full_content=True),
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    site_id = resp.json()["id"]

    try:
        # Verify rss_full_content is stored correctly
        detail = await auth_client.get(f"/sites/{site_id}")
        assert detail.status_code == 200
        assert detail.json()["rss_full_content"] is True
    finally:
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# RS-03: HTML site with full content rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_create_html_site_full_content_rejected(auth_client):
    """RS-03: POST /sites/ with source_type='html', rss_full_content=True → 422"""
    sfx = uuid.uuid4().hex[:6]
    name = f"HtmlFullReject_{sfx}"
    csrf = auth_client.cookies.get("csrf_token", "")

    resp = await auth_client.post(
        "/sites/",
        json=_html_site_payload(name, rss_full_content=True),
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# RS-04: List sites includes source_type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_list_sites_includes_source_type(auth_client):
    """RS-04: GET /sites/ → each item has source_type"""
    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_rss_site(auth_client, f"RssList_{sfx}")

    try:
        resp = await auth_client.get("/sites/")
        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert isinstance(items, list)

        # All returned items should have source_type
        for item in items:
            assert "source_type" in item, f"Item missing source_type: {item}"

        # Our newly created site should appear with source_type='rss'
        matching = [i for i in items if i["id"] == site_id]
        assert len(matching) == 1
        assert matching[0]["source_type"] == "rss"
    finally:
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# RS-05: Get RSS site detail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_get_rss_site_detail(auth_client):
    """RS-05: GET /sites/{id} → has source_type, rss_full_content, website_url"""
    sfx = uuid.uuid4().hex[:6]
    name = f"RssDetail_{sfx}"
    csrf = auth_client.cookies.get("csrf_token", "")

    # Create RSS site with website_url
    resp = await auth_client.post(
        "/sites/",
        json=_rss_site_payload(name, website_url="https://mysite.example.com"),
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    site_id = resp.json()["id"]

    try:
        detail = await auth_client.get(f"/sites/{site_id}")
        assert detail.status_code == 200, detail.text
        data = detail.json()
        assert "source_type" in data
        assert "rss_full_content" in data
        assert "website_url" in data
        assert data["source_type"] == "rss"
        assert data["website_url"] == "https://mysite.example.com"
    finally:
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# RS-06: Update site — switch to rss
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_update_site_switch_to_rss(auth_client):
    """RS-06: PUT /sites/{id} with source_type='rss' → 200"""
    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_html_site(auth_client, f"SwitchToRss_{sfx}")
    csrf = auth_client.cookies.get("csrf_token", "")

    try:
        resp = await auth_client.put(
            f"/sites/{site_id}",
            json={"source_type": "rss"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "updated"

        # Verify the update persisted
        detail = await auth_client.get(f"/sites/{site_id}")
        assert detail.json()["source_type"] == "rss"
    finally:
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# RS-07: Update site — switch to html clears rss_full_content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_update_site_switch_to_html_clears_full_content(auth_client):
    """RS-07: PUT with source_type='html' → rss_full_content forced False"""
    sfx = uuid.uuid4().hex[:6]
    # Create an RSS site with full content enabled
    site_id = await _create_rss_site(auth_client, f"SwitchToHtml_{sfx}", rss_full_content=True)
    csrf = auth_client.cookies.get("csrf_token", "")

    try:
        # Verify initial state: rss_full_content=True
        detail = await auth_client.get(f"/sites/{site_id}")
        assert detail.json()["rss_full_content"] is True

        # Switch to html source_type
        resp = await auth_client.put(
            f"/sites/{site_id}",
            json={"source_type": "html"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text

        # Verify rss_full_content is now False
        detail2 = await auth_client.get(f"/sites/{site_id}")
        assert detail2.json()["rss_full_content"] is False
        assert detail2.json()["source_type"] == "html"
    finally:
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# RS-08: Duplicate RSS site
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_rss_site(auth_client):
    """RS-08: POST /sites/{id}/duplicate → copy has same source_type"""
    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_rss_site(auth_client, f"RssDup_{sfx}")
    csrf = auth_client.cookies.get("csrf_token", "")

    new_id = None
    try:
        dup_resp = await auth_client.post(
            f"/sites/{site_id}/duplicate",
            headers={"X-CSRF-Token": csrf},
        )
        assert dup_resp.status_code == 200, dup_resp.text
        new_id = dup_resp.json()["id"]
        assert new_id != site_id
        assert dup_resp.json()["status"] == "duplicated"

        # Verify duplicate has same source_type
        detail = await auth_client.get(f"/sites/{new_id}")
        assert detail.status_code == 200
        assert detail.json()["source_type"] == "rss"
        assert detail.json()["name"].startswith("[Copy]")
    finally:
        await _delete_site(auth_client, site_id)
        if new_id is not None:
            await _delete_site(auth_client, new_id)


# ---------------------------------------------------------------------------
# RS-09: Delete RSS site
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_delete_rss_site(auth_client):
    """RS-09: DELETE /sites/{id} → 200"""
    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_rss_site(auth_client, f"RssDelete_{sfx}")
    csrf = auth_client.cookies.get("csrf_token", "")

    resp = await auth_client.delete(f"/sites/{site_id}", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "deleted"

    # Subsequent GET should return 404
    get_resp = await auth_client.get(f"/sites/{site_id}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# RS-10: Feed parse endpoint — success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_feed_parse_endpoint(auth_client):
    """RS-10: POST /feed/parse with valid RSS URL (mocked) → 200 with feed metadata"""
    mock_result = _mock_feed_result()

    with patch("routers.sites.fetch_and_parse_feed", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = mock_result
        resp = await auth_client.post(
            "/feed/parse",
            json={"url": "https://example.com/feed.xml"},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["feed_title"] == "Test Feed"
    assert data["item_count"] == 1
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Test Article"


# ---------------------------------------------------------------------------
# RS-11: Feed parse requires authentication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_feed_parse_requires_auth(client):
    """RS-11: POST /feed/parse without session → 401"""
    resp = await client.post(
        "/feed/parse",
        json={"url": "https://example.com/feed.xml"},
    )
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# RS-12: Feed parse — non-feed URL raises 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_feed_parse_invalid_url(auth_client):
    """RS-12: POST /feed/parse with non-feed URL (mocked FeedParseError) → 422"""
    from core.feed_parser import FeedParseError

    with patch("routers.sites.fetch_and_parse_feed", new_callable=AsyncMock) as mock_parse:
        mock_parse.side_effect = FeedParseError("Content is not a valid RSS/Atom feed")
        resp = await auth_client.post(
            "/feed/parse",
            json={"url": "https://example.com/not-a-feed"},
        )

    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# RS-13: RSS output uses website_url as channel link
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_rss_output_website_url(auth_client, client):
    """RS-13: GET /rss/{name} for RSS site with website_url → channel link = website_url"""
    sfx = uuid.uuid4().hex[:6]
    site_name = f"RssWebUrl{sfx}"
    website_url = "https://mywebsite.example.com"

    # Create RSS site with website_url
    csrf = auth_client.cookies.get("csrf_token", "")
    create_resp = await auth_client.post(
        "/sites/",
        json=_rss_site_payload(site_name, website_url=website_url),
        headers={"X-CSRF-Token": csrf},
    )
    assert create_resp.status_code == 200, create_resp.text
    site_id = create_resp.json()["id"]

    try:
        # Normalize site name for RSS URL (lowercase)
        normalized = site_name.lower()
        rss_resp = await client.get(f"/rss/{normalized}")
        assert rss_resp.status_code == 200, rss_resp.text

        ct = rss_resp.headers.get("content-type", "")
        assert "xml" in ct, f"Expected XML content-type, got: {ct}"

        body = rss_resp.text
        # The channel <link> should contain website_url
        assert website_url in body, (
            f"Expected website_url '{website_url}' in RSS channel link. "
            f"Got body snippet: {body[:500]}"
        )
    finally:
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# RS-14: Preview in RSS mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_preview_rss_mode(auth_client):
    """RS-14: POST /crawl/preview with source_type='rss' → returns feed items"""
    mock_result = _mock_feed_result()

    with patch("routers.sites.fetch_and_parse_feed", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = mock_result
        resp = await auth_client.post(
            "/crawl/preview",
            json={
                "url": "https://example.com/feed.xml",
                "source_type": "rss",
            },
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 1
    assert data["data"][0]["title"] == "Test Article"
    assert "feed_title" in data


# ===========================================================================
# Stream C — Crawl Pipeline Tests (RC-01 through RC-10)
#
# These tests exercise crawl_site_logic() directly with source_type='rss'.
# fetch_and_parse_feed is mocked throughout to avoid real network calls.
# ===========================================================================

import sqlalchemy
from unittest.mock import MagicMock


def _make_feed_item(sfx: str, idx: int, **kwargs):
    """Build a FeedItem with unique URL for test isolation."""
    from core.feed_parser import FeedItem
    defaults = dict(
        title=f"RC Article {idx}",
        url=f"https://example.com/rc/{sfx}/{idx}",
        pub_date=datetime(2024, 1, idx, tzinfo=timezone.utc),
        author=f"Author {idx}",
        content=f"<p>Article {idx} body text content.</p>",
        image_url=None,
    )
    defaults.update(kwargs)
    return FeedItem(**defaults)


def _make_feed_result(sfx: str, num_items: int = 2, feed_link="https://example.com", **item_overrides):
    """Build a FeedParseResult with `num_items` unique items."""
    from core.feed_parser import FeedParseResult
    items = [_make_feed_item(sfx, i + 1, **item_overrides) for i in range(num_items)]
    return FeedParseResult(
        feed_title="RC Test Feed",
        feed_link=feed_link,
        items=items,
        has_full_content=False,
        item_count=num_items,
    )


async def _cleanup_rc(db, auth_client, site_id: int) -> None:
    """Delete articles for site then delete the site itself."""
    from core.db import articles as _articles
    await db.execute(_articles.delete().where(_articles.c.site_id == site_id))
    await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# RC-01: Basic RSS crawl saves articles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_crawl_rss_site_basic(auth_client, db):
    """RC-01: RSS non-full-content crawl saves articles with title and URL from feed."""
    from core.crawler import crawl_site_logic
    from core.db import async_session_factory, articles as _articles
    from core.feed_parser import FeedParseResult

    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_rss_site(auth_client, f"RcBasic_{sfx}")
    feed_result = _make_feed_result(sfx, num_items=2)

    # Mock page returned by fetch_page for each article URL
    mock_page = MagicMock()
    mock_page.html_content = "<html><body>body</body></html>"

    try:
        with patch("core.crawler.fetch_and_parse_feed", new_callable=AsyncMock) as mock_feed, \
             patch("core.crawler.fetch_page", new_callable=AsyncMock) as mock_fp, \
             patch("core.crawler.parse_article") as mock_pa:
            mock_feed.return_value = feed_result
            mock_fp.return_value = mock_page
            mock_pa.return_value = ("Article body.", None, None, None)

            async with async_session_factory() as session:
                result = await crawl_site_logic(
                    site_id=site_id,
                    url=f"https://example.com/rc/{sfx}/feed",
                    list_rules={},
                    content_rules={},
                    db=session,
                    source_type="rss",
                    rss_full_content=False,
                )

        assert result["status"] == "success", result
        assert result["articles_found"] == 2
        assert result["articles_saved"] == 2
        assert result["articles_failed"] == 0

        saved = await db.fetch_all(
            _articles.select().where(_articles.c.site_id == site_id)
        )
        assert len(saved) == 2
        titles = {a["title"] for a in saved}
        assert "RC Article 1" in titles
        assert "RC Article 2" in titles

    finally:
        await _cleanup_rc(db, auth_client, site_id)


# ---------------------------------------------------------------------------
# RC-02: Full-content mode skips page fetch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_crawl_rss_site_full_content(auth_client, db):
    """RC-02: rss_full_content=True saves RSS content directly; no individual page fetches."""
    from core.crawler import crawl_site_logic
    from core.db import async_session_factory, articles as _articles

    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_rss_site(auth_client, f"RcFull_{sfx}", rss_full_content=True)
    feed_result = _make_feed_result(sfx, num_items=2)

    try:
        with patch("core.crawler.fetch_and_parse_feed", new_callable=AsyncMock) as mock_feed, \
             patch("core.crawler.fetch_page", new_callable=AsyncMock) as mock_fp:
            mock_feed.return_value = feed_result

            async with async_session_factory() as session:
                result = await crawl_site_logic(
                    site_id=site_id,
                    url=f"https://example.com/rc/{sfx}/feed",
                    list_rules={},
                    content_rules={},
                    db=session,
                    source_type="rss",
                    rss_full_content=True,
                )

            # fetch_page must NOT be called in full-content mode
            mock_fp.assert_not_called()

        assert result["status"] == "success", result
        assert result["articles_found"] == 2
        assert result["articles_saved"] == 2

        saved = await db.fetch_all(
            _articles.select().where(_articles.c.site_id == site_id)
        )
        assert len(saved) == 2
        # Content should come from the RSS item, not from page parsing
        for row in saved:
            assert row["content"] is not None
            # RSS item content (after sanitization) should contain the body text
            assert "Article" in row["content"]

    finally:
        await _cleanup_rc(db, auth_client, site_id)


# ---------------------------------------------------------------------------
# RC-03: Non-full-content mode fetches article pages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_crawl_rss_site_content_rules(auth_client, db):
    """RC-03: Non-full-content mode uses content_rules to parse each article page."""
    from core.crawler import crawl_site_logic
    from core.db import async_session_factory, articles as _articles

    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_rss_site(auth_client, f"RcRules_{sfx}")
    feed_result = _make_feed_result(sfx, num_items=1)

    mock_page = MagicMock()
    mock_page.html_content = "<html><body>page content</body></html>"

    try:
        with patch("core.crawler.fetch_and_parse_feed", new_callable=AsyncMock) as mock_feed, \
             patch("core.crawler.fetch_page", new_callable=AsyncMock) as mock_fp, \
             patch("core.crawler.parse_article") as mock_pa:
            mock_feed.return_value = feed_result
            mock_fp.return_value = mock_page
            # parse_article returns content from the page; no pub_date/author from rules
            mock_pa.return_value = ("Parsed page content.", None, None, None)

            async with async_session_factory() as session:
                result = await crawl_site_logic(
                    site_id=site_id,
                    url=f"https://example.com/rc/{sfx}/feed",
                    list_rules={},
                    content_rules={"body": ".article"},
                    db=session,
                    source_type="rss",
                    rss_full_content=False,
                )

            # fetch_page should be called for each article URL
            assert mock_fp.call_count == 1
            assert mock_pa.call_count == 1

        assert result["articles_saved"] == 1

        saved_row = await db.fetch_one(
            _articles.select().where(_articles.c.site_id == site_id)
        )
        assert saved_row is not None
        # Content comes from parse_article (mocked)
        assert "Parsed page content." in saved_row["content"]

    finally:
        await _cleanup_rc(db, auth_client, site_id)


# ---------------------------------------------------------------------------
# RC-04: Scheduled crawl deduplicates existing URLs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_crawl_rss_dedup_scheduled(auth_client, db):
    """RC-04: Scheduled crawl (force_update=False) skips URLs already in articles."""
    from core.crawler import crawl_site_logic
    from core.db import async_session_factory, articles as _articles
    from datetime import timezone

    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_rss_site(auth_client, f"RcDedup_{sfx}")

    # Build 2-item feed: one URL that we'll pre-insert, one that's new
    existing_url = f"https://example.com/rc/{sfx}/1"
    new_url = f"https://example.com/rc/{sfx}/2"
    from core.feed_parser import FeedItem, FeedParseResult
    items = [
        FeedItem(title="RC04 Existing", url=existing_url, pub_date=datetime(2024, 1, 1, tzinfo=timezone.utc)),
        FeedItem(title="RC04 New", url=new_url, pub_date=datetime(2024, 1, 2, tzinfo=timezone.utc)),
    ]
    feed_result = FeedParseResult(
        feed_title="Dedup Feed", feed_link="https://example.com",
        items=items, has_full_content=False, item_count=2,
    )

    # Pre-insert the "existing" article
    now = datetime.now(timezone.utc)
    await db.execute(
        _articles.insert().values(
            site_id=site_id, title="RC04 Existing", url=existing_url,
            content="old content", published_at=now, created_at=now, updated_at=now,
        )
    )

    mock_page = MagicMock()
    mock_page.html_content = "<html><body>x</body></html>"

    try:
        with patch("core.crawler.fetch_and_parse_feed", new_callable=AsyncMock) as mock_feed, \
             patch("core.crawler.fetch_page", new_callable=AsyncMock) as mock_fp, \
             patch("core.crawler.parse_article") as mock_pa:
            mock_feed.return_value = feed_result
            mock_fp.return_value = mock_page
            mock_pa.return_value = ("content", None, None, None)

            async with async_session_factory() as session:
                result = await crawl_site_logic(
                    site_id=site_id,
                    url=f"https://example.com/rc/{sfx}/feed",
                    list_rules={},
                    content_rules={},
                    db=session,
                    source_type="rss",
                    force_update=False,
                )

        assert result["articles_found"] == 2
        # Only 1 new article should be saved (existing URL was skipped)
        assert result["articles_saved"] == 1

        saved = await db.fetch_all(
            _articles.select().where(_articles.c.site_id == site_id)
        )
        assert len(saved) == 2  # 1 pre-existing + 1 new
        urls = {a["url"] for a in saved}
        assert existing_url in urls
        assert new_url in urls

    finally:
        await _cleanup_rc(db, auth_client, site_id)


# ---------------------------------------------------------------------------
# RC-05: Full-content mode also deduplicates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_crawl_rss_full_content_dedup(auth_client, db):
    """RC-05: rss_full_content=True skips URLs already in articles (same dedup as HTML path)."""
    from core.crawler import crawl_site_logic
    from core.db import async_session_factory, articles as _articles
    from core.feed_parser import FeedItem, FeedParseResult

    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_rss_site(auth_client, f"RcFcDedup_{sfx}", rss_full_content=True)

    existing_url = f"https://example.com/rc/{sfx}/fc/1"
    new_url = f"https://example.com/rc/{sfx}/fc/2"
    items = [
        FeedItem(title="FC Existing", url=existing_url,
                 content="<p>old</p>", pub_date=datetime(2024, 1, 1, tzinfo=timezone.utc)),
        FeedItem(title="FC New", url=new_url,
                 content="<p>new content</p>", pub_date=datetime(2024, 1, 2, tzinfo=timezone.utc)),
    ]
    feed_result = FeedParseResult(
        feed_title="FC Feed", feed_link="https://example.com",
        items=items, has_full_content=True, item_count=2,
    )

    now = datetime.now(timezone.utc)
    await db.execute(
        _articles.insert().values(
            site_id=site_id, title="FC Existing", url=existing_url,
            content="old content", published_at=now, created_at=now, updated_at=now,
        )
    )

    try:
        with patch("core.crawler.fetch_and_parse_feed", new_callable=AsyncMock) as mock_feed:
            mock_feed.return_value = feed_result
            async with async_session_factory() as session:
                result = await crawl_site_logic(
                    site_id=site_id,
                    url=f"https://example.com/rc/{sfx}/fc/feed",
                    list_rules={},
                    content_rules={},
                    db=session,
                    source_type="rss",
                    rss_full_content=True,
                    force_update=False,
                )

        assert result["articles_found"] == 2
        assert result["articles_saved"] == 1  # only the new one
        assert result["articles_updated"] == 0

        saved = await db.fetch_all(
            _articles.select().where(_articles.c.site_id == site_id)
        )
        assert len(saved) == 2

    finally:
        await _cleanup_rc(db, auth_client, site_id)


# ---------------------------------------------------------------------------
# RC-06: First crawl stores website_url from feed metadata
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_crawl_rss_website_url_stored(auth_client, db):
    """RC-06: crawl_site_logic stores feed_link as website_url on the sites row."""
    from core.crawler import crawl_site_logic
    from core.db import async_session_factory, sites as sites_table

    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_rss_site(auth_client, f"RcWebUrl_{sfx}")
    feed_result = _make_feed_result(sfx, num_items=1, feed_link="https://my-website.example.com")

    mock_page = MagicMock()
    mock_page.html_content = "<html><body>x</body></html>"

    try:
        with patch("core.crawler.fetch_and_parse_feed", new_callable=AsyncMock) as mock_feed, \
             patch("core.crawler.fetch_page", new_callable=AsyncMock) as mock_fp, \
             patch("core.crawler.parse_article") as mock_pa:
            mock_feed.return_value = feed_result
            mock_fp.return_value = mock_page
            mock_pa.return_value = ("body", None, None, None)

            async with async_session_factory() as session:
                await crawl_site_logic(
                    site_id=site_id,
                    url=f"https://example.com/rc/{sfx}/feed",
                    list_rules={},
                    content_rules={},
                    db=session,
                    source_type="rss",
                )

        site_row = await db.fetch_one(
            sqlalchemy.select(sites_table.c.website_url).where(sites_table.c.id == site_id)
        )
        assert site_row is not None
        assert site_row["website_url"] == "https://my-website.example.com"

    finally:
        from core.db import articles as _articles
        await db.execute(_articles.delete().where(_articles.c.site_id == site_id))
        await _delete_site(auth_client, site_id)


# ---------------------------------------------------------------------------
# RC-07: RSS sites never trigger list repair
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_crawl_rss_no_list_repair():
    """RC-07: RepairOrchestrator.handle_structural_failure returns 'disabled' for RSS list repair."""
    from core.crawl_repair_service import RepairOrchestrator, RepairResult
    from core.crawl_repair_models import define_crawl_repair_tables
    from unittest.mock import AsyncMock

    # Build real table objects (no DB needed — the guard fires before any DB call)
    _meta = sqlalchemy.MetaData()
    _tables = define_crawl_repair_tables(_meta)

    orchestrator = RepairOrchestrator(_tables)
    mock_session = AsyncMock()

    result = await orchestrator.handle_structural_failure(
        session=mock_session,
        site_id=9999,
        repair_kind="list",
        html_evidence="<html></html>",
        active_rules={"item": ".post"},
        rule_revision=1,
        source_type="rss",
    )

    # Guard must fire immediately with 'disabled'
    assert result.action == "disabled", f"Expected 'disabled', got {result.action!r}"
    # No DB calls should have been made
    mock_session.execute.assert_not_called()
    mock_session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# RC-08: Full-content HTML is sanitized before saving
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_crawl_rss_content_sanitized(auth_client, db):
    """RC-08: RSS full-content mode passes content through sanitize_content_html."""
    from core.crawler import crawl_site_logic
    from core.db import async_session_factory, articles as _articles
    from core.feed_parser import FeedItem, FeedParseResult

    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_rss_site(auth_client, f"RcSanitize_{sfx}", rss_full_content=True)

    # Dangerous content with script tags that sanitizer should strip
    dirty_html = "<p>Safe text.</p><script>alert('xss')</script><p>More text.</p>"
    items = [
        FeedItem(
            title="RC08 Sanitize",
            url=f"https://example.com/rc/{sfx}/s1",
            pub_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            content=dirty_html,
        ),
    ]
    feed_result = FeedParseResult(
        feed_title="Sanitize Feed", feed_link="https://example.com",
        items=items, has_full_content=True, item_count=1,
    )

    try:
        with patch("core.crawler.fetch_and_parse_feed", new_callable=AsyncMock) as mock_feed:
            mock_feed.return_value = feed_result
            async with async_session_factory() as session:
                result = await crawl_site_logic(
                    site_id=site_id,
                    url=f"https://example.com/rc/{sfx}/feed",
                    list_rules={},
                    content_rules={},
                    db=session,
                    source_type="rss",
                    rss_full_content=True,
                )

        assert result["articles_saved"] == 1

        saved_row = await db.fetch_one(
            _articles.select().where(_articles.c.site_id == site_id)
        )
        assert saved_row is not None
        content = saved_row["content"] or ""
        # Sanitizer must have removed the script tag
        assert "<script>" not in content
        assert "alert" not in content
        # But safe text should remain
        assert "Safe text" in content or "More text" in content

    finally:
        await _cleanup_rc(db, auth_client, site_id)


# ---------------------------------------------------------------------------
# RC-09: Word count is computed for full-content articles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_crawl_rss_word_count(auth_client, db):
    """RC-09: word_count is populated at insert time for RSS full-content articles."""
    from core.crawler import crawl_site_logic
    from core.db import async_session_factory, articles as _articles
    from core.feed_parser import FeedItem, FeedParseResult

    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_rss_site(auth_client, f"RcWordCnt_{sfx}", rss_full_content=True)

    # 7-word sentence to test word count
    items = [
        FeedItem(
            title="RC09 WordCount",
            url=f"https://example.com/rc/{sfx}/wc1",
            pub_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            content="<p>Hello world this is a test article.</p>",
        ),
    ]
    feed_result = FeedParseResult(
        feed_title="WordCount Feed", feed_link="https://example.com",
        items=items, has_full_content=True, item_count=1,
    )

    try:
        with patch("core.crawler.fetch_and_parse_feed", new_callable=AsyncMock) as mock_feed:
            mock_feed.return_value = feed_result
            async with async_session_factory() as session:
                result = await crawl_site_logic(
                    site_id=site_id,
                    url=f"https://example.com/rc/{sfx}/feed",
                    list_rules={},
                    content_rules={},
                    db=session,
                    source_type="rss",
                    rss_full_content=True,
                )

        assert result["articles_saved"] == 1

        saved_row = await db.fetch_one(
            _articles.select().where(_articles.c.site_id == site_id)
        )
        assert saved_row is not None
        assert saved_row["word_count"] is not None
        assert saved_row["word_count"] > 0

    finally:
        await _cleanup_rc(db, auth_client, site_id)


# ---------------------------------------------------------------------------
# RC-10: pub_date and author fall back to RSS values when content rules return None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio(loop_scope="session")
async def test_crawl_rss_fallback_fields(auth_client, db):
    """RC-10: When parse_article returns None for pub_date/author, RSS item values are used."""
    from core.crawler import crawl_site_logic
    from core.db import async_session_factory, articles as _articles
    from core.feed_parser import FeedItem, FeedParseResult

    sfx = uuid.uuid4().hex[:6]
    site_id = await _create_rss_site(auth_client, f"RcFallback_{sfx}")

    rss_pub_date = datetime(2024, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    rss_author = "RSS Feed Author"

    items = [
        FeedItem(
            title="RC10 Fallback",
            url=f"https://example.com/rc/{sfx}/fb1",
            pub_date=rss_pub_date,
            author=rss_author,
            content=None,  # no content (non-full-content mode)
        ),
    ]
    feed_result = FeedParseResult(
        feed_title="Fallback Feed", feed_link="https://example.com",
        items=items, has_full_content=False, item_count=1,
    )

    mock_page = MagicMock()
    mock_page.html_content = "<html><body>article</body></html>"

    try:
        with patch("core.crawler.fetch_and_parse_feed", new_callable=AsyncMock) as mock_feed, \
             patch("core.crawler.fetch_page", new_callable=AsyncMock) as mock_fp, \
             patch("core.crawler.parse_article") as mock_pa:
            mock_feed.return_value = feed_result
            mock_fp.return_value = mock_page
            # parse_article returns no pub_date and no author — RSS fallback should apply
            mock_pa.return_value = ("Article content from page.", None, None, None)

            async with async_session_factory() as session:
                result = await crawl_site_logic(
                    site_id=site_id,
                    url=f"https://example.com/rc/{sfx}/feed",
                    list_rules={},
                    content_rules={"body": ".article-body"},
                    db=session,
                    source_type="rss",
                    rss_full_content=False,
                )

        assert result["articles_saved"] == 1

        saved_row = await db.fetch_one(
            _articles.select().where(_articles.c.site_id == site_id)
        )
        assert saved_row is not None

        # Author should come from the RSS item (fallback)
        assert saved_row["author"] == rss_author, (
            f"Expected author '{rss_author}', got '{saved_row['author']}'"
        )

        # published_at should match the RSS pub_date (fallback)
        saved_pub = saved_row["published_at"]
        if saved_pub is not None and hasattr(saved_pub, "replace"):
            # Ensure timezone-aware for comparison
            if saved_pub.tzinfo is None:
                saved_pub = saved_pub.replace(tzinfo=timezone.utc)
        assert saved_pub == rss_pub_date, (
            f"Expected published_at {rss_pub_date}, got {saved_pub}"
        )

    finally:
        await _cleanup_rc(db, auth_client, site_id)
