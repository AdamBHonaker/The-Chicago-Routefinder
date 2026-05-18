# Bugs To Be Fixed

Known issues catalogued for future fixing. Severity: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When a bug in this file is fixed, **delete its entry from this file** and add a corresponding entry to the **Bugs Fixed** section of [`docs/archive/RESOLVED_HISTORY.md`](archive/RESOLVED_HISTORY.md) documenting what was changed and how. This file should only ever contain bugs that have not yet been resolved.

---

## Routing Engine Review 2026-05-11 (1 bug remaining: 1 Medium)

Surfaced by a detailed audit of the intermodal routing engine against its stated goals. BUG-008 and BUG-009 from the same audit were fixed same-day; BUG-045, BUG-046, BUG-047, BUG-048, BUG-049, BUG-050, BUG-051 (Chunk 1 — tagged service-period graph variants), and BUG-053 were resolved later. The item below remains.

---

# BUG-052 · 🟡 Medium — No quantitative accuracy benchmark vs. a known-good source; correctness regressions are undetectable

**Files:** `backend/tests/test_routing_accuracy.py` (scaffold present; all real-route tests `@pytest.mark.skip`), `backend/tests/routing_harness.py` (determinism framework complete), `backend/tests/known_stops.py` (pre-loaded L-station coordinates, added 2026-05-12), `backend/scripts/probe_route.py` (CLI fixture-probing helper, added 2026-05-12)

## What is happening

The determinism harness (`routing_harness.py`) is complete and seven smoke tests pass, but the 10–15 golden-fixture tests that would compare engine output against authoritative Chicago routes are not authored. There is no comparison to OSRM, Valhalla, CTA's own trip planner, or curated GTFS-reference itineraries. Determinism is well covered; correctness against ground truth is not.

**Effect:** We cannot quantitatively answer "is the routing accurate to within X minutes for Y% of queries." Any future regression — a graph-construction change, a transfer-logic refactor, a new mode — could silently degrade routing quality, and the only signal would be a user complaint. BUG-008 was caught by a unit test only after the integration regression test was retrospectively added.

**Reproduction:** Run `pytest backend/tests/test_routing_accuracy.py -v`; observe every meaningful test marked skipped.

## Scaffold improvements (2026-05-12 — BUG-052 still open)

The fixtures still need human authoring with Chicago rider knowledge, but the activation energy to finish them has been lowered:

- `backend/tests/known_stops.py` pre-loads every CTA L parent station as a named `(lat, lon)` constant (e.g. `KNOWN_STOPS["LOGAN_SQUARE_BLUE"]`), pulled from `gtfs_data/stops.txt`. Authors no longer need to copy/paste coordinates per fixture.
- `backend/scripts/probe_route.py` is a read-only CLI that runs one scenario and prints the engine's `primary_modes` / `lines` / `transfers` / `total_minutes` plus all ranked alternatives, so an author can see what the engine actually does for a candidate OD pair before pinning an assertion. Usage: `python -m backend.scripts.probe_route --origin-stop LOGAN_SQUARE_BLUE --dest-stop GARFIELD_RED`.
- The module docstring in `test_routing_accuracy.py` now points at both helpers, adds a "probe before pinning" step to the authoring guide, and warns explicitly against silently encoding the engine's current output as the expected answer.
- `routing_harness.summarize_route()` was fixed (pre-existing bug in the layer-3 harness): it was returning `"transit"` for every transit leg because `TransitLeg` has no `mode` attribute, and `0.0` for `total_minutes` because `Route` exposes the value as `total_minutes_no_wait`. Now classifies legs as `"train"` / `"bus"` via `line_code` against the known CTA train codes and reads `total_minutes_no_wait`. Any assertion authored against `summarize_route`'s output would have been wrong before this fix.

## Fix approach (single chunk)

Author 10–15 Chicago O/D fixtures in `test_routing_accuracy.py` covering: single-line train, train+train transfer, bus→train, train→bus, bus+bus, walk-only, edge-of-service, late-night, weekend service, and out-of-coverage (paired with BUG-047). For each fixture capture:

1. **Route topology** (line sequence and transfer stations) — asserted exactly.
2. **Total time** — asserted within a tolerance band derived from the determinism harness's observed variance (~±2 min for in-coverage routes is reasonable).

Source ground truth from CTA's own trip planner or a manually ride-tested itinerary. Do NOT use Google Maps for transit ground truth — Google often combines suboptimally on CTA. Run as part of CI so regressions block merges.

Acceptance: ≥10 unskipped golden fixtures; each fails loudly if route topology changes; the suite runs in <30 seconds in CI.

---

## Bug Scan — 2026-05-13 (Whole project — coverage gaps)

> Scope: entire project, with focus on files not yet thoroughly covered by today's earlier scans. Previously spot-checked backend files were re-read end-to-end (`transit_graph.py` 2828 lines, `gtfs_loader.py` 893, `cta_client.py` 447, `prompt_builder.py` 453). Previously unscanned backend modules: `hourly.py`, `public_stats.py`, `referrers.py`, `devices.py`, `routes/stats.py`, `fetch_gtfs.py`, `fetch_station_exits.py`, `fetch_street_graph.py`. Scripts: `backend/scripts/` (`_geocode_db.py`, `build_address_points.py`, `build_intersections.py`, `calibrate_detour_factor.py`, `probe_route.py`, `fetch_geolite.py`) and root `scripts/build_schedule_index.py`. Frontend re-scan deferred — the same-day Frontend scan above remains authoritative and no frontend file has changed since.
> ✅ No new bugs found.

Notes on items reviewed and dismissed:
- `transit_graph.clip_shape()` uses squared-degree distance (not haversine miles) for nearest-shape-point lookup at [`backend/transit_graph.py:1626-1627`](../backend/transit_graph.py#L1626-L1627). Lat/lon degrees are not isotropic at Chicago's latitude, but the function's job is shape-snapping along a single CTA route (small lateral extent), and the docstring acknowledges the squared-Euclidean choice. No rider-visible bug.
- `transit_graph._dedup_stations_by_line()` keys off the station's outbound (`G.adj`) transit edges only, and is applied to both origin and destination station lists. A pure dead-end destination terminal could in principle have no outbound edges for its line — but in the CTA graph each direction_id contributes its own edges, so terminals always retain at least one outbound edge from the opposite-direction first stop. No real-world miss.
- `cta_client.init_session()` leaks a previous session if called twice — flagged explicitly in the docstring as "don't call this twice in normal operation"; the FastAPI lifespan path calls it once. Not a latent bug.
- `scripts/build_schedule_index.py` `_normalise_hhmm()` is robust to GTFS 24+ hours via `h % 24`; minute-overflow isn't a real GTFS shape.

---

## Bug Scan — 2026-05-14 (Entire project — modified + untracked since yesterday)

> Scope: entire project, with emphasis on the 23 modified + 4 untracked files that have changed since the four 2026-05-13 scans above. Backend re-read: `active_routes.py`, `config.py`, `crowdedness.py`, `cta_client.py`, `fetch_gtfs.py`, `gtfs_loader.py`, `main.py` (1900 lines), `rate_limit.py`, `route_scoring.py`, `schedule.py`, `walking.py` (811 lines), `weather_service.py`, `public_stats.py`, `routes/stats.py`, `templates/stats.html`, and the `transit_graph.py` diff (OPT-014 transfer-edge cache, OPT-015 numpy shape cache, OPT-005 name fallback rework, OPT-002 midday rep reuse, OPT-004 progressive-ring single query, dedup-stations adj rework). Frontend re-read: `App.jsx` (891 lines), `MapView.jsx` diff (mute-watermark + line-suffix), `useFavorites.js`, `useTripTracker.js`, `useMapMarker.jsx`, `BottomSheet.jsx` (shared settle path), `AlertsFilterBar.jsx` (`FilterPopover` extraction), `RouteCard.jsx`, `LinePill.jsx`, `LanguagePicker.jsx` (SEC-002 SVG parse), `lineColors.js`, `SchedulesPicker.jsx`, `SchedulesView.jsx` (per-minute now-tick fix). Untracked: `AdSlot.jsx`, `ArrivedToast.jsx`, `useAlertsTabFilter.js`, `useCardsColumnWidth.js`.
> ✅ No new bugs found.

Notes on items reviewed and dismissed:
- `App.jsx:514` calls `performSearch(originGeoCoords ?? origin.trim(), ...)`. The geo-coords ref can lag the visible text, but `LocationInput.jsx:167` nulls `originGeoCoords` inside the input's `onChange` handler, so any typed change clears the stale ref before submission. The swap-row at `App.jsx:660` likewise clears it. Stale GPS coords cannot survive into a search.
- `MapView.jsx` mute-watermark effects: two `useEffect`s both depend on `route`. React runs effects in declaration order, so the watermark reset (`mutedWatermarkRef.current = -1`) lands before the muter reads it on the same render. No race.
- `useMapMarker.jsx` `shallowEqualProps` was rewritten to use `for…in` and key-count comparison. `for…in` walks the prototype chain, but for plain prop objects the count parity + value parity still hold (any prototype-pollution-injected key appears in both `a` and `b` with the same value). Behaviourally equivalent to the previous `Object.keys` form.
- `LanguagePicker.jsx` SEC-002 SVG parser extracts only the first `<path>`'s `d`. The bundled continent silhouettes are each authored as a single path, and the comment documents that invariant. Not a latent bug given the current asset shape.
- `SchedulesView.jsx` now ticks `now` once a minute only while `activeBucket === todayBucket`. After midnight, `todayBucket` recomputes but `activeBucket` lags; the past-time greyout is gated on `activeBucket === todayBucket`, so yesterday's bucket viewed after midnight never gets greyed-out incorrectly.
- `transit_graph._shape_np_cache` keyed by `id(list)`: the lists are owned by `_shape_lookup` for the process lifetime, and both caches are rebuilt together inside `_build_shape_lookup()`. No id-recycle risk under the current call graph.
- `walking.py` `_walk_directions_impl` / `_walk_path_impl` now `@lru_cache(maxsize=512)`. Both return tuples and `_walk_directions` / `_walk_path` wrap with `list(...)` before exposing to callers, so the immutable cache invariant is preserved.

---
