"""
Central configuration for all CTA Transit routing parameters.

All tuning constants live here so routing behaviour can be adjusted without
hunting across multiple modules.  Most values can also be overridden via
environment variables so Railway deployments can be tuned without a code change.

Units are noted in comments.  Typical ranges are given where relevant.
"""

import os

# ---------------------------------------------------------------------------
# Transit graph — leg / transfer constraints
# ---------------------------------------------------------------------------

# Maximum plausible scheduled leg time.  GTFS trips longer than this are treated
# as data noise and dropped during graph construction.  Range: 30–90 min.
MAX_LEG_MINUTES: float = float(os.getenv("MAX_LEG_MINUTES", "45"))

# Default transfer penalty added to trip time for each line change.  Range: 2–5 min.
# Shared with utils.TRANSFER_PENALTY_MINUTES — defined there to avoid circular import.

# ---------------------------------------------------------------------------
# Intermodal walk-edge tuning (train ↔ bus walk edges — Feature B)
# ---------------------------------------------------------------------------

# Radius within which a train station and bus stop are connected by a walk edge.
# Smaller values = fewer intermodal options; larger values = more edges, slower build.
# Range: 0.10–0.25 miles.
TRANSFER_RADIUS_MILES: float = float(os.getenv("TRANSFER_RADIUS_MILES", "0.15"))

# Walk-time cap for intermodal edges; pairs exceeding this are excluded from the graph.
# Range: 3–8 min.
TRANSFER_WALK_CAP_MIN: float = float(os.getenv("TRANSFER_WALK_CAP_MIN", "5.0"))

# Straight-line → street-network correction factor applied to Haversine distances
# at graph-build time (avoids loading the full street graph into memory on startup).
# Chicago's grid is very regular; 1.25–1.35 is typical for US cities.
DETOUR_FACTOR: float = float(os.getenv("DETOUR_FACTOR", "1.3"))

# ---------------------------------------------------------------------------
# Bus-to-bus transfer candidate scoring (Feature C)
# ---------------------------------------------------------------------------

# Maximum walk distance from a transfer stop to the destination for route B.
# Range: 0.3–1.0 miles.
MAX_EXIT_DIST_MILES: float = float(os.getenv("MAX_EXIT_DIST_MILES", "0.5"))

# Maximum walk between routes A and B at the transfer stop.
# Range: 0.1–0.5 miles.
MAX_TRANSFER_WALK_MILES: float = float(os.getenv("MAX_TRANSFER_WALK_MILES", "0.25"))

# Route A must reduce Haversine-to-destination by at least this ratio at each stop.
# 0.9 means each stop must bring ≥10 % forward progress toward the destination.
# Range: 0.85–0.95.
FWD_PROGRESS_RATIO: float = float(os.getenv("FWD_PROGRESS_RATIO", "0.9"))

# Maximum transfer candidates kept per (arrival × route-A) combination.
# Higher values find more routes but increase compute time quadratically.
# Range: 2–5.
MAX_CANDIDATES_PER_ARRIVAL: int = int(os.getenv("MAX_CANDIDATES_PER_ARRIVAL", "3"))

# Walk-time penalty factor in the candidate score (minutes per mile).
# Derived as: 60 min/hr ÷ 3 mph × 1.3 detour ≈ 26.0 min/mile.
# Adjust in lockstep with WALKING_SPEED_MPH and DETOUR_FACTOR.
TRANSFER_SCORE_WALK_FACTOR: float = float(os.getenv("TRANSFER_SCORE_WALK_FACTOR", "26.0"))

# ---------------------------------------------------------------------------
# Walking
# ---------------------------------------------------------------------------

# Comfortable pedestrian pace assumed throughout the app.  Range: 2.5–3.5 mph.
WALKING_SPEED_MPH: float = float(os.getenv("WALKING_SPEED_MPH", "3.0"))

# Derived: metres per second (used internally by walking.py and transit_graph.py).
WALKING_SPEED_MPS: float = WALKING_SPEED_MPH * 1609.34 / 3600  # ≈ 1.34 m/s

# Chicago block-length thresholds used for "long block" / "short block" labels.
# N-S numbered-address axis ≈ 1/8 mile = 201.17 m (660 ft).
LONG_BLOCK_METERS: float = 201.17
# E-W cross streets ≈ 1/16 mile = 100.58 m (330 ft).
SHORT_BLOCK_METERS: float = 100.58
# Midpoint: edges ≥ this length are classified as "long block".
BLOCK_TYPE_THRESHOLD_METERS: float = 150.0

# ---------------------------------------------------------------------------
# CTA API
# ---------------------------------------------------------------------------

# Number of upcoming train arrivals fetched per station from the Train Tracker API.
# The API default is 5; 6 gives one extra arrival for direction filtering.  Range: 3–10.
CTA_MAX_ARRIVALS_PER_STATION: int = int(os.getenv("CTA_MAX_ARRIVALS_PER_STATION", "6"))

# HTTP timeout for CTA Train Tracker and Bus Tracker API calls (seconds).
# Railway's latency to the CTA APIs is typically < 1 s; 8 s allows for bad-weather spikes.
# Range: 5–15 s.
CTA_API_TIMEOUT_SECONDS: float = float(os.getenv("CTA_API_TIMEOUT_SECONDS", "8"))

# ---------------------------------------------------------------------------
# Street graph memory management (see walking.py)
# ---------------------------------------------------------------------------

# Seconds of walk-request inactivity before the in-memory street graph is freed
# so Railway can reclaim ~300–600 MB during quiet periods (e.g. overnight).
# The graph reloads automatically on the next request (~2–3 s penalty for one user).
# Set to 0 to disable eviction entirely (e.g. on a busy instance).  Range: 0–3600 s.
WALK_GRAPH_EVICT_TTL_S: int = int(os.getenv("WALK_GRAPH_EVICT_TTL_S", "600"))

# ---------------------------------------------------------------------------
# Geocoding cache maintenance (see gtfs_loader.py)
# ---------------------------------------------------------------------------

# Geocode entries older than this are evicted during weekly maintenance sweeps.
# ZERO_RESULTS entries (permanent misses) are also subject to eviction.  Range: 30–365 days.
GEOCODE_CACHE_MAX_AGE_DAYS: int = int(os.getenv("GEOCODE_MAX_AGE_DAYS", "90"))

# How often the background thread runs the age-based eviction sweep (seconds).
# Weekly keeps the cache from growing without being expensive.
GEOCODE_EVICT_INTERVAL_SECONDS: int = int(os.getenv("GEOCODE_EVICT_INTERVAL_SECONDS", str(7 * 24 * 3600)))
