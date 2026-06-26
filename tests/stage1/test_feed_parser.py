"""
---
name: test_feed_parser
description: "Unit tests for core.feed_parser — RSS/Atom parsing, normalization, and detection"
stage: stage1
type: pytest
target:
  layer: backend
  domain: feed_parser
spec_doc: null
test_file: tests/stage1/test_feed_parser.py
functions:
  - name: test_parse_rss_feed
    id: FP-01
    purpose: "parse sample_rss.xml → 5 items with title, link, pub_date, author"
  - name: test_parse_atom_feed
    id: FP-02
    purpose: "parse sample_atom.xml → 3 items"
  - name: test_parse_rss_full_content
    id: FP-03
    purpose: "sample_rss_fullcontent.xml → has_full_content=True, items have content"
  - name: test_parse_rss_partial_content
    id: FP-04
    purpose: "sample_rss.xml (short descriptions) → has_full_content=False"
  - name: test_parse_rss_empty
    id: FP-05
    purpose: "sample_rss_empty.xml → items=[], has_full_content=False (no error for valid empty feed)"
  - name: test_parse_rss_malformed
    id: FP-06
    purpose: "sample_rss_malformed.xml → raises FeedParseError"
  - name: test_parse_html_as_rss
    id: FP-07
    purpose: "pass HTML string → raises FeedParseError"
  - name: test_normalize_feed_items_dates
    id: FP-08
    purpose: "entries with different date formats → all datetime with UTC tz"
  - name: test_normalize_feed_items_relative_urls
    id: FP-09
    purpose: "items with relative href → resolved against feed link"
  - name: test_detect_full_content_threshold
    id: FP-10
    purpose: "items with varying content lengths → threshold test"
  - name: test_feed_metadata_extraction
    id: FP-11
    purpose: "feed_title and feed_link populated from channel"
  - name: test_item_limit
    id: FP-12
    purpose: "feed with many items, limit=5 → only 5 returned"
---

Unit tests for core.feed_parser module.

These tests cover RSS/Atom parsing, content detection, URL normalization,
date handling, error cases, and item limiting.

All tests are pure unit tests and do not require a database or network.
"""
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.feed_parser import (
    FeedItem,
    FeedParseError,
    FeedParseResult,
    detect_full_content,
    normalize_feed_items,
    parse_feed_content,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> bytes:
    """Load a fixture file from the fixtures directory."""
    path = FIXTURES_DIR / name
    return path.read_bytes()


# ---------------------------------------------------------------------------
# FP-01: Parse standard RSS 2.0
# ---------------------------------------------------------------------------

def test_parse_rss_feed():
    """FP-01: Parse sample_rss.xml → 5 items with title, link, pub_date, author."""
    content = _load_fixture("sample_rss.xml")
    result = parse_feed_content(content)

    assert isinstance(result, FeedParseResult)
    assert result.item_count == 5
    assert len(result.items) == 5

    # Verify first item
    first = result.items[0]
    assert isinstance(first, FeedItem)
    assert first.title is not None and len(first.title) > 0
    assert first.url is not None and first.url.startswith("https://example.com")
    assert first.pub_date is not None
    assert isinstance(first.pub_date, datetime)
    # Author should be extracted
    assert first.author is not None


# ---------------------------------------------------------------------------
# FP-02: Parse Atom 1.0
# ---------------------------------------------------------------------------

def test_parse_atom_feed():
    """FP-02: Parse sample_atom.xml → 3 items."""
    content = _load_fixture("sample_atom.xml")
    result = parse_feed_content(content)

    assert isinstance(result, FeedParseResult)
    assert result.item_count == 3
    assert len(result.items) == 3

    for item in result.items:
        assert isinstance(item, FeedItem)
        assert item.title is not None
        assert item.url is not None and item.url.startswith("https://atom.example.com")


# ---------------------------------------------------------------------------
# FP-03: Parse RSS with content:encoded → full content detected
# ---------------------------------------------------------------------------

def test_parse_rss_full_content():
    """FP-03: sample_rss_fullcontent.xml → has_full_content=True, items have content."""
    content = _load_fixture("sample_rss_fullcontent.xml")
    result = parse_feed_content(content)

    assert result.has_full_content is True
    assert len(result.items) == 3

    for item in result.items:
        # Each item should have content (from content:encoded)
        assert item.content is not None
        assert len(item.content) > 200


# ---------------------------------------------------------------------------
# FP-04: Standard RSS has short descriptions → has_full_content=False
# ---------------------------------------------------------------------------

def test_parse_rss_partial_content():
    """FP-04: sample_rss.xml (short descriptions) → has_full_content=False."""
    content = _load_fixture("sample_rss.xml")
    result = parse_feed_content(content)

    assert result.has_full_content is False


# ---------------------------------------------------------------------------
# FP-05: Empty RSS feed → no error, empty items list
# ---------------------------------------------------------------------------

def test_parse_rss_empty():
    """FP-05: sample_rss_empty.xml → items=[], has_full_content=False (valid empty feed)."""
    content = _load_fixture("sample_rss_empty.xml")
    # Must NOT raise FeedParseError — an empty feed with valid channel is acceptable
    result = parse_feed_content(content)

    assert isinstance(result, FeedParseResult)
    assert result.items == []
    assert result.item_count == 0
    assert result.has_full_content is False


# ---------------------------------------------------------------------------
# FP-06: Malformed XML → raises FeedParseError
# ---------------------------------------------------------------------------

def test_parse_rss_malformed():
    """FP-06: sample_rss_malformed.xml → raises FeedParseError."""
    content = _load_fixture("sample_rss_malformed.xml")
    with pytest.raises(FeedParseError):
        parse_feed_content(content)


# ---------------------------------------------------------------------------
# FP-07: HTML content passed as feed → raises FeedParseError
# ---------------------------------------------------------------------------

def test_parse_html_as_rss():
    """FP-07: Pass HTML string → raises FeedParseError."""
    html_content = """<!DOCTYPE html>
<html>
<head><title>Not a Feed</title></head>
<body>
  <h1>This is an HTML page, not an RSS feed</h1>
  <p>Some paragraph content here.</p>
</body>
</html>"""
    with pytest.raises(FeedParseError):
        parse_feed_content(html_content)


# ---------------------------------------------------------------------------
# FP-08: Date normalization — entries with various date structures
# ---------------------------------------------------------------------------

def test_normalize_feed_items_dates():
    """FP-08: entries with different date formats → all datetime with UTC tz."""
    # Build synthetic feedparser entries with published_parsed (time.struct_time in UTC)
    entries = [
        {
            "title": "Entry with published_parsed",
            "link": "https://example.com/1",
            "published_parsed": time.strptime("2024-01-01T10:00:00", "%Y-%m-%dT%H:%M:%S"),
            "summary": "Short summary.",
        },
        {
            "title": "Entry with updated_parsed only",
            "link": "https://example.com/2",
            "updated_parsed": time.strptime("2024-01-02T12:00:00", "%Y-%m-%dT%H:%M:%S"),
            "summary": "Another short summary.",
        },
        {
            "title": "Entry with no date",
            "link": "https://example.com/3",
            "summary": "No date entry.",
        },
    ]

    items = normalize_feed_items(entries, feed_link="https://example.com")

    assert len(items) == 3

    # First item: published_parsed → UTC datetime
    assert items[0].pub_date is not None
    assert items[0].pub_date.tzinfo == timezone.utc

    # Second item: updated_parsed fallback → UTC datetime
    assert items[1].pub_date is not None
    assert items[1].pub_date.tzinfo == timezone.utc

    # Third item: no date → pub_date is None
    assert items[2].pub_date is None


# ---------------------------------------------------------------------------
# FP-09: Relative URL resolution
# ---------------------------------------------------------------------------

def test_normalize_feed_items_relative_urls():
    """FP-09: items with relative href → resolved against feed link."""
    entries = [
        {
            "title": "Relative URL entry",
            "link": "/articles/my-post",
            "summary": "A post with a relative URL.",
        },
        {
            "title": "Absolute URL entry",
            "link": "https://other.example.com/post",
            "summary": "A post with an absolute URL.",
        },
    ]

    items = normalize_feed_items(entries, feed_link="https://example.com")

    # Relative URL must be resolved against feed_link
    assert items[0].url == "https://example.com/articles/my-post"
    # Absolute URL remains unchanged
    assert items[1].url == "https://other.example.com/post"


# ---------------------------------------------------------------------------
# FP-10: detect_full_content threshold — >50% entries must have long content
# ---------------------------------------------------------------------------

def test_detect_full_content_threshold():
    """FP-10: items with varying content lengths → threshold test."""
    long_text = "A" * 300

    # All entries have long content → True
    all_long = [
        {"content": [{"value": long_text}], "summary": "short"},
        {"content": [{"value": long_text}], "summary": "short"},
        {"content": [{"value": long_text}], "summary": "short"},
    ]
    assert detect_full_content(all_long) is True

    # All entries have only short content → False
    all_short = [
        {"summary": "Short description here."},
        {"summary": "Another brief summary."},
        {"summary": "Yet another short line."},
    ]
    assert detect_full_content(all_short) is False

    # Exactly 50% long (2 of 4): should be False (need >50%)
    half = [
        {"content": [{"value": long_text}], "summary": "short"},
        {"content": [{"value": long_text}], "summary": "short"},
        {"summary": "Short summary one."},
        {"summary": "Short summary two."},
    ]
    assert detect_full_content(half) is False

    # 3 of 4 long (75%) → True
    majority_long = [
        {"content": [{"value": long_text}], "summary": "short"},
        {"content": [{"value": long_text}], "summary": "short"},
        {"content": [{"value": long_text}], "summary": "short"},
        {"summary": "Only this one is short."},
    ]
    assert detect_full_content(majority_long) is True

    # Empty list → False
    assert detect_full_content([]) is False


# ---------------------------------------------------------------------------
# FP-11: Feed-level metadata (title, link) extraction
# ---------------------------------------------------------------------------

def test_feed_metadata_extraction():
    """FP-11: feed_title and feed_link populated from channel."""
    content = _load_fixture("sample_rss.xml")
    result = parse_feed_content(content)

    assert result.feed_title == "Test RSS Feed"
    assert result.feed_link == "https://example.com"

    # Atom feed
    atom_content = _load_fixture("sample_atom.xml")
    atom_result = parse_feed_content(atom_content)

    assert atom_result.feed_title == "Test Atom Feed"
    assert atom_result.feed_link is not None
    assert "atom.example.com" in atom_result.feed_link


# ---------------------------------------------------------------------------
# FP-12: Item limit respected
# ---------------------------------------------------------------------------

def test_item_limit():
    """FP-12: feed with many items, limit=5 → only 5 returned."""
    # Build a synthetic list of 10 entries (no dates so order is preserve-order)
    entries = [
        {
            "title": f"Entry {i}",
            "link": f"https://example.com/entry-{i}",
            "summary": "Short summary.",
        }
        for i in range(10)
    ]

    items = normalize_feed_items(entries, feed_link="https://example.com", max_items=5)
    assert len(items) == 5
