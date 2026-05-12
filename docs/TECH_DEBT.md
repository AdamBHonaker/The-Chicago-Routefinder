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

### TD-BE-005 · Routing accuracy test suite — golden fixtures still pending (require human authoring)

- **File**: `backend/tests/test_routing_accuracy.py` (scaffolded 2026-05-11) and `backend/tests/routing_harness.py` (harness shipped 2026-05-11)
- **Category**: Missing Test Coverage
- **Priority**: 🟢 Low (was 🟡 Medium — invariants layer resolved 2026-05-04; determinism harness shipped 2026-05-11)
- **Status**: **Partially resolved.** Layers 2 and 3 are done. Layer 1 (golden fixtures) remains and still requires human authoring.
- **Description**: Existing `test_transit_graph.py` covers pure helpers and `test_endpoints.py` covers the API contract with mocks, but nothing exercises end-to-end routing correctness against known-good answers on the real Chicago graph. Routing accuracy is called out in CLAUDE.md / PROJECT_CONTEXT as non-negotiable; without a golden suite, silent regressions in `find_routes()` / `find_bus_transfer_routes()` after graph or scoring changes will not be caught by CI.
- **Why human authoring is required**: The golden fixtures encode rider-judgment calls about what counts as the "right" route for a given OD pair. Claude cannot author these correctly without local Chicago knowledge.
- **Three layers — current status:**
    1. **Golden-route fixtures** — ⏳ Not started (scaffold exists). ~10–15 origin/destination pairs with expected primary mode and transfer count (not exact minutes — those drift with GTFS). Cover: single-line train, train+train transfer, bus+train, bus+bus, walk-only short hop, edge-of-service-area. Example: *Logan Square → Hyde Park should prefer Blue→Red over a 3-bus chain.* Three skipped placeholder tests in `test_routing_accuracy.py` show the intended pattern.
    2. **Invariants** — ✅ Resolved 2026-05-04 in `test_graph_construction.py`. Tests verify on hand-built fixture graphs that: same-route consecutive edges merge into one TransitLeg, different routes do not merge, `transfer` edges become WalkLegs, transfer count equals `max(0, n_transit_legs - 1)`, walk-only routes have zero transfers, ORIGIN/DEST walk lookups override edge weights, faster path is preferred over slower, `n_routes` cap honored, disconnected graphs return `[]`. Synthetic graphs only — invariants hold but real Chicago routing decisions are still untested.
    3. **Determinism harness** — ✅ Resolved 2026-05-11 in `tests/routing_harness.py`. `frozen_chicago_now()` freezes wall-clock time via freezegun so GTFS service-calendar selection is reproducible; `stub_cta_arrivals()` patches `get_train_arrivals` / `get_bus_arrivals` in `main`'s and `cta_client`'s namespaces with canned responses; `RoutingScenario` / `run_scenario()` bundle a frozen moment + OD pair + canned arrivals and exercise `find_routes()` against the real Chicago graph, returning a summary suitable for golden assertions. 7 harness smoke tests pass.
- **Decisions made (2026-05-11)**: (a) Golden suite will hit the live GTFS feed in `backend/gtfs_data/`, not a trimmed fixture feed. (b) Determinism harness first, then golden fixtures — chosen so authored fixtures are stable from day one.
- **Open work for human (Layer 1 — golden fixtures)**:
    - **What**: Author ~10–15 golden OD fixtures in [`backend/tests/test_routing_accuracy.py`](../backend/tests/test_routing_accuracy.py). Three skipped placeholders are already in place — additional fixtures should be added in the same pattern.
    - **Why a human is required**: Each fixture encodes a rider-judgment call about what the "right" route is for a given OD pair. Claude has no local Chicago knowledge and would author plausible-looking but wrong assertions.
    - **Where the authoritative authoring guide lives**: the module docstring at the top of [`backend/tests/test_routing_accuracy.py`](../backend/tests/test_routing_accuracy.py). It covers — categories to cover, how to pin OD coordinates without the geocoder, how to choose `frozen_at` (and what to do when GTFS calendar windows rotate), when to pass canned arrival data vs. leaving it empty, why assertions must be on shape (`primary_modes` / `lines` / `transfers`) and never on `total_minutes`, how to handle a previously-passing fixture that starts failing, and a per-fixture authoring checklist.
    - **Categories to cover** (one fixture each minimum; ~10–15 fixtures total): single-line train, train+train transfer, bus→train, train→bus, bus+bus transfer, walk-only short hop, edge-of-service-area, late-night service, weekend service.
    - **What NOT to do**: do not assert on `total_minutes` (drifts with every GTFS refresh); do not rely on the geocoder for OD coordinates (separate moving part); do not "fix" a failing fixture by updating its expected output without first investigating whether a real regression caused the failure.
    - **Definition of done for this layer**: every test in `test_routing_accuracy.py` has real OD coordinates, real assertions, no `@pytest.mark.skip` marker, and passes locally against the bundled `backend/gtfs_data/` feed. Once that's true, this TD-BE-005 entry can be deleted from TECH_DEBT.md and a corresponding Layer 1 entry added to RESOLVED_HISTORY.md.

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

### TD-FE-019 · Content-Security-Policy still in report-only mode

- **File**: [frontend/index.html](frontend/index.html#L22)
- **Line(s)**: 22–34
- **Category**: TODO-FIXME / Pending Hardening
- **Priority**: 🟡 Medium
- **Status**: **Awaiting human walkthrough.** The CSP meta tag is `Content-Security-Policy-Report-Only`. The inline comment explicitly states the next step: *"Once a clean run through the main flows shows zero violations, swap `Content-Security-Policy-Report-Only` for `Content-Security-Policy` to enforce."* That validation has been deferred — until enforcement is on, the policy provides no actual protection. A wrong flip risks breaking production for users on networks where a tile/font CDN serves content from an origin we missed.
- **How to resolve**: Walk the main flows (search → results → trip → map tab → settings → language switch → saved routes → pinned stops) in production with DevTools open, capture any `[Report Only] Refused to…` console messages, fix or allowlist the offending sources, then change the meta-tag header to `Content-Security-Policy`. If any violations come from third-party tile/font CDNs that genuinely need to be allowlisted, update the policy directives in lockstep.

---
