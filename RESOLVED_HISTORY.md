# Resolved History

A combined log of all bugs fixed, technical debt paid off, and efficiency improvements implemented. Entries are moved here from the three active tracking files when resolved.

| Active File | Section in This File |
|---|---|
| `BUGS_TO_BE_FIXED.md` | [Bugs Fixed](#bugs-fixed) |
| `Technical_Debt.md` | [Technical Debt Paid Off](#technical-debt-paid-off) |
| `Efficiency_Improvements.md` | [Efficiency Improvements Implemented](#efficiency-improvements-implemented) |

Severity / Priority / Impact: 🔴 High · 🟡 Medium · 🟢 Low.

---

# Bugs Fixed

---

# 2026-04-28 BUG-016 · Pinned-stop type collision in favorites — FIXED

## 🟡 Bus stop_ids and train mapids dedupe by id only, silently rejecting the second pin — FIXED

**File:** `frontend/src/favorites.js` (`pinStop`), `frontend/src/hooks/useFavorites.js` (`handlePinToggle`)

**What was happening:** `pinStop` rejected duplicates with `current.some((s) => s.stop_id === stop_id)`, ignoring `type`. CTA bus stop IDs and train mapids share no namespace, so a numeric collision was plausible — pinning a train station whose mapid matched an already-pinned bus stop's stop_id silently no-opped. `handlePinToggle.find((s) => s.stop_id === stopId)` had the symmetric flaw on the unpin path: it could return a wrong-type stop and unpin it.

**Fixed by:** Match on both `type` and `stop_id` everywhere pinned stops are looked up. Updated `pinStop` to use `s.type === type && s.stop_id === stop_id` and `handlePinToggle` likewise.

---

# 2026-04-28 BUG-017 · Render-time crash when `/alerts` returns alert without `routes` — FIXED

## 🔴 `flatMap((a) => a.routes)` threw `TypeError`, dropping the whole app into the ErrorBoundary — FIXED

**File:** `frontend/src/App.jsx` (`activeAlertRoutes` useMemo), `frontend/src/components/ServiceAlertsBar.jsx`

**What was happening:** `serviceAlerts.flatMap((a) => a.routes).map((r) => r.replace(" Line", ""))` returned `[undefined]` if any alert lacked a `routes` array, then `.replace` on undefined threw and crashed render. `ServiceAlertsBar` had the same problem with `alert.routes.length > 0`.

**Fixed by:** Defensive defaults — `(a.routes ?? [])` in the App.jsx flatMap and `(alert.routes?.length ?? 0) > 0` in ServiceAlertsBar.

---

# 2026-04-28 BUG-018 · Pinned-stop arrivals lookup keyed inconsistently with backend — FIXED

## 🟡 Frontend looked up arrivals by `stop_id` while backend keyed responses by `stop_id`; bus/train collision could cross-contaminate the same key — FIXED

**File:** `backend/main.py` (`/stop-arrivals` response shape), `backend/tests/test_endpoints.py`, `frontend/src/components/PinnedStopsBoard.jsx`

**What was happening:** The backend keyed each entry of `arrivals` by raw `stop_id` (train `mapid` or bus `stop_id`). Two pinned stops with the same numeric id but different types would have their arrivals merged under the same dict entry, and the frontend would render whichever stop's arrivals it picked.

**Fixed by:** Switched the `/stop-arrivals` response to typed keys (`"train:40900"`, `"bus:1234"`) and updated `PinnedStopsBoard` to read `arrivals[`${stop.type}:${stop.stop_id}`]`. Updated the integration test to assert on the new key. Docstring on the endpoint updated to reflect the typed key shape.

---

# 2026-04-28 BUG-019 · RouteCard pinned indicator used untyped stop_id — FIXED

## 🟢 Train mapids could match unrelated bus stop_ids in `pinnedIds` Set, falsely toggling the pin badge — FIXED

**File:** `frontend/src/components/RouteCard.jsx`

**What was happening:** `pinnedIds = new Set(pinnedStops.map(s => s.stop_id))` followed by `pinnedIds.has(leg.from_mapid)` ignored `type`, so a train leg could test as pinned when only a same-id bus stop was actually pinned (or vice versa).

**Fixed by:** Key the Set by `${s.type}:${s.stop_id}` and look up via `${stopType}:${stopId}`, matching the typed-key model used elsewhere after BUG-016/018.

---

# 2026-04-28 BUG-020 · BYOK idle-clear ignored touch input — FIXED

## 🟢 30-minute idle timer wiped the API key mid-session for touch-only users — FIXED

**File:** `frontend/src/App.jsx` (BYOK idle-clear effect)

**What was happening:** The idle-reset listener only handled `mousemove` and `keydown`. On a phone or PWA tap-only session, neither event fires, so the key was wiped after 30 min despite the user actively interacting with the app.

**Fixed by:** Added `pointerdown` and `touchstart` listeners (plus the existing mouse/keyboard ones) and registered them with `{ passive: true }` to avoid scroll-jank. Cleanup symmetric.

---

# 2026-04-28 BUG-021 · WeatherStrip rendered "NaN°" when temperature was missing — FIXED

## 🟢 Math.round on undefined produced NaN in the hero temp display — FIXED

**File:** `frontend/src/components/WeatherStrip.jsx`

**What was happening:** `Math.round(temperature_f)` returned `NaN` for partial weather payloads (forecast/alerts present, temperature absent), surfacing "NaN°" to the user.

**Fixed by:** Guard the temp span with `Number.isFinite(temperature_f)`; the rest of the strip still renders so users get the forecast and any alert text.

---

# 2026-04-28 BUG-022 · Walk-step completion silently failed when `start_lon` was missing — FIXED

## 🟢 `haversineMeters` got `lng: undefined`, returned NaN, comparison never tripped — FIXED

**File:** `frontend/src/App.jsx` (`processTripPosition`)

**What was happening:** Step-completion guard checked `step.start_lat !== undefined` but read `step.start_lon` unguarded. A backend payload with lat but no lon would compute NaN distance forever — the step never got marked complete.

**Fixed by:** Tightened the guard to require both `start_lat` and `start_lon` to be defined before the haversine call.

---

# 2026-04-28 BUG-023 · SettingsPanel input showed stale BYOK key after idle-clear — FIXED

## 🟢 `useState(apiKey)` snapshotted only on mount; an idle-clear left the old key visible and re-saveable — FIXED

**File:** `frontend/src/components/SettingsPanel.jsx`

**What was happening:** When the BYOK idle timer cleared `byokKey` while the settings sheet was open, the local `draft` state still held the old value. The user could click Save and reinstall the cleared key.

**Fixed by:** Added `useEffect(() => setDraft(apiKey), [apiKey])` so external clears propagate to the input immediately.

---

# 2026-04-28 BUG-024 · LinePill could TypeError on undefined line — FIXED

## 🟢 Optional chain only covered `replace`; `.slice` on undefined threw — FIXED

**File:** `frontend/src/components/LinePill.jsx`

**What was happening:** `LINE_ABBREVS[line] ?? line?.replace(" Line", "").slice(0, 2).toUpperCase()` — when `line` was undefined and not in `LINE_ABBREVS`, the optional chain yielded `undefined` and the unguarded `.slice(0, 2)` threw. Latent crash; rare in practice but a real foot-gun.

**Fixed by:** `(line ?? "").replace(" Line", "").slice(0, 2).toUpperCase()` — empty-string fallback so the chain stays safe.

---

# 2026-04-28 BUG-025 · Unhandled promise rejection from `/ping` mount fetch — FIXED

## 🟢 Network failure produced an unhandled rejection visible to error trackers — FIXED

**File:** `frontend/src/App.jsx`

**What was happening:** The DAU-counting ping was documented as "silent on failure" but the code had no `.catch`. Offline users surfaced an unhandled rejection in DevTools and to Sentry-style trackers.

**Fixed by:** Added `.catch(() => {})` so the rejection is actually swallowed.

---

# 2026-04-28 BUG-009 · Crowdedness stop-position factor was always 1.0 — FIXED

## 🟢 Bell-curve stop-position adjustment re-enabled for all transit legs — FIXED

**File:** `backend/transit_graph.py` (new cache + lookup function), `backend/main.py` lines 1203–1215

**What was happening:** `_crowdedness_for_routes()` called `estimate_crowdedness()` with hardcoded `stop_sequence_position=1, total_stops=2` for every leg. The bell-curve formula `0.6 + 0.4 * sin(position/total * π)` always evaluated to `sin(π/2) = 1.0`, so the position factor was permanently maxed out and the lighter-crowding-at-terminals / heavier-in-the-middle adjustment was dead code for every route displayed to users.

**Fixed by:**
1. Added module-level `_train_stop_pos: dict[tuple[str, str, str], tuple[int, int]]` to `transit_graph.py`, keyed by `(parent_mapid, route_id, direction_id)` → `(position_0based, total_stops)`.
2. Populated `_train_stop_pos` in `_build_graph()` by iterating the already-built `stop_seqs` dict — zero extra I/O, runs once at startup.
3. Added public `get_stop_sequence_position(stop_id, route_id) -> (position, total)` that resolves train stops via `_train_stop_pos` and bus stops via the existing `_stop_to_routes` / `_bus_seq_cache` indexes. Falls back to `(1, 2)` (the previous no-op value) for unknown stops.
4. Updated `_crowdedness_for_routes()` in `main.py` to call `get_stop_sequence_position` and pass the real position to `estimate_crowdedness()`. Terminal stops now correctly receive a lower crowdedness factor (~0.6×) and mid-route stops receive the full 1.0× factor.

---

# 2026-04-28 BUG-008b · `get_counts()` returned stale DAU data by reading from disk — FIXED

## 🟡 In-flight unique visitors omitted from `/admin/dau` response until next batch flush — FIXED

**File:** `backend/dau.py` lines 142–144

**What was happening:** `get_counts()` called `_load()`, which reads `dau.json` from disk. Because `record_visit()` batch-writes to disk only every 20 unique visitors or 30 seconds (whichever comes first), any visits accumulated since the last flush were invisible to `/admin/dau`. The in-memory `_counts_cache` dict and today's in-flight count (`_base_count + len(_seen_hashes)`) are authoritative; the disk file is a lagging snapshot.

**Fixed by:** Rewrote `get_counts()` to acquire `_lock` and return a snapshot of `_counts_cache`. When `_current_day` matches today's Chicago date, today's entry is explicitly overridden with `_base_count + len(_seen_hashes)` to capture all in-flight visits. This eliminates the disk read entirely and prevents a data race between the read and any concurrent `record_visit()` call.

---

# 2026-04-28 BUG-008 · `is_major` threshold was 7 instead of 70 in route alerts — FIXED

## 🔴 Off-by-10× severity threshold caused nearly all alerts to be flagged as major — FIXED

**File:** `backend/cta_client.py` line 330

**What was happening:** `_fetch_alerts_for_route` marked an alert as `is_major` when `severity >= 7`. The CTA `SeverityScore` field runs 0–100, so with a threshold of 7, virtually every non-trivial alert (including routine planned work) was labelled major and prefixed with `"⚠ MAJOR —"` in the Claude prompt, degrading recommendation quality.

**Fixed by:** Changed `"is_major": severity >= 7` to `"is_major": severity >= 70`, matching the threshold used by the `/alerts` public endpoint.

---

# 2026-04-28 BUG-009 · `significant_alerts` filter threshold was 5, far too low for a 0–100 score scale — FIXED

## 🟡 Routine elevator alerts injected into Claude prompt as significant — FIXED

**File:** `backend/main.py` line 1364

**What was happening:** `significant_alerts = [a for a in (alerts or []) if a.get("severity_score", 0) >= 5]` included almost every alert in the Claude recommendation prompt. Combined with BUG-008, this flooded the prompt with routine/planned-work alerts.

**Fixed by:** Raised the threshold to 40 (`severity_score >= 40`), matching the "Minor" floor used by the `/alerts` public endpoint.

---

# 2026-04-28 BUG-010 · Empty NWS grid URLs cached for 24 hours, causing sustained weather failures — FIXED

## 🟡 Transient NWS empty-URL response permanently disabled weather for a coordinate for 24 h — FIXED

**File:** `backend/weather_service.py` lines 134–138

**What was happening:** `_get_grid_urls` cached a `("", "")` tuple when NWS returned a 200 OK with missing `forecast`/`forecastHourly` fields. All subsequent weather requests for that rounded lat/lon attempted to fetch an empty URL, raising an exception that `_safe_weather` silently swallowed, disabling weather for the entire 24-hour cache window.

**Fixed by:** Added a guard before caching: `if not urls[0] or not urls[1]: raise ValueError("NWS returned empty forecast URLs")`. The exception propagates up to `_safe_weather` which catches it; the cache is never written, so the next request retries the `/points` fetch.

---

# 2026-04-28 BUG-011 · BYOK Pydantic validator raised HTTP 422 even when BYOK is disabled — FIXED

## 🟡 Format validation fired before BYOK_ENABLED guard, incorrectly rejecting requests — FIXED

**File:** `backend/main.py` lines 315–326, 629–640

**What was happening:** The `validate_anthropic_key` field validator raised `ValueError` (→ HTTP 422) if `anthropic_api_key` did not start with `"sk-ant-"`, regardless of whether `BYOK_ENABLED` was true. Clients sending any non-`sk-ant-` string received a hard validation error even when the server was ignoring the field entirely.

**Fixed by:** Removed the `sk-ant-` prefix check from the Pydantic validator (which now only strips/nullifies the value). Moved the prefix check into `_validate_api_keys()` under the `if byok_key` branch — it only runs when BYOK is enabled and the user actually supplied a key.

---

# 2026-04-28 BUG-012 · ServiceAlertsBar crashed when `alert.severity` was missing or null — FIXED

## 🔴 `TypeError` on `null.toLowerCase()` crashed the entire alerts bar — FIXED

**File:** `frontend/src/components/ServiceAlertsBar.jsx` lines 34–35

**What was happening:** `alert.severity.toLowerCase()` was called and `alert.severity` was interpolated into CSS class names without a null guard. A missing or `null` severity field from the backend threw a `TypeError` that crashed the component with no error boundary.

**Fixed by:** Added a nullish-coalescing fallback on both lines: `(alert.severity ?? "unknown").toLowerCase()`.

---

# 2026-04-28 BUG-013 · Train alert `⚠` badges never appeared — `pillLabel` vs. backend route name mismatch — FIXED

## 🟡 `activeAlertRoutes` held `"Red Line"`; `pillLabel` was `"Red"` — `Set.has()` always returned false — FIXED

**File:** `frontend/src/App.jsx` lines 508–514

**What was happening:** `activeAlertRoutes` was built from `serviceAlerts.flatMap(a => a.routes)`, which produces full CTA names like `"Red Line"`. `RouteCard` compared against `pillLabel` (`leg.line?.replace(" Line", "")` = `"Red"`), so `activeAlertRoutes.has("Red")` never matched `"Red Line"` and the `⚠` badge was silently suppressed for every train leg.

**Fixed by:** Added `.map((r) => r.replace(" Line", ""))` when building `activeAlertRoutes` in `App.jsx`, so the Set contains abbreviated names (`"Red"`, `"Blue"`) that match `pillLabel`. Bus routes are unaffected as they don't contain `" Line"`.

---

# 2026-04-28 BUG-014 · User-position dot silently lost if map style loads after trip starts — FIXED

## 🟡 Early `return` when style unloaded left GPS dot permanently missing — FIXED

**File:** `frontend/src/MapView.jsx` lines 383–417

**What was happening:** The user-position `useEffect` began with `if (!map || !map.isStyleLoaded()) return;` with no deferred listener. If `tripActive` and `userPosition` were set before the MapLibre style finished loading (slow connection), the effect returned early and never added the blue GPS dot.

**Fixed by:** Extracted the rendering logic into a `render()` function. When `!map.isStyleLoaded()`, it now defers with `map.once("load", render)` and returns `() => map.off("load", render)` as cleanup, mirroring the pattern already used by the route-rendering effect.

---

# 2026-04-28 BUG-015 · Service alerts fetch not aborted on component unmount — FIXED

## 🟢 Missing AbortController caused stale state update in React 18 StrictMode — FIXED

**File:** `frontend/src/App.jsx` lines 521–526

**What was happening:** The `useEffect` fetching `/alerts` on mount had no AbortController. In React 18 StrictMode (dev), effects are double-invoked; the first mount's in-flight fetch completed after cleanup and called `setServiceAlerts` on an already-unmounted instance, producing a dev-mode warning.

**Fixed by:** Added `const ctrl = new AbortController()`, passed `{ signal: ctrl.signal }` to `fetch`, and returned `() => ctrl.abort()` as the cleanup function.

---

# 2026-04-28 BUG-011b · Last-departure tracking compared arrival time but stored departure string — FIXED

## 🟢 `last_dep` accumulator used `arr_min` for comparison, so latest arrival ≠ latest departure — FIXED

**File:** `backend/transit_graph.py` lines 376–382 (`_stream_all_stop_sequences`)

**What was happening:** The `last_dep` dict tracks the final scheduled departure per `(parent_mapid, direction_id)` to power the "last train" countdown. The accumulator compared `arr_min` (arrival minutes) to find the "latest" row, but stored `dep_str` (the departure time string). For intermediate stops, departure is always ≥ arrival, so the row with the largest `arr_min` is not necessarily the row with the largest `dep_min`. On lines with close last-run spacing (Yellow Line, Purple Express), a trip with a slightly higher arrival time could displace the trip with the true latest departure, making the last-train countdown off by a few minutes.

**Fixed by:** Parsed `dep_str` into `dep_min` via `_parse_gtfs_time(dep_str)` and changed the accumulator comparison to `dep_min > prev[0]`, storing `(dep_min, dep_str)`. The comparison and stored key now refer to the same quantity (departure time).

---

# 2026-04-28 BUG-016 · `useApiQuery` spreads caller `deps` into effect dep array — length must be constant — FIXED

## 🟢 Fragile hook contract — undocumented fixed-length requirement on `deps` argument — FIXED

**File:** `frontend/src/hooks/useApiQuery.js` line 17–18 (JSDoc)

**What was happening:** `}, [enabled, tick, ...deps])` spread the caller-supplied array directly into the `useEffect` dependency list. React's rules of hooks require constant dependency-array length. The contract was implicit and undocumented, risking stale or spurious re-fetches if any caller passed a variable-length `deps` array.

**Fixed by:** Added an explicit warning to the JSDoc `@param {Array} deps` description: the array is spread into a `useEffect` dep list so its length must be constant across renders. Callers needing a variable-length dependency should pass a single stable derived key instead.

---

# 2026-04-27 BUG-024 · Direct bus routes ranked with zero wait time — buses always float to top — FIXED

## 🔴 `_build_arrival_lookup` ingested only train arrivals; bus routes from `find_routes()` got `wait = None` — FIXED

**File:** `backend/main.py` — `_build_arrival_lookup()` (line 371) and `_run_routing()` (line 814)

**What was happening:** `_build_arrival_lookup()` accepted only `train_arrivals` and built a lookup keyed by `(line_code, station_mapid)`. When `_rank_routes()` processed a direct bus route from `find_routes()`, it looked up the first-leg wait using `(bus_route_number, bus_stop_id)` — a key that never existed in the train-only lookup. `dest_map` was always empty, `wait` was always `None`, and no wait time was added to the route total. Bus routes appeared 5–15 minutes faster than they actually were and consistently ranked above trains.

**Fixed by:**
1. **`_build_arrival_lookup()`** — Added optional `bus_arrivals: list[dict] | None` and `bus_stop_walk_map: dict[str, float] | None` parameters. Bus arrivals are now keyed by `(route, stop_id)`, matching the `(line_code, from_mapid)` structure that `_rank_routes` uses for bus `TransitLeg`s. Uncatchable buses (arriving before the user can walk to the stop) are filtered out the same way train arrivals are.
2. **`_run_routing()`** — Added `bus_stop_walk_map = {s["stop_id"]: s["walk_minutes"] for s in origin_bus_stops}` and passes both `bus_arrivals` and `bus_stop_walk_map` into `_build_arrival_lookup`. `origin_bus_stops` already carries per-stop walk times from GTFS so no new data fetch is needed.

The second call to `_build_arrival_lookup` in `_fetch_transfer_arrivals()` (for annotating transfer legs) is intentionally unchanged — that call is train-only and bus transfer wait annotation is handled separately by `_build_bus_transfer_lookup`.

---

# 2026-04-27 BUG-015 · Geolocation permission errors auto-dismiss with no UI path to re-enable — FIXED

## 🟡 Persistent denied banner + trip-start error surfacing — FIXED

**Files:** `frontend/src/App.jsx`, `frontend/src/components/RouteCard.jsx`, `frontend/src/App.css`, all 22 locale files

**What was happening:** When the browser denied geolocation, `handleGeoClick()` set `geoState` to `"denied"` then auto-reset it to `"idle"` after 4 seconds via `setTimeout`. No actionable message was shown explaining how to re-enable location. In `startTrip()`, the `watchPosition` error callback silently called `console.error()` on PERMISSION_DENIED with no user-visible feedback.

**Fixed by:**
1. **`handleGeoClick` in `LocationInput`** — removed the auto-dismiss timer for the `"denied"` case only (transient `"error"` still auto-dismisses). The button now stays in error state until the user acts.
2. **Persistent geo-denied banner** — added a `role="alert"` `<div className="geo-denied-banner">` rendered when `geoState === "denied"`. Shows `t("geo_denied_help")` ("Enable location in your browser settings, then refresh.") with an × dismiss button that calls `setGeoState("idle")`.
3. **`startTrip()` error surfacing** — added `tripGeoError` state in App.jsx. On PERMISSION_DENIED in `watchPosition`, `setTripGeoError(true)` is called and `stopTrip()` halts tracking. `stopTrip()` resets `tripGeoError` to `false`.
4. **RouteCard trip error message** — `tripGeoError` and `onDismissTripGeoError` props added to `RouteCard`. When `tripGeoError` is true, a `role="alert"` `.trip-geo-error` div renders `t("geo_trip_denied")` with an × dismiss button.
5. **CSS** — added `.geo-denied-banner` and `.trip-geo-error` styles (dark red background, border, `fca5a5` text, flex layout with dismiss button).
6. **i18n** — added `geo_denied_help` and `geo_trip_denied` keys to all 22 locale files (en, es, fr, it, pl, ro, uk, ru, zh, yue, ja, ko, tl, vi, hi, gu, pa, ne, ur, ar, ps, yo).

---

# 2026-04-27 BUG-008 · Naive `datetime.utcnow()` in `WeatherContext` — FIXED

## 🟡 `fetched_at` now uses timezone-aware Chicago local time via `zoneinfo` — FIXED

**File:** `backend/weather_service.py` — line 290

**What was happening:** `datetime.utcnow()` returns a timezone-naive datetime object. This is deprecated since Python 3.12 (emits `DeprecationWarning` on every weather fetch) and raises a `TypeError` if `fetched_at` is ever compared or serialized alongside a timezone-aware datetime. Additionally, the timestamp did not reflect Chicago local time.

**Fixed in:** Added `from zoneinfo import ZoneInfo` import and replaced `datetime.utcnow()` with `datetime.now(ZoneInfo("America/Chicago"))`. The result is a timezone-aware datetime in Chicago local time (handles CDT/CST automatically), eliminating the deprecation warning and any mixed-awareness comparison errors.

```python
# BEFORE (naive UTC, deprecated):
from datetime import datetime
fetched_at=datetime.utcnow()

# AFTER (timezone-aware Chicago time):
from datetime import datetime
from zoneinfo import ZoneInfo
fetched_at=datetime.now(ZoneInfo("America/Chicago"))
```

---

# 2026-04-27 BUG-016 · Missing `leg.from_coords`/`leg.to_coords` silently crashes map rendering — FIXED

## 🟡 `isValidCoord` helper + `renderRoute` try/catch prevent malformed coordinates from blanking the map — FIXED

**File:** `frontend/src/MapView.jsx` — `renderRoute`, `_renderRouteInner`, Pass 2 board/exit marker block

**What was happening:** The board/exit marker block in Pass 2 of the route renderer used `if (leg.from_coords)` — a truthiness guard that only rejects `null`/`undefined`. Values that are truthy but structurally invalid (e.g., `[null, null]`, an empty array, or a plain object) passed the check and were handed to `toGeo`, which destructures its argument as `([lat, lon])`. Destructuring a non-array or an array with non-finite elements throws a `TypeError` or produces `[undefined, undefined]` coordinates. MapLibre GL rejects invalid coordinates at `addSource`, throwing its own error. Because there was no try/catch around the render path, the throw propagated out of `renderRoute`, unwound the entire second pass, and left the map blank — no polyline, no markers — with no visible error message to the user.

**Fixed in:** Three changes to `frontend/src/MapView.jsx`:

1. **`isValidCoord` helper** (new, near top of file): validates that a value is a two-element array where both elements are finite numbers. Rejects `null`, `undefined`, `[]`, `[null, null]`, plain objects, and NaN values.

2. **Board/exit marker guard upgraded**: replaced `if (leg.from_coords)` / `if (leg.to_coords)` with `if (isValidCoord(leg.from_coords))` / `if (isValidCoord(leg.to_coords))`, so malformed coordinates are silently skipped rather than passed to `toGeo`.

3. **`renderRoute` try/catch wrapper**: extracted the rendering body into `_renderRouteInner`; `renderRoute` now wraps the call in `try/catch` and logs any uncaught error to the console. This prevents any future coordinate or MapLibre error from silently blanking the map — the polylines and other markers already added in Pass 1 survive even if Pass 2 partially fails.

```js
// NEW — isValidCoord helper
const isValidCoord = (c) =>
  Array.isArray(c) && c.length === 2 &&
  typeof c[0] === "number" && isFinite(c[0]) &&
  typeof c[1] === "number" && isFinite(c[1]);

// BEFORE (passes [null, null] or {} to toGeo → TypeError):
if (leg.from_coords) boardExit.push({ coord: toGeo(leg.from_coords), ... });
if (leg.to_coords)   boardExit.push({ coord: toGeo(leg.to_coords),   ... });

// AFTER (skips any non-finite or non-array coordinate):
if (isValidCoord(leg.from_coords)) boardExit.push({ coord: toGeo(leg.from_coords), ... });
if (isValidCoord(leg.to_coords))   boardExit.push({ coord: toGeo(leg.to_coords),   ... });

// BEFORE (unguarded — any throw blanks the whole map):
function renderRoute(map, route, originCoords, destCoords, layerIds, sourceIds) {
  const { legs } = route;
  if (!legs?.length) return;
  // ... entire render body inline ...
}

// AFTER (try/catch logs and isolates failures):
function renderRoute(map, route, originCoords, destCoords, layerIds, sourceIds) {
  if (!route?.legs?.length) return;
  try {
    _renderRouteInner(map, route, originCoords, destCoords, layerIds, sourceIds);
  } catch (err) {
    console.error("[MapView] renderRoute failed:", err);
  }
}
```

---

# 2026-04-27 BUG-009 · DAU count for today resets to zero on server restart — FIXED

## 🟡 `_base_count` now pre-loads today's persisted count on server startup — FIXED

**File:** `backend/dau.py` — lines 35, 73, 86–92, 103

**What was happening:** `_seen_hashes` is an in-memory set initialized to `set()` on every server startup. On the first new unique visitor after a restart, `counts[today] = len(_seen_hashes)` evaluated to `1` and was persisted to disk — overwriting whatever count had already been saved for today. 100 visitors before a mid-day restart + 5 after would persist as `5` instead of `105`.

**Fixed in:** Added a module-level `_base_count: int = 0`. When the day initialises (either at first request or after midnight rollover), `_base_count` is set to `_load().get(today, 0)` — the count already on disk for today. All writes now use `_base_count + len(_seen_hashes)` instead of `len(_seen_hashes)` alone. Because hashes are never persisted, duplicate counting across restarts is impossible, so the additive approach is safe.

```python
# BEFORE (restart silently overwrites today's existing count):
_seen_hashes = set()
_current_day = today
# ...
counts[today] = len(_seen_hashes)  # starts from 0, loses pre-restart visitors

# AFTER (restart preserves today's previously-persisted count):
_seen_hashes = set()
_current_day = today
_base_count = _load().get(today, 0)  # snapshot of disk count at startup
# ...
counts[today] = _base_count + len(_seen_hashes)  # additive; no duplicates
```

---

# 2026-04-27 BUG-010 · Walk-only routes always use Sonnet; `_is_simple_query` returns False for 0 TransitLegs — FIXED

## 🟢 `_is_simple_query` now returns `True` for walk-only (0 TransitLeg) routes — FIXED

**File:** `backend/main.py` — line 558

**What was happening:** `_is_simple_query` returned `True` only when a route had exactly 1 `TransitLeg` (`len(transit_legs) == 1`). Walk-only routes have zero `TransitLeg`s, so the check evaluated to `False` and the function returned `False`. This caused `_call_claude` to always select the expensive Sonnet model for walk-only queries, even though a walk description is the simplest possible query.

**Fixed in:** Changed `return len(transit_legs) == 1` to `return len(transit_legs) <= 1`. Walk-only routes (0 transit legs) and direct single-leg rides (1 transit leg) are now both classified as simple, routing them to Haiku.

```python
# BEFORE (missed walk-only routes):
return len(transit_legs) == 1

# AFTER (catches walk-only and single-leg):
return len(transit_legs) <= 1
```

---

# 2026-04-27 BUG-012 · `route.wait_minutes` undefined renders "· undefined min" in route summary — FIXED

## 🟡 `waitNote` null-guard changed from strict `=== null` to loose `== null` to also catch `undefined` — FIXED

**File:** `frontend/src/components/RouteCard.jsx` — line 148

**What was happening:** `waitNote` used a strict equality check (`route.wait_minutes === null`). When the backend omits `wait_minutes` entirely (field absent rather than explicitly `null`), JavaScript's `=== null` test evaluates to `false` for `undefined`, so the ternary fell through to the string-interpolation branch and produced `"· undefined min"` in the route card header.

**Fixed in:** Changed `route.wait_minutes === null` to `route.wait_minutes == null`. Loose equality treats both `null` and `undefined` as nullish, so an absent field now correctly collapses to the empty-string branch — no wait note is displayed.

```js
// BEFORE (misses undefined):
const waitNote =
  route.wait_minutes === null ? ""
  : route.wait_minutes === 0  ? ` · ${t("wait_due")}`
  : ` · ${t("wait_minutes", { minutes: route.wait_minutes })}`;

// AFTER (catches null and undefined):
const waitNote =
  route.wait_minutes == null ? ""
  : route.wait_minutes === 0  ? ` · ${t("wait_due")}`
  : ` · ${t("wait_minutes", { minutes: route.wait_minutes })}`;
```

---

# 2026-04-27 BUG-011 · Off-route detection fires false positives at the start of long walk legs — FIXED

## 🔴 Off-route detection now uses perpendicular distance to walk polyline segments instead of endpoint distances — FIXED

**File:** `frontend/src/App.jsx` — off-route detection block (~line 737), new `pointToSegmentMeters` helper (~line 641)

**What was happening:** The off-route check computed `minDist` as the minimum haversine distance from the user's GPS position to the **endpoint** of every leg in the route. At the start of any walk leg longer than ~400 m the user is correctly standing on the route path but is farther than 400 m from every leg endpoint — so the check immediately fired `setIsOffRoute(true)` and showed the false "You appear to be off your planned route" banner before the user had taken a single step.

**Fixed in:** Added a `pointToSegmentMeters(p, a, b)` helper that computes the minimum perpendicular distance from a point to a line segment using a flat-earth projection (accurate to within ~1% for segments under ~10 km). The off-route detection block now iterates over every consecutive `[lat, lon]` pair in `activeLeg.path` and takes the minimum segment distance. A single-point path falls back to a haversine point distance. This correctly evaluates whether the user has strayed from the walked path, not just how far they are from the walk leg's destination.

```js
// BEFORE (endpoint-only, false-positive on long walk legs):
const minDist = route.legs.reduce((min, leg) => {
  const end = legEndCoord(leg);
  return end ? Math.min(min, haversineMeters(userPosition, end)) : min;
}, Infinity);
setIsOffRoute(minDist > 400);

// AFTER (perpendicular distance to active leg's polyline segments):
const path = activeLeg.path;
let minDist = Infinity;
if (path?.length >= 2) {
  for (let i = 0; i < path.length - 1; i++) {
    const a = { lat: path[i][0], lng: path[i][1] };
    const b = { lat: path[i + 1][0], lng: path[i + 1][1] };
    minDist = Math.min(minDist, pointToSegmentMeters(userPosition, a, b));
  }
} else if (path?.length === 1) {
  minDist = haversineMeters(userPosition, { lat: path[0][0], lng: path[0][1] });
}
setIsOffRoute(minDist > 400);
```

---

# 2026-04-27 BUG-013 · `route.transfers` undefined renders "undefined transfers" in route summary — FIXED

## 🟡 Nullish coalesce added so missing `transfers` field defaults to `0` — FIXED

**File:** `frontend/src/components/RouteCard.jsx` — `RouteCard`, lines 151–157

**What was happening:** `xferNote` was computed directly from `route.transfers` with strict equality checks (`=== 0`, `=== 1`). When the backend response omitted the `transfers` field entirely, `route.transfers` was `undefined` — neither check matched — and the fallthrough branch called `t("label_n_transfers", { count: undefined })`, which i18next interpolated as the literal string `"undefined transfers"`.

**Fixed in:** Added `const transfers = route.transfers ?? 0;` before the ternary and replaced all `route.transfers` references with `transfers`. When the field is absent (`undefined`) or explicitly `null`, it now safely defaults to `0` and renders "No transfers".

```js
// BEFORE (crashes on missing field):
const xferNote =
  route.transfers === 0
    ? t("label_no_transfers")
    : route.transfers === 1
    ? t("label_1_transfer")
    : t("label_n_transfers", { count: route.transfers });

// AFTER (nullish-safe):
const transfers = route.transfers ?? 0;
const xferNote =
  transfers === 0
    ? t("label_no_transfers")
    : transfers === 1
    ? t("label_1_transfer")
    : t("label_n_transfers", { count: transfers });
```

---

# 2026-04-27 BUG-011 · Rate-limit bypass via spoofed `X-Forwarded-For` header — FIXED

## 🟢 `_client_ip()` now reads the rightmost proxy-appended IP instead of the client-supplied first entry — FIXED

**File:** `backend/main.py` — `_client_ip()`, lines 106–121

**What was happening:** `_client_ip()` extracted the **first** (leftmost) entry from the `X-Forwarded-For` header. Clients control the first entry — they can send `X-Forwarded-For: 1.2.3.4` to appear as any arbitrary IP. An attacker could cycle through fake IPs on every request to bypass the per-IP rate limit entirely when `RATE_LIMIT_ENABLED=true`.

**Fixed in:** Changed to read the **last** (rightmost) entry of `X-Forwarded-For`. Railway's load balancer appends the real client IP at the end of the chain; that entry cannot be forged by the client because the LB writes it after receiving the request. The function also now checks `X-Real-IP` first (set exclusively by the Railway LB), then falls back to the last `X-Forwarded-For` entry, then to `request.client.host`.

```python
# BEFORE (spoofable):
def _client_ip(http_request: Request) -> str:
    forwarded = http_request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()      # client-controlled, spoofable
    return http_request.client.host if http_request.client else "unknown"

# AFTER (proxy-safe):
def _client_ip(http_request: Request) -> str:
    real_ip = http_request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip                               # Railway LB header, not client-supplied
    forwarded = http_request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()      # rightmost = Railway-appended, not spoofable
    return http_request.client.host if http_request.client else "unknown"
```

---

# 2026-04-27 BUG-008 · DAU counter midnight race condition — FIXED

## 🟡 `today` and HMAC digest moved inside `async with _lock:` block — FIXED

**File:** `backend/dau.py` — `record_visit()`, lines 64–89

**What was happening:** `record_visit()` computed `today = _today_chi()` and the HMAC digest **before** acquiring `_lock`. A coroutine that read `today = "Apr27"` just before midnight could then suspend waiting for the lock while a second coroutine acquired the lock, advanced `_current_day` to `"Apr28"`, and reset `_seen_hashes`. When the first coroutine finally acquired the lock, it saw `today ("Apr27") != _current_day ("Apr28")`, then: (a) saved the already-reset Apr28 count (0) as the final Apr27 count, (b) reset `_seen_hashes` again, losing all Apr28 visits recorded so far, and (c) set `_current_day` backward to Apr27 — corrupting both days' counts.

**Fixed in:** Moved `today = _today_chi()` to the first line inside the `async with _lock:` block so the date is always observed atomically with respect to the in-memory state. The HMAC key and digest computation were also moved to after the day-rollover check so the digest is always keyed against the authoritative `today` value.

```python
# BEFORE (race-prone):
today = _today_chi()
hmac_key = (_DAILY_SALT + today).encode()
digest = hmac.new(hmac_key, ip.encode(), hashlib.sha256).hexdigest()
async with _lock:
    if today != _current_day:
        ...

# AFTER (race-safe):
async with _lock:
    today = _today_chi()
    if today != _current_day:
        ...
    hmac_key = (_DAILY_SALT + today).encode()
    digest = hmac.new(hmac_key, ip.encode(), hashlib.sha256).hexdigest()
    ...
```

---

# 2026-04-27 BUG-010 · File descriptor leak in `dau._save()` when `os.fdopen()` raises — FIXED

## 🟢 `os.close(tmp_fd)` now called in except block when `os.fdopen` fails — FIXED

**File:** `backend/dau.py` — `_save()`, lines 52–62

**What was happening:** `tempfile.mkstemp()` returned an open file descriptor `tmp_fd`. If `os.fdopen(tmp_fd, "w", encoding="utf-8")` raised (e.g., a rare platform-level fd error), the `except Exception` block called `os.unlink(tmp_path)` to remove the temp file but never called `os.close(tmp_fd)`. The raw fd leaked for the lifetime of the process. On Linux the default per-process fd limit is 1024; repeated failures would exhaust it.

**Fixed in:** Added an `fdopen_ok = False` flag before the `try` block. Inside the `with os.fdopen(...)` statement, `fdopen_ok` is set to `True` immediately on entry (so only the `os.fdopen` call itself can trigger the `False` path). In the `except` block, `os.close(tmp_fd)` is called only when `fdopen_ok` is `False`. When `os.fdopen` succeeds, the `with` statement's `__exit__` closes the fd normally and the explicit `os.close` is skipped.

```python
# BEFORE (fd leaks if os.fdopen raises):
def _save(counts: dict[str, int]) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(dir=DAU_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(counts, f)
        os.replace(tmp_path, DAU_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise

# AFTER (fd always closed):
def _save(counts: dict[str, int]) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(dir=DAU_FILE.parent, suffix=".tmp")
    fdopen_ok = False
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            fdopen_ok = True
            json.dump(counts, f)
        os.replace(tmp_path, DAU_FILE)
    except Exception:
        if not fdopen_ok:
            os.close(tmp_fd)
        os.unlink(tmp_path)
        raise
```

---

# 2026-04-27 BUG-009 · `_load_graph()` does not set `_graph_load_failed` on coordinate-array errors — FIXED

## 🟡 Coordinate-array and cKDTree construction wrapped in `try/except`; `_graph_load_failed` now set on any failure — FIXED

**File:** `backend/walking.py` — `_load_graph()`, lines 111–138

**What was happening:** After successfully loading the igraph artifact or GraphML fallback, `_load_graph()` built coordinate arrays with `np.array([v["x"] for v in G.vs])` and constructed the `cKDTree` outside any `try/except` block. If vertex attributes `"x"` or `"y"` were absent (e.g., a corrupt or non-OSMnx-generated pickle), a `KeyError` propagated out of the `with _graph_lock:` block without setting `_graph_load_failed = True`. On every subsequent call, `_load_graph()` found neither `_graph_cache` nor `_graph_load_failed`, re-entered the lock, and failed again — logging exceptions on every routing request and causing unnecessary lock contention while falling back to Haversine for all walk calculations.

**Fixed in:** Wrapped the entire coordinate-array construction and `cKDTree` build block in a `try/except Exception` that logs the error, sets `_graph_load_failed = True`, and returns `None`. The existing inner `try/except AttributeError` for `G.clusters()` is preserved inside the outer block. `_graph_cache` is only assigned at the end of the `try` body, so a partial failure can never leave a partially-initialized cache.

```python
try:
    lons = np.array([v["x"] for v in G.vs], dtype=np.float64)
    lats = np.array([v["y"] for v in G.vs], dtype=np.float64)
    _vertex_lats = lats
    _vertex_lons = lons
    try:
        comps = G.clusters(mode="WEAK")
    except AttributeError:
        comps = G.connected_components(mode="weak")
    lcc_ids = np.array(max(comps, key=len), dtype=np.int64)
    _lcc_vertex_ids = lcc_ids
    _coord_kdtree = cKDTree(np.column_stack([lons[lcc_ids], lats[lcc_ids]]))
    if len(lcc_ids) < G.vcount():
        print(f"[walking] LCC: {len(lcc_ids):,}/{G.vcount():,} vertices in main component")
    _graph_cache = G
except Exception as e:
    print(f"[walking] Failed to build coordinate arrays ({type(e).__name__}: {e}) — walking will use Haversine fallback.")
    _graph_load_failed = True
    return None
```

---

# 2026-04-25 BUG-023 · Purple Line (and other rush-hour express services) never appeared in routing — FIXED

## 🟢 Representative trip selection changed from noon-proximity to longest-trip — FIXED

**File:** `backend/transit_graph.py` — `_stream_all_stop_sequences`, line ~407

**What was happening:** The transit graph selected one representative trip per `(route_id, direction_id)` by choosing the weekday trip whose first-stop departure was closest to noon. Purple Express only runs during rush hours. GTFS data confirms 135 weekday Purple trips have 9 stops (Evanston local, Linden→Howard) and 55 have 43 stops (Purple Express, Linden→Loop). The noon selector always picked a local trip, so the graph contained no Purple edges south of Howard. Purple Line could never route to downtown regardless of actual travel time.

**Fixed in:** Changed the selector from `min(...noon proximity...)` to `max(...most stops..., tie-break by noon proximity)`. The Purple Express (43 stops) is now selected, creating graph edges from Howard through the Loop. For all other lines with full-length all-day service the selection is unchanged.

---

# 2026-04-25 BUG-022 · Shared-track lines (Purple, Green, Pink) invisible to station deduplication — FIXED

## 🟢 `_dedup_stations_by_line` now reads `all_routes` attribute alongside primary `line` — FIXED

**File:** `backend/transit_graph.py` — `_dedup_stations_by_line`, lines ~1332–1336

**What was happening:** When two lines serve identical consecutive stops (e.g. Red/Purple at Belmont→Fullerton, Green/Pink at Loop elevated stations), the graph stores only one edge per `(from, to)` node pair. The competing line is saved in an `all_routes` edge attribute but `_dedup_stations_by_line` collected station lines by reading only the primary `line` attribute. Shared-track lines were never detected, so stations that offered them were treated as redundant and dropped from routing candidates.

**Fixed in:** Rewrote the `station_lines` collection loop to also iterate `all_routes` on each transit edge, exposing every line that serves a station including those suppressed by edge-level tie-breaking.

---

# 2026-04-24 BUG-021 · CTA Alerts API — 100% failure rate due to dead endpoint — FIXED

## 🟢 `ALERTS_BASE` migrated to `lapi.transitchicago.com` — FIXED

**File:** `backend/cta_client.py` — `ALERTS_BASE`

**What was happening:** Every Alerts API call was returning an empty body, causing `json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`. The `ALERTS_BASE` URL pointed to `http://www.transitchicago.com/api/1.0/detailed_alerts.aspx` which now returns a 404. This affected all routes (Red, Blue, Brown, Green, Pink, Orange, Purple, Yellow, and all bus routes). The error was caught and swallowed gracefully, so the app continued to function but users received zero service alerts for the entire day.

**Fixed in:** Updated `ALERTS_BASE` to `https://lapi.transitchicago.com/api/1.0/alerts.aspx` — the current CTA Alerts endpoint. Also switched from plain HTTP to HTTPS. The `CTAAlerts.Alert` JSON response structure is identical so no other code changes were required.

---

# 2026-04-24 BUG-020 · `walk_path` routing failed when geocoded point snapped to disconnected graph vertex — FIXED

## 🟡 KDTree restricted to largest connected component; 1 km snap-distance guard added — FIXED

**File:** `backend/walking.py` — `_load_graph()`, `_get_nearest_node()`

**What was happening:** `_get_nearest_node()` used `cKDTree.query()` with no distance limit and no connectivity check. The KDTree was built from all 27,380 graph vertices, including peripheral vertices that exist in small disconnected components on the edge of the Chicago street network. When a geocoded origin or destination fell outside the graph's coverage area (or near its boundary), it snapped to one of these isolated vertices. Dijkstra then ran between two vertices in different connected components, `get_shortest_paths()` returned an empty list, and `_get_shortest_path()` raised `RuntimeError("path unavailable")`. This appeared 38 times in production logs, often in clusters of 5–7 consecutive failures within a single session (a user searching multiple nearby spots outside the network boundary).

**Fixed in:** Two changes to `walking.py`:

1. **LCC-only KDTree** — at graph load time, the largest weakly-connected component is computed via `G.clusters(mode="WEAK")`. The `cKDTree` and the new `_lcc_vertex_ids` index array are built from only those vertices. `_get_nearest_node()` translates the KDTree result index through `_lcc_vertex_ids` to get the actual graph vertex index. All Dijkstra calls now run between vertices that are guaranteed mutually reachable.

2. **1 km snap-distance guard** — after snapping, `_get_nearest_node()` computes the haversine distance from the input coordinate to the snapped vertex. If it exceeds 1 000 m the function returns `None`, causing `_get_shortest_path()` to return `None` early and all three public routing functions (`walk_minutes`, `walk_directions`, `walk_path`) to fall back to their Haversine estimates without logging a routing failure.

```python
# _load_graph() — build KDTree from LCC vertices only
try:
    comps = G.clusters(mode="WEAK")
except AttributeError:
    comps = G.connected_components(mode="weak")
lcc_ids = np.array(max(comps, key=len), dtype=np.int64)
_lcc_vertex_ids = lcc_ids
_coord_kdtree = cKDTree(np.column_stack([lons[lcc_ids], lats[lcc_ids]]))

# _get_nearest_node() — map KDTree index → graph vertex, reject if too far
_, kdtree_idx = _coord_kdtree.query([lon, lat])
graph_idx = int(_lcc_vertex_ids[kdtree_idx])
if _haversine_miles(lat, lon, _vertex_lats[graph_idx], _vertex_lons[graph_idx]) * 1609.34 > 1000:
    return None
return graph_idx
```

---

# 2026-04-24 BUG-013 · Service worker used `NetworkOnly` for `/recommend` — app unusable offline — FIXED

## 🟡 Workbox `NetworkOnly` replaced with `NetworkFirst` + cache options — FIXED

**File:** `frontend/vite.config.js` — runtime caching block for `/recommend` and `/health`

**What was happening:** The Workbox runtime caching strategy for `/recommend` (and `/health`) was `NetworkOnly`. If the network was unavailable or too slow — common in CTA underground stations — the user received no response and the app appeared broken. A transit app used underground should serve a stale cached result rather than nothing.

**Fixed in:** Changed `handler: "NetworkOnly"` to `handler: "NetworkFirst"` and added a `cacheName: "api-cache"` block with `maxEntries: 25` and `maxAgeSeconds: 3600` (1 hour). With `NetworkFirst`, Workbox attempts the network first; if the network is unreachable or times out, it falls back to the most recent cached response. Cache entries expire after 1 hour and the cache is capped at 50 entries to prevent unbounded growth.

```javascript
// BEFORE:
{
  urlPattern: /\/(recommend|health)(\?.*)?$/i,
  handler: "NetworkOnly",
}

// AFTER:
{
  urlPattern: /\/(recommend|health)(\?.*)?$/i,
  handler: "NetworkFirst",
  options: {
    cacheName: "api-cache",
    expiration: {
      maxEntries: 25,
      maxAgeSeconds: 3600,
    },
  },
}
```

---

# 2026-04-24 BUG-019 · Graph node accessed without existence check in `walking.py` — FIXED

## 🟢 Vertex index bounds check and coordinate-array None guards added — FIXED

**File:** `backend/walking.py` — `_get_shortest_path()`, `_walk_directions_impl()`, `_walk_path_impl()`

**What was happening:** The code has been migrated from NetworkX to igraph since the bug was originally filed. The equivalent vulnerability in the igraph codebase is:

1. **`_get_shortest_path`** — after `_get_nearest_node()` returned vertex indices, there was no guard verifying those indices were within `G.vcount()`. A stale KDTree (e.g., if the graph object were replaced between the tree build and the path query) could produce an out-of-bounds index, causing igraph to raise an `IndexError` on `G.get_shortest_paths()`.

2. **`_walk_directions_impl` / `_walk_path_impl`** — both functions access `_vertex_lats[vertex_idx]` and `_vertex_lons[vertex_idx]` directly. These module-level arrays are set inside `_load_graph()` but there was no explicit None guard before the access, meaning a corrupted or partially-initialized graph state could cause a `TypeError` when subscripting `None`.

**Fixed in:** Three guards added:

```python
# _get_shortest_path — after existing None check:
n = G.vcount()
if orig_idx >= n or dest_idx >= n:
    return None

# _walk_directions_impl — before vertex array access:
if _vertex_lats is None or _vertex_lons is None:
    raise RuntimeError("vertex coordinate arrays unavailable")

# _walk_path_impl — before vertex array access:
if _vertex_lats is None or _vertex_lons is None:
    raise RuntimeError("vertex coordinate arrays unavailable")
```

The `RuntimeError` cases in the two `_impl` functions are caught by their surrounding `try/except` blocks and fall back to the Haversine estimate, preserving graceful degradation.

---

# 2026-04-24 BUG-018 · Walking distance can round to `0.0` minutes — FIXED

## 🟢 `walk_minutes()` could return `0.0` for very short walks — FIXED

**File:** `backend/walking.py` — line 197 (inside `walk_minutes()`)

**What was happening:** For two stops less than ~6 metres apart, `round(length_m / WALKING_SPEED_MPS / 60, 1)` returned `0.0`. Downstream code treating `0.0` as "no walk needed" (or any division by walk time) could behave incorrectly.

**Fixed in:** Wrapped the return with `max(0.1, ...)` to enforce a minimum of 0.1 minutes (~6 seconds):

```python
# BEFORE:
return round(length_m / WALKING_SPEED_MPS / 60, 1)

# AFTER:
return max(0.1, round(length_m / WALKING_SPEED_MPS / 60, 1))
```

---

# 2026-04-24 BUG-017 · Street name non-string type causes `AttributeError` in `walking.py` — FIXED

## 🟢 `_street_name()` crashed on truthy non-string OSM `name` values — FIXED

**File:** `backend/walking.py` — `_street_name()` inner function inside `_walk_directions_impl`

**What was happening:** The `name` field from OpenStreetMap edges can be a string, a list, or occasionally a non-string scalar (e.g., an integer road number). After handling the list case, the code used `(name or "").strip()`. Python's `or` short-circuits on falsy values only — a truthy non-string like `42` passes through unchanged, and `42.strip()` raises an unhandled `AttributeError` in the walk directions path.

**Fixed in:** Added an explicit `isinstance(name, str)` guard after the list check. Non-string values now return `"unnamed path"` directly instead of attempting `.strip()`:

```python
# BEFORE:
if isinstance(name, list):
    name = name[0] if name else ""
name = (name or "").strip()
return name if name else "unnamed path"

# AFTER:
if isinstance(name, list):
    name = name[0] if name else ""
if not isinstance(name, str):
    return "unnamed path"
name = name.strip()
return name if name else "unnamed path"
```

---

# 2026-04-24 BUG-014 · BYOK API key had no idle timeout and no "Forget Key" button — FIXED

## 🟡 BYOK key persisted indefinitely with no idle auto-clear — FIXED

**File:** `frontend/src/App.jsx` — after `handleSaveByokKey` (~line 356)

**What was happening:** The BYOK Anthropic API key was stored in `sessionStorage` with no auto-expiry. A user who walked away from their computer left their key accessible for the entire browser session. The bug originally called for both a "Forget Key" button and a 30-minute idle timeout; the "Remove Key" button in `SettingsPanel.jsx` already satisfied the former (added during TD-013 component extraction), so only the idle timeout was missing.

**Fixed in:** Added a `useEffect` in `App.jsx` that activates only when a key is stored (`BYOK_ENABLED && byokKey`). On mount it attaches `mousemove` and `keydown` listeners that each reset a 30-minute `setTimeout`. When the timer fires (no user activity for 30 minutes), the key is removed from `sessionStorage` and `byokKey` state is cleared. The effect re-runs whenever `byokKey` changes, ensuring the timer is torn down and restarted correctly on key save/removal.

```javascript
useEffect(() => {
  if (!BYOK_ENABLED || !byokKey) return;
  let idleTimer;
  const resetTimer = () => {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      sessionStorage.removeItem("byok_api_key");
      setByokKey("");
    }, 30 * 60 * 1000);
  };
  window.addEventListener("mousemove", resetTimer);
  window.addEventListener("keydown", resetTimer);
  resetTimer();
  return () => {
    clearTimeout(idleTimer);
    window.removeEventListener("mousemove", resetTimer);
    window.removeEventListener("keydown", resetTimer);
  };
}, [byokKey]);
```

---

# 2026-04-24 BUG-016 · Fragile empty-legs fallback in `MapView.jsx` uses IIFE — FIXED

## 🟢 IIFE for last-leg path fallback replaced with explicit length guard — FIXED

**File:** `frontend/src/MapView.jsx` — line ~207

**What was happening:** The destination dot fallback used an IIFE (`(() => { ... })()`) to retrieve the last leg's path without first checking that `legs` is non-empty. Optional chaining masked any crash but produced `undefined` silently with no indication of the fallback intent, making the code fragile and hard to reason about.

**Fixed in:** Replaced the IIFE with an explicit `legs.length > 0` guard and a named intermediate `lastLegPath`:

```javascript
// BEFORE:
const destPt = destCoords
  ? [destCoords[1], destCoords[0]]
  : (() => { const lp = legs[legs.length - 1]?.path; return lp?.length ? toGeo(lp[lp.length - 1]) : null; })();

// AFTER:
const lastLegPath = legs.length > 0 ? legs[legs.length - 1]?.path : null;
const destPt = destCoords
  ? [destCoords[1], destCoords[0]]
  : (lastLegPath?.length ? toGeo(lastLegPath[lastLegPath.length - 1]) : null);
```

---

# 2026-04-24 BUG-012 · Boolean short-circuit on coordinate lookup silently substitutes wrong latitude — FIXED

## 🟡 Double `_bus_stop_coords.get()` call replaced with explicit membership check — FIXED

**File:** `backend/transit_graph.py` — `find_bus_transfer_routes()` lines ~1679–1684

**What was happening:** The boarding-stop haversine calculation called `_bus_stop_coords.get(stop_id, (origin_lat, origin_lon))` twice (once for index `[0]`, once for `[1]`) to extract coordinates to pass to `_haversine_miles()`. Beyond the redundant double dict lookup, the original bug report describes this code pattern as having originated from a `... [0] or origin_lat` form that treats a stored latitude of `0.0` as falsy (Python's `or` short-circuits on any falsy value), silently substituting `origin_lat` and producing an incorrect haversine distance with no error or log.

**Fixed in:** Replaced the double `.get()` calls with an explicit membership check:

```python
if stop_id in _bus_stop_coords:
    board_lat, board_lon = _bus_stop_coords[stop_id]
else:
    board_lat, board_lon = origin_lat, origin_lon
boarding_hav = _haversine_miles(board_lat, board_lon, dest_lat, dest_lon)
```

The dict is now looked up at most once per arrival, coordinate unpacking is unambiguous, and a latitude of `0.0` is handled correctly. No other nearby coordinate lookups in this function used the `or` short-circuit idiom.

---

# 2026-04-24 BUG-015 · Bus stop coordinate tuple unpacked without length validation — FIXED

## 🟡 `t_lat, t_lon = t_meta` unpacked without tuple-length guard — FIXED

**File:** `backend/transit_graph.py` — line ~1793

**What was happening:** `_bus_stop_coords.get(t_stop_id)` was checked for `None`, but immediately unpacked with `t_lat, t_lon = t_meta` without verifying the tuple had exactly 2 elements. A malformed cache entry (e.g., a 3-tuple or a scalar) would raise an unhandled `ValueError`, crashing the transfer-route pass for that candidate.

**Fixed in:** Added `isinstance` + `len` guards before unpacking:

```python
# BEFORE:
t_meta = _bus_stop_coords.get(t_stop_id)
if t_meta is None:
    continue
t_lat, t_lon = t_meta

# AFTER:
t_meta = _bus_stop_coords.get(t_stop_id)
if not t_meta or not isinstance(t_meta, tuple) or len(t_meta) != 2:
    continue
t_lat, t_lon = t_meta
```

---

# 2026-04-24 BUG-011 · `frontend/.env.production` missing `https://` in `VITE_BACKEND_URL` — FIXED

## 🔴 `VITE_BACKEND_URL` committed without `https://` protocol prefix — FIXED

**File:** `frontend/.env.production` — line 3

**What was happening:** `VITE_BACKEND_URL` was committed as a bare hostname with no protocol (`cta-transit-pwa-prod-production.up.railway.app`). Vite bakes this value into the production bundle at build time. Without `https://`, the browser treated concatenated API URLs (e.g. `/recommend`) as relative paths on the Vercel domain, causing every API request to return 404. A prior fix had updated the Vercel dashboard env var directly, but the committed file was never corrected. Any fresh Vercel deployment reading from the committed file (or any local production build) would reproduce the 404 regression.

**Fixed in:** Added the `https://` prefix to the committed file:
```env
VITE_BACKEND_URL=https://cta-transit-pwa-prod-production.up.railway.app
```

---

# 2026-04-23 BUG-010 · `_check_rate_limit` silently drops the first request's timestamp after a full hourly gap — FIXED

## 🟡 `_check_rate_limit` silently drops the first request's timestamp after a full hourly gap — FIXED

**File:** `backend/main.py`

**What was happening:** After evicting all timestamps older than 1 hour, `_check_rate_limit` called `del _rate_store[ip]` to remove the now-empty deque. The local `window` variable still held a reference to the orphaned deque, so `window.append(now)` at the end of the function appeared to succeed — but the deque was no longer stored in `_rate_store`. On the next request, `_rate_store.setdefault(ip, collections.deque())` created a fresh empty deque, silently discarding the previous request's timestamp. An attacker making exactly one request per hour would never accumulate quota and could never be rate-limited.

The `del _rate_store[ip]` block was originally added to prevent stale IPs from accumulating indefinitely. That concern is already addressed by the eviction loop (`window.popleft()` removes every timestamp older than 1 hour), so the deletion was both incorrect and unnecessary — empty deques are O(1) in memory.

**Fixed in:** Removed the `if not window: del _rate_store[ip]` block entirely. The eviction loop still keeps deques lean; IPs that have not sent a request in over an hour hold an empty deque at negligible cost, and every new request timestamp is correctly persisted.

---

# 2026-04-23 BUG-009 · Duplicate `_haversine_walk_minutes` Definition in `walking.py` — FIXED

## 🟡 `_haversine_walk_minutes` defined twice — first definition is dead code — FIXED

**File:** `backend/walking.py`

**What was happening:** `_haversine_walk_minutes` was defined twice in the module — first at line 171 (with a multi-line docstring describing it as a street-graph fallback) and again at line 409 (a compact one-liner). Python silently overwrites the first definition with the second at module load time. Both computed identical results, but the first definition was dead code: any future change to it would be silently ignored, and any reader who found the first definition would be confused about which one was active.

**Fixed in:** Deleted the first definition (the verbose version at line 171–186). The surviving definition at (now) line ~393 is the canonical one.

---

# 2026-04-20 BUG-008 `_haversine_walk_minutes()` Function Missing — FIXED

## 🔴 Missing `_haversine_walk_minutes()` function causes runtime crash — FIXED

**File:** [backend/walking.py](backend/walking.py)

**What was happening:** The `walk_minutes()` function (line 198) had a fallback exception handler that called `_haversine_walk_minutes(origin_lat, origin_lon, dest_lat, dest_lon)` when the street graph was unavailable or routing failed. However, this function was never defined anywhere in the module. When a user's origin or destination fell outside the street graph's bounding box (or the graph failed to load), the fallback would trigger and immediately raise `NameError: name '_haversine_walk_minutes' is not defined`, crashing the entire route recommendation pipeline with a 500 error.

**Fixed in:** Implemented the missing `_haversine_walk_minutes()` function (inserted at line 177–189, just before `walk_minutes()`):
```python
def _haversine_walk_minutes(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
) -> float:
    """Estimate walking time (minutes) using straight-line Haversine distance."""
    distance_miles = _haversine_miles(origin_lat, origin_lon, dest_lat, dest_lon)
    return round(distance_miles / 3.0 * 60.0, 1)
```

---

# 2026-04-20 `_rate_store` + `_response_cache` Race Condition — `asyncio.Lock` Added

## 🔴 `_rate_store` and `_response_cache` race condition under concurrent requests — FIXED

**File:** `backend/main.py`

**What was happening:** Both `_rate_store` (dict of deques) and `_response_cache` (OrderedDict) were read and written without any lock. Because `recommend()` is an `async def` that `await`s multiple times between the cache read (line ~982) and the cache write (line ~1040), the asyncio event loop could switch to a second coroutine mid-flight. This caused two failure modes under moderate concurrency:

1. **Cache stampede** — two concurrent requests with the same key both saw a cache miss, both launched the full expensive pipeline (geocode → routing → Claude API call), and both wrote the result. Wasted compute and API quota.
2. **Double-pop eviction** — both responses saw `len(_response_cache) > _CACHE_MAX_SIZE` and each called `popitem(last=False)`, evicting two entries when only one should have been dropped.

**Fixed in:**
1. **`_store_lock = asyncio.Lock()` added** at module level in `main.py`, alongside `_rate_store` and `_response_cache`.
2. **Rate-limit check + cache read wrapped in `async with _store_lock:`** — both `_check_rate_limit(ip)` and `_response_cache.get(key)` / `pop()` now execute inside a single locked block at the top of `recommend()`.
3. **Cache write wrapped in a second `async with _store_lock:`** — the `_response_cache[key] = ...`, `move_to_end(key)`, and `popitem()` eviction at the bottom of `recommend()` are wrapped in their own locked block. Prevents the double-pop race.
4. **`_check_rate_limit` docstring updated** — removed the now-incorrect "No locking needed" claim; replaced with "Callers must hold `_store_lock` before calling this function."

---

# 2026-04-18 Bug Scan Fixes (`fetch_station_exits.py`, `fetch_gtfs.py`, `App.jsx`) + BUG-003 False-Positive Investigation

## 🟡 BUG-001 · Unguarded `float()` calls crash `load_parent_stations` on bad GTFS data — FIXED

**File:** `backend/fetch_station_exits.py`

**What was happening:** The `try/except ValueError` block only wrapped `int(row["stop_id"].strip())`. The `float(row["stop_lat"].strip())` and `float(row["stop_lon"].strip())` calls that immediately follow were outside the `try` block. A blank, non-numeric, or missing lat/lon column in any parent-station row would raise `ValueError` or `KeyError` and abort the entire `load_parent_stations()` function.

**Fixed in:** Expanded the `try` block to cover the entire per-row processing block. The `except` clause now catches `(ValueError, KeyError)` so missing or malformed lat/lon columns are skipped gracefully with `continue`.

---

## 🟢 BUG-002 · Negative row count printed for empty GTFS files — FIXED

**File:** `backend/fetch_gtfs.py`

**Fixed in:** Changed to `rows = max(0, sum(1 for _ in fh) - 1)`. An empty file now prints `0 rows` instead of `-1 rows`.

---

## 🔴 BUG-008 · Unguarded `renderMarkdown` call crashes on non-string recommendation — FIXED

**File:** `frontend/src/App.jsx`

**Fixed in:** Changed call site to `renderMarkdown(data.recommendation || "")`. If `data.recommendation` is `null`, `undefined`, or any other falsy value, an empty string is passed instead, preventing the `TypeError`.

---

## 🟡 BUG-003 · `_cardinal` bearing calculation — INVESTIGATED, NO BUG FOUND

**File:** `backend/walking.py`

**Investigation result:** The existing code `math.atan2(dlon, dlat)` is mathematically correct for clockwise compass bearing from north. The proposed "fix" `atan2(dlat, dlon)` would swap north and east, introducing the very 90° rotation error the report claimed to fix. No code change made.

---

# 2026-04-18 `backend/gtfs_loader.py` — Geocode Cache Durability and CSV Parsing Fixes

## 🟡 BUG-004 · Transient geocode failures cached as permanent misses — FIXED

**File:** `backend/gtfs_loader.py` — `geocode_google()`

**Fixed in:** The `None` cache write is now gated on `status == "ZERO_RESULTS"` only. All other non-OK statuses and all exception paths return `None` without caching, so subsequent requests will retry the Google Maps API.

---

## 🟡 BUG-005 · Pending geocode cache entries lost on failed compaction — FIXED

**File:** `backend/gtfs_loader.py` — `_flush_geocode_cache_if_dirty()` and `_save_geocode_cache()`

**Fixed in:** `_save_geocode_cache()` now returns `bool` (`True` on success, `False` on failure). In `_flush_geocode_cache_if_dirty()`, the compaction path only clears journal counters when the save succeeds. On failure, `_geocode_pending.update(pending)` restores the entries so they will be retried on the next flush interval.

---

## 🟢 BUG-006 · `_load_stops()` opened `stops.txt` without `newline=""` — FIXED

**File:** `backend/gtfs_loader.py` — `_load_stops()`

**Fixed in:** Changed to `open(stops_file, newline="", encoding="utf-8-sig")`, which disables universal newline translation and lets `csv.DictReader` handle line endings correctly on all platforms.

---

# 2026-04-18 `_ABBR_MAP` Duplicate-Key Vulnerability — Converted to Pair-List with Import-Time Assertion

## 🔴 `_ABBR_MAP` could silently accept duplicate keys — FIXED

**File:** `backend/gtfs_loader.py`

**Fixed in:** Replaced the dict literal with a tuple of `(abbr, expansion)` pairs (`_ABBR_PAIRS`) and constructed `_ABBR_MAP = dict(_ABBR_PAIRS)`. An `assert len(_ABBR_MAP) == len(_ABBR_PAIRS)` immediately after the conversion now fails at import time if any key is duplicated.

---

# 2026-04-18 Bus-Mode Multi-Leg Routing — Transfer Branch No Longer Gated on Direct Emptiness

## 🟡 Bus-only filter suppressed multi-leg bus routing when any direct route existed — FIXED

**File:** `backend/main.py`

**Fixed in:** Removed the emptiness gate for "Bus" mode. Now in `transit_mode="Bus"` the backend always calls both `find_bus_routes()` (n=3) and `find_bus_transfer_routes()` (n=2), concatenates the results, runs the combined list through the existing `_rank_bus_routes()` → sort → top-5 truncation → fingerprint-dedup pipeline. For `transit_mode="All"` the original emptiness-gated fallback is preserved. Transfer `n_routes` was lowered from 3 → 2 as an upfront cost-control measure.

---

# 2026-04-18 BYOK Settings Panel — Browser-Storage Security Notice Added

## 🟢 BYOK key stored in browser with no user warning — FIXED

**File:** `frontend/src/App.jsx`, `frontend/src/App.css`

**Fixed in:** Added a prominent warning block at the top of `SettingsPanel` (above the API key input) that reads: *"⚠ Security notice: Your key is stored in this browser. Only use this feature on trusted personal devices."* The banner uses `role="alert"` for accessibility and is styled via a new `.settings-warning` rule in `App.css`.

---

# 2026-04-18 `_build_shape_lookup` Two-Pass Refactor (Memory Bound to Used Shapes)

## 🟢 `_build_shape_lookup` held all GTFS shape points in memory simultaneously — FIXED

**File:** `backend/transit_graph.py`

**Fixed in:** Reordered to a true two-pass approach: Pass 1 (trips.txt) collects the set of `shape_id`s actually referenced by trips. Pass 2 (shapes.txt) streams points and skips any row whose `shape_id` is not in the used-set. `raw_pts` is also cleared after conversion to flush the per-shape point tuples once the sorted arrays are built.

---

# 2026-04-18 Bus Route Pill Showed `0`/`1` Instead of Route Number on Intermodal Legs

## 🔴 Intermodal bus legs displayed direction_id ("0"/"1") as the route pill label — FIXED

**File:** `backend/transit_graph.py`

**Fixed in:** Added a `_bearing_to_direction(lat1, lon1, lat2, lon2)` helper that maps the great-circle bearing into one of `Northbound` / `Southbound` / `Eastbound` / `Westbound`. In `_build_graph()`'s "Add bus route edges" block, that direction string is now passed as `line=direction_name` instead of `line=did`. The `direction_id` is still preserved on the edge as `direction_id=did`.

---

# 2026-04-17 Style Error Dismissal, Geocode Double-Suffix, and Transfer Floor Documentation Fixes

## ✅ `styleError` in `MapView.jsx` cleared on any tile load, not specifically on style recovery — FIXED

**File:** `frontend/src/MapView.jsx`

**Fixed in:** Added `e.dataType === "style"` guard to the `map.on("data", ...)` handler alongside the existing `e.isSourceLoaded` check.

---

## ✅ `geocode_google()` double-appended `, Chicago, IL` if already present in query — FIXED

**File:** `backend/gtfs_loader.py`

**Fixed in:** Changed to `"address": query if "chicago" in query.lower() else query + ", Chicago, IL"`.

---

## ✅ `_load_transfer_edges` silently clamped sub-2-minute GTFS transfers with no explanation — FIXED

**File:** `backend/transit_graph.py` — `_load_transfer_edges()`

**Fixed in:** Added a multi-line comment above the `max(min_sec / 60.0, _TRANSFER_MINUTES)` line documenting that this is an intentional pessimistic floor, why it exists, and where to change it.

---

# 2026-04-17 Geocoding, Shape Direction, Transfer Scoring, and Bus Label Fixes

## ✅ `_coords_for_location()` passed raw `query` to `geocode_google()` — cache miss, double API call — FIXED

**File:** `backend/main.py`

**Fixed in:** Added `q = _normalize_street_abbr(q)` after the existing `q = query.lower().strip()` in `_coords_for_location()`, and changed `geocode_google(query)` to `geocode_google(q)`.

---

## ✅ `clip_shape()` returned shape points in wrong order for reverse-direction trips — FIXED

**File:** `backend/transit_graph.py`

**Fixed in:** After computing `board_idx` and `exit_idx`, the slice `shape_points[lo:hi+1]` is assigned to `segment` and reversed (`segment[::-1]`) when `board_idx > exit_idx`.

---

## ✅ Bus transfer scoring used haversine × 20 instead of grid-corrected walk minutes — FIXED

**File:** `backend/transit_graph.py` — `find_bus_transfer_routes()`

**Fixed in:** Applied a 1.3× Manhattan-grid correction factor: `transfer_hav * 26.0` and `best_exit_dist * 26.0` (previously `* 20.0`).

---

## ✅ `_format_routes()` labeled bus wait as "next train" in Claude prompt — FIXED

**File:** `backend/main.py`

**Fixed in:** `_format_routes()` already correctly detects `is_bus` and uses `"next bus Due"` / `"next bus in N min"` accordingly. Confirmed present in code and removed from BUGS_TO_BE_FIXED.md.

---

# 2026-04-17 Railway Log Rate Limit Fix

## ✅ GTFS download progress loop bursts past Railway's 500 logs/sec limit — FIXED

**File:** [`backend/fetch_gtfs.py`](backend/fetch_gtfs.py)

**Severity:** 🔴 High (caused Railway to drop log messages and flag the replica)

**Fixed in:** Removed the per-chunk progress print. Progress is now logged at most once per 5 MB downloaded (~10 lines for a 50 MB file). Net result: ~800 lines/download → ≤12 lines/download.

---

# 2026-04-16 Bus Wait Correctness Fix

## ✅ Bus routes bypass `_rank_routes` — live wait times not normalised — FIXED

**File:** `backend/main.py`

**Fixed in:** Added `_rank_bus_routes()` helper. Bus routes from `find_bus_routes()` / `find_bus_transfer_routes()` now re-express `wait` as `int | None` to match `_rank_routes()` output semantics.

---

# 2026-04-16 Performance Fix

## ✅ `get_bus_stop_sequences` double-streamed 5.8M-row `stop_times.txt` — FIXED

**File:** `backend/transit_graph.py`

**Fixed in:** Replaced `_stream_stop_sequences` with `_stream_all_stop_sequences`, which processes both train and bus trips in a single pass through `stop_times.txt`. Net result: one fewer 5.8M-row file scan, saving ~7–10 s on cold start.

---

# 2026-04-15 Low-Severity Audit Pass

## ✅ `_save_geocode_cache` rewrites entire file on every new geocode — FIXED

**File:** [backend/gtfs_loader.py](backend/gtfs_loader.py)

**Fixed in:** Replaced write-through with a dirty-flag + background-flush approach. A daemon thread calls `_flush_geocode_cache_if_dirty` every 30 s. An `atexit` handler guarantees a final flush on clean shutdown. The expensive atomic-rename write now happens at most once per 30 s.

---

## ✅ `_fetch_bus_chunk` silent exception and `get_train/bus_arrivals` missing error counts — FIXED

**Files:** `backend/cta_client.py`, `backend/main.py`, `frontend/src/App.jsx`

**Fixed in:** `_fetch_bus_chunk` now returns a sentinel `[{"_bus_error": True, "exc": ...}]` on exception. `get_bus_arrivals` and `get_train_arrivals` similarly return `(arrivals, n_errors)`. `main.py` unpacks both tuples and adds error counts to the response dict.

---

## ✅ `_rank_routes` dead `dest_lat`/`dest_lon` parameters — FIXED

**Fixed in:** Removed `dest_lat: float | None = None` and `dest_lon: float | None = None` from `_rank_routes` signature and call site.

---

## ✅ `_response_cache` O(n) eviction — FIXED

**Fixed in:** Changed `_response_cache` from `dict` to `collections.OrderedDict`. Eviction now uses `popitem(last=False)` — O(1) — instead of `min()` over all entries.

---

## ✅ `_rate_store` grows unboundedly — FIXED

**Fixed in:** After the hourly-eviction loop in `_check_rate_limit`, if the deque is now empty, `del _rate_store[ip]` removes the entry.

---

## ✅ BYOK cache collision — FIXED

**Fixed in:** `_cache_key` now accepts a `byok: bool` parameter and appends `"byok"` to the key when True.

---

## ✅ `prdctdn.isdigit()` crashes when API returns `None` — FIXED

**Fixed in:** Changed `prd.get("prdctdn", "")` to `prd.get("prdctdn") or ""`.

---

## ✅ `find_nearest_train_stations` computes Haversine twice per station — FIXED

**Fixed in:** Replaced the double-call with a walrus operator: `if (d := _haversine_miles(...)) <= max_distance_miles`.

---

## ✅ `_save_geocode_counter` lacks atomic rename — FIXED

**Fixed in:** Write to `.counter.tmp` then `tmp.replace(path)`.

---

## ✅ `_normalize_street_abbr` false-matches "St." in saint names — FIXED

**Fixed in:** Added lookahead `(?=\s*(?:,|$))` to `_STREET_ABBR_RE`.

---

## ✅ `fuzzy_match_neighborhood` runs SequenceMatcher over ~300 keys on every miss — FIXED

**Fixed in:** Added `@lru_cache(maxsize=1024)` to `fuzzy_match_neighborhood`.

---

## ✅ `min(G[u][v].values(), ...)` picks zero-length edges — FIXED

**Fixed in:** Changed `d.get("length", 0)` to `d.get("length", float("inf"))` in both `walk_directions` and `walk_path`.

---

## ✅ `walk_directions` fallback misclassifies block type by total distance — FIXED

**Fixed in:** Fallback step always uses `block_type: "long"` and `_LONG_BLOCK_METERS` for block counting.

---

## ✅ `lru_cache` on functions returning mutable lists — DOCUMENTED

**Fixed in:** Added inline comments to `walk_minutes`, `walk_directions`, and `walk_path` noting that `lru_cache` returns the same object on cache hits and callers must not mutate the returned value.

---

## ✅ `get_station_by_name` uncached O(N·M) SequenceMatcher fallback — FIXED

**Fixed in:** Added `@lru_cache(maxsize=512)` to `get_station_by_name`.

---

## ✅ Bus shape lookup relies on `route_short_name == route_id` coincidence — FIXED

**Fixed in:** `_build_shape_lookup` now always writes both `(route_id, direction_id)` and `(short_name, direction_id)` keys unconditionally.

---

## ✅ Pre-allocating `raw = {tid: [] for tid in candidates}` wastes memory — FIXED

**Fixed in:** Both `_stream_stop_sequences` and `get_bus_stop_sequences` now use `defaultdict(list)`.

---

## ✅ Transit edges store dead `all_routes` metadata — FIXED

**Fixed in:** Removed `all_routes=candidates` from `G.add_edge(...)`.

---

## ✅ BYOK API key persisted to `localStorage` in plaintext — FIXED

**Fixed in:** Changed `localStorage` to `sessionStorage` for the BYOK key.

---

## ✅ `busFullness` dead state sent to backend — FIXED

**Fixed in:** Removed the `busFullness` state variable and the `bus_fullness` field from the request body.

---

## ✅ `RouteCard` expanded state doesn't reset on new search — FIXED

**Fixed in:** Added `searchIdRef` (a `useRef` counter incremented on every form submit). `RouteCard` keys are now `${searchIdRef.current}-${i}`.

---

## ✅ `TransitPhoto` onError leaves orphan caption — FIXED

**Fixed in:** Added `const [failed, setFailed] = useState(false)` to `TransitPhoto`. On `onError`, `setFailed(true)` is called and the component returns `null`.

---

## ✅ `clearRouteLayers` silently no-ops when style not loaded — FIXED

**Fixed in:** `clearRouteLayers` now accepts explicit `layerIds` and `sourceIds` arrays tracked in refs inside `MapView`. Removal iterates the tracked lists directly without calling `getStyle()`.

---

# 2026-04-15 Production Deployment Fixes

## ✅ `/recommend` returned 404 on production — `VITE_BACKEND_URL` missing `https://` in Vercel — FIXED

**Fixed in:** Updated the `VITE_BACKEND_URL` environment variable in the Vercel dashboard to include the `https://` protocol prefix and redeployed.

---

## ✅ Preview deployment URLs returned 401 on `manifest.webmanifest` (Vercel Authentication) — FIXED

**Fixed in:** Adjusted Vercel Deployment Protection settings so PWA assets are accessible on preview URLs without authentication.

---

# 2026-04-12 Audit Pass — Fixed 2026-04-13

## ✅ `find_bus_routes` locks in the first arrival's boarding stop per route+direction — FIXED

**Fixed in:** Removed `seen_route_dirs` skip logic. All arrivals for a route+direction are now evaluated, and the candidate with the lowest composite score is kept.

---

## ✅ `get_station_by_name` contains-match fallback returns the first iteration match — FIXED

**Fixed in:** Contains-match fallback now ranks all substring matches by `SequenceMatcher.ratio()` and returns the highest-similarity result.

---

## ✅ `walk_path` geometry reversal heuristic compares longitude only — FIXED

**Fixed in:** Reversal check now computes squared 2-D Euclidean distance from node `u` to each geometry endpoint and reverses only when `du_start > du_end`.

---

## ✅ MapView `styleError` latches `true` on any map error and never resets — FIXED

**Fixed in:** Error handler now only latches when the source is the openmaptiles style document combined with a 4xx/5xx status. A `map.on("data")` listener resets `styleError` to `false` on any successful source load.

---

## ✅ MapView origin/destination dots depend on the first and last leg being walks — FIXED

**Fixed in:** `renderRoute` now accepts `originCoords`/`destCoords` parameters passed from `App.jsx`. Dot placement uses the explicit coords first, falling back to leg path inference only when props are null.

---

## ✅ `_save_geocode_cache` rewrites the full cache on every geocode miss or hit — FIXED

**Fixed in:** `_save_geocode_cache` now writes to a `.tmp` file and atomically renames it over the real file via `Path.replace()`.

---

## ✅ `_geocode_call_counter` never purges old month entries — FIXED

**Fixed in:** `_load_geocode_counter` now prunes on load, retaining only the current `YYYY-MM` key.

---

## ✅ `walk_path` returns a single-point list when origin and destination snap to the same OSM node — FIXED

**Fixed in:** When `len(node_ids) < 2`, `walk_path` now returns `[[origin_lat, origin_lon], [dest_lat, dest_lon]]`.

---

## ✅ Same-station line-change WalkLeg has a single-point `path_points` list — FIXED

**Fixed in:** Transfer `WalkLeg` now uses `path_points=[[blat, blon], [blat, blon]]` (two identical points) and includes `directions=[{"street": "Change trains", ...}]`.

---

## ✅ `bus_fullness` filter with unknown values silently matches empty `psgld` — FIXED

**Fixed in:** `RouteRequest` now includes a `@field_validator` for both `bus_fullness` and `transit_mode` that raises `ValueError` (→ HTTP 422) for values outside the allowed sets.

---

## ✅ `cta_client._fetch_bus_chunk` accepts negative `prdctdn` values — FIXED

**Fixed in:** Guard changed from `prdctdn.lstrip("-").isdigit()` to `prdctdn.isdigit()`.

---

## ✅ `cta_client._fetch_bus_chunk` delay parsing is case-sensitive — FIXED

**Fixed in:** `is_delayed` now uses `str(prd.get("dly", "")).lower() in ("true", "1", "yes")`.

---

## ✅ `find_nearest_bus_stops` uses a hard 0.25-mile radius with no progressive expansion — FIXED

**Fixed in:** `find_nearest_bus_stops` now iterates radii `(0.25, 0.5, 0.75, 1.0)` miles and breaks at the first non-empty result.

---

## ✅ `renderMarkdown` doesn't strip backticks, links, or list markers — FIXED

**Fixed in:** Chain extended with backtick stripping, link stripping, and list/blockquote marker stripping.

---

## ✅ `App.jsx handleSubmit` doesn't trim inputs before POST — FIXED

**Fixed in:** POST body now sends `origin: origin.trim()` and `destination: destination.trim()`.

---

## ✅ `TransitPhoto` has no `onError` fallback for missing images — FIXED

**Fixed in:** `<img>` now has `onError={(e) => { e.currentTarget.style.display = "none"; }}`.

---

## ✅ `App.jsx` in-flight fetch isn't aborted on component unmount — FIXED

**Fixed in:** The existing mount `useEffect` cleanup now also calls `abortRef.current.abort()` on unmount.

---

## ✅ `_load_weekday_service_ids` ignores `calendar_dates.txt` exceptions — FIXED

**Fixed in:** `_load_weekday_service_ids` now also reads `calendar_dates.txt` and augments the weekday set with any `service_id` that has ≥3 `exception_type=1` entries on Mon–Fri.

---

## ✅ `_path_to_route` inner transit-grouping loop treats DEST as an implicit break but reads the edge anyway — FIXED

**Fixed in:** Loop condition tightened to `while look < len(path) - 1 and path[look] != DEST and path[look + 1] != DEST:`.

---

## ✅ `_rank_routes` assumes bearing test won't degenerate when `from_coords == to_coords` — FIXED

**Fixed in:** Explicit guard added: when `dlat == 0.0 and dlon == 0.0`, a warning is logged and the code falls through to `min(dest_map.values())`.

---

## ✅ TransitPhoto remains over the map after an error or zero-route result, blocking map interaction — FIXED

**Fixed in:** Photo fade-out is now triggered unconditionally in both the success branch and the `catch` block.

---

## ✅ Railway GTFS re-download on every deploy — FIXED

**Fixed in:** `force` flag is now exclusively driven by `--force` in `sys.argv`. Non-interactive environments no longer trigger a re-download; pass `--force` explicitly to force a re-download.

---

## ✅ `load_dotenv()` called after module-level imports that read env vars — FIXED

**Fixed in:** `load_dotenv()` moved to before the `from gtfs_loader import ...` line.

---

## ✅ `line-cap` and `line-join` placed in MapLibre `paint` instead of `layout` — FIXED

**Fixed in:** Moved to a `layout` object:
```js
layout: { "line-cap": "round", "line-join": "round" },
paint:  { "line-color": color, "line-width": 5 },
```

---

## ✅ `wait_minutes === 0` ("Due") shows no indicator in RouteCard — FIXED

**Fixed in:** `waitNote` logic now explicitly handles the `0` case with `" · Due now"`.

---

## ✅ No `AbortController` — stale results if user re-submits during a pending search — FIXED

**Fixed in:** Added an `AbortController` ref; the in-flight request is cancelled at the start of each `handleSubmit`.

---

## ✅ PWA service worker pre-caches all PNGs including transit photos — FIXED

**Fixed in:** `globPatterns` now explicitly lists `icon-*.png` and `apple-touch-icon.png`. A `StaleWhileRevalidate` runtime cache for `/transit-photos/` added.

---

## ✅ `renderMarkdown` strips `**bold**` but not `*italic*` — FIXED

**Fixed in:** Added `.replace(/\*([^*]+)\*/g, "$1").replace(/_([^_]+)_/g, "$1")` to the chain.

---

## ✅ `_load_weekday_service_ids()` only checks Monday + Tuesday + Wednesday — FIXED

**Fixed in:** Added `and row.get("thursday", "0").strip() == "1" and row.get("friday", "0").strip() == "1"` to the condition.

---

## ✅ Train arrival datetime: `.replace(tzinfo)` wrong for ISO strings with UTC offset — FIXED

**Fixed in:**
```python
arr_dt = datetime.fromisoformat(arr_str)
if arr_dt.tzinfo is not None:
    arr_dt = arr_dt.astimezone(CHICAGO_TZ)
else:
    arr_dt = arr_dt.replace(tzinfo=CHICAGO_TZ)
```

---

## ✅ Destination walk times computed in wrong direction throughout — FIXED

**Fixed in:** Swapped the argument order in the three affected `walk_minutes()` calls so origin and destination match the direction of travel.

---

## ✅ `validate_and_report()` uses `encoding="utf-8"` instead of `"utf-8-sig"` — FIXED

**Fixed in:** Changed `open(path, encoding="utf-8")` to `open(path, encoding="utf-8-sig")`.

---

## ✅ `G_base.copy()` called on every train routing request — FIXED

**Fixed in:** `find_routes()` now keeps a thread-local copy of `G_base` keyed by `id(G_base)`, created once per executor thread.

---

## ✅ `_coords_for_location()` duplicates fuzzy-match logic from `resolve_location()` — FIXED

**Fixed in:** `fuzzy_match_neighborhood()` extracted as a public module-level helper shared by both functions.

---

## ✅ Redundant `walk_minutes` recomputation for destination stations in `find_routes()` — FIXED

**Fixed in:** The per-station `street_walk_minutes()` call inside the `dest_stations` loop was removed. `dest_walk` is populated once from `dest_stations[*]["walk_minutes"]`.

---

## ✅ `photoFadeTimer` ref not cleared on component unmount — FIXED

**Fixed in:** Added a `useEffect` cleanup:
```js
useEffect(() => {
  return () => { if (photoFadeTimer.current) clearTimeout(photoFadeTimer.current); };
}, []);
```

---

## ✅ Synchronous blocking calls inside async request handler — FIXED

**Fixed in:** Both `resolve_location` calls and `_coords_for_location` calls wrapped in `await loop.run_in_executor(...)`; Anthropic call switched to `AsyncAnthropic.messages.create()`.

---

## ✅ No user-facing message when location is outside coverage area — FIXED

**Fixed in:** Added 400 check after `resolve_location(request.destination)` with explicit coverage area message.

---

## ✅ Anthropic client instantiated on every request — FIXED

**Fixed in:** `AsyncAnthropic` client now instantiated once at module level as `_claude_client`.

---

## ✅ Bus fullness filter may silently return zero results — FIXED + VERIFIED

**Fixed in:** `_fetch_bus_chunk()` normalizes `psgld` at read time via `.replace(" ", "_").upper()`.

**Live API finding (2026-04-09):** `psgld` is consistently empty in all CTA Bus Tracker v3 API responses. The normalization fix is still correct for future-proofing. The Bus Fullness `<select>` in `frontend/src/App.jsx` is commented out but preserved in full.

---

## ✅ Missing validation for CTA_BUS_API_KEY when bus transit mode is requested — FIXED

**Fixed in:** Added a check: if `not bus_key` and `request.transit_mode in ("Bus", "All")`, raise HTTP 500.

---

## ✅ Routing engine exception swallows traceback — FIXED

**Fixed in:** Replaced with `import traceback; traceback.print_exc()`.

---

## ✅ Bus routing may use wrong direction sequence for stops served by multiple directions — FIXED

**Fixed in:** `board_index` type changed from `dict[str, tuple]` to `dict[str, list[tuple]]`; population now uses `setdefault(..., []).append(...)` so all direction entries for a stop are preserved.

---

## ✅ PWA manifest `purpose: "any maskable"` on a single icon entry — FIXED

**Fixed in:** Split into two icon entries with `purpose: "any"` and `purpose: "maskable"` respectively.

---

## ✅ No validation when origin and destination resolve to the same location — FIXED

**Fixed in:** After resolving both locations, checks if the resolved coordinates are within ~100m of each other and returns a 400.

---

## ✅ `osmnx` import inside `try` block masks misconfigured deployments — FIXED

**Fixed in:** `import osmnx as ox` moved to module level; an import failure now raises immediately at startup.

---

## ✅ `max_tokens=750` misaligned with prompt instruction "3-4 sentences" — FIXED

**Fixed in:** `max_tokens` lowered to ~350–400 and the prompt updated to match the intended response length.

---

## ✅ Representative trip selection may use off-peak schedules — FIXED

**Fixed in:** `_load_weekday_service_ids()` added; `_stream_stop_sequences()` selects the trip whose first-stop arrival is closest to noon (720 min) per line/direction.

---

## ✅ No error handling around Claude API call — FIXED

**Fixed in:** `_claude_client.messages.create()` wrapped in try/except; raises HTTP 502 with the error message on any failure.

---

## ✅ Frontend `res.json()` crashes on non-JSON error responses — FIXED

**Fixed in:** Non-OK responses now attempt `res.json()` inside a try/catch; if parsing fails, falls back to `"Service error (502 Bad Gateway)"`.

---

## ✅ Bus stop IDs silently truncated to 10 — no batching — FIXED

**Fixed in:** Extracted `_fetch_bus_chunk()` helper; `get_bus_arrivals()` now splits stop IDs into chunks of 10 and fires all chunks concurrently via `asyncio.gather`.

---

## ✅ `prdctdn` value "APPROACHING" (and similar) silently drops bus arrival — FIXED

**Fixed in:** Replaced `int(prdctdn)` with an `isdigit()` guard; non-numeric values map to `0` minutes.

---

## ✅ `wait=0` conflates "no arrival data" with "train is Due now" — FIXED

**Fixed in:** `_rank_routes()` now initialises `wait: int | None = None` (no data) instead of `0`. `_format_routes()` has three branches: `None` → no note, `0` → Due, `> 0` → N min.

---

## ✅ Bus shape lookup uses `route_short_name` instead of `route_id` — FIXED

**Fixed in:** `_build_shape_lookup()` now reads `routes.txt` to add alias entries for routes where `route_short_name != route_id`.

---

## ✅ Transfer `WalkLeg` missing turn-by-turn directions — FIXED

**Fixed in:** The inter-station transfer `WalkLeg` constructor now includes `directions=street_walk_directions(flat, flon, tlat, tlon)`.

---

## ✅ `geocode_google` not thread-safe under concurrent requests — FIXED

**Fixed in:** Added module-level `_geocode_lock = threading.Lock()`. `geocode_google()` now uses double-checked locking.

---

## ✅ MapLibre map renders as black screen on startup — FIXED (3 root causes)

**Root cause 1:** React StrictMode double-invoke. **Fix:** Wrap map initialization in `setTimeout(0)`.

**Root cause 2:** MapLibre CSS overrides container position. **Fix:** `position: absolute !important` on `.map-container`.

**Root cause 3:** OpenFreeMap Positron style has expression errors in MapLibre v4/v5. **Fix:** Switch tile style URL from `positron` to `liberty`. Also downgraded `maplibre-gl` from `^5.22.0` to `^4.7.1`.

---

## ✅ Map defaults to black panel before first route search — FIXED

**Fixed in:** Changed `DEFAULT_CENTER` to `[-87.654, 41.966]` (Uptown, Chicago) and `DEFAULT_ZOOM` to `13`.

---

## ✅ Walking paths drawn as Haversine straight lines instead of following streets — FIXED

**Fixed in:** Added `scikit-learn>=1.0` to `backend/requirements.txt`. `ox.nearest_nodes()` requires `scikit-learn` for spatial indexing on unprojected graphs; without it, every call raised `ImportError`.

---

## ✅ 4 high-severity npm vulnerabilities in `serialize-javascript` — FIXED

**Fixed in:** Added an npm `overrides` entry to force the patched version:
```json
"overrides": {
  "serialize-javascript": "^7.0.5"
}
```

---

## ✅ Bus transit leg not drawn on map when `clip_shape` returns single-element list — FIXED

**Fixed in:** When `lo >= hi`, return a 2-point straight line between the actual stop coordinates.

---

## ✅ Bus route shown as straight Haversine line — wrong shape selected (short-turn trip) — FIXED

**Fixed in:** Select the shape with the **most points** for each route/direction instead of the first encountered.

---

## ✅ Unclosed file handle in `fetch_gtfs.py` validation step — FIXED

**Fixed in:** Bare `open(path, ...)` replaced with `with open(path, ...) as fh:` context manager.

---

## ✅ Train routing returns no results for addresses >0.5 miles from nearest station — FIXED

**Fixed in:** Both origin and destination station searches now use a progressive-expansion loop: 0.25 → 0.5 → ... → 2.0 miles (+0.25 per step).

---

## ✅ Bus routing returns no results when best exit stop is marginally outside 0.5-mile cutoff — FIXED

**Fixed in:** Replaced the hard 0.5-mile cutoff with a progressive-expansion threshold matching the train station fix (0.25 → 2.0 miles, +0.25 per step).

---

# Technical Debt Paid Off

> **Note on TD numbering:** TD numbers are session-scoped — each scan session assigned numbers starting from a low value, so the same number (e.g. TD-011) may appear in multiple sessions with different meanings. Use the resolution date and description to uniquely identify an entry; do not rely on the number alone across sessions.

---

## 2026-04-27 · TD-033 through TD-037 — Frontend component decomposition and code deduplication

### TD-033 · Photo fade animation logic duplicated in success and error paths — RESOLVED

**File changed:** `frontend/src/App.jsx`

Resolved as a side effect of TD-032 (`fadePhoto()` extraction, same session). The `setPhotoFading(true)` + `setTimeout(…, 1000)` sequence that previously appeared four times (success/catch paths of both `handleSubmit` and `handleReroute`) was already consolidated into `fadePhoto()`. TD-033 was marked resolved at the same time TD-032 was implemented.

---

### TD-034 · Label-save panel UI copy-pasted for location saving and route saving — RESOLVED

**File changed:** `frontend/src/App.jsx`

Extracted a `<LabelSavePanel>` helper component above `LocationInput`. Accepts `value`, `onChange`, `onSave`, `onCancel`, `placeholder`, `showError`, and a `prefix` prop that drives all class names (`${prefix}-save-panel`, `${prefix}-save-input`, `${prefix}-save-btn`, `${prefix}-cancel-btn`). The existing stylesheet uses `label-save-*` for the location panel and `route-label-save-*` for the route panel — the `prefix` prop reproduces both class sets without any CSS changes. Both save panels (location save in `LocationInput`, route save in the main App JSX) now render `<LabelSavePanel …>` instead of their own duplicated input+button+error markup.

---

### TD-035 · `App.jsx` mega-component — favorites state extracted to `useFavorites` hook — RESOLVED

**Files changed:** `frontend/src/App.jsx`, `frontend/src/hooks/useFavorites.js` (new)

Created `frontend/src/hooks/useFavorites.js`. The hook encapsulates all localStorage-backed favorites state that was previously inline in `App`:
- `savedLocations` / `setSavedLocations`
- `savedRoutes` — with `handleDeleteRoute`, `handleToggleSaveRoute`, `handleSaveRoute`
- `showSavedRoutes` / `setShowSavedRoutes`
- `pinnedStops` — with `handleUnpin`, `handlePinToggle`
- Route-save UI state: `savingRoute`, `routeLabelDraft`, `routeLimitError`, plus the `routeLimitTimerRef` timeout

The hook takes `{ origin, destination }` and derives `currentRouteSaved` from them. `pinnedArrivals` data fetching is intentionally excluded — it is managed by `useApiQuery` in `App.jsx` to keep auto-refresh and loading state co-located with the fetch.

`App.jsx` was updated to import `useFavorites` and destructure its return value, replacing nine `useState` declarations, four handler functions, a derived value, and a `useRef`. The `SavedRoutesPanel` prop was refactored from `deleteRoute(id)` direct call to an `onDeleteRoute(id)` callback so `deleteRoute` is no longer imported directly in `App.jsx`.

---

### TD-036 · Three sequential `setActiveLegIndex` calls consolidated into `processTripPosition` — RESOLVED

**File changed:** `frontend/src/App.jsx`

Extracted `processTripPosition(pos, route)` — a pure function (no hook calls) defined at module scope. It encapsulates the full three-pass GPS position logic in one place:
1. **Leg advancement** — reads `activeLegIndexRef.current`, computes advance radius (150 m on transit when on-vehicle, 60 m otherwise), advances the ref and calls `setActiveLegIndex` at most once per tick.
2. **Walk step completion** — calls `setCompletedSteps` for the active walk leg's directions using the advanced index from pass 1.
3. **Off-route detection** — calls `setIsOffRoute` for the active walk leg when outside `suppressRerouteUntil`.

The GPS `userPosition` effect is now a single `processTripPosition(userPosition, route)` call. The three-pass structure is self-documenting via function body; the individual passes can no longer be accidentally reordered or dropped.

---

### TD-037 · MapView `_renderRouteInner` broken into named sub-functions — RESOLVED

**File changed:** `frontend/src/MapView.jsx`

Replaced the monolithic `_renderRouteInner` body with three named sub-functions and a coordinator:

- **`renderPolylines(map, legs, legGeoCoords, legColors, allGeoCoords, layerIds, sourceIds)`** — adds walk (dashed grey) and transit (solid colored) `LineString` layers; accumulates `allGeoCoords` for the subsequent `fitBounds` call.
- **`renderStopMarkers(map, legs, legGeoCoords, legColors, layerIds, sourceIds)`** — adds board/exit circle markers and intermediate stop dots for transit legs.
- **`renderOriginDestMarkers(map, legs, originCoords, destCoords, layerIds, sourceIds)`** — adds the blue origin dot and dark destination dot.

`_renderRouteInner` now precomputes `legColors` and `legGeoCoords`, calls all three functions in order, then does the `fitBounds` auto-fit. The coordinate-math and GL layer construction concerns are now isolated per function.

---

## 2026-04-27 · TD-011 through TD-018 — Backend cleanup, dependency updates, and integration tests

### TD-011 · Stray `=8.0` file in `backend/` — RESOLVED

**Files changed:** `backend/=8.0` (deleted), `.gitignore`

Deleted the artifact file created by a misquoted `pip install pytest>=8.0` command. Added `=*` to the root `.gitignore` with a comment explaining how the pattern prevents future occurrences.

---

### TD-012 · `anthropic` SDK pinned to `==0.40.0` — RESOLVED

**File changed:** `backend/requirements.txt`

Updated pin from `anthropic==0.40.0` to `anthropic>=0.50`. The project uses Claude 4.x model IDs; the ≥0.50 floor ensures prompt caching (TD-013), current tool-use schemas, and model-routing helpers are available.

---

### TD-013 · `_call_claude()` did not use prompt caching — RESOLVED

**File changed:** `backend/main.py`

Extracted the static system instruction into `_CLAUDE_SYSTEM_PROMPT = "You are a helpful Chicago transit assistant."` and passed it to `claude_client.messages.create()` as a `system` block with `"cache_control": {"type": "ephemeral"}`. Removed the "You are a helpful Chicago transit assistant. " prefix from `build_prompt()`'s return value so it is no longer re-sent as user-turn tokens. The 5-minute server-side cache means requests within that window share a cache hit, reducing token spend on every Sonnet call.

---

### TD-014 · `LINE_NAMES` duplicated in `cta_client.py` and `transit_graph.py` — RESOLVED

**File changed:** `backend/transit_graph.py`

Removed the duplicate `LINE_NAMES` dict from `transit_graph.py` and replaced it with `from cta_client import LINE_NAMES`. `cta_client.py` remains the single canonical source. No circular import — `utils.py` sits below both modules in the dependency graph.

---

### TD-015 · `CHICAGO_TZ` defined independently across four modules — RESOLVED

**Files changed:** `backend/utils.py`, `backend/cta_client.py`, `backend/crowdedness.py`, `backend/dau.py`, `backend/main.py`

Added `CHICAGO_TZ = ZoneInfo("America/Chicago")` to `utils.py` as the single canonical definition. All four modules that previously constructed `ZoneInfo("America/Chicago")` independently now import from `utils`:
- `cta_client.py`: `from utils import CHICAGO_TZ` (removed `from zoneinfo import ZoneInfo`)
- `crowdedness.py`: `from utils import CHICAGO_TZ` (removed standalone Timezone section)
- `dau.py`: `from utils import CHICAGO_TZ` (replaced inline `ZoneInfo("America/Chicago")`)
- `main.py`: `from utils import CHICAGO_TZ as _CHICAGO_TZ`; removed `from zoneinfo import ZoneInfo` and the inline `_CHICAGO_TZ = ZoneInfo(...)` definition; removed `CHICAGO_TZ as _CROWD_TZ` from the crowdedness import and replaced its one use with `_CHICAGO_TZ`.

---

### TD-016 · `HIGH_TRAFFIC_BUS_STOPS` always-empty dict in `crowdedness.py` — RESOLVED

**File changed:** `backend/crowdedness.py`

Removed the `HIGH_TRAFFIC_BUS_STOPS: dict[str, float] = {}` dict entirely (it was always empty, so its `.get(stop_id, 1.0)` lookup unconditionally returned `1.0`). Simplified the `ht_mult` expression in `estimate_crowdedness()` to `HIGH_TRAFFIC_TRAIN_STATIONS.get(stop_id, 1.0) if is_train else 1.0`. Kept `_DIRECTION_OVERRIDES` with an expanded comment documenting crosstown route examples (49/Western, 66/Chicago) as candidates for future entries.

---

### TD-017 · `dau.py` used `"default-insecure-salt"` fallback silently — RESOLVED

**File changed:** `backend/dau.py`

Added a module-level startup check: when `_DAILY_SALT == "default-insecure-salt"` and `APP_ENV == "production"`, `logging.getLogger(__name__).warning(...)` emits a loud message explaining that `DAILY_SALT` is not set and cross-day privacy is degraded. Added `import logging` to the imports. Development environments are unaffected (the check only fires in production).

---

### TD-018 · No integration tests for `/recommend` and `/stop-arrivals` — RESOLVED

**File added:** `backend/tests/test_endpoints.py`

Added 8 mock-based integration tests using `fastapi.testclient.TestClient` and `unittest.mock.patch`. No live CTA API calls, no Claude calls, no full GTFS data required.

Covers:
- `TestRecommendEndpoint.test_successful_recommend_returns_expected_shape` — response includes all required keys
- `TestRecommendEndpoint.test_successful_recommend_routes_have_legs` — routes list has legs
- `TestRecommendEndpoint.test_unresolvable_origin_returns_400` — 400 with "Could not find" detail
- `TestRecommendEndpoint.test_ai_disabled_recommendation_is_none` — `recommendation` is `null` when `ai_enabled=false`
- `TestStopArrivalsEndpoint.test_train_stop_returns_correct_structure` — correct nested arrivals dict
- `TestStopArrivalsEndpoint.test_empty_stops_returns_empty_arrivals` — empty input → empty dict
- `TestStopArrivalsEndpoint.test_over_ten_stops_returns_400` — >10 stops → 400
- `TestStopArrivalsEndpoint.test_unknown_stop_type_is_ignored` — unknown prefix silently skipped

---

## 2026-04-27 · TD-038, TD-039, TD-040, TD-041, TD-042 — Frontend patterns, test coverage, and server-state architecture

### TD-038 · No React Query — server state managed manually — RESOLVED

**Approach taken:** Rather than adding TanStack Query as a full dependency (significant bundle cost + migration scope), created a lightweight `useApiQuery` hook (`frontend/src/hooks/useApiQuery.js`) that provides the same core benefits:
- Centralised loading / error state management
- Automatic AbortController cleanup on unmount / dep change
- Background polling via `refetchInterval`
- Stable `refetch()` handle

Applied to the pinned-stop arrivals fetch in `App.jsx`. The board now polls every 60 s automatically; the refresh button uses `refetch()`; `handlePinToggle` no longer needs to call `fetchPinnedArrivals` manually because `pinnedStops` is in the dep array.

**Files changed:** `frontend/src/hooks/useApiQuery.js` (new), `frontend/src/App.jsx` (removed `fetchPinnedArrivals`, removed mount-only useEffect, updated `handlePinToggle`, updated `PinnedStopsBoard onRefresh`)

---

### TD-039 · `localStorage` accessed directly with no error handling — RESOLVED

**What changed:** Created `frontend/src/hooks/useLocalStorage.js` — a `useState`-compatible hook that:
- Initialises from `localStorage` via JSON.parse (catches SyntaxError, returns `defaultValue`)
- Persists every `setValue` call as JSON (silently ignores write failures e.g. quota exceeded, private-browsing restrictions)
- Removes the key from localStorage when value is set to `null`/`undefined`

Applied to `aiEnabled` and `walkSpeed` in `App.jsx`, replacing the raw `localStorage.getItem` initialisers and the manual `localStorage.setItem` calls in `handleAiChange` and `handleWalkSpeedChange`.

**Files changed:** `frontend/src/hooks/useLocalStorage.js` (new), `frontend/src/App.jsx` (replaced two useState+localStorage pairs, removed two manual setItem calls)

---

### TD-040 · No unit tests for `fetchWithRetry` — RESOLVED

**What changed:**
1. Extracted `fetchWithRetry` to `frontend/src/utils/fetchWithRetry.js` so it can be imported independently by tests. The function now takes an explicit `retryDelays` array instead of reading `RETRY_DELAYS_MS` from module scope. App.jsx keeps a thin wrapper that passes `RETRY_DELAYS_MS` by default.
2. Added `frontend/src/tests/fetchWithRetry.test.js` (14 tests) covering: first-attempt success, success after retry, 4xx not retried, 5xx retried exhausted and returned, network error thrown after retries, `onRetrying` callback counts, AbortError propagation, pre-abort signal check.
3. Installed Vitest + jsdom as dev dependencies; added `test` / `test:watch` / `test:coverage` scripts to `package.json`; added `test` config block to `vite.config.js`.

**Files changed:** `frontend/src/utils/fetchWithRetry.js` (new), `frontend/src/tests/fetchWithRetry.test.js` (new), `frontend/src/App.jsx` (inline function replaced with thin wrapper), `frontend/package.json`, `frontend/vite.config.js`

---

### TD-041 · No tests for Feature Trip GPS tracking and off-route detection — RESOLVED

**What changed:**
1. Extracted the four pure geometry helpers from App.jsx module scope into `frontend/src/utils/tripGeometry.js` (`haversineMeters`, `pointToSegmentMeters`, `legEndCoord`, and a new `distanceToPath` helper that encapsulates the inline polyline-scanning loop from the GPS effect).
2. Updated the GPS effect in App.jsx to call `distanceToPath(userPosition, activeLeg.path)` instead of the inline loop.
3. Added `frontend/src/tests/tripGeometry.test.js` (26 tests) covering: haversine distance accuracy, symmetry, same-point edge case; point-to-segment accuracy, perpendicular offset, endpoint clamping, degenerate segment; legEndCoord transit/walk/null cases; distanceToPath empty/single-point/multi-segment paths and the 400 m off-route boundary.

**Files changed:** `frontend/src/utils/tripGeometry.js` (new), `frontend/src/tests/tripGeometry.test.js` (new), `frontend/src/App.jsx` (imports from utils, off-route loop replaced)

---

### TD-042 · No unit tests for `favorites.js` persistence functions — RESOLVED

**What changed:** Added `frontend/src/tests/favorites.test.js` (14 test cases, 54 assertions) covering all public functions with a stubbed in-memory `localStorage`:
- `getSavedLocations` — empty / corrupted JSON fallback
- `saveLocation` — round-trip, MAX_ITEMS cap, boundary at 9
- `deleteLocation` — removes by id, persists, no-op on missing id
- `saveRoute` / `deleteRoute` — analogous coverage
- `pinStop` — round-trip, duplicate stop_id skipped, MAX_ITEMS cap
- `unpinStop` — removes by id, persists
- `isStopPinned` — reflects pin / unpin state

**Files changed:** `frontend/src/tests/favorites.test.js` (new)

---

---

## 2026-04-27 · TD-043 through TD-047 — Frontend code quality, error resilience, and i18n — RESOLVED

### 🟡 TD-043 · `eslint-disable-next-line` in App.jsx useEffect lacks explanation — RESOLVED

**File:** [frontend/src/App.jsx](frontend/src/App.jsx)

**What it was:** A `// eslint-disable-next-line react-hooks/exhaustive-deps` comment before the pinned-stop arrivals `useEffect` had no explanation, leaving reviewers unable to tell which dependency was intentionally omitted or why.

**Fixed by:** Expanded the comment above the suppression to explain that `pinnedStops` and `fetchPinnedArrivals` are intentionally omitted — the effect runs once on mount to pre-fetch arrivals; including them would re-fetch on every pin/unpin interaction (manual refresh is via the board's refresh button).

---

### 🟡 TD-044 · Three `eslint-disable-line` suppressions in MapView.jsx have no explanation — RESOLVED

**File:** [frontend/src/MapView.jsx](frontend/src/MapView.jsx)

**What it was:** Three `// eslint-disable-line react-hooks/exhaustive-deps` inline comments in the three MapView `useEffect` blocks had no explanation for why their dependency arrays are intentionally incomplete.

**Fixed by:** Added one explanatory comment above each suppression:
1. Map-init effect (`[]`): props (style, center, zoom) are construction-time values; re-running would destroy and recreate the WebGL context.
2. Route-render effect (`[route, originCoords, destCoords]`): `renderRoute` and `clearRouteLayers` are stable module-level functions; `routeLayerIds`/`routeSourceIds` are refs.
3. User-position effect (`[tripActive, userPosition]`): `mapRef` and `userPosLayerRef` are refs, not reactive values.

---

### 🔴 TD-045 · No React error boundary — unhandled render errors crash the whole app — RESOLVED

**Files:** [frontend/src/components/ErrorBoundary.jsx](frontend/src/components/ErrorBoundary.jsx) *(new)*, [frontend/src/main.jsx](frontend/src/main.jsx)

**What it was:** The React tree had no error boundary. A runtime error in any component (unexpected null from the backend, MapLibre failure, etc.) produced a blank white screen with no recovery path.

**Fixed by:** Created `frontend/src/components/ErrorBoundary.jsx` — a class-based `ErrorBoundary` with `getDerivedStateFromError` and `componentDidCatch` that renders a friendly fallback UI (bus emoji, "Something went wrong", and a "Refresh page" button styled in the app's dark-blue palette). Wrapped `<App>` in `<ErrorBoundary>` in `main.jsx`. Errors are logged via `componentDidCatch` for debugging.

---

### 🟡 TD-046 · `PinnedStopsBoard` renders hardcoded English strings — RESOLVED

**Files:** [frontend/src/components/PinnedStopsBoard.jsx](frontend/src/components/PinnedStopsBoard.jsx), all 22 locale files

**What it was:** "Pinned Stops", "No arrivals", and "Last train in {N} min" were hardcoded English strings, bypassing the i18next layer used by every other component.

**Fixed by:** Added `useTranslation` to `PinnedStopsBoard.jsx` and replaced the three strings with `t("pinned_stops_heading")`, `t("no_arrivals")`, and `t("last_train_in", { min: lastMin })`. Added all three keys with translations to all 22 locale files.

---

### 🟡 TD-047 · `RouteCard` pin/unpin button labels are hardcoded English — RESOLVED

**Files:** [frontend/src/components/RouteCard.jsx](frontend/src/components/RouteCard.jsx), all 22 locale files

**What it was:** The `title` and `aria-label` on the pin/unpin button used template-literal English (`Pin ${leg.from}` / `Unpin ${leg.from}`) that could not be translated with interpolation.

**Fixed by:** Added `useTranslation` to `RouteLegs` and replaced both attributes with `t("pin_stop", { stop: leg.from })` and `t("unpin_stop", { stop: leg.from })`. Added `pin_stop` and `unpin_stop` with `{{stop}}` interpolation to all 22 locale files.

---

## 🔴 TD-011 · No automated test suite — zero coverage — RESOLVED

**Files added:** `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_utils.py`, `backend/tests/test_transit_graph.py`, `backend/tests/test_main_helpers.py`, `backend/tests/test_gtfs_loader.py`

**What it was:** The project had zero automated tests — no `tests/`, `.test.py`, or `.test.js` files anywhere. Any change to routing logic, geocoding, or the API contract could break silently with no safety net.

**How it was resolved:** Created a `backend/tests/` pytest suite with **147 tests** covering the highest-risk pure functions across all four backend modules. The suite runs in ~4 seconds without GTFS files, CTA API keys, or a running server.

Test files and what they cover:

- **`test_utils.py`** (19 tests) — `haversine_miles` and `SpatialGrid`.
- **`test_transit_graph.py`** (56 tests) — `_bearing_to_direction`, `_parse_gtfs_time`, `clip_shape`, `Route` / `WalkLeg` / `TransitLeg` dataclasses, `_dedup_stations_by_line`.
- **`test_main_helpers.py`** (51 tests) — `_cache_key`, `_check_rate_limit`, `_is_simple_query`, `_alert_ids_from_routes`, `build_prompt`, `_format_routes`, `RouteRequest` Pydantic validators.
- **`test_gtfs_loader.py`** (21 tests) — `_normalize_street_abbr`, `fuzzy_match_neighborhood`.

`conftest.py` adds `backend/` to `sys.path` and creates header-only GTFS stub files in `backend/gtfs_data/` if the feed is absent (CI safety net).

Run the suite from `backend/` with: `python -m pytest tests/ -v`

**Date resolved:** 2026-04-24

---

## 🔴 TD-019 · `BACKEND_URL` hardcoded to `localhost:8000` as fallback — RESOLVED

**Files changed:** `frontend/src/App.jsx`, `frontend/.env.example` (created)

**What it was:** `BACKEND_URL` fell back to `http://localhost:8000` if `VITE_BACKEND_URL` was unset. No `.env.example` existed to document that the env var was required, so a developer cloning the repo for the first time would not know to configure it. A forgotten env var in production would silently route all API calls to localhost.

**How it was resolved:** Created `frontend/.env.example` documenting both `VITE_BACKEND_URL` and `VITE_BYOK_ENABLED` with explanatory comments. Added a code comment on the `BACKEND_URL` line in `App.jsx` explaining when the fallback applies and pointing at the example file. The `.env.local` (gitignored) and `.env.production` (committed) already exist; `.env.example` closes the documentation gap for new contributors.

**Date resolved:** 2026-04-27

---

## 🟡 TD-020 · Off-route detection threshold (400 m) is a magic number — RESOLVED

**Files changed:** `frontend/src/constants.js`, `frontend/src/App.jsx`

**What it was:** `setIsOffRoute(minDist > 400)` — the 400-meter threshold was embedded in logic with no name or rationale.

**How it was resolved:** Exported `OFF_ROUTE_THRESHOLD_METERS = 400` from `constants.js` with a comment explaining the value (chosen to avoid false positives on typical Chicago city blocks ~200 m apart while still triggering early enough to be useful). `App.jsx` now imports and uses the named constant.

**Date resolved:** 2026-04-27

---

## 🟡 TD-021 · Geolocation options duplicated with inconsistent `maximumAge` — RESOLVED

**Files changed:** `frontend/src/constants.js`, `frontend/src/App.jsx`

**What it was:** Geolocation options were defined inline in two places — `handleGeoClick` (`maximumAge: 30000`) and `startTrip` (`maximumAge: 15000`) — with the divergence silent and undocumented.

**How it was resolved:** Exported `GEO_OPTIONS` and `TRIP_GEO_OPTIONS` from `constants.js` with comments explaining why their `maximumAge` values differ (30 s tolerates a cached fix for one-shot detection; 15 s requires fresher fixes during live trip tracking). Both `handleGeoClick` and `startTrip` in `App.jsx` now reference the named constants.

**Date resolved:** 2026-04-27

---

## 🟢 TD-022 · Retry delay array `[1000, 2000, 4000]` is a magic number array — RESOLVED

**Files changed:** `frontend/src/constants.js`, `frontend/src/App.jsx`

**What it was:** The exponential back-off delays were stored in a private-scoped `_RETRY_DELAYS` constant local to `App.jsx`, undocumented and not importable by other modules.

**How it was resolved:** Moved the constant to `constants.js` and renamed it `RETRY_DELAYS_MS` (following the naming convention of `BYOK_IDLE_TIMEOUT_MS`, etc.). `App.jsx` now imports and uses `RETRY_DELAYS_MS`. The `fetchWithRetry` comment was updated to reference the named constant.

**Date resolved:** 2026-04-27

---

## 🟡 TD-023 · BYOK API key format validated with hardcoded prefix — RESOLVED

**Files changed:** `frontend/src/constants.js`, `frontend/src/components/SettingsPanel.jsx`

**What it was:** `SettingsPanel.jsx` validated the BYOK key with an inline `draft.trim().startsWith("sk-ant-")` predicate. If Anthropic changes the key format, the check would silently reject valid keys or accept invalid ones, with no indication of where to update the logic.

**How it was resolved:** Extracted to `isValidByokKey(key)` in `constants.js` with a comment noting the `sk-ant-` prefix should be revisited when the Anthropic SDK is upgraded. `SettingsPanel.jsx` now imports and calls `isValidByokKey(draft)`.

**Date resolved:** 2026-04-27

---

## 🟢 TD-024 · `MAX_ITEMS = 10` in favorites has no documented rationale — RESOLVED

**Files changed:** `frontend/src/favorites.js`

**What it was:** The 10-item cap on saved locations, routes, and pinned stops was unexplained. A developer could raise or remove the limit without understanding it was chosen for localStorage payload size and dropdown scannability.

**How it was resolved:** Added a one-line comment above `MAX_ITEMS` explaining the rationale (small localStorage payload, list fits on screen without scrolling).

**Date resolved:** 2026-04-27

---

## 🟡 TD-025 · Reroute suppression duration (90 s) is a magic number — RESOLVED

**Files changed:** `frontend/src/constants.js`, `frontend/src/App.jsx`

**What it was:** `suppressRerouteUntil.current = Date.now() + 90_000` — the 90-second window after the user dismisses the off-route banner was an unexplained inline literal.

**How it was resolved:** Exported `REROUTE_SUPPRESSION_MS = 90_000` from `constants.js` with a comment explaining the value (long enough for a deliberate crossing or detour before re-evaluation). `App.jsx` now imports and uses the named constant.

**Date resolved:** 2026-04-27

---

## 🔴 TD-026 · BYOK idle-clear timeout (30 min) is a security-relevant magic number — RESOLVED

**Files changed:** `frontend/src/constants.js`, `frontend/src/App.jsx`

**What it was:** The auto-clear timer for the BYOK API key used the inline literal `30 * 60 * 1000` with no explanation. Silently changing the value could cause keys to persist longer than intended on shared devices.

**How it was resolved:** Exported `BYOK_IDLE_TIMEOUT_MS = 30 * 60 * 1000` from `constants.js` with a security-rationale comment (30 minutes balances active-session usability against exposure on unattended devices; do not raise without a security review). `App.jsx` now imports and uses the named constant.

**Date resolved:** 2026-04-27

---

## 🟡 TD-027 · `LocationInput` lacks documentation of its state-management flow — RESOLVED

**Files changed:** `frontend/src/App.jsx`

**What it was:** `LocationInput` is a 254-line component with debounced autocomplete, abort signals, a 150 ms blur timeout, and saved-location interleaving. The state flow was entirely undocumented, making the component hard to reason about or modify safely.

**How it was resolved:** Added a comment block at the component definition explaining the five-stage flow: (1) Editing with 200 ms debounce + AbortController cancellation; (2) Autocomplete result navigation; (3) Saved-location dropdown that collapses when autocomplete results appear; (4) Star/save toggling; (5) The 150 ms blur `setTimeout` and why it exists (React synthetic-event ordering — lets `onMouseDown` fire before the list unmounts).

**Date resolved:** 2026-04-27

---

## 🔴 TD-028 · Feature Trip implementation lacks explanation of leg-advancement algorithm — RESOLVED

**Files changed:** `frontend/src/App.jsx`

**What it was:** The GPS `useEffect` block (190 lines) handled leg advancement, walk-step completion, and off-route detection via three sequential passes with no explanation of why they're separate or how each trigger condition works. The algorithm was hard to modify safely.

**How it was resolved:** Added a 25-line comment block directly above the `useEffect` explaining: (1) leg advancement — proximity radius, why `activeLegIndexRef` is used instead of state, and the wider 150 m radius when "on vehicle" is toggled; (2) walk-step completion — the 30 m trigger and the `"legIdx-stepIdx"` key format; (3) off-route detection — `pointToSegmentMeters` usage and the suppression timer; (4) why three independent passes are used instead of a single return-early chain.

**Date resolved:** 2026-04-27

---

## 🟢 TD-029 · `renderMarkdown` regex chain has no explanation of what each pattern removes — RESOLVED

**Files changed:** `frontend/src/App.jsx`

**What it was:** Seven `.replace()` calls stripped markdown formatting with no inline comments indicating which markdown element each regex handled.

**How it was resolved:** Added a trailing inline comment to each of the seven `.replace()` calls (e.g. `// strip bold **text**`, `// strip link [label](url) → label`).

**Date resolved:** 2026-04-27

---

## 🟡 TD-030 · `fetchWithRetry` JSDoc missing 4xx vs 5xx distinction and abort-signal behaviour — RESOLVED

**Files changed:** `frontend/src/App.jsx`

**What it was:** The comment block above `fetchWithRetry` mentioned retrying on 5xx errors and not retrying on AbortError, but did not explain *why* 4xx errors are not retried, what the `onRetrying` callback signature is, or how the AbortSignal propagates through the retry loop.

**How it was resolved:** Replaced the brief three-line comment with a proper JSDoc block that documents all three parameters (`url`, `options`, `onRetrying` with callback signature), and a "Retry policy" section explaining: 5xx/network retries with back-off, 4xx non-retry rationale (client errors won't self-resolve), AbortError non-retry rationale (explicit cancellation), and exhausted-retries behaviour (last Response returned to caller).

**Date resolved:** 2026-04-27

---

## 🟡 TD-031 · StrictMode double-invoke workaround in MapView initialisation has a vague comment — RESOLVED

**Files changed:** `frontend/src/MapView.jsx`

**What it was:** The `setTimeout(0)` workaround in the MapView init `useEffect` had a comment that mentioned WebGL context issues and StrictMode but did not explain *why* WebGL2 contexts are not released synchronously, *how* the timer mechanism ensures only the second invocation survives, or that the issue is development-only.

**How it was resolved:** Expanded the comment to explain: (1) why the context isn't released synchronously (WebGL2 teardown is deferred to the browser's GPU process, not the JS thread); (2) the exact timer-survival mechanism (StrictMode's cleanup calls `clearTimeout` synchronously on the first timer before it fires; only the second timer reaches the task queue); (3) that the issue is development-only (StrictMode is inactive in production builds, so the `setTimeout` adds no observable latency there).

**Date resolved:** 2026-04-27

---

## 🔴 TD-032 · `/recommend` API call logic duplicated between `handleSubmit` and `handleReroute` — RESOLVED

**Files changed:** `frontend/src/App.jsx`

**What it was:** ~60 lines of identical logic — building the same request body, calling `fetchWithRetry`, checking `res.ok`, parsing the JSON, and calling `setResult` — existed in both `handleSubmit` and `handleReroute`. Any change to the API call shape, error handling, or result mapping had to be applied in two places. In addition, the photo fade logic (4 occurrences: success and catch paths of both handlers) was also duplicated.

**How it was resolved:** Extracted `callRecommendAPI(originStr)` — a shared async function closed over the App component's state/refs — that owns the `fetchWithRetry` call, error parsing, and `setResult`. Also extracted `fadePhoto()` to own the `setPhotoFading` + 1 s `setTimeout` logic. Both `handleReroute` and `handleSubmit` now call `await callRecommendAPI(...)` and `fadePhoto()`, reducing each handler's try/catch body from ~30 lines to 4.

**Date resolved:** 2026-04-27

---

## 🔴 TD-001 · Haversine distance formula duplicated in three files — RESOLVED

**Files affected:** `backend/walking.py`, `backend/gtfs_loader.py`, `backend/transit_graph.py`, `backend/fetch_station_exits.py`

**How it was resolved:** Created `backend/utils.py` with a single canonical `haversine_miles(lat1, lon1, lat2, lon2) -> float`. All four files now import it as `from utils import haversine_miles as _haversine_miles`.

**Date resolved:** 2026-04-20

---

## 🔴 TD-002 · `recommend()` endpoint was 325 lines doing 10+ distinct tasks — RESOLVED

**File affected:** `backend/main.py`

**How it was resolved:** Decomposed into seven focused helpers: `_validate_api_keys`, `_resolve_locations`, `_fetch_arrivals`, `_run_routing`, `_fetch_transfer_arrivals`, `_call_claude`, `_format_response`. `recommend()` itself became an ~85-line thin coordinator.

**Date resolved:** 2026-04-20

---

## 🔴 TD-003 · Pre-production geocode rate-limit guard still in production code — RESOLVED

**File affected:** `backend/gtfs_loader.py` (~lines 60–66)

**How it was resolved:** Promoted the guard to a first-class production feature. The hardcoded `_GEOCODE_CALL_LIMIT = 9_500` was replaced with `int(os.getenv("GEOCODE_MONTHLY_LIMIT", "9500"))`, making the limit configurable via Railway env var. Set to `0` to disable the cap entirely.

**Date resolved:** 2026-04-20

---

## 🟡 TD-004 · Claude model names hardcoded — cannot be changed without a code deploy — RESOLVED

**File affected:** `backend/main.py` (inside `_call_claude`)

**How it was resolved:** `_call_claude` now reads `os.getenv("CLAUDE_SIMPLE_MODEL", "claude-haiku-4-5-20251001")` and `os.getenv("CLAUDE_COMPLEX_MODEL", "claude-sonnet-4-6")` at call time.

**Date resolved:** 2026-04-20

---

## 🟡 TD-006 · Chicago bounding box hardcoded in three separate files — RESOLVED

**Files affected:** `backend/utils.py`, `backend/gtfs_loader.py`, `backend/fetch_station_exits.py`, `backend/fetch_street_graph.py`

**How it was resolved:** Added canonical corner constants (`CHICAGO_SOUTH/NORTH/WEST/EAST`) and four derived format-specific constants (`CHICAGO_BBOX_GOOGLE`, `CHICAGO_BBOX_OVERPASS`, `CHICAGO_BBOX_OSMNX`, `STREET_GRAPH_BBOX_OSMNX`) to `backend/utils.py`. Each of the three files now imports the relevant constant.

**Date resolved:** 2026-04-20

---

## 🟡 TD-007 · Inconsistent error sentinels from `cta_client.py` — RESOLVED

**Files affected:** `backend/cta_client.py`

**How it was resolved:** Standardised on a single sentinel shape `{"_error": True, "exc": str, "mode": "train"|"bus"}` across both transport modes.

**Date resolved:** 2026-04-20

---

## 🟡 TD-008 · Alerts API silently returns `[]` on any exception — RESOLVED

**Files affected:** `backend/cta_client.py`

**How it was resolved:** Changed the except clause to `except Exception as exc:` and added `print(f"[cta_client] WARNING: Alerts API fetch failed for route {route_id!r}: {exc}")` before returning `[]`.

**Date resolved:** 2026-04-20

---

## 🟡 TD-009 · `find_bus_transfer_routes()` is 303 lines mixing two distinct passes — RESOLVED

**File affected:** `backend/transit_graph.py` (~lines 1575–1878)

**How it was resolved:** Split into two private helpers: `_select_transfer_candidates()` (Pass 1, pure haversine/spatial filtering) and `_build_transfer_routes()` (Pass 2, Route object assembly with OSMnx walk calls). `find_bus_transfer_routes()` is now a thin coordinator.

**Date resolved:** 2026-04-20

---

## 🟡 TD-005 · CTA API base URLs hardcoded in two files — RESOLVED

**Files affected:** `backend/cta_client.py` (~lines 22–23), `backend/active_routes.py` (~lines 47–48)

**How it was resolved:** Both files now derive base URLs from `os.getenv("CTA_TRAIN_API_URL", ...)` and `os.getenv("CTA_BUS_API_URL", ...)`.

**Date resolved:** 2026-04-20

---

## 🟡 TD-010 · Two independent spatial-grid implementations with no shared base — RESOLVED

**Files affected:** `backend/utils.py`, `backend/gtfs_loader.py`, `backend/transit_graph.py`

**How it was resolved:** Added a generic `SpatialGrid` class to `backend/utils.py`. Both `gtfs_loader.py` and `transit_graph.py` now import it; their independent implementations were removed.

**Date resolved:** 2026-04-20

---

## 🟢 TD-011 · Magic numbers scattered throughout backend with no config or documentation — RESOLVED

**Files affected:** `backend/main.py`, `backend/transit_graph.py`

**How it was resolved:** Named constants added at module level in two named sections in `transit_graph.py`. Created `backend/config.py` as the single authoritative source for all routing parameters with 16 named constants across four categories, all supporting env-var overrides.

**Date resolved:** 2026-04-20 / 2026-04-24

---

## 🟢 TD-012 · `lru_cache` on functions returning mutable lists — caller must not mutate — RESOLVED

**File affected:** `backend/walking.py`

**How it was resolved:** Both cached functions renamed to private implementations (`_walk_directions_impl`, `_walk_path_impl`) that return immutable containers (tuples). Public wrappers `walk_directions` and `walk_path` (not cached) return a fresh list on every invocation.

**Date resolved:** 2026-04-20

---

## 🟢 TD-013 · Module-level mutable globals managed with `global` statements in `transit_graph.py` — RESOLVED

**File affected:** `backend/transit_graph.py`

**How it was resolved:** Added a "Module-level state — initialization contract" comment block before the state variables enumerating all six globals, their initializer, and their lifecycle phase.

**Date resolved:** 2026-04-20

---

## 🟢 TD-014 · `fetch_street_graph.py` bounding box expansion left as a TODO — RESOLVED

**File affected:** `backend/utils.py`

**How it was resolved:** The one-line TODO was replaced with a multi-line expansion guide documenting: current coverage bounds, target expansion coordinates, and a four-step checklist (verify Railway RAM headroom, lower constants, re-run `fetch_street_graph.py`, redeploy).

**Date resolved:** 2026-04-20

---

## 🟡 TD-012 · Magic numbers scattered throughout codebase — RESOLVED

**Files affected:** `backend/transit_graph.py`, `backend/cta_client.py`, `backend/walking.py`

**How it was resolved:** Created `backend/config.py` as the single authoritative source for all routing parameters. The file defines 16 named constants across four categories, each with a comment explaining purpose, units, and typical range. All constants support env-var overrides. `cta_client.py` replaced its inline `6` and `8` literals with `_cfg.CTA_MAX_ARRIVALS_PER_STATION` and `_cfg.CTA_API_TIMEOUT_SECONDS`.

**Date resolved:** 2026-04-24

---

## 🟡 TD-013 · App.jsx was 1,165 lines containing 6 inline sub-components — RESOLVED

**File affected:** `frontend/src/App.jsx`

**How it was resolved:** Created `frontend/src/components/` and extracted all six components into four files: `TransitPhoto.jsx`, `RouteCard.jsx`, `SettingsPanel.jsx`, `LoadingSkeleton.jsx`. `App.jsx` was reduced by ~250 lines.

**Date resolved:** 2026-04-24

---

## 🟢 TD-014 · Frontend fetch had no retry logic — transient 5xx failures required manual re-submit — RESOLVED

**File affected:** `frontend/src/App.jsx`

**How it was resolved:** Added `fetchWithRetry(url, options, onRetrying)` helper. It retries up to 3 times (1 s → 2 s → 4 s delays) on network failures and HTTP 5xx responses. 4xx errors and `AbortError` are not retried. During each retry, `onRetrying` is called to update the error state with "Network error — retrying... (N/3)".

**Date resolved:** 2026-04-24

---

## 🟢 TD-015 · Geocoding cache had no age-based eviction — entries accumulated indefinitely — RESOLVED

**File affected:** `backend/gtfs_loader.py`

**How it was resolved:** Added two complementary garbage-collection mechanisms:

1. **Age-based eviction with sidecar file** — New geocode entries record their Unix insertion timestamp in `geocode_cache_ages.json`. Entries older than `GEOCODE_MAX_AGE_DAYS` (90 days, configurable via env var) are evicted at startup, weekly in background, and on compaction.

2. **Weekly background sweep** — `_flush_geocode_cache_if_dirty()` now also calls `_evict_old_geocode_entries()` once per `GEOCODE_EVICT_INTERVAL_SECONDS` (default: 7 days).

**Date resolved:** 2026-04-24

---

## 🔴 TD-048 · Off-route banner text is hardcoded English — RESOLVED

**Files changed:** `frontend/src/App.jsx`, all 22 locale files

**What it was:** "You appear to be off your planned route.", "Re-route from here", and "Dismiss" were hardcoded English strings in the off-route banner. Non-English users saw untranslated text at a critical navigation moment even though the rest of the app uses i18next.

**How it was resolved:** Added three i18n keys — `trip_off_route_message`, `trip_reroute_btn`, `trip_dismiss_btn` — to all 22 locale files (en, es, fr, it, pl, ro, uk, ru, zh, yue, ja, ko, tl, vi, hi, gu, pa, ne, ur, ar, ps, yo) and replaced the three hardcoded string literals in `App.jsx` with `{t("trip_off_route_message")}`, `{t("trip_reroute_btn")}`, and `{t("trip_dismiss_btn")}`.

**Date resolved:** 2026-04-27

---

## 🟡 TD-049 · `SettingsPanel` contains hardcoded English UI strings — RESOLVED

**Files changed:** `frontend/src/components/SettingsPanel.jsx`, all 22 locale files

**What it was:** Three strings in `SettingsPanel.jsx` were hardcoded English: the "AI Explanation" toggle label, the hint paragraph ("When on, Claude adds a plain-English summary…"), and the BYOK security notice. All other settings panel strings already used `t()`.

**How it was resolved:** Added three i18n keys — `settings_ai_explanation_label`, `settings_ai_explanation_hint`, `settings_byok_security_notice` — to all 22 locale files and replaced the hardcoded strings in `SettingsPanel.jsx` with `t()` calls. The `<strong>` wrapper around the security notice was removed; the `⚠` character and label are now part of the translated string, consistent with how other hint text is rendered.

**Date resolved:** 2026-04-27

---

## 🟢 TD-050 · `jsconfig.json` has `"strict": false` — IDE type checking weakened — RESOLVED

**Files changed:** `frontend/jsconfig.json`

**What it was:** `"strict": false` in the `compilerOptions` block disabled strict TypeScript/JSDoc checking in the IDE language server, reducing null-reference detection and other static analysis.

**How it was resolved:** Changed `"strict": false` to `"strict": true`. No new IDE errors surfaced after the change, confirming the existing codebase is already compatible with strict mode.

**Date resolved:** 2026-04-27

---

# Efficiency Improvements Implemented

---

# 2026-04-28 OPT-024 through OPT-028 · Five efficiency improvements to `fetch_station_exits.py` — IMPLEMENTED

**File changed:** `backend/fetch_station_exits.py`

## OPT-024 · Skip full M×N arcsin computation using monotonic argmin shortcut

`arcsin`, `sqrt`, and multiply-by-positive-constant are all monotonically increasing, so `argmin` and `min` on the raw haversine intermediate `a` produce the same nearest-station result as operating on the full `dist` matrix. The M×N arcsin/sqrt/multiply pass is now skipped entirely; only the M winning values (one per entrance) are converted to miles for the threshold test. Replaces ~39 K arcsin calls with ~260.

## OPT-025 · Replace fancy-index gather with `a.min(axis=1)`

`dist[np.arange(len(valid)), best_idx]` allocated a temporary arange array solely to gather per-row minimum values. Replaced with `a.min(axis=1)`, which is semantically equivalent (the minimum value of a row is the value at that row's argmin index) and avoids the allocation. This naturally follows from OPT-024 since the operation now runs on `a` rather than `dist`.

## OPT-026 · Convert `best_idx` to a Python list before the assignment loop

`int(best_idx[i])` inside the for-loop incurred numpy scalar boxing overhead on every iteration. A single `.tolist()` call before the loop converts the entire array to Python ints upfront, eliminating the per-iteration cast.

## OPT-027 · Cache raw Overpass API response to disk

The raw JSON response from the Overpass API is now written to `backend/.overpass_cache.json` after the first successful fetch. Subsequent runs load from the cache and skip the network request and polite sleep entirely, making re-runs during development (e.g. tuning `MAX_ASSIGN_MILES` or matching logic) instantaneous. The file is `.gitignore`d. Delete it to force a fresh OSM query.

## OPT-028 · Free M×N intermediate arrays after use

`del dlat, dlon` is called immediately after `a` is computed, and `del a` and `del best_a` are called as soon as each is no longer needed. This reduces peak memory by releasing the largest intermediate arrays before new ones are allocated.

---

# 2026-04-28 OPT-018 through OPT-023 · Six efficiency improvements to `fetch_gtfs.py` — IMPLEMENTED

**File changed:** `backend/fetch_gtfs.py`

## OPT-018 · Eliminated redundant HEAD request

Removed the separate `HEAD` request that was made solely to read `Content-Length` for the progress message. The `Content-Length` header is available on the `GET` response itself; it is now read there instead, eliminating a full round-trip before every download.

## OPT-019 · Increased download chunk size from 64 KB to 1 MB

Raised `chunk_size` from `64 * 1024` (64 KB) to `1024 * 1024` (1 MB). For a multi-megabyte GTFS zip, this cuts loop iterations by 16× with no change to the downloaded bytes or progress reporting.

## OPT-020 · Removed `shutil.rmtree` before re-download (in-place overwrite)

Removed the `shutil.rmtree(GTFS_DIR)` calls that preceded every re-download. Extraction now overwrites the existing files in place. This is safe in combination with OPT-021 (selective extraction), which ensures exactly the 8 expected files are written and no stale extras accumulate. The `shutil` import was also removed as it was no longer needed.

## OPT-021 · Selective extraction of only EXPECTED_FILES

Replaced `zf.extractall(GTFS_DIR)` with an explicit loop over `EXPECTED_FILES` that calls `zf.extract(filename, GTFS_DIR)` for each file present in the zip. The backend only reads the 8 files in `EXPECTED_FILES` (confirmed by audit), so extracting extras was pure wasted I/O.

## OPT-022 · Batched `stat()` calls in `validate_and_report` via `os.scandir`

Replaced the per-file `path.stat()` calls inside the validation loop with a single `os.scandir(GTFS_DIR)` pass that collects all `DirEntry.stat()` results into a dict upfront. All 8 membership and size checks then operate against the in-memory dict.

## OPT-023 · Replaced `glob("*.txt")` sentinel check with single file existence test

Replaced `any(GTFS_DIR.glob("*.txt"))` — which triggers a full directory scan — with `(GTFS_DIR / "stops.txt").exists()`. `stops.txt` is the most critical GTFS file and is always present in a complete download, making it a reliable sentinel.

---

# 2026-04-28 OPT-013 through OPT-016 · Four efficiency improvements to `dau.py` — IMPLEMENTED

**File changed:** `backend/dau.py`

## OPT-013 · Cached daily HMAC key

Added module-level `_today_hmac_key: bytes = b""`. Previously `(_DAILY_SALT + today).encode()` was string-concatenated and encoded on every unique visit. The key now recomputes once per day inside the day-rollover block alongside `_current_day`, eliminating per-visit allocation and encoding.

## OPT-014 · `digest()` instead of `hexdigest()` for `_seen_hashes`

`_seen_hashes` previously stored 64-character hex strings (one per unique visitor today). Changed to `.digest()`, storing 32-byte `bytes` objects instead — halving per-entry memory. The set is never persisted to disk, so there is no compatibility concern; only the integer counts reach `dau.json`.

## OPT-015 · `_load()` offloaded to thread executor on day rollover

`_load()` was a synchronous blocking file read called directly inside `async with _lock` on day rollover. Changed to `await loop.run_in_executor(None, _load)`, consistent with the existing treatment of `_save()`. The lock is still held during the await (asyncio Lock semantics), so no data race is introduced.

## OPT-016 · `time.monotonic()` deferred via short-circuit evaluation

Previously `now = time.monotonic()` was unconditionally called before the flush condition check on every new unique visit. Restructured the condition to `_visitors_since_last_flush >= _DAU_WRITE_BATCH or time.monotonic() - ...` so Python's short-circuit OR skips the `time.monotonic()` call when the batch threshold fires. A second `time.monotonic()` call inside the block captures an accurate `_last_flush_time` after the save completes.

---

# 2026-04-28 OPT-009 · Five micro-optimisations to `fetch_station_exits.py` — IMPLEMENTED

**File changed:** `backend/fetch_station_exits.py`

## Combined filter + array extraction (change 4)
The `valid` list comprehension and three separate list comprehensions for `e_rlat`, `e_rlon`, and `e_cos_lat` were replaced with a single `for` loop that simultaneously filters entrances and accumulates the lat/lon lists. Eliminates three extra iterations over the entrance list.

## Single-pass station array extraction (change 3)
Three separate list comprehensions for `s_rlat`, `s_rlon`, and `s_cos_lat` were replaced with one comprehension that builds a list of `(rlat, rlon, cos_lat)` tuples, then transposes with `zip(*s_vals)`. Iterates `station_ids` once instead of three times.

## `dist.min(axis=1)` instead of fancy indexing (change 1)
`dist[np.arange(len(valid)), best_idx]` required allocating a temporary `arange` array. Replaced with `dist.min(axis=1)`, which directly computes the minimum without a temporary index array.

## `best_idx.tolist()` before the assignment loop (change 2)
`int(best_idx[i])` inside the per-entrance loop converted a numpy scalar to a Python int on every iteration. Replaced with a single `.tolist()` call before the loop and plain list indexing inside.

## `heapq.nlargest` for the top-15 summary (change 5)
`sorted(exits.items(), ..., reverse=True)[:15]` sorted the full stations dict to discard all but 15 results. Replaced with `heapq.nlargest(15, ...)`, which is O(N log 15) vs O(N log N). Effect on the written JSON file is nil; the console summary order may differ for tied exit counts.

---

# 2026-04-28 OPT-012 through OPT-016 · Five efficiency improvements to `crowdedness.py` — IMPLEMENTED

**Files changed:** `backend/crowdedness.py`, `backend/main.py`, `backend/tests/test_crowdedness.py`

## OPT-012 · Pydantic `BaseModel` replaced with `@dataclass` for `CrowdednessEstimate`

`CrowdednessEstimate` was a Pydantic `BaseModel`, triggering full schema validation and reflection overhead on every instantiation. Replaced with a standard `@dataclass`. The only consumer (`_crowdedness_for_routes` in `main.py`) only reads `.level` — no Pydantic-specific methods (`.dict()`, `.model_dump()`, etc.) were in use anywhere.

## OPT-013 · `classify_time_period` now returns local hour as third element

Return type changed from `tuple[TimePeriod, DayType]` to `tuple[TimePeriod, DayType, int]`, where the third element is the Chicago local hour. This eliminates the need for callers to independently derive the local hour after calling this function. `main.py`'s `_get_crowdedness_period` was updated to use `classify_time_period(now)` directly instead of the previous `(*classify_time_period(now), now.hour)` unpacking. All tests updated to unpack the 3-tuple.

## OPT-014 · `strftime` for holiday set lookup replaced with f-string

`local.strftime("%Y-%m-%d")` replaced with `f"{local.year}-{local.month:02d}-{local.day:02d}"`, skipping the format-string parser for a string that is only used as a set key.

## OPT-015 · `factors` dict construction made conditional via `include_factors` flag

Added `include_factors: bool = True` parameter to `estimate_crowdedness`. When `False`, the heuristic `factors` dict (8 keys, multiple `round()` calls) and the live-path 2-key dict are skipped entirely. `CrowdednessEstimate.factors` changed to `dict | None = None`. `main.py`'s hot-path call (`_crowdedness_for_routes`) passes `include_factors=False` since it only uses `est.level`.

## OPT-016 · `stop_id.isdigit()` + `int(stop_id)` double-scan replaced with single `try/except`

`stop_id.isdigit() and int(stop_id) >= 40000` performed two sequential string scans. Replaced with `try: is_train = int(stop_id) >= 40000 / except ValueError: is_train = False`, resolving the train/bus check in a single pass.

---

# 2026-04-28 OPT-011 · Nine micro-optimisations applied to `walking.py` — IMPLEMENTED

## 🟡 Routing hot-path made faster; redundant allocations and trig calls eliminated

**File:** `backend/walking.py`

**Changes made:**

1. **`edge.attributes()` → `edge["name"]`** — `_walk_directions_impl` was calling `edge.attributes()` to produce a full dict copy just to read `"name"`. `_street_name` now accepts the raw attribute value directly, eliminating the allocation on every edge.

2. **Precomputed edge-length NumPy array** — `_load_graph` now builds `_edge_lengths: np.ndarray` once at startup (with `None → 0.0`). `walk_minutes` uses `_edge_lengths[list(epath)].sum()` instead of per-edge `G.es[e]["length"]` attribute lookups. `_walk_directions_impl` also uses `_edge_lengths[eid]` in its grouping loop.

3. **Flat-earth proximity check in `_get_nearest_node`** — replaced the haversine call (uses `sin`, `asin`, `sqrt`) with the flat-earth approximation (`dlat² + (dlon·cos(lat))²` scaled by 111 320 m/°). Accurate to ~0.1 % at Chicago's latitude; sub-meter boundary error. Avoids four trig calls per cache-miss node lookup.

4. **`_cardinal` and `_street_name` moved to module level** — both were defined inside `_walk_directions_impl`, recreating the function objects on every cache miss. Now defined once at import time.

5. **Single-pass grouping in `_walk_directions_impl`** — replaced the two-pass approach (build `raw` list then group) with a single-pass accumulator loop using the new `_make_step` module-level helper, eliminating the intermediate list allocation.

6. **`reversed()` instead of `[::-1]` in `_walk_path_impl`** — geometry coordinate lists that need to be traversed in reverse are now iterated with `reversed()` (zero-copy iterator) rather than `[::-1]` (copies the entire list). The effective-first-coord check uses `geom_coords[-1]` directly without materialising the copy.

7. **`import math` moved to module level** — was inside `_walk_directions_impl`; now a top-level import. Avoids a `sys.modules` dict lookup on every cache miss.

8. **Redundant `_load_graph()` calls removed** — `walk_minutes` and `_walk_directions_impl` both called `_load_graph()` before delegating to `_get_shortest_path`, which calls it again. The redundant calls are removed; both functions now rely on `_get_shortest_path`'s own guard and read `_graph_cache` directly when they need the graph object.

9. **Single-pass vertex coordinate arrays** — `_load_graph` previously built `lons` and `lats` with two separate list comprehensions over `G.vs`. Replaced with a single `[(v["x"], v["y"]) for v in G.vs]` pass producing an (N, 2) array; `lons` and `lats` are zero-copy column views.

---

# 2026-04-28 OPT-007 · Early exit added to `_stream_all_stop_sequences` stop_times.txt pass — IMPLEMENTED

## 🟡 Streaming loop now breaks as soon as all candidate trips are fully processed

**File:** `backend/transit_graph.py` — `_stream_all_stop_sequences()` (streaming loop, formerly lines 357–393)

**What was happening:** The CSV loop iterated all 5.8 M rows of `stop_times.txt` unconditionally. Once all candidate train and bus trips had been read, every remaining row was checked against `all_candidate_tids` and skipped — pure overhead that accounted for the bulk of the observed ~60 s stream time.

**Analysis of the `last_dep` blocker:** The original deferral note flagged that `last_dep` (Feature Last Train) accumulates the latest departure per `(parent_mapid, direction_id)` across *all* weekday train trips. Closer inspection confirms that `last_dep` is updated only when `tid in train_raw`, and `train_raw` is keyed exactly by `train_candidates` — all weekday train trips. The early exit fires only after *all* candidate trips (both train and bus) have been fully consumed, so the `last_dep` dict is complete before the break. No data is skipped.

**Fixed by:**
1. Added `remaining_tids: set[str] = set(all_candidate_tids)` and `prev_tid: str | None = None` before the loop.
2. At each trip-ID transition (`tid != prev_tid`): if the outgoing trip was a candidate, `discard` it from `remaining_tids`. If `remaining_tids` is then empty, `break`.
3. Added a comment noting the assumption that CTA's `stop_times.txt` is sorted by `trip_id` (standard GTFS — all rows for a trip are contiguous), which is required for the transition-detection to be correct.

**Expected improvement:** ~60 s → ~15–20 s for the streaming step at server startup, consistent with the estimate in OPT-007.

---

# 2026-04-28 OPT-009 · Vectorized NumPy haversine replaces 260 K-call nested loop in `fetch_station_exits.py` — IMPLEMENTED

## 🟢 Startup matching loop replaced with single broadcasting pass

**File:** `backend/fetch_station_exits.py` — `build_exits()` (lines 100–170)

**What was happening:** `build_exits()` iterated all ~200 Overpass entrance nodes in an outer loop, and for each node called `_haversine_precomputed` once per station in a Python inner loop (~1,300 stations × ~200 entrances ≈ 260,000 scalar function calls).

**Fixed by:** Replaced both loops with a single NumPy broadcasting pass. Station lat/lon/cos arrays (N,) and entrance lat/lon/cos arrays (M,) are constructed once, then `dlat`/`dlon` are computed as (M, N) matrices via `[:, np.newaxis]` broadcasting. The full distance matrix is computed in one vectorized haversine expression, `argmin(axis=1)` finds the nearest station per entrance, and the scalar result-assembly loop only runs once to build the output dict. Removed the now-unused `_haversine_precomputed` helper. Added `numpy>=1.24,<3` to `requirements.txt` (was an implicit transitive dep via scikit-learn/scipy).

---

# 2026-04-27 OPT-FE-001 · GPS effect fake state updates eliminated; OPT-FE-002 · RouteCard memoized; OPT-FE-003 · favorites.js mutations accept in-memory array

## 🔴 OPT-FE-001 — GPS effect no longer queues fake `setActiveLegIndex` updates

**File:** `frontend/src/App.jsx`

**What was happening:** The `userPosition` effect called `setActiveLegIndex(current => { ...; return current; })` for walk-step completion (block 2) and off-route detection (block 3) purely to read the current `activeLegIndex` value. These functional updates returned `current` unchanged every tick — queuing two no-op state updates per GPS update with no rendering benefit. The anti-pattern was identified in OPT-FE-005 (the ref was already added), but blocks 2 and 3 were not yet updated to use it.

**Fixed by:** Blocks 2 and 3 now read `activeLegIndexRef.current` directly (updated in block 1 when the leg advances). Both `setActiveLegIndex` calls in those blocks were removed. `setActiveLegIndex` is now called at most once per tick — only when the leg actually advances — down from up to three queued updates every GPS tick.

---

## 🔴 OPT-FE-002 — `RouteCard` wrapped with `React.memo`

**Files:** `frontend/src/components/RouteCard.jsx`

**What was happening:** During an active trip, `userPosition` is updated ~every second, re-rendering `App`. All 3–5 `RouteCard` instances re-rendered on every GPS tick regardless of whether their props changed. Only the selected card receives changing props (`activeLegIndex`, `completedSteps`); non-selected cards received identical props on every tick but still ran their render function.

**Fixed by:** Added `memo` import from React and wrapped the default export: `export default memo(function RouteCard({ ... }) { ... });`. Non-selected cards now bail out of re-render via shallow prop comparison. The selected card re-renders correctly because `completedSteps` is a new `Set` reference when steps complete.

---

## 🟡 OPT-FE-003 — `favorites.js` mutations accept caller's in-memory array

**Files:** `frontend/src/favorites.js`, `frontend/src/App.jsx`

**What was happening:** Every mutation function (`saveLocation`, `deleteLocation`, `saveRoute`, `deleteRoute`, `pinStop`, `unpinStop`) called `_load()` at the start, performing a `localStorage.getItem()` + `JSON.parse()`. Since `App` already holds the authoritative in-memory copy in React state, these reads returned identical data to what was just written — the deserialization was entirely wasted.

**Fixed by:** Changed each mutation function's signature to accept the current array as a final parameter (e.g. `saveLocation(label, value, current)`). Callers in `App.jsx` pass their corresponding React state (`savedLocations`, `savedRoutes`, `pinnedStops`). `handlePinToggle` now uses `pinnedStops` state directly instead of calling `getPinnedStops()`. `getSaved*` / `getPinnedStops` are unchanged and still used for initial state load.

---

# 2026-04-27 OPT-FE-004 · Module-scope trip helpers; OPT-FE-005 · activeLegIndexRef eliminates fake state updates

## 🟢 OPT-FE-004 — `WALK_SPEED_FACTORS`, `haversineMeters`, `pointToSegmentMeters`, `legEndCoord` moved to module scope

**File:** `frontend/src/App.jsx`

**What was happening:** `WALK_SPEED_FACTORS` (object literal), `haversineMeters`, `pointToSegmentMeters`, and `legEndCoord` were all defined inside the `App` component body, causing a fresh object or function to be allocated on every render. These have no dependency on component state or props.

**Fixed by:** Moved all four to module scope (alongside `BACKEND_URL`, `_RETRY_DELAYS`, etc.), under a shared `// Pure trip-geometry helpers` comment block. Per-render allocations are now eliminated entirely.

---

## 🟢 OPT-FE-005 — `activeLegIndexRef` eliminates three fake `setActiveLegIndex` state updates per GPS tick

**File:** `frontend/src/App.jsx`

**What was happening:** The `userPosition` effect called `setActiveLegIndex` three times per GPS update: once to advance the leg, and twice more purely as a way to read `activeLegIndex` synchronously (the functional-update form was used as a hack, with `return current` to leave the value unchanged). This queued two no-op React state updates on every GPS tick.

**Fixed by:** Added `activeLegIndexRef = useRef(null)` as a ref mirror of `activeLegIndex`. The GPS effect now reads `activeLegIndexRef.current` directly and only calls `setActiveLegIndex` when the value genuinely changes (at most once per tick, only when the leg advances). The ref is kept in sync in `startTrip`, `stopTrip`, and `handleReroute`. This reduces up to 3 queued updates per tick to at most 1.

---

# 2026-04-24 LRU cache promotion on hit, coordinate pre-transform in MapView, first_transit_leg_index on Route

---

## 🟡 OPT-001 · Response Cache Eviction Not LRU-Aware — IMPLEMENTED

**File:** `backend/main.py`

**Category:** Memory Inefficiency / Cache Performance

**What was inefficient:** The `_response_cache` `OrderedDict` used `move_to_end(key)` only on write, so every cache hit left the accessed entry at its original insertion position. On eviction (`popitem(last=False)`), a hot entry accessed hundreds of times could be evicted before a cold entry inserted after it.

**Implemented in:** Added `_response_cache.move_to_end(key)` inside the existing `async with _store_lock:` read block, immediately before returning the cache hit.

---

## 🟢 OPT-002 · Redundant Coordinate Transformations in MapView renderRoute — IMPLEMENTED

**File:** `frontend/src/MapView.jsx`

**Category:** Redundant Computation

**What was inefficient:** The `toGeo` helper was called via `.map(toGeo)` separately in Pass 1 (polylines) and again per intermediate stop point in Pass 2, for the same underlying `leg.shape` array.

**Implemented in:** Added `const legGeoCoords = legs.map(leg => { ... })` before Pass 1. Each entry calls `(leg.path ?? []).map(toGeo)` or `(leg.shape ?? []).map(toGeo)` exactly once. Both Pass 1 and Pass 2 read from `legGeoCoords[i]`. Reduces coordinate array allocations by ~50–60% per render for typical multi-leg routes.

---

## 🟢 OPT-003 · Sequential Leg Iteration in _rank_routes to Find First TransitLeg — IMPLEMENTED

**Files:** `backend/transit_graph.py`, `backend/main.py`

**Category:** Redundant Computation

**What was inefficient:** `_rank_routes()` called `next((l for l in route.legs if isinstance(l, TransitLeg)), None)` on each route — O(legs) scan per route, repeated for every route on every `/recommend` request.

**Implemented in:** Added `first_transit_leg_index: int | None = None` field to the `Route` dataclass. `_path_to_route()` computes it once at route construction. `_rank_routes()` now reads `route.legs[route.first_transit_leg_index]` — O(1) index access.

---

# 2026-04-27 Non-blocking DAU saves, autocomplete prefix index, parallel coord resolution

---

## 🔴 OPT-001 · Blocking Disk I/O in Async DAU Handler — IMPLEMENTED

**File:** `backend/dau.py`

**Category:** Async Pattern

**What was inefficient:** `record_visit()` called `_load()` (full disk read of `dau.json`) and `_save()` (temp-file atomic write) on every new unique visitor while holding `asyncio.Lock`, stalling the event loop for the duration of both operations.

**Implemented in:**
- Added module-level `_counts_cache: dict[str, int] = _load()` initialised once at import time.
- Removed all `_load()` calls from the per-visitor path; `record_visit()` now updates `_counts_cache[today]` directly and calls `await loop.run_in_executor(None, _save, _counts_cache.copy())` to push the write off the event loop.
- On day rollover (once per day), a synchronous `_load()` is still called to pick up counts from a previous process instance, then `_counts_cache` is refreshed; the per-day save uses `run_in_executor`.

---

## 🟡 OPT-002 · Linear Scan Through All Bus Stop Names on Every Autocomplete Request — IMPLEMENTED

**File:** `backend/main.py`

**Category:** Inefficient Data Structure / Redundant Computation

**What was inefficient:** `/autocomplete` performed an O(n) scan of all entries in `_ac_train_names`, `_ac_neighborhood_names`, and `_ac_bus_names` (3,000–8,000 unique bus names) on every keystroke, calling `_ac_score()` (which called `.lower()` and `.split()`) for every entry.

**Implemented in:**
- Added `_ac_prefix_index: dict[str, list[tuple[int, int, dict]]] = {}` at module scope.
- `_build_autocomplete_index()` now builds the index: for each name in all three tiers, each word's 2- and 3-character lowercase prefixes are mapped to `(tier, score, suggestion)` tuples. Score 0 = full-name prefix (first word), score 1 = inner-word prefix. A per-name `added` set prevents duplicate entries per prefix key.
- `/autocomplete` now does a single `dict` lookup by `query[:3]` (or `query[:2]` for 2-char queries), then filters and scores only the small candidate bucket — O(k) where k ≪ n, rather than O(n) over the full corpus. The unused `_ac_score()` helper was removed.

---

## 🟡 OPT-003 · Sequential Coordinate Resolution for Origin and Destination — IMPLEMENTED

**File:** `backend/main.py`

**Category:** Async Pattern

**What was inefficient:** In `_resolve_locations()`, `origin_coords` and `dest_coords` were resolved via two sequential `await loop.run_in_executor(...)` calls. These are fully independent operations; each can take ~100ms for a geocode lookup, adding unnecessary latency.

**Implemented in:** Replaced the two sequential awaits with `asyncio.gather`:
```python
origin_coords, dest_coords = await asyncio.gather(
    loop.run_in_executor(None, _coords_for_location, request.origin, origin_stations),
    loop.run_in_executor(None, _coords_for_location, request.destination, dest_stations),
)
```

---

# 2026-04-20 Replace NetworkX MultiDiGraph with igraph + scipy cKDTree in walking.py

---

## 🔴 OPT-008 · Replace NetworkX MultiDiGraph with compact igraph representation — IMPLEMENTED

**Files:** `backend/walking.py`, `backend/fetch_street_graph.py`, `backend/requirements.txt`

**Category:** Memory Footprint

**What was inefficient:** `walking.py` loaded the OSMnx pedestrian street graph as a `nx.MultiDiGraph`. NetworkX stores graphs as nested Python dicts (~200+ bytes of overhead per node/edge), so a ~120 MB GraphML file on disk ballooned to several hundred MB in RAM.

**Implemented in:** Three coordinated changes:

1. **`walking.py` fully rewritten** — `networkx` and `osmnx` removed from runtime walking logic. New state: `_graph_cache: ig.Graph | None`, `_coord_kdtree: cKDTree | None`, `_vertex_lats/lons: np.ndarray | None`. `_load_graph()` tries the pre-built igraph pickle first; falls back to `ig.Graph.Read_GraphML()`. `_get_nearest_node()` uses `_coord_kdtree.query([lon, lat])` (scipy cKDTree) instead of `ox.nearest_nodes()`.

2. **`fetch_street_graph.py` extended** — `_save_igraph_artifact(G_nx)` builds an igraph `Graph` and pickles it to `street_graph_igraph.pkl` with geometry pre-parsed as coord lists.

3. **`requirements.txt`** — added `igraph>=0.11` and `scipy>=1.7`.

---

# 2026-04-20 One-shot `styledata` listener replaces persistent `data` listener

---

## 🟡 OPT-017 · Replace persistent `map.on("data", …)` with a one-shot listener after style errors clear — IMPLEMENTED

**File:** `frontend/src/MapView.jsx`

**Category:** Rendering / DOM Inefficiency

**What was inefficient:** A persistent `map.on("data", …)` listener was registered unconditionally on map init to clear the `styleError` banner. MapLibre fires the `"data"` event for every tile, source, and style load throughout the map's lifetime — potentially hundreds of times per minute.

**Implemented in:** Removed the persistent `map.on("data", …)` block entirely. Inside the existing `"error"` handler, after `setStyleError(true)` is set, added `map.once("styledata", () => setStyleError(false))`. This one-shot listener is only registered when a style error actually occurs.

---

# 2026-04-20 O(n) `seenTransit` flag replaces O(n²) slice+scan in `RouteLegs`

---

## 🟢 OPT-016 · Precompute `isTransferLeg` before the `.map()` in `RouteLegs` — IMPLEMENTED

**File:** `frontend/src/App.jsx`

**Category:** Redundant Computation

**What was inefficient:** Inside `RouteLegs`, the expression `legs.slice(0, i).some(l => l.type === "transit")` was evaluated once per transit leg during the `.map()` render — O(n²) in the number of legs.

**Implemented in:** Declared `let seenTransit = false` in the `RouteLegs` function body. Inside the `.map()` callback, `isTransferLeg` is now assigned `seenTransit` directly (O(1)), then `seenTransit = true` is set unconditionally for every transit leg. O(n) total.

---

# 2026-04-20 Pre-computed entrance and station trig in `build_exits`

---

## 🟢 OPT-010 · Pre-compute entrance trig before inner station loop in `build_exits` — IMPLEMENTED

**File:** `backend/fetch_station_exits.py`

**Category:** Redundant Computation

**What was inefficient:** In `build_exits`, for each entrance node the inner loop called `_haversine_miles(lat, lon, info["lat"], info["lon"])` once per station (~150 stations). Entrance trig was recomputed inside `haversine_miles()` on every iteration.

**Implemented in:** (1) `load_parent_stations()` now stores `rlat`, `rlon`, `cos_lat` pre-computed at load time. (2) Entrance trig pre-computed before the inner loop. (3) Local `_haversine_precomputed` helper accepts pre-converted radians directly. Eliminates ~450k redundant trig operations per full dataset run.

---

# 2026-04-20 Drop row-count loop in `validate_and_report`

---

## 🟢 OPT-011 · Avoid full-file row iteration for `stop_times.txt` in `validate_and_report` — IMPLEMENTED

**File:** `backend/fetch_gtfs.py`

**Category:** Redundant Computation

**What was inefficient:** `validate_and_report` iterated every line of every GTFS file just to print a row count. `stop_times.txt` is ~354 MB / 5.8M rows.

**Implemented in:** Removed the `with open(path) as fh: rows = ...` block entirely. `validate_and_report` now calls `path.stat().st_size` only (a single kernel stat call) and prints file size in KB.

---

# 2026-04-20 Deduplicate LINE_COLORS and BUS_DIRECTION_COLORS into shared constants

---

## 🟡 OPT-015 · Deduplicate LINE_COLORS and BUS_DIRECTION_COLORS constants — IMPLEMENTED

**File:** `frontend/src/constants.js` (new), `frontend/src/App.jsx`, `frontend/src/MapView.jsx`

**Category:** Unnecessary Duplication

**What was inefficient:** `LINE_COLORS` and `BUS_DIRECTION_COLORS` were defined identically in both `App.jsx` and `MapView.jsx`. Any color change required editing two places.

**Implemented in:** Extracted both objects into `frontend/src/constants.js` as named exports. Both files now import from that shared module.

---

# 2026-04-20 Shared shortest-path and nearest-node cache across walk functions

---

## 🟡 OPT-009 · Cache shortest path computation to avoid redundant routing — IMPLEMENTED

**File:** `backend/walking.py`

**Category:** Redundant Computation

**What was inefficient:** `walk_minutes`, `_walk_directions_impl`, and `_walk_path_impl` each independently called `ox.nearest_nodes()` (twice per function) and `nx.shortest_path()`. When a single request triggers multiple functions for the same origin/dest pair, the full Dijkstra run plus two KD-tree queries were repeated independently per function.

**Implemented in:** Added two shared `@lru_cache` helpers: `_get_nearest_node(lat, lon)` and `_get_shortest_path(origin_lat, origin_lon, dest_lat, dest_lon)`. All three public functions share a single Dijkstra run for any given origin/dest pair.

---

# 2026-04-20 Consolidate OSMnx intersections before saving street_graph.graphml

---

## 🟡 OPT-007 · Consolidate street-graph intersections to shrink `street_graph.graphml` — IMPLEMENTED

**File:** `backend/fetch_street_graph.py`

**Category:** Memory Footprint / Asset Size

**What was inefficient:** `fetch_street_graph.py` saved the raw OSMnx pedestrian graph without any simplification, producing a ~120 MB `.graphml` that ballooned to several hundred MB in RAM.

**Implemented in:** Added an intersection-consolidation pass inside `download_and_save()` using `ox.consolidate_intersections(tolerance=10, rebuild_graph=True, dead_ends=False)` after reprojecting to UTM, then reprojecting back to WGS-84. Expected reduction: 20–40% fewer nodes.

---

# 2026-04-18 Persistent HTTP session, heapq partial sort, display-name preservation, cached legColor

---

## 🟡 OPT-012 · Persistent requests session for Google geocoding — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** Network Efficiency

**Implemented in:** Added a module-level `_http_session = requests.Session()`. `geocode_google()` now calls `_http_session.get(...)` instead of `requests.get(...)`, reusing the keep-alive TCP/SSL connection across calls.

---

## 🟡 OPT-013 · `heapq.nsmallest()` instead of full sort in nearest-stop finders — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** Algorithmic Efficiency

**Implemented in:** Replaced `hits.sort(key=...)` + `hits[:max_results]` with `heapq.nsmallest(max_results, hits, key=...)` in both `find_nearest_train_stations()` and `find_nearest_bus_stops()`. O(n log k) vs O(n log n).

---

## 🟢 OPT-014 · Preserve original query string as `matched_name` in `resolve_location` — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** UX / Data Fidelity

**Implemented in:** Added `original_query = query.strip()` before the lowercase/normalization step. Both the exact-match and geocoding branches now return `original_query` as `matched_name` instead of the normalized `q`, preserving user capitalization.

---

## 🟢 OPT-018 · Cache `legColor(leg)` result per transit leg in `renderRoute` — IMPLEMENTED

**File:** `frontend/src/MapView.jsx`

**Category:** Redundant Computation

**Implemented in:** Added `const legColors = legs.map(leg => leg.type === "transit" ? legColor(leg) : null)` before the Pass 1 loop. Both Pass 1 and Pass 2 read `legColors[i]` instead of calling `legColor(leg)` twice per leg.

---

# 2026-04-18 Short-circuit + inverted-index in `fuzzy_match_neighborhood`

---

## 🟢 OPT-006 · `fuzzy_match_neighborhood` scans all keys even after finding a high score — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** Redundant Computation

**Implemented in:** Three layered optimizations: (1) Word-based inverted index (`_neighborhood_word_index()`) narrows candidates from ~240 to ~1–20 for multi-word queries. (2) `SequenceMatcher` reuse with `query` set as `seq2` to leverage Python's `__chain_b` cache. (3) `quick_ratio()` prefilter + 0.99 short-circuit.

---

# 2026-04-18 Collapse double dict lookups on `_response_cache` hit/miss

---

## 🟢 OPT-005 · Double dict lookup on cache hit/miss — IMPLEMENTED

**File:** `backend/main.py`

**Category:** Redundant Computation

**Implemented in:** Cache read now uses `_response_cache.pop(key, None)` for stale-eviction path. Cache write uses unconditional assignment + `move_to_end(key)`, eliminating the membership-test hash on the existing-key branch.

---

# 2026-04-18 Drop per-request `_route_fingerprint` closure + dedup pass in `/recommend`

---

## 🟢 OPT-004 · Per-request closure for route fingerprinting — IMPLEMENTED

**File:** `backend/main.py`

**Category:** Redundant Computation

**Implemented in:** Resolved as a side effect of the Feature J refactor. The `_route_fingerprint` closure and the `seen_fps` loop were deleted; the merge is now just `sorted(ranked_routes + transfer_ranked, key=lambda x: x[0])[:5]`.

---

# 2026-04-18 Append-only journal + periodic compaction for geocode-cache flush

---

## 🟢 OPT-003 · Full JSON rewrite on every geocode-cache flush — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** Inefficient I/O

**Implemented in:** Replaced the `_geocode_cache_dirty: bool` flag with a `_geocode_pending: dict` that records only entries added since the last flush. Each 30s tick appends the delta as JSONL lines to `geocode_cache.journal` (O(delta) write). A full snapshot rewrite is forced only when 500 cumulative journal entries have built up or 3600s has elapsed. O(size) writes reduced to O(delta) for ~99% of flushes.

---

# 2026-04-18 Per-request memo for terminal-name lookups in `_rank_routes`

---

## 🟢 OPT-002 · Repeated `get_station_by_name` lookups inside ranking hot path — IMPLEMENTED

**File:** `backend/main.py`

**Category:** Redundant Computation

**Implemented in:** Added a per-request `terminal_coords: dict[str, tuple[float,float] | None]` memo at the top of `_rank_routes` to skip the cache's hash + thread-lock dispatch on repeat lookups within one request.

---

# 2026-04-18 Grid-bucket spatial index for nearest-stop lookups

---

## 🔴 OPT-001 · Full-catalog Haversine scan on every bus-stop lookup — IMPLEMENTED

**File:** `backend/gtfs_loader.py`

**Category:** Redundant Computation / Inefficient Data Structure

**What was inefficient:** `find_nearest_bus_stops` ran Haversine against every CTA bus stop (~10,729 stops) on every `/recommend` call — twice per request (origin + destination) — before applying any radius filter. Each call cost ~21k trig operations.

**Implemented in:** Added a grid/bucket spatial index keyed on floor(lat/cell_lat, lon/cell_lon) with cell dimensions ≈ 1 mile. Index is built lazily via `_spatial_index(kind)` and cached with `lru_cache(maxsize=2)`. `_candidates_within()` computes the lat/lon bounding box, iterates only intersecting bucket cells, applies a cheap bounding-box prefilter, then Haversine only on remaining candidates. Measured ~25.7 ms → ~0.08 ms per call at 0.25 mi (~300×) and ~0.58 ms at 1.0 mi (~44×).

---

# 2026-04-27 BUG-014 · Single-direction walk legs show no street-level detail to the user — FIXED

## 🟢 Single-step walk legs now render their street detail inline; multi-step legs keep the expandable toggle — FIXED

**File:** `frontend/src/components/RouteCard.jsx` — `WalkLegItem`, line 14

**What was happening:** `hasSteps` was `true` only when `leg.directions.length > 1`. A walk leg with exactly one direction step (e.g. "Walk north along State St for 2 blocks") had `hasSteps = false`, so neither the toggle button nor the step list was ever rendered. The user saw only the generic "Walk X min" label with no street name.

**Fixed in:** Replaced the single `hasSteps` boolean with two derived values: `hasSteps = dirCount > 0` and `isMultiStep = dirCount > 1`. Single-step legs (`hasSteps && !isMultiStep`) now render their one step directly inline using `leg-steps--inline` styling — no toggle needed, street name always visible. Multi-step legs still use the existing expand/collapse toggle. Zero-step legs continue to show nothing.

```jsx
// BEFORE (> 1 hides single-step legs entirely):
const hasSteps = leg.directions && leg.directions.length > 1;
// ... hasSteps gates both toggle and step list

// AFTER (> 0 catches single-step; inline vs toggle split by isMultiStep):
const dirCount = leg.directions?.length ?? 0;
const hasSteps = dirCount > 0;
const isMultiStep = dirCount > 1;
// single step: rendered inline (no toggle)
// multi-step: existing toggle behavior unchanged
```

---

# 2026-04-27 Shared aiohttp session, dau.py counts cache, single stops.txt pass, early-exit rate-limit scan

---

## 🟡 OPT-004 · New `aiohttp.ClientSession` Per API Call — IMPLEMENTED

**File:** `backend/cta_client.py`, `backend/main.py`

**Category:** Inefficient I/O

**What was inefficient:** `get_train_arrivals`, `get_bus_arrivals`, `get_alerts`, and `get_route_statuses` each created a fresh `aiohttp.ClientSession()` per call (4 sessions per `/recommend` request), each with its own connection pool, SSL context, and TCP handshake overhead. Connections could not be reused across these calls.

**Implemented in:** Added a module-level `_session: aiohttp.ClientSession | None` to `cta_client.py`, with `init_session()` / `close_session()` helpers. All four public API functions now call `_get_session()` to obtain the shared session. `main.py` lifespan calls `_init_cta_session()` at startup and `_close_cta_session()` at shutdown. A fallback creates a temporary session for isolated unit tests that call before `init_session()`.

---

## 🟢 OPT-005 · `dau.py` — Redundant Full File Read on Every Unique Visit — IMPLEMENTED

**File:** `backend/dau.py`

**Category:** Redundant Computation

**What was inefficient:** `record_visit()` called `_load()` to read `dau.json` from disk on every new unique visitor, then immediately overwrote today's entry. One disk read per unique IP was unnecessary since the only data needed from disk (other days' counts) was already in memory.

**Implemented in:** Added module-level `_counts_cache: dict[str, int] = _load()` (initialised at import time, after `_load()` is defined). Normal unique-visitor writes now do `_counts_cache[today] = ...; _save(_counts_cache.copy())` without any `_load()` call. On day rollover, `_counts_cache` is reloaded from disk once to pick up counts written by a previous process instance. The `_save` call is also moved off the event loop via `run_in_executor` (bonus async improvement). `_load()` and `_save()` definitions moved before module-level state so `_counts_cache = _load()` executes correctly.

---

## 🟢 OPT-006 · `stops.txt` Parsed Twice in `_build_graph` — IMPLEMENTED

**Files:** `backend/transit_graph.py`

**Category:** Redundant Computation

**What was inefficient:** `_build_graph()` called `_load_parent_stations()` and `_load_platform_to_parent()` sequentially — two separate full CSV passes over `stops.txt` (~10,000 rows) at every startup.

**Implemented in:** Added `_load_station_data() -> tuple[dict, dict]` which reads `stops.txt` exactly once and builds both the `parent_stations` dict (location_type=1, 40000–49999 range) and the `platform_to_parent` mapping (30000–39999 range) in a single pass. `_build_graph()` now calls `_load_station_data()`. The old `_load_parent_stations()` and `_load_platform_to_parent()` are kept as thin single-line wrappers for any isolated test callers.

---

## 🟢 OPT-007 · `_check_rate_limit()` Per-Minute Count is O(n) Linear Scan — IMPLEMENTED

**File:** `backend/main.py`

**Category:** Inefficient Data Structure

**What was inefficient:** Per-minute request count was computed as `sum(1 for t in window if now - t <= 60)` — a full scan over all hourly timestamps for the IP. At the default 50 req/hr cap this was at most O(50), but would become a hot path if the cap were raised significantly.

**Implemented in:** Replaced with a right-to-left early-exit loop: `for t in reversed(window): if now - t <= 60: recent += 1; else: break`. Because the deque is insertion-ordered (ascending timestamps), iterating from the right encounters the newest entries first and stops as soon as it exits the 60-second window, reducing the average scan to O(recent_requests) instead of O(all_hourly_requests).


---

# 2026-04-28 Efficiency Improvements Batch — OPT-001, OPT-002, OPT-003, OPT-005, OPT-006, OPT-008, OPT-011, OPT-012, OPT-013, OPT-014, OPT-015, OPT-016, OPT-017, OPT-018, OPT-019

## OPT-001 · DAU Batch Writes with Time-Based Flush — IMPLEMENTED

**File:** backend/dau.py  
**Impact:** High

Replaced per-visit disk writes with dual-condition batched writes: _save() fires when _visitors_since_last_flush reaches 20 OR when 30 seconds have elapsed since the last flush (_last_flush_time), whichever comes first. Day-rollover forces an immediate flush and resets both counters. Eliminated the unnecessary .copy() when passing _counts_cache to _save() since the dict is already held exclusively under _lock. Reduces disk I/O ~20x at peak traffic; the 30-second timer ensures counts are durable even at low traffic.

---

## OPT-002 · Response Cache TTL 45 s to 120 s — IMPLEMENTED

**File:** backend/main.py  
**Impact:** High

Changed _CACHE_TTL_SECONDS from 45 to 120. Route options change only when a new train or bus arrives, typically every 5-15 minutes. The 45-second TTL caused rapid repeat requests to miss the cache and relaunch the full pipeline unnecessarily.

---

## OPT-003 · Geocoding Journal Line-Count Compaction Trigger — IMPLEMENTED

**File:** backend/gtfs_loader.py  
**Impact:** High

Added _GEOCODE_JOURNAL_LINE_LIMIT = 1000 and a third compaction condition: _geocode_journal_entries >= _GEOCODE_JOURNAL_LINE_LIMIT. At 100 new geocodes/day the journal could accumulate 3,000+ lines in a month, adding 50-100 ms to every cold startup (O(N) replay). The line-count trigger ensures compaction fires before replay becomes expensive.

---

## OPT-005 · Crowdedness Period 1-Minute Cache — IMPLEMENTED

**File:** backend/main.py  
**Impact:** Medium

Extracted _get_crowdedness_period() which returns (time_period, day_type, hour) and caches the result for 60 seconds. _crowdedness_for_routes() now calls _get_crowdedness_period() instead of calling classify_time_period(datetime.now()) on every invocation. Savings compound across 5-15 legs per request x 10 requests/sec.

---

## OPT-006 · Weather Cache Sizing — IMPLEMENTED

**File:** backend/weather_service.py  
**Impact:** Medium

_weather_cache: maxsize 50 to 200, TTL 720s (12 min) to 1800s (30 min). Chicago at 2-decimal-degree resolution has ~100 grid cells; the 50-entry cache was saturating and evicting valid entries. Weather changes on a 30-minute scale so the longer TTL reduces NWS API calls ~2.5x with no accuracy loss. _grid_cache maxsize also raised 50 to 200.

---

## OPT-004 · Autocomplete Index Stores Pointer Indices Instead of Duplicate Dict Refs — IMPLEMENTED

**File:** backend/main.py  
**Impact:** Medium

Added _ac_master: list[dict] as a module-level master suggestion list. Each suggestion dict is now stored exactly once in _ac_master; _ac_prefix_index buckets store (tier, score, idx) integer tuples instead of full dict references. With ~5,000 unique names and 4+ prefix keys per name this cuts the number of in-memory dict objects from ~25,000+ to ~5,000 (~5x reduction). The /autocomplete endpoint dereferences via _ac_master[idx] at lookup time.

---

## OPT-008 · Bus Transfer Lookup Built Once Per Request — ALREADY RESOLVED

**File:** backend/main.py  
**Impact:** Low

The original entry described _build_bus_transfer_lookup being called at lines 906 and 1830. In the current codebase it is called only once (line 908, inside _fetch_transfer_arrivals). This was already resolved in a prior refactor. Entry removed from active tracking.

---

## OPT-011 · Pre-Filter Origin Stations to 3 Closest — IMPLEMENTED

**File:** backend/main.py (_fetch_arrivals)  
**Impact:** Medium

Added origin_stations = sorted(origin_stations, key=lambda s: s.get("walk_minutes", 0))[:3] at the top of _fetch_arrivals. resolve_location can return 5-8 nearby stations; only the 1-2 closest are ever useful. Each extra station adds a CTA Train Tracker API call. Filtering to 3 eliminates 2-5 unnecessary network requests per trip on average.

---

## OPT-012 · Walk Directions Capped at 15 Steps — IMPLEMENTED

**File:** backend/walking.py (walk_directions)  
**Impact:** Low

Added _WALK_DIRECTIONS_MAX_STEPS = 15 and sliced the returned steps: list(steps[:_WALK_DIRECTIONS_MAX_STEPS]). Long walks through dense street grids can produce 20-40 steps. The UI shows only the first 5-10 before a toggle, so serializing 30+ steps was pure payload overhead.

---

## OPT-013 · Lazy Import of xml.etree.ElementTree — IMPLEMENTED

**File:** backend/main.py  
**Impact:** Low

Removed top-level "import xml.etree.ElementTree as ET". Moved the import inline inside the /alerts endpoint handler where it is the only consumer. Reduces startup import time and keeps the module-level import list honest.

---

## OPT-014 · Cache Hit/Miss Instrumentation — IMPLEMENTED

**File:** backend/main.py  
**Impact:** Medium

Added _cache_hits, _cache_misses, _cache_requests_total counters and a _CACHE_LOG_INTERVAL = 100. The /recommend cache read path increments the appropriate counter and prints a log line every 100 requests: "[cache] 100 requests | hits=12 misses=88 hit_rate=12.0% size=42". Costs nothing at runtime and makes future TTL/size tuning data-driven.

---

## OPT-015 · Unmemoized serviceAlerts.filter() Inline in JSX — IMPLEMENTED

**File:** frontend/src/App.jsx  
**Impact:** High

Extracted serviceAlerts.filter((a) => !dismissedAlertIds.has(a.alert_id)) into a useMemo named visibleAlerts with deps [serviceAlerts, dismissedAlertIds]. The filter no longer runs on every keystroke in the origin/destination fields.

---

## OPT-016 · currentRouteSaved not memoized in useFavorites — IMPLEMENTED

**File:** frontend/src/hooks/useFavorites.js  
**Impact:** Medium

Wrapped savedRoutes.some(...) in useMemo([savedRoutes, currentOrigin, currentDest]). The O(savedRoutes.length) scan no longer runs on every keystroke.

---

## OPT-017 · Alert Sort Re-runs on Every Render in ServiceAlertsBar — IMPLEMENTED

**File:** frontend/src/components/ServiceAlertsBar.jsx  
**Impact:** Medium

Wrapped [...alerts].sort(...) in useMemo([alerts]). Moved the memo above the early-return guard to satisfy React rules of hooks. The sort only re-runs when the alerts array reference changes.

---

## OPT-018 · Blur Timeout in LocationInput Not Tracked for Cleanup — IMPLEMENTED

**File:** frontend/src/App.jsx  
**Impact:** Low

Added blurTimerRef = useRef(null). Changed onBlur to store the timer ID: blurTimerRef.current = setTimeout(...). Added clearTimeout(blurTimerRef.current) to the cleanup useEffect alongside the other timer refs.

---

## OPT-019 · pinnedStops.some() Inside legs.map() in RouteLegs — IMPLEMENTED

**File:** frontend/src/components/RouteCard.jsx  
**Impact:** Low

Added const pinnedIds = useMemo(() => new Set(pinnedStops?.map((s) => s.stop_id) ?? []), [pinnedStops]) at the top of RouteLegs. Replaced pinnedStops?.some(...) with pinnedIds.has(stopId). Lookup is now O(1) instead of O(pinnedStops.length) per leg.

---

## OPT-010 · Direction String Normalized at CTA Client Boundary — IMPLEMENTED

**File:** backend/cta_client.py, backend/crowdedness.py  
**Impact:** Low

Changed prd.get("rtdir", "") to prd.get("rtdir", "").lower() in get_bus_arrivals() so every arrival dict carries a pre-lowercased direction string. Removed rtdir_lower = rtdir.lower() from rtdir_to_inbound_outbound() in crowdedness.py since the value is now already lowercase at the call site. Eliminates ~250 redundant string allocations per request (50 routes × 5 legs each).

---

# Technical Debt Paid Off (2026-04-28 scan)

> **Note on TD numbering:** This section uses session-local numbering (`2026-04-28 TD-001` through `2026-04-28 TD-017`), independent of the global TD-NNN sequence used in earlier sections above. The date prefix distinguishes these entries.

---

## 2026-04-28 TD-001 · Missing test coverage for six core backend modules — RESOLVED

Added `backend/tests/test_weather_service.py`, `test_crowdedness.py`, `test_route_scoring.py`, and `test_dau.py` covering pure functions: `_parse_precip`, `_parse_wind`, `_feels_like`, `classify_time_period`, `rtdir_to_inbound_outbound`, `adjust_weights_for_weather`, `weight_hint_for_weather`, DAU helpers.

---

## 2026-04-28 TD-002 · Loose version pins in requirements.txt allow silent breaking upgrades — RESOLVED

Added `<next_major>` upper bounds to all six open-ended `>=` pins: `anthropic>=0.50,<1`, `scikit-learn>=1.0,<2`, `networkx>=3.0,<4`, `igraph>=0.11,<1`, `scipy>=1.7,<2`, `cachetools>=5.3,<6`, `pytest>=8.0,<9`.

---

## 2026-04-28 TD-003 · CTA Customer Alerts endpoint used HTTP, not HTTPS — RESOLVED

Changed `_CTA_CUSTOMER_ALERTS_URL` in `backend/main.py` from `http://www.transitchicago.com/...` to `https://www.transitchicago.com/...`.

---

## 2026-04-28 TD-004 · `_haversine_walk_minutes` fallback hardcoded 3.0 mph — RESOLVED

Replaced the literal `3.0` in `backend/walking.py` with `_cfg.WALKING_SPEED_MPH` so the fallback honours the config value when `WALKING_SPEED_MPH` is changed via env var.

---

## 2026-04-28 TD-005 · NWS User-Agent hardcoded a personal email address — RESOLVED

Made the contact email configurable via `NWS_CONTACT_EMAIL` env var in `backend/weather_service.py`. Defaults to the existing address if the env var is unset.

---

## 2026-04-28 TD-006 · Holiday list in crowdedness.py requires annual hand-maintenance — RESOLVED

Added a startup-time `logging.warning` in `backend/crowdedness.py` that fires whenever the current Chicago year exceeds `_HOLIDAY_MAX_YEAR` (the highest year in `_HOLIDAYS`). The warning names the file and the specific action needed so it is actionable in Railway logs.

---

## 2026-04-28 TD-007 · `ALERTS_BASE` and `ROUTES_BASE` in cta_client.py not env-overridable — RESOLVED

Applied the same `os.getenv(...)` pattern used for `_CTA_TRAIN_BASE` and `_CTA_BUS_BASE` to both constants in `backend/cta_client.py`. Env vars: `CTA_ALERTS_API_URL`, `CTA_ROUTES_API_URL`.

---

## 2026-04-28 TD-008 · `_DIRECTION_OVERRIDES` was a permanently empty dict — RESOLVED

Removed the empty `_DIRECTION_OVERRIDES` dict and its lookup from `backend/crowdedness.py`. Inlined the heuristic directly in `rtdir_to_inbound_outbound`. The function signature is preserved for call-site compatibility.

---

## 2026-04-28 TD-009 · App.jsx was a 1155-line monolith with three embedded components — RESOLVED

Extracted `LabelSavePanel`, `LocationInput`, and `SavedRoutesPanel` into dedicated files under `frontend/src/components/`. App.jsx imports them. `LocationInput` now imports `BACKEND_URL` from `constants.js` rather than inheriting a module-level closure.

---

## 2026-04-28 TD-010 · Hardcoded English strings bypassed i18n in multiple components — RESOLVED

Added 15 translation keys to `frontend/public/locales/en/translation.json`. Updated: `ErrorBoundary.jsx` (via new `FallbackUI` functional wrapper), `RouteCard.jsx` (Stop/Start Trip), `MapView.jsx` (tile error, unlock button), `LocationInput.jsx` (ac_type badge), `WeatherStrip.jsx` (precip labels, gusts).

---

## 2026-04-28 TD-011 · Core hooks and key utility have zero unit test coverage — RESOLVED

Added `frontend/src/tests/useApiQuery.test.js`, `useFavorites.test.js`, and `useLocalStorage.test.js` using Vitest `renderHook`. Covers success/error fetching, enabled flag, refetch, pin/unpin, route save/delete, limit error, localStorage round-trip and failure handling.

---

## 2026-04-28 TD-012 · Route-color lookup logic duplicated in three files — RESOLVED

Exported `getRouteColor(line, fallback = "#4a9eff")` from `frontend/src/constants.js`. Updated `RouteCard.jsx`, `PinnedStopsBoard.jsx`, and `MapView.jsx` to use it; removed the three inline implementations.

---

## 2026-04-28 TD-013 · `isStopPinned()` in favorites.js was dead code — RESOLVED

Removed `isStopPinned` from `frontend/src/favorites.js`. Removed corresponding tests from `favorites.test.js`. All consumers use `pinnedStops.some(...)` on the in-memory array directly.

---

## 2026-04-28 TD-014 · Magic timeout/delay values scattered inline in App.jsx — RESOLVED

Added five named constants to `frontend/src/constants.js`: `AC_DEBOUNCE_MS`, `DROPDOWN_BLUR_DELAY_MS`, `GEO_ERROR_RESET_MS`, `GEO_UNAVAILABLE_RESET_MS`, `LIMIT_ERROR_DISMISS_MS`. Used in the extracted `LocationInput.jsx`.

---

## 2026-04-28 TD-015 · Commented-out bus-fullness filter left in App.jsx JSX — RESOLVED

Deleted the 17-line commented-out `<select>` block from `frontend/src/App.jsx`. The `psgld` field is still absent from live CTA Bus Tracker responses; a GitHub issue tracks re-enabling when CTA populates the field.

---

## 2026-04-28 TD-016 · External tile-service URL hardcoded in MapView.jsx — RESOLVED

Changed `DEFAULT_STYLE` in `frontend/src/MapView.jsx` to read from `import.meta.env.VITE_MAP_STYLE_URL`, falling back to the OpenFreeMap liberty style. Operators can now switch tile providers via env var without a code change.

---

## 2026-04-28 TD-017 · ErrorBoundary.jsx used inline styles disconnected from app CSS theme — RESOLVED

Added `.error-boundary` and child CSS classes to `frontend/src/App.css` using CSS custom properties (`--bg`, `--text`, `--text-muted`, `--accent`) so the error screen responds to theming. Replaced all inline `style={{...}}` in `ErrorBoundary.jsx` with `className` references. Added a `FallbackUI` functional component so the error screen can use `useTranslation`.

---

# 2026-04-28 BUG-010 · "Freezing Sleet" NWS text misclassified as FREEZING_RAIN — FIXED

## 🟢 `"freezing"` check ran before `"sleet"` check, short-circuiting to wrong precipitation type — FIXED

**File:** `backend/weather_service.py` lines 165–168 (`_parse_precip`)

**What was happening:** The `if "freezing" in fc` branch appeared before the `elif "sleet" in fc or "ice pellet" in fc` branch. When NWS short-forecast text contained both words (e.g. `"Freezing Sleet"` or `"Slight Chance Freezing Sleet"`), the first condition matched and classified the precipitation as `FREEZING_RAIN` instead of `SLEET`. The two types are semantically distinct and map to different intensities and routing heuristics.

**Fixed by:** Moved the `"sleet" in fc or "ice pellet" in fc` branch to the top of the chain so it is checked first. The `"freezing"` branch now correctly handles only pure freezing rain (no sleet/ice pellets). The redundant `and "sleet" not in fc and "ice pellet" not in fc` guard on the old `"ice"` sub-check was also removed since sleet/ice-pellet cases can no longer reach that branch.

---

# Efficiency Improvements Implemented

---

## 2026-04-28 · Seven efficiency improvements to transit_graph.py — RESOLVED

**File:** `backend/transit_graph.py`

**Impact:** 🔴 High (intermodal edge loop, file I/O consolidation) / 🟡 Medium (per-request gains)

**What was changed:**

1. **stops.txt read consolidated from 3× to 1×** — Added `_load_all_stops()` decorated with `@lru_cache(maxsize=1)`, which reads stops.txt once and returns all three dicts: `parent_stations` (40000–49999), `platform_to_parent` (30000–39999), and `bus_stop_lookup` (0–29999). `_load_station_data()`, `_load_bus_stop_lookup()`, `_load_parent_stations()`, and `_load_platform_to_parent()` are now thin wrappers around it. `_build_bus_stop_grid()` (called at module import) and `_build_graph()` (called lazily) share the single cached result.

2. **routes.txt read consolidated from 3× to 1×** — Added `_load_all_routes()` decorated with `@lru_cache(maxsize=1)`, which reads routes.txt once and returns `(train_route_ids, bus_route_map, route_short_names)`. `_load_train_route_ids()` and `_load_bus_route_map()` are now thin wrappers. `_build_shape_lookup()` now uses the cached result instead of opening routes.txt a third time.

3. **`_load_weekday_service_ids()` memoized** — Added `@lru_cache(maxsize=1)`. Both `_load_representative_trips()` and `_load_bus_candidate_trips()` called it independently, causing calendar.txt and calendar_dates.txt to be read twice. Now both callers share one cached result.

4. **O(n²) intermodal walk-edge loop replaced with SpatialGrid** — The nested loop over all train stations × all bus stops (~1.5 M haversine calls) is replaced with `_bus_stop_grid.query(s_lat, s_lon, _TRANSFER_RADIUS_MILES)`, which returns only stops within the radius. The grid is already built at module import; no new data structure is introduced. The `dist` value returned by the query replaces the explicit haversine call, so the edge weights are identical.

5. **`get_station_by_name()` exact match is now O(1)** — Added module-level `_station_name_exact` (lowercase name → `(lat, lon)`) and `_station_name_entries` (pre-built list for the contains-match fallback), populated by `_build_station_name_index()` which is called from `warm_up()`. The previous implementation scanned all ~140 stations on every cache miss; exact matches now hit a dict. The `@lru_cache(maxsize=512)` is retained for repeated contains-match queries.

6. **`clip_shape()` nearest-point scan vectorized with numpy** — The inner `_nearest_idx` Python loop (O(N) per call, called twice per transit leg) is replaced with `np.argmin()` on a vectorized squared-distance array. numpy is already an implicit dependency via networkx.

7. **Best-exit scan in `_select_transfer_candidates()` de-duplicated** — Added a local `_exit_cache` dict (keyed by `(route_B_key, t_idx)`) within the function call. The same (route B, boarding-index) pair was rescanned for every route-A arrival that led to the same transfer point; the cache eliminates repeated haversine scans across duplicate combinations within one `find_bus_transfer_routes()` call.

---

## 2026-04-28 OPT-010 · Eight efficiency improvements to gtfs_loader.py — RESOLVED

**File:** `backend/gtfs_loader.py`

**Impact:** 🟡 Medium (geocoding concurrency + startup latency) / 🟢 Low (minor per-call overheads)

**What was changed:**

1. **`_geocode_lock` no longer held during HTTP I/O** — The lock is now acquired only for the pre-flight quota/key check and for the post-flight result store. The actual Google API call runs outside the lock, allowing concurrent requests for *different* queries to proceed in parallel instead of serialising on the single global lock. A re-check inside the inner lock handles the race where two threads request the same uncached query simultaneously.

2. **Monthly geocode counter save batched with existing flush cycle** — `_increment_geocode_call_count()` previously wrote `geocode_counter.json` to disk on every API call. It now marks a `_geocode_counter_dirty` flag and returns the new count; `_flush_geocode_cache_if_dirty()` persists the counter on its 30-second background tick (and on `atexit`). The monthly cap is now a soft cap — increments in a crash window are not persisted — which was accepted as a trade-off.

3. **`import datetime` moved to module level** — Previously imported inside three functions (`_load_geocode_counter`, `_geocode_call_count`, `_increment_geocode_call_count`) on every call. Now a single top-level import.

4. **Redundant `_geocode_call_count()` call eliminated** — `geocode_google()` previously called `_geocode_call_count()` twice: once for the cap check and once inside the success log message. `_increment_geocode_call_count()` now returns the new count, which is used directly in the log.

5. **Pickle cache for parsed GTFS stops** — `_load_stops()` now persists the parsed `(train_stations, bus_stops)` result to `gtfs_data/stops_cache.pkl` alongside the source `stops.txt` mtime. On subsequent starts the pickle is loaded instead of re-parsing the CSV, provided the mtime matches. The pickle is written atomically (tmp → rename). A corrupt or mismatched pickle falls through to full CSV re-parse.

6. **Duplicate `_geocode_max_age_seconds` / `_GEOCODE_MAX_AGE_SECONDS` variables removed** — Both held `_cfg.GEOCODE_CACHE_MAX_AGE_DAYS * 24 * 3600`. Consolidated into the single canonical `_GEOCODE_MAX_AGE_SECONDS`.

7. **`_ABBR_MAP` duplicate-key assertion uses `Counter`** — The error-message expression in the `assert` was O(n²) (`.count()` inside a list comp). Replaced with a single `collections.Counter` pass that produces the same error output in O(n).

8. **`_street_abbr_replace` promoted from closure to module-level function** — The `_replace` inner function inside `_normalize_street_abbr` was recreated on every call. Promoted to `_street_abbr_replace` at module level.

---

## 2026-04-28 OPT-001 · Duplicate condition evaluation and two-pass normalization in route_scoring.py — RESOLVED

**File:** `backend/route_scoring.py`

**What was changed:** Four efficiency improvements were made together:

1. **Shared condition evaluation (#1):** `adjust_weights_for_weather` and `weight_hint_for_weather` previously each evaluated the same three weather threshold conditions (temperature, precipitation, wind gusts) independently. Extracted a private `_active_conditions(c)` helper that evaluates all thresholds once and returns a list of `(weight_deltas_dict, hint_str)` tuples. Both public functions now call it, eliminating all duplicated threshold logic.

2. **Single-pass clamp + normalize (#2):** The normalization step previously produced one intermediate dict for clamping and a second for normalizing. Replaced with a list comprehension for clamped values, a single `sum()`, and one final dict comprehension — one fewer intermediate dict allocation.

3. **Short-circuit when no thresholds fire (#3):** When active conditions is empty (the common case in mild weather), both functions now return immediately without running clamp/normalize. Behavior is identical to the existing `weather is None` early-return path; per design, `base_weights` is returned as-is (not re-normalized) in both no-op cases.

4. **Removed unreachable `total > 0` guard (#4):** The guard `if total > 0:` before normalization was unreachable — `base_weights` values are always positive, and the clamp only floors to `0.0`, so `total` can never be zero with valid input. Removed.

---

## 2026-04-28 OPT-011 · Four efficiency improvements to utils.py — RESOLVED

**File:** `backend/utils.py`

**Impact:** 🟢 Low (minor per-call overheads) / 🟡 Medium (`SpatialGrid.query` inner-loop savings at scale)

**What was changed:**

1. **`_cell`: redundant `int()` wrap around `math.floor()` removed** — In Python 3, `math.floor()` returns an `int` by specification. The `int(math.floor(...))` double-conversion in `_cell` (and the four equivalent expressions in `query`) was a no-op. Replaced with bare `math.floor(...)` throughout.

2. **`haversine_miles`: temporary list removed from `map()` call** — `map(math.radians, [lat1, lon1, lat2, lon2])` allocated a temporary list object on every call. Since `haversine_miles` is called in the inner loop of `SpatialGrid.query`, this allocation repeated at high frequency. Replaced with four direct `math.radians()` assignments, which avoids the allocation entirely.

3. **`SpatialGrid.query`: AABB bounds check skipped for interior cells** — The per-entry lat/lon bounds check (`e_lat < lat_lo or ...`) was applied to all cells in the bounding-box window, including cells whose entire extent lies inside the bounding box. For interior cells (those where `min_cl < cl < max_cl` and `min_cn < cn < max_cn`) every entry is guaranteed to pass the check, so the four comparisons per entry were wasted work. The `interior` flag is now computed once per cell and the check is skipped when true.

4. **`SpatialGrid.query`: cheap planar distance pre-filter added before Haversine** — After the AABB check, `haversine_miles` (which calls `sin`, `cos`, `asin`, `sqrt`) was invoked for every surviving entry. A squared planar distance check using `_MILES_PER_DEG_LAT`/`_MILES_PER_DEG_LON` is now applied first. Because these constants slightly underestimate true arc distance at Chicago's latitude (`d_planar ≤ d_haversine`), a point where `d_planar > radius` is provably outside the radius and haversine can be skipped safely. The comparison uses `>` (not `>=`) so boundary points are never incorrectly discarded. The squared form avoids a `sqrt` call.

---

## 2026-04-28 · Three efficiency improvements to active_routes.py — RESOLVED

**File:** `backend/active_routes.py`

**Impact:** 🟡 Medium (concurrent GTFS load) / 🟢 Low (per-route syscall and string allocation savings)

**What was changed:**

1. **`sys.stdout.isatty()` cached at module level** — `_color_block` previously called `sys.stdout.isatty()` on every invocation, once per bus route in the print loop. Added module-level `_IS_TTY = sys.stdout.isatty()` and updated `_color_block` to test `_IS_TTY` instead. TTY state cannot change mid-run, so this is semantically identical.

2. **`_route_sort_key` single-pass character partition** — The function previously ran two separate generator expressions over the route string (`"".join(c for c in rt if c.isdigit())` and `"".join(c for c in rt if not c.isdigit())`), iterating the string twice. Replaced with a single `for` loop that appends each character to either a `digits` or `letters` list, halving the iterations for mixed-character routes such as `"J14"` or `"X9"`.

3. **GTFS file load overlapped with API fetches** — `_load_gtfs_routes()` previously ran synchronously before the `asyncio.gather` for the two CTA API calls, adding its file-read time to the critical path. It is now dispatched via `asyncio.to_thread(_load_gtfs_routes)` and included as a third coroutine in the `gather`, so the CSV parse runs concurrently with both network requests.

---

## 2026-04-28 · Seven efficiency improvements to main.py and walking.py — RESOLVED

**Files:** `backend/main.py`, `backend/walking.py`

**Impact:** 🔴 High (parallelised async I/O on every cache-miss request) / 🟡 Medium (memory growth bound, session reuse) / 🟢 Low (per-query autocomplete savings)

**What was changed:**

1. **`_fetch_arrivals` and `_safe_weather` parallelised (#1)** — The two calls were sequential in `recommend()` even though weather fetching and CTA arrival fetching are fully independent. Replaced with a single `asyncio.gather(...)` so both run concurrently. Saves ~1–2 s on every cache-miss transit request.

2. **`walk_all` consolidates the three walk functions (#2)** — `recommend()` previously dispatched `_walk_minutes`, `_walk_directions`, and `_walk_path` as three separate `run_in_executor` calls inside `asyncio.gather`. Because `_get_shortest_path` is `@lru_cache` but the three threads could all arrive before any of them cached the result, the Dijkstra path computation could run three times concurrently. Added `walk_all()` to `walking.py`, which calls the three public functions sequentially in a single thread (ensuring `_get_shortest_path` runs at most once), and updated `main.py` to dispatch only that one function.

3. **Origin and destination geocoded in parallel (#3)** — `_resolve_locations` previously geocoded the origin, validated it, then geocoded the destination sequentially. Both `resolve_location` calls are now dispatched together via `asyncio.gather`. Validation of each result is done in order afterward, so error messages remain correct. Saves one geocoding round-trip on every cache-miss request.

4. **API keys and model names cached as module-level constants (#4)** — `os.getenv()` was called on every request in `_validate_api_keys`, `_fetch_arrivals`, `_fetch_transfer_arrivals`, `stop_arrivals`, and `_call_claude`. These values never change at runtime. Replaced with five module-level constants (`_CTA_TRAIN_KEY`, `_CTA_BUS_KEY`, `_ANTHROPIC_KEY`, `_CLAUDE_SIMPLE_MODEL`, `_CLAUDE_COMPLEX_MODEL`) read once at import time. `_claude_client` was updated to use `_ANTHROPIC_KEY` as well.

5. **`_rate_store` IP keys pruned when deques empty (#5)** — The sliding-window eviction loop already removed timestamps older than one hour from each IP's deque, but the dict key itself was never removed. After eviction, if the deque is empty the IP has no activity in the past hour; `_check_rate_limit` now replaces the entry with a fresh deque containing only the current timestamp, preventing unbounded dict growth on long-running servers with many unique visitors.

6. **`/alerts` endpoint reuses the shared `aiohttp` session (#6)** — The endpoint previously created a new `aiohttp.ClientSession()` on every cache miss. The shared session from `cta_client.py` is a plain session with no base URL, custom headers, or auth — safe to reuse for the `transitchicago.com` request. Imported `_get_session` from `cta_client` and removed the per-request session creation.

7. **Autocomplete `_nl` and `_words` precomputed at index build time (#7)** — The `autocomplete` endpoint previously called `suggestion["label"].lower()` and `nl.split()` on every candidate for every query. Both values are now computed once inside `_index_entry` during startup and stored as `_nl` and `_words` in each master entry. The endpoint reads the precomputed fields directly.

---

## 2026-04-28 OPT-012 · Five efficiency improvements to weather_service.py — RESOLVED

**File:** `backend/weather_service.py`

**Impact:** 🔴 High (session reuse) / 🟢 Low (remaining four micro-optimisations)

**What was changed:**

1. **Shared `aiohttp.ClientSession` per service instance (#1)** — `get_weather_context` previously created a new `ClientSession` (and tore it down) on every cache miss, discarding TCP connection pooling. Added `__init__` initialising `self._session = None`, a `_get_session()` helper that creates the session lazily on first use and reuses it on subsequent calls, and an `async close()` method for callers to release the session on shutdown. The `async with aiohttp.ClientSession(...)` block in `get_weather_context` is replaced with `session = self._get_session()`.

2. **`_parse_precip` reduced from three passes to one (#2)** — The original implementation scanned `fc` up to 9 times for the early-exit check (`any(w in fc for w in precip_words)`), then made a second pass for type detection, then a third for intensity. Replaced with a single elif chain that determines type and falls to `else: return NONE` for non-precipitation forecasts. The priority order is preserved exactly (sleet/ice-pellet → freezing/ice → snow/flurr/blizzard → rain/drizzle/shower → none), and "shower" is now explicitly listed in the RAIN branch (it previously fell through to the original `else: ptype = RAIN` clause, producing the same result).

3. **`wind_speed_mph ** 0.16` computed once in `_feels_like` (#3)** — The NWS wind-chill formula used `wind_speed_mph ** 0.16` in two separate terms. Extracted to a local `w` variable, eliminating the duplicate exponentiation.

4. **Alert deduplication uses a set (#4)** — `if headline not in alert_headlines` performed a linear scan on a list. Added a `seen: set[str]` for O(1) membership checks; `alert_headlines` remains a list so insertion order is preserved.

5. **`itertools.islice` replaces `periods[:13]` slice (#5)** — The slice allocated a new list just to iterate 13 elements. Replaced with `itertools.islice(periods, 13)`, which is a zero-copy iterator.

---

## 2026-04-28 · Five efficiency improvements to cta_client.py — RESOLVED

**File:** `backend/cta_client.py`

**Impact:** 🟢 Low (per-request object allocation savings and minor code quality improvements)

**What was changed:**

1. **Module-level `ClientTimeout` objects (#1)** — `aiohttp.ClientTimeout(...)` was previously constructed fresh inside each of the four fetch functions on every call. Added two module-level constants: `_API_TIMEOUT = aiohttp.ClientTimeout(total=_cfg.CTA_API_TIMEOUT_SECONDS)` (shared by `_fetch_station_arrivals` and `_fetch_bus_chunk`) and `_SHORT_TIMEOUT = aiohttp.ClientTimeout(total=5)` (shared by `_fetch_alerts_for_route` and `get_route_statuses`). These objects are immutable value types and are safe to reuse across concurrent requests.

2. **`datetime.now()` computed once per batch in `get_train_arrivals` (#2)** — Previously, each concurrent `_fetch_station_arrivals` task computed its own `now = datetime.now(CHICAGO_TZ)` independently after receiving its API response. `now` is now computed once in `get_train_arrivals` before `asyncio.gather` and passed into each task as a parameter. All arrivals in a batch therefore share a single consistent reference time, eliminating minor per-task clock drift. **Note:** in the rare case where a fetch takes several seconds and an arrival falls exactly on a minute boundary, the reported `arrives_in_minutes` value could differ by ±1 from the previous behaviour.

3. **`itertools.chain.from_iterable` replaces extend loop (#3)** — `get_train_arrivals` accumulated results with an explicit `for result in results: all_arrivals.extend(result)` loop. Replaced with `list(itertools.chain.from_iterable(results))`, which flattens all sub-lists in a single pass without intermediate allocation. `import itertools` added at the top of the file.

4. **`_dly` extracted to a variable in `_fetch_bus_chunk` (#5)** — `prd.get("dly", "")` was evaluated inline inside the dict literal, making the `is_delayed` expression harder to follow. Extracted to `_dly = prd.get("dly", "")` before the `arrivals.append(...)` call; `is_delayed` now reads `str(_dly).lower() in ("true", "1", "yes")`. Logic is identical.

5. **`get_route_statuses` append loop converted to list comprehension (#6)** — The `statuses = []; for r in routes_raw: try: statuses.append({...}); except: continue` pattern is replaced with a direct `return [...]` list comprehension. All four fields use `.get()` with a default and cannot raise, so the `try/except` wrapper was purely defensive and safe to remove.

---

# Technical Debt Paid Off (2026-04-28 frontend scan)

> **Note on TD numbering:** This section uses the global TD-100+ range allocated by the 2026-04-28 frontend tech-debt scan.

---

## 2026-04-28 TD-100 · Hardcoded English strings in tab bar — RESOLVED

Replaced the four hardcoded mobile tab labels (`"Home"`, `"Map"`, `"Alerts"`, `"Saved"`) and the nav `aria-label="Main navigation"` in `frontend/src/App.jsx` with `t("tab_home")`, `t("tab_map")`, `t("tab_alerts")`, `t("tab_saved")`, and `t("aria_main_nav")`. Added the five keys to `frontend/public/locales/en/translation.json`; other locales fall back to en via i18next's built-in fallback.

---

## 2026-04-28 TD-101 · Hardcoded "No active service alerts." string — RESOLVED

Replaced the hardcoded literal in `frontend/src/App.jsx` (alerts tab empty state) with `{t("alerts_empty")}`. Also wrapped the per-row `"Advisory"` severity fallback as `t("alerts_advisory")`. New keys added to `en/translation.json`.

---

## 2026-04-28 TD-102 · Hardcoded "Underway" / "Bus N" labels in MapView — RESOLVED

Replaced hardcoded `"Underway"` kicker, `Bus ${code}` labels (in both the trip overlay and the map legend), and the inline `style={{ fontFamily: ... }}` block in `frontend/src/MapView.jsx`. Now uses `t("map_underway")` and `t("map_bus_label", { code })`. The inline style was extracted to a new `.map-train-card__line-text` rule in `App.css`.

---

## 2026-04-28 TD-103 · Hardcoded English strings in PinnedStopsBoard — RESOLVED

Replaced `aria-label="Live data"`, `title="Refresh arrivals"` (also used as aria-label), `title="Unpin stop"`, and the template-literal `aria-label={`Unpin ${stop.label}`}` in `frontend/src/components/PinnedStopsBoard.jsx`. Now uses `t("psb_live_data")`, `t("psb_refresh")`, `t("psb_unpin_stop")`, and the existing `t("unpin_stop", { stop })` interpolation.

---

## 2026-04-28 TD-104 · Hardcoded "Dismiss" aria-labels — RESOLVED

Three call-sites — `App.jsx:655`, `LocationInput.jsx:259`, `RouteCard.jsx:250` — now share a single `t("aria_dismiss")` key.

---

## 2026-04-28 TD-105 · Hardcoded "Close ×" string in SettingsPanel — RESOLVED

Footer button in `frontend/src/components/SettingsPanel.jsx` now uses `{t("settings_btn_close")} ×` rather than a hardcoded literal. The `×` character is decorative (icon role) and remains outside the translation key.

---

## 2026-04-28 TD-106 · Magic numbers in trip-tracking thresholds — RESOLVED

Extracted `60` (leg-advance radius), `150` (vehicle leg-advance radius), and `30` (walk-step proximity) from `processTripPosition` in `App.jsx` into three named constants in `constants.js`: `LEG_ADVANCE_RADIUS_M`, `LEG_ADVANCE_RADIUS_VEHICLE_M`, `WALK_STEP_PROXIMITY_M`. All GPS-tuning thresholds now live in one file alongside `OFF_ROUTE_THRESHOLD_METERS` and `REROUTE_SUPPRESSION_MS`.

---

## 2026-04-28 TD-107 · Magic 3000 ms in useFavorites duplicates LIMIT_ERROR_DISMISS_MS — RESOLVED

`frontend/src/hooks/useFavorites.js` now imports `LIMIT_ERROR_DISMISS_MS` from `constants.js` and uses it in place of the literal `3000` in the route-save limit-error timer.

---

## 2026-04-28 TD-108 · Magic 1000 ms photo fade duration — RESOLVED

Extracted to `PHOTO_FADE_MS = 1000` in `constants.js` with a comment noting it must match the `.transit-photo--fading` CSS transition. `App.jsx` now uses the constant in `fadePhoto()`.

---

## 2026-04-28 TD-109 · Volume year `2022` hardcoded in masthead — RESOLVED

Extracted to `MASTHEAD_EPOCH_YEAR = 2022` in `constants.js` with a comment explaining its meaning (project-publication year used for the newspaper-style "VOL." number). `App.jsx` imports and uses the constant.

---

## 2026-04-28 TD-110 · TransitPhoto captions are not i18n'd — RESOLVED

Replaced inline string captions in `frontend/src/components/TransitPhoto.jsx` with translation keys: `photo_caption_red_line_howard`, `photo_caption_loop_elevated`, `photo_caption_blue_line_ohare`, `photo_caption_state_lake`, `photo_caption_wrigley_addison`. The component now imports `useTranslation` and resolves the caption via `t(photo.captionKey)`. Image `alt` text reuses the same translated string.

---

## 2026-04-28 TD-111 · Missing component-level test coverage — RESOLVED

Added `@testing-library/react` and `@testing-library/jest-dom` as dev-dependencies. The existing hook tests were already importing `@testing-library/react` (broken — 3 test files failed to load), so this also restored test discovery for `useFavorites.test.js`, `useLocalStorage.test.js`, and `useApiQuery.test.js`. Added a global setup file at `frontend/src/tests/setup.js` (registers jest-dom matchers) and updated `vite.config.js` to include `.test.jsx` files and run the setup file. Added the first component-level test file `frontend/src/tests/LinePill.test.jsx` (4 smoke tests: train abbreviation, bus code, lg-size full label, Yellow Line dark text). Test suite now 81 tests across 7 files (was 50/3 before; the other 3 files were broken). Coverage config now also includes `src/components/**` so future component tests show up in coverage reports.

---

## 2026-04-28 TD-112 · React 18 → React 19 upgrade pending — RESOLVED

Bumped `react` and `react-dom` from `^18.3.1` to `^19` in `frontend/package.json`. Verification:
- All 81 unit tests pass on React 19.
- `npm run build` succeeds; PWA service-worker generation unchanged.
- No code changes were required — the codebase was already React-19-compatible (no legacy `forwardRef` patterns, no string refs, no use of deprecated lifecycle methods, `react-i18next@17` and `vite-plugin-pwa@1` both already support React 19).

---
