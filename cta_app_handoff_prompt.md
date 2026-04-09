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
- MapLibre GL JS — map rendering
- OpenFreeMap Positron — vector tile style (free, no API key)

**Backend**
- Python
- FastAPI (server connecting routing engine to React frontend)

**Hosting**
- Railway (backend, free tier)
- Vercel (frontend, free tier)

**Routing Engine (Python libraries)**
- `networkx` — graph-based route calculation
- `osmnx` — walking distance via real street network data
- `requests` — CTA API HTTP calls + Nominatim geocoding
- `aiohttp` — simultaneous async API calls for speed

> Note: CTA GTFS data is parsed directly with Python's built-in `csv` module (streaming). `gtfs_kit`, `pandas`, and `shapely` were considered during planning but are not used — direct CSV parsing proved sufficient and keeps the dependency footprint small.

**AI Integration**
- `anthropic` (official Python SDK) — Claude API calls from backend
- Model: `claude-sonnet-4-6`

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
- Consider Claude Haiku for simpler queries (65% cheaper than Sonnet)

> **Rate limiting status:** Not yet implemented — intentionally deferred during testing so queries are unrestricted. Add rate limiting to the `/recommend` endpoint before or shortly after public launch. Without it, a single user or bot can run up Claude API costs without any cap.

> Owner has no fixed staffing costs — significant structural cost advantage over competitors

---

## Bring Your Own API Key (BYOK) — Future Feature

A "bring your own Anthropic API key" option has been identified as a potential power-user feature. If implemented:

- Users supply their own Anthropic API key via an in-app setup workflow
- Their usage costs shift entirely off the app's variable cost base
- Reduces owner's Claude API spend for that segment of users
- Target audience for this feature: technically savvy early adopters and developers

**Important considerations when building this:**
- Most target users (everyday CTA riders) will not use this feature — do not rely on it as a primary cost solution
- API keys must be stored and handled securely — user financial liability is at stake if keys are exposed
- Build as an optional power-user setting, not a core requirement
- Caching and per-user request limiting will move the cost needle more broadly than BYOK

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
| 5.6 | Map feature — MapLibre GL JS + GTFS shapes + OSMnx walk geometry | ⬜ Next — see MAP_IMPLEMENTATION_PLAN.md |
| 6 | Deploy publicly (Vercel + Railway + custom domain) | ⬜ Pending — awaiting Google Maps key + Railway/Vercel accounts |
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
- **Known bugs:** See `BUGS_TO_BE_FIXED.md` for a full list. Pre-deployment: 1 🔴 (Claude API error handling — no try-except around `_claude_client.messages.create()`), 1 🟡 (arrival direction lookup), 1 🟡 (frontend res.json crash on non-JSON error responses). Several 🟢 deferred post-launch. Intermodal routing documented as a post-launch enhancement.
- **API keys:** CTA Train Tracker, CTA Bus Tracker, and Anthropic API keys are all obtained and configured. `GOOGLE_MAPS_API_KEY` not yet obtained — required before deployment (see Geocoding Strategy below).
- **Geocoding:** Nominatim (current) returns wrong/missing results for specific landmarks and full street addresses. Google Maps Geocoding API upgrade implementation is ready — awaiting API key. Can be done in parallel with Phase 5.6 map chunks or immediately after.

### Notable changes (session — 2026-04-06)
Three bugs in `backend/main.py` were fixed before deployment:
1. **Async event loop blocking** — `resolve_location`, `_coords_for_location`, and the Anthropic call all now run off the event loop (`run_in_executor` / `AsyncAnthropic`). Server handles concurrent requests correctly.
2. **Out-of-coverage destination** — If the destination geocodes but has no CTA stops nearby, a clear 400 is returned explaining the coverage boundary. Previously the app silently returned empty results.
3. **Anthropic client singleton** — `_claude_client = anthropic.AsyncAnthropic(...)` is now instantiated once at module level instead of on every request.

### Notable changes (session — 2026-04-08)
1. **Workbox production URL** — `vite.config.js` `runtimeCaching` pattern updated from `http://localhost:8000/.*` to `/\/(recommend|health)/` so the `NetworkOnly` rule applies to the Railway production URL, not just localhost.
2. **Stale comment removed** — `cta_client.py` module docstring updated; old Phase 4 TODO comment about bus stop IDs removed (Phase 4 is complete).
3. **Tech stack corrected** — Handoff tech stack section updated; `gtfs_kit`, `pandas`, `shapely` removed (not used — direct CSV parsing is used instead).
4. **`max_tokens` raised to 750** — Was 300. Raised for testing to give Claude more room. Plan to tune down for production.
5. **Frontend request timeout removed** — `App.jsx` no longer imposes a 15-second `AbortController` timeout. Requests run until the server responds. Removed for testing; can be re-added with a longer limit before launch if needed.
6. **Rate limiting deferred** — Noted in documentation; intentionally not implemented during testing phase. Must add before or shortly after public launch.

### Notable changes (session — 2026-04-09)
1. **Off-peak trip selection fixed** — `transit_graph.py`: `_load_weekday_service_ids()` added; `_load_representative_trips()` now loads all weekday candidate trips per direction; `_stream_stop_sequences()` selects the trip whose first-stop arrival is closest to noon per line/direction.
2. **Structured bus route cards built** — `transit_graph.py`: `get_bus_stop_sequences()` builds a `{(route_short_name, direction_id): [(stop_id, stop_name, lat, lon, arr_minutes), ...]}` table at startup (second pass through `stop_times.txt`); `find_bus_routes()` computes `Route` objects from live bus arrivals using stop_id-based direction resolution (no direction-string mapping needed — CTA GTFS stop IDs are direction-specific). `main.py`: train and bus routes merged into one ranked list, capped at 5; `_format_train_routes` renamed `_format_routes` and extended for bus legs; `line_code` added to leg serialization. `cta_client.py`: `stop_id` added to bus arrival dicts.
3. **Bus direction resolution confirmed** — stop_id approach correctly identifies southbound (and by the same logic, all directions) without any direction-string-to-direction_id mapping.
4. **Geocoding upgrade triggered** — Nominatim returns wrong/missing results for specific landmarks and addresses. Google Maps Geocoding API upgrade (already planned as Option B in gtfs_loader.py) is now required. Awaiting `GOOGLE_MAPS_API_KEY` from user to implement.
5. **Intermodal routing deferred** — combined train+bus trips (e.g., train then bus) not supported. Documented in `BUGS_TO_BE_FIXED.md` as a post-launch enhancement.
6. **Bus direction colors added (Chunk 4 complete)** — `App.jsx`: `BUS_DIRECTION_COLORS` added for Northbound/Southbound/Eastbound/Westbound; bus leg pill now shows route number (`line_code`) with direction-based color.
7. **`osmnx` import fixed** — `walking.py`: `import osmnx as ox` moved to module level so a missing dependency crashes at startup rather than being silently swallowed by the walk-time `try/except`.
8. **Bus stop ID batching fixed** — `cta_client.py`: `get_bus_arrivals()` now splits stop IDs into chunks of 10 and fires all chunks concurrently via `asyncio.gather` using new `_fetch_bus_chunk()` helper. Previously silently truncated to 10 stops.
9. **`psgld` normalization added; Bus Fullness filter hidden** — `cta_client.py`: raw `psgld` value normalized to `UPPER_SNAKE` at read time. Live API testing confirmed CTA does not currently populate `psgld` in any Bus Tracker v3 responses — Bus Fullness `<select>` commented out in `App.jsx` until CTA enables this data. Backend filter logic preserved intact.
10. **Map feature designed** — MapLibre GL JS + OpenFreeMap Positron selected. Full design decisions and 10-chunk implementation plan documented in `MAP_IMPLEMENTATION_PLAN.md`. This is Phase 5.6 and the next coding work to begin.

## Geocoding Strategy

Location resolution uses a three-step fallback (implemented in `gtfs_loader.py`):

1. **Exact match** against `NEIGHBORHOOD_COORDS` dict (instant, no network)
2. **Fuzzy match** against `NEIGHBORHOOD_COORDS` (instant, no network)
3. **OSM Nominatim** (Option A) — free geocoding API, ~200ms, biased to Chicago bounding box

**Upgrade required — Option B: Google Maps Geocoding API**
- Nominatim confirmed insufficient: returns wrong/missing results for specific landmarks, newer places, and full street addresses. Users must be able to type any address or place name — this is load-bearing functionality.
- Higher accuracy for ambiguous/partial addresses, building names, and new construction
- Free up to ~40,000 calls/month, then $5/1,000 (Google Maps Platform)
- Requires `GOOGLE_MAPS_API_KEY` in `backend/.env` AND in Railway environment variables
- To implement: replace the `geocode_nominatim()` function body in `gtfs_loader.py`. The function signature `(query: str) -> tuple[float, float] | None` stays the same — no other files need changes.
- Keep Nominatim as a fallback if Google returns no result.
- **Status:** Implementation designed and ready. Awaiting `GOOGLE_MAPS_API_KEY` from user.
- **How to get the key:** console.cloud.google.com → create project → enable Geocoding API → create API key. Add to `backend/.env` as `GOOGLE_MAPS_API_KEY=your_key`. Also add to Railway dashboard env vars before deploy.

---

## Current File Structure

```
CTA-Transit-PWA/
├── .gitignore
├── cta_app_handoff_prompt.md           ← This file
├── HUMAN_TODO.md                       ← Tasks only a human can do (accounts, keys, deploy steps, UI checks)
├── BUGS_TO_BE_FIXED.md                 ← Known bugs catalogued by severity
├── MAP_IMPLEMENTATION_PLAN.md          ← Map feature design decisions + 10 implementation chunks (Phase 5.6)
├── PYTHON_TERMINAL_TEST_STARTUP_INSTRUCTIONS.md  ← How to run backend + frontend locally
├── backend/
│   ├── .env                            ← API keys (never commit)
│   ├── main.py                         ← FastAPI server, /recommend + /health endpoints
│   ├── gtfs_loader.py                  ← 3-step location resolver + Nominatim geocoding + persistent cache
│   ├── transit_graph.py                ← NetworkX transit graph, find_routes(), find_bus_routes(), get_bus_stop_sequences(), Route/WalkLeg/TransitLeg
│   ├── walking.py                      ← OSMnx street-network walking time calculator (import osmnx at module level)
│   ├── cta_client.py                   ← Async Train Tracker + Bus Tracker API clients; batched bus stop fetching; psgld normalization
│   ├── fetch_gtfs.py                   ← Script to download/update CTA GTFS data
│   ├── fetch_street_graph.py           ← Script to download/cache OSMnx street graph
│   ├── railway.toml                    ← Railway deployment config (start command, restart policy)
│   ├── nixpacks.toml                   ← Railway build config (Python 3.12, gdal, proj)
│   ├── requirements.txt
│   ├── geocode_cache.json              ← Persistent Nominatim results cache (gitignored, built at runtime)
│   ├── gtfs_data/                      ← Downloaded GTFS files (gitignored, re-downloaded on deploy)
│   └── street_graph.graphml            ← Cached OSMnx street graph (gitignored, re-downloaded on deploy)
└── frontend/
    ├── index.html                      ← PWA meta tags, theme color, apple-touch-icon
    ├── package.json
    ├── vite.config.js                  ← VitePWA plugin config, manifest, service worker
    ├── .env.local                      ← Local dev env vars (gitignored)
    ├── .env.production                 ← Production env vars — update VITE_BACKEND_URL before deploy
    ├── src/
    │   ├── main.jsx
    │   ├── index.css
    │   ├── App.jsx                     ← RouteCard, RouteLegs, LoadingSkeleton, BUS_DIRECTION_COLORS, markdown cleanup
    │   └── App.css
    └── public/
        ├── icon-192.png
        ├── icon-512.png
        ├── apple-touch-icon.png
        └── transit-photos/             ← (pending) Transit location photos for map loading state; see HUMAN_TODO.md
```

> **Note:** Five `demo-*.html` files exist in the repo root from map style comparisons. These are temporary and will be deleted in Chunk 10 of `MAP_IMPLEMENTATION_PLAN.md`.

## Phase 6 Deployment — Step-by-Step

### Backend → Railway
1. Create account at railway.app — "Sign in with GitHub"
2. New Project → "Deploy from GitHub repo" → select this repo
3. Set the **root directory** to `backend`
4. Railway will detect `railway.toml` automatically
5. Add environment variables in the Railway dashboard (Settings → Variables):
   - `CTA_TRAIN_API_KEY`
   - `CTA_BUS_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `GOOGLE_MAPS_API_KEY` ← required for address/landmark geocoding
   - `ALLOWED_ORIGINS` ← fill in after Vercel deploy (e.g. `https://cta-transit.vercel.app`)
6. Deploy — first deploy takes ~5–8 min (downloads GTFS + street graph). Note: GTFS data and the street graph are re-downloaded on every deploy (Railway's filesystem is ephemeral). This keeps data fresh but means every redeploy takes 5–8 min.
7. Copy the Railway public URL (e.g. `https://cta-transit-backend.railway.app`)

### Frontend → Vercel
1. Create account at vercel.com — "Continue with GitHub"
2. "Add New Project" → import this repo
3. Set **root directory** to `frontend`
4. Add environment variable:
   - `VITE_BACKEND_URL` = your Railway URL from step 7 above
5. Deploy — takes ~1 min
6. Copy the Vercel URL and paste it into Railway's `ALLOWED_ORIGINS` variable
7. Redeploy the Railway backend (so CORS picks up the new origin)

### After both are live
- Update `frontend/.env.production` → replace the `your-backend.railway.app` placeholder with the real Railway URL and commit (note: the file currently contains a placeholder — the frontend will not reach the backend until this is updated)
- Test end-to-end on the live URLs
- Optional: add a custom domain in Vercel dashboard (Settings → Domains)

---

## Where to Resume

**Next coding task: Phase 5.6 — Map feature, Chunk 1** — Pre-compute GTFS shape lookup in `transit_graph.py`. Full plan in `MAP_IMPLEMENTATION_PLAN.md`. Work through all 10 chunks in order before moving to Phase 6 deployment.

**Parallel / prerequisite:** Google Maps Geocoding API upgrade — Nominatim returns wrong/missing results for specific landmarks and addresses. Fix is designed (Option B in `gtfs_loader.py`). Awaiting `GOOGLE_MAPS_API_KEY` from user. Can be done in parallel with map chunks or immediately after.

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

**`find_bus_routes()`** (`transit_graph.py`)
- Takes origin/destination coordinates, live bus arrivals (including `stop_id` field), and origin bus stops with walk times
- Resolves direction via `stop_id` alone — CTA GTFS assigns unique stop IDs per direction, so no direction-string-to-direction_id mapping is needed. Confirmed working in testing.
- Scans forward from boarding stop to find the exit stop with minimum haversine distance to destination (0.5-mile cutoff)
- Computes: board walk (OSMnx) + wait (live API) + in-vehicle (GTFS scheduled times) + exit walk (OSMnx)
- Returns `list[tuple[float, int, Route]]` — same `(total_minutes, wait_minutes, Route)` format as `_rank_routes()` for trains
- Bus `TransitLeg`: `line` = direction string (e.g. `"Northbound"`) for color lookup; `line_code` = route number (e.g. `"36"`) for pill label
- Deduplicates to one result per route+direction; caps at 3 bus routes

**`main.py` integration**
- `origin_coords` and `dest_coords` resolved unconditionally (needed by both train and bus routing)
- Train routing: runs for Train/All modes. Bus routing: runs for Bus/All modes
- Results merged, sorted by total minutes, capped at 5 combined
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
