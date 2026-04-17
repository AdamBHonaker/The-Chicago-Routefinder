# Bugs To Be Fixed

Known issues catalogued for future fixing. Severity: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When a bug in this file is fixed, **delete its entry from this file** and add a corresponding entry to [`BUGS_FIXED_HISTORY.md`](BUGS_FIXED_HISTORY.md) documenting what was changed and how. This file should only ever contain bugs that have not yet been resolved.

---

## 🔴 `_rate_store` and `_response_cache` race condition under concurrent requests

**File:** `backend/main.py`

**What happens:** Both `_rate_store` (dict of deques) and `_response_cache` are mutated without any lock. The `recommend()` async function `await`s between operations, so two concurrent requests can both pass the cache check simultaneously and both attempt to write to `_response_cache`, or both read a stale `_rate_store` before either has written its timestamp. Under moderate concurrency this causes rate limit bypasses and cache corruption.

**Fix:** Protect both structures with a shared `asyncio.Lock()` (not `threading.Lock`).

---

## 🔴 `_ABBR_MAP` contains duplicate keys — last value silently wins

**File:** `backend/gtfs_loader.py`

**What happens:** `_ABBR_MAP` defines `"blvd"` four times and `"pkwy"` twice. Python dicts silently keep the last assignment. Values happen to be identical now, but a future typo in a duplicate key will cause the wrong expansion with no error.

**Fix:** Remove all duplicate keys from `_ABBR_MAP` so each suffix appears exactly once.

---

## 🟡 `_coords_for_location()` passes raw `query` to `geocode_google()` — cache miss, double API call

**File:** `backend/main.py`

**What happens:** `resolve_location()` in `gtfs_loader.py` correctly calls `geocode_google(q)` (normalized/lowercased). `_coords_for_location()` in `main.py` still calls `geocode_google(query)` with the raw string. The cache key differs (e.g. `"450 W Belmont Ave"` vs. `"450 w belmont avenue"`), causing a cache miss and a second redundant Google API call on every lookup from `_coords_for_location`.

**Fix:** Add `q = query.lower().strip(); q = _normalize_street_abbr(q)` at the top of `_coords_for_location()` and pass `q` to `geocode_google()`.

---

## 🟡 `clip_shape()` returns shape points in wrong order for reverse-direction trips

**File:** `backend/transit_graph.py`

**What happens:** `clip_shape()` always returns `shape_points[lo:hi+1]` where `lo = min(board_idx, exit_idx)` and `hi = max(board_idx, exit_idx)`. If the GTFS shape runs north-to-south but the rider travels south-to-north, the slice is geometrically correct but ordered backward. The animated direction of travel on the map appears reversed.

**Fix:** After computing `board_idx` and `exit_idx`, check whether `board_idx > exit_idx` and if so return the slice reversed: `shape_points[lo:hi+1][::-1]`.

---

## 🟡 Bus transfer scoring uses haversine × 20 instead of actual walk minutes — incorrect candidate ranking

**File:** `backend/transit_graph.py` — `find_bus_transfer_routes()`

**What happens:** The candidate scoring formula multiplies haversine distance by `20.0` to approximate minutes. `street_walk_minutes()` (OSMnx) is used for actual walk times elsewhere and typically yields higher times through a real street grid. A 0.3-mile haversine leg scores as 6 minutes but the OSMnx walk may be 9+ minutes, causing incorrect candidate ranking — a stop that looks short straight-line may be selected over a better one.

**Fix:** Use `street_walk_minutes()` for the transfer leg in the scoring formula, or apply a grid correction factor (e.g., multiply haversine × 1.3–1.4 to approximate Manhattan distance).

---

## 🟡 `_format_routes()` labels bus wait as "next train" in Claude prompt

**File:** `backend/main.py`

**What happens:** When formatting bus routes for the Claude prompt, the wait-time note says `"next train Due"` or `"next train in N min"` regardless of whether the route is a bus or train. Claude may then refer to boarding a train when advising on a bus route.

**Fix:** In `_format_routes()`, detect whether the first transit leg is a bus or train (e.g., check if `line_code` is in `LINE_NAMES`) and use `"next bus"` vs. `"next train"` accordingly.

---

## 🟢 Transit photos missing — broken images on production

**Files:** `frontend/public/transit-photos/`; `frontend/src/App.jsx` (PHOTOS array)

**What happens:** The `frontend/public/transit-photos/` directory contains no image files. The app references photos like `blue-line-ohare.jpg` which return 404 on production, showing broken images in the background photo feature. This is a pre-existing blocking item from Phase 6 setup, not a code bug.

**Fix:** Add ≥10 transit photos to `frontend/public/transit-photos/` and update the `PHOTOS` array in `frontend/src/App.jsx` to match the filenames. Then commit and let Vercel redeploy.

---

## 🟢 BYOK key stored in browser with no user warning

**File:** `frontend/src/App.jsx`

**What happens:** The Anthropic API key is stored in plaintext in `sessionStorage` (moved from `localStorage` in the 2026-04-15 fix — clears on tab close). The key is still exposed to any XSS vulnerability or malicious browser extension on the Vercel domain — a key with direct billing implications. No in-app warning tells the user about this risk.

**Fix:** Add a visible warning in the BYOK settings panel: *"Your key is stored in this browser. Only use this feature on trusted personal devices."*

---

## 🟢 `styleError` in `MapView.jsx` clears on any tile load, not specifically on style recovery

**File:** `frontend/src/MapView.jsx`

**What happens:** The `map.on("data", ...)` handler calls `setStyleError(false)` whenever `e.isSourceLoaded` is true. A successful tile load from *any* source clears the error banner, even if the map style itself is still broken and rendering incorrectly.

**Fix:** Gate the error-clear on `e.dataType === "style"` in addition to `e.isSourceLoaded`, so only a successful style load dismisses the banner.

---

## 🟢 `geocode_google()` double-appends `, Chicago, IL` if already present in query

**File:** `backend/gtfs_loader.py`

**What happens:** `geocode_google()` unconditionally appends `", Chicago, IL"` to every query. If the user types `"Wrigley Field, Chicago, IL"`, the Google API receives `"Wrigley Field, Chicago, IL, Chicago, IL"`. Google is usually forgiving, but this can occasionally bias results or return the wrong location.

**Fix:** Before appending, check `if "chicago" not in query.lower(): query += ", Chicago, IL"`.

---

## 🟢 `_build_shape_lookup` holds all GTFS shape points in memory simultaneously

**File:** [backend/transit_graph.py:500-518](backend/transit_graph.py#L500)

**What happens:** `raw_pts: defaultdict(list)` accumulates every point from `shapes.txt` before the second pass (trips.txt) decides which shapes are kept. For CTA this is a few MB, acceptable. Would scale poorly for larger agencies.

**Fix (optional):** Two-pass — read trips.txt first to get the set of shape_ids actually used per route/direction, then stream shapes.txt keeping only those. Not worth the complexity at current data size.

---

## 🟢 `_load_transfer_edges` always enforces `_TRANSFER_MINUTES=2.0` floor, even when GTFS says less

**File:** [backend/transit_graph.py:362-368](backend/transit_graph.py#L362)

**What happens:** `max(min_sec / 60.0, _TRANSFER_MINUTES)` clamps any GTFS transfer time below 2 minutes up to 2. If CTA ever publishes a faster same-platform transfer (e.g. 45 sec at a cross-platform xfer), the routing engine will over-estimate it. Intentional pessimistic design, but should be documented or made configurable.
