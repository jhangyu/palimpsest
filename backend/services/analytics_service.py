"""Analytics business logic — pure computation, no FastAPI dependencies."""

import statistics
from collections import defaultdict
from datetime import datetime, date as _date_cls, timedelta, timezone
from zoneinfo import ZoneInfo

from dateutil import parser as dateutil_parser

from routers._deps import FEED_COLORS

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


# --- Analytics helper functions ---

def _parse_iso_to_taipei_date(iso_str: str) -> str | None:
    """Parse an ISO timestamp string and return its Asia/Taipei date as YYYY-MM-DD."""
    if not iso_str:
        return None
    try:
        dt = dateutil_parser.parse(iso_str)
        if dt.tzinfo is None:
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


async def compute_analytics_overview(db, days: int = 30) -> dict:
    """Compute aggregated analytics overview data."""
    # DPERF-013/018: defaultdict and _date_cls moved to module-level imports

    # Clamp days to 7-90
    days = max(7, min(90, days))

    date_labels = _get_date_range(days)
    date_set = set(date_labels)
    window_start_date = date_labels[0]  # YYYY-MM-DD, earliest in window
    this_week_start, today, last_week_start, last_week_end = _get_week_boundaries()

    # ── 1. Total + weekly counts (single SQL query, no full-table load) ──────────
    # DD-10: use proper date casting with AT TIME ZONE now that columns are TIMESTAMPTZ
    counts_row = await db.fetch_one(
        "SELECT COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE created_at IS NOT NULL "
        "  AND (created_at AT TIME ZONE 'Asia/Taipei')::date >= :tw_start "
        "  AND (created_at AT TIME ZONE 'Asia/Taipei')::date <= :today) AS this_week, "
        "COUNT(*) FILTER (WHERE created_at IS NOT NULL "
        "  AND (created_at AT TIME ZONE 'Asia/Taipei')::date >= :lw_start "
        "  AND (created_at AT TIME ZONE 'Asia/Taipei')::date <= :lw_end) AS last_week "
        "FROM articles",
        values={
            "tw_start": this_week_start.isoformat(),
            "today": today.isoformat(),
            "lw_start": last_week_start.isoformat(),
            "lw_end": last_week_end.isoformat(),
        },
    )
    total_article_scrap = counts_row["total"] if counts_row else 0
    new_articles_this_week = counts_row["this_week"] if counts_row else 0
    new_articles_last_week = counts_row["last_week"] if counts_row else 0

    new_articles_weekly_change_pct = None
    if new_articles_last_week > 0:
        new_articles_weekly_change_pct = round(
            ((new_articles_this_week - new_articles_last_week) / new_articles_last_week) * 100, 1
        )

    # ── 2. Median word count (SQL, fetch only word_count column) ─────────────────
    # F-M020: 90-day window to prevent loading years of historical data
    window_start = datetime.now(tz=timezone.utc) - timedelta(days=90)
    wc_rows = await db.fetch_all(
        "SELECT word_count FROM articles WHERE word_count IS NOT NULL AND word_count > 0"
        " AND created_at >= :window_start",
        values={"window_start": window_start},
    )
    word_counts = [r["word_count"] for r in wc_rows]
    median_article_word_count = round(statistics.median(word_counts)) if word_counts else None

    # ── 3. Median feed update minutes (needs per-article published_at) ────────────
    pub_rows = await db.fetch_all(
        "SELECT site_id, published_at FROM articles"
        " WHERE published_at IS NOT NULL AND site_id IS NOT NULL AND created_at >= :window_start",
        values={"window_start": window_start},
    )
    site_articles_times: dict[int, list[datetime]] = defaultdict(list)
    for a in pub_rows:
        try:
            val = a["published_at"]
            # DD-10: published_at is now TIMESTAMPTZ (datetime); handle legacy strings
            if isinstance(val, datetime):
                site_articles_times[a["site_id"]].append(val)
            elif isinstance(val, str):
                dt = dateutil_parser.parse(val)
                site_articles_times[a["site_id"]].append(dt)
        except Exception:
            pass

    feed_avg_intervals = []
    for sid, times in site_articles_times.items():
        if len(times) < 2:
            continue
        times.sort()
        diffs = [(times[i + 1] - times[i]).total_seconds() / 60.0 for i in range(len(times) - 1)]
        diffs = [d for d in diffs if d > 0]
        if diffs:
            feed_avg_intervals.append(sum(diffs) / len(diffs))

    median_feed_update_minutes = round(statistics.median(feed_avg_intervals), 1) if feed_avg_intervals else None
    median_feed_update_change_pct = None

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

    # ── 4. Daily counts by site within window (SQL GROUP BY, no Python date loop) ─
    # DD-10: use AT TIME ZONE for proper Taipei date bucketing
    daily_sql_rows = await db.fetch_all(
        "SELECT (a.created_at AT TIME ZONE 'Asia/Taipei')::date::text AS date, a.site_id, "
        "COALESCE(s.name, 'Feed #' || a.site_id::text) AS site_name, COUNT(*) AS count "
        "FROM articles a "
        "LEFT JOIN sites s ON s.id = a.site_id "
        "WHERE a.created_at IS NOT NULL AND a.created_at >= :start "
        "GROUP BY 1, 2, 3 ORDER BY 1",
        values={"start": window_start_date},
    )

    daily_feed_counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    site_name_map: dict[int, str] = {}
    for row in daily_sql_rows:
        d_str = row["date"]
        if d_str in date_set:
            daily_feed_counts[d_str][row["site_id"]] += row["count"]
        site_name_map[row["site_id"]] = row["site_name"]

    active_site_ids = set()
    for d_str in date_labels:
        for sid in daily_feed_counts.get(d_str, {}):
            active_site_ids.add(sid)
    active_site_ids_sorted = sorted(active_site_ids)

    # DD-15: FEED_COLORS now a module-level constant

    articles_counts_overview = {
        "labels": date_labels,
        "datasets": [
            {
                "label": site_name_map.get(sid, f"Feed #{sid}"),
                "data": [daily_feed_counts.get(d, {}).get(sid, 0) for d in date_labels],
                "color": FEED_COLORS[i % len(FEED_COLORS)],
            }
            for i, sid in enumerate(active_site_ids_sorted)
        ],
    }

    # Feeds distribution (total per site within window)
    feed_dist: dict[int, int] = defaultdict(int)
    for d_str in date_labels:
        for sid, cnt in daily_feed_counts.get(d_str, {}).items():
            feed_dist[sid] += cnt

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

    # ── 5. Traffic metrics: RSS query (SQL GROUP BY) ─────────────────────────────
    # Note: rss_query_events.requested_at is still VARCHAR — keep substr for now
    rss_sql_rows = await db.fetch_all(
        "SELECT substr(requested_at, 1, 10) AS date, COUNT(*) AS count "
        "FROM rss_query_events "
        "WHERE requested_at IS NOT NULL AND requested_at >= :start "
        "GROUP BY 1",
        values={"start": window_start_date},
    )
    daily_rss_counts: dict[str, int] = {
        row["date"]: row["count"] for row in rss_sql_rows if row["date"] in date_set
    }

    rss_query_dataset = {
        "labels": date_labels,
        "datasets": [{"label": "RSS Queries", "data": [daily_rss_counts.get(d, 0) for d in date_labels]}],
    }

    # ── 6. Traffic metrics: crawl_attempts (SQL GROUP BY) ────────────────────────
    # Note: crawl_attempts.started_at is still VARCHAR — keep substr for now
    crawl_sql_rows = await db.fetch_all(
        "SELECT substr(started_at, 1, 10) AS date, "
        "SUM(COALESCE(articles_saved, 0) + COALESCE(articles_updated, 0)) AS success_count, "
        "SUM(COALESCE(articles_failed, 0)) AS fail_count "
        "FROM crawl_attempts "
        "WHERE started_at IS NOT NULL AND started_at >= :start "
        "GROUP BY 1",
        values={"start": window_start_date},
    )
    daily_scrap_success: dict[str, int] = {}
    daily_scrap_fail: dict[str, int] = {}
    for row in crawl_sql_rows:
        if row["date"] in date_set:
            daily_scrap_success[row["date"]] = int(row["success_count"] or 0)
            daily_scrap_fail[row["date"]] = int(row["fail_count"] or 0)

    article_scrap_dataset = {
        "labels": date_labels,
        "datasets": [
            {"label": "Success", "data": [daily_scrap_success.get(d, 0) for d in date_labels]},
            {"label": "Fail", "data": [daily_scrap_fail.get(d, 0) for d in date_labels]},
        ],
    }

    traffic_metrics = {
        "rss_query": rss_query_dataset,
        "article_scrap": article_scrap_dataset,
    }

    # ── 7. Article growth (cumulative, SQL GROUP BY) ──────────────────────────────
    # DD-10: use AT TIME ZONE for proper Taipei date bucketing
    growth_sql_rows = await db.fetch_all(
        "SELECT (created_at AT TIME ZONE 'Asia/Taipei')::date::text AS date, COUNT(*) AS count "
        "FROM articles WHERE created_at IS NOT NULL "
        "GROUP BY 1 ORDER BY 1"
    )
    all_dates_with_counts = [(row["date"], row["count"]) for row in growth_sql_rows]
    cumulative = 0
    date_cumulative: dict[str, int] = {}
    g_idx = 0
    for d in date_labels:
        while g_idx < len(all_dates_with_counts) and all_dates_with_counts[g_idx][0] <= d:
            cumulative += all_dates_with_counts[g_idx][1]
            g_idx += 1
        date_cumulative[d] = cumulative

    article_growth = {
        "labels": date_labels,
        "datasets": [{"label": "Total Articles", "data": [date_cumulative.get(d, 0) for d in date_labels]}],
    }

    # ── 8. Latest articles (JOIN with sites, no separate sites fetch) ─────────────
    latest_rows = await db.fetch_all(
        "SELECT a.site_id, COALESCE(s.name, 'Feed #' || a.site_id::text) AS feed_name, "
        "a.title, a.url, a.created_at, a.word_count "
        "FROM articles a "
        "LEFT JOIN sites s ON s.id = a.site_id "
        "ORDER BY a.created_at DESC NULLS LAST LIMIT 10"
    )
    latest_articles = [
        {
            "feed_name": row["feed_name"],
            "article_title": row["title"],
            "update_time": row["created_at"].isoformat() if row["created_at"] else "",
            "word_count": row["word_count"] or 0,
            "ori_url": row["url"],
        }
        for row in latest_rows
    ]

    return {
        "summary": summary,
        "articles_counts_overview": articles_counts_overview,
        "feeds_distribution": feeds_distribution,
        "traffic_metrics": traffic_metrics,
        "article_growth": article_growth,
        # DPERF-016: removed duplicate daily_rss_query (same as traffic_metrics.rss_query)
        "latest_articles": latest_articles,
    }


async def compute_articles_list(db, filter: str, search: str, page: int, page_size: int) -> dict:
    """Compute paginated article listing with filters."""
    # DPERF-018: timezone import moved to module-level
    _tz = timezone

    # Sanitize inputs
    page = max(1, page)
    page_size = max(1, min(500, page_size))
    if filter not in ("today", "week", "month", "all"):
        filter = "all"

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

    # --- DPERF-010: compute all 4 counts in a single conditional aggregation query ---
    # DD-10: created_at is now TIMESTAMPTZ — no CAST needed
    counts_sql = (
        "SELECT"
        " COUNT(*) FILTER (WHERE a.created_at >= :c_today_from AND a.created_at < :c_today_to) AS today_count,"
        " COUNT(*) FILTER (WHERE a.created_at >= :c_week_from) AS week_count,"
        " COUNT(*) FILTER (WHERE a.created_at >= :c_month_from) AS month_count,"
        " COUNT(*) AS all_count"
        " FROM articles a WHERE 1=1" + search_sql
    )
    counts_params = {
        **search_params,
        "c_today_from": today_start_utc,
        "c_today_to": today_end_utc,
        "c_week_from": week_start_utc,
        "c_month_from": month_start_utc,
    }
    counts_row = await db.fetch_one(counts_sql, values=counts_params)
    filter_counts = {
        "today": counts_row["today_count"] if counts_row else 0,
        "week": counts_row["week_count"] if counts_row else 0,
        "month": counts_row["month_count"] if counts_row else 0,
        "all": counts_row["all_count"] if counts_row else 0,
    }

    # --- Build time condition for the main paginated query ---
    time_sql = ""
    time_params: dict = {}
    # DD-10: created_at is now TIMESTAMPTZ — no CAST needed
    if filter == "today":
        time_sql = (
            " AND a.created_at >= :main_from"
            " AND a.created_at < :main_to"
        )
        time_params = {"main_from": today_start_utc, "main_to": today_end_utc}
    elif filter == "week":
        time_sql = " AND a.created_at >= :main_from"
        time_params = {"main_from": week_start_utc}
    elif filter == "month":
        time_sql = " AND a.created_at >= :main_from"
        time_params = {"main_from": month_start_utc}
    # "all" → no time condition

    total = filter_counts[filter]

    # --- Paginated main query (JOIN with sites to get feed_name, no separate sites fetch) ---
    offset = (page - 1) * page_size
    main_sql = (
        "SELECT a.site_id, a.title, a.url, a.image_url, a.author, a.created_at, a.word_count, "
        "COALESCE(s.name, 'Feed #' || a.site_id::text) AS feed_name "
        "FROM articles a LEFT JOIN sites s ON s.id = a.site_id WHERE 1=1"
        + search_sql
        + time_sql
        + " ORDER BY a.created_at DESC NULLS LAST"
        " LIMIT :lim OFFSET :off"
    )
    all_params = {**search_params, **time_params, "lim": page_size, "off": offset}
    rows = await db.fetch_all(main_sql, values=all_params)

    article_list = [
        {
            "article_title": row["title"],
            "image_url": row["image_url"],
            "feed_name": row["feed_name"],
            "word_count": row["word_count"] or 0,
            "update_time": row["created_at"].isoformat() if row["created_at"] else "",
            "ori_url": row["url"],
            "author": row["author"],
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
