# backend/core/crawler.py
import os
import asyncio
import json
from datetime import datetime
from hashlib import md5

from core.scraper import fetch_page
from core.parser import parse_listing, parse_article, normalize_selector


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

async def get_page_content(url: str, wait_for_selector: str = None, browser=None, fast_mode=False) -> str:
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


async def crawl_site_logic(site_id: int, url: str, list_rules: dict, content_rules: dict, db, debug_writer=None, force_update: bool = False, scrape_method: str = "scrapling"):
    """
    爬取網站邏輯，包含自動修復機制 (Scrapling 兩階段流程)

    Args:
        force_update: 如果為 True，即使 URL 已存在也會用最新內容覆蓋（手動重爬模式）
                      如果為 False，會比對 published_at，只插入時間更新的文章（排程模式）
        scrape_method: 抓取方式，'scrapling'（預設）或 'playwright'
    """
    try:
        log_with_time(f"[Crawl] >>>>>>>> Starting crawl for site {site_id}: {url}")

        # Stage 1: 取得列表頁
        page = await fetch_page(url, method=scrape_method)
        if page is None:
            log_with_time(f"[Crawl] Failed to get page for site {site_id}")
            return

        if debug_writer is not None:
            debug_writer.save("01", "list_raw_html.html", page.html_content or "")

        # 解析文章列表
        articles_found = parse_listing(page, list_rules, url)

        # 自動修復邏輯
        if len(articles_found) == 0:
            log_with_time(f"[Crawl] Warning: No items found for site {site_id}. Rules might be broken.")
            query = "SELECT consecutive_failure_count FROM sites WHERE id = :id"
            result = await db.fetch_one(query=query, values={"id": site_id})
            current_count = result[0] if result else 0
            new_count = current_count + 1
            await db.execute("UPDATE sites SET consecutive_failure_count = :count WHERE id = :id", values={"count": new_count, "id": site_id})

            if new_count >= FAILURE_THRESHOLD:
                from core.ai import analyze_structure
                new_list_rules = await analyze_structure(page.html_content or "", mode="list")
                if new_list_rules and "item" in new_list_rules:
                    await db.execute("UPDATE sites SET list_rules = :rules, consecutive_failure_count = 0 WHERE id = :id",
                                     values={"rules": json.dumps(new_list_rules), "id": site_id})
                    list_rules = new_list_rules
                    articles_found = parse_listing(page, list_rules, url)

            if len(articles_found) == 0:
                return
        else:
            await db.execute("UPDATE sites SET consecutive_failure_count = 0 WHERE id = :id", values={"id": site_id})

        # 過濾文章（排程模式：只抓不存在的）
        articles_to_crawl = []
        for article in articles_found:
            if force_update:
                articles_to_crawl.append(article)
            else:
                existing = await db.fetch_one("SELECT id FROM articles WHERE url = :url", values={"url": article['url']})
                if not existing:
                    articles_to_crawl.append(article)

        log_with_time(f"[Crawl] Found {len(articles_to_crawl)} articles to crawl for site {site_id} (force_update={force_update})")

        if debug_writer is not None:
            debug_writer.save("02", "list_items.json", json.dumps(articles_to_crawl, ensure_ascii=False, indent=2))

        if not articles_to_crawl:
            return

        # Stage 2: 並行抓取內文 (控制併發)
        semaphore = asyncio.Semaphore(3)
        crawl_results = []

        async def fetch_and_save_content(article: dict):
            async with semaphore:
                a_url = article['url']
                title = article['title']
                uhash = url_hash(a_url)

                a_page = await fetch_page(a_url, method=scrape_method)
                if a_page is None:
                    return

                if debug_writer is not None:
                    debug_writer.save(f"03_article_raw_{uhash}", "raw.html", a_page.html_content or "")

                pub_date = datetime.now().isoformat()
                content_text, parsed_date, image_url = parse_article(a_page, content_rules, a_url)
                if parsed_date:
                    pub_date = parsed_date

                if debug_writer is not None:
                    debug_writer.save(f"03_article_cleaned_{uhash}", "cleaned.html", content_text[:5000])

                if force_update:
                    # 手動重爬模式：直接用最新內容覆蓋（INSERT OR REPLACE）
                    await db.execute("""
                        INSERT INTO articles (site_id, title, url, content, image_url, published_at)
                        VALUES (:sid, :title, :url, :content, :image_url, :pub_date)
                        ON CONFLICT (url) DO UPDATE SET
                            site_id = :sid, title = :title, content = :content,
                            image_url = :image_url, published_at = :pub_date
                    """, values={"sid": site_id, "title": title, "url": a_url, "content": content_text, "image_url": image_url, "pub_date": pub_date})
                    log_with_time(f"[Crawl] Force updated: {title[:30]}...")
                    crawl_results.append({"url": a_url, "title": title, "status": "force_updated"})
                else:
                    # 排程模式：檢查 published_at 是否改變
                    existing = await db.fetch_one("SELECT id, published_at FROM articles WHERE url = :url", values={"url": a_url})
                    if existing:
                        old_pub_date = existing['published_at']
                        if old_pub_date == pub_date:
                            # 時間相同，不用更新
                            log_with_time(f"[Crawl] Skipped (no change): {title[:30]}...")
                            return
                        # 時間改變了，更新內容
                        await db.execute("""
                            UPDATE articles SET title = :title, content = :content, image_url = :image_url, published_at = :pub_date
                            WHERE url = :url
                        """, values={"title": title, "content": content_text, "image_url": image_url, "pub_date": pub_date, "url": a_url})
                        log_with_time(f"[Crawl] Updated (new content): {title[:30]}...")
                        crawl_results.append({"url": a_url, "title": title, "status": "updated"})
                    else:
                        # 不存在，直接插入
                        await db.execute("""
                            INSERT INTO articles (site_id, title, url, content, image_url, published_at)
                            VALUES (:sid, :title, :url, :content, :image_url, :pub_date)
                        """, values={"sid": site_id, "title": title, "url": a_url, "content": content_text, "image_url": image_url, "pub_date": pub_date})
                        log_with_time(f"[Crawl] Saved: {title[:30]}...")
                        crawl_results.append({"url": a_url, "title": title, "status": "saved"})

        await asyncio.gather(*[fetch_and_save_content(a) for a in articles_to_crawl])

        if debug_writer is not None:
            debug_writer.save("04", "crawl_results.json", json.dumps(crawl_results, ensure_ascii=False, indent=2))

        log_with_time(f"[Crawl] Completed for site {site_id}")

    except Exception as e:
        import traceback
        log_with_time(f"[Crawl] !!!!! UNHANDLED ERROR: {type(e).__name__}: {e}")
        log_with_time(traceback.format_exc())


async def test_crawl_logic(url: str, list_rules: dict, content_rules: dict, mode: str = "both", target_url: str = None, debug_writer=None, scrape_method: str = "scrapling") -> list:
    """乾跑預覽爬蟲，支援 list / content / both 模式"""
    import time

    start_total = time.time()
    log_with_time(f"[Preview] Starting mode={mode} for: {url if mode != 'content' else target_url}")

    try:
        new_articles = []

        # --- LIST MODE ---
        if mode in ("list", "both"):
            page = await fetch_page(url, method=scrape_method)
            if page is None:
                return [{"error": "Failed to fetch list page"}]

            if debug_writer is not None:
                debug_writer.save("01", "list_raw_html.html", page.html_content or "")

            new_articles = parse_listing(page, list_rules, url)

            if debug_writer is not None:
                debug_writer.save("02", "list_items.json", json.dumps(new_articles, ensure_ascii=False, indent=2))

            log_with_time(f"[Preview] Found {len(new_articles)} articles in list")

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
                return {"title": title, "url": a_url, "content": "Failed to fetch page", "published_at": ""}

            if debug_writer is not None:
                debug_writer.save(f"03_article_raw_{uhash}", "raw.html", a_page.html_content or "")

            pub_date = datetime.now().isoformat()
            content_text, parsed_date, image_url = parse_article(a_page, content_rules, a_url)
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

            log_with_time(f"[Preview] Article {a_url[:30]} parsed in {time.time() - a_start:.2f}s")
            return {
                "title": title,
                "url": a_url,
                "content": content_text,
                "published_at": pub_date
            }

        results = await asyncio.gather(*[fetch_article_details(a) for a in new_articles])

        if debug_writer is not None:
            debug_writer.save("04", "preview_results.json", json.dumps(list(results), ensure_ascii=False, indent=2))

        log_with_time(f"[Preview] Total preview time: {time.time() - start_total:.2f}s")
        return list(results)

    except Exception as e:
        import traceback
        log_with_time(f"[Preview] ERROR: {str(e)}\n{traceback.format_exc()}")
        return [{"error": f"Preview crawl failed: {str(e)}"}]
