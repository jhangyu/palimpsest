"""Automatic crawl frequency calculation helpers."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Iterable, Mapping, Sequence

from sqlalchemy import select, update

from core.db import articles, sites

MIN_REFRESH_MINUTES = 60.0
MAX_REFRESH_MINUTES = 20160.0
AUTO_SAMPLE_SIZE = 100
MIN_INTERVAL_MINUTES = 5.0  # exclude intervals shorter than this from median calc


def ensure_aware_utc(value: datetime) -> datetime:
    """Return *value* as a timezone-aware UTC datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def clamp_refresh_minutes(minutes: float) -> float:
    """Clamp a refresh interval to the supported scheduler range."""
    return max(MIN_REFRESH_MINUTES, min(MAX_REFRESH_MINUTES, float(minutes)))


def round_refresh_minutes(minutes: float) -> float:
    """Clamp and round a refresh interval to two decimal places."""
    return round(clamp_refresh_minutes(minutes), 2)


def positive_intervals_minutes(timestamps: Iterable[datetime | None]) -> list[float]:
    """Return positive adjacent intervals in minutes for up to the latest 100 timestamps."""
    normalized = [
        ensure_aware_utc(ts)
        for ts in timestamps
        if isinstance(ts, datetime)
    ]
    latest = sorted(normalized, reverse=True)[:AUTO_SAMPLE_SIZE]
    chronological = sorted(latest)

    intervals: list[float] = []
    for previous, current in zip(chronological, chronological[1:]):
        minutes = (current - previous).total_seconds() / 60
        if minutes >= MIN_INTERVAL_MINUTES:
            intervals.append(minutes)
    return intervals


def calculate_auto_refresh_frequency_minutes(
    timestamps: Iterable[datetime | None],
) -> float | None:
    """Calculate auto refresh minutes from article publication timestamps.

    The algorithm samples the latest 100 timestamps, keeps adjacent
    publication intervals ≥ 5 minutes (to filter burst posts that don't
    represent the real cadence), uses half of their median, clamps the
    result to the 60 … 20160 minute range, and rounds to two decimals.

    Returns ``None`` when there are fewer than 2 usable timestamps
    (can't form any interval).  When ≥ 2 timestamps exist but every
    interval falls below the 5‑minute floor the result is clamped to
    ``MIN_REFRESH_MINUTES`` (60 min).
    """
    normalized = [
        ensure_aware_utc(ts)
        for ts in timestamps
        if isinstance(ts, datetime)
    ]
    if len(normalized) < 2:
        return None  # can't form a single interval

    intervals = positive_intervals_minutes(normalized)
    if not intervals:
        # ≥ 2 timestamps exist but every interval < 5 min — floor to minimum.
        return MIN_REFRESH_MINUTES

    return round_refresh_minutes(median(intervals) / 2)


def apply_one_way_jitter(minutes: float, rng: random.Random | None = None) -> float:
    """Apply one-way +10%..+20% jitter to an interval in minutes."""
    generator = rng or random
    return float(minutes) * generator.uniform(1.10, 1.20)


def compute_next_crawl_at(
    now: datetime,
    effective_refresh_minutes: float,
    rng: random.Random | None = None,
) -> datetime:
    """Compute the next crawl timestamp from an effective refresh interval."""
    base = ensure_aware_utc(now)
    jittered_minutes = apply_one_way_jitter(effective_refresh_minutes, rng=rng)
    return base + timedelta(minutes=jittered_minutes)


def effective_refresh_minutes_for_site(site_row: Mapping) -> float:
    """Return the effective refresh interval for a site row."""
    mode = site_row.get("refresh_frequency_mode") or "manual"
    auto_minutes = site_row.get("auto_refresh_frequency_minutes")
    if mode == "auto" and auto_minutes is not None and float(auto_minutes) > 0:
        return round_refresh_minutes(float(auto_minutes))

    manual_minutes = site_row.get("refresh_frequency") or MIN_REFRESH_MINUTES
    return round_refresh_minutes(float(manual_minutes))


async def calculate_site_auto_refresh_frequency_minutes(db, site_id: int) -> float | None:
    """Calculate auto refresh frequency for a site's latest articles."""
    rows = (await db.execute(
        select(articles.c.published_at)
        .where(articles.c.site_id == site_id)
        .where(articles.c.published_at.is_not(None))
        .order_by(
            articles.c.published_at.desc().nulls_last(),
            articles.c.created_at.desc().nulls_last(),
        )
        .limit(AUTO_SAMPLE_SIZE)
    )).mappings().all()
    return calculate_auto_refresh_frequency_minutes(row["published_at"] for row in rows)


async def update_site_crawl_schedule(db, site_id: int, crawled_at: datetime | None = None) -> dict | None:
    """Update last/next crawl timestamps and auto effective interval for a site.

    Returns the values written, or ``None`` if the site no longer exists.
    """
    site_row = (await db.execute(
        select(sites).where(sites.c.id == site_id)
    )).mappings().first()
    if site_row is None:
        return None

    now = ensure_aware_utc(crawled_at or datetime.now(timezone.utc))
    mode = site_row.get("refresh_frequency_mode") or "manual"
    auto_minutes = site_row.get("auto_refresh_frequency_minutes")

    if mode == "auto":
        calculated = await calculate_site_auto_refresh_frequency_minutes(db, site_id)
        if calculated is not None:
            auto_minutes = calculated

    effective_minutes = effective_refresh_minutes_for_site({
        **dict(site_row),
        "auto_refresh_frequency_minutes": auto_minutes,
    })
    next_crawl_at = compute_next_crawl_at(now, effective_minutes)

    values = {
        "last_crawled_at": now,
        "next_crawl_at": next_crawl_at,
    }
    if mode == "auto":
        values["auto_refresh_frequency_minutes"] = auto_minutes

    await db.execute(
        update(sites)
        .where(sites.c.id == site_id)
        .values(**values)
    )
    await db.commit()

    return {
        **values,
        "effective_refresh_frequency_minutes": effective_minutes,
    }
