# Feature Plans & Future Enhancements

Chunked plans for upcoming major features, followed by ideas deferred until post-launch. For chunked features, work through each chunk in order, one chunk per session or per commit. Do not start a chunk until all previous chunks are complete.

---

# Chunked Implementation Plans

---

# Feature A — Train Station Exit Guidance

## Overview

Many CTA train stations have multiple exits spread across a city block. The app currently routes a rider to the alighting station's centroid coordinates and gives OSMnx walk directions from there. This feature improves the final walk leg by:

1. Identifying available exits at the alighting station
2. Recommending the exit that minimises the remaining walk to the destination
3. Optionally letting the rider choose a different exit and recalculating directions

**Why it matters:** Getting the exit wrong adds confusion and unnecessary street-level walking, especially at large stations like Clark/Lake, Jackson, O'Hare, or Howard where exits are spread across a full city block.

**Status: ✅ Complete (2026-04-13)**

---

## Data note — before starting any chunk

CTA GTFS `stops.txt` contains platform stops (30000–39999) and parent stations (40000–49999) but does **not** contain named exit locations. The best free source is OpenStreetMap `railway=subway_entrance` nodes. An Overpass API query can pull all Chicago CTA subway entrance nodes with their lat/lon and `ref` tag (which often names the exit, e.g. "Damen Ave / Milwaukee Ave").

Manual curation of the 15–20 most-used stations is an acceptable first pass and avoids a full OSM data pipeline.

---

## Chunk 1 — Data: Build exit coordinates file

**Files:** `backend/fetch_station_exits.py` (new), `backend/station_exits.json` (generated)

**What to build:**
- Write a one-time script `fetch_station_exits.py` that queries the Overpass API for all `railway=subway_entrance` nodes within Chicago's bounding box
- For each entrance node, extract: `osm_id`, `lat`, `lon`, `name` or `ref` (exit label), and the nearest CTA parent station mapid (by haversine distance to known station coordinates from `_load_parent_stations()`)
- Write results to `backend/station_exits.json` as:
  ```json
  {
    "40900": [
      {"label": "Damen Ave", "lat": 41.9099, "lon": -87.6789},
      {"label": "Milwaukee Ave", "lat": 41.9092, "lon": -87.6798}
    ]
  }
  ```
  where the key is the CTA parent station mapid.
- `station_exits.json` should be committed to the repo (it's small, static, manually correctable)
- After generating, manually review and correct any misassigned exits for the 10–15 most-used stations

**Notes:**
- Overpass query: `node["railway"="subway_entrance"](41.64,-87.94,42.02,-87.52)`
- If OSM coverage is sparse for a station, add entries manually — the JSON format is simple
- This script is run once (or re-run after OSM data improves); it does not run at server startup

---

## Chunk 2 — Backend: Load exit data at startup

**Files:** `backend/transit_graph.py`

**What to build:**
- Add `_load_station_exits() -> dict[str, list[dict]]` — reads `station_exits.json` at import time, returns `{mapid: [{label, lat, lon}, ...]}`. Returns `{}` gracefully if file not found (so the server still starts without exits data).
- Store result in module-level `_station_exits` dict (same pattern as `_shape_lookup`)
- Add public helper `get_station_exits(mapid: str) -> list[dict]` — returns the exit list for a station, or `[]` if none known
- Call nothing extra in `warm_up()` — this is loaded at import time (data is tiny, ~5 KB)

---

## Chunk 3 — Backend: Exit selection logic

**Files:** `backend/transit_graph.py`

**What to build:**
- Add `best_exit(mapid: str, dest_lat: float, dest_lon: float) -> dict | None`
  - Gets exits for the station via `get_station_exits(mapid)`
  - If no exits known: returns `None` (caller falls back to station centroid)
  - Scores each exit by `street_walk_minutes(exit_lat, exit_lon, dest_lat, dest_lon)`
  - Returns the exit dict with the minimum walk time, with an added `"walk_minutes"` key

**Notes:**
- `street_walk_minutes` is already imported and cached — no extra I/O
- Do not call `street_walk_directions` here — that happens in Chunk 4 once the exit is selected

---

## Chunk 4 — Backend: Thread exit into walk leg + API response

**Files:** `backend/transit_graph.py`, `backend/main.py`

**What to build:**

In `transit_graph.py`:
- In `_path_to_route()`, for the **destination walk leg** (when `to_node == DEST`):
  - Call `best_exit(from_node, dest_lat, dest_lon)`
  - If an exit is found: use its `(lat, lon)` as the walk origin instead of the station centroid; set `exit_label` on the `WalkLeg`
  - If no exit found: behaviour unchanged (station centroid as before)
- In `find_bus_routes()`, same change on the exit walk leg
- Add `exit_label: str = ""` field to `WalkLeg` dataclass

In `main.py`:
- Add `"exit_label": leg.exit_label` to the walk leg serialization in the `/recommend` response

**Notes:**
- `walk_directions` is called with the exit coords instead of station centroid — the street-level directions will now start from the right point
- `path_points` similarly uses exit coords as origin — the dashed walk line on the map will start from the exit, not the station centre

---

## Chunk 5 — Frontend: Show exit label on final walk leg

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`

**What to build:**
- In `WalkLegItem`: if `leg.exit_label` is present and `leg.to === "Your destination"`, show the exit label between the summary line and the Steps toggle:
  ```
  Walk 6 min to your destination
  Exit: Milwaukee Ave ›
  ↓ S on Milwaukee Ave · 2 min
  ↑ W on Dickens Ave · 1 min
  ```
- Style the exit label as a small secondary line (muted color, slightly smaller than the main leg text)
- The Steps toggle behaviour is unchanged — it expands/collapses the street-level directions below the exit label

**Future extension (Chunk 6, separate session):** Let the rider tap the exit label to see all available exits and pick a different one. This requires a client-side recalculation — the `available_exits` array would need to be included in the API response (add in Chunk 4 when ready to build this).

---

# Feature C — Multi-Leg Bus Routing (Bus + Bus Transfers)

## Overview

The current `find_bus_routes()` finds single-bus direct routes only. Trips requiring a bus transfer (e.g. Route 81 westbound to Kedzie, then Route 78 southbound) are not surfaced. Single-bus routing covers the majority of useful bus trips; multi-leg bus routing is a significant architectural addition best done post-launch with real trip data to validate against.

**Status: ✅ Complete (2026-04-13)**

---

## Scoping decisions — resolved

1. **Architecture**: Standalone `find_bus_transfer_routes()` function, NOT via the NetworkX graph. Feature B will later extend the graph for intermodal (train+bus) routing; Feature C keeps bus+bus transfers self-contained and independently implementable.

2. **Transfer model**:
   - One transfer preferred, max two transfers (bus A → walk → bus B → walk → bus c). Three-bus chains are not surfaced.
   - Max transfer walk: 0.25 miles (~5 min)
   - Leg 2 wait time: **7.5 min fixed estimate** (half of a typical 15-min CTA headway). Live arrivals at the transfer stop are not queried in v1 — this is a known limitation. Claude's recommendation copy will reflect this.

3. **Activation gate**: `find_bus_transfer_routes()` is only called when `find_bus_routes()` returns no results OR all single-bus candidates have an exit haversine distance > 0.5 miles from the destination. Never called when a direct bus already works well — avoids latency and inferior transfer suggestions.

4. **Pruning rules** (controls combinatorial explosion):
   - Transfer stops: only stops on route A where haversine distance to destination improves by ≥ 10% vs. the boarding stop (forward-progress filter)
   - Route B candidates: exit stop must be within 0.5 miles of destination (same threshold as single-bus routing)
   - Max 3 transfer candidates per live arrival
   - Total trip capped at 90 minutes

5. **Spatial index**: Grid-based stop lookup (0.005° cells) built at startup, avoids O(11,000) haversine checks per candidate transfer point. A 0.25-mile radius search checks at most ~9 cells (~150 stops).

6. **Stop-to-routes index**: Invert `get_bus_stop_sequences()` once at startup → `{stop_id: [(short_name, did, idx_in_seq, arr_min), ...]}`. Enables O(1) lookup of "which routes serve stop X?" during transfer candidate evaluation.

---

## Chunk 1 — Startup: Bus stop spatial grid index

**Files:** `backend/transit_graph.py`

**What to build:**
- Add a module-level `_bus_stop_grid: dict[tuple[int, int], list[str]]` — a dict keyed by `(int(lat / 0.005), int(lon / 0.005))` cell, value is a list of stop_ids in that cell
- Add `_bus_stop_coords: dict[str, tuple[float, float]]` = `{stop_id: (lat, lon)}` — flat coordinate lookup for haversine post-filtering
- Populate both at module import time by calling `_load_bus_stop_lookup()` (same source used by `get_bus_stop_sequences()`)
- Add `def _stops_near(lat: float, lon: float, radius_miles: float = 0.25) -> list[str]`:
  - Converts `radius_miles` to degree offsets (use 0.0145° per mile for lat, 0.0175° per mile for lon at Chicago's latitude)
  - Queries all grid cells in the bounding box
  - Post-filters by exact `_haversine_miles`
  - Returns list of stop_ids within radius

**Notes:**
- 0.005° ≈ 0.34 miles lat / 0.27 miles lon at Chicago latitude — a 0.25-mile radius search covers at most a 3×3 = 9-cell window, ~150 stops worst case
- `_load_bus_stop_lookup()` is already defined at the bottom of `transit_graph.py` — call it once at module level for this index (second call is cheap; data is identical to what `get_bus_stop_sequences()` uses internally)
- Do not `lru_cache` `_stops_near` — it is fast enough without caching and caching lat/lon float keys risks unbounded cache growth

---

## Chunk 2 — Startup: Stop-to-routes index

**Files:** `backend/transit_graph.py`

**What to build:**
- Add module-level `_stop_to_routes: dict[str, list[tuple[str, str, int, float]]]` — initially `{}`
- Add `def _build_stop_to_routes() -> None`:
  - Iterates `get_bus_stop_sequences().items()`
  - For each `(short_name, did), stops` and each `(stop_id, _, _, _, arr_min)` at index `idx`:
    - Appends `(short_name, did, idx, arr_min)` to `_stop_to_routes[stop_id]`
  - Logs the total number of (stop, route) entries at completion
- Call `_build_stop_to_routes()` from `warm_up()` immediately after `get_bus_stop_sequences()` and before `_build_shape_lookup()`

**Notes:**
- This is a pure in-memory index inversion — no I/O, runs in under a second
- After this chunk, answering "which routes serve stop X?" is `_stop_to_routes.get(stop_id, [])`
- The `arr_min` stored per entry is used in Chunk 3 to compute in-vehicle time for leg 2

---

## Chunk 3 — Backend: Transfer candidate algorithm

**Files:** `backend/transit_graph.py`

**What to build:**

Add `find_bus_transfer_routes(origin_lat, origin_lon, dest_lat, dest_lon, bus_arrivals, origin_bus_stops, n_routes=3) -> list[tuple[float, int, object]]` — same signature and return format as `find_bus_routes()`.

**Pass 1 — find candidate transfer stops** (haversine only):
- Same board_walk + board_index setup as `find_bus_routes()`
- For each live arrival, get the sequence for `(route, direction)` from `get_bus_stop_sequences()`
- Scan forward from the boarding stop; for each stop Sk:
  - Skip if `_haversine_miles(Sk.lat, Sk.lon, dest_lat, dest_lon) >= _haversine_miles(boarding_stop.lat, boarding_stop.lon, dest_lat, dest_lon) * 0.9` (no forward progress)
  - Call `_stops_near(Sk.lat, Sk.lon, 0.25)` → nearby stop ids
  - For each nearby stop T, check `_stop_to_routes.get(T, [])` → routes serving T
  - For each route B key `(short_B, did_B)`, scan forward from T's index in route B's sequence to find the exit stop closest to destination
  - If that exit stop is within 0.5 miles of destination: record `(route_A_key, Sk_idx, T_stop_id, route_B_key, exit_B_idx)` as a candidate
- Keep only top 3 candidates per live arrival (by raw haversine score: exit_B haversine + transfer walk haversine)
- `_stops_near` must not return stops that are on the same route+direction as route A (avoid "transfer to yourself")

**Pass 2 — build Route objects for surviving candidates** (OSMnx calls):
- For each candidate:
  - `board_walk_min` — from `origin_bus_stops` (same as `find_bus_routes()`)
  - `in_vehicle_A` — `arr_time[Sk] - arr_time[boarding_stop]` (from sequence arr_minutes)
  - `transfer_walk_min` — `street_walk_minutes(Sk.lat, Sk.lon, T.lat, T.lon)` (OSMnx, cached)
  - `in_vehicle_B` — `arr_time[exit_B] - arr_time[T]` (from route B's sequence arr_minutes)
  - `exit_walk_min` — `street_walk_minutes(exit_B.lat, exit_B.lon, dest_lat, dest_lon)` (OSMnx, cached)
  - Skip if total exceeds 90 minutes
  - Assemble 5-leg `Route`:
    ```
    WalkLeg  (origin → boarding_stop_A)
    TransitLeg (route A: boarding_stop_A → Sk)
    WalkLeg  (Sk → T)           ← transfer walk; minutes=0 if same stop
    TransitLeg (route B: T → exit_B)
    WalkLeg  (exit_B → destination)
    ```
  - `shape_points` for both transit legs via `clip_shape(get_shape(short, did), ...)` (same as `find_bus_routes()`)
  - `route.transfers = 1`
- Sort by `total_minutes_no_wait + wait_A + 7.5` (7.5 = estimated leg 2 wait), return top `n_routes`

**Notes:**
- The 7.5 min leg-2 wait is included in the sort key but NOT added to `route.walk_minutes_total` or `route.transit_minutes` — these retain their strict definitions. Document this in the function docstring.
- If Sk and T are the same stop (same stop_id, different route): the transfer WalkLeg has `minutes=0`, `from_name=to_name=stop_name`. Still include it so the frontend renders a transfer indicator.
- The `wait_min` returned in the tuple `(total, wait_min, route)` is the live wait for bus A only (same as `find_bus_routes()`)

---

## Chunk 4 — Backend: Integrate into main.py

**Files:** `backend/main.py`

**What to build:**
- Import `find_bus_transfer_routes` from `transit_graph`
- Add helper `def _bus_exit_dist(route) -> float` — returns the haversine distance from the last `WalkLeg`'s origin coords to destination. Use `get_station_coords` pattern or store coords on the leg. Simpler: check `route.legs[-2].to_mapid` and look up in `_bus_stop_coords` (move that dict to a public or accessible location), or just check `route.walk_minutes_total` as a proxy (> 15 min walk ≈ > 0.75 miles). **Preferred shortcut:** check if `find_bus_routes()` returned an empty list rather than inspecting exit distances.
- In the bus routing block, after `find_bus_routes()` returns:
  ```python
  if not bus_ranked and request.transit_mode in ("Bus", "All"):
      try:
          transfer_ranked = find_bus_transfer_routes(
              origin_lat, origin_lon, dest_lat, dest_lon,
              bus_arrivals, origin_bus_stops, n_routes=3,
          )
          bus_ranked = transfer_ranked
      except Exception:
          traceback.print_exc()
  ```
- Merge `bus_ranked` with any train routes as before — no format changes needed
- `build_prompt()` requires no changes — `Route.transfers` and the multi-leg serialization already work

**Notes:**
- Start simple: only call `find_bus_transfer_routes()` when `find_bus_routes()` returned empty. Expand the activation gate in a follow-up if real-world testing shows direct-bus results are often poor quality.
- Do not call `find_bus_transfer_routes()` when `transit_mode == "Train"` — same guard as `find_bus_routes()`

---

## Chunk 5 — Frontend: Verify transfer route cards render correctly

**Files:** `frontend/src/App.jsx`, `frontend/src/MapView.jsx`

**What to verify/fix:**
- A 5-leg route (walk + bus + walk + bus + walk) should render in `RouteLegs` without changes — each leg is handled by type and the list can be any length
- Transfer walk leg: `from_name` and `to_name` are bus stop names. Verify `WalkLegItem` renders these correctly (it already handles non-"Your location"/"Your destination" names; confirm visually)
- Zero-minute transfer walk leg (same stop, different route): verify it renders without a blank or broken line item
- Map: `renderRoute()` will produce two colored bus route segments for the two `TransitLeg`s. Verify `BUS_DIRECTION_COLORS` lookup works for both; if a direction string isn't in the map, the fallback color must not crash
- Manual test: find a real Chicago trip requiring a transfer (e.g. Humboldt Park → Bridgeport, or Rogers Park → Midway) and confirm the full route card and map display correctly end-to-end

---

# Feature B — Intermodal Routing (Train + Bus in One Trip)

## Overview

Train and bus routes are currently found independently (`find_routes()` for trains, `find_bus_routes()` for buses) and merged by total time in `main.py`. A combined trip — walk → Red Line → transfer to bus 36 → destination — is never surfaced as a structured route card. The majority of Chicago trips are served by train-only or bus-only routes, so this is deferred until post-launch with real trip data to validate demand.

**Status: ⬜ Not started**

**Prerequisite:** This is a significant architectural change. Do not start until Phase 6 deployment is complete and the app is running stably in production. A scoping session is also recommended before implementation begins.

**Note on `find_bus_routes()`:** As of 2026-04-11, `find_bus_routes()` uses a two-pass design. Pass 1 collects candidates via haversine only; Pass 2 builds Route objects via OSMnx only for candidates within the progressive exit-stop threshold (0.25–2.0 miles). Any changes to `find_bus_routes()` as part of this feature must preserve this two-pass structure or replace it with something equally efficient.

**Note on shared-track edge deduplication:** `_build_graph()` stores only one edge per `(from_station, to_station)` pair — the fastest route_id. On segments where Red, Brown, and Purple lines share consecutive stations (e.g. Belmont↔Fullerton), the edge is labelled with whichever line had the fastest representative trip. When this feature adds bus nodes and bus edges, the same deduplication constraint applies to any bus segments that share stops with other routes. A future improvement to the train routing (documented in "Future Enhancements" below under "Multi-Leg Train Routing") would resolve the shared-track mis-labelling — but this is out of scope for Feature B and should be addressed in a separate scoped session.

---

## Scoping decisions — resolved

1. **Graph architecture: extend `_build_graph()`, not a separate function.** Bus nodes and edges are added at the end of `_build_graph()`, which is already `@lru_cache(maxsize=1)` and process-lifetime cached. No separate `_build_intermodal_graph()` function. Rationale: a single cached builder avoids a second lazy-init race and keeps startup sequencing simple. The existing `_build_graph()` return type `(G, parent_stations)` is unchanged — callers receive the enriched graph transparently.

2. **`get_bus_stop_sequences()` must be called inside `_build_graph()`.** Bus edges depend on bus stop sequences. Currently `warm_up()` calls `_build_graph()` then `get_bus_stop_sequences()` — this order must flip. Decision: `_build_graph()` calls `get_bus_stop_sequences()` directly (both are `@lru_cache`'d; the second call from `warm_up()` is a free cache hit). `warm_up()` call order becomes: `get_bus_stop_sequences()` → `_build_graph()` → `_build_shape_lookup()`, but since `_build_graph()` calls `get_bus_stop_sequences()` internally the external order is irrelevant.

3. **`_path_to_route()` node metadata: fall back to graph node attributes.** `stations` (train parent stations dict) does not cover bus stops. Rather than passing a second bus-stops dict, `_path_to_route()` will resolve node metadata by first checking `stations.get(node)`, then falling back to `G.nodes[node]` (which will carry `name`, `lat`, `lon` for bus stops as of Chunk 1). This keeps the function signature unchanged and works naturally for any new node type added in the future.

4. **Bus stop `name` field comes from `stops.txt` `stop_name`.** CTA GTFS bus stop names are intersection strings (e.g. "Clark & Division"). `_load_bus_stop_lookup()` already reads `stop_name`. Store it as the `name` attribute on each bus node so `_path_to_route()` can render readable `from_station`/`to_station` labels without special-casing bus stops.

5. **Thread-local copy pattern is retained.** `find_routes()` currently copies `G_base` once per executor thread. With ~11,000 bus stop nodes + ~50,000+ bus transit edges + ~3,000 train-bus walk edges, the per-thread graph copy grows from ~1 MB to ~8–15 MB. NetworkX copies are shallow (node/edge attribute dicts share references), so this is memory-pointer cost, not deep-copy cost. The pattern is retained as-is. Document the increased per-thread memory footprint in the `warm_up()` startup log (e.g. `[transit_graph] Graph size: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges`).

6. **Train-bus transfer edge type is `"walk"`, not `"transfer"`.** GTFS `transfers.txt` only contains train-to-train transfer pairs; the new train-bus cross-modal edges are street walks computed by `street_walk_minutes`. `edge_type="walk"` is correct for these. `_path_to_route()` already distinguishes ORIGIN walks, DEST walks, and mid-path walks via the `from_node == ORIGIN` / `to_node == DEST` checks — a mid-path walk edge between a train station and a bus stop falls through to the existing `edge_type == "transfer"` handler, which is correct (it renders a `WalkLeg` with named endpoints). No new edge type is needed.

7. **Startup time: transfer edges are built synchronously in `_build_graph()`.** ~150 train stations × up to ~20 nearby bus stops = up to ~3,000 `street_walk_minutes` calls at graph build time. All subsequent calls are OSMnx cache hits (same coordinate pairs). This adds an estimated 30–90 s to first startup (same order as the existing 30–90 s startup). Subsequent restarts are faster once the OSMnx cache is warm. No background-thread approach is used — the server must not accept requests until the graph is fully built (existing constraint, unchanged).

8. **Activation gate: `find_routes()` always uses the unified graph once built.** No feature flag, no separate `find_intermodal_routes()` call in `main.py`. Intermodal paths emerge naturally from Dijkstra on the unified graph. `main.py` continues to call `find_routes()` and `find_bus_routes()` and merges their results — when intermodal routes are present they will simply appear in `find_routes()` output alongside pure-train routes.

9. **Deduplication of bus-only routes.** The unified graph will find bus-only paths that duplicate `find_bus_routes()` results. After merging both lists in `main.py`, deduplicate by fingerprint: `tuple((leg.leg_type, leg.line_code, getattr(leg, "from_mapid", ""), getattr(leg, "to_mapid", "")) for leg in route.legs)`. First occurrence by total time wins. The deduplication applies only to bus-only paths — intermodal paths have a unique fingerprint and will never collide with pure-bus results.

10. **`find_routes()` `n_routes` default stays at 3; `main.py` passes `n_routes=5` explicitly.** Chunk 5 says to increase `n_routes` to 5 to surface intermodal options. Changing the default would be a silent behavior change for any caller that doesn't pass `n_routes`. Instead, the function signature default stays at 3; `main.py` passes `n_routes=5` explicitly once intermodal routing is active. This is backward-compatible with any future callers and makes the intent visible at the call site.

---

## Chunk 1 — Backend: Add bus stop nodes to the graph

**Files:** `backend/transit_graph.py`

**What to build:**
- In `_build_graph()`, after building the train graph, add bus parent stop nodes
- CTA bus stops (0–29999) are already loaded by `_load_bus_stop_lookup()` — reuse it
- Add each bus stop as a node: `G.add_node(stop_id, node_type="bus", lat=..., lon=..., name=stop_name)`
- Do not add any edges yet — just nodes
- Update the module docstring to reflect that the graph now contains both train stations and bus stops

**Notes:**
- Bus stops number ~11,000 in CTA GTFS — adding them as nodes is cheap (NetworkX nodes are just dict entries)
- The existing `__ORIGIN__` / `__DEST__` virtual node pattern in `find_routes()` is unchanged
- Include `name=stop_name` on each node (from `_load_bus_stop_lookup()`) so `_path_to_route()` can resolve stop labels via the graph node fallback (Scoping decision 3 & 4)

---

## Chunk 2 — Backend: Add bus route edges to the graph

**Files:** `backend/transit_graph.py`

**What to build:**
- After adding bus stop nodes, stream `stop_times.txt` for the representative bus trip per `(route_id, direction_id)` (this data is already computed in `get_bus_stop_sequences()` — reuse the sequence table rather than re-streaming)
- For each consecutive pair of stops in a bus sequence, add a directed transit edge:
  ```python
  G.add_edge(from_stop_id, to_stop_id,
             weight=leg_minutes,
             route_id=short_name,
             direction_id=did,
             line=direction_string,   # e.g. "Northbound"
             edge_type="transit",
             mode="bus")
  ```
- Add `mode="train"` to existing train transit edges for disambiguation
- Update `_path_to_route()` to handle `mode="bus"` transit edges — the leg assembly is the same as for trains but `line_code = route_short_name` (e.g. "36") and `line = direction_string`

**Notes:**
- Bus sequences are already in memory via `get_bus_stop_sequences()` — no extra file I/O
- `_build_graph()` calls `get_bus_stop_sequences()` directly (Scoping decision 2) — ordering is guaranteed, no `warm_up()` restructuring needed

---

## Chunk 3 — Backend: Train-to-bus and bus-to-train transfer edges

**Files:** `backend/transit_graph.py`

**What to build:**
- After adding all nodes and transit edges, add transfer edges between train stations and nearby bus stops
- For each train station, find all bus stops within 0.15 miles (haversine) using `_haversine_miles`
- For each nearby bus stop, add bidirectional walk edges:
  ```python
  walk_min = street_walk_minutes(station_lat, station_lon, stop_lat, stop_lon)
  G.add_edge(station_mapid, bus_stop_id, weight=walk_min, edge_type="walk", route_id="walk")
  G.add_edge(bus_stop_id, station_mapid, weight=walk_min, edge_type="walk", route_id="walk")
  ```
- Cap at 5 min walk — any bus stop more than 5 min walk from a train station is not a useful transfer
- Log transfer edge count at startup alongside existing train/transit edge counts

**Notes:**
- 0.15 miles ≈ 240m — a comfortable transfer walk distance
- `street_walk_minutes` is cached — repeated calls for the same coordinate pairs are free
- This step is the performance-sensitive one: ~150 stations × up to ~20 nearby stops = ~3,000 walk time lookups at startup. Acceptable given the existing startup time of 30–90s.

---

## Chunk 4 — Backend: Update `_path_to_route` for mixed paths

**Files:** `backend/transit_graph.py`

**What to build:**
- `_path_to_route()` currently handles `edge_type in ("transit", "transfer", "walk")`. Extend it to correctly handle bus transit edges (`mode="bus"`) — the `TransitLeg` assembly is identical, just ensure `line` and `line_code` are set correctly for bus legs
- Handle the case where a path contains both train and bus transit legs with a walk transfer between them — the existing same-station transfer detection logic may need updating since bus stop IDs and train mapids are in different ID ranges and won't accidentally collide
- Bus-only paths found via the unified graph should be deduplicated against `find_bus_routes()` results — once intermodal routing is enabled, consider deprecating `find_bus_routes()` in favour of the unified graph (separate decision, document as a TODO)

---

## Chunk 5 — Backend: Update `find_routes()` and `main.py` integration

**Files:** `backend/transit_graph.py`, `backend/main.py`

**What to build:**

In `transit_graph.py`:
- Update `find_routes()` to also add origin→bus_stop walk edges and bus_stop→DEST walk edges (same pattern as the existing train station virtual edges), so the unified graph finds train+bus paths
- Increase `n_routes` default to 5 to surface intermodal options alongside pure train/bus options

In `main.py`:
- Once `find_routes()` returns intermodal routes, `find_bus_routes()` becomes partially redundant. For now: keep both, merge as before, deduplicate on identical route fingerprints (same sequence of line_codes and stop names)
- The response format is unchanged — legs already serialize correctly regardless of mode

---

## Chunk 6 — Frontend: Verify intermodal route cards render correctly

**Files:** `frontend/src/App.jsx`, `frontend/src/MapView.jsx`

**What to verify/fix:**
- Route cards with mixed train + bus legs should already render correctly — `RouteLegs` handles each leg by type, and bus legs already have `BUS_DIRECTION_COLORS` + `line_code` pill
- Map rendering: `renderRoute()` uses `leg.line` to pick color — verify `BUS_DIRECTION_COLORS` lookup works for bus legs within a mixed route
- Walk transfer legs between train station and bus stop should render as dashed gray walk segments on the map (same as other walk legs) — verify `leg.path` is populated for these
- Manual test: find a real Chicago trip that benefits from an intermodal route (e.g. Brown Line to Western, then bus 49 south) and confirm the route card and map look correct

---

---

# Feature D — Live Arrivals at Transfer Stop

## Overview

When a route requires a transfer — train-to-train (already supported via the NetworkX graph) or bus-to-bus (Feature C) — the app currently shows only scheduled times for the connecting service. The rider has no way to know whether the connecting train or bus is 1 minute away or 12 minutes away when they arrive at the transfer stop.

This feature fetches live arrival data for the connecting service at the transfer stop(s) in each ranked route, threads that data through the Claude prompt and the API response, and displays it inline on the route card.

**Why it matters:** A route requiring a 10-minute transfer wait is materially different from one where the connection is 2 minutes away. Without this data, Claude cannot give accurate time advice for transfer trips, and the rider cannot compare transfer options on real-time footing. Feature C explicitly deferred this as a known limitation ("7.5 min fixed estimate"); Feature D closes that gap.

**Status: ⬜ Not started**

**Prerequisites:** No hard prerequisites — train-to-train transfer routing already works. Feature D is most impactful after Feature C (bus+bus transfers) is built, but the train-transfer half is independently useful and can be implemented first.

---

## Scoping decisions — resolved

1. **Which legs get live arrivals?** Only the 2nd and subsequent `TransitLeg`s in a route (i.e., legs where the rider is waiting at a transfer stop, not the first boarding leg). The first leg's wait is already handled by `route.wait_minutes` via `_rank_routes()`.

2. **Transfer stop identification:** After `ranked_routes` is computed, scan each route's legs. A `TransitLeg` is a transfer boarding leg if any earlier leg in the same route is also a `TransitLeg`. Implemented as a helper `_extract_transfer_stops(ranked_routes)` that returns two deduped lists: train station dicts `[{mapid, name}]` and bus stop_id strings. Dedup by mapid/stop_id across all routes before calling the API — one call per unique stop, not per route.

3. **Train vs. bus leg identification:** A `TransitLeg` is a train leg if its `line_code` is in `LINE_NAMES` (the dict in `cta_client.py`: Red, Blue, Brn, G, Org, P, Pink, Y). A bus leg has a `line_code` that is a route number string (e.g. "36", "49"). Bus `from_mapid` values are in the 0–29999 range (GTFS stop IDs); train `from_mapid` values are in the 40000–49999 range. Either check works; prefer `line_code in LINE_NAMES`.

4. **Arrival direction filter at transfer stop:** Reuse `_build_arrival_lookup()` for train transfers — it already returns `{(line_code, station_mapid): {destNm: earliest_minutes}}` and the bearing-based direction filter in `_rank_routes()` handles multi-direction stations. For bus transfers: add a simple `_build_bus_transfer_lookup(arrivals) -> dict[tuple[str, str], int]` keyed by `(route, stop_id)` → earliest arrival minutes (bus arrivals at a specific stop_id are already direction-filtered by the API).

5. **When to fetch:** After `ranked_routes` is computed and before `build_prompt()` is called. Run `get_train_arrivals(transfer_train_stations, train_key)` and `get_bus_arrivals(transfer_bus_stop_ids, bus_key)` concurrently via `asyncio.gather`. Only call if the respective API key is set and the list is non-empty. Total added latency: one extra concurrent API round-trip (~300ms).

6. **`bus_fullness` filter:** Do NOT apply the origin-side `bus_fullness` filter to transfer bus arrivals. The rider has no choice of bus at a transfer stop — they board whatever arrives next.

7. **Serialization:** Add `"transfer_wait_minutes": int | null` to each `TransitLeg` dict in the `/recommend` response. This is `None` if no live data was returned. The existing `"wait_minutes"` on the route object (first-leg wait) is unchanged.

8. **Claude prompt:** Add a short "Live arrivals at transfer stop(s):" section to `build_prompt()` when transfer arrival data is present, formatted similarly to the existing origin arrivals section. This allows Claude to give accurate transfer-wait advice (e.g. "the Brown Line at Belmont is 4 min away when you'd arrive — good connection").

9. **Frontend:** Show `transfer_wait_minutes` inline on the transfer `TransitLeg` in `RouteLegs`. If the preceding leg in the list is a `WalkLeg` with `from === to` (same-station transfer) or is any non-first transit leg: render a small secondary line "~X min wait" (or "Due") immediately above the transit leg summary, styled as muted text — same visual weight as the route header's wait note but scoped to the individual leg.

---

## Chunk 1 — Backend: Extract transfer stops and fetch live arrivals

**Files:** `backend/main.py`

**What to build:**
- Add `_extract_transfer_stops(ranked_routes: list[tuple]) -> tuple[list[dict], list[str]]`:
  - Iterates each `(total, wait, route)` in `ranked_routes`
  - For each route, identifies `TransitLeg` objects where at least one earlier leg in `route.legs` is also a `TransitLeg`
  - Train legs (`leg.line_code in LINE_NAMES`): collect `{"mapid": leg.from_mapid, "name": leg.from_station}` — dedup by `mapid`
  - Bus legs: collect `leg.from_mapid` as a stop_id string — dedup
  - Returns `(train_transfer_stations, bus_transfer_stop_ids)`
- After `ranked_routes` is computed (after both train and bus routing blocks), call:
  ```python
  transfer_train_stations, transfer_bus_stop_ids = _extract_transfer_stops(ranked_routes)
  transfer_train_arrivals, transfer_bus_arrivals = await asyncio.gather(
      get_train_arrivals(transfer_train_stations, train_key) if transfer_train_stations and train_key else asyncio.coroutine(lambda: [])(),
      get_bus_arrivals(transfer_bus_stop_ids, bus_key) if transfer_bus_stop_ids and bus_key else asyncio.coroutine(lambda: [])(),
  )
  ```
  Use `asyncio.gather` with appropriate short-circuit for empty lists (see Notes).

**Notes:**
- If `ranked_routes` is empty, both return lists will be empty — no API calls made
- Simplest empty-coroutine pattern: define a small `async def _empty(): return []` helper and use it in place of real calls when the list is empty. Avoid `asyncio.coroutine` (deprecated).
- Import `LINE_NAMES` from `cta_client` (it's already a module-level dict there) — or duplicate the set of train line codes as a constant in `main.py`. Either is fine; importing is cleaner.

---

## Chunk 2 — Backend: Annotate transit legs and serialize transfer wait

**Files:** `backend/transit_graph.py`, `backend/main.py`

**What to build:**

In `transit_graph.py`:
- Add `transfer_wait_minutes: int | None = None` field to `TransitLeg` dataclass (after existing fields)

In `main.py`:
- Add `_build_bus_transfer_lookup(bus_arrivals: list[dict]) -> dict[tuple[str, str], int]`:
  - Returns `{(route, stop_id): earliest_minutes}` — one entry per `(route, stop_id)` pair, taking `min` across all matching arrivals
- After fetching transfer arrivals, build lookups:
  ```python
  train_xfer_lookup = _build_arrival_lookup(transfer_train_arrivals)
  bus_xfer_lookup   = _build_bus_transfer_lookup(transfer_bus_arrivals)
  ```
- Annotate transfer legs in-place. For each route in `ranked_routes`:
  ```python
  seen_transit = False
  for leg in route.legs:
      if isinstance(leg, TransitLeg):
          if seen_transit:
              # This is a transfer boarding leg — look up live wait
              if leg.line_code in LINE_NAMES:
                  dest_map = train_xfer_lookup.get((leg.line_code, leg.from_mapid), {})
                  # Apply bearing filter (same as _rank_routes) to pick correct direction
                  leg.transfer_wait_minutes = _pick_wait(dest_map, leg.from_mapid, leg.to_mapid)
              else:
                  leg.transfer_wait_minutes = bus_xfer_lookup.get((leg.line_code, leg.from_mapid))
          seen_transit = True
  ```
  Extract the bearing filter into a shared helper `_pick_wait(dest_map, from_mapid, to_mapid) -> int | None` so it can be reused here and in `_rank_routes()`. This refactor removes the duplicate direction-selection logic.
- Add `"transfer_wait_minutes": leg.transfer_wait_minutes` to the `TransitLeg` dict in the `/recommend` response serialization (the `**{...}` block at lines 521–528 of `main.py`)

**Notes:**
- `_pick_wait` should accept an empty `dest_map` and return `None` (no live data) — same fallback as the existing `_rank_routes` wait-resolution logic
- The annotation modifies `Route.legs` in place after ranking — this is safe because the route objects are not reused after the response is built

---

## Chunk 3 — Backend: Include transfer arrivals in Claude prompt

**Files:** `backend/main.py`

**What to build:**
- Add `_format_transfer_arrivals(arrivals: list[dict]) -> str`:
  - Groups arrivals by `station` (train) or `stop_name` (bus)
  - For each stop, lists up to 3 next arrivals: `"  {line}/{route} → {destination}: {minutes} min"` (or "Due")
  - Returns a multi-line string, one stop per group header
- Extend `build_prompt()` signature: add `transfer_arrivals: list[dict] | None = None`
- In `build_prompt()`, if `transfer_arrivals` is non-empty, insert section after the origin arrivals blocks:
  ```
  Live arrivals at transfer stop(s):
  {_format_transfer_arrivals(transfer_arrivals)}
  ```
- In `main.py`, pass `transfer_arrivals = transfer_train_arrivals + transfer_bus_arrivals` to `build_prompt()`

**Notes:**
- Combined list is fine — `_format_transfer_arrivals` groups by stop name regardless of mode
- If `transfer_arrivals` is empty or `None`, the section is omitted entirely — no prompt change for non-transfer routes
- Claude should be able to infer "this is the wait at the transfer stop" from the section header without further instruction

---

## Chunk 4 — Frontend: Show transfer wait inline in route card

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`

**What to build:**
- In `RouteLegs`, before rendering a transit leg, check if it is a transfer boarding leg:
  ```js
  const isTransferLeg = legs.slice(0, i).some(l => l.type === 'transit');
  ```
- If `isTransferLeg && leg.transfer_wait_minutes !== undefined && leg.transfer_wait_minutes !== null`:
  - Render a small annotation immediately above the transit leg pill:
    ```
    ⏱ Due  /  ⏱ 4 min wait
    ```
  - Use a `<span className="transfer-wait-note">` element inserted just before the `<li>` for the transit leg, or as the first child inside it
- Style `.transfer-wait-note` in `App.css`: same muted color as secondary text elsewhere, `font-size: 0.75rem`, no extra margin (sits flush above the transit leg)
- If `transfer_wait_minutes === 0`: show "Due" (not "0 min wait")
- Do not change the route card header — `waitNote` continues to reflect only the first-leg wait

**Notes:**
- The existing `waitNote` in the route card header (line ~144 in `App.jsx`) is for `route.wait_minutes` — leave it unchanged
- This feature only adds UI when `transfer_wait_minutes` is populated; non-transfer routes and routes with no live data are unaffected
- Manual test: find a real Chicago trip requiring a train-to-train transfer (e.g. Wicker Park → Evanston: Blue Line → Red Line at Clark/Lake) and verify the wait badge appears on the Red Line leg and updates with live data

---

# Feature E — Walk Leg Street-Level Distance Detail

## Overview

Walk leg steps currently render as "↓ S on Broadway · 1.2 min". The street name and direction are already computed by `walk_directions()`, but the actual distance per street is not shown. This feature adds block-count distance to each step so riders can understand and verify the walk without mentally converting minutes into distance.

Target display per step:
```
Walk South along Broadway for 2 blocks
Head East along Wilson for 3 blocks
```

**Why it matters:** "Walk 6 minutes" is less actionable than "Walk 2 blocks south then 3 blocks east". A rider unfamiliar with the area can self-correct if they've gone too far on a street, which is not possible when only time is shown.

**Status: ✅ Complete (2026-04-13)**

---

## Scoping decisions — resolved

1. **Block size constant.** Use `_CHICAGO_BLOCK_METERS = 80.0` (≈ 264 feet). This matches the CTA grid standard of 8 blocks per mile and aligns with the mental model Chicago riders use. The constant is intentionally a round number — block counting is approximate by nature.

2. **Rounding granularity.** Round to the nearest 0.5 block: `max(0.5, round(length_m / 80.0 * 2) / 2)`. A 0-block step cannot occur because adjacent OSMnx nodes always have a positive-length edge. The `max(0.5, ...)` guard handles sub-25m micro-edges that would otherwise round to 0.

3. **Display format.** First step verb: "Walk". All subsequent step verbs: "Head". Format: `{verb} {direction_full} along {street} for {blocks_str}`. This matches the specified example. The leading direction arrow is removed — the full direction word makes it redundant.

4. **Where to add the new fields.** Add `"blocks": float` and `"direction_full": str` to each step dict returned by `walk_directions()` in `walking.py`. `transit_graph.py` stores the result list verbatim on `WalkLeg.directions` — no changes needed there. The fields flow through to the API response and frontend without additional wiring.

5. **Fallback step.** The `except` path in `walk_directions()` returns a single step with `minutes=total_min` and no routing data. Add `"blocks"` computed from `total_min * 60 * WALKING_SPEED_MPS / _CHICAGO_BLOCK_METERS` (rounded to 0.5), and `"direction_full": ""`.

6. **Per-step minutes removed from step UI.** The parent `WalkLegItem` already shows total walk time on the leg summary line. Per-step minutes add noise alongside the block count. Remove `step.minutes` from each step's rendered output. The `minutes` key stays in the dict (no backend change) — it's available for future use or Claude prompt reasoning.

7. **`direction_full` mapping.** Eight cardinal/intercardinal directions map to their full English names: N→"North", NE→"Northeast", E→"East", SE→"Southeast", S→"South", SW→"Southwest", W→"West", NW→"Northwest". Empty string stays empty (fallback path).

8. **`lru_cache` key unchanged.** `walk_directions()` is `@lru_cache(maxsize=512)` keyed on the four lat/lon floats. Adding fields to the returned dicts does not affect the cache key. No cache invalidation needed.

9. **API contract.** Adding `direction_full` and `blocks` to step dicts is strictly additive. No existing consumers (`transit_graph.py`, `main.py`) inspect step dict contents — they store and pass the list through. The frontend already reads `step.direction`, `step.street`, and `step.minutes`; the new Chunk 2 rendering replaces those references intentionally.

---

## Chunk 1 — Backend: Add `blocks` and `direction_full` to walk_directions()

**Files:** `backend/walking.py`

**What to build:**
- Add `_CHICAGO_BLOCK_METERS = 80.0` module-level constant directly after `WALKING_SPEED_MPS`
- Add a module-level dict `_DIRECTION_FULL`:
  ```python
  _DIRECTION_FULL = {
      "N": "North", "NE": "Northeast", "E": "East",   "SE": "Southeast",
      "S": "South", "SW": "Southwest", "W": "West",   "NW": "Northwest",
  }
  ```
- In `walk_directions()`, inside the grouping loop, after computing `minutes` for each step, also compute:
  ```python
  blocks = max(0.5, round(total_length / _CHICAGO_BLOCK_METERS * 2) / 2)
  direction_abbrev = _cardinal(lat1, lon1, lat2, lon2)
  ```
  And update the step dict to include `"blocks": blocks` and `"direction_full": _DIRECTION_FULL.get(direction_abbrev, direction_abbrev)`.
  The existing `"direction": direction_abbrev` key is kept — removing it would break any frontend that hasn't deployed Chunk 2 yet.
- In the `except` fallback block, the single fallback step dict currently has `{"street": "Walk", "direction": "", "minutes": total_min}`. Add:
  ```python
  fallback_meters = total_min * 60 * WALKING_SPEED_MPS
  fallback_blocks = max(0.5, round(fallback_meters / _CHICAGO_BLOCK_METERS * 2) / 2)
  ```
  and add `"blocks": fallback_blocks, "direction_full": ""` to the fallback dict.

**Notes:**
- `total_length` is already accumulated in the while-loop as the sum of edge lengths in metres — no additional work
- `direction_abbrev` is computed by `_cardinal()` and already assigned to the `"direction"` key — reuse the same value for `_DIRECTION_FULL` lookup
- The `@lru_cache(maxsize=512)` decorator is unchanged; do not remove or modify it
- After this chunk, a sample step dict looks like: `{"street": "Broadway", "direction": "S", "direction_full": "South", "minutes": 1.2, "blocks": 2.0}`

---

## Chunk 2 — Frontend: Update step rendering in WalkLegItem

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`

**What to build:**

In `App.jsx`:
- Add a `formatBlocks(b)` helper immediately above `WalkLegItem`:
  ```js
  function formatBlocks(b) {
    if (b === 1) return "1 block";
    return `${b} blocks`;
  }
  ```
- In `WalkLegItem`, replace the current `leg-step` `<li>` content (which renders arrow + abbreviated direction + "on" + street + minutes) with:
  ```jsx
  <li key={si} className="leg-step">
    <span className="leg-step-text">
      {si === 0 ? "Walk" : "Head"}
      {step.direction_full ? ` ${step.direction_full}` : ""}
      {" along "}
      <span className="leg-step-street">{step.street}</span>
      {" for "}
      {formatBlocks(step.blocks ?? 1)}
    </span>
  </li>
  ```
- Remove the `.leg-step-arrow`, `.leg-step-dir`, and `.leg-step-time` `<span>` elements and the `DIRECTION_ARROWS` usage from step rendering. The `DIRECTION_ARROWS` constant itself can remain in case it's used elsewhere; if it is only used in the step rendering, remove it too.

In `App.css`:
- Remove the `.leg-step-arrow`, `.leg-step-dir`, and `.leg-step-time` rule blocks (lines ~430–455). The `.leg-step`, `.leg-step-text`, and `.leg-step-street` rules remain — the new prose format is a single flex row with an inline street name span, and no layout change is expected.

**Notes:**
- `step.blocks` may be `undefined` for any in-flight or cached API responses from before this deploy. The `?? 1` fallback prevents a blank display on stale responses; after cache expiry it is harmless dead code.
- `step.direction_full` may be `""` on the fallback step — the conditional `step.direction_full ? ` ${step.direction_full}` : ""` handles this without rendering a trailing space.
- The `hasSteps` guard (`leg.directions && leg.directions.length > 1`) is unchanged — the Steps toggle only appears on walks with 2+ named-street segments.
- **Manual test:** Query a route with a walk leg spanning 2+ named streets. Confirm steps render as `"Walk South along Broadway for 2 blocks"` / `"Head East along Wilson for 3 blocks"`. Confirm a single-segment walk leg shows no Steps toggle (unchanged). Confirm the fallback case (no street graph, straight-line walk) shows something like `"Walk along Walk for N blocks"` — this is acceptable for a graceful degradation.

---

# Feature F — Street Abbreviation Normalization

## Overview

When a user types a street address containing common abbreviations — "123 N State St", "450 W Belmont Ave", "2800 N Lakeview Blvd" — those abbreviations pass through to `NEIGHBORHOOD_COORDS` lookup and `geocode_google()` as-is. Google Maps tolerates them well, but the `NEIGHBORHOOD_COORDS` fuzzy matcher does not. An entry keyed as `"wells street"` won't hit the 0.95 similarity threshold for the query `"wells st"`, causing an unnecessary Google API call for a location we already have in the fast path.

Beyond the cache miss, abbreviated queries produce inconsistent `geocode_cache.json` keys: "123 N State St", "123 N State Street", and "123 North State Street" would each cache separately even though they resolve to the same coordinates.

This feature adds a single normalization pass — called before any matching — that expands USPS-standard street suffix abbreviations and period-terminated variants to their full form.

**Why it matters:** Reduces unnecessary Google API calls (quota cost), improves `NEIGHBORHOOD_COORDS` hit rate for streets that appear in that dict with full names, and produces stable geocode-cache keys regardless of whether the user typed "Ave" or "Avenue".

**Status: ✅ Complete (2026-04-13)**

**Prerequisites:** None — self-contained change in `gtfs_loader.py` with no dependencies on other features.

---

## Scoping decisions — resolved

1. **Where to apply normalization.** At the very top of `resolve_location()`, before exact or fuzzy matching. The normalized string is used for all lookups and as the `geocode_google()` argument (and therefore the cache key). The raw user-typed string is not preserved anywhere — normalization is transparent.

2. **Which abbreviations to expand.** USPS standard street suffix abbreviations that appear in Chicago addresses, plus their period-terminated variants (e.g. both `"Ave"` and `"Ave."`). The complete list:

   | Abbreviation(s) | Full form |
   |---|---|
   | St, St. | Street |
   | Ave, Ave. | Avenue |
   | Blvd, Blvd. | Boulevard |
   | Dr, Dr. | Drive |
   | Ln, Ln. | Lane |
   | Ct, Ct. | Court |
   | Rd, Rd. | Road |
   | Pl, Pl. | Place |
   | Pkwy, Pkwy. | Parkway |
   | Hwy, Hwy. | Highway |
   | Expy, Expy. | Expressway |
   | Cir, Cir. | Circle |
   | Sq, Sq. | Square |
   | Ter, Ter., Terr, Terr. | Terrace |

   Directional prefixes (N, S, E, W, NW, NE, SW, SE) are explicitly **excluded** — they are used both as abbreviations and as standalone words/station-name fragments, and Google Maps handles them correctly without expansion. Expanding "N" → "North" throughout a query would break intersections like "North/Clybourn" and landmarks keyed with directional words.

3. **Matching strategy.** Use a single compiled regex that matches each abbreviation as a whole word (word-boundary anchored, case-insensitive). Replacements run left-to-right on the lowercased query copy. The case-lowercased result is consistent with how `resolve_location()` already normalizes its input (`q = query.lower().strip()`). The normalization function receives and returns a lowercased string.

4. **Replacement order.** Sort patterns from longest to shortest before compiling so that `"Blvd"` is tried before any shorter pattern that could partially overlap. In practice there are no overlaps in the suffix list, but ordering by length is a safe default that prevents future issues.

5. **Period handling.** Abbreviations ending in a period (e.g. `"Ave."`) must have the period consumed as part of the match, not left as a trailing punctuation mark. The regex alternation for each suffix includes both forms: `r"\bave\.?\b"` matches `"ave"` and `"ave."`. The replacement string never includes a trailing period.

6. **`_normalize_street_abbr` is private.** The function is an implementation detail of `resolve_location()`. It does not need to be exported. Prefix with `_` and place it immediately before `resolve_location()`.

7. **No change to `NEIGHBORHOOD_COORDS` keys.** All neighborhood keys already use full-form street names (e.g. `"wells street"`, `"chicago avenue"`). The normalization means user queries now match those keys correctly without any changes to the dict.

8. **Geocode cache backward compatibility.** Existing cache entries keyed on abbreviated strings (e.g. `"123 N State St"`) will no longer be hit after this change — the normalized key `"123 n state street"` is different. Those stale entries are harmless (they will never be looked up again) and will be evicted naturally when the cache file is cleared. Do not attempt a one-time migration of existing cache keys.

---

## Chunk 1 — Backend: Add `_normalize_street_abbr()` and call it in `resolve_location()`

**Files:** `backend/gtfs_loader.py`

**What to build:**

- Add a module-level compiled regex object `_STREET_ABBR_RE` and a `_normalize_street_abbr(query: str) -> str` function. Place both immediately above `resolve_location()` (around line 634).

- Build `_STREET_ABBR_RE` from a dict of `{abbreviation: full_form}` mappings. Each key in the dict generates two alternatives: the bare abbreviation and the abbreviation followed by a literal period. Sort by descending key length to ensure longer patterns match first:

  ```python
  _ABBR_MAP: dict[str, str] = {
      "blvd":  "boulevard",
      "pkwy":  "parkway",
      "expy":  "expressway",
      "terr":  "terrace",
      "ter":   "terrace",
      "hwy":   "highway",
      "blvd":  "boulevard",
      "ave":   "avenue",
      "cir":   "circle",
      "blvd":  "boulevard",
      "blvd":  "boulevard",
      "pkwy":  "parkway",
      "st":    "street",
      "dr":    "drive",
      "ln":    "lane",
      "ct":    "court",
      "rd":    "road",
      "pl":    "place",
      "sq":    "square",
  }
  # Sort longest-first to avoid shorter patterns shadowing longer ones
  _sorted_abbrs = sorted(_ABBR_MAP, key=len, reverse=True)
  _STREET_ABBR_RE = re.compile(
      r"\b(" + "|".join(re.escape(a) + r"\.?" for a in _sorted_abbrs) + r")\b",
      re.IGNORECASE,
  )
  ```

  > **Note:** The regex alternation `re.escape(a) + r"\.?"` matches e.g. `ave` or `ave.` as a whole word. The outer `\b` word-boundary anchors prevent `"St"` from matching inside `"Stanton"` or `"Estes"`.

- Implement `_normalize_street_abbr`:

  ```python
  def _normalize_street_abbr(query: str) -> str:
      """
      Expand USPS street suffix abbreviations (e.g. "Ave" → "avenue",
      "Blvd." → "boulevard") in a lowercased address string.

      Directional prefixes (N/S/E/W) are intentionally not expanded.
      """
      def _replace(m: re.Match) -> str:
          token = m.group(0).lower().rstrip(".")
          return _ABBR_MAP.get(token, m.group(0))

      return _STREET_ABBR_RE.sub(_replace, query)
  ```

- Add `import re` to the top of `gtfs_loader.py` (it is not currently imported; verify before adding).

- In `resolve_location()`, apply normalization immediately after the existing `q = query.lower().strip()` line:

  ```python
  q = query.lower().strip()
  q = _normalize_street_abbr(q)          # expand "Ave" → "avenue", etc.
  ```

  No other changes to `resolve_location()` are needed — `q` is already the string used for all subsequent matching.

**Notes:**
- `_ABBR_MAP` has some duplicate keys in the draft above — clean those up before committing. The final dict should have exactly one entry per suffix.
- The `_replace` closure strips trailing periods from the matched token before looking it up in `_ABBR_MAP`, so both `"ave"` and `"ave."` resolve to the same key.
- `geocode_google(query)` on line 661 of `resolve_location()` currently receives the un-lowercased original `query`. After this change it still should: `q` is the normalized lowercased form used for neighborhood matching; the Google API call should pass `q` (normalized) rather than `query` (raw) so the cache key is stable. Change that call to `geocode_google(q)`.
- After this change, the Google geocode cache key for any address with a suffix abbreviation will be the normalized lowercased string (e.g. `"123 n state street, chicago, il"` appended inside `geocode_google`). This is consistent and stable.

**Manual test:**
- Query `"123 N State St"` — confirm it normalizes to `"123 n state street"` and geocodes correctly.
- Query `"450 W Belmont Ave."` (with trailing period) — confirm the period is consumed and the query becomes `"450 w belmont avenue"`.
- Query `"wells st"` — confirm it resolves via `NEIGHBORHOOD_COORDS` fuzzy match to `"wells street"` (no Google API call).
- Query `"Stanton Ave"` — confirm `"stanton"` is not modified (word-boundary guard works); `"ave"` becomes `"avenue"`.
- Query `"North/Clybourn"` — confirm no change (no suffix abbreviation present).

---

# Future Enhancements

Post-launch ideas and improvements. These are not bugs — the app works correctly without them. Prioritize after Phase 6 deployment based on user feedback and real usage patterns.

---

## Multi-Leg Train Routing — Accuracy and Coverage Gaps

Train-to-train routing with line changes and transfers is **already implemented** via the NetworkX graph. A path like "Red Line → transfer at Belmont → Brown Line" is found naturally by `nx.shortest_simple_paths` and converted to a structured route card by `_path_to_route()`. This section documents two distinct gaps in the current implementation.

### Gap 1 — Shared-track edge deduplication (route label accuracy)

**What happens:** For each `(from_station, to_station)` edge, `_build_graph()` keeps only the single fastest route_id. On segments where multiple CTA lines share the same track and stations (e.g. Red/Brown between Belmont and Fullerton, or Red/Purple between Howard and Belmont), the edge is labelled with whichever line was fastest in the representative GTFS trip. If a rider transfers to the other line at the shared-track start station, `_path_to_route()` sees no route_id change on the shared segment and cannot detect the correct line.

**Practical effect:** Route cards on shared-track trips may show the wrong line name for the shared segment (e.g. "Red Line" when the rider is on the "Brown Line" through the shared section). Timing is still correct — only the label can be wrong.

**Future fix:** Store `all_routes` on the edge (already persisted as `edge_data["all_routes"]`) and use the incoming line context when labelling the shared-track leg. Alternatively, retain separate edges per route_id for shared-track pairs and handle deduplication during `_path_to_route()` rather than at graph-build time.

**Status: ⬜ Not started**

---

#### Verification — confirm the bug before implementing

Before any code changes, run these test queries and inspect leg labels in the JSON response:

| Trip | Shared segment to watch |
|---|---|
| Linden → Evanston/Davis (Purple Exp → Red) | Howard → Belmont: should say "Purple Line", not "Red Line" |
| O'Hare → Howard, then Howard → Belmont | If routed via Red, shared segment should say "Red Line" |
| Kimball → Merchandise Mart (Brown, all-elevated) | Belmont → Fullerton segment, if applicable |

Log the `line` field on each `TransitLeg` in the returned route. If mis-labelling is absent or rare (e.g. the graph happens to prefer a direction_id that coincides with the correct line), the fix may not be worth the complexity. If it fires consistently on the Purple/Red shared segment, proceed.

---

#### Chunk 1 — Fix `_path_to_route()` to use incoming line context

**File:** `backend/transit_graph.py`

**What to change:**

The transit-leg grouping block (lines ~888–937) always uses `edge.get("route_id")` and `edge.get("line")` as the canonical label for the leg. The fix: before committing to that label, check whether the incoming line (from the previous `TransitLeg`) is also a valid candidate for this edge, and prefer it if so.

```python
# Resolve incoming line context — find the last TransitLeg in `legs` (if any),
# looking past any same-station transfer WalkLeg.
def _last_transit_leg(legs: list) -> TransitLeg | None:
    for leg in reversed(legs):
        if isinstance(leg, TransitLeg):
            return leg
    return None
```

In the transit-leg grouping block, after reading `group_route = edge.get("route_id", "")`:

```python
# If the rider is already on a line that also serves this edge, keep that label
# (shared-track case: e.g. Purple Line rider passing through Red-labelled edge).
incoming = _last_transit_leg(legs)
if incoming:
    all_routes = edge.get("all_routes", [])  # list[(route_id, dir_id, line_name, minutes)]
    match = next(
        (r for r in all_routes if r[0] == incoming.line_code),
        None,
    )
    if match:
        group_route, group_dir, group_line = match[0], match[1], match[2]
```

The while-loop that merges consecutive edges uses `next_edge.get("route_id") != group_route` as the break condition. This comparison already uses `group_route` — after the override above it will correctly break when the shared segment ends and the lines diverge. No change needed to the loop itself.

Shape lookup at the end of the block calls `get_shape(group_route, group_dir)`. After the override, `group_route` and `group_dir` are the correct incoming-line values, so shape lookup inherits the fix automatically.

**Edge cases:**
- If the incoming line is not in `all_routes` (genuine line change, not shared-track): the override does not fire; the stored label is used as before.
- First transit leg (no `incoming`): `_last_transit_leg` returns `None`; override skipped.
- Same-station transfer WalkLeg inserted between two transit legs: `_last_transit_leg` still finds the previous `TransitLeg` correctly because it searches backward past walk legs.

**Test after:** Re-run the verification queries above. Purple Line through the Howard–Belmont segment should now label as "Purple Line".

---

### Gap 2 — Bus access/egress to train stations (first/last mile)

**What happens:** Both the origin walk leg (user → boarding station) and the destination walk leg (alighting station → destination) are always pedestrian walks. If a bus would provide faster access to a better-positioned train station — e.g. taking Route 22 to a Red Line station rather than walking 12 minutes — that option is never considered.

**Future fix:** Addressed by Feature B (Intermodal Routing — Train + Bus), which is now fully scoped above. No separate implementation work needed here — Feature B's unified graph handles this gap as a natural consequence.

**Status: ⬜ Deferred to Feature B**

---

## Rate Limiting on `/recommend` Endpoint

**What:** The `/recommend` endpoint currently has no per-user or global rate limiting. A single user or bot can run up Claude API costs without any cap.

**Why deferred:** Intentionally deferred during testing so queries are unrestricted.

**Must add before or shortly after public launch.** Without it, a bad actor can drain the Anthropic API budget with no friction.

**Status: ✅ Complete (2026-04-14) — code written and merged; feature is OFF by default. Enable by setting `RATE_LIMIT_ENABLED=true` in `backend/.env` (or Railway env vars).**

---

### What was implemented

**Approach used: zero-dependency in-memory sliding window** (not `slowapi` as originally scoped — that approach was replaced with a simpler self-contained implementation to avoid adding a new dependency).

**Files changed:** `backend/main.py` only. No `requirements.txt` change needed.

**Key design decisions (vs. scoping above):**

| Scoping decision | What shipped |
|---|---|
| Use `slowapi` library | Replaced with inline `_check_rate_limit()` using `collections.deque` — no new dependency |
| Per-IP rolling 60 s: 10 req | ✅ Same — `RATE_LIMIT_RPM=10` (tunable via env var) |
| Per-IP rolling 60 min: 30 req | Changed to 50 — `RATE_LIMIT_RPH=50` (tunable via env var) |
| Global 200 req/60 min cap | Not implemented — per-IP limits plus caching are sufficient for phase 1 |
| `ENVIRONMENT=development` bypass | Replaced with master on/off `RATE_LIMIT_ENABLED` flag — cleaner for Railway deployment |
| `Retry-After` header | Not added in phase 1 — HTTP 429 + detail message is sufficient |
| Redis backend (future) | Not built; documented as a future step when Railway scales to multi-instance |

**New additions to `main.py`:**
- `import collections` — standard library, no extra install
- `from fastapi import FastAPI, HTTPException, Request` — `Request` added to extract client IP
- `_RATE_LIMIT_ENABLED`, `_RATE_LIMIT_RPM`, `_RATE_LIMIT_RPH` — env-var-driven config (all read at startup)
- `_rate_store: dict[str, collections.deque]` — in-memory per-IP timestamp store
- `_client_ip(http_request)` — extracts real IP from `X-Forwarded-For` (Railway proxy) or falls back to `request.client.host`
- `_check_rate_limit(ip)` — sliding-window check; returns `True` (allowed) or `False` (rate-limited); called before any I/O at the top of `/recommend`
- `/recommend` endpoint signature: `async def recommend(request: RouteRequest, http_request: Request)` — FastAPI injects `Request` automatically alongside the Pydantic model

**To activate:** Set `RATE_LIMIT_ENABLED=true` in Railway env vars before public launch. Optionally tune `RATE_LIMIT_RPM` and `RATE_LIMIT_RPH`.

**Future (if Railway scales to multi-instance):** Replace `_rate_store` with a Redis-backed counter. The `_check_rate_limit(ip)` interface is unchanged — only the storage backend needs to swap.

---

## Bring Your Own API Key (BYOK)

**What:** Let technically savvy users supply their own Anthropic API key in an in-app setup workflow. Their usage shifts entirely off the app's variable cost base.

**Considerations:**
- Most target users (everyday CTA riders) will not use this — do not rely on it as a primary cost solution
- API keys must be stored and handled securely — user financial liability is at stake if keys are exposed
- Build as an optional power-user setting, not a core requirement
- Caching and per-user request limiting will move the cost needle more broadly

**Status: ✅ Complete (2026-04-14) — code written and merged; feature is OFF by default. Enable by setting `BYOK_ENABLED=true` in `backend/.env` AND `VITE_BYOK_ENABLED=true` in `frontend/.env` (or Vercel env vars).**

---

### What was implemented

**Files changed:** `backend/main.py`, `frontend/src/App.jsx`, `frontend/src/App.css`.

**Key design decisions (vs. scoping above):**

| Scoping decision | What shipped |
|---|---|
| Field name `byok_api_key` on `RouteRequest` | Changed to `anthropic_api_key` — clearer without the BYOK acronym |
| `localStorage` key `cta_byok_api_key` | Changed to `byok_api_key` — shorter, unambiguous |
| Settings panel collapses below search form | Implemented as a gear icon ⚙ in the header filters row; panel slides in above the form |
| "Key saved" inline confirmation | Panel closes on Save — no extra confirmation message needed |
| Key masking in error messages | Deferred — the existing generic HTTP 502 handler is sufficient; masking adds complexity for a rare edge case |
| Rate limiting: BYOK bypasses global cap | No global cap was implemented, so no bypass logic needed; BYOK requests count against per-IP limits like all others |
| BYOK enabled unconditionally | Gated behind `BYOK_ENABLED` (backend) + `VITE_BYOK_ENABLED` (frontend) env vars — both must be `true` to activate |

**Backend (`main.py`):**
- `anthropic_api_key: str | None = None` added to `RouteRequest` with a `@field_validator` that strips whitespace, returns `None` for empty strings, and rejects values not starting with `"sk-ant-"` (fast 400 before hitting Anthropic)
- `_BYOK_ENABLED = os.getenv("BYOK_ENABLED", "false").lower() == "true"` — master on/off; when `false`, `anthropic_api_key` is accepted in the body but silently ignored (frontend doesn't need to know server BYOK state)
- Per-request client: `anthropic.AsyncAnthropic(api_key=byok_key)` created only when `byok_key` is set; otherwise falls back to `_claude_client` singleton
- Anthropic key validation: skipped when `byok_key` is set (a valid BYOK key is sufficient; the shared server key need not be present)

**Frontend (`App.jsx` + `App.css`):**
- `BYOK_ENABLED = import.meta.env.VITE_BYOK_ENABLED === "true"` — compile-time flag; `false` means `SettingsPanel` is never rendered and no `anthropic_api_key` is ever sent
- `SettingsPanel` component: gear icon ⚙ in header filters row (active-state tint when key is stored); modal-style panel with `type="password"` input, Save and Remove key buttons, inline format validation error
- `byokKey` state initialised from `localStorage` (`byok_api_key`) on mount; `handleSaveByokKey` writes/removes from `localStorage`
- Fetch body spreads `{ anthropic_api_key: byokKey }` only when `BYOK_ENABLED && byokKey`

**To activate:** Set `BYOK_ENABLED=true` in Railway env vars AND `VITE_BYOK_ENABLED=true` in Vercel env vars, then redeploy both services.

**Still out of scope (deferred):**
- Key validation endpoint (pre-flight test call to Anthropic)
- Server-side key storage of any kind
- Encrypting the key at rest in `localStorage`
- Usage or cost dashboard for BYOK users
- Auto-detecting when the server key is exhausted and prompting for BYOK

---

## Claude Response Caching

**What:** Cache the full `/recommend` response for identical origin/destination/mode queries within a short TTL. Repeat requests from different users for popular routes (e.g. Wrigleyville → Loop at 5pm) skip the CTA API calls, routing engine, and Claude call entirely and return the cached payload instantly.

**Benefit:** Reduces Anthropic API spend significantly once traffic scales. Also lowers CTA API call volume and response latency for cached hits.

**Status: ✅ Complete**

---

### Scoping

#### What to cache

Cache the **full response dict** returned by `/recommend`, including `recommendation`, `routes`, `train_arrivals`, `bus_arrivals`, `origin_coords`, `dest_coords`, and `origin_stations`. Caching the full payload (not just the Claude text) skips all upstream I/O on a hit.

Add a `cache_hit: true` field to cached responses so the frontend can optionally surface a freshness note (e.g. "as of 30s ago"). Do not show this to users in the initial implementation — wire the field but leave the UI unchanged.

#### Cache key

Normalize and join the four request fields that determine a unique query:

```python
def _cache_key(origin: str, destination: str, transit_mode: str, bus_fullness: str) -> str:
    return "|".join([
        origin.lower().strip(),
        destination.lower().strip(),
        transit_mode,
        bus_fullness,
    ])
```

Do **not** incorporate live arrival data into the key — two users asking the same route in the same window should share one cache entry regardless of the exact second their request lands.

#### TTL

**45 seconds.** Rationale:
- Short enough that live arrival data in the cached payload is not materially misleading. A recommendation that says "next train in 3 min" returned 45s later is still actionable.
- Long enough to collapse request bursts from multiple users hitting the same popular route simultaneously.
- The CTA Train Tracker API refreshes arrivals roughly every 30s; a 45s window means at most one refresh cycle of staleness.

Do not cache for 60s — arrival data becomes noticeably stale near the 60s mark (a "Due" train may have departed).

#### Storage backend

**In-memory dict (phase 1).** Same rationale as rate limiting: single Railway instance, zero dependencies, acceptable reset-on-redeploy behaviour.

```python
_response_cache: dict[str, tuple[float, dict]] = {}
# key → (expires_at: float (time.monotonic), response: dict)
```

**Redis (phase 2, if multi-instance).** If Railway scales to multiple replicas, in-memory caches diverge and hit rates drop significantly. Switch to Redis at that point. Do not build the Redis path now.

#### Eviction

**Lazy TTL eviction.** On each cache lookup, check `time.monotonic() > expires_at` and delete stale entries inline. No background task required at this scale.

**Size cap.** Cap `_response_cache` at **500 entries** to bound memory. When the cap is reached, evict the single entry with the lowest `expires_at` (nearest to expiry) before inserting the new one. A simple `min(cache, key=lambda k: cache[k][0])` is sufficient — no need for an LRU structure.

#### Where to place the cache check

Check the cache **before** any I/O — before CTA API calls, before routing, before Claude. This maximises latency savings on hits.

On a miss, proceed through the full request pipeline and store the response before returning it.

```python
# In /recommend, immediately after building the cache key:
cached = _response_cache.get(key)
if cached and time.monotonic() < cached[0]:
    return {**cached[1], "cache_hit": True}

# ... full pipeline ...

response = { ... }
_response_cache[key] = (time.monotonic() + 45, response)
if len(_response_cache) > 500:
    oldest = min(_response_cache, key=lambda k: _response_cache[k][0])
    del _response_cache[oldest]
return response
```

#### Files to change

- `backend/main.py` — add `_response_cache` dict, `_cache_key()` helper, and cache read/write logic at the top of the `/recommend` handler. Add `import time` if not present.

#### Out of scope

- Redis backend (defer until multi-instance)
- Manual cache invalidation on CTA schedule changes (TTL handles staleness)
- Frontend freshness UI (field is wired but display is deferred)
- Caching any endpoint other than `/recommend`
- Fuzzy key matching (e.g. treating "wrigleyville" and "Wrigley" as equivalent — rely on `resolve_location()` to normalise inputs before the key is built, not the cache layer)

---

## Claude Haiku for Simple Queries

**What:** Route queries with only one clear option (e.g. a single direct train, no transfers) don't need Sonnet-level reasoning. Haiku is ~65% cheaper and fast enough for straightforward recommendations.

**Benefit:** Meaningful cost reduction at scale with no user-facing quality loss on simple routes.

**Status: ⬜ Not started**

---

### Scoping

#### Definition of "simple"

A query is **simple** if both conditions hold after routing completes:

1. `ranked_routes` contains exactly **one** route.
2. That route contains exactly **one** `TransitLeg` (no transfer — a direct ride from origin to destination).

This is the most conservative definition: Claude's only job is to format the result and give a departure time. There is no comparison between options, no transfer tradeoff, no "ride A then B" complexity. Any query with multiple routes or a transfer leg uses Sonnet.

Intentionally **not** included in the simple definition:
- Two routes on the same line (e.g. two direct Red Line options) — still requires comparison reasoning.
- One route with multiple `TransitLeg`s but no walk between them — still a transfer, still Sonnet.
- Walk-only legs (`WalkLeg`) do not count against the TransitLeg limit; a route with one `WalkLeg` + one `TransitLeg` is still simple.

#### Classifier function

Add `_is_simple_query(ranked_routes: list[tuple]) -> bool` in `main.py`:

```python
def _is_simple_query(ranked_routes: list[tuple]) -> bool:
    if len(ranked_routes) != 1:
        return False
    _, _, route = ranked_routes[0]
    transit_legs = [leg for leg in route.legs if isinstance(leg, TransitLeg)]
    return len(transit_legs) == 1
```

Call it after `ranked_routes` is finalized and before `build_prompt()`.

#### Model selection

```python
model = (
    "claude-haiku-4-5-20251001"
    if _is_simple_query(ranked_routes)
    else "claude-sonnet-4-6"
)
message = await _claude_client.messages.create(
    model=model,
    max_tokens=300 if model.startswith("claude-haiku") else 400,
    messages=[{"role": "user", "content": prompt}],
)
```

`max_tokens=300` for Haiku: a single-route direct recommendation fits comfortably in 300 tokens. Sonnet keeps 400 for complex multi-route responses.

No changes to the prompt itself — the same `build_prompt()` output is sent to both models.

#### Logging

Print the selected model to stdout so Railway logs capture it:

```python
print(f"[claude model={'haiku' if model.startswith('claude-haiku') else 'sonnet'} simple={_is_simple_query(ranked_routes)}]")
```

#### Response field

Add `"model_used": "haiku" | "sonnet"` to the `/recommend` response dict. The frontend ignores this field initially — it exists for log-based cost analysis and future observability. Do not surface it to the user.

#### BYOK interaction

BYOK keys (when that feature is built) work with all Claude models. Apply the same model-selection logic regardless of whether the request uses a BYOK key or the server key — BYOK users benefit from the same cost reduction.

#### Cache interaction

The response cache (when built) stores the full response including `model_used`. On a cache hit, Claude is not called at all — model selection is irrelevant. No special handling needed.

#### Files to change

- `backend/main.py` — add `_is_simple_query()` helper; add model selection and `max_tokens` branching before the `_claude_client.messages.create()` call; add `model_used` to the response dict; add the stdout log line.

#### Out of scope

- Prompt differences between Haiku and Sonnet (same prompt for both — diverging prompts adds maintenance cost with no clear benefit)
- Expanding the "simple" definition to cover two-route same-line queries (deferred; measure quality first)
- Per-model cost tracking in the response or UI
- Automatic fallback from Haiku to Sonnet on low-confidence responses (not needed; the classifier is conservative by design)

---

# Feature G — Long/Short Block Classification

## Overview

Chicago's street grid has two standard block sizes that differ by 2×:
- **Long Block**: 1/8 mile (660 ft / 201.17 m) — the N-S numbered-address axis
- **Short Block**: 1/16 mile (330 ft / 100.58 m) — E-W cross streets

The original Feature E implementation used a single constant `_CHICAGO_BLOCK_METERS = 80.0` (~262 ft) as an approximation for all blocks. Feature G replaces this with accurate per-type constants and classifies each walk step as long or short based on the actual measured OSM edge lengths.

**Why it matters:** A rider walking 2 long blocks north is walking twice as far as 2 short blocks east — both labeled "2 blocks" under the old constant. Feature G makes the block count label geometrically accurate and qualitatively informative.

**Status: ✅ Complete (2026-04-13)**

---

## Scoping decisions — resolved

1. **Classification threshold.** Use 150 m as the midpoint between 201.17 m and 100.58 m. For each merged street segment, compute `avg_edge_m = total_length / edge_count`. If `avg_edge_m >= 150` → long block; else → short block.

2. **Block count formula.** Same rounding as Feature E: `max(0.5, round(total_length / block_m * 2) / 2)`, where `block_m` is now either `_LONG_BLOCK_METERS` or `_SHORT_BLOCK_METERS` depending on classification.

3. **Fallback path.** The `except` path in `walk_directions()` derives `fallback_meters` from the Haversine walk time estimate. Apply the same 150 m threshold to `fallback_meters` itself (treating the whole leg as a single notional edge).

4. **Cache note.** `walk_directions` is `@lru_cache(maxsize=512)`. The in-memory cache resets on server restart, so old entries without `block_type` are never served in production. No cache-busting work needed.

5. **API contract.** Adding `"block_type"` to step dicts is strictly additive. `transit_graph.py` and `main.py` store and pass the list through without inspecting step keys — no changes needed in either file.

6. **Frontend fallback.** `formatBlocks(b, blockType)` returns plain `"N block(s)"` when `blockType` is absent — backward compatible with any cached or test data that predates this feature.

---

## Chunk G-1 — Backend: Replace constant, add classification, emit `block_type`

**Files:** `backend/walking.py`

**Status: ✅ Complete**

**What was built:**
- Replaced `_CHICAGO_BLOCK_METERS = 80.0` with three constants:
  ```python
  _LONG_BLOCK_METERS    = 201.17   # 1/8 mile = 660 ft — N-S numbered-address axis
  _SHORT_BLOCK_METERS   = 100.58   # 1/16 mile = 330 ft — E-W cross streets
  _BLOCK_TYPE_THRESHOLD = 150.0    # midpoint; ≥ threshold → long block
  ```
- Added `edge_count` accumulator alongside `total_length` in the inner `while` loop
- After the inner loop: computes `avg_edge_m = total_length / edge_count`, classifies as long/short, selects the correct `block_m`, and sets `block_type = "long" | "short"`
- Added `"block_type": block_type` to the step dict appended to `steps`
- Fallback path: applies same threshold to `fallback_meters`, sets `block_type_fb`, adds `"block_type": block_type_fb` to the fallback step dict

---

## Chunk G-2 — Frontend: Display long/short block label

**Files:** `frontend/src/App.jsx`

**Status: ✅ Complete**

**What was built:**
- Updated `formatBlocks(b, blockType)` to accept `blockType` and produce a qualified label:
  ```js
  function formatBlocks(b, blockType) {
    if (!blockType) return b === 1 ? "1 block" : `${b} blocks`;
    const label = blockType === "long" ? "long block" : "short block";
    return `${b} ${b === 1 ? label : label + "s"}`;
  }
  ```
- Updated the call site in `WalkLegItem` to pass `step.block_type`:
  ```jsx
  {formatBlocks(step.blocks ?? 1, step.block_type)}
  ```
- Walk step output now reads e.g. "Walk North along Clark for 2 long blocks" or "Head East along Chicago for 3 short blocks"
