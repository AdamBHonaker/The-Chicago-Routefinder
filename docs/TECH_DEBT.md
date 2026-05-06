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

## Tech Debt Scan — 2026-05-06 (frontend)

> Scanned: `frontend/src/` (App.jsx, MapView.jsx, all components/, hooks/, utils/, constants, analytics, favorites, lineColors, i18n, main, index.css, App.css, styles/), `frontend/index.html`, `frontend/vite.config.js`, `frontend/package.json`
>
> Found: 6 item(s) · **Resolved 2026-05-06: 5 of 6** (TD-FE-017, TD-FE-018, TD-FE-020, TD-FE-021, TD-FE-022). TD-FE-019 retained — flipping CSP from report-only to enforce requires manual flow-by-flow QA that cannot be auto-resolved.

---

### TD-FE-019 · Content-Security-Policy still in report-only mode

- **File**: [frontend/index.html](frontend/index.html#L22)
- **Line(s)**: 22–34
- **Category**: TODO-FIXME / Pending Hardening
- **Priority**: 🟡 Medium
- **Status**: **Awaiting human walkthrough.** The CSP meta tag is `Content-Security-Policy-Report-Only`. The inline comment explicitly states the next step: *"Once a clean run through the main flows shows zero violations, swap `Content-Security-Policy-Report-Only` for `Content-Security-Policy` to enforce."* That validation has been deferred — until enforcement is on, the policy provides no actual protection. A wrong flip risks breaking production for users on networks where a tile/font CDN serves content from an origin we missed.
- **How to resolve**: Walk the main flows (search → results → trip → map tab → settings → language switch → saved routes → pinned stops) in production with DevTools open, capture any `[Report Only] Refused to…` console messages, fix or allowlist the offending sources, then change the meta-tag header to `Content-Security-Policy`. If any violations come from third-party tile/font CDNs that genuinely need to be allowlisted, update the policy directives in lockstep.

---

> **Audit date:** 2026-05-06 · Files scanned: `backend/*.py` (28 modules) and `backend/routes/*.py`. Excluded `backend/scripts/` and `backend/tests/`.
>
> **Resolved:** 2026-05-06 · All 7 actionable items (TD-BE-009 through TD-BE-015) resolved in the same session. See `docs/archive/RESOLVED_HISTORY.md` for details.

---
