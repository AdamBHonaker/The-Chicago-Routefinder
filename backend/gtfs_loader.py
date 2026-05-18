"""
GTFS-based stop resolver for the CTA Transit app.

Loads stops.txt from the downloaded GTFS feed and provides functions
to find the nearest train stations and bus stops to any location, plus the
curated NEIGHBORHOOD_COORDS landmark lookup + fuzzy-match helper used by the
forward-geocoding cascade in `geocoding.py`.

Stop ID ranges (per CTA GTFS / Train Tracker docs):
  0     – 29999  →  Bus stops
  30000 – 39999  →  Train platform stops (direction-specific)
  40000 – 49999  →  Train parent stations (used by Train Tracker API as mapid)

Stops are parsed from stops.txt once per process and also persisted to a
JSON cache (stops_cache.json) in the same directory. On subsequent starts
the cache is loaded instead of re-parsing CSV, provided the mtime of
stops.txt has not changed. The cache is written atomically so a crash during
the write never leaves a corrupt cache file. JSON (not pickle) is used so
the deserialization surface is plain data — a tampered cache file cannot
execute arbitrary code at startup (SEC-005).

This module no longer geocodes free text. The full resolution cascade lives
in `backend/geocoding.py` (Chunk 5 of the Geocoding & Autocomplete plan).
NEIGHBORHOOD_COORDS + `fuzzy_match_neighborhood` are retained here because
they are the curated-landmark layer the cascade consumes — keeping them
adjacent to the stop loader avoids a circular import with geocoding.py.

Geographic scope: Howard St (north) to 50th St (south), lakefront (east) to
Pulaski Rd (west). Walk times outside this rectangle fall back to Haversine
estimates and no CTA stops will be found beyond the boundary.
"""

import csv
import heapq
import json
from functools import lru_cache
from pathlib import Path

from walking import walk_minutes
from utils import haversine_miles as _haversine_miles, SpatialGrid
from geocode_text import (
    fuzzy_match_neighborhood as _fuzzy_match_neighborhood,
)

GTFS_DIR = Path(__file__).parent / "gtfs_data"
_STOPS_CACHE_PATH = GTFS_DIR / "stops_cache.json"



# ---------------------------------------------------------------------------
# Neighborhood / landmark coordinates — fast cache
# Geographic scope: Howard St (north) → 50th St (south) | Lakefront → Pulaski Rd (west)
# Entries outside this rectangle are omitted — they would find no nearby CTA stops.
# ---------------------------------------------------------------------------

# Loaded once at first access from backend/static_data/neighborhoods.json.
# Storing the landmark list as JSON keeps it editable without a Python source
# change and lets a non-Python contributor add a new entry by appending one
# line. The directory is named static_data/ (not data/) because /app/data/ is
# the Railway persistent-volume mount point in production — placing static
# fixtures there gets them hidden by the volume overlay at runtime.
_NEIGHBORHOODS_PATH: Path = Path(__file__).parent / "static_data" / "neighborhoods.json"


def _load_neighborhood_coords() -> dict[str, tuple[float, float]]:
    raw = json.loads(_NEIGHBORHOODS_PATH.read_text(encoding="utf-8"))
    return {k: (float(v[0]), float(v[1])) for k, v in raw.items()}


NEIGHBORHOOD_COORDS: dict[str, tuple[float, float]] = _load_neighborhood_coords()




# ---------------------------------------------------------------------------
# GTFS stop loader (cached after first call)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_stops() -> tuple[list[dict], list[dict]]:
    """
    Parse stops.txt and return (train_stations, bus_stops).

    On first call after a GTFS update the CSV is parsed and the result is
    persisted to stops_cache.json alongside the source file's mtime.  On
    subsequent starts the cache is loaded instead, skipping CSV parsing
    entirely.  The cache is written atomically (tmp → rename) so a crash
    during the write never leaves a corrupt cache.

    JSON (not pickle) is used so the deserialization surface is plain data
    — a tampered cache file cannot execute arbitrary code at startup
    (SEC-005). The cached structure is shaped as
    ``{"mtime": float, "train_stations": [dict], "bus_stops": [dict]}``;
    older ``stops_cache.pkl`` files from before the migration are simply
    ignored (the loader falls through to re-parse) and removed.

    Called once per process; result is also kept in the lru_cache.
    """
    stops_file = GTFS_DIR / "stops.txt"
    if not stops_file.exists():
        raise FileNotFoundError(
            f"GTFS stops file not found at {stops_file}. "
            "Run `python fetch_gtfs.py` to download the data."
        )

    current_mtime: float = stops_file.stat().st_mtime

    # Clean up the legacy pickle artifact if a previous install left one
    # behind. We never read it (see SEC-005) — re-parsing the CSV is cheap.
    _legacy_pkl = GTFS_DIR / "stops_cache.pkl"
    if _legacy_pkl.exists():
        try:
            _legacy_pkl.unlink()
        except OSError:
            pass

    # Try the JSON cache first.
    if _STOPS_CACHE_PATH.exists():
        try:
            with _STOPS_CACHE_PATH.open("r", encoding="utf-8") as f:
                cached = json.load(f)
            if (
                isinstance(cached, dict)
                and cached.get("mtime") == current_mtime
                and isinstance(cached.get("train_stations"), list)
                and isinstance(cached.get("bus_stops"), list)
            ):
                return cached["train_stations"], cached["bus_stops"]
            # mtime mismatch or shape mismatch — fall through to re-parse.
        except Exception as exc:
            print(f"[gtfs_loader] Could not load stops cache (will re-parse): {exc}")

    train_stations: list[dict] = []
    bus_stops: list[dict] = []

    with open(stops_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                stop_id_int = int(row["stop_id"].strip())
                lat = float(row["stop_lat"].strip())
                lon = float(row["stop_lon"].strip())
            except (ValueError, KeyError):
                continue

            name = row.get("stop_name", "").strip()
            location_type = row.get("location_type", "0").strip()
            stop_id_str = str(stop_id_int)

            if 40000 <= stop_id_int <= 49999 and location_type == "1":
                train_stations.append({
                    "mapid": stop_id_str,
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "type": "train_station",
                })

            elif stop_id_int <= 29999 and location_type in ("0", ""):
                bus_stops.append({
                    "stop_id": stop_id_str,
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "type": "bus_stop",
                })

    # Persist the parsed result atomically so the next startup can skip CSV parsing.
    tmp = _STOPS_CACHE_PATH.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "mtime": current_mtime,
                    "train_stations": train_stations,
                    "bus_stops": bus_stops,
                },
                f,
            )
        tmp.replace(_STOPS_CACHE_PATH)
    except Exception as exc:
        print(f"[gtfs_loader] Could not save stops cache: {exc}")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

    return train_stations, bus_stops


# ---------------------------------------------------------------------------
# Spatial index for nearest-stop queries
# ---------------------------------------------------------------------------
#
# Cell size of ~1 mile in each axis means a 1.0-mile radius query touches
# at most a 3×3 block of cells (9 cells), regardless of catalog size.
# SpatialGrid from utils handles bucketing, bounding-box prefilter, and
# Haversine postfilter in one shared implementation.

_SPATIAL_CELL_LAT_DEG = 1.0 / 69.0    # ~1 mile of latitude
_SPATIAL_CELL_LON_DEG = 1.0 / 51.35   # ~1 mile of longitude at Chicago's latitude


@lru_cache(maxsize=2)
def _spatial_index(kind: str) -> SpatialGrid:
    """
    Build a SpatialGrid for either "train" or "bus" stops.
    Built once on first use and cached for the process lifetime.
    """
    train_stations, bus_stops = _load_stops()
    stops = train_stations if kind == "train" else bus_stops
    grid = SpatialGrid(cell_lat_deg=_SPATIAL_CELL_LAT_DEG, cell_lon_deg=_SPATIAL_CELL_LON_DEG)
    for s in stops:
        grid.add(s["lat"], s["lon"], s)
    return grid


def _candidates_within(
    kind: str,
    lat: float,
    lon: float,
    radius_miles: float,
) -> list[tuple[float, dict]]:
    """Return (distance_miles, stop) pairs for every stop of `kind` within radius_miles of (lat, lon)."""
    return _spatial_index(kind).query(lat, lon, radius_miles)


# ---------------------------------------------------------------------------
# Public lookup functions
# ---------------------------------------------------------------------------

def find_nearest_train_stations_progressive(
    lat: float,
    lon: float,
    rings: tuple[float, ...],
    max_results: int = 3,
    walk_to_station: bool = True,
) -> tuple[list[dict], float]:
    """
    Single-pass equivalent of calling find_nearest_train_stations() once per
    ring in `rings` and stopping at the first non-empty result (OPT-004).

    Runs the spatial-grid query once at the outermost ring, then partitions
    the hits client-side until a non-empty ring is found. Returns
    ``(stations, ring_radius_used)``; ``stations`` is empty when no station
    sits within ``rings[-1]`` miles.
    """
    if not rings:
        return [], 0.0
    max_radius = rings[-1]
    all_hits = _candidates_within("train", lat, lon, max_radius)
    if not all_hits:
        return [], max_radius

    selected: list[tuple[float, dict]] = []
    used_radius = max_radius
    for radius in rings:
        selected = [item for item in all_hits if item[0] <= radius]
        if selected:
            used_radius = radius
            break
    if not selected:
        return [], max_radius

    candidates = [
        {**s}
        for _, s in heapq.nsmallest(max_results, selected, key=lambda item: item[0])
    ]
    for s in candidates:
        if walk_to_station:
            s["walk_minutes"] = walk_minutes(lat, lon, s["lat"], s["lon"])
        else:
            s["walk_minutes"] = walk_minutes(s["lat"], s["lon"], lat, lon)
    candidates.sort(key=lambda s: s["walk_minutes"])
    return candidates, used_radius


def find_nearest_train_stations(
    lat: float,
    lon: float,
    max_distance_miles: float = 0.5,
    max_results: int = 3,
    walk_to_station: bool = True,
) -> list[dict]:
    """
    Return the closest train parent stations within walking distance,
    each annotated with real street-network walk_minutes.

    walk_to_station=True  (default): walk_minutes computed from (lat,lon) → station.
                                     Use for origin: user walks TO the station.
    walk_to_station=False:           walk_minutes computed from station → (lat,lon).
                                     Use for destination: user walks FROM the station.
    """
    hits = _candidates_within("train", lat, lon, max_distance_miles)
    candidates = [{**s} for _, s in heapq.nsmallest(max_results, hits, key=lambda item: item[0])]

    for s in candidates:
        if walk_to_station:
            s["walk_minutes"] = walk_minutes(lat, lon, s["lat"], s["lon"])
        else:
            s["walk_minutes"] = walk_minutes(s["lat"], s["lon"], lat, lon)

    return sorted(candidates, key=lambda s: s["walk_minutes"])


def find_nearest_bus_stops(
    lat: float,
    lon: float,
    max_distance_miles: float = 0.25,
    max_results: int = 5,
) -> list[dict]:
    """
    Return the closest bus stops within reach, each annotated with real
    street-network walk_minutes.  Probes the spatial index at the maximum
    radius once and partitions client-side by ring (0.25 → 0.5 → 0.75 → 1.0)
    so a sparse area still gets the "expand outward" behavior without
    re-querying the spatial index multiple times.
    """
    rings = [r for r in (0.25, 0.5, 0.75, 1.0) if r <= max_distance_miles]
    if not rings or rings[-1] < max_distance_miles:
        rings.append(max_distance_miles)
    max_radius = rings[-1]

    # One spatial query at the largest radius. The grid cost dominates over
    # the per-stop distance test we'll re-do in the partition step.
    all_hits = _candidates_within("bus", lat, lon, max_radius)
    if not all_hits:
        return []

    # Walk outward through the rings until we find at least one stop. This
    # preserves the original "prefer closest, expand only if empty" behaviour.
    hits: list[tuple[float, dict]] = []
    for radius in rings:
        hits = [item for item in all_hits if item[0] <= radius]
        if hits:
            break

    candidates = [{**s} for _, s in heapq.nsmallest(max_results, hits, key=lambda item: item[0])]

    for s in candidates:
        s["walk_minutes"] = walk_minutes(lat, lon, s["lat"], s["lon"])

    return sorted(candidates, key=lambda s: s["walk_minutes"])


@lru_cache(maxsize=1024)
def fuzzy_match_neighborhood(query: str) -> tuple[tuple[float, float] | None, str | None]:
    """Cached, NEIGHBORHOOD_COORDS-bound wrapper around the pure matcher in
    geocode_text.fuzzy_match_neighborhood. The cache lives here (not in
    geocode_text) so the underlying function stays decoupled from any
    specific coords dict — see geocode_text module docstring."""
    return _fuzzy_match_neighborhood(query, NEIGHBORHOOD_COORDS)


