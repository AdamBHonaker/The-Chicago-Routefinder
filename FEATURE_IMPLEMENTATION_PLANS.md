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
4. Multi-Leg Train Routing — Shared-Track Edge Deduplication — **Structural** (Dependency on Feature B, now complete)
5. Feature Language — Multi-Language Support (i18n) — **Bolt-On**
6. Feature K — Restore Street-Network Walking Graph in Production — **Bolt-On**

> Items 1–3 are prioritized chunked plans. Items 4–6 appear in the **Future Enhancements** section below — post-launch, implement based on user feedback.

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

---

# Future Enhancements

Post-launch ideas and improvements. These are not bugs — the app works correctly without them. Prioritize after Phase 6 deployment based on user feedback and real usage patterns.

---

## Multi-Leg Train Routing — Shared-Track Edge Deduplication (Route Label Accuracy)

**What happens:** For each `(from_station, to_station)` edge, `_build_graph()` keeps only the single fastest route_id. On segments where multiple CTA lines share the same track and stations (e.g. Red/Brown between Belmont and Fullerton, or Red/Purple between Howard and Belmont), the edge is labelled with whichever line was fastest in the representative GTFS trip. If a rider transfers to the other line at the shared-track start station, `_path_to_route()` sees no route_id change on the shared segment and cannot detect the correct line.

**Practical effect:** Route cards on shared-track trips may show the wrong line name for the shared segment (e.g. "Red Line" when the rider is on the "Brown Line" through the shared section). Timing is still correct — only the label can be wrong.

**Future fix:** Retain separate edges per route_id for shared-track pairs in `_build_graph()`, then handle deduplication during `_path_to_route()` using incoming line context.

> **Note:** The original approach of storing `all_routes` metadata on edges was removed in the 2026-04-15 audit (`G.add_edge(..., all_routes=candidates)` removed as dead code — the field was never read). Any implementation of this fix must use the alternative approach: store multiple edges per shared-track pair and select the correct one in `_path_to_route()` based on the incoming `TransitLeg`'s `line_code`.

**Type: Structural** — modifies `_path_to_route()`. Feature B is complete — any fix here must be written against the post-B version of `_path_to_route()` (which uses `_resolve_node()` for all node metadata). No additional dependency blockers remain.

**Status: ⬜ Not started**

---

### Verification — confirm the bug before implementing

Before any code changes, run these test queries and inspect leg labels in the JSON response:

| Trip | Shared segment to watch |
|---|---|
| Linden → Evanston/Davis (Purple Exp → Red) | Howard → Belmont: should say "Purple Line", not "Red Line" |
| O'Hare → Howard, then Howard → Belmont | If routed via Red, shared segment should say "Red Line" |
| Kimball → Merchandise Mart (Brown, all-elevated) | Belmont → Fullerton segment, if applicable |

Log the `line` field on each `TransitLeg` in the returned route. If mis-labelling is absent or rare, the fix may not be worth the complexity. If it fires consistently on the Purple/Red shared segment, proceed.

---

### Chunk 1 — Fix `_path_to_route()` to use incoming line context

**File:** `backend/transit_graph.py`

**What to change:**

The transit-leg grouping block always uses `edge.get("route_id")` and `edge.get("line")` as the canonical label for the leg. The fix: before committing to that label, check whether the incoming line (from the previous `TransitLeg`) is also a valid candidate for this edge, and prefer it if so.

```python
def _last_transit_leg(legs: list) -> TransitLeg | None:
    for leg in reversed(legs):
        if isinstance(leg, TransitLeg):
            return leg
    return None
```

In the transit-leg grouping block, after reading `group_route = edge.get("route_id", "")`:

> **Important:** `all_routes` is NOT available on edges — it was removed as dead code in the 2026-04-15 audit. The correct approach is to first update `_build_graph()` to store multiple edges per shared-track station pair (one per route_id), then use incoming line context in `_path_to_route()` to select the right one.

```python
incoming = _last_transit_leg(legs)
if incoming and incoming.line_code == edge.get("route_id"):
    pass  # already on the right edge — no override needed
elif incoming:
    # check if there is a parallel edge for the incoming line_code
    # (implementation depends on chosen graph storage approach)
    pass
```

The while-loop that merges consecutive edges uses `next_edge.get("route_id") != group_route` as the break condition — this is unchanged.

Shape lookup at the end of the block calls `get_shape(group_route, group_dir)`. After the override, `group_route` and `group_dir` should carry the correct incoming-line values.

**Edge cases:**
- First transit leg (no `incoming`): no override needed; stored label is used as-is.
- Same-station transfer WalkLeg between two transit legs: `_last_transit_leg` finds the previous `TransitLeg` correctly because it searches backward past walk legs.

**Test after:** Re-run the verification queries above. Purple Line through the Howard–Belmont segment should now label as "Purple Line".

---

# Feature Language — Multi-Language Support (i18n)

## Overview

Chicago is one of the most linguistically diverse cities in the US. Many transit riders speak languages beyond English as their primary language — including Spanish, Polish, Mandarin, Tagalog, Arabic, Urdu, Vietnamese, Pashto, Hindi, Korean, and others. Mainstream transit apps often support only English, or English plus a handful of Western European languages, leaving many Chicago residents underserved.

This feature adds full internationalization (i18n) to the frontend UI and Claude's AI-generated recommendation text, with a language selector that persists across sessions. The goal is to support a broad, community-representative set of languages — not just common Western ones.

**Why it matters:** The app's value proposition ("stop thinking about how to get there") is only fully realized for riders who can read it. Translating both the static UI text and the AI recommendation opens the app to a much larger share of Chicago's actual transit-riding population.

**Type: Bolt-On** — self-contained change to the frontend and the Claude prompt. No dependency on any routing feature.

**Status: ⬜ Not started**

---

## Scoping decisions — resolved

1. **i18n library:** Use `react-i18next` + `i18next`. This is the standard React i18n stack, well-maintained, supports RTL via HTML `dir` attribute, and handles dynamic string interpolation (e.g. "Walk {minutes} min") cleanly.

2. **Languages to support at launch.** Chosen to reflect Chicago's actual spoken-language demographics per census and community data:

   | Code | Language |
   |---|---|
   | `en` | English |
   | `es` | Spanish |
   | `fr` | French |
   | `it` | Italian |
   | `pl` | Polish |
   | `ro` | Romanian |
   | `uk` | Ukrainian |
   | `ru` | Russian |
   | `zh` | Chinese (Mandarin, Simplified) |
   | `yue` | Chinese (Cantonese, Simplified) |
   | `ja` | Japanese (Standard; furigana parenthetical notation — see decision 11) |
   | `ko` | Korean |
   | `tl` | Tagalog |
   | `vi` | Vietnamese |
   | `hi` | Hindi |
   | `gu` | Gujarati |
   | `pa` | Punjabi |
   | `ne` | Nepali |
   | `ur` | Urdu (RTL) |
   | `ar` | Arabic (RTL) |
   | `ps` | Pashto (RTL) |
   | `yo` | Yoruba |

   This list can be extended without structural changes — adding a language is just adding a translation JSON file and a menu entry.

3. **What gets translated.** All static UI strings in `App.jsx` are extracted into translation keys. The AI-generated `recommendation` text from Claude is handled separately (see decision 4). Station names, line names, and street names in leg data are **not** translated — they are proper nouns that must remain in their canonical CTA form for geographic accuracy.

4. **Claude recommendation language.** The `/recommend` backend accepts an optional `language` field in the request body. When present, `build_prompt()` appends a one-line instruction: `"Respond in {language_name}."` This causes Claude to write its recommendation in the user's language. No translation library is needed server-side — Claude handles it natively. The language code is mapped to a full language name (e.g. `"ur"` → `"Urdu"`) before being inserted into the prompt.

5. **Language selector placement.** A `<select>` in the existing header filters bar, next to the transit mode selector. Defaults to the browser's `navigator.language` if it matches a supported language; otherwise defaults to `"en"`. Persists to `localStorage` under key `"cta_language"`.

6. **RTL layout.** Arabic, Urdu, and Pashto are RTL scripts. When one of these languages is selected, set `document.documentElement.dir = "rtl"` and `document.documentElement.lang = langCode`. The existing CSS uses flexbox throughout; RTL flip requires only `direction: rtl` on `.app` plus a few targeted `margin-inline-start/end` adjustments (no full CSS rewrite needed). Test against Arabic at minimum.

7. **Translation files.** One JSON file per language at `frontend/public/locales/{code}/translation.json`. `i18next-http-backend` loads them on demand — only the active language is fetched. English (`en`) is the fallback: if a key is missing from a translation, the English string is shown.

8. **Translation source.** Machine-translate the English strings to seed all other language files (use any translation API or Claude directly during development). The translations do not need to be perfect for launch — native speakers can refine them in future PRs. Mark machine-translated files with a comment `// machine-translated, review welcome` at the top.

9. **Interpolation.** Dynamic strings (e.g. `"Walk {minutes} min to {destination}"`) use i18next's interpolation syntax: `"walk_to": "Walk {{minutes}} min to {{to}}"`. This is already how i18next works; no custom logic required.

10. **Scope of translated strings.** All strings visible to the user in `App.jsx`: form labels, placeholders, button text, status messages, error messages, route card metadata labels, leg descriptions, alerts copy, settings panel text. Strings that are CTA data (station names, line names, alert headlines from the CTA API) are not translated.

11. **Japanese furigana.** For the Claude recommendation text, use parenthetical furigana notation (`漢字（かんじ）`) rather than HTML `<ruby>` tags. This is a widely understood convention in Japanese texts aimed at general audiences, requires no HTML rendering changes on the frontend, and is safe to pass through the existing `renderMarkdown()` function. The Claude prompt instruction for Japanese is: `"Respond in Japanese. Use standard Japanese (a natural mix of hiragana, katakana, and kanji). Add furigana in parentheses after each kanji compound to aid readability — for example: 電車（でんしゃ）."` For static UI translation strings in `ja/translation.json`, include parenthetical furigana inline in the translated values for any kanji-heavy terms.

---

## Chunk 1 — Install i18n library and set up translation infrastructure

**Files:** `frontend/package.json`, `frontend/src/i18n.js` (new), `frontend/public/locales/en/translation.json` (new), `frontend/src/main.jsx`

**What to build:**

- Run: `npm install i18next react-i18next i18next-http-backend i18next-browser-languagedetector`
- Create `frontend/src/i18n.js`:
  ```js
  import i18n from "i18next";
  import { initReactI18next } from "react-i18next";
  import HttpBackend from "i18next-http-backend";
  import LanguageDetector from "i18next-browser-languagedetector";

  const SUPPORTED = ["en","es","fr","it","pl","ro","uk","ru","zh","yue","ja","ko","tl","vi","hi","gu","pa","ne","ur","ar","ps","yo"];

  i18n
    .use(HttpBackend)
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
      fallbackLng: "en",
      supportedLngs: SUPPORTED,
      backend: { loadPath: "/locales/{{lng}}/translation.json" },
      detection: {
        order: ["localStorage", "navigator"],
        caches: ["localStorage"],
        lookupLocalStorage: "cta_language",
      },
      interpolation: { escapeValue: false },
    });

  export default i18n;
  export { SUPPORTED };
  ```
- In `frontend/src/main.jsx`, import `"./i18n.js"` before rendering `<App />`. Wrap `<App />` with `<Suspense fallback={null}>` to handle async locale loading.
- Create `frontend/public/locales/en/translation.json` with all English strings extracted (see Chunk 2 for the full string inventory).

**Notes:**
- `i18next-browser-languagedetector` reads `localStorage["cta_language"]` first, then `navigator.language`. This gives the language selector (Chunk 3) automatic persistence for free.
- Do not add translations for other languages in this chunk — just the English baseline.

---

## Chunk 2 — Extract all UI strings into translation keys

**Files:** `frontend/src/App.jsx`, `frontend/public/locales/en/translation.json`

**What to build:**

Replace every hardcoded user-visible string in `App.jsx` with `t("key")` calls using the `useTranslation` hook (or `Trans` component for interpolated strings). Below is the complete inventory:

| Key | English value |
|---|---|
| `app_title` | `CTA Transit` |
| `tagline` | `Stop thinking about how to get there. Just go.` |
| `label_from` | `From` |
| `label_to` | `To` |
| `placeholder_location` | `Neighborhood, address, or building` |
| `btn_get_route` | `Get Route` |
| `btn_finding_route` | `Finding your route…` |
| `route_options_heading` | `Route options` |
| `badge_best` | `Best` |
| `label_min_total` | `{{minutes}} min total` |
| `label_no_transfers` | `No transfers` |
| `label_1_transfer` | `1 transfer` |
| `label_n_transfers` | `{{count}} transfers` |
| `wait_due` | `Due now` |
| `wait_minutes` | `{{minutes}} min wait` |
| `walk_from_origin` | `Walk {{minutes}} min to {{to}}` |
| `walk_to_destination` | `Walk {{minutes}} min to your destination` |
| `walk_transfer` | `Transfer — walk {{minutes}} min` |
| `exit_label_prefix` | `Exit:` |
| `steps_show` | `Steps` |
| `steps_hide` | `Hide steps` |
| `step_walk` | `Walk` |
| `step_head` | `Head` |
| `step_along` | `along` |
| `step_for` | `for` |
| `block_singular` | `block` |
| `block_plural` | `blocks` |
| `long_block_singular` | `long block` |
| `long_block_plural` | `long blocks` |
| `short_block_singular` | `short block` |
| `short_block_plural` | `short blocks` |
| `error_generic` | `Something went wrong. Please try again.` |
| `bus_data_partial` | `Bus arrival data partially unavailable — some results may be missing.` |
| `alerts_more` | `and {{count}} more` |
| `settings_title` | `Settings` |
| `settings_label_api_key` | `Your Anthropic API Key` |
| `settings_hint_api_key` | `Provide your own key and your usage won't count against the app's shared quota.` |
| `settings_error_key_format` | `Key must start with "sk-ant-"` |
| `settings_btn_save` | `Save` |
| `settings_btn_remove_key` | `Remove key` |
| `aria_close_settings` | `Close settings` |
| `aria_transit_mode` | `Transit mode` |
| `aria_language` | `Language` |
| `aria_settings_active` | `Settings (using your API key)` |
| `aria_settings` | `Settings` |
| `aria_loading` | `Finding your route` |
| `mode_all` | `All modes` |
| `mode_train` | `Train` |
| `mode_bus` | `Bus` |

Add each key to `frontend/public/locales/en/translation.json`. In `App.jsx`, call `const { t } = useTranslation()` at the top of each component that uses translated strings.

**Notes:**
- `formatBlocks()` becomes a call to `t()` with appropriate singular/plural keys — i18next's built-in plural handling (`_one`, `_other` suffixes) can be used, but for simplicity in Chunk 2, just use separate singular/plural keys as listed above.
- The `"and X more"` alerts string uses `Trans` or a simple template: `t("alerts_more", { count: result.alerts.length - 3 })`.
- Do not yet add the language selector in this chunk — just wire up `t()` calls against English strings and verify the app still works identically.

---

## Chunk 3 — Add language selector to header

**Files:** `frontend/src/App.jsx`

**What to build:**

- Import `{ useTranslation }` and `{ SUPPORTED }` from `./i18n.js`.
- Add a `<select>` in the `.filters` div, adjacent to the transit mode selector:
  ```jsx
  const { i18n, t } = useTranslation();

  <select
    value={i18n.language}
    onChange={(e) => i18n.changeLanguage(e.target.value)}
    aria-label={t("aria_language")}
  >
    {SUPPORTED.map((code) => (
      <option key={code} value={code}>{LANGUAGE_NAMES[code]}</option>
    ))}
  </select>
  ```
- Add `LANGUAGE_NAMES` constant in `App.jsx` (not in a translation file — these are the native-script names displayed to speakers of each language):
  ```js
  const LANGUAGE_NAMES = {
    en: "English",    es: "Español",      fr: "Français",    it: "Italiano",
    pl: "Polski",     ro: "Română",       uk: "Українська",  ru: "Русский",
    zh: "中文（普通话）",  yue: "粤语",         ja: "日本語",       ko: "한국어",
    tl: "Filipino",   vi: "Tiếng Việt",   hi: "हिंदी",        gu: "ગુજરાતી",
    pa: "ਪੰਜਾਬੀ",     ne: "नेपाली",        ur: "اردو",         ar: "العربية",
    ps: "پښتو",        yo: "Yorùbá",
  };
  ```
- Wire RTL: add a `useEffect` that watches `i18n.language` and sets `document.documentElement.dir` and `document.documentElement.lang`:
  ```js
  const RTL_LANGS = new Set(["ar", "ur", "ps"]);
  useEffect(() => {
    document.documentElement.dir = RTL_LANGS.has(i18n.language) ? "rtl" : "ltr";
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);
  ```
- `i18n.changeLanguage()` automatically persists to `localStorage["cta_language"]` via the detector config in Chunk 1.

**Notes:**
- Native-script language names (العربية, 中文, etc.) must appear in the `<option>` elements — not English names — so a speaker of that language can find their own language in the list.
- At this point, switching to a non-English language will show English strings (fallback) because other translation files don't exist yet. That is expected. Test that the selector persists across page refreshes and that RTL flip works for Arabic.

---

## Chunk 4 — Create translation files for all supported languages

**Files:** `frontend/public/locales/{es,fr,it,pl,ro,uk,ru,zh,yue,ja,ko,tl,vi,hi,gu,pa,ne,ur,ar,ps,yo}/translation.json`

**What to build:**

For each language code, create `frontend/public/locales/{code}/translation.json` containing translations of every key from the English file. Seed using machine translation (use Claude or any translation API).

Guidelines for each translation:
- Keep dynamic placeholders (`{{minutes}}`, `{{to}}`, `{{count}}`) exactly as they appear in the English source — i18next requires them to match.
- Transit-specific terms like "Bus", "Train" should be translated naturally in context.
- "CTA Transit" in `app_title` should not be translated — it is a proper name.
- For RTL languages (ar, ur, ps): the JSON values themselves are RTL text, but the JSON file format and keys remain LTR. No special file encoding needed.

Add a comment at the top of each non-English file (as a `"_comment"` key): `"machine-translated, review welcome"`.

**Notes:**
- 22 languages × ~45 keys = ~990 string translations total. Seed in one or two Claude sessions, grouping by script family for consistency.
- For `ja/translation.json`: include parenthetical furigana inline in values for kanji-heavy terms (e.g. `"btn_get_route": "経路（けいろ）を取得（しゅとく）"`) — no special tooling needed.
- After seeding, do a spot-check on at least 3 languages by switching the selector and reading through the UI.
- RTL languages: verify that Arabic, Urdu, and Pashto text renders correctly in-browser and that the layout flips properly (form labels on the right, chevron on the left, etc.).

---

## Chunk 5 — Backend: Pass language to Claude prompt

**Files:** `backend/main.py`

**What to build:**

- In the `/recommend` endpoint, read `language: str | None = None` from the request body (add to the request schema).
- Add a `LANGUAGE_NAMES` dict in `main.py` mapping all 22 language codes to their full English names. English names are used in the prompt because that is Claude's instruction language:
  ```python
  LANGUAGE_NAMES = {
      "en": "English",           "es": "Spanish",            "fr": "French",
      "it": "Italian",           "pl": "Polish",             "ro": "Romanian",
      "uk": "Ukrainian",         "ru": "Russian",            "zh": "Mandarin Chinese",
      "yue": "Cantonese Chinese","ja": "Japanese",           "ko": "Korean",
      "tl": "Filipino (Tagalog)","vi": "Vietnamese",         "hi": "Hindi",
      "gu": "Gujarati",          "pa": "Punjabi",            "ne": "Nepali",
      "ur": "Urdu",              "ar": "Arabic",             "ps": "Pashto",
      "yo": "Yoruba",
  }
  ```
- In `build_prompt()`, add an optional `language: str | None = None` parameter. If non-null and not `"en"`, construct the closing instruction based on the language:
  - For Japanese (`language == "ja"`): append `"Respond in Japanese. Use standard Japanese (a natural mix of hiragana, katakana, and kanji). Add furigana in parentheses after each kanji compound to aid readability — for example: 電車（でんしゃ）."`
  - For all other non-English languages: append `"Respond in {LANGUAGE_NAMES[language]}."`
- In `main.py`, pass `language=language` (the raw code from the request) directly to `build_prompt()`.
- In the frontend `handleSubmit`, include `language: i18n.language` in the request body alongside `origin`, `destination`, and `transit_mode`.

**Notes:**
- If `language` is `"en"` or absent, do not append any instruction — Claude defaults to English already, and adding it wastes tokens.
- This is the only backend change for this feature. No translation library, no additional dependencies.
- Claude handles all listed scripts (Arabic, Urdu, Pashto, Cyrillic, Devanagari, CJK, etc.) natively.
- Test manually: set language to Urdu in the selector, submit a query, and verify that the recommendation text is in Urdu script. Set to Japanese and verify parenthetical furigana appears.

---

## Chunk 6 — CSS: RTL layout adjustments

**Files:** `frontend/src/App.css`

**What to build:**

Audit the existing CSS for properties that break under RTL and replace with logical properties or add `[dir="rtl"]` overrides. Key areas to check:

- Any `margin-left` / `margin-right` or `padding-left` / `padding-right` on flex children that creates visual asymmetry under RTL. Replace with `margin-inline-start` / `margin-inline-end` where safe, or add targeted `[dir="rtl"]` overrides.
- `.leg-pill` — floated or flex-start positioned; verify it aligns correctly when the row direction flips.
- `.route-chevron` — `▲` / `▼` chevrons don't flip; `◄` / `►` would need to, but these aren't used. No change needed.
- `.alerts-more` link — verify text alignment under RTL.
- Form layout — `<label>` spans should right-align under RTL; `text-align: start` (already logical) handles this if used.

**Acceptance criteria:**
- No text or element visually overlaps under Arabic, Urdu, or Pashto.
- Form inputs, buttons, and route cards all read correctly right-to-left.
- LTR layout (English and all other languages) is unchanged.

**Notes:**
- Do not rewrite the entire CSS file. Only change properties where a visual bug is confirmed in-browser.
- Test by selecting Arabic, Urdu, and Pashto in the language selector and visually inspecting the full app flow: form → submit → route cards → walk steps.

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
