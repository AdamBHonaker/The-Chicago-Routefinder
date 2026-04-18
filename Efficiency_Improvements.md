# Efficiency Improvements

Known efficiency improvements catalogued for future improvement. Impact: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When an efficiency in this file is implemented, **delete its entry from this file** and add a corresponding entry to [`Efficiency_Improvement_History.md`](Efficiency_Improvement_History.md) documenting what was changed and how. This file should only ever contain efficiencys that have not yet been implemented.

## Efficiency Scan — 2026-04-18 (backend/)

> Scanned: `backend/main.py`, `backend/gtfs_loader.py`, `backend/transit_graph.py`
> Found: 6 opportunities (1 resolved → see `Efficiency_Improvement_History.md`)

---

### OPT-002 · Repeated `get_station_by_name` lookups inside ranking hot path
- **File**: `backend/main.py`
- **Line(s)**: 308–319 (`_rank_routes`)
- **Category**: Redundant Computation
- **Impact**: Low
- **Description**: For each candidate route with multiple arrival directions, the inner loop calls `get_station_by_name(dest_name)` once per destination name. Across 5 ranked routes × up to ~4 directions, the same terminal names (e.g. "Howard", "95th/Dan Ryan") get resolved repeatedly within a single request.
- **Suggested Improvement**: Cache terminal-name → coords either via `functools.lru_cache` on `get_station_by_name` (if not already cached in `transit_graph.py`) or build a local `{dest_name: coords}` dict before entering the route loop. ⚠️ Unsure: may already be cached in `transit_graph.py` — verify first.

---

### OPT-003 · Full JSON rewrite on every geocode-cache flush
- **File**: `backend/gtfs_loader.py`
- **Line(s)**: 126–140, 152–175 (`_save_geocode_cache`, flush thread)
- **Category**: Inefficient I/O
- **Impact**: Low
- **Description**: The 30-second flush thread serialises the **entire** geocode cache to JSON and atomically renames it, even when only one new key was added since the last tick. As the cache grows (months of production queries), flush cost grows linearly while the delta is typically tiny.
- **Suggested Improvement**: Either (a) switch the backing store to SQLite / a tiny key-value file that supports incremental writes, or (b) keep JSON but track a `pending_writes` set and append-only journal, rewriting the full file less often (e.g. once per hour or at N pending entries). For the current call volumes this is Low impact — worth doing before it grows.

---

### OPT-004 · Per-request closure for route fingerprinting
- **File**: `backend/main.py`
- **Line(s)**: 718–733 (`_route_fingerprint` defined inside `/recommend`)
- **Category**: Redundant Computation
- **Impact**: Low
- **Description**: `_route_fingerprint` is a pure function defined inside the request handler, so a new function object is allocated on every `/recommend` call. The `seen_fps` dedup loop also performs a full O(n²ish) reconstruction of `ranked_routes` into `deduped` after already sorting.
- **Suggested Improvement**: Lift `_route_fingerprint` to module scope. Dedup in-place while building the sorted list — or fold dedup into the `sorted(...)[:5]` step by tracking seen fingerprints in a single pass.

---

### OPT-005 · Double dict lookup on cache hit/miss
- **File**: `backend/main.py`
- **Line(s)**: 572–577, 821–823 (response cache)
- **Category**: Redundant Computation
- **Impact**: Low
- **Description**: Cache read does `_response_cache.get(key)` followed by `del _response_cache[key]` (two hashes). Cache write does `if key in _response_cache: del _response_cache[key]` then `_response_cache[key] = ...` (up to three hashes). Minor, but hot path.
- **Suggested Improvement**: Use `_response_cache.pop(key, None)` for eviction in both places; for write, `_response_cache.move_to_end(key, last=True)` after assignment (or `_response_cache[key] = ...; _response_cache.move_to_end(key)`) achieves the same reorder without the membership test.

---

### OPT-006 · `fuzzy_match_neighborhood` scans all keys even after finding a high score
- **File**: `backend/gtfs_loader.py`
- **Line(s)**: 663–691
- **Category**: Redundant Computation
- **Impact**: Low
- **Description**: The fuzzy matcher iterates **all** ~240 `NEIGHBORHOOD_COORDS` keys with `SequenceMatcher` on every cache miss, even once a near-perfect score (≥0.99) is found. `SequenceMatcher.ratio()` is not cheap. Results are `lru_cache`d (maxsize=1024), so repeat queries are fine, but cold queries (every new user typo) pay full cost.
- **Suggested Improvement**: Short-circuit the loop when `best_score >= 0.99` — unlikely to be beaten and would skip ~half the work on average for strong matches. Also consider building a word-based inverted index (first significant word → candidate keys) so most queries only compare against a handful of keys rather than all 240.

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

