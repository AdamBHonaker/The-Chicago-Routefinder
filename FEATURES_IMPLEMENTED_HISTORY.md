# Features Implemented History

A log of features that have been designed and fully implemented. Entries are moved here from `FEATURE_IMPLEMENTATION_PLANS.md` when complete.

> **Process:** When a feature in `FEATURE_IMPLEMENTATION_PLANS.md` is finished, **delete its entry from that file** and add a corresponding entry here summarizing what was built. `FEATURE_IMPLEMENTATION_PLANS.md` should only ever contain features that have not yet been implemented.

---

## Feature Index

**Bolt-On** = self-contained, no dependencies on other planned features.
**Structural** = depends on one or more other features before it can be fully built or realized.

1. Feature Weather UI — Weather Strip Display — **Bolt-On** (depends on Feature Weather ✅)
2. Feature Precip Walk — Precipitation Walk-Speed Penalty — **Bolt-On**
2. Feature Departure Window — Optimal Departure Timing Hint — **Bolt-On**
3. Feature Weather Scoring — Weather-Adjusted Route Ranking — **Structural** (depends on Feature Weather ✅ + Feature Crowdedness ✅)
4. Feature Crowdedness — CTA Vehicle Crowdedness Estimation — **Bolt-On**
5. Feature Weather — Live Weather Integration — **Bolt-On**
5. Feature Autocomplete — Location Input Suggestions — **Bolt-On**
3. Feature A — Train Station Exit Guidance — **Bolt-On**
4. Feature C — Multi-Leg Bus Routing (Bus + Bus Transfers) — **Bolt-On**
5. Feature D — Live Arrivals at Transfer Stop — **Structural** (Dependency on Feature C)
6. Feature E — Walk Leg Street-Level Distance Detail — **Bolt-On**
7. Feature F — Street Abbreviation Normalization — **Bolt-On**
8. Feature G — Long/Short Block Classification — **Bolt-On** (Dependency on Feature E)
9. Feature B — Intermodal Routing (Train + Bus) — **Structural** (Dependency on Feature C)
10. Feature H — Deduplicate Same-Line Station Candidates — **Bolt-On** (Dependency on Feature B)
11. Feature I — CTA Alerts Integration — **Bolt-On**
12. Rate Limiting — **Bolt-On**
13. BYOK (Bring Your Own API Key) — **Bolt-On**
14. Claude Response Caching — **Bolt-On**
15. Multi-Leg Train Routing Gap 2 (Bus First/Last Mile) — **Structural** (Resolved by Feature B)
16. Feature J — Deprecate `find_bus_routes()` in Favor of Unified Graph — **Bolt-On** (Dependency on Feature B)
17. Claude Haiku for Simple Queries — **Bolt-On**
18. Multi-Leg Train Routing — Shared-Track Edge Deduplication — **Structural**
19. Feature Language — Multi-Language Support (i18n) — **Bolt-On**
20. Feature Trip — Live Trip-in-Progress Routing — **Bolt-On**
21. Feature Favorites — Saved Locations & Routes — **Bolt-On**
22. Feature DAU — Daily Unique User Counting — **Bolt-On**
23. Feature MultiLine — Multi-Pattern Train Graph — **Bolt-On**
24. Feature WalkMode — Walk-Only Transit Mode — **Bolt-On**
25. Feature Walk Speed — Walking Speed Preference — **Bolt-On**
26. Feature Pinned Stops — Saved-Stop Arrivals Board — **Bolt-On**
27. Feature Last Train — Last Train Countdown — **Bolt-On**
28. Feature Crowdedness — CTA Vehicle Crowdedness Estimation — **Bolt-On**
29. Feature Service Alerts — CTA Service Alerts Feed — **Bolt-On**
30. Feature K — Restore Street-Network Walking Graph in Production — **Bolt-On**
31. Feature Heritage — Editorial Almanac Redesign — **Bolt-On**
32. Feature MapMarkers — Editorial On-Map Symbols — **Bolt-On**

---

# Feature MapMarkers — Editorial On-Map Symbols

**Completed: 2026-04-30**

**Overview:** Replaced the three legacy on-map symbols (a blue circle origin dot, a dark circle destination dot, and a pulsing blue `circle` layer for live position) with the three orthogonal editorial marks defined in *Specimen E · Map Marks* of the Chicago Routefinder design system. The new marks are deliberately distinct silhouettes — § square, ✦ concentric ring, ➤ compass needle — so they cannot be confused at any zoom level. All three are self-contained React SVG components mounted as MapLibre `Marker` elements via `ReactDOM.createRoot`.

**What was implemented:**

- **`OriginMarker.jsx`** (`frontend/src/components/markers/`) — italic silcrow § inside a double-ruled ink square on a cream paper backing. Supports an optional `label` / `flagSide` flag.
- **`DestinationMarker.jsx`** — surveyor's crosshair ring (concentric circle + four ticks + bullseye) on a cream backing. Supports an `arrived` boolean: when true the ring fills solid ink, the crosshair/ticks hide, and an italic "arrived" caption appears. Label weight 500 to match `OriginMarker` (both are coordinates, neither is primary).
- **`LivePositionMarker.jsx`** — rust compass needle inside a pulsing rust ring on a cream backing. Heading-aware: CSS `transform: rotate()` on the needle group with a 200 ms linear transition. Pulse ring uses SMIL `<animate>` nodes that are conditionally not rendered (not just paused) when `reducedMotion={true}`, since `animation-play-state` doesn't reliably pause SMIL in all browsers.
- **`MapView.jsx`** — `renderOriginDestMarkers` (MapLibre circle layers) deleted. Module-level `prefersReducedMotion`, `smoothHeading` (circular EMA, alpha=0.3, wrap-aware), `haversineMetres`, `mountMarker`, and `removeMarker` helpers added. Five new refs: `originMarkerRef`, `destMarkerRef`, `liveMarkerRef`, `smoothedHeadingRef`, `arrivedRef`. Route effect now mounts React origin/dest markers after polylines (preserving coord-fallback logic). User-position circle layer effect replaced with `LivePositionMarker` logic: heading EMA, 50 m arrived latch (one-way, trip-scoped), fly-to on first GPS fix, center-follow while locked.
- **`App.css`** — Added scoped `@media (prefers-reduced-motion: reduce) { .marker-live-position animate { animation-play-state: paused !important; } }` as a belt-and-suspenders fallback.

**Key design decisions:**
- MapLibre integration uses Option A (imperative `maplibregl.Marker` + `ReactDOM.createRoot`) — no `react-map-gl` dependency introduced.
- CSS `transform` via `style` on the needle group — SVG `transform` *attributes* do not respond to CSS transitions.
- `prefersReducedMotion` is a module-level snapshot (page-load only, intentional) — a full reload picks up OS changes.
- Arrived latch is a `useRef` boolean, never reverses during an active trip even if GPS drifts past the 50 m threshold.
- Labels are omitted when mounting markers on the map; place names surface only in the bottom-sheet route summary.
- Z-order: render origin → destination → user in DOM order so user paints last (on top).

**Files changed:**
- `frontend/src/components/markers/OriginMarker.jsx` — new file
- `frontend/src/components/markers/DestinationMarker.jsx` — new file
- `frontend/src/components/markers/LivePositionMarker.jsx` — new file
- `frontend/src/MapView.jsx` — removed `renderOriginDestMarkers`; replaced user-position circle layer; added marker utilities and refs
- `frontend/src/App.css` — added `.marker-live-position` reduced-motion CSS

---

# Feature Heritage — Editorial Almanac Redesign

**Completed: 2026-04-28**

**Overview:** Replaced the app's original dark-themed, utility-first UI with "The Chicago Routefinder" editorial almanac design system — an 11-step CSS and JSX redesign covering every surface. The new visual language uses cream paper, charcoal ink, rust accents, Fraunces italic serif headlines, Inter sans body, and hairline rules throughout. No routing logic, hooks, or API contracts were touched — all changes are presentational.

**What was implemented (11 steps):**

- **Step 1 — Tokens + fonts:** Added `:root` design tokens to `App.css` (paper/ink/rust/navy/field/lake/river, type scale, spacing, motion). Added Google Fonts to `index.html`: Fraunces, Inter, JetBrains Mono.

- **Step 2 — Header masthead:** Restyled `.header` to a newspaper masthead with folio date/vol line, thick rule, two-weight serif title, and tagline. Controls restyled as `btn-ghost-icon` (hairline border, no radius). Language + transit mode selects use `.masthead-select`.

- **Step 3 — Tab bar:** Fixed bottom 4-tab bar (Home / Map / Alerts / Saved) on mobile ≤ 800px. `data-active-tab` on `.app` drives CSS panel visibility. Tab labels: serif italic inactive, roman + rust underline active.

- **Step 4 — Form + LocationInput:** `.form` → cream-paper panel with `var(--rule)` border, no rounded corners. Inputs: serif 19/600, transparent background, `var(--dashed)` between-field divider. Submit button → full-width ink primary serif italic. LocationInput suggestions: `var(--paper-bright)`, no radius, `var(--rust)` highlight.

- **Step 5 — RouteCard:** Drop-cap minutes: 72px Fraunces italic (capped 56px at ≤ 359px). `★ Recommended Path` kicker in rust Inter 800 caps. Hairline between cards, no shadow. Selected: 2px `var(--rust)` border-inline-start. Legs: hairline list, 7×7 square markers, `LinePill size="sm"`, serif walk text. Trip footer: `var(--rule-thick)` top, primary "Commence Journey ⟶" / secondary stop. Off-route banner → `.special-dispatch--delay`.

- **Step 6 — Pinned Stops + Service Alerts + Weather:** `PinnedStopsBoard.jsx`: editorial paper bg, caps header + signal lamp + refresh `↺`, mono ETA. `ServiceAlertsBar.jsx`: collapse toggle removed; each alert is a `.special-dispatch` block (Major→delay/rust, Minor→notice/navy, Planned→minor/mute). `WeatherStrip.jsx`: paper bg, hairline borders, mono temp + serif italic condition. Added `@keyframes flicker` signal lamp with `prefers-reduced-motion` fallback.

- **Step 7 — Settings + Saved Routes panels:** `SettingsPanel.jsx`: full-screen modal via `position: fixed; inset: 0; z-index: 500`; cream backdrop click-to-close; "⟡ Preferences ⟡" caps header; native checkbox styled via hidden input + sibling span; walk-speed chips border active fills ink; BYOK underline-only input. `SavedRoutesPanel.jsx`: inline editorial panel; caps "SAVED VOYAGES"; serif label + italic ghost "go →" + ghost delete `×`. Dead CSS removed.

- **Step 8 — Live Trip footer + radar-pulse active leg:** Added `@keyframes radar-pulse` (box-shadow glow, 2s ease-out infinite). `.leg-active::after` pseudo-element: 6×6 rust dot centered on the 2px left border, pulsing outward. `.leg-active .leg-text`: ink color, weight 600. `.leg-complete .leg-text`: line-through italic. `on-vehicle-btn` padding bumped to `8px 14px`. `prefers-reduced-motion: reduce` suppresses radar-pulse.

- **Step 9 — Loading skeleton + map overlays:** `LoadingSkeleton.jsx`: replaced shimmer bars with "Plotting…" (22px Fraunces italic) + `.plot-rule` animated hairline + 3 ghost lines. `.transit-photo-caption`: replaced dark hexes with editorial tokens + `::before` "Fig. —" caps prefix. `.map-unlock-btn`: restyled to cream/ink/hairline/serif-italic. `MapView.jsx`: imported `BUS_DIRECTION_COLORS` + `LinePill`; added bottom-left `.map-legend` (distinct transit line pills) and top-right `.map-train-card` (kicker "Underway" + LinePill + from→to, shown when `tripActive`).

- **Step 10 — RTL pass:** `text-align: left` → `text-align: start` on `.route-card-header`. `margin-left: auto` → `margin-inline-start: auto` on `.pin-btn`. Added `@media (prefers-contrast: more)` block: `--hairline` → `2px solid var(--ink)`, `--dashed` → `1px dashed var(--ink)`, `--mute-fog` → `var(--mute)` — propagates to all hairline borders app-wide automatically.

- **Step 11 — Cleanup:** Replaced all remaining dark-theme hex values with editorial tokens in: `.error-boundary`, `.panel-map`, `.error`, `.data-warning`, `.map-error`, `.map-unlock-btn:hover`. MapLibre GL paint properties (`"circle-color"`, `"line-color"` etc.) correctly exempted — must be hex literals for GL style engine. Locale audit: all 57 `t()` keys present in EN file; 22 locale files confirmed; no regressions.

**Files changed:**
- `frontend/src/App.css` — Complete redesign; ~2200+ lines; all dark-theme hex removed; design tokens + all step CSS added
- `frontend/src/App.jsx` — Tab bar wiring (`data-active-tab`), `on-vehicle-btn` markup, `handleReroute` integration
- `frontend/index.html` — Google Fonts (Fraunces, Inter, JetBrains Mono) added
- `frontend/src/components/LoadingSkeleton.jsx` — Full rewrite (plot-rule skeleton)
- `frontend/src/components/PinnedStopsBoard.jsx` — Editorial reskin
- `frontend/src/components/ServiceAlertsBar.jsx` — Collapse toggle removed; `.special-dispatch` blocks
- `frontend/src/components/WeatherStrip.jsx` — Editorial reskin
- `frontend/src/components/SettingsPanel.jsx` — Full modal reskin
- `frontend/src/components/SavedRoutesPanel.jsx` — Editorial reskin
- `frontend/src/MapView.jsx` — `BUS_DIRECTION_COLORS` + `LinePill` imports; `.map-legend` + `.map-train-card` overlays

**Key design decisions:**
- `SettingsPanel` uses `position: fixed; inset: 0; z-index: 500` — works even though it renders inside `panel-cards` (overflow-y: auto does NOT create a containing block for fixed-position children)
- `ServiceAlertsBar` no longer has a collapse toggle — each alert renders directly as `.special-dispatch` block
- Signal lamp uses CSS `@keyframes flicker` + `prefers-reduced-motion: reduce` disables it
- Radar-pulse dot uses `inset-inline-start: -4px` to center a 6px dot on the 2px left border
- `prefers-contrast: more` overrides CSS custom properties at `:root` so every `var(--hairline)` thickens automatically without touching individual rules
- MapLibre GL paint hex values (`#4a9eff`, `#ffffff` etc.) are exempt from dark-hex removal — GL style engine cannot use CSS variables

---

# Feature K — Restore Street-Network Walking Graph in Production

**Completed: 2026-04-28**

**Overview:** `backend/street_graph.graphml` (79 MB OSMnx pedestrian network of Chicago) was absent at Railway runtime — rebuilding OOM-kills on the free tier and the old GitHub LFS download URL returned 404. The app was falling back to Haversine straight-line walking estimates throughout. This feature hosts the graphml as a GitHub Release asset and re-enables the Dockerfile curl step, transparently restoring street-routed walking, turn-by-turn directions, and curved walk-path polylines across the entire app.

**What was implemented (2 chunks):**

- **Chunk 1 — GitHub Release upload:**
  - Created release tag `street-graph-v1` on `AdamBHonaker/CTA-Transit-PWA` via `gh release create`.
  - Uploaded `backend/street_graph.graphml` (81,789,243 bytes / ~78 MB) as a release asset.
  - Asset URL: `https://github.com/AdamBHonaker/CTA-Transit-PWA/releases/download/street-graph-v1/street_graph.graphml`
  - Note: repo is private — download requires a GitHub PAT with `repo` or `contents:read` scope (see Dockerfile comment and Chunk 2 below).

- **Chunk 2 — Dockerfile (`backend/Dockerfile`):**
  - Removed the old commented-out LFS URL block and the degradation notice.
  - Added `ARG STREET_GRAPH_URL` (defaulting to the `street-graph-v1` release asset URL) and `ARG GITHUB_TOKEN`.
  - `RUN` step: conditionally passes `-H "Authorization: Bearer $GITHUB_TOKEN"` when the build arg is set, then performs the same two safety checks as before (size ≥ 1 MB; reject LFS pointer stub).
  - **Railway setup required (one-time):** In the Railway service → Settings → Build → Build Arguments, add `GITHUB_TOKEN=<PAT>`. The PAT needs `Contents: Read` scope on the repo. This is a build-time secret only — not stored in the image.
  - For future graph regenerations (NorthExpansion, SouthExpansion): run `python fetch_street_graph.py --force`, create `street-graph-v2` (etc.) via `gh release create`, and update `STREET_GRAPH_URL` in the Dockerfile.

**Chunk 3 (production verification — requires manual Railway redeploy):**
- Trigger a Railway redeploy and confirm build log shows `street_graph.graphml: 81789243 bytes`.
- Confirm runtime startup log shows `[walking] igraph loaded: N vertices, M edges` (not `Street graph not found ... Haversine fallback`).
- Spot-check one trip: walk directions should return multi-step named-street routes; walk path on map should follow streets rather than a straight line.

**Files changed:** `backend/Dockerfile`
**External actions:** GitHub Release `street-graph-v1` created with `street_graph.graphml` asset.

---

# Feature Weather UI — Weather Strip Display

**Completed: 2026-04-27**

**Overview:** The already-fetched `WeatherContext` (from Feature Weather) was invisible to riders — they could only see weather through Claude's prose. A compact `WeatherStrip` component now appears at the top of every result set, showing temperature, short forecast, precipitation badge, and wind gusts at a glance. Active NWS alerts render as an amber one-liner below. A "Feels Like" temperature was added in a follow-up fix (BUG-030, 2026-04-30) — see below.

**What was implemented (2 chunks):**

- **Chunk 1 (`backend/main.py`):**
  - Added `weather: "WeatherContext | None" = None` parameter to `_format_response()`.
  - Serializes the weather context into the response under a new `"weather"` key: `{ temperature_f, feels_like_f, short_forecast, precipitation_type, precipitation_intensity, wind_gust_mph, alerts }`. `null` when weather is unavailable.
  - Updated both `_format_response()` call sites to pass `weather=walk_weather` (Walk mode path) and `weather=weather` (main routing path). Purely additive — callers that don't read the new key are unaffected.

- **Chunk 2 (frontend + i18n):**
  - `frontend/src/components/WeatherStrip.jsx` (new): Props `weather` (serialized object or null). Returns `null` when weather is null. Line 1: temperature + short forecast text + precipitation badge (shown when `precipitation_type !== "none"`) + wind gust note (shown when `wind_gust_mph >= 15`). Line 2 (optional): amber alert bar `⚠ NWS: {alerts[0]}` when alerts present, truncated to 80 chars.
  - `frontend/src/App.jsx`: Added `WeatherStrip` import. Added `weather: data.weather || null` to `setResult` in both `handleSubmit` and `handleReroute`. Mounts `<WeatherStrip weather={result.weather} />` at the top of the `.results` div, above the recommendation text.
  - `frontend/src/App.css`: Added `.weather-strip` (0.85rem, cream-forward `var(--color-surface)` bg, `var(--color-border)` bottom border), `.weather-strip__main` (flex-wrap row), `.weather-strip__badge` (small pill), and `.weather-strip__alert` (`#fef3c7` amber bg, `#2c2c2c` text, 0.8rem). CSS variables include fallbacks for the current dark theme; tokens will activate fully with Feature Heritage.
  - All 22 `frontend/public/locales/*/translation.json` files: Added `weather_feels_like` (`"feels like {{temp}}°F"` / native-language equivalents) and `weather_nws_alert` (`"NWS: {{headline}}"`) keys. NWS short-forecast text remains English (NWS data is English-only).

**Post-launch fix (2026-04-30 BUG-030):** `feels_like_f` was sent by the backend but not rendered. Fixed in `WeatherStrip.jsx`: now shows `/ feels N°` inline with the temperature when the apparent temperature differs from the actual by ≥ 2°F.

---

# Feature Precip Walk — Precipitation Walk-Speed Penalty

**Completed: 2026-04-27**

**Overview:** Automatically applies a walk-time multiplier based on live precipitation conditions before route ranking. Walk legs are made longer on rainy, snowy, icy, cold, or windy days — reflecting real reduced walking speed — without requiring the rider to manually select "Slow" pace.

**What was implemented (both chunks in `backend/main.py`):**

- **`_precip_walk_factor(weather: WeatherContext | None) -> float`** (placed after `_scale_walk_legs`): Returns a ≤1.0 multiplier from three penalty tiers:
  - *Precipitation type/intensity*: no precip → 1.00; light rain/drizzle → 0.96; moderate rain → 0.90; heavy rain → 0.82; light snow/flurries → 0.92; moderate snow → 0.84; heavy snow/blizzard → 0.74; freezing rain or sleet → 0.78.
  - *Wind penalty*: gusts > 35 mph → additional ×0.90 (Chicago elevated-platform hazard).
  - *Extreme cold floor*: feels_like_f < 0°F → additional ×0.88 (bulky clothing, ice patches).
  - Hard floor of 0.60 prevents absurd stacked-penalty results (e.g. blizzard + dangerous wind + extreme cold).
- **`_run_routing()` updated**: gains a `weather: WeatherContext | None = None` parameter. Computes `effective_speed = request.walk_speed * _precip_walk_factor(weather)` and passes it to both `_scale_walk_legs` calls (unified-graph routes and bus-transfer routes). Single combined call per scoping decision 4.
- **Walk mode updated**: `walk_effective_speed = request.walk_speed * _precip_walk_factor(walk_weather)` applied to `walk_min` inline in the Walk-mode early-return branch.
- **Execution order change**: weather is now fetched with a standalone `await _safe_weather(origin_coords)` before `_run_routing()`. Removed from the subsequent `asyncio.gather(get_alerts, get_route_statuses)` call — alerts and route statuses are still concurrent.

**Scoping decisions taken:**
1. All precipitation multipliers accepted as proposed (conservative, Chicago-appropriate).
2. Wind penalty (×0.90 at >35 mph gusts) included.
3. Extreme cold floor (×0.88 at feels_like < 0°F) included.
4. Combined into one `_scale_walk_legs` call: `effective_speed = walk_speed * precip_factor`.
5. Weather fetch moved before routing (serial single await, uses 12-min cache so negligible latency).

---

# Feature Service Alerts — CTA Service Alerts Feed

**Completed: 2026-04-27**

**Overview:** Fetches all active CTA service alerts (delays, reroutes, outages) from the CTA Customer Alerts XML API and surfaces them as a collapsible bar on the home view (above the search form) and as small ⚠ warning badges on route card transit legs for affected routes.

**What was implemented (2 chunks):**

- **Chunk 1 (`backend/main.py` — new `GET /alerts` endpoint):**
  - `import xml.etree.ElementTree as ET` and `import aiohttp` added to imports.
  - `_ALERTS_CACHE_TTL = 300`, `_alerts_cache` (5-min `OrderedDict` TTL cache, single key `"alerts"`).
  - `GET /alerts`: fetches `http://www.transitchicago.com/api/1.0/alerts.aspx?outputType=XML&accessibility=N` with `aiohttp`, parses XML, maps each `<Alert>` to `{ alert_id, headline, short_description, routes, severity }`. Severity: score ≥ 70 → Major, 40–69 → Minor, < 40 → Planned. Route names normalized (`removesuffix(" Line")` so "Red Line" → "Red"). Sorted Major → Minor → Planned. Returns `{ "alerts": [] }` on any failure; logs via `traceback.print_exc()`; never raises.

- **Chunk 2 (frontend):**
  - **`frontend/src/components/ServiceAlertsBar.jsx`** (new): Props `alerts`, `onDismiss(alertId)`. Returns `null` when no alerts. Collapsed default shows count badge; expanded shows alert cards sorted Major → Minor → Planned with severity badge, route list, headline, short description, and dismiss button.
  - **`frontend/src/components/RouteCard.jsx`**: Added `activeAlertRoutes: Set<string>` prop threaded through `RouteCard` → `RouteLegs`. Transit legs check `activeAlertRoutes?.has(pillLabel)` (pillLabel = stripped train name or bus line_code) and render a `⚠` `.leg-alert-badge` when matched.
  - **`frontend/src/App.jsx`**: Imports `ServiceAlertsBar`; adds `serviceAlerts`, `dismissedAlertIds` (initialized from `sessionStorage["dismissed_alert_ids"]`), and `activeAlertRoutes` (useMemo Set) state. `useEffect` on mount fetches `GET /alerts` and populates `serviceAlerts`. `handleAlertDismiss` writes back to `sessionStorage`. `ServiceAlertsBar` mounted between `PinnedStopsBoard` and the search form. `activeAlertRoutes` passed to each `RouteCard`.
  - **`frontend/src/App.css`**: `.service-alerts-bar`, `.service-alerts-toggle`, `.service-alerts-list`, `.service-alert`, `.service-alert--major/minor/planned`, `.service-alert-severity--major/minor/planned`, `.leg-alert-badge` styles added.
  - **22 locale files**: `alerts_active_count` and `alerts_dismiss` keys added to all locales.

**Files changed:** `backend/main.py`, `frontend/src/App.jsx`, `frontend/src/App.css`, `frontend/src/components/ServiceAlertsBar.jsx` (new), `frontend/src/components/RouteCard.jsx`, all 22 `frontend/public/locales/*/translation.json`.

**Post-launch enhancement (2026-04-30):** Alerts on the home page are now filtered to only those relevant to the user's currently selected route. Previously all non-dismissed alerts appeared regardless of whether they affected the displayed route. Fixed in `App.jsx`: added `currentRouteLines` (a `useMemo` Set of `line_code` identifiers extracted from the selected route's transit legs) and updated `visibleAlerts` to filter against it. When no route has been searched yet, all alerts continue to show. Alert route names and route leg line codes are both normalized by stripping any " Line" suffix before comparison.

---

# Feature Weather Scoring — Weather-Adjusted Route Ranking

**Completed: 2026-04-27**

**Overview:** Adds a weather-aware weight-adjustment layer to the Claude recommendation pipeline. When live weather data is available, a short "Weight guidance:" hint is appended to the weather section of the Claude prompt (prompt-only path — `_rank_routes()` ordering is unchanged). Claude uses the hint to verbally bias its recommendation toward lower-exposure options on cold/rainy/windy days.

**What was implemented (2 chunks):**

- **Chunk 1 (`backend/route_scoring.py` — new):**
  - `DEFAULT_WEIGHTS = {travel_time: 0.35, outdoor_exposure: 0.25, crowdedness: 0.20, reliability: 0.15, transfers: 0.05}` — baseline weight dict per scoping decision 2.
  - `adjust_weights_for_weather(base_weights, weather) -> dict`: applies threshold-based deltas (coldest-first for temperature: `< 0°F` → outdoor_exposure +0.20, travel_time −0.10; `< 15°F` → +0.10/−0.05), heavy precipitation (type != NONE and intensity == "heavy" → outdoor_exposure +0.15, travel_time −0.10), and high gusts (> 35 mph → reliability +0.05). Clamps negatives to 0, then normalizes to sum 1.0. Returns `dict(base_weights)` unchanged when `weather is None`.
  - `weight_hint_for_weather(weather) -> str`: derives a human-readable one-line hint from the same threshold conditions ("Weight guidance: outdoor exposure heavily prioritized due to dangerous wind chill."). Returns `""` when no thresholds fire or weather is None. Temperature thresholds are coldest-first with mutual exclusion (mirrors `adjust_weights_for_weather`).

- **Chunk 2 (`backend/main.py`):**
  - `from route_scoring import weight_hint_for_weather` added to imports.
  - In `build_prompt()`, after `_format_weather_for_prompt(weather)` builds the weather section, calls `weight_hint_for_weather(weather)` and appends the result (when non-empty) as a new line in `weather_section`. The hint appears as a single line directly after the weather conditions line — one token-efficient addition.

**Scoping decisions taken:**
1. Prompt-only (not numeric re-rank) — `_rank_routes()` unchanged.
2. Default weights accepted as proposed.
3. Weather thresholds and deltas accepted as proposed.
4. Isolated module `backend/route_scoring.py`.

---

# Feature Departure Window — Optimal Departure Timing Hint

**Completed: 2026-04-27**

**Overview:** When precipitation is present or forecast to change within the next few hours, Claude now receives a departure-timing hint enabling advice like "if you can leave in about 2 hours the rain should clear." The hint is derived from `WeatherContext.hourly_forecast` (already fetched on every request) — zero additional API calls and no new files.

**What was implemented (2 chunks, both in `backend/main.py`):**

- **Chunk 1 — `_departure_window_hint(weather)`:** New helper placed immediately after `_format_weather_for_prompt`. Receives `WeatherContext | None`; returns `""` when `weather` is `None` or `len(hourly_forecast) < 2`. Scans `hourly_forecast[:3]` starting at index 1 (index 0 = too imminent to be actionable) for two signal types:
  - Improving: `current_type != NONE` and a future period has `type == NONE` → `"(forecast: clears in ~{i+1}h)"`
  - Worsening: `current_type == NONE` and a future period has `type != NONE` → `"(forecast: {type.value} starts in ~{i+1}h)"`
  - Returns `""` if no qualifying transition is found.

- **Chunk 2 — wire-up:** `_format_weather_for_prompt` gained optional `hint: str = ""` parameter; when non-empty it is appended inline to the existing conditions line. In `build_prompt()`, `_departure_window_hint(weather)` is called once (stored in `departure_hint`) and passed into `_format_weather_for_prompt(weather, departure_hint)`. When `departure_hint` is non-empty, one sentence — `"If conditions improve soon, mention the optimal departure window."` — is appended to the end-of-prompt instruction (only on relevant days, to avoid token waste on clear days).

**Example prompt output (rain clearing in 2h):**
```
Current weather: Rain, 52°F (feels like 47°F), precipitation: rain (moderate) (forecast: clears in ~2h)
```

**Scoping decisions taken:**
1. Minimum gap index ≥ 1 (index 0 imminent = not actionable).
2. Hint computed once in `build_prompt()`, passed as parameter to avoid double-calling `_departure_window_hint`.
3. Departure instruction added conditionally — only when hint is non-empty.
4. Both improving and worsening transitions detected; steady conditions emit no hint.

---

# Feature Crowdedness — CTA Vehicle Crowdedness Estimation

**Completed: 2026-04-27**

**Overview:** Added a heuristic crowdedness estimator that annotates each Claude route option with an `[est. crowdedness: X]` tag. The estimator considers time period (PEAK / REGULAR / OFF_PEAK), day type (WEEKDAY / WEEKEND / HOLIDAY), travel direction (inbound/outbound relative to the Loop), position along the route (bell-curve factor), and known high-traffic stops. When CTA's Bus Tracker `psgld` field returns non-empty data it takes priority with `confidence="high"`; otherwise the heuristic produces `confidence="medium"` at peak and `"low"` otherwise. Claude weaves crowding context naturally into its recommendations.

**What was implemented (3 chunks):**

- **Chunk 1+2 (`backend/crowdedness.py` — new):**
  - `TimePeriod` enum (`PEAK/REGULAR/OFF_PEAK`), `DayType` enum (`WEEKDAY/WEEKEND/HOLIDAY`), `CrowdednessLevel` enum (`LOW/MODERATE/HIGH/VERY_HIGH`), `CrowdednessEstimate` Pydantic model (`score: float`, `level`, `confidence`, `factors` dict).
  - `CHICAGO_TZ = ZoneInfo("America/Chicago")` defined locally to avoid coupling to `cta_client.py`.
  - Static `_HOLIDAYS` set covering 2025–2027 US federal + Illinois state holidays (hand-maintained; ~5 min/year update).
  - `_TIME_PERIOD_CONFIG`: weekday PEAK 06:30–09:30 + 15:30–18:30; REGULAR 09:30–15:30 + 18:30–21:00; OFF_PEAK fallback. Weekend/holiday REGULAR 09:00–21:00; OFF_PEAK fallback.
  - `classify_time_period(dt, holidays=None) -> (TimePeriod, DayType)` — normalises to Chicago local time, handles timezone-aware and naive datetimes.
  - `BASE_SCORES = {PEAK: 0.75, REGULAR: 0.45, OFF_PEAK: 0.20}`.
  - `_direction_multiplier(direction, time_period, current_hour)`: AM peak inbound → 1.2 (outbound 0.8); PM peak outbound → 1.2; non-peak → 1.0.
  - `_stop_position_factor(position, total)`: bell curve `0.6 + 0.4 * sin(pos/total * π)`.
  - `HIGH_TRAFFIC_TRAIN_STATIONS`: 10 curated mapids verified against `stops.txt` — Clark/Lake (40380, ×1.35), Washington/Wells (40730, ×1.30), Harold Washington Library (40850, ×1.25), Belmont (41320, ×1.25), Howard (40900, ×1.20), Fullerton (41220, ×1.20), Chicago Red (41450, ×1.20), O'Hare (40890, ×1.15), Midway (40930, ×1.15), 95th/Dan Ryan (40450, ×1.15).
  - `HIGH_TRAFFIC_BUS_STOPS = {}` — empty at launch per scoping decision.
  - `rtdir_to_inbound_outbound(route_short_name, rtdir)`: heuristic (Southbound/Eastbound → inbound) + `_DIRECTION_OVERRIDES` dict for exceptions.
  - `estimate_crowdedness(...)`: live `psgld` path (EMPTY→LOW, HALF_EMPTY→MODERATE, FULL→HIGH, confidence "high") and heuristic path (`base * dir_mult * pos_factor * ht_mult`, clamped [0,1]).
  - `CROWDEDNESS_LEVEL_ORDER` dict for enum comparison without relying on Enum ordering.

- **Chunk 3 (`backend/main.py`):**
  - Imports `classify_time_period`, `estimate_crowdedness`, `rtdir_to_inbound_outbound`, `CrowdednessLevel`, `CROWDEDNESS_LEVEL_ORDER`, and `CHICAGO_TZ` (as `_CROWD_TZ`) from `crowdedness`.
  - `_CROWDEDNESS_LABELS` dict mapping levels to prompt-friendly strings (light / moderate / busy / very crowded).
  - `_crowdedness_for_routes(ranked) -> dict[int, str]`: computes current Chicago time, calls `classify_time_period`, iterates all `TransitLeg`s per route, calls `estimate_crowdedness()` with `stop_sequence_position=1, total_stops=2` (midpoint approximation), takes the worst level across legs, returns per-route-index label dict.
  - `_format_routes()` updated: calls `_crowdedness_for_routes(ranked)` once, appends `[est. crowdedness: {label}]` to each route option line when transit legs are present.
  - Bus legs use `rtdir_to_inbound_outbound(leg.line_code, leg.line)` for direction; train legs default to `"inbound"` (conservative).
  - Automatic live-override: `estimate_crowdedness` already prefers non-empty `psgld` — no further change needed when CTA restores real data.

**Scoping decisions taken:**
1. Static holiday list (no `holidays` library dependency).
2. Heuristic + override dict for direction mapping.
3. Curated train-only high-traffic list; bus stops empty.
4. Base scores and direction multipliers accepted as proposed.
5. Prompt-only surfacing (no UI crowdedness badge in v1).

---

# Feature Weather — Live Weather Integration

**Completed: 2026-04-27**

**Overview:** Integrated the NWS (weather.gov) API to inject live weather context into Claude's `/recommend` pipeline. `WeatherContext` (current conditions, near-term hourly forecast, and active NWS alerts) is fetched per request for the origin coordinates and appended as a single concise line in `build_prompt()`. Claude naturally weaves weather into its recommendation — e.g. flagging freezing rain, dangerous wind chills, or heavy snow when advising on outdoor vs. covered routing options.

**What was implemented (3 chunks, all in `backend/weather_service.py` + `backend/main.py` + `backend/requirements.txt`):**

- **Chunk 1 (Data models):** `backend/weather_service.py` — `PrecipitationType` enum (`NONE/RAIN/SNOW/SLEET/FREEZING_RAIN`), `PrecipitationInfo`, `WindInfo`, `CurrentWeather`, `ForecastPoint`, and `WeatherContext` (current + `hourly_forecast[:6]` + `alerts[:3]` + `fetched_at`). All Pydantic `BaseModel` subclasses.

- **Chunk 2 (WeatherService + cache):** `WeatherService` class with `async get_weather_context(lat, lon) → WeatherContext`. NWS two-step flow: `GET /points/{lat},{lon}` returns grid-point metadata (cached 24 h via `cachetools.TTLCache`); `GET forecastHourly` + `GET /alerts/active?point=…` fetched concurrently via `asyncio.gather` (cached 12 min). Cache key is rounded lat/lon to 2 decimal places. `_parse_wind()` handles `"10 mph"` and `"5 to 10 mph"` forms. `_feels_like()` applies NWS wind-chill formula (≤50°F + wind ≥3 mph) and Steadman heat-index approximation (≥80°F, 45% RH default). `_parse_precip()` infers type + intensity from NWS short-forecast text. `User-Agent: CTA-Transit-PWA/1.0 (adambhonaker@gmail.com)` per NWS requirements. `cachetools>=5.3` added to `requirements.txt`.

- **Chunk 3 (Integration):** `backend/main.py` — `weather_service = WeatherService()` module-level singleton. `_safe_weather(origin_coords)` async helper wraps `get_weather_context` in try/except (non-fatal; returns `None` on failure). `_format_weather_for_prompt(weather)` formats one-line summary: `Current weather: {condition}, {temp:.0f}°F (feels like {feels:.0f}°F), precipitation: {type}[ ({intensity})][, wind gusts {gusts:.0f} mph]` plus optional `Weather alerts: …` line. Weather fetched concurrently with CTA alerts via `asyncio.gather(get_alerts(…), get_route_statuses(), _safe_weather(origin_coords))` — zero added latency. `build_prompt()` gained `weather: WeatherContext | None = None` param; injects weather section and updates end-of-prompt instruction to `"Keep it to 3-4 sentences; incorporate weather context naturally within those sentences, not as a separate paragraph."` Walk mode path also fetches weather via `asyncio.gather` alongside the three walk-engine calls. `import traceback` added to `main.py`.

---

# Feature A — Train Station Exit Guidance

**Completed: 2026-04-13**

**Overview:** Improved the final walk leg by identifying available exits at the alighting station, recommending the exit that minimises the remaining walk to the destination, and optionally letting the rider choose a different exit.

**What was implemented (5 chunks):**
- **Chunk 1 (Data):** One-time `fetch_station_exits.py` script queries Overpass API for all `railway=subway_entrance` nodes in Chicago, matches them to CTA parent stations by haversine distance, and writes `backend/station_exits.json` (`{mapid: [{label, lat, lon}, ...]}` format). File committed to repo and manually reviewed for the 10–15 most-used stations.
- **Chunk 2 (Backend — load):** `_load_station_exits()` in `transit_graph.py` reads `station_exits.json` at import time into module-level `_station_exits` dict. Public helper `get_station_exits(mapid)` returns exit list or `[]` if none known.
- **Chunk 3 (Backend — selection):** `best_exit(mapid, dest_lat, dest_lon)` scores each exit via `street_walk_minutes`, returns the exit dict with minimum walk time plus `"walk_minutes"` key, or `None` if no exits known (caller falls back to station centroid).
- **Chunk 4 (Backend — integration):** `_path_to_route()` uses exit coords as walk origin for the destination walk leg. `exit_label: str = ""` field added to `WalkLeg`. `"exit_label"` added to walk leg serialization in `/recommend` response.
- **Chunk 5 (Frontend):** `WalkLegItem` shows exit label between summary line and Steps toggle when `leg.exit_label` is present and `leg.to === "Your destination"`. Styled as small muted secondary line.

---

# Feature C — Multi-Leg Bus Routing (Bus + Bus Transfers)

**Completed: 2026-04-13**

**Overview:** Added `find_bus_transfer_routes()` for trips requiring a bus transfer (bus A → walk → bus B). Standalone function, not via the NetworkX graph. One transfer preferred, max two transfers; 0.25-mile max transfer walk; 7.5-min fixed estimate for leg-2 wait; activation gate only when `find_bus_routes()` returns no useful results.

**What was implemented (5 chunks):**
- **Chunk 1 (Startup — spatial grid):** `_bus_stop_grid` and `_bus_stop_coords` module-level dicts populated at import time. `_stops_near(lat, lon, radius_miles)` helper using 0.005° grid cells, ~9-cell bounding box, haversine post-filter.
- **Chunk 2 (Startup — stop-to-routes index):** `_stop_to_routes: dict[str, list[tuple]]` built by `_build_stop_to_routes()`, called from `warm_up()` after `get_bus_stop_sequences()`. Enables O(1) "which routes serve stop X?" lookup.
- **Chunk 3 (Algorithm):** `find_bus_transfer_routes()` — Pass 1 collects candidate transfer stops via haversine only (forward-progress filter, max 3 per live arrival). Pass 2 builds 5-leg `Route` objects via OSMnx for surviving candidates. Sort by `total + wait_A + 7.5`, return top `n_routes`.
- **Chunk 4 (Integration):** `find_bus_transfer_routes` imported in `main.py`. Called as fallback when `find_bus_routes()` returns empty results. No format changes to the response.
- **Chunk 5 (Frontend — verification):** 5-leg route cards, zero-minute transfer walk legs, and map dual-color bus segments all confirmed working.

---

# Feature D — Live Arrivals at Transfer Stop

**Completed: 2026-04-18**

**Overview:** Fetches live arrival data for the connecting service at each transfer stop and displays it inline on the route card. Replaces the fixed 7.5-minute estimate used by Feature C with real-time data. Also threads transfer arrival data into the Claude prompt so Claude can give accurate wait-time advice for transfer trips (e.g., "the Brown Line at Belmont is 4 min away — good connection").

**What was implemented (4 chunks):**
- **Chunk 1 (`backend/main.py`):** `async def _empty()` no-op coroutine used as a placeholder in `asyncio.gather` when transfer fetch is not needed. `_extract_transfer_stops(ranked_routes)` scans all routes for transfer `TransitLeg`s (legs where an earlier leg in the same route is also a `TransitLeg`), deduplicates across routes, and returns two collections: train station dicts `[{mapid, name}]` and bus `stop_id` strings. Called after routing finalization; results fed to `asyncio.gather(get_train_arrivals(...), get_bus_arrivals(...))` concurrently — one extra round-trip, ~300ms added latency.
- **Chunk 2 (`backend/transit_graph.py`, `backend/main.py`):** Added `transfer_wait_minutes: int | None = None` to `TransitLeg` dataclass. Added `_build_bus_transfer_lookup(bus_arrivals)` returning `{(route, stop_id): earliest_minutes}`. Extracted `_pick_wait(dest_map, from_mapid, to_mapid) -> int | None` helper containing the dot-product bearing test previously inlined in `_rank_routes()` — both call sites now use the shared helper. Transfer legs annotated in-place: train transfers via `_build_arrival_lookup` + `_pick_wait`; bus transfers via `_build_bus_transfer_lookup`. `"transfer_wait_minutes"` added to transit leg serialization in `/recommend` response.
- **Chunk 3 (`backend/main.py`):** `_format_transfer_arrivals(arrivals)` groups combined train+bus arrivals by stop name, shows up to 3 arrivals per stop in `"{line_code/route} → {destination}: {N} min"` format. `build_prompt()` gained `transfer_arrivals: list[dict] | None = None` parameter; when non-empty, inserts a "Live arrivals at transfer stop(s):" section after the route options block. Combined list passed as `transfer_train_arrivals + transfer_bus_arrivals`.
- **Chunk 4 (`frontend/src/App.jsx`, `frontend/src/App.css`):** `RouteLegs` detects transfer boarding legs via `legs.slice(0, i).some(l => l.type === 'transit')`. When `isTransferLeg && transfer_wait_minutes` is set, renders a `<span className="transfer-wait-note">⏱ Due</span>` or `⏱ N min wait` inline above the transit leg pill. Added `.transfer-wait-note` CSS rule (`display: block; color: #888; font-size: 0.75rem`). Non-transfer legs and legs with no live data are unaffected.

---

# Feature B — Intermodal Routing (Train + Bus in One Trip)

**Completed: 2026-04-16**

**Overview:** Extended `_build_graph()` to include bus stop nodes, bus transit edges, and bidirectional train↔bus walk edges, so `find_routes()` naturally surfaces intermodal paths (e.g. walk → Red Line → transfer to bus 36 → destination) via Dijkstra on the unified graph.

**What was implemented:**
- `_build_graph()` — added `node_type="train"` to existing train station nodes; `mode="train"` to all train transit edges; `line_code` attribute added to train transit edges.
- `_build_graph()` — bus stop nodes added (node_type="bus", lat, lon, name from stops.txt).
- `_build_graph()` — bus transit edges added for all route/direction pairs from cached bus stop sequences (mode="bus", line_code=route_short_name, edge_type="transit").
- `_build_graph()` — bidirectional train↔bus walk edges for every train station / bus stop pair within 0.15 miles and ≤5 min street walk (edge_type="walk", mode="walk").
- `_resolve_node()` helper added — resolves node name, lat, lon from either the stations dict (train) or graph node attributes (bus).
- `_path_to_route()` — all node metadata lookups updated to use `_resolve_node()`; new `edge_type == "walk"` handler added for mid-path train↔bus transfers; bus TransitLeg assembly uses `edge.get("line_code")`.
- `find_routes()` — virtual ORIGIN→bus_stop and bus_stop→DEST walk edges added so Dijkstra surfaces intermodal paths.
- `warm_up()` — logs graph size (nodes + edges) after `_build_graph()`.
- `main.py` — `find_routes()` called with `n_routes=5`; `_route_fingerprint()` deduplication added after merge-sort to prevent unified-graph bus-only routes from duplicating `find_bus_routes()` results.
- Module docstring updated to describe bus stop nodes and walk edges.
- `find_nearest_bus_stops` imported in transit_graph.py.

**Known gap (documented in plans):** Bus access/egress first/last-mile gap resolved by this feature. Shared-track edge deduplication (route label accuracy) is a separate gap documented in `FEATURE_IMPLEMENTATION_PLANS.md`.

---

# Feature H — Deduplicate Same-Line Station Candidates

**Completed: 2026-04-17**

**Overview:** When the user is near a stretch of a single-line corridor (e.g., Lawrence / Argyle / Berwyn are all Red Line only), `find_nearest_train_stations()` returned all three as candidate origin nodes, producing near-duplicate routes. Added `_dedup_stations_by_line()` to keep at most one station per unique set of transit lines served.

**What was implemented (3 chunks, all in `backend/transit_graph.py`):**
- **H-1:** `_dedup_stations_by_line(G, stations)` module-level helper. For each station sorted by walk_minutes, inspects `G.edges(mapid, data=True)` to collect the `"line"` attribute on all `edge_type="transit"` edges. Keeps the station if `station_lines - covered_lines` is non-empty; otherwise drops it. Stations with no edges always kept.
- **H-2:** In `find_routes()`, after both `origin_stations` and `dest_stations` are populated, applies `_dedup_stations_by_line(G_base, ...)` to each list before adding ORIGIN/DEST virtual-node edges.
- **H-3:** Manual verification — origin `1131 W Winona St` yields one Red Line candidate instead of three; origin near Belmont still yields both Red Line and Brown Line candidates.

---

# Feature I — CTA Alerts Integration + Route Status

**Completed: 2026-04-17 | Updated: 2026-04-24**

**Overview:** After routes are calculated, active service alerts are fetched from the CTA Alerts API for every transit line/route involved in the ranked results. System-wide route statuses are also fetched in parallel from the CTA Route Status API. Both are included in Claude's prompt and disruptions are surfaced in the UI.

**What was implemented (3 chunks, updated 2026-04-24):**
- **I-1 (`cta_client.py`):** `ALERTS_BASE` constant (`https://lapi.transitchicago.com/api/1.0/alerts.aspx` — updated 2026-04-24 from dead `www.transitchicago.com/api/1.0/detailed_alerts.aspx` endpoint), `_TRAIN_LINE_TO_ALERT_ID` dict (maps internal line_code → Alerts API route id), `_fetch_alerts_for_route(session, route_id)` (async fetch, timeout 5s, returns `[]` on error), `get_alerts(route_ids)` (concurrent gather, dedup by `alert_id`, sorted by `severity_score` descending). Also added: `ROUTES_BASE` constant (`https://lapi.transitchicago.com/api/1.0/routes.aspx`), `get_route_statuses()` (single async call returning all lines; each dict has `service_id`, `route`, `status`, `status_color`).
- **I-2 (`main.py`):** `get_alerts`, `get_route_statuses`, and `_TRAIN_LINE_TO_ALERT_ID` imported from `cta_client`. `_alert_ids_from_routes(ranked_routes)` helper extracts deduplicated Alerts API ids from all `TransitLeg`s. `get_alerts` and `get_route_statuses` fetched concurrently via `asyncio.gather` after `ranked_routes` finalized. `build_prompt()` gained `alerts` and `route_statuses` params — alerts with `severity_score >= 5` appended as "Active service alerts on your route" block; routes where `status != "Normal Service"` appended as "Current system-wide route disruptions" block. `alerts` key added to response payload with 7 fields per alert.
- **I-3 (`App.jsx` / `App.css`):** `alerts` stored in result state. Rendered between recommendation text and route cards when non-empty. Major alerts (`is_major: true`) get red left border + bold red headline; minor alerts get yellow border. Capped at 3 with "and N more" link. Alert styles in `App.css` (`.alerts-section`, `.alert-item`, `.alert-item--major`, `.alert-item--minor`, `.alert-headline`, `.alert-impact`, `.alerts-more`).

---

# Feature E — Walk Leg Street-Level Distance Detail

**Completed: 2026-04-13**

**Overview:** Added block-count distance to each walk step so riders can understand and verify the walk without mentally converting minutes into distance. Target format: "Walk South along Broadway for 2 blocks / Head East along Wilson for 3 blocks".

**What was implemented (2 chunks):**
- **Chunk 1 (`backend/walking.py`):** Added `_CHICAGO_BLOCK_METERS = 80.0` constant, `_DIRECTION_FULL` dict (8 cardinal/intercardinal directions). Each step dict gains `"blocks": float` (rounded to nearest 0.5, min 0.5) and `"direction_full": str`. Fallback step also gets both fields. `@lru_cache` key unchanged.
- **Chunk 2 (`frontend/src/App.jsx`, `App.css`):** `formatBlocks(b)` helper. `WalkLegItem` step rendering replaced with prose format ("Walk"/"Head" + direction_full + "along" + street + blocks). Removed `.leg-step-arrow`, `.leg-step-dir`, `.leg-step-time` spans and CSS rules. Per-step minutes removed from display.

---

# Feature F — Street Abbreviation Normalization

**Completed: 2026-04-13**

**Overview:** Added a normalization pass in `resolve_location()` that expands USPS-standard street suffix abbreviations (e.g. "Ave" → "avenue", "Blvd." → "boulevard") before any matching. Reduces unnecessary Google API calls, improves `NEIGHBORHOOD_COORDS` hit rate, and produces stable geocode-cache keys.

**What was implemented (1 chunk, `backend/gtfs_loader.py`):**
- `_ABBR_MAP` dict and module-level compiled `_STREET_ABBR_RE` regex (sorted longest-first, word-boundary anchored, case-insensitive, handles period-terminated variants).
- `_normalize_street_abbr(query: str) -> str` private helper. Applied immediately after `q = query.lower().strip()` in `resolve_location()`. Google API call updated to pass normalized `q` for stable cache keys.
- Directional prefixes (N/S/E/W) intentionally excluded.

---

# Feature G — Long/Short Block Classification

**Completed: 2026-04-13**

**Overview:** Replaced the single `_CHICAGO_BLOCK_METERS = 80.0` approximation with accurate per-type constants: `_LONG_BLOCK_METERS = 201.17` (N-S axis, 1/8 mile) and `_SHORT_BLOCK_METERS = 100.58` (E-W cross streets, 1/16 mile). Each walk step is classified as long or short based on average OSM edge length; block count uses the correct constant.

**What was implemented (2 chunks):**
- **G-1 (`backend/walking.py`):** Replaced `_CHICAGO_BLOCK_METERS` with three constants. Added `edge_count` accumulator in inner loop. Classification: `avg_edge_m = total_length / edge_count`; threshold 150 m; selects correct `block_m` and sets `block_type = "long" | "short"`. Added `"block_type"` to step dict. Fallback path applies same threshold to `fallback_meters`.
- **G-2 (`frontend/src/App.jsx`):** Updated `formatBlocks(b, blockType)` to produce qualified label ("long block(s)" or "short block(s)"). Call site updated to pass `step.block_type`. Output: "Walk North along Clark for 2 long blocks" / "Head East along Chicago for 3 short blocks". Backward compatible when `blockType` absent.

---

# Rate Limiting on `/recommend` Endpoint

**Completed: 2026-04-14**

**Overview:** Zero-dependency in-memory sliding window rate limiter. Feature is OFF by default. Enable by setting `RATE_LIMIT_ENABLED=true` in Railway env vars.

**What was implemented (`backend/main.py` only):**
- `_RATE_LIMIT_ENABLED`, `_RATE_LIMIT_RPM` (default 10), `_RATE_LIMIT_RPH` (default 50) — env-var-driven config.
- `_rate_store: dict[str, collections.deque]` — in-memory per-IP timestamp store.
- `_client_ip(http_request)` — extracts real IP from `X-Forwarded-For` or falls back to `request.client.host`.
- `_check_rate_limit(ip)` — sliding-window check; returns True (allowed) or False (rate-limited); called before any I/O at top of `/recommend`.
- `/recommend` signature: `async def recommend(request: RouteRequest, http_request: Request)`.

**Known gap:** `_rate_store` and `_response_cache` are mutated without a lock — race condition under concurrent requests. Documented in `BUGS_TO_BE_FIXED.md`.

**Future:** Replace `_rate_store` with Redis-backed counter if Railway scales to multi-instance. Interface unchanged.

---

# Bring Your Own API Key (BYOK)

**Completed: 2026-04-14**

**Overview:** Lets technically savvy users supply their own Anthropic API key. Feature is OFF by default. Enable by setting `BYOK_ENABLED=true` in Railway AND `VITE_BYOK_ENABLED=true` in Vercel, then redeploy both services.

**What was implemented (`backend/main.py`, `frontend/src/App.jsx`, `frontend/src/App.css`):**

Backend:
- `anthropic_api_key: str | None = None` on `RouteRequest` with `@field_validator` (strips whitespace, rejects non-`sk-ant-` values with 400).
- `_BYOK_ENABLED` env flag. When false, field accepted but silently ignored.
- Per-request `anthropic.AsyncAnthropic(api_key=byok_key)` when BYOK key set; otherwise falls back to `_claude_client` singleton.

Frontend:
- `BYOK_ENABLED = import.meta.env.VITE_BYOK_ENABLED === "true"` compile-time flag.
- `SettingsPanel` component with gear icon ⚙ in header filters row. Modal-style panel with `type="password"` input, Save and Remove key buttons, inline format validation. Key stored in `sessionStorage` (clears on tab close).
- Fetch body spreads `{ anthropic_api_key: byokKey }` only when `BYOK_ENABLED && byokKey`.

---

# Claude Response Caching

**Completed: (date not recorded)**

**Overview:** Caches the full `/recommend` response for identical origin/destination/mode/bus_fullness queries within a 45-second TTL. Repeat requests for popular routes skip all upstream I/O.

**What was implemented (`backend/main.py`):**
- `_response_cache: dict[str, tuple[float, dict]]` — key → (expires_at, response dict).
- `_cache_key(origin, destination, transit_mode, bus_fullness)` — lowercased, joined with `"|"`.
- Cache check before any I/O at top of `/recommend`; lazy TTL eviction inline; 500-entry size cap (evicts entry nearest to expiry when full).
- `cache_hit: true` field added to cached responses (frontend wires the field but does not surface it to users).
- TTL: 45 seconds (short enough that live arrivals aren't materially stale; long enough to collapse burst traffic).

---

# Multi-Leg Train Routing — Gap 2 (Bus First/Last Mile)

**Completed: 2026-04-16 (resolved by Feature B)**

**Overview:** The origin and destination walk legs previously always used pedestrian walking. Taking a bus to a better-positioned train station was never considered.

**Resolution:** Feature B (Intermodal Routing) resolved this gap as a natural consequence of adding `ORIGIN→bus_stop` virtual walk edges in `find_routes()`. No separate implementation required.

---

# Feature J — Deprecate `find_bus_routes()` in Favor of Unified Graph

**Completed: 2026-04-18**

**Overview:** Removed the legacy standalone `find_bus_routes()` function. Direct bus-only routes now come exclusively from the unified NetworkX graph via `find_routes()` (added in Feature B); `find_bus_transfer_routes()` continues to handle bus+bus transfer itineraries the graph does not model. Eliminates two parallel bus-routing codepaths that had to be kept in sync as the graph evolved.

**What was implemented (3 chunks):**

- **Chunk 1 (Verification):** Confirmed that `find_routes()` over the unified graph surfaces direct-bus options of comparable quality to the deleted function for canonical test trips (Wicker Park↔Logan Square, Lincoln Square↔Lakeview, Pilsen↔Bridgeport). Route totals within tolerance; no nonsensical bus paths.
- **Chunk 2 (`main.py` restructure):** Removed the `find_bus_routes(...)` call and its activation-gate for `find_bus_transfer_routes()`. Bus routing block now calls `find_bus_transfer_routes()` unconditionally (subject to the existing `bus_arrivals and origin_bus_stops` guard) for both `"Bus"` and `"All"` modes with `n_routes=2`. Removed the `_route_fingerprint()` deduplication block — the unified graph and `find_bus_transfer_routes()` produce non-overlapping route types (direct vs. transfer) by design. Updated `_rank_bus_routes()` docstring to reference `find_bus_transfer_routes()` as its sole caller. Also dropped the legacy `if transit_mode != "Bus"` gate on `find_routes()` so the unified-graph call runs in every mode — it is now the sole source of direct bus-only itineraries. In Bus mode, results are post-filtered to drop any route that traverses a train `TransitLeg` (`line_code in LINE_NAMES`). Imports `LINE_NAMES` from `cta_client`.
- **Chunk 3 (cleanup):** Deleted `find_bus_routes()` from `transit_graph.py` (~205 lines). Removed the `find_bus_routes` symbol from the `main.py` import list. Updated the `_build_shape_lookup()` comment to cite `find_bus_transfer_routes()` as the remaining `get_shape(route_short_name, direction_id)` caller. Updated `find_bus_transfer_routes()` docstring (no longer gated by the legacy function) and the `_MAX_EXIT_DIST` comment. Updated the `stop_id` comment in `cta_client.py`. `grep -r "find_bus_routes" backend/` confirms zero remaining references.

**Net effect:** One less per-request bus-routing codepath, one fewer CTA Bus Tracker API-derived computation path to keep in sync, and a simpler merge in `main.py` (no fingerprint dedup step). Response schema and frontend are unchanged.

---

# Multi-Leg Train Routing — Shared-Track Edge Deduplication

**Completed: 2026-04-20**

**Overview:** Fixed a route-label accuracy bug on CTA segments where multiple train lines share the same physical track and station pair (e.g. Red/Purple between Howard and Belmont). Previously `_build_graph()` kept only the single fastest `route_id` per `(from_station, to_station)` edge, so a rider transferring to the Purple Line at Howard would still see the transit leg labelled "Red Line" through the shared section. Timing was always correct — only the displayed line name was wrong.

**What was implemented (1 chunk, `backend/transit_graph.py`):**

- **`_build_graph()`:** For every `(from_mapid, to_mapid)` edge that has more than one route candidate (i.e., shared-track segments), stores `all_routes: dict[route_id, (dir_id, line_name)]` as an edge attribute. Single-route edges get `all_routes=None` (no overhead). Edge weight, `route_id`, and all other attributes continue to reflect the fastest candidate.
- **`_last_transit_leg()` helper:** New module-level function that searches backward through the assembled `legs` list (past any intervening walk legs) to find the most recent `TransitLeg`. Used to detect the incoming line at the start of each new transit segment.
- **`_path_to_route()` — shared-track label correction block:** After reading the raw `route_id` and `line` from the first edge of a new transit group, checks: (a) there is an incoming `TransitLeg`, (b) the edge has `all_routes` metadata, (c) the incoming line_code differs from the edge's stored `route_id`, and (d) the incoming line_code is present in `all_routes`. If all four conditions hold, overrides `group_route`, `group_dir`, and `group_line` with the incoming line's values — so the leg is labelled with the line the rider is actually on.
- **`_path_to_route()` — merge-loop fix:** The while-loop that groups consecutive same-route edges previously broke on `next_edge.get("route_id") != group_route`. Updated to also accept edges where `group_route in next_edge.get("all_routes", {})`, so the Purple Line leg continues merging through Howard→Wilson→Montrose→… even though those edges store `route_id="Red"`.
- **`line_code` assignment fix:** Changed `line_code = edge.get("line_code") or group_route` to `line_code = group_route` so the `TransitLeg.line_code` field reflects the overridden value (not the raw edge attribute). This ensures shape lookup calls `get_shape(group_route, group_dir)` with the correct line.

**Correctness properties:**
- No override fires when there is no incoming transit leg (first leg of the trip): stored label used as-is.
- No override fires when the incoming line equals the stored `route_id`: already correct.
- No override fires when `all_routes` is None (non-shared-track edge): behavior unchanged.
- Override only fires when the incoming line actually appears in `all_routes` — prevents spurious relabelling on lines that genuinely diverge.
- Bus edges never have `all_routes` set (only train candidates are stored per edge), so bus leg labelling is unaffected.

---

# Claude Haiku for Simple Queries

**Completed: 2026-04-18**

**Overview:** Routes with exactly one option and a single direct `TransitLeg` (no transfers) are now handled by `claude-haiku-4-5-20251001` instead of `claude-sonnet-4-6`. Haiku is ~65% cheaper and fully capable of formatting a single-option recommendation; Sonnet is reserved for multi-option or multi-leg responses that need comparison reasoning.

**What was implemented:**

- Added `_is_simple_query(ranked_routes)` helper in `backend/main.py`. Returns `True` iff `len(ranked_routes) == 1` **and** that route contains exactly one `TransitLeg` (walk legs do not count). Conservative by design — any query with multiple routes, a transfer, or multiple same-line options falls through to Sonnet.
- Model selection branch in `/recommend` immediately before the `claude_client.messages.create(...)` call. Haiku uses `max_tokens=300`; Sonnet keeps `max_tokens=400`. The prompt is identical for both models — no prompt divergence to maintain.
- Stdout log line `[claude model=haiku|sonnet simple=True|False]` printed on every request for cost analysis.
- `"model_used": "haiku" | "sonnet"` added to the `/recommend` response dict. Frontend ignores it; exists for observability and future surfacing. The response cache stores it unchanged, so cache hits still return the correct `model_used` value from the original call.
- BYOK path uses the same classifier — whether the request uses a shared-quota key or a user-supplied key, the same `simple` determination picks the model.

**Out of scope (explicitly not done):** Haiku-specific prompt tuning; expanding "simple" to cover two same-line options; per-model cost tracking in the response; automatic Haiku→Sonnet fallback on low-confidence output (the classifier is conservative enough that this is not needed).

---

# Feature AI Toggle — Optional Claude Recommendation Layer

**Completed: 2026-04-20**

**Overview:** The Claude recommendation layer is now opt-in. The UI adds an "AI Explanation" toggle in the settings panel (off by default, persisted to `localStorage`). When off, the backend skips the Claude call entirely — no latency, no token spend, and `recommendation: null` is returned. When on, behavior is identical to before. The feature is designed so a paywall can be added later with a single auth check at the `if request.ai_enabled:` branch in `main.py`.

**What was implemented (2 chunks):**

- **Chunk 1 — Backend (`backend/main.py`):**
  - Added `ai_enabled: bool = False` field to `RouteRequest`. Defaults to `False` — old clients that omit the field get the safe default (no Claude call, no breakage).
  - Updated `_validate_api_keys()` to only require `ANTHROPIC_API_KEY` when `request.ai_enabled` is `True`. Non-AI requests no longer fail if the key is absent.
  - Updated `_cache_key()` to include `ai_enabled` in the key string so AI-on and AI-off responses are cached separately.
  - Wrapped the `_call_claude(...)` call in `if request.ai_enabled:`. When the flag is `False`, `recommendation` and `model_used` are both `None`. The response always includes `"recommendation": recommendation` (value is the string when AI ran, `None` otherwise).

- **Chunk 2 — Frontend (`frontend/src/App.jsx`, `frontend/src/App.css`):**
  - Added `aiEnabled` state, initialized from `localStorage.getItem("cta_ai_enabled") === "true"` (defaults to `false`).
  - Added `handleAiChange(value)` helper that updates both state and `localStorage`.
  - Added `ai_enabled: aiEnabled` to the `handleSubmit` fetch request body.
  - Updated `setResult` to store `null` (not `""`) when `data.recommendation` is `null`.
  - Added an "AI Explanation" labeled checkbox (`<label className="setting-row">`) to `SettingsPanel`, with a one-line hint below it. `SettingsPanel` now accepts `aiEnabled` and `onAiChange` props. The BYOK key section is conditionally rendered inside the panel when `BYOK_ENABLED` is true.
  - Removed the `BYOK_ENABLED` gate on the settings gear icon — the button now always shows so the AI toggle is always reachable.
  - Removed the `BYOK_ENABLED` gate on the `{settingsOpen && <SettingsPanel ...>}` render.
  - Gated `<div className="recommendation">` on `result.recommendation != null`. Moved `busDataPartial` warning outside the recommendation div so it still renders when AI is off.
  - Added `.setting-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; }` to `App.css`.

**Future paywall gate:** Add an auth check inside the `if request.ai_enabled:` block in `main.py`. No other code needs to change.

---

## Feature Trip — Live Trip-in-Progress Routing

**Completed: 2026-04-23**

**Overview:** After a rider selects a route card, a "Start Trip" button activates GPS tracking via `navigator.geolocation.watchPosition`. The app follows the user through each route leg, highlights the active leg and dims completed ones, marks individual walk steps complete as the user passes them, detects significant deviation from the planned route, and offers a one-tap re-route from the current GPS position. A "Stop Trip" button is always visible while tracking is active. Starting a new search automatically ends any in-progress trip.

**What was implemented (3 chunks):**

- **Chunk 1 — GPS tracking, trip activation UI, and map position dot:**
  - `App.jsx`: `tripActive`, `userPosition`, `watchIdRef` state/refs; `startTrip()` / `stopTrip()` helpers; "Start Trip" / "Stop Trip" buttons rendered in the selected route card footer; GPS watch options `{ enableHighAccuracy: true, maximumAge: 15000, timeout: 10000 }`; `stopTrip()` called at top of `handleSubmit` and when switching route cards; `userPosition` / `tripActive` passed to `MapView`.
  - `MapView.jsx`: `userPosition` and `tripActive` props accepted; when trip active, a blue circle (`#4A90E2`, radius 10, white stroke) is added as a GeoJSON source/layer `user-position-source`/`user-position-layer`; map `flyTo` centers on first GPS fix; subsequent position updates call `setData` rather than re-adding the layer; when trip stops, layer visibility set to `"none"` rather than removed (avoids MapLibre source-still-in-use errors); `userPosLayerRef` reset to `false` on map re-init.
  - `App.css`: `.route-card-trip-footer`, `.start-trip-btn` (blue, primary), `.stop-trip-btn` (muted/destructive).

- **Chunk 2 — Active leg tracking and walk step completion:**
  - `App.jsx`: `activeLegIndex` (default `null`, set to `0` on trip start) and `completedSteps` (`Set<string>`, keys `"legIdx-stepIdx"`) state; `haversineMeters(a, b)` inline 5-line Haversine; `legEndCoord(leg)` returns `{lat, lng}` from `leg.to_coords` (transit) or last `leg.path` point (walk); `useEffect([userPosition])` runs three functional `setActiveLegIndex` passes: (1) advance leg when within 60 m of its endpoint, (2) mark walk steps complete when within 30 m of `step.start_lat`/`start_lon`, (3) off-route detection; `activeLegIndex` / `completedSteps` passed via `RouteCard` → `RouteLegs` → `WalkLegItem`.
  - `RouteLegs`: accepts `activeLegIndex` and `completedSteps` props; applies `.leg-active` (blue left border) to active leg and `.leg-complete` (50% opacity + ✓ check icon) to completed legs.
  - `WalkLegItem`: accepts `completedSteps` and `extraClass`; renders ✓ + `.leg-step--complete` on steps whose key is in `completedSteps`.
  - `backend/walking.py`: Added `"start_lat": lat1, "start_lon": lon1` to every step dict in `_walk_directions_impl` (both street-routed path and Haversine fallback).

- **Chunk 3 — Off-route detection and re-route prompt:**
  - `App.jsx`: `isOffRoute` boolean state; `suppressRerouteUntil` ref (90 s suppression after dismiss); off-route fires only during walk legs when min distance to any leg endpoint exceeds 400 m; `handleReroute()` function submits GPS coords as origin without stopping the GPS watch (`setOrigin(gpsOrigin)`, fresh fetch, resets `activeLegIndex`/`completedSteps`); off-route banner rendered above route cards with "Re-route from here" and "Dismiss" buttons.
  - `backend/gtfs_loader.py`: `_COORD_RE` module-level regex + fast-path at top of `resolve_location()` so GPS coordinate strings (e.g. `"41.893450,-87.631200"`) bypass fuzzy matching and geocoding entirely, resolving directly to `find_nearest_train_stations` / `find_nearest_bus_stops`.
  - `App.css`: `.off-route-banner` (amber `#FFF3CD` background, `border-left: 4px solid #D97706`), `.off-route-message`, `.off-route-actions`, `.off-route-reroute-btn`, `.off-route-dismiss-btn`.

**Future iteration ideas (not implemented):**
- Live arrival countdown polling every 30 s during transit wait phase.
- Adaptive GPS polling rate (lower on walk legs, higher on transit legs).
- Shape-based off-route detection using the clipped GTFS shape polyline.
- Haptic / browser notification alerts for boarding nudges.

---

## Feature Language — Multi-Language Support (i18n)

**Completed: 2026-04-20**

**Overview:** Added full internationalization to the frontend UI and Claude's AI-generated recommendation text, supporting 22 languages including RTL scripts (Arabic, Urdu, Pashto). A language selector in the header persists to `localStorage` and automatically detects the browser language on first visit.

**What was implemented (6 chunks):**

- **Chunk 1 — i18n infrastructure (`frontend/src/i18n.js`, `frontend/src/main.jsx`, `frontend/public/locales/en/translation.json`):**
  - Installed `i18next`, `react-i18next`, `i18next-http-backend`, `i18next-browser-languagedetector`.
  - Created `frontend/src/i18n.js` with `SUPPORTED` list (22 language codes), `HttpBackend` for on-demand locale loading, `LanguageDetector` reading `localStorage["cta_language"]` then `navigator.language`, and `fallbackLng: "en"`.
  - Updated `frontend/src/main.jsx` to import `i18n.js` and wrap `<App />` in `<Suspense fallback={null}>`.
  - Created `frontend/public/locales/en/translation.json` with all 45 English strings.

- **Chunk 2 — String extraction (`frontend/src/App.jsx`):**
  - Added `useTranslation()` hook to all components: `WalkLegItem`, `RouteCard`, `SettingsPanel`, `LoadingSkeleton`, and main `App`.
  - `formatBlocks()` now accepts `t` as a third parameter, using `block_singular/plural`, `long_block_singular/plural`, `short_block_singular/plural` keys.
  - Replaced all 45+ hardcoded user-visible strings with `t("key")` or `t("key", { vars })` calls. Station names, line names, and CTA alert text are NOT translated (proper nouns).

- **Chunk 3 — Language selector (`frontend/src/App.jsx`):**
  - Added `LANGUAGE_NAMES` constant with native-script names (العربية, 中文, etc.) for all 22 languages.
  - Added `<select>` in `.filters` bar adjacent to transit mode selector, bound to `i18n.changeLanguage()`.
  - Added `useEffect` watching `i18n.language` to set `document.documentElement.dir` (rtl/ltr) and `document.documentElement.lang`. `RTL_LANGS = new Set(["ar", "ur", "ps"])`.

- **Chunk 4 — Translation files (`frontend/public/locales/{code}/translation.json`):**
  - Created machine-translated files for all 21 non-English languages: es, fr, it, pl, ro, uk, ru, zh, yue, ja, ko, tl, vi, hi, gu, pa, ne, ur, ar, ps, yo.
  - Japanese file includes parenthetical furigana on all kanji-heavy terms.
  - All non-English files include `"_comment": "machine-translated, review welcome"`.

- **Chunk 5 — Backend language pass-through (`backend/main.py`):**
  - Added `language: str | None = None` field to `RouteRequest`.
  - Added `LANGUAGE_NAMES` dict mapping all 22 codes to English names.
  - Extended `build_prompt()` with `language` parameter. Appends `"Respond in {language_name}."` for non-English languages; Japanese gets the extended furigana instruction.
  - Updated `_cache_key()` to include language so same-route queries in different languages cache separately.
  - Frontend `handleSubmit` now sends `language: i18n.language` in the request body.

- **Chunk 6 — RTL CSS (`frontend/src/App.css`):**
  - Added `[dir="rtl"]` overrides for `.header-top`, `.filters`, `.route-card-header`, `.route-card-summary`, `.leg`, `.leg-walk-body`, `.leg-steps` (border flips), `.alert-item` (border flips), `.settings-header`, `.settings-actions`, `.form label`.
  - No full CSS rewrite — only targeted overrides for confirmed RTL issues.

---

# Feature Favorites — Saved Locations & Routes

**Completed: 2026-04-23**

**Overview:** Added a localStorage-backed favorites system so repeat users can save named locations (e.g. "Home", "Work") that quick-fill either text field, and named routes (origin+destination pairs) that repopulate both fields with one tap. All state lives in the browser — no backend changes. Cap of 10 items per list.

**What was implemented (3 chunks):**

- **Chunk 1 — Data layer (`frontend/src/favorites.js`, new):** Pure utility module with no React dependency. `_load(key)` / `_save(key, arr)` private helpers backed by `localStorage`. Public exports: `getSavedLocations`, `saveLocation` (returns updated array or `null` on cap), `deleteLocation`, `getSavedRoutes`, `saveRoute` (same null-on-cap contract), `deleteRoute`. Cap is 10 items per list; IDs generated with `crypto.randomUUID()`.

- **Chunk 2 — Saved Locations UI (`frontend/src/App.jsx`, `frontend/src/App.css`):** New `LocationInput` component wraps each "From"/"To" field in a `.field-wrapper` (position: relative). A `☆` star button (absolute-positioned right) appears when the field has a non-empty value; turns amber `★` when the value is already saved. Clicking an unsaved field opens an inline label save panel (text input + Save/Cancel buttons; Enter saves, Escape cancels; blocks form submission). Clicking a saved field immediately removes it. Focusing a field with saved locations shows a `.saved-dropdown` (absolute, `z-index: 100`) listing up to 5 items with per-item `×` delete buttons; `onMouseDown` + `e.preventDefault()` ensures selection fires before `onBlur` closes the dropdown (150 ms debounce). Cap hit shows a 3-second inline error then auto-dismisses. RTL overrides flip star to left edge.

- **Chunk 3 — Saved Routes UI (`frontend/src/App.jsx`, `frontend/src/App.css`):** `⭐` toggle button added to the `.filters` bar; opens a `.saved-routes-panel` between the header and form listing all saved routes with "Go" (populates fields + closes panel) and `×` (deletes) buttons, plus an empty-state message. After a successful query, a "Save ☆" / "Saved ★" button appears in a `.routes-section-header` flex row alongside the "Route options" heading. Clicking to save opens an inline route-label save panel (same pattern as locations, 30-char max, pre-filled with `origin → destination`). Clicking to unsave immediately removes the matching entry. Route save UI resets on new query submission. 14 new i18n keys added to `frontend/public/locales/en/translation.json`; other locale files require manual translation review.

---

# Feature DAU — Daily Unique User Counting

**Completed: 2026-04-24**

**Overview:** Tracks how many unique users access the site per day as a single integer per day — the minimum viable growth signal. No personal data, behavioral data, or session information is persisted. Client IPs are HMAC-SHA256 hashed with a daily secret salt and kept only in an in-memory set for the current UTC day; when the day rolls over the set is discarded and only the final count is written to disk. Cross-day correlation is impossible because the daily salt changes.

**What was implemented (2 chunks):**

- **Chunk 1 — Backend counter (`backend/dau.py` new, `backend/main.py`):**
  - `backend/dau.py`: `DAU_FILE` path — `/app/data/dau.json` when `APP_ENV=production` (Railway persistent volume), `backend/data/dau.json` otherwise. `DAU_FILE.parent.mkdir(parents=True, exist_ok=True)` runs at module load. Module-level state: `_current_day: str`, `_seen_hashes: set[str]`, `_lock: asyncio.Lock`. `_load() -> dict[str, int]` — reads the JSON file, returns `{}` on missing or corrupt. `_save(counts)` — atomic write via `tempfile.mkstemp` + `os.replace`. `async def record_visit(ip)` — derives today's HMAC key from `DAILY_SALT + today_utc`, hashes the IP, checks if already in `_seen_hashes` (skip), flushes previous day's count on day rollover, adds hash to set, and saves the incremented count. `async def get_counts()` — returns `_load()`.
  - `backend/main.py`: Imported `dau` module. Added `Header` to FastAPI imports. Added `GET /ping` — calls `_client_ip()` (already honors `X-Forwarded-For` for Railway proxy), calls `await dau.record_visit(ip)`, returns `{"ok": True}`. Added `GET /admin/dau` — checks `Authorization: Bearer <DAU_ADMIN_TOKEN>` header (env var); returns `await dau.get_counts()`; returns 403 on mismatch or absent token. `DAILY_SALT` and `DAU_ADMIN_TOKEN` must be set in Railway env vars (values never committed).

- **Chunk 2 — Frontend ping (`frontend/src/App.jsx`):**
  - Added `useEffect(() => { fetch(\`${BACKEND_URL}/ping\`); }, [])` in the `App` component — fires once on mount, fire-and-forget (no await, no error handling, never blocks the UI).

**Railway setup required:**

- Add Railway persistent volume mounted at `/app/data`.
- Set env vars: `DAILY_SALT=<random-secret>`, `DAU_ADMIN_TOKEN=<random-secret>`, `APP_ENV=production`.

**Data access:** `GET /admin/dau` with `Authorization: Bearer <DAU_ADMIN_TOKEN>` returns the full `{"YYYY-MM-DD": count, ...}` JSON object.

---

# Feature MultiLine — Multi-Pattern Train Graph

**Completed: 2026-04-25**

**Overview:** Fixed two related bugs that caused certain CTA train lines — most critically the Purple Line — to never appear in routing recommendations.

**Root cause (Bug 1 — rush-hour-only express services missing from graph):** The transit graph was built by selecting one representative trip per `(route_id, direction_id)`, choosing the weekday trip whose first-stop departure was closest to noon. Purple Express only runs during rush hours. GTFS data confirmed: 135 weekday Purple trips have 9 stops (Evanston local, Linden→Howard) while 55 trips have 43 stops (Purple Express, Linden→Loop). The noon selector reliably picked a local trip, so no Purple edges existed south of Howard — Purple Line could never route to downtown.

**Secondary bug (Bug 2 — shared-track line suppression):** On segments where two lines serve the same consecutive stops (e.g. Red/Purple at Belmont→Fullerton, Green/Pink at Loop elevated stations), only one edge is stored per `(from, to)` node pair. The competing line was saved in an `all_routes` edge attribute but `_dedup_stations_by_line` read only the primary `line` attribute, making shared-track lines invisible to station deduplication.

**What was implemented (2 chunks, `backend/transit_graph.py` only):**
- **Chunk 1:** Changed representative trip selection in `_stream_all_stop_sequences` from "closest to noon" to "most parent-station stops, tie-break by noon proximity." This selects Purple Express (43 stops) over the Evanston local (9 stops). For all other lines with full-length all-day service the selection is unchanged — no regression risk.
- **Chunk 2:** Rewrote the `station_lines` collection in `_dedup_stations_by_line` to also iterate the `all_routes` attribute on each edge, so every line serving a shared-track segment is visible to station deduplication.

---

# Feature Autocomplete — Location Input Suggestions

**Completed: 2026-04-25**

**Overview:** As the user types in the origin or destination field, a dropdown of up to 8 matching suggestions appears covering CTA train stations, named neighborhoods/landmarks, and deduplicated bus stop names. Selecting a suggestion fills the field exactly. The autocomplete dropdown takes priority over the saved-locations dropdown while the user is actively typing; when the field is cleared or blurred, the saved-locations dropdown resumes normal behavior.

**What was implemented (1 chunk, Chunk 2 / Google Places deferred):**

- **Backend (`backend/main.py`):** `_build_autocomplete_index()` runs at startup (inside `lifespan`) and populates three module-level lists: `_ac_train_names` (~145 CTA parent station names from `_load_stops()`), `_ac_neighborhood_names` (title-cased keys from `NEIGHBORHOOD_COORDS`), and `_ac_bus_names` (bus stop names deduplicated by lowercase name). `_ac_score(query, name) -> int | None` returns 0 (prefix), 1 (word-start), 2 (substring), or `None` (no match). `GET /autocomplete?q=<str>` returns `{"suggestions": [...]}` with objects `{label, value, type}` where type is `"train"`, `"neighborhood"`, or `"bus"`. Results are sorted by (tier, match-quality score) and capped at 8. Requires `Query` added to FastAPI imports and `_load_stops` added to gtfs_loader imports.
- **Frontend (`frontend/src/App.jsx`):** `LocationInput` gains `acSuggestions` (list), `acActiveIndex` (int), `acDebounceRef`, and `acAbortRef`. The `onChange` handler calls `fetchAcSuggestions()` which debounces 200 ms then fetches `/autocomplete`, cancelling any in-flight request via `AbortController`. The autocomplete dropdown reuses `.saved-dropdown` / `.saved-dropdown-item` CSS and shows above the saved-locations dropdown (which is now gated on `acSuggestions.length === 0`). Keyboard navigation: `ArrowDown`/`ArrowUp` move `acActiveIndex`, `Enter` selects the highlighted item, `Escape` closes without selecting. `onBlur` clears suggestions after 150 ms (so `onMouseDown` on an item fires first). On focus with an existing value ≥ 2 chars, autocomplete fires immediately.
- **Frontend (`frontend/src/App.css`):** Added `.ac-type-badge` (small muted uppercase label) and `.saved-dropdown-item--active` (active-highlight background) rules.

**Deferred (Chunk 2):** Google Places Autocomplete API integration for street address suggestions — deferred pending Places API enablement in GCP Console.

---

# Feature WalkMode — Walk-Only Transit Mode

**Completed: 2026-04-27**

**Overview:** Added a fourth transit mode option — **Walk** — to the mode selector. When selected, the app skips all CTA train/bus API calls and instead computes a street-network walking route between origin and destination using the existing `walking.py` infrastructure, returning turn-by-turn directions, an estimated walking time, and a polyline path.

**What was implemented (2 chunks):**

- **Backend (`backend/main.py`):**
  - Added `"Walk"` to `_VALID_TRANSIT_MODES`. Updated `RouteRequest` transit_mode comment. Updated `_validate_api_keys` to skip the `CTA_TRAIN_API_KEY` requirement when `transit_mode == "Walk"`.
  - Added `Route` to `transit_graph` imports and new `walking` module imports (`_walk_minutes`, `_walk_directions`, `_walk_path`).
  - Added `"Walk"` entry to `mode_constraints` in `build_prompt()`: `"The rider wants to WALK. Provide a brief summary of the walking route and estimated time. Do not mention transit."`
  - Added Walk mode early-return branch in `recommend()` after the cache check: geocodes origin/destination directly (no CTA stop lookup required), runs `walk_minutes`/`walk_directions`/`walk_path` concurrently via `asyncio.gather` + `run_in_executor`, applies `walk_speed` scaling, wraps result in a single `WalkLeg` + `Route`, builds prompt, optionally calls Claude, formats and caches the response using the existing `_format_response` schema. All CTA API calls (arrivals, routing, transfer arrivals, alerts) are entirely bypassed.

- **Frontend + i18n (`frontend/src/App.jsx`, all 22 locale files):**
  - Added `<option value="Walk">{t("mode_walk")}</option>` to the transit mode selector after the Bus option.
  - Added `"mode_walk"` key to all 22 `frontend/public/locales/*/translation.json` files with native-language translations (en: Walk, es: Caminar, fr: Marche, ar: مشي, zh/yue: 步行, hi/ne: पैदल/हिँडाइ, ur/pa: پیدل/ਪੈਦਲ, gu: ચાલો, ko: 걷기, ja: 徒歩（とほ）, ru: Пешком, uk: Пішки, pl: Pieszo, ro: Mers pe jos, vi: Đi bộ, tl: Maglakad, yo: Rìn, ps: پلي, it: A piedi).
  - No changes needed to result rendering — the walk-only response uses the existing `WalkLeg` schema that RouteCard already renders.

---

# Feature Walk Speed — Walking Speed Preference

**Completed: 2026-04-27**

**Overview:** Users set their walking pace (Slow / Standard / Brisk) in the Settings panel. The preference is stored in `localStorage`, and the corresponding multiplier is sent as `walk_speed` in the `/recommend` request body. The backend applies the multiplier to every `WalkLeg` before route ranking so both displayed walk times and route ordering reflect the user's actual pace.

**What was implemented (2 chunks):**

- **Backend (`backend/main.py`):**
  - Added `Field` to the pydantic import.
  - Added `walk_speed: float = Field(default=1.0, ge=0.5, le=2.0)` to `RouteRequest`. `walk_speed=1.0` is a no-op; standard requests omit the field and get the default.
  - Added `walk_speed` to `_cache_key()` so different pace preferences cache separately.
  - Added `_scale_walk_legs(routes, walk_speed)` helper: iterates all `WalkLeg`s in a route list, multiplies `leg.minutes` by `1 / walk_speed` (rounded to 1 decimal), then updates `route.walk_minutes_total`. No-op when `walk_speed == 1.0`.
  - Refactored `_run_routing()`: `find_routes()` result is stored as `raw_routes`, `_scale_walk_legs` is called before `_rank_routes`. For bus transfer routes from `find_bus_transfer_routes()`, walk legs are scaled and tuple totals are rebuilt before `_rank_bus_routes`.

- **Frontend (`frontend/src/components/SettingsPanel.jsx`, `frontend/src/App.jsx`, `frontend/src/App.css`, all 22 locale files):**
  - `SettingsPanel.jsx`: Added `walkSpeed` and `onWalkSpeedChange` props. Renders a three-button segmented toggle (Slow | Standard | Brisk) using `.walk-speed-toggle` / `.walk-speed-btn` / `.walk-speed-btn--active` CSS classes. Labels use `t("settings_walk_speed_{speed}")` i18n keys.
  - `App.jsx`: Added `walkSpeed` state (initialized from `localStorage.getItem("cta_walk_speed") || "standard"`). Added `WALK_SPEED_FACTORS = { slow: 0.75, standard: 1.0, brisk: 1.25 }` constant. Added `handleWalkSpeedChange(speed)` handler (writes to state + localStorage). Both fetch bodies (GPS reroute and normal submit) conditionally include `walk_speed: WALK_SPEED_FACTORS[walkSpeed]` when the factor is not 1.0. Props `walkSpeed` and `onWalkSpeedChange` passed to `SettingsPanel`.
  - `App.css`: Added `.walk-speed-toggle`, `.walk-speed-btn`, `.walk-speed-btn:last-child`, `.walk-speed-btn:hover`, and `.walk-speed-btn--active` rules.
  - All 22 `frontend/public/locales/*/translation.json` files: Added `settings_walk_speed_label`, `settings_walk_speed_slow`, `settings_walk_speed_standard`, `settings_walk_speed_brisk`, and `settings_walk_speed_hint` keys with native-language translations.

---

## Feature Pinned Stops — Saved-Stop Arrivals Board

**Completed: 2026-04-27**

**Overview:** Users can pin individual transit stops (train stations or bus stops) from any route result leg to a persistent home-screen board that shows live arrivals without typing an origin/destination. Persists in `localStorage`; live arrivals fetched on demand.

**What was implemented (3 chunks):**

- **Backend (`backend/main.py`, `backend/transit_graph.py`):**
  - Added `"from_mapid": leg.from_mapid` to the `TransitLeg` serialization branch in `_format_response()` so the frontend knows which stop to offer for pinning.
  - Added `GET /stop-arrivals` endpoint: accepts `stops` as repeated `type:stop_id` query params (e.g. `train:40500`), gathers train and bus arrivals concurrently via `asyncio.gather`, caps at 3 arrivals per stop, returns `{ "arrivals": { "<stop_id>": { "arrivals": [...] } } }`. Non-fatal per-stop errors logged but not surfaced. 30 s `OrderedDict` TTL cache (200-entry cap) keyed on sorted stop list string.

- **Frontend storage (`frontend/src/favorites.js`):**
  - Added `PINNED_KEY = "cta_pinned_stops"` constant (separate namespace from locations/routes).
  - Added four functions following the existing plain-module pattern: `getPinnedStops()`, `pinStop(type, stop_id, label, route_hint)` (returns `null` at 10-stop cap), `unpinStop(id)`, `isStopPinned(stop_id)`.

- **Frontend UI (`frontend/src/components/PinnedStopsBoard.jsx` new, `frontend/src/components/RouteCard.jsx`, `frontend/src/App.jsx`, `frontend/src/App.css`):**
  - `PinnedStopsBoard.jsx`: New component. Header with title + refresh button. Horizontally scrollable row of stop cards each showing label, route_hint badge, up to 3 `ArrivalPill` sub-components (colored by `LINE_COLORS`/`BUS_DIRECTION_COLORS`), and unpin (×) button. Returns `null` when `stops.length === 0`.
  - `RouteCard.jsx`: Pin button (📍/📌) on each transit leg. Derives `stopId = leg.from_mapid`, calls `onPinToggle(stopType, stopId, leg.from, leg.line_code, isPinned)` via prop callback. Walk legs omitted.
  - `App.jsx`: Added `pinnedStops` state (initialized from `getPinnedStops()`), `pinnedArrivals` state, `fetchPinnedArrivals()` async function, `handlePinToggle()` handler wiring `pinStop`/`unpinStop` + state updates. `useEffect` fetches arrivals on mount if stops exist. `PinnedStopsBoard` rendered above the search form. `pinnedStops` and `onPinToggle` passed to each `RouteCard`.
  - `App.css`: Added `.pin-btn` / `.pin-btn--pinned` and full PinnedStopsBoard CSS (`.psb`, `.psb-card`, `.psb-arrival-pill`, etc.).

---

## Feature Last Train — Last Train Countdown

**Completed: 2026-04-27**

**Overview:** Pinned train station cards show a countdown badge ("Last train in X min") when within 0–120 minutes of the last scheduled weekday departure for that station. Motivates late-night app opens and repeat visits.

**What was implemented (3 chunks):**

- **Backend graph (`backend/transit_graph.py`):**
  - Added module-level `_last_departure: dict[tuple[str, str], str] = {}` dict.
  - Extended `_stream_all_stop_sequences()` to return a 3-tuple, accumulating `last_dep: dict[tuple[str, str], tuple[float, str]]` keyed on `(parent_mapid, direction_id)` — the latest departure time string (by parsed minutes) seen across all weekday train trips per station/direction pair. Both directions `"0"` and `"1"` tracked independently.
  - `_build_graph()` unpacks the 3-tuple and assigns `_last_departure` via `global`.
  - Added `get_last_departure(mapid: str, direction_id: str) -> str | None` public helper.

- **Backend endpoint (`backend/main.py`):**
  - Added `from datetime import datetime` and `from zoneinfo import ZoneInfo` imports; defined `_CHICAGO_TZ = ZoneInfo("America/Chicago")`.
  - Added `_parse_gtfs_time_mins(t: str) -> float` — handles 24:xx/25:xx post-midnight GTFS times naturally (h×60+m+s/60, no special case needed).
  - Added `_last_dep_minutes(mapid: str, now_chicago: datetime) -> int | None` — computes `now_mins` (offset by +1440 when hour < 3 to align with GTFS 24:xx/25:xx encoding), checks both direction `"0"` and `"1"`, returns the maximum minutes-until-last-departure in the 0–120 window (or `None`).
  - Extended `/stop-arrivals` handler: for each train stop in the response, calls `_last_dep_minutes(stop_id, now_chicago)` and includes `"last_departure_minutes": int` in the payload when the value is in range.

- **Frontend (`frontend/src/components/PinnedStopsBoard.jsx`):**
  - `PinnedStopsBoard` reads `data.last_departure_minutes` per stop card.
  - Renders a badge below the arrival pills: "Last train in X min". Styled amber (`.psb-last-train`, `#78350f` bg / `#fbbf24` text) normally; red (`.psb-last-train--urgent`, `#7f1d1d` bg / `#f87171` text) when ≤ 15 min. Hidden when `last_departure_minutes` is absent.
