# Bugs To Be Fixed

Known issues catalogued for future fixing. Severity: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When a bug in this file is fixed, **delete its entry from this file** and add a corresponding entry to [`BUGS_FIXED_HISTORY.md`](BUGS_FIXED_HISTORY.md) documenting what was changed and how. This file should only ever contain bugs that have not yet been resolved.

---

## 🔴 `_rate_store` and `_response_cache` race condition under concurrent requests

**File:** `backend/main.py`

**What happens:** Both `_rate_store` (dict of deques) and `_response_cache` are mutated without any lock. The `recommend()` async function `await`s between operations, so two concurrent requests can both pass the cache check simultaneously and both attempt to write to `_response_cache`, or both read a stale `_rate_store` before either has written its timestamp. Under moderate concurrency this causes rate limit bypasses and cache corruption.

**Fix:** Protect both structures with a shared `asyncio.Lock()` (not `threading.Lock`).

---

## Bug Scan — 2026-04-18 (`backend/fetch_station_exits.py`, `backend/fetch_gtfs.py`, `backend/fetch_street_graph.py`)

---


### BUG-007 · Transit photos missing from production

- **File**: `frontend/public/transit-photos/` (directory), `frontend/src/App.jsx` (`PHOTOS` array)
- **Severity**: Low

**What happens:** The `frontend/public/transit-photos/` directory contains no image files. The app references photos like `blue-line-ohare.jpg` which return 404 on production, showing broken images in the background photo feature. This is a pre-existing asset gap from Phase 6 setup, not a code bug.

**Fix:** Add ≥10 transit photos to `frontend/public/transit-photos/` and update the `PHOTOS` array in `frontend/src/App.jsx` to match the filenames. Then commit and let Vercel redeploy.

---

## Bug Scan — 2026-04-18 (`frontend/src/`)

> Scanned: `frontend/src/App.jsx`, `frontend/src/MapView.jsx`, `frontend/src/main.jsx`
> Found: 1 bug

---


## Bug Scan — 2026-04-18 (`backend/gtfs_loader.py`)

> Scanned: `backend/gtfs_loader.py`
> Found: 3 bug(s) — all fixed 2026-04-18
