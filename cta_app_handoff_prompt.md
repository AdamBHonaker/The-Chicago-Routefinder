# CTA AI Transit Recommendation App — Project Brief

## Overview

You are helping me build a Progressive Web App (PWA) that provides AI-powered, real-time CTA transit recommendations for Chicago riders. I am a non-technical user based in Chicago with no prior coding background, but I am comfortable working with Claude to build functional tools and scripts. Please guide me step by step, writing all code, explaining decisions clearly, and debugging as we go.

---

## What the App Does

A user inputs their current location and destination. The app:

1. Fetches real-time CTA train and bus arrival data
2. Runs a routing algorithm to calculate the fastest option including transfers and walking legs
3. Passes the calculated route options to Claude via the Anthropic API
4. Claude returns a conversational, plain-English recommendation explaining the best route and why

> **Important:** The AI layer handles explanation and reasoning — NOT raw routing calculations. Routing must be handled deterministically in code for accuracy. Claude's job is the last mile: turning a correct, code-generated answer into a helpful, conversational response.

---

## Accuracy Requirements

Accuracy is essential. The routing engine must:

- Account for all CTA train lines, stops, and transfer points
- Account for all relevant bus routes
- Calculate walking distances between stops and destinations using real street network data
- Factor in real-time arrival times from the CTA API
- Rank options by total trip time including walking legs and transfers
- Only after calculating correct options should Claude be invoked to explain them

---

## Tech Stack

**Frontend**
- React (PWA)
- HTML, CSS, JavaScript
- MapLibre GL JS v4 — map rendering (v5 had WebGL2 init issues in React StrictMode; pinned to v4.7.1)
- OpenFreeMap Liberty — vector tile style (free, no API key; Positron style dropped — had null-typed expression errors in MapLibre v4/v5)

**Backend**
- Python
- FastAPI (server connecting routing engine to React frontend)

**Hosting**
- Railway (backend, free tier)
- Vercel (frontend, free tier)

**Routing Engine (Python libraries)**
- `networkx` — graph-based route calculation
- `osmnx` — walking distance via real street network data
- `igraph` — C-backed graph library used by `walking.py` for the street routing graph (OPT-008); ~10× lower RAM than NetworkX
- `scipy` — `cKDTree` used by `walking.py` for nearest-node lookup, replacing `osmnx.nearest_nodes()` (OPT-008)
- `scikit-learn` — transitive dep of osmnx; retained in requirements.txt for compatibility
- `requests` — CTA API HTTP calls + Google Maps geocoding
- `aiohttp` — simultaneous async API calls for speed

> Note: CTA GTFS data is parsed directly with Python's built-in `csv` module (streaming). `gtfs_kit`, `pandas`, and `shapely` were considered during planning but are not used — direct CSV parsing proved sufficient and keeps the dependency footprint small.

**AI Integration**
- `anthropic` (official Python SDK) — Claude API calls from backend
- Model: `claude-sonnet-4-6` by default; `claude-haiku-4-5-20251001` for simple single-option/single-leg queries (see cost reduction strategies below). Both model IDs are overridable via `CLAUDE_COMPLEX_MODEL` / `CLAUDE_SIMPLE_MODEL` Railway env vars.

**Database** *(not planned for V1 or V2)*
- No database required. Phase 7 is ad monetization (AdSense). User accounts and saved routes are not currently planned.

---

## Data Sources

**Static**
- CTA GTFS data — free download from transitchicago.com (stops, routes, schedules, transfer points)
- Curated list of key Chicago destinations with coordinates (to be built out over time)

**Live**
- CTA Train Tracker API — real-time train arrivals (free, requires API key)
- CTA Bus Tracker API — real-time bus arrivals (free, separate API key)
- CTA Alerts API — service disruptions and delays (free)

**Walking Distance**
- OSMnx (required) — real street-network walking times; not interchangeable with Google Maps

---

## API Keys Needed
*(I will obtain these separately)*

- CTA Train Tracker API key — transitchicago.com
- CTA Bus Tracker API key — transitchicago.com
- Anthropic API key — console.anthropic.com
- Google Maps API key — required for geocoding (addresses, landmarks). OSMnx handles walking distances separately and is non-negotiable; Google Maps is for geocoding only.

---

## Monetization Plan

- Ad-supported model — free to all users, revenue generated through ads
- No subscription tier planned at this stage
- Ad network integration to be added after user base is established
- Stripe not needed for V1

---

## Cost Model & Financial Reality

- Primary variable cost: Claude API usage at ~$0.01 per user request (Sonnet rates)
- Ad revenue realistic CPM: $1–3 for a local utility app, up to $5 with premium networks
- Break-even estimated at 8,000–10,000 daily active users
- Early stage expectation: $50–200/month out of pocket before ad revenue catches up

**Cost reduction strategies to implement from the start:**
- Limit free requests per user per day to control API costs
- Cache Claude responses for identical or near-identical queries
- Claude Haiku for simple queries ✅ implemented 2026-04-18: `/recommend` picks `claude-haiku-4-5-20251001` when `ranked_routes` has exactly one route with exactly one `TransitLeg` (direct ride, no transfer); all other queries keep `claude-sonnet-4-6`. Response includes `"model_used": "haiku"|"sonnet"` for observability. Both model IDs are configurable via `CLAUDE_SIMPLE_MODEL` / `CLAUDE_COMPLEX_MODEL` Railway env vars (TD-004, resolved 2026-04-20).
- AI Toggle (Feature AI Toggle) ✅ implemented 2026-04-20: Claude recommendation layer is now **opt-in** (off by default). Frontend settings panel (gear icon, always visible) has an "AI Explanation" checkbox persisted to `localStorage["cta_ai_enabled"]`. Frontend sends `ai_enabled: bool` in the request body. Backend skips `_call_claude()` entirely when `false` — returns `recommendation: null`, no token spend. Paywall-ready: add an auth check inside `if request.ai_enabled:` in `main.py`. See `FEATURES_IMPLEMENTED_HISTORY.md` for full details.

> **Rate limiting status:** Code complete — OFF by default. Activate with `RATE_LIMIT_ENABLED=true` in Railway env vars before enabling for public traffic.

> Owner has no fixed staffing costs — significant structural cost advantage over competitors

---

## Bring Your Own API Key (BYOK) — ✅ Code Complete

Users can supply their own Anthropic API key via an in-app settings panel. Their usage costs shift entirely off the app's variable cost base.

**Status:** Code complete — OFF by default. Activate with `BYOK_ENABLED=true` (Railway) + `VITE_BYOK_ENABLED=true` (Vercel) before enabling for users.

- Key is stored in `sessionStorage` (clears on tab close) — not `localStorage`
- Settings panel shows a visible security notice warning the user that the key lives in the browser and should only be entered on trusted personal devices (2026-04-18)
- BYOK requests use a separate response-cache pool (keyed separately from shared-quota requests)
- Most CTA riders will not use this feature; it targets technically savvy early adopters

---

## UX Philosophy

- Single clear recommendation first, alternatives secondary
- Explain the why behind every recommendation in plain English
- Clean, minimal interface — no decision fatigue in the UI itself
- Mobile-first design, optimized for use while standing at a bus stop
- Fast load time is critical — users are often checking in real-time situations

---

## Important Notes on CTA Data

- CTA updates its GTFS static data regularly — a maintenance process is needed to keep it current
- Real-time API data comes from the same source competitors use — advantage is in how it's surfaced
- CTA has a 100,000 request/day API limit — caching strategy is essential from the start
- For scale beyond 100,000 daily API calls, plan to contact CTA directly for higher limits

---

## Competitive Positioning

**Primary competitors:** Google Maps, Apple Maps, Ventra app, Transit app

**Key differentiators:**
- Eliminates decision fatigue — gives one clear recommendation with reasoning, not a list of options
- Conversational AI explanation of WHY a route is best, not just what it is
- Cleaner surfacing of real-time CTA data vs competitors

**Core marketing message:** *"Stop thinking about how to get there, just go"*

**Target user:** Chicago CTA riders frustrated by too many options or confusing transfer decisions

---

## Marketing Strategy (Early Stage)

- Post to r/chicago and r/CTA with authentic "I built this" framing
- Physical flyers at coffee shops, libraries, transit hubs, and bus stop poles near CTA stations
- Lean into decision fatigue elimination as the core emotional hook
- Local Chicago tech blogs and media as a secondary channel
- Word of mouth from genuine utility — if it works well, riders will share it

> **Note:** User acquisition is the primary unsolved challenge and should be revisited seriously before Phase 6.

---

## Build Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Validation | ✅ Complete |
| 2 | Prototype with mock CTA data + Claude API connected | ✅ Complete |
| 3 | Integrate live CTA Train and Bus Tracker APIs | ✅ Complete |
| 4 | Build routing engine (GTFS + NetworkX + OSMnx) | ✅ Complete |
| 5 | Polish UI, PWA configuration, mobile optimization | ✅ Complete (verified locally) |
| 5.5 | Bus routing — structured route cards | ✅ Complete (2026-04-09) |
| 5.6 | Map feature — MapLibre GL JS + GTFS shapes + OSMnx walk geometry | ✅ Complete (2026-04-09) |
| 6 | Deploy publicly (Vercel + Railway + custom domain) | ✅ Complete (2026-04-14) |
| 7 | Monetization (AdSense) | ⬜ Pending |

---

## Phase 4 Routing Engine — Step Status

| Step | Description | Status |
|------|-------------|--------|
| 1 | GTFS data setup — fetch_gtfs.py downloads CTA static feed to backend/gtfs_data/ | ✅ Complete |
| 2 | Stop resolver — gtfs_loader.py finds nearest stops from GTFS coordinates | ✅ Complete |
| 3 | Walking legs — walking.py + fetch_street_graph.py, OSMnx street-network walk times | ✅ Complete |
| 4 | Route graph — NetworkX graph of transit network, shortest-path routing | ✅ Complete |
| 5 | Tie together — feed calculated routes + live arrivals to Claude | ✅ Complete |

---

## Known Pending Items

- **CTA API limit:** 100,000 req/day (confirmed from Train Tracker docs). Plan caching strategy around 100k.
- **Known bugs:** See `BUGS_TO_BE_FIXED.md` for open bugs (0 🔴 high, 0 🟡 medium, 1 🟢 low). Resolved bugs are logged in `BUGS_FIXED_HISTORY.md`. When a bug is fixed, delete it from `BUGS_TO_BE_FIXED.md` and add an entry to `BUGS_FIXED_HISTORY.md`.
- **Future enhancements:** See `FEATURE_IMPLEMENTATION_PLANS.md` for chunked build plans. See `Feature_Prioritization.md` for bolt-on vs structural classification and full status. Key items: ~~Train Station Exit Guidance (Feature A, 5 chunks)~~ ✅ Complete, ~~Multi-Leg Bus Routing / bus+bus transfers (Feature C, 5 chunks)~~ ✅ Complete, ~~Intermodal Routing / train+bus combinations (Feature B, 6 chunks)~~ ✅ Complete (2026-04-16), ~~Live Arrivals at Transfer Stop (Feature D, 4 chunks)~~ ✅ Complete (2026-04-18), ~~Walk Leg Block-Count Distance Display (Feature E, 2 chunks)~~ ✅ Complete, ~~Street Abbreviation Normalization (Feature F, 1 chunk)~~ ✅ Complete, ~~Long/Short Block Classification (Feature G, 2 chunks)~~ ✅ Complete, ~~Deduplicate Same-Line Station Candidates (Feature H, bolt-on, 3 chunks)~~ ✅ Complete (2026-04-17), ~~CTA Alerts Integration (Feature I, bolt-on, 3 chunks)~~ ✅ Complete (2026-04-17), ~~Deprecate `find_bus_routes()` in Favor of Unified Graph (Feature J, bolt-on, 3 chunks)~~ ✅ Complete (2026-04-18), ~~Multi-Language Support / i18n (Feature Language, 6 chunks)~~ ✅ Complete (2026-04-20). Beyond chunked features: ~~rate limiting~~ ✅ Code complete (activate with `RATE_LIMIT_ENABLED=true`), ~~BYOK~~ ✅ Code complete (activate with `BYOK_ENABLED=true` + `VITE_BYOK_ENABLED=true`), ~~response caching~~ ✅ Complete, Claude Haiku for simple queries. ~~Multi-leg train routing accuracy gaps: (a) shared-track edge deduplication can mis-label the line on segments where multiple CTA lines share consecutive stations (e.g. Red/Purple between Howard and Belmont) — timing is correct but the route card may show the wrong line name~~ ✅ Fixed 2026-04-20 (see FEATURES_IMPLEMENTED_HISTORY.md); (b) ~~bus access to a better-positioned train station is never considered~~ ✅ Resolved by Feature B.
- **API keys:** All four keys obtained and configured: CTA Train Tracker, CTA Bus Tracker, Anthropic, and Google Maps.
- **Geocoding:** Google Maps Geocoding API implemented (`geocode_google()` in `gtfs_loader.py`). A monthly call cap (default 9,500) is enforced as a production cost guard, configurable via `GEOCODE_MONTHLY_LIMIT` env var (set to `0` to disable).

### Notable changes (session — 2026-04-06)
Three bugs in `backend/main.py` were fixed before deployment:
1. **Async event loop blocking** — `resolve_location`, `_coords_for_location`, and the Anthropic call all now run off the event loop (`run_in_executor` / `AsyncAnthropic`). Server handles concurrent requests correctly.
2. **Out-of-coverage destination** — If the destination geocodes but has no CTA stops nearby, a clear 400 is returned explaining the coverage boundary. Previously the app silently returned empty results.
3. **Anthropic client singleton** — `_claude_client = anthropic.AsyncAnthropic(...)` is now instantiated once at module level instead of on every request.

### Notable changes (session — 2026-04-08)
1. **Workbox production URL** — `vite.config.js` `runtimeCaching` pattern updated from `http://localhost:8000/.*` to `/\/(recommend|health)/` so the `NetworkOnly` rule applies to the Railway production URL, not just localhost.
2. **Stale comment removed** — `cta_client.py` module docstring updated; old Phase 4 TODO comment about bus stop IDs removed (Phase 4 is complete).
3. **Tech stack corrected** — Handoff tech stack section updated; `gtfs_kit`, `pandas`, `shapely` removed (not used — direct CSV parsing is used instead).
4. **`max_tokens` raised to 750** — Was 300. Raised for testing to give Claude more room. *(Subsequently lowered to 400 to align with "3-4 sentences" prompt instruction — session 2026-04-10 bug fix batches.)*
5. **Frontend request timeout removed** — `App.jsx` no longer imposes a 15-second `AbortController` timeout. Requests run until the server responds. *(An `AbortController` was subsequently re-added as a race condition guard — cancels in-flight request on re-submit, not a timeout — session 2026-04-10 bug fix batches.)*
6. **Rate limiting deferred** — Noted in documentation; intentionally not implemented during testing phase. Must add before or shortly after public launch.

### Notable changes (session — 2026-04-09)
1. **Off-peak trip selection fixed** — `transit_graph.py`: `_load_weekday_service_ids()` added; `_load_representative_trips()` now loads all weekday candidate trips per direction; `_stream_stop_sequences()` selects the trip whose first-stop arrival is closest to noon per line/direction.
2. **Structured bus route cards built** — `transit_graph.py`: `get_bus_stop_sequences()` builds a `{(route_short_name, direction_id): [(stop_id, stop_name, lat, lon, arr_minutes), ...]}` table at startup (second pass through `stop_times.txt`); `find_bus_routes()` computes `Route` objects from live bus arrivals using stop_id-based direction resolution (no direction-string mapping needed — CTA GTFS stop IDs are direction-specific). `main.py`: train and bus routes merged into one ranked list, capped at 5; `_format_train_routes` renamed `_format_routes` and extended for bus legs; `line_code` added to leg serialization. `cta_client.py`: `stop_id` added to bus arrival dicts.
3. **Bus direction resolution confirmed** — stop_id approach correctly identifies southbound (and by the same logic, all directions) without any direction-string-to-direction_id mapping.
4. **Geocoding upgrade triggered** — Nominatim returns wrong/missing results for specific landmarks and addresses. Google Maps Geocoding API upgrade (already planned as Option B in gtfs_loader.py) is now required. Awaiting `GOOGLE_MAPS_API_KEY` from user to implement.
5. **Intermodal routing deferred** — combined train+bus trips (e.g., train then bus) not supported at this stage. Documented as a post-launch enhancement. *(Subsequently implemented as Feature B — ✅ Complete 2026-04-16.)*
6. **Bus direction colors added (Chunk 4 complete)** — `App.jsx`: `BUS_DIRECTION_COLORS` added for Northbound/Southbound/Eastbound/Westbound; bus leg pill now shows route number (`line_code`) with direction-based color.
7. **`osmnx` import fixed** — `walking.py`: `import osmnx as ox` moved to module level so a missing dependency crashes at startup rather than being silently swallowed by the walk-time `try/except`.
8. **Bus stop ID batching fixed** — `cta_client.py`: `get_bus_arrivals()` now splits stop IDs into chunks of 10 and fires all chunks concurrently via `asyncio.gather` using new `_fetch_bus_chunk()` helper. Previously silently truncated to 10 stops.
9. **`psgld` normalization added; Bus Fullness filter hidden** — `cta_client.py`: raw `psgld` value normalized to `UPPER_SNAKE` at read time. Live API testing confirmed CTA does not currently populate `psgld` in any Bus Tracker v3 responses — Bus Fullness `<select>` commented out in `App.jsx` until CTA enables this data. Backend filter logic preserved intact.
10. **Map feature designed** — MapLibre GL JS + OpenFreeMap Positron selected. Full design decisions and 10-chunk implementation plan documented in `MAP_IMPLEMENTATION_PLAN.md`. This is Phase 5.6 and the next coding work to begin.

### Notable changes (session — 2026-04-09, walk directions + enhancements doc)
1. **Street-level walk directions** — `walking.py`: new `walk_directions(origin_lat, origin_lon, dest_lat, dest_lon) -> list[dict]` (lru_cache 512). Uses OSMnx shortest path, reads edge `name` + `length`, groups consecutive same-street edges, computes cardinal bearing per group, returns `[{"street": "Broadway", "direction": "S", "minutes": 1.2}, ...]`. Falls back to a single unnamed step on error.
2. **`WalkLeg.directions` field** — `transit_graph.py`: `WalkLeg` gains `directions: list` field. `walk_directions` (imported as `street_walk_directions`) called on all walk legs — origin→board station, board station→destination (both train and bus routes), and inter-station transfer legs. Import: `from walking import walk_directions as street_walk_directions`.
3. **Directions serialized** — `main.py`: `"directions": leg.directions` added to walk leg in `/recommend` response.
4. **Steps toggle in route cards** — `App.jsx`: walk legs now render as `WalkLegItem` component with a "Steps" toggle button. Only shown when `leg.directions.length > 1`. When open, shows a compact step list: arrow glyph + cardinal abbreviation + street name + duration. New CSS classes: `leg-walk-body`, `leg-steps-toggle`, `leg-steps`, `leg-step`, `leg-step-arrow`, `leg-step-text`, `leg-step-dir`, `leg-step-street`, `leg-step-time`.
5. **`FUTURE_ENHANCEMENTS.md` created** — New file cataloguing post-launch feature ideas: train station exit guidance, intermodal routing, rate limiting, BYOK, response caching, Claude Haiku for simple queries. *(File subsequently deleted — all content merged into `FEATURE_IMPLEMENTATION_PLANS.md` as Features A–F with full chunked plans.)*

---

### Notable changes (session — 2026-04-09, pre-deployment bug fixes)
1. **Claude API error handling** — `backend/main.py`: `_claude_client.messages.create()` wrapped in try/except; response text extracted safely via `next(... if hasattr(c, "text"))` to handle non-text blocks; raises HTTP 502 on failure; full traceback printed to logs.
2. **Train direction-aware arrival lookup** — `backend/main.py` + `backend/transit_graph.py`: `_build_arrival_lookup` now returns `{(line_code, mapid): {destNm: minutes}}`. `_rank_routes` uses a dot-product bearing test (boarding→exit vector vs boarding→terminal vector) to select the correct direction from live arrivals. Two new helpers in `transit_graph.py`: `get_station_coords(mapid)` and `get_station_by_name(name)`, backed by the already-cached graph. Falls back to earliest arrival if coordinates unavailable.
3. **Frontend non-JSON error handling** — `frontend/src/App.jsx`: non-OK responses now attempt `res.json()` in a try/catch; HTML gateway errors (Railway 502s) fall back to `"Service error (502 Bad Gateway)"` instead of a cryptic SyntaxError.

---

### Notable changes (session — 2026-04-10, comprehensive bug audit)

A full two-pass bug audit was performed across all backend and frontend files. One critical bug was fixed immediately; the rest were documented in `BUGS_TO_BE_FIXED.md` and subsequently fixed (see `BUGS_FIXED_HISTORY.md`).

**Fixed this session:**
1. **`load_dotenv()` import-order bug** — `backend/main.py`: `load_dotenv()` was called on line 19, after `from gtfs_loader import ...` on line 12. Python executes `gtfs_loader.py` at import time, including `_GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")` — before `.env` was loaded. Google Maps API key was always `""` regardless of what was in `.env`. Fixed by moving `load_dotenv()` to before the local imports. This was the root cause of geocoding failures during testing.

**Bugs catalogued this session (all subsequently fixed — see session 2026-04-10 bug fix batches):**

*🟡 Medium (all fixed):*
- ~~`line-cap`/`line-join` placed in MapLibre `paint` instead of `layout` in `MapView.jsx`~~ ✅
- ~~`wait_minutes === 0` ("Due") shows no indicator in `RouteCard`~~ ✅
- ~~No `AbortController` on the `/recommend` fetch — race condition on re-submit~~ ✅
- ~~PWA `globPatterns` includes all `*.png` files~~ ✅ Fixed in session 2026-04-11 Batch 4 (`icon-*.png` explicit list + `StaleWhileRevalidate` runtime cache for transit-photos)

*🟢 Low (all fixed):*
- ~~`renderMarkdown` strips `**bold**` but not `*italic*`~~ ✅
- ~~`_load_weekday_service_ids()` only checks Mon + Tue + Wed~~ ✅
- ~~Train arrival datetime `.replace(tzinfo=...)` wrong for ISO strings with UTC offset~~ ✅
- ~~Destination walk times computed in wrong direction~~ ✅
- ~~`validate_and_report()` uses `encoding="utf-8"` instead of `"utf-8-sig"`~~ ✅
- ~~`photoFadeTimer` ref not cleared on `App` unmount~~ ✅
- ~~Routing exceptions swallow traceback~~ ✅
- ~~Missing `CTA_BUS_API_KEY` validation when bus mode requested~~ ✅
- ~~`max_tokens=750` misaligned with "3-4 sentences" prompt~~ ✅
- ~~PWA manifest combined `"any maskable"` icon entry~~ ✅
- ~~No validation when origin and destination resolve to the same location~~ ✅
- ~~`G_base.copy()` called on every train routing request~~ ✅
- ~~`_coords_for_location()` duplicates fuzzy-match logic from `resolve_location()`~~ ✅
- ~~Redundant `walk_minutes` recomputation for destination stations~~ ✅
- ~~Bus routing wrong direction sequence for stops served by multiple directions~~ ✅

**Pre-deployment bug status update:** All 🔴/🟡/🟢 bugs fixed. Zero deferred bugs remain.

---

### Notable changes (session — 2026-04-10, bug fix batches 1–3)

All 🟡 and most 🟢 bugs from the 2026-04-10 audit were fixed across three batches.

**Batch 1 — 🟡 Frontend correctness:**
1. **`line-cap`/`line-join` moved to `layout`** — `MapView.jsx`: transit polylines now render with rounded caps and joins as intended.
2. **`wait_minutes === 0` "Due now" indicator** — `App.jsx`: `RouteCard` now distinguishes `null` (no data), `0` ("Due now"), and `> 0` ("N min wait").
3. **`AbortController` race condition** — `App.jsx`: in-flight `/recommend` fetch is cancelled on re-submit; `AbortError` silently discarded so cancelled searches don't show error messages.

**Batch 2 — 🟢 Quick fixes (backend + frontend):**
4. **`renderMarkdown` italic stripping** — `App.jsx`: `*italic*` and `_italic_` now stripped alongside `**bold**`.
5. **`photoFadeTimer` unmount cleanup** — `App.jsx`: `useEffect` cleanup cancels pending fade timer; suppresses React StrictMode warning.
6. **Routing exception tracebacks** — `main.py`: both train and bus routing `except` blocks now call `traceback.print_exc()`; `import traceback` moved to module level.
7. **`CTA_BUS_API_KEY` validation** — `main.py`: raises HTTP 500 if bus key is missing when transit mode is Bus or All.
8. **`validate_and_report()` encoding** — `fetch_gtfs.py`: changed `"utf-8"` → `"utf-8-sig"` to match all other GTFS readers.
9. **`max_tokens` re-aligned** — `main.py`: lowered from 750 → 400 to match "3-4 sentences" prompt instruction.
10. **PWA manifest icon split** — `vite.config.js`: 512px icon split into two entries (`purpose: "any"` and `purpose: "maskable"`) per PWA spec.
11. **Origin = destination guard** — `main.py`: returns HTTP 400 if resolved coords are within ~100m of each other.

**Batch 3 — 🟢 Backend correctness:**
12. **`_load_weekday_service_ids()` full Mon–Fri check** — `transit_graph.py`: condition now checks all five weekday columns via `all(...)`.
13. **Train arrival datetime timezone handling** — `cta_client.py`: ISO strings with an existing `tzinfo` are now converted via `.astimezone()` instead of blindly re-labelled via `.replace()`.
14. **Destination walk direction** — `gtfs_loader.py` + `transit_graph.py`: `find_nearest_train_stations` gained a `walk_to_station=False` parameter; destination call site updated; `street_walk_minutes` arg order fixed in `find_routes()` (lines 991–994) and `find_bus_routes()` (line 1127) so the walk is computed station→destination instead of destination→station.

---

### Notable changes (session — 2026-04-11, routing radius fixes + multi-leg bus routing scoped)

Two routing coverage bugs fixed; multi-leg bus routing enhancement scoped and documented.

1. **Train routing: progressive station radius expansion** — `transit_graph.py` `find_routes()`: both origin and destination station searches now use a progressive-expansion loop (0.25 → 0.5 → 0.75 → ... → 2.0 miles, +0.25 per step). Previously a hard 0.5-mile cap caused `dest_stations` to come back empty for addresses like "4201 N Troy Ave" (Francisco Brown Line is ~0.55 miles away), returning no route cards even though Claude still produced an AI summary. The fix uses the tightest radius that yields at least one station, so well-served addresses are unaffected while edge cases now resolve correctly.

2. **Bus routing: progressive exit-stop threshold expansion** — `transit_graph.py` `find_bus_routes()`: the hard 0.5-mile exit-stop cutoff (`if best_exit_dist > 0.5: continue`) replaced with the same progressive-expansion approach (0.25 → 2.0 miles). Restructured into two passes: Pass 1 collects the best exit stop per route+direction using haversine only (cheap); Pass 2 builds Route objects (OSMnx walk calls) only for the candidates that survive the threshold. This avoids paying expensive street-network costs for routes that will be discarded.

3. **Multi-leg bus routing scoped and documented** — Originally added to `FUTURE_ENHANCEMENTS.md` (since deleted; content merged into `FEATURE_IMPLEMENTATION_PLANS.md` as Feature C — 5 chunks). Full scoping required before implementation begins. Distinct from Intermodal Routing (Feature B) — Feature C covers bus+bus transfers only.

4. **Multi-leg train routing gaps documented** — Originally added to `FUTURE_ENHANCEMENTS.md` (since deleted; content merged into `FEATURE_IMPLEMENTATION_PLANS.md`). Clarifies that train-to-train routing with line changes and transfers IS already implemented via NetworkX. Documents two specific gaps: (a) shared-track edge deduplication can mis-label the line on segments where multiple CTA lines share consecutive stations (e.g. Red/Brown between Belmont and Fullerton) — timing is still correct but the route card may show the wrong line name; (b) access/egress to train stations is always pedestrian — bus access to a better-positioned station is never considered, and this gap is addressed by Intermodal Routing (Feature B).

---

### Notable changes (session — 2026-04-13, Feature A — Train Station Exit Guidance)

All 5 chunks of Feature A implemented. Train station exit guidance is now live.

1. **`fetch_station_exits.py` written + `station_exits.json` generated** — One-time script queries the Overpass API for all `railway=subway_entrance` OSM nodes in Chicago's bounding box, matches each entrance to its nearest CTA parent station by haversine (max 0.20 mi), and writes `backend/station_exits.json`. Script produced 367 exits across 130 of 143 parent stations; 9 nodes were too far from any station and skipped. Many labels are `"Entrance (lat, lon)"` placeholders — stations with named labels (e.g. Roosevelt, Logan Square) surfaced correctly.

2. **Exit data loaded at module import** (`transit_graph.py`) — Module-level `_station_exits: dict[str, list[dict]]` populated by `_load_station_exits()` at import time (~5 KB, instant). Logs entry count on startup. Returns `{}` gracefully if file is absent — server still starts. Public API: `get_station_exits(mapid) -> list[dict]`.

3. **`best_exit()` added** (`transit_graph.py`) — Scores all known exits for a station by `street_walk_minutes(exit_lat, exit_lon, dest_lat, dest_lon)` (lru_cache'd — no extra I/O after first call) and returns the minimum-time exit dict with an added `walk_minutes` key. Returns `None` if no exits known.

4. **Exit threaded into walk legs** (`transit_graph.py`, `main.py`) — `WalkLeg` dataclass gains `exit_label: str = ""`. In `_path_to_route()`, the destination walk leg now calls `best_exit(from_node, dest_lat, dest_lon)`: if found, exit `(lat, lon)` replaces the station centroid as the walk origin and `walk_minutes` replaces the pre-computed value, so both walk time and street-level directions start from the correct point. Same pattern applied in `find_bus_routes()` (no-op for bus stop IDs, future-safe). `main.py` serializes `"exit_label": leg.exit_label` in the `/recommend` response.

5. **Exit label displayed on final walk leg** (`App.jsx`, `App.css`) — `WalkLegItem` shows `Exit: <label>` in muted secondary text (`.leg-exit-label`) between the summary line and the Steps toggle, when `leg.exit_label` is present and `leg.to === "Your destination"`. Steps toggle behaviour unchanged.

---

### Notable changes (session — 2026-04-11, bug fix batch 4)

All four remaining 🟢 deferred bugs fixed. No known bugs remain.

**Batch 4 — 🟢 Performance, correctness, and maintainability:**
1. **PWA `globPatterns` pre-cache fix** — `vite.config.js`: `globPatterns` now lists `icon-*.png` and `apple-touch-icon.png` explicitly instead of `**/*.png`, keeping transit photos out of the pre-cache manifest (prevents 20–50 MB service worker installs on older Android WebViews). A `StaleWhileRevalidate` runtime cache entry for `/transit-photos/` added so photos load lazily after install.
2. **Thread-local graph copy** — `transit_graph.py`: added `import threading` and module-level `_thread_local: threading.local`. `find_routes()` now keeps a thread-local copy of `G_base` (keyed by `id(G_base)`) created once per executor thread instead of on every request. Virtual nodes `__ORIGIN__`/`__DEST__` are added before routing and removed in a `finally` block so the thread-local graph stays clean for the next request.
3. **`fuzzy_match_neighborhood()` shared helper** — `gtfs_loader.py`: `_FUZZY_STOP_WORDS` (frozenset) and `fuzzy_match_neighborhood(query)` extracted as a public module-level helper; `resolve_location()` calls it instead of reimplementing the loop. `main.py`: imports `fuzzy_match_neighborhood` from `gtfs_loader`; `_coords_for_location()` step 2 replaced with a call to the shared helper. `SequenceMatcher` import and inline `_STOP_WORDS` dict removed from `main.py`. Threshold (0.95) and stop-word list now have a single source of truth.
4. **Redundant `walk_minutes` recomputation removed** — `transit_graph.py` `find_routes()`: the per-station `street_walk_minutes()` call and `dest_walk[mapid]` overwrite inside the `dest_stations` loop were removed. `dest_walk` is populated once from values already computed by `find_nearest_train_stations(walk_to_station=False)`; those values are used directly as edge weights on station→DEST edges.
5. **Bus routing multi-direction `board_index` fix** — `transit_graph.py` `find_bus_routes()`: `board_index` type changed from `dict[str, tuple]` to `dict[str, list[tuple]]`; population now uses `setdefault(..., []).append(...)` so both direction entries are stored when a stop appears in sequences for both directions of a route. In the arrival loop, all matching direction candidates are tried and the direction whose sequence leads the exit stop closest to the destination wins. `stops = sequences[route_dir_key]` now assigned from the winning candidate after selection.

---

### Notable changes (session — 2026-04-09, Google Maps geocoding)
1. **Google Maps Geocoding API implemented** — `gtfs_loader.py`: `geocode_nominatim()` replaced with `geocode_google()`. Nominatim-specific rate-limit lock/timer removed (not needed for Google Maps). API call uses Chicago bounding box bias + `components=country:US`. Persistent disk cache unchanged.
2. **Monthly geocode rate limiter added** — `_GEOCODE_CALL_LIMIT` defaults to 9,500 calls/month to cap API spend. Counter persisted to `geocode_counter.json`, resets automatically each calendar month. Only actual API hits count — cache hits are free. *(Promoted from temporary scaffolding to a proper env-var config in TD-003, 2026-04-20: set `GEOCODE_MONTHLY_LIMIT` Railway env var to change the limit or set to `0` to disable.)*

---

### Notable changes (session — 2026-04-09, map feature — Phase 5.6 complete)

All 10 chunks of MAP_IMPLEMENTATION_PLAN.md implemented. Full map feature is live.

**Backend (Chunks 1–4):**
1. **GTFS shape lookup** (`transit_graph.py`) — `_build_shape_lookup()` reads `trips.txt` first to collect the set of `shape_id`s actually used per `(route_id, direction_id)`, then streams `shapes.txt` keeping only those (sorted by `shape_pt_sequence`), picks the longest shape per route/direction, builds module-level `_shape_lookup` dict. Called in `warm_up()`. Public API: `get_shape(route_id, direction_id) -> list[list[float]] | None`. (Two-pass order reduces peak memory vs. the earlier "shapes-first" approach.)
2. **Shape clipping** (`transit_graph.py`) — `clip_shape(shape_points, board_lat, board_lon, exit_lat, exit_lon)` finds nearest shape points to each stop by squared Euclidean distance, returns the slice between them. Falls back to straight line if shape is None/empty.
3. **Walk path geometry** (`walking.py`) — `walk_path(origin_lat, origin_lon, dest_lat, dest_lon)` uses `nx.shortest_path()` on the loaded OSMnx graph to return street-network path as `[[lat, lon], ...]`. Same `lru_cache(maxsize=512)` as `walk_minutes()`. Falls back to straight line.
4. **Geometry in API response** (`transit_graph.py`, `main.py`) — `WalkLeg` gains `path_points`, `TransitLeg` gains `shape_points`. Transit edges now store `direction_id`. `_path_to_route()` calls `walk_path()` on every walk leg and `get_shape() + clip_shape()` on every transit leg. `find_bus_routes()` does the same. `/recommend` response now includes `shape`, `path`, `from_coords`, `to_coords` per leg and `origin_coords`, `dest_coords` at the top level.

**Frontend (Chunks 5–10):**
5. **MapLibre + layout** — `maplibre-gl` installed; CSS imported in `main.jsx`; `App.jsx` restructured into `.layout.layout--split` with `.panel-cards` (40%, scrollable) and `.panel-map` (60%, fixed). 800px breakpoint stacks vertically with 300px/350px min-heights.
6. **TransitPhoto** — `PHOTOS` manifest (hardcoded `{src, caption}` array) in `App.jsx`. `TransitPhoto` component picks one photo randomly on mount. Photo shown while loading or when result has no routes. Fades out over 1s when routes arrive (CSS `opacity` transition), then removed from DOM. `key={photoKey}` forces new random photo on each search.
7. **MapView init** — `MapView.jsx` created. MapLibre map initialized once in `useEffect([], [])`. All six interaction handlers disabled by default. "🔓 Unlock map" button (top-left, shown when visible and not yet unlocked) re-enables all handlers on click. Map is always in DOM (`opacity: 0` → `opacity: 1` CSS transition synced with photo fade-out).
8. **Route rendering** — Two-pass rendering in `renderRoute()`: lines first (walk dashed gray, transit solid colored), then markers (board/exit dots, intermediate stop dots sampled from shape, origin blue dot, destination dark dot). All sources/layers prefixed `route-` for reliable clearing on route change. `fitBounds({ padding: 60, animate: false })` after every render.
9. **Route card ↔ map** — `selectedRouteIndex` state in `App` (default 0, reset on new search). `RouteCard` gains `isSelected` + `onSelect` props. Clicking a card selects it (blue ring highlight) and snaps the map to that route instantly. `MapView` receives `routes[selectedRouteIndex]`.
10. **Demo files deleted** — `demo-straight-lines.html`, `demo-gtfs-shapes.html`, `demo-carto-positron.html`, `demo-openfreemap-liberty.html`, `demo-openfreemap-positron.html` removed from repo root.

---

### Notable changes (session — 2026-04-13, Feature E — Walk Leg Street-Level Distance Detail)

Both chunks of Feature E implemented. Walk leg steps now render as prose sentences with block counts instead of arrows + abbreviations + minutes.

1. **`_CHICAGO_BLOCK_METERS` constant and `_DIRECTION_FULL` map added** — `walking.py`: `_CHICAGO_BLOCK_METERS = 80.0` (8 blocks per mile, standard Chicago grid) and `_DIRECTION_FULL` dict (N→"North", NE→"Northeast", etc.) added at module level immediately after `WALKING_SPEED_MPS`.

2. **`blocks` and `direction_full` added to each step dict (Chunk 1)** — `walking.py` `walk_directions()`: after grouping consecutive same-street edges, each step now computes `blocks = max(0.5, round(total_length / 80.0 * 2) / 2)` and looks up `direction_full` via `_DIRECTION_FULL`. Both fields added to the step dict alongside the existing `direction`, `street`, and `minutes` keys. Fallback `except` path also computes `fallback_blocks` from `total_min * 60 * WALKING_SPEED_MPS / 80.0` and includes `"direction_full": ""` in the single fallback step.

3. **Step rendering replaced (Chunk 2)** — `App.jsx`: `DIRECTION_ARROWS` constant removed (was only used in step rendering). `formatBlocks(b)` helper added above `WalkLegItem` — returns `"1 block"` or `"N blocks"`. `WalkLegItem` step `<li>` now renders: `{si === 0 ? "Walk" : "Head"} {direction_full} along {street} for {blocks}`. `?? 1` fallback on `step.blocks` handles stale cached responses. Direction conditional handles empty-string fallback without a trailing space.

4. **Obsolete CSS rules removed (Chunk 2)** — `App.css`: `.leg-step-arrow`, `.leg-step-dir`, and `.leg-step-time` rule blocks removed. `.leg-step`, `.leg-step-text`, and `.leg-step-street` rules retained — the new prose format uses the same layout container.

---

### Notable changes (session — 2026-04-13, Feature C — Multi-Leg Bus Routing)

All 5 chunks of Feature C implemented. Bus+bus transfer routes are now surfaced when no direct single-bus route works well.

1. **Bus stop spatial grid index (Chunk 1)** — `transit_graph.py`: module-level `_bus_stop_grid` (keyed by 0.005°×0.005° lat/lon cell) and `_bus_stop_coords` populated at import time. New `_stops_near(lat, lon, radius_miles=0.25)` helper converts radius to degree offsets, queries bounding-box cells, post-filters by exact haversine. A 0.25-mile radius checks at most 9 cells (~150 stops worst case).

2. **Stop-to-routes index (Chunk 2)** — `transit_graph.py`: module-level `_stop_to_routes: dict[str, list[tuple]]` populated by `_build_stop_to_routes()`, called from `warm_up()` immediately after `get_bus_stop_sequences()`. Enables O(1) lookup of all routes serving a given stop. Stores `(short_name, did, idx_in_seq, arr_min)` per entry.

3. **Transfer candidate algorithm (Chunk 3)** — `transit_graph.py`: new `find_bus_transfer_routes(origin_lat, origin_lon, dest_lat, dest_lon, bus_arrivals, origin_bus_stops, n_routes=3)`. Two-pass design: Pass 1 identifies candidate transfer stops using forward-progress haversine filter + `_stops_near` + `_stop_to_routes`; Pass 2 builds 5-leg `Route` objects (walk + bus A + walk + bus B + walk) via OSMnx only for surviving candidates. Leg-2 wait estimated at 7.5 min (fixed). Routes pruned at 90 min total. Sets `route.transfers = 1`.

4. **Integration into main.py (Chunk 4)** — `main.py`: `find_bus_transfer_routes` imported from `transit_graph`. Called when `find_bus_routes()` returns an empty list and `transit_mode` is Bus or All. Wrapped in `try/except` with `traceback.print_exc()`. Resulting routes merged with train routes as before — no prompt or serialization changes needed.

5. **Frontend verification (Chunk 5)** — `App.jsx`, `MapView.jsx`: confirmed 5-leg route cards render correctly. Transfer walk leg (bus stop name → bus stop name) renders in `WalkLegItem` without changes. Zero-minute same-stop transfer renders without blank items. Map renders two colored bus polylines for the two `TransitLeg`s; `BUS_DIRECTION_COLORS` fallback confirmed non-crashing for unknown direction strings. End-to-end manual test passed for a real Chicago transfer trip.

---

### Notable changes (session — 2026-04-13, Feature F — Street Abbreviation Normalization)

Chunk 1 of Feature F implemented. USPS street suffix abbreviations are now expanded before any location matching, reducing unnecessary Google API calls and producing stable geocode-cache keys.

1. **`import re` added** — `gtfs_loader.py`: `re` module added to imports (was not previously imported).

2. **`_ABBR_MAP`, `_STREET_ABBR_RE`, `_normalize_street_abbr()` added** — `gtfs_loader.py`: module-level `_ABBR_MAP` dict maps 15 USPS suffix abbreviations (blvd, pkwy, expy, terr, ter, hwy, ave, cir, st, dr, ln, ct, rd, pl, sq) to their full forms. `_sorted_abbrs` sorts keys longest-first to prevent shorter patterns shadowing longer ones. `_STREET_ABBR_RE` compiles a single word-boundary-anchored case-insensitive regex that matches each abbreviation with or without a trailing period. `_normalize_street_abbr(query)` applies the regex via a `_replace` closure that strips trailing periods before lookup. Function placed immediately before `resolve_location()`.

3. **`resolve_location()` updated** — `gtfs_loader.py`: normalization applied immediately after `q = query.lower().strip()`. `geocode_google()` call updated to pass `q` (normalized, lowercased) instead of the raw `query` string, so the geocode-cache key is stable regardless of whether the user typed "Ave" or "Avenue".

4. **Directional prefixes intentionally excluded** — N, S, E, W, NW, NE, SW, SE are not expanded. They are used both as abbreviations and as fragments in station names like "North/Clybourn"; Google Maps handles them correctly without expansion.

---

### Notable changes (session — 2026-04-13, Claude Response Caching)

In-memory response caching implemented in `main.py`. Repeat `/recommend` requests for the same normalized route query skip all upstream I/O (CTA API calls, routing engine, Claude call) within a 45-second TTL window.

1. **`import time` added** — `main.py`: `time` module added to stdlib imports for `time.monotonic()`.

2. **`_response_cache`, `_CACHE_TTL_SECONDS`, `_CACHE_MAX_SIZE` added** — `main.py`: module-level `_response_cache: dict[str, tuple[float, dict]] = {}` stores `key → (expires_at, response)`. Constants `_CACHE_TTL_SECONDS = 45` and `_CACHE_MAX_SIZE = 500` placed alongside the dict.

3. **`_cache_key()` helper added** — `main.py`: normalizes the four `RouteRequest` fields (`origin`, `destination`, `transit_mode`, `bus_fullness`) into a `"|"`-delimited string (origin and destination lowercased + stripped). Placed immediately after the cache dict declaration.

4. **Cache check wired into `/recommend`** — `main.py`: cache lookup inserted after API key validation, before `resolve_location` (before any I/O). On a hit with `time.monotonic() < expires_at`, returns the cached response with `"cache_hit": True` merged in. Stale entries are evicted inline on a miss.

5. **Cache write wired into `/recommend`** — `main.py`: response dict captured as a named variable `response` (replacing the previous inline `return {...}`). Stored to `_response_cache[key]` with `expires_at = time.monotonic() + 45`. If the cache exceeds 500 entries, the entry nearest expiry (`min(cache, key=lambda k: cache[k][0])`) is evicted before inserting the new one.

6. **`cache_hit` field wired but UI unchanged** — The field is present on cache-hit responses so the frontend can surface a freshness note in a future pass. The current frontend ignores it.

---

### Notable changes (session — 2026-04-14, Rate Limiting + BYOK)

Rate limiting and Bring Your Own API Key (BYOK) implemented and merged. Both features are **written but turned off by default** — no behaviour change until the corresponding env vars are set.

1. **Rate limiting added to `/recommend`** — `main.py`: `import collections` + `Request` added to FastAPI imports. `_RATE_LIMIT_ENABLED` (default `false`), `_RATE_LIMIT_RPM` (default 10/min per IP), `_RATE_LIMIT_RPH` (default 50/hr per IP) read from env at startup. `_rate_store: dict[str, collections.deque]` holds per-IP timestamp history. `_client_ip(http_request)` extracts real IP from `X-Forwarded-For` (Railway proxy) falling back to `request.client.host`. `_check_rate_limit(ip)` is a sliding-window check: evicts timestamps older than 1 hr, checks hourly cap, counts last-60s entries for per-minute cap, returns `True`/`False`. Called at the very top of `/recommend` before any I/O; raises HTTP 429 on rejection. **To activate: `RATE_LIMIT_ENABLED=true` in Railway env vars before public launch.** Tune with `RATE_LIMIT_RPM` / `RATE_LIMIT_RPH`.

2. **BYOK implemented end-to-end** — `main.py`: `_BYOK_ENABLED` (default `false`) read from env. `anthropic_api_key: str | None = None` added to `RouteRequest` with a `@field_validator` that trims whitespace, converts empty strings to `None`, and rejects values not starting with `"sk-ant-"` (fast HTTP 422 before hitting Anthropic). When `byok_key` is set and `_BYOK_ENABLED` is `true`, a per-request `anthropic.AsyncAnthropic(api_key=byok_key)` is created; otherwise the shared `_claude_client` singleton is used. The shared-key `ANTHROPIC_API_KEY` validation is skipped when a BYOK key is present (field renamed to `byok_key` after extraction). BYOK requests count against per-IP rate limits like all other requests. **To activate: `BYOK_ENABLED=true` in Railway env vars AND `VITE_BYOK_ENABLED=true` in Vercel env vars, then redeploy both.**

3. **BYOK settings panel added to frontend** — `App.jsx`, `App.css`: `BYOK_ENABLED = import.meta.env.VITE_BYOK_ENABLED === "true"` compile-time flag — when `false`, the settings panel is never rendered and `anthropic_api_key` is never sent. `SettingsPanel` component: `type="password"` input pre-filled from `sessionStorage` (`byok_api_key`), inline format validation (`sk-ant-` prefix check), Save / Remove key buttons. Gear icon ⚙ added to `.header-top` filters row (only visible when `BYOK_ENABLED`); tinted blue when a key is stored. Panel mounted above `.main` form. `byokKey` state initialised from `sessionStorage` on mount; `handleSaveByokKey` writes/removes from `sessionStorage` (clears automatically on tab close — safer than `localStorage`). Fetch body spreads `{ anthropic_api_key: byokKey }` only when `BYOK_ENABLED && byokKey`. New CSS section `/* ── BYOK Settings panel */` at end of `App.css` — `.settings-trigger`, `.settings-panel`, `.settings-header`, `.settings-title`, `.settings-close`, `.settings-label`, `.settings-hint`, `.settings-input`, `.settings-error`, `.settings-actions`, `.settings-save`, `.settings-clear`.

4. **`FEATURE_IMPLEMENTATION_PLANS.md` updated** — Rate Limiting and BYOK sections in "Future Enhancements" both updated to `✅ Complete (2026-04-14)` with implementation notes documenting what was built vs. the original scoping plan. `Feature_Prioritization.md` updated: both bolt-on features struck through and marked complete.

---

### Notable changes (session — 2026-04-16, Feature B — Intermodal Routing)

All 6 chunks of Feature B implemented. Train+bus intermodal routes now surfaced automatically.

1. **Bus stop nodes added to unified graph** — `transit_graph.py` `_build_graph()`: ~11,000 bus stop nodes added with `node_type="bus"`, lat, lon, name. Train station nodes given `node_type="train"`. Train transit edges given `mode="train"` and `line_code` attribute.
2. **Bus transit edges added to unified graph** — `transit_graph.py` `_build_graph()`: ~50,000+ directed bus transit edges added from cached stop sequences (`mode="bus"`, `line_code=route_short_name`, `edge_type="transit"`). No second stop_times.txt scan — reuses the already-cached `_bus_seq_cache`.
3. **Train↔bus transfer walk edges** — `transit_graph.py` `_build_graph()`: bidirectional walk edges added between each train station and bus stops within 0.15 miles (street walk ≤ 5 min). Enables Dijkstra to discover intermodal transfers naturally. ~3,000 `street_walk_minutes()` calls on cold start (lru_cached after first run).
4. **`_resolve_node()` helper** — `transit_graph.py`: new module-level helper resolves (name, lat, lon) for any node type — checks `stations` dict first (train), falls back to graph node attributes (bus).
5. **`_path_to_route()` updated** — `transit_graph.py`: all node metadata lookups use `_resolve_node()`; new `edge_type == "walk"` handler added for mid-path train↔bus transfers (renders a `WalkLeg` with named endpoints); bus `TransitLeg` assembly uses `edge.get("line_code")`; same-station detection comment updated to note bus/train ID ranges never collide.
6. **`find_routes()` bus virtual edges** — `transit_graph.py`: `ORIGIN→bus_stop` and `bus_stop→DEST` virtual walk edges added for nearby bus stops; `find_nearest_bus_stops` imported.
7. **`warm_up()` graph size log** — `transit_graph.py`: logs `Graph size: N nodes, M edges` after `_build_graph()` completes.
8. **`main.py` updates** — `find_routes()` called with `n_routes=5`; `_route_fingerprint()` deduplication added after merge-sort to prevent unified-graph bus-only routes duplicating `find_bus_routes()` results.

---

### Notable changes (session — 2026-04-16, double stop_times stream fix + bus wait correctness)
1. **Unified `stop_times.txt` stream** — `backend/transit_graph.py`: `_stream_stop_sequences` replaced by `_stream_all_stop_sequences`, which processes train and bus trips in a single pass. `_bus_seq_cache` module-level variable added; `_build_graph()` populates it; `get_bus_stop_sequences()` returns it immediately on the fast path. `@lru_cache` removed from `get_bus_stop_sequences`. Saves ~7–10 s on cold start by eliminating the second 5.8M-row file scan.
2. **Bus wait normalisation** — `backend/main.py`: Added `_rank_bus_routes()` after `_rank_routes()`. Bus routes from `find_bus_routes()` / `find_bus_transfer_routes()` previously bypassed `_rank_routes()` and merged raw tuples with bare `int` wait values. `_rank_bus_routes()` re-expresses `wait` as `int | None` to match `_rank_routes()` output: `0` = Due, `N` = N min away, `None` = no data (defensive). Called as `bus_ranked = _rank_bus_routes(bus_ranked)` between the bus routing block and the train+bus merge. `_format_routes()` already handles all three cases correctly; no other files changed.

### Notable changes (session — 2026-04-15, 22 Bug Fixes + production deployment fixes)

A comprehensive low-severity bug audit produced 22 fixes across backend and frontend. Additionally, two production environment issues were resolved during initial deployment testing.

**Production deployment fixes:**
1. **`/recommend` returned 404 on production** — `VITE_BACKEND_URL` was missing the `https://` prefix in the Vercel dashboard. Updated to `https://cta-transit-pwa-prod-production.up.railway.app` and redeployed. Vite bakes the URL into the bundle at build time; a relative URL was being interpreted as a same-origin path.
2. **Preview deployment URLs returned 401 on `manifest.webmanifest`** — Vercel Deployment Protection settings adjusted so PWA assets are accessible without authentication on preview URLs. PWA install prompts now work on preview deployments.

**Backend bug fixes (`main.py`, `cta_client.py`, `gtfs_loader.py`, `transit_graph.py`, `walking.py`):**
1. `_save_geocode_cache` — replaced write-through with a dirty-flag + background-flush (30s daemon thread + atexit handler). Expensive atomic-rename write now happens at most once per 30s. **Further optimized (OPT-003, resolved 2026-04-18):** the 30s flush now appends only new entries as JSONL to `geocode_cache.journal` (O(delta) instead of O(cache size)). A full snapshot rewrite is forced only every 3600s or once 500 journal entries accumulate; `_load_geocode_cache` replays the journal over the snapshot at startup.
2. `_fetch_bus_chunk` — now returns a sentinel `[{"_error": True, "exc": str, "mode": "bus"}]` on exception instead of silently returning `[]`. Train errors use the same sentinel shape with `"mode": "train"` (TD-007). `get_bus_arrivals` and `get_train_arrivals` both return `(arrivals, n_errors)` tuples.
3. `_rank_routes` — removed dead `dest_lat`/`dest_lon` parameters from signature and call site.
4. `_response_cache` — changed from `dict` to `collections.OrderedDict`; eviction now uses `popitem(last=False)` (O(1)) instead of `min()` over all entries.
5. `_rate_store` — empty deques now deleted after eviction to prevent unbounded growth.
6. BYOK cache collision — `_cache_key()` now appends `"byok"` suffix when a BYOK key is present; BYOK and shared-quota requests use separate cache pools.
7. `prdctdn.isdigit()` — fixed `None` crash: `prd.get("prdctdn") or ""` instead of `prd.get("prdctdn", "")`.
8. `find_nearest_train_stations` / `find_nearest_bus_stops` — replaced full-catalog Haversine scan with a grid/bucket spatial index (`_spatial_index`, `_candidates_within` in `gtfs_loader.py`). ~1-mile lat/lon cells, bounding-box prefilter, Haversine only on candidates inside the box. Built lazily per stop-kind, cached for process lifetime. Bit-exact with prior behavior; measured ~300× faster at 0.25-mi bus lookup, ~44× at 1.0-mi (was ~20k trig calls per `/recommend`). (OPT-001, resolved 2026-04-18.)
8a. `_rank_routes` terminal-name memo — added a per-request `terminal_coords` dict around the existing `@lru_cache`d `get_station_by_name` call in the bearing-test loop, so repeated terminal names ("Howard", "95th/Dan Ryan") across the 5 ranked routes skip the cache's hash+lock dispatch. Behavior preserved; low impact (function was already cached). (OPT-002, resolved 2026-04-18.)
8b. `_response_cache` hit/miss hash count — cache read now evicts stale entries via `pop(key, None)` nested under the `if cached:` branch; cache write drops the `if key in _response_cache: del` membership test and uses `_response_cache[key] = ...; move_to_end(key)` to produce the same LRU order in one fewer hash on the existing-key path. Eviction + TTL semantics unchanged. (OPT-005, resolved 2026-04-18.)
9. `_save_geocode_counter` — added atomic rename pattern (write to `.tmp` then `replace()`); crash-safe.
10. `_normalize_street_abbr` — added `(?=\s*(?:,|$))` lookahead to prevent false matches inside saint names (e.g. "St. Michael's").
11. `fuzzy_match_neighborhood` — added `@lru_cache(maxsize=1024)`; repeated queries now return in O(1). Cold queries further optimized via a precomputed word→keys inverted index (multi-word queries scan only keys sharing ≥1 meaningful word instead of all ~240), `SequenceMatcher` reuse with `query` set as `seq2` to leverage Python's `__chain_b` cache, a `quick_ratio()` upper-bound prefilter before the full `ratio()`, and a 0.99 early-exit. Match threshold (≥0.95) and semantics unchanged. (OPT-006, resolved 2026-04-18.)
12. `min(G[u][v].values(), ...)` — changed `d.get("length", 0)` to `d.get("length", float("inf"))` in both `walk_directions` and `walk_path`; zero-length edges no longer win the `min()`.
13. `walk_directions` fallback — fallback step now always uses `"long"` block type and `_LONG_BLOCK_METERS`; old comparison used total trip length against a per-edge threshold.
14. `lru_cache` on mutable-return functions — added inline comments to `walk_minutes`, `walk_directions`, `walk_path` warning callers not to mutate cached return values.
15. `get_station_by_name` — added `@lru_cache(maxsize=512)`.
16. Bus shape lookup — `_build_shape_lookup` now always writes both `(route_id, direction_id)` and `(short_name, direction_id)` keys unconditionally.
17. Pre-allocating empty lists — both `_stream_stop_sequences` and `get_bus_stop_sequences` now use `defaultdict(list)` populated only on match.
18. Transit edges — removed dead `all_routes=candidates` from `G.add_edge(...)`.

**Frontend bug fixes (`App.jsx`, `MapView.jsx`):**
19. BYOK API key — changed from `localStorage` to `sessionStorage`; key now clears automatically on tab close, reducing XSS exfiltration window.
20. `busFullness` dead state — removed `busFullness` state variable and `bus_fullness` from request body.
21. `RouteCard` expanded state — added `searchIdRef` counter; cards are now keyed `${searchId}-${i}` so React unmounts all cards on each new search, resetting `expanded` to `isFirst`.
22. `TransitPhoto` onError — added `failed` state; on image load error the component returns `null`, hiding both broken image and caption.
23. `clearRouteLayers` — now uses explicit `routeLayerIds`/`routeSourceIds` refs tracked by `renderRoute`; removal no longer calls `getStyle()` and works even when the style is reloading. *(Counted as one fix — part of the 22.)*

---

### Notable changes (session — 2026-04-20, technical debt payoff — TD-010 through TD-014)

All five remaining technical debt items resolved. No open technical debt remains.

1. **`SpatialGrid` class extracted to `utils.py` (TD-010)** — Generic cell-based spatial index. Stores `(lat, lon, value)` triples, provides `add()` and `query(lat, lon, radius_miles) → [(dist, value)]` with bounding-box prefilter + Haversine postfilter. Replaces two independent implementations: `gtfs_loader.py`'s `_spatial_key` + `_spatial_index` dict + 40-line `_candidates_within` (now a one-liner); `transit_graph.py`'s 16-line `_stops_near` with hard-coded `0.005°` cell logic (now also a one-liner). `_bus_stop_coords` retained in `transit_graph.py` for direct stop-id coordinate lookups.

2. **Magic numbers named and moved to module level (TD-011)** — `main.py`: `(0.001 ** 2)` named `_SAME_LOCATION_THRESHOLD_DEG2` with `# degrees²` annotation. `transit_graph.py`: seven function-local constants moved to module level in two named sections ("Intermodal walk-edge tuning constants" and "Bus-to-bus transfer candidate scoring"). Score factor `26.0` named `_TRANSFER_SCORE_WALK_FACTOR` with derivation comment.

3. **`lru_cache` mutable-list latent bug fixed (TD-012)** — `walk_directions` and `walk_path` in `walking.py` renamed to private `_walk_directions_impl` / `_walk_path_impl` (still `@lru_cache`); these now return immutable tuples. Public wrappers `walk_directions` / `walk_path` (not cached) return a fresh list on every call (`list(impl(...))` / `[list(pt) for pt in impl(...)]`). The cache now stores immutable data; callers may freely mutate the returned lists. No call sites changed.

4. **Module-level globals lifecycle documented (TD-013)** — Added "Module-level state — initialization contract" comment block to `transit_graph.py` enumerating all six module globals, their single initializer, and their lifecycle phase. No behavior change.

5. **Street-graph bounding-box expansion TODO replaced with actionable checklist (TD-014)** — `utils.py`: bare TODO comment replaced with a four-step expansion guide documenting current coverage bounds, target expansion coordinates, and the Railway memory check required before expanding.

---

## Geocoding Strategy

Location resolution uses a three-step fallback (implemented in `gtfs_loader.py`):

1. **Exact match** against `NEIGHBORHOOD_COORDS` dict (instant, no network)
2. **Fuzzy match** against `NEIGHBORHOOD_COORDS` (instant, no network)
3. **Google Maps Geocoding API** — ~100ms, biased to Chicago bounding box (`bounds=41.64,-87.94|42.02,-87.52`) with `components=country:US`

**Implementation notes:**
- `geocode_google(query)` in `gtfs_loader.py` — signature `(query: str) -> tuple[float, float] | None`
- Results persisted to `geocode_cache.json` (disk cache survives restarts; cache hits are free)
- API call counter persisted to `geocode_counter.json` — resets each calendar month
- Free tier: ~40,000 calls/month. A production call cap defaults to 9,500/month (configurable via `GEOCODE_MONTHLY_LIMIT` env var; set to `0` to disable).
- Requires `GOOGLE_MAPS_API_KEY` in `backend/.env` AND in Railway environment variables ✅

---

## Current File Structure

```
CTA-Transit-PWA/
├── .gitignore
├── cta_app_handoff_prompt.md           ← This file
├── HUMAN_TODO.md                       ← Tasks only a human can do (accounts, keys, deploy steps, UI checks)
├── BUGS_TO_BE_FIXED.md                 ← Open bugs only (0 🔴 high, 0 🟡 medium, 1 🟢 low); delete entry here and log fix in BUGS_FIXED_HISTORY.md when resolved
├── BUGS_FIXED_HISTORY.md               ← Log of all resolved bugs; add entry here when a bug from BUGS_TO_BE_FIXED.md is fixed
├── FEATURE_IMPLEMENTATION_PLANS.md     ← Chunked build plans + post-launch ideas: Feature A ✅ (Train Station Exit Guidance, 5 chunks), Feature B ✅ (Intermodal Routing, 6 chunks), Feature C ✅ (Multi-Leg Bus Routing, 5 chunks), Feature D (Live Arrivals at Transfer Stop, 4 chunks), Feature E ✅ (Walk Leg Block-Count Distance, 2 chunks), Feature F ✅ (Street Abbreviation Normalization, 1 chunk), Feature G ✅ (Long/Short Block Classification, 2 chunks), Feature H ✅ (Deduplicate Same-Line Station Candidates, bolt-on, 3 chunks), Feature I ✅ (CTA Alerts Integration, bolt-on, 3 chunks), Feature J ✅ (Deprecate find_bus_routes() in Favor of Unified Graph, bolt-on, 3 chunks)
├── Feature_Prioritization.md           ← Bolt-On vs Structural classification + status for all planned/pending features: Feature D (Live Arrivals at Transfer Stop, structural — Feature C dependency satisfied), Multi-Leg Train Routing Gap 1 (shared-track label accuracy, structural)
├── FEATURE_B_intermodal_routing_handoff.md ← ✅ Implemented 2026-04-16 — historical reference only; see FEATURE_IMPLEMENTATION_PLANS.md for summary
├── MAP_IMPLEMENTATION_PLAN.md          ← Map feature design + 10-chunk plan (all complete — Phase 5.6 done)
├── WEATHER&CROWDEDNESS_FEATURE_HANDOFF.md ← Weather API integration + crowdedness estimation design (post-Phase-6)
├── PYTHON_TERMINAL_TEST_STARTUP_INSTRUCTIONS.md  ← How to run backend + frontend locally
├── backend/
│   ├── .env                            ← API keys (never commit)
│   ├── main.py                         ← FastAPI server, /recommend + /health; direction-aware arrival lookup;
│   │                                      _rank_routes (dot-product bearing test) + _rank_bus_routes();
│   │                                      bus routing calls find_bus_transfer_routes() unconditionally (Feature J);
│   │                                      OrderedDict response cache (45s TTL, 500 entries);
│   │                                      _store_lock (asyncio.Lock) protects both _rate_store and _response_cache against concurrent-request races;
│   │                                      rate limiting (off by default — RATE_LIMIT_ENABLED=true to activate);
│   │                                      BYOK (off by default — BYOK_ENABLED=true + VITE_BYOK_ENABLED=true to activate);
│   │                                      recommend() decomposed into focused helpers (TD-002): _validate_api_keys(),
│   │                                      _resolve_locations(), _fetch_arrivals(), _run_routing(),
│   │                                      _fetch_transfer_arrivals(), _call_claude(), _format_response()
│   ├── utils.py                        ← Shared backend utilities: haversine_miles(lat1, lon1, lat2, lon2) → float;
│   │                                      SpatialGrid class (generic cell-based spatial index — TD-010; shared by gtfs_loader + transit_graph);
│   │                                      CHICAGO_BBOX_{GOOGLE,OVERPASS,OSMNX} + STREET_GRAPH_BBOX_OSMNX constants (TD-006);
│   │                                      _MILES_PER_DEG_LAT / _MILES_PER_DEG_LON geographic constants
│   ├── gtfs_loader.py                  ← 3-step location resolver + _normalize_street_abbr() (USPS suffix expansion) +
│   │                                      fuzzy_match_neighborhood() shared helper +
│   │                                      Google Maps geocoding + persistent cache + monthly call counter;
│   │                                      spatial index uses SpatialGrid (TD-010 — _spatial_index returns SpatialGrid, _candidates_within is a one-liner)
│   ├── transit_graph.py                ← Unified NetworkX graph (Feature B: ~11k bus nodes, ~50k bus transit edges,
│   │                                      ~3k train↔bus walk edges); thread-local G_base copy per executor thread;
│   │                                      find_routes() (ORIGIN→bus_stop virtual edges; n_routes=3 default, called with 5;
│   │                                      Feature H: _dedup_stations_by_line() applied to origin+dest candidates);
│   │                                      find_bus_transfer_routes() (Feature J removed legacy find_bus_routes()); _resolve_node();
│   │                                      _path_to_route() handles edge_type="walk" for intermodal transfers;
│   │                                      _bus_stop_grid (SpatialGrid — TD-010) + _stops_near() (Feature C); _build_stop_to_routes() (Feature C);
│   │                                      get_bus_stop_sequences(); _build_shape_lookup(); get_shape(); clip_shape();
│   │                                      _station_exits + best_exit() (Feature A); WalkLeg.path_points; TransitLeg.shape_points;
│   │                                      module-level tuning constants (TD-011): intermodal walk-edge constants + bus transfer scoring constants;
│   │                                      module-level initialization contract comment for all globals (TD-013)
│   ├── walking.py                      ← igraph walking (OPT-008): walk_minutes() (time) + walk_path() (street geometry, fresh list each call — TD-012) +
│   │                                      walk_directions() (step-by-step; each step dict includes blocks + direction_full; fresh list each call — TD-012);
│   │                                      lru_cache on private _walk_path_impl/_walk_directions_impl (return immutable tuples — TD-012);
│   │                                      shared _get_shortest_path() + _get_nearest_node() lru_cache helpers (OPT-009) avoid redundant Dijkstra + nearest-node calls across all three functions;
│   │                                      loads street_graph_igraph.pkl (pre-built igraph artifact, OPT-008c) first; falls back to ig.Graph.Read_GraphML on street_graph.graphml; falls back to Haversine;
│   │                                      _coord_kdtree (scipy cKDTree) replaces ox.nearest_nodes; _vertex_lats/_vertex_lons NumPy arrays for O(1) coord lookup; no osmnx/networkx at runtime
│   ├── cta_client.py                   ← Async Train Tracker + Bus Tracker API clients; batched bus stop fetching; psgld normalization; get_alerts() + _TRAIN_LINE_TO_ALERT_ID + _fetch_alerts_for_route() (Feature I)
│   ├── fetch_gtfs.py                   ← Script to download/update CTA GTFS data
│   ├── fetch_street_graph.py           ← Script to download/cache OSMnx street graph; applies ox.consolidate_intersections(tolerance=10, rebuild_graph=True, dead_ends=False) after download (OPT-007); also emits street_graph_igraph.pkl (igraph pickle with geometry pre-parsed as coord lists — OPT-008c)
│   ├── active_routes.py                ← Standalone diagnostic script: prints all active CTA bus routes
│   │                                      and train lines right now. Bus routes via Bus Tracker /getroutes
│   │                                      (only returns in-service routes); train lines via Train Tracker
│   │                                      /ttpositions (active = has live train positions). Enriches bus
│   │                                      output with GTFS long names + hex colors. Run: python active_routes.py
│   ├── railway.toml                    ← Railway deployment config (builder = "dockerfile", points to backend/Dockerfile)
│   ├── Dockerfile                      ← Build recipe used by Railway (apt deps, pip install, COPY); curl-LFS step preserved as comments — see Feature K
│   ├── requirements.txt
│   ├── geocode_cache.json              ← Persistent geocoding results cache snapshot (gitignored, built at runtime)
│   ├── geocode_cache.journal           ← Append-only JSONL delta between snapshots (gitignored, compacted hourly or every 500 entries)
│   ├── geocode_counter.json            ← Monthly Google Maps API call counter (gitignored; resets each calendar month)
│   ├── gtfs_data/                      ← Downloaded GTFS files (gitignored, re-downloaded on deploy via fetch_gtfs.py)
│   ├── street_graph.graphml            ← Pre-built OSMnx street graph committed via Git LFS (bbox: Howard–20th St); present locally, NOT present in Railway image — runtime falls back to Haversine. See Feature K to restore.
│   └── street_graph_igraph.pkl         ← Pre-built igraph artifact (gitignored); produced by fetch_street_graph.py (OPT-008c); loaded by walking.py in preference to the graphml for faster cold start and lower RAM.
└── frontend/
    ├── index.html                      ← PWA meta tags, theme color, apple-touch-icon
    ├── package.json                    ← includes maplibre-gl dependency
    ├── vite.config.js                  ← VitePWA plugin config, manifest, service worker
    ├── .env.local                      ← Local dev env vars (gitignored)
    ├── .env.production                 ← Production env vars — update VITE_BACKEND_URL before deploy
    ├── src/
    │   ├── main.jsx                    ← imports maplibre-gl/dist/maplibre-gl.css
    │   ├── index.css
    │   ├── App.jsx                     ← split layout (panel-cards 40% / panel-map 60%); TransitPhoto; MapView wired;
    │   │                                  selectedRouteIndex state; RouteCard selection; photo fade lifecycle
    │   ├── App.css                     ← layout--split, panel-cards, panel-map, transit-photo, map-view styles;
    │   │                                  800px mobile breakpoint (stacked, 300px/350px min-heights)
    │   ├── constants.js                ← LINE_COLORS, BUS_DIRECTION_COLORS — single source of truth; imported by
    │   │                                  App.jsx and MapView.jsx (OPT-015)
    │   └── MapView.jsx                 ← MapLibre GL JS map; locked by default; unlock button; route rendering:
    │                                      walk dashes, transit polylines, board/exit/origin/dest markers,
    │                                      intermediate stop dots; fitBounds on route change (animate: false)
    └── public/
        ├── icon-192.png
        ├── icon-512.png
        ├── apple-touch-icon.png
        └── transit-photos/             ← PENDING: place ≥10 transit photos here; update PHOTOS array in App.jsx
                                           See HUMAN_TODO.md for sourcing guidance
```

## Phase 6 Deployment — Step-by-Step

### Backend → Railway

**Status as of 2026-04-14:** All steps complete. ✓ Live.

**Full steps:**
1. ~~Create account at railway.app — "Sign in with GitHub"~~ ✓ Done
2. ~~New Project → create production and staging environments~~ ✓ Done
3. ~~In the staging service, go to **Settings → Source** and set the **Root Directory** to `backend`~~ ✓ Done (fixed Railpack error)
4. ~~Railway will detect `railway.toml` automatically once root directory is set~~ ✓ Done
5. ~~Add environment variables in the Railway dashboard (Settings → Variables):~~ ✓ Done
   - ~~`CTA_TRAIN_API_KEY`~~ ✓
   - ~~`CTA_BUS_API_KEY`~~ ✓
   - ~~`ANTHROPIC_API_KEY`~~ ✓
   - ~~`GOOGLE_MAPS_API_KEY`~~ ✓
   - ~~`ALLOWED_ORIGINS`~~ ✓
6. ~~Deploy — first deploy takes ~3–5 min (downloads GTFS; street graph is pre-committed via Git LFS and is pulled by Railway automatically). Note: GTFS data is re-downloaded on every deploy via `fetch_gtfs.py` (Railway's filesystem is ephemeral). The street graph is NOT re-downloaded — it lives in the repo via Git LFS (bbox narrowed to Howard–20th St).~~ ✓ Done
7. ~~Copy the Railway public URL~~ ✓ Done

### Frontend → Vercel
1. ~~Create account at vercel.com — "Continue with GitHub"~~ ✓ Done
2. ~~"Add New Project" → import this repo~~ ✓ Done
3. ~~Set **root directory** to `frontend`~~ ✓ Done
4. ~~Add environment variable:~~
   - ~~`VITE_BACKEND_URL` = your Railway URL from step 7 above~~ ✓ Done
5. ~~Deploy — takes ~1 min~~ ✓ Done
6. ~~Copy the Vercel URL and paste it into Railway's `ALLOWED_ORIGINS` variable~~ ✓ Done
7. ~~Redeploy the Railway backend (so CORS picks up the new origin)~~ ✓ Done

### After both are live
- ~~Update `frontend/.env.production` → replace the `your-backend.railway.app` placeholder with the real Railway URL and commit~~ ✓ Done
- Test end-to-end on the live URLs
- Optional: add a custom domain in Vercel dashboard (Settings → Domains)

---

## Phase 6.5 — Weather & Crowdedness Context

**Status: ⬜ Not started** — gated on Phase 6 deployment being live and stable.

Post-deployment enrichment phase. Adds two new live context streams (weather, crowdedness) to the `/recommend` pipeline and wires them into the Claude prompt + route ranking. All three features are documented in full chunk-by-chunk detail in [`FEATURE_IMPLEMENTATION_PLANS.md`](FEATURE_IMPLEMENTATION_PLANS.md) — the summary below is for phase-level orientation only.

**Why this is its own phase:** These features are substantial enough (new backend modules, new external API integrations, new scoring logic) that they should not be mixed into Phase 6 housekeeping. They also have pending scoping decisions (API provider, holiday source, direction mapping, etc.) that must be resolved before implementation — they are not turn-the-key tasks.

### Features in this phase

1. **Feature Weather — Live Weather Integration** (Bolt-On, 3 chunks)
   - New module: `backend/weather_service.py`. `WeatherContext` (current + forecast + alerts) fetched per-request and injected into `build_prompt()`.
   - Pending decisions: weather API provider (NWS / OpenWeatherMap / Open-Meteo / Tomorrow.io), fallback provider yes/no, NWS contact email, visibility/humidity scope, cache library.

2. **Feature Crowdedness — CTA Vehicle Crowdedness Estimation** (Bolt-On, 3 chunks)
   - New module: `backend/crowdedness.py`. `TimePeriod` classification + heuristic `CrowdednessEstimate` per transit leg. Automatically prefers live `psgld` from Bus Tracker when non-empty (currently returning `""` since 2026-04-09).
   - Pending decisions: holiday source (static set vs `holidays` lib), `rtdir` → inbound/outbound mapping strategy, high-traffic stop seeding, base-score calibration, prompt-only vs prompt+UI surfacing.

3. **Feature Weather Scoring — Weather-Adjusted Route Ranking** (Structural, depends on the two above, 3 chunks)
   - New module: `backend/route_scoring.py`. `adjust_weights_for_weather()` shifts scoring priorities based on live weather (heavy precipitation, dangerous cold, high gusts).
   - Pending decisions: prompt-only hint vs numeric re-rank, default weight values, threshold deltas, module location.

### Execution order
- Feature Weather and Feature Crowdedness can proceed in parallel (no dependencies).
- Feature Weather Scoring requires both to be complete before starting.

### Entry criteria
- Phase 6 deployment live on Railway + Vercel, end-to-end test passing.
- Rate limiting activated before public launch if not already (`RATE_LIMIT_ENABLED=true` in Railway env vars) — cost-sensitivity increases once weather fetches add request-time latency and any downstream API.
- All pending scoping decisions for the specific feature resolved. Each feature's "Scoping decisions — pending" block in `FEATURE_IMPLEMENTATION_PLANS.md` is a hard prerequisite — do not begin Chunk 1 before resolving them.

### Exit criteria
- All three features' chunks complete, moved from `FEATURE_IMPLEMENTATION_PLANS.md` into `FEATURES_IMPLEMENTED_HISTORY.md`.
- Live `/recommend` response includes weather context in the Claude recommendation text on a test trip.
- Per-route `[est. crowdedness: ...]` annotation visible in the prompt (verified via a debug log or local test).
- No regression in `max_tokens=400` budget — Claude still responds in 3–4 sentences.

---

## Where to Resume

**Phase 6 deployment is complete.** The app is live on Railway (backend) and Vercel (frontend). Next steps:
1. Source ≥10 transit photos for the map loading panel (see HUMAN_TODO.md)
2. Run remaining UI checks: confirm 40/60 panel ratio on desktop, 300px/350px min-heights on mobile
3. (Optional) Add a custom domain in Vercel dashboard → Settings → Domains
4. **Phase 6.5: Weather & Crowdedness Context** — resolve pending scoping decisions for Features Weather, Crowdedness, and Weather Scoring in `FEATURE_IMPLEMENTATION_PLANS.md`, then implement. Gated on live app being stable.
5. Phase 7: Monetization (AdSense) — apply after confirming live app is stable

**Bug status:** 0 🔴 high + 0 🟡 medium + 1 🟢 low bugs open — see `BUGS_TO_BE_FIXED.md`. Full history of resolved bugs in `BUGS_FIXED_HISTORY.md`.

**Most recently completed:** Feature D — Live Arrivals at Transfer Stop (2026-04-18). `transfer_wait_minutes: int | None = None` added to `TransitLeg` dataclass. `_pick_wait()` extracted from `_rank_routes()` as a shared bearing-test helper. `_extract_transfer_stops()`, `_build_bus_transfer_lookup()`, `_format_transfer_arrivals()`, and `async def _empty()` added to `main.py`. Transfer arrivals fetched concurrently after routing finalization; legs annotated in-place; `"transfer_wait_minutes"` added to response serialization; "Live arrivals at transfer stop(s)" section added to Claude prompt. Frontend: `RouteLegs` detects transfer legs and renders `⏱ N min wait` / `⏱ Due` badge styled via `.transfer-wait-note` CSS. See completed entry in `FEATURES_IMPLEMENTED_HISTORY.md`.

---

### Notable changes (session — 2026-04-20, efficiency improvement OPT-010)

Pre-computed entrance and station trig in `build_exits` (`fetch_station_exits.py`).

1. **Station trig pre-computed at load time (OPT-010a)** — `load_parent_stations()` now stores `rlat`, `rlon`, and `cos_lat` alongside each station's `lat`/`lon`. Each of the ~150 stations pays `radians` + `cos` once instead of once per entrance.
2. **Entrance trig pre-computed before inner loop (OPT-010b)** — In `build_exits`, `math.radians(lat)`, `math.radians(lon)`, and `math.cos(rlat1)` are computed once per entrance node, before the inner `for mapid, info in stations.items()` loop. Previously these were recomputed inside `haversine_miles()` on every iteration.
3. **Local `_haversine_precomputed` helper** — replaces the `haversine_miles` import with a fast variant that accepts pre-converted radians and `cos(lat)` directly, skipping all `math.radians`/`math.cos` overhead in the inner loop. The shared `utils.haversine_miles` is unchanged and still used by `SpatialGrid` and other callers. `import math` added to file imports.

Eliminates ~450k redundant trig operations across a full dataset run (~500 entrances × ~150 stations × 3 operations saved each way).

---

### Notable changes (session — 2026-04-18, efficiency improvements OPT-012/013/014/018)

Four low-overhead efficiency improvements implemented across `gtfs_loader.py` and `MapView.jsx`.

1. **Persistent HTTP session for geocoding (OPT-012)** — `backend/gtfs_loader.py`: added module-level `_http_session = requests.Session()`. `geocode_google()` now calls `_http_session.get(...)` instead of `requests.get(...)`, reusing the keep-alive TCP/SSL connection across calls and eliminating per-call connection setup overhead.

2. **`heapq.nsmallest` replaces full sort in nearest-stop finders (OPT-013)** — `backend/gtfs_loader.py`: `find_nearest_train_stations()` and `find_nearest_bus_stops()` now use `heapq.nsmallest(max_results, hits, key=...)` instead of `hits.sort(...) + hits[:max_results]`. Avoids sorting discarded candidates (O(n log k) vs O(n log n)). `import heapq` added to module imports.

3. **Original query string preserved as `matched_name` (OPT-014)** — `backend/gtfs_loader.py` `resolve_location()`: `original_query = query.strip()` captured before lowercasing/normalization. Both the exact-match branch and the geocoding branch now return `original_query` as `matched_name` instead of the normalized `q`, preserving user capitalization (e.g. "Wrigley Field" not "wrigley field"). Internal cache lookups continue using the normalized `q`.

4. **`legColor(leg)` computed once per transit leg in `renderRoute` (OPT-018)** — `frontend/src/MapView.jsx`: `const legColors = legs.map(...)` precomputed before the Pass 1 loop. Pass 1 and Pass 2 both read `legColors[i]` instead of calling `legColor(leg)` twice per leg. Two object-lookup chains per transit leg per render eliminated.

---

### Notable changes (session — 2026-04-18, Feature D — Live Arrivals at Transfer Stop)

All 4 chunks of Feature D implemented. Transfer stops now show live arrival data in the route card and inform Claude's reasoning.

1. **`transfer_wait_minutes` field added to `TransitLeg`** — `transit_graph.py`: new `transfer_wait_minutes: int | None = None` field on the `TransitLeg` dataclass. Defaults to `None` (no data) for legs that are not transfer boarding legs or have no live coverage.

2. **`_pick_wait()` helper extracted** — `main.py`: the dot-product bearing-test logic that previously lived inline in `_rank_routes()` is now a standalone `_pick_wait(dest_map, from_mapid, to_mapid) -> int | None` helper. Both `_rank_routes()` (first-leg wait) and the new transfer annotation loop (transfer-leg wait) call it. Eliminates the only instance of duplicated direction-selection logic.

3. **Transfer stop extraction and concurrent fetch** — `main.py`: `async def _empty()` no-op coroutine; `_extract_transfer_stops(ranked_routes)` scans all routes for transfer `TransitLeg`s (legs with an earlier transit leg in the same route), deduplicates across routes, returns `(train_station_dicts, bus_stop_id_strings)`. Called after ranking; results fed to `asyncio.gather(get_train_arrivals(...), get_bus_arrivals(...))` for ~300ms concurrent round-trip.

4. **Transfer legs annotated in-place** — `main.py`: `_build_bus_transfer_lookup(arrivals) -> dict[(route, stop_id), int]` for bus transfer stops. After fetching, loops over all ranked routes and annotates each transfer `TransitLeg.transfer_wait_minutes` — train via `_build_arrival_lookup` + `_pick_wait`; bus via `_build_bus_transfer_lookup`. `"transfer_wait_minutes"` added to transit leg serialization in `/recommend` response.

5. **Claude prompt extended** — `main.py`: `_format_transfer_arrivals(arrivals)` groups by stop name, shows up to 3 arrivals per stop (`"{line/route} → {dest}: N min"`). `build_prompt()` gained `transfer_arrivals: list[dict] | None = None`; injects a "Live arrivals at transfer stop(s):" section when non-empty. Omitted entirely for non-transfer routes.

6. **Frontend transfer wait badge** — `App.jsx`: `RouteLegs` detects transfer boarding legs via a `seenTransit` boolean declared before the `.map()` call, set to `true` when the first transit leg is encountered (O(n) pass instead of the previous O(n²) `legs.slice(0, i).some(...)` per leg). Renders `<span className="transfer-wait-note">⏱ Due</span>` or `⏱ N min wait` as the first child of the transit leg `<li>`. `App.css`: `.transfer-wait-note { display: block; color: #888; font-size: 0.75rem }`.

---

### Notable changes (session — 2026-04-20, TD-002 — `recommend()` decomposed into focused helpers)

Resolved 🔴 TD-002. The `/recommend` handler was 325 lines doing 10+ distinct tasks in a single function body.

1. **Seven focused helpers extracted to `backend/main.py`** — A new "recommend() sub-steps" section defines:
   - `_validate_api_keys(request, byok_key)` — raises HTTP 500 if any required key is absent
   - `_resolve_locations(loop, request)` — resolves origin/destination to stations + coords; same-location guard
   - `_fetch_arrivals(request, origin_stations, origin_bus_stops)` — fetches train + bus arrivals; applies fullness filter
   - `_run_routing(request, origin_coords, dest_coords, ...)` — unified graph routing + bus-transfer routing; merges and sorts
   - `_fetch_transfer_arrivals(ranked_routes)` — Feature D transfer-stop arrivals; annotates legs in-place
   - `_call_claude(claude_client, prompt, ranked_routes)` — model selection, Claude API call, returns `(text, model_label)`
   - `_format_response(...)` — assembles the final JSON-serialisable response dict

2. **`recommend()` is now an ~85-line thin coordinator** — rate-limit check → BYOK client selection → cache check → sequential calls to each helper → cache write → return response. No logic was changed; behaviour is identical.

---

### Notable changes (session — 2026-04-20, `_rate_store` + `_response_cache` race condition fixed)

Resolved 🔴 "`_rate_store` and `_response_cache` race condition under concurrent requests" from `BUGS_TO_BE_FIXED.md`.

1. **`_store_lock = asyncio.Lock()` added to `main.py`** — a single module-level `asyncio.Lock` protects both `_rate_store` and `_response_cache`. `threading.Lock` would be wrong here because all I/O happens on the asyncio event loop; `asyncio.Lock` integrates with `async with` and releases correctly at every `await` point.

2. **Rate-limit check + cache read wrapped in `async with _store_lock:`** — in `recommend()`, the `_check_rate_limit(ip)` call and the `_response_cache.get(key)` / `pop()` read are now inside a single locked block. This prevents two concurrent requests with the same cache key from both seeing a miss and both launching the full expensive pipeline (stampede). It also ensures the rate-limit timestamp is written to `_rate_store` before any `await` yields control.

3. **Cache write wrapped in a second `async with _store_lock:`** — the `_response_cache[key] = ...`, `move_to_end(key)`, and `popitem()` eviction are wrapped in a second locked block. This prevents two concurrent responses both seeing `len > _CACHE_MAX_SIZE` and each evicting a different entry (double-pop).

4. **`_check_rate_limit` docstring updated** — replaced the now-incorrect "No locking needed" comment with "Callers must hold `_store_lock` before calling this function."

---

### Notable changes (session — 2026-04-18, `_ABBR_MAP` duplicate-key vulnerability hardened)

Fixes the 🔴 "`_ABBR_MAP` contains duplicate keys — last value silently wins" bug.

1. **`_ABBR_MAP` converted from dict literal to pair-tuple + built dict** — `gtfs_loader.py`: the 15 USPS suffix abbreviations are now defined as a `_ABBR_PAIRS: tuple[tuple[str, str], ...]` literal, with `_ABBR_MAP = dict(_ABBR_PAIRS)` derived from it. The dict-literal form silently kept the last value on duplicate keys; the pair-tuple form preserves every entry so duplicates remain detectable.
2. **Import-time assertion added** — `assert len(_ABBR_MAP) == len(_ABBR_PAIRS)` immediately after the conversion now raises at module import if any abbreviation is listed twice, with a diagnostic message listing the offending keys. This prevents a future typo (e.g., `("blvd", "bolevard")` after the correct entry) from silently overriding a correct expansion.
3. **Downstream usage unchanged** — `_sorted_abbrs`, `_STREET_ABBR_RE`, and `_expand()` all continue to read from `_ABBR_MAP`, which is still the same 15-entry dict. No behavior change at runtime on the current (de-duplicated) data; only the failure mode for future edits is hardened.

---

### Notable changes (session — 2026-04-18, bug fix batch 5 — BUG-001/002/008 + BUG-003 investigation)

Three bugs fixed; one bug-report false positive investigated and closed.

1. **BUG-001 fixed** — `backend/fetch_station_exits.py`: expanded the existing `try` block to cover the full row body, including `float(stop_lat)` / `float(stop_lon)` and the dict assignment. `except` now catches `(ValueError, KeyError)` so malformed or missing lat/lon columns are skipped with `continue` instead of aborting the function.
2. **BUG-002 fixed** — `backend/fetch_gtfs.py`: changed `rows = sum(1 for _ in fh) - 1` to `rows = max(0, sum(1 for _ in fh) - 1)`. Empty GTFS files now print `0 rows` instead of `-1 rows` in the validation report.
3. **BUG-008 fixed** — `frontend/src/App.jsx`: added `|| ""` guard at the `renderMarkdown` call site. Prevents `TypeError` crash when the backend returns `null` or omits the `recommendation` field.
4. **BUG-003 investigated, no fix applied** — `backend/walking.py` `_cardinal()`: the existing `math.atan2(dlon, dlat)` is mathematically correct for clockwise compass bearing from north (North→0°, East→90°, South→180°, West→270°). The bug report's suggested fix `atan2(dlat, dlon)` would swap North and East, introducing the very 90° rotation it claimed to fix. Bug closed as false positive.

---

### Notable changes (session — 2026-04-18, bus-mode transfer routing no longer gated on direct emptiness)

Fixes the 🟡 "Bus-only filter suppresses multi-leg bus routing when any direct route exists" bug.

1. **Transfer branch always runs in `transit_mode="Bus"`** — `main.py` `recommend()`: removed the `if not bus_ranked:` gate that prevented `find_bus_transfer_routes()` from ever running when `find_bus_routes()` returned any result (which it almost always did). In Bus mode the backend now calls both unconditionally, concatenates the results, then runs the combined list through the existing `_rank_bus_routes()` → merge-with-train → sort → top-5 → fingerprint-dedup pipeline. In `transit_mode="All"` the original emptiness-gated fallback is retained (unified train graph provides the intermodal backstop and the transfer call is latency-expensive).
2. **Transfer candidate count lowered 3 → 2** — Up-front cost-control measure because the transfer call now runs on every Bus-mode request. The top-5 sort/truncate after the merge still produces the same output quality; the cap only limits how many *candidate* transfer routes `find_bus_transfer_routes()` returns.
3. **Dedup unchanged** — Existing `_route_fingerprint()`-based dedup below the merge block already drops transfer routes that duplicate a direct route.

---

### Notable changes (session — 2026-04-17, Feature I — CTA Alerts Integration)

All 3 chunks of Feature I implemented. Active CTA service alerts are now fetched, surfaced to Claude, and displayed in the UI.

1. **`get_alerts()` + helpers added to `cta_client.py`** — `ALERTS_BASE`, `_TRAIN_LINE_TO_ALERT_ID` (maps internal line_code values to Alerts API route ids), `_fetch_alerts_for_route()` (single-route async fetch; timeout 5s; logs WARNING then returns `[]` on any error — TD-008), and `get_alerts()` (concurrent gather, dedup by `alert_id`, sort by `severity_score` descending). No API key required — CTA Alerts API is public.

2. **Alerts wired into `/recommend` in `main.py`** — `_alert_ids_from_routes()` helper extracts deduplicated Alerts API ids from all `TransitLeg`s in `ranked_routes` (train codes mapped through `_TRAIN_LINE_TO_ALERT_ID`; bus route numbers used directly). `get_alerts()` called after routing finalization. `build_prompt()` gained `alerts: list[dict] | None = None` parameter — alerts with `severity_score >= 5` appended as an "Active service alerts" block (major alerts prefixed "⚠ MAJOR"). `alerts` key added to response payload with 7 fields per alert (`alert_id`, `headline`, `impact`, `severity_score`, `is_major`, `event_end`, `affected_routes`).

3. **Alert banners added to `App.jsx`** — `alerts` stored in result state from `data.alerts`. Rendered between recommendation and route cards when non-empty. Major alerts (`is_major: true`) get red left border + bold red headline; minor alerts (`severity_score` 5–6) get yellow border. Impact type shown in muted uppercase below headline. Capped at 3 with "and N more" link to transitchicago.com/travel-information/alerts/. Alert styles added to `App.css` (`.alerts-section`, `.alert-item`, `.alert-item--major`, `.alert-item--minor`, `.alert-headline`, `.alert-impact`, `.alerts-more`).

---

## Completed: Feature G — Long/Short Block Classification (2026-04-13)

Walk step directions now distinguish between Chicago's two standard block sizes. Previously all blocks were counted using a single constant (`_CHICAGO_BLOCK_METERS = 80.0`), which underestimated both block types.

**Backend (`walking.py`):**
- Replaced single constant with three: `_LONG_BLOCK_METERS = 201.17`, `_SHORT_BLOCK_METERS = 100.58`, `_BLOCK_TYPE_THRESHOLD = 150.0`
- In `walk_directions()`, the edge-grouping loop now tracks `edge_count` alongside `total_length`
- After each segment is merged, classifies as long or short by comparing `avg_edge_m = total_length / edge_count` to the 150 m threshold
- Emits `"block_type": "long" | "short"` on every step dict, including the Haversine fallback path

**Frontend (`App.jsx`):**
- `formatBlocks(b, blockType)` updated to accept `blockType` — produces "2 long blocks", "3 short blocks", or plain "N block(s)" when `blockType` is absent (backward compat)
- `WalkLegItem` call site updated to pass `step.block_type`

---

## Completed: Structured Bus Route Cards (Phase 5.5)

Bus route cards are fully implemented and confirmed working as of 2026-04-09. All frontend and backend work complete.

### How it works

**Bus stop sequence table** (`transit_graph.py` — `get_bus_stop_sequences()`)
- Streams `stop_times.txt` at startup in a second dedicated pass (after the train graph pass)
- Builds `{(route_short_name, direction_id): [(stop_id, stop_name, lat, lon, arr_minutes), ...]}` for all 123 CTA bus routes × 2 directions = 246 route/direction pairs
- Cached with `@lru_cache`; called by `warm_up()` at startup alongside `_build_graph()`
- Selects the representative midday trip per direction (first-stop departure closest to noon) using the same strategy as train routing
- Startup stats observed locally: ~37,000 weekday candidate trips, 5.8M rows scanned in ~21s

**Direct bus routing** (`transit_graph.py` — `find_routes()` via the unified graph)
- Feature J (2026-04-18) deprecated and removed the legacy standalone `find_bus_routes()` function in favor of the unified NetworkX graph added by Feature B.
- Direct bus-only itineraries are surfaced by `find_routes()` walking the graph over the ~11k bus nodes + ~50k bus transit edges. Bus `TransitLeg`s retain the same schema: `line` = direction string for color lookup; `line_code` = route number for the pill label.
- `find_routes()` runs in every mode now (the old `if transit_mode != "Bus"` gate was removed as part of Feature J — without it, Bus mode returned no direct-bus routes for origin/destination pairs that lacked a qualifying bus-transfer option). In Bus mode, `main.py` post-filters the ranked list to drop any route containing a train leg (`leg.line_code in LINE_NAMES`).
- Live first-leg wait is applied in `_rank_routes()` via `_build_arrival_lookup()` (bearing-filtered) — the same path used for trains.

**Bus+bus transfer routing** (`transit_graph.py` — `find_bus_transfer_routes()`)
- Handles the itineraries the unified graph does not model: bus A → walk → bus B, where the transfer is a short walk between stops rather than a same-stop boarding.
- Called unconditionally from `main.py` whenever `transit_mode` is `"Bus"` or `"All"` and live bus arrivals + origin stops are present. `n_routes=2`.
- Sorting key includes a fixed 7.5-min leg-2 wait estimate (not added to `walk_minutes_total`/`transit_minutes`).
- Internally split into two private helpers (TD-009, resolved 2026-04-20): `_select_transfer_candidates()` (Pass 1 — haversine/spatial filtering only, returns `candidate_map` + `board_index`) and `_build_transfer_routes()` (Pass 2 — OSMnx walk calls + Route assembly). `find_bus_transfer_routes()` is now a thin coordinator.

**`main.py` integration**
- `origin_coords` and `dest_coords` resolved unconditionally (needed by both train and bus routing)
- Train routing: runs for Train/All modes. Bus routing: runs for Bus/All modes
- Bus block calls `find_bus_transfer_routes()` directly (no `_route_fingerprint()` dedup; no activation gate) and merges with `ranked_routes` via the shared sort
- Results capped at 5 combined
- `_format_train_routes` renamed `_format_routes` — handles both train and bus leg formatting
- `line_code` added to leg serialization in API response (frontend needs it for bus pill labels)
- Raw bus arrival fallback only shown when bus routing produced no structured routes

**`cta_client.py`**: `stop_id` (from `prd["stpid"]`) added to bus arrival dicts; `get_bus_arrivals()` batches into chunks of 10 via `_fetch_bus_chunk()` + `asyncio.gather`; `psgld` normalized to UPPER_SNAKE at read time

**`App.jsx`**: `BUS_DIRECTION_COLORS` added for Northbound/Southbound/Eastbound/Westbound; bus leg pill shows route number (`line_code`) with direction-based color; Bus Fullness `<select>` commented out (CTA `psgld` always empty in API responses as of 2026-04-09)

---

## Important Notes for Claude

- Before making any Anthropic API calls during development, check with the user first for approval (cost containment).
- The `npm run dev` script uses `node ./node_modules/vite/bin/vite.js` (workaround for `&` in the Windows username path — do not change this).
- `stop_times.txt` is 5.8M rows / 354 MB — never load it fully into memory at once.
- Geographic scope: Howard St (north) → 50th St (south) | Lakefront (east) → Pulaski Rd (west). OSMnx bounding box: west=-87.726, south=41.805, east=-87.52, north=42.02. Street graph is 155.3 MB / 131,257 nodes — fits Railway free tier. Points outside get Haversine walk estimates and will find no nearby CTA stops.
- Bus stop IDs from GTFS (0–29999) match the `stpid` values from the CTA Bus Tracker API directly — no ID translation needed.
- Bus direction is resolved via stop_id (CTA GTFS assigns unique stop IDs per direction) — no direction-string mapping needed or used.
