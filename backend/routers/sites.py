"""Sites, RSS, crawl, and analyze endpoints.

Extracted from backend/main.py — every function is a verbatim copy of the
original logic.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator
from dateutil import parser as dateutil_parser
from rfeed import Item, Feed
from sqlalchemy import text

from core.ai import analyze_with_providers
from core.crawler import crawl_site_logic, _utcnow_iso as _utcnow_iso_impl
from core.scraper import fetch_page
from core.debug import create_debug_writer
from core.ownership import check_site_owner_or_admin
from core.db import get_db, sites, articles, rss_query_events, crawl_attempts, ai_tables as _ai_tables
from core.llm.service import NoProviderAvailableError
from routers._deps import (
    require_user, _csrf_dependency,
    log_with_time, normalize_site_name, get_site_by_name_or_id,
    require_kek,
)

# Shared helpers imported from core.crawler (canonical location)
_utcnow_iso = _utcnow_iso_impl

router = APIRouter(tags=["sites"])

# Module-level set for graceful shutdown tracking
_background_tasks: set[asyncio.Task] = set()


# --- Pydantic Models ---

class SiteCreate(BaseModel):
    url: str
    name: str
    refresh_frequency: Optional[int] = 60
    scrape_method: Optional[str] = "scrapling"

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

class SiteUpdate(BaseModel):
    url: Optional[str] = None
    name: Optional[str] = None
    refresh_frequency: Optional[int] = None
    list_rules: Optional[dict] = None
    content_rules: Optional[dict] = None
    scrape_method: Optional[str] = None

class RulesInput(BaseModel):
    list_rules: dict
    content_rules: dict

class PreviewRequest(BaseModel):
    url: str
    list_rules: dict
    content_rules: dict
    mode: Optional[str] = "both"  # "list", "content", or "both"
    target_url: Optional[str] = None  # 用於 content 模式下的單篇文章測試
    debug: Optional[bool] = False
    scrape_method: Optional[str] = "scrapling"


# --- Shared helper for _record_crawl_attempt ---

async def _record_crawl_attempt(site_id: int, trigger_type: str, url: str, list_rules: dict, content_rules: dict, force_update: bool, scrape_method: str, debug_writer=None, owner_user_id=None, db=None, kek_backend=None):
    """Wrapper that records a crawl attempt around crawl_site_logic."""
    if db is None:
        from core.db import async_session_factory
        async with async_session_factory() as _session:
            return await _record_crawl_attempt(
                site_id=site_id,
                trigger_type=trigger_type,
                url=url,
                list_rules=list_rules,
                content_rules=content_rules,
                force_update=force_update,
                scrape_method=scrape_method,
                debug_writer=debug_writer,
                owner_user_id=owner_user_id,
                db=_session,
                kek_backend=kek_backend,
            )

    attempt_id = None
    try:
        result = await db.execute(
            crawl_attempts.insert().values(
                site_id=site_id,
                started_at=_utcnow_iso(),
                trigger_type=trigger_type,
                status="running",
                articles_found=0, articles_saved=0, articles_updated=0,
                articles_failed=0, content_fetch_failed=0, parse_failed=0,
            )
        )
        await db.commit()
        attempt_id = result.inserted_primary_key[0]
    except Exception as e:
        log_with_time(f"[CrawlAttempt] Failed to create attempt record: {e}")

    _kek_backend = kek_backend

    crawl_result = await crawl_site_logic(
        site_id=site_id,
        url=url,
        list_rules=list_rules,
        content_rules=content_rules,
        db=db,
        debug_writer=debug_writer,
        force_update=force_update,
        scrape_method=scrape_method,
        owner_user_id=owner_user_id,
        ai_tables=_ai_tables,
        kek_backend=_kek_backend,
    )

    if crawl_result is None:
        crawl_result = {"status": "fail", "articles_found": 0, "articles_saved": 0,
                        "articles_updated": 0, "articles_failed": 0,
                        "content_fetch_failed": 0, "parse_failed": 0,
                        "error_message": "crawl_site_logic returned None"}

    if attempt_id is not None:
        try:
            await db.execute(
                crawl_attempts.update().where(crawl_attempts.c.id == attempt_id).values(
                    finished_at=_utcnow_iso(),
                    status=crawl_result.get("status", "fail"),
                    articles_found=crawl_result.get("articles_found", 0),
                    articles_saved=crawl_result.get("articles_saved", 0),
                    articles_updated=crawl_result.get("articles_updated", 0),
                    articles_failed=crawl_result.get("articles_failed", 0),
                    content_fetch_failed=crawl_result.get("content_fetch_failed", 0),
                    parse_failed=crawl_result.get("parse_failed", 0),
                    error_message=crawl_result.get("error_message"),
                )
            )
            await db.commit()
        except Exception as e:
            log_with_time(f"[CrawlAttempt] Failed to update attempt record: {e}")


# --- Shared helper for analyze endpoints ---

async def _run_analyze(mode: str, url: str, debug: bool, current_user: dict, is_admin: bool, db=None, kek_backend=None) -> dict:
    """Shared logic for /analyze/list and /analyze/content route handlers.

    Fetches the page, invokes the AI provider, and returns a response dict.
    Raises HTTPException(503) when no provider is available.
    Returns {"rules": None, "error": "..."} when the page cannot be fetched or
    the AI analysis fails.
    """
    _kek_backend = kek_backend

    label = f"Analyze {mode.title()}"
    start_time = time.time()
    log_with_time(f"[{label}] Starting analysis for: {url}")

    fetch_start = time.time()
    page = await fetch_page(url)
    fetch_duration = time.time() - fetch_start
    log_with_time(f"[{label}] fetch_page completed: {fetch_duration:.2f}s")

    if page is None:
        return {"rules": None, "error": "Failed to fetch page content. The website may be blocking crawlers or taking too long to load."}
    html = page.html_content

    domain = url.replace("https://", "").replace("http://", "").split("/")[0][:30]
    dw = create_debug_writer(debug, f"analyze_{mode}", domain)
    if debug:
        dw.save("01", "raw_html.html", html)

    ai_start = time.time()
    try:
        rules = await analyze_with_providers(
            html, mode,
            user_id=current_user["id"],
            db=db,
            tables=_ai_tables,
            kek_backend=_kek_backend,
            url=url,
            debug_writer=dw,
        )
    except NoProviderAvailableError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "no_provider_available", "message": str(e) or "No AI provider available. Configure a provider in AI Service settings."},
        )
    ai_duration = time.time() - ai_start
    log_with_time(f"[{label}] analyze completed: {ai_duration:.2f}s")

    if not rules:
        return {"rules": None, "error": "AI analysis failed. Check backend logs for details."}

    response: dict = {"rules": rules, "error": None}
    if mode == "list":
        response["preview_html"] = html[:500]

    if debug:
        response["debug_dir"] = dw.debug_dir

    total_duration = time.time() - start_time
    log_with_time(f"[{label}] Total duration: {total_duration:.2f}s")
    return response


# --- Endpoints ---

@router.post("/analyze/list")
async def analyze_list_structure(url: str, debug: bool = False, current_user: dict = Depends(require_user), db=Depends(get_db), kek=Depends(require_kek)):
    """Parse website list page structure (calls AI)"""
    is_admin = "admin" in current_user.get("roles", [])
    return await _run_analyze("list", url, debug, current_user, is_admin, db=db, kek_backend=kek)

@router.post("/analyze/content")
async def analyze_content_structure(url: str, debug: bool = False, current_user: dict = Depends(require_user), db=Depends(get_db), kek=Depends(require_kek)):
    """解析網站內容頁結構 (呼叫 AI)"""
    is_admin = "admin" in current_user.get("roles", [])
    return await _run_analyze("content", url, debug, current_user, is_admin, db=db, kek_backend=kek)

@router.post("/crawl/preview")
async def preview_crawl(req: PreviewRequest, current_user: dict = Depends(require_user)):
    """乾跑預覽爬蟲，支援 list / content / both 模式"""
    from core.crawler import test_crawl_logic

    dw = create_debug_writer(req.debug or False, "preview", req.url.replace("https://", "").replace("http://", "").split("/")[0][:30])

    results = await test_crawl_logic(
        req.url,
        req.list_rules,
        req.content_rules,
        mode=req.mode or "both",
        target_url=req.target_url,
        debug_writer=dw,
        scrape_method=req.scrape_method or "scrapling",
    )

    response = {"status": "success", "data": results}
    if req.debug:
        response["debug_dir"] = dw.debug_dir
    return response

@router.post("/sites/", dependencies=[Depends(_csrf_dependency)])
async def create_site(
    site: SiteCreate,
    rules: RulesInput,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_user),
    db=Depends(get_db),
):
    """新增網站並開始背景爬取"""
    query = sites.insert().values(
        url=site.url,
        name=site.name,
        list_rules=rules.list_rules,
        content_rules=rules.content_rules,
        consecutive_failure_count=0,
        refresh_frequency=site.refresh_frequency,
        scrape_method=site.scrape_method or "scrapling",
        owner_user_id=current_user["id"],
    )
    result = await db.execute(query)
    await db.commit()
    site_id = result.inserted_primary_key[0]
    # 背景觸發爬蟲（初始抓取視為手動重爬），with attempt recording
    background_tasks.add_task(
        _record_crawl_attempt,
        site_id=site_id,
        trigger_type="manual",
        url=site.url,
        list_rules=rules.list_rules,
        content_rules=rules.content_rules,
        force_update=True,
        scrape_method=site.scrape_method or "scrapling",
        owner_user_id=current_user["id"],
        db=db,
        kek_backend=request.app.state.kek_backend,
    )
    return {"id": site_id, "status": "created and crawling started"}

@router.get("/sites/{site_id}")
async def get_site(site_id: int, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """取得特定網站資詳細資料"""
    query = sites.select().where(sites.c.id == site_id)
    row = (await db.execute(query)).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Site not found")
    is_admin = "admin" in current_user.get("roles", [])
    if not check_site_owner_or_admin(row, current_user["id"], is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to access this site")
    return dict(row)

@router.put("/sites/{site_id}", dependencies=[Depends(_csrf_dependency)])
async def update_site(site_id: int, update_data: SiteUpdate, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """更新網站設定"""
    query = sites.select().where(sites.c.id == site_id)
    site = (await db.execute(query)).mappings().first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    is_admin = "admin" in current_user.get("roles", [])
    if not check_site_owner_or_admin(site, current_user["id"], is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to modify this site")

    values = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not values:
        return {"status": "no change"}

    query = sites.update().where(sites.c.id == site_id).values(**values)
    await db.execute(query)
    await db.commit()
    return {"status": "updated", "site_id": site_id}

@router.post("/sites/{site_id}/duplicate", dependencies=[Depends(_csrf_dependency)])
async def duplicate_site(site_id: int, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """複製網站設定 (不含文章，不自動爬取)"""
    query = sites.select().where(sites.c.id == site_id)
    site = (await db.execute(query)).mappings().first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    is_admin = "admin" in current_user.get("roles", [])
    if not check_site_owner_or_admin(site, current_user["id"], is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to access this site")

    new_query = sites.insert().values(
        url=site['url'],
        name=f"[Copy] {site['name']}",
        list_rules=site['list_rules'],
        content_rules=site['content_rules'],
        refresh_frequency=site['refresh_frequency'],
        consecutive_failure_count=0,
        scrape_method=site['scrape_method'] or "scrapling",
        owner_user_id=current_user["id"],
    )
    result = await db.execute(new_query)
    await db.commit()
    new_id = result.inserted_primary_key[0]
    return {"id": new_id, "status": "duplicated"}

@router.get("/sites/")
async def list_sites(current_user: dict = Depends(require_user), db=Depends(get_db)):
    """列出所有網站（只返回清單需要的欄位，排除 list_rules/content_rules 大型 JSON）"""
    rows = (await db.execute(
        text(
            "SELECT id, name, url, refresh_frequency, scrape_method, "
            "consecutive_failure_count, owner_user_id FROM sites"
        )
    )).mappings().all()
    return [dict(row) for row in rows]

@router.delete("/sites/{site_id}", dependencies=[Depends(_csrf_dependency)])
async def delete_site(site_id: int, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """刪除指定網站及其所有文章與相關事件"""
    site = (await db.execute(sites.select().where(sites.c.id == site_id))).mappings().first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    is_admin = "admin" in current_user.get("roles", [])
    if not check_site_owner_or_admin(site, current_user["id"], is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to modify this site")

    async with db.begin():
        # 刪除相關 crawl attempts 和 RSS query events
        await db.execute(crawl_attempts.delete().where(crawl_attempts.c.site_id == site_id))
        await db.execute(rss_query_events.delete().where(rss_query_events.c.site_id == site_id))

        # 刪除該網站的所有文章
        await db.execute(articles.delete().where(articles.c.site_id == site_id))

        # 刪除該網站
        await db.execute(sites.delete().where(sites.c.id == site_id))

    return {"status": "deleted", "site_id": site_id}

@router.get("/rss/{site_identifier}")
async def get_rss(site_identifier: str, limit: int = 20, db=Depends(get_db)):
    """取得指定網站的 RSS Feed

    Args:
        site_identifier: 網站名稱（會被標準化）或 ID
        limit: 回傳文章數量上限，預設20，範圍5-30
    """
    # 限制 limit 範圍
    limit = max(5, min(30, limit))

    site = await get_site_by_name_or_id(site_identifier, db)
    if not site:
        # Record 404 RSS query event
        try:
            await db.execute(
                rss_query_events.insert().values(
                    site_id=None,
                    site_identifier=site_identifier,
                    requested_at=_utcnow_iso(),
                    limit_param=limit,
                    status_code=404,
                )
            )
            await db.commit()
        except Exception as e:
            log_with_time(f"[RSS] Failed to record 404 query event: {e}")
        raise HTTPException(status_code=404, detail="Site not found")

    site_name_normalized = normalize_site_name(site['name'])

    query = articles.select().where(articles.c.site_id == site['id']).order_by(articles.c.id.desc()).limit(limit)
    rows = (await db.execute(query)).mappings().all()

    items = []
    for row in rows:
        pub_date = row['published_at']
        # DD-10: published_at is now TIMESTAMPTZ (datetime); handle legacy strings gracefully
        if isinstance(pub_date, str):
            try:
                pub_date = dateutil_parser.parse(pub_date)
            except Exception:
                pub_date = datetime.now(timezone.utc)
        elif pub_date is None:
            pub_date = datetime.now(timezone.utc)

        items.append(Item(
            title=row['title'],
            link=row['url'],
            description=row['content'],
            author=row['author'] or None,
            pubDate=pub_date
        ))

    feed = Feed(
        title=site['name'],
        link=site['url'],
        description=f"RSS feed for {site['name']}",
        items=items
    )

    # Record 200 RSS query event
    try:
        await db.execute(
            rss_query_events.insert().values(
                site_id=site['id'],
                site_identifier=site_identifier,
                requested_at=_utcnow_iso(),
                limit_param=limit,
                status_code=200,
            )
        )
        await db.commit()
    except Exception as e:
        log_with_time(f"[RSS] Failed to record 200 query event: {e}")

    return Response(content=feed.rss(), media_type="application/xml")

@router.post("/crawl/{site_id}", dependencies=[Depends(_csrf_dependency)])
async def trigger_crawl(site_id: int, request: Request, background_tasks: BackgroundTasks, debug: bool = False, current_user: dict = Depends(require_user), db=Depends(get_db)):
    """手動觸發指定網站爬取"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [API] trigger_crawl called for site {site_id}")
    query = sites.select().where(sites.c.id == site_id)
    site = (await db.execute(query)).mappings().first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    list_rules = site['list_rules'] if isinstance(site['list_rules'], dict) else json.loads(site['list_rules'])
    content_rules = site['content_rules'] if isinstance(site['content_rules'], dict) else json.loads(site['content_rules'])

    dw = create_debug_writer(debug, "crawl", site['name'][:30])

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [API] list_rules: {list_rules}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [API] content_rules: {content_rules}")

    background_tasks.add_task(
        _record_crawl_attempt,
        site_id=site['id'],
        trigger_type="manual",
        url=site['url'],
        list_rules=list_rules,
        content_rules=content_rules,
        force_update=True,
        scrape_method=site['scrape_method'] if site['scrape_method'] else "scrapling",
        debug_writer=dw,
        owner_user_id=current_user["id"],
        db=db,
        kek_backend=request.app.state.kek_backend,
    )
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [API] Background task added")

    response: dict = {"status": "crawl started"}
    if debug:
        response["debug_dir"] = dw.debug_dir
    return response
