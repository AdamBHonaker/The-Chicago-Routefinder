# Technical Debt

Known technical debt catalogued for future resolution. Priority: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When an item in this file is resolved, **delete its entry from this file** and add a corresponding entry to the **Technical Debt Paid Off** section of [`RESOLVED_HISTORY.md`](RESOLVED_HISTORY.md) documenting what was changed and how. This file should only ever contain debt that has not yet been addressed.

> **Audit date:** 2026-04-28 · Files scanned: entire project (`backend/`, `frontend/`, config files)
> **Resolved:** 2026-04-30 · All 2026-04-28 scan items resolved previously.

---

> **Audit date:** 2026-04-30 · Files scanned: `frontend/src/`, `backend/*.py`
> **Resolved:** 2026-04-30 · All 15 actionable items resolved (see RESOLVED_HISTORY.md). TD-BE-004 (dual graph library: networkx + igraph) intentionally deferred pending performance profiling.

---

_No outstanding items at this time._

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
