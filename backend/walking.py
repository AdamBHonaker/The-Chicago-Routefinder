"""
Street-network walking time calculator using OSMnx + NetworkX.

The pedestrian street graph is loaded from the cached GraphML file produced
by fetch_street_graph.py. It is loaded once at startup and held in memory.

Walking speed assumption: 3 mph (1.34 m/s) — a comfortable pedestrian pace.

Key OSMnx 2.x notes:
  - ox.nearest_nodes(G, X=longitude, Y=latitude)  ← X is lon, Y is lat
  - graph_from_bbox bbox = (west, south, east, north)
  - Edge "length" attribute is in metres
"""

import threading
from functools import lru_cache
from pathlib import Path

import networkx as nx
import osmnx as ox

GRAPH_PATH = Path(__file__).parent / "street_graph.graphml"

WALKING_SPEED_MPS = 3.0 * 1609.34 / 3600  # 3 mph → metres per second ≈ 1.34 m/s

_LONG_BLOCK_METERS    = 201.17   # 1/8 mile = 660 ft — N-S numbered-address axis
_SHORT_BLOCK_METERS   = 100.58   # 1/16 mile = 330 ft — E-W cross streets
_BLOCK_TYPE_THRESHOLD = 150.0    # midpoint; ≥ threshold → long block

_DIRECTION_FULL = {
    "N":  "North",     "NE": "Northeast", "E":  "East",      "SE": "Southeast",
    "S":  "South",     "SW": "Southwest", "W":  "West",      "NW": "Northwest",
}


_graph_lock = threading.Lock()
_graph_cache: "nx.MultiDiGraph | None" = None


def _load_graph() -> "nx.MultiDiGraph":
    """Load street graph once; subsequent calls return the cached instance."""
    global _graph_cache
    if _graph_cache is not None:
        return _graph_cache
    with _graph_lock:
        if _graph_cache is not None:
            return _graph_cache
        if not GRAPH_PATH.exists():
            raise FileNotFoundError(
                f"Street graph not found at {GRAPH_PATH}. "
                "Run `python fetch_street_graph.py` to download it."
            )
        print(f"[walking] Loading street graph from {GRAPH_PATH} ...")
        G = ox.load_graphml(GRAPH_PATH)
        print(f"[walking] Graph loaded: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
        _graph_cache = G
    return _graph_cache


@lru_cache(maxsize=512)
def walk_minutes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> float:  # lru_cache safe — float is immutable
    """
    Return the estimated walking time in minutes between two lat/lon points,
    routed along the real pedestrian street network.

    Falls back to a straight-line Haversine estimate if routing fails
    (e.g., a point falls outside the graph's bounding box).
    """
    try:
        G = _load_graph()

        # OSMnx convention: X = longitude, Y = latitude
        origin_node = ox.nearest_nodes(G, X=origin_lon, Y=origin_lat)
        dest_node   = ox.nearest_nodes(G, X=dest_lon,   Y=dest_lat)

        length_m = nx.shortest_path_length(G, origin_node, dest_node, weight="length")
        return round(length_m / WALKING_SPEED_MPS / 60, 1)

    except Exception:
        # Graceful fallback to straight-line estimate
        return _haversine_walk_minutes(origin_lat, origin_lon, dest_lat, dest_lon)


@lru_cache(maxsize=512)
def walk_directions(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> list[dict]:  # lru_cache returns the same list object on hits — callers must NOT mutate
    """
    Return turn-by-turn walking directions as a list of steps:
      [{"street": "Broadway", "direction": "S", "minutes": 1.2}, ...]

    Each step represents a continuous segment along a named street.
    Consecutive edges with the same street name are merged into one step.
    Direction is the cardinal bearing (N/NE/E/SE/S/SW/W/NW) from the start
    to the end of that segment.

    Falls back to a single unnamed step if routing fails.
    """
    import math

    def _cardinal(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        deg = math.degrees(math.atan2(dlon, dlat)) % 360
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return dirs[round(deg / 45) % 8]

    def _street_name(data: dict) -> str:
        name = data.get("name", "")
        if isinstance(name, list):
            name = name[0] if name else ""
        name = (name or "").strip()
        return name if name else "unnamed path"

    try:
        G = _load_graph()
        origin_node = ox.nearest_nodes(G, X=origin_lon, Y=origin_lat)
        dest_node   = ox.nearest_nodes(G, X=dest_lon,   Y=dest_lat)
        node_ids    = nx.shortest_path(G, origin_node, dest_node, weight="length")

        if len(node_ids) < 2:
            return []

        # Build flat list of (name, length_m, from_node, to_node) per edge
        raw: list[tuple[str, float, int, int]] = []
        for u, v in zip(node_ids, node_ids[1:]):
            # MultiDiGraph — pick the shortest parallel edge
            edge_data = min(G[u][v].values(), key=lambda d: d.get("length", float("inf")))
            raw.append((_street_name(edge_data), edge_data.get("length", 0.0), u, v))

        # Group consecutive edges by street name
        steps: list[dict] = []
        i = 0
        while i < len(raw):
            name = raw[i][0]
            total_length = 0.0
            edge_count   = 0
            start_node   = raw[i][2]
            end_node     = raw[i][3]
            while i < len(raw) and raw[i][0] == name:
                total_length += raw[i][1]
                edge_count   += 1
                end_node = raw[i][3]
                i += 1
            lat1 = G.nodes[start_node]["y"]
            lon1 = G.nodes[start_node]["x"]
            lat2 = G.nodes[end_node]["y"]
            lon2 = G.nodes[end_node]["x"]
            minutes = round(total_length / WALKING_SPEED_MPS / 60, 1)
            direction_abbrev = _cardinal(lat1, lon1, lat2, lon2)
            avg_edge_m = total_length / edge_count
            is_long    = avg_edge_m >= _BLOCK_TYPE_THRESHOLD
            block_m    = _LONG_BLOCK_METERS if is_long else _SHORT_BLOCK_METERS
            blocks     = max(0.5, round(total_length / block_m * 2) / 2)
            block_type = "long" if is_long else "short"
            steps.append({
                "street":         name,
                "direction":      direction_abbrev,
                "direction_full": _DIRECTION_FULL.get(direction_abbrev, direction_abbrev),
                "blocks":         blocks,
                "block_type":     block_type,
                "minutes":        minutes,
            })
        return steps

    except Exception:
        total_min = _haversine_walk_minutes(origin_lat, origin_lon, dest_lat, dest_lon)
        fallback_meters = total_min * 60 * WALKING_SPEED_MPS
        # Default to "long" (N-S numbered-address axis) — the fallback total
        # distance is the full trip, not a per-edge average, so the old threshold
        # comparison produced wrong classifications for any walk >= 150 m.
        fallback_blocks = max(0.5, round(fallback_meters / _LONG_BLOCK_METERS * 2) / 2)
        return [{"street": "Walk", "direction": "", "direction_full": "", "blocks": fallback_blocks, "block_type": "long", "minutes": total_min}]


@lru_cache(maxsize=512)
def walk_path(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> list[list[float]]:  # lru_cache returns the same list object on hits — callers must NOT mutate
    """
    Return the street-network path between two lat/lon points as [[lat, lon], ...].

    For each edge in the shortest path, the edge's Shapely geometry is used when
    present (curved / diagonal streets like Milwaukee Ave, Lake Shore Drive, etc.).
    Straight city-grid segments fall back to start/end node coordinates.  This
    ensures the drawn path follows actual street centrelines and never cuts through
    buildings.

    Falls back to a straight line [[origin_lat, origin_lon], [dest_lat, dest_lon]]
    if routing fails (e.g., a point falls outside the graph's bounding box).
    """
    try:
        G = _load_graph()

        origin_node = ox.nearest_nodes(G, X=origin_lon, Y=origin_lat)
        dest_node   = ox.nearest_nodes(G, X=dest_lon,   Y=dest_lat)

        node_ids = nx.shortest_path(G, origin_node, dest_node, weight="length")

        if len(node_ids) < 2:
            return [[origin_lat, origin_lon], [dest_lat, dest_lon]]

        coords: list[list[float]] = []

        for u, v in zip(node_ids, node_ids[1:]):
            # MultiDiGraph — pick the shortest parallel edge
            edge_data = min(G[u][v].values(), key=lambda d: d.get("length", float("inf")))

            if "geometry" in edge_data:
                # Shapely stores coords as (lon, lat); convert to [lat, lon].
                geom = list(edge_data["geometry"].coords)
                # OSMnx geometry direction should match u→v, but verify and
                # reverse if needed (compare first geom point to node u).
                u_lon, u_lat = G.nodes[u]["x"], G.nodes[u]["y"]
                if geom:
                    du_start = (geom[0][0] - u_lon)**2 + (geom[0][1] - u_lat)**2
                    du_end   = (geom[-1][0] - u_lon)**2 + (geom[-1][1] - u_lat)**2
                    if du_start > du_end:
                        geom = geom[::-1]
                # Skip the first coord if it duplicates the last one we added.
                start = 1 if coords and [geom[0][1], geom[0][0]] == coords[-1] else 0
                for lon, lat in geom[start:]:
                    coords.append([lat, lon])
            else:
                # Straight segment — just use the node endpoints.
                if not coords:
                    coords.append([G.nodes[u]["y"], G.nodes[u]["x"]])
                coords.append([G.nodes[v]["y"], G.nodes[v]["x"]])

        return coords

    except Exception as e:
        print(f"[walk_path] routing failed: {type(e).__name__}: {e}")
        return [[origin_lat, origin_lon], [dest_lat, dest_lon]]


def _haversine_walk_minutes(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Straight-line walking time estimate — used as fallback only."""
    import math
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    a = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    miles = R * 2 * math.asin(math.sqrt(a))
    return round(miles / 3.0 * 60, 1)  # 3 mph walking
