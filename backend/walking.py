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

from functools import lru_cache
from pathlib import Path

import networkx as nx
import osmnx as ox

GRAPH_PATH = Path(__file__).parent / "street_graph.graphml"

WALKING_SPEED_MPS = 3.0 * 1609.34 / 3600  # 3 mph → metres per second ≈ 1.34 m/s


@lru_cache(maxsize=1)
def _load_graph():
    """
    Load the cached street graph. Cached after first call — subsequent
    requests reuse the in-memory graph with no disk or network I/O.
    """
    if not GRAPH_PATH.exists():
        raise FileNotFoundError(
            f"Street graph not found at {GRAPH_PATH}. "
            "Run `python fetch_street_graph.py` to download it."
        )
    print(f"[walking] Loading street graph from {GRAPH_PATH} ...")
    G = ox.load_graphml(GRAPH_PATH)
    print(f"[walking] Graph loaded: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
    return G


@lru_cache(maxsize=512)
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
) -> list[dict]:
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
            edge_data = min(G[u][v].values(), key=lambda d: d.get("length", 0))
            raw.append((_street_name(edge_data), edge_data.get("length", 0.0), u, v))

        # Group consecutive edges by street name
        steps: list[dict] = []
        i = 0
        while i < len(raw):
            name = raw[i][0]
            total_length = 0.0
            start_node   = raw[i][2]
            end_node     = raw[i][3]
            while i < len(raw) and raw[i][0] == name:
                total_length += raw[i][1]
                end_node = raw[i][3]
                i += 1
            lat1 = G.nodes[start_node]["y"]
            lon1 = G.nodes[start_node]["x"]
            lat2 = G.nodes[end_node]["y"]
            lon2 = G.nodes[end_node]["x"]
            minutes = round(total_length / WALKING_SPEED_MPS / 60, 1)
            steps.append({
                "street":    name,
                "direction": _cardinal(lat1, lon1, lat2, lon2),
                "minutes":   minutes,
            })
        return steps

    except Exception:
        total_min = _haversine_walk_minutes(origin_lat, origin_lon, dest_lat, dest_lon)
        return [{"street": "Walk", "direction": "", "minutes": total_min}]


@lru_cache(maxsize=512)
def walk_path(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> list[list[float]]:
    """
    Return the street-network path between two lat/lon points as [[lat, lon], ...].

    Node coordinates are read from G.nodes[n]['y'] (lat) and G.nodes[n]['x'] (lon),
    which is OSMnx's standard attribute naming.

    Falls back to a straight line [[origin_lat, origin_lon], [dest_lat, dest_lon]]
    if routing fails (e.g., a point falls outside the graph's bounding box) —
    same fallback strategy as walk_minutes().
    """
    try:
        G = _load_graph()

        origin_node = ox.nearest_nodes(G, X=origin_lon, Y=origin_lat)
        dest_node   = ox.nearest_nodes(G, X=dest_lon,   Y=dest_lat)

        node_ids = nx.shortest_path(G, origin_node, dest_node, weight="length")
        return [[G.nodes[n]["y"], G.nodes[n]["x"]] for n in node_ids]

    except Exception:
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
