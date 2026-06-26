# backend/core/crawl_outcomes.py
"""
---
name: crawl_outcomes
description: "C1 typed outcome models and pure-function classifiers for crawl results: FetchOutcome, ListOutcome, ContentOutcome enums + classify_list_outcome / classify_content_batch"
type: core
target:
  layer: backend
  domain: crawl
spec_doc: null
test_file: tests/stage1/test_crawl_outcomes.py
functions:
  - name: FetchOutcome
    line: 31
    purpose: "Enum: result of a single fetch_page() call (SUCCESS, HTTP_ERROR, TIMEOUT, etc.)"
  - name: ListOutcome
    line: 40
    purpose: "Enum: outcome of parsing the listing page (SUCCESS, ZERO_ITEMS, FETCH_FAILED)"
  - name: ContentOutcome
    line: 47
    purpose: "Enum: aggregate outcome of content batch parse (SUCCESS, PARTIAL, ALL_FAILED, etc.)"
  - name: FetchResult
    line: 58
    purpose: "Dataclass: outcome of a single fetch_page() call with metadata"
  - name: ListExtractionResult
    line: 85
    purpose: "Dataclass: outcome of parse_listing() with valid_items and counts"
  - name: ContentExtractionResult
    line: 112
    purpose: "Dataclass: outcome of parse_article() for a single article"
  - name: ContentExtractionResult.is_effective
    line: 139
    purpose: "Property: True if content passes effective-content thresholds"
  - name: is_valid_content
    line: 146
    purpose: "Pure function: determine if extracted content qualifies as effective (>=20 words or >=80 non-ws chars)"
  - name: classify_list_outcome
    line: 195
    purpose: "Classify list fetch+parse into ListExtractionResult with appropriate outcome"
  - name: classify_content_batch
    line: 238
    purpose: "Classify aggregate batch of ContentExtractionResult into ContentOutcome"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# ── Sentinel strings (must match core/parser.py exactly) ──────────────────────

SENTINEL_PARSE_FAILED = "Parsing failed"
SENTINEL_VUE_FAILED = "Vue template extraction failed"

# Minimum thresholds for "effective content" (Decision Freeze, C0)
EFFECTIVE_CONTENT_MIN_WORDS = 20
EFFECTIVE_CONTENT_MIN_NONWS_CHARS = 80


# ── Outcome enumerations ───────────────────────────────────────────────────────

class FetchOutcome(str, Enum):
    """Result of a single fetch_page() call."""
    SUCCESS = "success"          # page returned, status 2xx
    HTTP_ERROR = "http_error"    # server returned 4xx/5xx
    TIMEOUT = "timeout"          # request timed out
    CONNECTION_ERROR = "connection_error"  # network unreachable, DNS failure, etc.
    UNKNOWN_ERROR = "unknown_error"


class ListOutcome(str, Enum):
    """Outcome of parsing the listing page."""
    SUCCESS = "success"          # >= 1 valid items extracted
    ZERO_ITEMS = "zero_items"    # selectors matched page but found 0 items
    FETCH_FAILED = "fetch_failed"  # fetch_page() returned None; parse never ran


class ContentOutcome(str, Enum):
    """Outcome of parsing a batch of content pages."""
    SUCCESS = "success"              # >= 1 article has effective content
    PARTIAL = "partial"              # some articles valid, some failed
    ALL_FAILED = "all_failed"        # every article returned sentinel / was empty
    ALL_FETCH_FAILED = "all_fetch_failed"  # every article's fetch_page() returned None
    ZERO_DENOMINATOR = "zero_denominator"  # no articles were attempted (empty batch)


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class FetchResult:
    """
    The outcome of a single fetch_page() call.

    Attributes:
        outcome: Classified fetch result.
        url: The requested URL.
        final_url: The final URL after redirects (may differ from url).
        status_code: HTTP status code (None for non-HTTP failures).
        page: The Scrapling page object (None on failure).
        html: Raw HTML string (None on failure).
        error_code: String error code for logging / metrics (e.g. "TIMEOUT", "DNS_FAILURE").
    """
    outcome: FetchOutcome
    url: str
    final_url: Optional[str] = None
    status_code: Optional[int] = None
    page: Optional[object] = None
    html: Optional[str] = None
    error_code: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.outcome == FetchOutcome.SUCCESS


@dataclass
class ListExtractionResult:
    """
    The outcome of running parse_listing() on a fetched listing page.

    Attributes:
        outcome: Classified list extraction result.
        valid_items: The list of extracted article dicts (url + title).
        raw_item_matches: Count of raw selector hits before URL validation.
        valid_url_count: Count of items with a valid absolute URL.
        fetch_result: The upstream FetchResult (None if not tracked).
    """
    outcome: ListOutcome
    valid_items: list[dict] = field(default_factory=list)
    raw_item_matches: int = 0
    valid_url_count: int = 0
    fetch_result: Optional[FetchResult] = None

    @property
    def count(self) -> int:
        return len(self.valid_items)

    @property
    def succeeded(self) -> bool:
        return self.outcome == ListOutcome.SUCCESS


@dataclass
class ContentExtractionResult:
    """
    The outcome of parse_article() for a single article.

    Attributes:
        outcome: Classified content extraction result (SUCCESS / PARSE_FAILED / etc.)
        content_html: The extracted HTML (may be sentinel string on failure).
        visible_word_count: Word count as computed by compute_visible_word_count().
        title: Extracted or provided title.
        pub_date: Extracted publication date string.
        image_url: Extracted image URL.
        author: Extracted author name.
        article_url: The article URL this result is for.
        fetch_failed: True if fetch_page() returned None (parse never ran).
    """
    outcome: str          # "success" | "parse_sentinel" | "vue_sentinel" | "fetch_failed" | "empty"
    content_html: str = ""
    visible_word_count: int = 0
    title: str = ""
    pub_date: str = ""
    image_url: Optional[str] = None
    author: Optional[str] = None
    article_url: str = ""
    fetch_failed: bool = False

    @property
    def is_effective(self) -> bool:
        """True if this result counts as effective content."""
        return is_valid_content(self.content_html, self.visible_word_count)


# ── Shared content validity function ──────────────────────────────────────────

def is_valid_content(content_html: str, visible_word_count: int = -1) -> bool:
    """
    Determine if extracted content qualifies as "effective content".

    Decision Freeze (C0):
      - non-empty string
      - not a sentinel failure string
      - visible word count >= 20 words  OR  len(non-whitespace chars) >= 80

    Args:
        content_html: The raw content string (may be HTML or sentinel).
        visible_word_count: Pre-computed word count; -1 means "auto-compute".
                            Auto-compute is done by stripping tags (simple heuristic).

    Returns:
        True if the content is considered effective.
    """
    if not content_html:
        return False
    if content_html == SENTINEL_PARSE_FAILED:
        return False
    if content_html == SENTINEL_VUE_FAILED:
        return False

    # Compute non-whitespace char count
    nonws_count = sum(1 for c in content_html if not c.isspace())
    if nonws_count >= EFFECTIVE_CONTENT_MIN_NONWS_CHARS:
        # May still qualify even without word count
        # But check word count for text-light HTML (e.g. tag-heavy with little text)
        pass

    # Word count
    if visible_word_count < 0:
        # Simple fallback: strip obvious HTML tags and count words
        import re
        stripped = re.sub(r'<[^>]+>', ' ', content_html)
        words = stripped.split()
        visible_word_count = len(words)

    if visible_word_count >= EFFECTIVE_CONTENT_MIN_WORDS:
        return True
    if nonws_count >= EFFECTIVE_CONTENT_MIN_NONWS_CHARS:
        return True

    return False


# ── Classifier: list outcome ───────────────────────────────────────────────────

def classify_list_outcome(
    fetch_failed: bool,
    items: list[dict],
) -> ListExtractionResult:
    """
    Classify the outcome of a listing-page fetch + parse.

    Args:
        fetch_failed: True if fetch_page() returned None (page unreachable).
        items: The result of parse_listing() — empty list if fetch failed or 0 items.

    Returns:
        ListExtractionResult with the appropriate outcome.
    """
    if fetch_failed:
        return ListExtractionResult(
            outcome=ListOutcome.FETCH_FAILED,
            valid_items=[],
            raw_item_matches=0,
            valid_url_count=0,
        )

    valid_items = [i for i in items if isinstance(i, dict) and i.get("url")]
    count = len(valid_items)

    if count == 0:
        return ListExtractionResult(
            outcome=ListOutcome.ZERO_ITEMS,
            valid_items=[],
            raw_item_matches=len(items),
            valid_url_count=0,
        )

    return ListExtractionResult(
        outcome=ListOutcome.SUCCESS,
        valid_items=valid_items,
        raw_item_matches=len(items),
        valid_url_count=count,
    )


# ── Classifier: content batch outcome ─────────────────────────────────────────

def classify_content_batch(
    results: list[ContentExtractionResult],
) -> ContentOutcome:
    """
    Classify the aggregate outcome of crawling a batch of content articles.

    Rules (Decision Freeze, C0):
      - ZERO_DENOMINATOR: batch is empty (no articles attempted).
      - ALL_FETCH_FAILED: every item had fetch_failed=True.
      - SUCCESS: all attempted articles have effective content.
      - ALL_FAILED: no article has effective content (but at least one was fetched).
      - PARTIAL: some have effective content, some do not.

    Args:
        results: List of ContentExtractionResult for each article attempted.

    Returns:
        ContentOutcome enum value.
    """
    if not results:
        return ContentOutcome.ZERO_DENOMINATOR

    fetch_failed_count = sum(1 for r in results if r.fetch_failed)
    if fetch_failed_count == len(results):
        return ContentOutcome.ALL_FETCH_FAILED

    # Only consider items that were actually fetched
    fetched = [r for r in results if not r.fetch_failed]
    effective_count = sum(1 for r in fetched if r.is_effective)

    if effective_count == 0:
        return ContentOutcome.ALL_FAILED
    if effective_count == len(fetched):
        return ContentOutcome.SUCCESS
    return ContentOutcome.PARTIAL
