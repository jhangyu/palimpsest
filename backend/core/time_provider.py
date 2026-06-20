# backend/core/time_provider.py
"""
C1 — Deterministic time provider for crawl auto-repair.

Provides a Clock protocol, SystemClock and FakeClock implementations, and
the taipei_week_window() helper that determines the current Sunday-anchored
week boundary in Asia/Taipei time.

Design goals:
  - All production code accepts a Clock instance via DI (never calls datetime.now() directly).
  - Tests inject FakeClock with a fixed timestamp, making time-sensitive logic deterministic.
  - taipei_week_window() is a pure function — no side effects, no I/O.

Week definition (Decision Freeze, C0):
  - Week starts on SUNDAY (weekday index 6 in Python's isoweekday(), or 6 for .weekday()).
  - Timezone: Asia/Taipei (UTC+8, no DST).
  - WeekWindow.start_utc is Sunday 00:00:00 Taipei time expressed in UTC (Sat 16:00:00 UTC).
  - WeekWindow.end_utc is the following Sunday 00:00:00 Taipei time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

# ── Constants ─────────────────────────────────────────────────────────────────

AUTO_REPAIR_TIMEZONE = ZoneInfo("Asia/Taipei")

# Python weekday(): Monday=0 … Sunday=6
AUTO_REPAIR_WEEK_START_WEEKDAY = 6  # Sunday


# ── Clock protocol / implementations ──────────────────────────────────────────

class Clock(Protocol):
    """Protocol for injectable time providers."""

    def now_utc(self) -> datetime:
        """Return the current moment as a timezone-aware UTC datetime."""
        ...  # pragma: no cover


class SystemClock:
    """
    Production implementation: delegates to datetime.now(timezone.utc).
    """

    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeClock:
    """
    Test implementation: returns a fixed UTC datetime.

    Args:
        fixed_utc: A timezone-aware datetime in UTC (tzinfo must be UTC or
                   a fixed-offset equivalent).

    Raises:
        ValueError: if *fixed_utc* is naive (no tzinfo).
    """

    def __init__(self, fixed_utc: datetime) -> None:
        if fixed_utc.tzinfo is None:
            raise ValueError(
                "FakeClock requires a timezone-aware datetime; "
                f"got naive datetime: {fixed_utc!r}"
            )
        # Normalise to UTC
        self._fixed = fixed_utc.astimezone(timezone.utc)

    def now_utc(self) -> datetime:
        return self._fixed

    def advance(self, seconds: float = 0, minutes: float = 0, hours: float = 0) -> None:
        """Advance the clock by the given duration (in-place)."""
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours)
        self._fixed = self._fixed + delta


# ── Week window ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class WeekWindow:
    """
    A Sunday-anchored week in Asia/Taipei time.

    Attributes:
        start_utc: The Sunday 00:00:00 Asia/Taipei converted to UTC
                   (e.g. UTC Saturday 16:00:00 for Asia/Taipei UTC+8).
        end_utc: The *following* Sunday 00:00:00 Asia/Taipei in UTC.
        start_local_date: The calendar date of the Sunday in Asia/Taipei
                          (e.g. datetime.date(2024, 1, 7)).
    """
    start_utc: datetime
    end_utc: datetime
    start_local_date: object  # datetime.date — kept as 'object' to avoid import cycle concerns

    def contains(self, ts_utc: datetime) -> bool:
        """Return True if *ts_utc* falls within [start_utc, end_utc)."""
        if ts_utc.tzinfo is None:
            raise ValueError(
                f"contains() requires a timezone-aware datetime; got {ts_utc!r}"
            )
        return self.start_utc <= ts_utc < self.end_utc


def taipei_week_window(now_utc: datetime) -> WeekWindow:
    """
    Compute the current Sunday-anchored week window in Asia/Taipei time.

    Args:
        now_utc: Current UTC time (must be timezone-aware).

    Returns:
        WeekWindow whose start_utc is the most recent Sunday 00:00:00 Taipei
        and whose end_utc is the next Sunday 00:00:00 Taipei.

    Raises:
        ValueError: if *now_utc* is naive (no tzinfo).

    Example (Asia/Taipei is UTC+8):
        now_utc = 2024-01-10 (Wednesday) 05:00 UTC
                = 2024-01-10 (Wednesday) 13:00 Taipei
        Previous Sunday Taipei = 2024-01-07 00:00:00 Taipei = 2024-01-06 16:00:00 UTC
        Next Sunday Taipei     = 2024-01-14 00:00:00 Taipei = 2024-01-13 16:00:00 UTC
    """
    if now_utc.tzinfo is None:
        raise ValueError(
            f"taipei_week_window() requires a timezone-aware datetime; got {now_utc!r}"
        )

    # Convert to Asia/Taipei local time
    now_local = now_utc.astimezone(AUTO_REPAIR_TIMEZONE)

    # Python weekday(): Monday=0, Tuesday=1, ..., Sunday=6
    days_since_sunday = (now_local.weekday() - AUTO_REPAIR_WEEK_START_WEEKDAY) % 7

    # Compute the most recent Sunday (start of week) in local time
    sunday_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_sunday)

    # Next Sunday = start of next week
    next_sunday_local = sunday_local + timedelta(weeks=1)

    # Convert back to UTC
    start_utc = sunday_local.astimezone(timezone.utc)
    end_utc = next_sunday_local.astimezone(timezone.utc)

    return WeekWindow(
        start_utc=start_utc,
        end_utc=end_utc,
        start_local_date=sunday_local.date(),
    )
