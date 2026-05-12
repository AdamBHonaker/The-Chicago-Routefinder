"""
Street-network walking time calculator using igraph + scipy.

The pedestrian street graph is loaded from the pre-built igraph artifact
(street_graph_igraph.pkl) produced by fetch_street_graph.py, or falls back
to parsing street_graph.graphml via igraph directly.

Walking speed assumption: 3 mph (1.34 m/s) — a comfortable pedestrian pace.
"""

import gc
import hashlib
import math
import pickle
import threading
import time
from functools import lru_cache
from pathlib import Path

import igraph as ig
import numpy as np
from scipy.spatial import cKDTree

from utils import haversine_miles as _haversine_miles
import config as _cfg

GRAPH_PATH  = Path(__file__).parent / "street_graph.graphml"
IGRAPH_PATH = Path(__file__).parent / "street_graph_igraph.pkl"
# Sidecar produced at Docker build time (see backend/Dockerfile) containing the
# SHA-256 of IGRAPH_PATH at the moment it was downloaded from GitHub Releases.
# Verified before pickle.load() so any post-build tampering with the file is
# caught before an unsafe deserialization runs.
IGRAPH_SHA256_PATH = IGRAPH_PATH.with_suffix(IGRAPH_PATH.suffix + ".sha256")


def _verify_igraph_sha256() -> bool:
    """Return True if IGRAPH_PATH matches the build-time hash, or if no
    manifest exists (e.g. local dev without Docker build). Returns False only
    when the manifest exists and disagrees — in that case the file has been
    tampered with after build and must not be unpickled."""
    if not IGRAPH_SHA256_PATH.exists():
        return True
    try:
        expected = IGRAPH_SHA256_PATH.read_text().strip().split()[0].lower()
    except Exception:
        return True  # unreadable manifest — fall through to load (and other errors)
    h = hashlib.sha256()
    with open(IGRAPH_PATH, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().lower() == expected

# Sourced from config.py — edit there to tune walking behaviour.
WALKING_SPEED_MPS     = _cfg.WALKING_SPEED_MPS        # metres per second ≈ 1.34
_LONG_BLOCK_METERS    = _cfg.LONG_BLOCK_METERS         # 1/8 mile = 660 ft
_SHORT_BLOCK_METERS   = _cfg.SHORT_BLOCK_METERS        # 1/16 mile = 330 ft
_BLOCK_TYPE_THRESHOLD = _cfg.BLOCK_TYPE_THRESHOLD_METERS  # midpoint; ≥ → long block

_DIRECTION_FULL = {
    "N":  "North",     "NE": "Northeast", "E":  "East",      "SE": "Southeast",
    "S":  "South",     "SW": "Southwest", "W":  "West",      "NW": "Northwest",
}


_graph_lock: threading.Lock = threading.Lock()
_graph_cache: "ig.Graph | None" = None
_coord_kdtree: "cKDTree | None" = None
_vertex_lats: "np.ndarray | None" = None
_vertex_lons: "np.ndarray | None" = None
_edge_lengths: "np.ndarray | None" = None
_graph_load_failed: bool = False
_lcc_vertex_ids: "np.ndarray | None" = None

# Idle-eviction TTL sourced from config.py; set WALK_GRAPH_EVICT_TTL_S=0 to disable.
WALK_GRAPH_EVICT_TTL_S: int = _cfg.WALK_GRAPH_EVICT_TTL_S
_EVICT_CHECK_INTERVAL_S: int = 60  # how often the background thread wakes to check
_last_walk_time: float = 0.0       # monotonic timestamp of the most recent walk call


def _touch_walk_time() -> None:
    """Record that a walk function was just called; resets the idle-eviction clock."""
    global _last_walk_time
    _last_walk_time = time.monotonic()


def _graph_eviction_worker() -> None:
    """Daemon thread: evict the street graph after WALK_GRAPH_EVICT_TTL_S idle seconds."""
    global _graph_cache, _coord_kdtree, _vertex_lats, _vertex_lons, _edge_lengths, _lcc_vertex_ids, _graph_load_failed
    while True:
        time.sleep(_EVICT_CHECK_INTERVAL_S)
        if WALK_GRAPH_EVICT_TTL_S <= 0:
            continue
        with _graph_lock:
            if _graph_cache is None:
                continue
            idle = time.monotonic() - _last_walk_time
            if idle < WALK_GRAPH_EVICT_TTL_S:
                continue
            _graph_cache = None
            _coord_kdtree = None
            _vertex_lats = None
            _vertex_lons = None
            _edge_lengths = None
            _lcc_vertex_ids = None
            _graph_load_failed = False
            print(f"[walking] Graph evicted after {idle:.0f}s idle — will reload on next request")
        gc.collect()


threading.Thread(
    target=_graph_eviction_worker, daemon=True, name="walk-graph-evictor"
).start()

# Coordinate snap precision for cache keys. 5 decimals ≈ 1.1 m at Chicago's
# latitude — well below the precision GTFS / geocoded coords need to land on
# the same nearest-node. Snapping at the cache boundary collapses near-identical
# inputs (e.g. 41.87901 vs 41.87902) onto a single cache entry, turning the
# raw-float caches that previously almost never hit into effective ones.
_COORD_SNAP_DECIMALS: int = 5
# Coordinate precision for walk_path output. 5 decimals ≈ 1.1 m at Chicago's
# latitude — well below the visual resolution of any zoom level used in the UI,
# and consistent with transit_graph._SHAPE_COORD_DECIMALS.
_WALK_COORD_DECIMALS: int = 5


def _snap(v: float) -> float:
    return round(v, _COORD_SNAP_DECIMALS)


# ---------------------------------------------------------------------------
# Module-level helpers (moved out of cached inner functions)
# ---------------------------------------------------------------------------

def _cardinal(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    dlat = lat2 - lat1
    # Scale longitude by cos(mean latitude) so equal real-world east/north
    # distances produce equal planar deltas — without this, Chicago's ~42°N
    # latitude over-weights east/west by ~25 % and biases the bearing.
    dlon = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    deg = math.degrees(math.atan2(dlon, dlat)) % 360
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[round(deg / 45) % 8]


def _clean_name(raw_name) -> str:
    """Return the street name, or "" if the edge has no name."""
    name = raw_name
    if isinstance(name, list):
        name = name[0] if name else ""
    if not isinstance(name, str):
        return ""
    return name.strip()


# Maps OSM highway tag (+ optional footway subtag) → display path-type token.
_HIGHWAY_PATH_TYPE: dict[str, str] = {
    "crossing":   "crosswalk",
    "footway":    "footway",
    "path":       "path",
    "steps":      "steps",
    "pedestrian": "pedestrian",
    "cycleway":   "path",
    "track":      "path",
}

def _highway_path_type(highway, footway="") -> str:
    """Map OSM highway (+ footway subtag) to a display path-type string."""
    if isinstance(highway, list):
        highway = highway[0] if highway else ""
    if isinstance(footway, list):
        footway = footway[0] if footway else ""
    highway = (highway or "").strip()
    footway = (footway or "").strip()
    if highway == "crossing" or footway == "crossing":
        return "crosswalk"
    return _HIGHWAY_PATH_TYPE.get(highway, "")


def _make_step(
    name: str,
    path_type: str,
    total_length: float,
    edge_count: int,
    start_vertex: int,
    end_vertex: int,
) -> dict:
    lat1 = _vertex_lats[start_vertex]
    lon1 = _vertex_lons[start_vertex]
    lat2 = _vertex_lats[end_vertex]
    lon2 = _vertex_lons[end_vertex]
    minutes = round(total_length / WALKING_SPEED_MPS / 60, 1)
    direction_abbrev = _cardinal(lat1, lon1, lat2, lon2)
    avg_edge_m = total_length / edge_count
    is_long    = avg_edge_m >= _BLOCK_TYPE_THRESHOLD
    block_m    = _LONG_BLOCK_METERS if is_long else _SHORT_BLOCK_METERS
    blocks     = max(0.5, round(total_length / block_m * 2) / 2)
    block_type = "long" if is_long else "short"
    return {
        "street":         name,
        "path_type":      path_type,
        "direction":      direction_abbrev,
        "direction_full": _DIRECTION_FULL.get(direction_abbrev, direction_abbrev),
        "blocks":         blocks,
        "block_type":     block_type,
        "minutes":        minutes,
        "start_lat":      lat1,
        "start_lon":      lon1,
    }


# ---------------------------------------------------------------------------
# Graph loading
# ---------------------------------------------------------------------------

def _parse_geometry_inplace(G: ig.Graph) -> None:
    """Convert geometry WKT strings to coordinate lists [(lon, lat), ...] in-place."""
    try:
        from shapely import wkt as shapely_wkt
        for e in G.es:
            geom = e["geometry"]
            if isinstance(geom, str) and geom:
                try:
                    e["geometry"] = list(shapely_wkt.loads(geom).coords)
                except Exception:
                    e["geometry"] = None
            elif not geom:
                e["geometry"] = None
    except ImportError:
        # shapely not available — walk_path will degrade gracefully
        for e in G.es:
            e["geometry"] = None


def _load_graph() -> "ig.Graph | None":
    """Load street graph once; returns None (and never retries) if unavailable."""
    global _graph_cache, _coord_kdtree, _vertex_lats, _vertex_lons, _edge_lengths, _graph_load_failed, _lcc_vertex_ids

    if _graph_cache is not None:
        return _graph_cache
    if _graph_load_failed:
        return None

    with _graph_lock:
        if _graph_cache is not None:
            return _graph_cache
        if _graph_load_failed:
            return None

        G: "ig.Graph | None" = None

        # 1. Try pre-built igraph pickle (OPT-008c artifact — fast load, no parsing)
        if IGRAPH_PATH.exists():
            if not _verify_igraph_sha256():
                print(
                    f"[walking] SECURITY: {IGRAPH_PATH.name} hash does NOT match the "
                    f"build-time manifest. Refusing to deserialize a potentially "
                    f"tampered pickle. Falling back to the graphml parser."
                )
                G = None
            else:
                print(f"[walking] Loading igraph artifact from {IGRAPH_PATH} ...")
                try:
                    with open(IGRAPH_PATH, "rb") as f:
                        data = pickle.load(f)
                    G = data["graph"]
                    print(f"[walking] igraph loaded: {G.vcount():,} vertices, {G.ecount():,} edges")
                except Exception as e:
                    print(f"[walking] igraph pickle failed ({type(e).__name__}: {e}) — trying graphml fallback")
                    G = None

        # 2. Fallback: parse graphml directly with igraph
        if G is None:
            if not GRAPH_PATH.exists():
                print(f"[walking] Street graph not found at {GRAPH_PATH} — walking will use Haversine fallback.")
                _graph_load_failed = True
                return None
            print(f"[walking] Loading street graph from {GRAPH_PATH} ...")
            try:
                G = ig.Graph.Read_GraphML(str(GRAPH_PATH))
                _parse_geometry_inplace(G)
                print(f"[walking] igraph loaded: {G.vcount():,} vertices, {G.ecount():,} edges")
            except Exception as e:
                print(f"[walking] Failed to load street graph ({type(e).__name__}: {e}) — walking will use Haversine fallback.")
                _graph_load_failed = True
                return None

        # Build coordinate arrays and spatial index — set before _graph_cache so any
        # thread that sees _graph_cache is not None also sees fully-initialized state.
        # Wrapped in try/except so a corrupt pickle (e.g., missing "x"/"y" vertex
        # attributes) sets _graph_load_failed and stops retrying instead of raising
        # KeyError on every routing request (BUG-009).
        #
        # Service/alley edge filtering and directed→undirected conversion are now
        # done at build time inside fetch_street_graph._save_igraph_artifact(), so
        # the pkl arrives already undirected with those edges removed.  The
        # is_directed() guard below is kept as a backward-compat safety net for old
        # pkls or the graphml fallback path.
        if G.is_directed():
            try:
                pre_e = G.ecount()
                combine = {"length": "min"}
                # Preserve other attributes by taking the first instance — the
                # two opposing directed edges share name/highway/footway, and
                # geometry direction is auto-corrected in _walk_path_impl.
                for attr in ("name", "highway", "footway", "geometry"):
                    if attr in G.es.attributes():
                        combine[attr] = "first"
                G.to_undirected(mode="collapse", combine_edges=combine)
                print(f"[walking] Converted to undirected: {pre_e:,} → {G.ecount():,} edges")
            except Exception as und_err:
                print(f"[walking] to_undirected skipped ({type(und_err).__name__}: {und_err}) — directed routing in use")

        try:
            # Bulk attribute access — G.vs["x"] and G.vs["y"] each return a list
            # in one C call, far cheaper than per-vertex dict lookup.
            lons = np.asarray(G.vs["x"], dtype=np.float64)
            lats = np.asarray(G.vs["y"], dtype=np.float64)
            _vertex_lats = lats
            _vertex_lons = lons

            # Precompute edge lengths once; None lengths become 0.0
            raw_lengths = G.es["length"]
            _edge_lengths = np.fromiter(
                (l if l is not None else 0.0 for l in raw_lengths),
                dtype=np.float64,
                count=len(raw_lengths),
            )

            # Restrict spatial index to the largest weakly-connected component so that
            # _get_nearest_node never returns a vertex unreachable from the rest of the
            # graph — the root cause of "path unavailable" errors when a geocoded point
            # snaps to a disconnected peripheral vertex.
            try:
                comps = G.clusters(mode="WEAK")
            except AttributeError:
                comps = G.connected_components(mode="weak")
            lcc_ids = np.array(max(comps, key=len), dtype=np.int64)
            _lcc_vertex_ids = lcc_ids
            _coord_kdtree = cKDTree(np.column_stack([lons[lcc_ids], lats[lcc_ids]]))
            if len(lcc_ids) < G.vcount():
                print(f"[walking] LCC: {len(lcc_ids):,}/{G.vcount():,} vertices in main component")
            _graph_cache = G
        except Exception as e:
            print(f"[walking] Failed to build coordinate arrays ({type(e).__name__}: {e}) — walking will use Haversine fallback.")
            _graph_load_failed = True
            return None

    return _graph_cache


def _get_nearest_node(lat: float, lon: float) -> "int | None":
    """Return the nearest LCC vertex index; None if graph unavailable or point is >1 km from any vertex."""
    return _get_nearest_node_cached(_snap(lat), _snap(lon))


@lru_cache(maxsize=2048)
def _get_nearest_node_cached(lat: float, lon: float) -> "int | None":
    if _load_graph() is None:
        return None
    try:
        _, kdtree_idx = _coord_kdtree.query([lon, lat])
        graph_idx = int(_lcc_vertex_ids[kdtree_idx])
        # Flat-earth proximity check — avoids haversine trig for the 1 km threshold.
        # Accurate to ~0.1 % at Chicago's latitude; sub-meter error at the boundary.
        dlat = lat - _vertex_lats[graph_idx]
        dlon = (lon - _vertex_lons[graph_idx]) * math.cos(math.radians(lat))
        if 111320.0 * math.sqrt(dlat * dlat + dlon * dlon) > 1000.0:
            return None
        return graph_idx
    except Exception:
        return None


def _get_shortest_path(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> "tuple[tuple[int, ...], tuple[int, ...]] | None":
    """
    Compute and cache the shortest path between two lat/lon coordinates.

    Returns (vpath, epath) — tuples of vertex indices and edge indices — or None
    if the graph is unavailable or routing fails. All three public routing functions
    share this cache so the expensive Dijkstra run happens at most once per unique
    origin/destination pair per process lifetime.
    """
    return _get_shortest_path_cached(
        _snap(origin_lat), _snap(origin_lon),
        _snap(dest_lat),   _snap(dest_lon),
    )


@lru_cache(maxsize=512)
def _get_shortest_path_cached(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> "tuple[tuple[int, ...], tuple[int, ...]] | None":
    G = _load_graph()
    if G is None:
        return None
    orig_idx = _get_nearest_node(origin_lat, origin_lon)
    dest_idx = _get_nearest_node(dest_lat, dest_lon)
    if orig_idx is None or dest_idx is None:
        return None
    n = G.vcount()
    if orig_idx >= n or dest_idx >= n:
        return None
    try:
        result = G.get_shortest_paths(orig_idx, to=dest_idx, weights="length", output="epath")
        if not result or not result[0]:
            return None
        epath = result[0]
        # Reconstruct vpath from epath; handles both directed and undirected graphs.
        vpath = [orig_idx]
        for eid in epath:
            e = G.es[eid]
            nxt = e.target if e.source == vpath[-1] else e.source
            vpath.append(nxt)
        return (tuple(vpath), tuple(epath))
    except Exception:
        return None


def walk_minutes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> float:
    """
    Return the estimated walking time in minutes between two lat/lon points,
    routed along the real pedestrian street network.

    Falls back to a straight-line Haversine estimate if routing fails
    (e.g., a point falls outside the graph's bounding box).

    No lru_cache wrapper — _get_shortest_path is already cached at the
    Dijkstra level, and the post-processing (one numpy sum) is cheaper than
    the cache bookkeeping for a 256-entry float-keyed dict.
    """
    _touch_walk_time()
    try:
        path = _get_shortest_path(origin_lat, origin_lon, dest_lat, dest_lon)
        if path is None:
            raise RuntimeError("path unavailable")

        _, epath = path
        length_m = float(_edge_lengths[list(epath)].sum())
        return max(0.1, round(length_m / WALKING_SPEED_MPS / 60, 1))

    except Exception:
        return _haversine_walk_minutes(origin_lat, origin_lon, dest_lat, dest_lon)


def _walk_directions_impl(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> tuple:
    """Cached implementation for walk_directions — returns a tuple so the cache holds immutable data."""
    try:
        path = _get_shortest_path(origin_lat, origin_lon, dest_lat, dest_lon)
        if path is None:
            raise RuntimeError("path unavailable")

        if _vertex_lats is None or _vertex_lons is None:
            raise RuntimeError("vertex coordinate arrays unavailable")

        G = _graph_cache  # safe: path is not None implies graph is loaded
        vpath, epath = path

        if len(vpath) < 2:
            return ()

        # Bulk-fetch attribute lists once instead of allocating a fresh dict
        # per edge inside the loop (OPT-BE-221). Each G.es[<attr>] is a single
        # C-level call returning the full edge-attribute array; indexing by
        # eid is then a plain list lookup. For a 100-edge walk this avoids
        # building 100 throwaway attribute dicts.
        edge_attrs = set(G.es.attributes()) if G.ecount() > 0 else set()
        edge_names     = G.es["name"]     if "name"     in edge_attrs else None
        edge_highways  = G.es["highway"]  if "highway"  in edge_attrs else None
        edge_footways  = G.es["footway"]  if "footway"  in edge_attrs else None

        # Single-pass grouping of consecutive edges by (name, path_type).
        # Named edges group by name; unnamed edges group by OSM highway type
        # so a crosswalk and a footway are always separate steps.
        steps: list[dict] = []
        current_key:       "tuple | None" = None
        current_name:      str  = ""
        current_path_type: str  = ""
        total_length = 0.0
        edge_count   = 0
        start_vertex = 0
        end_vertex   = 0

        for eid, u, v in zip(epath, vpath, vpath[1:]):
            name = _clean_name(edge_names[eid]) if edge_names is not None else ""
            hw   = (edge_highways[eid] if edge_highways is not None else "") or ""
            fw   = (edge_footways[eid] if edge_footways is not None else "") or ""
            path_type = _highway_path_type(hw, fw)
            # Named segments group by name; unnamed group by path_type token.
            group_key = (name, "") if name else ("", path_type or "__unnamed__")
            length = _edge_lengths[eid]
            if group_key == current_key:
                total_length += length
                edge_count   += 1
                end_vertex    = v
            else:
                if current_key is not None:
                    steps.append(_make_step(current_name, current_path_type, total_length, edge_count, start_vertex, end_vertex))
                current_key       = group_key
                current_name      = name
                current_path_type = path_type
                total_length      = length
                edge_count        = 1
                start_vertex      = u
                end_vertex        = v

        if current_key is not None:
            steps.append(_make_step(current_name, current_path_type, total_length, edge_count, start_vertex, end_vertex))

        return tuple(steps)

    except Exception:
        total_min = _haversine_walk_minutes(origin_lat, origin_lon, dest_lat, dest_lon)
        fallback_meters = total_min * 60 * WALKING_SPEED_MPS
        fallback_blocks = max(0.5, round(fallback_meters / _LONG_BLOCK_METERS * 2) / 2)
        return ({"street": "", "path_type": "", "direction": "", "direction_full": "", "blocks": fallback_blocks, "block_type": "long", "minutes": total_min, "start_lat": origin_lat, "start_lon": origin_lon},)


_WALK_DIRECTIONS_MAX_STEPS = 15


def walk_directions(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> list[dict]:
    """
    Return turn-by-turn walking directions as a list of steps (capped at 15).
      [{"street": "Broadway", "direction": "S", "minutes": 1.2}, ...]

    Each step represents a continuous segment along a named street.
    Consecutive edges with the same street name are merged into one step.
    Direction is the cardinal bearing (N/NE/E/SE/S/SW/W/NW) from the start
    to the end of that segment.

    Falls back to a single unnamed step if routing fails.
    Returns a fresh list on every call (safe to mutate).
    """
    _touch_walk_time()
    steps = _walk_directions_impl(origin_lat, origin_lon, dest_lat, dest_lon)
    return list(steps[:_WALK_DIRECTIONS_MAX_STEPS])


def _walk_path_impl(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> tuple:
    """
    Cached implementation for walk_path.

    Returns a tuple of (lat, lon) tuples so the cache holds fully immutable data.
    The public walk_path wrapper converts each point back to [lat, lon] lists.
    """
    try:
        G = _load_graph()
        if G is None:
            raise RuntimeError("street graph unavailable")

        path = _get_shortest_path(origin_lat, origin_lon, dest_lat, dest_lon)
        if path is None:
            raise RuntimeError("path unavailable")

        if _vertex_lats is None or _vertex_lons is None:
            raise RuntimeError("vertex coordinate arrays unavailable")

        vpath, epath = path

        if len(vpath) < 2:
            return ((origin_lat, origin_lon), (dest_lat, dest_lon))

        result_coords: list[tuple[float, float]] = []

        for eid, u, v in zip(epath, vpath, vpath[1:]):
            # geometry is stored as [(lon, lat), ...] list (None if absent)
            geom_coords = G.es[eid]["geometry"]

            if geom_coords:
                u_lon = _vertex_lons[u]
                u_lat = _vertex_lats[u]
                # Verify/correct direction so coords flow u→v
                du_start = (geom_coords[0][0] - u_lon)**2 + (geom_coords[0][1] - u_lat)**2
                du_end   = (geom_coords[-1][0] - u_lon)**2 + (geom_coords[-1][1] - u_lat)**2
                if du_start > du_end:
                    # Reversed — derive effective first coord without copying the list
                    first_coord = geom_coords[-1]
                    ordered = reversed(geom_coords)
                else:
                    first_coord = geom_coords[0]
                    ordered = iter(geom_coords)
                # Skip first coord if it duplicates the last accumulated point
                if result_coords and (first_coord[1], first_coord[0]) == result_coords[-1]:
                    next(ordered)
                for lon, lat in ordered:
                    result_coords.append((lat, lon))
            else:
                # Straight segment — use node endpoints
                if not result_coords:
                    result_coords.append((_vertex_lats[u], _vertex_lons[u]))
                result_coords.append((_vertex_lats[v], _vertex_lons[v]))

        return tuple(result_coords)

    except Exception as e:
        print(f"[walk_path] routing failed for ({origin_lat:.6f},{origin_lon:.6f})→({dest_lat:.6f},{dest_lon:.6f}): {type(e).__name__}: {e}")
        return ((origin_lat, origin_lon), (dest_lat, dest_lon))


def walk_path(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> list[list[float]]:
    """
    Return the street-network path between two lat/lon points as [[lat, lon], ...].

    For each edge in the shortest path, the edge's geometry is used when present
    (curved / diagonal streets like Milwaukee Ave, Lake Shore Drive, etc.).
    Straight city-grid segments fall back to start/end node coordinates.  This
    ensures the drawn path follows actual street centrelines and never cuts through
    buildings.

    Falls back to a straight line [[origin_lat, origin_lon], [dest_lat, dest_lon]]
    if routing fails (e.g., a point falls outside the graph's bounding box).
    Returns a fresh list on every call (safe to mutate).
    """
    _touch_walk_time()
    return [
        [round(lat, _WALK_COORD_DECIMALS), round(lon, _WALK_COORD_DECIMALS)]
        for lat, lon in _walk_path_impl(origin_lat, origin_lon, dest_lat, dest_lon)
    ]


def walk_all(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> tuple[float, list[dict], list[list[float]]]:
    """Return (minutes, directions, path_points) in one call.

    Calling the three public functions sequentially in a single thread ensures
    _get_shortest_path() is computed at most once (its lru_cache is populated on
    the first call) rather than racing across three concurrent executor threads
    before any of them can cache the result.
    """
    minutes    = walk_minutes(origin_lat, origin_lon, dest_lat, dest_lon)
    directions = walk_directions(origin_lat, origin_lon, dest_lat, dest_lon)
    path       = walk_path(origin_lat, origin_lon, dest_lat, dest_lon)
    return minutes, directions, path


def _haversine_walk_minutes(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Straight-line walking time estimate — used as fallback only."""
    return round(_haversine_miles(lat1, lon1, lat2, lon2) / _cfg.WALKING_SPEED_MPH * 60, 1)
