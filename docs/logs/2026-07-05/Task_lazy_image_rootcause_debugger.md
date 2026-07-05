# Task #1: content_rules.image lazyload.png root-cause investigation

## 1. Fetch sources providing raw HTML/page content

| Source | File:Line | Method | JS Exec? |
|---|---|---|---|
| Scrapling (default) | scraper.py:67 (_fetch_scrapling_sync:60-68) | Fetcher.get() static HTTP, no JS | **No** |
| Playwright CDP | crawler.py:278-285 (get_page_content_on_page:290-315) | Remote Chrome via CDP, JS enabled | Yes |
| Playwright local | crawler.py:260-271 (get_page_content_on_page:290-315) | Local Chromium, JS enabled | Yes |
| RSS feed | feed_parser.py:296-301 via scraper.py | Fetcher.get(), no JS | **No** |

Key: Default scrape_method=scrapling uses static HTTP; lazy-load placeholders
in src are preserved. Playwright runs JS but page.content() (crawler.py:315)
returns DOM at scroll position; lazy images below the fold may still show
placeholders unless Intersection Observer callbacks have fired.

## 2. content_rules.image evaluation -- how image src is chosen

Critical code: parse_article() at **parser.py:213-226**

    img_selector = normalize_selector(content_rules.get("image", "")) or "img"
    img_el = page.find(img_selector)    # searches RAW page root
    if img_el:
        raw_src = img_el.attrib.get("src", "")
        image_url = (
            (raw_src if raw_src.startswith("http") else "")   # (1) src if absolute
            or img_el.attrib.get("data-original", "")           # (2) fallback chain
            or img_el.attrib.get("data-src", "")
            or img_el.attrib.get("data-lazy-src", "")
            or img_el.attrib.get("data-lazy", "")
            or raw_src                                           # (3) placeholder
        )
        if image_url and not image_url.startswith("http"):
            image_url = urljoin(article_url, image_url)

Decision chain: absolute http src -> 4 data-* attrs -> raw src (placeholder).
When NO data-* attr matches and src is a relative/lazy placeholder (lazyload.png,
data:image/gif;base64,..., 1x1.gif), the fallback hits "or raw_src" returning the
placeholder. Non-http values are urljoin"d -> bogus absolute URL.
Default selector is "img" (first <img> on entire page, not scoped to body).

## 3. Existing lazy-load resolution: timing and insufficiency

### Designated resolver: _resolve_lazy_images() at sanitizer.py:86-93

LAZY_SRC_ATTRS = ("data-original", "data-src", "data-lazy-src", "data-lazy")  # sanitizer.py:83

_resolve_lazy_images: for each img, copies first matching data-* http value to src.
Called only from _resolve_and_clean_lazy() (sanitizer.py:125-131):
  - sanitize_content_html() at sanitizer.py:212 -- body text sanitization
  - clean_html_for_ai() content mode at sanitizer.py:330 -- LLM prep
  - clean_html_for_ai() list mode at sanitizer.py:359 -- LLM prep

### Why too late / insufficient for content_rules.image

Execution order in parse_article() (parser.py:199-226):
  1. body_el = page.find(body_selector)                    # parser.py:201
  2. content_text = sanitize_content_html(str(body_el))     # parser.py:203
       L _resolve_and_clean_lazy() runs HERE              # sanitizer.py:212
       L Modifies img src in body_el soup ONLY
  3. img_el = page.find(img_selector)                      # parser.py:214 (RAW page root!)
  4. image_url = extract from img_el.attrib[src]           # parser.py:216-226

_resolve_lazy_images operates on BeautifulSoup(str(body_el)) -- a DIFFERENT
DOM object than the page root where page.find(img_selector) searches.
Resolved src values NEVER reach the image_url extraction. The lazy resolver is
effectively dead code for content_rules.image.

The parser inline fallback (parser.py:218-222) is a DUPLICATE of LAZY_SRC_ATTRS.
Currently they match (4 attrs) but additions to LAZY_SRC_ATTRS wont auto-benefit
image extraction. When no data attr matches, or raw_src (parser.py:223) returns
the placeholder.

## 4. Image persistence into article records / RSS

image_url from parse_article() written directly to DB in crawler.py:
  - crawler.py:823 -- new article insert (scheduled crawl)
  - crawler.py:778 -- new article insert (force update)
  - crawler.py:803 -- article update (content changed)
  - crawler.py:945 -- force refresh all articles
  - crawler.py:468,488 -- RSS full-content (from feed directly)
DB schema: db.py:88 -- image_url nullable String on articles table.

RSS gap: when rss_full_content=False (Stage 2), crawler.py:726-734 only uses
RSS fallbacks for pub_date and author, NOT image_url. The RSS feeds reliable
image is silently discarded.

## 5. Root cause (conclusion)

1. Separated DOM objects: _resolve_lazy_images (sanitizer.py:86) operates on
   BeautifulSoup(str(body_el)), while parse_article extracts image_url from the
   raw page root via page.find() (parser.py:214). Resolved src values never reach
   the image extraction path. The lazy resolver is effectively dead code for
   content_rules.image.

2. Duplicate and fragile fallback: parser inline data-attribute chain
   (parser.py:218-222) duplicates LAZY_SRC_ATTRS (sanitizer.py:83). When a site
   uses an attribute outside this hardcoded set (data-image, srcset, data-echo,
   JS-computed URLs) or has no data attr at all, the chain exhausts and returns
   the placeholder via or raw_src (parser.py:223).

3. No JS execution in default fetch: scraper.py:67 uses Fetcher.get() for static
   HTML. Lazy-load placeholders in src are preserved. Even with Playwright
   (crawler.py:290-315), below-fold images may not have triggered Intersection
   Observer callbacks, so page.content() still shows placeholder src.

4. RSS image_url silently dropped: When rss_full_content=False (crawler.py:726-734),
   the RSS feed image_url is not used as a fallback (only pub_date/author are).
