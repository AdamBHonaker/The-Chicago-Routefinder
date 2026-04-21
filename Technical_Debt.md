# Technical Debt

Known technical debt catalogued for future resolution. Priority: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When an item in this file is resolved, **delete its entry from this file** and add a corresponding entry to [`Technical_Debt_Paid_Off.md`](Technical_Debt_Paid_Off.md) documenting what was changed and how. This file should only ever contain debt that has not yet been addressed.

> **Audit date:** 2026-04-20 · Files scanned: entire project (`backend/`, `frontend/`, config files)

---

## TD-009 · Transit photo manifest incomplete — missing photos for 5 hardcoded entries
- **File**: [frontend/src/App.jsx](frontend/src/App.jsx#L18)
- **Line(s)**: 18, 25–29
- **Category**: Missing implementation / TODO-FIXME
- **Priority**: Medium
- **Description**: The `PHOTOS` array contains 5 entries with hardcoded photo paths but no images have been sourced and added to `public/transit-photos/`. A comment explicitly marks this as `HUMAN_TODO`. When any photo fails to load (via `onError`), the placeholder silently hides but users see an empty space instead of a fallback. This is a minor UX issue but blocks the transit photo feature from being production-ready.
- **Suggested Improvement**: Either (1) source the actual photos and commit them to the repo, or (2) remove the PHOTOS array entirely and disable the transit-photo component if photos won't be used. If keeping the feature, add a fallback image or cached web-accessible URL for each photo.

---

## TD-010 · Bus fullness filter is disabled and commented out — waiting on CTA API data
- **File**: [frontend/src/App.jsx](frontend/src/App.jsx#L455-L467)
- **Line(s)**: 455–467
- **Category**: Disabled feature / waiting on external dependency
- **Priority**: Low
- **Description**: The bus fullness filter UI (a `<select>` dropdown for "Empty", "Half-Full", "Full") is entirely commented out with an explanation that CTA Bus Tracker API currently returns empty strings for the `psgld` (passenger load) field. The backend code in `cta_client.py` normalizes and filters on this field, but the frontend has no way to expose the filter until CTA populates it. The dead code takes up ~15 lines and requires a comment to explain why it's disabled.
- **Suggested Improvement**: Delete the commented-out code block entirely. Document the condition ("Bus Tracker psgld field is empty; re-enable when CTA populates it") in a brief comment on line 454 or as a note in a project README. When CTA enables the data, restore the feature from git history or commit history.

---

## TD-011 · No automated test suite — zero coverage
- **Files affected**: Entire codebase
- **Category**: Missing tests for critical paths
- **Priority**: High
- **Description**: The project has no `tests/`, `__tests__/`, `.test.js`, or `.test.py` files anywhere. Zero automated tests exist for:
  - Backend route-finding logic (the core algorithm in `transit_graph.py`)
  - Geocoding and location resolution (`gtfs_loader.py`)
  - API request handling and response formatting (`main.py`)
  - Frontend routing and rendering (`MapView.jsx`, `App.jsx`)
  - Walking time calculation and street-graph fallbacks (`walking.py`)
  
  This is a significant risk: any change to routing, geocoding, or API contract could break silently. New contributors cannot verify their changes don't regress behaviour.
- **Suggested Improvement**: Create a comprehensive test suite covering:
  1. **Backend unit tests** (pytest): Routing functions with known graphs, geocoding cache hits/misses, alert parsing
  2. **Backend integration tests**: End-to-end `/recommend` requests with fixtures
  3. **Frontend unit tests** (Jest/Vitest): Route rendering, leg filtering, language detection
  4. Start with high-risk core logic (find_routes, find_bus_transfer_routes, recommend endpoint)

---

## TD-012 · Magic numbers scattered throughout codebase — should be named constants
- **Files affected**: `backend/transit_graph.py`, `backend/cta_client.py`, `backend/walking.py`, `frontend/src/constants.js`
- **Category**: Hardcoded values that should be configurable
- **Priority**: Medium
- **Description**: Multiple unexplained numbers appear in code:
  - `backend/transit_graph.py`: `_MAX_EXIT_DIST = 0.5`, `_MAX_TRANSFER_WALK = 0.25`, `_FWD_PROGRESS_RATIO = 0.9`, `_MAX_CANDIDATES_PER_ARRIVAL = 3`, `_TRANSFER_SCORE_WALK_FACTOR = 26.0`, `_TRANSFER_WALK_CAP_MIN = 5.0`, `_TRANSFER_RADIUS_MILES = 0.15`, `_DETOUR_FACTOR = 1.3`, `_MAX_LEG_MINUTES = 45.0`
  - `backend/cta_client.py`: `max: 6` (max arrivals per station), timeouts `total=8`
  - `backend/walking.py`: `3.0` mph (walking speed), `201.17`, `100.58`, `150.0` (block length thresholds)
  - `frontend/src/MapView.jsx`: `DEFAULT_ZOOM = 13`
  
  While many are already in named variables (which is good), some are still magic literals. These should all be grouped in a single configuration section so routing behaviour can be tuned without code changes.
- **Suggested Improvement**: Create a `backend/config.py` with all routing parameters (transfer limits, walking speeds, timeouts) as environment variables or class constants. Document each parameter with a comment explaining its purpose and typical range.

---

## TD-013 · Frontend component size growing — App.jsx is 600+ lines
- **File**: [frontend/src/App.jsx](frontend/src/App.jsx#L1)
- **Line(s)**: 1–600+
- **Category**: Overly complex logic / need for modularization
- **Priority**: Medium
- **Description**: `App.jsx` has grown to over 600 lines and contains 7–8 distinct sub-components (`TransitPhoto`, `WalkLegItem`, `RouteLegs`, `RouteCard`, `SettingsPanel`, `LoadingSkeleton`) plus the main `App` component, all in a single file. The main `App` function alone is 200+ lines managing complex state (origin, destination, loading, results, BYOK, i18n, photo fade timers, abort refs). Testing individual features or debugging state is difficult; any change to shared state risks breaking multiple features.
- **Suggested Improvement**: Extract sub-components into separate files:
  1. `components/TransitPhoto.jsx`
  2. `components/RouteCard.jsx` (includes `RouteLegs`, `WalkLegItem`)
  3. `components/SettingsPanel.jsx`
  4. `components/LoadingSkeleton.jsx`
  5. Reorganize `App.jsx` to focus on layout and top-level state management only.

---

## TD-014 · Inconsistent error handling in frontend fetch — no retry logic
- **File**: [frontend/src/App.jsx](frontend/src/App.jsx#L445)
- **Line(s)**: 445–475
- **Category**: Missing resilience / error handling
- **Priority**: Low
- **Description**: The `/recommend` endpoint fetch in `handleSubmit()` has a single try/catch that catches all errors (network, JSON parse, HTTP 5xx) and displays them as a plain string to the user. No retry logic, no exponential backoff, no distinction between retryable (5xx, timeout) and non-retryable errors (400, malformed request). If Railway or the backend is momentarily unavailable, the user must manually re-submit.
- **Suggested Improvement**: Implement exponential backoff retry (e.g., max 3 attempts with 1s, 2s, 4s delays) for HTTP 5xx and network errors. Log attempts to console for debugging. Display "Network error — retrying..." to the user during retries.

---

## TD-015 · Geocoding cache not garbage-collected — journal can grow unbounded
- **File**: [backend/gtfs_loader.py](backend/gtfs_loader.py#L155-L180)
- **Line(s)**: 155–180
- **Category**: Missing maintenance / memory leak potential
- **Priority**: Low
- **Description**: The geocode cache uses an append-only journal (`geocode_cache.journal`) that is periodically compacted into a snapshot. However, the compaction strategy is time-based and entry-count-based: `_GEOCODE_COMPACT_THRESHOLD = 500` (compact after 500 new entries OR 1 hour). If the server handles fewer than 500 geocoding requests per hour, the journal can accumulate stale entries indefinitely without ever triggering compaction. Over months, the journal could grow to 10k+ lines with old/redundant entries, slowing startup.
- **Suggested Improvement**: Implement two additional cleanup strategies:
  1. Age-based eviction: Remove geocode entries older than N days (e.g., 90 days) since they're less likely to be queried again.
  2. Add a manual maintenance endpoint (or background job) that trims the cache on a fixed schedule (e.g., weekly), not just when thresholds are hit.
