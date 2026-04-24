"""
Pytest configuration and shared fixtures for the CTA backend test suite.

This conftest runs before any test module is imported, ensuring:
  1. The backend/ directory is on sys.path so all modules are importable.
  2. Minimal GTFS stub files exist in backend/gtfs_data/ so transit_graph
     can be imported in CI environments that lack the full feed download.
     Stub files are never created if real data already exists.
"""

import sys
import csv
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path: make backend/ importable from any working directory
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).parent.parent   # backend/
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# CI guard: create header-only GTFS stubs if the feed is absent.
# transit_graph._build_bus_stop_grid() reads stops.txt at module import time;
# an empty CSV with just the header row lets it succeed and return {}.
# Real data files are never overwritten.
# ---------------------------------------------------------------------------
_GTFS_DIR = BACKEND_DIR / "gtfs_data"
_STUBS: dict[str, list[str]] = {
    "stops.txt":       ["stop_id", "stop_name", "stop_lat", "stop_lon",
                        "location_type", "parent_station"],
    "routes.txt":      ["route_id", "route_short_name", "route_type"],
    "trips.txt":       ["route_id", "service_id", "trip_id",
                        "direction_id", "shape_id"],
    "calendar.txt":    ["service_id", "monday", "tuesday", "wednesday",
                        "thursday", "friday", "saturday", "sunday",
                        "start_date", "end_date"],
    "stop_times.txt":  ["trip_id", "arrival_time", "departure_time",
                        "stop_id", "stop_sequence"],
    "transfers.txt":   ["from_stop_id", "to_stop_id",
                        "transfer_type", "min_transfer_time"],
    "shapes.txt":      ["shape_id", "shape_pt_lat", "shape_pt_lon",
                        "shape_pt_sequence"],
}

_GTFS_DIR.mkdir(exist_ok=True)
for _fname, _headers in _STUBS.items():
    _path = _GTFS_DIR / _fname
    if not _path.exists():
        # UTF-8-BOM matches the real CTA GTFS encoding
        _path.write_text("﻿" + ",".join(_headers) + "\n", encoding="utf-8")
