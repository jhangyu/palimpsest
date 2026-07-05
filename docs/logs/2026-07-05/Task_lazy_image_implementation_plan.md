# Task #3: Lazy-Load Image Implementation Plan

**Date**: 2026-07-05
**Author**: implementer (Task #3)
**Status**: FINAL — cross-referenced with Task #1 (root-cause) and Task #2 (architecture)

---

## Pre-Implementation: Cleanup (Task #1 Residue)

Task #1 created 5 temporary scripts under `scripts/tmp/` during investigation. These are unrelated to the lazy-load feature and should be removed before implementation starts:

- `scripts/tmp/parse_transcript.py`
- `scripts/tmp/write_b64.py`
- `scripts/tmp/write_stdin.py`
- `scripts/tmp/gen_report.py`
- `scripts/tmp/write_report.py`

**Action**: `rm -rf scripts/tmp/` (destructive — confirm before running)

---

## 0. Cross-Reference: Task #1 (Root Cause Report)

**Source**: `docs/logs/2026-07-05/Task_lazy_image_rootcause_debugger.md`

### Confirmed Assumptions

| My Draft Analysis | Task #1 Confirmation | Verdict |
|---|---|---|
| sanitizer's `_resolve_lazy_images` runs on a different DOM object than `page.find(img_selector)` (gap §1.3.1) | "Separated DOM objects: `_resolve_lazy_images` operates on BeautifulSoup(str(body_el)), while parse_article extracts image_url from the raw page root" (§5.1) | ✅ **Confirmed and sharpened** — the lazy resolver is effectively dead code for `content_rules.image` |
| Parser inline fallback duplicates LAZY_SRC_ATTRS (§1.2) | "parser inline data-attribute chain duplicates LAZY_SRC_ATTRS" (§5.2) | ✅ **Confirmed** |
| No JS execution in default Scrapling fetch (risk table) | "Scrapling static HTTP, no JS. Lazy-load placeholders in src are preserved" (§1, §5.3) | ✅ **Confirmed** |
| Playwright may not resolve below-fold lazy images (risk table) | "Even with Playwright, below-fold images may not have triggered Intersection Observer callbacks" (§5.3) | ✅ **Confirmed** |

### Contradicted / Missed

| Finding | Impact on Plan |
|---|---|
| **RSS image_url silently dropped**: When `rss_full_content=False` (Stage 2 path), crawler.py:726-734 uses RSS fallbacks for `pub_date` and `author` but NOT `image_url`. The RSS feed's reliable image is discarded. (§4, §5.4) | New gap not in my draft. Should add RSS `image_url` fallback in crawler.py `fetch_and_save_content()`. Low-risk, follows existing pattern for `pub_date`/`author`. Added to plan §2.5. |

---

## 1. Cross-Reference: Task #2 (Architecture Report) — Discrepancy Resolution

**Source**: `docs/logs/2026-07-05/Task_lazy_image_architecture_mapper.md` + team-lead relay

### Discrepancy

| | My Draft (§2.1) | Task #2 Recommendation |
|---|---|---|
| Normalization insertion point | `parse_article()` in **parser.py:175** (parser layer) | `fetch_page()` in **scraper.py** (fetch layer, "immediately after Scrapling/Playwright fetch") |

### Resolution: parser.py is the correct insertion point

**Reasoning**:

1. **Root cause is a DOM disconnect in parse_article, not a fetch defect.**
   Task #1 proves (§5.1) the problem is that `_resolve_lazy_images` (sanitizer.py:212) runs on `BeautifulSoup(str(body_el))` while `page.find(img_selector)` (parser.py:214) searches the raw page root. Normalizing the page object at `parse_article` entry fixes this exact disconnect. Normalizing in `fetch_page()` would also fix it (both DOMs would be normalized) but is broader than necessary.

2. **Scraper.py insertion breaks the `fetch_page()` return type contract.**
   `fetch_page()` returns a Scrapling Fetcher page object (for scrapling mode) that exposes `.status` and `.body` attributes consumed by `feed_parser.py:323,326`. Normalizing requires extracting HTML, parsing with BeautifulSoup, and re-wrapping as Selector — losing `.status`/`.body` unless these are manually attached via attribute patching. This introduces a fragile abstraction with no benefit for the image extraction fix.

3. **The task spec's "immediately after fetch" means "before any consumer extracts image_url."**
   `parse_article()` is the sole entry point for content extraction. Normalizing at its entry achieves "immediately after fetch" semantics for the affected data path without touching unrelated consumers (`feed_parser.py`, listing HTML paths).

4. **Listing pages don't need image normalization.**
   Normalizing in `fetch_page()` would add a BeautifulSoup parse to every listing page fetch — unnecessary overhead. Listing pages use `fetch_page()` → `parse_listing()` which extracts only URLs and titles, never images.

5. **Belt-and-suspenders already exists.**
   `sanitize_content_html()` already runs `_resolve_and_clean_lazy()` (sanitizer.py:212). After normalizing at `parse_article` entry, this becomes a harmless no-op second pass. The body content is clean regardless of insertion point — the only gap is `content_rules.image` extraction, which `parse_article`-level normalization fixes.

**Bottom line**: parser.py insertion is the minimal fix for the specific defect. Scraper.py would also work but introduces unnecessary complexity, brittleness, and scope creep for no additional benefit.

---

## 2. Current State Summary (Updated with Task #1/#2 Evidence)

### 2.1 Root Cause (from Task #1)

The lazy image resolver (`sanitizer.py:86-93`) operates on `BeautifulSoup(str(body_el))` — a separate DOM from the raw page root where `page.find(img_selector)` (parser.py:214) searches. Resolved `src` values never reach the `content_rules.image` extraction path. The inline fallback chain (parser.py:218-222) duplicates `LAZY_SRC_ATTRS` (sanitizer.py:83) and both are limited to the same 4 attributes.

### 2.2 Data Flow

```
fetch_page() [scraper.py:71]
  → returns Scrapling page object or Selector(html)
  ↓
crawl_site_logic() [crawler.py:318]
  → fetch_and_save_content() [crawler.py:687]
    → parse_article(a_page, content_rules, a_url) [parser.py:163]
      → img_el = page.find(img_selector)  ← RAW page root, NOT the sanitizer's soup
      → image_url extracted from img_el.attrib [parser.py:213-226]
        → _resolve_lazy_images runs on body_el soup only (dead code for image_url)
      → image_url persisted to DB [crawler.py:770,823]
```

### 2.3 RSS Image Gap (from Task #1)

In `crawl_site_logic()` [crawler.py:726-734], when `source_type == "rss"` and `rss_full_content=False`, RSS fallbacks only cover `pub_date` and `author` — `image_url` from the RSS feed is silently discarded. The same fallback pattern should apply to `image_url`.

---

## 3. Proposed Implementation

### 3.1 New Function in `sanitizer.py`

**File**: `backend/core/sanitizer.py` (implementer ownership)

**Add after** `_resolve_lazy_images` (after line 93):

```python
def normalize_lazy_images_in_html(html: str) -> str:
    """Resolve lazy-load image placeholders in raw HTML string.

    Parses HTML with BeautifulSoup, resolves data-* src attributes
    to real URLs via _resolve_lazy_images, and returns the modified HTML.

    Returns original string unchanged if no lazy images found.
    """
    if not html:
        return html
    soup = BeautifulSoup(html, 'html.parser')
    _resolve_lazy_images(soup)
    return str(soup)
```

**Export**: no `__all__` currently in sanitizer.py. Function is accessible via module import. Add `normalize_lazy_images_in_html` to the module docstring function list.

### 3.2 Normalize at `parse_article` Entry (parser.py)

**File**: `backend/core/parser.py` (implementer ownership)

**Change**: add normalization after string-to-Selector conversion, before `is_vue_template` branch.

**Insert after line 175** (`page = Selector(page)` for string input), **before line 178** (`is_vue_template = ...`):

```python
    # Resolve lazy-load image placeholders at parse time so that
    # content_rules.image extraction sees real URLs (Task #1 §5.1:
    # sanitizer's _resolve_lazy_images runs on a separate DOM object
    # and never reaches the page root where we extract image_url).
    raw_html = page.html_content if hasattr(page, 'html_content') else str(page)
    normalized_html = normalize_lazy_images_in_html(raw_html)
    if normalized_html != raw_html:
        page = Selector(normalized_html)
```

**Updated import** at line 38:
```python
from .sanitizer import sanitize_content_html, normalize_lazy_images_in_html
```

### 3.3 RSS Image Fallback (crawler.py)

**File**: `backend/core/crawler.py` (implementer ownership — crawler is assigned to implementer per this task)

**Change**: extend the RSS fallback block at line 728-734 to also fall back `image_url`.

**At line 728-734**, add image_url fallback alongside pub_date and author:

```python
                # RSS fallback: if content rules didn't extract pub_date / author / image_url,
                # use values from the RSS feed item as a fallback.
                if source_type == "rss" and rss_items_by_url:
                    rss_item = rss_items_by_url.get(a_url)
                    if rss_item:
                        if not parsed_date and rss_item.pub_date:
                            pub_date = rss_item.pub_date
                        if not author and rss_item.author:
                            author = rss_item.author
                        if not image_url and rss_item.image_url:
                            image_url = rss_item.image_url  # ← NEW
```

### 3.4 No Changes Needed

| Path | File:Line | Resolution Mechanism | Why No Change |
|---|---|---|---|
| `sanitize_content_html()` | sanitizer.py:212 | `_resolve_and_clean_lazy(soup)` | Already resolves; becomes redundant but harmless second pass |
| `clean_html_for_ai()` | sanitizer.py:330,359 | `_resolve_and_clean_lazy(soup)` | Already resolves |
| `feed_parser.py` data-* preservation | feed_parser.py:30-32 | `acceptable_attributes` | Preserves attrs; no placeholder resolution needed at this layer |
| `fetch_page()` listing calls | scraper.py:90-102 | N/A | Listing pages don't need image normalization |
| `force_refresh_all_articles()` | crawler.py:878-957 | Inherits through `parse_article()` | Fixed transitively |
| `test_crawl_logic()` preview | crawler.py:1017-1091 | Inherits through `parse_article()` | Fixed transitively (though preview discards image_url anyway) |

### 3.5 File Ownership Boundaries (Final)

| File | Owner | Action |
|---|---|---|
| `backend/core/sanitizer.py` | implementer (Task #3) | Add `normalize_lazy_images_in_html()` |
| `backend/core/parser.py` | implementer (Task #3) | Add normalization call at `parse_article()` entry; update import |
| `backend/core/crawler.py` | implementer (Task #3) | Add RSS `image_url` fallback (3-line extension of existing pattern) |
| `backend/core/scraper.py` | **NOT modified** | Decision: parser.py insertion is the correct fix point (see §1) |
| `backend/core/feed_parser.py` | **NOT modified** | Already handles its own layer |

---

## 4. Proposed Tests

### 4.1 New Unit Test: `normalize_lazy_images_in_html`

**Add to**: `tests/scripts/test_lazy_load.py`

```python
def test_normalize_lazy_images_in_html():
    from core.sanitizer import normalize_lazy_images_in_html

    html = '''<article>
      <img src="/images/preimg.png" data-original="https://cdn.example.com/real1.jpg">
      <img src="lazyload.png" data-src="https://cdn.example.com/real2.jpg">
      <img src="placeholder.gif" data-lazy-src="https://cdn.example.com/real3.jpg">
      <img src="blank.png" data-lazy="https://cdn.example.com/real4.jpg">
      <img src="https://cdn.example.com/already-resolved.jpg">
    </article>'''
    result = normalize_lazy_images_in_html(html)

    assert '/images/preimg.png' not in result
    assert 'lazyload.png' not in result
    assert 'placeholder.gif' not in result
    assert 'blank.png' not in result
    assert 'https://cdn.example.com/real1.jpg' in result
    assert 'https://cdn.example.com/real2.jpg' in result
    assert 'https://cdn.example.com/real3.jpg' in result
    assert 'https://cdn.example.com/real4.jpg' in result
    assert 'https://cdn.example.com/already-resolved.jpg' in result
```

### 4.2 Characterization Test: Lazy Image in `content_rules.image`

**File**: `tests/stage1/test_crawl_characterization.py`

**New fixture**: `tests/stage1/fixtures/crawl_content_lazy_image.html`
```html
<!DOCTYPE html>
<html><body>
  <article>
    <h1>Lazy Image Article</h1>
    <div class="article-body">
      <p>Article with lazy-loaded hero image. This paragraph has enough
      text to exceed minimum content thresholds for the parse pipeline.</p>
    </div>
    <img class="article-image" src="/images/preimg.png"
         data-original="https://cdn.example.com/real-hero.jpg" alt="Hero">
  </article>
</body></html>
```

**New test** in `TestContentExtraction` class:
```python
def test_lazy_image_content_rules_resolved(self):
    """parse_article() resolves lazy-load placeholder in content_rules.image
    via HTML normalization at entry point.
    Regression test for Task #3: content_rules.image must see resolved
    data-original URL, not the placeholder src."""
    html = _load_fixture("crawl_content_lazy_image.html")
    page = _make_page(html)
    content_text, pub_date, image_url, author = parse_article(
        page, _CONTENT_RULES, "https://example.com/article/lazy"
    )
    assert image_url == "https://cdn.example.com/real-hero.jpg"
    assert "/images/preimg.png" not in (image_url or "")
    # Body content should still be non-empty (sanitizer path unchanged)
    assert content_text != ""
    assert len(content_text) > 50
```

### 4.3 Existing Tests That Must Still Pass

| Test | Command | Rationale |
|---|---|---|
| `tests/scripts/test_lazy_load.py` | `PYTHONPATH=backend python tests/scripts/test_lazy_load.py` | Existing lazy-load tests must remain green |
| `tests/scripts/test_lazy_load_e2e.py` | `PYTHONPATH=backend python tests/scripts/test_lazy_load_e2e.py` | E2E lazy-load test must still pass |
| `tests/stage1/test_crawl_characterization.py` | `PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_crawl_characterization.py -v` | All 12 existing characterization tests — MUST NOT regress |
| `tests/stage1/test_site_rss.py` | `PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_site_rss.py -v` | RSS tests, especially RC-08 sanitization |

---

## 5. Test Commands to Run

```bash
# 1. Existing lazy-load tests
PYTHONPATH=backend python tests/scripts/test_lazy_load.py

# 2. Characterization tests (pins current parser behavior + new lazy test)
PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_crawl_characterization.py -v

# 3. RSS full suite
PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_site_rss.py -v

# 4. Full stage1 test suite (safety net)
PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/ -v --timeout=60
```

---

## 6. Risk / Rollback Notes

### 6.1 Behavior Compatibility

| Concern | Assessment | Mitigation |
|---|---|---|
| **Sanitizer double-resolution** | `_resolve_lazy_images` checks `img.get('src')` and only overwrites if data-* attr exists — idempotent. Second pass is no-op when src already resolved. | No risk |
| **Feed parser path** | RSS content path uses `sanitize_content_html()` which already resolves lazy images. No change. | No risk |
| **Vue template path** | `is_vue_template=True` [parser.py:184-198] calls `sanitize_content_html(vue_html)` which already resolves. Normalization at entry is redundant but harmless (Vue html content has no lazy attrs to resolve). | No risk |
| **RSS image fallback** | Follows existing pattern for `pub_date`/`author` fallback (same block, same conditional). Only fills `image_url` when `not image_url`. | No risk |
| **`srcset` / `data-srcset`** | Not handled by `_resolve_lazy_images` or existing fallback. Out of scope. | Known limitation — see §7 Q1 |
| **JS-dependent lazy load** | Playwright may not trigger Intersection Observer for below-fold images. Static Scrapling never executes JS. | Accept residual risk; secondary defense via inline fallback + RSS fallback |

### 6.2 Rollback Procedure

1. Revert `parser.py` — remove normalization block (lines 176-182 area) and revert import
2. Revert `crawler.py` — remove `image_url` fallback line
3. `normalize_lazy_images_in_html()` in `sanitizer.py` can remain (additive, unused)
4. Run characterization tests to confirm baseline restored

### 6.3 Performance Impact

- One additional BeautifulSoup parse per article page (~5ms for 10-50KB HTML)
- Negligible vs network fetch (500ms-5s)
- `normalize_lazy_images_in_html` short-circuits on empty input
- RSS `image_url` fallback: single attribute assignment, zero cost

---

## 7. Unresolved Questions

### User Decisions (require user input)

1. **`srcset` / `data-srcset` support**: Some sites use `srcset` or `data-srcset` for responsive lazy loading. Currently neither `_resolve_lazy_images` nor `parse_article` handle these attributes. Should the lazy-load resolver also normalize `srcset`/`data-srcset`, or is `src`-only sufficient for the `content_rules.image` extraction use case? (The task only mentions `src` resolution.)

### Code-Convention-Inferable (recommended decisions, no user input needed)

2. **~~Scrapling `.attrib` behavior~~** → RESOLVED by Task #1. `.attrib` preserves data-* attrs, but the DOM separation makes inline fallback insufficient on its own. Normalization at HTML level is the correct fix regardless of `.attrib` behavior. Keep inline fallback as defense-in-depth.

3. **~~Insertion point: parser vs scraper~~** → RESOLVED in §1. parser.py is the correct insertion point. Scraper.py would require attribute patching for `.status`/`.body` and would add unnecessary BeautifulSoup parsing to listing page fetches.

4. **RSS image_url fallback scope**: Should the RSS fallback also apply on the `rss_full_content=True` path? Currently `rss_full_content=True` uses `rss_item.image_url` directly (crawler.py:468,488) — this is correct and needs no change. The fallback only applies to `rss_full_content=False` (Stage 2 HTML scraping), matching the existing `pub_date`/`author` pattern. → Code-convention-inferable: follow existing pattern exactly.

---

## 8. Summary of Changes from Draft

| Change | Trigger |
|---|---|
| Added cross-reference sections (§0, §1) confirming Task #1 findings and resolving scraper.py vs parser.py discrepancy | Task #1 and #2 reports |
| Added RSS `image_url` fallback (§3.3) to `crawler.py` | Task #1 §4, §5.4 — RSS image silently dropped |
| Updated file ownership to include `crawler.py` (§3.5) | RSS fallback addition |
| Added characterization test fixture + test (§4.2) | New lazy image behavior to pin |
| Re-categorized unresolved questions (§7): 1 user decision, 3 code-convention-inferable | Team-lead instruction |
| Added `test_site_rss.py` full suite to test commands (§5) | RSS fallback change |
