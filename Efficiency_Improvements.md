# Efficiency Improvements

Known efficiency improvements catalogued for future improvement. Impact: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When an efficiency improvement in this file is implemented, **delete its entry from this file** and add a corresponding entry to the **Efficiency Improvements Implemented** section of [`RESOLVED_HISTORY.md`](RESOLVED_HISTORY.md) documenting what was changed and how. This file should only ever contain improvements that have not yet been implemented.

---

## Deferred / Not Yet Implemented

### OPT-017 · HMAC Digest Computed Inside the Lock in `dau.py`
- **File**: `backend/dau.py`
- **Line(s)**: `record_visit()` — digest computation after lock acquisition
- **Category**: Lock Contention
- **Impact**: 🟢 Low
- **Description**: In `record_visit()`, the HMAC digest is computed inside `async with _lock`, even though the computation is purely CPU-bound and does not depend on shared state (only `_today_hmac_key` and the caller-supplied `ip`, both read-only at that point). Moving the digest computation before the lock acquisition would shorten the critical section to just the set membership check and add.
- **Note**: **Requires care** — `_today_hmac_key` must represent the same day as the `_current_day` check inside the lock. If a coroutine reads `_today_hmac_key` just before midnight and then acquires the lock after another coroutine has already rolled the day forward, it would hash the IP with yesterday's key and insert the wrong digest into today's `_seen_hashes`. This could cause a visit at the midnight boundary to be either double-counted (if yesterday's digest isn't in today's set) or silently dropped (in an unlikely collision). The existing comment on lines 103–106 documents exactly this invariant. Any implementation must either (a) snapshot the key and date together before the lock, then verify the date hasn't changed after acquiring it, or (b) accept the small midnight-boundary risk as negligible.

---

### OPT-010 · trips.txt Read Three Times During Startup
- **File**: `backend/transit_graph.py`
- **Line(s)**: `_load_representative_trips()`, `_load_bus_candidate_trips()`, `_build_shape_lookup()`
- **Category**: Redundant I/O
- **Impact**: 🟡 Medium
- **Description**: trips.txt is streamed three times at startup: once for train weekday candidate trips, once for bus weekday candidate trips, and once inside `_build_shape_lookup()` to collect `(route_id, direction_id, shape_id)` candidates. All three reads could be combined into a single pass.
- **Note**: **Requires care** — `_build_shape_lookup()` intentionally reads all trips (no weekday filter) to collect the full set of `shape_id` candidates. The other two loaders filter to weekday service IDs only. A merged pass must apply the weekday filter only to the trip-candidate outputs, not to the shape_id collection step. Failing to respect this distinction would cause weekend-only services to lose their GTFS shape, falling back to a straight-line polyline.

---

