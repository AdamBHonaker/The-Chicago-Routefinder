# Efficiency Improvements

Known efficiency improvements catalogued for future improvement. Impact: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When an efficiency in this file is implemented, **delete its entry from this file** and add a corresponding entry to [`Efficiency_Improvement_History.md`](Efficiency_Improvement_History.md) documenting what was changed and how. This file should only ever contain improvements that have not yet been implemented.

---

## Efficiency Scan — April 20, 2026 (Entire Project)

> Scanned: `backend/` (Python), `frontend/src/` (React/JavaScript)  
> Found: 3 opportunities (1 Medium, 2 Low)

---

### OPT-001 · Response Cache Eviction Not LRU-Aware
- **File**: `backend/main.py` (lines 30–50)
- **Category**: Memory Inefficiency / Cache Performance
- **Impact**: 🟡 Medium
- **Description**: The response cache uses `OrderedDict` with FIFO eviction (`popitem(last=False)` when size exceeds 500). However, frequently-accessed cache entries are never moved to the end, so a hot entry can be evicted while cold entries remain. This wastes cache memory and forces repeated expensive API calls for popular routes.
- **Suggested Improvement**: When a cache hit occurs (in `recommend()`), call `_response_cache.move_to_end(cache_key)` to promote the accessed entry to the end. This ensures the least-recently-used entry is always at the front for eviction. For a production app with repeated route queries, this could reduce API latency by 10–20% for hot queries.

---

### OPT-002 · Redundant Coordinate Transformations in MapView renderRoute
- **File**: `frontend/src/MapView.jsx` (lines 31–45, 85–95, 135–155)
- **Category**: Redundant Computation
- **Impact**: 🟢 Low
- **Description**: The `toGeo` helper converts [lat, lon] to [lon, lat] for each coordinate individually. In `renderRoute`, coordinates are transformed multiple times: once during leg iteration, again in the bounds calculation, and again when building feature collections. For routes with many legs or dense intermediate stops, this means hundreds of small allocations and function calls.
- **Suggested Improvement**: Pre-transform all coordinates in a single pass before the two-pass rendering loop and store them in a shared lookup. This would reduce object allocations by ~50–60% for typical routes, improving frame paint time slightly on low-end devices.

---

### OPT-003 · Sequential Leg Iteration in _rank_routes to Find First TransitLeg
- **File**: `backend/main.py` (lines 405–425)
- **Category**: Redundant Computation
- **Impact**: 🟢 Low
- **Description**: The `_rank_routes` function iterates through every leg in each route to find the first `TransitLeg` using `next(..., None)`. This is O(routes × legs) per request. While typical routes have only 2–4 legs, this is unnecessary iteration if the first transit leg could be identified at route construction time.
- **Suggested Improvement**: Add a `first_transit_leg_index` field to the `Route` dataclass and populate it during route construction. Then `_rank_routes` can access it in O(1) time. This reduces code complexity and makes the intent clearer.

---

## Summary

The codebase is **generally well-optimized**. Most patterns follow best practices:
- ✅ Single-pass GTFS streaming (avoiding repeated reads of 5.8 M–row stop_times.txt)
- ✅ Response caching with TTL to avoid redundant API calls
- ✅ Pre-built spatial grid and KDTree for fast geolocation
- ✅ Memoized expensive path-finding functions (`@lru_cache` in `walking.py`)
- ✅ Rate limiting to prevent quota exhaustion
- ✅ Lazy graph loading on startup, not on import

The three opportunities above are **nice-to-have optimizations** that provide incremental gains but are not blocking user experience at current scale.
