# backend/core/crawler.py
"""
---
name: crawler
description: "Core crawl engine: Scrapling/Playwright page fetching, article extraction, DB persistence with force-update and filter support, and dry-run preview mode"
type: core
target:
  layer: backend
  domain: crawl
spec_doc: null
test_file: tests/stage1/test_crawl_characterization.py
functions:
  - name: _get_http_client
    line: 36
    purpose: "Lazily create and return shared httpx AsyncClient singleton (PERF-008)"
  - name: _utcnow_iso
    line: 54
    purpose: "Return current UTC time as timezone-aware ISO string"
  - name: _parse_pub_date
    line: 59
    purpose: "Convert raw date string or datetime to timezone-aware datetime"
  - name: compute_visible_word_count
    line: 73
    purpose: "Compute visible word count from HTML; CJK chars counted individually"
  - name: _require_playwright
    line: 169
    purpose: "Lazy-import playwright for CHROME_MODE=local; raises clear error if missing"
  - name: get_page_content
    line: 181
    purpose: "Render URL via remote Chrome (CDP) or local Playwright; returns HTML string"
  - name: get_page_content_on_page
    line: 244
    purpose: "Execute page navigation and content extraction on a given Page object"
  - name: crawl_site_logic
    line: 272
    purpose: "Full crawl: fetch listing, extract articles, persist to DB with auto-repair trigger"
  - name: test_crawl_logic
    line: 625
    purpose: "Dry-run preview crawl returning article list + filter summary; no DB writes"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
import os
import re
import asyncio
import json
import httpx
from datetime import datetime, timezone
from hashlib import md5

from sqlalchemy import select, text

from core.db import sites, articles
from core.scraper import fetch_page
from core.parser import parse_listing, parse_article, normalize_selector
from core.filter_engine import apply_filter
from core.sanitizer import sanitize_content_html
from core.feed_parser import fetch_and_parse_feed, FeedParseError


def log_with_time(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def url_hash(url: str) -> str:
    return md5(url.encode()).hexdigest()[:8]

CHROME_WS = os.getenv("CHROME_WS_ENDPOINT", "ws://chrome:3000")
FAILURE_THRESHOLD = 3  # 連續失敗次數數閾值，觸發自動修復

# 完整的現代 Chrome User-Agent（避免被 WAF 如 Akamai 阻擋）
MODERN_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# --- PERF-008: Module-level HTTP client singleton for connection reuse ---
_HTTP_CLIENT: httpx.AsyncClient | None = None

def _get_http_client() -> httpx.AsyncClient:
    """Return (or lazily create) the shared httpx AsyncClient for crawl session reuse."""
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=20),
            headers={"User-Agent": MODERN_CHROME_UA},
        )
    return _HTTP_CLIENT

# --- DPERF-014 + PERF-011: Compiled regex for HTML stripping (~10x faster than BS4) ---
_SCRIPT_RE = re.compile(r'<(script|style|template|noscript)\b[^>]*>.*?</\1>', re.S | re.I)
_TAG_RE = re.compile(r'<[^>]+>')

# --- Shared Helpers ---
# These are the canonical definitions. main.py imports them from here.

def _utcnow_iso() -> str:
    """Return current UTC time as timezone-aware ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _parse_pub_date(raw) -> datetime:
    """Convert a date string to timezone-aware datetime. Returns utcnow on failure."""
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if not raw or not isinstance(raw, str):
        return datetime.now(timezone.utc)
    try:
        from dateutil.parser import parse as dateutil_parse
        dt = dateutil_parse(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def compute_visible_word_count(content: str) -> int:
    """Compute visible word count from HTML content.

    Single shared implementation used by both crawler insert/update and main.py backfill.
    Strips HTML tags, script/style/template elements.
    CJK characters are counted individually; English tokens counted by whitespace split.
    """
    if not content:
        return 0
    # Strip script/style/template/noscript blocks first, then all remaining HTML tags.
    # Regex approach is ~10x faster than BeautifulSoup and avoids parser overhead.
    text_content = _SCRIPT_RE.sub('', content)
    text_content = _TAG_RE.sub(' ', text_content)
    text_content = text_content.strip()
    if not text_content:
        return 0

    count = 0
    buf = []  # buffer for non-CJK tokens

    for ch in text_content:
        cp = ord(ch)
        is_cjk = (
            (0x4E00 <= cp <= 0x9FFF) or    # CJK Unified Ideographs
            (0x3400 <= cp <= 0x4DBF) or    # CJK Extension A
            (0xF900 <= cp <= 0xFAFF) or    # CJK Compatibility Ideographs
            (0xAC00 <= cp <= 0xD7AF) or    # Hangul Syllables
            (0x3040 <= cp <= 0x309F) or    # Hiragana
            (0x30A0 <= cp <= 0x30FF)       # Katakana
        )
        is_cjk_punct = (
            (0x3000 <= cp <= 0x303F) or    # CJK Symbols and Punctuation
            (0xFF00 <= cp <= 0xFF0F) or    # Fullwidth digits/symbols
            (0xFF1A <= cp <= 0xFF20) or    # Fullwidth punctuation
            (0xFF3B <= cp <= 0xFF40) or
            (0xFF5B <= cp <= 0xFF65)
        )
        if is_cjk and not is_cjk_punct:
            # Flush English buffer
            if buf:
                token = "".join(buf).strip()
                if token:
                    count += len(token.split())
                buf = []
            count += 1
        elif is_cjk_punct:
            # Flush English buffer but don't count punctuation
            if buf:
                token = "".join(buf).strip()
                if token:
                    count += len(token.split())
                buf = []
        else:
            buf.append(ch)

    # Flush remaining English buffer
    if buf:
        token = "".join(buf).strip()
        if token:
            count += len(token.split())

    return count



# Shared context settings — same keyword names work for both CDPBrowser and Playwright
_BROWSER_CONTEXT_SETTINGS = {
    "user_agent": MODERN_CHROME_UA,
    "viewport": {"width": 1920, "height": 1080},
    "locale": "zh-TW",
    "timezone_id": "Asia/Taipei",
    "extra_http_headers": {
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
    },
}

# Args for local Playwright Chromium launch (anti-detection)
_LOCAL_CHROME_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
]


def _require_playwright():
    """Lazy-import playwright for CHROME_MODE=local. Raises clear error if not installed."""
    try:
        from playwright.async_api import async_playwright
        return async_playwright
    except ImportError:
        raise RuntimeError(
            "CHROME_MODE=local requires playwright. "
            "Install it with: pip install playwright && playwright install chromium"
        )


async def get_page_content(url: str, wait_for_selector: str | None = None, browser=None, fast_mode=False) -> str:
    """連線到遠端 Chrome (Browserless) 取得渲染後的 HTML

    Args:
        url: 目標網址
        wait_for_selector: 可選，等待特定元素出現後再取得 HTML
        browser: 可選，重用現有的 browser 實例 (CDPBrowser or Playwright Browser)
        fast_mode: 預覽模式，縮短等待時間

    Browser selection:
        - CHROME_MODE=server (default/production): lightweight CDP client → remote Chrome
        - CHROME_MODE=local (dev): playwright → local Chromium (requires pip install playwright)
    """
    import time
    start_ts = time.time()

    # Reuse existing browser instance (works for both CDP and Playwright browsers)
    if browser:
        context = await browser.new_context(**_BROWSER_CONTEXT_SETTINGS)
        page = await context.new_page()
        try:
            content = await get_page_content_on_page(page, url, wait_for_selector, fast_mode)
            await page.close()
            await context.close()
            return content
        except Exception as e:
            log_with_time(f"[Crawler] Error in reused browser for {url}: {e}")
            return ""

    mode = os.getenv("CHROME_MODE", "server")

    if mode == "local":
        # Local dev mode: use playwright to launch local Chromium
        async_playwright = _require_playwright()
        async with async_playwright() as p:
            try:
                browser_obj = await p.chromium.launch(
                    headless=True, args=_LOCAL_CHROME_ARGS,
                )
                context = await browser_obj.new_context(**_BROWSER_CONTEXT_SETTINGS)
                page = await context.new_page()
                content = await get_page_content_on_page(page, url, wait_for_selector, fast_mode)
                await browser_obj.close()
                log_with_time(f"[Crawler] Fetched {url} in {time.time() - start_ts:.2f}s (local)")
                return content
            except Exception as e:
                log_with_time(f"[Crawler] Error fetching {url}: {e}")
                return ""
    else:
        # Server/production mode: lightweight CDP client → remote Chrome (browserless)
        try:
            from core.cdp_client import CDPBrowser
            browser_obj = await CDPBrowser.connect(CHROME_WS)
            context = await browser_obj.new_context(**_BROWSER_CONTEXT_SETTINGS)
            page = await context.new_page()
            content = await get_page_content_on_page(page, url, wait_for_selector, fast_mode)
            await browser_obj.close()
            log_with_time(f"[Crawler] Fetched {url} in {time.time() - start_ts:.2f}s")
            return content
        except Exception as e:
            log_with_time(f"[Crawler] Error fetching {url}: {e}")
            return ""

async def get_page_content_on_page(page, url, wait_for_selector=None, fast_mode=False):
    """在給定的 Page 對象上執行抓取動作"""
    # 預覽模式下縮短超時
    page_timeout = 20000 if fast_mode else 60000
    idle_timeout = 3000 if fast_mode else 15000

    await page.goto(url, timeout=page_timeout, wait_until="domcontentloaded")

    # 等待網路閒置
    try:
        await page.wait_for_load_state("networkidle", timeout=idle_timeout)
    except Exception as e:
        if not fast_mode: # 預覽模式下超時很正常，不特別 log
            log_with_time(f"[Crawler] Network idle timeout, continuing...: {e}")

    if wait_for_selector:
        try:
            await page.wait_for_selector(wait_for_selector, timeout=5000 if fast_mode else 10000)
        except TimeoutError:
            pass

    # 預覽模式下減少額外等待
    if not fast_mode:
        await asyncio.sleep(2)

    return await page.content()


async def crawl_site_logic(
    site_id: int,
    url: str,
    list_rules: dict,
    content_rules: dict,
    db,
    debug_writer=None,
    force_update: bool = False,
    scrape_method: str = "scrapling",
    owner_user_id=None,
    ai_tables=None,
    kek_backend=None,
    filter_rules: dict | None = None,
    source_type: str = "html",
    rss_full_content: bool = False,
    skip_empty_content: bool = False,
):
    """
    爬取網站邏輯，包含自動修復機制 (Scrapling 兩階段流程)

    Args:
        force_update: 如果為 True，即使 URL 已存在也會用最新內容覆蓋（手動重爬模式）
                      如果為 False，會比對 published_at，只插入時間改變的文章（排程模式）
        scrape_method: 抓取方式，'scrapling'（預設）或 'playwright'
        source_type: 'html' (default) or 'rss' — controls which Stage 1 path is taken
        rss_full_content: When True and source_type='rss', use RSS content directly
                          (skip Stage 2 page fetching)

    Returns:
        dict with keys: status, articles_found, articles_saved, articles_updated,
        articles_failed, content_fetch_failed, parse_failed, error_message
    """
    _compute_wc = compute_visible_word_count
    _utc_now = lambda: datetime.now(timezone.utc)

    result = {
        "status": "success",
        "articles_found": 0,
        "articles_saved": 0,
        "articles_updated": 0,
        "articles_failed": 0,
        "articles_filtered": 0,
        "content_fetch_failed": 0,
        "parse_failed": 0,
        "error_message": None,
    }

    try:
        log_with_time(f"[Crawl] >>>>>>>> Starting crawl for site {site_id}: {url}")

        # articles_found and rss_items_by_url are populated by the appropriate
        # Stage 1 path (RSS or HTML) and then consumed by the common Stage 2 code.
        articles_found = []
        rss_items_by_url: dict = {}  # populated in RSS non-full-content path for fallback

        # ── RSS branch: replaces HTML Stage 1 (fetch_page + parse_listing) ──────
        if source_type == "rss":
            try:
                feed_result = await fetch_and_parse_feed(url)
            except FeedParseError as e:
                log_with_time(f"[Crawl] RSS feed parse failed for site {site_id}: {e}")
                result["status"] = "fail"
                result["error_message"] = str(e)
                return result

            # Store website_url from feed-level metadata on the first crawl
            # (only updates when website_url is currently NULL to avoid overwriting
            #  a manually-set value).
            if feed_result.feed_link:
                try:
                    await db.execute(
                        text(
                            "UPDATE sites SET website_url = :wu "
                            "WHERE id = :sid AND website_url IS NULL"
                        ),
                        {"wu": feed_result.feed_link, "sid": site_id},
                    )
                    await db.commit()
                except Exception as _wu_err:
                    log_with_time(
                        f"[Crawl] Warning: could not store website_url for site {site_id}: {_wu_err}"
                    )
                    try:
                        await db.rollback()
                    except Exception:
                        pass

            rss_article_links = [
                {"url": item.url, "title": item.title} for item in feed_result.items
            ]
            rss_items_by_url = {item.url: item for item in feed_result.items}
            result["articles_found"] = len(rss_article_links)

            if rss_full_content:
                # ── Full-content mode: batch dedup → sanitize → insert ────────────
                article_urls = [a["url"] for a in rss_article_links]
                if not force_update and article_urls:
                    existing_res = await db.execute(
                        text("SELECT url FROM articles WHERE url = ANY(:urls)"),
                        {"urls": article_urls},
                    )
                    existing_urls = {row[0] for row in existing_res}
                    rss_article_links = [
                        a for a in rss_article_links if a["url"] not in existing_urls
                    ]

                now_utc = _utc_now()
                for link_info in rss_article_links:
                    rss_item = rss_items_by_url[link_info["url"]]
                    # Pre-strip script/style/iframe before sanitizing so that
                    # their inner text (e.g. alert('xss')) is removed entirely.
                    _raw = _SCRIPT_RE.sub('', rss_item.content) if rss_item.content else ""
                    _raw = re.sub(r'<iframe\b[^>]*>.*?</iframe>', '', _raw, flags=re.S | re.I)
                    content_html = sanitize_content_html(_raw) if _raw else ""
                    word_count = _compute_wc(content_html)
                    pub_date = (
                        _parse_pub_date(rss_item.pub_date) if rss_item.pub_date else _utc_now()
                    )

                    try:
                        if force_update:
                            if skip_empty_content and not (content_html or "").strip():
                                log_with_time(f"[Crawl] Force refresh skipped (empty content): {rss_item.url[:50]}")
                                continue
                            # INSERT OR UPDATE — preserve created_at on conflict
                            await db.execute(
                                text("""
                                    INSERT INTO articles
                                        (site_id, title, url, content, image_url,
                                         published_at, created_at, updated_at,
                                         word_count, author)
                                    VALUES
                                        (:sid, :title, :url, :content, :image_url,
                                         :pub_date, :created_at, :updated_at,
                                         :word_count, :author)
                                    ON CONFLICT (url) DO UPDATE SET
                                        site_id = :sid,
                                        title = :title,
                                        content = :content,
                                        image_url = :image_url,
                                        published_at = :pub_date,
                                        updated_at = :updated_at,
                                        word_count = :word_count,
                                        author = :author
                                """),
                                {
                                    "sid": site_id,
                                    "title": rss_item.title,
                                    "url": rss_item.url,
                                    "content": content_html,
                                    "image_url": rss_item.image_url,
                                    "pub_date": pub_date,
                                    "created_at": now_utc,
                                    "updated_at": now_utc,
                                    "word_count": word_count,
                                    "author": rss_item.author,
                                },
                            )
                            await db.commit()
                            log_with_time(
                                f"[Crawl] RSS full-content force updated: {rss_item.title[:30]}..."
                            )
                            result["articles_updated"] += 1
                        else:
                            await db.execute(
                                articles.insert().values(
                                    site_id=site_id,
                                    title=rss_item.title,
                                    url=rss_item.url,
                                    content=content_html,
                                    image_url=rss_item.image_url,
                                    author=rss_item.author,
                                    published_at=pub_date,
                                    created_at=now_utc,
                                    updated_at=now_utc,
                                    word_count=word_count,
                                )
                            )
                            await db.commit()
                            log_with_time(
                                f"[Crawl] RSS full-content saved: {rss_item.title[:30]}..."
                            )
                            result["articles_saved"] += 1
                    except Exception as db_err:
                        log_with_time(
                            f"[Crawl] DB error saving RSS article {rss_item.url}: {db_err}"
                        )
                        try:
                            await db.rollback()
                        except Exception:
                            pass
                        result["articles_failed"] += 1

                log_with_time(
                    f"[Crawl] RSS full-content completed for site {site_id}: "
                    f"saved={result['articles_saved']}, updated={result['articles_updated']}"
                )
                return result

            else:
                # ── Non-full-content mode: use RSS items as article list ───────────
                # rss_items_by_url is populated above and accessible in the Stage 2
                # fetch_and_save_content closure for pub_date/author fallback.
                articles_found = rss_article_links

                # Reset consecutive failure count: feed was successfully fetched
                await db.execute(
                    sites.update()
                    .where(sites.c.id == site_id)
                    .values(consecutive_failure_count=0)
                )
                await db.commit()

                if not articles_found:
                    return result

        else:
            # ── HTML path: existing Stage 1 code (fetch_page + parse_listing) ────
            page = await fetch_page(url, method=scrape_method, fallback_playwright=True)
            if page is None:
                log_with_time(f"[Crawl] Failed to get page for site {site_id}")
                result["status"] = "fail"
                result["error_message"] = "Failed to fetch listing page"
                return result

            if debug_writer is not None:
                debug_writer.save("01", "list_raw_html.html", page.html_content or "")

            # 解析文章列表
            articles_found = parse_listing(page, list_rules, url)
            result["articles_found"] = len(articles_found)

            # 自動修復邏輯
            if len(articles_found) == 0:
                log_with_time(
                    f"[Crawl] Warning: No items found for site {site_id}. Rules might be broken."
                )
                row = (await db.execute(
                    select(sites.c.consecutive_failure_count)
                    .where(sites.c.id == site_id)
                )).mappings().first()
                current_count = row['consecutive_failure_count'] if row else 0
                new_count = current_count + 1
                await db.execute(
                    sites.update()
                    .where(sites.c.id == site_id)
                    .values(consecutive_failure_count=new_count)
                )
                await db.commit()

                if new_count >= FAILURE_THRESHOLD:
                    if owner_user_id is not None and ai_tables is not None and kek_backend is not None:
                        from core.ai import analyze_with_providers
                        try:
                            new_list_rules = await analyze_with_providers(
                                page.html_content or "", "list",
                                user_id=owner_user_id, db=db,
                                tables=ai_tables, kek_backend=kek_backend,
                            )
                        except Exception:
                            new_list_rules = {}
                    else:
                        log_with_time(
                            f"[Crawl] Skipping auto-repair for site {site_id}: no owner context available"
                        )
                        new_list_rules = {}
                    if new_list_rules and "item" in new_list_rules:
                        await db.execute(
                            sites.update()
                            .where(sites.c.id == site_id)
                            .values(list_rules=json.dumps(new_list_rules), consecutive_failure_count=0)
                        )
                        await db.commit()
                        list_rules = new_list_rules
                        articles_found = parse_listing(page, list_rules, url)
                        result["articles_found"] = len(articles_found)

                if len(articles_found) == 0:
                    return result
            else:
                await db.execute(
                    sites.update()
                    .where(sites.c.id == site_id)
                    .values(consecutive_failure_count=0)
                )
                await db.commit()

        # ── Common path: dedup + Stage 1 filter + Stage 2 ───────────────────────
        # PERF-005: Batch existence check — one query instead of N individual queries
        if force_update:
            articles_to_crawl = list(articles_found)
        else:
            discovered_urls = [a['url'] for a in articles_found]
            if discovered_urls:
                rows = (await db.execute(
                    text("SELECT url FROM articles WHERE url = ANY(:urls)"),
                    {"urls": discovered_urls}
                )).mappings().all()
                existing_url_set = {row['url'] for row in rows}
            else:
                existing_url_set = set()
            articles_to_crawl = [a for a in articles_found if a['url'] not in existing_url_set]

        # Stage 1 Filter: apply title-based filter before content fetch
        if filter_rules and articles_to_crawl:
            try:
                before_count = len(articles_to_crawl)
                articles_to_crawl, _ = apply_filter(
                    articles_to_crawl, filter_rules,
                    available_fields=['title']
                )
                stage1_filtered = before_count - len(articles_to_crawl)
                result["articles_filtered"] += stage1_filtered
                if stage1_filtered > 0:
                    log_with_time(f"[Crawl] Stage 1 filter removed {stage1_filtered} articles (title-only)")
            except Exception as e:
                log_with_time(f"[Crawl] filter_rules error at Stage 1, skipping: {e}")

        log_with_time(
            f"[Crawl] Found {len(articles_to_crawl)} articles to crawl for site {site_id} "
            f"(force_update={force_update})"
        )

        if debug_writer is not None:
            debug_writer.save("02", "list_items.json", json.dumps(articles_to_crawl, ensure_ascii=False, indent=2))

        if not articles_to_crawl:
            return result

        # Stage 2: 並行抓取內文 (控制併發)
        # PERF-009: Launch a single shared browser for the entire crawl session.
        # Each article will create a new page/context rather than a new browser process.
        _shared_browser = None
        _pw_ctx = None  # Only used for CHROME_MODE=local playwright cleanup
        if scrape_method == "playwright":
            mode = os.getenv("CHROME_MODE", "server")
            if mode == "local":
                # Local dev: use playwright for shared browser
                try:
                    async_playwright = _require_playwright()
                    _pw_ctx = async_playwright()
                    _pw = await _pw_ctx.__aenter__()
                    _shared_browser = await _pw.chromium.launch(
                        headless=True, args=_LOCAL_CHROME_ARGS,
                    )
                    log_with_time(f"[Crawl] Shared Playwright browser ready for site {site_id} (local)")
                except Exception as br_err:
                    log_with_time(f"[Crawl] Failed to launch shared browser: {br_err}, falling back to per-article browser")
                    if _pw_ctx is not None:
                        try:
                            await _pw_ctx.__aexit__(None, None, None)
                        except Exception:
                            pass
                    _shared_browser = None
                    _pw_ctx = None
            else:
                # Server/production: use CDP client for shared browser
                try:
                    from core.cdp_client import CDPBrowser
                    _shared_browser = await CDPBrowser.connect(CHROME_WS)
                    log_with_time(f"[Crawl] Shared CDP browser ready for site {site_id}")
                except Exception as br_err:
                    log_with_time(f"[Crawl] Failed to launch shared browser: {br_err}, falling back to per-article browser")
                    _shared_browser = None

        semaphore = asyncio.Semaphore(3)
        _db_lock = asyncio.Lock()
        crawl_results = []

        async def fetch_and_save_content(article: dict):
            async with semaphore:
                a_url = article['url']
                title = article['title']
                uhash = url_hash(a_url)

                # PERF-008 / PERF-009: Reuse session-level browser or HTTP client.
                # CDP: use shared browser (new page per article, not new browser).
                # Scrapling: fetch_page manages its own connection; _get_http_client() is
                # available for any direct HTTP calls added in future.
                if scrape_method == "playwright" and _shared_browser is not None:
                    from scrapling.parser import Selector
                    _html = await get_page_content(a_url, browser=_shared_browser)
                    a_page = Selector(_html) if _html else None
                    a_page_html = _html or ""
                else:
                    a_page = await fetch_page(a_url, method=scrape_method, fallback_playwright=True)
                    a_page_html = getattr(a_page, 'html_content', '') if a_page is not None else ""

                if a_page is None:
                    result["content_fetch_failed"] += 1
                    result["articles_failed"] += 1
                    return

                if debug_writer is not None:
                    debug_writer.save(f"03_article_raw_{uhash}", "raw.html", a_page_html or "")

                pub_date = datetime.now(timezone.utc)
                try:
                    content_text, parsed_date, image_url, author = parse_article(a_page, content_rules, a_url)
                except Exception as parse_err:
                    log_with_time(f"[Crawl] Parse error for {a_url}: {parse_err}")
                    result["parse_failed"] += 1
                    result["articles_failed"] += 1
                    return

                if parsed_date:
                    pub_date = parsed_date

                # RSS fallback: if content rules didn't extract pub_date / author,
                # use values from the RSS feed item as a fallback.
                if source_type == "rss" and rss_items_by_url:
                    rss_item = rss_items_by_url.get(a_url)
                    if rss_item:
                        if not parsed_date and rss_item.pub_date:
                            pub_date = rss_item.pub_date
                        if not author and rss_item.author:
                            author = rss_item.author

                pub_date = _parse_pub_date(pub_date)

                # Stage 2 Filter: apply full filter (title + content) before DB write
                if filter_rules:
                    try:
                        article_data = {"title": title, "content": content_text}
                        _, stage2_filtered = apply_filter(
                            [article_data], filter_rules,
                            available_fields=['title', 'content']
                        )
                        if stage2_filtered:
                            result["articles_filtered"] += 1
                            log_with_time(f"[Crawl] Stage 2 filter excluded: {title[:30]}...")
                            return
                    except Exception as e:
                        log_with_time(f"[Crawl] filter_rules error at Stage 2, skipping: {e}")

                # Compute word count
                wc = _compute_wc(content_text)
                now_utc = _utc_now()

                if debug_writer is not None:
                    debug_writer.save(f"03_article_cleaned_{uhash}", "cleaned.html", content_text[:5000])

                async with _db_lock:
                    try:
                        if force_update:
                            if skip_empty_content and not (content_text or "").strip():
                                log_with_time(f"[Crawl] Force refresh skipped (empty content): {a_url[:50]}")
                                return
                            # 手動重爬模式：INSERT OR UPDATE, preserve created_at on conflict
                            await db.execute(
                                text("""
                                    INSERT INTO articles (site_id, title, url, content, image_url, published_at, created_at, updated_at, word_count, author)
                                    VALUES (:sid, :title, :url, :content, :image_url, :pub_date, :created_at, :updated_at, :word_count, :author)
                                    ON CONFLICT (url) DO UPDATE SET
                                        site_id = :sid, title = :title, content = :content,
                                        image_url = :image_url, published_at = :pub_date,
                                        updated_at = :updated_at, word_count = :word_count,
                                        author = :author
                                """),
                                {
                                    "sid": site_id, "title": title, "url": a_url,
                                    "content": content_text, "image_url": image_url,
                                    "pub_date": pub_date, "created_at": now_utc,
                                    "updated_at": now_utc, "word_count": wc,
                                    "author": author,
                                }
                            )
                            await db.commit()
                            log_with_time(f"[Crawl] Force updated: {title[:30]}...")
                            crawl_results.append({"url": a_url, "title": title, "status": "force_updated"})
                            result["articles_updated"] += 1
                        else:
                            # 排程模式：檢查 published_at 是否改變
                            existing = (await db.execute(
                                select(articles.c.id, articles.c.published_at, articles.c.created_at)
                                .where(articles.c.url == a_url)
                            )).mappings().first()
                            if existing:
                                old_pub_date = existing['published_at']
                                if old_pub_date == pub_date:
                                    # 時間相同，不用更新
                                    log_with_time(f"[Crawl] Skipped (no change): {title[:30]}...")
                                    return
                                # 時間改變了，更新內容, preserve created_at
                                await db.execute(
                                    articles.update()
                                    .where(articles.c.url == a_url)
                                    .values(
                                        title=title,
                                        content=content_text,
                                        image_url=image_url,
                                        published_at=pub_date,
                                        updated_at=now_utc,
                                        word_count=wc,
                                        author=author,
                                    )
                                )
                                await db.commit()
                                log_with_time(f"[Crawl] Updated (new content): {title[:30]}...")
                                crawl_results.append({"url": a_url, "title": title, "status": "updated"})
                                result["articles_updated"] += 1
                            else:
                                # 不存在，直接插入
                                await db.execute(
                                    articles.insert().values(
                                        site_id=site_id,
                                        title=title,
                                        url=a_url,
                                        content=content_text,
                                        image_url=image_url,
                                        published_at=pub_date,
                                        created_at=now_utc,
                                        updated_at=now_utc,
                                        word_count=wc,
                                        author=author,
                                    )
                                )
                                await db.commit()
                                log_with_time(f"[Crawl] Saved: {title[:30]}...")
                                crawl_results.append({"url": a_url, "title": title, "status": "saved"})
                                result["articles_saved"] += 1
                    except Exception as db_err:
                        log_with_time(f"[Crawl] DB error saving {a_url}: {db_err}")
                        try:
                            await db.rollback()
                        except Exception:
                            pass
                        result["articles_failed"] += 1

        try:
            await asyncio.gather(*[fetch_and_save_content(a) for a in articles_to_crawl])
        finally:
            # PERF-009: Close shared browser after all articles are processed
            if _shared_browser is not None:
                try:
                    await _shared_browser.close()
                    log_with_time(f"[Crawl] Shared browser closed for site {site_id}")
                except Exception:
                    pass
            if _pw_ctx is not None:
                try:
                    await _pw_ctx.__aexit__(None, None, None)
                except Exception:
                    pass

        if debug_writer is not None:
            debug_writer.save("04", "crawl_results.json", json.dumps(crawl_results, ensure_ascii=False, indent=2))

        log_with_time(f"[Crawl] Completed for site {site_id}: saved={result['articles_saved']}, updated={result['articles_updated']}, failed={result['articles_failed']}")
        return result

    except Exception as e:
        import traceback
        log_with_time(f"[Crawl] !!!!! UNHANDLED ERROR: {type(e).__name__}: {e}")
        log_with_time(traceback.format_exc())
        result["status"] = "fail"
        result["error_message"] = str(e)
        return result


async def force_refresh_all_articles(site_id: int, content_rules: dict, scrape_method: str, db) -> dict:
    """Re-scrape ALL articles in DB for a site. Skip if content is empty after scraping."""
    try:
        rows = (await db.execute(
            select(articles.c.url, articles.c.title).where(articles.c.site_id == site_id)
        )).mappings().all()

        semaphore = asyncio.Semaphore(3)
        _db_lock = asyncio.Lock()
        updated = 0
        skipped_empty = 0
        failed = 0

        async def refresh_one(row):
            nonlocal updated, skipped_empty, failed
            a_url = row["url"]
            async with semaphore:
                a_page = await fetch_page(a_url, method=scrape_method, fallback_playwright=True)
                if a_page is None:
                    failed += 1
                    return
                try:
                    content_text, parsed_date, image_url, author = parse_article(a_page, content_rules, a_url)
                except Exception as parse_err:
                    log_with_time(f"[ForceRefresh] Parse error for {a_url[:50]}: {parse_err}")
                    failed += 1
                    return
                if not (content_text or "").strip():
                    skipped_empty += 1
                    return

                # Extract title from content_rules title selector, fallback to existing
                title = row["title"]
                try:
                    title_selector = normalize_selector(content_rules.get("title", ""))
                    if title_selector:
                        el = a_page.find(title_selector)
                        if el and (el.text or "").strip():
                            title = el.text.strip()
                except Exception:
                    pass  # keep existing title on any selector error

                now_utc = datetime.now(timezone.utc)
                wc = compute_visible_word_count(content_text)
                pub_date = _parse_pub_date(parsed_date) if parsed_date else None

                async with _db_lock:
                    try:
                        update_vals = {
                            "content": content_text,
                            "title": title,
                            "image_url": image_url,
                            "updated_at": now_utc,
                            "word_count": wc,
                            "author": author,
                        }
                        if pub_date:
                            update_vals["published_at"] = pub_date
                        await db.execute(
                            articles.update().where(articles.c.url == a_url).values(**update_vals)
                        )
                        await db.commit()
                        updated += 1
                        log_with_time(f"[ForceRefresh] Updated: {a_url[:50]}")
                    except Exception as e:
                        await db.rollback()
                        failed += 1
                        log_with_time(f"[ForceRefresh] DB error for {a_url[:50]}: {e}")

        await asyncio.gather(*[refresh_one(row) for row in rows])
        log_with_time(f"[ForceRefresh] Site {site_id} all_db done: updated={updated}, skipped_empty={skipped_empty}, failed={failed}")
        return {"articles_updated": updated, "articles_skipped_empty": skipped_empty, "articles_failed": failed}
    except Exception as e:
        log_with_time(f"[ForceRefresh] Unhandled error for site {site_id}: {e}")
        return {"articles_updated": 0, "articles_skipped_empty": 0, "articles_failed": 0}


async def test_crawl_logic(url: str, list_rules: dict, content_rules: dict, filter_rules: dict | None = None, mode: str = "both", target_url: str | None = None, debug_writer=None, scrape_method: str = "scrapling", pre_built_articles: list | None = None, rss_meta_by_url: dict | None = None) -> dict:
    """乾跑預覽爬蟲，支援 list / content / both 模式

    Returns a dict with keys:
        articles: list of article dicts (each with 'filtered: bool')
        filter_summary: {passed: int, filtered_out: int}
    """
    import time

    start_total = time.time()
    log_with_time(f"[Preview] Starting mode={mode} for: {url if mode != 'content' else target_url}")

    try:
        new_articles = []
        stage1_filtered_count = 0

        # --- LIST MODE ---
        if mode in ("list", "both"):
            if pre_built_articles is not None:
                new_articles = pre_built_articles
                log_with_time(f"[Preview] Using {len(new_articles)} pre-built articles from RSS feed")
            else:
                page = await fetch_page(url, method=scrape_method, fallback_playwright=True)
                if page is None:
                    return {"articles": [{"error": "Failed to fetch list page"}], "filter_summary": None}

                if debug_writer is not None:
                    debug_writer.save("01", "list_raw_html.html", page.html_content or "")

                new_articles = parse_listing(page, list_rules, url)

                if debug_writer is not None:
                    debug_writer.save("02", "list_items.json", json.dumps(new_articles, ensure_ascii=False, indent=2))

                log_with_time(f"[Preview] Found {len(new_articles)} articles in list")

            # Stage 1 Filter: apply title-based filter before content fetch
            if filter_rules and new_articles:
                try:
                    passed_s1, filtered_s1 = apply_filter(
                        new_articles, filter_rules,
                        available_fields=['title']
                    )
                    stage1_filtered_count = len(filtered_s1)
                    new_articles = passed_s1
                    if stage1_filtered_count > 0:
                        log_with_time(f"[Preview] Stage 1 filter removed {stage1_filtered_count} articles")
                except Exception as e:
                    log_with_time(f"[Preview] filter_rules error at Stage 1, skipping: {e}")

        # --- CONTENT MODE ---
        if mode == "content" and target_url:
            new_articles = [{"url": target_url, "title": "Content Test"}]

        async def fetch_article_details(article_item):
            a_url = article_item['url']
            title = article_item.get('title', 'No Title')
            a_start = time.time()
            uhash = url_hash(a_url)

            a_page = await fetch_page(a_url, method=scrape_method, fallback_playwright=True)
            if a_page is None:
                return {"title": title, "url": a_url, "content": "Failed to fetch page", "published_at": "", "filtered": False}

            if debug_writer is not None:
                debug_writer.save(f"03_article_raw_{uhash}", "raw.html", a_page.html_content or "")

            pub_date = datetime.now(timezone.utc)
            content_text, parsed_date, _, _ = parse_article(a_page, content_rules, a_url)
            if parsed_date:
                pub_date = parsed_date
            elif rss_meta_by_url and a_url in rss_meta_by_url:
                rss_pub = rss_meta_by_url[a_url].get("published_at")
                if rss_pub:
                    try:
                        pub_date = datetime.fromisoformat(rss_pub)
                    except (ValueError, TypeError):
                        pass
            pub_date = _parse_pub_date(pub_date)

            # 從 content_rules 的 title selector 提取真正標題（覆蓋佔位符）
            title_selector = normalize_selector(content_rules.get('title', ''))
            if title_selector:
                title_el = a_page.find(title_selector)
                if title_el:
                    extracted = (title_el.text or "").strip()
                    if not extracted and title_el.tag == 'img':
                        extracted = (title_el.attrib.get('alt', '')).strip()
                    if extracted:
                        title = extracted
            if title == "Content Test" or title == "No Title":
                h1 = a_page.find('h1')
                if h1:
                    extracted = (h1.text or "").strip()
                    if extracted:
                        title = extracted

            if debug_writer is not None:
                debug_writer.save(f"03_article_cleaned_{uhash}", "cleaned.html", content_text[:5000])

            # Stage 2 Filter: full filter check with content available
            is_filtered = False
            if filter_rules:
                try:
                    article_data = {"title": title, "content": content_text}
                    _, stage2_filtered = apply_filter(
                        [article_data], filter_rules,
                        available_fields=['title', 'content']
                    )
                    if stage2_filtered:
                        is_filtered = True
                        log_with_time(f"[Preview] Stage 2 filter excluded: {title[:30]}...")
                except Exception as e:
                    log_with_time(f"[Preview] filter_rules error at Stage 2, skipping: {e}")

            log_with_time(f"[Preview] Article {a_url[:30]} parsed in {time.time() - a_start:.2f}s")
            return {
                "title": title,
                "url": a_url,
                "content": content_text,
                "published_at": pub_date.isoformat() if isinstance(pub_date, datetime) else str(pub_date),
                "filtered": is_filtered,
            }

        results = list(await asyncio.gather(*[fetch_article_details(a) for a in new_articles]))

        # Compute filter summary
        stage2_filtered_count = sum(1 for r in results if r.get('filtered', False))
        total_filtered = stage1_filtered_count + stage2_filtered_count
        total_passed = len(results) - stage2_filtered_count
        filter_summary = {
            "passed": total_passed,
            "filtered_out": total_filtered,
        } if filter_rules else None

        if debug_writer is not None:
            debug_writer.save("04", "preview_results.json", json.dumps(results, ensure_ascii=False, indent=2))

        log_with_time(f"[Preview] Total preview time: {time.time() - start_total:.2f}s")
        return {
            "articles": results,
            "filter_summary": filter_summary,
        }

    except Exception as e:
        import traceback
        log_with_time(f"[Preview] ERROR: {str(e)}\n{traceback.format_exc()}")
        return {"articles": [{"error": f"Preview crawl failed: {str(e)}"}], "filter_summary": None}
