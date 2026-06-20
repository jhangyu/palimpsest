# backend/core/crawler.py
import os
import re
import asyncio
import json
import httpx
from datetime import datetime
from hashlib import md5

from sqlalchemy import select, text

from core.db import sites, articles
from core.scraper import fetch_page
from core.parser import parse_listing, parse_article, normalize_selector
from core.filter_engine import apply_filter


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
    from datetime import timezone
    return datetime.now(timezone.utc).isoformat()


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



async def get_page_content(url: str, wait_for_selector: str | None = None, browser=None, fast_mode=False) -> str:
    """連線到遠端 Chrome (Browserless) 取得渲染後的 HTML

    Args:
        url: 目標網址
        wait_for_selector: 可選，等待特定元素出現後再取得 HTML
        browser: 可選，重用現有的 browser 實例
        fast_mode: 預覽模式，縮短等待時間
    """
    from playwright.async_api import async_playwright
    import time
    start_ts = time.time()

    # 決定是否使用內部啟動的 playwright
    if browser:
        context = await browser.new_context(
            user_agent=MODERN_CHROME_UA,
            viewport={"width": 1920, "height": 1080},
            locale="zh-TW",
            timezone_id="Asia/Taipei",
            extra_http_headers={
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
            }
        )
        page = await context.new_page()
        try:
            content = await get_page_content_on_page(page, url, wait_for_selector, fast_mode)
            await page.close()
            await context.close()
            return content
        except Exception as e:
            log_with_time(f"[Crawler] Error in reused browser for {url}: {e}")
            return ""

    async with async_playwright() as p:
        try:
            mode = os.getenv("CHROME_MODE", "server")
            if mode == "local":
                # 本地模式：添加反偵測參數
                browser_obj = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-web-security",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ]
                )
            else:
                browser_obj = await p.chromium.connect_over_cdp(CHROME_WS)

            context = await browser_obj.new_context(
                user_agent=MODERN_CHROME_UA,
                viewport={"width": 1920, "height": 1080},
                locale="zh-TW",
                timezone_id="Asia/Taipei",
                extra_http_headers={
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
                }
            )
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


async def crawl_site_logic(site_id: int, url: str, list_rules: dict, content_rules: dict, db, debug_writer=None, force_update: bool = False, scrape_method: str = "scrapling", owner_user_id=None, ai_tables=None, kek_backend=None, filter_rules: dict | None = None):
    """
    爬取網站邏輯，包含自動修復機制 (Scrapling 兩階段流程)

    Args:
        force_update: 如果為 True，即使 URL 已存在也會用最新內容覆蓋（手動重爬模式）
                      如果為 False，會比對 published_at，只插入時間改變的文章（排程模式）
        scrape_method: 抓取方式，'scrapling'（預設）或 'playwright'

    Returns:
        dict with keys: status, articles_found, articles_saved, articles_updated,
        articles_failed, content_fetch_failed, parse_failed, error_message
    """
    _compute_wc = compute_visible_word_count
    _utc_now = _utcnow_iso

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

        # Stage 1: 取得列表頁
        page = await fetch_page(url, method=scrape_method)
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
            log_with_time(f"[Crawl] Warning: No items found for site {site_id}. Rules might be broken.")
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
                    log_with_time(f"[Crawl] Skipping auto-repair for site {site_id}: no owner context available")
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

        # 過濾文章（排程模式：只抓不存在的）
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

        log_with_time(f"[Crawl] Found {len(articles_to_crawl)} articles to crawl for site {site_id} (force_update={force_update})")

        if debug_writer is not None:
            debug_writer.save("02", "list_items.json", json.dumps(articles_to_crawl, ensure_ascii=False, indent=2))

        if not articles_to_crawl:
            return result

        # Stage 2: 並行抓取內文 (控制併發)
        # PERF-009: Launch a single shared Playwright browser for the entire crawl session.
        # Each article will create a new page/context rather than a new browser process.
        _shared_browser = None
        _pw_ctx = None
        if scrape_method == "playwright":
            try:
                from playwright.async_api import async_playwright
                _pw_ctx = async_playwright()
                _pw = await _pw_ctx.__aenter__()
                mode = os.getenv("CHROME_MODE", "server")
                if mode == "local":
                    _shared_browser = await _pw.chromium.launch(
                        headless=True,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--disable-dev-shm-usage",
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-web-security",
                            "--disable-features=IsolateOrigins,site-per-process",
                        ]
                    )
                else:
                    _shared_browser = await _pw.chromium.connect_over_cdp(CHROME_WS)
                log_with_time(f"[Crawl] Shared Playwright browser ready for site {site_id}")
            except Exception as br_err:
                log_with_time(f"[Crawl] Failed to launch shared browser: {br_err}, falling back to per-article browser")
                if _pw_ctx is not None:
                    try:
                        await _pw_ctx.__aexit__(None, None, None)
                    except Exception:
                        pass
                _shared_browser = None
                _pw_ctx = None

        semaphore = asyncio.Semaphore(3)
        crawl_results = []

        async def fetch_and_save_content(article: dict):
            async with semaphore:
                a_url = article['url']
                title = article['title']
                uhash = url_hash(a_url)

                # PERF-008 / PERF-009: Reuse session-level browser or HTTP client.
                # Playwright: use shared browser (new page per article, not new browser).
                # Scrapling: fetch_page manages its own connection; _get_http_client() is
                # available for any direct HTTP calls added in future.
                if scrape_method == "playwright" and _shared_browser is not None:
                    from scrapling.parser import Selector
                    _html = await get_page_content(a_url, browser=_shared_browser)
                    a_page = Selector(_html) if _html else None
                    a_page_html = _html or ""
                else:
                    a_page = await fetch_page(a_url, method=scrape_method)
                    a_page_html = getattr(a_page, 'html_content', '') if a_page is not None else ""

                if a_page is None:
                    result["content_fetch_failed"] += 1
                    result["articles_failed"] += 1
                    return

                if debug_writer is not None:
                    debug_writer.save(f"03_article_raw_{uhash}", "raw.html", a_page_html or "")

                pub_date = datetime.now().isoformat()
                try:
                    content_text, parsed_date, image_url, author = parse_article(a_page, content_rules, a_url)
                except Exception as parse_err:
                    log_with_time(f"[Crawl] Parse error for {a_url}: {parse_err}")
                    result["parse_failed"] += 1
                    result["articles_failed"] += 1
                    return

                if parsed_date:
                    pub_date = parsed_date

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

                try:
                    if force_update:
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
                    result["articles_failed"] += 1

        try:
            await asyncio.gather(*[fetch_and_save_content(a) for a in articles_to_crawl])
        finally:
            # PERF-009: Close shared Playwright browser after all articles are processed
            if _shared_browser is not None:
                try:
                    await _shared_browser.close()
                    log_with_time(f"[Crawl] Shared Playwright browser closed for site {site_id}")
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


async def test_crawl_logic(url: str, list_rules: dict, content_rules: dict, filter_rules: dict | None = None, mode: str = "both", target_url: str | None = None, debug_writer=None, scrape_method: str = "scrapling") -> dict:
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
            page = await fetch_page(url, method=scrape_method)
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

            a_page = await fetch_page(a_url, method=scrape_method)
            if a_page is None:
                return {"title": title, "url": a_url, "content": "Failed to fetch page", "published_at": "", "filtered": False}

            if debug_writer is not None:
                debug_writer.save(f"03_article_raw_{uhash}", "raw.html", a_page.html_content or "")

            pub_date = datetime.now().isoformat()
            content_text, parsed_date, _, _ = parse_article(a_page, content_rules, a_url)
            if parsed_date:
                pub_date = parsed_date

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
                "published_at": pub_date,
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
