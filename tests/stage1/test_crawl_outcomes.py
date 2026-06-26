"""
---
name: test_crawl_outcomes
description: "C1 unit tests for crawl_outcomes.py — typed outcome models and classifiers"
stage: stage1
type: pytest
target:
  layer: backend
  domain: crawl
spec_doc: null
test_file: tests/stage1/test_crawl_outcomes.py
functions:
  - name: test_empty_string_is_invalid
    line: 46
    purpose: "Empty string content is invalid"
    fixtures: []
  - name: test_none_like_falsy_is_invalid
    line: 49
    purpose: "Falsy/empty content is invalid"
    fixtures: []
  - name: test_sentinel_parse_failed_is_invalid
    line: 53
    purpose: "SENTINEL_PARSE_FAILED content is invalid"
    fixtures: []
  - name: test_sentinel_vue_failed_is_invalid
    line: 56
    purpose: "SENTINEL_VUE_FAILED content is invalid"
    fixtures: []
  - name: test_long_content_by_word_count
    line: 59
    purpose: "Content with >= 20 visible words is valid"
    fixtures: []
  - name: test_content_below_word_count_but_above_char_threshold
    line: 65
    purpose: "Content with < 20 words but >= 80 non-ws chars is still valid"
    fixtures: []
  - name: test_thin_content_below_both_thresholds_is_invalid
    line: 71
    purpose: "Content with < 20 words AND < 80 non-ws chars is invalid"
    fixtures: []
  - name: test_html_with_sufficient_text
    line: 76
    purpose: "HTML with enough text content qualifies"
    fixtures: []
  - name: test_precomputed_word_count_used_when_provided
    line: 81
    purpose: "When visible_word_count >= 20 is passed, is_valid_content returns True"
    fixtures: []
  - name: test_precomputed_word_count_zero_falls_back_to_char_check
    line: 89
    purpose: "When wc=0 but non-ws chars >= 80, is_valid_content still returns True"
    fixtures: []
  - name: test_sentinel_case_sensitive
    line: 95
    purpose: "Sentinel detection is case-sensitive"
    fixtures: []
  - name: test_whitespace_only_content_is_invalid
    line: 111
    purpose: "Content consisting only of whitespace is invalid"
    fixtures: []
  - name: test_success_when_items_found
    line: 125
    purpose: "classify_list_outcome returns SUCCESS when items are found"
    fixtures: []
  - name: test_zero_items_outcome
    line: 134
    purpose: "classify_list_outcome returns ZERO_ITEMS when items list is empty"
    fixtures: []
  - name: test_fetch_failed_outcome
    line: 141
    purpose: "classify_list_outcome returns FETCH_FAILED when fetch_failed=True"
    fixtures: []
  - name: test_fetch_failed_ignores_items
    line: 147
    purpose: "fetch_failed wins even if items is non-empty"
    fixtures: []
  - name: test_items_without_url_are_excluded
    line: 154
    purpose: "Items missing 'url' key or with empty URL are filtered out"
    fixtures: []
  - name: test_all_items_missing_url_gives_zero_items
    line: 167
    purpose: "If every item lacks a URL, outcome is ZERO_ITEMS"
    fixtures: []
  - name: test_succeeded_property
    line: 174
    purpose: "ListResult.succeeded is True only on SUCCESS outcome"
    fixtures: []
  - name: test_all_valid_returns_success
    line: 219
    purpose: "classify_content_batch returns SUCCESS when all results are valid"
    fixtures: []
  - name: test_all_failed_returns_all_failed
    line: 223
    purpose: "classify_content_batch returns ALL_FAILED when all results fail"
    fixtures: []
  - name: test_partial_returns_partial
    line: 227
    purpose: "classify_content_batch returns PARTIAL when mix of valid and failed"
    fixtures: []
  - name: test_empty_batch_returns_zero_denominator
    line: 234
    purpose: "classify_content_batch returns ZERO_DENOMINATOR for empty batch"
    fixtures: []
  - name: test_all_fetch_failed_returns_all_fetch_failed
    line: 237
    purpose: "classify_content_batch returns ALL_FETCH_FAILED when all fetches failed"
    fixtures: []
  - name: test_mixed_fetch_failed_and_valid
    line: 241
    purpose: "Outcome based on fetched articles only when some fetches failed"
    fixtures: []
  - name: test_mixed_fetch_failed_and_parse_failed
    line: 250
    purpose: "Some fetched but all parse failed → ALL_FAILED"
    fixtures: []
  - name: test_single_valid_is_success
    line: 258
    purpose: "Single valid result returns SUCCESS"
    fixtures: []
  - name: test_single_failed_is_all_failed
    line: 261
    purpose: "Single failed result returns ALL_FAILED"
    fixtures: []
  - name: test_vue_sentinel_content_counts_as_failed
    line: 265
    purpose: "Vue extraction failure sentinel is not effective content"
    fixtures: []
  - name: test_valid_content_is_effective
    line: 283
    purpose: "ContentExtractionResult with valid content has is_effective=True"
    fixtures: []
  - name: test_sentinel_is_not_effective
    line: 292
    purpose: "ContentExtractionResult with sentinel has is_effective=False"
    fixtures: []
  - name: test_thin_content_not_effective
    line: 301
    purpose: "ContentExtractionResult with thin content has is_effective=False"
    fixtures: []
  - name: test_succeeded_property_true
    line: 316
    purpose: "FetchResult.succeeded is True on SUCCESS outcome"
    fixtures: []
  - name: test_succeeded_property_false_on_error
    line: 320
    purpose: "FetchResult.succeeded is False on HTTP_ERROR outcome"
    fixtures: []
  - name: test_all_fields_optional_except_outcome_and_url
    line: 324
    purpose: "FetchResult optional fields default to None"
    fixtures: []
  - name: test_parse_failed_sentinel_matches_parser
    line: 338
    purpose: "SENTINEL_PARSE_FAILED must exactly match parser.py"
    fixtures: []
  - name: test_vue_failed_sentinel_matches_parser
    line: 342
    purpose: "SENTINEL_VUE_FAILED must exactly match parser.py"
    fixtures: []
  - name: test_thresholds_match_decision_freeze
    line: 346
    purpose: "Thresholds must match the C0 decision freeze values"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_crawl_outcomes.py -v"
  env: {}
  prerequisites:
    - "Python deps installed"
---
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from core.crawl_outcomes import (
    SENTINEL_PARSE_FAILED,
    SENTINEL_VUE_FAILED,
    EFFECTIVE_CONTENT_MIN_WORDS,
    EFFECTIVE_CONTENT_MIN_NONWS_CHARS,
    FetchOutcome,
    ListOutcome,
    ContentOutcome,
    FetchResult,
    ContentExtractionResult,
    is_valid_content,
    classify_list_outcome,
    classify_content_batch,
)


# ── is_valid_content ───────────────────────────────────────────────────────────

class TestIsValidContent:
    """Tests for the shared is_valid_content() predicate."""

    def test_empty_string_is_invalid(self):
        assert is_valid_content("") is False

    def test_none_like_falsy_is_invalid(self):
        # Technically the function signature is str, but guard against empty
        assert is_valid_content("") is False

    def test_sentinel_parse_failed_is_invalid(self):
        assert is_valid_content(SENTINEL_PARSE_FAILED) is False

    def test_sentinel_vue_failed_is_invalid(self):
        assert is_valid_content(SENTINEL_VUE_FAILED) is False

    def test_long_content_by_word_count(self):
        """Content with >= 20 visible words is valid."""
        # 20 words exactly
        words = " ".join(["word"] * EFFECTIVE_CONTENT_MIN_WORDS)
        assert is_valid_content(words) is True

    def test_content_below_word_count_but_above_char_threshold(self):
        """Content with < 20 words but >= 80 non-whitespace chars is still valid."""
        # 10 long words = fewer than 20 words but > 80 non-ws chars
        content = "abcdefghij " * 10  # 10 words × 10 chars = 100 non-ws chars
        assert is_valid_content(content.strip()) is True

    def test_thin_content_below_both_thresholds_is_invalid(self):
        """Content with < 20 words AND < 80 non-ws chars is invalid."""
        content = "Loading..."  # 1 word, 10 non-ws chars
        assert is_valid_content(content) is False

    def test_html_with_sufficient_text(self):
        """HTML with enough text content qualifies (word-count auto-computed by strip)."""
        html = "<p>" + " ".join(["paragraph"] * 25) + "</p>"
        assert is_valid_content(html) is True

    def test_precomputed_word_count_used_when_provided(self):
        """When visible_word_count >= 20 is passed, is_valid_content returns True."""
        # Single-char content would normally fail both thresholds
        result = is_valid_content("x", visible_word_count=20)
        # With explicit wc=20, the word count threshold is met; but nonws_chars check
        # also matters — "x" has 1 nonws char which is < 80. BUT wc >= 20 alone suffices.
        assert result is True

    def test_precomputed_word_count_zero_falls_back_to_char_check(self):
        """When wc=0 but non-ws chars >= 80, is_valid_content still returns True."""
        content = "a" * 80  # 1 "word" but 80 non-ws chars
        result = is_valid_content(content, visible_word_count=0)
        assert result is True

    def test_sentinel_case_sensitive(self):
        """Sentinel detection is case-sensitive (must match exactly).
        Note: near-misses that differ only in case are NOT sentinels, but still
        need to meet the word/char threshold to qualify as effective content.
        """
        # Exact sentinels are always rejected
        assert is_valid_content(SENTINEL_PARSE_FAILED) is False
        assert is_valid_content(SENTINEL_VUE_FAILED) is False

        # Build strings that differ in case AND are long enough to pass thresholds
        # Need >= 20 words OR >= 80 non-whitespace chars
        not_sentinel_lower = "parsing failed " + " ".join(["filler"] * 20)
        assert is_valid_content(not_sentinel_lower) is True
        not_sentinel_upper = "PARSING FAILED " + " ".join(["FILLER"] * 20)
        assert is_valid_content(not_sentinel_upper) is True

    def test_whitespace_only_content_is_invalid(self):
        """Content consisting only of whitespace is invalid (nonws_chars = 0)."""
        content = "   \n\t  "
        assert is_valid_content(content) is False


# ── classify_list_outcome ──────────────────────────────────────────────────────

class TestClassifyListOutcome:
    """Tests for classify_list_outcome()."""

    def _make_items(self, count: int) -> list[dict]:
        return [{"url": f"https://example.com/{i}", "title": f"Article {i}"} for i in range(count)]

    def test_success_when_items_found(self):
        items = self._make_items(5)
        result = classify_list_outcome(fetch_failed=False, items=items)

        assert result.outcome == ListOutcome.SUCCESS
        assert result.count == 5
        assert result.valid_url_count == 5
        assert result.raw_item_matches == 5

    def test_zero_items_outcome(self):
        result = classify_list_outcome(fetch_failed=False, items=[])

        assert result.outcome == ListOutcome.ZERO_ITEMS
        assert result.count == 0
        assert result.valid_items == []

    def test_fetch_failed_outcome(self):
        result = classify_list_outcome(fetch_failed=True, items=[])

        assert result.outcome == ListOutcome.FETCH_FAILED
        assert result.count == 0

    def test_fetch_failed_ignores_items(self):
        """Even if items is non-empty (shouldn't happen in practice), fetch_failed wins."""
        result = classify_list_outcome(fetch_failed=True, items=self._make_items(3))

        assert result.outcome == ListOutcome.FETCH_FAILED
        assert result.valid_items == []

    def test_items_without_url_are_excluded(self):
        """Items missing 'url' key or with empty URL are filtered out."""
        items = [
            {"url": "https://example.com/valid", "title": "Valid"},
            {"url": "", "title": "Empty URL"},
            {"title": "No URL at all"},
        ]
        result = classify_list_outcome(fetch_failed=False, items=items)

        assert result.outcome == ListOutcome.SUCCESS
        assert result.count == 1  # only the valid item
        assert result.raw_item_matches == 3  # all three were "found"

    def test_all_items_missing_url_gives_zero_items(self):
        """If every item lacks a URL, outcome is ZERO_ITEMS."""
        items = [{"title": "No URL"}, {"title": "Also No URL"}]
        result = classify_list_outcome(fetch_failed=False, items=items)

        assert result.outcome == ListOutcome.ZERO_ITEMS

    def test_succeeded_property(self):
        result_success = classify_list_outcome(fetch_failed=False, items=self._make_items(1))
        result_fail = classify_list_outcome(fetch_failed=False, items=[])

        assert result_success.succeeded is True
        assert result_fail.succeeded is False


# ── classify_content_batch ─────────────────────────────────────────────────────

class TestClassifyContentBatch:
    """Tests for classify_content_batch()."""

    def _make_valid_result(self, url: str = "https://example.com/1") -> ContentExtractionResult:
        """ContentExtractionResult that qualifies as effective content."""
        # 25 words worth of content (above 20 word threshold)
        content = "<p>" + " ".join(["word"] * 25) + "</p>"
        return ContentExtractionResult(
            outcome="success",
            content_html=content,
            visible_word_count=25,
            article_url=url,
            fetch_failed=False,
        )

    def _make_failed_result(self, url: str = "https://example.com/2") -> ContentExtractionResult:
        """ContentExtractionResult with sentinel string (parse failure)."""
        return ContentExtractionResult(
            outcome="parse_sentinel",
            content_html=SENTINEL_PARSE_FAILED,
            visible_word_count=2,
            article_url=url,
            fetch_failed=False,
        )

    def _make_fetch_failed_result(self, url: str = "https://example.com/3") -> ContentExtractionResult:
        """ContentExtractionResult where fetch_page returned None."""
        return ContentExtractionResult(
            outcome="fetch_failed",
            content_html="",
            visible_word_count=0,
            article_url=url,
            fetch_failed=True,
        )

    def test_all_valid_returns_success(self):
        results = [self._make_valid_result(f"https://example.com/{i}") for i in range(3)]
        assert classify_content_batch(results) == ContentOutcome.SUCCESS

    def test_all_failed_returns_all_failed(self):
        results = [self._make_failed_result(f"https://example.com/{i}") for i in range(3)]
        assert classify_content_batch(results) == ContentOutcome.ALL_FAILED

    def test_partial_returns_partial(self):
        results = [
            self._make_valid_result("https://example.com/1"),
            self._make_failed_result("https://example.com/2"),
        ]
        assert classify_content_batch(results) == ContentOutcome.PARTIAL

    def test_empty_batch_returns_zero_denominator(self):
        assert classify_content_batch([]) == ContentOutcome.ZERO_DENOMINATOR

    def test_all_fetch_failed_returns_all_fetch_failed(self):
        results = [self._make_fetch_failed_result(f"https://example.com/{i}") for i in range(3)]
        assert classify_content_batch(results) == ContentOutcome.ALL_FETCH_FAILED

    def test_mixed_fetch_failed_and_valid(self):
        """Some fetched → outcome based on fetched articles only."""
        results = [
            self._make_fetch_failed_result("https://example.com/1"),
            self._make_valid_result("https://example.com/2"),
        ]
        # 1 fetched, 1 effective → SUCCESS
        assert classify_content_batch(results) == ContentOutcome.SUCCESS

    def test_mixed_fetch_failed_and_parse_failed(self):
        """Some fetched but all parse failed → ALL_FAILED."""
        results = [
            self._make_fetch_failed_result("https://example.com/1"),
            self._make_failed_result("https://example.com/2"),
        ]
        assert classify_content_batch(results) == ContentOutcome.ALL_FAILED

    def test_single_valid_is_success(self):
        results = [self._make_valid_result()]
        assert classify_content_batch(results) == ContentOutcome.SUCCESS

    def test_single_failed_is_all_failed(self):
        results = [self._make_failed_result()]
        assert classify_content_batch(results) == ContentOutcome.ALL_FAILED

    def test_vue_sentinel_content_counts_as_failed(self):
        """Vue extraction failure sentinel is not effective content."""
        vue_fail = ContentExtractionResult(
            outcome="vue_sentinel",
            content_html=SENTINEL_VUE_FAILED,
            visible_word_count=5,
            article_url="https://example.com/vue",
            fetch_failed=False,
        )
        assert classify_content_batch([vue_fail]) == ContentOutcome.ALL_FAILED


# ── ContentExtractionResult.is_effective ──────────────────────────────────────

class TestContentExtractionResultIsEffective:
    """Tests for the is_effective property on ContentExtractionResult."""

    def test_valid_content_is_effective(self):
        r = ContentExtractionResult(
            outcome="success",
            content_html="<p>" + " ".join(["word"] * 25) + "</p>",
            visible_word_count=25,
            article_url="https://example.com/1",
        )
        assert r.is_effective is True

    def test_sentinel_is_not_effective(self):
        r = ContentExtractionResult(
            outcome="parse_sentinel",
            content_html=SENTINEL_PARSE_FAILED,
            visible_word_count=2,
            article_url="https://example.com/2",
        )
        assert r.is_effective is False

    def test_thin_content_not_effective(self):
        r = ContentExtractionResult(
            outcome="success",
            content_html="Loading...",
            visible_word_count=1,
            article_url="https://example.com/3",
        )
        assert r.is_effective is False


# ── FetchResult helpers ───────────────────────────────────────────────────────

class TestFetchResult:
    """Basic smoke tests for FetchResult dataclass."""

    def test_succeeded_property_true(self):
        r = FetchResult(outcome=FetchOutcome.SUCCESS, url="https://example.com")
        assert r.succeeded is True

    def test_succeeded_property_false_on_error(self):
        r = FetchResult(outcome=FetchOutcome.HTTP_ERROR, url="https://example.com", status_code=404)
        assert r.succeeded is False

    def test_all_fields_optional_except_outcome_and_url(self):
        r = FetchResult(outcome=FetchOutcome.TIMEOUT, url="https://example.com/slow")
        assert r.status_code is None
        assert r.page is None
        assert r.html is None
        assert r.error_code is None
        assert r.final_url is None


# ── Sentinel constants ─────────────────────────────────────────────────────────

class TestSentinelConstants:
    """Verify sentinel strings match core/parser.py exactly."""

    def test_parse_failed_sentinel_matches_parser(self):
        """SENTINEL_PARSE_FAILED must exactly match parser.py line 174."""
        assert SENTINEL_PARSE_FAILED == "Parsing failed"

    def test_vue_failed_sentinel_matches_parser(self):
        """SENTINEL_VUE_FAILED must exactly match parser.py line 162."""
        assert SENTINEL_VUE_FAILED == "Vue template extraction failed"

    def test_thresholds_match_decision_freeze(self):
        """Thresholds must match the C0 decision freeze values."""
        assert EFFECTIVE_CONTENT_MIN_WORDS == 20
        assert EFFECTIVE_CONTENT_MIN_NONWS_CHARS == 80
