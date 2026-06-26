"""
---
name: analytics_router
description: "Analytics overview and paginated articles list API routes"
type: router
target:
  layer: backend
  domain: analytics
spec_doc: null
test_file: null
functions:
  - name: get_analytics_overview
    line: 35
    purpose: "GET /analytics/overview — return aggregated analytics dashboard data for N days"
  - name: list_articles
    line: 45
    purpose: "GET /articles/list — paginated article listing with filter (today/week/month/all) and search"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

from fastapi import APIRouter, Depends

from core.db import get_db
from routers._deps import require_user
from services.analytics_service import compute_analytics_overview, compute_articles_list

router = APIRouter(tags=["analytics"])


@router.get("/analytics/overview")
async def get_analytics_overview(
    days: int = 30,
    current_user: dict = Depends(require_user),
    db=Depends(get_db),
):
    return await compute_analytics_overview(db, days)


@router.get("/articles/list")
async def list_articles(
    filter: str = "all",
    search: str = "",
    page: int = 1,
    page_size: int = 100,
    current_user: dict = Depends(require_user),
    db=Depends(get_db),
):
    return await compute_articles_list(db, filter, search, page, page_size)
