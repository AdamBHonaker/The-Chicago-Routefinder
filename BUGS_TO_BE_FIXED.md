# Bugs To Be Fixed

Known issues catalogued for future fixing. Severity: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When a bug in this file is fixed, **delete its entry from this file** and add a corresponding entry to [`BUGS_FIXED_HISTORY.md`](BUGS_FIXED_HISTORY.md) documenting what was changed and how. This file should only ever contain bugs that have not yet been resolved.

---

## 🟢 `_fetch_station_arrivals` and `_fetch_bus_chunk` catch all exceptions and return empty

**Files:** `backend/cta_client.py` lines 59–60, 167–169

**What happens:** Broad `except Exception` silently drops aiohttp timeouts, JSON decode errors, and API-level errors. The station-level handler does return an `error` dict in the train case (and logs it), but the bus chunk handler only prints and returns `[]`. There is no aggregate counter surfaced back to the user — if all bus requests fail, the user sees "no bus arrivals" with no indication that the API itself is down vs. there being no buses.

**Full scope:**

*Chunk A — Backend (`backend/cta_client.py` + `backend/main.py`):*
- `_fetch_bus_chunk` (line 168): on `except Exception`, instead of returning `[]`, return a sentinel list `[{"_bus_error": True, "exc": str(exc)}]`. This preserves the current `list[dict]` return type so callers don't change shape.
- `get_bus_arrivals` (lines 229–237): after `asyncio.gather`, scan results for `_bus_error` sentinels. Count them, strip them from `all_arrivals`, and return `(arrivals, n_errors)` — a `tuple[list[dict], int]`.
- `get_train_arrivals` (lines 119–139): already filters `error` dicts internally; change the return to `(sorted_good, len(errors))` — same `tuple[list[dict], int]` pattern for consistency.
- `main.py` (lines 420–430): unpack both calls: `train_arrivals, n_train_errors = await get_train_arrivals(...)` and `bus_arrivals, n_bus_errors = await get_bus_arrivals(...)`. Add `"bus_errors": n_bus_errors` and `"train_errors": n_train_errors` to the response dict (lines 525–533).

*Chunk B — Frontend (`frontend/src/App.jsx`):*
- After a successful fetch, read `data.bus_errors` and `data.train_errors` from the response.
- If `bus_errors > 0` and `bus_arrivals` is empty (or missing), render a small warning below the recommendation text: `"Bus arrival data partially unavailable — some results may be missing."` Use the same styling as the existing error/empty-state messages. No change needed when arrivals are present despite errors (partial data is still useful).

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
