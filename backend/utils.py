"""
Shared utility functions and constants for the CTA Transit backend.
"""

import math
from typing import Any
from zoneinfo import ZoneInfo

# Canonical Chicago timezone — import this rather than constructing ZoneInfo("America/Chicago")
# inline across modules.
CHICAGO_TZ = ZoneInfo("America/Chicago")

# Minutes added to total trip time for each line transfer.
TRANSFER_PENALTY_MINUTES: float = 3

_EARTH_RADIUS_MILES = 3958.8

# Miles per degree of latitude (approximately constant worldwide).
_MILES_PER_DEG_LAT: float = 69.0
# Miles per degree of longitude at Chicago's latitude (~41.9°).
# Derived as 69.0 × cos(41.9°) ≈ 51.35.
_MILES_PER_DEG_LON: float = 51.35


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in miles between two lat/lon points."""
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return _EARTH_RADIUS_MILES * 2 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Spatial grid index — shared implementation used by gtfs_loader and transit_graph.
# ---------------------------------------------------------------------------

class SpatialGrid:
    """
    Generic cell-based spatial bucket index for lat/lon data.

    Divides the lat/lon plane into cells of cell_lat_deg × cell_lon_deg and
    supports O(cells in radius ring + results) radius queries.  Each entry
    stores its own (lat, lon) alongside the caller-supplied value, so no
    external coordinate lookup is needed during query.

    Typical usage:
        grid = SpatialGrid(cell_lat_deg=1/69.0, cell_lon_deg=1/51.35)
        for stop in stops:
            grid.add(stop["lat"], stop["lon"], stop)
        for dist_miles, stop in grid.query(user_lat, user_lon, radius_miles=0.5):
            ...
    """

    def __init__(self, cell_lat_deg: float, cell_lon_deg: float) -> None:
        self._clat = cell_lat_deg
        self._clon = cell_lon_deg
        # Each bucket stores (entry_lat, entry_lon, value) triples.
        self._grid: dict[tuple[int, int], list[tuple[float, float, Any]]] = {}

    def _cell(self, lat: float, lon: float) -> tuple[int, int]:
        return (math.floor(lat / self._clat), math.floor(lon / self._clon))

    def add(self, lat: float, lon: float, value: Any) -> None:
        """Insert value at (lat, lon) into the grid."""
        self._grid.setdefault(self._cell(lat, lon), []).append((lat, lon, value))

    @property
    def cell_count(self) -> int:
        return len(self._grid)

    def query(
        self, lat: float, lon: float, radius_miles: float
    ) -> list[tuple[float, Any]]:
        """
        Return (distance_miles, value) pairs for all entries within radius_miles of (lat, lon).

        Uses a bounding-box prefilter before exact Haversine, touching at most a
        (2k+1)×(2k+1) cell window where k = ceil(radius / cell_size).
        """
        dlat = radius_miles / _MILES_PER_DEG_LAT
        dlon = radius_miles / _MILES_PER_DEG_LON

        min_cl = math.floor((lat - dlat) / self._clat)
        max_cl = math.floor((lat + dlat) / self._clat)
        min_cn = math.floor((lon - dlon) / self._clon)
        max_cn = math.floor((lon + dlon) / self._clon)

        lat_lo, lat_hi = lat - dlat, lat + dlat
        lon_lo, lon_hi = lon - dlon, lon + dlon

        radius_sq = radius_miles ** 2

        results: list[tuple[float, Any]] = []
        for cl in range(min_cl, max_cl + 1):
            interior_lat = min_cl < cl < max_cl
            for cn in range(min_cn, max_cn + 1):
                bucket = self._grid.get((cl, cn))
                if not bucket:
                    continue
                interior = interior_lat and min_cn < cn < max_cn
                for e_lat, e_lon, value in bucket:
                    if not interior and (e_lat < lat_lo or e_lat > lat_hi or e_lon < lon_lo or e_lon > lon_hi):
                        continue
                    # _MILES_PER_DEG constants slightly underestimate true arc distance at
                    # Chicago's latitude, so d_planar <= d_haversine — safe to discard when > radius.
                    dlat_e = abs(e_lat - lat)
                    dlon_e = abs(e_lon - lon)
                    if (dlat_e * _MILES_PER_DEG_LAT) ** 2 + (dlon_e * _MILES_PER_DEG_LON) ** 2 > radius_sq:
                        continue
                    d = haversine_miles(lat, lon, e_lat, e_lon)
                    if d <= radius_miles:
                        results.append((d, value))
        return results


# ---------------------------------------------------------------------------
# Chicago geographic bounds — single source of truth for all bounding-box uses.
# Coverage: Howard St (north) to 50th St (south), lakefront (east) to Pulaski Rd (west).
# ---------------------------------------------------------------------------

# Canonical corner coordinates
CHICAGO_SOUTH: float = 41.64
CHICAGO_NORTH: float = 42.02
CHICAGO_WEST:  float = -87.94
CHICAGO_EAST:  float = -87.52

# Format-specific derived constants — import whichever matches the target API.
# Google Maps Geocoding API bounds parameter: "SW_lat,SW_lon|NE_lat,NE_lon"
CHICAGO_BBOX_GOOGLE: str   = f"{CHICAGO_SOUTH},{CHICAGO_WEST}|{CHICAGO_NORTH},{CHICAGO_EAST}"
# Overpass QL bbox: south,west,north,east (all as a comma-joined string)
CHICAGO_BBOX_OVERPASS: str = f"{CHICAGO_SOUTH},{CHICAGO_WEST},{CHICAGO_NORTH},{CHICAGO_EAST}"
# OSMnx / ox.graph_from_bbox format: (left/west, bottom/south, right/east, top/north)
CHICAGO_BBOX_OSMNX: tuple  = (CHICAGO_WEST, CHICAGO_SOUTH, CHICAGO_EAST, CHICAGO_NORTH)

# ---------------------------------------------------------------------------
# Street-graph bounding box — Chicago city limits + Evanston (Purple Line).
#
# Coverage:
#   North 42.083 — Linden (Wilmette, Purple Line terminal)
#   South 41.712 — ~100th St, just south of 95th/Dan Ryan (Red Line terminal)
#   West  -87.800 — Chicago west side; covers Austin (Blue Line) but excludes
#                   Oak Park, Forest Park, Cicero, Skokie, and Rosemont suburbs
#   East  -87.520 — Chicago lakefront
#
# Includes Chicago + Evanston only. Pace and Metra service areas are out of scope
# (see docs/FEATURE_PLANS.md → Feature PaceMetraCoverage).
# ---------------------------------------------------------------------------
STREET_GRAPH_SOUTH: float = 41.7120
STREET_GRAPH_NORTH: float = 42.0830
STREET_GRAPH_WEST:  float = -87.8000
STREET_GRAPH_EAST:  float = -87.5200
STREET_GRAPH_BBOX_OSMNX: tuple = (STREET_GRAPH_WEST, STREET_GRAPH_SOUTH, STREET_GRAPH_EAST, STREET_GRAPH_NORTH)
