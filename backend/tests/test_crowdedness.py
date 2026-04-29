"""
Unit tests for crowdedness.py pure functions.

Coverage targets:
  classify_time_period:
    - Weekday AM peak → PEAK / WEEKDAY
    - Weekday midday → REGULAR / WEEKDAY
    - Weekday PM peak → PEAK / WEEKDAY
    - Weekday overnight → OFF_PEAK / WEEKDAY
    - Saturday → REGULAR / WEEKEND (midday)
    - Holiday → HOLIDAY day_type, weekend schedule

  rtdir_to_inbound_outbound:
    - Southbound → inbound
    - Northbound → outbound
    - Eastbound → inbound
    - Westbound → outbound
    - Case-insensitive
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from crowdedness import (
    classify_time_period,
    rtdir_to_inbound_outbound,
    TimePeriod,
    DayType,
)

CHICAGO_TZ = ZoneInfo("America/Chicago")


def _dt(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=CHICAGO_TZ)


# ---------------------------------------------------------------------------
# classify_time_period — weekday schedule
# ---------------------------------------------------------------------------

class TestClassifyTimePeriodWeekday:
    def test_am_peak(self):
        # Tuesday 8:00 AM
        period, day_type, _ = classify_time_period(_dt(2026, 4, 28, 8, 0))
        assert period == TimePeriod.PEAK
        assert day_type == DayType.WEEKDAY

    def test_midday_regular(self):
        # Tuesday 12:00 PM
        period, day_type, _ = classify_time_period(_dt(2026, 4, 28, 12, 0))
        assert period == TimePeriod.REGULAR
        assert day_type == DayType.WEEKDAY

    def test_pm_peak(self):
        # Tuesday 4:30 PM
        period, day_type, _ = classify_time_period(_dt(2026, 4, 28, 16, 30))
        assert period == TimePeriod.PEAK
        assert day_type == DayType.WEEKDAY

    def test_evening_regular(self):
        # Tuesday 7:00 PM
        period, day_type, _ = classify_time_period(_dt(2026, 4, 28, 19, 0))
        assert period == TimePeriod.REGULAR
        assert day_type == DayType.WEEKDAY

    def test_late_night_off_peak(self):
        # Wednesday 2:00 AM
        period, day_type, _ = classify_time_period(_dt(2026, 4, 29, 2, 0))
        assert period == TimePeriod.OFF_PEAK
        assert day_type == DayType.WEEKDAY

    def test_early_morning_off_peak(self):
        # Tuesday 5:00 AM (before 6:30)
        period, day_type, _ = classify_time_period(_dt(2026, 4, 28, 5, 0))
        assert period == TimePeriod.OFF_PEAK
        assert day_type == DayType.WEEKDAY


# ---------------------------------------------------------------------------
# classify_time_period — weekend schedule
# ---------------------------------------------------------------------------

class TestClassifyTimePeriodWeekend:
    def test_saturday_midday_regular(self):
        # Saturday 1:00 PM
        period, day_type, _ = classify_time_period(_dt(2026, 5, 2, 13, 0))
        assert period == TimePeriod.REGULAR
        assert day_type == DayType.WEEKEND

    def test_saturday_early_off_peak(self):
        # Saturday 7:00 AM (before 09:00)
        period, day_type, _ = classify_time_period(_dt(2026, 5, 2, 7, 0))
        assert period == TimePeriod.OFF_PEAK
        assert day_type == DayType.WEEKEND

    def test_sunday_late_off_peak(self):
        # Sunday 10:00 PM
        period, day_type, _ = classify_time_period(_dt(2026, 5, 3, 22, 0))
        assert period == TimePeriod.OFF_PEAK
        assert day_type == DayType.WEEKEND


# ---------------------------------------------------------------------------
# classify_time_period — holiday schedule
# ---------------------------------------------------------------------------

class TestClassifyTimePeriodHoliday:
    def test_known_holiday_uses_weekend_schedule(self):
        # 2026-07-04 at 2:00 PM — holiday, weekend schedule → REGULAR
        period, day_type, _ = classify_time_period(_dt(2026, 7, 4, 14, 0))
        assert day_type == DayType.HOLIDAY
        assert period == TimePeriod.REGULAR

    def test_custom_holiday_override(self):
        # Provide a custom holidays set containing a weekday date
        custom = {"2026-04-28"}  # Tuesday
        period, day_type, _ = classify_time_period(_dt(2026, 4, 28, 12, 0), holidays=custom)
        assert day_type == DayType.HOLIDAY

    def test_non_holiday_weekday_not_flagged_as_holiday(self):
        # Regular Tuesday with empty holidays override
        period, day_type, _ = classify_time_period(_dt(2026, 4, 28, 8, 0), holidays=set())
        assert day_type == DayType.WEEKDAY


# ---------------------------------------------------------------------------
# rtdir_to_inbound_outbound
# ---------------------------------------------------------------------------

class TestRtdirToInboundOutbound:
    # rtdir is pre-lowercased at the CTA client boundary (OPT-010); tests use lowercase.

    def test_southbound_is_inbound(self):
        assert rtdir_to_inbound_outbound("22", "southbound") == "inbound"

    def test_northbound_is_outbound(self):
        assert rtdir_to_inbound_outbound("22", "northbound") == "outbound"

    def test_eastbound_is_inbound(self):
        assert rtdir_to_inbound_outbound("66", "eastbound") == "inbound"

    def test_westbound_is_outbound(self):
        assert rtdir_to_inbound_outbound("66", "westbound") == "outbound"

    def test_unknown_direction_is_outbound(self):
        assert rtdir_to_inbound_outbound("22", "loop") == "outbound"

    def test_partial_match_southeast_is_inbound(self):
        assert rtdir_to_inbound_outbound("X", "southeast") == "inbound"
