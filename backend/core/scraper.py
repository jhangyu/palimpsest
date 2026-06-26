# backend/core/scraper.py
"""
---
name: scraper
description: "Scrapling fetch abstraction layer: unified fetch_page() interface supporting scrapling (default) and playwright methods with shared thread pool and headers"
type: core
target:
  layer: backend
  domain: crawl
spec_doc: null
test_file: null
functions:
  - name: _fetch_scrapling_sync
    line: 32
    purpose: "Synchronous Scrapling Fetcher.get() call; run via thread pool to avoid blocking event loop"
  - name: fetch_page
    line: 43
    purpose: "Unified async fetch: scrapling (default) or playwright; supports fallback_playwright=True to retry with playwright on anti-bot status codes"
constants:
  - name: _FALLBACK_STATUSES
    line: 50
    purpose: "Set of HTTP status codes that trigger playwright fallback: 403, 429, 451, 503 (anti-bot signals)"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from typing import Optional


def log_with_time(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


_SCRAPER_POOL = ThreadPoolExecutor(max_workers=4)


# 預設 headers：現代 Chrome UA + 繁體中文 Accept-Language
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Anti-bot HTTP status codes that trigger playwright fallback:
# 403 Forbidden (WAF/bot detection), 429 Too Many Requests (rate limiting),
# 451 Unavailable For Legal Reasons (geo-block), 503 Service Unavailable (Cloudflare JS challenge)
_FALLBACK_STATUSES = {403, 429, 451, 503}


def _fetch_scrapling_sync(url: str, headers: dict):
    """
    同步執行 Scrapling Fetcher.get()。
    在 async 函式中透過 run_in_executor 呼叫，避免阻塞 event loop。
    回傳 Scrapling page 物件（支援 .css()、.xpath()、.text、.attrib）。
    """
    from scrapling import Fetcher
    page = Fetcher.get(url, headers=headers)
    return page


async def fetch_page(url: str, method: str = "scrapling", headers: Optional[dict] = None, fallback_playwright: bool = False):
    """
    統一抓取介面。

    Args:
        url: 目標網址
        method: 抓取方式，'scrapling'（預設）或 'playwright'
        headers: 自訂 HTTP headers，將與預設 headers 合併（自訂優先）
        fallback_playwright: scrapling 回傳 4xx/5xx 時自動改用 playwright 重試

    Returns:
        Scrapling page 物件（支援 .css()、.xpath()、.text、.attrib）。
        - scrapling mode: 直接回傳 Fetcher 取得的 page 物件
        - playwright mode: 回傳以 Scrapling Adaptor 包裝的 page 物件
        若抓取失敗，回傳 None。
    """
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}

    if method == "scrapling":
        try:
            log_with_time(f"[Scraper] Fetching (scrapling): {url}")
            loop = asyncio.get_running_loop()
            page = await loop.run_in_executor(
                _SCRAPER_POOL,
                partial(_fetch_scrapling_sync, url, merged_headers),
            )
            log_with_time(f"[Scraper] Status {page.status}: {url}")
            if fallback_playwright and page.status in _FALLBACK_STATUSES:
                log_with_time(f"[Scraper] Scrapling got {page.status}, falling back to playwright: {url}")
                # fallback_playwright intentionally NOT passed: playwright is the terminal fallback
                return await fetch_page(url, method="playwright", headers=headers)
            return page
        except Exception as e:
            log_with_time(f"[Scraper] Scrapling error for {url}: {e}")
            return None

    elif method == "playwright":
        try:
            log_with_time(f"[Scraper] Fetching (playwright): {url}")
            from core.crawler import get_page_content
            from scrapling.parser import Selector

            html_content = await get_page_content(url)
            if not html_content:
                log_with_time(f"[Scraper] Playwright returned empty content for {url}")
                return None

            page = Selector(html_content)
            log_with_time(f"[Scraper] Playwright fetched and wrapped: {url}")
            return page
        except Exception as e:
            log_with_time(f"[Scraper] Playwright error for {url}: {e}")
            return None

    else:
        log_with_time(f"[Scraper] Unknown method '{method}', supported: 'scrapling', 'playwright'")
        return None
