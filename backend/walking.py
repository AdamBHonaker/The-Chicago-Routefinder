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
