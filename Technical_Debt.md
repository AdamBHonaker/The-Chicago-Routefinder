# Technical Debt

Known technical debt catalogued for future resolution. Priority: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When an item in this file is resolved, **delete its entry from this file** and add a corresponding entry to [`Technical_Debt_Paid_Off.md`](Technical_Debt_Paid_Off.md) documenting what was changed and how. This file should only ever contain debt that has not yet been addressed.

> **Audit date:** 2026-04-18 · Files scanned: all `backend/*.py`

---

## 🔴 TD-001 · Haversine distance formula duplicated in three files

**Files:** `backend/walking.py` (~line 263), `backend/gtfs_loader.py` (~line 524), `backend/transit_graph.py` (~line 618)

**What it is:** The same Haversine great-circle distance formula is copy-pasted across three modules. Any fix or tuning (e.g. switching to Vincenty) must be applied in three places; the copies are already beginning to diverge (different variable names, slightly different signatures).

**Fix:** Extract into a `backend/utils.py` module with a single `haversine_miles(lat1, lon1, lat2, lon2) -> float` function. Update all three call sites to import from there.

---

## 🔴 TD-002 · `recommend()` endpoint is 325 lines doing 10+ distinct tasks

**File:** `backend/main.py` (~line 625)

**What it is:** The `/recommend` FastAPI handler combines: input validation, cache lookup, location resolution, CTA API calls, train routing, bus routing, transfer detection, alert fetching, Claude prompt assembly, Claude API call, response formatting, and cache write — all in a single function. It is difficult to test, debug, or modify any one step in isolation.

**Fix:** Decompose into focused helpers, e.g. `_resolve_locations()`, `_fetch_routes()`, `_build_prompt()`, `_call_claude()`. The endpoint itself becomes a thin coordinator.

---

## 🔴 TD-003 · Pre-production geocode rate-limit guard still in production code

**File:** `backend/gtfs_loader.py` (~lines 60–66)

**What it is:** A `TODO` comment explicitly marks ~30 lines of code (including `_GEOCODE_CALL_LIMIT`, `_geocode_call_counter`, `_load_geocode_counter`, `_save_geocode_counter`, and an in-function check) as temporary scaffolding to be removed once production call volume is known. This code remains active, cluttering every geocode path with counter logic that was never intended to be permanent.

**Fix:** Assess current production call volume. If below the limit and stable, delete the guard block and all supporting variables. If limits are still needed, promote the limit to a proper env-var config and remove the TODO.

---

## 🟡 TD-004 · Claude model names hardcoded — cannot be changed without a code deploy

**File:** `backend/main.py` (~line 870)

**What it is:** `"claude-haiku-4-5-20251001"` and `"claude-sonnet-4-6"` are hardcoded string literals. Changing the model (e.g. on a new release or for A/B testing) requires a code change and redeploy rather than a Railway environment variable update.

**Fix:** Read from env vars `CLAUDE_SIMPLE_MODEL` / `CLAUDE_COMPLEX_MODEL` with the current values as defaults.

---

## 🟡 TD-005 · CTA API base URLs hardcoded in two files

**Files:** `backend/cta_client.py` (~lines 22–23), `backend/active_routes.py` (~lines 47–48)

**What it is:** `TRAIN_BASE`, `BUS_BASE`, `BUS_ROUTES_URL`, and `TRAIN_POSITIONS_URL` are hardcoded string literals. There is no way to point the app at a staging or mock CTA endpoint without editing source code — making integration testing against a test double impossible.

**Fix:** Move to env vars (`CTA_TRAIN_API_URL`, `CTA_BUS_API_URL`) with the current production URLs as defaults.

---

## 🟡 TD-006 · Chicago bounding box hardcoded in three separate files

**Files:** `backend/gtfs_loader.py` (~line 50), `backend/fetch_station_exits.py` (~line 29), `backend/fetch_street_graph.py` (~line 36)

**What it is:** The Chicago geographic bounds are defined three times as identical or near-identical string/tuple literals. If coverage ever expands (e.g. the south boundary TODO in `fetch_street_graph.py`), all three must be updated in sync.

**Fix:** Define a single `CHICAGO_BBOX` constant (or small config module) and import it in all three places.

---

## 🟡 TD-007 · Inconsistent error sentinels from `cta_client.py`

**File:** `backend/cta_client.py` (~lines 56–64, 165–169)

**What it is:** Train arrivals signal errors by injecting `{"error": str}` dicts into the arrivals list. Bus arrivals use a structurally different sentinel `{"_bus_error": True, "exc": str}`. This asymmetry forces `main.py` to contain separate filtering logic for each transport mode, and makes it easy to add a third mode that is missed by existing filters.

**Fix:** Standardise on one sentinel shape (e.g. `{"_error": True, "exc": str, "mode": "train"|"bus"}`), or — better — raise typed exceptions and let the caller handle them rather than embedding errors in result lists.

---

## 🟡 TD-008 · Alerts API silently returns `[]` on any exception

**File:** `backend/cta_client.py` (~line 270)

**What it is:** The alerts fetch catches all exceptions and returns an empty list without logging. Callers cannot distinguish "no active alerts" from "API unreachable" or "JSON parse failure". A sustained CTA alerts outage would silently suppress all alert information with no diagnostic trail.

**Fix:** Log the exception at `WARNING` level before returning `[]`, so Railway logs surface alerts-API failures without crashing the request.

---

## 🟡 TD-009 · `find_bus_transfer_routes()` is 303 lines mixing two distinct passes

**File:** `backend/transit_graph.py` (~lines 1575–1878)

**What it is:** The function combines candidate stop selection (spatial filtering, Haversine ranking) and route object assembly (OSMnx walk times, stop sequence iteration, path building) in one monolithic body. Profiling, testing, or swapping out the candidate-selection strategy requires reading through all 303 lines to find the right seam.

**Fix:** Split into `_select_transfer_candidates()` (Pass 1, pure data filtering) and `_build_transfer_routes()` (Pass 2, object assembly). The public function becomes a two-line coordinator.

---

## 🟡 TD-010 · Two independent spatial-grid implementations with no shared base

**Files:** `backend/gtfs_loader.py` (~lines 682–694), `backend/transit_graph.py` (~lines 1425–1442)

**What it is:** Both files implement cell-based spatial bucketing (divide lat/lon space into a grid, assign stops to cells, query nearby cells). They use different cell sizes and were written independently. Bug fixes or tuning applied to one copy will not propagate to the other.

**Fix:** Extract a generic `SpatialGrid` class or function into `backend/utils.py` and replace both implementations.

---

## 🟢 TD-011 · Magic numbers scattered throughout backend with no config or documentation

**Files:** `backend/main.py` (~lines 38–39, 733), `backend/gtfs_loader.py` (~lines 68, 183–185), `backend/transit_graph.py` (~lines 55, 81, 84, 618–620), `backend/walking.py` (~lines 24, 26–28), `backend/fetch_gtfs.py` (~lines 57, 68)

**What it is:** Tuning parameters — cache TTL (45 s), max cache size (500), geocode monthly limit (9 500), flush interval (30 s), walking speed (3 mph), block distances, transfer radius (0.15 mi), detour factor (1.3), download chunk size (64 KB), same-location threshold (`0.001²`) — are bare literals with no naming, units, or origin. Changing any one requires knowing which files to search.

**Fix:** Consolidate into named constants at the top of each file (or a shared `config.py`), with a brief unit comment on each (e.g. `# miles`, `# seconds`).

---

## 🟢 TD-012 · `lru_cache` on functions returning mutable lists — caller must not mutate

**File:** `backend/walking.py` (~line 106)

**What it is:** `walk_minutes`, `walk_directions`, and `walk_path` are decorated with `@lru_cache`. On cache hits, the cache returns the *same list object* that was stored. Any caller that mutates the returned list corrupts future cache hits. The current callers are well-behaved, but this is a latent correctness trap for future contributors.

**Fix:** Either return `tuple` from cached functions (immutable by nature) or wrap the return in `list(result)` at each call site to force a copy.

---

## 🟢 TD-013 · Module-level mutable globals managed with `global` statements in `transit_graph.py`

**File:** `backend/transit_graph.py` (~lines 37–38, 78, 95, 1425–1426, 1457)

**What it is:** `_graph_cache`, `_shape_lookup`, `_bus_seq_cache`, `_bus_stop_grid`, and `_station_exits` are module-level dicts/None values mutated via `global` inside functions. This pattern works under the GIL but makes it hard to reason about initialization order, test in isolation, or safely add async initialization paths in the future.

**Fix:** No immediate behavior change required. Document the initialization contract in a module-level comment, or encapsulate state into a `TransitGraph` class with explicit `build()` / `is_built()` lifecycle methods.

---

## 🟢 TD-014 · `fetch_street_graph.py` bounding box expansion left as a TODO

**File:** `backend/fetch_street_graph.py` (~line 35)

**What it is:** A TODO comment notes that the south boundary should be expanded toward 50th St when Railway memory allows. The current hard-coded `BBOX` silently excludes southern Chicago neighborhoods from street-graph walk routing.

**Fix:** Assess current Railway memory headroom. If sufficient, expand the south boundary and remove the TODO. If not, file a project memory note so it is not forgotten when the plan is upgraded.

---
