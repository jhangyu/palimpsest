# backend/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel, field_validator
import databases
import sqlalchemy
from typing import Optional
import json
import os
import asyncio
import re
import time
import statistics
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from dotenv import load_dotenv
from dateutil import parser as dateutil_parser

# Load .env file
load_dotenv()

# Fixed imports: use core module
from core.ai import analyze_structure
from core.crawler import crawl_site_logic, get_page_content, compute_visible_word_count, _utcnow_iso as _utcnow_iso_impl
from core.scraper import fetch_page
from core.debug import create_debug_writer

# Helper for timestamped logging
def log_with_time(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

# Shared helpers imported from core.crawler (canonical location)
_utcnow_iso = _utcnow_iso_impl



from apscheduler.schedulers.asyncio import AsyncIOScheduler
from rfeed import Item, Feed

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://palimpsest:palimpsest@db:5432/palimpsest")
database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

# --- Database Schema ---
sites = sqlalchemy.Table(
    "sites", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("url", sqlalchemy.String),
    sqlalchemy.Column("name", sqlalchemy.String),
    sqlalchemy.Column("list_rules", sqlalchemy.JSON),
    sqlalchemy.Column("content_rules", sqlalchemy.JSON),
    # NEW: For self-healing mechanism
    sqlalchemy.Column("consecutive_failure_count", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("refresh_frequency", sqlalchemy.Integer, default=60), # In minutes
    sqlalchemy.Column("scrape_method", sqlalchemy.String, default="scrapling"),
)

articles = sqlalchemy.Table(
    "articles", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("site_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("sites.id")),
    sqlalchemy.Column("title", sqlalchemy.String),
    sqlalchemy.Column("url", sqlalchemy.String, unique=True),
    sqlalchemy.Column("content", sqlalchemy.Text),
    sqlalchemy.Column("image_url", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("published_at", sqlalchemy.String),
    # Analytics columns
    sqlalchemy.Column("created_at", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("updated_at", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("word_count", sqlalchemy.Integer, nullable=True),
)

rss_query_events = sqlalchemy.Table(
    "rss_query_events", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("site_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("sites.id"), nullable=True),
    sqlalchemy.Column("site_identifier", sqlalchemy.String),
    sqlalchemy.Column("requested_at", sqlalchemy.String),
    sqlalchemy.Column("limit_param", sqlalchemy.Integer),
    sqlalchemy.Column("status_code", sqlalchemy.Integer),
)

crawl_attempts = sqlalchemy.Table(
    "crawl_attempts", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("site_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("sites.id")),
    sqlalchemy.Column("started_at", sqlalchemy.String),
    sqlalchemy.Column("finished_at", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("trigger_type", sqlalchemy.String),  # manual / scheduled
    sqlalchemy.Column("status", sqlalchemy.String),  # success / fail / running
    sqlalchemy.Column("articles_found", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("articles_saved", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("articles_updated", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("articles_failed", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("content_fetch_failed", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("parse_failed", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("error_message", sqlalchemy.Text, nullable=True),
)

# --- Scheduler ---
scheduler = AsyncIOScheduler()

async def _record_crawl_attempt(site_id: int, trigger_type: str, url: str, list_rules: dict, content_rules: dict, force_update: bool, scrape_method: str, debug_writer=None):
    """Wrapper that records a crawl attempt around crawl_site_logic."""
    attempt_id = None
    try:
        attempt_id = await database.execute(
            crawl_attempts.insert().values(
                site_id=site_id,
                started_at=_utcnow_iso(),
                trigger_type=trigger_type,
                status="running",
                articles_found=0, articles_saved=0, articles_updated=0,
                articles_failed=0, content_fetch_failed=0, parse_failed=0,
            )
        )
    except Exception as e:
        log_with_time(f"[CrawlAttempt] Failed to create attempt record: {e}")

    crawl_result = await crawl_site_logic(
        site_id=site_id,
        url=url,
        list_rules=list_rules,
        content_rules=content_rules,
        db=database,
        debug_writer=debug_writer,
        force_update=force_update,
        scrape_method=scrape_method,
    )

    if crawl_result is None:
        crawl_result = {"status": "fail", "articles_found": 0, "articles_saved": 0,
                        "articles_updated": 0, "articles_failed": 0,
                        "content_fetch_failed": 0, "parse_failed": 0,
                        "error_message": "crawl_site_logic returned None"}

    if attempt_id is not None:
        try:
            await database.execute(
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
        except Exception as e:
            log_with_time(f"[CrawlAttempt] Failed to update attempt record: {e}")

    return crawl_result

async def scheduled_crawl_job():
    """排程任務：取出所有網站並執行爬蟲（排程模式：只更新時間改變的文章）"""
    print("[Scheduler] Running scheduled crawl...")
    query = "SELECT * FROM sites"
    all_sites = await database.fetch_all(query)
    for site in all_sites:
        try:
            await _record_crawl_attempt(
                site_id=site['id'],
                trigger_type="scheduled",
                url=site['url'],
                list_rules=site['list_rules'] if isinstance(site['list_rules'], dict) else json.loads(site['list_rules']),
                content_rules=site['content_rules'] if isinstance(site['content_rules'], dict) else json.loads(site['content_rules']),
                force_update=False,
                scrape_method=site['scrape_method'] if site['scrape_method'] else "scrapling",
            )
        except Exception as e:
            print(f"[Scheduler] Error crawling site {site['id']}: {e}")

# --- Schema Migration Helpers ---
def _run_schema_migration(engine):
    """Idempotent schema upgrade for existing databases."""
    from sqlalchemy import text as sa_text

    with engine.connect() as conn:
        # Add new columns to articles if they don't exist
        for col, col_type in [("created_at", "VARCHAR"), ("updated_at", "VARCHAR"), ("word_count", "INTEGER")]:
            try:
                conn.execute(sa_text(f"ALTER TABLE articles ADD COLUMN IF NOT EXISTS {col} {col_type}"))
            except Exception as e:
                log_with_time(f"[Migration] Column articles.{col} migration note: {e}")

        # Create indexes if not exist
        index_stmts = [
            "CREATE INDEX IF NOT EXISTS idx_articles_site_id ON articles(site_id)",
            "CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at)",
            "CREATE INDEX IF NOT EXISTS idx_rss_query_events_requested_at ON rss_query_events(requested_at)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_attempts_started_at ON crawl_attempts(started_at)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_attempts_site_started ON crawl_attempts(site_id, started_at)",
        ]
        for stmt in index_stmts:
            try:
                conn.execute(sa_text(stmt))
            except Exception as e:
                log_with_time(f"[Migration] Index creation note: {e}")

        conn.commit()
    log_with_time("[Migration] Schema migration completed.")

async def _backfill_articles():
    """Backfill created_at, updated_at, word_count for existing articles with NULL values."""
    log_with_time("[Backfill] Starting article backfill...")

    # Backfill created_at / updated_at
    rows = await database.fetch_all("SELECT id, published_at FROM articles WHERE created_at IS NULL LIMIT 500")
    if rows:
        log_with_time(f"[Backfill] Backfilling created_at/updated_at for {len(rows)} articles...")
        for row in rows:
            ts = None
            if row['published_at']:
                try:
                    parsed = dateutil_parser.parse(row['published_at'])
                    ts = parsed.isoformat()
                    if not parsed.tzinfo:
                        ts = ts + "Z"
                except Exception:
                    pass
            if ts is None:
                ts = _utcnow_iso()
            try:
                await database.execute(
                    "UPDATE articles SET created_at = :ts, updated_at = :ts WHERE id = :id AND created_at IS NULL",
                    values={"ts": ts, "id": row['id']}
                )
            except Exception as e:
                log_with_time(f"[Backfill] Warning: failed to backfill article {row['id']}: {e}")

    # Backfill word_count
    wc_rows = await database.fetch_all("SELECT id, content FROM articles WHERE word_count IS NULL AND content IS NOT NULL LIMIT 500")
    if wc_rows:
        log_with_time(f"[Backfill] Backfilling word_count for {len(wc_rows)} articles...")
        for row in wc_rows:
            try:
                wc = compute_visible_word_count(row['content'])
                await database.execute(
                    "UPDATE articles SET word_count = :wc WHERE id = :id AND word_count IS NULL",
                    values={"wc": wc, "id": row['id']}
                )
            except Exception as e:
                log_with_time(f"[Backfill] Warning: failed to compute word_count for article {row['id']}: {e}")

    log_with_time("[Backfill] Article backfill completed.")


# --- Lifespan (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    # Create tables if not exist
    sync_url = DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql://")
    engine = sqlalchemy.create_engine(sync_url)
        
    metadata.create_all(engine)

    # Run idempotent migration for existing DBs
    await asyncio.to_thread(_run_schema_migration, engine)

    # Backfill existing articles
    await _backfill_articles()

    # Start scheduler with stagger to prevent thundering herd
    scheduler.add_job(scheduled_crawl_job, 'interval', hours=1, jitter=300)
    scheduler.start()
    print("[Startup] Database connected, scheduler started.")
    yield
    scheduler.shutdown()
    await database.disconnect()
    print("[Shutdown] Database disconnected.")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(
    os.getenv("PALIMPSEST_FRONTEND_DIR", Path(__file__).resolve().parent.parent / "frontend-astro")
).resolve()

# --- Helper Functions ---
def normalize_site_name(name: str) -> str:
    """將網站名稱標準化為 URL 友好的格式"""
    # 替換空白為底線
    name = name.replace(' ', '_')
    # 移除非英文數字底線的字元
    name = re.sub(r'[^a-zA-Z0-9_\-]', '', name)
    # 轉小寫
    name = name.lower()
    return name

async def get_site_by_name_or_id(site_identifier: str, database):
    """根據名稱或 ID 查詢網站"""
    # 先嘗試當作 ID 查詢
    try:
        site_id = int(site_identifier)
        query = sites.select().where(sites.c.id == site_id)
        site = await database.fetch_one(query)
        if site:
            return site
    except ValueError:
        pass
    
    # 嘗試當作名稱查詢
    normalized = normalize_site_name(site_identifier)
    query = sites.select()
    all_sites = await database.fetch_all(query)
    for site in all_sites:
        if normalize_site_name(site['name']) == normalized:
            return site
    return None

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

# --- Analytics Helpers ---

def _parse_iso_to_taipei_date(iso_str: str) -> str | None:
    """Parse an ISO timestamp string and return its Asia/Taipei date as YYYY-MM-DD."""
    if not iso_str:
        return None
    try:
        dt = dateutil_parser.parse(iso_str)
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        taipei_dt = dt.astimezone(TAIPEI_TZ)
        return taipei_dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def _get_date_range(days: int) -> list[str]:
    """Generate a list of YYYY-MM-DD strings for the past N days in Asia/Taipei timezone."""
    today = datetime.now(TAIPEI_TZ).date()
    return [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

def _get_week_boundaries():
    """Get ISO week start (Monday) and end for this week and last week in Asia/Taipei."""
    now_taipei = datetime.now(TAIPEI_TZ)
    today = now_taipei.date()
    # This week: Monday to today
    this_week_start = today - timedelta(days=today.weekday())
    # Last week
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start - timedelta(days=1)
    return this_week_start, today, last_week_start, last_week_end


# --- API Endpoints ---

@app.post("/analyze/list")
async def analyze_list_structure(url: str, debug: bool = False):
    """Parse website list page structure (calls AI)"""
    start_time = time.time()
    log_with_time(f"[Analyze List] Starting analysis for: {url}")

    fetch_start = time.time()
    page = await fetch_page(url)
    fetch_duration = time.time() - fetch_start
    log_with_time(f"[Analyze List] fetch_page completed: {fetch_duration:.2f}s")

    if page is None:
        return {"rules": None, "error": "Failed to fetch page content. The website may be blocking crawlers or taking too long to load."}
    html = page.html_content

    dw = create_debug_writer(debug, "analyze_list", url.replace("https://", "").replace("http://", "").split("/")[0][:30])
    if debug:
        dw.save("01", "raw_html.html", html)

    ai_start = time.time()
    rules = await analyze_structure(html, mode="list", debug_writer=dw)
    ai_duration = time.time() - ai_start
    log_with_time(f"[Analyze List] analyze_structure completed: {ai_duration:.2f}s")

    if not rules:
        return {"rules": None, "error": "AI analysis failed. Check backend logs for details (possibly API quota exceeded)."}

    response = {"rules": rules, "preview_html": html[:500], "error": None}
    if debug:
        response["debug_dir"] = dw.debug_dir

    total_duration = time.time() - start_time
    log_with_time(f"[Analyze List] Total duration: {total_duration:.2f}s")
    return response

@app.post("/analyze/content")
async def analyze_content_structure(url: str, debug: bool = False):
    """解析網站內容頁結構 (呼叫 AI)"""
    start_time = time.time()
    log_with_time(f"[Analyze Content] Starting analysis for: {url}")

    fetch_start = time.time()
    page = await fetch_page(url)
    fetch_duration = time.time() - fetch_start
    log_with_time(f"[Analyze Content] fetch_page completed: {fetch_duration:.2f}s")

    if page is None:
        raise HTTPException(status_code=500, detail="Failed to fetch page content")
    html = page.html_content

    dw = create_debug_writer(debug, "analyze_content", url.replace("https://", "").replace("http://", "").split("/")[0][:30])
    if debug:
        dw.save("01", "raw_html.html", html)

    ai_start = time.time()
    rules = await analyze_structure(html, mode="content", debug_writer=dw)
    ai_duration = time.time() - ai_start
    log_with_time(f"[Analyze Content] analyze_structure completed: {ai_duration:.2f}s")

    response = {"rules": rules}
    if debug:
        response["debug_dir"] = dw.debug_dir

    total_duration = time.time() - start_time
    log_with_time(f"[Analyze Content] Total duration: {total_duration:.2f}s")
    return response

@app.post("/crawl/preview")
async def preview_crawl(req: PreviewRequest):
    """乾跑預覽爬蟲，支援 list / content / both 模式"""
    from core.crawler import test_crawl_logic
    
    dw = create_debug_writer(req.debug, "preview", req.url.replace("https://", "").replace("http://", "").split("/")[0][:30])
    
    results = await test_crawl_logic(
        req.url,
        req.list_rules,
        req.content_rules,
        mode=req.mode,
        target_url=req.target_url,
        debug_writer=dw,
        scrape_method=req.scrape_method or "scrapling",
    )
    
    response = {"status": "success", "data": results}
    if req.debug:
        response["debug_dir"] = dw.debug_dir
    return response

@app.post("/sites/")
async def create_site(
    site: SiteCreate,
    rules: RulesInput,
    background_tasks: BackgroundTasks
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
    )
    site_id = await database.execute(query)
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
    )
    return {"id": site_id, "status": "created and crawling started"}

@app.get("/sites/{site_id}")
async def get_site(site_id: int):
    """取得特定網站資詳細資料"""
    query = sites.select().where(sites.c.id == site_id)
    row = await database.fetch_one(query)
    if not row:
        raise HTTPException(status_code=404, detail="Site not found")
    return dict(row)

@app.put("/sites/{site_id}")
async def update_site(site_id: int, update_data: SiteUpdate):
    """更新網站設定"""
    query = sites.select().where(sites.c.id == site_id)
    site = await database.fetch_one(query)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    values = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not values:
        return {"status": "no change"}
        
    query = sites.update().where(sites.c.id == site_id).values(**values)
    await database.execute(query)
    return {"status": "updated", "site_id": site_id}

@app.post("/sites/{site_id}/duplicate")
async def duplicate_site(site_id: int):
    """複製網站設定 (不含文章，不自動爬取)"""
    query = sites.select().where(sites.c.id == site_id)
    site = await database.fetch_one(query)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    new_query = sites.insert().values(
        url=site['url'],
        name=f"[Copy] {site['name']}",
        list_rules=site['list_rules'],
        content_rules=site['content_rules'],
        refresh_frequency=site['refresh_frequency'],
        consecutive_failure_count=0,
        scrape_method=site['scrape_method'] or "scrapling",
    )
    new_id = await database.execute(new_query)
    return {"id": new_id, "status": "duplicated"}

@app.get("/sites/")
async def list_sites():
    """列出所有網站"""
    query = sites.select()
    rows = await database.fetch_all(query)
    return [dict(row) for row in rows]

@app.delete("/sites/{site_id}")
async def delete_site(site_id: int):
    """刪除指定網站及其所有文章與相關事件"""
    # 刪除相關 crawl attempts 和 RSS query events
    await database.execute(crawl_attempts.delete().where(crawl_attempts.c.site_id == site_id))
    await database.execute(rss_query_events.delete().where(rss_query_events.c.site_id == site_id))

    # 刪除該網站的所有文章
    query = articles.delete().where(articles.c.site_id == site_id)
    await database.execute(query)

    # 刪除該網站
    query = sites.delete().where(sites.c.id == site_id)
    result = await database.execute(query)

    if result == 0:
        raise HTTPException(status_code=404, detail="Site not found")

    return {"status": "deleted", "site_id": site_id}

@app.get("/rss/{site_identifier}")
async def get_rss(site_identifier: str, limit: int = 10):
    """取得指定網站的 RSS Feed
    
    Args:
        site_identifier: 網站名稱（會被標準化）或 ID
        limit: 回傳文章數量上限，預設10，範圍5-30
    """
    # 限制 limit 範圍
    limit = max(5, min(30, limit))
    
    site = await get_site_by_name_or_id(site_identifier, database)
    if not site:
        # Record 404 RSS query event
        try:
            await database.execute(
                rss_query_events.insert().values(
                    site_id=None,
                    site_identifier=site_identifier,
                    requested_at=_utcnow_iso(),
                    limit_param=limit,
                    status_code=404,
                )
            )
        except Exception as e:
            log_with_time(f"[RSS] Failed to record 404 query event: {e}")
        raise HTTPException(status_code=404, detail="Site not found")

    site_name_normalized = normalize_site_name(site['name'])
    
    query = articles.select().where(articles.c.site_id == site['id']).order_by(articles.c.id.desc()).limit(limit)
    rows = await database.fetch_all(query)

    items = []
    for row in rows:
        pub_date = row['published_at']
        # Convert string to datetime if needed
        if isinstance(pub_date, str):
            try:
                pub_date = dateutil_parser.parse(pub_date)
            except Exception:
                pub_date = datetime.now()
        
        items.append(Item(
            title=row['title'],
            link=row['url'],
            description=row['content'],
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
        await database.execute(
            rss_query_events.insert().values(
                site_id=site['id'],
                site_identifier=site_identifier,
                requested_at=_utcnow_iso(),
                limit_param=limit,
                status_code=200,
            )
        )
    except Exception as e:
        log_with_time(f"[RSS] Failed to record 200 query event: {e}")

    return Response(content=feed.rss(), media_type="application/xml")

@app.post("/crawl/{site_id}")
async def trigger_crawl(site_id: int, background_tasks: BackgroundTasks, debug: bool = False):
    """手動觸發指定網站爬取"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [API] trigger_crawl called for site {site_id}")
    query = sites.select().where(sites.c.id == site_id)
    site = await database.fetch_one(query)
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
    )
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [API] Background task added")
    
    response = {"status": "crawl started"}
    if debug:
        response["debug_dir"] = dw.debug_dir
    return response


# --- Analytics API ---

@app.get("/analytics/overview")
async def get_analytics_overview(days: int = 30):
    """Aggregated analytics overview for the dashboard.

    Returns summary metrics, chart datasets, and latest articles.
    All daily bucketing uses Asia/Taipei timezone.
    """
    # Clamp days to 7-90
    days = max(7, min(90, days))

    date_labels = _get_date_range(days)
    this_week_start, today, last_week_start, last_week_end = _get_week_boundaries()

    # --- Fetch all articles with analytics columns ---
    all_articles = await database.fetch_all(
        "SELECT id, site_id, published_at, created_at, word_count FROM articles"
    )

    # --- Fetch all sites for name mapping ---
    all_sites_rows = await database.fetch_all("SELECT id, name FROM sites")
    site_name_map = {row['id']: row['name'] for row in all_sites_rows}

    # --- Summary ---
    total_article_scrap = len(all_articles)

    # Per-article: parse created_at to Taipei date
    article_taipei_dates = []
    for a in all_articles:
        d = _parse_iso_to_taipei_date(a['created_at'])
        article_taipei_dates.append(d)

    # New articles this week / last week
    new_articles_this_week = 0
    new_articles_last_week = 0
    for d_str in article_taipei_dates:
        if d_str is None:
            continue
        try:
            from datetime import date as _date_cls
            d = _date_cls.fromisoformat(d_str)
        except Exception:
            continue
        if this_week_start <= d <= today:
            new_articles_this_week += 1
        if last_week_start <= d <= last_week_end:
            new_articles_last_week += 1

    # Weekly change pct
    new_articles_weekly_change_pct = None
    if new_articles_last_week > 0:
        new_articles_weekly_change_pct = round(
            ((new_articles_this_week - new_articles_last_week) / new_articles_last_week) * 100, 1
        )

    # --- Median feed update minutes ---
    # Group articles by site_id, sort by published_at, compute intervals
    from collections import defaultdict
    site_articles_times: dict[int, list[datetime]] = defaultdict(list)
    for a in all_articles:
        if a['published_at'] and a['site_id']:
            try:
                dt = dateutil_parser.parse(a['published_at'])
                site_articles_times[a['site_id']].append(dt)
            except Exception:
                pass

    feed_avg_intervals = []
    for sid, times in site_articles_times.items():
        if len(times) < 2:
            continue
        times.sort()
        diffs = [(times[i+1] - times[i]).total_seconds() / 60.0 for i in range(len(times) - 1)]
        diffs = [d for d in diffs if d > 0]  # skip zero/negative diffs
        if diffs:
            avg_interval = sum(diffs) / len(diffs)
            feed_avg_intervals.append(avg_interval)

    median_feed_update_minutes = None
    if feed_avg_intervals:
        median_feed_update_minutes = round(statistics.median(feed_avg_intervals), 1)

    # Median feed update change pct (simplified: compare overall, not weekly, as insufficient data is common)
    median_feed_update_change_pct = None

    # --- Median article word count ---
    word_counts = [a['word_count'] for a in all_articles if a['word_count'] is not None and a['word_count'] > 0]
    median_article_word_count = None
    if word_counts:
        median_article_word_count = round(statistics.median(word_counts))

    summary = {
        "total_article_scrap": total_article_scrap,
        "new_articles_last_week": new_articles_last_week,
        "new_articles_this_week": new_articles_this_week,
        "new_articles_weekly_change_pct": new_articles_weekly_change_pct,
        "median_feed_update_minutes": median_feed_update_minutes,
        "median_feed_update_change_pct": median_feed_update_change_pct,
        "median_article_word_count": median_article_word_count,
        "median_article_word_count_trend_label": "Across all stored articles",
    }

    # --- Articles counts overview (daily new by feed source) ---
    # Build: date -> site_id -> count
    daily_feed_counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for a, d_str in zip(all_articles, article_taipei_dates):
        if d_str and d_str in date_labels:
            sid = a['site_id']
            daily_feed_counts[d_str][sid] += 1

    # Collect unique site_ids that appear in window
    active_site_ids = set()
    for d_str in date_labels:
        for sid in daily_feed_counts.get(d_str, {}):
            active_site_ids.add(sid)
    active_site_ids = sorted(active_site_ids)

    # Color palette for feeds
    FEED_COLORS = [
        "#1ABB9C", "#7533f9", "#198754", "#ffc107", "#dc3545",
        "#0d6efd", "#6610f2", "#fd7e14", "#20c997", "#6f42c1",
        "#d63384", "#0dcaf0", "#adb5bd", "#e35d6a", "#6ea8fe",
    ]

    articles_counts_overview = {
        "labels": date_labels,
        "datasets": [
            {
                "label": site_name_map.get(sid, f"Feed #{sid}"),
                "data": [daily_feed_counts.get(d, {}).get(sid, 0) for d in date_labels],
                "color": FEED_COLORS[i % len(FEED_COLORS)],
            }
            for i, sid in enumerate(active_site_ids)
        ]
    }

    # --- Feeds distribution (past 30 days) ---
    feed_dist: dict[int, int] = defaultdict(int)
    for a, d_str in zip(all_articles, article_taipei_dates):
        if d_str and d_str in date_labels:
            feed_dist[a['site_id']] += 1

    feeds_distribution = {
        "items": [
            {
                "name": site_name_map.get(sid, f"Feed #{sid}"),
                "value": count,
                "color": FEED_COLORS[i % len(FEED_COLORS)],
            }
            for i, (sid, count) in enumerate(sorted(feed_dist.items(), key=lambda x: -x[1]))
        ]
    }

    # --- Traffic metrics: RSS query ---
    rss_events = await database.fetch_all("SELECT requested_at, status_code FROM rss_query_events")
    daily_rss_counts: dict[str, int] = defaultdict(int)
    for evt in rss_events:
        d = _parse_iso_to_taipei_date(evt['requested_at'])
        if d and d in date_labels:
            daily_rss_counts[d] += 1

    rss_query_dataset = {
        "labels": date_labels,
        "datasets": [{"label": "RSS Queries", "data": [daily_rss_counts.get(d, 0) for d in date_labels]}]
    }

    # --- Traffic metrics: Article scrap (from crawl_attempts) ---
    crawl_rows = await database.fetch_all(
        "SELECT started_at, articles_saved, articles_updated, articles_failed FROM crawl_attempts"
    )
    daily_scrap_success: dict[str, int] = defaultdict(int)
    daily_scrap_fail: dict[str, int] = defaultdict(int)
    for cr in crawl_rows:
        d = _parse_iso_to_taipei_date(cr['started_at'])
        if d and d in date_labels:
            daily_scrap_success[d] += (cr['articles_saved'] or 0) + (cr['articles_updated'] or 0)
            daily_scrap_fail[d] += (cr['articles_failed'] or 0)

    article_scrap_dataset = {
        "labels": date_labels,
        "datasets": [
            {"label": "Success", "data": [daily_scrap_success.get(d, 0) for d in date_labels]},
            {"label": "Fail", "data": [daily_scrap_fail.get(d, 0) for d in date_labels]},
        ]
    }

    traffic_metrics = {
        "rss_query": rss_query_dataset,
        "article_scrap": article_scrap_dataset,
    }

    # --- Article growth (cumulative) ---
    # Sort all articles by created_at Taipei date, compute cumulative by day
    sorted_dates = sorted([d for d in article_taipei_dates if d is not None])
    cumulative = 0
    date_cumulative: dict[str, int] = {}
    date_idx = 0
    for d in date_labels:
        while date_idx < len(sorted_dates) and sorted_dates[date_idx] <= d:
            cumulative += 1
            date_idx += 1
        date_cumulative[d] = cumulative

    article_growth = {
        "labels": date_labels,
        "datasets": [{"label": "Total Articles", "data": [date_cumulative.get(d, 0) for d in date_labels]}]
    }

    # --- Latest articles ---
    latest_rows = await database.fetch_all(
        "SELECT a.site_id, a.title, a.url, a.created_at, a.word_count "
        "FROM articles a ORDER BY a.created_at DESC NULLS LAST LIMIT 10"
    )
    latest_articles = [
        {
            "feed_name": site_name_map.get(row['site_id'], f"Feed #{row['site_id']}"),
            "article_title": row['title'],
            "update_time": row['created_at'] or "",
            "word_count": row['word_count'] or 0,
            "ori_url": row['url'],
        }
        for row in latest_rows
    ]

    return {
        "summary": summary,
        "articles_counts_overview": articles_counts_overview,
        "feeds_distribution": feeds_distribution,
        "traffic_metrics": traffic_metrics,
        "article_growth": article_growth,
        "daily_rss_query": rss_query_dataset,
        "latest_articles": latest_articles,
    }


@app.get("/articles/list")
async def list_articles(
    filter: str = "all",
    search: str = "",
    page: int = 1,
    page_size: int = 100,
):
    """List articles with time filtering, search, and pagination.

    filter: today | week | month | all
    search: optional text search against title and feed name
    page / page_size: pagination (1-based page index)
    """
    from datetime import timezone as _tz

    # Sanitize inputs
    page = max(1, page)
    page_size = max(1, min(500, page_size))
    if filter not in ("today", "week", "month", "all"):
        filter = "all"

    # --- Fetch site name map (same pattern as analytics_overview) ---
    all_sites_rows = await database.fetch_all("SELECT id, name FROM sites")
    site_name_map = {row['id']: row['name'] for row in all_sites_rows}

    # --- Compute time boundaries in Taipei timezone ---
    now_taipei = datetime.now(TAIPEI_TZ)
    today_start = datetime(now_taipei.year, now_taipei.month, now_taipei.day, 0, 0, 0, tzinfo=TAIPEI_TZ)
    today_end = today_start + timedelta(days=1)
    week_start = today_start - timedelta(days=6)
    month_start = today_start - timedelta(days=29)

    today_start_utc = today_start.astimezone(_tz.utc)
    today_end_utc = today_end.astimezone(_tz.utc)
    week_start_utc = week_start.astimezone(_tz.utc)
    month_start_utc = month_start.astimezone(_tz.utc)

    # --- Build search condition ---
    search_sql = ""
    search_params: dict = {}
    if search.strip():
        search_sql = (
            " AND (a.title ILIKE :search_pat"
            " OR a.site_id IN (SELECT id FROM sites WHERE name ILIKE :search_pat))"
        )
        search_params["search_pat"] = f"%{search.strip()}%"

    # --- filter_counts: compute counts for all 4 time ranges ---
    async def _count(extra_time_sql: str, extra_time_params: dict) -> int:
        sql = "SELECT COUNT(*) AS cnt FROM articles a WHERE 1=1" + search_sql + extra_time_sql
        row = await database.fetch_one(sql, values={**search_params, **extra_time_params})
        return row['cnt'] if row else 0

    today_count = await _count(
        " AND CAST(a.created_at AS TIMESTAMPTZ) >= :t_from"
        " AND CAST(a.created_at AS TIMESTAMPTZ) < :t_to",
        {"t_from": today_start_utc, "t_to": today_end_utc},
    )
    week_count = await _count(
        " AND CAST(a.created_at AS TIMESTAMPTZ) >= :t_from",
        {"t_from": week_start_utc},
    )
    month_count = await _count(
        " AND CAST(a.created_at AS TIMESTAMPTZ) >= :t_from",
        {"t_from": month_start_utc},
    )
    all_count = await _count("", {})

    filter_counts = {
        "today": today_count,
        "week": week_count,
        "month": month_count,
        "all": all_count,
    }

    # --- Build time condition for the main paginated query ---
    time_sql = ""
    time_params: dict = {}
    if filter == "today":
        time_sql = (
            " AND CAST(a.created_at AS TIMESTAMPTZ) >= :main_from"
            " AND CAST(a.created_at AS TIMESTAMPTZ) < :main_to"
        )
        time_params = {"main_from": today_start_utc, "main_to": today_end_utc}
    elif filter == "week":
        time_sql = " AND CAST(a.created_at AS TIMESTAMPTZ) >= :main_from"
        time_params = {"main_from": week_start_utc}
    elif filter == "month":
        time_sql = " AND CAST(a.created_at AS TIMESTAMPTZ) >= :main_from"
        time_params = {"main_from": month_start_utc}
    # "all" → no time condition

    total = filter_counts[filter]

    # --- Paginated main query ---
    offset = (page - 1) * page_size
    main_sql = (
        "SELECT a.site_id, a.title, a.url, a.image_url, a.created_at, a.word_count "
        "FROM articles a WHERE 1=1"
        + search_sql
        + time_sql
        + " ORDER BY a.created_at DESC NULLS LAST"
        " LIMIT :lim OFFSET :off"
    )
    all_params = {**search_params, **time_params, "lim": page_size, "off": offset}
    rows = await database.fetch_all(main_sql, values=all_params)

    article_list = [
        {
            "article_title": row['title'],
            "image_url": row['image_url'],
            "feed_name": site_name_map.get(row['site_id'], f"Feed #{row['site_id']}"),
            "word_count": row['word_count'] or 0,
            "update_time": row['created_at'] or "",
            "ori_url": row['url'],
        }
        for row in rows
    ]

    return {
        "articles": article_list,
        "filter_counts": filter_counts,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    try:
        await database.execute("SELECT 1")
        return {"status": "healthy", "db": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "db": str(e)}

@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    """Serve the built Astro frontend when packaged in the Docker image."""
    if not FRONTEND_DIR.is_dir():
        raise HTTPException(status_code=404, detail="Frontend not built")

    safe_path = full_path.strip("/")
    # Block path traversal before any path resolution
    if ".." in safe_path:
        raise HTTPException(status_code=403, detail="Forbidden")

    candidates = []

    if safe_path:
        # Validate path components before constructing candidates
        path_parts = safe_path.split("/")
        for part in path_parts:
            if part == ".." or part.startswith("."):
                raise HTTPException(status_code=403, detail="Forbidden")

        requested = FRONTEND_DIR / safe_path
        if requested.is_file():
            candidates.append(requested)
        if (requested / "index.html").is_file():
            candidates.append(requested / "index.html")

        first_segment = safe_path.split("/", 1)[0]
        if first_segment and (FRONTEND_DIR / first_segment / "index.html").is_file():
            candidates.append(FRONTEND_DIR / first_segment / "index.html")

    if (FRONTEND_DIR / "index.html").is_file():
        candidates.append(FRONTEND_DIR / "index.html")

    for candidate in candidates:
        # Final safety check - ensure resolved path is within FRONTEND_DIR
        if candidate.resolve().is_relative_to(FRONTEND_DIR):
            return FileResponse(candidate)

    raise HTTPException(status_code=404, detail="Frontend asset not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)
