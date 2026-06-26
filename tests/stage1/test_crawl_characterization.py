"""
---
name: test_crawl_characterization
description: "C0 characterization tests — pin current parser behavior with local fixtures"
stage: stage1
type: pytest
target:
  layer: backend
  domain: crawl
spec_doc: null
test_file: tests/stage1/test_crawl_characterization.py
functions:
  - name: test_valid_list_returns_articles
    line: 97
    purpose: "parse_listing() extracts articles when selectors match"
    fixtures: []
  - name: test_valid_list_resolves_relative_urls
    line: 106
    purpose: "Relative URLs are resolved against base_url"
    fixtures: []
  - name: test_valid_list_extracts_titles
    line: 117
    purpose: "Titles are extracted from the title selector"
    fixtures: []
  - name: test_zero_items_when_selectors_broken
    line: 128
    purpose: "parse_listing() returns [] when expected selectors don't match"
    fixtures: []
  - name: test_empty_listing_shell_returns_empty
    line: 138
    purpose: "parse_listing() returns [] when container exists but has no items"
    fixtures: []
  - name: test_parse_listing_accepts_raw_html_string
    line: 150
    purpose: "parse_listing() can accept raw HTML string and wraps it internally"
    fixtures: []
  - name: test_default_item_selector_is_li
    line: 158
    purpose: "When item selector is empty, parse_listing defaults to 'li'"
    fixtures: []
  - name: test_valid_content_extracts_body
    line: 178
    purpose: "parse_article() returns sanitized body content when selector matches"
    fixtures: []
  - name: test_valid_content_extracts_metadata
    line: 192
    purpose: "parse_article() extracts date, image, author from matching selectors"
    fixtures: []
  - name: test_sentinel_parsing_failed
    line: 205
    purpose: "parse_article() returns 'Parsing failed' sentinel when body selector doesn't match"
    fixtures: []
  - name: test_sentinel_vue_extraction_failed
    line: 219
    purpose: "parse_article() returns Vue sentinel when is_vue_template=True but template is malformed"
    fixtures: []
  - name: test_partial_content_returns_thin_text
    line: 232
    purpose: "parse_article() returns thin text when selector matches minimal content"
    fixtures: []
  - name: test_parse_article_accepts_raw_html_string
    line: 249
    purpose: "parse_article() can accept raw HTML string and wraps it internally"
    fixtures: []
  - name: test_valid_content_exceeds_threshold
    line: 268
    purpose: "Valid article content should have word count well above minimum threshold"
    fixtures: []
  - name: test_thin_content_below_threshold
    line: 278
    purpose: "Thin content should have very low word count"
    fixtures: []
  - name: test_sentinel_has_low_word_count
    line: 290
    purpose: "Sentinel strings should have very low word count"
    fixtures: []
  - name: test_empty_content_has_zero_word_count
    line: 295
    purpose: "Empty or None content should have 0 word count"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_crawl_characterization.py -v"
  env: {}
  prerequisites:
    - "Python deps installed (scrapling, beautifulsoup4)"
---

C0 Characterization Tests for Crawl Auto-Repair Phase 22.

These tests pin the **current** observable behavior of parse_listing()
and parse_article() using local HTML fixtures.  They do NOT require a
database, network access, or any external service.

No production code is modified by these tests.
"""

import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure backend is on the path so we can import core.parser
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from core.parser import parse_listing, parse_article
from core.crawler import compute_visible_word_count

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load an HTML fixture file and return its content as a string."""
    path = _FIXTURES_DIR / name
    return path.read_text(encoding="utf-8")


def _make_page(html: str):
    """Wrap raw HTML string in a Scrapling Selector for parser consumption."""
    from scrapling.parser import Selector
    return Selector(html)


# ---------------------------------------------------------------------------
# Standard list rules used across list tests
# ---------------------------------------------------------------------------

_LIST_RULES = {
    "container": ".article-list",
    "item": ".article-item",
    "link": "a",
    "title": "h3",
}

_CONTENT_RULES = {
    "body": "div.article-body",
    "date": "time.pub-date",
    "image": "img.article-image",
    "author": "span.author",
}

_CONTENT_RULES_BODY_ONLY = {
    "body": "div.article-body",
}

_BASE_URL = "https://example.com"


# ═══════════════════════════════════════════════════════════════════════════════
# AR-LIST: List extraction characterization
# ═══════════════════════════════════════════════════════════════════════════════


class TestListExtraction:
    """Characterize current parse_listing() behavior."""

    # AR-LIST-001: Valid list with multiple items
    def test_valid_list_returns_articles(self):
        """parse_listing() extracts articles when selectors match."""
        html = _load_fixture("crawl_valid_list.html")
        page = _make_page(html)
        items = parse_listing(page, _LIST_RULES, _BASE_URL)

        assert len(items) == 3
        assert all("url" in item and "title" in item for item in items)

    def test_valid_list_resolves_relative_urls(self):
        """Relative URLs are resolved against base_url."""
        html = _load_fixture("crawl_valid_list.html")
        page = _make_page(html)
        items = parse_listing(page, _LIST_RULES, _BASE_URL)

        # First item has relative URL /articles/2024-01-01-first-post
        assert items[0]["url"] == f"{_BASE_URL}/articles/2024-01-01-first-post"
        # Second item has absolute URL
        assert items[1]["url"] == "https://example.com/articles/2024-01-02-second-post"

    def test_valid_list_extracts_titles(self):
        """Titles are extracted from the title selector."""
        html = _load_fixture("crawl_valid_list.html")
        page = _make_page(html)
        items = parse_listing(page, _LIST_RULES, _BASE_URL)

        assert items[0]["title"] == "First Article Title"
        assert items[1]["title"] == "Second Article Title"
        assert items[2]["title"] == "Third Article Title"

    # AR-LIST-002: List extraction with zero results (structural failure scenario)
    def test_zero_items_when_selectors_broken(self):
        """parse_listing() returns [] when expected selectors don't match
        (simulates a site redesign that changes CSS classes)."""
        html = _load_fixture("crawl_list_zero_items.html")
        page = _make_page(html)
        items = parse_listing(page, _LIST_RULES, _BASE_URL)

        assert items == []

    # AR-LIST-003: Valid empty listing shell (NOT structural failure)
    def test_empty_listing_shell_returns_empty(self):
        """parse_listing() returns [] when container exists but has no items.
        This represents a legitimate empty page (e.g., no articles yet),
        NOT a selector failure.  Current behavior: indistinguishable from
        structural failure (both return [])."""
        html = _load_fixture("crawl_empty_listing_shell.html")
        page = _make_page(html)
        items = parse_listing(page, _LIST_RULES, _BASE_URL)

        assert items == []

    # AR-LIST-004: parse_listing with raw HTML string (no Selector wrapping)
    def test_parse_listing_accepts_raw_html_string(self):
        """parse_listing() can accept raw HTML string and wraps it internally."""
        html = _load_fixture("crawl_valid_list.html")
        items = parse_listing(html, _LIST_RULES, _BASE_URL)

        assert len(items) == 3

    # AR-LIST-005: parse_listing with empty/default rules
    def test_default_item_selector_is_li(self):
        """When item selector is empty, parse_listing defaults to 'li'."""
        html = _load_fixture("crawl_valid_list.html")
        page = _make_page(html)
        rules = {"container": ".article-list", "item": "", "link": "a", "title": "h3"}
        items = parse_listing(page, rules, _BASE_URL)

        # Default item selector 'li' should still match .article-item <li> elements
        assert len(items) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# AR-CONTENT: Content extraction characterization
# ═══════════════════════════════════════════════════════════════════════════════


class TestContentExtraction:
    """Characterize current parse_article() behavior."""

    # AR-CONTENT-001: Valid content extraction
    def test_valid_content_extracts_body(self):
        """parse_article() returns sanitized body content when selector matches."""
        html = _load_fixture("crawl_valid_content.html")
        page = _make_page(html)
        content_text, pub_date, image_url, author = parse_article(
            page, _CONTENT_RULES, "https://example.com/article/1"
        )

        # Body should be non-empty and non-sentinel
        assert content_text != ""
        assert content_text != "Parsing failed"
        assert content_text != "Vue template extraction failed"
        assert len(content_text) > 80  # substantial content

    def test_valid_content_extracts_metadata(self):
        """parse_article() extracts date, image, author from matching selectors."""
        html = _load_fixture("crawl_valid_content.html")
        page = _make_page(html)
        content_text, pub_date, image_url, author = parse_article(
            page, _CONTENT_RULES, "https://example.com/article/1"
        )

        assert pub_date == "2024-01-15"
        assert image_url == "https://example.com/images/test-article.jpg"
        assert author == "Jane Doe"

    # AR-CONTENT-002: Sentinel "Parsing failed" detection
    def test_sentinel_parsing_failed(self):
        """parse_article() returns 'Parsing failed' sentinel when body selector
        doesn't match any element — current behavior that will be replaced
        with typed outcomes in C1."""
        html = _load_fixture("crawl_content_sentinel_fail.html")
        page = _make_page(html)
        content_text, pub_date, image_url, author = parse_article(
            page, _CONTENT_RULES_BODY_ONLY, "https://example.com/article/fail"
        )

        # Pin current sentinel behavior
        assert content_text == "Parsing failed"

    # AR-CONTENT-002b: Vue sentinel detection
    def test_sentinel_vue_extraction_failed(self):
        """parse_article() returns 'Vue template extraction failed' sentinel
        when is_vue_template=True but template content is malformed JSON."""
        html = _load_fixture("crawl_content_vue_fail.html")
        page = _make_page(html)
        vue_rules = {"is_vue_template": True}
        content_text, pub_date, image_url, author = parse_article(
            page, vue_rules, "https://example.com/article/vue-fail"
        )

        assert content_text == "Vue template extraction failed"

    # AR-CONTENT-003: Partial/thin content (selector matches but minimal text)
    def test_partial_content_returns_thin_text(self):
        """parse_article() returns whatever text the selector finds, even if
        very thin (e.g. 'Loading...').  Current behavior: no minimum content
        threshold — anything non-empty from the selector is accepted."""
        html = _load_fixture("crawl_content_partial.html")
        page = _make_page(html)
        content_text, pub_date, image_url, author = parse_article(
            page, _CONTENT_RULES_BODY_ONLY, "https://example.com/article/partial"
        )

        # Should NOT be a sentinel
        assert content_text != "Parsing failed"
        assert content_text != "Vue template extraction failed"
        # But content is very thin
        assert content_text != ""

    # AR-CONTENT-004: parse_article accepts raw HTML string
    def test_parse_article_accepts_raw_html_string(self):
        """parse_article() can accept raw HTML string and wraps it internally."""
        html = _load_fixture("crawl_valid_content.html")
        content_text, pub_date, image_url, author = parse_article(
            html, _CONTENT_RULES, "https://example.com/article/1"
        )

        assert content_text != "Parsing failed"
        assert len(content_text) > 80


# ═══════════════════════════════════════════════════════════════════════════════
# AR-WC: Word count / content threshold characterization
# ═══════════════════════════════════════════════════════════════════════════════


class TestWordCountThreshold:
    """Characterize compute_visible_word_count() for content validity threshold."""

    def test_valid_content_exceeds_threshold(self):
        """Valid article content should have word count well above minimum threshold."""
        html = _load_fixture("crawl_valid_content.html")
        page = _make_page(html)
        content_text, _, _, _ = parse_article(page, _CONTENT_RULES, _BASE_URL)
        wc = compute_visible_word_count(content_text)

        # Valid article should have meaningful word count
        assert wc > 20, f"Valid content word count {wc} is below minimum threshold"

    def test_thin_content_below_threshold(self):
        """Thin content (e.g. 'Loading...') should have very low word count."""
        html = _load_fixture("crawl_content_partial.html")
        page = _make_page(html)
        content_text, _, _, _ = parse_article(
            page, _CONTENT_RULES_BODY_ONLY, _BASE_URL
        )
        wc = compute_visible_word_count(content_text)

        # 'Loading...' should produce very few words
        assert wc < 5, f"Thin content word count {wc} unexpectedly high"

    def test_sentinel_has_low_word_count(self):
        """Sentinel strings should have very low word count."""
        assert compute_visible_word_count("Parsing failed") < 5
        assert compute_visible_word_count("Vue template extraction failed") < 10

    def test_empty_content_has_zero_word_count(self):
        """Empty or None content should have 0 word count."""
        assert compute_visible_word_count("") == 0
        assert compute_visible_word_count(None) == 0
