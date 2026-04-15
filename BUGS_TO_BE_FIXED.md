# Bugs To Be Fixed

Known issues catalogued for future fixing. Severity: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When a bug in this file is fixed, **delete its entry from this file** and add a corresponding entry to [`BUGS_FIXED_HISTORY.md`](BUGS_FIXED_HISTORY.md) documenting what was changed and how. This file should only ever contain bugs that have not yet been resolved.

---

## 🟢 Transit photos missing — broken images on production

**Files:** `frontend/public/transit-photos/`; `frontend/src/App.jsx` (PHOTOS array)

**What happens:** The `frontend/public/transit-photos/` directory contains no image files. The app references photos like `blue-line-ohare.jpg` which return 404 on production, showing broken images in the background photo feature. This is a pre-existing blocking item from Phase 6 setup, not a code bug.

**Fix:** Add ≥10 transit photos to `frontend/public/transit-photos/` and update the `PHOTOS` array in `frontend/src/App.jsx` to match the filenames. Then commit and let Vercel redeploy.

---

## 🟢 `get_bus_stop_sequences` streams 5.8M-row `stop_times.txt` a second time

**File:** `backend/transit_graph.py` lines 703–799

**What happens:** `_stream_stop_sequences` already reads `stop_times.txt` once during train graph build; `get_bus_stop_sequences` reads it again for bus sequences. That's ~7–10 s of startup time duplicated. Not a correctness bug — purely performance.

**Full scope (`backend/transit_graph.py` only):**

The fix collapses both passes into one stream inside `_build_graph()`, then caches the bus result so `get_bus_stop_sequences()` can return it without re-reading the file.

1. **Add a module-level cache variable** near the top of the file (after the `lru_cache` imports):
   ```python
   _bus_seq_cache: dict[tuple[str, str], list[tuple]] | None = None
   ```

2. **Replace `_stream_stop_sequences`** with a new `_stream_all_stop_sequences(train_candidates, train_dirs, bus_candidates, bus_dirs, platform_to_parent, bus_stop_lookup)`. The loop body checks `tid` against the union of both candidate sets, then dispatches to a `train_raw` or `bus_raw` dict. Train-side logic is identical to the current function (parent-station mapping via `platform_to_parent`). Bus-side logic mirrors `get_bus_stop_sequences` (direct `stop_id` → `bus_stop_lookup`). Returns both `train_selected` (current return value) and `bus_result` (the complete `{(route_short_name, direction_id): [stops]}` dict, fully post-processed to match what `get_bus_stop_sequences` currently returns).

3. **Update `_build_graph()`** (lines ~384–391): before calling the streamer, also call `_load_bus_route_map()`, `_load_bus_stop_lookup()`, and `_load_bus_candidate_trips()` to build the bus candidate sets. Pass them into `_stream_all_stop_sequences`. Store the returned `bus_result` into `_bus_seq_cache`. The `_build_graph` return value is unchanged.

4. **Update `get_bus_stop_sequences()`** (line 738): at the top of the function, check `if _bus_seq_cache is not None: return _bus_seq_cache`. The rest of the existing function body stays as a fallback (handles the unlikely case that `get_bus_stop_sequences` is called before `_build_graph`, e.g. in tests). Remove the `@lru_cache` decorator since the module-level variable now serves that role.

**Risk:** `_build_graph` startup adds `_load_bus_route_map` + `_load_bus_stop_lookup` + `_load_bus_candidate_trips` work before the stream. These are fast in-memory dict builds (no file stream), so the added overhead is negligible. The net change is one fewer 5.8M-row file scan (~7–10 s saved on cold start).

---

## 🟢 Bus routes bypass `_rank_routes` — live wait times not applied to bus options

**File:** [backend/main.py:606-636](backend/main.py#L606)

**What happens:** Train routes from `find_routes()` pass through `_rank_routes()` which adds live arrival wait time to `total_minutes`. Bus routes from `find_bus_routes()` / `find_bus_transfer_routes()` are appended directly to `ranked_routes` without any wait-time enrichment, so the `(total, wait, route)` tuples for buses use whatever shape those functions return. If they return `wait=None`, bus options are systematically under-costed vs. trains and may outrank them unfairly when trains have long waits. Verify the tuple shape from `find_bus_routes` and add a symmetric wait lookup (bus arrivals keyed by `(route, stop_id)`) if missing.

---


## 🟢 `_build_shape_lookup` holds all GTFS shape points in memory simultaneously

**File:** [backend/transit_graph.py:500-518](backend/transit_graph.py#L500)

**What happens:** `raw_pts: defaultdict(list)` accumulates every point from `shapes.txt` before the second pass (trips.txt) decides which shapes are kept. For CTA this is a few MB, acceptable. Would scale poorly for larger agencies.

**Fix (optional):** Two-pass — read trips.txt first to get the set of shape_ids actually used per route/direction, then stream shapes.txt keeping only those. Not worth the complexity at current data size.

---

## 🟢 `_load_transfer_edges` always enforces `_TRANSFER_MINUTES=2.0` floor, even when GTFS says less

**File:** [backend/transit_graph.py:362-368](backend/transit_graph.py#L362)

**What happens:** `max(min_sec / 60.0, _TRANSFER_MINUTES)` clamps any GTFS transfer time below 2 minutes up to 2. If CTA ever publishes a faster same-platform transfer (e.g. 45 sec at a cross-platform xfer), the routing engine will over-estimate it. Intentional pessimistic design, but should be documented or made configurable.
