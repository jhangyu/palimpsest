# backend/core/crawler.py
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import os
import asyncio
import json
import re
import time
from datetime import datetime
from urllib.parse import urljoin
from hashlib import md5

from core.crawl_utils import normalize_selector, extract_article_info
from core.vue_parser import extract_vue_json, parse_vue_json

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


async def crawl_site_logic(site_id: int, url: str, list_rules: dict, content_rules: dict, db, debug_writer=None, force_update: bool = False):
    """
    爬取網站邏輯，包含自動修復機制 (優化版：單一瀏覽器連通 + 並行抓取)

    Args:
        force_update: 如果為 True，即使 URL 已存在也會用最新內容覆蓋（手動重爬模式）
                      如果為 False，會比對 published_at，只插入時間更新的文章（排程模式）
    """
    try:
        log_with_time(f"[Crawl] >>>>>>>> Starting optimized crawl for site {site_id}: {url}")
        
        async with async_playwright() as p:
            # 1. 初始化瀏覽器
            mode = os.getenv("CHROME_MODE", "server")
            if mode == "local":
                browser = await p.chromium.launch(headless=True)
            else:
                browser = await p.chromium.connect_over_cdp(CHROME_WS)
            
            # 2. 取得列表頁 HTML
            # 正式爬取給予較長的超時，但仍比 15s 短
            html = await get_page_content(url, browser=browser) 
            if not html:
                log_with_time(f"[Crawl] Failed to get HTML for site {site_id}")
                await browser.close()
                return
            
            if debug_writer is not None:
                debug_writer.save("01", "list_raw_html.html", html)

            soup = BeautifulSoup(html, 'html.parser')
            
            # 3. 解析文章列表
            container_selector = normalize_selector(list_rules.get('container', ''))
            item_selector = normalize_selector(list_rules.get('item', ''))
            
            if container_selector and item_selector:
                full_selector = f"{container_selector} {item_selector}"
            elif item_selector:
                full_selector = item_selector
            else:
                full_selector = ""
            
            items = soup.select(full_selector) if full_selector else []
            
            # 自動修復邏輯 (維持現狀，但改用現成的 html)
            if len(items) == 0:
                log_with_time(f"[Crawl] Warning: No items found for site {site_id}. Rules might be broken.")
                query = "SELECT consecutive_failure_count FROM sites WHERE id = :id"
                result = await db.fetch_one(query=query, values={"id": site_id})
                current_count = result[0] if result else 0
                new_count = current_count + 1
                await db.execute("UPDATE sites SET consecutive_failure_count = :count WHERE id = :id", values={"count": new_count, "id": site_id})
                
                if new_count >= FAILURE_THRESHOLD:
                    from core.ai import analyze_structure
                    new_list_rules = await analyze_structure(html, mode="list")
                    if new_list_rules and "item" in new_list_rules:
                        await db.execute("UPDATE sites SET list_rules = :rules, consecutive_failure_count = 0 WHERE id = :id", 
                                       values={"rules": json.dumps(new_list_rules), "id": site_id})
                        list_rules = new_list_rules
                        full_selector = f"{list_rules.get('container','')} {list_rules.get('item','')}".strip()
                        items = soup.select(full_selector)
                
                if len(items) == 0:
                    await browser.close()
                    return
            else:
                await db.execute("UPDATE sites SET consecutive_failure_count = 0 WHERE id = :id", values={"id": site_id})

            # 4. 解析文章清單
            articles_to_crawl = []
            link_selector = normalize_selector(list_rules.get('link', 'a'))
            title_selector = normalize_selector(list_rules.get('title', ''))

            for item in items:
                try:
                    link_el = item.select_one(link_selector)
                    if not link_el: continue
                    article_url = link_el.get('href', '')
                    if not article_url: continue
                    if not article_url.startswith('http'):
                        article_url = urljoin(url, article_url)

                    title = ""
                    if title_selector:
                        title_el = item.select_one(title_selector)
                        title = title_el.get_text(strip=True) if title_el else ""
                    if not title:
                        title = link_el.get_text(strip=True) or "No Title"

                    if force_update:
                        # 手動重爬模式：不管存在與否都抓
                        articles_to_crawl.append({"url": article_url, "title": title})
                    else:
                        # 排程模式：只抓新的或時間有更新的
                        existing = await db.fetch_one("SELECT id, published_at FROM articles WHERE url = :url", values={"url": article_url})
                        if not existing:
                            # 不存在，直接新增
                            articles_to_crawl.append({"url": article_url, "title": title})
                        # else: 已存在文章，之後在 fetch_and_save_content 中比對 published_at
                except (AttributeError, ValueError) as e:
                    log_with_time(f"[Crawl] Skip item: {e}")
                    continue

            log_with_time(f"[Crawl] Found {len(articles_to_crawl)} articles to crawl for site {site_id} (force_update={force_update})")

            if debug_writer is not None:
                debug_writer.save("02", "list_items.json", json.dumps(articles_to_crawl, ensure_ascii=False, indent=2))

            if not articles_to_crawl:
                await browser.close()
                return

            # 5. 並行抓取內文 (控制併發)
            semaphore = asyncio.Semaphore(3)
            crawl_results = []

            async def fetch_and_save_content(article: dict):
                async with semaphore:
                    a_url = article['url']
                    title = article['title']
                    uhash = url_hash(a_url)

                    # 重用同一個瀏覽器實例
                    c_html = await get_page_content(a_url, browser=browser)
                    if not c_html: return

                    if debug_writer is not None:
                        debug_writer.save(f"03_article_raw_{uhash}", "raw.html", c_html)

                    is_vue_template = content_rules.get('is_vue_template', False)
                    content_text = ""
                    pub_date = datetime.now().isoformat()
                    image_url = None

                    if is_vue_template:
                        from core.ai import extract_template_html, decode_vue_gallery, _sanitize_content_html
                        vue_html = extract_template_html(c_html)
                        if vue_html:
                            # 處理 Vue gallery 元件，轉換為標準 HTML
                            vue_html = decode_vue_gallery(vue_html)
                            # 進一步淨化，移除裝飾性 class 和非必要標籤
                            content_text = _sanitize_content_html(vue_html)
                        else:
                            content_text = "Vue template extraction failed"

                        # 從 Vue template JSON 解析 pub_date 與 image_url
                        import re
                        import json
                        template_match = re.search(r'<template[^>]*>(.*?)</template>', c_html, re.DOTALL)
                        if template_match:
                            try:
                                template_content = template_match.group(1)
                                cleaned = re.sub(r'[:@](\w+)="[^"]*"', '', template_content)
                                cleaned = re.sub(r'v-\w+="[^"]*"', '', cleaned)
                                data = json.loads(cleaned)
                                for k in ['to_publish_time', 'updated_at', 'date', 'my_publish_date', 'publish_time']:
                                    if k in data and data[k]: pub_date = str(data[k]); break
                                for k in ['large', 'medium', 'feature_picture']:
                                    if k in data and data[k]: image_url = data[k]; break
                            except (json.JSONDecodeError, KeyError) as e:
                                log_with_time(f"[Crawl] Vue JSON parse error: {e}")
                    else:
                        c_soup = BeautifulSoup(c_html, 'html.parser')
                        body_el = c_soup.select_one(content_rules.get('body', 'article'))
                        content_text = str(body_el) if body_el else "Parsing failed"
                        date_el = c_soup.select_one(content_rules.get('date', 'time'))
                        if date_el: pub_date = date_el.get_text(strip=True)
                        img_el = c_soup.select_one(content_rules.get('image', 'img'))
                        if img_el:
                            image_url = img_el.get('src', '')
                            if image_url and not image_url.startswith('http'): image_url = urljoin(a_url, image_url)

                    if debug_writer is not None:
                        debug_writer.save(f"03_article_cleaned_{uhash}", "cleaned.html", content_text[:5000])

                    if force_update:
                        # 手動重爬模式：直接用最新內容覆蓋（INSERT OR REPLACE）
                        await db.execute("""
                            INSERT OR REPLACE INTO articles (site_id, title, url, content, image_url, published_at)
                            VALUES (:sid, :title, :url, :content, :image_url, :pub_date)
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

            await browser.close()
            log_with_time(f"[Crawl] Completed for site {site_id}")

    except Exception as e:
        log_with_time(f"[Crawl] Error: {e}")
        import traceback
        log_with_time(traceback.format_exc())
        log_with_time(f"[Crawl] !!!!! UNHANDLED ERROR: {type(e).__name__}: {e}")
        log_with_time(traceback.format_exc())


async def test_crawl_logic(url: str, list_rules: dict, content_rules: dict, mode: str = "both", target_url: str = None, debug_writer=None) -> list:
    """乾跑預覽爬蟲，支援 list / content / both 模式"""
    from urllib.parse import urljoin
    from bs4 import BeautifulSoup
    import time
    import asyncio

    start_total = time.time()
    log_with_time(f"[Preview] Starting mode={mode} for: {url if mode != 'content' else target_url}")

    try:
        # 1. 啟動單一瀏覽器連通
        async with async_playwright() as p:
            browser_type = p.chromium
            # 使用與正式爬蟲一致的連線邏輯
            browser_choice = os.getenv("CHROME_MODE", "local")
            if browser_choice == "local":
                browser = await browser_type.launch(headless=True)
            else:
                browser = await browser_type.connect(os.getenv("BROWSER_WS_URL", "ws://chrome:3000"))

            # --- LIST MODE ---
            new_articles = []
            if mode in ("list", "both"):
                list_html = await get_page_content(url, browser=browser, fast_mode=True)
                if not list_html:
                    await browser.close()
                    return [{"error": "Failed to fetch list page"}]

                if debug_writer is not None:
                    debug_writer.save("01", "list_raw_html.html", list_html)

                list_soup = BeautifulSoup(list_html, 'html.parser')
                container_sel = normalize_selector(list_rules.get('container', ''))
                item_sel = normalize_selector(list_rules.get('item', ''))

                full_sel = f"{container_sel} {item_sel}".strip() if container_sel and item_sel else item_sel
                items = list_soup.select(full_sel) if full_sel else []

                link_sel = normalize_selector(list_rules.get('link', 'a'))
                title_sel = normalize_selector(list_rules.get('title', ''))

                for item in items:
                    try:
                        link_el = item.select_one(link_sel)
                        if not link_el: continue
                        article_url = link_el.get('href', '')
                        if not article_url: continue
                        if not article_url.startswith('http'):
                            article_url = urljoin(url, article_url)
                        title = ""
                        if title_sel:
                            title_el = item.select_one(title_sel)
                            title = title_el.get_text(strip=True) if title_el else ""
                        if not title:
                            title = link_el.get_text(strip=True) or "No Title"
                        new_articles.append({"url": article_url, "title": title})
                    except (AttributeError, ValueError) as e:
                        log_with_time(f"[Preview] Skip item: {e}")
                        continue

                if debug_writer is not None:
                    debug_writer.save("02", "list_items.json", json.dumps(new_articles, ensure_ascii=False, indent=2))

                log_with_time(f"[Preview] Found {len(new_articles)} articles in list")

            # --- CONTENT MODE ---
            if mode == "content" and target_url:
                new_articles = [{"url": target_url, "title": "Content Test"}]

            # 定義解析單篇文章的內部函數
            async def fetch_article_details(article_item, browser_instance):
                a_url = article_item['url']
                title = article_item.get('title', 'No Title')
                a_start = time.time()
                uhash = url_hash(a_url)
                
                c_html = await get_page_content(a_url, browser=browser_instance, fast_mode=True)
                if not c_html:
                    return {"title": title, "url": a_url, "content": "Failed to fetch page", "published_at": ""}

                if debug_writer is not None:
                    debug_writer.save(f"03_article_raw_{uhash}", "raw.html", c_html)
                
                # 解析邏輯 (與正式爬蟲邏輯同步)
                is_vue_template = content_rules.get('is_vue_template', False)
                content_text = ""
                pub_date = datetime.now().isoformat()
                
                if is_vue_template:
                    from core.ai import extract_template_html, decode_vue_gallery, _sanitize_content_html
                    vue_html = extract_template_html(c_html)
                    if vue_html:
                        # 處理 Vue gallery 元件，轉換為標準 HTML
                        vue_html = decode_vue_gallery(vue_html)
                        # 進一步淨化，移除裝飾性 class 和非必要標籤
                        content_text = _sanitize_content_html(vue_html)
                    else:
                        content_text = "Vue template extraction failed"
                    import re
                    template_match = re.search(r'<template[^>]*>(.*?)</template>', c_html, re.DOTALL)
                    if template_match:
                        try:
                            import json
                            template_content = template_match.group(1)
                            # 清洗 Vue 特有的屬性以利 JSON 解析 (簡單處理)
                            cleaned = re.sub(r'[:@](\w+)="[^"]*"', '', template_content)
                            cleaned = re.sub(r'v-\w+="[^"]*"', '', cleaned)
                            data = json.loads(cleaned)
                            for date_key in ['to_publish_time', 'updated_at', 'date', 'my_publish_date', 'publish_time']:
                                if date_key in data and data[date_key]:
                                    pub_date = str(data[date_key])
                                    break
                        except (json.JSONDecodeError, KeyError) as e:
                            log_with_time(f"[Preview] Vue JSON parse error: {e}")
                else:
                    c_soup = BeautifulSoup(c_html, 'html.parser')
                    body_selector = normalize_selector(content_rules.get('body', 'article'))
                    body_el = c_soup.select_one(body_selector)
                    raw_content = str(body_el) if body_el else "Content parsing failed (Selector missing)"
                    # 淨化 content，移除裝飾性 class 和非必要標籤
                    from core.ai import _sanitize_content_html
                    content_text = _sanitize_content_html(raw_content) if body_el else raw_content
                    
                    date_selector = normalize_selector(content_rules.get('date', content_rules.get('time', '')))
                    if date_selector:
                        date_el = c_soup.select_one(date_selector)
                        if date_el:
                            pub_date = date_el.get_text(strip=True) or pub_date

                if debug_writer is not None:
                    debug_writer.save(f"03_article_cleaned_{uhash}", "cleaned.html", content_text[:5000])

                log_with_time(f"[Preview] Article {a_url[:30]} parsed in {time.time() - a_start:.2f}s")
                return {
                    "title": title,
                    "url": a_url,
                    "content": content_text,
                    "published_at": pub_date
                }

            results = await asyncio.gather(*[fetch_article_details(a, browser) for a in new_articles])

            if debug_writer is not None:
                debug_writer.save("04", "preview_results.json", json.dumps(results, ensure_ascii=False, indent=2))
            
            # 4. 關閉瀏覽器
            await browser.close()
            log_with_time(f"[Preview] Total preview time: {time.time() - start_total:.2f}s")
            return results

    except Exception as e:
        import traceback
        log_with_time(f"[Preview] ERROR: {str(e)}\n{traceback.format_exc()}")
        return [{"error": f"Preview crawl failed: {str(e)}"}]
