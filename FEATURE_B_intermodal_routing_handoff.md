# Feature B — Intermodal Routing (Train + Bus in One Trip)
## Claude Code Implementation Handoff

> **✅ IMPLEMENTED 2026-04-16** — All 6 chunks complete. See `FEATURE_IMPLEMENTATION_PLANS.md` for the implementation summary and `cta_app_handoff_prompt.md` (Notable changes — 2026-04-16) for the session log. This file is kept as a historical reference.

**Files to edit:** `backend/transit_graph.py`, `backend/main.py`  
**Frontend verification only:** `frontend/src/App.jsx`, `frontend/src/MapView.jsx`  
**Complexity:** Large — 6 sequential chunks; implement in order  
**Risk:** Medium-High — architectural change to `_build_graph()` and `find_routes()`; existing train and bus routing must remain fully functional

---

## Background — what this feature does

Train routes and bus routes are currently found independently and merged by total time in `main.py`. A combined trip — e.g. walk → Red Line → walk → Bus 36 → destination — is never surfaced as a structured route card. Feature B extends the NetworkX graph to include bus stop nodes and bus route edges, so Dijkstra naturally discovers intermodal paths alongside pure-train ones.

**No feature flag is needed.** Once the graph is built with bus nodes and edges, intermodal paths emerge automatically from `find_routes()`.

---

## Important constraints — read before starting

1. **Phase 6 deployment prerequisite — ✅ Satisfied.** The feature plan required the app to be running stably in production before starting Feature B. Phase 6 is complete: the backend is live on Railway and the frontend is live on Vercel. You may begin implementation immediately.

2. **`find_bus_routes()` uses a two-pass design** (Pass 1: haversine candidates; Pass 2: OSMnx Route objects). Do not change this function's internal logic. It continues to run in parallel with `find_routes()` in `main.py`.

3. **Feature A is complete.** `_path_to_route()` already has exit-guidance logic. All changes to `_path_to_route()` in Chunk 4 must be written against the current (post-Feature-A) version.

4. **Feature C is complete.** `find_bus_transfer_routes()` exists and is called from `main.py`. The deduplication logic added in Chunk 5 must not interfere with bus-transfer routes.

5. **Shared-track mis-labelling** (e.g. Red/Brown edges between Belmont and Fullerton) is a known pre-existing issue. Do not attempt to fix it here — it is out of scope for Feature B.

6. **Startup time will increase** by an estimated 30–90 s on cold start due to ~3,000 `street_walk_minutes` calls in Chunk 3. This is acceptable and documented.

---

## Chunk 1 — Add bus stop nodes to the graph

**File:** `backend/transit_graph.py`  
**Function:** `_build_graph()`

### What to do

Inside `_build_graph()`, after the existing train graph is fully built (all train nodes, transit edges, and transfer edges added), add bus stop nodes. Use the existing `_load_bus_stop_lookup()` function — it already reads `stops.txt` and returns a dict of bus stops.

Add each bus stop as a node:

```python
bus_stop_lookup = _load_bus_stop_lookup()
for stop_id, stop in bus_stop_lookup.items():
    G.add_node(
        stop_id,
        node_type="bus",
        lat=stop["lat"],
        lon=stop["lon"],
        name=stop["stop_name"],   # intersection string e.g. "Clark & Division"
    )
print(f"[transit_graph] Added {len(bus_stop_lookup)} bus stop nodes to graph")
```

Do **not** add any edges in this chunk — nodes only.

### Also do

Add `node_type="train"` to the existing train station nodes when they are created earlier in `_build_graph()`, so they can be distinguished from bus nodes. Find the `G.add_node(mapid, ...)` calls for train stations and add `node_type="train"` to each.

Update the module-level docstring to note that the graph contains both train stations and bus stops.

### Notes

- `_load_bus_stop_lookup()` already exists — do not rewrite it.
- Bus stop IDs are integers 0–29999; train station mapids are 5-digit integers (40000+). They will never collide.
- The `__ORIGIN__` / `__DEST__` virtual node pattern in `find_routes()` is unchanged.

---

## Chunk 2 — Add bus route edges to the graph

**File:** `backend/transit_graph.py`  
**Function:** `_build_graph()`

### What to do

Immediately after the bus stop nodes are added (end of Chunk 1 block), add directed transit edges between consecutive stops on each bus route. Reuse `get_bus_stop_sequences()` — do not re-stream `stop_times.txt`.

```python
bus_sequences = get_bus_stop_sequences()
bus_edge_count = 0
for (short_name, did), stops in bus_sequences.items():
    direction_string = stops[0][5] if stops and len(stops[0]) > 5 else did  # e.g. "Northbound"
    for i in range(len(stops) - 1):
        from_stop = stops[i]
        to_stop   = stops[i + 1]
        from_id   = from_stop[0]   # stop_id
        to_id     = to_stop[0]     # stop_id
        from_arr  = from_stop[4]   # arr_minutes since midnight
        to_arr    = to_stop[4]     # arr_minutes since midnight
        leg_min   = max(0.5, to_arr - from_arr)
        G.add_edge(
            from_id, to_id,
            weight=leg_min,
            route_id=short_name,       # e.g. "36"
            direction_id=did,
            line=direction_string,     # e.g. "Northbound"
            line_code=short_name,      # e.g. "36"
            edge_type="transit",
            mode="bus",
        )
        bus_edge_count += 1
print(f"[transit_graph] Added {bus_edge_count} bus transit edges to graph")
```

### Also do

Add `mode="train"` to all existing train transit edges so they can be distinguished from bus edges. Find where train transit edges are added in `_build_graph()` (they use `edge_type="transit"`) and add `mode="train"` to each `G.add_edge(...)` call.

### Notes

- The `get_bus_stop_sequences()` sequence tuple format is `(stop_id, stop_name, lat, lon, arr_minutes, ...)`. Confirm the exact tuple indices against the current implementation before writing the edge loop.
- If a `(short_name, did)` pair has only one stop in its sequence, skip it (no consecutive pair to add).
- `leg_min` should never be negative — use `max(0.5, ...)` as a safety floor.
- `_build_graph()` calls `get_bus_stop_sequences()` directly here (Scoping decision 2 from the feature plan). Since both are `@lru_cache`'d, a subsequent call from `warm_up()` is a free cache hit — no warm-up restructuring needed.

---

## Chunk 3 — Add train-to-bus and bus-to-train transfer edges

**File:** `backend/transit_graph.py`  
**Function:** `_build_graph()`

### What to do

After bus nodes and bus transit edges are added, add bidirectional walk edges between train stations and nearby bus stops. This is the step that makes intermodal transfers possible.

```python
# Build transfer edges between train stations and nearby bus stops
transfer_edge_count = 0
TRANSFER_RADIUS_MILES = 0.15   # ~240m — comfortable transfer walk
TRANSFER_WALK_CAP_MIN = 5.0    # skip if street walk exceeds 5 minutes

_, parent_stations = _build_graph.cache_info()  # NOTE: use the stations dict built earlier in this function
# Actually: parent_stations is built earlier in _build_graph() — just reference it directly

for mapid, station in parent_stations.items():
    s_lat, s_lon = station["lat"], station["lon"]
    for stop_id, stop in bus_stop_lookup.items():
        dist = _haversine_miles(s_lat, s_lon, stop["lat"], stop["lon"])
        if dist > TRANSFER_RADIUS_MILES:
            continue
        walk_min = street_walk_minutes(s_lat, s_lon, stop["lat"], stop["lon"])
        if walk_min > TRANSFER_WALK_CAP_MIN:
            continue
        G.add_edge(mapid, stop_id,
                   weight=walk_min, edge_type="walk", route_id="walk", mode="walk")
        G.add_edge(stop_id, mapid,
                   weight=walk_min, edge_type="walk", route_id="walk", mode="walk")
        transfer_edge_count += 2

print(f"[transit_graph] Added {transfer_edge_count} train↔bus transfer walk edges")
```

Also update the `warm_up()` startup log to include graph size after the unified graph is built:

```python
G, _ = _build_graph()
print(f"[transit_graph] Graph size: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
```

### Notes

- `bus_stop_lookup` is already in scope from Chunk 1 — do not call `_load_bus_stop_lookup()` again.
- `parent_stations` is built earlier inside `_build_graph()` — reference it directly; do not call `_build_graph()` recursively.
- `street_walk_minutes` is `@lru_cache`'d — repeated calls for the same coordinate pairs are free after the first call.
- The edge type is `"walk"`, not `"transfer"`. `_path_to_route()` already handles mid-path walk edges between named nodes as a `WalkLeg` — no new edge type is needed.
- This step is the performance-sensitive one: ~150 train stations × up to ~20 nearby bus stops = ~3,000 `street_walk_minutes` calls. Subsequent restarts hit OSMnx cache and are faster.
- **Per-thread memory footprint:** `find_routes()` copies the shared graph once per executor thread. After Feature B, the graph grows from ~1 MB to an estimated ~8–15 MB per thread copy. NetworkX copies are shallow — node and edge attribute dicts share references with the base graph — so the actual overhead is pointer cost, not deep-copy cost. This is acceptable but should be noted in the `warm_up()` startup log (already covered by the graph size print added in this chunk).

---

## Chunk 4 — Update `_path_to_route()` for mixed train+bus paths

**File:** `backend/transit_graph.py`  
**Function:** `_path_to_route()`

### What to do

`_path_to_route()` currently resolves node metadata only from `stations` (the train parent stations dict). Bus stop nodes won't be in `stations`, so add a fallback to graph node attributes.

**Step 1 — Add node metadata fallback.**

Find the section in `_path_to_route()` where it resolves `from_station` and `to_station` names and coordinates. After the existing `stations.get(node)` lookup, add a fallback:

```python
def _resolve_node(node, stations, G):
    """Return (name, lat, lon) for a train station or bus stop node."""
    if node in stations:
        s = stations[node]
        return s["station_name"], s["lat"], s["lon"]
    node_data = G.nodes.get(node, {})
    return node_data.get("name", str(node)), node_data.get("lat", 0.0), node_data.get("lon", 0.0)
```

Use `_resolve_node()` wherever node names and coordinates are resolved in `_path_to_route()`.

**Step 2 — Handle `mode="bus"` transit edges.**

In the `edge_type == "transit"` branch of `_path_to_route()`, add handling for bus legs. The `Transitleg` assembly is the same as for trains, but the attributes come from the edge differently:

```python
if edge_data.get("mode") == "bus":
    line_code = edge_data.get("line_code") or edge_data.get("route_id", "")
    line      = edge_data.get("line", "")   # direction string e.g. "Northbound"
    # from_name, to_name, from_lat/lon, to_lat/lon via _resolve_node()
    # shape_points via clip_shape / get_shape as already done for trains
    # mode field on TransitLeg should be set to "bus"
```

Confirm how `TransitLeg` is constructed for bus legs in the existing `find_bus_routes()` path and mirror that pattern exactly.

**Step 3 — Ensure same-station transfer detection does not break.**

`_path_to_route()` currently detects zero-minute same-station transfers between train legs. Bus stop IDs (0–29999) and train mapids (40000+) are in different numeric ranges and will never collide, so the existing detection logic should work without changes. Verify this and add a comment to that effect.

### Notes

- Do not change the function signature of `_path_to_route()`.
- The `from_node == ORIGIN` / `to_node == DEST` checks for walk legs already handle mid-path walk edges via the existing `edge_type == "transfer"` handler — a walk edge between a train station and a bus stop falls through to this handler correctly, rendering a `WalkLeg` with named endpoints. No changes needed for these walk legs.

---

## Chunk 5 — Update `find_routes()` and `main.py` integration

### Part A — `find_routes()` in `transit_graph.py`

**Add bus stop virtual edges** so the unified graph can find paths that start or end at a bus stop.

In `find_routes()`, after the existing block that adds `ORIGIN → train_station` and `train_station → DEST` virtual edges, add a matching block for nearby bus stops:

```python
# Add virtual walk edges to/from nearby bus stops (same pattern as train stations)
origin_bus_stops = find_nearest_bus_stops(origin_lat, origin_lon)   # existing function
for stop in origin_bus_stops:
    walk_min = stop["walk_minutes"]
    G_local.add_edge(ORIGIN, stop["stop_id"],
                     weight=walk_min, edge_type="walk", route_id="walk", mode="walk")

dest_bus_stops = find_nearest_bus_stops(dest_lat, dest_lon)         # existing function
for stop in dest_bus_stops:
    walk_min = stop["walk_minutes"]
    G_local.add_edge(stop["stop_id"], DEST,
                     weight=walk_min, edge_type="walk", route_id="walk", mode="walk")
```

The `finally` block that removes `ORIGIN` and `DEST` already removes all edges incident to these virtual nodes — no change needed there.

**Do not change the `n_routes` function default.** It stays at 3. `main.py` will pass `n_routes=5` explicitly (see Part B).

### Part B — `main.py`

**1. Pass `n_routes=5` to `find_routes()`.**

Find the call to `find_routes()` in the `/recommend` endpoint and add `n_routes=5` explicitly:

```python
routes = find_routes(
    origin_lat, origin_lon,
    dest_lat, dest_lon,
    n_routes=5,        # ← add this
)
```

**2. Add route fingerprint deduplication after merging.**

After `find_routes()` and `find_bus_routes()` results are merged and sorted, add a deduplication pass to remove bus-only routes from the graph that duplicate `find_bus_routes()` results. Insert this block immediately after the merge sort:

```python
def _route_fingerprint(route):
    return tuple(
        (leg.leg_type, getattr(leg, "line_code", ""), getattr(leg, "from_mapid", ""), getattr(leg, "to_mapid", ""))
        for leg in route.legs
    )

seen_fingerprints = set()
deduplicated = []
for total, wait, route in combined_sorted:
    fp = _route_fingerprint(route)
    if fp not in seen_fingerprints:
        seen_fingerprints.add(fp)
        deduplicated.append((total, wait, route))
combined_sorted = deduplicated
```

**3. No other changes to `main.py`.** `_rank_routes()`, `_rank_bus_routes()`, `_format_routes()`, `build_prompt()`, and the response serializer are all unchanged.

---

## Chunk 6 — Frontend verification (no new code expected)

**Files:** `frontend/src/App.jsx`, `frontend/src/MapView.jsx`

This chunk is verification only. The frontend already handles mixed-mode route cards because `RouteLegs` renders each leg by type, and bus legs already have `BUS_DIRECTION_COLORS` and `line_code` pills.

### Verify the following

- [ ] A route card with train legs followed by a walk transfer then bus legs renders without errors or blank sections.
- [ ] The walk transfer leg between a train station and a bus stop renders as a `WalkLegItem` with both endpoint names showing (not "Your location" / "Your destination").
- [ ] Map rendering: `renderRoute()` picks correct colors for bus legs within a mixed route via `BUS_DIRECTION_COLORS`. If a direction string is not in the map, confirm the fallback color does not crash.
- [ ] Walk transfer polylines between train station and bus stop render as dashed gray segments on the map — confirm `leg.path` is populated for these legs (it should be, since `_path_to_route()` uses `street_walk_minutes` which returns path geometry).
- [ ] Zero-minute walk transfers (train station and bus stop at the same location) render without blank or broken line items.

### Manual end-to-end test

Find a real Chicago trip that benefits from an intermodal route. A good example: **origin near a Brown Line station, destination south of Western Ave** — the app should surface Brown Line to Western, then Bus 49 southbound as a structured route card alongside pure-train and pure-bus options.

Confirm the route card shows: walk leg → train leg (Brown Line) → walk transfer leg → bus leg (Route 49) → walk leg.

---

## Verification checklist for Claude Code

### transit_graph.py

- [ ] `_build_graph()` adds bus stop nodes with `node_type="bus"`, `lat`, `lon`, `name` attributes (Chunk 1).
- [ ] Existing train nodes have `node_type="train"` added (Chunk 1).
- [ ] `_build_graph()` adds bus transit edges with `mode="bus"`, `line_code`, `line`, `edge_type="transit"` (Chunk 2).
- [ ] Existing train transit edges have `mode="train"` added (Chunk 2).
- [ ] `_build_graph()` adds bidirectional train↔bus walk edges with `edge_type="walk"`, `mode="walk"`, capped at 5 min street walk (Chunk 3).
- [ ] Startup log prints node count, edge count, and transfer edge count (Chunk 3).
- [ ] `_path_to_route()` resolves bus stop names and coordinates via graph node attributes when not found in `stations` (Chunk 4).
- [ ] `_path_to_route()` correctly assembles `TransitLeg` for `mode="bus"` edges (Chunk 4).
- [ ] `find_routes()` adds `ORIGIN→bus_stop` and `bus_stop→DEST` virtual walk edges (Chunk 5A).
- [ ] `find_routes()` function signature default for `n_routes` is **unchanged** at 3 (Chunk 5A).

### main.py

- [ ] `find_routes()` is called with `n_routes=5` explicitly (Chunk 5B).
- [ ] `_route_fingerprint()` deduplication runs after the merge sort (Chunk 5B).
- [ ] `find_bus_routes()` and `find_bus_transfer_routes()` are **not** modified.
- [ ] `_rank_routes()`, `_rank_bus_routes()`, `_format_routes()`, `build_prompt()` are **not** modified.

### What is NOT changed

- `find_bus_routes()` — internal logic unchanged.
- `find_bus_transfer_routes()` — unchanged.
- `get_bus_stop_sequences()` — unchanged (still called by `_build_graph()` internally).
- `_rank_routes()`, `_rank_bus_routes()` — unchanged.
- `_format_routes()` — unchanged; already handles bus and train legs.
- All dataclasses (`WalkLeg`, `TransitLeg`, `Route`) — unchanged.
- The API response schema — unchanged.
- Frontend components — no code changes expected; verification only.

---

## Optional post-implementation: scoping `find_bus_routes()` deprecation

Once Feature B is live and verified, the unified graph's `find_routes()` will surface bus-only paths alongside intermodal ones, making `find_bus_routes()` partially redundant. Full deprecation is a **separate decision** — do not attempt it as part of Feature B. This section scopes the work required if that decision is made in a future session.

### What `find_bus_routes()` currently provides that the unified graph does not

Before deprecating, confirm that `find_routes()` on the unified graph fully replaces `find_bus_routes()` for the following:

- **Live arrival data on the first boarding leg.** `find_bus_routes()` queries `bus_arrivals` (from the CTA Bus Tracker API) to get real-time wait times for the first bus. `find_routes()` / Dijkstra uses static GTFS schedule weights and does not consult `bus_arrivals`. If `find_bus_routes()` is removed, the first-leg bus wait becomes a schedule estimate only. Determine whether this is acceptable before deprecating.
- **Progressive exit-stop threshold.** `find_bus_routes()` uses a two-pass haversine filter to prune buses that don't make meaningful progress toward the destination. The unified graph relies solely on Dijkstra edge weights — it may surface bus paths that are technically shortest-path but not useful. Validate route quality in real-world testing first.
- **`find_bus_transfer_routes()` activation gate.** `find_bus_transfer_routes()` is currently only called when `find_bus_routes()` returns empty results. If `find_bus_routes()` is removed, the activation gate must be redesigned (e.g. trigger when `find_routes()` returns no route that terminates within 0.25 miles of the destination).

### All code locations that reference `find_bus_routes()`

A complete deprecation requires changes in the following locations:

**`backend/transit_graph.py`**
- Line ~1361: **function definition** — `def find_bus_routes(...)`. The entire function body (~200 lines) would be removed.
- Line ~627: **comment** in `_build_shape_lookup()` — `"find_bus_routes() calls get_shape(route_short_name, direction_id)"`. Update or remove the comment.
- Lines ~1584, ~1600, ~1610: **comments and docstring** inside `find_bus_transfer_routes()` that reference `find_bus_routes()` as the caller and activation-gate context. Update to reflect the new gate logic.

**`backend/main.py`**
- Line ~25: **import** — `find_bus_routes` in the `from transit_graph import ...` line. Remove it.
- Line ~649: **call site** — the bus routing block that calls `find_bus_routes(...)`. This entire block must be restructured: remove the `find_bus_routes()` call; decide whether `find_bus_transfer_routes()` is still called (and on what trigger); decide whether `_rank_bus_routes()` is still needed (it normalises `find_bus_routes()` / `find_bus_transfer_routes()` wait semantics — keep it if `find_bus_transfer_routes()` is retained).
- Lines ~337, ~340, ~348: **comments and docstring** in `_rank_bus_routes()` that describe its relationship to `find_bus_routes()`. Update to reflect the new caller context.

**`backend/cta_client.py`**
- Line ~203: **comment** on a field — `"# GTFS stop ID — used by find_bus_routes()"`. Update to reflect new caller if the field is still used, or remove the comment.

### Recommended deprecation approach (if pursued)

1. Keep `find_bus_transfer_routes()` — it provides bus+bus transfer routes that the unified graph does not model (bus-to-bus walk transfers are not in the graph).
2. Remove `find_bus_routes()` and its import.
3. Restructure the bus routing block in `main.py`: call `find_bus_transfer_routes()` unconditionally (not as a fallback) when `transit_mode` is `"Bus"` or `"All"`, subject to the existing `bus_arrivals and origin_bus_stops` guard.
4. Update the `_rank_bus_routes()` docstring to reference `find_bus_transfer_routes()` as its sole caller.
5. Update all comments listed above.
6. Run the full verification checklist for Feature B after the removal to confirm no routing regressions.

---

## Documentation updates after implementation

Once all 6 chunks are complete and verified, update the following files:

1. **`FEATURE_IMPLEMENTATION_PLANS.md`** — Change Feature B status from `⬜ Not started` to `✅ Complete (date)`. Add a "What was implemented" summary section (same pattern as Features A, C, E, F, G).

2. **`Feature_Prioritization.md`** — Delete the Feature B entry from "Chunked Features". Update the "Multi-Leg Train Routing — Gap 2" entry to mark it resolved (it is resolved as a natural consequence of Feature B). Update "Multi-Leg Train Routing — Gap 1" to note it must now be written against the post-B version of `_path_to_route()`.

3. **`cta_app_handoff_prompt.md`** — Add a session summary entry for this work. Strike through Feature B in the Known Pending Items list and mark it complete with the date.
