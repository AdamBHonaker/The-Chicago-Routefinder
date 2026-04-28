# Bugs To Be Fixed

Known issues catalogued for future fixing. Severity: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When a bug in this file is fixed, **delete its entry from this file** and add a corresponding entry to the **Bugs Fixed** section of [`RESOLVED_HISTORY.md`](RESOLVED_HISTORY.md) documenting what was changed and how. This file should only ever contain bugs that have not yet been resolved.

---

## BUG-007 · Transit photos missing from production

- **File**: `frontend/public/transit-photos/` (directory), `frontend/src/App.jsx` (`PHOTOS` array)
- **Severity**: Low

**What happens:** The `frontend/public/transit-photos/` directory contains no image files. The app references photos like `blue-line-ohare.jpg` which return 404 on production, showing broken images in the background photo feature. This is a pre-existing asset gap from Phase 6 setup, not a code bug.

**Fix:** Add ≥10 transit photos to `frontend/public/transit-photos/` and update the `PHOTOS` array in `frontend/src/App.jsx` to match the filenames. Then commit and let Vercel redeploy.

---

## Bug Scan — 2026-04-28 (backend/)

> Scanned: `backend/main.py`, `backend/cta_client.py`, `backend/crowdedness.py`, `backend/dau.py`, `backend/walking.py`, `backend/weather_service.py`, `backend/gtfs_loader.py`, `backend/route_scoring.py`, `backend/transit_graph.py`, `backend/utils.py`
> Found: 4 bug(s)

---

### BUG-008 · `get_counts()` returns stale DAU data
- **File**: `backend/dau.py`
- **Line(s)**: 142–144
- **Severity**: Medium
- **Description**: `get_counts()` calls `_load()` which reads directly from disk, completely bypassing the in-memory `_counts_cache`. Any unique visitors accumulated since the last flush (up to 30 seconds or 20 visits per the batch-write config) are silently omitted from the `/admin/dau` response. The in-memory count is authoritative and always up-to-date; the disk file is a lagging snapshot.
- **Reproduction**: Hit `/ping` several times in quick succession (fewer than 20 unique IPs), then immediately call `/admin/dau` before the next flush fires. The count returned will be lower than the true number of unique visitors for that day.
- **Suggested Fix**: Return `dict(_counts_cache)` (merged with the current in-flight count) instead of calling `_load()`. To reflect today's in-memory state: merge `{**dict(_counts_cache), today: _base_count + len(_seen_hashes)}` under `_lock` to avoid a data race.

---

### BUG-009 · Crowdedness stop-position factor is always 1.0 (bell-curve disabled)
- **File**: `backend/main.py`
- **Line(s)**: 1202–1212 (`_crowdedness_for_routes`)
- **Severity**: Low
- **Description**: `estimate_crowdedness()` is called with hardcoded `stop_sequence_position=1, total_stops=2` for every transit leg. The bell-curve formula is `0.6 + 0.4 * sin(position/total * π)` — with these values that always evaluates to `sin(π/2) = 1.0`, the maximum possible position factor. The stop-position adjustment documented in `crowdedness.py` (lighter crowding at terminals, heavier in the middle) is effectively dead code for every route displayed to users.
- **Reproduction**: Any request — the factor is always 1.0 regardless of the line or stop.
- **Suggested Fix**: Pass the actual stop sequence position by looking up the transit leg's `from_mapid` in the bus/train stop sequence data via `get_bus_stop_sequences()`. At a minimum, a rough 3-bucket heuristic (start/middle/end of route) would re-enable the adjustment.

---

### BUG-010 · "Freezing Sleet" NWS text misclassified as FREEZING_RAIN
- **File**: `backend/weather_service.py`
- **Line(s)**: 165–171 (`_parse_precip`)
- **Severity**: Low
- **Description**: The `"freezing" in fc` check appears before the `"sleet"` check. If the NWS short-forecast text contains both words (e.g. `"Freezing Sleet"` or `"Slight Chance Freezing Sleet"`), the condition short-circuits and the precipitation is classified as `FREEZING_RAIN` instead of `SLEET`. The two types are semantically distinct and map to different intensities and routing heuristics.
- **Reproduction**: Trigger a weather fetch when NWS reports "Freezing Sleet" for Chicago.
- **Suggested Fix**: Check for sleet/ice pellets before the generic `"freezing"` catch. Move the `elif "sleet" in fc or "ice pellet" in fc` branch above the `if "freezing" in fc` branch, or add `and "sleet" not in fc and "ice pellet" not in fc` to the freezing-rain guard.

---

### BUG-011 · Last-departure tracking compares arrival time but stores departure string
- **File**: `backend/transit_graph.py`
- **Line(s)**: 376–382 (`_stream_all_stop_sequences`)
- **Severity**: Low
- **Description**: The `last_dep` accumulator finds the "latest" stop-time row per `(parent_mapid, direction_id)` by comparing `arr_min` (arrival), but stores `dep_str` (the departure time string for that row). For intermediate stops the departure time is later than arrival, so the row with the largest `arr_min` may not have the largest `dep_min`. In edge cases a different trip could have a slightly higher `arr_min` while the correct trip has the actual latest departure, causing the "last train" countdown to be off by a few minutes.
- **Reproduction**: Most likely to surface on lines with close last-run spacing (Yellow Line, Purple Express) where two trips' final stops are only minutes apart.
- **Suggested Fix**: Parse `dep_str` into `dep_min` and compare on departure time: `if prev is None or dep_min > prev[0]: last_dep[key] = (dep_min, dep_str)`.

---

