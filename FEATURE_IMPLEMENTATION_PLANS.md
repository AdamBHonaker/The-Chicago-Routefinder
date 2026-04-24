# Feature Plans

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
4. Feature K — Restore Street-Network Walking Graph in Production — **Bolt-On**

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

## Scoping decisions — partially resolved

Decision 1 was resolved before Chunk 1 began.

1. **Primary weather API provider.** **Decision: Weather.gov (NWS)** — free, unlimited, no API key, reliable for US. No dedicated "current conditions" endpoint (first hourly period is used as current); `feels_like_f` must be derived; visibility/humidity require a second call. Requires a real contact email in the `User-Agent` header.

2. **Secondary / fallback provider.** Options:
   - A second provider as fallback if the primary errors, or single provider only? Adds complexity and (for paid APIs) a second key/quota. Recommendation: none at launch; add only if the primary proves flaky in production.

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

## Scoping decisions — partially complete

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

4. **Module location.** `backend/route_scoring.py` (new, isolated) Scoring and fetching are distinct concerns and easier to test separately.

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
