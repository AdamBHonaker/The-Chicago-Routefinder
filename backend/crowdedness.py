"""
CTA Vehicle Crowdedness Estimation (Feature Crowdedness).

Produces a CrowdednessEstimate for each transit leg based on:
- Time period (PEAK / REGULAR / OFF_PEAK)
- Day type (WEEKDAY / WEEKEND / HOLIDAY)
- Direction of travel (inbound / outbound)
- Position along the route (bell-curve stop position factor)
- Known high-traffic stops

When live psgld data is available (non-empty), the live value takes priority.
Otherwise the heuristic fills the gap with confidence "medium" or "low".

CHICAGO_TZ is defined locally to avoid coupling this module to cta_client.py.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Set

import holidays as _holidays_pkg

from utils import CHICAGO_TZ

# ---------------------------------------------------------------------------
# Holiday set — generated programmatically from the `holidays` package.
# Covers US federal + Illinois state holidays for current year ± 5 years.
# Built lazily on first lookup and recomputed when the year rolls over so
# long-running servers don't keep using a stale set after January 1.
# ---------------------------------------------------------------------------
def _build_holiday_set(year: int) -> Set[str]:
    il = _holidays_pkg.US(subdiv="IL", years=range(year - 1, year + 6))
    return {d.strftime("%Y-%m-%d") for d in il.keys()}


_HOLIDAYS_YEAR: int | None = None
_HOLIDAYS_CACHE: Set[str] = set()


def _get_holidays() -> Set[str]:
    global _HOLIDAYS_YEAR, _HOLIDAYS_CACHE
    current_year = datetime.now(tz=CHICAGO_TZ).year
    if _HOLIDAYS_YEAR != current_year:
        _HOLIDAYS_CACHE = _build_holiday_set(current_year)
        _HOLIDAYS_YEAR = current_year
    return _HOLIDAYS_CACHE

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TimePeriod(Enum):
    """Time-of-day bucket used by the crowdedness heuristic.

    PEAK covers weekday rush hours (CTA's published peak windows); REGULAR is
    mid-day; OFF_PEAK is evenings/late-night. Maps to a base-crowdedness
    multiplier inside ``_estimate_crowdedness``.
    """
    PEAK     = "peak"
    REGULAR  = "regular"
    OFF_PEAK = "off_peak"


class DayType(Enum):
    """Day-of-week / holiday bucket.

    HOLIDAY (US-federal + Illinois state) is treated as WEEKEND for
    crowdedness purposes — CTA runs reduced service and ridership tracks the
    weekend profile more closely than the weekday profile.
    """
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"    # treated as weekend for crowdedness purposes


class CrowdednessLevel(Enum):
    """Four-step ordinal crowdedness rating surfaced to the frontend.

    Ordering (LOW < MODERATE < HIGH < VERY_HIGH) is preserved in
    ``CROWDEDNESS_LEVEL_ORDER`` for max/min comparisons across legs.
    """
    LOW       = "low"
    MODERATE  = "moderate"
    HIGH      = "high"
    VERY_HIGH = "very_high"


# Ordering for comparison: LOW < MODERATE < HIGH < VERY_HIGH
CROWDEDNESS_LEVEL_ORDER: dict[CrowdednessLevel, int] = {
    CrowdednessLevel.LOW:       0,
    CrowdednessLevel.MODERATE:  1,
    CrowdednessLevel.HIGH:      2,
    CrowdednessLevel.VERY_HIGH: 3,
}

# ---------------------------------------------------------------------------
# Time period configuration
# All times are in minutes since midnight (0–1440).
#
# Weekday schedule:
#   PEAK:     06:30–09:30 (390–570) and 15:30–18:30 (930–1110)
#   REGULAR:  09:30–15:30 (570–930) and 18:30–21:00 (1110–1260)
#   OFF_PEAK: 21:00–06:30 (fallback)
#
# Weekend / holiday schedule:
#   REGULAR:  09:00–21:00 (540–1260)
#   OFF_PEAK: 21:00–09:00 (fallback)
# ---------------------------------------------------------------------------
_TIME_PERIOD_CONFIG: dict[DayType, list[tuple[int, int, TimePeriod]]] = {
    DayType.WEEKDAY: [
        (390,  570,  TimePeriod.PEAK),     # 06:30–09:30
        (930,  1110, TimePeriod.PEAK),     # 15:30–18:30
        (570,  930,  TimePeriod.REGULAR),  # 09:30–15:30
        (1110, 1260, TimePeriod.REGULAR),  # 18:30–21:00
        # OFF_PEAK is the fallback (before 06:30 or after 21:00)
    ],
    DayType.WEEKEND: [
        (540, 1260, TimePeriod.REGULAR),   # 09:00–21:00
        # OFF_PEAK is the fallback
    ],
}


def classify_time_period(
    dt: datetime,
    holidays: Set[str] | None = None,
) -> tuple[TimePeriod, DayType, int]:
    """
    Classify a datetime into (TimePeriod, DayType).

    dt should be timezone-aware; if naive, it is treated as Chicago local time.
    holidays may be provided to override the built-in static set.
    """
    if holidays is None:
        holidays = _get_holidays()

    # Normalise to Chicago local time
    if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
        local = dt.astimezone(CHICAGO_TZ)
    else:
        local = dt.replace(tzinfo=CHICAGO_TZ)

    date_str = f"{local.year}-{local.month:02d}-{local.day:02d}"

    if date_str in holidays:
        day_type = DayType.HOLIDAY
    elif local.weekday() >= 5:  # Saturday=5, Sunday=6
        day_type = DayType.WEEKEND
    else:
        day_type = DayType.WEEKDAY

    # HOLIDAY is treated identically to WEEKEND for schedule lookup
    config_key = DayType.WEEKEND if day_type != DayType.WEEKDAY else DayType.WEEKDAY
    mins = local.hour * 60 + local.minute

    for start, end, period in _TIME_PERIOD_CONFIG[config_key]:
        if start <= mins < end:
            return period, day_type, local.hour

    return TimePeriod.OFF_PEAK, day_type, local.hour


# ---------------------------------------------------------------------------
# Crowdedness model
# ---------------------------------------------------------------------------

@dataclass
class CrowdednessEstimate:
    score:      float            # 0.0 (empty) – 1.0 (standing room only)
    level:      CrowdednessLevel
    confidence: str              # "high" | "medium" | "low"
    factors:    dict | None = None  # explainability dict; None when include_factors=False


# ---------------------------------------------------------------------------
# Heuristic constants
# ---------------------------------------------------------------------------

BASE_SCORES: dict[TimePeriod, float] = {
    TimePeriod.PEAK:     0.75,
    TimePeriod.REGULAR:  0.45,
    TimePeriod.OFF_PEAK: 0.20,
}

# High-traffic train stations: mapid → crowdedness multiplier.
# Keys verified against backend/gtfs_data/stops.txt (location_type=1 parent stations).
# Train-station keys use mapid (40000–49999).
HIGH_TRAFFIC_TRAIN_STATIONS: dict[str, float] = {
    "40380": 1.35,  # Clark/Lake (Brown/Purple/Orange/Pink/Green — Loop hub)
    "40730": 1.30,  # Washington/Wells (Brown/Purple/Orange/Pink)
    "40850": 1.25,  # Harold Washington Library-State/Van Buren
    "40900": 1.20,  # Howard (Red/Purple/Yellow — major north-side transfer)
    "40890": 1.15,  # O'Hare (Blue terminus)
    "40930": 1.15,  # Midway (Orange terminus)
    "41220": 1.20,  # Fullerton (Red/Brown/Purple — major transfer)
    "41320": 1.25,  # Belmont (Red/Brown/Purple — major transfer)
    "41450": 1.20,  # Chicago (Red)
    "40450": 1.15,  # 95th/Dan Ryan (Red terminus)
}

def rtdir_to_inbound_outbound(route_short_name: str, rtdir: str) -> str:
    """
    Map a Bus Tracker rtdir string to "inbound" or "outbound".

    rtdir must already be lowercase (normalized at the CTA client boundary).
    Heuristic: southbound/eastbound → inbound (toward the Loop);
               northbound/westbound → outbound.
    """
    if "south" in rtdir or "east" in rtdir:
        return "inbound"
    return "outbound"


def _direction_multiplier(direction: str, time_period: TimePeriod, current_hour: int) -> float:
    """
    Crowdedness multiplier based on direction and time period.

    AM peak: inbound (toward Loop) more crowded → 1.2; outbound → 0.8.
    PM peak: outbound more crowded → 1.2; inbound → 0.8.
    Non-peak: symmetric, no adjustment.
    """
    if time_period != TimePeriod.PEAK:
        return 1.0
    is_am_peak = current_hour < 12
    if direction == "inbound":
        return 1.2 if is_am_peak else 0.8
    return 0.8 if is_am_peak else 1.2


def _stop_position_factor(position: float, total: float) -> float:
    """
    Bell-curve factor based on fractional stop position along the route.

    Routes are most crowded near the middle and less crowded at terminals.
    Formula: 0.6 + 0.4 * sin(position/total * π)
    """
    if total <= 0:
        return 1.0
    return 0.6 + 0.4 * math.sin(position / total * math.pi)


def _score_to_level(score: float) -> CrowdednessLevel:
    if score >= 0.80:
        return CrowdednessLevel.VERY_HIGH
    if score >= 0.55:
        return CrowdednessLevel.HIGH
    if score >= 0.30:
        return CrowdednessLevel.MODERATE
    return CrowdednessLevel.LOW


_LIVE_PSGLD_MAP: dict[str, tuple[float, CrowdednessLevel]] = {
    "EMPTY":      (0.10, CrowdednessLevel.LOW),
    "HALF_EMPTY": (0.45, CrowdednessLevel.MODERATE),
    "FULL":       (0.90, CrowdednessLevel.HIGH),
}


def estimate_crowdedness(
    route_id: str,
    direction: str,
    stop_id: str,
    stop_sequence_position: float,
    total_stops: float,
    time_period: TimePeriod,
    day_type: DayType,
    current_hour: int,
    live_psgld: str = "",
    include_factors: bool = True,
) -> CrowdednessEstimate:
    """
    Estimate crowdedness for a single transit leg.

    Parameters
    ----------
    route_id:               CTA route short name or train line code (e.g. "Red", "22")
    direction:              "inbound" | "outbound"
    stop_id:                Station mapid (trains, 40000–49999) or stop_id (buses)
    stop_sequence_position: Position of this stop within the route (0-based index)
    total_stops:            Total number of stops on the route/direction
    time_period:            Classified time period from classify_time_period()
    day_type:               Classified day type from classify_time_period()
    current_hour:           Local hour (0–23) for AM/PM peak discrimination
    live_psgld:             Normalised passenger load from CTA Bus Tracker ("EMPTY" |
                            "HALF_EMPTY" | "FULL" | "" when unavailable)

    Returns
    -------
    CrowdednessEstimate with score [0,1], level, confidence, and factors dict.
    """
    # --- Live path (high confidence) ---
    if live_psgld and live_psgld in _LIVE_PSGLD_MAP:
        score, level = _LIVE_PSGLD_MAP[live_psgld]
        return CrowdednessEstimate(
            score=score,
            level=level,
            confidence="high",
            factors={"source": "live_psgld", "psgld": live_psgld} if include_factors else None,
        )

    # --- Heuristic path ---
    base       = BASE_SCORES.get(time_period, 0.45)
    dir_mult   = _direction_multiplier(direction, time_period, current_hour)
    pos_factor = _stop_position_factor(stop_sequence_position, total_stops)

    try:
        is_train = int(stop_id) >= 40000
    except ValueError:
        is_train = False
    ht_mult  = HIGH_TRAFFIC_TRAIN_STATIONS.get(stop_id, 1.0) if is_train else 1.0

    score = max(0.0, min(1.0, base * dir_mult * pos_factor * ht_mult))
    confidence = "medium" if time_period == TimePeriod.PEAK else "low"
    level = _score_to_level(score)

    factors_dict = None
    if include_factors:
        factors_dict = {
            "source":      "heuristic",
            "base_score":  base,
            "direction":   direction,
            "dir_mult":    round(dir_mult, 2),
            "pos_factor":  round(pos_factor, 3),
            "ht_mult":     ht_mult,
            "time_period": time_period.value,
            "day_type":    day_type.value,
        }

    return CrowdednessEstimate(
        score=round(score, 3),
        level=level,
        confidence=confidence,
        factors=factors_dict,
    )
