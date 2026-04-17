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
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import networkx as nx

from gtfs_loader import GTFS_DIR, _haversine_miles, find_nearest_train_stations, find_nearest_bus_stops
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

# Cache populated by _build_graph() so get_bus_stop_sequences() can return
# it without re-streaming stop_times.txt a second time.
_bus_seq_cache: dict[tuple[str, str], list[tuple]] | None = None


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
    """Returns service_ids active on weekdays (Mon–Fri) from calendar.txt,
    augmented with services defined purely via calendar_dates.txt add-exceptions."""
    import datetime
    ids: set[str] = set()
    cal_file = GTFS_DIR / "calendar.txt"
    if cal_file.exists():
        with open(cal_file, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if all(row.get(d, "0").strip() == "1"
                       for d in ("monday", "tuesday", "wednesday", "thursday", "friday")):
                    ids.add(row["service_id"].strip())

    # Also include services expressed purely through calendar_dates.txt
    # (exception_type=1 add-dates on Mon–Fri). Require ≥3 such dates to avoid
    # including one-off special services.
    cal_dates_file = GTFS_DIR / "calendar_dates.txt"
    if cal_dates_file.exists():
        weekday_add_counts: dict[str, int] = {}
        with open(cal_dates_file, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("exception_type", "").strip() != "1":
                    continue
                sid = row.get("service_id", "").strip()
                date_str = row.get("date", "").strip()
                try:
                    d = datetime.date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
                    if d.weekday() < 5:   # 0=Mon … 4=Fri
                        weekday_add_counts[sid] = weekday_add_counts.get(sid, 0) + 1
                except (ValueError, IndexError):
                    continue
        for sid, count in weekday_add_counts.items():
            if count >= 3:
                ids.add(sid)

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


def _stream_all_stop_sequences(
    train_candidates:   dict[str, str],   # {trip_id: route_id}  — train weekday trips
    train_dirs:         dict[str, str],   # {trip_id: direction_id}
    bus_candidates:     dict[str, str],   # {trip_id: route_id}  — bus weekday trips
    bus_dirs:           dict[str, str],   # {trip_id: direction_id}
    platform_to_parent: dict[str, str],   # {platform_stop_id: parent_mapid}
    bus_stop_lookup:    dict[str, dict],  # {stop_id: {name, lat, lon}}
    bus_route_map:      dict[str, str],   # {route_id: route_short_name}
) -> tuple[dict[str, list[tuple[str, float]]], dict[tuple[str, str], list[tuple]]]:
    """
    Single-pass stream of stop_times.txt that simultaneously builds:
      - train_selected : {trip_id: [(parent_mapid, arrival_min), ...]}
                         (same output as the old _stream_stop_sequences)
      - bus_result     : {(route_short_name, direction_id): [(stop_id, stop_name,
                           lat, lon, arr_minutes), ...]}
                         (same output as get_bus_stop_sequences)

    Replaces the old _stream_stop_sequences and eliminates the second
    dedicated stop_times.txt pass that get_bus_stop_sequences previously
    performed.

    Selection strategy (unchanged from original functions):
      Train — one representative trip per (route_id, direction_id), chosen as
              the weekday trip whose first-stop departure is closest to noon.
      Bus   — same midday-targeting strategy per (route_short_name, direction_id).
    """
    print("[transit_graph] Streaming stop_times.txt (unified train+bus pass) …")
    t0 = time.time()

    # --- raw accumulators ---
    train_raw: dict[str, list] = {tid: [] for tid in train_candidates}
    bus_raw:   dict[str, list] = {tid: [] for tid in bus_candidates}

    all_candidate_tids = set(train_candidates) | set(bus_candidates)
    rows_read = 0

    with open(GTFS_DIR / "stop_times.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows_read += 1
            tid = row.get("trip_id", "").strip()
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

            if tid in bus_raw:
                sid = row.get("stop_id", "").strip()
                if sid in bus_stop_lookup:
                    bus_raw[tid].append((seq, sid, arr_min))

    print(
        f"[transit_graph] Unified stream: {rows_read:,} rows in {time.time() - t0:.1f}s"
    )

    # ------------------------------------------------------------------ #
    # Train side — identical post-processing to old _stream_stop_sequences
    # ------------------------------------------------------------------ #
    train_sorted: dict[str, list] = {}
    train_first:  dict[str, float] = {}
    for tid, rows in train_raw.items():
        if not rows:
            continue
        rows.sort(key=lambda x: x[0])
        train_sorted[tid] = rows
        train_first[tid]  = rows[0][2]

    train_groups: dict[tuple[str, str], list[str]] = {}
    for tid in train_sorted:
        rid = train_candidates[tid]
        did = train_dirs.get(tid, "0")
        train_groups.setdefault((rid, did), []).append(tid)

    train_selected: dict[str, list[tuple[str, float]]] = {}
    for (rid, did), tids in train_groups.items():
        best = min(tids, key=lambda t: abs(train_first.get(t, 0.0) - _TARGET_NOON_MINUTES))
        seq_list: list[tuple[str, float]] = []
        for _, parent, arr_min in train_sorted[best]:
            seq_list.append((parent, arr_min))
        train_selected[best] = seq_list

    print(f"[transit_graph] Selected {len(train_selected)} representative train trips "
          f"({len(train_groups)} line/direction pairs, targeting noon departures)")

    # ------------------------------------------------------------------ #
    # Bus side — mirrors get_bus_stop_sequences post-processing exactly
    # ------------------------------------------------------------------ #
    bus_sorted: dict[str, list] = {}
    bus_first:  dict[str, float] = {}
    for tid, rows in bus_raw.items():
        if not rows:
            continue
        rows.sort(key=lambda x: x[0])
        bus_sorted[tid] = rows
        bus_first[tid]  = rows[0][2]

    bus_groups: dict[tuple[str, str], list[str]] = {}
    for tid in bus_sorted:
        rid = bus_candidates[tid]
        did = bus_dirs.get(tid, "0")
        bus_groups.setdefault((rid, did), []).append(tid)

    bus_result: dict[tuple[str, str], list[tuple]] = {}
    for (rid, did), tids in bus_groups.items():
        best  = min(tids, key=lambda t: abs(bus_first.get(t, 0.0) - _TARGET_NOON_MINUTES))
        short = bus_route_map.get(rid, rid)
        seq_entries: list[tuple] = []
        for _, sid, arr_min in bus_sorted[best]:
            meta = bus_stop_lookup.get(sid, {})
            seq_entries.append((
                sid,
                meta.get("name", sid),
                meta.get("lat", 0.0),
                meta.get("lon", 0.0),
                arr_min,
            ))
        bus_result[(short, did)] = seq_entries

    n_pairs = len(bus_result)
    print(f"[transit_graph] Bus sequences built: {n_pairs} route/direction pairs")

    return train_selected, bus_result


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

    # Load bus metadata so the unified streamer can process both train and bus
    # stop_times in a single pass — eliminating the second file stream that
    # get_bus_stop_sequences() previously performed.
    bus_route_map   = _load_bus_route_map()
    bus_stop_lookup = _load_bus_stop_lookup()
    bus_trip_route, bus_trip_dir = _load_bus_candidate_trips(set(bus_route_map.keys()))

    stop_seqs, bus_result = _stream_all_stop_sequences(
        selected_trips, trip_dirs,
        bus_trip_route, bus_trip_dir,
        platform_to_parent,
        bus_stop_lookup,
        bus_route_map,
    )

    # Cache bus sequences so get_bus_stop_sequences() returns them immediately
    # without re-streaming stop_times.txt.
    global _bus_seq_cache
    _bus_seq_cache = bus_result

    G = nx.DiGraph()

    # Add all parent station nodes with metadata
    for mapid, meta in parent_stations.items():
        G.add_node(mapid, node_type="train", **meta)

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
            line_code=best_route,
            edge_type="transit",
            mode="train",
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

    # ── Chunk 1 (Feature B): Add bus stop nodes ────────────────────────────
    # Bus stop IDs (0–29999) never collide with train mapids (40000–49999).
    for stop_id, stop in bus_stop_lookup.items():
        G.add_node(
            stop_id,
            node_type="bus",
            lat=stop["lat"],
            lon=stop["lon"],
            name=stop["name"],
        )
    print(f"[transit_graph] Added {len(bus_stop_lookup)} bus stop nodes to graph")

    # ── Chunk 2 (Feature B): Add bus route edges ───────────────────────────
    # Reuse the already-cached bus sequences — no second stop_times.txt scan.
    bus_sequences = get_bus_stop_sequences()
    bus_edge_count = 0
    for (short_name, did), stops in bus_sequences.items():
        if len(stops) < 2:
            continue
        for i in range(len(stops) - 1):
            from_stop = stops[i]
            to_stop   = stops[i + 1]
            from_id   = from_stop[0]   # stop_id
            to_id     = to_stop[0]     # stop_id
            from_arr  = from_stop[4]   # arr_minutes since midnight
            to_arr    = to_stop[4]     # arr_minutes since midnight
            leg_min   = max(0.5, to_arr - from_arr)
            G.add_edge(
                from_id, to_id,
                weight=leg_min,
                route_id=short_name,
                direction_id=did,
                line=did,          # direction_id; no direction string in GTFS static data
                line_code=short_name,
                edge_type="transit",
                mode="bus",
            )
            bus_edge_count += 1
    print(f"[transit_graph] Added {bus_edge_count} bus transit edges to graph")

    # ── Chunk 3 (Feature B): Add train↔bus transfer walk edges ────────────
    # Bidirectional walk edges between each train station and nearby bus stops
    # within 0.15 miles (street walk ≤ 5 min). These enable Dijkstra to
    # discover intermodal paths naturally alongside pure-train/bus paths.
    intermodal_edge_count = 0
    _TRANSFER_RADIUS_MILES = 0.15
    _TRANSFER_WALK_CAP_MIN = 5.0

    for mapid, station in parent_stations.items():
        s_lat, s_lon = station["lat"], station["lon"]
        for stop_id, stop in bus_stop_lookup.items():
            dist = _haversine_miles(s_lat, s_lon, stop["lat"], stop["lon"])
            if dist > _TRANSFER_RADIUS_MILES:
                continue
            walk_min = street_walk_minutes(s_lat, s_lon, stop["lat"], stop["lon"])
            if walk_min > _TRANSFER_WALK_CAP_MIN:
                continue
            G.add_edge(mapid, stop_id,
                       weight=walk_min, edge_type="walk", route_id="walk", mode="walk")
            G.add_edge(stop_id, mapid,
                       weight=walk_min, edge_type="walk", route_id="walk", mode="walk")
            intermodal_edge_count += 2

    print(f"[transit_graph] Added {intermodal_edge_count} train↔bus transfer walk edges")
    print(
        f"[transit_graph] Graph ready: {G.number_of_nodes()} nodes, "
        f"{G.number_of_edges()} edges "
        f"(train: {transit_edge_count} transit + {transfer_edge_count} transfer; "
        f"bus: {bus_edge_count} transit + {intermodal_edge_count} intermodal walk) "
        f"({time.time() - t0:.1f}s)"
    )
    return G, parent_stations


def warm_up() -> None:
    """
    Trigger graph construction and bus stop sequence loading at startup
    so the first user request is fast.
    Call this from the FastAPI lifespan or startup event.
    """
    G, _ = _build_graph()
    print(f"[transit_graph] Graph size: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    get_bus_stop_sequences()
    _build_stop_to_routes()
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
    # Use the shape with the MOST points for each route/direction so we always
    # get the full-length route shape rather than a short-turn variant.
    route_dir_to_shape: dict[tuple[str, str], str] = {}
    route_dir_shape_len: dict[tuple[str, str], int] = {}

    with open(GTFS_DIR / "trips.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            route_id     = row.get("route_id",     "").strip()
            direction_id = row.get("direction_id", "0").strip()
            shape_id     = row.get("shape_id",     "").strip()
            if not route_id or not shape_id:
                continue
            key = (route_id, direction_id)
            n = len(shapes.get(shape_id, []))
            if n > route_dir_shape_len.get(key, -1):
                route_dir_to_shape[key] = shape_id
                route_dir_shape_len[key] = n

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


@lru_cache(maxsize=512)
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
    # Contains-match fallback — rank by similarity to avoid wrong-line matches
    # (e.g. "Harlem" matches both Harlem-Lake and Harlem-Forest Park)
    best_match = None
    best_ratio = 0.0
    for s in stations.values():
        s_lower = s["name"].lower()
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

    if lo >= hi:
        # Both stops map to the same nearest shape point — happens on short trips
        # where stop spacing exceeds shape point density.  Return a straight line
        # between the actual stop coordinates so the caller always gets ≥ 2 points.
        return [[board_lat, board_lon], [exit_lat, exit_lon]]

    segment = shape_points[lo : hi + 1]
    # If the rider travels in the opposite direction of the shape, reverse so the
    # animated polyline direction matches actual travel.
    if board_idx > exit_idx:
        segment = segment[::-1]
    return segment


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


def get_bus_stop_sequences() -> dict[tuple[str, str], list[tuple]]:
    """
    Build and cache the bus stop sequence table.

    Returns:
        {(route_short_name, direction_id): [
            (stop_id, stop_name, lat, lon, arr_minutes), ...
        ]}
        Sequences are ordered by stop_sequence. arr_minutes is minutes since
        midnight for the representative midday trip.

    Fast path: if _build_graph() has already run (the normal case), the result
    is returned directly from _bus_seq_cache with no I/O.

    Fallback path: if called before _build_graph() (e.g. in isolated tests),
    the function streams stop_times.txt independently — identical behaviour to
    the original implementation.
    """
    # Fast path — _build_graph() already populated the cache during startup.
    if _bus_seq_cache is not None:
        return _bus_seq_cache

    # Fallback path — should only be reached in tests or unusual call orders.
    print("[transit_graph] get_bus_stop_sequences: cache miss — streaming independently …")
    print("[transit_graph] Building bus stop sequence table …")
    t0 = time.time()

    bus_route_map  = _load_bus_route_map()                        # {route_id: route_short_name}
    bus_stop_lookup = _load_bus_stop_lookup()                      # {stop_id: {name, lat, lon}}
    trip_route, trip_dir = _load_bus_candidate_trips(
        set(bus_route_map.keys())
    )

    # Stream stop_times.txt, collecting sequences for all candidate bus trips
    candidate_set = set(trip_route)   # fast membership test; no list pre-allocation
    raw: dict[str, list] = defaultdict(list)

    print("[transit_graph] Streaming stop_times.txt for bus sequences …")
    t1 = time.time()
    rows_read = 0

    with open(GTFS_DIR / "stop_times.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows_read += 1
            tid = row.get("trip_id", "").strip()
            if tid not in candidate_set:
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
            legs.append(WalkLeg(
                from_name="Your location",
                to_name=to_name,
                minutes=walk_min,
                path_points=street_walk_path(origin_lat, origin_lon, to_lat, to_lon),
                directions=street_walk_directions(origin_lat, origin_lon, to_lat, to_lon),
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
            legs.append(WalkLeg(
                from_name=from_name,
                to_name="Your destination",
                minutes=walk_min,
                path_points=street_walk_path(from_lat, from_lon, dest_lat, dest_lon),
                directions=street_walk_directions(from_lat, from_lon, dest_lat, dest_lon),
                exit_label=label,
            ))
            walk_total += walk_min
            idx += 1
            continue

        # ── Inter-station transfer walk (train↔train from transfers.txt) ─────
        if edge_type == "transfer":
            from_name, flat, flon = _resolve_node(from_node, stations, G)
            to_name,   tlat, tlon = _resolve_node(to_node,   stations, G)
            legs.append(WalkLeg(
                from_name=from_name,
                to_name=to_name,
                minutes=weight,
                path_points=street_walk_path(flat, flon, tlat, tlon),
                directions=street_walk_directions(flat, flon, tlat, tlon),
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
            legs.append(WalkLeg(
                from_name=from_name,
                to_name=to_name,
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
        while look < len(path) - 1 and path[look] != DEST and path[look + 1] != DEST:
            next_edge = G.edges[path[look], path[look + 1]]
            if (next_edge.get("route_id") != group_route
                    or next_edge.get("edge_type") != "transit"):
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
                directions=[{"street": "Change trains", "direction": "", "minutes": _TRANSFER_MINUTES}],
            ))
            walk_total += _TRANSFER_MINUTES

        board_name,  board_lat,  board_lon  = _resolve_node(board_node,  stations, G)
        alight_name, alight_lat, alight_lon = _resolve_node(alight_node, stations, G)

        # For bus edges, line_code comes from the edge attribute (same as route_id,
        # but being explicit is safer). For train edges, group_route is the line code.
        line_code = edge.get("line_code") or group_route

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
    return Route(
        legs=legs,
        transit_minutes=transit_total,
        walk_minutes_total=walk_total,
        transfers=max(0, len(transit_legs) - 1),
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
        station_lines = {
            data.get("line", "")
            for _, _, data in G.edges(mapid, data=True)
            if data.get("line") and data.get("edge_type") == "transit"
        }
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

    # Origin stations (nearest train stations with walk times already computed).
    # If the caller passed an empty list (no stations within 0.5 miles per
    # resolve_location), or passed None, search directly — expanding the
    # radius in 0.25-mile increments up to 2.0 miles when needed (e.g. the
    # user is in a neighbourhood that is more than 0.5 miles from the nearest
    # station).
    if not origin_stations:
        for _r in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0):
            origin_stations = find_nearest_train_stations(
                origin_lat, origin_lon, max_distance_miles=_r
            )
            if origin_stations:
                break

    # Destination stations (walk direction: station → destination).
    # Same progressive-expansion logic: prefer the closest station but don't
    # fail just because the destination is slightly over 0.5 miles from the
    # nearest platform.
    for _r in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0):
        dest_stations = find_nearest_train_stations(
            dest_lat, dest_lon, walk_to_station=False, max_distance_miles=_r
        )
        if dest_stations:
            break

    if not origin_stations or not dest_stations:
        return []

    # Feature H: drop candidate stations that add no new transit lines vs.
    # a closer same-line station — eliminates near-duplicate routes.
    origin_stations = _dedup_stations_by_line(G_base, origin_stations)
    dest_stations   = _dedup_stations_by_line(G_base, dest_stations)

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

    # Feature B: add virtual walk edges to/from nearby bus stops so Dijkstra
    # can discover intermodal paths that start or end at a bus stop.
    for stop in find_nearest_bus_stops(origin_lat, origin_lon):
        sid = stop["stop_id"]
        if sid in G.nodes:
            G.add_edge(ORIGIN, sid,
                       weight=stop["walk_minutes"], edge_type="walk",
                       route_id="walk", mode="walk")

    for stop in find_nearest_bus_stops(dest_lat, dest_lon):
        sid = stop["stop_id"]
        if sid in G.nodes:
            G.add_edge(sid, DEST,
                       weight=stop["walk_minutes"], edge_type="walk",
                       route_id="walk", mode="walk")

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


# ---------------------------------------------------------------------------
# Bus stop spatial grid index (Chunk 1 — Feature C)
# ---------------------------------------------------------------------------
#
# _bus_stop_grid: grid cell → list of stop_ids in that cell
#   key = (int(lat / 0.005), int(lon / 0.005))
#   0.005° ≈ 0.34 miles lat / 0.27 miles lon at Chicago's latitude
#
# _bus_stop_coords: stop_id → (lat, lon) for haversine post-filtering
#
# Both are populated once at module import via _build_bus_stop_grid().

_bus_stop_grid:   dict[tuple[int, int], list[str]] = {}
_bus_stop_coords: dict[str, tuple[float, float]]   = {}


def _build_bus_stop_grid() -> None:
    """Populate _bus_stop_grid and _bus_stop_coords from stops.txt at module load."""
    global _bus_stop_grid, _bus_stop_coords
    stops = _load_bus_stop_lookup()
    grid: dict[tuple[int, int], list[str]] = {}
    coords: dict[str, tuple[float, float]] = {}
    for sid, meta in stops.items():
        lat, lon = meta["lat"], meta["lon"]
        coords[sid] = (lat, lon)
        cell = (int(lat / 0.005), int(lon / 0.005))
        grid.setdefault(cell, []).append(sid)
    _bus_stop_grid   = grid
    _bus_stop_coords = coords
    print(f"[transit_graph] Bus stop grid built: {len(coords)} stops, {len(grid)} cells")


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

    Uses the pre-built _bus_stop_grid for an initial bounding-box filter
    (checking at most a 3×3 cell window for a 0.25-mile radius), then
    post-filters with exact haversine distance.

    Not cached — lat/lon float keys would produce unbounded cache growth.
    """
    lat_delta = radius_miles * 0.0145   # degrees per mile at Chicago latitude
    lon_delta = radius_miles * 0.0175

    lat_min = int((lat - lat_delta) / 0.005)
    lat_max = int((lat + lat_delta) / 0.005)
    lon_min = int((lon - lon_delta) / 0.005)
    lon_max = int((lon + lon_delta) / 0.005)

    candidates: list[str] = []
    for clat in range(lat_min, lat_max + 1):
        for clon in range(lon_min, lon_max + 1):
            candidates.extend(_bus_stop_grid.get((clat, clon), []))

    return [
        sid for sid in candidates
        if _haversine_miles(lat, lon, *_bus_stop_coords[sid]) <= radius_miles
    ]


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

    # ── Pass 1: find the best exit stop per route+direction (haversine only) ──
    #
    # No Route objects are built here — just the cheapest possible per-candidate
    # distance check.  Building a Route requires OSMnx street-network calls
    # (walk_minutes, walk_path, walk_directions) which are expensive; we defer
    # them to Pass 2 so we only pay that cost for candidates that survive the
    # progressive distance threshold.
    #
    # {route_dir_key: (exit_dist_miles, stop_id, route_num, direction,
    #                  wait_min, board_idx, exit_idx)}
    # {route_dir_key: (score, exit_dist_miles, stop_id, route_num, direction,
    #                  wait_min, board_idx, exit_idx)}
    # score = board_walk_min + wait_min + exit_dist_miles*20 (proxy for exit walk)
    pass1: dict[tuple[str, str], tuple] = {}

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
        cands = [e for e in board_index[stop_id] if e[0] == route_num]
        if not cands:
            continue

        board_walk_min = board_walk.get(stop_id, 0.0)

        for short_name, did, board_idx in cands:
            route_dir_key = (short_name, did)
            seq = sequences[route_dir_key]

            best_exit_idx  = -1
            best_exit_dist = float("inf")
            for j in range(board_idx + 1, len(seq)):
                _, _, slat, slon, _ = seq[j]
                dist = _haversine_miles(dest_lat, dest_lon, slat, slon)
                if dist < best_exit_dist:
                    best_exit_dist = dist
                    best_exit_idx  = j

            if best_exit_idx < 0:
                continue   # boarding at terminus

            # Score = board walk + wait + proxy for exit walk (20 min/mile)
            score = board_walk_min + wait_min + best_exit_dist * 20.0

            existing = pass1.get(route_dir_key)
            if existing is None or score < existing[0]:
                pass1[route_dir_key] = (
                    score, best_exit_dist, stop_id, route_num, direction,
                    wait_min, board_idx, best_exit_idx,
                )

    if not pass1:
        return []

    # ── Progressive threshold ─────────────────────────────────────────────────
    # Start at 0.25 miles, expand by 0.25-mile increments up to 2.0 miles.
    # Use the tightest threshold that yields at least one result, so the exit
    # walk is minimised rather than allowed to creep up without reason.
    threshold = next(
        (_r for _r in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
         if any(v[1] <= _r for v in pass1.values())),
        None,
    )
    if threshold is None:
        return []

    # ── Pass 2: build Route objects only for candidates within the threshold ──
    ranked: list[tuple[float, int, object]] = []

    for (short_name, did), (_score, best_exit_dist, stop_id, route_num, direction,
                             wait_min, board_idx, best_exit_idx) in pass1.items():
        if best_exit_dist > threshold:
            continue

        stops = sequences[(short_name, did)]
        _, board_name, board_lat, board_lon, board_arr = stops[board_idx]
        exit_sid, exit_name, exit_lat, exit_lon, exit_arr = stops[best_exit_idx]

        board_walk_min = board_walk.get(stop_id, 0.0)

        # In-vehicle scheduled time from GTFS arrival times
        in_vehicle_min = exit_arr - board_arr
        if in_vehicle_min < 0:
            in_vehicle_min += 24 * 60   # handle times past midnight
        if in_vehicle_min <= 0:
            continue

        # Street-network walk time from exit stop to destination (OSMnx).
        # Feature A: try to find a named station exit for the alighting stop.
        # Bus stops are not train stations, so best_exit() returns None for
        # them — behaviour is identical to before when no exit is found.
        bus_exit_info = best_exit(exit_sid, dest_lat, dest_lon)
        if bus_exit_info is not None:
            walk_origin_lat = bus_exit_info["lat"]
            walk_origin_lon = bus_exit_info["lon"]
            exit_walk_min   = bus_exit_info["walk_minutes"]
            bus_exit_label  = bus_exit_info["label"]
        else:
            walk_origin_lat = exit_lat
            walk_origin_lon = exit_lon
            exit_walk_min   = street_walk_minutes(exit_lat, exit_lon, dest_lat, dest_lon)
            bus_exit_label  = ""

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
                path_points=street_walk_path(walk_origin_lat, walk_origin_lon, dest_lat, dest_lon),
                directions=street_walk_directions(walk_origin_lat, walk_origin_lon, dest_lat, dest_lon),
                exit_label=bus_exit_label,
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
# Bus-to-bus transfer routing (Chunk 3 — Feature C)
# ---------------------------------------------------------------------------

def find_bus_transfer_routes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    bus_arrivals: list[dict],      # from cta_client.get_bus_arrivals(); must include stop_id
    origin_bus_stops: list[dict],  # from gtfs_loader.find_nearest_bus_stops(); includes walk_minutes
    n_routes: int = 3,
) -> list[tuple[float, int, object]]:
    """
    Find bus+bus transfer routes from origin to destination.

    Only called when find_bus_routes() returns no direct bus results.
    Builds 5-leg routes of the form:
        WalkLeg  (origin → boarding_stop_A)
        TransitLeg (route A: boarding_stop_A → transfer_stop_Sk)
        WalkLeg  (Sk → transfer_boarding_stop_T)   ← minutes=0 if same stop
        TransitLeg (route B: T → exit_stop_B)
        WalkLeg  (exit_stop_B → destination)

    Sorting key includes a fixed 7.5-min estimate for the leg-2 wait (half
    of a typical 15-min CTA headway). This estimate is NOT added to
    route.walk_minutes_total or route.transit_minutes — those fields retain
    their strict definitions.

    Returns:
        list of (total_minutes, wait_minutes_A, Route) sorted by total_minutes.
        wait_minutes_A is the live wait for route A (same convention as
        find_bus_routes()). Empty list if no transfer routes are found.
    """
    sequences = get_bus_stop_sequences()
    if not sequences or not bus_arrivals or not origin_bus_stops:
        return []
    if not _stop_to_routes:
        return []

    _LEG2_WAIT_ESTIMATE = 7.5   # fixed leg-2 wait estimate (minutes)
    _MAX_TRIP_MINUTES   = 90.0
    _MAX_EXIT_DIST      = 0.5   # miles — same threshold as find_bus_routes()
    _MAX_TRANSFER_WALK  = 0.25  # miles
    _FWD_PROGRESS_RATIO = 0.9   # Sk must reduce haversine-to-dest by ≥10%
    _MAX_CANDIDATES_PER_ARRIVAL = 3

    # Walk time from origin to each nearby boarding stop
    board_walk: dict[str, float] = {
        s["stop_id"]: s.get("walk_minutes", 0.0)
        for s in origin_bus_stops
    }
    boarding_stop_ids = set(board_walk.keys())

    # Build board_index: stop_id → [(short_name, did, idx_in_seq), ...]
    # Limited to our actual boarding stops (cheap per request).
    board_index: dict[str, list[tuple[str, str, int]]] = {}
    for (short_name, did), stops in sequences.items():
        for idx, entry in enumerate(stops):
            sid = entry[0]
            if sid in boarding_stop_ids:
                board_index.setdefault(sid, []).append((short_name, did, idx))

    # ── Pass 1: find candidate transfers (haversine only) ────────────────────
    #
    # For each live arrival, scan forward from the boarding stop on route A.
    # At each stop Sk that shows forward progress toward the destination,
    # check nearby stops T and the routes serving them.  If route B exits
    # within 0.5 miles of the destination, record the candidate.
    #
    # Stored as: {(route_A_key, Sk_idx, T_stop_id, route_B_key, exit_B_idx):
    #              (score, board_walk_min, wait_min_A, board_stop_id)}
    #
    # score = board_walk_min + wait_A + transfer_walk_haversine*20 + exit_B_haversine*20

    # Use a dict keyed by the logical candidate identity to deduplicate
    # (same route A + transfer stop + route B combination from different arrivals).
    candidate_map: dict[tuple, tuple] = {}

    for arrival in bus_arrivals:
        stop_id   = arrival.get("stop_id", "")
        route_num = arrival.get("route", "")
        wait_min  = arrival.get("arrives_in_minutes", 0)

        if not stop_id or stop_id not in board_index:
            continue

        cands_A = [e for e in board_index[stop_id] if e[0] == route_num]
        if not cands_A:
            continue

        board_walk_min   = board_walk.get(stop_id, 0.0)
        boarding_hav     = _haversine_miles(stop_id and _bus_stop_coords.get(stop_id, (origin_lat, origin_lon))[0] or origin_lat,
                                            stop_id and _bus_stop_coords.get(stop_id, (origin_lat, origin_lon))[1] or origin_lon,
                                            dest_lat, dest_lon)

        for short_A, did_A, board_idx in cands_A:
            seq_A = sequences[(short_A, did_A)]
            route_A_key = (short_A, did_A)

            # Per-arrival per-route-A candidate list for top-3 capping
            arrival_candidates: list[tuple] = []

            for sk_idx in range(board_idx + 1, len(seq_A)):
                sk_sid, sk_name, sk_lat, sk_lon, _ = seq_A[sk_idx]

                # Forward-progress filter: Sk must be ≥10% closer to dest than boarding
                sk_hav = _haversine_miles(sk_lat, sk_lon, dest_lat, dest_lon)
                if sk_hav >= boarding_hav * _FWD_PROGRESS_RATIO:
                    continue

                # Find bus stops near Sk within transfer-walk radius
                nearby = _stops_near(sk_lat, sk_lon, _MAX_TRANSFER_WALK)
                if not nearby:
                    continue

                for t_stop_id in nearby:
                    # Don't transfer to a stop on the same route+direction
                    routes_at_T = _stop_to_routes.get(t_stop_id, [])
                    for short_B, did_B, t_idx, _ in routes_at_T:
                        if (short_B, did_B) == route_A_key:
                            continue   # same route — skip

                        seq_B = sequences.get((short_B, did_B))
                        if seq_B is None:
                            continue

                        # Scan forward from T on route B to find best exit stop
                        best_exit_idx  = -1
                        best_exit_dist = float("inf")
                        for j in range(t_idx + 1, len(seq_B)):
                            _, _, elat, elon, _ = seq_B[j]
                            d = _haversine_miles(elat, elon, dest_lat, dest_lon)
                            if d < best_exit_dist:
                                best_exit_dist = d
                                best_exit_idx  = j

                        if best_exit_idx < 0 or best_exit_dist > _MAX_EXIT_DIST:
                            continue

                        transfer_hav = _haversine_miles(sk_lat, sk_lon,
                                                        *_bus_stop_coords.get(t_stop_id, (sk_lat, sk_lon)))
                        # 20.0 = 60 min/hr ÷ 3 mph walk speed; ×1.3 corrects
                        # straight-line to Manhattan-grid distance.
                        score = (board_walk_min + wait_min
                                 + transfer_hav * 26.0
                                 + best_exit_dist * 26.0)

                        arrival_candidates.append((
                            score,
                            route_A_key, sk_idx, t_stop_id,
                            (short_B, did_B), best_exit_idx,
                            board_walk_min, wait_min, stop_id,
                        ))

            # Keep only top-3 candidates for this arrival+route-A combination
            arrival_candidates.sort(key=lambda x: x[0])
            for cand in arrival_candidates[:_MAX_CANDIDATES_PER_ARRIVAL]:
                score, rA, sk_i, t_sid, rB, exit_i, bwm, wm, bsid = cand
                key = (rA, sk_i, t_sid, rB, exit_i)
                existing = candidate_map.get(key)
                if existing is None or score < existing[0]:
                    candidate_map[key] = (score, bwm, wm, bsid)

    if not candidate_map:
        return []

    # ── Pass 2: build Route objects for surviving candidates (OSMnx calls) ───
    ranked: list[tuple[float, int, object]] = []

    for (route_A_key, sk_idx, t_stop_id, route_B_key, exit_B_idx), \
        (score, board_walk_min, wait_min_A, board_stop_id) in candidate_map.items():

        short_A, did_A = route_A_key
        short_B, did_B = route_B_key
        seq_A = sequences[(short_A, did_A)]
        seq_B = sequences[(short_B, did_B)]

        # Locate boarding stop index from the stored board_stop_id
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
        if t_meta is None:
            continue
        t_lat, t_lon = t_meta

        # Look up T's name from the sequence entry (index known from _stop_to_routes)
        t_idx_in_seq = next(
            (e[2] for e in _stop_to_routes.get(t_stop_id, [])
             if (e[0], e[1]) == route_B_key),
            None,
        )
        if t_idx_in_seq is None:
            continue
        t_sid_check, t_name, t_lat_s, t_lon_s, t_arr = seq_B[t_idx_in_seq]

        exit_sid, exit_name, exit_lat, exit_lon, exit_arr = seq_B[exit_B_idx]

        # In-vehicle times from GTFS scheduled arrival minutes
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

        # Transfer walk time (OSMnx) — skip if Sk and T are the same stop
        same_stop = (sk_sid == t_stop_id)
        if same_stop:
            transfer_walk_min = 0.0
            transfer_path     = []
            transfer_dirs     = []
        else:
            transfer_walk_min = street_walk_minutes(sk_lat, sk_lon, t_lat_s, t_lon_s)
            transfer_path     = street_walk_path(sk_lat, sk_lon, t_lat_s, t_lon_s)
            transfer_dirs     = street_walk_directions(sk_lat, sk_lon, t_lat_s, t_lon_s)

        exit_walk_min = street_walk_minutes(exit_lat, exit_lon, dest_lat, dest_lon)

        total_no_wait = (board_walk_min + in_vehicle_A + transfer_walk_min
                         + in_vehicle_B + exit_walk_min)

        if total_no_wait + wait_min_A + _LEG2_WAIT_ESTIMATE > _MAX_TRIP_MINUTES:
            continue

        # Look up direction strings for both transit legs
        direction_A = next(
            (a.get("direction", short_A)
             for a in bus_arrivals
             if a.get("stop_id") == board_stop_id and a.get("route") == short_A),
            short_A,
        )
        direction_B = short_B   # no live arrival for leg B; use route number as fallback

        legs = [
            WalkLeg(
                from_name="Your location",
                to_name=board_name,
                minutes=round(board_walk_min, 1),
                path_points=street_walk_path(origin_lat, origin_lon, board_lat, board_lon),
                directions=street_walk_directions(origin_lat, origin_lon, board_lat, board_lon),
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
                path_points=street_walk_path(exit_lat, exit_lon, dest_lat, dest_lon),
                directions=street_walk_directions(exit_lat, exit_lon, dest_lat, dest_lon),
            ),
        ]

        route = Route(
            legs=legs,
            transit_minutes=round(in_vehicle_A + in_vehicle_B, 1),
            walk_minutes_total=round(board_walk_min + transfer_walk_min + exit_walk_min, 1),
            transfers=1,
        )
        sort_key = total_no_wait + wait_min_A + _LEG2_WAIT_ESTIMATE
        ranked.append((sort_key, wait_min_A, route))

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
