# Bugs Fixed History

A log of bugs that have been identified and resolved. Entries are moved here from `BUGS_TO_BE_FIXED.md` when fixed.

Severity: 🔴 High · 🟡 Medium · 🟢 Low.

---

# 2026-04-18 `_ABBR_MAP` Duplicate-Key Vulnerability — Converted to Pair-List with Import-Time Assertion

---

## 🔴 `_ABBR_MAP` could silently accept duplicate keys — FIXED

**File:** `backend/gtfs_loader.py`

**What was happening:** `_ABBR_MAP` was defined as a dict literal. Earlier revisions had included `"blvd"` four times and `"pkwy"` twice; Python silently keeps the last assignment for duplicate keys in a dict literal, so a future typo like `"blvd": "bolevard"` after a correct entry would override it with no error at import or runtime. By the time of this fix the visible duplicates had already been removed, but the structural vulnerability remained — the dict-literal form offers no protection against reintroducing duplicates.

**Fixed in:** Replaced the dict literal with a tuple of `(abbr, expansion)` pairs (`_ABBR_PAIRS`) and constructed `_ABBR_MAP = dict(_ABBR_PAIRS)`. An `assert len(_ABBR_MAP) == len(_ABBR_PAIRS)` immediately after the conversion now fails at import time if any key is duplicated, with a diagnostic message listing the offending keys. Downstream usage (`_sorted_abbrs`, `_STREET_ABBR_RE`, `_expand`) is unchanged — `_ABBR_MAP` is still the same dict with the same 15 entries.

---

# 2026-04-18 Bus-Mode Multi-Leg Routing — Transfer Branch No Longer Gated on Direct Emptiness

---

## 🟡 Bus-only filter suppressed multi-leg bus routing when any direct route existed — FIXED

**File:** `backend/main.py`

**What was happening:** In the `recommend()` bus-routing block, `find_bus_transfer_routes()` (bus→bus multi-leg) was only invoked when `find_bus_routes()` (direct single-leg) returned an empty list (`if not bus_ranked:`). Because almost any O/D pair yields *some* direct bus pairing — even a slow one — the transfer branch was effectively unreachable in production. Users in `transit_mode="Bus"` saw only single-bus options, never a dramatically faster 2-bus transfer. `transit_mode="All"` masked this because the unified train graph surfaces intermodal alternatives.

**Fixed in:** Removed the emptiness gate for "Bus" mode. Now in `transit_mode="Bus"` the backend always calls both `find_bus_routes()` (n=3) and `find_bus_transfer_routes()` (n=2), concatenates the results, runs the combined list through the existing `_rank_bus_routes()` → sort → top-5 truncation → fingerprint-dedup pipeline. For `transit_mode="All"` the original emptiness-gated fallback is preserved (train routing is the intermodal backstop there, and the transfer call is latency-expensive). Transfer `n_routes` was lowered from 3 → 2 as an upfront cost-control measure given the transfer branch now runs on every Bus-mode request. Duplicate routes that happen to be produced by both calls are dropped by the pre-existing fingerprint dedup below the merge block.

---

# 2026-04-18 BYOK Settings Panel — Browser-Storage Security Notice Added

---

## 🟢 BYOK key stored in browser with no user warning — FIXED

**File:** `frontend/src/App.jsx`, `frontend/src/App.css`

**What was happening:** The Anthropic API key was stored in plaintext `sessionStorage` (moved from `localStorage` in the 2026-04-15 fix). While session-scoped storage narrows the exposure window, the key remains readable by any XSS vector or malicious browser extension for the lifetime of the tab — a non-trivial risk given the key has direct billing implications. The BYOK settings panel gave no indication of this risk, so a user could reasonably assume "password"-type input meant secure-at-rest storage.

**Fixed in:** Added a prominent warning block at the top of `SettingsPanel` (above the API key input) that reads: *"⚠ Security notice: Your key is stored in this browser. Only use this feature on trusted personal devices."* The banner uses `role="alert"` for accessibility and is styled via a new `.settings-warning` rule in `App.css` — an amber-on-dark card that matches the existing settings panel palette without competing with form controls. No behavior change: storage mechanism, key validation, and save/clear flows are untouched; this is purely a user-facing disclosure so users can make an informed choice before entering their key.

---

# 2026-04-18 `_build_shape_lookup` Two-Pass Refactor (Memory Bound to Used Shapes)

---

## 🟢 `_build_shape_lookup` held all GTFS shape points in memory simultaneously — FIXED

**File:** `backend/transit_graph.py`

**What was happening:** The original implementation streamed `shapes.txt` first into a `defaultdict(list)` keyed by every `shape_id`, then read `trips.txt` to decide which `(route_id, direction_id) → shape_id` pairs to keep. Peak memory held every point for every shape in the file, including shape variants that no trip actually references. For CTA the overhead is a few MB (acceptable), but for larger agencies with many unreferenced shape variants it would scale poorly.

**Fixed in:** Reordered to a true two-pass approach:
1. **Pass 1 (trips.txt):** collect the set of `shape_id`s actually referenced by trips, grouped per `(route_id, direction_id)` as candidates.
2. **Pass 2 (shapes.txt):** stream points and skip any row whose `shape_id` is not in the used-set, so unused shapes never enter `raw_pts`.
3. **Resolve:** pick the longest shape per `(route_id, direction_id)` from the candidate sets (preserves the prior "full-length beats short-turn" selection rule).
4. **Join:** same routes.txt short-name keying as before.

`raw_pts` is now also cleared after conversion to flush the per-shape point tuples once the sorted `[[lat, lon], ...]` arrays are built. Behavior (which shape is chosen per route/direction, which keys appear in `_shape_lookup`) is unchanged; only peak memory and work done on unused shape rows are reduced. `get_shape()` and `clip_shape()` callers are unaffected.

---

# 2026-04-18 Bus Route Pill Showed `0`/`1` Instead of Route Number on Intermodal Legs

---

## 🔴 Intermodal bus legs displayed direction_id ("0"/"1") as the route pill label — FIXED

**File:** `backend/transit_graph.py`

**What was happening:** Bus transit edges in the unified intermodal graph (Feature B) were added with `line=did`, where `did` is the GTFS `direction_id` — literally the strings `"0"` or `"1"`. When Dijkstra produced a path through bus edges, `_path_to_route()` propagated that value into the leg's `line` field. On the frontend, `isBus = leg.line in BUS_DIRECTION_COLORS` then failed (since `"0"`/`"1"` aren't in `{Northbound, Southbound, Eastbound, Westbound}`), so the leg fell into the train-rendering branch and the pill showed `leg.line.replace(" Line", "")` → `0` or `1` instead of the route number. Direct single-leg bus routes (`find_bus_routes`) and 2-bus transfer routes (`find_bus_transfer_routes`) were unaffected because both pull a real direction string from live `bus_arrivals`. Only intermodal paths that traversed the unified-graph bus edges were broken — which became visible after the unified graph was the dominant source of bus legs.

**Fixed in:** Added a `_bearing_to_direction(lat1, lon1, lat2, lon2)` helper that maps the great-circle bearing from a sequence's first stop to its last stop into one of `Northbound` / `Southbound` / `Eastbound` / `Westbound`. In `_build_graph()`'s "Add bus route edges" block, that direction string is now computed once per `(short_name, did)` pair and passed as `line=direction_name` instead of `line=did`. The `direction_id` is still preserved on the edge as `direction_id=did` for any future routing logic that needs it. The frontend's `BUS_DIRECTION_COLORS` lookup now succeeds and the pill renders `leg.line_code` (the route number) as intended. The parallel `is_bus` check in [`backend/main.py:385`](backend/main.py#L385) that feeds Claude's prompt is also fixed by the same change since it relied on the same direction-string set.

---

# 2026-04-17 Style Error Dismissal, Geocode Double-Suffix, and Transfer Floor Documentation Fixes

---

## ✅ `styleError` in `MapView.jsx` cleared on any tile load, not specifically on style recovery — FIXED

**File:** `frontend/src/MapView.jsx`

**Fixed in:** Added `e.dataType === "style"` guard to the `map.on("data", ...)` handler alongside the existing `e.isSourceLoaded` check. The error banner now clears only when the map style itself has successfully loaded, not when any arbitrary tile source finishes loading.

---

## ✅ `geocode_google()` double-appended `, Chicago, IL` if already present in query — FIXED

**File:** `backend/gtfs_loader.py`

**Fixed in:** Changed `"address": query + ", Chicago, IL"` to `"address": query if "chicago" in query.lower() else query + ", Chicago, IL"`. Queries that already contain "chicago" (any case) are sent as-is; the suffix is only appended when the city is absent.

---

## ✅ `_load_transfer_edges` silently clamped sub-2-minute GTFS transfers with no explanation — FIXED

**File:** `backend/transit_graph.py` — `_load_transfer_edges()`

**Fixed in:** Added a multi-line comment above the `max(min_sec / 60.0, _TRANSFER_MINUTES)` line documenting that this is an intentional pessimistic floor, why it exists (conservative routing estimates, unvalidated GTFS values), and where to change it (`_TRANSFER_MINUTES` constant at the top of the file).

---

# 2026-04-17 Geocoding, Shape Direction, Transfer Scoring, and Bus Label Fixes

---

## ✅ `_coords_for_location()` passed raw `query` to `geocode_google()` — cache miss, double API call — FIXED

**File:** `backend/main.py`

**Fixed in:** Added `q = _normalize_street_abbr(q)` after the existing `q = query.lower().strip()` in `_coords_for_location()`, and changed `geocode_google(query)` to `geocode_google(q)`. Imported `_normalize_street_abbr` from `gtfs_loader`. The geocode cache key now matches the one produced by `resolve_location()`, eliminating the redundant Google Maps API call on every routing request.

---

## ✅ `clip_shape()` returned shape points in wrong order for reverse-direction trips — FIXED

**File:** `backend/transit_graph.py`

**Fixed in:** After computing `board_idx` and `exit_idx`, the slice `shape_points[lo:hi+1]` is now assigned to `segment` and reversed (`segment[::-1]`) when `board_idx > exit_idx`. The reversed segment is returned so the animated polyline direction always matches the rider's actual direction of travel.

---

## ✅ Bus transfer scoring used haversine × 20 instead of grid-corrected walk minutes — FIXED

**File:** `backend/transit_graph.py` — `find_bus_transfer_routes()`

**Fixed in:** Applied a 1.3× Manhattan-grid correction factor to both the transfer-walk and exit-walk haversine terms in the candidate scoring formula: `transfer_hav * 26.0` and `best_exit_dist * 26.0` (previously `* 20.0`). The correction factor approximates real street-grid walk distances, improving candidate ranking so nearby-looking stops via straight-line distance are not incorrectly favored over better options.

---

## ✅ `_format_routes()` labeled bus wait as "next train" in Claude prompt — FIXED

**File:** `backend/main.py`

**Fixed in:** `_format_routes()` already correctly detects `is_bus` by checking whether `first_transit.line` is a directional string (`"Northbound"`, `"Southbound"`, etc.) and uses `"next bus Due"` / `"next bus in N min"` vs. `"next train Due"` / `"next train in N min"` accordingly. Confirmed present in code and removed from BUGS_TO_BE_FIXED.md.

---

# 2026-04-17 Railway Log Rate Limit Fix

---

## ✅ GTFS download progress loop bursts past Railway's 500 logs/sec limit — FIXED

**File:** [`backend/fetch_gtfs.py`](backend/fetch_gtfs.py)

**Severity:** 🔴 High (caused Railway to drop log messages and flag the replica)

**What happened:** `backend/gtfs_data/` is gitignored, so Railway re-downloads the full CTA GTFS zip (~50 MB) on every fresh container (first deploy, container restarts). The old `download_gtfs()` printed one progress line per 64 KB chunk — ~800 `print()` calls for a 50 MB file. In a terminal these overwrite each other via `end="\r"`, but Railway treats every `print()` as a new log line. A fast Railway network connection could push all 800 lines through in under a second, exceeding Railway's 500 logs/sec replica limit. This manifested as a Railway warning ("Messages dropped: N") observed by the user when initiating a directions request that coincided with a backend container restart.

**Fix:** Removed the per-chunk progress print. Added a HEAD request before download to show the file size up front (one log line). Progress is now logged at most once per 5 MB downloaded (~10 lines for a 50 MB file). Start and completion messages are retained. Net result: ~800 lines/download → ≤12 lines/download.

---

# 2026-04-16 Bus Wait Correctness Fix

---

## ✅ Bus routes bypass `_rank_routes` — live wait times not normalised — FIXED

**File:** `backend/main.py`

**Fixed in:** Added `_rank_bus_routes()` helper immediately after `_rank_routes()`. It takes the `(total, wait, route)` tuples already returned by `find_bus_routes()` / `find_bus_transfer_routes()` and re-expresses the `wait` field as `int | None` to match `_rank_routes()` output semantics: `wait > 0` = bus in N min, `wait == 0` = Due, `wait is None` = no data (defensive; bus routing only builds routes when a live arrival exists, so None should not occur). In the `/recommend` endpoint, `if bus_ranked: bus_ranked = _rank_bus_routes(bus_ranked)` is called immediately after the bus routing block and before the merge with train results. `find_bus_routes()`, `find_bus_transfer_routes()`, and `_rank_routes()` were **not** modified.

---

# 2026-04-16 Performance Fix

---

## ✅ `get_bus_stop_sequences` double-streamed 5.8M-row `stop_times.txt` — FIXED

**File:** `backend/transit_graph.py`

**Fixed in:** Replaced `_stream_stop_sequences` with `_stream_all_stop_sequences`, which processes both train and bus trips in a single pass through `stop_times.txt`. Added `_bus_seq_cache: dict | None = None` at module level. `_build_graph()` now loads bus metadata (`_load_bus_route_map`, `_load_bus_stop_lookup`, `_load_bus_candidate_trips`) before the stream call, passes them into the unified streamer, and stores the returned `bus_result` into `_bus_seq_cache`. `get_bus_stop_sequences()` returns `_bus_seq_cache` immediately when set (fast path); the original streaming logic is preserved as a fallback for isolated test calls. `@lru_cache` removed from `get_bus_stop_sequences` — the module-level variable replaces it. Net result: one fewer 5.8M-row file scan, saving ~7–10 s on cold start.

---

# 2026-04-15 Low-Severity Audit Pass

---

## ✅ `_save_geocode_cache` rewrites entire file on every new geocode — FIXED

**File:** [backend/gtfs_loader.py](backend/gtfs_loader.py)

**Fixed in:** Replaced write-through with a dirty-flag + background-flush approach. `_geocode_cache_dirty` (bool, always accessed under `_geocode_lock`) is set to `True` whenever a hit or miss is added to `_geocode_cache`. A daemon thread (`geocode-cache-flusher`) calls `_flush_geocode_cache_if_dirty` every 30 s and writes the cache only when dirty. An `atexit` handler guarantees a final flush on clean shutdown. The expensive atomic-rename write now happens at most once per 30 s instead of on every uncached query.

---

## ✅ `_fetch_bus_chunk` silent exception and `get_train/bus_arrivals` missing error counts — FIXED

**Files:** `backend/cta_client.py`, `backend/main.py`, `frontend/src/App.jsx`

**Fixed in:** `_fetch_bus_chunk` now returns a sentinel `[{"_bus_error": True, "exc": ...}]` on exception instead of `[]`. `get_bus_arrivals` scans results for sentinels, strips them, and returns `(arrivals, n_errors)`. `get_train_arrivals` similarly returns `(sorted_good, n_errors)`. `main.py` unpacks both tuples and adds `"bus_errors"` and `"train_errors"` to the response dict. `App.jsx` reads `data.bus_errors` and renders a `.data-warning` message when bus arrivals are empty due to API failures.

---

## ✅ `_rank_routes` dead `dest_lat`/`dest_lon` parameters — FIXED

**Files:** `backend/main.py:253-254, 599`

**Fixed in:** Removed `dest_lat: float | None = None` and `dest_lon: float | None = None` from `_rank_routes` signature and from the call site in `/recommend`.

---

## ✅ `_response_cache` O(n) eviction — FIXED

**Files:** `backend/main.py:36, 702-705`

**Fixed in:** Changed `_response_cache` from `dict` to `collections.OrderedDict`. Cache writes re-insert the key at the end (to maintain insertion order), and eviction now uses `popitem(last=False)` — O(1) — instead of `min()` over all entries.

---

## ✅ `_rate_store` grows unboundedly — FIXED

**Files:** `backend/main.py:87-88`

**Fixed in:** After the hourly-eviction loop in `_check_rate_limit`, if the deque is now empty, `del _rate_store[ip]` removes the entry. The `window` reference is retained for the current request's append, preventing stale IPs from accumulating indefinitely.

---

## ✅ BYOK cache collision — FIXED

**Files:** `backend/main.py:41-47`

**Fixed in:** `_cache_key` now accepts a `byok: bool` parameter and appends `"byok"` to the key when True. The call site passes `byok=bool(byok_key)`. BYOK and shared-quota requests now use separate cache pools.

---

## ✅ `prdctdn.isdigit()` crashes when API returns `None` — FIXED

**Files:** `backend/cta_client.py:179`

**Fixed in:** Changed `prd.get("prdctdn", "")` to `prd.get("prdctdn") or ""`. The `or ""` short-circuits on an explicit `null` value, preventing `AttributeError` on `None.isdigit()`.

---

## ✅ `find_nearest_train_stations` computes Haversine twice per station — FIXED

**Files:** `backend/gtfs_loader.py:567-571`

**Fixed in:** Replaced the double-call with a walrus operator: `if (d := _haversine_miles(...)) <= max_distance_miles` so the result is computed once and reused as `distance_miles`.

---

## ✅ `_save_geocode_counter` lacks atomic rename — FIXED

**Files:** `backend/gtfs_loader.py:76-84`

**Fixed in:** Mirrored `_save_geocode_cache`'s atomic write pattern: write to `.counter.tmp` then `tmp.replace(path)`. A mid-write crash can no longer silently reset the monthly call counter to zero.

---

## ✅ `_normalize_street_abbr` false-matches "St." in saint names — FIXED

**Files:** `backend/gtfs_loader.py:679-683`

**Fixed in:** Added lookahead `(?=\s*(?:,|$))` to `_STREET_ABBR_RE` requiring the suffix token to appear at end-of-string or before a comma. "St. Michael's Church" no longer normalises to "street michael's church"; "123 N Clark St" and "123 Main St, Chicago" still normalise correctly.

---

## ✅ `fuzzy_match_neighborhood` runs SequenceMatcher over ~300 keys on every miss — FIXED

**Files:** `backend/gtfs_loader.py:626`

**Fixed in:** Added `@lru_cache(maxsize=1024)` to `fuzzy_match_neighborhood`. Repeated queries for the same lowercased string now return instantly without re-running O(n·m) SequenceMatcher comparisons.

---

## ✅ `min(G[u][v].values(), ...)` picks zero-length edges — FIXED

**Files:** `backend/walking.py:128, 210`

**Fixed in:** Changed `d.get("length", 0)` to `d.get("length", float("inf"))` in both `walk_directions` and `walk_path`. Edges missing a `length` attribute are now treated as infinitely long, so they lose the `min()` comparison rather than winning it.

---

## ✅ `walk_directions` fallback misclassifies block type by total distance — FIXED

**Files:** `backend/walking.py:167-173`

**Fixed in:** Fallback step always uses `block_type: "long"` and `_LONG_BLOCK_METERS` for block counting. The old `fallback_meters >= _BLOCK_TYPE_THRESHOLD` comparison compared total trip length against a per-edge threshold, producing wrong classifications for walks ≥ 150 m.

---

## ✅ `lru_cache` on functions returning mutable lists — DOCUMENTED

**Files:** `backend/walking.py:52, 81, 176`

**Fixed in:** Added inline comments to `walk_minutes`, `walk_directions`, and `walk_path` noting that `lru_cache` returns the same object on cache hits and callers must not mutate the returned value.

---

## ✅ `get_station_by_name` uncached O(N·M) SequenceMatcher fallback — FIXED

**Files:** `backend/transit_graph.py:582`

**Fixed in:** Added `@lru_cache(maxsize=512)` to `get_station_by_name`. Common destination names like "Howard" now resolve in O(1) after the first call.

---

## ✅ Bus shape lookup relies on `route_short_name == route_id` coincidence — FIXED

**Files:** `backend/transit_graph.py:559-562`

**Fixed in:** `_build_shape_lookup` now always writes both `(route_id, direction_id)` and `(short_name, direction_id)` keys unconditionally, instead of setting the short_name alias only when it differs from route_id. Both keys are always available regardless of CTA renumbering.

---

## ✅ Pre-allocating `raw = {tid: [] for tid in candidates}` wastes memory — FIXED

**Files:** `backend/transit_graph.py:273, 766`

**Fixed in:** Both `_stream_stop_sequences` (trains) and `get_bus_stop_sequences` (buses) now use `defaultdict(list)` populated only when a row matches, with `candidate_set = set(...)` for the membership check. No empty lists are pre-allocated for non-matching trips.

---

## ✅ Transit edges store dead `all_routes` metadata — FIXED

**Files:** `backend/transit_graph.py:435`

**Fixed in:** Removed `all_routes=candidates` from `G.add_edge(...)`. The field was never read by any routing code; removing it reduces per-edge memory for heavily-served segments (Loop, Red Line core).

---

## ✅ BYOK API key persisted to `localStorage` in plaintext — FIXED

**Files:** `frontend/src/App.jsx:274-286`

**Fixed in:** Changed `localStorage` to `sessionStorage` for the BYOK key. The key now clears automatically when the tab is closed, reducing the window for XSS exfiltration.

---

## ✅ `busFullness` dead state sent to backend — FIXED

**Files:** `frontend/src/App.jsx:265, 331`

**Fixed in:** Removed the `busFullness` state variable and the `bus_fullness` field from the request body. Updated the commented-out select JSX with restoration instructions for when CTA re-enables `psgld`.

---

## ✅ `RouteCard` expanded state doesn't reset on new search — FIXED

**Files:** `frontend/src/App.jsx:162-163, 489`

**Fixed in:** Added `searchIdRef` (a `useRef` counter incremented on every form submit). `RouteCard` keys are now `${searchIdRef.current}-${i}` instead of `${i}`, so React unmounts and remounts all cards on each new search, resetting `expanded` to `isFirst`.

---

## ✅ `TransitPhoto` onError leaves orphan caption — FIXED

**Files:** `frontend/src/App.jsx:44-60`

**Fixed in:** Added `const [failed, setFailed] = useState(false)` to `TransitPhoto`. On `onError`, `setFailed(true)` is called and the component returns `null`, hiding both the broken image and its caption.

---

## ✅ `clearRouteLayers` silently no-ops when style not loaded — FIXED

**Files:** `frontend/src/MapView.jsx:45-56`

**Fixed in:** `clearRouteLayers` now accepts explicit `layerIds` and `sourceIds` arrays (tracked in `routeLayerIds` / `routeSourceIds` refs inside `MapView`). `renderRoute` receives the same arrays and records every ID it adds via `_trackSource`/`_trackLayer` helpers. Removal iterates the tracked lists directly without calling `getStyle()`, so stale layers are always removed even when the style is reloading.

---

# 2026-04-15 Production Deployment Fixes

---

## ✅ `/recommend` returned 404 on production — `VITE_BACKEND_URL` missing `https://` in Vercel — FIXED

**Files:** Vercel dashboard → Environment Variables

**Fixed in:** Updated the `VITE_BACKEND_URL` environment variable in the Vercel dashboard to include the `https://` protocol prefix (`https://cta-transit-pwa-prod-production.up.railway.app`) and redeployed. Vite now bakes the absolute URL into the production bundle, so `/recommend` requests hit the Railway backend directly instead of being interpreted as a relative path under the Vercel domain.

---

## ✅ Preview deployment URLs returned 401 on `manifest.webmanifest` (Vercel Authentication) — FIXED

**Files:** Vercel dashboard → Settings → Deployment Protection

**Fixed in:** Adjusted Vercel Deployment Protection settings so PWA assets (`manifest.webmanifest`, icons) are accessible on preview URLs without authentication. PWA install prompts now work on preview deployments.

---

# 2026-04-12 Audit Pass — Fixed 2026-04-13

---

## ✅ `find_bus_routes` locks in the first arrival's boarding stop per route+direction — FIXED

**File:** `backend/transit_graph.py` `find_bus_routes()`

**Fixed in:** Removed `seen_route_dirs` skip logic. All arrivals for a route+direction are now evaluated, and the candidate with the lowest composite score (`board_walk_min + wait_min + exit_dist * 20`) is kept via `pass1` dict update, so a closer boarding stop discovered later in the arrivals list can replace a worse earlier candidate.

---

## ✅ `get_station_by_name` contains-match fallback returns the first iteration match — FIXED

**File:** `backend/transit_graph.py` lines 568–572

**Fixed in:** Contains-match fallback now ranks all substring matches by `SequenceMatcher.ratio()` and returns the highest-similarity result, preventing wrong-line matches like `"Harlem"` → Harlem-Lake when Harlem/Forest Park is the correct terminal.

---

## ✅ `walk_path` geometry reversal heuristic compares longitude only — FIXED

**File:** `backend/walking.py` line 194

**Fixed in:** Reversal check now computes squared 2-D Euclidean distance from node `u` to each geometry endpoint (`du_start`/`du_end`) and reverses only when `du_start > du_end`, correctly handling north–south edges where longitude differences are negligible.

---

## ✅ MapView `styleError` latches `true` on any map error and never resets — FIXED

**File:** `frontend/src/MapView.jsx` lines 288–294

**Fixed in:** Error handler now only latches when the source is the openmaptiles style document (`e.sourceId === "openmaptiles"`) combined with a 4xx/5xx status, ignoring per-tile transient failures. A `map.on("data")` listener resets `styleError` to `false` on any successful source load, allowing the banner to clear after the map recovers.

---

## ✅ MapView origin/destination dots depend on the first and last leg being walks — FIXED

**File:** `frontend/src/MapView.jsx` lines 179–218

**Fixed in:** `renderRoute` now accepts `originCoords`/`destCoords` parameters; `MapView` exposes them as props and passes them from `App.jsx` (`result.originCoords`/`result.destCoords`). Dot placement uses the explicit coords first, falling back to leg path inference only when props are null.

---

## ✅ `_save_geocode_cache` rewrites the full cache on every geocode miss or hit — FIXED

**File:** `backend/gtfs_loader.py`

**Fixed in:** `_save_geocode_cache` now writes to a `.tmp` file and atomically renames it over the real file via `Path.replace()`, eliminating the risk of a partial write corrupting `geocode_cache.json`.

---

## ✅ `_geocode_call_counter` never purges old month entries — FIXED

**File:** `backend/gtfs_loader.py`

**Fixed in:** `_load_geocode_counter` now prunes on load, retaining only the current `YYYY-MM` key. This naturally resets the count each month without any explicit rollover logic.

---

## ✅ `walk_path` returns a single-point list when origin and destination snap to the same OSM node — FIXED

**File:** `backend/walking.py` lines 178–180

**Fixed in:** When `len(node_ids) < 2`, `walk_path` now returns `[[origin_lat, origin_lon], [dest_lat, dest_lon]]` — a valid 2-point polyline — instead of a single-point list that MapView silently drops.

---

## ✅ Same-station line-change WalkLeg has a single-point `path_points` list — FIXED

**File:** `backend/transit_graph.py` `_path_to_route()` lines 908–918

**Fixed in:** Transfer `WalkLeg` now uses `path_points=[[blat, blon], [blat, blon]]` (two identical points) so MapView's `coords.length < 2` guard doesn't suppress it, and includes `directions=[{"street": "Change trains", "direction": "", "minutes": _TRANSFER_MINUTES}]` so the RouteCard "Steps" button appears.

---

## ✅ `bus_fullness` filter with unknown values silently matches empty `psgld` — FIXED

**File:** `backend/main.py` lines 408–414

**Fixed in:** `RouteRequest` now includes a `@field_validator` for both `bus_fullness` and `transit_mode` that raises `ValueError` (→ HTTP 422) for values outside the allowed sets. Unknown values can no longer silently pass through.

---

## ✅ `cta_client._fetch_bus_chunk` accepts negative `prdctdn` values — FIXED

**File:** `backend/cta_client.py` lines 183–186

**Fixed in:** Guard changed from `prdctdn.lstrip("-").isdigit()` to `prdctdn.isdigit()`, so only non-negative integers are accepted; `"-5"` now falls through to `minutes = 0`.

---

## ✅ `cta_client._fetch_bus_chunk` delay parsing is case-sensitive — FIXED

**File:** `backend/cta_client.py` line 203

**Fixed in:** `is_delayed` now uses `str(prd.get("dly", "")).lower() in ("true", "1", "yes")`, accepting any casing or common truthy string the CTA API might send.

---

## ✅ `find_nearest_bus_stops` uses a hard 0.25-mile radius with no progressive expansion — FIXED

**File:** `backend/gtfs_loader.py` lines 574–598

**Fixed in:** `find_nearest_bus_stops` now iterates radii `(0.25, 0.5, 0.75, 1.0)` miles and breaks at the first non-empty result, matching the progressive-expansion pattern used for train stations.

---

## ✅ `renderMarkdown` doesn't strip backticks, links, or list markers — FIXED

**File:** `frontend/src/App.jsx` lines 50–58

**Fixed in:** Chain extended with backtick stripping (`` `code` `` → `code`), link stripping (`[text](url)` → `text`), and list/blockquote marker stripping (`- item` → `item`).

---

## ✅ `App.jsx handleSubmit` doesn't trim inputs before POST — FIXED

**File:** `frontend/src/App.jsx` lines 232–237

**Fixed in:** POST body now sends `origin: origin.trim()` and `destination: destination.trim()`, ensuring no leading/trailing whitespace reaches the backend or Claude prompt.

---

## ✅ `TransitPhoto` has no `onError` fallback for missing images — FIXED

**File:** `frontend/src/App.jsx` lines 37–48

**Fixed in:** `<img>` now has `onError={(e) => { e.currentTarget.style.display = "none"; }}` so broken images hide instead of showing the browser's broken-image icon.

---

## ✅ `App.jsx` in-flight fetch isn't aborted on component unmount — FIXED

**File:** `frontend/src/App.jsx` lines 203–278

**Fixed in:** The existing mount `useEffect` cleanup now also calls `abortRef.current.abort()` on unmount alongside the photo timer cancel, preventing stale state updates on unmounted components.

---

## ✅ `_load_weekday_service_ids` ignores `calendar_dates.txt` exceptions — FIXED

**File:** `backend/transit_graph.py` lines 175–186

**Fixed in:** `_load_weekday_service_ids` now also reads `calendar_dates.txt` and augments the weekday set with any `service_id` that has ≥3 `exception_type=1` (add-date) entries on Mon–Fri, catching services defined purely through add-exceptions.

---

## ✅ `_path_to_route` inner transit-grouping loop treats DEST as an implicit break but reads the edge anyway — FIXED

**File:** `backend/transit_graph.py` lines 897–904

**Fixed in:** Loop condition tightened to `while look < len(path) - 1 and path[look] != DEST and path[look + 1] != DEST:`, preventing any future code inside the loop from reading attributes of the DEST-adjacent walk edge before the type guard fires.

---

## ✅ `_rank_routes` assumes bearing test won't degenerate when `from_coords == to_coords` — FIXED

**File:** `backend/main.py` lines 173–190

**Fixed in:** Explicit guard added: when `dlat == 0.0 and dlon == 0.0`, a warning is logged and the code falls through directly to `min(dest_map.values())` instead of silently computing zero dot-products for every terminal.

---

## ✅ TransitPhoto remains over the map after an error or zero-route result, blocking map interaction — FIXED

**Files:** `frontend/src/App.jsx` lines 262–270, 272–277

**Fixed in:** Photo fade-out is now triggered unconditionally in both the success branch (regardless of `routes.length`) and the `catch` block, so the photo always clears after any search completes — whether successful, empty, or errored.

---

## ✅ Railway GTFS re-download on every deploy — FIXED

**File:** `backend/fetch_gtfs.py` lines 99–114

**Fixed in:** `force` flag is now exclusively driven by `--force` in `sys.argv`. Non-interactive environments (Railway, CI) detected via env vars no longer trigger a re-download; instead they skip the interactive prompt and exit early with existing data intact. Pass `--force` explicitly to force a re-download in CI/CD.

---

## ✅ `load_dotenv()` called after module-level imports that read env vars — FIXED

**File:** `backend/main.py`

**Fixed in:** `load_dotenv()` moved to before the `from gtfs_loader import ...` line.

`gtfs_loader.py` reads `GOOGLE_MAPS_API_KEY = os.getenv(...)` at module level (import time). When Python processes `from gtfs_loader import ...` in `main.py`, it immediately executes all of `gtfs_loader.py`. `load_dotenv()` was previously called after those imports, so the `.env` file had not yet been loaded into `os.environ` when `_GOOGLE_MAPS_API_KEY` was captured — causing it to always be `""` regardless of what was in `.env`. Moving `load_dotenv()` before the local imports ensures the environment is populated before any module reads from it.

---

## ✅ `line-cap` and `line-join` placed in MapLibre `paint` instead of `layout` — FIXED

**File:** `frontend/src/MapView.jsx` lines 101–108

**Fixed in:** In MapLibre GL JS, `line-cap` and `line-join` are **layout** properties, not paint properties. Placing them in the `paint` object silently ignores them. Moved to a `layout` object:
```js
layout: { "line-cap": "round", "line-join": "round" },
paint:  { "line-color": color, "line-width": 5 },
```

---

## ✅ `wait_minutes === 0` ("Due") shows no indicator in RouteCard — FIXED

**File:** `frontend/src/App.jsx` line 141

**Fixed in:** Updated `waitNote` logic to explicitly handle the `0` case:
```js
const waitNote =
  route.wait_minutes === null ? ""
  : route.wait_minutes === 0  ? " · Due now"
  : ` · ${route.wait_minutes} min wait`;
```

---

## ✅ No `AbortController` — stale results if user re-submits during a pending search — FIXED

**File:** `frontend/src/App.jsx` lines 215–260

**Fixed in:** Added an `AbortController` ref; the in-flight request is cancelled at the start of each `handleSubmit` and `signal: abortRef.current.signal` is passed to `fetch`. `AbortError` is ignored in the catch block so a cancelled search doesn't surface as an error message.

---

## ✅ PWA service worker pre-caches all PNGs including transit photos — FIXED

**File:** `frontend/vite.config.js`

**Fixed in:** `globPatterns` now explicitly lists `icon-*.png` and `apple-touch-icon.png` instead of `**/*.png`, so only icon PNGs are pre-cached. A `StaleWhileRevalidate` runtime cache entry for `/transit-photos/` was added so photos load from cache when available and update in the background.

---

## ✅ `renderMarkdown` strips `**bold**` but not `*italic*` — FIXED

**File:** `frontend/src/App.jsx` lines 51–56

**Fixed in:** Added `.replace(/\*([^*]+)\*/g, "$1").replace(/_([^_]+)_/g, "$1")` to the chain.

---

## ✅ `_load_weekday_service_ids()` only checks Monday + Tuesday + Wednesday — FIXED

**File:** `backend/transit_graph.py` lines 175–178

**Fixed in:** Added `and row.get("thursday", "0").strip() == "1" and row.get("friday", "0").strip() == "1"` to the condition so all five weekday columns are required.

---

## ✅ Train arrival datetime: `.replace(tzinfo)` wrong for ISO strings with UTC offset — FIXED

**File:** `backend/cta_client.py` line 80

**Fixed in:**
```python
arr_dt = datetime.fromisoformat(arr_str)
if arr_dt.tzinfo is not None:
    arr_dt = arr_dt.astimezone(CHICAGO_TZ)
else:
    arr_dt = arr_dt.replace(tzinfo=CHICAGO_TZ)
```

---

## ✅ Destination walk times computed in wrong direction throughout — FIXED

**Files:** `backend/transit_graph.py` lines 991–994, `backend/gtfs_loader.py` line 558, `backend/transit_graph.py` line 1127

**Fixed in:** Swapped the argument order in the three affected `walk_minutes()` calls so origin and destination match the direction of travel (`station → destination` instead of `destination → station`).

---

## ✅ `validate_and_report()` uses `encoding="utf-8"` instead of `"utf-8-sig"` — FIXED

**File:** `backend/fetch_gtfs.py` line 79

**Fixed in:** Changed `open(path, encoding="utf-8")` to `open(path, encoding="utf-8-sig")` in `validate_and_report()`, consistent with all other GTFS file readers.

---

## ✅ `G_base.copy()` called on every train routing request — FIXED

**Fixed in:** `backend/transit_graph.py` — added `import threading` and a module-level `_thread_local: threading.local`. `find_routes()` now keeps a thread-local copy of `G_base` (`_thread_local.G`) keyed by `id(G_base)`. The copy is created once per executor thread and reused for all subsequent requests on that thread. `__ORIGIN__` and `__DEST__` virtual nodes are added before routing and removed in a `finally` block to leave the thread-local graph clean for the next request.

---

## ✅ `_coords_for_location()` duplicates fuzzy-match logic from `resolve_location()` — FIXED

**Fixed in:** `backend/gtfs_loader.py` — added `_FUZZY_STOP_WORDS` (frozenset) and `fuzzy_match_neighborhood(query)` as a public module-level helper. `resolve_location()` now calls `fuzzy_match_neighborhood()` instead of reimplementing the loop inline. `backend/main.py` — imports `fuzzy_match_neighborhood` from `gtfs_loader`; `_coords_for_location()` uses it for step 2 instead of its own copy of the logic.

---

## ✅ Redundant `walk_minutes` recomputation for destination stations in `find_routes()` — FIXED

**Fixed in:** `backend/transit_graph.py` `find_routes()` — the per-station `street_walk_minutes()` call and `dest_walk[mapid] = walk_min` overwrite inside the `dest_stations` loop were removed. `dest_walk` is now populated once from `dest_stations[*]["walk_minutes"]` and those values are used directly as edge weights when adding the station→DEST edges.

---

## ✅ `photoFadeTimer` ref not cleared on component unmount — FIXED

**File:** `frontend/src/App.jsx` lines 195–261

**Fixed in:** Added a `useEffect` cleanup:
```js
useEffect(() => {
  return () => { if (photoFadeTimer.current) clearTimeout(photoFadeTimer.current); };
}, []);
```

---

## ✅ Synchronous blocking calls inside async request handler — FIXED

**Fixed in:** `backend/main.py` — both `resolve_location` calls and `_coords_for_location` calls wrapped in `await loop.run_in_executor(...)`; Anthropic call switched to `AsyncAnthropic.messages.create()`.

---

## ✅ No user-facing message when location is outside coverage area — FIXED

**Fixed in:** `backend/main.py` — added 400 check after `resolve_location(request.destination)` with explicit coverage area message.

---

## ✅ Anthropic client instantiated on every request — FIXED

**Fixed in:** `backend/main.py` — `AsyncAnthropic` client now instantiated once at module level as `_claude_client`, reused across all requests.

---

## ✅ Bus fullness filter may silently return zero results — FIXED + VERIFIED

**Fixed in:** `backend/cta_client.py` — `_fetch_bus_chunk()` now normalizes `psgld` at read time via `.replace(" ", "_").upper()` before storing it. `_FULLNESS_API_VALUES` in `main.py` already uses UPPER_SNAKE; a comment was added documenting the normalization contract.

**Live API finding (2026-04-09):** After testing 30+ predictions across multiple high-traffic routes and stops (Michigan Ave, State St, Belmont), `psgld` is consistently empty (`""`) in all CTA Bus Tracker v3 API responses. CTA includes the field in the JSON but does not currently populate it with load data. The normalization fix is still correct for future-proofing if CTA enables this data.

**UI action taken:** The Bus Fullness `<select>` in `frontend/src/App.jsx` is commented out but preserved in full. All backend filter logic (`_FULLNESS_API_VALUES`, the `bus_fullness` filter in `/recommend`, `psgld` normalization) is intact and ready. Re-enable the commented `<select>` block when CTA starts populating this field.

---

## ✅ Missing validation for CTA_BUS_API_KEY when bus transit mode is requested — FIXED

**File:** `backend/main.py` `/recommend` endpoint (lines ~280–285)

**Fixed in:** Added a check: `if not bus_key: raise HTTPException(status_code=500, detail="CTA_BUS_API_KEY not configured in backend/.env")` if `request.transit_mode in ("Bus", "All")`.

---

## ✅ Routing engine exception swallows traceback — FIXED

**File:** `backend/main.py` lines 365–366

**Fixed in:** Replaced with `import traceback; traceback.print_exc()` so the full stack trace appears in production logs.

---

## ✅ Bus routing may use wrong direction sequence for stops served by multiple directions — FIXED

**Fixed in:** `backend/transit_graph.py` `find_bus_routes()` — `board_index` type changed from `dict[str, tuple[str, str, int]]` to `dict[str, list[tuple[str, str, int]]]`; population now uses `setdefault(..., []).append(...)` instead of plain assignment so all direction entries for a stop are preserved rather than overwriting. In the arrival loop, candidates are filtered to entries matching the arrival's route number, then all valid direction candidates are tried; the direction whose exit stop is closest to the destination wins.

---

## ✅ PWA manifest `purpose: "any maskable"` on a single icon entry — FIXED

**File:** `frontend/vite.config.js` line 31

**Fixed in:** Split into two icon entries:
```js
{ src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
{ src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
```

---

## ✅ No validation when origin and destination resolve to the same location — FIXED

**File:** `backend/main.py` `/recommend` endpoint

**Fixed in:** After resolving both locations, checks if the resolved coordinates are within ~100m of each other and returns a 400 with a message: "Your origin and destination appear to be the same location."

---

## ✅ `osmnx` import inside `try` block masks misconfigured deployments — FIXED

**Fixed in:** `backend/walking.py` — `import osmnx as ox` moved to module level; removed from `_load_graph()` and from inside the `try` block in `walk_minutes()`. An import failure now raises immediately at startup rather than being silently caught and falling back to Haversine estimates.

---

## ✅ `max_tokens=750` misaligned with prompt instruction "3-4 sentences" — FIXED

**File:** `backend/main.py` line 382 (token limit); line ~266 (prompt instruction)

**Fixed in:** Re-aligned before public launch. Note: this was an intentional testing-phase setting, not a pre-launch bug. `max_tokens` lowered to ~350–400 and/or the prompt updated to match the intended response length.

---

## ✅ Representative trip selection may use off-peak schedules — FIXED

**Fixed in:** `backend/transit_graph.py` — `_load_weekday_service_ids()` added; `_load_representative_trips()` now loads all weekday candidate trips per direction; `_stream_stop_sequences()` selects the trip whose first-stop arrival is closest to noon (720 min) per line/direction. Single pass through `stop_times.txt`.

---

## ✅ No error handling around Claude API call — FIXED

**Fixed in:** `backend/main.py` — `_claude_client.messages.create()` wrapped in try/except; response text extracted via `next((c for c in message.content if hasattr(c, "text")), None)` to safely handle non-text blocks; raises HTTP 502 with the error message on any failure; full traceback printed to server logs.

---

## ✅ Frontend `res.json()` crashes on non-JSON error responses — FIXED

**Fixed in:** `frontend/src/App.jsx` — non-OK responses now attempt `res.json()` inside a try/catch; if parsing fails (e.g. Railway/nginx 502 returning HTML), falls back to `"Service error (502 Bad Gateway)"`.

---

## ✅ Bus stop IDs silently truncated to 10 — no batching — FIXED

**Fixed in:** `backend/cta_client.py` — extracted `_fetch_bus_chunk()` helper; `get_bus_arrivals()` now splits stop IDs into chunks of 10 and fires all chunks concurrently via `asyncio.gather`. Results merged and sorted by arrival time.

---

## ✅ `prdctdn` value "APPROACHING" (and similar) silently drops bus arrival — FIXED

**Fixed in:** `backend/cta_client.py` — replaced `int(prdctdn)` with an `isdigit()` guard: numeric strings are parsed as before; `"DUE"`, `"APPROACHING"`, and any other non-numeric value all map to `0` minutes instead of raising `ValueError` and silently dropping the arrival.

---

## ✅ `wait=0` conflates "no arrival data" with "train is Due now" — FIXED

**Fixed in:** `backend/main.py` — `_rank_routes()` now initialises `wait: int | None = None` (no data) instead of `0`. The empty `dest_map` branch explicitly sets `wait = None`. `total` computation uses `wait if wait is not None else 0`. `_format_routes()` now has three branches: `wait is None` → no note, `wait == 0` → `"next train Due"` / `"next bus Due"`, `wait > 0` → `"next train in N min"` / `"next bus in N min"`.

---

## ✅ Bus shape lookup uses `route_short_name` instead of `route_id` — FIXED

**Fixed in:** `backend/transit_graph.py` `_build_shape_lookup()` — after building the primary `(route_id, direction_id)` entries, the function now reads `routes.txt` once more to get each route's `route_short_name`. For any bus route where `route_short_name != route_id`, an alias entry `(route_short_name, direction_id)` is added to `_shape_lookup` via `setdefault` (so an existing `route_id` entry is never overwritten).

---

## ✅ Transfer `WalkLeg` missing turn-by-turn directions — FIXED

**Fixed in:** `backend/transit_graph.py` `_path_to_route()` — the inter-station transfer `WalkLeg` constructor now includes `directions=street_walk_directions(flat, flon, tlat, tlon)`, consistent with the origin and destination walk legs.

---

## ✅ `geocode_google` not thread-safe under concurrent requests — FIXED

**Fixed in:** `backend/gtfs_loader.py` — added module-level `_geocode_lock = threading.Lock()`. `geocode_google()` now uses a double-checked locking pattern: fast path reads the cache without a lock; slow path acquires the lock, re-checks the cache, then performs the network call, cache write, and counter increment inside the lock. All mutation of `_geocode_cache` and `_geocode_call_counter` is serialised.

---

## ✅ MapLibre map renders as black screen on startup — FIXED (3 root causes)

**Files:** `frontend/src/MapView.jsx`, `frontend/src/App.css`, `frontend/package.json`

Three independent bugs combined to produce a black map panel:

**Root cause 1 — React StrictMode double-invoke:**
React 18 StrictMode intentionally mounts → unmounts → remounts every component. The original `useEffect` created a MapLibre map immediately; StrictMode's synchronous cleanup (`map.remove()`) destroyed it before it could render. The second mount had no container to attach to.
**Fix:** Wrap map initialization in `setTimeout(0)`.

**Root cause 2 — MapLibre CSS overrides container position:**
MapLibre appends `.maplibregl-map { position: relative }` to the container element after initialization, overriding the component's `position: absolute; inset: 0` rule.
**Fix:** `position: absolute !important` plus `width: 100%; height: 100%` on `.map-container`.

**Root cause 3 — OpenFreeMap Positron style has expression errors in MapLibre v4/v5:**
The Positron style uses expressions that return `null` where MapLibre expects a number.
**Fix:** Switch tile style URL from `positron` to `liberty`. Also downgraded `maplibre-gl` from `^5.22.0` to `^4.7.1`.

---

## ✅ Map defaults to black panel before first route search — FIXED

**File:** `frontend/src/MapView.jsx`

**Fixed in:** Changed `DEFAULT_CENTER` to `[-87.654, 41.966]` (Uptown, Chicago) and `DEFAULT_ZOOM` to `13`. The map now renders the Uptown neighborhood on startup.

---

## ✅ Walking paths drawn as Haversine straight lines instead of following streets — FIXED

**Files:** `backend/requirements.txt`, `backend/walking.py`

**Fixed in:** Added `scikit-learn>=1.0` to `backend/requirements.txt`. `ox.nearest_nodes()` requires `scikit-learn` for spatial indexing on unprojected graphs; without it, every call raised `ImportError` — silently caught and falling back to straight-line Haversine paths.

---

## ✅ 4 high-severity npm vulnerabilities in `serialize-javascript` — FIXED

**File:** `frontend/package.json`

**Fixed in:** Added an npm `overrides` entry to force the patched version:
```json
"overrides": {
  "serialize-javascript": "^7.0.5"
}
```

---

## ✅ Bus transit leg not drawn on map when `clip_shape` returns single-element list — FIXED

**Files:** `backend/transit_graph.py`

**Fixed in:** When `lo >= hi`, return a 2-point straight line between the actual stop coordinates rather than an unrenderable 1-element list:
```python
if lo >= hi:
    return [[board_lat, board_lon], [exit_lat, exit_lon]]
```

---

## ✅ Bus route shown as straight Haversine line — wrong shape selected (short-turn trip) — FIXED

**File:** `backend/transit_graph.py` — `_build_shape_lookup()`

**Fixed in:** Select the shape with the **most points** for each route/direction instead of the first encountered:
```python
n = len(shapes.get(shape_id, []))
if n > route_dir_shape_len.get(key, -1):
    route_dir_to_shape[key] = shape_id
    route_dir_shape_len[key] = n
```

---

## ✅ Unclosed file handle in `fetch_gtfs.py` validation step — FIXED

**Fixed in:** `backend/fetch_gtfs.py` `validate_and_report()` — bare `open(path, ...)` replaced with `with open(path, ...) as fh:` context manager.

---

## ✅ Train routing returns no results for addresses >0.5 miles from nearest station — FIXED

**File:** `backend/transit_graph.py` `find_routes()`

**Fixed in:** Both the origin and destination station searches now use a progressive-expansion loop: 0.25 → 0.5 → 0.75 → 1.0 → 1.25 → 1.5 → 1.75 → 2.0 miles (+0.25 per step). The first radius that returns at least one station is used.

---

## ✅ Bus routing returns no results when best exit stop is marginally outside 0.5-mile cutoff — FIXED

**File:** `backend/transit_graph.py` `find_bus_routes()`

**Fixed in:** Replaced the hard 0.5-mile cutoff with a progressive-expansion threshold matching the train station fix (0.25 → 2.0 miles, +0.25 per step). Restructured into two passes: **Pass 1** finds the best exit stop per route+direction using haversine only. **Pass 2** builds Route objects — including OSMnx walk times, walk paths, and directions — only for candidates within the chosen threshold.
