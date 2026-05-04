# The Chicago Routefinder — Project Context

> **Project owner email:** `wayfarer.atlas@gmail.com` — used for Anthropic, Railway, Vercel, Google Cloud (Maps), CTA Train/Bus Tracker, and GitHub. Use this mailbox for password resets, billing, and account recovery.

## Overview

The Chicago Routefinder is a Progressive Web App (PWA) that provides AI-powered, real-time CTA transit recommendations for Chicago riders. The project owner has no prior coding background and builds with Claude as a coding partner — write all code, explain decisions clearly, and debug step by step.

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

### Frontend

- React (PWA)
- HTML, CSS, JavaScript
- MapLibre GL JS v4 — map rendering (v5 had WebGL2 init issues in React StrictMode; pinned to v4.7.1)
- OpenFreeMap Liberty — vector tile style (free, no API key; Positron style dropped — had null-typed expression errors in MapLibre v4/v5)

### Backend

- Python
- FastAPI (server connecting routing engine to React frontend)

### Hosting

- Railway (backend, free tier)
- Vercel (frontend, free tier)

### Routing Engine (Python libraries)

- `networkx` — graph-based route calculation
- `osmnx` — walking distance via real street network data
- `igraph` — C-backed graph library used by `walking.py` for the street routing graph; ~10× lower RAM than NetworkX
- `scipy` — `cKDTree` used by `walking.py` for nearest-node lookup; index is built from the largest connected component only
- `scikit-learn` — transitive dep of osmnx; retained in `requirements.txt` for compatibility
- `requests` — CTA API HTTP calls + Google Maps geocoding
- `aiohttp` — simultaneous async API calls for speed

> Note: CTA GTFS data is parsed directly with Python's built-in `csv` module (streaming). `gtfs_kit`, `pandas`, and `shapely` were considered during planning but are not used.

### AI Integration

- `anthropic>=0.50` (official Python SDK) — Claude API calls from backend
- Model: `claude-sonnet-4-6` by default; `claude-haiku-4-5-20251001` for simple single-option/single-leg queries. Both model IDs are overridable via `CLAUDE_COMPLEX_MODEL` / `CLAUDE_SIMPLE_MODEL` Railway env vars.
- **Prompt caching**: static system instruction passed as a `system` block with `cache_control: {"type": "ephemeral"}` — Anthropic caches it server-side for 5 minutes, reducing input token spend per request.
- **AI Toggle** ✅ Implemented — Claude recommendation layer is opt-in (off by default). Settings panel has an "AI Explanation" checkbox persisted to `localStorage["cta_ai_enabled"]`. Backend skips `_call_claude()` entirely when `false`. Paywall-ready: add an auth check inside `if request.ai_enabled:` in `main.py`.
- **BYOK** ✅ Code complete (OFF by default — activate with `BYOK_ENABLED=true` Railway + `VITE_BYOK_ENABLED=true` Vercel). Users can supply their own Anthropic API key via the settings panel. Key stored in `sessionStorage` (clears on tab close). 30-minute idle timeout auto-clears the key. BYOK requests use a separate response-cache pool.

**Database** *(not planned for V1 or V2)*

No database required. User accounts are not planned; saved locations, routes, and pinned stops are persisted to browser `localStorage` via `frontend/src/favorites.js`.

---

## Data Sources

### Static

- CTA GTFS data — free download from transitchicago.com (stops, routes, schedules, transfer points)

### Live

- CTA Train Tracker API — real-time train arrivals (free, requires API key)
- CTA Bus Tracker API — real-time bus arrivals (free, separate API key)
- CTA Alerts API — service disruptions and delays (free, no key)
- NWS (National Weather Service) — live weather context (free, no key)

### Walking Distance

- OSMnx (required) — real street-network walking times; not interchangeable with Google Maps

---

## API Keys Needed

(All obtained and configured.)

- CTA Train Tracker API key — transitchicago.com ✅
- CTA Bus Tracker API key — transitchicago.com ✅
- Anthropic API key — console.anthropic.com ✅
- Google Maps API key — required for geocoding (addresses, landmarks) ✅

---

## Monetization Plan

- Ad-supported model — free to all users, revenue generated through ads
- No subscription tier planned at this stage
- **Phase 1 (now):** House ads only — contextual affiliate banners styled to match The Chicago Routefinder editorial design. No external ad scripts, no third-party cookies, no layout disruption.
- **Phase 2 (after meaningful user base):** Evaluate EthicalAds or Carbon Ads — developer/tech-adjacent networks with clean, text-only units that are less visually intrusive than display ads.
- **Google AdSense:** Deliberately avoided for now. Auto-placed display ads are very likely to clash with The Chicago Routefinder editorial design and hurt retention. Revisit only if revenue is critically needed and aesthetic controls can be guaranteed.
- Stripe not needed for V1

---

## Cost Model & Financial Reality

- Primary variable cost: Claude API usage at ~$0.01 per user request (Sonnet rates)
- Ad revenue realistic CPM: $1–3 for a local utility app, up to $5 with premium networks
- Break-even estimated at 8,000–10,000 daily active users
- Early stage expectation: $50–200/month out of pocket before ad revenue catches up

**Cost reduction strategies (all implemented):**

- Claude Haiku for simple queries ✅ — single-option or single-leg routes use Haiku; all others use Sonnet
- AI Toggle ✅ — Claude opt-in, off by default; zero token spend when disabled
- Response caching ✅ — 120s TTL, 500-entry LRU cache; repeat queries skip all upstream I/O; hit/miss logged every 100 requests
- BYOK ✅ — code complete; user's API key usage shifts off the app's variable cost base
- Rate limiting ✅ — code complete, OFF by default; activate with `RATE_LIMIT_ENABLED=true` before public launch

> Owner has no fixed staffing costs — significant structural cost advantage over competitors

---

## Monetization Strategy — Full Decision Record

This is the single canonical reference for all ad/monetization decisions. The implementation plan in `FEATURE_IMPLEMENTATION_PLANS.md` → Feature Monetization follows from these decisions.

### Philosophy

Preserving The Chicago Routefinder editorial design system is the top priority. An ad that looks out of place is worse than no ad — it signals low quality and hurts retention. Every monetization decision is filtered through this constraint first.

### Phase 1 — House Ads (current focus)

- **What:** A static `<a>` banner at the bottom of the results panel. Inline React component (`AdSlot`), no external scripts, no cookies, no third-party dependencies.
- **Styling:** Paper background (`--paper`), `--mute-fog` hairline top-divider, ink text (`--ink`). Must look like a contextual tip, not a foreign element. The Chicago Routefinder editorial aesthetic must be completely preserved.
- **Placement:** Below the last RouteCard, inside the left panel. Never shown on empty/loading state.
- **Content:** Contextual affiliate links for Chicago commuter gear — battery packs, noise-canceling headphones, rain gear, commuter bags. See affiliate product table below.
- **Env vars (Vercel):** `VITE_HOUSE_AD_ENABLED` (default `false` locally), `VITE_HOUSE_AD_URL`, `VITE_HOUSE_AD_TEXT` — all swappable without a redeploy.
- **Affiliate program:** Amazon Associates is the practical starting point. Apply at affiliate-program.amazon.com with the live app URL.

### Phase 2 — Developer-Friendly Ad Networks (deferred)

Revisit after reaching meaningful traffic. Both require applying with a live site and have minimum traffic/content requirements.

- **EthicalAds** (ethicalads.io) — text-only, developer/tech audience, no behavioral tracking. Closest to house-ad aesthetics of any network. Preferred if a network is ever adopted.
- **Carbon Ads** (carbonads.com) — similar positioning, slightly more design-heavy. Second choice.

### Google AdSense — Explicitly Deferred

Auto-placed display ads cannot be reliably constrained to The Chicago Routefinder visual language. The risk of visual regression outweighs the revenue upside at current traffic levels. Only revisit if:

- Revenue is critically needed AND
- AdSense offers layout/style controls sufficient to guarantee the ad looks native

### Affiliate Product Reference (House Ad Candidates)

Content strategy: contextual, local, utility-focused items that solve real Chicago commuter pain points.

| Category | Top Picks | Chicago Pain Point |
| :--- | :--- | :--- |
| **Noise canceling** | Sony WH-1000XM6 | Blocks "L" screeching and platform noise |
| **Open-ear / safety** | Shokz OpenDots ONE | Hear "Doors Closing" while staying aware |
| **Power** | Nestout 15000mAh; Anker 313 PowerCore 10K | Dead phone = missed train |
| **Rain gear** | Repel Windproof Travel Umbrella | Blue Line platforms are fully exposed |
| **Footwear** | Sorel Emelie III; Hunter Commando Boots | Puddles at every platform gap |
| **Bags** | Nordace Siena; Travelon Anti-Theft Heritage | Pickpocket risk + daily carry |
| **Cold** | North Face Etip Gloves | Touch-screen gloves for fare tap |
| **Reading** | Kindle Paperwhite | Waterproof for rainy platform waits |
| **CTA gear** | CTAGifts.com | Local, on-brand |
| **Tracking** | Apple AirTag; Tile Mate | Lost bag recovery |

**Copy tip:** Lead with the Chicago-specific use case, not the product name. e.g. "Survive the Blue Line platform in January →" converts better than "Buy North Face Gloves →".

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

See [`Implementation Plans/User_Acquisition_Plan.md`](Implementation%20Plans/User_Acquisition_Plan.md) for the full user acquisition strategy.

---

## Build Status

All phases through 6.5 are complete (deploy live since 2026-04-14; Weather & Crowdedness shipped 2026-04-27). Phase 7 — Monetization (House Ads) — is next.

---

## Features Implemented

See [`docs/archive/FEATURE_HISTORY.md`](archive/FEATURE_HISTORY.md) for the full record of all 42 completed features.

---

## Known Pending Items

Open bugs: [`docs/BUGS.md`](BUGS.md) · Technical debt: [`docs/TECH_DEBT.md`](TECH_DEBT.md) · Upcoming features: [`docs/FEATURE_PLANS.md`](FEATURE_PLANS.md). When resolved, move entries to [`docs/archive/RESOLVED_HISTORY.md`](archive/RESOLVED_HISTORY.md).

---

## Deployment Status

**Backend → Railway:** ✅ Live at `https://cta-transit-pwa-prod-production.up.railway.app`

**Frontend → Vercel:** ✅ Live

| Env var | Where | Notes |
|---------|-------|-------|
| `CTA_TRAIN_API_KEY` | Railway | ✅ Set |
| `CTA_BUS_API_KEY` | Railway | ✅ Set |
| `ANTHROPIC_API_KEY` | Railway | ✅ Set |
| `GOOGLE_MAPS_API_KEY` | Railway | ✅ Set |
| `ALLOWED_ORIGINS` | Railway | ✅ Set (Vercel URL) |
| `VITE_BACKEND_URL` | Vercel | ✅ Set (Railway URL with `https://`) |
| `RATE_LIMIT_ENABLED` | Railway | `true` to activate rate limiting |
| `BYOK_ENABLED` | Railway | `true` to activate BYOK |
| `VITE_BYOK_ENABLED` | Vercel | `true` to activate BYOK on frontend |
| `GEOCODE_MONTHLY_LIMIT` | Railway | Default 9,500; set `0` to disable |
| `CLAUDE_COMPLEX_MODEL` | Railway | Default `claude-sonnet-4-6` |
| `CLAUDE_SIMPLE_MODEL` | Railway | Default `claude-haiku-4-5-20251001` |
| `APP_ENV` | Railway | `production` for DAU tracking |
| `DAILY_SALT` | Railway | Random secret for DAU HMAC hashing |
| `DAU_ADMIN_TOKEN` | Railway | Protects `GET /admin/dau` and `GET /admin/geography` |
| `GITHUB_TOKEN` | Railway build arg | PAT with Contents:Read — needed for Dockerfile to pull street graph from GitHub Release street-graph-v1 |
| `MAXMIND_LICENSE_KEY` | Railway build arg | Free MaxMind key — Dockerfile downloads GeoLite2-City.mmdb for FEAT-003 (geography). If unset, geography counting silently no-ops at runtime. |

**Analytics persistent volume:** Add a Railway persistent volume mounted at `/app/data` so the analytics counters (`dau.json`, `geography.json`, `sessions.json`, `hourly.json`, `devices.json`, `referrers.json`) survive container restarts.

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
- Free tier: ~40,000 calls/month. Production call cap defaults to 9,500/month (configurable via `GEOCODE_MONTHLY_LIMIT` env var; set to `0` to disable).
- Requires `GOOGLE_MAPS_API_KEY` in `backend/.env` AND in Railway environment variables ✅

---

## Current File Structure

```text
CTA-Transit-PWA/
├── .gitignore
├── README.md
├── CLAUDE.md                           ← Claude Code project instructions
├── docs/
│   ├── PROJECT_CONTEXT.md              ← This file
│   ├── BUGS.md                         ← Open bugs only; delete entry here when fixed
│   ├── TECH_DEBT.md                    ← Open technical debt only; delete entry here when resolved
│   ├── EFFICIENCY.md                   ← Open efficiency improvements only; delete entry here when implemented
│   ├── FEATURE_PLANS.md                ← Pending features only; delete entry here when shipped
│   ├── TODO.md                         ← Tasks requiring human action (accounts, API keys, deploy steps)
│   └── archive/                        ← Frozen historical records (do not append)
│       ├── RESOLVED_HISTORY.md         ← Combined log: Bugs Fixed + Technical Debt Paid Off + Efficiency Improvements Implemented
│       ├── FEATURE_HISTORY.md            ← All implemented features with full chunk-by-chunk detail
│       └── session_changelogs.md       ← All "Notable changes" session logs
├── Human Documentation/
│   ├── Saved Prompts.md                ← Reusable prompts for recurring workflows
│   └── PYTHON_TERMINAL_TEST_STARTUP_INSTRUCTIONS.md  ← How to run backend + frontend locally
├── backend/
│   ├── .env                            ← API keys (never commit)
│   ├── main.py                         ← FastAPI app wiring + lifespan + /recommend, /health, /ping, /autocomplete, /alerts, /reverse-geocode, /stop-arrivals (admin/stats endpoints live in routes/)
│   ├── rate_limit.py                   ← Per-IP /recommend RPM/RPH + rolling-24h + geocode-bucket sliding-window limiter; _client_ip extractor
│   ├── middleware.py                   ← register_middlewares(): request-size cap, security headers, privacy-preserving analytics dispatcher
│   ├── prompt_builder.py               ← build_prompt() + LANGUAGE_NAMES + crowdedness labels + route/weather/transfer formatting helpers
│   ├── analytics_store.py              ← Shared persistence skeleton (today_chi/data_file/safe_load_json/atomic_write_json) for the 6 daily-aggregate counters
│   ├── routes/
│   │   ├── admin.py                    ← /admin/{dau,geography,sessions,hourly,devices,referrers} APIRouter + DAU_ADMIN_TOKEN gate
│   │   └── stats.py                    ← /stats, /stats/{dau,geography,sessions,hourly,devices,referrers}, /privacy APIRouter (geocode-bucket rate-limited)
│   ├── config.py                       ← Central routing constants (16 named values, all env-var overridable)
│   ├── utils.py                        ← haversine_miles(), SpatialGrid, Chicago bbox constants
│   ├── gtfs_loader.py                  ← 3-step location resolver + Google Maps geocoding + persistent cache + monthly counter
│   ├── transit_graph.py                ← Unified NetworkX graph; find_routes(); find_bus_transfer_routes(); shape/exit helpers
│   ├── walking.py                      ← igraph street routing; walk_minutes/path/directions; lru_cache; Haversine fallback
│   ├── cta_client.py                   ← Async CTA Train + Bus Tracker clients; alerts feed; shared aiohttp session
│   ├── weather_service.py              ← NWS two-step weather fetch; WeatherContext Pydantic model
│   ├── crowdedness.py                  ← Crowdedness estimator: time-period/day-type enums + psgld-first heuristic
│   ├── route_scoring.py                ← Weather-adjusted ranking weights; prompt-only hint injection
│   ├── dau.py                          ← HMAC-SHA256 privacy-safe DAU counter; batched writes to /app/data/dau.json
│   ├── geography.py                    ← FEAT-003: per-day per-city counter via MaxMind GeoLite2-City; privacy floor + Chicago-metro rollup; /app/data/geography.json
│   ├── sessions.py                     ← FEAT-001: random sid cookie (httpOnly Secure SameSite=Lax, 30-min sliding TTL); idle-finalised session aggregates; /app/data/sessions.json
│   ├── hourly.py                       ← FEAT-004: per-day 24-int /recommend histogram in Chicago tz; /app/data/hourly.json
│   ├── devices.py                      ← FEAT-005: ua-parser-driven mobile/tablet/desktop/bot/unknown buckets; raw UA never persisted; /app/data/devices.json
│   ├── referrers.py                    ← FEAT-008: Referer hostname → direct/search/social/other buckets; path/query stripped pre-storage; /app/data/referrers.json
│   ├── public_stats.py                 ← FEAT-009: public-safe projection of admin counters + /stats HTML page (no third-party scripts) + /privacy text
│   ├── fetch_gtfs.py                   ← Script: download/update CTA GTFS data
│   ├── fetch_street_graph.py           ← Script: build OSMnx street graph + emit igraph pickle
│   ├── fetch_station_exits.py          ← Script: build station_exits.json from Overpass OSM data
│   ├── active_routes.py                ← Diagnostic: print all active CTA routes right now
│   ├── railway.toml                    ← Railway deployment config
│   ├── Dockerfile                      ← Railway build recipe; pulls street_graph from GitHub Release at build time
│   ├── requirements.txt
│   ├── station_exits.json              ← ~367 OSM subway entrances for 130 stations; loaded at startup
│   ├── geocode_cache.json              ← Persistent geocoding cache snapshot (gitignored)
│   ├── geocode_cache.journal           ← Append-only JSONL delta (gitignored)
│   ├── geocode_counter.json            ← Monthly API call counter (gitignored)
│   ├── gtfs_data/                      ← Downloaded GTFS files (gitignored)
│   ├── street_graph.graphml            ← OSMnx graph source (gitignored, ~227 MB; Chicago + Evanston bbox; built locally by fetch_street_graph.py)
│   └── street_graph_igraph.pkl         ← igraph runtime pickle (gitignored, ~47 MB; hosted on the "street-graph" GitHub Release, fetched at Docker build); preferred over graphml at runtime
└── frontend/
    ├── index.html                      ← PWA meta tags, theme color, apple-touch-icon
    ├── package.json
    ├── vite.config.js                  ← VitePWA plugin config, manifest, service worker
    ├── .env.local                      ← Local dev env vars (gitignored)
    ├── .env.production                 ← Production env vars — update VITE_BACKEND_URL before deploy
    ├── src/
    │   ├── main.jsx                    ← Entry point; i18n Suspense wrapper
    │   ├── i18n.js                     ← i18next config: 22 language codes, HttpBackend, LanguageDetector
    │   ├── index.css
    │   ├── App.jsx                     ← Top-level state; split layout; LocationInput; GPS trip tracking; off-route detection
    │   ├── App.css                     ← Design tokens; layout--split; 800px mobile breakpoint
    │   ├── constants.js                ← LINE_COLORS, GEO_OPTIONS, thresholds, timeouts — single source of truth
    │   ├── favorites.js                ← localStorage helpers: savedLocations, savedRoutes, pinnedStops
    │   ├── hooks/
    │   │   ├── useApiQuery.js          ← Centralised data-fetch hook: loading/error state, AbortController, polling
    │   │   ├── useLocalStorage.js      ← useState-compatible hook with JSON serialisation + error recovery
    │   │   └── useFavorites.js         ← All localStorage-backed favorites state + handlers
    │   ├── utils/
    │   │   ├── fetchWithRetry.js       ← Exponential back-off fetch wrapper (1s/2s/4s for 5xx/network errors)
    │   │   └── tripGeometry.js         ← haversineMeters, pointToSegmentMeters, legEndCoord, distanceToPath
    │   ├── tests/                      ← Vitest + jsdom frontend test suite (26 files, 258 tests)
    │   │   ├── *.test.jsx              ← Component tests for all 16 non-map components
    │   │   ├── *.test.js               ← Util tests (5) + hook tests (4)
    │   │   └── setup.js                ← jest-dom matcher registration
    │   ├── components/
    │   │   ├── TransitPhoto.jsx        ← Photo carousel (PHOTOS manifest defined here)
    │   │   ├── RouteCard.jsx           ← Route card with walk legs, transit legs, pin button; React.memo wrapped
    │   │   ├── PinnedStopsBoard.jsx    ← Live arrivals board for pinned stops; last-train countdown badge
    │   │   ├── WeatherStrip.jsx        ← Compact NWS weather bar; alert amber bar; returns null when weather is null
    │   │   ├── ServiceAlertsBar.jsx    ← CTA service alerts panel: collapsed by default, expand to show cards
    │   │   ├── SettingsPanel.jsx       ← BYOK / AI-toggle / walk-speed dialog
    │   │   └── LoadingSkeleton.jsx     ← Loading skeleton animation
    │   └── MapView.jsx                 ← MapLibre GL JS map; renderPolylines + stop/origin/dest markers; user position dot
    └── public/
        ├── icon-192.png
        ├── icon-512.png
        ├── apple-touch-icon.png
        ├── locales/                    ← 22 language JSON files for i18next HttpBackend
        └── transit-photos/             ← PENDING: place ≥10 transit photos here (see HUMAN_TODO.md)
```

---

## Automated Test Suite

**Combined: 651 tests** — backend 393 (pytest, 18 files) + frontend 258 (Vitest + jsdom, 26 files). All passing as of 2026-05-04.

### Run commands

| Command | What it runs |
| --- | --- |
| `python -m pytest` (from repo root) | Full backend suite via `pyproject.toml` config |
| `python -m pytest backend/tests/test_<name>.py` | Single backend file |
| `python -m pytest -k <pattern>` | Backend tests matching name pattern |
| `npm test` (from `frontend/`) | Full frontend suite |
| `npm test -- --run <pattern>` | Single frontend file or test name |

### Backend coverage (`backend/tests/`)

| Layer | Files | What's covered |
| --- | --- | --- |
| **Pure utilities** | `test_utils.py`, `test_crowdedness.py`, `test_dau.py`, `test_route_scoring.py`, `test_weather_service.py` | Haversine, spatial grid, time-period classification, DAU counters, weather parsing, route scoring weights |
| **GTFS parsing** | `test_gtfs_parsing.py`, `test_gtfs_loader.py` | All `_load_*` functions in `transit_graph.py` exercised against synthetic CSV fixtures; geocoding/neighborhood helpers in `gtfs_loader.py` |
| **Graph routing** | `test_transit_graph.py`, `test_graph_construction.py` | Pure helpers (bearing, time parse, dedup) + `_path_to_route` and `find_routes` against hand-built fixture graphs |
| **CTA API client** | `test_cta_client.py` | Train/Bus/Alerts/Routes parsing with mocked `aiohttp.ClientSession`; CTA dict-vs-list quirks, error sentinels, dedup |
| **FastAPI app** | `test_main_helpers.py`, `test_endpoints.py` | `_cache_key`, rate limiter, prompt builder, `RouteRequest` validators, `/recommend` + `/stop-arrivals` contract via `TestClient` |
| **Analytics** | `test_devices.py`, `test_geography.py`, `test_hourly.py`, `test_public_stats.py`, `test_referrers.py`, `test_sessions.py` | All FEAT-001/003/004/005/008 modules and the `/stats` projection layer |

### Frontend coverage (`frontend/src/tests/`)

| Layer | What's covered |
| --- | --- |
| **Components (15 of 16)** | All non-map components tested: ErrorBoundary, LabelSavePanel, LinePill, LoadingSkeleton, LocationInput, PinnedStopsBoard, RouteCard, SavedRoutesPanel, ServiceAlertsBar, SettingsPanel, SharedRouteBanner, SideRail, SignalLamp, TwoToneHeading, WeatherStrip, Wordmark. Not covered: `markers/*` (3 files — maplibre-dependent) |
| **Utils (5 of 5)** | deriveTransferPoints, fetchWithRetry, renderMarkdown, routeUtils, tripGeometry |
| **Hooks (4 of 7)** | useApiQuery, useByokIdleClear, useFavorites, useLocalStorage. Not covered: useMapMarker, useRouteLayers, useTripTracker (all maplibre/geolocation-dependent) |
| **Persistence** | favorites.js — save/load round-trip, MAX_ITEMS, dedup |

### Design principles

- **No live network in tests.** No CTA API calls, no Claude calls, no NWS calls, no live GTFS reads. All I/O patched at the boundary.
- **Synthetic fixtures over real data.** GTFS parsing tested against 2–5-row CSV fixtures written to `tmp_path`; graph routing tested against hand-built `nx.DiGraph` instances.
- **`conftest.py` creates header-only GTFS stubs** in `backend/gtfs_data/` if the real feed is absent (CI-safe).
- **Mocked `aiohttp.ClientSession`** for `cta_client`; mocked `react-i18next` per component test for translation keys.
- **lru_cache reset between GTFS tests** via autouse fixture so each test sees fresh data.

### Configuration

- `pyproject.toml` (repo root) — `pythonpath = ["backend"]`, `testpaths = ["backend/tests"]`, `asyncio_mode = "strict"`. Lets `python -m pytest` work from any cwd.
- `frontend/vite.config.js` — Vitest config: jsdom environment, `src/tests/**/*.test.{js,jsx}`, setup file.
- `backend/requirements-dev.txt` — `pytest`, `pytest-asyncio`, `httpx` (for FastAPI `TestClient`), `osmnx`, `psutil`.

### Known coverage gaps (intentional)

- **maplibre-gl-dependent code** — `MapView.jsx`, `markers/*`, `useMapMarker`, `useRouteLayers`, `useTripTracker`. Each would need ~100 lines of brittle WebGL mocks. The right tool is Playwright with a real browser; see [FEATURE_PLANS.md → Consideration — Playwright E2E suite for maplibre + geolocation paths](FEATURE_PLANS.md).
- **`App.jsx`** — top-level orchestration. Better tested as E2E than unit.
- **`warm_up()` / live `_build_graph()`** — exercised indirectly via the GTFS-parsing tests of every loader it calls.
- **`find_bus_transfer_routes`** — large, real-graph-dependent. Defer until the bus-to-bus path becomes a reliability concern.

---

## Where to Resume

The app is live on Railway + Vercel. All phases through 6.5 are complete; Feature Heritage, MapMarkers, and NorthExpansion/SouthExpansion shipped 2026-05-01. Feature HeadingTwoTone and Feature ItinerarySpine shipped 2026-05-03, completing the deferred D2 design-system work for panel headings and itinerary leg rows.

**Next steps (in order):**

1. (Optional) Add a custom domain in Vercel → Settings → Domains.
2. **Phase 7:** Monetization (House Ads first) — implement `AdSlot` component. See "Monetization Strategy — Full Decision Record" below.

**Bug status:** 0 🔴 high + 0 🟡 medium + 0 🟢 low — see `BUGS_TO_BE_FIXED.md`.
**Technical debt status:** 0 items open — see `Technical_Debt.md`.

---

## Development Guidelines

- **Never start coding without reading the relevant files first.** The codebase is large and has evolved significantly. Always read the file(s) you plan to edit before writing any changes.
- **Routing accuracy is non-negotiable.** Every bug introduced into the routing engine is a real navigation failure for a real rider. Be conservative with routing changes.
- **The unified NetworkX graph is the canonical routing surface.** `find_bus_routes()` was deprecated and removed by Feature J. All routing goes through `find_routes()` on the unified graph, plus `find_bus_transfer_routes()` for bus+bus transfers.
- **The street graph uses igraph, not NetworkX.** `walking.py` loads `street_graph_igraph.pkl` (igraph) not the graphml directly. The KDTree is built from LCC vertices only.
- **BYOK and Rate Limiting are code-complete but OFF by default.** Do not activate them without explicit instruction.
- **i18n is live in 22 languages.** Any new user-facing string in React components must have keys added to all 22 locale files in `frontend/public/locales/`.
- **When resolving bugs or debt**, delete the entry from `BUGS_TO_BE_FIXED.md` or `Technical_Debt.md` and add an entry to `RESOLVED_HISTORY.md`. Do not leave resolved items in the open files.
- **When implementing features**, delete the entry from `FEATURE_IMPLEMENTATION_PLANS.md` and add an entry to `FEATURE_HISTORY.md`. Do not mark features as ✅ in the plans file; remove them.

---

Session logs → [`docs/archive/session_changelogs.md`](docs/archive/session_changelogs.md). Do not add session logs to this file.
