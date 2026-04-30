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

## Bug Scan — 2026-04-28 (backend/ + frontend/)

> Scanned: `backend/main.py`, `backend/cta_client.py`, `backend/crowdedness.py`, `backend/dau.py`, `backend/walking.py`, `backend/weather_service.py`, `backend/gtfs_loader.py`, `backend/route_scoring.py`, `backend/transit_graph.py`, `backend/utils.py`, `frontend/src/App.jsx`, `frontend/src/components/ServiceAlertsBar.jsx`, `frontend/src/MapView.jsx`
> Found: 8 bug(s) · 8 fixed (BUG-008, BUG-008b, BUG-009, BUG-010, BUG-011, BUG-012, BUG-013, BUG-014, BUG-015) — all resolved, see RESOLVED_HISTORY.md

---

## Bug Scan — 2026-04-28 (frontend/src/)

> Scanned: `frontend/src/App.jsx`, `frontend/src/MapView.jsx`, `frontend/src/favorites.js`, `frontend/src/hooks/{useApiQuery,useFavorites,useLocalStorage}.js`, `frontend/src/utils/{fetchWithRetry,tripGeometry}.js`, `frontend/src/components/*.jsx`, `frontend/src/constants.js`, `frontend/src/i18n.js`, `frontend/src/main.jsx`
> Found: 10 bug(s) · 10 fixed (BUG-016, BUG-017, BUG-018, BUG-019, BUG-020, BUG-021, BUG-022, BUG-023, BUG-024, BUG-025) — all resolved, see RESOLVED_HISTORY.md

---

## Bug Scan — 2026-04-30 (frontend/src/)

> Scanned: `frontend/src/App.jsx`, `frontend/src/MapView.jsx`, `frontend/src/constants.js`, `frontend/src/favorites.js`, `frontend/src/i18n.js`, `frontend/src/main.jsx`, `frontend/src/hooks/useApiQuery.js`, `frontend/src/hooks/useFavorites.js`, `frontend/src/hooks/useLocalStorage.js`, `frontend/src/utils/fetchWithRetry.js`, `frontend/src/utils/tripGeometry.js`, `frontend/src/components/ErrorBoundary.jsx`, `frontend/src/components/LabelSavePanel.jsx`, `frontend/src/components/LinePill.jsx`, `frontend/src/components/LoadingSkeleton.jsx`, `frontend/src/components/LocationInput.jsx`, `frontend/src/components/PinnedStopsBoard.jsx`, `frontend/src/components/RouteCard.jsx`, `frontend/src/components/SavedRoutesPanel.jsx`, `frontend/src/components/ServiceAlertsBar.jsx`, `frontend/src/components/SettingsPanel.jsx`, `frontend/src/components/SideRail.jsx`, `frontend/src/components/SignalLamp.jsx`, `frontend/src/components/TransitPhoto.jsx`, `frontend/src/components/WeatherStrip.jsx`, `frontend/src/components/markers/OriginMarker.jsx`, `frontend/src/components/markers/DestinationMarker.jsx`, `frontend/src/components/markers/LivePositionMarker.jsx`
> Found: 3 bug(s) · 3 fixed (BUG-026, BUG-027, BUG-028) — all resolved, see RESOLVED_HISTORY.md

---

## Bug Scan — 2026-04-30 (backend/)

> Scanned: `backend/main.py`, `backend/gtfs_loader.py`, `backend/walking.py`, `backend/transit_graph.py` (partial), `backend/cta_client.py`, `backend/route_scoring.py`, `backend/weather_service.py`, `backend/utils.py`, `backend/crowdedness.py`, `backend/dau.py`
> Found: 2 bug(s) · 2 fixed (BUG-029, BUG-030) — all resolved, see RESOLVED_HISTORY.md

---
