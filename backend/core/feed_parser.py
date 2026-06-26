"""
RSS/Atom feed parser module.

Provides synchronous and asynchronous utilities for fetching and parsing
RSS 2.0 and Atom 1.0 feeds using ``feedparser``.

Public API:
    - FeedItem          — dataclass for a single feed entry
    - FeedParseResult   — dataclass for the overall parse result
    - FeedParseError    — exception raised on invalid/unparseable feeds
    - parse_feed_content(content)          — sync, parse raw bytes/str
    - fetch_and_parse_feed(url, ...)       — async, fetch then parse
    - detect_full_content(entries)         — heuristic for full-text detection
    - normalize_feed_items(entries, ...)   — convert feedparser entries → FeedItem list
"""
from __future__ import annotations

import asyncio
import calendar
import functools
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import feedparser  # type: ignore[import]

# Extend feedparser's HTML sanitizer whitelist to preserve lazy-load attributes
feedparser.sanitizer._HTMLSanitizer.acceptable_attributes |= {
    'data-original', 'data-src', 'data-lazy-src', 'data-lazy',
}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class FeedItem:
    """Represents a single parsed entry from an RSS or Atom feed."""

    title: str
    url: str
    pub_date: datetime | None = None
    author: str | None = None
    content: str | None = None
    image_url: str | None = None


@dataclass
class FeedParseResult:
    """Result of parsing a feed document."""

    feed_title: str | None
    feed_link: str | None          # Website URL from feed-level metadata
    items: list[FeedItem]
    has_full_content: bool
    item_count: int


class FeedParseError(Exception):
    """Raised when a feed cannot be parsed or the content is not a valid feed."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FULL_CONTENT_THRESHOLD_CHARS = 200
_FULL_CONTENT_FRACTION = 0.5   # >50% of entries must have long content


def _struct_time_to_utc(t: Any) -> datetime | None:
    """Convert a ``time.struct_time`` (UTC) to a timezone-aware ``datetime``."""
    if t is None:
        return None
    try:
        # calendar.timegm treats the struct_time as UTC
        ts = calendar.timegm(t)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        return None


def _extract_content(entry: dict[str, Any]) -> str | None:
    """Return the richest content string available in a feedparser entry dict.

    Preference order: content[0].value (content:encoded) → summary.
    """
    # feedparser normalises content:encoded into entry['content']
    content_list = entry.get("content", [])
    if content_list:
        value = content_list[0].get("value", "")
        if value:
            return value

    summary = entry.get("summary", "")
    return summary if summary else None


def _extract_image(entry: dict[str, Any]) -> str | None:
    """Try to extract a representative image URL from a feedparser entry."""
    # media:content elements
    for media in entry.get("media_content", []):
        url = media.get("url", "")
        if url:
            return url

    # <link rel="enclosure" type="image/..."> or similar
    for link in entry.get("links", []):
        link_type = link.get("type", "")
        if link_type.startswith("image/"):
            href = link.get("href", "")
            if href:
                return href

    return None


def _extract_author(entry: dict[str, Any]) -> str | None:
    """Return a best-effort author string from a feedparser entry."""
    # feedparser sets entry.author for RSS <author> and Atom <author><name>
    author = entry.get("author", "")
    if author:
        return author

    # Atom detail
    author_detail = entry.get("author_detail", {})
    name = author_detail.get("name", "")
    return name if name else None


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def detect_full_content(entries: list[Any]) -> bool:
    """Return True when >50% of entries have substantial content (>200 chars).

    Checks ``entry['content'][0]['value']`` first, then ``entry['summary']``.

    Args:
        entries: List of feedparser entry dicts (or compatible mappings).

    Returns:
        True if the majority of entries carry full-text content.
    """
    if not entries:
        return False

    long_count = 0
    for entry in entries:
        # content:encoded or Atom <content>
        content_list = entry.get("content", [])
        content_val = content_list[0].get("value", "") if content_list else ""

        # Fall back to summary
        text = content_val or entry.get("summary", "")
        if len(text) > _FULL_CONTENT_THRESHOLD_CHARS:
            long_count += 1

    return (long_count / len(entries)) > _FULL_CONTENT_FRACTION


def normalize_feed_items(
    entries: list[Any],
    feed_link: str | None,
    max_items: int = 50,
) -> list[FeedItem]:
    """Convert a list of feedparser entry dicts into ``FeedItem`` objects.

    - Dates are converted from ``time.struct_time`` (UTC) to timezone-aware
      ``datetime`` objects.  ``published_parsed`` is preferred over
      ``updated_parsed``.
    - Relative URLs are resolved against ``feed_link`` using ``urljoin``.
    - Results are sorted newest-first when dates are available, then truncated
      to ``max_items``.

    Args:
        entries:    Raw feedparser entry list.
        feed_link:  The feed's own website URL used for relative URL resolution.
        max_items:  Maximum number of items to return.

    Returns:
        List of at most *max_items* ``FeedItem`` objects.
    """
    items: list[FeedItem] = []

    for entry in entries:
        title: str = entry.get("title", "") or ""
        raw_url: str = entry.get("link", "") or ""

        # Resolve relative URLs
        if feed_link and raw_url and not raw_url.startswith(("http://", "https://")):
            url = urljoin(feed_link, raw_url)
        else:
            url = raw_url

        # Date: prefer published_parsed, fall back to updated_parsed
        pub_date = _struct_time_to_utc(
            entry.get("published_parsed") or entry.get("updated_parsed")
        )

        author = _extract_author(entry)
        content = _extract_content(entry)
        image_url = _extract_image(entry)

        items.append(
            FeedItem(
                title=title,
                url=url,
                pub_date=pub_date,
                author=author,
                content=content,
                image_url=image_url,
            )
        )

    # Sort newest-first when dates are available (undated items go to the end)
    dated = [i for i in items if i.pub_date is not None]
    undated = [i for i in items if i.pub_date is None]
    dated.sort(key=lambda i: i.pub_date, reverse=True)  # type: ignore[arg-type]
    sorted_items = dated + undated

    return sorted_items[:max_items]


def parse_feed_content(content: str | bytes) -> FeedParseResult:
    """Parse raw RSS/Atom content and return a ``FeedParseResult``.

    This function is **synchronous** and is safe to call from a thread pool
    (e.g., ``asyncio.get_event_loop().run_in_executor``).

    Args:
        content: Raw feed bytes or string.

    Returns:
        Populated ``FeedParseResult``.

    Raises:
        FeedParseError: If the content is not a recognisable RSS/Atom feed,
                        is an HTML page, or is so badly malformed that no
                        feed-level data can be extracted.
    """
    from xml.sax._exceptions import SAXParseException  # noqa: PLC0415

    parsed = feedparser.parse(content)

    feed = parsed.get("feed", {})
    entries = parsed.get("entries", [])
    version = parsed.get("version", "")
    bozo = parsed.get("bozo", False)
    bozo_exception = parsed.get("bozo_exception", None)

    # Reject HTML pages: feedparser sets version='' when it cannot identify feed type
    if not version and bozo:
        exc_msg = str(bozo_exception) if bozo_exception else "unknown parse error"
        raise FeedParseError(
            f"Content does not appear to be a valid RSS/Atom feed: {exc_msg}"
        )

    # Reject feeds with fatal XML parse errors (malformed XML)
    if bozo and isinstance(bozo_exception, SAXParseException):
        raise FeedParseError(
            f"Feed XML is malformed: {bozo_exception}"
        )

    # If there are no entries AND no meaningful feed-level metadata, reject it
    feed_title: str | None = feed.get("title") or None
    feed_link: str | None = feed.get("link") or None

    if not entries and not feed_title and not feed_link:
        raise FeedParseError(
            "Feed has no entries and no recognisable feed-level metadata."
        )

    # Normalise entries → FeedItem list
    items = normalize_feed_items(entries, feed_link=feed_link)

    # Detect whether the feed carries full-text content
    has_full = detect_full_content(entries)

    return FeedParseResult(
        feed_title=feed_title,
        feed_link=feed_link,
        items=items,
        has_full_content=has_full,
        item_count=len(items),
    )


async def fetch_and_parse_feed(
    url: str,
    timeout: float = 30.0,
    max_items: int = 50,
) -> FeedParseResult:
    """Asynchronously fetch a feed URL and parse it.

    Uses scrapling for the HTTP request (bypasses CDN anti-bot measures) and
    wraps ``feedparser.parse()`` in ``run_in_executor`` to avoid blocking the
    event loop.

    Args:
        url:       URL of the RSS or Atom feed.
        timeout:   HTTP request timeout in seconds.
        max_items: Maximum number of feed items to include in the result.

    Returns:
        Populated ``FeedParseResult``.

    Raises:
        FeedParseError: On network errors, HTTP errors, or invalid feed content.
    """
    from core.scraper import fetch_page

    page = await fetch_page(url, method="scrapling")
    if page is None:
        raise FeedParseError(f"Failed to fetch feed (network error): {url}")
    if page.status != 200:
        raise FeedParseError(f"HTTP error {page.status} fetching feed: {url}")

    content: bytes = page.body

    loop = asyncio.get_event_loop()
    parse_fn = functools.partial(feedparser.parse, content)
    parsed = await loop.run_in_executor(None, parse_fn)

    feed = parsed.get("feed", {})
    entries = parsed.get("entries", [])
    version = parsed.get("version", "")
    bozo = parsed.get("bozo", False)
    bozo_exception = parsed.get("bozo_exception", None)

    if not version and bozo:
        exc_msg = str(bozo_exception) if bozo_exception else "unknown parse error"
        raise FeedParseError(
            f"Content at {url} is not a valid RSS/Atom feed: {exc_msg}"
        )

    feed_title: str | None = feed.get("title") or None
    feed_link: str | None = feed.get("link") or None

    if not entries and not feed_title and not feed_link:
        raise FeedParseError(
            f"Feed at {url} has no entries and no recognisable feed-level metadata."
        )

    items = normalize_feed_items(entries, feed_link=feed_link, max_items=max_items)
    has_full = detect_full_content(entries)

    return FeedParseResult(
        feed_title=feed_title,
        feed_link=feed_link,
        items=items,
        has_full_content=has_full,
        item_count=len(items),
    )
