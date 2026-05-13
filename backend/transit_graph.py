"""
Transit graph builder and route finder for the CTA transit network.

Builds a NetworkX directed weighted graph from CTA GTFS static data.

Nodes:  train parent stations (mapids 40000–49999) and bus stops (IDs 0–29999)
Edges:
  - Transit:  consecutive stops on the same trip; weight = scheduled minutes
  - Transfer: inter-station transfer points (from transfers.txt); weight = 2 min
  - Walk:     train↔bus transfer connections within 0.15 miles; weight = street
              walk minutes (Feature B — intermodal routing)

The graph is built once and cached for the lifetime of the process.

stop_times.txt is 5.8 M rows / 354 MB.  We stream it in one pass, collecting
rows only for one representative trip per (route_id, direction_id).  It is
never loaded fully into memory.
"""

import csv
import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import networkx as nx
import numpy as np

from gtfs_loader import GTFS_DIR, find_nearest_train_stations, find_nearest_bus_stops
from utils import haversine_miles as _haversine_miles, SpatialGrid, TRANSFER_PENALTY_MINUTES, CHICAGO_TZ
from cta_client import LINE_NAMES
from walking import (
    walk_minutes as street_walk_minutes,
    walk_path as street_walk_path,
    walk_directions as street_walk_directions,
    walk_all as street_walk_all,
)
import config as _cfg

# Default transfer time at a station when switching lines (minutes)
_TRANSFER_MINUTES = TRANSFER_PENALTY_MINUTES

# Maximum number of line changes per route (3 transit legs = 2 transfers).
# find_routes() drops any candidate path that exceeds this so Yen's algorithm
# can't surface absurd 4+ transfer itineraries.
_MAX_TRANSFERS: int = 2

# Deadline applied to NetworkX Yen's k-shortest-paths iteration in find_routes
# (BUG-049 chunk 1). Yen's is a generator that can take arbitrarily long on a
# pathologically dense neighbourhood; without a deadline a single stuck request
# would hold _routing_lock and stall every subsequent caller. The loop returns
# whatever routes have been accepted so far (possibly zero) when the deadline
# trips. 0 disables the deadline.
_YEN_DEADLINE_S: float = _cfg.ROUTING_YEN_DEADLINE_S


def _bearing_to_direction(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Map the bearing from (lat1,lon1)→(lat2,lon2) to a CTA-style cardinal
    direction string ("Northbound"/"Southbound"/"Eastbound"/"Westbound").
    Returns "Northbound" as a safe fallback for degenerate input."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(phi2)
    y = (math.cos(phi1) * math.sin(phi2)
         - math.sin(phi1) * math.cos(phi2) * math.cos(dlon))
    bearing = (math.degrees(math.atan2(x, y)) + 360) % 360
    if bearing < 45 or bearing >= 315:
        return "Northbound"
    if bearing < 135:
        return "Eastbound"
    if bearing < 225:
        return "Southbound"
    return "Westbound"

# Pre-computed shape lookup: (route_id, direction_id) -> [[lat, lon], ...]
# Populated once during warm_up() by _build_shape_lookup(); read-only after that.
_shape_lookup: dict[tuple[str, str], list[list[float]]] = {}

# Maximum plausible scheduled leg time; longer values are treated as GTFS noise
_MAX_LEG_MINUTES: float = _cfg.MAX_LEG_MINUTES

# Target departure time for representative trip selection: noon = 720 min past midnight.
# Used by the canonical (midday) snapshot that backs aux caches like
# _train_stop_pos and _bus_seq_cache; per-period builds use their own targets
# from _PERIODS below (BUG-051).
_TARGET_NOON_MINUTES = 720.0


# ---------------------------------------------------------------------------
# Service-period graph variants (BUG-051)
# ---------------------------------------------------------------------------
# Until 2026-05-12 the engine built ONE graph using trips closest to noon and
# served every query off that snapshot. A 3 AM owl-hour query could be told to
# board a line whose service ended at 1:30 AM. The fix is to build five graph
# variants tagged by service period and pick the appropriate one per request
# based on the requested departure time (defaults to "now" in Chicago time).
#
# Periods are mutually exclusive in real time (every Chicago wall-clock minute
# resolves to exactly one). Their clock windows for query-time selection are:
#
#   weekday_peak     Mon–Fri  06:00–09:30 + 15:30–19:00
#   weekday_midday   Mon–Fri  09:30–15:30
#   weekday_evening  Mon–Fri  19:00–22:00
#   weekend          Sat–Sun  05:00–22:00
#   owl              Every    22:00–05:00 (wraps midnight)
#
# Trip-to-period assignment uses the trip's first-stop departure (GTFS minutes
# past midnight) normalized to 0–1439, with a day-of-week shift when GTFS time
# is ≥24:00 (e.g. a weekday trip starting at GTFS 25:30 actually runs at 01:30
# the FOLLOWING day, so its effective day-set shifts by +1 — sending it to the
# owl variant whose period.days set spans every weekday).
#
# Memory cost: ~5× a single graph, fits Railway free tier.
# Build cost: lazy per-period — the first request for a given period triggers
# that variant's build (~few seconds, since the underlying GTFS streams happen
# only once via _load_canonical_trip_data()). Subsequent same-period requests
# read the cached graph for free.

@dataclass(frozen=True)
class _ServicePeriod:
    name: str
    days: frozenset           # 0=Mon..6=Sun; days on which the period applies
    windows: tuple            # ((start_min, end_min), ...) clock minutes in 0–1440
    target_min: int           # representative-trip selection target (minutes past midnight)


_PERIODS_LIST: tuple[_ServicePeriod, ...] = (
    _ServicePeriod("weekday_peak",    frozenset({0, 1, 2, 3, 4}), ((360, 570), (930, 1140)), 480),
    _ServicePeriod("weekday_midday",  frozenset({0, 1, 2, 3, 4}), ((570, 930),),             720),
    _ServicePeriod("weekday_evening", frozenset({0, 1, 2, 3, 4}), ((1140, 1320),),          1230),
    _ServicePeriod("weekend",         frozenset({5, 6}),          ((300, 1320),),            720),
    # Owl spans midnight: 22:00–24:00 + 00:00–05:00, every day.
    _ServicePeriod("owl",             frozenset({0, 1, 2, 3, 4, 5, 6}), ((1320, 1440), (0, 300)), 120),
)
_PERIODS: dict[str, _ServicePeriod] = {p.name: p for p in _PERIODS_LIST}
# Canonical period used by aux caches and as the back-compat default when no
# departure_time is given AND the current Chicago time happens to fall outside
# every variant's window (which should never happen — the periods tile the day —
# but defensively the default is midday).
_DEFAULT_PERIOD: str = "weekday_midday"


def _select_period(dt: datetime | None = None) -> str:
    """
    Pick which service-period variant should serve a query at *dt*.

    *dt* is treated as Chicago wall-clock time:
      - None        → datetime.now(CHICAGO_TZ)
      - naive       → assume already Chicago-local
      - tz-aware    → converted to Chicago
    Returns one of the period names in _PERIODS.
    """
    if dt is None:
        dt = datetime.now(CHICAGO_TZ)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=CHICAGO_TZ)
    else:
        dt = dt.astimezone(CHICAGO_TZ)
    dow = dt.weekday()               # 0=Mon … 6=Sun
    mod = dt.hour * 60 + dt.minute   # 0–1439

    # Owl (every day, wraps midnight) wins before the weekday/weekend split so
    # that e.g. 03:00 Sat resolves to owl, not weekend.
    if mod >= 1320 or mod < 300:
        return "owl"
    if dow in (5, 6):
        return "weekend"
    if 360 <= mod < 570 or 930 <= mod < 1140:
        return "weekday_peak"
    if 570 <= mod < 930:
        return "weekday_midday"
    if 1140 <= mod < 1320:
        return "weekday_evening"
    # Mon–Fri 05:00–06:00 — pre-peak sliver. CTA still runs midday-pattern
    # service here; treat as midday.
    return "weekday_midday"


def _periods_for_trip(
    first_dep_min: float,
    service_id: str,
    sids_by_day: dict[int, frozenset[str]],
) -> set[str]:
    """
    Return the set of period names this trip belongs to.

    A trip qualifies for period P iff:
      (1) its service_id is active on at least one calendar day d such that
          (d + day_offset) % 7 ∈ P.days   — where day_offset = first_dep_min // 1440
          accounts for GTFS times ≥ 24:00 spilling onto the next day; AND
      (2) the normalized first-stop minute (first_dep_min % 1440) lies in at
          least one of P.windows.
    """
    normalized = int(first_dep_min) % 1440
    day_offset = int(first_dep_min) // 1440
    effective_days: set[int] = set()
    for d in range(7):
        if service_id in sids_by_day.get(d, frozenset()):
            effective_days.add((d + day_offset) % 7)
    if not effective_days:
        return set()

    matches: set[str] = set()
    for p in _PERIODS_LIST:
        if not (effective_days & p.days):
            continue
        for (start, end) in p.windows:
            if start <= normalized < end:
                matches.add(p.name)
                break
    return matches

# ---------------------------------------------------------------------------
# Intermodal walk-edge tuning constants (used in _build_graph — Feature B)
# ---------------------------------------------------------------------------
# Sourced from config.py — edit there to tune routing behaviour.
_TRANSFER_RADIUS_MILES: float = _cfg.TRANSFER_RADIUS_MILES
_TRANSFER_WALK_CAP_MIN: float = _cfg.TRANSFER_WALK_CAP_MIN
_DETOUR_FACTOR: float          = _cfg.DETOUR_FACTOR

# ---------------------------------------------------------------------------
# Bus-to-bus transfer candidate scoring (used in _select_transfer_candidates — Feature C)
# ---------------------------------------------------------------------------
# Sourced from config.py — edit there to tune routing behaviour.
_MAX_EXIT_DIST: float              = _cfg.MAX_EXIT_DIST_MILES
_MAX_TRANSFER_WALK: float          = _cfg.MAX_TRANSFER_WALK_MILES
_FWD_PROGRESS_RATIO: float         = _cfg.FWD_PROGRESS_RATIO
_MAX_CANDIDATES_PER_ARRIVAL: int   = _cfg.MAX_CANDIDATES_PER_ARRIVAL
_TRANSFER_SCORE_WALK_FACTOR: float = _cfg.TRANSFER_SCORE_WALK_FACTOR

# ---------------------------------------------------------------------------
# Module-level state — initialization contract
# ---------------------------------------------------------------------------
# All module-level dicts/None values below are populated exactly once:
#
#   _shape_lookup       ← warm_up() → _build_shape_lookup()   (read-only after)
#   _bus_seq_cache      ← _load_canonical_trip_data() during warm_up() (read-only after)
#   _last_departure     ← _load_canonical_trip_data() during warm_up() (read-only after)
#   _train_stop_pos     ← _load_canonical_trip_data() during warm_up() (read-only after)
#   _stop_to_routes     ← warm_up() → _build_stop_to_routes() (read-only after)
#   _bus_stop_grid      ← module import → _build_bus_stop_grid() (read-only after)
#   _bus_stop_coords    ← same as above
#   _station_exits      ← module import → _load_station_exits()  (read-only after)
#
# All writes go through a single initializer function and are protected by the
# GIL (CPython).  No writes occur after startup, so concurrent reads are safe.

# Global lock serialising route finding on the shared transit graph.
# The previous design used a thread-local copy of G_base per executor thread to
# avoid taking a lock — but FastAPI's default 40-thread pool meant up to 40×
# the graph in RAM. find_routes() typically completes in well under 200 ms, so
# serialising the routing section is a far better trade-off than carrying that
# much duplicate graph state. ORIGIN/DEST virtual nodes and their edges are
# mutated under the lock and removed in a `finally` block so the shared graph
# is always left in its base state for the next call.
_routing_lock: threading.Lock = threading.Lock()

# Cache populated by _populate_canonical_aux_caches() during warm_up()
# so get_bus_stop_sequences() can return it without re-streaming stop_times.txt.
_bus_seq_cache: dict[tuple[str, str], list[tuple]] | None = None

# Last scheduled departure per (route_id, direction_id, parent_mapid) —
# populated during startup and used by the /last-departure endpoint
# (Last Train tool). Keys: (route_id_str, direction_id_str, parent_mapid_str),
# Values: GTFS departure time string (HH:MM:SS, may be "24:xx"/"25:xx" for
# post-midnight CTA service runs). Keyed per-line so a multi-line station
# (Belmont serves Red/Brown/Purple) returns the correct last-train for the
# line the rider actually wants.
_last_departure: dict[tuple[str, str, str], str] = {}

# Train stop position index for crowdedness bell-curve.
# (parent_mapid, route_id, direction_id) → (position_0based, total_stops)
# Populated during _populate_canonical_aux_caches(); read-only after startup.
_train_stop_pos: dict[tuple[str, str, str], tuple[int, int]] = {}

# Cache populated by _load_canonical_trip_data() so _build_shape_lookup() can
# skip its own pass over trips.txt. Tuple of (route_dir_shape_candidates,
# used_shape_ids).
_shape_candidates_cache: tuple[dict[tuple[str, str], set[str]], set[str]] | None = None


# ---------------------------------------------------------------------------
# Route / Leg data structures
# ---------------------------------------------------------------------------

@dataclass
class WalkLeg:
    from_name: str
    to_name: str
    minutes: float
    path_points: list = field(default_factory=list)   # [[lat, lon], ...] street path
    directions: list  = field(default_factory=list)   # [{"street", "direction", "minutes"}, ...]
    exit_label: str   = ""                            # Feature A: named exit at alighting station
    leg_type: str     = "walk"


@dataclass
class TransitLeg:
    line: str         # e.g. "Red Line"
    line_code: str    # e.g. "Red"
    from_station: str
    from_mapid: str
    to_station: str
    to_mapid: str
    minutes: float    # scheduled in-vehicle time (no wait time)
    shape_points: list = field(default_factory=list)  # [[lat, lon], ...] clipped GTFS shape
    leg_type: str = "transit"
    transfer_wait_minutes: int | None = None           # Feature D: live wait at transfer boarding stop


@dataclass
class Route:
    legs: list = field(default_factory=list)   # list[WalkLeg | TransitLeg]
    transit_minutes: float = 0.0               # in-vehicle time only
    walk_minutes_total: float = 0.0            # sum of all walk legs
    transfers: int = 0                         # number of line changes
    first_transit_leg_index: int | None = None  # index of first TransitLeg in legs, or None

    @property
    def total_minutes_no_wait(self) -> float:
        """Transit + walk time, excluding wait for the train."""
        return self.transit_minutes + self.walk_minutes_total

    def summary(self) -> str:
        """One-line human-readable summary for logging."""
        parts = []
        for leg in self.legs:
            if leg.leg_type == "walk":
                parts.append(f"Walk {leg.minutes:.0f}min")
            else:
                parts.append(f"{leg.line} ({leg.from_station}->{leg.to_station} {leg.minutes:.0f}min)")
        return " -> ".join(parts) + f"  [total excl. wait: {self.total_minutes_no_wait:.0f}min]"


# ---------------------------------------------------------------------------
# Single arithmetic authority for total trip minutes (BUG-050).
#
# Every site that converts a Route + live-wait data into a displayed total
# trip time must route through compute_route_total(). This keeps the formula
# in one place so a change to the leg-2 fallback, the wait semantics, or the
# transfer-penalty accounting cannot drift between call sites — which is what
# caused BUG-008. No caller should add to `route.total_minutes_no_wait`
# directly; pass the route in and let this function do the arithmetic.
#
# Walk-speed scaling is normally applied in-place to route legs by
# main._scale_walk_legs() BEFORE this is called, in which case `walk_factor`
# is left at 1.0. The `walk_factor` parameter exists for the BUG-045 case
# inside _build_transfer_routes() where the Route is still baseline-walked
# but ranking needs the weather-derated walk minutes.
# ---------------------------------------------------------------------------
def compute_route_total(
    route: "Route",
    first_leg_wait: float = 0.0,
    transfer_waits: "list | None" = None,
    walk_factor: float = 1.0,
) -> float:
    """Return the total trip minutes for a route given live-wait data.

    Formula:
        total = route.transit_minutes
              + route.walk_minutes_total * walk_factor
              + first_leg_wait
              + sum(w if w is not None else TRANSFER_PENALTY_MINUTES
                    for w in transfer_waits[:route.transfers])

    `transfer_waits` is one entry per non-first transit leg, in leg order.
    Missing or `None` entries fall back to TRANSFER_PENALTY_MINUTES — the same
    flat estimate used everywhere else as the "no live data yet" wait. If
    `transfer_waits` is shorter than `route.transfers`, the missing tail
    likewise falls back.

    `walk_factor` defaults to 1.0; pass a value > 1.0 when the route's
    walk_minutes_total has not yet been weather-derated by _scale_walk_legs().
    """
    waits = list(transfer_waits or [])
    total = float(route.transit_minutes) + float(route.walk_minutes_total) * walk_factor
    total += float(first_leg_wait)
    for i in range(route.transfers):
        w = waits[i] if i < len(waits) else None
        total += float(w) if w is not None else TRANSFER_PENALTY_MINUTES
    return total


# BUG-047 — Typed result for find_routes_with_status().
#
# When the caller doesn't pre-resolve origin/destination, find_routes() searches
# outward in 0.25-mile rings up to 2.0 miles for a nearby train station. If
# nothing is in range, it used to return [] silently — indistinguishable from a
# transient backend failure. find_routes_with_status() returns this struct so
# callers can tell the three cases apart:
#
#   status="ok"               — `routes` is the (possibly empty) result list
#   status="out_of_coverage"  — origin and/or destination has no station within
#                               `max_radius_searched` miles; `side` identifies
#                               which boundary failed
#   status="no_path"          — both boundaries resolved but Yen's produced no
#                               accepted path (all candidates over _MAX_TRANSFERS,
#                               graph disconnected, etc.)
#
# `find_routes()` (back-compat alias) keeps returning `list[Route]` — it discards
# the status. /recommend uses find_routes_with_status() to surface the signal.
@dataclass
class RoutingResult:
    routes: list = field(default_factory=list)
    status: str = "ok"                                   # "ok" | "out_of_coverage" | "no_path"
    side: str | None = None                              # "origin" | "destination" | "both" | None
    max_radius_searched: float = 2.0                     # miles — outermost ring tried


# ---------------------------------------------------------------------------
# GTFS small-file loaders
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_all_stops() -> tuple[dict[str, dict], dict[str, str], dict[str, dict]]:
    """
    Single-pass read of stops.txt returning all three stop dicts.

    Returns:
      parent_stations    — {mapid: {name, lat, lon}} for location_type=1 entries (40000–49999)
      platform_to_parent — {platform_stop_id: parent_mapid} for platform stops (30000–39999)
      bus_stop_lookup    — {stop_id: {name, lat, lon}} for bus stops (0–29999)
    """
    stations:  dict[str, dict] = {}
    mapping:   dict[str, str]  = {}
    bus_stops: dict[str, dict] = {}
    with open(GTFS_DIR / "stops.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                sid = int(row["stop_id"].strip())
            except (ValueError, KeyError):
                continue
            if 30000 <= sid <= 39999:
                parent = row.get("parent_station", "").strip()
                if parent:
                    mapping[str(sid)] = parent
                continue
            try:
                lat = float(row["stop_lat"].strip())
                lon = float(row["stop_lon"].strip())
            except (ValueError, KeyError):
                continue
            if 40000 <= sid <= 49999 and row.get("location_type", "").strip() == "1":
                stations[str(sid)] = {
                    "name": row.get("stop_name", "").strip(),
                    "lat":  lat,
                    "lon":  lon,
                }
            elif 0 <= sid <= 29999:
                bus_stops[str(sid)] = {
                    "name": row.get("stop_name", "").strip(),
                    "lat":  lat,
                    "lon":  lon,
                }
    return stations, mapping, bus_stops


def _load_station_data() -> tuple[dict[str, dict], dict[str, str]]:
    """Thin wrapper — use _load_all_stops() when all three dicts are needed."""
    stations, mapping, _ = _load_all_stops()
    return stations, mapping


def _load_parent_stations() -> dict[str, dict]:
    """Thin wrapper kept for isolated callers/tests."""
    stations, _, _ = _load_all_stops()
    return stations


def _load_platform_to_parent() -> dict[str, str]:
    """Thin wrapper kept for isolated callers/tests."""
    _, mapping, _ = _load_all_stops()
    return mapping


@lru_cache(maxsize=1)
def _load_all_routes() -> tuple[set[str], dict[str, str], dict[str, str]]:
    """
    Single-pass read of routes.txt returning:
      train_route_ids   — set of route_ids for rail routes (route_type=1)
      bus_route_map     — {route_id: route_short_name} for bus routes
      route_short_names — {route_id: route_short_name} for all routes
    """
    train_ids: set[str]      = set()
    bus_map:   dict[str, str] = {}
    all_short: dict[str, str] = {}
    with open(GTFS_DIR / "routes.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rid   = row.get("route_id",         "").strip()
            short = row.get("route_short_name", "").strip()
            rtype = row.get("route_type",       "").strip()
            if not rid:
                continue
            if rtype == "1":
                train_ids.add(rid)
            else:
                bus_map[rid] = short or rid
            if short:
                all_short[rid] = short
    return train_ids, bus_map, all_short


def _load_train_route_ids() -> set[str]:
    """Thin wrapper — returns train route IDs from the shared _load_all_routes() cache."""
    train_ids, _, _ = _load_all_routes()
    return train_ids


@lru_cache(maxsize=1)
def _load_service_ids_by_day() -> dict[int, frozenset[str]]:
    """
    Returns ``{0..6: frozenset(service_id) active on that weekday}`` from
    calendar.txt, augmented with services defined purely via calendar_dates.txt
    add-exceptions (≥3 weekday-specific add-dates required, to avoid one-off
    holiday specials being treated as recurring service).

    0 = Monday, 6 = Sunday.
    """
    import datetime as _dt
    by_day: dict[int, set[str]] = {i: set() for i in range(7)}
    day_cols = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

    cal_file = GTFS_DIR / "calendar.txt"
    if cal_file.exists():
        with open(cal_file, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                sid = row.get("service_id", "").strip()
                if not sid:
                    continue
                for i, col in enumerate(day_cols):
                    if row.get(col, "0").strip() == "1":
                        by_day[i].add(sid)

    # calendar_dates.txt: services expressed purely through add-exceptions
    # (exception_type=1). Bucket by the weekday of each add-date and require
    # ≥3 hits on the same weekday before treating that day as a recurring
    # service day, so one-off specials don't pollute the variant routing.
    cal_dates_file = GTFS_DIR / "calendar_dates.txt"
    if cal_dates_file.exists():
        add_counts: dict[tuple[str, int], int] = {}
        with open(cal_dates_file, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("exception_type", "").strip() != "1":
                    continue
                sid = row.get("service_id", "").strip()
                date_str = row.get("date", "").strip()
                if not sid or len(date_str) < 8:
                    continue
                try:
                    d = _dt.date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
                except (ValueError, IndexError):
                    continue
                key = (sid, d.weekday())
                add_counts[key] = add_counts.get(key, 0) + 1
        for (sid, wd), count in add_counts.items():
            if count >= 3:
                by_day[wd].add(sid)

    return {k: frozenset(v) for k, v in by_day.items()}


@lru_cache(maxsize=1)
def _load_weekday_service_ids() -> frozenset[str]:
    """Back-compat wrapper: union of Mon–Fri service_ids.

    Existing callers that just want a "weekday" boolean still work; the
    period-aware code uses _load_service_ids_by_day() directly so it can
    distinguish weekday vs weekend service.
    """
    by_day = _load_service_ids_by_day()
    return frozenset().union(*(by_day[i] for i in range(5)))


def _load_trips_unified(
    train_route_ids: set[str],
    bus_route_ids:   set[str],
) -> tuple[
    dict[str, str], dict[str, str], dict[str, str],   # train trip_route, trip_dir, trip_sid
    dict[str, str], dict[str, str], dict[str, str],   # bus   trip_route, trip_dir, trip_sid
    dict[tuple[str, str], set[str]],                  # route_dir_shape_candidates (unfiltered)
    set[str],                                          # used_shape_ids (unfiltered)
]:
    """
    Single-pass read of trips.txt that builds, in one stream:
      - train candidate trips (ALL service_ids, with the per-trip service_id
        retained so the variant builder can later bucket trips by service
        period — BUG-051)
      - bus candidate trips (same shape)
      - shape_id candidates per (route_id, direction_id)
      - the set of all referenced shape_ids

    Returns service_id per trip so period bucketing can intersect it with
    _load_service_ids_by_day() at variant-build time. Before BUG-051 this
    function pre-filtered to weekday service_ids; that bake-in is what made the
    routing engine fixed-noon. We now return every candidate trip and defer
    the period filter to _build_graph_for_period().
    """
    train_route: dict[str, str] = {}
    train_dir:   dict[str, str] = {}
    train_sid:   dict[str, str] = {}

    bus_route: dict[str, str] = {}
    bus_dir:   dict[str, str] = {}
    bus_sid:   dict[str, str] = {}

    route_dir_shape_candidates: dict[tuple[str, str], set[str]] = defaultdict(set)
    used_shape_ids: set[str] = set()

    with open(GTFS_DIR / "trips.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rid          = row.get("route_id",     "").strip()
            direction_id = row.get("direction_id", "0").strip()
            shape_id     = row.get("shape_id",     "").strip()
            tid          = row.get("trip_id",      "").strip()
            sid          = row.get("service_id",   "").strip()

            # Shape lookup — unfiltered.
            if rid and shape_id:
                route_dir_shape_candidates[(rid, direction_id)].add(shape_id)
                used_shape_ids.add(shape_id)

            if not tid:
                continue

            if rid in train_route_ids:
                train_route[tid] = rid
                train_dir[tid]   = direction_id
                train_sid[tid]   = sid
            elif rid in bus_route_ids:
                bus_route[tid] = rid
                bus_dir[tid]   = direction_id
                bus_sid[tid]   = sid

    n_train_dirs = len({(r, train_dir[t]) for t, r in train_route.items()})
    n_bus_dirs   = len({(r, bus_dir[t])   for t, r in bus_route.items()})
    print(f"[transit_graph] Loaded {len(train_route)} candidate train trips "
          f"across {n_train_dirs} line/direction pairs")
    print(f"[transit_graph] Loaded {len(bus_route)} candidate bus trips "
          f"across {n_bus_dirs} route/direction pairs")
    return (
        train_route, train_dir, train_sid,
        bus_route,   bus_dir,   bus_sid,
        route_dir_shape_candidates, used_shape_ids,
    )


def _parse_gtfs_time(t: str) -> float:
    """GTFS HH:MM:SS → minutes since midnight. Handles times past 24:00."""
    parts = t.strip().split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    return h * 60.0 + m + s / 60.0


def _stream_all_stop_sequences(
    train_candidates:   dict[str, str],   # {trip_id: route_id}  — ALL train candidate trips
    train_dirs:         dict[str, str],   # {trip_id: direction_id}
    bus_candidates:     dict[str, str],   # {trip_id: route_id}  — ALL bus candidate trips
    bus_dirs:           dict[str, str],   # {trip_id: direction_id}
    platform_to_parent: dict[str, str],   # {platform_stop_id: parent_mapid}
    bus_stop_lookup:    dict[str, dict],  # {stop_id: {name, lat, lon}}
    bus_route_map:      dict[str, str],   # {route_id: route_short_name}
) -> tuple[
    dict[str, list[tuple[str, float]]],          # train_seqs       tid -> [(parent_mapid, arr_min), ...]
    dict[str, float],                             # train_first_dep tid -> first stop arr_min
    dict[str, list[tuple]],                       # bus_seqs        tid -> [(stop_id, name, lat, lon, arr_min), ...]
    dict[str, float],                             # bus_first_dep   tid -> first stop arr_min
    dict[tuple[str, str, str], str],              # last_dep_times  (route_id, dir, mapid) -> latest GTFS time string
]:
    """
    Single-pass stream of stop_times.txt for every candidate trip in
    *train_candidates* and *bus_candidates*. Unlike the pre-BUG-051
    implementation, this no longer picks a single representative trip per
    (route_id, direction_id) — that choice is now made per service-period
    variant in _build_graph_for_period(), since different periods need
    different representatives (an owl-hour run vs. a peak-hour express).

    Returns the raw per-trip sequences plus the per-trip first-stop departure
    minute (used by _periods_for_trip() to bucket each trip) and the
    Feature-Last-Train lookup, which still aggregates across ALL trips.
    """
    print("[transit_graph] Streaming stop_times.txt (unified train+bus pass) …")
    t0 = time.time()

    train_raw: dict[str, list] = {tid: [] for tid in train_candidates}
    bus_raw:   dict[str, list] = {tid: [] for tid in bus_candidates}
    # Last Train tool: latest GTFS departure per (route_id, direction_id,
    # parent_mapid). Per-line keying lets a multi-line station return the
    # correct last-train for the specific line the rider picked.
    last_dep: dict[tuple[str, str, str], tuple[float, str]] = {}

    all_candidate_tids = set(train_candidates) | set(bus_candidates)
    # CTA stop_times.txt is sorted by trip_id (standard GTFS), so all rows for
    # a given trip are contiguous. Track which candidate trips have not yet
    # been fully seen; once the set empties, every remaining row is irrelevant.
    remaining_tids: set[str] = set(all_candidate_tids)
    prev_tid: str | None = None
    rows_read = 0

    with open(GTFS_DIR / "stop_times.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows_read += 1
            tid = row.get("trip_id", "").strip()

            if tid != prev_tid:
                if prev_tid in remaining_tids:
                    remaining_tids.discard(prev_tid)
                    if not remaining_tids:
                        break
                prev_tid = tid

            if tid not in all_candidate_tids:
                continue

            arr_str = (row.get("arrival_time") or row.get("departure_time") or "").strip()
            if not arr_str:
                continue

            try:
                seq     = int(row.get("stop_sequence", "0").strip())
                arr_min = _parse_gtfs_time(arr_str)
            except (ValueError, IndexError):
                continue

            if tid in train_raw:
                sid = row.get("stop_id", "").strip()
                parent = platform_to_parent.get(sid, sid)
                train_raw[tid].append((seq, parent, arr_min))
                dep_str = (row.get("departure_time") or arr_str).strip()
                try:
                    dep_min = _parse_gtfs_time(dep_str)
                except (ValueError, IndexError):
                    dep_min = arr_min
                rid = train_candidates.get(tid, "")
                did = train_dirs.get(tid, "0")
                key = (rid, did, parent)
                prev = last_dep.get(key)
                if prev is None or dep_min > prev[0]:
                    last_dep[key] = (dep_min, dep_str)

            if tid in bus_raw:
                sid = row.get("stop_id", "").strip()
                if sid in bus_stop_lookup:
                    bus_raw[tid].append((seq, sid, arr_min))

    print(
        f"[transit_graph] Unified stream: {rows_read:,} rows in {time.time() - t0:.1f}s"
    )

    # ------------------------------------------------------------------ #
    # Sort per-trip rows and produce the per-period builder's inputs.
    # ------------------------------------------------------------------ #
    train_seqs:      dict[str, list[tuple[str, float]]] = {}
    train_first_dep: dict[str, float]                    = {}
    for tid, rows in train_raw.items():
        if not rows:
            continue
        rows.sort(key=lambda x: x[0])
        train_seqs[tid]      = [(parent, arr_min) for _, parent, arr_min in rows]
        train_first_dep[tid] = rows[0][2]

    bus_seqs:      dict[str, list[tuple]] = {}
    bus_first_dep: dict[str, float]       = {}
    for tid, rows in bus_raw.items():
        if not rows:
            continue
        rows.sort(key=lambda x: x[0])
        bus_seqs[tid] = [
            (
                sid,
                bus_stop_lookup.get(sid, {}).get("name", sid),
                bus_stop_lookup.get(sid, {}).get("lat", 0.0),
                bus_stop_lookup.get(sid, {}).get("lon", 0.0),
                arr_min,
            )
            for _, sid, arr_min in rows
        ]
        bus_first_dep[tid] = rows[0][2]

    last_dep_times: dict[tuple[str, str, str], str] = {k: v[1] for k, v in last_dep.items()}
    print(f"[transit_graph] Per-trip sequences collected: "
          f"{len(train_seqs)} train, {len(bus_seqs)} bus")
    print(f"[transit_graph] Last-departure lookup built: "
          f"{len(last_dep_times)} route/direction/station triples")

    return train_seqs, train_first_dep, bus_seqs, bus_first_dep, last_dep_times


def _load_transfer_edges(
    platform_to_parent: dict[str, str],
    parent_stations: dict[str, dict],
) -> list[tuple[str, str, float]]:
    """
    Returns [(from_mapid, to_mapid, minutes)] from transfers.txt.
    Self-transfers and transfers between stops that aren't in our node set
    are filtered out.
    """
    edges: list[tuple[str, str, float]] = []
    xfer_file = GTFS_DIR / "transfers.txt"
    if not xfer_file.exists():
        return edges

    with open(xfer_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            from_sid = row.get("from_stop_id", "").strip()
            to_sid   = row.get("to_stop_id",   "").strip()

            # Map platform → parent (fall back to the ID itself if it's already a parent)
            from_p = platform_to_parent.get(from_sid, from_sid)
            to_p   = platform_to_parent.get(to_sid,   to_sid)

            if from_p == to_p:
                continue  # same parent — same-station line changes need no edge
            if from_p not in parent_stations or to_p not in parent_stations:
                continue

            # Pessimistic floor: even if GTFS publishes a sub-2-minute transfer
            # (e.g. 45 s for a cross-platform xfer), we clamp it to _TRANSFER_MINUTES
            # so routing estimates stay conservative and never promise a tight
            # connection that relies on a GTFS value we haven't validated in the field.
            # To override, change _TRANSFER_MINUTES at the top of this file.
            try:
                min_sec = float(row.get("min_transfer_time", "").strip() or "0")
                minutes = max(min_sec / 60.0, _TRANSFER_MINUTES)
            except ValueError:
                minutes = _TRANSFER_MINUTES

            edges.append((from_p, to_p, minutes))
    return edges


# ---------------------------------------------------------------------------
# Graph builder — service-period-aware (BUG-051)
# ---------------------------------------------------------------------------
#
# Until 2026-05-12 a single graph was built using trips closest to noon and
# served every query. The refactor introduces:
#
#   _load_canonical_trip_data()  — one-shot GTFS pass. Streams trips.txt and
#                                  stop_times.txt once for every candidate
#                                  trip and stashes per-trip sequences,
#                                  first-stop departure minute, and service_id
#                                  in module state. Populates _last_departure
#                                  too (period-independent).
#
#   _build_graph_for_period(p)  — lazy per-period build. Filters the canonical
#                                  trip data to trips operating in period *p*,
#                                  picks one representative trip per
#                                  (route_id, direction_id) using that period's
#                                  target_min, and assembles the NetworkX
#                                  graph. Each variant is cached on first
#                                  build; subsequent same-period requests
#                                  return the cached graph directly.
#
#   _build_graph()              — back-compat wrapper returning the canonical-
#                                  period graph. Tests that patch this function
#                                  continue to work transparently because
#                                  find_routes_with_status() funnels
#                                  default-period requests back through it.
#
# Auxiliary caches that are period-independent (_bus_seq_cache for stop-
# position lookups; _train_stop_pos for the crowdedness bell-curve) are
# populated from the canonical (midday) trip selection — not per-variant —
# since their consumers want a stable positional view, not a service-period
# view.


@dataclass
class _CanonicalTripData:
    parent_stations:    dict[str, dict]
    platform_to_parent: dict[str, str]
    bus_route_map:      dict[str, str]
    bus_stop_lookup:    dict[str, dict]

    train_seqs:        dict[str, list[tuple[str, float]]]
    train_first_dep:   dict[str, float]
    train_trip_route:  dict[str, str]
    train_trip_dir:    dict[str, str]
    train_trip_sid:    dict[str, str]

    bus_seqs:          dict[str, list[tuple]]
    bus_first_dep:     dict[str, float]
    bus_trip_route:    dict[str, str]
    bus_trip_dir:      dict[str, str]
    bus_trip_sid:      dict[str, str]


_canonical_data: _CanonicalTripData | None = None
_canonical_lock: threading.Lock = threading.Lock()

# Per-period graph cache. Built lazily on first request for the period.
_variant_graphs: dict[str, tuple[nx.DiGraph, dict[str, dict]]] = {}
_variant_locks:  dict[str, threading.Lock] = {p.name: threading.Lock() for p in _PERIODS_LIST}


def _load_canonical_trip_data() -> _CanonicalTripData:
    """
    Stream GTFS files once and stash per-trip data needed by every variant
    build. Subsequent calls return the cached struct directly.
    """
    global _canonical_data, _last_departure, _shape_candidates_cache
    if _canonical_data is not None:
        return _canonical_data
    with _canonical_lock:
        if _canonical_data is not None:
            return _canonical_data

        print("[transit_graph] Loading canonical GTFS trip data …")
        t0 = time.time()

        parent_stations, platform_to_parent = _load_station_data()
        train_route_ids    = _load_train_route_ids()
        bus_route_map      = _load_bus_route_map()
        bus_stop_lookup    = _load_bus_stop_lookup()

        (
            train_trip_route, train_trip_dir, train_trip_sid,
            bus_trip_route,   bus_trip_dir,   bus_trip_sid,
            shape_candidates, used_shape_ids,
        ) = _load_trips_unified(train_route_ids, set(bus_route_map.keys()))

        _shape_candidates_cache = (shape_candidates, used_shape_ids)

        (
            train_seqs, train_first_dep,
            bus_seqs,   bus_first_dep,
            last_dep_times,
        ) = _stream_all_stop_sequences(
            train_trip_route, train_trip_dir,
            bus_trip_route,   bus_trip_dir,
            platform_to_parent,
            bus_stop_lookup,
            bus_route_map,
        )

        _last_departure = last_dep_times

        _canonical_data = _CanonicalTripData(
            parent_stations=parent_stations,
            platform_to_parent=platform_to_parent,
            bus_route_map=bus_route_map,
            bus_stop_lookup=bus_stop_lookup,
            train_seqs=train_seqs,
            train_first_dep=train_first_dep,
            train_trip_route=train_trip_route,
            train_trip_dir=train_trip_dir,
            train_trip_sid=train_trip_sid,
            bus_seqs=bus_seqs,
            bus_first_dep=bus_first_dep,
            bus_trip_route=bus_trip_route,
            bus_trip_dir=bus_trip_dir,
            bus_trip_sid=bus_trip_sid,
        )
        _populate_canonical_aux_caches(_canonical_data)
        print(f"[transit_graph] Canonical trip data ready ({time.time() - t0:.1f}s)")
        return _canonical_data


def _populate_canonical_aux_caches(data: _CanonicalTripData) -> None:
    """
    Pick midday rep trips per (route, dir) and populate _bus_seq_cache plus
    _train_stop_pos. These caches feed callers that need a stable positional
    view (crowdedness bell-curve, transfer scoring) — not per-period ones.
    """
    global _bus_seq_cache, _train_stop_pos

    # Train stop position index
    train_groups: dict[tuple[str, str], list[str]] = {}
    for tid in data.train_seqs:
        rid = data.train_trip_route.get(tid)
        if not rid:
            continue
        did = data.train_trip_dir.get(tid, "0")
        train_groups.setdefault((rid, did), []).append(tid)

    train_pos: dict[tuple[str, str, str], tuple[int, int]] = {}
    for (rid, did), tids in train_groups.items():
        best = max(tids, key=lambda t: (
            len(data.train_seqs.get(t, [])),
            -abs(data.train_first_dep.get(t, 0.0) - _TARGET_NOON_MINUTES),
        ))
        seq = data.train_seqs[best]
        total = len(seq)
        for pos, (mapid, _) in enumerate(seq):
            train_pos[(mapid, rid, did)] = (pos, total)
    _train_stop_pos = train_pos

    # Canonical (midday) bus stop sequences
    bus_groups: dict[tuple[str, str], list[str]] = {}
    for tid in data.bus_seqs:
        rid = data.bus_trip_route.get(tid)
        if not rid:
            continue
        did = data.bus_trip_dir.get(tid, "0")
        bus_groups.setdefault((rid, did), []).append(tid)

    bus_result: dict[tuple[str, str], list[tuple]] = {}
    for (rid, did), tids in bus_groups.items():
        best = min(tids, key=lambda t: abs(data.bus_first_dep.get(t, 0.0) - _TARGET_NOON_MINUTES))
        short = data.bus_route_map.get(rid, rid)
        bus_result[(short, did)] = data.bus_seqs[best]
    _bus_seq_cache = bus_result
    print(f"[transit_graph] Canonical aux caches: "
          f"{len(train_pos)} train stop-pos entries, {len(bus_result)} bus route/dir sequences")


def _select_representative_trips(
    data: _CanonicalTripData,
    period_name: str,
) -> tuple[dict[str, tuple[str, str]], dict[tuple[str, str], list[tuple]]]:
    """
    For the given period, return:
      train_selected — {tid: (route_id, dir_id)} for each chosen rep trip
                       (longest sequence, tie-break by closest-to-target)
      bus_for_period — {(route_short, dir_id): bus stop sequence} for the rep
                       bus trip in that period
    Trips not operating in the period are filtered via _periods_for_trip().
    """
    period = _PERIODS[period_name]
    sids_by_day = _load_service_ids_by_day()

    # Train
    train_groups: dict[tuple[str, str], list[str]] = {}
    for tid, first_dep in data.train_first_dep.items():
        sid = data.train_trip_sid.get(tid, "")
        if not sid:
            continue
        if period_name not in _periods_for_trip(first_dep, sid, sids_by_day):
            continue
        rid = data.train_trip_route.get(tid)
        if not rid:
            continue
        did = data.train_trip_dir.get(tid, "0")
        train_groups.setdefault((rid, did), []).append(tid)

    train_selected: dict[str, tuple[str, str]] = {}
    for (rid, did), tids in train_groups.items():
        # Prefer longest sequence so peak-only expresses (e.g. Purple Express)
        # are picked when they're in the candidate set; tie-break by closeness
        # to the period's target minute so travel-time estimates reflect
        # typical speed in that period.
        best = max(tids, key=lambda t: (
            len(data.train_seqs.get(t, [])),
            -abs(data.train_first_dep.get(t, 0.0) - period.target_min),
        ))
        train_selected[best] = (rid, did)

    # Bus
    bus_groups: dict[tuple[str, str], list[str]] = {}
    for tid, first_dep in data.bus_first_dep.items():
        sid = data.bus_trip_sid.get(tid, "")
        if not sid:
            continue
        if period_name not in _periods_for_trip(first_dep, sid, sids_by_day):
            continue
        rid = data.bus_trip_route.get(tid)
        if not rid:
            continue
        did = data.bus_trip_dir.get(tid, "0")
        bus_groups.setdefault((rid, did), []).append(tid)

    bus_for_period: dict[tuple[str, str], list[tuple]] = {}
    for (rid, did), tids in bus_groups.items():
        best = min(tids, key=lambda t: abs(data.bus_first_dep.get(t, 0.0) - period.target_min))
        short = data.bus_route_map.get(rid, rid)
        bus_for_period[(short, did)] = data.bus_seqs[best]

    return train_selected, bus_for_period


def _assemble_graph(
    parent_stations: dict[str, dict],
    platform_to_parent: dict[str, str],
    bus_stop_lookup: dict[str, dict],
    train_selected: dict[str, tuple[str, str]],
    train_seqs: dict[str, list[tuple[str, float]]],
    bus_for_period: dict[tuple[str, str], list[tuple]],
    period_label: str,
) -> nx.DiGraph:
    """Construct the NetworkX graph for a single service-period variant from
    already-selected representative trips."""
    G = nx.DiGraph()

    for mapid, meta in parent_stations.items():
        G.add_node(mapid, node_type="train", **meta)

    edge_candidates: dict[tuple[str, str], list] = {}
    for tid, (route_id, dir_id) in train_selected.items():
        seq = train_seqs[tid]
        line_name = LINE_NAMES.get(route_id, route_id)
        for i in range(len(seq) - 1):
            from_mapid, from_min = seq[i]
            to_mapid,   to_min   = seq[i + 1]
            if from_mapid not in parent_stations or to_mapid not in parent_stations:
                continue
            if from_mapid == to_mapid:
                continue
            leg_min = to_min - from_min
            if leg_min <= 0 or leg_min > _MAX_LEG_MINUTES:
                continue
            edge_candidates.setdefault((from_mapid, to_mapid), []).append(
                (route_id, dir_id, line_name, leg_min)
            )

    transit_edge_count = 0
    for (from_mapid, to_mapid), candidates in edge_candidates.items():
        best_route, best_dir, best_line, best_min = min(candidates, key=lambda x: x[3])
        all_routes = (
            {c[0]: (c[1], c[2]) for c in candidates}
            if len(candidates) > 1 else None
        )
        G.add_edge(
            from_mapid, to_mapid,
            weight=best_min,
            route_id=best_route,
            direction_id=best_dir,
            line=best_line,
            edge_type="transit",
            mode="train",
            all_routes=all_routes,
        )
        transit_edge_count += 1

    transfer_edges = _load_transfer_edges(platform_to_parent, parent_stations)
    transfer_edge_count = 0
    for from_mapid, to_mapid, minutes in transfer_edges:
        for a, b in [(from_mapid, to_mapid), (to_mapid, from_mapid)]:
            if not G.has_edge(a, b):
                G.add_edge(a, b, weight=minutes, route_id="transfer",
                           line="transfer", edge_type="transfer")
                transfer_edge_count += 1

    # Bus stop nodes (period-independent — physical infrastructure)
    for stop_id, stop in bus_stop_lookup.items():
        G.add_node(
            stop_id,
            node_type="bus",
            lat=stop["lat"],
            lon=stop["lon"],
            name=stop["name"],
        )

    # Bus transit edges (period-specific weights from this period's rep trips)
    bus_edge_count = 0
    for (short_name, did), stops in bus_for_period.items():
        if len(stops) < 2:
            continue
        direction_name = _bearing_to_direction(
            stops[0][2], stops[0][3], stops[-1][2], stops[-1][3]
        )
        for i in range(len(stops) - 1):
            from_stop = stops[i]
            to_stop   = stops[i + 1]
            from_id   = from_stop[0]
            to_id     = to_stop[0]
            from_arr  = from_stop[4]
            to_arr    = to_stop[4]
            leg_min   = max(0.5, to_arr - from_arr)
            G.add_edge(
                from_id, to_id,
                weight=leg_min,
                route_id=short_name,
                direction_id=did,
                line=direction_name,
                edge_type="transit",
                mode="bus",
            )
            bus_edge_count += 1

    # Train↔bus intermodal walk edges (period-independent)
    intermodal_edge_count = 0
    for mapid, station in parent_stations.items():
        s_lat, s_lon = station["lat"], station["lon"]
        for dist, stop_id in _bus_stop_grid.query(s_lat, s_lon, _TRANSFER_RADIUS_MILES):
            walk_min = dist / 3.0 * 60 * _DETOUR_FACTOR
            walk_min = max(walk_min, _TRANSFER_MINUTES)
            if walk_min > _TRANSFER_WALK_CAP_MIN:
                continue
            G.add_edge(mapid, stop_id,
                       weight=walk_min, edge_type="walk", route_id="walk", mode="walk")
            G.add_edge(stop_id, mapid,
                       weight=walk_min, edge_type="walk", route_id="walk", mode="walk")
            intermodal_edge_count += 2

    print(
        f"[transit_graph] Variant '{period_label}' ready: "
        f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges "
        f"(train: {transit_edge_count} transit + {transfer_edge_count} transfer; "
        f"bus: {bus_edge_count} transit + {intermodal_edge_count} intermodal walk)"
    )
    return G


def _build_graph(period_name: str | None = None) -> tuple[nx.DiGraph, dict[str, dict]]:
    """
    Return ``(G, parent_stations)`` for the requested service period, lazily
    building and caching the variant on first request.

    *period_name* is one of the keys in ``_PERIODS`` (or ``None`` for the
    canonical default). Unknown names fall back to the default.

    This is the unified entry point: legacy callers that pass no argument get
    the canonical (midday) variant, and the period-aware routing path calls it
    with the resolved period name. Tests that patch ``_build_graph`` with a
    fixture mock intercept every variant request — the patch ignores
    ``period_name``, so tests stay deterministic regardless of wall-clock time.
    """
    if period_name is None or period_name not in _PERIODS:
        period_name = _DEFAULT_PERIOD
    cached = _variant_graphs.get(period_name)
    if cached is not None:
        return cached
    with _variant_locks[period_name]:
        cached = _variant_graphs.get(period_name)
        if cached is not None:
            return cached

        t0 = time.time()
        data = _load_canonical_trip_data()
        train_selected, bus_for_period = _select_representative_trips(data, period_name)
        print(
            f"[transit_graph] Building '{period_name}' variant: "
            f"{len(train_selected)} train reps, {len(bus_for_period)} bus reps"
        )
        G = _assemble_graph(
            data.parent_stations,
            data.platform_to_parent,
            data.bus_stop_lookup,
            train_selected,
            data.train_seqs,
            bus_for_period,
            period_name,
        )
        print(f"[transit_graph] Variant '{period_name}' built in {time.time() - t0:.1f}s")
        _variant_graphs[period_name] = (G, data.parent_stations)
        return _variant_graphs[period_name]


# Back-compat alias retained for callers that imported _build_graph_for_period
# before the unification. Identical semantics — pass the period name through.
_build_graph_for_period = _build_graph


def warm_up() -> None:
    """
    Pre-stream GTFS data and pre-build the canonical (midday) graph at startup.

    Per the BUG-051 design (lazy per-period), variant graphs for other periods
    are NOT built here — they build on first request that needs them. The
    canonical pre-pass means each lazy build is just in-memory selection
    + edge assembly (a few seconds), not a fresh file stream.
    """
    _load_canonical_trip_data()
    G, _ = _build_graph()
    print(f"[transit_graph] Graph size: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    get_bus_stop_sequences()
    _build_stop_to_routes()
    _build_shape_lookup()
    _build_station_name_index()
    # Street graph is loaded lazily on the first routing request that needs it.
    # Loading it here would cause an OOM kill on Railway before startup completes.


# ---------------------------------------------------------------------------
# GTFS shape lookup — pre-computed at startup
# ---------------------------------------------------------------------------

def _build_shape_lookup() -> None:
    """
    Populate _shape_lookup at startup.

    Step 1: Obtain (route_id, direction_id, shape_id) candidates and the set of
            shape_ids actually referenced by trips. Normally these were already
            collected by _load_trips_unified() during _build_graph() and live in
            _shape_candidates_cache; if the cache is empty (e.g. tests calling
            this in isolation), fall back to streaming trips.txt here.
    Step 2: Stream shapes.txt → {shape_id: [(seq, lat, lon), ...]}, keeping
            ONLY shape_ids from Step 1's used-set. Unused shapes never enter
            memory. Sort each kept shape by shape_pt_sequence and convert to
            [[lat, lon], ...].
    Step 3: Resolve each (route_id, direction_id) to the shape with the MOST
            points (full-length route vs. short-turn variants).
    Step 4: Join → _shape_lookup[(route_id, direction_id)] = [[lat, lon], ...]

    Knowing the used shape_ids before reading shapes.txt lets us filter inline,
    bounding peak memory to the kept shapes only rather than every point in
    the file. For CTA this is a minor win; for larger agencies it matters.
    """
    global _shape_lookup

    shapes_file = GTFS_DIR / "shapes.txt"
    if not shapes_file.exists():
        print("[transit_graph] shapes.txt not found — shape lookup unavailable")
        return

    print("[transit_graph] Building shape lookup from GTFS …")
    t0 = time.time()

    # --- Step 1: obtain used shape_ids per (route_id, direction_id) ---
    if _shape_candidates_cache is not None:
        route_dir_shape_candidates, used_shape_ids = _shape_candidates_cache
    else:
        # Fallback for isolated callers — should only be reached in tests or
        # unusual call orders where _build_graph() hasn't run yet.
        route_dir_shape_candidates = defaultdict(set)
        used_shape_ids = set()
        with open(GTFS_DIR / "trips.txt", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                route_id     = row.get("route_id",     "").strip()
                direction_id = row.get("direction_id", "0").strip()
                shape_id     = row.get("shape_id",     "").strip()
                if not route_id or not shape_id:
                    continue
                route_dir_shape_candidates[(route_id, direction_id)].add(shape_id)
                used_shape_ids.add(shape_id)

    # --- Step 2: shapes.txt → sorted [[lat, lon], ...], filtered to used set ---
    raw_pts: dict[str, list[tuple[int, float, float]]] = defaultdict(list)

    with open(shapes_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            shape_id = row.get("shape_id", "").strip()
            if not shape_id or shape_id not in used_shape_ids:
                continue
            try:
                seq = int(row["shape_pt_sequence"].strip())
                lat = float(row["shape_pt_lat"].strip())
                lon = float(row["shape_pt_lon"].strip())
            except (ValueError, KeyError):
                continue
            raw_pts[shape_id].append((seq, lat, lon))

    shapes: dict[str, list[list[float]]] = {}
    for shape_id, pts in raw_pts.items():
        pts.sort(key=lambda x: x[0])
        shapes[shape_id] = [[lat, lon] for _, lat, lon in pts]
    raw_pts.clear()

    print(f"[transit_graph] Loaded {len(shapes)} shapes from shapes.txt")

    # --- Step 3: pick the longest shape per (route_id, direction_id) ---
    route_dir_to_shape: dict[tuple[str, str], str] = {}
    for key, shape_ids in route_dir_shape_candidates.items():
        best_sid = ""
        best_n   = -1
        for sid in shape_ids:
            n = len(shapes.get(sid, []))
            if n > best_n:
                best_n   = n
                best_sid = sid
        if best_sid:
            route_dir_to_shape[key] = best_sid

    # --- Step 4: join ---
    # Use the cached routes lookup so bus routes can be found by short_name (e.g. "22")
    # as well as route_id.  find_bus_transfer_routes() calls get_shape(route_short_name,
    # direction_id).  _load_all_routes() is already cached — no extra I/O here.
    _, _, route_short_names = _load_all_routes()

    new_lookup: dict[tuple[str, str], list[list[float]]] = {}
    for (route_id, direction_id), shape_id in route_dir_to_shape.items():
        coords = shapes.get(shape_id)
        if coords:
            new_lookup[(route_id, direction_id)] = coords
            # Always also key by route_short_name so callers can use either
            # identifier. Previously only set when short != route_id, which was
            # brittle if CTA ever renumbers route_ids without updating short_names.
            short = route_short_names.get(route_id, "")
            if short:
                new_lookup[(short, direction_id)] = coords

    _shape_lookup = new_lookup

    print(
        f"[transit_graph] Shape lookup ready: {len(_shape_lookup)} route/direction pairs "
        f"({time.time() - t0:.1f}s)"
    )


def get_station_coords(mapid: str) -> tuple[float, float] | None:
    """
    Return (lat, lon) for a train parent station mapid, or None if not found.
    Uses the already-cached graph — no extra I/O after first call.
    """
    _, stations = _build_graph()
    s = stations.get(mapid)
    return (s["lat"], s["lon"]) if s else None


def get_last_departure(route_id: str, direction_id: str, mapid: str) -> str | None:
    """
    Return the latest scheduled GTFS departure time string (HH:MM:SS, may be
    "24:xx"/"25:xx" for post-midnight CTA runs) for a specific
    (route, direction, parent station), or None if unknown.

    Populated during startup by _build_graph() / _stream_all_stop_sequences().
    Used by the /last-departure endpoint (Last Train tool).
    """
    return _last_departure.get((route_id, direction_id, mapid))


def to_parent_mapid(stop_id: str) -> str:
    """
    Resolve a CTA stop_id to its parent station mapid. Platform stop_ids
    (30000–39999) are mapped to their parent (40000–49999) via the
    platform_to_parent index built from stops.txt; parent mapids and unknown
    IDs pass through unchanged.

    Needed because schedule_data (built offline) publishes platform stop_ids
    in route schedules, while runtime caches keyed on station (e.g.
    _last_departure) use parent mapids.
    """
    return _load_platform_to_parent().get(stop_id, stop_id)


# Station name index — built once during warm_up(); read-only after that.
# _station_name_exact  : lowercase name → (lat, lon) for O(1) exact matches.
# _station_name_entries: pre-built list for the linear contains-match fallback.
_station_name_exact:   dict[str, tuple[float, float]] = {}
_station_name_entries: list[tuple[str, dict]]         = []


def _build_station_name_index() -> None:
    """Populate _station_name_exact and _station_name_entries from the graph cache."""
    global _station_name_exact, _station_name_entries
    _, stations = _build_graph()
    exact: dict[str, tuple[float, float]] = {}
    entries: list[tuple[str, dict]] = []
    for s in stations.values():
        key = s["name"].lower()
        exact[key] = (s["lat"], s["lon"])
        entries.append((key, s))
    _station_name_exact   = exact
    _station_name_entries = entries


@lru_cache(maxsize=512)
def get_station_by_name(name: str) -> tuple[float, float] | None:
    """
    Return (lat, lon) for a train parent station by stop_name (case-insensitive
    exact match, then contains-match fallback). Used to resolve CTA destNm
    terminal names like 'Howard' or '95th/Dan Ryan' to coordinates.
    Returns None if no match found.
    """
    if not _station_name_exact:
        _build_station_name_index()
    name_lower = name.lower().strip()
    # O(1) exact match via pre-built index
    coords = _station_name_exact.get(name_lower)
    if coords:
        return coords
    # Contains-match fallback — rank by similarity to avoid wrong-line matches
    # (e.g. "Harlem" matches both Harlem-Lake and Harlem-Forest Park)
    best_match = None
    best_ratio = 0.0
    for s_lower, s in _station_name_entries:
        if name_lower in s_lower or s_lower in name_lower:
            ratio = SequenceMatcher(None, name_lower, s_lower).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = s
    if best_match:
        return (best_match["lat"], best_match["lon"])
    return None


def get_shape(route_id: str, direction_id: str) -> list[list[float]] | None:
    """
    Return the pre-computed GTFS shape for a (route_id, direction_id) pair.

    Returns [[lat, lon], ...] in shape_pt_sequence order, or None if no shape
    is available (e.g. shapes.txt absent or route not found).
    """
    return _shape_lookup.get((route_id, direction_id))


# Cap on the number of shape points returned per leg. CTA route shapes can be
# 300–500 dense points; the rendered polyline is visually indistinguishable at
# 100 uniformly-sampled points. Trimming here shrinks both the response payload
# and the in-memory footprint of the 500-entry response cache.
_MAX_SHAPE_POINTS_PER_LEG = 100
# Coordinate precision in shape output. 5 decimals ≈ 1.1 m at Chicago's
# latitude — well below the visual resolution of any zoom level used in the UI.
_SHAPE_COORD_DECIMALS = 5


def _round_pt(pt: list[float]) -> list[float]:
    return [round(pt[0], _SHAPE_COORD_DECIMALS), round(pt[1], _SHAPE_COORD_DECIMALS)]


def _downsample_shape(points: list[list[float]]) -> list[list[float]]:
    """Uniformly subsample to at most _MAX_SHAPE_POINTS_PER_LEG points,
    always retaining the first and last point so the polyline starts/ends
    exactly at the boarding/alighting positions."""
    n = len(points)
    if n <= _MAX_SHAPE_POINTS_PER_LEG:
        return [_round_pt(p) for p in points]
    step = (n - 1) / (_MAX_SHAPE_POINTS_PER_LEG - 1)
    out = [_round_pt(points[int(round(i * step))]) for i in range(_MAX_SHAPE_POINTS_PER_LEG - 1)]
    out.append(_round_pt(points[-1]))
    return out


def clip_shape(
    shape_points: list[list[float]] | None,
    board_lat: float,
    board_lon: float,
    exit_lat: float,
    exit_lon: float,
) -> list[list[float]]:
    """
    Clip a full route shape to the segment between a boarding and exit stop.

    Finds the shape point nearest to each stop (by squared Euclidean distance —
    sufficient for nearest-point ranking on the scale of a single CTA route),
    then returns the slice between those two indices inclusive, downsampled to
    at most _MAX_SHAPE_POINTS_PER_LEG points and rounded to 5-decimal precision.

    Falls back to a straight line [[board_lat, board_lon], [exit_lat, exit_lon]]
    if shape_points is None or empty.
    """
    if not shape_points:
        return [_round_pt([board_lat, board_lon]), _round_pt([exit_lat, exit_lon])]

    pts = np.array(shape_points)          # (N, 2) — rows are [lat, lon]
    board_idx = int(np.argmin((pts[:, 0] - board_lat) ** 2 + (pts[:, 1] - board_lon) ** 2))
    exit_idx  = int(np.argmin((pts[:, 0] - exit_lat)  ** 2 + (pts[:, 1] - exit_lon)  ** 2))

    lo = min(board_idx, exit_idx)
    hi = max(board_idx, exit_idx)

    if lo >= hi:
        # Both stops map to the same nearest shape point — happens on short trips
        # where stop spacing exceeds shape point density.  Return a straight line
        # between the actual stop coordinates so the caller always gets ≥ 2 points.
        return [_round_pt([board_lat, board_lon]), _round_pt([exit_lat, exit_lon])]

    segment = shape_points[lo : hi + 1]
    # If the rider travels in the opposite direction of the shape, reverse so the
    # animated polyline direction matches actual travel.
    if board_idx > exit_idx:
        segment = segment[::-1]
    return _downsample_shape(segment)


# ---------------------------------------------------------------------------
# Bus stop sequence table — cached for process lifetime
# ---------------------------------------------------------------------------

def _load_bus_route_map() -> dict[str, str]:
    """Thin wrapper — returns bus route map from the shared _load_all_routes() cache."""
    _, bus_map, _ = _load_all_routes()
    return bus_map


def _load_bus_stop_lookup() -> dict[str, dict]:
    """Thin wrapper — returns bus stop lookup from the shared _load_all_stops() cache."""
    _, _, bus_stops = _load_all_stops()
    return bus_stops


def get_bus_stop_sequences() -> dict[tuple[str, str], list[tuple]]:
    """
    Return the canonical (midday) bus stop sequence table.

    Returns:
        {(route_short_name, direction_id): [
            (stop_id, stop_name, lat, lon, arr_minutes), ...
        ]}
        Sequences are ordered by stop_sequence. arr_minutes is minutes since
        midnight for the canonical midday representative trip — period-
        independent, suitable for positional/transfer-scoring callers.

    Populated by ``_load_canonical_trip_data()`` during ``warm_up()``. Callers
    that hit this function before warm_up trigger the canonical pass now.
    """
    if _bus_seq_cache is None:
        _load_canonical_trip_data()
    # _bus_seq_cache is set by _populate_canonical_aux_caches(); narrow Optional.
    assert _bus_seq_cache is not None
    return _bus_seq_cache


# ---------------------------------------------------------------------------
# Path → Route conversion
# ---------------------------------------------------------------------------

def _resolve_node(node: str, stations: dict, G: "nx.DiGraph") -> tuple[str, float, float]:
    """Return (name, lat, lon) for a train station or bus stop node.

    Train stations are found in the stations dict; bus stops fall back to
    graph node attributes (Feature B — intermodal routing).
    """
    if node in stations:
        s = stations[node]
        return s["name"], s["lat"], s["lon"]
    node_data = G.nodes.get(node, {})
    return node_data.get("name", str(node)), node_data.get("lat", 0.0), node_data.get("lon", 0.0)


def _last_transit_leg(legs: list) -> "TransitLeg | None":
    """Return the most recent TransitLeg in legs, searching backward past walk legs."""
    for leg in reversed(legs):
        if isinstance(leg, TransitLeg):
            return leg
    return None


def _path_to_route(
    path: list[str],
    G: nx.DiGraph,
    stations: dict[str, dict],
    origin_walk_lookup: dict[str, float],  # {mapid: walk_minutes from user}
    dest_walk_lookup:   dict[str, float],  # {mapid: walk_minutes to dest}
    origin_lat: float = 0.0,
    origin_lon: float = 0.0,
    dest_lat: float = 0.0,
    dest_lon: float = 0.0,
) -> Route | None:
    """Convert a graph node path to a structured Route with Walk and Transit legs."""
    if len(path) < 2:
        return None

    legs: list = []
    walk_total    = 0.0
    transit_total = 0.0
    ORIGIN = "__ORIGIN__"
    DEST   = "__DEST__"

    idx = 0
    while idx < len(path) - 1:
        from_node = path[idx]
        to_node   = path[idx + 1]
        edge      = G.edges[from_node, to_node]
        edge_type = edge.get("edge_type", "transit")
        weight    = edge.get("weight", 0.0)

        # ── Walk from user location to first boarding station or bus stop ────
        if from_node == ORIGIN:
            to_name, to_lat, to_lon = _resolve_node(to_node, stations, G)
            walk_min = origin_walk_lookup.get(to_node, weight)
            # walk_all() returns (minutes, directions, path) in one call so the
            # cached Dijkstra result is reused — replaces the prior pair of
            # street_walk_path() + street_walk_directions() calls.
            _wm, walk_dirs, walk_pts = street_walk_all(origin_lat, origin_lon, to_lat, to_lon)
            legs.append(WalkLeg(
                from_name="Your location",
                to_name=to_name,
                minutes=walk_min,
                path_points=walk_pts,
                directions=walk_dirs,
            ))
            walk_total += walk_min
            idx += 1
            continue

        # ── Walk from last alighting station or bus stop to destination ──────
        if to_node == DEST:
            from_name, from_lat, from_lon = _resolve_node(from_node, stations, G)
            walk_min  = dest_walk_lookup.get(from_node, weight)
            # Feature A: use the best station exit if one is known.
            # best_exit() returns None for bus stop IDs — no-op for bus alighting.
            exit_info = best_exit(from_node, dest_lat, dest_lon)
            if exit_info is not None:
                from_lat  = exit_info["lat"]
                from_lon  = exit_info["lon"]
                walk_min  = exit_info["walk_minutes"]
            label = exit_info["label"] if exit_info else ""
            _wm, walk_dirs, walk_pts = street_walk_all(from_lat, from_lon, dest_lat, dest_lon)
            legs.append(WalkLeg(
                from_name=from_name,
                to_name="Your destination",
                minutes=walk_min,
                path_points=walk_pts,
                directions=walk_dirs,
                exit_label=label,
            ))
            walk_total += walk_min
            idx += 1
            continue

        # ── Inter-station transfer walk (train↔train from transfers.txt) ─────
        if edge_type == "transfer":
            from_name, flat, flon = _resolve_node(from_node, stations, G)
            to_name,   tlat, tlon = _resolve_node(to_node,   stations, G)
            _wm, walk_dirs, walk_pts = street_walk_all(flat, flon, tlat, tlon)
            legs.append(WalkLeg(
                from_name=from_name,
                to_name=to_name,
                minutes=weight,
                path_points=walk_pts,
                directions=walk_dirs,
            ))
            walk_total += weight
            idx += 1
            continue

        # ── Mid-path walk edge (train↔bus transfer, Feature B) ─────────────
        # Walk edges between train stations and bus stops have edge_type="walk".
        # They are distinct from ORIGIN/DEST walk legs (handled above) and from
        # transfers.txt transfer edges (edge_type="transfer").
        if edge_type == "walk":
            from_name, flat, flon = _resolve_node(from_node, stations, G)
            to_name,   tlat, tlon = _resolve_node(to_node,   stations, G)
            _wm, walk_dirs, walk_pts = street_walk_all(flat, flon, tlat, tlon)
            legs.append(WalkLeg(
                from_name=from_name,
                to_name=to_name,
                minutes=weight,
                path_points=walk_pts,
                directions=walk_dirs,
            ))
            walk_total += weight
            idx += 1
            continue

        # ── Transit leg — group consecutive same-route edges ──────────────
        group_route = edge.get("route_id", "")
        group_dir   = edge.get("direction_id", "0")
        group_line  = edge.get("line", group_route)
        board_node  = from_node
        alight_node = to_node
        seg_minutes = weight

        # Shared-track label correction: if the incoming transit leg is on a
        # different line that also serves this edge (e.g. Purple through the
        # Red/Purple shared Howard–Belmont segment), prefer the incoming line's
        # label so the leg displays the correct line name to the rider.
        incoming = _last_transit_leg(legs)
        all_routes = edge.get("all_routes")  # {route_id: (dir_id, line_name)} or None
        if (incoming and all_routes
                and incoming.line_code != group_route
                and incoming.line_code in all_routes):
            alt_dir, alt_line = all_routes[incoming.line_code]
            group_route = incoming.line_code
            group_dir   = alt_dir
            group_line  = alt_line

        look = idx + 1
        while look < len(path) - 1 and path[look] != DEST and path[look + 1] != DEST:
            next_edge = G.edges[path[look], path[look + 1]]
            next_route     = next_edge.get("route_id", "")
            next_all       = next_edge.get("all_routes") or {}
            # Continue merging if the next edge serves our (possibly overridden) line
            serves_group = (next_route == group_route or group_route in next_all)
            if not serves_group or next_edge.get("edge_type") != "transit":
                break
            seg_minutes += next_edge.get("weight", 0.0)
            alight_node  = path[look + 1]
            look += 1

        # Detect same-station line change: if previous leg was transit and
        # ended at the same node where this one starts, insert a transfer walk.
        # Bus stop IDs (0–29999) and train mapids (40000+) never collide, so
        # this comparison is safe for both node types.
        if legs and isinstance(legs[-1], TransitLeg) and legs[-1].to_mapid == board_node:
            board_xfer_name, blat, blon = _resolve_node(board_node, stations, G)
            legs.append(WalkLeg(
                from_name=board_xfer_name,
                to_name=board_xfer_name,
                minutes=_TRANSFER_MINUTES,
                path_points=[[blat, blon], [blat, blon]],
                directions=[{"is_platform_transfer": True, "street": "", "direction": "", "minutes": _TRANSFER_MINUTES}],
            ))
            walk_total += _TRANSFER_MINUTES

        board_name,  board_lat,  board_lon  = _resolve_node(board_node,  stations, G)
        alight_name, alight_lat, alight_lon = _resolve_node(alight_node, stations, G)

        # group_route already holds the correct (possibly overridden) route/line code
        # for both train and bus edges — use it directly for the TransitLeg.
        line_code = group_route

        legs.append(TransitLeg(
            line=group_line,
            line_code=line_code,
            from_station=board_name,
            from_mapid=board_node,
            to_station=alight_name,
            to_mapid=alight_node,
            minutes=seg_minutes,
            shape_points=clip_shape(
                get_shape(line_code, group_dir),
                board_lat,  board_lon,
                alight_lat, alight_lon,
            ),
        ))
        transit_total += seg_minutes
        idx = look

    transit_legs = [l for l in legs if isinstance(l, TransitLeg)]
    first_transit_idx = next((i for i, l in enumerate(legs) if isinstance(l, TransitLeg)), None)
    return Route(
        legs=legs,
        transit_minutes=transit_total,
        walk_minutes_total=walk_total,
        transfers=max(0, len(transit_legs) - 1),
        first_transit_leg_index=first_transit_idx,
    )


# ---------------------------------------------------------------------------
# Feature H — Same-line station deduplication
# ---------------------------------------------------------------------------

def _dedup_stations_by_line(G: nx.DiGraph, stations: list[dict]) -> list[dict]:
    """
    Given stations sorted by ascending walk_minutes, keep only the closest
    station per unique set of lines served. Stations that introduce no new
    lines are dropped (they would produce near-duplicate routes).

    Edge case: a station with no edges in the graph is always included to
    avoid silently breaking routing in degenerate cases.
    """
    covered_lines: set[str] = set()
    result: list[dict] = []
    for s in stations:
        mapid = s.get("mapid", "")
        if mapid not in G:
            result.append(s)
            continue
        station_lines: set[str] = set()
        for _, _, data in G.edges(mapid, data=True):
            if data.get("edge_type") != "transit":
                continue
            if data.get("line"):
                station_lines.add(data["line"])
            for _, (_, line_name) in (data.get("all_routes") or {}).items():
                station_lines.add(line_name)
        if not station_lines or station_lines - covered_lines:
            result.append(s)
            covered_lines |= station_lines
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_routes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    origin_stations: list[dict] | None = None,
    n_routes: int = 3,
    origin_bus_stops: list[dict] | None = None,
    dest_bus_stops: list[dict] | None = None,
    effective_speed: float = 1.0,
    departure_time: datetime | None = None,
) -> list[Route]:
    """
    Back-compat wrapper around find_routes_with_status() that returns just the
    list of routes. Callers that need to distinguish out-of-coverage from
    no-path (BUG-047) should use find_routes_with_status() directly.

    *departure_time* — see find_routes_with_status (BUG-051). None means "now".
    """
    return find_routes_with_status(
        origin_lat, origin_lon, dest_lat, dest_lon,
        origin_stations=origin_stations,
        n_routes=n_routes,
        origin_bus_stops=origin_bus_stops,
        dest_bus_stops=dest_bus_stops,
        effective_speed=effective_speed,
        departure_time=departure_time,
    ).routes


# Progressive-expansion rings used when the caller doesn't pre-resolve
# origin/destination train stations. _MAX_RADIUS_MILES is the outermost ring;
# beyond that the boundary is reported as out_of_coverage instead of returning
# an empty list silently (BUG-047).
_RADIUS_RINGS: tuple[float, ...] = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
_MAX_RADIUS_MILES: float = _RADIUS_RINGS[-1]


def find_routes_with_status(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    origin_stations: list[dict] | None = None,
    n_routes: int = 3,
    origin_bus_stops: list[dict] | None = None,
    dest_bus_stops: list[dict] | None = None,
    effective_speed: float = 1.0,
    departure_time: datetime | None = None,
) -> RoutingResult:
    """
    Find the fastest transit routes from (origin_lat, origin_lon) to
    (dest_lat, dest_lon) and report the outcome as a typed RoutingResult.

    Args:
        origin_lat / origin_lon:  User's current coordinates
        dest_lat / dest_lon:      Destination coordinates
        origin_stations:          Pre-computed origin stations from gtfs_loader
                                  (pass these in to avoid recomputing walk times)
        n_routes:                 How many route options to return (default 3)
        origin_bus_stops /
        dest_bus_stops:           Optional pre-resolved bus stops with
                                  walk_minutes already populated. When supplied,
                                  find_routes skips the redundant
                                  find_nearest_bus_stops() call. resolve_location()
                                  in gtfs_loader already does this work for the
                                  user-supplied origin/destination, so the
                                  /recommend path passes its results in.
        effective_speed:          User walk-speed factor × weather precip factor
                                  (BUG-045). When <1.0 (rain, snow, cold, gusts),
                                  Dijkstra derates every walk-type edge weight by
                                  1/effective_speed so route SELECTION reflects
                                  the rider's actual walking pace. The graph
                                  itself is not mutated — a weight callback is
                                  passed to shortest_simple_paths instead. Stored
                                  edge weights remain baseline, so _path_to_route
                                  builds WalkLegs at baseline minutes and the
                                  caller's _scale_walk_legs() pass is the single
                                  authority that scales DISPLAY minutes. Default
                                  1.0 = no-op for tests and direct callers.
        departure_time:           Chicago wall-clock datetime the query is
                                  planned for. None → datetime.now(CHICAGO_TZ).
                                  Resolves to one of five service-period graph
                                  variants (BUG-051): weekday_peak,
                                  weekday_midday, weekday_evening, weekend, owl.
                                  Trips that don't operate in the chosen period
                                  are absent from the variant — a 03:00 query
                                  cannot board a line whose service ended at
                                  01:30, because that line's edges are not in
                                  the owl variant. See _select_period().

    Returns:
        RoutingResult with `.routes` sorted by total time (transit + walk, no
        wait) and `.status` one of:
            "ok"               — routes (possibly empty after filtering) computed.
            "out_of_coverage"  — origin and/or destination > _MAX_RADIUS_MILES
                                 from any CTA train station. `.side` is
                                 "origin" / "destination" / "both".
            "no_path"          — both boundaries resolved but Yen's produced
                                 no accepted itinerary.
    """
    period_name = _select_period(departure_time)
    G_base, stations = _build_graph(period_name)

    # Origin stations (nearest train stations with walk times already computed).
    # If the caller passed an empty list (no stations within 0.5 miles per
    # resolve_location), or passed None, search directly — expanding the
    # radius in 0.25-mile increments up to 2.0 miles when needed (e.g. the
    # user is in a neighbourhood that is more than 0.5 miles from the nearest
    # station).
    if not origin_stations:
        for _r in _RADIUS_RINGS:
            origin_stations = find_nearest_train_stations(
                origin_lat, origin_lon, max_distance_miles=_r
            )
            if origin_stations:
                break

    # Destination stations (walk direction: station → destination).
    # Same progressive-expansion logic: prefer the closest station but don't
    # fail just because the destination is slightly over 0.5 miles from the
    # nearest platform.
    dest_stations: list[dict] = []
    for _r in _RADIUS_RINGS:
        dest_stations = find_nearest_train_stations(
            dest_lat, dest_lon, walk_to_station=False, max_distance_miles=_r
        )
        if dest_stations:
            break

    if not origin_stations or not dest_stations:
        # BUG-047: distinguish "out of CTA coverage" from "no path found" so the
        # API can surface a helpful user-facing explanation instead of an
        # unexplained blank result.
        if not origin_stations and not dest_stations:
            side = "both"
        elif not origin_stations:
            side = "origin"
        else:
            side = "destination"
        return RoutingResult(
            routes=[],
            status="out_of_coverage",
            side=side,
            max_radius_searched=_MAX_RADIUS_MILES,
        )

    # Feature H: drop candidate stations that add no new transit lines vs.
    # a closer same-line station — eliminates near-duplicate routes.
    origin_stations = _dedup_stations_by_line(G_base, origin_stations)
    dest_stations   = _dedup_stations_by_line(G_base, dest_stations)

    # Walk-time lookups for path→route conversion.
    # dest_walk is already computed by find_nearest_train_stations(walk_to_station=False)
    # using the same street_walk_minutes function — no need to recompute here.
    origin_walk = {s["mapid"]: s.get("walk_minutes", 0.0) for s in origin_stations}
    dest_walk   = {s["mapid"]: s.get("walk_minutes", 0.0) for s in dest_stations}

    # Reuse bus stops resolve_location() already produced when available; fall
    # back to a fresh query for direct callers (tests, etc.). Computed before
    # the routing lock so concurrent threads don't serialize on this work.
    if origin_bus_stops is None:
        origin_bus_stops = find_nearest_bus_stops(origin_lat, origin_lon)
    if dest_bus_stops is None:
        dest_bus_stops = find_nearest_bus_stops(dest_lat, dest_lon)

    # Mutate the shared cached graph under a lock instead of copying it per
    # thread. ORIGIN/DEST and their incident walk edges are added before the
    # path search and torn down in the finally block, so G_base is always left
    # in its pristine state for the next caller.
    G = G_base
    ORIGIN = "__ORIGIN__"
    DEST   = "__DEST__"

    routes: list[Route] = []
    with _routing_lock:
        G.add_node(ORIGIN)
        G.add_node(DEST)

        try:
            for s in origin_stations:
                mapid = s["mapid"]
                if mapid in stations:
                    G.add_edge(ORIGIN, mapid,
                               weight=s.get("walk_minutes", 0.0),
                               edge_type="walk", route_id="walk", line="walk")

            for s in dest_stations:
                mapid = s["mapid"]
                if mapid in stations:
                    # walk_minutes from this station → dest already stored in dest_walk
                    # by find_nearest_train_stations(walk_to_station=False); reuse it.
                    G.add_edge(mapid, DEST,
                               weight=dest_walk.get(mapid, 0.0),
                               edge_type="walk", route_id="walk", line="walk")

            # Feature B: virtual walk edges to/from nearby bus stops so Dijkstra
            # can discover intermodal paths that start or end at a bus stop.
            for stop in origin_bus_stops:
                sid = stop["stop_id"]
                if sid in G.nodes:
                    G.add_edge(ORIGIN, sid,
                               weight=stop["walk_minutes"], edge_type="walk",
                               route_id="walk", mode="walk")

            for stop in dest_bus_stops:
                sid = stop["stop_id"]
                if sid in G.nodes:
                    G.add_edge(sid, DEST,
                               weight=stop["walk_minutes"], edge_type="walk",
                               route_id="walk", mode="walk")

            # BUG-045: when effective_speed < 1.0 (bad weather), derate every
            # walk-type edge weight by 1/effective_speed during route SELECTION.
            # Covers both virtual ORIGIN/DEST walk edges (added above) and the
            # cached intermodal train↔bus walk edges (built once at startup).
            # Stored edge weights are not mutated — the callback is per-request.
            if effective_speed and effective_speed < 1.0:
                walk_weight_multiplier = 1.0 / effective_speed

                def _weight_fn(u, v, edge_data):
                    w = edge_data.get("weight", 0.0)
                    if edge_data.get("edge_type") == "walk":
                        return w * walk_weight_multiplier
                    return w

                weight_arg = _weight_fn
            else:
                weight_arg = "weight"

            try:
                path_gen = nx.shortest_simple_paths(G, ORIGIN, DEST, weight=weight_arg)
                # Diversity filter: Yen's algorithm naturally surfaces many
                # near-duplicate paths that differ only in their first walk leg
                # (ORIGIN has multiple low-weight walk edges to nearby stations
                # and bus stops). Skip any path whose transit core — the ordered
                # tuple of (line_code, from_mapid, to_mapid) per TransitLeg —
                # already appears in our accepted set, so the n_routes slots
                # capture genuinely distinct itineraries.
                seen_signatures: set[tuple] = set()
                # Cap iterations so we don't run Yen's forever in the rare case
                # where every candidate collides with an existing signature.
                max_path_iterations = max(n_routes * 8, 25)
                iterations = 0
                # Wall-clock deadline (BUG-049 chunk 1) — protects against a
                # hung Yen's iteration holding _routing_lock indefinitely.
                deadline = (
                    time.monotonic() + _YEN_DEADLINE_S
                    if _YEN_DEADLINE_S > 0
                    else None
                )
                for path in path_gen:
                    iterations += 1
                    if iterations > max_path_iterations:
                        break
                    if len(routes) >= n_routes:
                        break
                    if deadline is not None and time.monotonic() > deadline:
                        print(
                            f"[transit_graph] Yen's deadline ({_YEN_DEADLINE_S}s) "
                            f"reached after {iterations} iterations; "
                            f"returning {len(routes)} partial route(s)."
                        )
                        break
                    route = _path_to_route(
                        path, G, stations, origin_walk, dest_walk,
                        origin_lat, origin_lon, dest_lat, dest_lon,
                    )
                    if route is None:
                        continue
                    if route.transfers > _MAX_TRANSFERS:
                        continue
                    signature = tuple(
                        (leg.line_code, leg.from_mapid, leg.to_mapid)
                        for leg in route.legs
                        if isinstance(leg, TransitLeg)
                    )
                    # Walk-only routes have an empty signature; allow only one.
                    if signature in seen_signatures:
                        continue
                    seen_signatures.add(signature)
                    routes.append(route)
            except nx.NetworkXNoPath:
                pass
            except Exception as exc:
                print(f"[transit_graph] Route finding error: {exc}")
        finally:
            # Always remove virtual nodes so the next caller sees a clean graph,
            # even if routing raised. remove_nodes_from also drops their edges.
            G.remove_nodes_from([ORIGIN, DEST])

    # BUG-047: both boundaries resolved but Yen's produced nothing usable —
    # surface a "no_path" status so callers can distinguish this from
    # "out_of_coverage" above. The empty-routes case still returns status="ok"
    # for callers that pre-resolved stations and got a real (empty) answer back
    # from Yen's; only the truly unreachable case carries no_path.
    if not routes:
        return RoutingResult(
            routes=[],
            status="no_path",
            side=None,
            max_radius_searched=_MAX_RADIUS_MILES,
        )
    return RoutingResult(routes=routes, status="ok")


# ---------------------------------------------------------------------------
# Bus stop spatial grid index (Chunk 1 — Feature C)
# ---------------------------------------------------------------------------
#
# _bus_stop_grid: SpatialGrid keyed by stop_id strings.
#   Cell size 0.005° ≈ 0.34 miles lat / 0.27 miles lon at Chicago's latitude.
#   A 0.25-mile radius query touches at most a 3×3 cell window.
#
# _bus_stop_coords: stop_id → (lat, lon) for direct coordinate lookups by ID
#   (e.g. computing haversine to a specific stop without a grid query).
#
# Both are populated once at module import via _build_bus_stop_grid().

_BUS_STOP_CELL_DEG: float = 0.005  # degrees; ~0.34 miles lat, ~0.27 miles lon

_bus_stop_grid:   SpatialGrid | None           = None
_bus_stop_coords: dict[str, tuple[float, float]] = {}


def _build_bus_stop_grid() -> None:
    """Populate _bus_stop_grid and _bus_stop_coords from stops.txt at module load."""
    global _bus_stop_grid, _bus_stop_coords
    stops = _load_bus_stop_lookup()
    grid = SpatialGrid(cell_lat_deg=_BUS_STOP_CELL_DEG, cell_lon_deg=_BUS_STOP_CELL_DEG)
    coords: dict[str, tuple[float, float]] = {}
    for sid, meta in stops.items():
        lat, lon = meta["lat"], meta["lon"]
        coords[sid] = (lat, lon)
        grid.add(lat, lon, sid)
    _bus_stop_grid   = grid
    _bus_stop_coords = coords
    print(f"[transit_graph] Bus stop grid built: {len(coords)} stops, {grid.cell_count} cells")


_build_bus_stop_grid()


# ---------------------------------------------------------------------------
# Station exit data (Feature A)
# ---------------------------------------------------------------------------
#
# _station_exits: mapid -> [{label, lat, lon}, ...]
#
# Loaded once at module import from station_exits.json.  Returns {} gracefully
# if the file is absent so the server still starts without exit data.

_station_exits: dict[str, list[dict]] = {}


def _load_station_exits() -> dict[str, list[dict]]:
    """
    Read station_exits.json and return {mapid: [{label, lat, lon}, ...]}.
    Returns {} if the file does not exist (server still starts without it).
    """
    import json as _json
    exits_file = Path(__file__).parent / "station_exits.json"
    if not exits_file.exists():
        print("[transit_graph] station_exits.json not found -- exit guidance disabled")
        return {}
    try:
        with open(exits_file, encoding="utf-8") as f:
            data = _json.load(f)
        total = sum(len(v) for v in data.values())
        print(f"[transit_graph] Station exits loaded: {total} exits across {len(data)} stations")
        return data
    except Exception as exc:  # noqa: BLE001
        print(f"[transit_graph] Warning: could not load station_exits.json: {exc}")
        return {}


_station_exits = _load_station_exits()


def get_station_exits(mapid: str) -> list[dict]:
    """Return the list of known exits for a train parent station, or [] if none."""
    return _station_exits.get(mapid, [])


def best_exit(mapid: str, dest_lat: float, dest_lon: float) -> dict | None:
    """
    Return the exit dict for *mapid* that minimises the street-network walk
    time to (dest_lat, dest_lon), or None if no exits are known for the station.

    The returned dict is a copy of the station_exits entry with an added
    ``walk_minutes`` key.  ``street_walk_minutes`` is lru_cache'd, so repeated
    calls with the same coords are free.
    """
    exits = get_station_exits(mapid)
    if not exits:
        return None
    best: dict | None = None
    best_minutes = float("inf")
    for ex in exits:
        minutes = street_walk_minutes(ex["lat"], ex["lon"], dest_lat, dest_lon)
        if minutes < best_minutes:
            best_minutes = minutes
            best = ex
    if best is None:
        return None
    return {**best, "walk_minutes": best_minutes}


def _stops_near(lat: float, lon: float, radius_miles: float = 0.25) -> list[str]:
    """
    Return stop_ids within radius_miles of (lat, lon).

    Uses SpatialGrid for bounding-box prefilter + Haversine postfilter.
    Not cached — lat/lon float keys would produce unbounded cache growth.
    """
    return [sid for _, sid in _bus_stop_grid.query(lat, lon, radius_miles)]


# ---------------------------------------------------------------------------
# Stop-to-routes index (Chunk 2 — Feature C)
# ---------------------------------------------------------------------------
#
# _stop_to_routes: stop_id → [(short_name, direction_id, idx_in_seq, arr_min), ...]
#
# Built once during warm_up() after get_bus_stop_sequences() is available.
# Enables O(1) lookup of "which routes serve stop X?".

_stop_to_routes: dict[str, list[tuple[str, str, int, float]]] = {}


def _build_stop_to_routes() -> None:
    """
    Invert get_bus_stop_sequences() into _stop_to_routes.
    Called from warm_up() after get_bus_stop_sequences().
    """
    global _stop_to_routes
    index: dict[str, list[tuple[str, str, int, float]]] = {}
    for (short_name, did), stops in get_bus_stop_sequences().items():
        for idx, (stop_id, _name, _lat, _lon, arr_min) in enumerate(stops):
            index.setdefault(stop_id, []).append((short_name, did, idx, arr_min))
    _stop_to_routes = index
    total_entries = sum(len(v) for v in index.values())
    print(f"[transit_graph] Stop-to-routes index built: {total_entries} (stop, route) entries "
          f"across {len(index)} stops")


def get_stop_sequence_position(stop_id: str, route_id: str) -> tuple[int, int]:
    """
    Return (position_0based, total_stops) for stop_id on route_id.

    For trains (stop_id >= 40000): looks up _train_stop_pos, tries both
    direction_ids and returns the first match.
    For buses: looks up _stop_to_routes and resolves total from _bus_seq_cache.
    Falls back to (1, 2) — the legacy no-op value — when the stop is unknown.
    """
    if stop_id.isdigit() and int(stop_id) >= 40000:
        for did in ("0", "1"):
            entry = _train_stop_pos.get((stop_id, route_id, did))
            if entry:
                return entry
        return (1, 2)
    for short_name, did, idx, _ in _stop_to_routes.get(stop_id, []):
        if short_name == route_id:
            total = len((_bus_seq_cache or {}).get((short_name, did), []))
            if total > 0:
                return (idx, total)
    return (1, 2)


# ---------------------------------------------------------------------------
# Bus-to-bus transfer routing (Chunk 3 — Feature C)
# ---------------------------------------------------------------------------

def _select_transfer_candidates(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    bus_arrivals: list[dict],
    origin_bus_stops: list[dict],
    sequences: dict,
) -> tuple[dict, dict]:
    """
    Pass 1: spatial / haversine-only candidate selection.

    For each live arrival at a nearby boarding stop, scans forward on route A
    to find transfer stops Sk with forward progress toward the destination,
    then checks whether any route B from a nearby stop T exits within 0.5 mi
    of the destination.  Candidates are deduplicated by (rA, Sk, T, rB, exitB)
    identity and capped at 3 per arrival+route-A combination.

    Returns:
        candidate_map  — {(route_A_key, sk_idx, t_stop_id, route_B_key, exit_B_idx):
                           (score, board_walk_min, wait_min_A, board_stop_id)}
        board_index    — {stop_id: [(short_name, did, idx_in_seq), ...]}
                         (needed by Pass 2 to resolve the boarding stop index)
    """
    board_walk: dict[str, float] = {
        s["stop_id"]: s.get("walk_minutes", 0.0)
        for s in origin_bus_stops
    }
    boarding_stop_ids = set(board_walk.keys())

    # Build board_index: stop_id → [(short_name, did, idx_in_seq), ...]
    board_index: dict[str, list[tuple[str, str, int]]] = {}
    for (short_name, did), stops in sequences.items():
        for idx, entry in enumerate(stops):
            sid = entry[0]
            if sid in boarding_stop_ids:
                board_index.setdefault(sid, []).append((short_name, did, idx))

    candidate_map: dict[tuple, tuple] = {}

    # Precomputed suffix-minimum arrays per route_B for the innermost best-exit
    # lookup. For each (short_B, did_B), suffix_best[i] = (idx, dist) where dist
    # is the minimum haversine distance to the destination over all stops j >= i
    # along that route, and idx is the j that achieves it. Built once per route
    # per call (O(len(seq))) — replaces the prior O(len(seq)) scan repeated for
    # every (route_B, t_idx) pair the outer loop encountered.
    _suffix_best: dict[tuple[str, str], list[tuple[int, float]] | None] = {}

    def _get_suffix_best(rB_key: tuple[str, str]) -> list[tuple[int, float]] | None:
        cached = _suffix_best.get(rB_key, ...)
        if cached is not ...:
            return cached  # type: ignore[return-value]
        seq = sequences.get(rB_key)
        if seq is None:
            _suffix_best[rB_key] = None
            return None
        n = len(seq)
        arr: list[tuple[int, float]] = [(-1, float("inf"))] * n
        best_idx = -1
        best_dist = float("inf")
        for i in range(n - 1, -1, -1):
            _, _, elat, elon, _ = seq[i]
            d = _haversine_miles(elat, elon, dest_lat, dest_lon)
            if d < best_dist:
                best_dist = d
                best_idx = i
            arr[i] = (best_idx, best_dist)
        _suffix_best[rB_key] = arr
        return arr

    for arrival in bus_arrivals:
        stop_id   = arrival.get("stop_id", "")
        route_num = arrival.get("route", "")
        wait_min  = arrival.get("arrives_in_minutes", 0)

        if not stop_id or stop_id not in board_index:
            continue

        cands_A = [e for e in board_index[stop_id] if e[0] == route_num]
        if not cands_A:
            continue

        board_walk_min = board_walk.get(stop_id, 0.0)
        if stop_id in _bus_stop_coords:
            board_lat, board_lon = _bus_stop_coords[stop_id]
        else:
            board_lat, board_lon = origin_lat, origin_lon
        boarding_hav = _haversine_miles(board_lat, board_lon, dest_lat, dest_lon)

        for short_A, did_A, board_idx in cands_A:
            seq_A = sequences[(short_A, did_A)]
            route_A_key = (short_A, did_A)

            arrival_candidates: list[tuple] = []

            for sk_idx in range(board_idx + 1, len(seq_A)):
                sk_sid, sk_name, sk_lat, sk_lon, _ = seq_A[sk_idx]

                # Forward-progress filter: Sk must be ≥10% closer to dest than boarding
                sk_hav = _haversine_miles(sk_lat, sk_lon, dest_lat, dest_lon)
                if sk_hav >= boarding_hav * _FWD_PROGRESS_RATIO:
                    continue

                nearby = _stops_near(sk_lat, sk_lon, _MAX_TRANSFER_WALK)
                if not nearby:
                    continue

                for t_stop_id in nearby:
                    routes_at_T = _stop_to_routes.get(t_stop_id, [])
                    for short_B, did_B, t_idx, _ in routes_at_T:
                        if (short_B, did_B) == route_A_key:
                            continue

                        sb = _get_suffix_best((short_B, did_B))
                        if sb is None:
                            continue
                        next_idx = t_idx + 1
                        if next_idx >= len(sb):
                            continue
                        best_exit_idx, best_exit_dist = sb[next_idx]
                        if best_exit_idx < 0 or best_exit_dist > _MAX_EXIT_DIST:
                            continue

                        transfer_hav = _haversine_miles(sk_lat, sk_lon,
                                                        *_bus_stop_coords.get(t_stop_id, (sk_lat, sk_lon)))
                        score = (board_walk_min + wait_min
                                 + transfer_hav * _TRANSFER_SCORE_WALK_FACTOR
                                 + best_exit_dist * _TRANSFER_SCORE_WALK_FACTOR)

                        arrival_candidates.append((
                            score,
                            route_A_key, sk_idx, t_stop_id,
                            (short_B, did_B), best_exit_idx,
                            board_walk_min, wait_min, stop_id,
                        ))

            arrival_candidates.sort(key=lambda x: x[0])
            for cand in arrival_candidates[:_MAX_CANDIDATES_PER_ARRIVAL]:
                score, rA, sk_i, t_sid, rB, exit_i, bwm, wm, bsid = cand
                key = (rA, sk_i, t_sid, rB, exit_i)
                existing = candidate_map.get(key)
                if existing is None or score < existing[0]:
                    candidate_map[key] = (score, bwm, wm, bsid)

    return candidate_map, board_index


def _build_transfer_routes(
    candidate_map: dict,
    board_index: dict,
    bus_arrivals: list[dict],
    sequences: dict,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    n_routes: int,
    *,
    effective_speed: float = 1.0,
) -> list[tuple[float, int, object]]:
    """
    Pass 2: build Route objects for the candidates returned by Pass 1.

    Performs all OSMnx street-walk calls, assembles WalkLeg / TransitLeg
    objects, and applies the 90-minute trip cap.  Returns up to n_routes
    results sorted by (in-vehicle + walk + live wait for A + leg-2
    estimated wait estimated as TRANSFER_PENALTY_MINUTES).

    BUG-045: when effective_speed < 1.0 (bad weather), walk components of the
    sort key and 90-min cap are scaled by 1/effective_speed so that bus+bus
    candidate ranking reflects the rider's actual walking pace. WalkLeg.minutes
    on the returned Route objects remain baseline so the caller's
    _scale_walk_legs() pass is the single authority that scales display.

    BUG-050: the sort key and the 90-min cap both run through
    compute_route_total() so the per-transfer wait fallback stays in lockstep
    with _rank_routes / _apply_transfer_wait_estimates in main.py.
    """
    _MAX_TRIP_MINUTES = 90.0
    walk_factor = (1.0 / effective_speed) if effective_speed and effective_speed < 1.0 else 1.0

    ranked: list[tuple[float, int, object]] = []

    for (route_A_key, sk_idx, t_stop_id, route_B_key, exit_B_idx), \
        (score, board_walk_min, wait_min_A, board_stop_id) in candidate_map.items():

        short_A, did_A = route_A_key
        short_B, did_B = route_B_key
        seq_A = sequences[(short_A, did_A)]
        seq_B = sequences[(short_B, did_B)]

        board_idx = next(
            (e[2] for e in board_index.get(board_stop_id, [])
             if (e[0], e[1]) == route_A_key),
            None,
        )
        if board_idx is None:
            continue

        board_sid, board_name, board_lat, board_lon, board_arr = seq_A[board_idx]
        sk_sid,    sk_name,    sk_lat,    sk_lon,    sk_arr    = seq_A[sk_idx]
        t_meta = _bus_stop_coords.get(t_stop_id)
        if not t_meta or not isinstance(t_meta, tuple) or len(t_meta) != 2:
            continue
        t_lat, t_lon = t_meta

        t_idx_in_seq = next(
            (e[2] for e in _stop_to_routes.get(t_stop_id, [])
             if (e[0], e[1]) == route_B_key),
            None,
        )
        if t_idx_in_seq is None:
            continue
        t_sid_check, t_name, t_lat_s, t_lon_s, t_arr = seq_B[t_idx_in_seq]

        exit_sid, exit_name, exit_lat, exit_lon, exit_arr = seq_B[exit_B_idx]

        in_vehicle_A = sk_arr - board_arr
        if in_vehicle_A < 0:
            in_vehicle_A += 24 * 60
        if in_vehicle_A <= 0:
            continue

        in_vehicle_B = exit_arr - t_arr
        if in_vehicle_B < 0:
            in_vehicle_B += 24 * 60
        if in_vehicle_B <= 0:
            continue

        same_stop = (sk_sid == t_stop_id)
        if same_stop:
            transfer_walk_min = 0.0
            transfer_path     = []
            transfer_dirs     = []
        else:
            tw_min, transfer_dirs, transfer_path = street_walk_all(sk_lat, sk_lon, t_lat_s, t_lon_s)
            transfer_walk_min = max(tw_min, _TRANSFER_MINUTES)  # apply minimum transfer penalty

        exit_walk_min = street_walk_minutes(exit_lat, exit_lon, dest_lat, dest_lon)

        # Pre-flight 90-minute cap. Walks are weather-derated via walk_factor
        # (BUG-045) and the leg-2 fallback comes from compute_route_total
        # (BUG-050) so the cap matches what the user will eventually see.
        cap_pretotal = (
            board_walk_min * walk_factor
            + in_vehicle_A
            + transfer_walk_min * walk_factor
            + in_vehicle_B
            + exit_walk_min * walk_factor
            + wait_min_A
            + TRANSFER_PENALTY_MINUTES  # leg-2 fallback (same as compute_route_total)
        )
        if cap_pretotal > _MAX_TRIP_MINUTES:
            continue

        direction_A = next(
            (a.get("direction", short_A)
             for a in bus_arrivals
             if a.get("stop_id") == board_stop_id and a.get("route") == short_A),
            short_A,
        )
        direction_B = short_B   # no live arrival for leg B; use route number as fallback

        _bw_m, board_dirs, board_path = street_walk_all(origin_lat, origin_lon, board_lat, board_lon)
        _ex_m, exit_dirs, exit_path   = street_walk_all(exit_lat, exit_lon, dest_lat, dest_lon)
        legs = [
            WalkLeg(
                from_name="Your location",
                to_name=board_name,
                minutes=round(board_walk_min, 1),
                path_points=board_path,
                directions=board_dirs,
            ),
            TransitLeg(
                line=direction_A,
                line_code=short_A,
                from_station=board_name,
                from_mapid=board_sid,
                to_station=sk_name,
                to_mapid=sk_sid,
                minutes=round(in_vehicle_A, 1),
                shape_points=clip_shape(get_shape(short_A, did_A), board_lat, board_lon, sk_lat, sk_lon),
            ),
            WalkLeg(
                from_name=sk_name,
                to_name=t_name,
                minutes=round(transfer_walk_min, 1),
                path_points=transfer_path,
                directions=transfer_dirs,
            ),
            TransitLeg(
                line=direction_B,
                line_code=short_B,
                from_station=t_name,
                from_mapid=t_stop_id,
                to_station=exit_name,
                to_mapid=exit_sid,
                minutes=round(in_vehicle_B, 1),
                shape_points=clip_shape(get_shape(short_B, did_B), t_lat_s, t_lon_s, exit_lat, exit_lon),
            ),
            WalkLeg(
                from_name=exit_name,
                to_name="Your destination",
                minutes=round(exit_walk_min, 1),
                path_points=exit_path,
                directions=exit_dirs,
            ),
        ]

        route = Route(
            legs=legs,
            transit_minutes=round(in_vehicle_A + in_vehicle_B, 1),
            walk_minutes_total=round(board_walk_min + transfer_walk_min + exit_walk_min, 1),
            transfers=1,
            first_transit_leg_index=1,  # always Walk[0], Transit[1], Walk[2], Transit[3], Walk[4]
        )
        sort_key = compute_route_total(route, wait_min_A, walk_factor=walk_factor)
        ranked.append((sort_key, wait_min_A, route))

    ranked.sort(key=lambda x: x[0])
    return ranked[:n_routes]


def find_bus_transfer_routes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    bus_arrivals: list[dict],      # from cta_client.get_bus_arrivals(); must include stop_id
    origin_bus_stops: list[dict],  # from gtfs_loader.find_nearest_bus_stops(); includes walk_minutes
    n_routes: int = 3,
    effective_speed: float = 1.0,  # BUG-045: weather × user walk-speed factor (<=1.0 derates walks during selection)
) -> list[tuple[float, int, object]]:
    """
    Find bus+bus transfer routes from origin to destination.

    Called unconditionally from main.py whenever transit_mode is "Bus" or
    "All" and live bus arrival data is available. Direct bus-only paths come
    from the unified graph via find_routes(); this function surfaces the
    bus+bus transfer itineraries (bus A → walk → bus B) that the graph does
    not model, since bus-to-bus walk transfers are not represented as graph
    edges.

    Builds 5-leg routes of the form:
        WalkLeg  (origin → boarding_stop_A)
        TransitLeg (route A: boarding_stop_A → transfer_stop_Sk)
        WalkLeg  (Sk → transfer_boarding_stop_T)   ← minutes=0 if same stop
        TransitLeg (route B: T → exit_stop_B)
        WalkLeg  (exit_stop_B → destination)

    Sorting key includes a fixed TRANSFER_PENALTY_MINUTES (3-min) estimate for
    the leg-2 wait. This matches the per-transfer fallback that
    _apply_transfer_wait_estimates() in main.py later subtracts and re-adds
    (replacing the estimate with the live wait when available), so bus+bus
    routes stay comparable to train/intermodal routes. The estimate is NOT
    added to route.walk_minutes_total or route.transit_minutes — those fields
    retain their strict definitions.

    Returns:
        list of (total_minutes, wait_minutes_A, Route) sorted by total_minutes.
        wait_minutes_A is the live wait for route A. Empty list if no
        transfer routes are found.
    """
    sequences = get_bus_stop_sequences()
    if not sequences or not bus_arrivals or not origin_bus_stops or not _stop_to_routes:
        return []
    candidate_map, board_index = _select_transfer_candidates(
        origin_lat, origin_lon, dest_lat, dest_lon, bus_arrivals, origin_bus_stops, sequences,
    )
    if not candidate_map:
        return []
    return _build_transfer_routes(
        candidate_map, board_index, bus_arrivals, sequences,
        origin_lat, origin_lon, dest_lat, dest_lon, n_routes,
        effective_speed=effective_speed,
    )


# ---------------------------------------------------------------------------
# CLI test — run directly to verify graph build and routing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print("=== CTA Transit Graph — smoke test ===\n")

    # Test: Wrigleyville → Loop
    origin_lat,  origin_lon  = 41.9476, -87.6542   # Wrigleyville / Addison
    dest_lat,    dest_lon    = 41.8827, -87.6326   # The Loop

    print(f"Finding routes from Wrigleyville ({origin_lat}, {origin_lon})")
    print(f"        to The Loop ({dest_lat}, {dest_lon})\n")

    routes = find_routes(origin_lat, origin_lon, dest_lat, dest_lon, n_routes=3)

    if not routes:
        print("No routes found — check that GTFS data is downloaded and graph built correctly.")
        sys.exit(1)

    for i, r in enumerate(routes, 1):
        print(f"Route {i}: {r.summary()}")
        print(f"  Legs:")
        for leg in r.legs:
            if isinstance(leg, WalkLeg):
                print(f"    Walk  {leg.from_name} -> {leg.to_name}  ({leg.minutes:.1f} min)")
            else:
                print(f"    {leg.line:12s}  {leg.from_station} -> {leg.to_station}  ({leg.minutes:.1f} min)")
        print()
