# Technical Debt Paid Off

A log of technical debt items that have been identified and resolved. Entries are moved here from [`Technical_Debt.md`](Technical_Debt.md) when the debt is paid off.

Priority: 🔴 High · 🟡 Medium · 🟢 Low.

---

## 🔴 TD-001 · Haversine distance formula duplicated in three files — RESOLVED

**Files affected:** `backend/walking.py`, `backend/gtfs_loader.py`, `backend/transit_graph.py`, `backend/fetch_station_exits.py`

**What it was:** The Haversine great-circle distance formula was copy-pasted across four modules (the audit identified three; `fetch_station_exits.py` held a fourth). The copies had begun to diverge in variable names and intermediate-step style.

**How it was resolved:** Created `backend/utils.py` with a single canonical `haversine_miles(lat1, lon1, lat2, lon2) -> float`. All four files now import it as `from utils import haversine_miles as _haversine_miles`, preserving existing call-site names. `walking.py`'s `_haversine_walk_minutes` wrapper was simplified to call `haversine_miles` and convert to minutes. `transit_graph.py` updated its import source from `gtfs_loader` to `utils`.

**Date resolved:** 2026-04-20

---

## 🔴 TD-002 · `recommend()` endpoint was 325 lines doing 10+ distinct tasks — RESOLVED

**File affected:** `backend/main.py`

**What it was:** The `/recommend` FastAPI handler combined input validation, cache lookup, location resolution, CTA API calls, train routing, bus routing, bus-transfer routing, transfer-stop arrivals, alert fetching, Claude prompt assembly, Claude API call, response formatting, and cache write — all in a single function body. Each step was inlined with no seams, making individual steps impossible to test or modify in isolation.

**How it was resolved:** Decomposed the function body into seven focused helpers inserted in a new "recommend() sub-steps" section of `main.py`:

- `_validate_api_keys(request, byok_key)` — checks CTA and Anthropic key presence
- `_resolve_locations(loop, request)` — resolves origin/destination to stations, bus stops, and coordinates; enforces same-location guard
- `_fetch_arrivals(request, origin_stations, origin_bus_stops)` — fetches live train and bus arrivals; applies bus-fullness filter
- `_run_routing(request, origin_coords, dest_coords, ...)` — runs unified graph routing and bus-transfer routing; merges and sorts results
- `_fetch_transfer_arrivals(ranked_routes)` — fetches live arrivals at transfer stops (Feature D) and annotates legs in-place
- `_call_claude(claude_client, prompt, ranked_routes)` — selects model by query complexity, calls Claude, returns `(text, model_label)`
- `_format_response(...)` — assembles the final JSON-serialisable response dict

`recommend()` itself became a ~85-line thin coordinator: rate-limit check → BYOK client selection → cache check → call each helper in sequence → cache write → return. No logic was changed; all behaviour is identical.

**Date resolved:** 2026-04-20

---

## 🔴 TD-003 · Pre-production geocode rate-limit guard still in production code — RESOLVED

**File affected:** `backend/gtfs_loader.py` (~lines 60–66)

**What it was:** A `TODO` comment marked ~30 lines of code — `_GEOCODE_CALL_LIMIT`, `_geocode_call_counter`, `_load_geocode_counter`, `_save_geocode_counter`, and an in-function rate-limit check — as temporary pre-deployment scaffolding to be removed once production call volume was known. The guard was hardcoded to 9,500 calls/month with no way to change it without a code deploy.

**How it was resolved:** Promoted the guard to a first-class production feature. The hardcoded `_GEOCODE_CALL_LIMIT = 9_500` was replaced with `int(os.getenv("GEOCODE_MONTHLY_LIMIT", "9500"))`, making the limit configurable via Railway env var. The in-function check was updated to short-circuit when `GEOCODE_MONTHLY_LIMIT=0` (disables the cap entirely). All `TEMPORARY`/`TODO` comments were removed and replaced with a concise operational comment. No counter logic was deleted — it is now the correct permanent implementation.

**Date resolved:** 2026-04-20

---

## 🟡 TD-004 · Claude model names hardcoded — cannot be changed without a code deploy — RESOLVED

**File affected:** `backend/main.py` (inside `_call_claude`)

**What it was:** `"claude-haiku-4-5-20251001"` and `"claude-sonnet-4-6"` were hardcoded string literals inside `_call_claude`. Swapping models for a new release or A/B test required a code change and redeploy.

**How it was resolved:** `_call_claude` now reads `os.getenv("CLAUDE_SIMPLE_MODEL", "claude-haiku-4-5-20251001")` and `os.getenv("CLAUDE_COMPLEX_MODEL", "claude-sonnet-4-6")` at call time. The production defaults are unchanged; model IDs can now be overridden via Railway env vars without a deploy.

**Date resolved:** 2026-04-20

---

## 🟡 TD-006 · Chicago bounding box hardcoded in three separate files — RESOLVED

**Files affected:** `backend/utils.py`, `backend/gtfs_loader.py`, `backend/fetch_station_exits.py`, `backend/fetch_street_graph.py`

**What it was:** The Chicago geographic bounds were defined three times as independent string/tuple literals in different formats (`"SW|NE"` for Google Maps, `"S,W,N,E"` for Overpass, `(W,S,E,N)` tuple for OSMnx). The street-graph bounds (a tighter sub-area) were also a bare literal with a TODO comment.

**How it was resolved:** Added canonical corner constants (`CHICAGO_SOUTH/NORTH/WEST/EAST`) and four derived format-specific constants (`CHICAGO_BBOX_GOOGLE`, `CHICAGO_BBOX_OVERPASS`, `CHICAGO_BBOX_OSMNX`, `STREET_GRAPH_BBOX_OSMNX`) to `backend/utils.py`. Each of the three files now imports the relevant constant; the TODO on `fetch_street_graph.py`'s local literal was replaced with an import and a pointer to the utils definition. A single edit to `utils.py` now propagates any coverage change to all consumers.

**Date resolved:** 2026-04-20

---

## 🟡 TD-007 · Inconsistent error sentinels from `cta_client.py` — RESOLVED

**Files affected:** `backend/cta_client.py`

**What it was:** Train arrivals signalled errors via `{"error": str}` dicts; bus arrivals used the structurally different `{"_bus_error": True, "exc": str}`. The two consumers (`get_train_arrivals`, `get_bus_arrivals`) each had separate ad-hoc filter logic keyed to their own sentinel shape.

**How it was resolved:** Standardised on a single sentinel shape `{"_error": True, "exc": str, "mode": "train"|"bus"}` across both transport modes. Both `_fetch_station_arrivals` and `_fetch_bus_chunk` now produce this shape on failure. Both collector functions filter with `item.get("_error")` and log via `e["exc"]`, eliminating the per-mode branching. Adding a third transport mode now requires no changes to filter logic.

**Date resolved:** 2026-04-20

---

## 🟡 TD-008 · Alerts API silently returns `[]` on any exception — RESOLVED

**Files affected:** `backend/cta_client.py`

**What it was:** `_fetch_alerts_for_route()` caught all exceptions with a bare `except Exception: return []`. Callers had no way to distinguish "no active alerts" from "API unreachable" or "JSON parse failure", and a sustained Alerts API outage left no trace in Railway logs.

**How it was resolved:** Changed the except clause to `except Exception as exc:` and added `print(f"[cta_client] WARNING: Alerts API fetch failed for route {route_id!r}: {exc}")` before returning `[]`. The function still returns `[]` on failure (graceful degradation preserved), but failures are now visible in Railway logs for diagnosis.

**Date resolved:** 2026-04-20

---

## 🟡 TD-009 · `find_bus_transfer_routes()` is 303 lines mixing two distinct passes — RESOLVED

**File affected:** `backend/transit_graph.py` (~lines 1575–1878)

**What it was:** The function combined candidate stop selection (spatial filtering, Haversine ranking) and route object assembly (OSMnx walk times, stop sequence iteration, path building) in one 303-line monolithic body. There was no seam between the two passes, making it impossible to profile, test, or swap the candidate-selection strategy without reading the entire function.

**How it was resolved:** Split into two private helpers inserted immediately before the public function:

- `_select_transfer_candidates(origin_lat, origin_lon, dest_lat, dest_lon, bus_arrivals, origin_bus_stops, sequences)` — Pass 1, pure haversine/spatial data filtering. Returns `(candidate_map, board_index)`. No OSMnx calls; O(arrivals × seq_A × nearby × seq_B) but all in-memory.
- `_build_transfer_routes(candidate_map, board_index, bus_arrivals, sequences, origin_lat, origin_lon, dest_lat, dest_lon, n_routes)` — Pass 2, Route object assembly. Performs all OSMnx street-walk calls, applies the 90-minute trip cap, and assembles `WalkLeg` / `TransitLeg` objects.

`find_bus_transfer_routes()` is now a thin coordinator: guard check → call `_select_transfer_candidates` → early-return if empty → call `_build_transfer_routes`. All behaviour is identical; no constants, logic, or scoring was changed. The `boarding_hav` computation in Pass 1 was also simplified (removed a redundant ternary around `_bus_stop_coords.get`).

**Date resolved:** 2026-04-20

---

## 🟡 TD-005 · CTA API base URLs hardcoded in two files — RESOLVED

**Files affected:** `backend/cta_client.py` (~lines 22–23), `backend/active_routes.py` (~lines 47–48)

**What it was:** `TRAIN_BASE`, `BUS_BASE`, `BUS_ROUTES_URL`, and `TRAIN_POSITIONS_URL` were hardcoded string literals. Pointing the app at a staging or mock CTA endpoint required editing source code, making integration testing against a test double impossible.

**How it was resolved:** Both files now derive `_CTA_TRAIN_BASE` from `os.getenv("CTA_TRAIN_API_URL", "https://lapi.transitchicago.com/api/1.0")` and `_CTA_BUS_BASE` from `os.getenv("CTA_BUS_API_URL", "https://www.ctabustracker.com/bustime/api/v3")`. The four endpoint constants are assembled by appending path suffixes to those base vars. Production defaults are unchanged; both files share the same two env vars so a single Railway variable change redirects all CTA traffic.

**Date resolved:** 2026-04-20

---

## 🟡 TD-010 · Two independent spatial-grid implementations with no shared base — RESOLVED

**Files affected:** `backend/utils.py`, `backend/gtfs_loader.py`, `backend/transit_graph.py`

**What it was:** `gtfs_loader.py` and `transit_graph.py` each maintained an independent cell-based spatial bucketing implementation. `gtfs_loader.py` used `_SPATIAL_CELL_LAT_DEG`/`_SPATIAL_CELL_LON_DEG` (~1-mile cells) with `_spatial_key`, `_spatial_index` (returns `dict[cell → list[stop_dict]]`), and `_candidates_within` (manual 40-line nested-loop query). `transit_graph.py` used hard-coded `0.005°` cells in `_build_bus_stop_grid` and a separate 16-line `_stops_near` with its own degree-expansion constants (`0.0145`, `0.0175`). The two implementations diverged in cell size, stored type, and query logic.

**How it was resolved:** Added a generic `SpatialGrid` class to `backend/utils.py`. The class stores `(lat, lon, value)` triples in a `dict[cell → list]`, provides `add(lat, lon, value)` and `query(lat, lon, radius_miles) → list[(dist, value)]` (bounding-box prefilter + Haversine postfilter), and uses `_MILES_PER_DEG_LAT`/`_MILES_PER_DEG_LON` constants defined once in `utils.py`.

- `gtfs_loader.py`: imports `SpatialGrid`; `_spatial_index()` now builds and returns a `SpatialGrid` instead of a dict; `_candidates_within()` collapsed to a single-line `return _spatial_index(kind).query(lat, lon, radius_miles)`. `_spatial_key()` and all manual loop/filter logic removed.
- `transit_graph.py`: imports `SpatialGrid`; `_build_bus_stop_grid()` now constructs a `SpatialGrid(cell_lat_deg=0.005, cell_lon_deg=0.005)` via `grid.add(lat, lon, sid)`; `_bus_stop_grid` type changed from `dict` to `SpatialGrid | None`; `_stops_near()` collapsed to a one-liner. `_bus_stop_coords` is retained for direct stop-id coordinate lookups in `_select_transfer_candidates`.

**Date resolved:** 2026-04-20

---

## 🟢 TD-011 · Magic numbers scattered throughout backend with no config or documentation — RESOLVED

**Files affected:** `backend/main.py`, `backend/transit_graph.py`

**What it was:** Several tuning parameters were either bare literals with no naming (same-location threshold `0.001²` in `main.py`) or named constants defined inside function bodies rather than at module level (`_TRANSFER_RADIUS_MILES`, `_TRANSFER_WALK_CAP_MIN`, `_DETOUR_FACTOR` inside `_build_graph()`; `_MAX_EXIT_DIST`, `_MAX_TRANSFER_WALK`, `_FWD_PROGRESS_RATIO`, `_MAX_CANDIDATES_PER_ARRIVAL` inside `_select_transfer_candidates()`; the score factor `26.0` with only a comment). Constants defined inside function bodies cannot be discovered by project-wide search or referenced from documentation.

**How it was resolved:**
- `main.py`: `(0.001 ** 2)` replaced with named constant `_SAME_LOCATION_THRESHOLD_DEG2: float = 0.001 ** 2` with a `# degrees²` annotation and a human-readable comment (≈0.07 miles at Chicago's latitude). Unit comments added to `_CACHE_TTL_SECONDS` (`# seconds`) and `_CACHE_MAX_SIZE` (`# entries`).
- `transit_graph.py`: All seven function-local constants moved to module level in two named sections. `_TRANSFER_RADIUS_MILES`, `_TRANSFER_WALK_CAP_MIN`, `_DETOUR_FACTOR` placed in an "Intermodal walk-edge tuning constants" block. `_MAX_EXIT_DIST`, `_MAX_TRANSFER_WALK`, `_FWD_PROGRESS_RATIO`, `_MAX_CANDIDATES_PER_ARRIVAL`, and the new `_TRANSFER_SCORE_WALK_FACTOR = 26.0` placed in a "Bus-to-bus transfer candidate scoring" block. Each constant has a one-line comment with units and purpose.

**Date resolved:** 2026-04-20

---

## 🟢 TD-012 · `lru_cache` on functions returning mutable lists — caller must not mutate — RESOLVED

**File affected:** `backend/walking.py`

**What it was:** `walk_directions` and `walk_path` were decorated with `@lru_cache`. On cache hits, the cache returned the *same list object* that was stored. Any caller that mutated the returned list would corrupt future cache hits. The risk was documented with inline comments but not structurally enforced.

**How it was resolved:** Both cached functions were renamed to private implementations (`_walk_directions_impl`, `_walk_path_impl`) that return immutable containers: `_walk_directions_impl` returns a `tuple` of step dicts; `_walk_path_impl` returns a `tuple` of `(lat, lon)` tuples. Public wrappers `walk_directions` and `walk_path` (not cached) call the private impl and return a fresh `list` on every invocation — `list(impl(...))` for directions and `[list(pt) for pt in impl(...)]` for path points. The `lru_cache` now stores immutable tuples; callers always receive a new list that is safe to mutate. No call sites changed.

**Date resolved:** 2026-04-20

---

## 🟢 TD-013 · Module-level mutable globals managed with `global` statements in `transit_graph.py` — RESOLVED

**File affected:** `backend/transit_graph.py`

**What it was:** `_shape_lookup`, `_bus_seq_cache`, `_stop_to_routes`, `_bus_stop_grid`, `_bus_stop_coords`, and `_station_exits` were module-level dicts/None values mutated via `global` inside initializer functions, with no documented lifecycle contract.

**How it was resolved:** Added a "Module-level state — initialization contract" comment block immediately before the state variables. The block enumerates all six globals, maps each to its single initializer function and the lifecycle phase (module import vs. `warm_up()`), and notes that no writes occur after startup so concurrent reads are safe under the GIL. No behavior was changed; the fix is documentation only, as the debt specified "No immediate behavior change required."

**Date resolved:** 2026-04-20

---

## 🟢 TD-014 · `fetch_street_graph.py` bounding box expansion left as a TODO — RESOLVED

**File affected:** `backend/utils.py`

**What it was:** A bare TODO comment in `utils.py` noted that `STREET_GRAPH_SOUTH` should be expanded toward 50th St (41.80°) when Railway memory allows. The comment gave no actionable expansion steps.

**How it was resolved:** The one-line TODO was replaced with a multi-line expansion guide in `utils.py` documenting: the current coverage bounds (Howard St → ~21st St/Cermak Rd), the target expansion (50th St ≈ 41.80°, Cicero Ave ≈ -87.745°), and a four-step checklist (verify Railway RAM headroom ≥ 2 GB free, lower the two constants, re-run `fetch_street_graph.py`, redeploy and confirm no OOM). The `fetch_street_graph.py` header comment already pointed to the `utils.py` definition — no change needed there. The expansion itself is deferred until Railway memory headroom is confirmed; the checklist is the contract for a future session.

**Date resolved:** 2026-04-20
