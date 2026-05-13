"""
Builds the static schedule index used by FEAT-018 (Published CTA schedule viewer).

Reads ``backend/gtfs_data/`` and emits one JSON file per route into
``backend/schedule_data/``. The backend's ``/schedule/{route_id}`` endpoint
streams these files unmodified; the frontend's three-step Schedules picker
walks the JSON to render route → direction → stop → timetable.

------------------------------------------------------------------------------
JSON SHAPE
------------------------------------------------------------------------------

Per-route file (``backend/schedule_data/<route_id>.json``)::

    {
      "route_id":         "Red",
      "route_short_name": "Red",
      "route_long_name":  "Red Line",
      "route_color":      "c60c30",
      "route_type":       "1",            # GTFS route_type as a string
      "category":         "train",        # see "ROUTE-CATEGORY RULE" below
      "directions": [
        {
          "direction_id": "0",
          "headsign":     "95th/Dan Ryan",
          "stops": [
            {
              "stop_id":  "30173",
              "name":     "Howard",
              "lat":      42.019063,
              "lon":      -87.672892,
              "sequence": 1,
              "times": {
                "weekday":  ["04:30", "04:50", ...],
                "saturday": ["05:00", ...],
                "sunday":   ["05:30", ...]
              }
            },
            ...
          ]
        },
        ...
      ]
    }

Times are ``"HH:MM"`` strings in service-local time, sorted ascending per
service-day bucket. Times past midnight (GTFS ``"24:xx"`` / ``"25:xx"``) are
normalised back into the 00–23 range so the frontend can render them as
hour-grouped entries on the *next* service day's tab; this matches how riders
read printed CTA timetables (the 1:15 a.m. Red Line train shows up under the
Saturday-night "1 a.m." hour group, not the Sunday-morning one). See
``_normalise_hhmm`` for the exact rule.

Picker manifest (``backend/schedule_data/_manifest.json``) is also written so
the ``/schedule/routes`` endpoint can answer the picker query without parsing
every per-route file::

    {
      "routes": [
        {"route_id": "Red", "short_name": "Red", "long_name": "Red Line",
         "color": "c60c30", "category": "train"},
        {"route_id": "22",  "short_name": "22",  "long_name": "Clark",
         "color": "414145", "category": "bus_frequent"},
        ...
      ],
      "stop_routes": {
        "30173": ["Red", "Pink", "22", ...],
        ...
      },
      "generated_at": "2026-05-12T...",
      "gtfs_calendar_start": "20260320",
      "gtfs_calendar_end":   "20260531"
    }

The ``stop_routes`` reverse index powers FEAT-018 Decision 10 (the "View
schedule" affordance on saved-stop cards pre-highlights the stop's serving
routes in the step-1 picker).

------------------------------------------------------------------------------
SERVICE-DAY BUCKET RULES
------------------------------------------------------------------------------

For each ``service_id`` in ``calendar.txt``, we derive a bucket in
``{"weekday", "saturday", "sunday"}`` from the day flags:

  * Mon–Fri columns all == 1 → ``"weekday"``
  * Saturday == 1            → ``"saturday"``
  * Sunday   == 1            → ``"sunday"``

A service_id can land in more than one bucket (e.g. a service that runs
Sat+Sun is added to both saturday and sunday). Mixed-day services (e.g. one
weekday-only column == 1) fall through to whichever single-day flag is set;
this is rare in CTA's feed and is logged.

``calendar_dates.txt`` overrides are applied as follows: any
``exception_type=1`` (added service) row whose date is a CTA-Sunday-service
holiday (federal holidays where CTA explicitly runs Sunday schedule — list
below) folds the row's service_id into the ``"sunday"`` bucket. This is the
"holiday folds into Sunday" rule from Decision 7 of FEAT-018. We do NOT try
to handle ``exception_type=2`` (removed service) date-by-date; the bucket is
the union, and the frontend's day-tab UI only ever shows the current bucket.

CTA-Sunday-service holidays (per transitchicago.com service notices):
New Year's Day, Memorial Day, Independence Day, Labor Day, Thanksgiving,
Christmas Day. We match by month/day so the rule survives year rollover.

------------------------------------------------------------------------------
ROUTE-CATEGORY RULE
------------------------------------------------------------------------------

The picker categorises each route by its CTA ``route_type`` and (for buses)
its GTFS ``route_color`` — CTA's own taxonomy, per FEAT-018 Decision 8.

  * ``route_type == "1"`` (subway/elevated rail) → ``"train"``
  * ``route_type == "3"`` (bus):
      - ``route_color == "b71234"`` → ``"bus_express"``     (17 routes)
      - ``route_color == "414145"`` → ``"bus_frequent"``    (19 routes)
      - anything else                → ``"bus_regular"``    (~86 routes)

The two hex literals above are CTA's published taxonomy; they are stable
across GTFS refreshes (CTA has used them since the 2012 route-color rollout).
If CTA changes the taxonomy, edit ``_BUS_EXPRESS_COLOR`` /
``_BUS_FREQUENT_COLOR`` below — categories are derived at build time, not
hard-coded per route.

------------------------------------------------------------------------------
USAGE
------------------------------------------------------------------------------

    python scripts/build_schedule_index.py

Runs in well under 2 minutes on the maintainer's machine against the
committed GTFS bundle. Emits per-route JSON + manifest into
``backend/schedule_data/``. Re-run after every ``backend/fetch_gtfs.py``
refresh.
"""

from __future__ import annotations

import csv
import datetime
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
GTFS_DIR = REPO_ROOT / "backend" / "gtfs_data"
OUT_DIR = REPO_ROOT / "backend" / "schedule_data"

# Make backend importable so we can reuse LINE_NAMES (canonical 8-line dict).
sys.path.insert(0, str(REPO_ROOT / "backend"))
from cta_client import LINE_NAMES  # noqa: E402

# Route-color taxonomy — see "ROUTE-CATEGORY RULE" header block.
_BUS_EXPRESS_COLOR = "b71234"
_BUS_FREQUENT_COLOR = "414145"

# CTA-Sunday-service holidays as (month, day) pairs.
_SUNDAY_SERVICE_HOLIDAYS: set[tuple[int, int]] = {
    (1, 1),    # New Year's Day
    (7, 4),    # Independence Day
    (12, 25),  # Christmas Day
}
# Floating-date holidays where CTA runs Sunday service. We resolve these per
# year by matching weekday + ordinal-in-month rather than a static (m, d) set.
# (Memorial Day = last Mon in May; Labor Day = first Mon in Sep;
#  Thanksgiving = fourth Thu in Nov.)
_FLOATING_SUNDAY_HOLIDAYS = (
    ("last_monday", 5),       # Memorial Day
    ("first_monday", 9),      # Labor Day
    ("fourth_thursday", 11),  # Thanksgiving
)


def _is_sunday_service_holiday(d: datetime.date) -> bool:
    if (d.month, d.day) in _SUNDAY_SERVICE_HOLIDAYS:
        return True
    for rule, month in _FLOATING_SUNDAY_HOLIDAYS:
        if d.month != month:
            continue
        if rule == "first_monday" and d.weekday() == 0 and d.day <= 7:
            return True
        if rule == "fourth_thursday" and d.weekday() == 3 and 22 <= d.day <= 28:
            return True
        if rule == "last_monday":
            # Last Monday: weekday is Monday AND adding 7 days would overflow month.
            if d.weekday() == 0:
                next_week = d + datetime.timedelta(days=7)
                if next_week.month != d.month:
                    return True
    return False


def _normalise_hhmm(time_str: str) -> str | None:
    """GTFS ``HH:MM:SS`` (where HH may be 24+) → canonical ``HH:MM`` in 0–23.

    GTFS allows times past midnight (24:15 = 12:15 a.m. *next* service day).
    The frontend renders hour-grouped lists; we collapse 24+ back into 0–23
    so the 1:15 a.m. trip lands under the "1 a.m." hour bucket on the same
    service day's tab (which matches how printed CTA timetables read).
    Returns None on malformed input.
    """
    parts = time_str.strip().split(":")
    if len(parts) < 2:
        return None
    try:
        h = int(parts[0])
        m = int(parts[1])
    except ValueError:
        return None
    h_norm = h % 24
    return f"{h_norm:02d}:{m:02d}"


def _classify_route(route_type: str, route_color: str) -> str:
    """Apply the FEAT-018 Decision-8 category rule. See header for taxonomy."""
    if route_type == "1":
        return "train"
    if route_type == "3":
        c = (route_color or "").strip().lower()
        if c == _BUS_EXPRESS_COLOR:
            return "bus_express"
        if c == _BUS_FREQUENT_COLOR:
            return "bus_frequent"
        return "bus_regular"
    # route_type "2" (rail), "0" (light rail), etc. — CTA's feed currently
    # only emits 1 (L) and 3 (bus), but classify defensively.
    return "other"


def _load_routes() -> dict[str, dict]:
    """Return ``{route_id: {short, long, color, type, category}}``."""
    routes: dict[str, dict] = {}
    with open(GTFS_DIR / "routes.txt", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rid = row["route_id"].strip()
            rtype = row.get("route_type", "").strip()
            color = row.get("route_color", "").strip().lower()
            short = row.get("route_short_name", "").strip()
            long_name = row.get("route_long_name", "").strip()
            # Train lines get human-friendly long names from cta_client.LINE_NAMES
            # when present; otherwise fall back to GTFS values.
            if rtype == "1" and rid in LINE_NAMES:
                long_name = LINE_NAMES[rid]
            routes[rid] = {
                "short": short,
                "long": long_name,
                "color": color,
                "type": rtype,
                "category": _classify_route(rtype, color),
            }
    return routes


def _load_service_buckets() -> tuple[dict[str, set[str]], str, str]:
    """Map each service_id to the set of buckets it serves.

    Returns ``(service_to_buckets, calendar_start, calendar_end)``.

    Buckets: subset of {"weekday", "saturday", "sunday"}.
    """
    svc_to_buckets: dict[str, set[str]] = defaultdict(set)
    start_str, end_str = "", ""
    cal_file = GTFS_DIR / "calendar.txt"
    if cal_file.exists():
        with open(cal_file, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                sid = row["service_id"].strip()
                weekday_flags = [row.get(d, "0").strip() == "1"
                                 for d in ("monday", "tuesday", "wednesday",
                                           "thursday", "friday")]
                if all(weekday_flags):
                    svc_to_buckets[sid].add("weekday")
                if row.get("saturday", "0").strip() == "1":
                    svc_to_buckets[sid].add("saturday")
                if row.get("sunday", "0").strip() == "1":
                    svc_to_buckets[sid].add("sunday")
                s = row.get("start_date", "").strip()
                e = row.get("end_date", "").strip()
                if s and (not start_str or s < start_str):
                    start_str = s
                if e and (not end_str or e > end_str):
                    end_str = e

    # Holiday override: any service added (exception_type=1) on a
    # CTA-Sunday-service holiday folds into the Sunday bucket.
    cal_dates_file = GTFS_DIR / "calendar_dates.txt"
    if cal_dates_file.exists():
        with open(cal_dates_file, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("exception_type", "").strip() != "1":
                    continue
                sid = row.get("service_id", "").strip()
                date_str = row.get("date", "").strip()
                if len(date_str) != 8:
                    continue
                try:
                    d = datetime.date(int(date_str[:4]),
                                      int(date_str[4:6]),
                                      int(date_str[6:8]))
                except ValueError:
                    continue
                if _is_sunday_service_holiday(d):
                    svc_to_buckets[sid].add("sunday")

    return svc_to_buckets, start_str, end_str


def _load_stops() -> dict[str, dict]:
    """Return ``{stop_id: {name, lat, lon}}``."""
    stops: dict[str, dict] = {}
    with open(GTFS_DIR / "stops.txt", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sid = row.get("stop_id", "").strip()
            if not sid:
                continue
            try:
                lat = float(row.get("stop_lat", "") or 0.0)
                lon = float(row.get("stop_lon", "") or 0.0)
            except ValueError:
                lat, lon = 0.0, 0.0
            stops[sid] = {
                "name": (row.get("stop_name", "") or "").strip(),
                "lat": lat,
                "lon": lon,
                "parent_station": (row.get("parent_station", "") or "").strip(),
            }
    return stops


def _load_trips(routes: dict[str, dict]) -> dict[str, dict]:
    """Return ``{trip_id: {route_id, direction_id, service_id, headsign}}``.

    Only emits trips for routes we recognise (defensive — GTFS shouldn't
    reference unknown routes but tolerating it costs nothing).
    """
    trips: dict[str, dict] = {}
    with open(GTFS_DIR / "trips.txt", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        # CTA's trips.txt uses "direction" for the human headsign (e.g.
        # "North", "South"); fall back to "trip_headsign" if a future feed
        # rev switches to standard GTFS field names.
        for row in reader:
            tid = row.get("trip_id", "").strip()
            rid = row.get("route_id", "").strip()
            if not tid or rid not in routes:
                continue
            trips[tid] = {
                "route_id": rid,
                "direction_id": row.get("direction_id", "0").strip(),
                "service_id": row.get("service_id", "").strip(),
                "headsign": (row.get("trip_headsign") or row.get("direction") or "").strip(),
            }
    return trips


def _build_per_route_schedules(
    routes: dict[str, dict],
    trips: dict[str, dict],
    stops: dict[str, dict],
    svc_to_buckets: dict[str, set[str]],
) -> tuple[dict[str, dict], dict[str, set[str]]]:
    """Stream stop_times.txt and assemble the per-route schedule structures.

    Returns ``(route_schedules, stop_routes)`` where:
      * route_schedules[rid] = the fully-built JSON-shaped dict.
      * stop_routes[stop_id] = set of route_ids that serve the stop.
    """
    # Per-direction stop ordering: keyed (rid, dir_id, stop_id) → sequence.
    # We take the *first* sequence we see for a (rid, dir_id, stop_id) tuple,
    # which is fine for CTA's feed where stop ordering is stable per direction.
    stop_seq: dict[tuple[str, str, str], int] = {}
    # Headsigns: (rid, dir_id) → headsign (first non-empty wins).
    headsigns: dict[tuple[str, str], str] = {}
    # Times: (rid, dir_id, stop_id, bucket) → list of "HH:MM"
    times: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    # Reverse index for picker pre-highlight (Decision 10).
    stop_routes: dict[str, set[str]] = defaultdict(set)

    print(f"[build_schedule_index] streaming stop_times.txt ...")
    t0 = time.time()
    rows_read = 0
    with open(GTFS_DIR / "stop_times.txt", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_read += 1
            tid = row.get("trip_id", "").strip()
            trip = trips.get(tid)
            if not trip:
                continue
            rid = trip["route_id"]
            dir_id = trip["direction_id"]
            sid = trip["service_id"]
            buckets = svc_to_buckets.get(sid)
            if not buckets:
                continue

            stop_id = row.get("stop_id", "").strip()
            if not stop_id:
                continue

            dep = (row.get("departure_time") or row.get("arrival_time") or "").strip()
            hhmm = _normalise_hhmm(dep)
            if hhmm is None:
                continue

            try:
                seq = int((row.get("stop_sequence") or "0").strip())
            except ValueError:
                seq = 0

            key3 = (rid, dir_id, stop_id)
            prev_seq = stop_seq.get(key3)
            if prev_seq is None or seq < prev_seq:
                stop_seq[key3] = seq

            # Headsign: prefer stop_headsign on the first stop of a trip if present;
            # otherwise use the trip-level headsign captured in _load_trips.
            if (rid, dir_id) not in headsigns:
                hs = (row.get("stop_headsign") or "").strip() or trip["headsign"]
                if hs:
                    headsigns[(rid, dir_id)] = hs

            stop_routes[stop_id].add(rid)
            for b in buckets:
                times[(rid, dir_id, stop_id, b)].append(hhmm)

    print(f"[build_schedule_index] streamed {rows_read:,} rows in {time.time()-t0:.1f}s")

    # Now assemble per-route JSON.
    print("[build_schedule_index] assembling per-route JSON ...")
    # Group keys by (rid, dir_id, stop_id) for time-bucket aggregation.
    grouped: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for (rid, dir_id, stop_id, bucket), tlist in times.items():
        entry = grouped[(rid, dir_id)].get(stop_id)
        if entry is None:
            entry = {"weekday": [], "saturday": [], "sunday": []}
            grouped[(rid, dir_id)][stop_id] = entry
        entry[bucket] = tlist

    route_schedules: dict[str, dict] = {}
    for rid, meta in routes.items():
        directions: list[dict] = []
        # Find all directions for this route by scanning grouped keys.
        dir_keys = sorted({d for (r, d) in grouped.keys() if r == rid})
        for dir_id in dir_keys:
            stops_map = grouped.get((rid, dir_id), {})
            ordered_stop_ids = sorted(
                stops_map.keys(),
                key=lambda s: (stop_seq.get((rid, dir_id, s), 0), s),
            )
            stop_entries = []
            for sid in ordered_stop_ids:
                stop_meta = stops.get(sid, {})
                bucket_times = stops_map[sid]
                # Sort + dedupe per bucket.
                clean = {
                    "weekday": sorted(set(bucket_times["weekday"])),
                    "saturday": sorted(set(bucket_times["saturday"])),
                    "sunday": sorted(set(bucket_times["sunday"])),
                }
                stop_entries.append({
                    "stop_id": sid,
                    "name": stop_meta.get("name", ""),
                    "lat": stop_meta.get("lat", 0.0),
                    "lon": stop_meta.get("lon", 0.0),
                    "sequence": stop_seq.get((rid, dir_id, sid), 0),
                    "times": clean,
                })
            directions.append({
                "direction_id": dir_id,
                "headsign": headsigns.get((rid, dir_id), ""),
                "stops": stop_entries,
            })

        if not directions:
            # Route has no scheduled trips in the current feed window — skip
            # emitting an empty file so /schedule/<route_id> 404s cleanly.
            continue

        route_schedules[rid] = {
            "route_id": rid,
            "route_short_name": meta["short"],
            "route_long_name": meta["long"],
            "route_color": meta["color"],
            "route_type": meta["type"],
            "category": meta["category"],
            "directions": directions,
        }

    return route_schedules, stop_routes


def _safe_route_id(rid: str) -> str:
    """Return a filename-safe rendering of ``rid`` (filesystem-portable)."""
    return "".join(c if (c.isalnum() or c in ("_", "-")) else "_" for c in rid)


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[build_schedule_index] loading routes / calendar / stops / trips ...")
    t0 = time.time()
    routes = _load_routes()
    svc_to_buckets, cal_start, cal_end = _load_service_buckets()
    stops = _load_stops()
    trips = _load_trips(routes)
    print(f"[build_schedule_index]   routes={len(routes)} trips={len(trips):,} "
          f"stops={len(stops):,} services={len(svc_to_buckets)} "
          f"({time.time()-t0:.1f}s)")

    route_schedules, stop_routes = _build_per_route_schedules(
        routes, trips, stops, svc_to_buckets,
    )

    # Write per-route files.
    written = 0
    total_bytes = 0
    for rid, payload in route_schedules.items():
        out_path = OUT_DIR / f"{_safe_route_id(rid)}.json"
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        out_path.write_text(data, encoding="utf-8")
        written += 1
        total_bytes += len(data.encode("utf-8"))

    # Write manifest.
    manifest_routes = []
    for rid, meta in routes.items():
        if rid not in route_schedules:
            continue
        manifest_routes.append({
            "route_id": rid,
            "short_name": meta["short"],
            "long_name": meta["long"],
            "color": meta["color"],
            "category": meta["category"],
        })
    # Stable ordering: trains first (alphabetical by short_name), then buses.
    _cat_order = {"train": 0, "bus_frequent": 1, "bus_express": 2,
                  "bus_regular": 3, "other": 4}
    manifest_routes.sort(key=lambda r: (_cat_order.get(r["category"], 9),
                                        r["short_name"]))

    manifest = {
        "routes": manifest_routes,
        "stop_routes": {sid: sorted(rids) for sid, rids in stop_routes.items()},
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "gtfs_calendar_start": cal_start,
        "gtfs_calendar_end": cal_end,
    }
    (OUT_DIR / "_manifest.json").write_text(
        json.dumps(manifest, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[build_schedule_index] wrote {written} route files "
          f"({total_bytes/1_000_000:.1f} MB) + manifest into {OUT_DIR}")
    print(f"[build_schedule_index] done in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    build()
