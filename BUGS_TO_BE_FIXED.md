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

## 🟢 `_build_shape_lookup` holds all GTFS shape points in memory simultaneously

**File:** [backend/transit_graph.py:500-518](backend/transit_graph.py#L500)

**What happens:** `raw_pts: defaultdict(list)` accumulates every point from `shapes.txt` before the second pass (trips.txt) decides which shapes are kept. For CTA this is a few MB, acceptable. Would scale poorly for larger agencies.

**Fix (optional):** Two-pass — read trips.txt first to get the set of shape_ids actually used per route/direction, then stream shapes.txt keeping only those. Not worth the complexity at current data size.
