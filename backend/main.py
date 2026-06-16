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
import re
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Fixed imports: use core module
from core.ai import analyze_structure
from core.crawler import crawl_site_logic, get_page_content
from core.scraper import fetch_page
from core.debug import create_debug_writer

# Helper for timestamped logging
def log_with_time(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

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
)

# --- Scheduler ---
scheduler = AsyncIOScheduler()

async def scheduled_crawl_job():
    """排程任務：取出所有網站並執行爬蟲（排程模式：只更新時間改變的文章）"""
    print("[Scheduler] Running scheduled crawl...")
    query = "SELECT * FROM sites"
    all_sites = await database.fetch_all(query)
    for site in all_sites:
        try:
            await crawl_site_logic(
                site_id=site['id'],
                url=site['url'],
                list_rules=site['list_rules'] if isinstance(site['list_rules'], dict) else json.loads(site['list_rules']),
                content_rules=site['content_rules'] if isinstance(site['content_rules'], dict) else json.loads(site['content_rules']),
                db=database,
                force_update=False,  # 排程模式：不覆蓋，只更新時間改變的文章
                scrape_method=site['scrape_method'] if site['scrape_method'] else "scrapling",
            )
        except Exception as e:
            print(f"[Scheduler] Error crawling site {site['id']}: {e}")

# --- Lifespan (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    # Create tables if not exist
    sync_url = DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql://")
    engine = sqlalchemy.create_engine(sync_url)
        
    metadata.create_all(engine)

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
    # 背景觸發爬蟲（初始抓取視為手動重爬）
    background_tasks.add_task(
        crawl_site_logic,
        site_id, site.url,
        rules.list_rules, rules.content_rules,
        database,
        force_update=True,  # 初始抓取：強制更新所有文章
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
    """刪除指定網站及其所有文章"""
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
                from dateutil import parser
                pub_date = parser.parse(pub_date)
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
        crawl_site_logic,
        site['id'], site['url'],
        list_rules,
        content_rules,
        database,
        debug_writer=dw,
        force_update=True,  # 手動重爬模式：強制更新所有文章
        scrape_method=site['scrape_method'] if site['scrape_method'] else "scrapling",
    )
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [API] Background task added")
    
    response = {"status": "crawl started"}
    if debug:
        response["debug_dir"] = dw.debug_dir
    return response

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
