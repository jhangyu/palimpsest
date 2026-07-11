"""
---
name: notifications_router
description: "Notifications API route — surfaces recent crawl-failure and AI re-analyze events grouped by site"
type: router
target:
  layer: backend
  domain: notifications
spec_doc: null
test_file: null
functions:
  - name: _classify_error
    line: 46
    purpose: "Classify crawl error message as 'fail_access' or 'fail_crawl' by keyword matching"
  - name: _to_iso
    line: 56
    purpose: "Convert datetime object or string to ISO 8601 string for consistent sort comparison"
  - name: get_notifications
    line: 65
    purpose: "GET /api/notifications — return grouped crawl-failure and AI-repair events, sorted by time"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, desc

from core.db import get_db, sites, crawl_attempts, crawl_repair_tables, users
from routers._deps import require_user

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Keywords that indicate an access-level failure (case-insensitive match)
_ACCESS_KEYWORDS = (
    "timeout", "connection", "http", "unreachable", "dns",
    "refused", "ssl", "network",
)


def _classify_error(error_message: Optional[str]) -> str:
    """Return 'fail_access' or 'fail_crawl' based on error_message content."""
    if error_message:
        lower = error_message.lower()
        for kw in _ACCESS_KEYWORDS:
            if kw in lower:
                return "fail_access"
    return "fail_crawl"


def _to_iso(t) -> str:
    """Convert a datetime or ISO string to an ISO string for consistent comparison."""
    if t is None:
        return ""
    if hasattr(t, "isoformat"):
        return t.isoformat()
    return str(t)


@router.get("")
async def get_notifications(
    limit: int = Query(default=20, ge=1, le=50),
    types: Optional[str] = Query(default=None),
    since: Optional[str] = Query(default=None),
    current_user: dict = Depends(require_user),
    db=Depends(get_db),
):
    """Return grouped notification events for recent crawl failures and AI re-analyze attempts."""

    # Parse optional comma-separated type filter
    type_filter: Optional[set] = None
    if types:
        type_filter = {t.strip() for t in types.split(",") if t.strip()}

    # Determine the "read" cutoff timestamp.
    # Prefer explicit ?since= query param; otherwise fall back to user preferences.
    last_read_at: Optional[str] = since
    if not last_read_at:
        prefs = current_user.get("preferences") or {}
        notif_prefs = prefs.get("notifications") if isinstance(prefs, dict) else {}
        last_read_at = notif_prefs.get("last_read_at") if isinstance(notif_prefs, dict) else None

    crawl_repair_attempts_table = crawl_repair_tables.crawl_repair_attempts

    # 1. Query crawl_attempts WHERE status='fail', JOIN sites, ORDER BY started_at DESC
    crawl_stmt = (
        select(
            crawl_attempts.c.site_id,
            crawl_attempts.c.started_at,
            crawl_attempts.c.error_message,
            sites.c.name.label("site_name"),
        )
        .join(sites, crawl_attempts.c.site_id == sites.c.id)
        .where(crawl_attempts.c.status == "fail")
        .order_by(desc(crawl_attempts.c.started_at))
        .limit(limit)
    )
    crawl_rows = (await db.execute(crawl_stmt)).mappings().all()

    # 2. Query crawl_repair_attempts, JOIN sites, ORDER BY started_at DESC
    repair_stmt = (
        select(
            crawl_repair_attempts_table.c.site_id,
            crawl_repair_attempts_table.c.started_at,
            sites.c.name.label("site_name"),
        )
        .join(sites, crawl_repair_attempts_table.c.site_id == sites.c.id)
        .order_by(desc(crawl_repair_attempts_table.c.started_at))
        .limit(limit)
    )
    repair_rows = (await db.execute(repair_stmt)).mappings().all()

    # 3. Build flat event list with normalised ISO time strings
    events = []

    for row in crawl_rows:
        fail_type = _classify_error(row["error_message"])
        display_type = "Fail Crawl" if fail_type == "fail_crawl" else "Fail Access"
        events.append({
            "site_id": row["site_id"],
            "feed_source": row["site_name"] or str(row["site_id"]),
            "fail_type": display_type,
            "time": _to_iso(row["started_at"]),
        })

    for row in repair_rows:
        events.append({
            "site_id": row["site_id"],
            "feed_source": row["site_name"] or str(row["site_id"]),
            "fail_type": "AI Re-analyze",
            "time": _to_iso(row["started_at"]),
        })

    # 4. Group by (site_id, fail_type) — count occurrences, keep most recent time
    groups: dict[tuple, dict] = {}
    for event in events:
        key = (event["site_id"], event["fail_type"])
        if key not in groups:
            groups[key] = {
                "feed_source": event["feed_source"],
                "fail_type": event["fail_type"],
                "count": 0,
                "time": event["time"],
                "site_id": event["site_id"],
            }
        groups[key]["count"] += 1
        # ISO strings sort lexicographically — keep the most recent
        if event["time"] > groups[key]["time"]:
            groups[key]["time"] = event["time"]

    results = list(groups.values())

    # 5. Apply type filter if specified
    if type_filter:
        results = [r for r in results if r["fail_type"] in type_filter]

    # 6. Filter out events on or before last_read_at (user has already seen them)
    if last_read_at:
        results = [r for r in results if r["time"] > last_read_at]

    # 7. Sort by time descending
    results.sort(key=lambda x: x["time"], reverse=True)

    return results


@router.put("/read")
async def mark_notifications_read(
    request: Request,
    current_user: dict = Depends(require_user),
    db=Depends(get_db),
):
    """Mark all current notifications as read by persisting the current UTC timestamp."""
    now_iso = datetime.now(timezone.utc).isoformat()
    prefs = dict(current_user.get("preferences") or {})
    notif_prefs = dict(prefs.get("notifications") or {})
    notif_prefs["last_read_at"] = now_iso
    prefs["notifications"] = notif_prefs

    await db.execute(
        users.update().where(users.c.id == current_user["id"]).values(
            preferences=prefs,
        )
    )
    await db.commit()
    return {"status": "ok", "last_read_at": now_iso}
