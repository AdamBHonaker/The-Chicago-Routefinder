# Feature Plans & Future Enhancements

Chunked plans for upcoming major features, followed by ideas deferred until post-launch. For chunked features, work through each chunk in order, one chunk per session or per commit. Do not start a chunk until all previous chunks are complete.

> **Process:** When a feature here is fully implemented, **delete its entry from this file** and add a corresponding entry to [`FEATURES_IMPLEMENTED_HISTORY.md`](FEATURES_IMPLEMENTED_HISTORY.md) summarizing what was built. This file should only ever contain features that have not yet been implemented.

---

## Feature Index

**Bolt-On** = self-contained, no dependencies on other planned features.
**Structural** = depends on one or more other features before it can be fully built or realized.

**Chunked Implementation Plans** (in document order):
1. Feature Weather — Live Weather Integration — **Bolt-On**
2. Feature Crowdedness — CTA Vehicle Crowdedness Estimation — **Bolt-On**
3. Feature Weather Scoring — Weather-Adjusted Route Ranking — **Structural** (depends on Feature Weather + Feature Crowdedness)
4. Multi-Leg Train Routing — Shared-Track Edge Deduplication — **Structural** (✅ Complete 2026-04-20)
5. Feature K — Restore Street-Network Walking Graph in Production — **Bolt-On**
6. Feature Trip — Live Trip-in-Progress Routing — **Bolt-On**
7. Feature Favorites — Saved Locations & Routes — **Bolt-On**

> Items 1–3 are prioritized chunked plans. Items 4–8 appear in the **Future Enhancements** section below — post-launch, implement based on user feedback.

---

# Chunked Implementation Plans

---

# Feature Weather — Live Weather Integration

## Overview

The `/recommend` pipeline currently assembles routing context (train/bus arrivals, walk times, route rankings) without any awareness of weather. A 15-minute walk in a blizzard or a freezing-rain wait at an outdoor Red Line platform is materially different from the same trip in mild weather, but Claude has no signal to say so.

This feature integrates a live weather API, exposes a `WeatherContext` summarizing current conditions, near-term forecast, and active alerts for the origin, and injects it into `build_prompt()`. Claude's natural-language output becomes the primary surface for weather context to the rider.

**Why it matters:** Weather is the single most important latent variable in Chicago transit decisions that the app currently ignores. Adding it makes recommendations substantially more realistic (e.g. "given the freezing rain, the Red Line is preferable to the 22 Clark bus since you'll spend less time waiting outside").

**Type: Bolt-On** — self-contained backend addition. No changes to routing logic; only `build_prompt()` is extended. Precondition for Feature Weather Scoring.

**Status: ⬜ Not started**

**Prerequisites:**
- Railway + Vercel deployment live (Phase 6 complete).
- All scoping decisions below resolved.

---

## Scoping decisions — pending

These must be resolved before Chunk 1 begins.

1. **Primary weather API provider.** Options:
   - **Weather.gov (NWS)** — free, unlimited, no API key, reliable for US. No dedicated "current conditions" endpoint (first hourly period is used as current); `feels_like_f` must be derived; visibility/humidity require a second call. Requires a real contact email in the `User-Agent` header.
   - **OpenWeatherMap** — free tier 1,000 calls/day, polished DX, returns `feels_like`, visibility, humidity in one call. Requires API key and billing account.
   - **Open-Meteo** — free, no key, solid hourly data. Less real-time granularity.
   - **Tomorrow.io** — 500 calls/day free, excellent minute-level precipitation.
   - **Recommendation:** NWS primary — zero cost, no key, no rate limits.

2. **Secondary / fallback provider.** A second provider as fallback if the primary errors, or single provider only? Adds complexity and (for paid APIs) a second key/quota. Recommendation: none at launch; add only if the primary proves flaky in production.

3. **Contact email for NWS `User-Agent` header** (only if NWS chosen). NWS requires a real email or URL. Recommendation: `adambhonaker@gmail.com` or a project-specific alias.

4. **Include visibility + humidity in `CurrentWeather`?** These are not in the NWS hourly forecast. Including them requires an extra call to `/stations/{id}/observations/latest` per fetch. Recommendation: drop for v1 — Claude rarely needs humidity to advise on a transit choice.

5. **Cache implementation.** `cachetools.TTLCache` (adds a dependency but gives explicit TTL semantics) or a hand-rolled timestamp + dict (no new dependency). Recommendation: `cachetools`.

---

## Chunk 1 — Weather data models

**Files:** `backend/weather_service.py` (new)

**What to build:**

Define Pydantic models: `PrecipitationType` enum (`NONE/RAIN/SNOW/SLEET/FREEZING_RAIN`), `PrecipitationInfo`, `WindInfo`, `CurrentWeather`, `ForecastPoint`, and top-level `WeatherContext` (current + hourly forecast for next 6–12h + active alerts + `fetched_at` timestamp).

**Notes:**
- Use `pydantic.BaseModel` (already a backend dependency via FastAPI).
- `CurrentWeather.visibility_miles` and `humidity_percent` inclusion follows scoping decision 4.
- Flat module — `backend/weather_service.py`, not `backend/models/weather.py`.

---

## Chunk 2 — WeatherService class (fetch + parse + cache)

**Files:** `backend/weather_service.py`, `backend/requirements.txt`

**What to build:**

`WeatherService` class with:
- `async def get_weather_context(lat: float, lon: float) -> WeatherContext` — fetches current + forecast for coords, cache-aware.
- `_parse_nws_response(forecast, alerts)` (or provider-equivalent) — maps upstream JSON to `WeatherContext`.
- NWS two-step flow (if chosen): `GET /points/{lat},{lon}` → returns forecast URL (cached 24h); `GET <forecastHourly>` → actual weather (cached 10–15 min); `GET /alerts/active?point={lat},{lon}` for alerts.
- `User-Agent` header with real contact email (scoping decision 3).
- Parse `windSpeed` string form (`"10 mph"`, `"5 to 10 mph"`); derive `feels_like_f` from wind chill (below ~50°F) or heat index (above ~80°F) when upstream does not provide it.
- Use `aiohttp` (already a dependency via `cta_client.py`) — do not add a new HTTP library.

Add `cachetools` to `requirements.txt` if scoping decision 5 chose `TTLCache`.

**Cache design:**
- Weather cache key: rounded lat/lon (2 decimal places), TTL 10–15 min.
- Grid-point URL cache: keyed on rounded lat/lon, TTL 24 h (URL is stable per location).

**Notes:**
- Follow the existing try/except + `traceback.print_exc()` pattern from `main.py` for API failures — never raise into the `/recommend` handler.
- If the chosen provider is not NWS, adapt endpoints and parsing; the public interface (`get_weather_context` → `WeatherContext`) stays identical.

---

## Chunk 3 — Integrate into /recommend and Claude prompt

**Files:** `backend/main.py`

**What to build:**
- Instantiate a module-level `weather_service = WeatherService()` alongside `_claude_client`.
- In the `/recommend` handler, after `origin_coords` is resolved:
  ```python
  weather = None
  if origin_coords:
      try:
          weather = await weather_service.get_weather_context(
              origin_coords[0], origin_coords[1]
          )
      except Exception:
          traceback.print_exc()  # Non-fatal — proceed without weather
  ```
  `get_weather_context` is `async` — await directly like `get_train_arrivals` / `get_bus_arrivals`. Do **not** wrap in `loop.run_in_executor` (that's for CPU-bound graph ops).
- Extend `build_prompt()` signature with `weather: WeatherContext | None = None`.
- When `weather` is not None, append one concise line:
  ```
  Current weather: {condition}, {temp:.0f}°F (feels like {feels:.0f}°F), precipitation: {type}[ ({intensity})][, wind gusts {gusts:.0f} mph]
  ```
  Plus a `Weather alerts: ...` line if `weather.alerts` is non-empty.
- Update the end-of-prompt instruction from "Keep it to 3-4 sentences." to "Keep it to 3-4 sentences; incorporate weather context naturally within those sentences, not as a separate paragraph." — prevents token creep.

**Notes:**
- `max_tokens=400` stays unchanged — the response-length instruction above is the guard.
- Keep the weather summary to one line. Claude does not need a full forecast dump.

---

# Feature Crowdedness — CTA Vehicle Crowdedness Estimation

## Overview

CTA's Bus Tracker API exposes a `psgld` (passenger load) field already retrieved and normalized by `cta_client.py` to `EMPTY | HALF_EMPTY | FULL`. A request-level `bus_fullness` filter is already wired end-to-end, but **the UI toggle is currently hidden because CTA has been returning empty strings for `psgld` on all bus arrivals since at least 2026-04-09**. The train API has no equivalent field at all.

This feature adds a heuristic crowdedness estimator that produces a `CrowdednessEstimate` for each transit leg based on time period, direction of travel, position along the route, and known high-traffic stops. When live `psgld` is non-empty, the live value takes priority; otherwise the heuristic fills the gap. Claude sees an inline `[est. crowdedness: moderate]` tag on each route option so it can reason about crowding trade-offs.

**Why it matters:** Crowding is a major rider-comfort factor — parents with strollers, riders with mobility aids, and cautious travellers often accept longer trips to avoid standing-room-only vehicles. The app cannot currently signal this at all.

**Type: Bolt-On** — backend-only for the heuristic-only path. (Unhiding the `bus_fullness` UI toggle is a separate micro-change that can happen whenever CTA restores real `psgld` values.)

**Status: ⬜ Not started**

**Prerequisites:**
- Railway + Vercel deployment live (Phase 6 complete).
- All scoping decisions below resolved.

---

## Scoping decisions — pending

1. **Holiday source.** Static hand-maintained set of `YYYY-MM-DD` strings in `crowdedness.py` (no new dependency; must be updated annually) vs. the `holidays` Python library (`holidays.US(state="IL")`; adds a dependency but auto-updates). Recommendation: static list — predictable, tiny surface area, ~5 min/year maintenance.

2. **Direction mapping (`rtdir` → inbound/outbound).** Bus Tracker returns `rtdir` as `Northbound/Southbound/Eastbound/Westbound`; GTFS `direction_id` is `"0"|"1"`. Neither maps cleanly to "inbound/outbound" (needed by the direction multiplier). Two options:
   - **Per-route mapping dict** keyed on `(route_short_name, rtdir) → "inbound"|"outbound"` — accurate, but must be populated for every bus route in service (~130 CTA routes).
   - **Heuristic rule + override dict** — treat southbound/eastbound as inbound (toward the Loop), northbound/westbound as outbound, with a hand-maintained override dict for routes where the rule is wrong (cross-town, Far South Side, etc.).
   Recommendation: heuristic + override dict; populate override entries as bugs surface.

3. **High-traffic stop lists.** `HIGH_TRAFFIC_TRAIN_STATIONS` (`mapid` → multiplier) and `HIGH_TRAFFIC_BUS_STOPS` (`stop_id` → multiplier) need initial values. Two options:
   - Launch with a small curated list (~10 Loop / major transfer train stations; ~20 bus stops).
   - Launch with empty dicts; populate once rider feedback arrives.
   Recommendation: small curated train list only; bus stops empty until usage data exists.

4. **Base crowdedness scores.** Handoff proposes `{PEAK: 0.75, REGULAR: 0.45, OFF_PEAK: 0.20}` and direction multipliers `1.2 / 0.8`. Accept as-is or recalibrate? Recommendation: accept as-is — plausible priors, easier to tune with real usage data.

5. **Surfacing.** Two options:
   - **Prompt-only** — extend `_format_routes()` to append `[est. crowdedness: moderate]` per route option. Claude weaves it in. No UI change.
   - **Prompt + UI** — also serialize a `crowdedness` field per route and render a badge on the route card.
   Recommendation: prompt-only for v1; revisit UI once the heuristic is proven useful.

---

## Chunk 1 — Time period classification

**Files:** `backend/crowdedness.py` (new)

**What to build:**
- `TimePeriod` enum (`PEAK`, `REGULAR`, `OFF_PEAK`) and `DayType` enum (`WEEKDAY`, `WEEKEND`, `HOLIDAY` — holiday treated as weekend).
- `TIME_PERIOD_CONFIG` dict encoding:
  - Weekday: Peak 06:30–09:30 + 15:30–18:30; Regular 09:30–15:30 + 18:30–21:00; Off-Peak 21:00–06:30.
  - Weekend: Peak empty; Regular 09:00–21:00; Off-Peak 21:00–09:00.
- `classify_time_period(dt: datetime, holidays: Set[str] | None = None) -> tuple[TimePeriod, DayType]`.
- `CHICAGO_TZ = ZoneInfo("America/Chicago")` defined locally (do not import from `cta_client.py` — avoid coupling crowdedness to the API client).
- Holiday source per scoping decision 1.

**Notes:**
- Manually verify edge cases: boundary times (06:30, 09:30, 21:00), midnight, holidays, weekend off-peak wrap-around.

---

## Chunk 2 — Crowdedness estimation

**Files:** `backend/crowdedness.py`

**What to build:**
- Models: `CrowdednessLevel` enum (`LOW/MODERATE/HIGH/VERY_HIGH`) and `CrowdednessEstimate` Pydantic model with `score: float`, `level: CrowdednessLevel`, `confidence: str`, `factors: dict` (explainability).
- `estimate_crowdedness(route_id, direction, stop_id, stop_sequence_position, total_stops, time_period, day_type, current_hour, live_psgld="") -> CrowdednessEstimate`:
  - If `live_psgld` is non-empty → map directly (`EMPTY → LOW`, `HALF_EMPTY → MODERATE`, `FULL → HIGH`) with `confidence="high"`.
  - Else compute heuristic: `base_score * direction_multiplier * stop_position_factor * high_traffic_multiplier`, clamped `[0, 1]`; confidence `medium` at peak, `low` otherwise.
- `BASE_SCORES`, `direction_multiplier(direction, time_period, current_hour)` (splits AM/PM peak — `current_hour` is required since `TimePeriod.PEAK` alone cannot distinguish them), and `stop_position_factor(position, total)` (bell curve, `0.6 + 0.4 * sin(pos/total * pi)`).
- `rtdir_to_inbound_outbound(route_short_name, rtdir)` helper per scoping decision 2.
- `HIGH_TRAFFIC_TRAIN_STATIONS` + `HIGH_TRAFFIC_BUS_STOPS` dicts per scoping decision 3.

**Notes:**
- Verify every ID in `HIGH_TRAFFIC_*` against `backend/gtfs_data/stops.txt` — wrong IDs silently have no effect.
- Train-station keys use `mapid` (40000–49999); bus-stop keys use `stop_id` (0–29999). Keep the dicts separate.
- `stop_times.txt` is 5.8 M rows / 354 MB — do NOT load it for this module. Reuse `get_bus_stop_sequences()` in `transit_graph.py` for sequence info.

---

## Chunk 3 — Integrate into /recommend and prompt

**Files:** `backend/main.py`, `backend/transit_graph.py` (only if scoping decision 5 adds serialization)

**What to build:**
- For each ranked route, call `estimate_crowdedness()` per `TransitLeg`, using the leg's `line_code`, direction, `from_mapid`, and sequence position.
- Extend the ranked tuple from `(total, wait, route)` to `(total, wait, route, crowdedness)` (or attach the estimate to the `Route` dataclass).
- Update `_format_routes()` in `main.py` to append `[est. crowdedness: moderate]` per route option line — co-located with the route it describes, per handoff guidance. Do not add a separate `crowdedness_by_route` parameter to `build_prompt()`.
- Automatic live-override: if CTA ever restores non-empty `psgld`, the estimator already prefers it — no further change needed.

**Notes:**
- The hidden `bus_fullness` UI toggle in `App.jsx` stays hidden under this feature. Unhide only once CTA's `psgld` returns real data.

---

# Feature Weather Scoring — Weather-Adjusted Route Ranking

## Overview

Once Feature Weather and Feature Crowdedness are in place, the `/recommend` pipeline has two new context streams (`WeatherContext` + `CrowdednessEstimate`) but `_rank_routes()` still orders routes purely by `total_minutes_no_wait + wait_time`. A 10-minute walk in a blizzard ties with a 10-minute walk in mild weather; a crowded route ties with an empty one.

This feature adds a weight-adjustment layer that shifts scoring priorities based on live weather (e.g. heavy precipitation → weight outdoor exposure more heavily) and optionally re-ranks routes after the existing time-based ordering. The primary mechanism remains the Claude prompt — Claude already handles nuanced trade-offs well and now has both weather and crowdedness context.

**Why it matters:** Getting weather + crowdedness data into the prompt (Features Weather and Crowdedness) is most of the value. This feature closes the loop by letting the numeric ordering of route cards also reflect weather — so on a freezing day, a shorter-walk option can outrank a faster-but-more-exposed one by default.

**Type: Structural** — depends on Feature Weather and Feature Crowdedness.

**Status: ⬜ Not started**

**Prerequisites:**
- Feature Weather complete.
- Feature Crowdedness complete.
- All scoping decisions below resolved.

---

## Scoping decisions — pending

1. **Scope: prompt-only vs. numeric re-rank.**
   - **Prompt-only** — pass adjusted weights as a one-line hint to `build_prompt()`. `_rank_routes()` is unchanged. Low risk.
   - **Numeric re-rank** — after `_rank_routes()` produces its time-based ordering, compute a weighted score per route and reorder. Higher risk — e.g. could push a 15-min trip above a 5-min trip during rain.
   Recommendation: prompt-only for v1.

2. **Default weight values.** Handoff proposes `{travel_time: 0.35, outdoor_exposure: 0.25, crowdedness: 0.20, reliability: 0.15, transfers: 0.05}`. Accept or adjust? Recommendation: accept.

3. **Weather threshold adjustments.** Handoff proposes:
   - Heavy precipitation → outdoor_exposure +0.15, travel_time −0.10.
   - `feels_like_f < 0` → outdoor_exposure +0.20, travel_time −0.10.
   - `feels_like_f < 15` → outdoor_exposure +0.10, travel_time −0.05.
   - Gusts > 35 mph → reliability +0.05.
   Accept thresholds and deltas, or recalibrate? Recommendation: accept — Chicago-plausible priors.

4. **Module location.** `backend/route_scoring.py` (new, isolated) vs. `backend/weather_service.py` (co-located with weather models). Recommendation: `backend/route_scoring.py` — scoring and fetching are distinct concerns and easier to test separately.

---

## Chunk 1 — Scoring module and weight adjustment

**Files:** `backend/route_scoring.py` (new, per scoping decision 4)

**What to build:**
- `DEFAULT_WEIGHTS` dict per scoping decision 2.
- `adjust_weights_for_weather(base_weights: dict, weather: WeatherContext | None) -> dict`:
  - Applies threshold-based deltas per scoping decision 3.
  - Normalizes output weights to sum to 1.0.
  - Coldest-first ordering on temperature thresholds (`< 0` before `< 15`) — order matters.
  - `weather is None` → returns `base_weights` unchanged.

**Notes:**
- Unit test with fixtures: mild (no change), light rain, heavy snow, dangerous cold, high gusts. Confirm normalization.

---

## Chunk 2 — Wire weights into the prompt / ranking

**Files:** `backend/main.py`

**What to build:**

Per scoping decision 1:
- **Prompt-only path:** compute adjusted weights, then pass a short derived hint into `build_prompt()` (e.g. "Weight guidance: outdoor exposure prioritized due to heavy snow."). Claude uses this to bias the recommendation verbally.
- **Re-rank path (if chosen):** compute a per-route weighted score using `Route.walk_minutes_total` (already summed in the `Route` dataclass — no new helper) for `outdoor_exposure`, crowdedness level for `crowdedness`, etc. Sort `ranked_routes` by weighted score; keep the original time-sort as a tiebreaker.

**Notes:**
- Keep the prompt-hint to one line — `max_tokens=400` is tight.
- The "Keep it to 3-4 sentences" end-of-prompt instruction (already updated in Feature Weather Chunk 3) continues to bound response length.

---

## Chunk 3 — Verify end-to-end

**Files:** none (verification pass).

**What to check:**
- Submit a test trip with a mocked cold `WeatherContext` (`feels_like_f = -5`) and confirm the adjusted weights appear in the prompt (prompt-only path) or that route ordering shifts as expected (re-rank path).
- Regression-check a mild-weather trip: no visible change vs. pre-feature behavior.
- Verify Claude's response still fits within `max_tokens=400` (3–4 sentences).

# Feature Trip — Live Trip-in-Progress Routing

## Overview

Once a rider selects a route, the app currently goes silent — it has no awareness of whether the user is walking to the stop, waiting on the platform, riding the vehicle, or has missed their transfer. This feature activates GPS-based position tracking after the user taps "Start Trip," follows their progress through each route leg, highlights the active leg in the UI and on the map, and detects when they have meaningfully deviated from the planned route so they can be offered a re-route from their current position.

**Why it matters:** The routing recommendation is only half the job. A rider who misses a stop or takes the wrong bus has no in-app recovery path today — they must re-enter their query from scratch. Trip-in-progress mode closes that loop and makes the app genuinely useful for the entire journey, not just the planning step.

**Type: Bolt-On** — primarily a frontend feature. The backend `/recommend` endpoint already accepts arbitrary `origin` coordinates, so re-routing from current GPS position requires no new backend endpoint. No dependency on any other planned feature.

**Status: ⬜ Not started**

**Prerequisites:**
- Railway + Vercel deployment live (Phase 6 complete ✅).
- All scoping decisions below resolved before Chunk 1 begins.

---

## Scoping decisions — pending

These must be resolved before Chunk 1 begins.

1. **Trip activation: manual or automatic.**
   - **Manual (recommended):** After a route card is selected, a "Start Trip" button appears. The user taps it to activate GPS tracking. Clear, predictable, zero battery drain until the user explicitly opts in.
   - **Automatic:** GPS activates as soon as a route card is selected. Simpler UX, but GPS starts without a user consent-to-battery gesture and may fire on users just browsing routes.
   - Recommendation: manual button. Also show a "Stop Trip" button while active so the user can end tracking at any time.

2. **Leg detection algorithm.** Given the user's current GPS position, how do we determine which route leg they're on?
   - For walk legs: user is "on" the walk leg if they are within ~100 m of the leg's start or end stop, or within ~50 m of the walk path's bounding corridor.
   - For transit legs: user is "on" the leg once they've passed the boarding stop and have not yet reached the alighting stop.
   - Simpler fallback: advance the active leg when the user comes within 60 m of the leg's **end point** (alighting stop or destination). This avoids requiring shape lookup on the frontend.
   - Recommendation: simpler distance-to-endpoint rule for v1. Shape proximity can be added in a future iteration.

3. **Re-route deviation threshold.** What distance from the planned route triggers a re-route prompt?
   - Candidate thresholds: 300 m (~1 city block), 500 m, 800 m.
   - Must distinguish "slightly off the walk path" (common) from "clearly on the wrong vehicle."
   - Recommendation: 400 m from the nearest leg endpoint in the current route. Do not prompt during an active transit leg — wait until the user should have alighted and hasn't.

4. **GPS polling rate strategy.**
   - `watchPosition` with `maximumAge: 15000, timeout: 10000` gives a position fix every ~15 s.
   - Adaptive polling (lower rate on transit legs) adds complexity with marginal battery gain for typical 20–40 min trips.
   - Recommendation: single `watchPosition` call with `enableHighAccuracy: true` and `maximumAge: 15000` for all legs. Do not implement adaptive polling in v1.

5. **Re-route experience: prompted or automatic.**
   - **Prompted (recommended):** Show a banner — "You appear to be off your planned route. Re-route from here?" — and only call `/recommend` if the user taps "Re-route." Avoids surprise API calls and token spend.
   - **Automatic:** Silently call `/recommend` with current position and replace the route. Unexpected behavior; wastes Claude tokens if the user momentarily stepped off the path.
   - Recommendation: prompted. Suppress re-prompting for 90 seconds after the user dismisses the banner.

6. **Walk step completion tracking in v1.**
   - Marking individual walk steps complete as the user moves through them adds meaningful value for riders navigating an unfamiliar area.
   - Requires comparing GPS position to each step's start coordinate (already in the `walk_directions` response payload).
   - Recommendation: include in Chunk 2 — position data is already flowing by then and no additional API calls are needed.

---

## Chunk 1 — GPS tracking, trip activation UI, and map position dot

**Files:** `frontend/src/App.jsx`, `frontend/src/MapView.jsx`, `frontend/src/App.css`

**What to build:**

**App.jsx:**
- Add `tripActive` boolean state (default `false`) and `userPosition` state (`{ lat, lng } | null`).
- After a route card is selected (`selectedRouteIndex` is non-null), render a "Start Trip" button in the route card footer. On click: call `navigator.geolocation.watchPosition(...)`, set `tripActive = true`, store the `watchId` in a `useRef`.
- Render a "Stop Trip" button while `tripActive` is true. On click: `clearWatch(watchId)`, reset `tripActive = false`, `userPosition = null`.
- `watchPosition` options: `{ enableHighAccuracy: true, maximumAge: 15000, timeout: 10000 }`.
- On each position callback: update `userPosition`. On error: log to console only — do not crash or alert (GPS errors are transient).
- On route card change or new query submit: call `clearWatch(watchId)` and reset trip state.
- Pass `userPosition` and `tripActive` as props to `MapView`.

**MapView.jsx:**
- Accept `userPosition` and `tripActive` props.
- When `tripActive` is true and `userPosition` is non-null, add a GeoJSON source `"user-position"` with a Point at `[userPosition.lng, userPosition.lat]`. Render as a circle layer (`circle-color: "#4A90E2"`, `circle-radius: 10`, `circle-stroke-width: 2`, `circle-stroke-color: "#fff"`).
- Track `"user-position-source"` and `"user-position-layer"` in the existing source/layer tracking refs. When `tripActive` becomes false, set `visibility: "none"` rather than removing the layer (avoids MapLibre source-still-in-use errors).
- Center the map on `userPosition` on the first GPS fix after trip activation (one-time `flyTo`; do not re-center on subsequent position updates).

**App.css:**
- Style the "Start Trip" / "Stop Trip" button in the `.route-card` footer. "Start Trip" uses the app's primary action color; "Stop Trip" uses a muted/destructive variant.

**Notes:**
- `navigator.geolocation` requires HTTPS. Satisfied by Vercel in production; `localhost` is also a secure context.
- Do not request geolocation until the user taps "Start Trip" — premature permission prompts are commonly denied.
- `watchId` must be in a `useRef`, not state, so cleanup in both the stop button and any `useEffect` teardown closes the correct watch.

---

## Chunk 2 — Active leg tracking and walk step completion

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`, `backend/main.py` (if alight coords missing), `backend/walking.py` (if step start coords missing)

**What to build:**

**Leg advancement logic:**
- Add `activeLegIndex` state (default `null`; set to `0` on trip activation).
- On each `userPosition` update, call a pure helper `advanceLeg(pos, route, currentLegIdx)`:
  ```js
  function advanceLeg(pos, route, idx) {
    const leg = route.legs[idx];
    if (!leg) return idx;
    const end = legEndCoord(leg); // alighting stop or destination {lat, lng}
    if (haversineMeters(pos, end) < 60)
      return Math.min(idx + 1, route.legs.length - 1);
    return idx;
  }
  ```
- `haversineMeters(a, b)` — ~5 lines of inline Haversine, no library.
- `legEndCoord(leg)` — returns `{ lat, lng }` from `alight_lat`/`alight_lon` on `TransitLeg`, or destination coords on `WalkLeg`. If `alight_lat`/`alight_lon` are absent from the API response, add them to `TransitLeg` serialization in `backend/main.py`.

**Active leg UI highlighting:**
- Apply `.leg-active` to the leg at `activeLegIndex` (e.g. left border accent — must not clash with `.leg-pill` colors).
- Apply `.leg-complete` to legs at index < `activeLegIndex`: 50% opacity + ✓ icon before the leg icon.
- Future legs remain unstyled.

**Walk step completion (scoping decision 6):**
- Add `completedSteps` state: `Set<string>` of `"legIdx-stepIdx"` keys.
- On each `userPosition` update, for the active `WalkLeg`, check `haversineMeters(pos, stepStart) < 30` for each step. On match, add the step's key to `completedSteps`.
- In the expanded walk step list, render completed steps with a ✓ and reduced opacity.
- Confirm `start_lat`/`start_lon` are present on each walk direction step object. If not, add them in `backend/walking.py`'s `walk_directions()` output.
- `completedSteps` resets to `new Set()` on trip stop or new route submission.

---

## Chunk 3 — Off-route detection and re-route prompt

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`, `backend/gtfs_loader.py` (fast-path for coordinate strings)

**What to build:**

**Off-route detection:**
- Add `isOffRoute` boolean state (default `false`) and `suppressRerouteUntil` `useRef` (timestamp, default `0`).
- On each `userPosition` update: compute distance to every leg endpoint in the selected route. If the minimum exceeds **400 m** and `Date.now() > suppressRerouteUntil.current`, set `isOffRoute = true`.
- If the user returns within 400 m before tapping the banner, clear `isOffRoute = false` silently.
- Gate: only fire when the active leg is a walk leg, or when the expected transit arrival time has passed by more than 5 minutes (indicating a missed vehicle). Do not fire mid-transit-leg.

**Re-route banner:**
- When `isOffRoute` is true, render a full-width dismissible banner above the route cards:
  ```
  You appear to be off your planned route.
  [Re-route from here]   [Dismiss]
  ```
- "Dismiss": `isOffRoute = false`, `suppressRerouteUntil.current = Date.now() + 90_000`.
- "Re-route from here": call `handleSubmit()` with `origin` replaced by `"${userPosition.lat},${userPosition.lng}"` and the same `destination` already in state. After submission resolves: `activeLegIndex = 0`, `completedSteps = new Set()`, `isOffRoute = false`. GPS watch remains active.

**Backend fast-path for coordinate strings:**
- In `backend/gtfs_loader.py`'s `resolve_location()`, add a fast-path at the top before any fuzzy matching or geocoding:
  ```python
  import re
  _COORD_RE = re.compile(r"^(-?\d{1,3}\.?\d*),\s*(-?\d{1,3}\.?\d*)$")
  m = _COORD_RE.match(location.strip())
  if m:
      return float(m.group(1)), float(m.group(2))
  ```
  This prevents GPS coordinate strings (e.g. `"41.893,-87.631"`) from falling through to `geocode_google()`, which would add latency and API cost.

**App.css:**
- Banner: full-width strip between header and route cards; `background: #FFF3CD`; dark text; buttons right-aligned. Use `border-left: 4px solid #D97706` to distinguish from existing CTA alert banners (which share the amber palette).

---

## Future iteration ideas (not in scope above)

- **Live arrival countdown.** Poll arrivals every 30 s during the transit wait phase; surface "Your Blue Line arrives in 2 min" as a status line on the active leg.
- **Adaptive GPS polling.** Lower `maximumAge` to 5 s during walk legs; raise to 60 s during transit legs.
- **Shape-based deviation.** Use `clip_shape` polyline from the route response to compute true off-path distance rather than distance to endpoints.
- **Haptic / notification alerts.** Browser Notification or Vibration API for "Time to board" nudges.

---

# Future Enhancements

Post-launch ideas and improvements. These are not bugs — the app works correctly without them. Prioritize after Phase 6 deployment based on user feedback and real usage patterns.

---

---

# Feature K — Restore Street-Network Walking Graph in Production

## Overview

`backend/street_graph.graphml` is a 120 MB OSMnx pedestrian network of Chicago, used by [walking.py](backend/walking.py) (`walk_minutes`, `walk_directions`, `walk_path`) to produce street-routed walking times, turn-by-turn directions, and curved Shapely polylines for the map view. The file is committed via Git LFS but **not present at runtime in the Railway deployment**:

- Rebuilding from OpenStreetMap via `fetch_street_graph.py` OOM-kills on the Railway free memory tier.
- Pulling the LFS object at Docker build time via `media.githubusercontent.com/media/...` returns 404 (likely LFS-bandwidth quota exhausted, or LFS objects not publicly served for this repo).
- Current state (commit 954c7fa + Dockerfile change in this commit): runtime falls back to Haversine straight-line walking estimates. App is functional but walking UX is degraded — walk minutes are crow-flies, "directions" collapse to a single `"Walk"` step, and the drawn walk path is a straight line rather than following streets.

**Goal:** Get the real graphml onto the deployed container so `walking.py` loads it at startup, restoring street-routed walking. Do this without paying for a Railway memory upgrade and without depending on GitHub LFS bandwidth.

**Type: Bolt-On** — backend-only; no frontend or routing-engine changes. Restoring the graph file is transparent to all callers because the fallback path in [walking.py:53-66](backend/walking.py#L53-L66) is already in place.

**Status: ⬜ Not started**

**Prerequisites:** None. The Dockerfile already contains the preserved curl block (commented out under `--- PRESERVED FOR FUTURE RESTORATION (Feature K) ---`); restoration is mostly a matter of pointing it at a working URL.

---

## Hosting options (pick one in Chunk 1)

1. **GitHub Release asset.** Upload `street_graph.graphml` as a binary asset on a tagged release (e.g. `street-graph-v1`). Public download URL is stable, served by GitHub's CDN, and not subject to LFS bandwidth limits. **Recommended** — zero infra cost, no new accounts.
   - URL pattern: `https://github.com/AdamBHonaker/CTA-Transit-PWA/releases/download/<tag>/street_graph.graphml`
2. **Cloudflare R2.** Free tier covers 10 GB storage + 10M reads/mo. Pay $0 for this use case. Requires a Cloudflare account and one bucket.
3. **AWS S3 / Backblaze B2.** Similar to R2 but with non-zero egress cost on AWS. Avoid unless already in use.
4. **Railway volume.** Mount a persistent volume, upload the file once via `railway run`. Avoids any external host but adds a Railway resource and complicates local/dev parity. Lowest priority.

## Chunk 1 — Choose host and upload graphml

- Pick from the four options above (default: GitHub Release).
- Upload the local `backend/street_graph.graphml` (120 MB, sha256 `55a82d0fc8eadbd47289fc3e4ad37130a187622343c15f65dcabdff0a4a58afc` per the LFS pointer).
- Verify the public download URL works with `curl -fSL` and that `Content-Length` matches the local file size.

## Chunk 2 — Re-enable Dockerfile curl step

- In `backend/Dockerfile`, uncomment the block under `--- PRESERVED FOR FUTURE RESTORATION (Feature K) ---`.
- Update the `STREET_GRAPH_URL` ARG default to the new host URL.
- Keep both safety checks intact (size ≥ 1 MB; reject LFS-pointer stub).
- Optional: pin to a specific Release tag rather than `latest`/`main` so future graph regenerations don't silently change the deployed file.

## Chunk 3 — Verify in production

- Trigger a Railway redeploy.
- Watch the build log for `street_graph.graphml: <bytes> bytes` (should be ~120 MB).
- Watch the runtime startup log for `[walking] Graph loaded: <N> nodes, <M> edges` (vs. the current `Street graph not found ... Haversine fallback`).
- Spot-check one trip in the live app: confirm `walk_minutes` reports street-routed values (not Haversine), `walk_directions` returns multiple named-street steps, and the map's walk path follows actual streets rather than a straight line.

## Acceptance criteria

- Build completes without 404 on the graph URL.
- Backend logs confirm graph loaded at startup.
- Live app shows multi-step walk directions and curved walk paths on the map for at least one verified trip.
- No regression in build time beyond the ~5–10 s curl download.

## Notes / gotchas

- The graphml is regenerated by `fetch_street_graph.py` whenever the OSM bbox changes. After any regeneration, re-upload to the chosen host and (if pinned) bump the Release tag in the Dockerfile.
- If memory becomes the limiting factor again at runtime (graph load is ~300 MB resident), revisit the bbox in `fetch_street_graph.py:36` rather than abandoning street routing.
- Feature K is purely operational; once the file is reachable from the build, all routing/UX behavior is restored automatically by existing code.
- This chunk can be done in parallel with Chunk 4 (translation files) if needed — they are fully independent.

---

# Feature Favorites — Saved Locations & Routes

## Overview

Users currently must re-type their origin and destination on every visit. Commonly-used places ("Home", "Work") and regular commutes ("Home → Office") have no persistence. This feature adds a lightweight, localStorage-backed favorites system: saved **locations** (named places that quick-fill a single field) and saved **routes** (origin+destination pairs that reload an entire query with one tap).

No backend changes are needed — all state lives in the browser. The feature is additive and does not affect the routing engine, Claude prompt, or any server-side logic.

**Why it matters:** The most-common transit app interaction is the same trip, every day. Eliminating re-typing for repeat users is the highest-impact UX improvement that requires the least technical risk.

**Type: Bolt-On** — frontend-only. No dependency on any other planned feature.

**Status: ⬜ Not started**

**Prerequisites:**
- Railway + Vercel deployment live (Phase 6 complete).
- All scoping decisions below resolved.

---

## Scoping decisions — pending

1. **Save locations, routes, or both?**
   - **Locations only** — named places (e.g. "Home") that quick-fill the origin or destination field.
   - **Routes only** — origin+destination pairs.
   - **Both** — locations can fill either field; routes reload a full query.
   Recommendation: both — they serve different use cases and share almost all UI infrastructure.

2. **Storage key and schema.** Two separate localStorage keys:
   - `cta_saved_locations`: `Array<{ id: string, label: string, value: string }>` — a named place string.
   - `cta_saved_routes`: `Array<{ id: string, label: string, origin: string, destination: string }>` — a named origin+destination pair.
   Recommendation: two keys as above. Keeping them separate simplifies each CRUD path and allows independent limits.

3. **How to save a location.** Options:
   - Star/bookmark icon rendered inside each text field (right side), visible when the field has a non-empty value.
   - "Save location" button that appears after a successful query.
   Recommendation: star icon inside the field — discoverable without cluttering the post-query results area. Clicking the star when a saved location already matches the field value removes it (toggle behavior).

4. **How to save a route.** Options:
   - "Save this route" button rendered in the results header after a successful query.
   - Star icon next to the submit button.
   Recommendation: "Save this route" text button in the results header (below "Route options") — more visible and contextually clear after a query.

5. **Label input.** When saving, how does the user assign a name?
   - Auto-generate label from the text value (e.g. first 20 characters).
   - Prompt the user with a small inline input for the label.
   Recommendation: prompt with an inline input — "Home", "Work" are far more useful than truncated address strings. Default the input to the raw field value so the user can accept it quickly.

6. **Quick-access UI for locations.** Options:
   - Dropdown list that appears when a field is focused and saved locations exist (similar to browser autofill).
   - Persistent chips/pills above the form.
   Recommendation: dropdown on focus — familiar pattern, requires no persistent layout space. Show a maximum of 5 saved locations in the dropdown (oldest entry drops off if the cap is hit — see decision 7).

7. **Cap on saved items.** Unlimited vs. capped.
   Recommendation: cap at 10 saved locations and 10 saved routes. Prevents the lists from becoming unmanageable; localStorage has ample capacity. When the cap is hit on save, show a brief inline message ("Limit reached — delete a saved item to add more") instead of silently discarding.

8. **Quick-launch behavior for saved routes.** When the user selects a saved route:
   - Populate origin + destination fields only (user reviews then clicks "Get Route").
   - Populate and auto-submit.
   Recommendation: populate only — user should review before submitting, especially if live arrival data has changed.

9. **Saved routes access point.** Options:
   - A persistent section above the form listing saved routes.
   - A collapsible panel below the filter bar.
   - A "Recent / Saved" tab toggle on the form.
   Recommendation: collapsible panel below the filter bar, hidden by default. One icon/button in the filter bar toggles it. Avoids adding visual weight unless the user opts in.

10. **Feature Language integration.** If Feature Language is implemented before this feature, every user-visible string added here must receive a translation key following the same pattern used in App.jsx (see Feature Language Chunk 2). If implemented before Feature Language, add a `// i18n: needs translation key` comment above each hardcoded string so it is easy to extract later.

---

## Chunk 1 — Data layer (localStorage CRUD utilities)

**Files:** `frontend/src/favorites.js` (new)

**What to build:**

A pure utility module — no React, no side effects beyond `localStorage` reads and writes.

```js
// Location schema: { id: string, label: string, value: string }
// Route schema:    { id: string, label: string, origin: string, destination: string }

const LOC_KEY   = "cta_saved_locations";
const ROUTE_KEY = "cta_saved_routes";
const MAX_ITEMS = 10;

function _load(key)           { /* JSON.parse with fallback to [] */ }
function _save(key, arr)      { /* JSON.stringify and set */ }

export function getSavedLocations()                        { return _load(LOC_KEY); }
export function saveLocation(label, value)                  { /* append { id: crypto.randomUUID(), label, value }, enforce MAX_ITEMS, return new array */ }
export function deleteLocation(id)                          { /* filter and save */ }
export function isLocationSaved(value)                      { /* returns bool — used for star toggle state */ }

export function getSavedRoutes()                            { return _load(ROUTE_KEY); }
export function saveRoute(label, origin, destination)       { /* append, enforce MAX_ITEMS, return new array */ }
export function deleteRoute(id)                             { /* filter and save */ }
export function isRouteSaved(origin, destination)           { /* returns bool — used for save-button toggle state */ }
```

- `MAX_ITEMS` is enforced on save: if the array is already at 10, return without modifying and return `null` (caller checks for null to show the "limit reached" message).
- ID generation: use `crypto.randomUUID()` — available in all modern browsers, no library needed.
- No React imports, no side effects — this module is purely functional so it is easy to test in isolation.

**Notes:**
- Do not import from `App.jsx` or any other component — this module must be dependency-free.

---

## Chunk 2 — Saved Locations UI (star button + dropdown)

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`

**What to build:**

**Star button (save/unsave a location):**
- Render a star icon button (`★` / `☆`) inside the right edge of the "From" and "To" `<input>` wrappers, visible only when the field has a non-empty value.
- `onClick`: if `isLocationSaved(value)` → call `deleteLocation` and refresh local state. Else → show an inline label input (see below).
- Use `useState` to track `savedLocations` array (initialized from `getSavedLocations()`; updated after every save/delete).

**Label input (inline, not a modal):**
- When the star is clicked to save, replace the star with a small `<input type="text">` pre-filled with the current field value, alongside "Save" and "Cancel" buttons.
- On "Save": call `saveLocation(label, value)`. If `saveLocation` returns `null` (cap hit), show an inline error string ("Limit reached — delete a saved item first.") for 3 seconds, then restore the star. Otherwise, refresh `savedLocations` state and restore the star (now filled `★`).
- On "Cancel": restore the star unchanged.

**Dropdown on focus:**
- Wrap each `<input>` in a `<div className="field-wrapper">` (relative position).
- On `onFocus`, if `savedLocations.length > 0`, render a `<ul className="saved-dropdown">` (absolute position, below the input).
- Each `<li>` shows the label + a small delete `×` button.
- Clicking a `<li>` sets the field value and closes the dropdown.
- Clicking `×` calls `deleteLocation(id)`, refreshes state; if the list empties, close the dropdown.
- Close the dropdown on `onBlur` (use `setTimeout(0)` to allow click events on list items to fire before the blur handler removes the list).

**CSS:**
- `.field-wrapper`: `position: relative; display: flex; align-items: center;`
- `.star-btn`: `position: absolute; right: 8px; background: none; border: none; cursor: pointer; font-size: 1rem; color: var(--accent);`
- `.saved-dropdown`: `position: absolute; top: 100%; left: 0; right: 0; background: white; border: 1px solid var(--border); border-radius: 6px; list-style: none; margin: 2px 0 0; padding: 0; z-index: 100; max-height: 220px; overflow-y: auto;`
- `.saved-dropdown li`: `display: flex; justify-content: space-between; padding: 8px 12px; cursor: pointer;` + hover highlight.

**Notes:**
- The inline label input must not submit the main form when Enter is pressed — use `onKeyDown` to intercept Enter and trigger "Save" instead of form submit.
- Do not render the dropdown when the field is read-only or disabled (i.e. while a route query is in flight).

---

## Chunk 3 — Saved Routes UI (save button + quick-launch panel)

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`

**What to build:**

**"Save this route" button:**
- After a successful query (`result` is non-null), render a small "Save this route ☆" (or "Saved ★") button in the results header area, adjacent to the "Route options" heading.
- `isRouteSaved(origin, destination)` drives the filled/unfilled star state.
- On click to save: show an inline label input (same pattern as Chunk 2 — pre-filled with `"{origin} → {destination}"`, truncated to 30 chars). On confirm: call `saveRoute(label, origin, destination)`. Handle the cap error with the same inline message.
- On click to unsave: call `deleteRoute(id)` where `id` is found by matching origin+destination in `savedRoutes`.

**Saved routes panel:**
- Add a bookmark icon button (`🔖` or `⭐` — a simple Unicode glyph, no icon library) to the existing `.filters` bar.
- Clicking it toggles `showSavedRoutes` boolean state.
- When open, render a `.saved-routes-panel` `<div>` below the filter bar:
  - Heading: "Saved routes"
  - List of saved routes, each showing `label`, and small "Go" + `×` (delete) buttons.
  - Clicking "Go": call `setOrigin(route.origin)` and `setDestination(route.destination)`, then close the panel. The user reviews and submits manually (per scoping decision 8).
  - Clicking `×`: call `deleteRoute(id)` and refresh `savedRoutes` state.
  - Empty state: "No saved routes yet. Save a route after getting directions."
- Close the panel when origin/destination are populated from it (so the form is immediately visible for review).

**State management:**
- Add `savedRoutes` state (initialized from `getSavedRoutes()`; updated after every save/delete).
- `showSavedRoutes` boolean state, default `false`.

**CSS:**
- `.saved-routes-panel`: `background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px; margin-bottom: 12px;`
- `.saved-route-row`: `display: flex; align-items: center; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border);` (no border on last child).
- The panel should appear between the filter bar and the form (not overlapping the map or results).

**Notes:**
- Both `savedLocations` and `savedRoutes` state arrays should be derived from a single `useState` per type, not from repeated `getSaved*()` calls scattered through event handlers. Keep a single source of truth per list.
- If Feature Language has been implemented: add `t()` keys for all strings in this feature. If not yet implemented: add `// i18n: needs translation key` comment on every hardcoded user-visible string.
