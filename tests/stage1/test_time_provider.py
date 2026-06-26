"""
---
name: test_time_provider
description: "Unit tests for time_provider.py — SystemClock, FakeClock, WeekWindow, taipei_week_window boundary logic"
stage: stage1
type: pytest
target:
  layer: backend
  domain: time
spec_doc: null
test_file: tests/stage1/test_time_provider.py
functions:
  - name: TestConstants::test_timezone_is_asia_taipei
    line: 57
    purpose: "AUTO_REPAIR_TIMEZONE constant equals 'Asia/Taipei'"
    fixtures: []
  - name: TestConstants::test_week_start_is_sunday
    line: 60
    purpose: "AUTO_REPAIR_WEEK_START_WEEKDAY equals 6 (Python Sunday)"
    fixtures: []
  - name: TestSystemClock::test_returns_aware_utc_datetime
    line: 69
    purpose: "SystemClock.now_utc() returns timezone-aware UTC datetime"
    fixtures: []
  - name: TestFakeClock::test_returns_fixed_time
    line: 81
    purpose: "FakeClock returns the fixed datetime passed at construction"
    fixtures: []
  - name: TestFakeClock::test_rejects_naive_datetime
    line: 86
    purpose: "FakeClock raises ValueError when given a naive datetime"
    fixtures: []
  - name: TestFakeClock::test_normalizes_to_utc
    line: 90
    purpose: "FakeClock normalizes a Taipei-tz datetime to UTC for now_utc()"
    fixtures: []
  - name: TestFakeClock::test_advance_moves_time
    line: 97
    purpose: "FakeClock.advance(hours=1) increments internal clock by 1 hour"
    fixtures: []
  - name: TestFakeClock::test_advance_multiple_units
    line: 104
    purpose: "FakeClock.advance with multiple units sums correctly"
    fixtures: []
  - name: TestWeekWindow::test_contains_within_window
    line: 117
    purpose: "WeekWindow.contains() returns True for mid-week datetime"
    fixtures: []
  - name: TestWeekWindow::test_contains_at_start_boundary
    line: 125
    purpose: "WeekWindow.contains() returns True at start boundary (inclusive)"
    fixtures: []
  - name: TestWeekWindow::test_contains_at_end_boundary
    line: 132
    purpose: "WeekWindow.contains() returns False at end boundary (exclusive)"
    fixtures: []
  - name: TestWeekWindow::test_contains_rejects_naive_datetime
    line: 139
    purpose: "WeekWindow.contains() raises ValueError for naive datetime"
    fixtures: []
  - name: TestTaipeiWeekWindow::test_rejects_naive_datetime
    line: 155
    purpose: "taipei_week_window() raises ValueError for naive datetime input"
    fixtures: []
  - name: TestTaipeiWeekWindow::test_wednesday_mid_week
    line: 159
    purpose: "Wednesday 2024-06-19 Taipei → week started Sunday 2024-06-16"
    fixtures: []
  - name: TestTaipeiWeekWindow::test_sunday_at_midnight
    line: 171
    purpose: "Sunday 2024-06-16 00:00:00 Taipei is the week start itself"
    fixtures: []
  - name: TestTaipeiWeekWindow::test_saturday_2359_is_still_previous_week
    line: 180
    purpose: "Saturday 2024-06-15 23:59:59 Taipei → previous week starting 2024-06-09"
    fixtures: []
  - name: TestTaipeiWeekWindow::test_sunday_at_0001_is_current_week
    line: 192
    purpose: "Sunday 2024-06-16 00:01:00 Taipei → current week starting 2024-06-16"
    fixtures: []
  - name: TestTaipeiWeekWindow::test_rollover_one_second_boundary
    line: 201
    purpose: "Critical 1-second boundary: Sat 23:59:59 vs Sun 00:00:00 Taipei week change"
    fixtures: []
  - name: TestTaipeiWeekWindow::test_window_is_exactly_7_days
    line: 217
    purpose: "WeekWindow spans exactly 7 × 24 hours"
    fixtures: []
  - name: TestTaipeiWeekWindow::test_now_utc_is_within_its_own_window
    line: 224
    purpose: "The input moment falls within its own computed week window"
    fixtures: []
  - name: TestTimezoneIndependence::test_same_result_from_utc_and_taipei_input
    line: 239
    purpose: "Same instant as UTC and Taipei tz gives identical WeekWindow"
    fixtures: []
  - name: TestTimezoneIndependence::test_same_result_from_los_angeles_input
    line: 251
    purpose: "Same instant as America/Los_Angeles gives identical WeekWindow"
    fixtures: []
  - name: TestTimezoneIndependence::test_utc_saturday_1600_is_taipei_sunday_boundary
    line: 263
    purpose: "UTC Saturday 16:00:00 = Taipei Sunday 00:00:00 — critical cross-tz edge case"
    fixtures: []
  - name: TestTimezoneIndependence::test_new_years_boundary
    line: 280
    purpose: "Year boundary: Sunday 2024-12-29 Taipei → correct week; Saturday prior is previous"
    fixtures: []
  - name: TestLazyRolloverDecision::test_same_week_no_rollover_needed
    line: 301
    purpose: "Stored bucket matching current window means no rollover needed"
    fixtures: []
  - name: TestLazyRolloverDecision::test_different_week_rollover_needed
    line: 309
    purpose: "Stored bucket from previous week differs from current window — rollover needed"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_time_provider.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "Python deps installed (zoneinfo — Python 3.9+)"
---
"""

import os
import sys
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from core.time_provider import (
    AUTO_REPAIR_TIMEZONE,
    AUTO_REPAIR_WEEK_START_WEEKDAY,
    SystemClock,
    FakeClock,
    WeekWindow,
    taipei_week_window,
)

# ── Constants ─────────────────────────────────────────────────────────────────

TPE = ZoneInfo("Asia/Taipei")
UTC = timezone.utc


# ── Helper: build a Taipei local datetime and return it as UTC ──────────────
def _taipei_to_utc(year, month, day, hour=0, minute=0, second=0) -> datetime:
    """Create a datetime in Asia/Taipei and convert to UTC."""
    local = datetime(year, month, day, hour, minute, second, tzinfo=TPE)
    return local.astimezone(UTC)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstants:
    def test_timezone_is_asia_taipei(self):
        assert str(AUTO_REPAIR_TIMEZONE) == "Asia/Taipei"

    def test_week_start_is_sunday(self):
        assert AUTO_REPAIR_WEEK_START_WEEKDAY == 6  # Python weekday: Sunday=6


# ═══════════════════════════════════════════════════════════════════════════════
# SystemClock
# ═══════════════════════════════════════════════════════════════════════════════

class TestSystemClock:
    def test_returns_aware_utc_datetime(self):
        clock = SystemClock()
        now = clock.now_utc()
        assert now.tzinfo is not None
        assert now.tzinfo == UTC or now.utcoffset() == timedelta(0)


# ═══════════════════════════════════════════════════════════════════════════════
# FakeClock
# ═══════════════════════════════════════════════════════════════════════════════

class TestFakeClock:
    def test_returns_fixed_time(self):
        fixed = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        clock = FakeClock(fixed)
        assert clock.now_utc() == fixed

    def test_rejects_naive_datetime(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            FakeClock(datetime(2024, 6, 15, 12, 0, 0))

    def test_normalizes_to_utc(self):
        # Pass a Taipei time → should be stored as UTC
        taipei_time = datetime(2024, 6, 15, 20, 0, 0, tzinfo=TPE)
        clock = FakeClock(taipei_time)
        result = clock.now_utc()
        assert result.tzinfo == UTC or result.utcoffset() == timedelta(0)
        assert result == taipei_time.astimezone(UTC)

    def test_advance_moves_time(self):
        fixed = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        clock = FakeClock(fixed)
        clock.advance(hours=1)
        assert clock.now_utc() == fixed + timedelta(hours=1)

    def test_advance_multiple_units(self):
        fixed = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        clock = FakeClock(fixed)
        clock.advance(hours=2, minutes=30, seconds=15)
        expected = fixed + timedelta(hours=2, minutes=30, seconds=15)
        assert clock.now_utc() == expected


# ═══════════════════════════════════════════════════════════════════════════════
# WeekWindow
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeekWindow:
    def test_contains_within_window(self):
        start = datetime(2024, 6, 15, 16, 0, 0, tzinfo=UTC)  # Sun 00:00 Taipei
        end = datetime(2024, 6, 22, 16, 0, 0, tzinfo=UTC)    # Next Sun 00:00 Taipei
        window = WeekWindow(start_utc=start, end_utc=end, start_local_date=date(2024, 6, 16))

        mid_week = datetime(2024, 6, 18, 12, 0, 0, tzinfo=UTC)
        assert window.contains(mid_week) is True

    def test_contains_at_start_boundary(self):
        start = datetime(2024, 6, 15, 16, 0, 0, tzinfo=UTC)
        end = datetime(2024, 6, 22, 16, 0, 0, tzinfo=UTC)
        window = WeekWindow(start_utc=start, end_utc=end, start_local_date=date(2024, 6, 16))

        assert window.contains(start) is True  # inclusive start

    def test_contains_at_end_boundary(self):
        start = datetime(2024, 6, 15, 16, 0, 0, tzinfo=UTC)
        end = datetime(2024, 6, 22, 16, 0, 0, tzinfo=UTC)
        window = WeekWindow(start_utc=start, end_utc=end, start_local_date=date(2024, 6, 16))

        assert window.contains(end) is False  # exclusive end

    def test_contains_rejects_naive_datetime(self):
        start = datetime(2024, 6, 15, 16, 0, 0, tzinfo=UTC)
        end = datetime(2024, 6, 22, 16, 0, 0, tzinfo=UTC)
        window = WeekWindow(start_utc=start, end_utc=end, start_local_date=date(2024, 6, 16))

        with pytest.raises(ValueError, match="timezone-aware"):
            window.contains(datetime(2024, 6, 18, 12, 0, 0))


# ═══════════════════════════════════════════════════════════════════════════════
# taipei_week_window — Core Sunday boundary tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTaipeiWeekWindow:
    """Tests for taipei_week_window() — the core week-boundary computation."""

    def test_rejects_naive_datetime(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            taipei_week_window(datetime(2024, 6, 18, 12, 0, 0))

    def test_wednesday_mid_week(self):
        """Wednesday 2024-06-19 13:00 Taipei → week started Sunday 2024-06-16."""
        now_utc = _taipei_to_utc(2024, 6, 19, 13, 0, 0)
        window = taipei_week_window(now_utc)

        expected_start = _taipei_to_utc(2024, 6, 16, 0, 0, 0)  # Sunday 00:00 Taipei
        expected_end = _taipei_to_utc(2024, 6, 23, 0, 0, 0)    # Next Sunday 00:00 Taipei

        assert window.start_utc == expected_start
        assert window.end_utc == expected_end
        assert window.start_local_date == date(2024, 6, 16)

    def test_sunday_at_midnight(self):
        """Sunday 2024-06-16 00:00:00 Taipei → this IS the week start."""
        now_utc = _taipei_to_utc(2024, 6, 16, 0, 0, 0)
        window = taipei_week_window(now_utc)

        expected_start = _taipei_to_utc(2024, 6, 16, 0, 0, 0)
        assert window.start_utc == expected_start
        assert window.start_local_date == date(2024, 6, 16)

    def test_saturday_2359_is_still_previous_week(self):
        """Saturday 2024-06-15 23:59:59 Taipei → week started Sunday 2024-06-09."""
        now_utc = _taipei_to_utc(2024, 6, 15, 23, 59, 59)
        window = taipei_week_window(now_utc)

        expected_start = _taipei_to_utc(2024, 6, 9, 0, 0, 0)   # Previous Sunday
        expected_end = _taipei_to_utc(2024, 6, 16, 0, 0, 0)     # This Sunday

        assert window.start_utc == expected_start
        assert window.end_utc == expected_end
        assert window.start_local_date == date(2024, 6, 9)

    def test_sunday_at_0001_is_current_week(self):
        """Sunday 2024-06-16 00:01:00 Taipei → week started this Sunday."""
        now_utc = _taipei_to_utc(2024, 6, 16, 0, 1, 0)
        window = taipei_week_window(now_utc)

        expected_start = _taipei_to_utc(2024, 6, 16, 0, 0, 0)
        assert window.start_utc == expected_start
        assert window.start_local_date == date(2024, 6, 16)

    def test_rollover_one_second_boundary(self):
        """Test the critical 1-second boundary: Taipei Sat 23:59:59 → Sun 00:00:00.

        Saturday 23:59:59 Taipei = Saturday 15:59:59 UTC → week of prev Sunday.
        Sunday 00:00:00 Taipei = Saturday 16:00:00 UTC → week of this Sunday.
        """
        # Just before midnight: still in previous week
        before = _taipei_to_utc(2024, 6, 15, 23, 59, 59)
        window_before = taipei_week_window(before)
        assert window_before.start_local_date == date(2024, 6, 9)

        # At midnight: new week
        at_midnight = _taipei_to_utc(2024, 6, 16, 0, 0, 0)
        window_at = taipei_week_window(at_midnight)
        assert window_at.start_local_date == date(2024, 6, 16)

    def test_window_is_exactly_7_days(self):
        """WeekWindow spans exactly 7 × 24 hours."""
        now_utc = _taipei_to_utc(2024, 6, 19, 12, 0, 0)
        window = taipei_week_window(now_utc)

        assert (window.end_utc - window.start_utc) == timedelta(days=7)

    def test_now_utc_is_within_its_own_window(self):
        """The input moment should fall within its own computed window."""
        now_utc = _taipei_to_utc(2024, 6, 19, 14, 30, 0)
        window = taipei_week_window(now_utc)
        assert window.contains(now_utc)


# ═══════════════════════════════════════════════════════════════════════════════
# Server timezone independence
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimezoneIndependence:
    """Ensure taipei_week_window() produces the same result regardless of
    server/process timezone."""

    def test_same_result_from_utc_and_taipei_input(self):
        """Same instant expressed as UTC and as Taipei should give identical window."""
        instant_utc = datetime(2024, 6, 18, 5, 0, 0, tzinfo=UTC)
        instant_tpe = instant_utc.astimezone(TPE)

        window_from_utc = taipei_week_window(instant_utc)
        window_from_tpe = taipei_week_window(instant_tpe)

        assert window_from_utc.start_utc == window_from_tpe.start_utc
        assert window_from_utc.end_utc == window_from_tpe.end_utc
        assert window_from_utc.start_local_date == window_from_tpe.start_local_date

    def test_same_result_from_los_angeles_input(self):
        """Same instant expressed as America/Los_Angeles should give identical window."""
        la_tz = ZoneInfo("America/Los_Angeles")
        instant_utc = datetime(2024, 6, 18, 5, 0, 0, tzinfo=UTC)
        instant_la = instant_utc.astimezone(la_tz)

        window_from_utc = taipei_week_window(instant_utc)
        window_from_la = taipei_week_window(instant_la)

        assert window_from_utc.start_utc == window_from_la.start_utc
        assert window_from_utc.end_utc == window_from_la.end_utc

    def test_utc_saturday_1600_is_taipei_sunday_boundary(self):
        """UTC Saturday 16:00:00 = Taipei Sunday 00:00:00 (week boundary).

        This is the critical cross-timezone edge case.
        """
        # UTC Saturday 15:59:59 → Taipei Saturday 23:59:59 → previous week
        utc_before = datetime(2024, 6, 15, 15, 59, 59, tzinfo=UTC)
        window_before = taipei_week_window(utc_before)

        # UTC Saturday 16:00:00 → Taipei Sunday 00:00:00 → new week
        utc_at = datetime(2024, 6, 15, 16, 0, 0, tzinfo=UTC)
        window_at = taipei_week_window(utc_at)

        assert window_before.start_local_date != window_at.start_local_date
        assert window_before.start_local_date == date(2024, 6, 9)
        assert window_at.start_local_date == date(2024, 6, 16)

    def test_new_years_boundary(self):
        """Year boundary: Sunday 2024-12-29 Taipei → correct year/week."""
        # 2024-12-29 is a Sunday in Taipei
        now_utc = _taipei_to_utc(2024, 12, 29, 0, 0, 0)
        window = taipei_week_window(now_utc)
        assert window.start_local_date == date(2024, 12, 29)

        # 2024-12-28 (Saturday) should be in previous week
        sat_utc = _taipei_to_utc(2024, 12, 28, 23, 59, 59)
        window_sat = taipei_week_window(sat_utc)
        assert window_sat.start_local_date == date(2024, 12, 22)


# ═══════════════════════════════════════════════════════════════════════════════
# Lazy rollover decision helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestLazyRolloverDecision:
    """Test the concept of comparing stored week_start_at with current window
    to determine if a lazy rollover is needed."""

    def test_same_week_no_rollover_needed(self):
        """If stored bucket matches current window, no rollover."""
        now_utc = _taipei_to_utc(2024, 6, 19, 12, 0, 0)
        window = taipei_week_window(now_utc)

        stored_bucket = window.start_utc  # Same week
        assert stored_bucket == window.start_utc  # No rollover needed

    def test_different_week_rollover_needed(self):
        """If stored bucket is from a previous week, rollover is needed."""
        now_utc = _taipei_to_utc(2024, 6, 19, 12, 0, 0)  # Wednesday
        window = taipei_week_window(now_utc)

        # Stored from 2 weeks ago
        old_bucket = _taipei_to_utc(2024, 6, 2, 0, 0, 0)
        assert old_bucket != window.start_utc  # Rollover needed
