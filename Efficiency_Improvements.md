# Efficiency Improvements

Known efficiency improvements catalogued for future improvement. Impact: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When an efficiency improvement in this file is implemented, **delete its entry from this file** and add a corresponding entry to the **Efficiency Improvements Implemented** section of [`RESOLVED_HISTORY.md`](RESOLVED_HISTORY.md) documenting what was changed and how. This file should only ever contain improvements that have not yet been implemented.

---

## Deferred / Not Yet Implemented

### OPT-007 · GTFS Stop-Times Stream Reads Entire 354 MB File Without Early Exit
- **File**: `backend/transit_graph.py`
- **Line(s)**: 352–388
- **Category**: Inefficient I/O
- **Impact**: 🟡 Medium
- **Description**: `_stream_all_stop_sequences()` reads the full `stop_times.txt` (354 MB) even after representative trips for all lines and directions have been collected. Rows after the last needed trip (~1 M rows in) are pure overhead, but there is no early-exit condition.
- **Suggested Improvement**: Track how many (line, direction) pairs still need a representative trip. Break out of the CSV loop once the count reaches zero. In practice this should cut streaming time from ~60 s to ~15–20 s.
- **Note**: Deferred — the streaming loop also accumulates Feature Last Train data (`last_dep`) across ALL weekday trips, so an early exit based on line/direction pair completion would skip valid last-departure data. Needs deeper analysis before implementing.

---

### OPT-009 · Haversine Called 260 K Times in Nested Loop During Startup
- **File**: `backend/fetch_station_exits.py`, `backend/transit_graph.py`
- **Line(s)**: 140–150 (`fetch_station_exits.py`)
- **Category**: Redundant Computation
- **Impact**: 🟢 Low
- **Description**: Station-exit matching iterates all ~1,300 CTA stations against ~200 Overpass nodes, calling `_haversine_precomputed` ~260,000 times. This is a one-time startup cost but adds perceptible cold-start latency.
- **Suggested Improvement**: Pre-compute the full pairwise distance matrix with NumPy broadcasting (`numpy.hypot` on lat/lon arrays) in a single vectorized pass — orders-of-magnitude faster than a Python loop.
- **Note**: `fetch_station_exits.py` is a one-time offline script (not called at server startup), so runtime impact is minimal. Deferred.

---
