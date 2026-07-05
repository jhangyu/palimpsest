# Task #7 — Lazy Image Rootcause: Code Review Report

**Reviewer**: review-lazy-image | **Date**: 2026-07-05
**Dimension**: Architecture + Testing (correctness, regressions, scope creep)

---

## Summary

**Verdict: No should-fix findings.** The lazy image normalization is correctly implemented, tests validate the right behavior, and no regressions were introduced. Two low-severity nits and one low concern are recorded below. Missing dependency failures (feedparser, pytest-asyncio) are confirmed environment-only.

---

## Finding 1 [NIT]: Unnecessary Selector reconstruction for pages with <img> tags

**Location**: `backend/core/parser.py:182`
**Severity**: Nit

**Evidence**:
The guard `if normalized_html != raw_html:` is intended to skip Selector reconstruction when no lazy images were modified. However, BeautifulSoup's `str()` always changes self-closing tag format (`<img ...>` → `<img .../>`) and reorders attributes, so the comparison is **always False** for any page containing `<img>` tags — even non-lazy ones with valid `http` src.

Empirically confirmed:
```
Input:  '<article><img src="https://example.com/real.jpg" alt="test">'
Output: '<article><img alt="test" src="https://example.com/real.jpg"/>'
Same:   False  ← BS always alters output when <img> is present
```

For pages **without** `<img>` tags, BS preserves the exact input and the guard correctly avoids reconstruction.

**Impact**: Every article parse that contains images (lazy or not) incurs a full BeautifulSoup parse + Scrapling Selector reconstruction. Negligible performance impact for individual articles (< 1ms for typical article HTML), but wasted work on each request.

**Recommended Fix**: Track whether `_resolve_lazy_images` actually modified anything, or accept the cost:
```python
def normalize_lazy_images_in_html(html: str) -> tuple[str, bool]:
    soup = BeautifulSoup(html, 'html.parser')
    modified = _resolve_lazy_images(soup)  # return bool
    return (str(soup), modified)
```
Or simply always accept the BS parse cost (it is trivially cheap). Either way, not a blocker.

---

## Finding 2 [NIT]: Test script hardcoded machine-specific path

**Location**: `tests/scripts/test_lazy_load.py:7`
**Severity**: Nit (pre-existing)

**Evidence**:
```python
sys.path.insert(0, '/Users/jhangyu/project/palimpsest/backend')
```
Hardcoded absolute path from developer machine. Not introduced by this diff — existed before the lazy image changes.

**Impact**: Script fails when run on any machine other than the original developer's.

**Recommended Fix**: Replace with relative path:
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))
```

---

## Finding 3 [NIT]: Inconsistent import pattern in Test 5

**Location**: `tests/scripts/test_lazy_load.py:147`
**Severity**: Nit

**Evidence**:
Test 5 uses `(result_bs := __import__('bs4').BeautifulSoup(result, 'html.parser'))` while Tests 6-9 use the cleaner `from bs4 import BeautifulSoup as _BS`. No functional difference but inconsistent with neighbors.

**Impact**: Readability only. No functional impact.

**Recommended Fix**: Harmonize Test 5 to match Tests 6-9 pattern.

---

## Finding 4 [LOW]: RSS image_url bypasses sanitize_image_url

**Location**: `backend/core/crawler.py:735-736`
**Severity**: Low

**Evidence**:
The new RSS image_url fallback sets `image_url` directly from `rss_item.image_url` without passing through `sanitize_image_url()`. RSS feed image URLs frequently carry query strings (e.g., `?w=800&h=600`) that `sanitize_image_url` would strip.

**Impact**: Image URLs stored in DB may retain unnecessary query strings from RSS feeds.

**Recommended Fix**: Apply sanitization:
```python
if not image_url and rss_item.image_url:
    image_url = sanitize_image_url(rss_item.image_url)
```

---

## Acceptance Criteria — Status

1. ✅ **Findings include file:line, severity, problem, consequence, fix** — 4 findings above, all with file:line citations.
2. ✅ **Missing dependency failures confirmed environment-only**: `feedparser` declared in `backend/requirements.txt:22` but test venv not synced; `pytest-asyncio` declared nowhere. Neither is caused by lazy image changes.
3. ✅ **Correctness verified for**: `normalize_lazy_images_in_html()` — full pipeline tested with fixture, produces correct image_url; `parse_article` normalization — resolves before selector extraction; RSS fallback — follows existing pattern for date/author; tests — cover all 4 data-* attributes plus priority order.
4. ✅ **No should-fix findings.**
5. ✅ **Files not modified.**
6. ⚠️ **Uncertain/not verified**: The Vue template path I could not fully exercise due to JSON escaping in ad-hoc test construction, but the existing characterization test suite covers it. The normalization does not alter the Vue data path (image comes from `extract_image_from_vue_data()`, not from HTML selectors).

---

## Changed/Reviewed Files

- `backend/core/sanitizer.py` (read)
- `backend/core/parser.py` (read)
- `backend/core/crawler.py` (read lines 715-755)
- `tests/scripts/test_lazy_load.py` (read)
- `tests/stage1/test_crawl_characterization.py` (read)
- `tests/stage1/fixtures/crawl_content_lazy_image.html` (read)
