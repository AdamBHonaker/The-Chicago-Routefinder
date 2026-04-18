# Efficiency Improvements

Known efficiency improvements catalogued for future improvement. Impact: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When an efficiency in this file is implemented, **delete its entry from this file** and add a corresponding entry to [`Efficiency_Improvement_History.md`](Efficiency_Improvement_History.md) documenting what was changed and how. This file should only ever contain improvements that have not yet been implemented.

## Efficiency Scan — 2026-04-18 (backend/)

> Scanned: `backend/main.py`, `backend/gtfs_loader.py`, `backend/transit_graph.py`
> Found: 6 opportunities (6 resolved → see `Efficiency_Improvement_History.md`)

---

### OPT-007 · Consolidate street-graph intersections to shrink `street_graph.graphml`
- **File**: [backend/fetch_street_graph.py](backend/fetch_street_graph.py) (offline prep); consumer [backend/walking.py](backend/walking.py)
- **Line(s)**: [fetch_street_graph.py:71-78](backend/fetch_street_graph.py#L71-L78) (insert consolidation step after `graph_from_bbox`, before `save_graphml`)
- **Category**: Memory Footprint / Asset Size
- **Impact**: 🟡 Medium
- **Context**: The cached pedestrian graph is ~120 MB on disk and contributed to the Railway OOM crash fixed in commit `954c7fa` (street-graph load is currently deferred — see Feature K in the handoff). OSM models most intersections as 4–8 distinct nodes (one per approach lane / turn pocket); those collapse cleanly without routing-quality loss at pedestrian precision.
- **Description**: Apply `osmnx.simplification.consolidate_intersections(G, tolerance=10, rebuild_graph=True, dead_ends=False)` as a one-time preprocessing step inside `fetch_street_graph.py` before `ox.save_graphml`. Expected reduction: 20–40% fewer nodes and a proportional drop in edges, producing a smaller `.graphml` on disk and a correspondingly smaller in-memory `MultiDiGraph` at runtime.
- **Suggested Improvement**:
  1. After `G = ox.graph_from_bbox(...)` in `fetch_street_graph.py`, project to a metric CRS (`ox.project_graph(G)`), run `consolidate_intersections(..., tolerance=10, rebuild_graph=True, dead_ends=False)`, then project back to EPSG:4326 before saving. Log before/after node + edge counts so the reduction is visible.
  2. Re-run `python fetch_street_graph.py --force` locally to regenerate the file; commit the smaller `.graphml` via Git LFS (no consumer code changes needed — `walking.py` uses only `ox.nearest_nodes` and `nx.shortest_path*`, both unaffected).
  3. Measure RSS during `_load_graph()` in [walking.py:41-66](backend/walking.py#L41-L66) before and after; record the delta in `Efficiency_Improvement_History.md`.
- **Risk / Caveats**:
  - Edge attributes on merged parallel edges get combined — verify `length` (used at [walking.py:92](backend/walking.py#L92)) remains numeric and sensible. Geometry is preserved as edge attributes, not lost.
  - `consolidate_intersections` on a continent-scale `walk` bbox for Chicago takes minutes; fine as an offline step, do NOT move it to runtime.
  - `dead_ends=False` avoids collapsing cul-de-sacs that share a stub with a main road; keep this default unless profiling shows otherwise.
- **Estimated effort**: 1–2 hours (one code change + regenerate + commit LFS file + measure).

---

### OPT-009 · Cache shortest path computation to avoid redundant routing

- **File**: [backend/walking.py](backend/walking.py)
- **Line(s)**: [walking.py:75-97](backend/walking.py#L75-L97) (`walk_minutes`), [walking.py:99-199](backend/walking.py#L99-199) (`walk_directions`), [walking.py:201-267](backend/walking.py#L201-267) (`walk_path`)
- **Category**: Redundant Computation
- **Impact**: 🟡 Medium
- **Context**: `walk_minutes`, `walk_directions`, and `walk_path` all independently compute `nx.shortest_path` for the same origin/dest points, leading to duplicate routing calculations when multiple functions are called.
- **Description**: Add a cached helper function `_get_shortest_path` that computes and caches the node path list. Modify the three functions to use this cached path, computing length or directions from it as needed.
- **Suggested Improvement**:
  1. Add `@lru_cache(maxsize=512)` decorated `_get_shortest_path(origin_lat, origin_lon, dest_lat, dest_lon) -> list[int]` that loads graph, finds nodes, computes `nx.shortest_path`.
  2. In `walk_minutes`, call `_get_shortest_path` and sum edge lengths from the path.
  3. In `walk_directions` and `walk_path`, use the cached path directly.
- **Risk / Caveats**: Ensure the cache handles exceptions consistently; path computation is the expensive part, so minimal risk.
- **Estimated effort**: 1 hour.

---

### OPT-008 · Replace NetworkX MultiDiGraph with a compact graph representation (igraph or CSR)
- **File**: [backend/walking.py](backend/walking.py) (primary consumer); [backend/fetch_street_graph.py](backend/fetch_street_graph.py) (may need an additional export step)
- **Line(s)**: [walking.py:19-66](backend/walking.py#L19-L66) (load + cache); [walking.py:83-97](backend/walking.py#L83-L97), [walking.py:134-145](backend/walking.py#L134-L145), [walking.py:216-230](backend/walking.py#L216-L230) (call sites using `ox.nearest_nodes` + `nx.shortest_path*`)
- **Category**: Memory Footprint
- **Impact**: 🔴 High
- **Context**: NetworkX stores the graph as nested Python dicts (~200+ bytes of overhead per node/edge). A ~120 MB GraphML file balloons to several hundred MB in RAM once loaded, which is the root cause of the deferred street-graph load on Railway. Swapping to igraph (C-backed) or a SciPy CSR matrix typically yields a 5–15× memory reduction. This is the biggest single RAM lever available on the backend and would very likely un-block Feature K.
- **Recommendation**: Prefer **igraph** over raw CSR. igraph preserves per-edge attribute semantics and a familiar API while still giving ~10× reduction; raw CSR needs parallel NumPy arrays per attribute and a bespoke nearest-node index, for limited additional savings.
- **Scope is split into 3 chunks** so the work can land incrementally:

  #### OPT-008a · Benchmark current footprint & validate target
  - Measure `_load_graph()` peak RSS and steady-state RSS on the current `.graphml` (ideally after OPT-007 lands, so the baseline reflects the smaller graph).
  - Prototype a standalone script that loads the same graph into `igraph.Graph` (via `igraph.Graph.Read_GraphML` or conversion from the NetworkX graph) and into a SciPy CSR matrix; record RSS for each.
  - **Deliverable**: numbers in a short comment block at the top of the OPT-008b PR confirming the expected 5–15× reduction on this specific graph. If the reduction is <3×, stop and re-scope — the rewrite cost is not justified.
  - **Effort**: 2–4 hours.

  #### OPT-008b · Swap runtime representation to igraph in `walking.py`
  - Replace `_graph_cache: nx.MultiDiGraph` with `_graph_cache: igraph.Graph` plus two side-tables held alongside it:
    - `_coord_kdtree`: a `scipy.spatial.cKDTree` built from node `(lon, lat)` — replaces `ox.nearest_nodes`. Store the original OSM node IDs in a parallel array so KDTree index → node ID is O(1).
    - `_node_id_to_index`: dict mapping OSM node ID → igraph vertex index (igraph uses contiguous int indices, not OSM IDs).
  - Rewrite the three call sites:
    - `ox.nearest_nodes(G, X=lon, Y=lat)` → `_coord_kdtree.query([lon, lat])` → igraph vertex index.
    - `nx.shortest_path_length(G, u, v, weight="length")` → `G.distances(source=u, target=v, weights="length")[0][0]`.
    - `nx.shortest_path(G, u, v, weight="length")` → `G.get_shortest_paths(u, to=v, weights="length", output="vpath")[0]`, then map indices back to `(lat, lon)` via the coordinate array for the polyline output.
  - Preserve the existing Haversine fallback at [walking.py:95-97](backend/walking.py#L95-L97) — nothing about failure semantics should change.
  - Update `backend/requirements.txt`: add `igraph>=0.11` (and `scipy` if not already pinned via osmnx's deps).
  - **Deliverable**: `walking.py` runs against igraph; all three public functions return values within a small tolerance of the NetworkX version for a fixed test set of origin/destination pairs (add a quick parity test).
  - **Risk**: igraph wheels must be available for the Railway build image (they are, on manylinux). Verify in CI before merging.
  - **Effort**: 1–2 days.

  #### OPT-008c · Move graph conversion offline and ship a pre-built artifact
  - Once OPT-008b is stable, extend `fetch_street_graph.py` to also emit a pre-converted igraph pickle (or igraph's native `.graphmlz`/`.picklez` format) alongside `street_graph.graphml`. Runtime then loads the compact artifact directly instead of parsing GraphML + converting on startup — faster cold start and avoids needing NetworkX at runtime.
  - Optionally drop the NetworkX runtime dependency from `requirements.txt` (still needed for the offline prep script).
  - **Deliverable**: startup log shows the compact artifact being loaded; cold-start time and RSS both measurably better than OPT-008b alone.
  - **Effort**: 2–4 hours.

- **Overall risk**: Medium. Behaviour-preserving but touches the one code path keeping Feature K blocked. Parity test in OPT-008b is the critical safety net.
- **Dependency ordering**: OPT-007 should land **before** OPT-008b — a smaller graph makes the benchmark (OPT-008a) cheaper and the parity test faster, and the two optimizations compound multiplicatively.

---

## Efficiency Scan — 2026-04-18 (backend/fetch*)

> Scanned: `backend/fetch_station_exits.py`, `backend/fetch_gtfs.py`, `backend/fetch_street_graph.py`
> Found: 2 opportunities (2 Low)

---

### OPT-010 · Pre-compute entrance trig before inner station loop in `build_exits`
- **File**: [backend/fetch_station_exits.py](backend/fetch_station_exits.py)
- **Line(s)**: [fetch_station_exits.py:128-131](backend/fetch_station_exits.py#L128-L131) (inner loop); [fetch_station_exits.py:44-47](backend/fetch_station_exits.py#L44-L47) (`_haversine_miles`)
- **Category**: Redundant Computation
- **Impact**: 🟢 Low
- **Description**: In `build_exits`, for each entrance node the inner loop calls `_haversine_miles(lat, lon, ...)` once per station (~150 stations). Inside `_haversine_miles`, `math.cos(math.radians(lat1))` is recomputed every call even though `lat1` (the entrance latitude) is constant across all station comparisons. This produces ~150 redundant `radians` + `cos` calls per entrance — roughly 75,000 extra trig operations across the full dataset.
- **Suggested Improvement**: Pre-compute `cos_lat = math.cos(math.radians(lat))` before the inner `for mapid, info in stations.items()` loop and pass it into a refactored `_haversine_miles`. Similarly, pre-compute `math.radians(lat)` for each station when building the `stations` dict so station-side trig is computed once rather than per entrance.

---

### OPT-011 · Avoid full-file row iteration for `stop_times.txt` in `validate_and_report`
- **File**: [backend/fetch_gtfs.py](backend/fetch_gtfs.py)
- **Line(s)**: [fetch_gtfs.py:91-93](backend/fetch_gtfs.py#L91-L93)
- **Category**: Redundant Computation
- **Impact**: 🟢 Low
- **Description**: `validate_and_report` opens every GTFS file and iterates every line to count rows (`sum(1 for _ in fh)`). `stop_times.txt` typically contains 8–10 million rows; reading all of them just to print a count adds several seconds of unnecessary I/O at the end of an already-slow download+extract step.
- **Suggested Improvement**: Replace the full-iteration row count with a fast binary chunk scan counting `\n` bytes, or report an estimated count derived from file size ÷ average row length. Alternatively, drop the row count and display file size only — size is the actionable signal for whether the download succeeded.

---

## Efficiency Scan — 2026-04-18 (`frontend/src/`)

> Scanned: `frontend/src/App.jsx`, `frontend/src/MapView.jsx`, `frontend/src/main.jsx`, `frontend/vite.config.js`, `frontend/package.json`
> Found: 4 opportunities (3 remaining · 1 resolved → see `Efficiency_Improvement_History.md`)

---

### OPT-015 · Deduplicate LINE_COLORS and BUS_DIRECTION_COLORS constants
- **File**: [frontend/src/App.jsx](frontend/src/App.jsx#L14-L30), [frontend/src/MapView.jsx](frontend/src/MapView.jsx#L16-L32)
- **Line(s)**: App.jsx 14–30 · MapView.jsx 16–32
- **Category**: Unnecessary Duplication
- **Impact**: 🟡 Medium
- **Description**: `LINE_COLORS` and `BUS_DIRECTION_COLORS` are defined identically in both files. Any color change must be made in two places; a mismatch would silently produce different colors on the card vs. the map layer.
- **Suggested Improvement**: Extract both objects into `frontend/src/constants.js` and import from there in both files. Zero runtime impact, eliminates the drift risk.

---

### OPT-016 · Precompute `isTransferLeg` before the `.map()` in `RouteLegs`
- **File**: [frontend/src/App.jsx](frontend/src/App.jsx#L149)
- **Line(s)**: 149
- **Category**: Redundant Computation
- **Impact**: 🟢 Low
- **Description**: Inside the `legs.map()`, `legs.slice(0, i).some(l => l.type === "transit")` creates a new sliced array and scans it for every leg rendered. This is O(n²) in the number of legs. For a typical 4-leg route that's 10 slice+scan operations per render; small today but unnecessary.
- **Suggested Improvement**: Compute a `Set` or boolean flag once before the map call:
  ```js
  let seenTransit = false;
  legs.map((leg, i) => {
    const isTransferLeg = seenTransit;
    if (leg.type === "transit") seenTransit = true;
    ...
  })
  ```

---

### OPT-017 · Replace persistent `map.on("data", …)` with a one-shot listener after style errors clear
- **File**: [frontend/src/MapView.jsx](frontend/src/MapView.jsx#L322-L326)
- **Line(s)**: 322–326
- **Category**: Rendering / DOM Inefficiency
- **Impact**: 🟡 Medium
- **Description**: The `"data"` event fires for every tile, source, and style load throughout the map's lifetime. On an active map session this can run hundreds of times per minute. The current handler checks `e.dataType === "style" && e.isSourceLoaded` before acting, but the event callback overhead accumulates across all tile loads. The listener was added to clear the `styleError` banner — once the style is confirmed loaded, the listener is no longer needed.
- **Suggested Improvement**: Remove the persistent listener and instead register a `map.once("styledata", () => setStyleError(false))` immediately after `setStyleError(true)` is set inside the `"error"` handler. This fires exactly once when the style recovers and never again, so there is zero ongoing per-tile overhead.

---

---

## Efficiency Scan — 2026-04-18 (`backend/gtfs_loader.py`)

> Scanned: `backend/gtfs_loader.py`
> Found: 3 opportunities (3 resolved → see `Efficiency_Improvement_History.md`)

