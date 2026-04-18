# Efficiency Improvement History

A log of efficiency opportunities that have been identified and implemented. Entries are moved here from `EFFICIENCY_IMPROVEMENTS.md` when resolved.

Impact: 🔴 High · 🟡 Medium · 🟢 Low.

Categories: Redundant Computation · Inefficient Data Structure · Inefficient I/O · Memory Footprint · Algorithmic Complexity.

---

<!--
Entry template — copy this block when moving an item from EFFICIENCY_IMPROVEMENTS.md:

# YYYY-MM-DD <Short title summarizing the change>

---

## <impact emoji> <OPT-ID> · <Opportunity title> — IMPLEMENTED

**File:** `path/to/file.py` (and any others touched)

**Category:** <e.g. Redundant Computation / Inefficient I/O>

**What was inefficient:** <Describe the prior behavior: what was being recomputed, what memory was held unnecessarily, what I/O was redundant, etc. Include scale — "~20k Haversine calls per request", "rewrote full 3MB JSON every 30s", "held all 1.2M shape points in memory" — so future readers can judge whether a similar pattern elsewhere is worth revisiting.>

**Implemented in:** <Describe the fix concretely: what data structure / caching / indexing / reordering was introduced, where it lives (module-level vs per-request, startup vs first-call), and what behavior is preserved unchanged. Note any measured or estimated before/after numbers if available. Mention any callers or adjacent code that had to change to accommodate the new shape, and any follow-ups deliberately deferred.>

-->

# 2026-04-18 Grid-bucket spatial index for nearest-stop lookups

---

## 🔴 OPT-001 · Full-catalog Haversine scan on every bus-stop lookup — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** Redundant Computation / Inefficient Data Structure

**What was inefficient:** `find_nearest_bus_stops` ran Haversine against every CTA bus stop (~10,729 stops) on every `/recommend` call — twice per request (origin + destination) — before applying any radius filter. The progressive-radius loop (0.25 → 1.0 mi) only shrank results, not work, so each call cost ~21k trig operations purely for stop proximity. `find_nearest_train_stations` had the identical pattern against ~143 stations.

**Implemented in:** Added a grid/bucket spatial index keyed on floor(lat/cell_lat, lon/cell_lon) with cell dimensions ≈ 1 mile at Chicago's latitude (`_SPATIAL_CELL_LAT_DEG = 1/69`, `_SPATIAL_CELL_LON_DEG = 1/51.35`). Index is built lazily via `_spatial_index(kind)` and cached with `lru_cache(maxsize=2)` for process lifetime (same scope as `_load_stops`). New `_candidates_within(kind, lat, lon, radius_miles)` computes the lat/lon bounding box, iterates only the bucket cells intersecting that box, applies a cheap bounding-box prefilter, then Haversine only on remaining candidates. Both `find_nearest_train_stations` and `find_nearest_bus_stops` now delegate to it; semantics (radius ceiling, progressive expansion, `walk_minutes` annotation, sort order) are preserved unchanged. Verified bit-exact against brute force across multiple radii and locations. Measured ~25.7 ms → ~0.08 ms per call at 0.25 mi (~300×) and ~0.58 ms at 1.0 mi (~44×) on the 10,729-stop catalog.

