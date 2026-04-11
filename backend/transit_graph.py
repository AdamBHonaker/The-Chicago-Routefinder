"""
Transit graph builder and route finder for the CTA train network.

Builds a NetworkX directed weighted graph from CTA GTFS static data.

Nodes:  train parent stations (mapids 40000–49999)
Edges:
  - Transit:  consecutive stops on the same trip; weight = scheduled minutes
  - Transfer: inter-station transfer points (from transfers.txt); weight = 2 min

The graph is built once and cached for the lifetime of the process.

stop_times.txt is 5.8 M rows / 354 MB.  We stream it in one pass, collecting
rows only for one representative trip per (route_id, direction_id).  It is
never loaded fully into memory.
"""

import csv
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import networkx as nx

from gtfs_loader import GTFS_DIR, _haversine_miles, find_nearest_train_stations
from walking import (
    walk_minutes as street_walk_minutes,
    walk_path as street_walk_path,
    walk_directions as street_walk_directions,
)

# ---------------------------------------------------------------------------
# CTA line metadata
# ---------------------------------------------------------------------------

LINE_NAMES = {
    "Red":  "Red Line",
    "Blue": "Blue Line",
    "Brn":  "Brown Line",
    "G":    "Green Line",
    "Org":  "Orange Line",
    "P":    "Purple Line",
    "Pink": "Pink Line",
    "Y":    "Yellow Line",
}

# Default transfer time at a station when switching lines (minutes)
_TRANSFER_MINUTES = 2.0

# Pre-computed shape lookup: (route_id, direction_id) -> [[lat, lon], ...]
# Populated once during warm_up() by _build_shape_lookup(); read-only after that.
_shape_lookup: dict[tuple[str, str], list[list[float]]] = {}

# Maximum plausible scheduled leg time; longer values are treated as GTFS noise
_MAX_LEG_MINUTES = 45.0

# Target departure time for representative trip selection: noon = 720 min past midnight
_TARGET_NOON_MINUTES = 720.0

# Thread-local storage for per-thread graph copies used by find_routes().
# Each executor thread in the FastAPI thread pool keeps its own copy of G_base
# so routing requests can run concurrently without copying the graph on every
# call. The copy is created once per thread (lazily on first request) and reused
# for all subsequent requests on that thread.
_thread_local: threading.local = threading.local()


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
    leg_type: str = "walk"


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


@dataclass
class Route:
    legs: list = field(default_factory=list)   # list[WalkLeg | TransitLeg]
    transit_minutes: float = 0.0               # in-vehicle time only
    walk_minutes_total: float = 0.0            # sum of all walk legs
    transfers: int = 0                         # number of line changes

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
# GTFS small-file loaders
# ---------------------------------------------------------------------------

def _load_parent_stations() -> dict[str, dict]:
    """
    Returns {mapid: {name, lat, lon}} for all train parent stations.
    These are the 40000-range location_type=1 entries in stops.txt.
    """
    stations: dict[str, dict] = {}
    with open(GTFS_DIR / "stops.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                sid = int(row["stop_id"].strip())
            except ValueError:
                continue
            if 40000 <= sid <= 49999 and row.get("location_type", "").strip() == "1":
                stations[str(sid)] = {
                    "name": row.get("stop_name", "").strip(),
                    "lat":  float(row["stop_lat"].strip()),
                    "lon":  float(row["stop_lon"].strip()),
                }
    return stations


def _load_platform_to_parent() -> dict[str, str]:
    """
    Returns {platform_stop_id: parent_mapid} for train platform stops (30000–39999).
    Relies on the parent_station column in stops.txt (confirmed present in CTA GTFS).
    """
    mapping: dict[str, str] = {}
    with open(GTFS_DIR / "stops.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                sid = int(row["stop_id"].strip())
            except ValueError:
                continue
            if 30000 <= sid <= 39999:
                parent = row.get("parent_station", "").strip()
                if parent:
                    mapping[str(sid)] = parent
    return mapping


def _load_train_route_ids() -> set[str]:
    """Returns the set of route_ids for rail routes (route_type=1)."""
    ids: set[str] = set()
    with open(GTFS_DIR / "routes.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("route_type", "").strip() == "1":
                ids.add(row["route_id"].strip())
    return ids


def _load_weekday_service_ids() -> set[str]:
    """Returns service_ids active on weekdays (Mon–Fri) from calendar.txt."""
    ids: set[str] = set()
    cal_file = GTFS_DIR / "calendar.txt"
    if not cal_file.exists():
        return ids
    with open(cal_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if all(row.get(d, "0").strip() == "1"
                   for d in ("monday", "tuesday", "wednesday", "thursday", "friday")):
                ids.add(row["service_id"].strip())
    return ids


def _load_representative_trips(train_route_ids: set[str]) -> tuple[dict[str, str], dict[str, str]]:
    """
    Returns (trip_route, trip_direction) where each dict maps trip_id to its
    route_id or direction_id respectively.  All weekday candidate trips are
    returned (potentially many per line/direction); _stream_stop_sequences uses
    first-stop arrival times to pick the one closest to noon per direction.
    Falls back to all trips if calendar.txt is absent or yields nothing.
    """
    weekday_sids = _load_weekday_service_ids()

    trip_route: dict[str, str] = {}   # {trip_id: route_id}
    trip_dir:   dict[str, str] = {}   # {trip_id: direction_id}

    def _read_trips(service_filter: set[str]) -> None:
        with open(GTFS_DIR / "trips.txt", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                rid = row.get("route_id", "").strip()
                if rid not in train_route_ids:
                    continue
                if service_filter and row.get("service_id", "").strip() not in service_filter:
                    continue
                tid = row["trip_id"].strip()
                trip_route[tid] = rid
                trip_dir[tid]   = row.get("direction_id", "0").strip()

    _read_trips(weekday_sids)
    if not trip_route:          # calendar.txt absent or no matches — use all trips
        _read_trips(set())

    n_dirs = len({(r, trip_dir[t]) for t, r in trip_route.items()})
    print(f"[transit_graph] Loaded {len(trip_route)} weekday candidate trips "
          f"across {n_dirs} line/direction pairs")
    return trip_route, trip_dir


def _parse_gtfs_time(t: str) -> float:
    """GTFS HH:MM:SS → minutes since midnight. Handles times past 24:00."""
    parts = t.strip().split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    return h * 60.0 + m + s / 60.0


def _stream_stop_sequences(
    candidate_trips: dict[str, str],   # {trip_id: route_id} — all weekday candidates
    trip_direction:  dict[str, str],   # {trip_id: direction_id}
    platform_to_parent: dict[str, str],
) -> dict[str, list[tuple[str, float]]]:
    """
    Stream stop_times.txt once, collecting ordered (parent_mapid, arrival_min)
    sequences for all candidate trip IDs.  After streaming, one trip per
    (route_id, direction_id) is selected — the one whose first-stop departure
    is closest to noon — giving representative midday in-vehicle times.

    stop_times.txt is 5.8 M rows; this function reads the whole file once and
    keeps only a few thousand rows across all candidates.

    Returns {trip_id: [(mapid, arrival_minutes), ...]} for the selected trips only.
    """
    raw: dict[str, list] = {tid: [] for tid in candidate_trips}

    print("[transit_graph] Streaming stop_times.txt …")
    t0 = time.time()
    rows_read = 0

    with open(GTFS_DIR / "stop_times.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows_read += 1
            tid = row.get("trip_id", "").strip()
            if tid not in raw:
                continue

            sid = row.get("stop_id", "").strip()
            parent = platform_to_parent.get(sid)
            if not parent:
                continue

            arr_str = (row.get("arrival_time") or row.get("departure_time") or "").strip()
            if not arr_str:
                continue

            try:
                seq     = int(row.get("stop_sequence", "0").strip())
                arr_min = _parse_gtfs_time(arr_str)
            except (ValueError, IndexError):
                continue

            raw[tid].append((seq, parent, arr_min))

    elapsed = time.time() - t0
    print(f"[transit_graph] Streamed {rows_read:,} rows in {elapsed:.1f}s")

    # Sort each trip's stops and record first-stop departure time
    sorted_raw: dict[str, list] = {}
    first_arrival: dict[str, float] = {}
    for tid, rows in raw.items():
        if not rows:
            continue
        rows.sort(key=lambda x: x[0])
        sorted_raw[tid] = rows
        first_arrival[tid] = rows[0][2]   # arrival_min of stop_sequence=min

    # For each (route_id, direction_id) group, pick the trip closest to noon
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for tid in sorted_raw:
        rid = candidate_trips[tid]
        did = trip_direction.get(tid, "0")
        groups[(rid, did)].append(tid)

    selected: dict[str, list[tuple[str, float]]] = {}
    for (rid, did), tids in groups.items():
        best = min(tids, key=lambda t: abs(first_arrival.get(t, 0.0) - _TARGET_NOON_MINUTES))
        selected[best] = [(mapid, arr_min) for _, mapid, arr_min in sorted_raw[best]]

    print(f"[transit_graph] Selected {len(selected)} representative trips "
          f"({len(groups)} line/direction pairs, targeting noon departures)")
    return selected


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

            # transfers.txt has no min_transfer_time — use our default
            try:
                min_sec = float(row.get("min_transfer_time", "").strip() or "0")
                minutes = max(min_sec / 60.0, _TRANSFER_MINUTES)
            except ValueError:
                minutes = _TRANSFER_MINUTES

            edges.append((from_p, to_p, minutes))
    return edges


# ---------------------------------------------------------------------------
# Graph builder — cached for process lifetime
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _build_graph() -> tuple[nx.DiGraph, dict[str, dict]]:
    """
    Build and cache the transit graph.

    Returns (G, parent_stations) where:
      G               — nx.DiGraph with mapid nodes and weighted edges
      parent_stations — {mapid: {name, lat, lon}}
    """
    print("[transit_graph] Building CTA transit graph …")
    t0 = time.time()

    parent_stations    = _load_parent_stations()
    platform_to_parent = _load_platform_to_parent()
    train_route_ids    = _load_train_route_ids()
    selected_trips, trip_dirs = _load_representative_trips(train_route_ids)
    stop_seqs          = _stream_stop_sequences(selected_trips, trip_dirs, platform_to_parent)

    G = nx.DiGraph()

    # Add all parent station nodes with metadata
    for mapid, meta in parent_stations.items():
        G.add_node(mapid, **meta)

    # Build transit edges from stop sequences
    # edge_candidates[(from, to)] = list of (route_id, line_name, minutes)
    edge_candidates: dict[tuple[str, str], list] = {}

    for trip_id, seq in stop_seqs.items():
        route_id  = selected_trips[trip_id]
        dir_id    = trip_dirs.get(trip_id, "0")
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

            key = (from_mapid, to_mapid)
            edge_candidates.setdefault(key, []).append((route_id, dir_id, line_name, leg_min))

    transit_edge_count = 0
    for (from_mapid, to_mapid), candidates in edge_candidates.items():
        # Keep the fastest route for the edge weight; store all serving lines
        best_route, best_dir, best_line, best_min = min(candidates, key=lambda x: x[3])
        G.add_edge(
            from_mapid, to_mapid,
            weight=best_min,
            route_id=best_route,
            direction_id=best_dir,
            line=best_line,
            all_routes=candidates,
            edge_type="transit",
        )
        transit_edge_count += 1

    # Add transfer edges from transfers.txt (bidirectional)
    transfer_edges = _load_transfer_edges(platform_to_parent, parent_stations)
    transfer_edge_count = 0
    for from_mapid, to_mapid, minutes in transfer_edges:
        for a, b in [(from_mapid, to_mapid), (to_mapid, from_mapid)]:
            if not G.has_edge(a, b):
                G.add_edge(a, b, weight=minutes, route_id="transfer",
                           line="transfer", edge_type="transfer")
                transfer_edge_count += 1

    print(
        f"[transit_graph] Graph ready: {G.number_of_nodes()} stations, "
        f"{transit_edge_count} transit edges, {transfer_edge_count} transfer edges "
        f"({time.time() - t0:.1f}s)"
    )
    return G, parent_stations


def warm_up() -> None:
    """
    Trigger graph construction and bus stop sequence loading at startup
    so the first user request is fast.
    Call this from the FastAPI lifespan or startup event.
    """
    _build_graph()
    get_bus_stop_sequences()
    _build_shape_lookup()


# ---------------------------------------------------------------------------
# GTFS shape lookup — pre-computed at startup
# ---------------------------------------------------------------------------

def _build_shape_lookup() -> None:
    """
    Populate _shape_lookup at startup.

    Step 1: Stream shapes.txt → {shape_id: [(seq, lat, lon), ...]}
            Sort each shape by shape_pt_sequence, then convert to [[lat, lon], ...].
    Step 2: Read trips.txt → {(route_id, direction_id): shape_id}
            First shape_id encountered per pair is used (all trips on the same
            route/direction use the same shape in CTA GTFS).
    Step 3: Join → _shape_lookup[(route_id, direction_id)] = [[lat, lon], ...]

    shapes.txt is read via csv.DictReader (streaming); it is never loaded fully
    into memory as a string.  The intermediate per-shape point lists are
    discarded once the sorted coordinate arrays are built.
    """
    global _shape_lookup

    shapes_file = GTFS_DIR / "shapes.txt"
    if not shapes_file.exists():
        print("[transit_graph] shapes.txt not found — shape lookup unavailable")
        return

    print("[transit_graph] Building shape lookup from GTFS …")
    t0 = time.time()

    # --- Step 1: shapes.txt → shape_id → sorted [[lat, lon], ...] ---
    raw_pts: dict[str, list[tuple[int, float, float]]] = defaultdict(list)

    with open(shapes_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            shape_id = row.get("shape_id", "").strip()
            if not shape_id:
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

    print(f"[transit_graph] Loaded {len(shapes)} shapes from shapes.txt")

    # --- Step 2: trips.txt → (route_id, direction_id) → shape_id ---
    route_dir_to_shape: dict[tuple[str, str], str] = {}

    with open(GTFS_DIR / "trips.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            route_id     = row.get("route_id",     "").strip()
            direction_id = row.get("direction_id", "0").strip()
            shape_id     = row.get("shape_id",     "").strip()
            if not route_id or not shape_id:
                continue
            key = (route_id, direction_id)
            if key not in route_dir_to_shape:
                route_dir_to_shape[key] = shape_id

    # --- Step 3: join ---
    # Also load route_short_name → route_id mapping so bus routes can be found
    # by short_name (e.g. "22") as well as route_id.  For most CTA bus routes
    # these are identical, but keying by both ensures correctness if they ever
    # diverge.  find_bus_routes() calls get_shape(route_short_name, direction_id).
    route_short_names: dict[str, str] = {}  # {route_id: route_short_name}
    with open(GTFS_DIR / "routes.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rid   = row.get("route_id",          "").strip()
            short = row.get("route_short_name",  "").strip()
            if rid and short:
                route_short_names[rid] = short

    new_lookup: dict[tuple[str, str], list[list[float]]] = {}
    for (route_id, direction_id), shape_id in route_dir_to_shape.items():
        coords = shapes.get(shape_id)
        if coords:
            new_lookup[(route_id, direction_id)] = coords
            # Add alias by route_short_name when it differs from route_id
            short = route_short_names.get(route_id, "")
            if short and short != route_id:
                new_lookup.setdefault((short, direction_id), coords)

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


def get_station_by_name(name: str) -> tuple[float, float] | None:
    """
    Return (lat, lon) for a train parent station by stop_name (case-insensitive
    exact match, then contains-match fallback). Used to resolve CTA destNm
    terminal names like 'Howard' or '95th/Dan Ryan' to coordinates.
    Returns None if no match found.
    """
    _, stations = _build_graph()
    name_lower = name.lower().strip()
    # Exact match first
    for s in stations.values():
        if s["name"].lower() == name_lower:
            return (s["lat"], s["lon"])
    # Contains-match fallback (e.g. "O'Hare" vs "O'Hare Airport")
    for s in stations.values():
        if name_lower in s["name"].lower() or s["name"].lower() in name_lower:
            return (s["lat"], s["lon"])
    return None


def get_shape(route_id: str, direction_id: str) -> list[list[float]] | None:
    """
    Return the pre-computed GTFS shape for a (route_id, direction_id) pair.

    Returns [[lat, lon], ...] in shape_pt_sequence order, or None if no shape
    is available (e.g. shapes.txt absent or route not found).
    """
    return _shape_lookup.get((route_id, direction_id))


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
    then returns the slice between those two indices inclusive.

    Falls back to a straight line [[board_lat, board_lon], [exit_lat, exit_lon]]
    if shape_points is None or empty.
    """
    if not shape_points:
        return [[board_lat, board_lon], [exit_lat, exit_lon]]

    def _nearest_idx(lat: float, lon: float) -> int:
        best_idx  = 0
        best_dist = float("inf")
        for i, (pt_lat, pt_lon) in enumerate(shape_points):
            d = (pt_lat - lat) ** 2 + (pt_lon - lon) ** 2
            if d < best_dist:
                best_dist = d
                best_idx  = i
        return best_idx

    board_idx = _nearest_idx(board_lat, board_lon)
    exit_idx  = _nearest_idx(exit_lat,  exit_lon)

    lo = min(board_idx, exit_idx)
    hi = max(board_idx, exit_idx)
    return shape_points[lo : hi + 1]


# ---------------------------------------------------------------------------
# Bus stop sequence table — cached for process lifetime
# ---------------------------------------------------------------------------

def _load_bus_route_map() -> dict[str, str]:
    """Returns {route_id: route_short_name} for all bus routes (route_type != 1)."""
    mapping: dict[str, str] = {}
    with open(GTFS_DIR / "routes.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("route_type", "").strip() == "1":
                continue  # skip rail
            rid   = row.get("route_id", "").strip()
            short = row.get("route_short_name", "").strip() or rid
            if rid:
                mapping[rid] = short
    return mapping


def _load_bus_stop_lookup() -> dict[str, dict]:
    """Returns {stop_id: {name, lat, lon}} for all bus stops (IDs 0–29999)."""
    stops: dict[str, dict] = {}
    with open(GTFS_DIR / "stops.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                sid = int(row["stop_id"].strip())
                lat = float(row["stop_lat"].strip())
                lon = float(row["stop_lon"].strip())
            except (ValueError, KeyError):
                continue
            if 0 <= sid <= 29999:
                stops[str(sid)] = {
                    "name": row.get("stop_name", "").strip(),
                    "lat":  lat,
                    "lon":  lon,
                }
    return stops


def _load_bus_candidate_trips(
    bus_route_ids: set[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """
    Returns (trip_route, trip_direction) for all weekday bus candidate trips.
    Same pattern as _load_representative_trips() for trains.
    Falls back to all trips if calendar.txt is absent or yields nothing.
    """
    weekday_sids = _load_weekday_service_ids()

    trip_route: dict[str, str] = {}
    trip_dir:   dict[str, str] = {}

    def _read_trips(service_filter: set[str]) -> None:
        with open(GTFS_DIR / "trips.txt", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                rid = row.get("route_id", "").strip()
                if rid not in bus_route_ids:
                    continue
                if service_filter and row.get("service_id", "").strip() not in service_filter:
                    continue
                tid = row["trip_id"].strip()
                trip_route[tid] = rid
                trip_dir[tid]   = row.get("direction_id", "0").strip()

    _read_trips(weekday_sids)
    if not trip_route:
        _read_trips(set())

    n_dirs = len({(r, trip_dir[t]) for t, r in trip_route.items()})
    print(f"[transit_graph] Loaded {len(trip_route)} weekday bus candidate trips "
          f"across {n_dirs} route/direction pairs")
    return trip_route, trip_dir


@lru_cache(maxsize=1)
def get_bus_stop_sequences() -> dict[tuple[str, str], list[tuple]]:
    """
    Build and cache the bus stop sequence table.

    Streams stop_times.txt once (a second dedicated pass after train graph build),
    collects sequences for all weekday bus candidate trips, then selects the one
    per route/direction whose first-stop departure is closest to noon — the same
    midday-targeting strategy used for train representative trips.

    Returns:
        {(route_short_name, direction_id): [
            (stop_id, stop_name, lat, lon, arr_minutes), ...
        ]}
        Sequences are ordered by stop_sequence. arr_minutes is minutes since
        midnight for the representative midday trip.
    """
    print("[transit_graph] Building bus stop sequence table …")
    t0 = time.time()

    bus_route_map  = _load_bus_route_map()                        # {route_id: route_short_name}
    bus_stop_lookup = _load_bus_stop_lookup()                      # {stop_id: {name, lat, lon}}
    trip_route, trip_dir = _load_bus_candidate_trips(
        set(bus_route_map.keys())
    )

    # Stream stop_times.txt, collecting sequences for all candidate bus trips
    raw: dict[str, list] = {tid: [] for tid in trip_route}

    print("[transit_graph] Streaming stop_times.txt for bus sequences …")
    t1 = time.time()
    rows_read = 0

    with open(GTFS_DIR / "stop_times.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows_read += 1
            tid = row.get("trip_id", "").strip()
            if tid not in raw:
                continue

            sid = row.get("stop_id", "").strip()
            if sid not in bus_stop_lookup:
                continue

            arr_str = (row.get("arrival_time") or row.get("departure_time") or "").strip()
            if not arr_str:
                continue

            try:
                seq     = int(row.get("stop_sequence", "0").strip())
                arr_min = _parse_gtfs_time(arr_str)
            except (ValueError, IndexError):
                continue

            raw[tid].append((seq, sid, arr_min))

    print(f"[transit_graph] Bus stream: {rows_read:,} rows in {time.time() - t1:.1f}s")

    # Sort each trip's stops and record first-stop departure time
    sorted_raw: dict[str, list] = {}
    first_arrival: dict[str, float] = {}
    for tid, rows in raw.items():
        if not rows:
            continue
        rows.sort(key=lambda x: x[0])
        sorted_raw[tid] = rows
        first_arrival[tid] = rows[0][2]

    # Group by (route_id, direction_id), pick the trip closest to noon
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for tid in sorted_raw:
        rid = trip_route[tid]
        did = trip_dir.get(tid, "0")
        groups[(rid, did)].append(tid)

    result: dict[tuple[str, str], list[tuple]] = {}
    for (rid, did), tids in groups.items():
        best      = min(tids, key=lambda t: abs(first_arrival.get(t, 0.0) - _TARGET_NOON_MINUTES))
        short     = bus_route_map.get(rid, rid)
        seq_entries: list[tuple] = []
        for _, sid, arr_min in sorted_raw[best]:
            meta = bus_stop_lookup.get(sid, {})
            seq_entries.append((
                sid,
                meta.get("name", sid),
                meta.get("lat",  0.0),
                meta.get("lon",  0.0),
                arr_min,
            ))
        result[(short, did)] = seq_entries

    n_routes = len({k[0] for k in result})
    print(
        f"[transit_graph] Bus stop sequences ready: {len(result)} route/direction pairs "
        f"across {n_routes} routes ({time.time() - t0:.1f}s total)"
    )
    return result


# ---------------------------------------------------------------------------
# Path → Route conversion
# ---------------------------------------------------------------------------

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

        # ── Walk from user location to first boarding station ──────────────
        if from_node == ORIGIN:
            to_meta  = stations.get(to_node, {})
            walk_min = origin_walk_lookup.get(to_node, weight)
            to_lat   = to_meta.get("lat", origin_lat)
            to_lon   = to_meta.get("lon", origin_lon)
            legs.append(WalkLeg(
                from_name="Your location",
                to_name=to_meta.get("name", to_node),
                minutes=walk_min,
                path_points=street_walk_path(origin_lat, origin_lon, to_lat, to_lon),
                directions=street_walk_directions(origin_lat, origin_lon, to_lat, to_lon),
            ))
            walk_total += walk_min
            idx += 1
            continue

        # ── Walk from last alighting station to destination ────────────────
        if to_node == DEST:
            from_meta = stations.get(from_node, {})
            walk_min  = dest_walk_lookup.get(from_node, weight)
            from_lat  = from_meta.get("lat", dest_lat)
            from_lon  = from_meta.get("lon", dest_lon)
            legs.append(WalkLeg(
                from_name=from_meta.get("name", from_node),
                to_name="Your destination",
                minutes=walk_min,
                path_points=street_walk_path(from_lat, from_lon, dest_lat, dest_lon),
                directions=street_walk_directions(from_lat, from_lon, dest_lat, dest_lon),
            ))
            walk_total += walk_min
            idx += 1
            continue

        # ── Inter-station transfer walk ────────────────────────────────────
        if edge_type == "transfer":
            from_meta = stations.get(from_node, {})
            to_meta   = stations.get(to_node,   {})
            flat = from_meta.get("lat", 0.0)
            flon = from_meta.get("lon", 0.0)
            tlat = to_meta.get("lat",  0.0)
            tlon = to_meta.get("lon",  0.0)
            legs.append(WalkLeg(
                from_name=from_meta.get("name", from_node),
                to_name=to_meta.get("name", to_node),
                minutes=weight,
                path_points=street_walk_path(flat, flon, tlat, tlon),
                directions=street_walk_directions(flat, flon, tlat, tlon),
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

        look = idx + 1
        while look < len(path) - 1 and path[look] != DEST:
            next_edge = G.edges[path[look], path[look + 1]]
            if (next_edge.get("route_id") != group_route
                    or next_edge.get("edge_type") != "transit"):
                break
            seg_minutes += next_edge.get("weight", 0.0)
            alight_node  = path[look + 1]
            look += 1

        # Detect same-station line change: if previous leg was transit and
        # ended at the same node where this one starts, insert a transfer walk.
        if legs and isinstance(legs[-1], TransitLeg) and legs[-1].to_mapid == board_node:
            board_meta = stations.get(board_node, {})
            blat = board_meta.get("lat", 0.0)
            blon = board_meta.get("lon", 0.0)
            legs.append(WalkLeg(
                from_name=board_meta.get("name", board_node),
                to_name=board_meta.get("name", board_node),
                minutes=_TRANSFER_MINUTES,
                path_points=[[blat, blon]],
            ))
            walk_total += _TRANSFER_MINUTES

        board_meta  = stations.get(board_node,  {})
        alight_meta = stations.get(alight_node, {})
        legs.append(TransitLeg(
            line=group_line,
            line_code=group_route,
            from_station=board_meta.get("name",  board_node),
            from_mapid=board_node,
            to_station=alight_meta.get("name",   alight_node),
            to_mapid=alight_node,
            minutes=seg_minutes,
            shape_points=clip_shape(
                get_shape(group_route, group_dir),
                board_meta.get("lat", 0.0),  board_meta.get("lon", 0.0),
                alight_meta.get("lat", 0.0), alight_meta.get("lon", 0.0),
            ),
        ))
        transit_total += seg_minutes
        idx = look

    transit_legs = [l for l in legs if isinstance(l, TransitLeg)]
    return Route(
        legs=legs,
        transit_minutes=transit_total,
        walk_minutes_total=walk_total,
        transfers=max(0, len(transit_legs) - 1),
    )


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
) -> list[Route]:
    """
    Find the fastest transit routes from (origin_lat, origin_lon) to
    (dest_lat, dest_lon).

    Args:
        origin_lat / origin_lon:  User's current coordinates
        dest_lat / dest_lon:      Destination coordinates
        origin_stations:          Pre-computed origin stations from gtfs_loader
                                  (pass these in to avoid recomputing walk times)
        n_routes:                 How many route options to return (default 3)

    Returns:
        List of Route objects sorted by total time (transit + walk, no wait).
        Empty list if no path found.
    """
    G_base, stations = _build_graph()

    # Origin stations (nearest train stations with walk times already computed)
    if origin_stations is None:
        origin_stations = find_nearest_train_stations(origin_lat, origin_lon)

    # Destination stations (walk direction: station → destination)
    dest_stations = find_nearest_train_stations(dest_lat, dest_lon, walk_to_station=False)

    if not origin_stations or not dest_stations:
        return []

    # Walk-time lookups for path→route conversion.
    # dest_walk is already computed by find_nearest_train_stations(walk_to_station=False)
    # using the same street_walk_minutes function — no need to recompute here.
    origin_walk = {s["mapid"]: s.get("walk_minutes", 0.0) for s in origin_stations}
    dest_walk   = {s["mapid"]: s.get("walk_minutes", 0.0) for s in dest_stations}

    # Use a thread-local copy of the cached graph to avoid a full deep copy on
    # every request while staying safe under concurrent load. Each executor
    # thread in FastAPI's thread pool gets its own copy (created once, reused
    # across all requests handled by that thread). ORIGIN/DEST virtual nodes are
    # added before routing and removed in the finally block so the copy stays
    # clean for the next request on the same thread.
    if not hasattr(_thread_local, "G") or _thread_local.G_id != id(G_base):
        _thread_local.G    = G_base.copy()
        _thread_local.G_id = id(G_base)
    G = _thread_local.G

    ORIGIN = "__ORIGIN__"
    DEST   = "__DEST__"
    G.add_node(ORIGIN)
    G.add_node(DEST)

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

    routes: list[Route] = []
    try:
        path_gen = nx.shortest_simple_paths(G, ORIGIN, DEST, weight="weight")
        for path in path_gen:
            if len(routes) >= n_routes:
                break
            route = _path_to_route(
                path, G, stations, origin_walk, dest_walk,
                origin_lat, origin_lon, dest_lat, dest_lon,
            )
            if route is not None:
                routes.append(route)
    except nx.NetworkXNoPath:
        pass
    except Exception as exc:
        print(f"[transit_graph] Route finding error: {exc}")
    finally:
        # Clean up virtual nodes so the thread-local graph is reusable
        G.remove_nodes_from([ORIGIN, DEST])

    return routes


def find_bus_routes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    bus_arrivals: list[dict],      # from cta_client.get_bus_arrivals(); must include stop_id
    origin_bus_stops: list[dict],  # from gtfs_loader.find_nearest_bus_stops(); includes walk_minutes
    n_routes: int = 3,
) -> list[tuple[float, int, object]]:
    """
    Find bus routes from origin to destination using live bus arrivals.

    For each live arrival we know the boarding stop (via stop_id) and the wait
    time.  We locate that stop in the GTFS stop sequence for its route, scan
    forward to find the exit stop closest to the destination, then assemble a
    Route from:
        WalkLeg (origin → boarding stop)
        TransitLeg (boarding stop → exit stop)
        WalkLeg (exit stop → destination)

    The boarding stop's direction is resolved by its stop_id — bus stop IDs are
    direction-specific in CTA GTFS, so no direction-string mapping is needed.

    Returns:
        list of (total_minutes, wait_minutes, Route) sorted by total_minutes.
        Same format as _rank_routes() for trains, making main.py merging trivial.
        Empty list if no usable arrivals.
    """
    sequences = get_bus_stop_sequences()

    if not sequences or not bus_arrivals or not origin_bus_stops:
        return []

    # Walk time from origin to each nearby boarding stop
    board_walk: dict[str, float] = {
        s["stop_id"]: s.get("walk_minutes", 0.0)
        for s in origin_bus_stops
    }
    boarding_stop_ids = set(board_walk.keys())

    # Build a reverse index over the sequence table, limited to our boarding
    # stop IDs only (typically 3–5 stops — cheap to build per request).
    # A stop may appear in sequences for both directions of the same route, so
    # we store ALL matching entries as a list instead of overwriting.
    # {stop_id: [(route_short_name, direction_id, index_in_seq), ...]}
    board_index: dict[str, list[tuple[str, str, int]]] = {}
    for (short_name, did), stops in sequences.items():
        for idx, entry in enumerate(stops):
            sid = entry[0]
            if sid in boarding_stop_ids:
                board_index.setdefault(sid, []).append((short_name, did, idx))

    ranked: list[tuple[float, int, object]] = []
    seen_route_dirs: set[tuple[str, str]] = set()   # one result per route+direction

    for arrival in bus_arrivals:
        stop_id   = arrival.get("stop_id", "")
        route_num = arrival.get("route", "")
        direction = arrival.get("direction", "")
        wait_min  = arrival.get("arrives_in_minutes", 0)

        if not stop_id or stop_id not in board_index:
            continue

        # Filter entries to those matching this arrival's route number.
        # If the stop appears in both directions, try each and pick the direction
        # whose sequence leads closest to the destination.
        candidates = [e for e in board_index[stop_id] if e[0] == route_num]
        if not candidates:
            continue

        best_exit_idx  = -1
        best_exit_dist = float("inf")
        best_cand: tuple[str, str, int] | None = None

        for short_name, did, board_idx in candidates:
            route_dir_key = (short_name, did)
            if route_dir_key in seen_route_dirs:
                continue   # already have a result for this route+direction

            seq = sequences[route_dir_key]
            # Scan forward from the boarding stop
            for j in range(board_idx + 1, len(seq)):
                _, _, slat, slon, _ = seq[j]
                dist = _haversine_miles(dest_lat, dest_lon, slat, slon)
                if dist < best_exit_dist:
                    best_exit_dist = dist
                    best_exit_idx  = j
                    best_cand      = (short_name, did, board_idx)

        if best_cand is None or best_exit_idx < 0:
            continue   # boarding at terminus for all candidates, or all seen

        # Skip if the closest reachable stop is still far from the destination.
        # 0.5 miles ~ 10 min walk; beyond that the bus isn't serving this trip.
        if best_exit_dist > 0.5:
            continue

        short_name, did, board_idx = best_cand
        route_dir_key = (short_name, did)
        seen_route_dirs.add(route_dir_key)

        stops = sequences[route_dir_key]
        _, board_name, board_lat, board_lon, board_arr = stops[board_idx]
        exit_sid, exit_name, exit_lat, exit_lon, exit_arr = stops[best_exit_idx]

        board_walk_min = board_walk.get(stop_id, 0.0)

        # In-vehicle scheduled time from GTFS arrival times
        in_vehicle_min = exit_arr - board_arr
        if in_vehicle_min < 0:
            in_vehicle_min += 24 * 60   # handle times past midnight
        if in_vehicle_min <= 0:
            continue

        # Street-network walk time from exit stop to destination (OSMnx)
        exit_walk_min = street_walk_minutes(exit_lat, exit_lon, dest_lat, dest_lon)

        legs = [
            WalkLeg(
                from_name="Your location",
                to_name=board_name,
                minutes=round(board_walk_min, 1),
                path_points=street_walk_path(origin_lat, origin_lon, board_lat, board_lon),
                directions=street_walk_directions(origin_lat, origin_lon, board_lat, board_lon),
            ),
            TransitLeg(
                line=direction,           # direction string used for color lookup in UI
                line_code=route_num,      # route number used for pill label in UI
                from_station=board_name,
                from_mapid=stop_id,
                to_station=exit_name,
                to_mapid=exit_sid,
                minutes=round(in_vehicle_min, 1),
                shape_points=clip_shape(
                    get_shape(short_name, did),
                    board_lat, board_lon, exit_lat, exit_lon,
                ),
            ),
            WalkLeg(
                from_name=exit_name,
                to_name="Your destination",
                minutes=round(exit_walk_min, 1),
                path_points=street_walk_path(exit_lat, exit_lon, dest_lat, dest_lon),
                directions=street_walk_directions(exit_lat, exit_lon, dest_lat, dest_lon),
            ),
        ]

        route = Route(
            legs=legs,
            transit_minutes=round(in_vehicle_min, 1),
            walk_minutes_total=round(board_walk_min + exit_walk_min, 1),
            transfers=0,
        )
        total = route.total_minutes_no_wait + wait_min
        ranked.append((total, wait_min, route))

    ranked.sort(key=lambda x: x[0])
    return ranked[:n_routes]


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
