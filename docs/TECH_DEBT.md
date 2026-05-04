# Technical Debt

Known technical debt catalogued for future resolution. Priority: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When an item in this file is resolved, **delete its entry from this file** and add a corresponding entry to the **Technical Debt Paid Off** section of [`docs/archive/RESOLVED_HISTORY.md`](archive/RESOLVED_HISTORY.md) documenting what was changed and how. This file should only ever contain debt that has not yet been addressed.

---

> **Audit date:** 2026-04-28 · Files scanned: entire project (`backend/`, `frontend/`, config files)
>
> **Resolved:** 2026-04-30 · All 2026-04-28 scan items resolved previously.

---

> **Audit date:** 2026-04-30 · Files scanned: `frontend/src/`, `backend/*.py`
>
> **Resolved:** 2026-04-30 · All 15 actionable items resolved (see RESOLVED_HISTORY.md). TD-BE-004 (dual graph library: networkx + igraph) intentionally deferred pending performance profiling.

---

### TD-BE-005 · Routing accuracy test suite (requires human authoring)

- **File**: `backend/tests/` (new file: `test_routing_accuracy.py`)
- **Category**: Missing Test Coverage
- **Priority**: 🟢 Low (was 🟡 Medium — invariants layer resolved 2026-05-04)
- **Status**: **Partially resolved.** Layer 2 (invariants) shipped 2026-05-04 in `test_graph_construction.py` (16 tests). Layers 1 (golden fixtures) and 3 (determinism harness) remain — both still require human authoring.
- **Description**: Existing `test_transit_graph.py` covers pure helpers and `test_endpoints.py` covers the API contract with mocks, but nothing exercises end-to-end routing correctness against known-good answers on the real Chicago graph. Routing accuracy is called out in CLAUDE.md / PROJECT_CONTEXT as non-negotiable; without a golden suite, silent regressions in `find_routes()` / `find_bus_transfer_routes()` after graph or scoring changes will not be caught by CI.
- **Why human authoring is required**: The golden fixtures encode rider-judgment calls about what counts as the "right" route for a given OD pair. Claude cannot author these correctly without local Chicago knowledge.
- **Three layers — current status:**
    1. **Golden-route fixtures** — ⏳ Not started. ~10–15 origin/destination pairs with expected primary mode and transfer count (not exact minutes — those drift with GTFS). Cover: single-line train, train+train transfer, bus+train, bus+bus, walk-only short hop, edge-of-service-area. Example: *Logan Square → Hyde Park should prefer Blue→Red over a 3-bus chain.*
    2. **Invariants** — ✅ Resolved 2026-05-04 in `test_graph_construction.py`. Tests verify on hand-built fixture graphs that: same-route consecutive edges merge into one TransitLeg, different routes do not merge, `transfer` edges become WalkLegs, transfer count equals `max(0, n_transit_legs - 1)`, walk-only routes have zero transfers, ORIGIN/DEST walk lookups override edge weights, faster path is preferred over slower, `n_routes` cap honored, disconnected graphs return `[]`. Synthetic graphs only — invariants hold but real Chicago routing decisions are still untested.
    3. **Determinism harness** — ⏳ Not started. Freeze "now" and stub real-time arrivals so results are reproducible in CI.
- **Open decisions for human (still outstanding)**: (a) does the golden-fixtures suite hit the live GTFS feed in `backend/gtfs_data/` or a trimmed fixture feed? (b) golden fixtures next, or determinism harness first?

---

_No other outstanding items at this time._

---

## Deferred (awaiting profiling before action)

### TD-BE-004 · Dual graph library dependency (networkx + igraph)

- **File**: `backend/transit_graph.py` (networkx), `backend/walking.py` (igraph)
- **Category**: Duplicated Code
- **Priority**: Low
- **Description**: Transit routing uses NetworkX while the walking engine uses igraph. Both are large graph-algorithm libraries (~30–50 MB combined install). igraph is typically 5–10× faster and could handle transit routing too.
- **Deferred reason**: Migration would be a significant rewrite. Profile `warm_up()` build phase first to confirm NetworkX is a real bottleneck before committing.

---

_All items from the 2026-04-30 scans have been resolved. See RESOLVED_HISTORY.md for details._

---

> **Audit date:** 2026-05-04 · Files scanned: all `backend/*.py` (21 modules, ~10,500 LOC). Excluded `backend/scripts/` and `backend/tests/`.
>
> **Resolved:** 2026-05-04 · All 3 actionable items (TD-BE-006, TD-BE-007, TD-BE-008) resolved in the same session. See `docs/archive/RESOLVED_HISTORY.md` for details.

---

> **Audit date:** 2026-05-04 · Files scanned: `frontend/src/`
>
> **Resolved:** 2026-05-04 · All 11 frontend items (TD-FE-006 through TD-FE-016) resolved in the same session. See `docs/archive/RESOLVED_HISTORY.md` for details.

---
