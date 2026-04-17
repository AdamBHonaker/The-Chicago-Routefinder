# Feature Prioritization

Classification of each feature as **Bolt-On** (self-contained, no dependencies on other planned features) or **Structural** (depends on one or more other planned or unplanned features before it can be built or fully realized). Once a feature has been completed, it should be deleted from this file when updating documentation, and any features with a dependency on the completed feature should be updated to remove that portion of their dependencies.

---

## Chunked Features

### Feature D — Live Arrivals at Transfer Stop
**Type: Structural (soft dependency)**
The train-to-train half works independently today. The bus-transfer half depends on:
- **Feature C** (Bus+Bus Transfers) — bus transfer arrivals are only meaningful once bus transfer routes exist. ✅ Feature C is now complete, so this dependency is satisfied.

---

## Future Enhancements

### Multi-Leg Train Routing — Gap 1 (Shared-Track Edge Deduplication)
**Type: Structural**
Modifies `_path_to_route()`. Feature B is now complete — any fix here must be written against the post-B version of `_path_to_route()` (which uses `_resolve_node()` for all node metadata). No additional dependency blockers remain.

---

### Feature J — Deprecate `find_bus_routes()` in Favor of Unified Graph
**Type: Bolt-On**
Self-contained cleanup to `transit_graph.py`, `main.py`, and `cta_client.py`. No dependency on any planned feature beyond Feature B (which is ✅ complete).

**Prerequisite:** Feature B must be verified in production — unified-graph bus-only routes must be manually validated on real Chicago trips before `find_bus_routes()` is removed.

**What it does:** Removes `find_bus_routes()` (~200 lines) now that the unified NetworkX graph from Feature B surfaces bus-only paths via `find_routes()`. Restructures `main.py` to call `find_bus_transfer_routes()` unconditionally (not as a fallback). Removes the `_route_fingerprint()` deduplication step that exists only to reconcile the two bus-routing codepaths. Full implementation plan in `FEATURE_IMPLEMENTATION_PLANS.md`.

**Files touched:**
- `backend/transit_graph.py` — remove `find_bus_routes()` definition (~200 lines); update comments in `_build_shape_lookup()` and `find_bus_transfer_routes()`
- `backend/main.py` — remove import and call site; restructure bus routing block; update `_rank_bus_routes()` docstring; remove `_route_fingerprint()` dedup
- `backend/cta_client.py` — update stale comment referencing `find_bus_routes()`

