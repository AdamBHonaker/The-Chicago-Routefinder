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

# 2026-04-18 Persistent HTTP session, heapq partial sort, display-name preservation, cached legColor

---

## 🟡 OPT-012 · Persistent requests session for Google geocoding — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** Network Efficiency

**What was inefficient:** `geocode_google()` called `requests.get()` directly on every uncached lookup. Each call opened a fresh TCP connection and paid SSL handshake overhead. With connection keep-alive disabled, concurrent geocoding requests in a bursty session (e.g., first load after a cold cache) each incurred a full round-trip connection setup (~10–40 ms overhead on top of the API latency).

**Implemented in:** Added a module-level `_http_session = requests.Session()` immediately after the `import requests` line. `geocode_google()` now calls `_http_session.get(...)` instead of `requests.get(...)`. The session reuses the underlying TCP/SSL connection across geocode calls, amortizing handshake cost to ~0 on subsequent requests to the same host. No behavior changes — timeout, params, and error handling are identical.

---

## 🟡 OPT-013 · `heapq.nsmallest()` instead of full sort in nearest-stop finders — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** Algorithmic Efficiency

**What was inefficient:** `find_nearest_train_stations()` called `hits.sort(key=...)` on the full candidate list then sliced to `max_results` (default 3). `find_nearest_bus_stops()` did the same before slicing to `max_results` (default 5). A full sort is O(n log n); selecting k smallest from n unsorted items is O(n log k) via `heapq.nsmallest`. In dense bus-stop queries returning 50–100 candidates inside the search radius, the sort did unnecessary work on 45–95 items that would be discarded immediately after.

**Implemented in:** Replaced `hits.sort(key=lambda item: item[0])` + `[{**s} for _, s in hits[:max_results]]` with `[{**s} for _, s in heapq.nsmallest(max_results, hits, key=lambda item: item[0])]` in both functions. Added `import heapq` to module-level imports. Output order is identical (ascending distance); the final `sorted(..., key=lambda s: s["walk_minutes"])` that follows is unaffected.

---

## 🟢 OPT-014 · Preserve original query string as `matched_name` in `resolve_location` — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** UX / Data Fidelity

**What was inefficient:** `resolve_location()` lowercased and street-abbreviation-normalized the raw query into `q` and then returned `q` as `matched_name` for both the exact-match and geocoding branches. This meant a user typing "Wrigley Field" would get `"wrigley field"` back as the matched name — losing their original capitalisation. The fuzzy-match branch already returned the NEIGHBORHOOD_COORDS dict key (also lowercase), so the issue was limited to exact-match and geocoding hits.

**Implemented in:** Added `original_query = query.strip()` before the lowercase/normalization step; `q` is derived from it (`q = original_query.lower()`). Both `matched_name = q if coords else None` (exact-match branch) and `matched_name = q` (geocoding branch) now use `original_query` instead. The fuzzy-match branch returns the dict key unchanged (already correct — no change). Internal lookup (`NEIGHBORHOOD_COORDS.get(q)`, `geocode_google(q)`) still uses the normalized `q` for stable cache keys.

---

## 🟢 OPT-018 · Cache `legColor(leg)` result per transit leg in `renderRoute` — IMPLEMENTED

**File:** `frontend/src/MapView.jsx`

**Category:** Redundant Computation

**What was inefficient:** In `renderRoute()`, `legColor(leg)` was called once in Pass 1 (polyline drawing) and a second time in Pass 2 (board/exit marker drawing) for each transit leg. Each call performed two object lookups (`LINE_COLORS[leg.line]`, `BUS_DIRECTION_COLORS[leg.line]`) plus a nullish-coalesce chain. With a typical 4-leg route this is 4 wasted calls per render; small but trivially avoidable.

**Implemented in:** Added `const legColors = legs.map(leg => leg.type === "transit" ? legColor(leg) : null)` immediately before the Pass 1 `forEach`. Pass 1 now reads `const color = legColors[i]` instead of calling `legColor(leg)`. Pass 2 reads the same `legColors[i]`. `legColor()` is called exactly once per transit leg per render. No behavior change; z-order of layers is preserved.

---

# 2026-04-18 Short-circuit + inverted-index in `fuzzy_match_neighborhood`

---

## 🟢 OPT-006 · `fuzzy_match_neighborhood` scans all keys even after finding a high score — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** Redundant Computation

**What was inefficient:** Every cold-cache call to `fuzzy_match_neighborhood` ran `SequenceMatcher(None, query, key).ratio()` against **all** ~240 `NEIGHBORHOOD_COORDS` keys, even after finding a near-perfect match, and built a fresh `SequenceMatcher` per key (no reuse of the seq2 `__chain_b` cache that Python's docs explicitly recommend for one-vs-many comparisons). For multi-word queries, the loop paid the full `ratio()` cost on every key and only discarded non-overlapping keys *after* computing the score.

**Implemented in:** Three layered optimizations in [backend/gtfs_loader.py:787-859](backend/gtfs_loader.py#L787-L859):
1. **Word-based inverted index** — `_neighborhood_word_index()` is a new `@lru_cache(maxsize=1)` helper that precomputes `word → frozenset[keys]` once. For multi-word queries (the common case that triggered the word-overlap filter), the loop now iterates only keys that share ≥1 meaningful word with the query instead of all ~240. Typical narrowing: 240 → ~1–20 candidates.
2. **`SequenceMatcher` reuse with seq2 caching** — one matcher is constructed per call with `query` set as `seq2` (the fixed side), then `set_seq1(key)` is swapped per candidate. This is the documented fast pattern and reuses Python's internal `__chain_b` cache for the query string.
3. **`quick_ratio()` prefilter + 0.99 short-circuit** — `quick_ratio()` is an O(n) upper bound on `ratio()`; if it can't beat `best_score`, the expensive real computation is skipped. Once any key scores ≥0.99 the loop breaks (exact/near-exact matches can't be meaningfully beaten). Single-word and zero-meaningful-word queries still fall back to scanning `NEIGHBORHOOD_COORDS` (behavior-preserving — those queries never had the word-overlap requirement). Match threshold (≥0.95) and stop-word list are unchanged, so the `resolve_location()` and `_coords_for_location()` call sites see identical semantics.

---

# 2026-04-18 Collapse double dict lookups on `_response_cache` hit/miss

---

## 🟢 OPT-005 · Double dict lookup on cache hit/miss — IMPLEMENTED

**File:** `backend/main.py`

**Category:** Redundant Computation

**What was inefficient:** The `/recommend` response-cache hot path hashed the cache key more times than necessary. On read, a stale-entry eviction did `_response_cache.get(key)` followed by `del _response_cache[key]` (two hashes). On write, the LRU reorder did `if key in _response_cache: del _response_cache[key]` then `_response_cache[key] = ...` (up to three hashes on the existing-key branch).

**Implemented in:** Cache read now nests the freshness check inside `if cached:` and uses `_response_cache.pop(key, None)` for the stale-eviction path — same hash count when `cached is None`, and avoids the `KeyError` risk on the del branch. Cache write now unconditionally assigns `_response_cache[key] = (...)` and then calls `_response_cache.move_to_end(key)` to shift existing keys to the newest position — eliminating the membership-test hash on the existing-key branch (3 → 2 ops) while still producing the identical LRU ordering consumed by `popitem(last=False)` at the size-cap check. Eviction semantics, TTL semantics, and cache-key shape (including the BYOK suffix) are unchanged. Touched [backend/main.py:594-599](backend/main.py#L594-L599) and [backend/main.py:824-830](backend/main.py#L824-L830).

---

# 2026-04-18 Drop per-request `_route_fingerprint` closure + dedup pass in `/recommend`

---

## 🟢 OPT-004 · Per-request closure for route fingerprinting — IMPLEMENTED

**File:** `backend/main.py`

**Category:** Redundant Computation

**What was inefficient:** `/recommend` defined `_route_fingerprint` as a nested pure function inside the handler, allocating a new function object on every request. After merging direct bus routes with transfer routes it ran a dedup loop (`seen_fps` / `deduped`) that rebuilt the already-sorted list, producing a redundant O(n) reconstruction on top of the `sorted(...)[:5]` step.

**Implemented in:** Resolved as a side effect of commit `072e9d4` ("Add spatial index, fix ABBR, simplify bus routing"). That commit replaced the dual codepath (`find_bus_routes` + `find_bus_transfer_routes`) with a single unconditional `find_bus_transfer_routes(n_routes=2)` call whose outputs are disjoint from the unified-graph direct routes by construction — so no dedup is needed. The `_route_fingerprint` closure and the `seen_fps` loop were deleted; the merge is now just `sorted(ranked_routes + transfer_ranked, key=lambda x: x[0])[:5]` at [backend/main.py:728-731](backend/main.py#L728-L731). Behavior preserved: the non-overlap guarantee is documented in the surrounding comment at [backend/main.py:705-712](backend/main.py#L705-L712). Cataloged here retroactively so the scan list reflects current state.

---

# 2026-04-18 Append-only journal + periodic compaction for geocode-cache flush

---

## 🟢 OPT-003 · Full JSON rewrite on every geocode-cache flush — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** Inefficient I/O

**What was inefficient:** The 30-second background flush thread re-serialised the entire `_geocode_cache` dict to `geocode_cache.json` and atomically renamed it every tick whenever a single key had been added — O(cache size) work for an O(1) delta. At current volumes the cache is small, but the cost grows linearly with months of production queries while the delta per flush is typically 0–2 entries.

**Implemented in:** Replaced the `_geocode_cache_dirty: bool` flag with a `_geocode_pending: dict` that records only entries added since the last flush. Each 30s tick now appends the delta as JSONL lines to a sidecar `geocode_cache.journal` file (O(delta) write, `fsync`'d). A full snapshot rewrite of `geocode_cache.json` — which also drops the journal — is forced only when either (a) `_GEOCODE_COMPACT_THRESHOLD = 500` cumulative journal entries have built up, or (b) `_GEOCODE_COMPACT_INTERVAL = 3600s` has elapsed since the last compaction. `_load_geocode_cache` now loads the snapshot and then replays the journal on top, so restarts are crash-safe; torn trailing JSONL lines are skipped rather than failing startup. `atexit` still guarantees a final flush. Same public surface (`_flush_geocode_cache_if_dirty`, `geocode_google`), same persistence guarantees, O(size) writes reduced to O(delta) for ~99% of flushes.

---

# 2026-04-18 Per-request memo for terminal-name lookups in `_rank_routes`

---

## 🟢 OPT-002 · Repeated `get_station_by_name` lookups inside ranking hot path — IMPLEMENTED

**File:** `backend/main.py`

**Category:** Redundant Computation

**What was inefficient:** `_rank_routes` called `get_station_by_name(dest_name)` once per destination name inside the bearing-test inner loop, across up to 5 ranked routes × up to ~4 directions per boarding station. Terminal names like "Howard" or "95th/Dan Ryan" are frequently shared across routes within a single request, so the same string was resolved repeatedly.

**Implemented in:** Verified that `get_station_by_name` in `transit_graph.py` is already decorated with `@lru_cache(maxsize=512)`, so cross-request lookups were already O(1). Added a per-request `terminal_coords: dict[str, tuple[float,float] | None]` memo at the top of `_rank_routes` to skip the cache's hash + thread-lock dispatch on repeat lookups within one request and to record `None` (no-match) results once. Behavior preserved: same terminal coords fed to the dot-product bearing test, same fallback to `min(dest_map.values())` when coords unavailable. Impact is low — the underlying function was already cached — but eliminates duplicate dispatch across routes and is essentially free.

---

# 2026-04-18 Grid-bucket spatial index for nearest-stop lookups

---

## 🔴 OPT-001 · Full-catalog Haversine scan on every bus-stop lookup — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** Redundant Computation / Inefficient Data Structure

**What was inefficient:** `find_nearest_bus_stops` ran Haversine against every CTA bus stop (~10,729 stops) on every `/recommend` call — twice per request (origin + destination) — before applying any radius filter. The progressive-radius loop (0.25 → 1.0 mi) only shrank results, not work, so each call cost ~21k trig operations purely for stop proximity. `find_nearest_train_stations` had the identical pattern against ~143 stations.

**Implemented in:** Added a grid/bucket spatial index keyed on floor(lat/cell_lat, lon/cell_lon) with cell dimensions ≈ 1 mile at Chicago's latitude (`_SPATIAL_CELL_LAT_DEG = 1/69`, `_SPATIAL_CELL_LON_DEG = 1/51.35`). Index is built lazily via `_spatial_index(kind)` and cached with `lru_cache(maxsize=2)` for process lifetime (same scope as `_load_stops`). New `_candidates_within(kind, lat, lon, radius_miles)` computes the lat/lon bounding box, iterates only the bucket cells intersecting that box, applies a cheap bounding-box prefilter, then Haversine only on remaining candidates. Both `find_nearest_train_stations` and `find_nearest_bus_stops` now delegate to it; semantics (radius ceiling, progressive expansion, `walk_minutes` annotation, sort order) are preserved unchanged. Verified bit-exact against brute force across multiple radii and locations. Measured ~25.7 ms → ~0.08 ms per call at 0.25 mi (~300×) and ~0.58 ms at 1.0 mi (~44×) on the 10,729-stop catalog.

