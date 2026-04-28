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
- `igraph` — C-backed graph library used by `walking.py` for the street routing graph; ~10× lower RAM than NetworkX
- `scipy` — `cKDTree` used by `walking.py` for nearest-node lookup; index is built from the largest connected component only
- `scikit-learn` — transitive dep of osmnx; retained in `requirements.txt` for compatibility
- `requests` — CTA API HTTP calls + Google Maps geocoding
- `aiohttp` — simultaneous async API calls for speed

> Note: CTA GTFS data is parsed directly with Python's built-in `csv` module (streaming). `gtfs_kit`, `pandas`, and `shapely` were considered during planning but are not used.

**AI Integration**
- `anthropic>=0.50` (official Python SDK) — Claude API calls from backend
- Model: `claude-sonnet-4-6` by default; `claude-haiku-4-5-20251001` for simple single-option/single-leg queries. Both model IDs are overridable via `CLAUDE_COMPLEX_MODEL` / `CLAUDE_SIMPLE_MODEL` Railway env vars.
- **Prompt caching**: static system instruction passed as a `system` block with `cache_control: {"type": "ephemeral"}` — Anthropic caches it server-side for 5 minutes, reducing input token spend per request.
- **AI Toggle** ✅ Implemented — Claude recommendation layer is opt-in (off by default). Settings panel has an "AI Explanation" checkbox persisted to `localStorage["cta_ai_enabled"]`. Backend skips `_call_claude()` entirely when `false`. Paywall-ready: add an auth check inside `if request.ai_enabled:` in `main.py`.
- **BYOK** ✅ Code complete (OFF by default — activate with `BYOK_ENABLED=true` Railway + `VITE_BYOK_ENABLED=true` Vercel). Users can supply their own Anthropic API key via the settings panel. Key stored in `sessionStorage` (clears on tab close). 30-minute idle timeout auto-clears the key. BYOK requests use a separate response-cache pool.

**Database** *(not planned for V1 or V2)*

No database required. User accounts are not planned; saved locations, routes, and pinned stops are persisted to browser `localStorage` via `frontend/src/favorites.js`.

---

## Data Sources

**Static**
- CTA GTFS data — free download from transitchicago.com (stops, routes, schedules, transfer points)

**Live**
- CTA Train Tracker API — real-time train arrivals (free, requires API key)
- CTA Bus Tracker API — real-time bus arrivals (free, separate API key)
- CTA Alerts API — service disruptions and delays (free, no key)
- NWS (National Weather Service) — live weather context (free, no key)

**Walking Distance**
- OSMnx (required) — real street-network walking times; not interchangeable with Google Maps

---

## API Keys Needed
*(All obtained and configured)*

- CTA Train Tracker API key — transitchicago.com ✅
- CTA Bus Tracker API key — transitchicago.com ✅
- Anthropic API key — console.anthropic.com ✅
- Google Maps API key — required for geocoding (addresses, landmarks) ✅

---

## Monetization Plan

- Ad-supported model — free to all users, revenue generated through ads
- No subscription tier planned at this stage
- **Phase 1 (now):** House ads only — contextual affiliate banners styled to match the Heritage Organic UI. No external ad scripts, no third-party cookies, no layout disruption.
- **Phase 2 (after meaningful user base):** Evaluate EthicalAds or Carbon Ads — developer/tech-adjacent networks with clean, text-only units that are less visually intrusive than display ads.
- **Google AdSense:** Deliberately avoided for now. Auto-placed display ads are very likely to clash with the Heritage Organic design and hurt retention. Revisit only if revenue is critically needed and aesthetic controls can be guaranteed.
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
Preserving the Heritage Organic UI is the top priority. An ad that looks out of place is worse than no ad — it signals low quality and hurts retention. Every monetization decision is filtered through this constraint first.

### Phase 1 — House Ads (current focus)
- **What:** A static `<a>` banner at the bottom of the results panel. Inline React component (`AdSlot`), no external scripts, no cookies, no third-party dependencies.
- **Styling:** Cream background (`--color-bg`), `--color-border` top-divider, charcoal text (`--color-text`). Must look like a contextual tip, not a foreign element. Heritage Organic must be completely preserved.
- **Placement:** Below the last RouteCard, inside the left panel. Never shown on empty/loading state.
- **Content:** Contextual affiliate links for Chicago commuter gear — battery packs, noise-canceling headphones, rain gear, commuter bags. See affiliate product table below.
- **Env vars (Vercel):** `VITE_HOUSE_AD_ENABLED` (default `false` locally), `VITE_HOUSE_AD_URL`, `VITE_HOUSE_AD_TEXT` — all swappable without a redeploy.
- **Affiliate program:** Amazon Associates is the practical starting point. Apply at affiliate-program.amazon.com with the live app URL.

### Phase 2 — Developer-Friendly Ad Networks (deferred)
Revisit after reaching meaningful traffic. Both require applying with a live site and have minimum traffic/content requirements.
- **EthicalAds** (ethicalads.io) — text-only, developer/tech audience, no behavioral tracking. Closest to house-ad aesthetics of any network. Preferred if a network is ever adopted.
- **Carbon Ads** (carbonads.com) — similar positioning, slightly more design-heavy. Second choice.

### Google AdSense — Explicitly Deferred
Auto-placed display ads cannot be reliably constrained to the Heritage Organic visual language. The risk of visual regression outweighs the revenue upside at current traffic levels. Only revisit if:
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

## Marketing Strategy (Early Stage)

- Post to r/chicago and r/CTA with authentic "I built this" framing
- Physical flyers at coffee shops, libraries, transit hubs, and bus stop poles near CTA stations
- Lean into decision fatigue elimination as the core emotional hook
- Local Chicago tech blogs and media as a secondary channel
- Word of mouth from genuine utility — if it works well, riders will share it

> **Note:** User acquisition is the primary unsolved challenge and should be revisited seriously before Phase 7.

---

## Build Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Validation | ✅ Complete |
| 2 | Prototype with mock CTA data + Claude API connected | ✅ Complete |
| 3 | Integrate live CTA Train and Bus Tracker APIs | ✅ Complete |
| 4 | Build routing engine (GTFS + NetworkX + OSMnx) | ✅ Complete |
| 5 | Polish UI, PWA configuration, mobile optimization | ✅ Complete |
| 5.5 | Bus routing — structured route cards | ✅ Complete (2026-04-09) |
| 5.6 | Map feature — MapLibre GL JS + GTFS shapes + OSMnx walk geometry | ✅ Complete (2026-04-09) |
| 6 | Deploy publicly (Vercel + Railway + custom domain) | ✅ Complete (2026-04-14) |
| 6.5 | Weather & Crowdedness Context | ✅ Complete (2026-04-27) |
| 7 | Monetization (House Ads first; third-party networks deferred) | ⬜ Pending |

---

## Features Implemented

All implemented features are documented in detail in [`FEATURES_IMPLEMENTED_HISTORY.md`](FEATURES_IMPLEMENTED_HISTORY.md). Key categories:

- **Routing:** Train+bus intermodal (Feature B), multi-leg bus transfers (Feature C), live transfer arrivals (Feature D), train station exit guidance (Feature A), multi-pattern train graph (Feature MultiLine)
- **Walk:** Walk-only mode (Feature WalkMode), walk speed preference (Feature Walk Speed), precipitation walk-speed penalty (Feature Precip Walk), street-level directions with block counts (Features E & G)
- **UI/UX:** Structured bus route cards (Phase 5.5), map view with GTFS shapes (Phase 5.6), service alerts bar (Feature Service Alerts), weather strip (Feature Weather UI), loading skeleton, transit photo carousel
- **Personalization:** Saved locations & routes (Feature Favorites), pinned stops arrivals board (Feature Pinned Stops), last train countdown (Feature Last Train), location autocomplete (Feature Autocomplete)
- **AI/Cost:** Claude Haiku for simple queries, AI Toggle, BYOK, response caching, rate limiting, prompt caching
- **Backend:** Live weather integration (Feature Weather), weather-adjusted route ranking (Feature Weather Scoring), optimal departure timing hint (Feature Departure Window), crowdedness estimation (Feature Crowdedness), DAU counting (Feature DAU), CTA alerts (Feature I)
- **i18n:** 22-language support via i18next + HttpBackend (Feature Language)
- **Infrastructure:** Street-network walking graph in production via Docker build (Feature K), igraph for street routing (~10× lower RAM), scipy cKDTree for nearest-node lookup

---

## Phase 6.5 — Weather & Crowdedness Context

**Status: ✅ Complete (2026-04-27)**

All five features shipped. NWS weather context, crowdedness estimates, and weather-adjusted routing now flow into every recommendation.

1. **Feature Weather** — `backend/weather_service.py` (new). NWS two-step flow (grid-point URL cached 24h, forecast+alerts cached 30min via `cachetools.TTLCache`, maxsize 200). `WeatherContext` injected into `build_prompt()`. Weather fetch runs before `_run_routing()` so the precip factor can be applied to walk legs.

2. **Feature Crowdedness** — `backend/crowdedness.py` (new). `TimePeriod`/`DayType`/`CrowdednessLevel` enums; static 2025–2027 holiday set; `estimate_crowdedness()` uses live `psgld` first, heuristic fallback. Per-route `[est. crowdedness: ...]` annotation appended to each route option in the Claude prompt.

3. **Feature Departure Window** — `backend/main.py` only. `_departure_window_hint(weather)` scans `hourly_forecast[:3]` for improving/worsening precipitation transitions. Hint appended to the weather section of `build_prompt()`. Zero extra API calls.

4. **Feature Weather Scoring** — `backend/route_scoring.py` (new). `adjust_weights_for_weather()` + `weight_hint_for_weather()`. Prompt-only: hint injected when thresholds fire (dangerous cold, extreme cold, heavy precipitation, high gusts). `_rank_routes()` ordering unchanged.

5. **Feature Precip Walk** — `backend/main.py` only. `_precip_walk_factor(weather)` returns ≤1.0 multiplier based on precipitation type/intensity, wind gusts >35 mph (×0.90), and feels_like <0°F (×0.88). Floor 0.60. Applied via `_scale_walk_legs` to all routes before ranking.

---

## Known Pending Items

- **CTA API limit:** 100,000 req/day (confirmed from Train Tracker docs). Plan caching strategy around 100k.
- **Known bugs:** See [`BUGS_TO_BE_FIXED.md`](BUGS_TO_BE_FIXED.md) for open bugs (0 🔴 high; 0 🟡 medium; 1 🟢 low — BUG-007 transit photos asset gap). Resolved bugs are logged in [`RESOLVED_HISTORY.md`](RESOLVED_HISTORY.md). When a bug is fixed, delete it from `BUGS_TO_BE_FIXED.md` and add an entry to `RESOLVED_HISTORY.md`.
- **Technical debt:** See [`Technical_Debt.md`](Technical_Debt.md) for open items (TD-009 transit photo manifest incomplete, TD-010 bus fullness filter disabled). Resolved debt is logged in `RESOLVED_HISTORY.md`. When debt is paid off, delete it from `Technical_Debt.md` and add an entry to `RESOLVED_HISTORY.md`.
- **Future enhancements:** See [`FEATURE_IMPLEMENTATION_PLANS.md`](FEATURE_IMPLEMENTATION_PLANS.md) for chunked build plans. Pending features: Feature NorthExpansion, Feature SouthExpansion, Feature Heritage, Feature Monetization.
- **API keys:** All four keys obtained and configured: CTA Train Tracker, CTA Bus Tracker, Anthropic, and Google Maps.

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
| `DAU_ADMIN_TOKEN` | Railway | Protects `GET /admin/dau` endpoint |
| `GITHUB_TOKEN` | Railway build arg | PAT with Contents:Read — needed for Dockerfile to pull street graph from GitHub Release street-graph-v1 |

**DAU persistent volume:** Add a Railway persistent volume mounted at `/app/data` so `dau.json` survives container restarts.

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

```
CTA-Transit-PWA/
├── .gitignore
├── cta_app_handoff_prompt.md           ← This file
├── HUMAN_TODO.md                       ← Tasks only a human can do (accounts, keys, deploy steps, UI checks)
├── BUGS_TO_BE_FIXED.md                 ← Open bugs only; delete entry here when fixed, add to RESOLVED_HISTORY.md
├── Technical_Debt.md                   ← Open technical debt only; delete entry here when resolved
├── Efficiency_Improvements.md          ← Open efficiency improvements only; delete entry here when implemented
├── RESOLVED_HISTORY.md                 ← Combined log: Bugs Fixed + Technical Debt Paid Off + Efficiency Improvements Implemented
├── FEATURES_IMPLEMENTED_HISTORY.md    ← All implemented features with full chunk-by-chunk detail
├── FEATURE_IMPLEMENTATION_PLANS.md     ← Pending features only: NorthExpansion, SouthExpansion, Heritage, Monetization
├── Design Documents/                   ← HTML mockups + design feedback (option 2 preferred)
├── Human Documentation/
│   ├── Saved Prompts.md                ← Reusable prompts for recurring workflows
│   ├── PYTHON_TERMINAL_TEST_STARTUP_INSTRUCTIONS.md  ← How to run backend + frontend locally
│   └── Claude Code Built-in Commands.md
├── docs/archive/
│   ├── session_changelogs.md           ← All "Notable changes" session logs archived here
│   └── MAP_IMPLEMENTATION_PLAN.md      ← Map feature design + 10-chunk plan (all complete — Phase 5.6 done)
├── backend/
│   ├── .env                            ← API keys (never commit)
│   ├── main.py                         ← FastAPI server; /recommend + /health + /autocomplete + /ping + /admin/dau + /stop-arrivals;
│   │                                      recommend() decomposed into focused helpers: _validate_api_keys(),
│   │                                      _resolve_locations() (concurrent asyncio.gather), _fetch_arrivals(),
│   │                                      _run_routing(), _fetch_transfer_arrivals(), _call_claude(), _format_response();
│   │                                      _build_arrival_lookup() indexes train AND bus arrivals (bus keyed by (route, stop_id));
│   │                                      _rank_routes (dot-product bearing test) + _rank_bus_routes();
│   │                                      OrderedDict response cache (45s TTL, 500 entries, LRU-on-hit);
│   │                                      _store_lock (asyncio.Lock) protects _rate_store + _response_cache;
│   │                                      rate limiting (off by default — RATE_LIMIT_ENABLED=true to activate);
│   │                                      BYOK (off by default — BYOK_ENABLED=true + VITE_BYOK_ENABLED=true to activate);
│   │                                      weather fetched standalone before _run_routing(); alerts + route statuses concurrent after;
│   │                                      _precip_walk_factor() + _scale_walk_legs() for precipitation walk-speed penalty;
│   │                                      _departure_window_hint() injects timing hint into weather prompt section;
│   │                                      _build_autocomplete_index() builds _ac_prefix_index (O(1) lookup, 2/3-char prefix → candidates)
│   ├── config.py                       ← Central routing config: 16 named constants across 4 categories
│   │                                      (transit graph, intermodal walk edges, walking speed/blocks, CTA API).
│   │                                      All support env-var overrides; import here, not in individual modules.
│   ├── utils.py                        ← Shared backend utilities: haversine_miles(lat1, lon1, lat2, lon2) → float;
│   │                                      SpatialGrid class (generic cell-based spatial index);
│   │                                      CHICAGO_BBOX_{GOOGLE,OVERPASS,OSMNX} + STREET_GRAPH_BBOX_OSMNX constants
│   ├── gtfs_loader.py                  ← 3-step location resolver + _normalize_street_abbr() (USPS suffix expansion) +
│   │                                      fuzzy_match_neighborhood() shared helper +
│   │                                      Google Maps geocoding + persistent cache + monthly call counter +
│   │                                      age-based eviction (90d, configurable via GEOCODE_MAX_AGE_DAYS);
│   │                                      spatial index uses SpatialGrid
│   ├── transit_graph.py                ← Unified NetworkX graph (~11k bus nodes, ~50k bus transit edges,
│   │                                      ~3k train↔bus walk edges); thread-local G_base copy per executor thread;
│   │                                      find_routes() (ORIGIN→bus_stop virtual edges; n_routes=5);
│   │                                      find_bus_transfer_routes() (bus+bus transfers; n_routes=2);
│   │                                      _resolve_node(); _path_to_route() handles intermodal walk transfers;
│   │                                      _bus_stop_grid (SpatialGrid) + _stops_near() + _build_stop_to_routes();
│   │                                      get_bus_stop_sequences(); _build_shape_lookup(); get_shape(); clip_shape();
│   │                                      _station_exits + best_exit() (train station exit guidance);
│   │                                      WalkLeg.path_points; TransitLeg.shape_points; Route.first_transit_leg_index;
│   │                                      _load_station_data() single-pass stops.txt reader
│   ├── walking.py                      ← igraph walking: walk_minutes() + walk_path() + walk_directions();
│   │                                      lru_cache on private _walk_path_impl/_walk_directions_impl (return immutable tuples);
│   │                                      public wrappers return fresh lists so callers may mutate safely;
│   │                                      shared _get_shortest_path() + _get_nearest_node() lru_cache helpers;
│   │                                      loads street_graph_igraph.pkl first; falls back to street_graph.graphml; falls back to Haversine;
│   │                                      _coord_kdtree (scipy cKDTree) replaces ox.nearest_nodes;
│   │                                      built from LCC vertices only; _get_nearest_node returns None if snap >1 km from network
│   ├── cta_client.py                   ← Async Train Tracker + Bus Tracker API clients; batched bus stop fetching;
│   │                                      psgld normalization; get_alerts() + _TRAIN_LINE_TO_ALERT_ID + _fetch_alerts_for_route();
│   │                                      shared long-lived aiohttp.ClientSession via init_session()/close_session()
│   ├── weather_service.py              ← NWS weather integration: WeatherService class; PrecipitationType/PrecipitationInfo/
│   │                                      WindInfo/CurrentWeather/ForecastPoint/WeatherContext Pydantic models;
│   │                                      two-step NWS flow (grid-point URL cached 24h, forecast+alerts cached 12min);
│   │                                      _feels_like() wind-chill + heat-index; _parse_precip() infers type+intensity
│   ├── crowdedness.py                  ← Crowdedness estimator: TimePeriod/DayType/CrowdednessLevel enums;
│   │                                      CrowdednessEstimate Pydantic model; static 2025–2027 holiday set;
│   │                                      classify_time_period(); estimate_crowdedness(); rtdir_to_inbound_outbound();
│   │                                      rtdir_to_inbound_outbound() expects pre-lowercased rtdir (normalized at CTA client boundary);
│   │                                      HIGH_TRAFFIC_TRAIN_STATIONS (10 curated mapids)
│   ├── route_scoring.py                ← Weather-adjusted route ranking: DEFAULT_WEIGHTS dict;
│   │                                      adjust_weights_for_weather() applies threshold-based deltas;
│   │                                      weight_hint_for_weather() returns human-readable prompt hint;
│   │                                      prompt-only path — _rank_routes() ordering unchanged
│   ├── dau.py                          ← Privacy-safe daily unique visitor counter: HMAC-SHA256 IP hashing with daily salt;
│   │                                      in-memory _seen_hashes set discarded on day rollover;
│   │                                      counts written to dau.json (Railway persistent volume at /app/data);
│   │                                      async record_visit(); non-blocking saves via run_in_executor;
│   │                                      batched writes: flush every 20 new visitors OR 30 seconds (whichever first);
│   │                                      get_counts() returns full {YYYY-MM-DD: count} history
│   ├── fetch_gtfs.py                   ← Script to download/update CTA GTFS data
│   ├── fetch_street_graph.py           ← Script to download/cache OSMnx street graph; applies ox.consolidate_intersections;
│   │                                      also emits street_graph_igraph.pkl (igraph pickle)
│   ├── fetch_station_exits.py          ← One-time script: queries Overpass API for railway=subway_entrance nodes,
│   │                                      matches each to nearest CTA parent station by haversine (max 0.20 mi),
│   │                                      writes station_exits.json
│   ├── active_routes.py                ← Standalone diagnostic: prints all active CTA bus routes and train lines right now
│   ├── railway.toml                    ← Railway deployment config (builder = "dockerfile")
│   ├── Dockerfile                      ← Railway build recipe; ARG STREET_GRAPH_URL + ARG GITHUB_TOKEN curl step
│   │                                      downloads street graph from GitHub Release street-graph-v1 at build time;
│   │                                      set GITHUB_TOKEN as Railway build arg before deploying
│   ├── requirements.txt
│   ├── station_exits.json              ← OSM subway entrance data (~367 exits, 130 stations); loaded at startup
│   ├── geocode_cache.json              ← Persistent geocoding results cache snapshot (gitignored, built at runtime)
│   ├── geocode_cache.journal           ← Append-only JSONL delta between snapshots (gitignored)
│   ├── geocode_counter.json            ← Monthly Google Maps API call counter (gitignored)
│   ├── gtfs_data/                      ← Downloaded GTFS files (gitignored, re-downloaded on deploy via fetch_gtfs.py)
│   ├── street_graph.graphml            ← Pre-built OSMnx street graph committed via Git LFS (bbox: Howard–20th St);
│   │                                      also hosted as GitHub Release asset street-graph-v1 (81.8 MB).
│   │                                      Downloaded at Docker build time via GITHUB_TOKEN curl step.
│   │                                      Runtime: igraph pkl first, graphml as fallback, Haversine if both absent.
│   └── street_graph_igraph.pkl         ← Pre-built igraph artifact (gitignored); produced by fetch_street_graph.py;
│                                          loaded by walking.py in preference to graphml for faster cold start + lower RAM.
└── frontend/
    ├── index.html                      ← PWA meta tags, theme color, apple-touch-icon
    ├── package.json                    ← includes maplibre-gl dependency
    ├── vite.config.js                  ← VitePWA plugin config, manifest, service worker
    ├── .env.local                      ← Local dev env vars (gitignored)
    ├── .env.production                 ← Production env vars — update VITE_BACKEND_URL before deploy
    ├── src/
    │   ├── main.jsx                    ← imports maplibre-gl/dist/maplibre-gl.css; wraps <App /> in <Suspense> for i18n
    │   ├── i18n.js                     ← i18next configuration: SUPPORTED list (22 codes), HttpBackend for on-demand
    │   │                                  locale loading, LanguageDetector, fallbackLng "en"
    │   ├── index.css
    │   ├── App.jsx                     ← split layout (panel-cards 40% / panel-map 60%); top-level state;
    │   │                                  photo fade lifecycle; LocationInput with autocomplete (200ms debounce,
    │   │                                  AbortController, keyboard nav); GPS trip tracking;
    │   │                                  off-route detection + re-route; BYOK 30-min idle timeout
    │   ├── App.css                     ← layout--split, panel-cards, panel-map, transit-photo, map-view styles;
    │   │                                  800px mobile breakpoint (stacked, 300px/350px min-heights)
    │   ├── constants.js                ← LINE_COLORS, BUS_DIRECTION_COLORS, GEO_OPTIONS, TRIP_GEO_OPTIONS,
    │   │                                  OFF_ROUTE_THRESHOLD_METERS, RETRY_DELAYS_MS, BYOK_IDLE_TIMEOUT_MS,
    │   │                                  REROUTE_SUPPRESSION_MS, isValidByokKey — single source of truth
    │   ├── favorites.js                ← localStorage helpers: savedLocations, savedRoutes, pinnedStops
    │   │                                  (cta_pinned_stops key); pinStop (10-stop cap), unpinStop, isStopPinned
    │   ├── hooks/
    │   │   ├── useApiQuery.js          ← centralised data-fetch hook: loading/error state, AbortController, polling
    │   │   ├── useLocalStorage.js      ← useState-compatible hook with JSON serialisation + error recovery
    │   │   └── useFavorites.js         ← all localStorage-backed favorites state + handlers (savedLocations,
    │   │                                  savedRoutes, pinnedStops, route-save UI)
    │   ├── utils/
    │   │   ├── fetchWithRetry.js       ← exponential back-off fetch wrapper (1s/2s/4s for 5xx/network errors)
    │   │   └── tripGeometry.js         ← haversineMeters, pointToSegmentMeters, legEndCoord, distanceToPath
    │   ├── tests/                      ← Vitest + jsdom frontend test suite (54 tests)
    │   │   ├── fetchWithRetry.test.js  ← 14 tests
    │   │   ├── tripGeometry.test.js    ← 26 tests
    │   │   └── favorites.test.js       ← 14 tests
    │   ├── components/
    │   │   ├── TransitPhoto.jsx        ← photo carousel (PHOTOS manifest defined here)
    │   │   ├── RouteCard.jsx           ← WalkLegItem + RouteLegs + RouteCard; formatBlocks helper;
    │   │   │                              pin button (📍/📌) on each TransitLeg; React.memo wrapped
    │   │   ├── PinnedStopsBoard.jsx    ← live arrivals board for pinned stops; last-train countdown badge;
    │   │   │                              returns null when no stops pinned
    │   │   ├── WeatherStrip.jsx        ← compact weather bar: temp + feels-like + forecast + precip badge + wind note;
    │   │   │                              NWS alert amber bar when alerts present; returns null when weather is null
    │   │   ├── ServiceAlertsBar.jsx    ← CTA service alerts panel: collapsed by default (count badge);
    │   │   │                              expanded shows alert cards with severity badge + dismiss button
    │   │   ├── SettingsPanel.jsx       ← BYOK / AI-toggle / walk-speed dialog
    │   │   └── LoadingSkeleton.jsx     ← loading skeleton animation
    │   └── MapView.jsx                 ← MapLibre GL JS map; locked by default; unlock button;
    │                                      _renderRouteInner → renderPolylines() + renderStopMarkers() + renderOriginDestMarkers();
    │                                      legGeoCoords pre-transform; isValidCoord guard; user position dot
    └── public/
        ├── icon-192.png
        ├── icon-512.png
        ├── apple-touch-icon.png
        ├── locales/                    ← 22 language JSON files for i18next HttpBackend
        └── transit-photos/             ← PENDING: place ≥10 transit photos here; update PHOTOS array in TransitPhoto.jsx
                                           See HUMAN_TODO.md for sourcing guidance
```

---

## Automated Test Suite

**Backend — Location:** `backend/tests/` (pytest, 155 tests)

Run from `backend/` with: `python -m pytest tests/ -v`

| Test file | Module / layer tested | Tests |
| --- | --- | --- |
| `test_utils.py` | `utils.py` — `haversine_miles`, `SpatialGrid` | 19 |
| `test_transit_graph.py` | `transit_graph.py` — pure functions only | 56 |
| `test_main_helpers.py` | `main.py` — helpers, Pydantic validators | 51 |
| `test_gtfs_loader.py` | `gtfs_loader.py` — pure string/dict functions | 21 |
| `test_endpoints.py` | `/recommend` and `/stop-arrivals` endpoint contract | 8 |

**Frontend — Location:** `frontend/src/tests/` (Vitest + jsdom, 54 tests)

Run from `frontend/` with: `npm test`

| Test file | Module tested | Tests |
| --- | --- | --- |
| `fetchWithRetry.test.js` | `utils/fetchWithRetry.js` — retry logic, abort, 4xx/5xx | 14 |
| `tripGeometry.test.js` | `utils/tripGeometry.js` — haversine, point-to-segment, off-route boundary | 26 |
| `favorites.test.js` | `favorites.js` — save/load round-trip, MAX_ITEMS, duplicates | 14 |

**Design principles:**
- No live CTA API calls, no Claude calls, no GTFS file reads during tests
- `conftest.py` creates header-only GTFS stubs in `backend/gtfs_data/` if feed is absent (CI-safe)
- `test_endpoints.py` uses `TestClient` + `unittest.mock.patch` to stub the pipeline functions

`pytest>=8.0` is in `backend/requirements.txt`.

---

## Where to Resume

**Phase 6 and Phase 6.5 are fully complete.** The app is live on Railway (backend) and Vercel (frontend). All Weather & Crowdedness features shipped 2026-04-27.

**Next steps (in order):**
1. **In Railway → Service → Settings → Build → Build Arguments**, add `GITHUB_TOKEN=<PAT with Contents:Read>` then trigger a redeploy — this activates Feature K (street-network walking graph in production).
2. Source ≥10 transit photos for the map loading panel (see `HUMAN_TODO.md`)
3. Run remaining UI checks: confirm 40/60 panel ratio on desktop, 300px/350px min-heights on mobile
4. (Optional) Add a custom domain in Vercel dashboard → Settings → Domains
5. **Next feature work:** Feature NorthExpansion or Feature SouthExpansion (both depend on Feature K street graph). See `FEATURE_IMPLEMENTATION_PLANS.md`.
6. Phase 7: Monetization (House Ads first) — implement `AdSlot` component after confirming live app is stable; defer third-party ad networks until user base is established. See "Monetization Strategy — Full Decision Record" section above.

**Bug status:** 0 🔴 high + 0 🟡 medium + 1 🟢 low bugs open (BUG-007 transit photos asset gap) — see `BUGS_TO_BE_FIXED.md`.

**Technical debt status:** 2 items open — TD-009 (transit photo manifest incomplete), TD-010 (bus fullness filter disabled) — see `Technical_Debt.md`.

**Most recently completed (2026-04-27):** All Phase 6.5 features (Weather, Crowdedness, Departure Window, Weather Scoring, Precip Walk). Frontend TD-028 through TD-037 (hook extraction, MapView sub-function split, GPS consolidation). Frontend efficiency improvements OPT-FE-001 through OPT-FE-005. Feature Pinned Stops, Feature Last Train, Feature Walk Speed, Feature WalkMode, Feature Service Alerts. BUG-015 fix (geolocation denied state now persistent). Feature K (street-network graph in production via Dockerfile build).

---

## Important Notes for Claude

- **Never start coding without reading the relevant files first.** The codebase is large and has evolved significantly. Always read the file(s) you plan to edit before writing any changes.
- **Routing accuracy is non-negotiable.** Every bug introduced into the routing engine is a real navigation failure for a real rider. Be conservative with routing changes.
- **The unified NetworkX graph is the canonical routing surface.** `find_bus_routes()` was deprecated and removed by Feature J. All routing goes through `find_routes()` on the unified graph, plus `find_bus_transfer_routes()` for bus+bus transfers.
- **The street graph uses igraph, not NetworkX.** `walking.py` loads `street_graph_igraph.pkl` (igraph) not the graphml directly. The KDTree is built from LCC vertices only.
- **BYOK and Rate Limiting are code-complete but OFF by default.** Do not activate them without explicit instruction.
- **i18n is live in 22 languages.** Any new user-facing string in React components must have keys added to all 22 locale files in `frontend/public/locales/`.
- **When resolving bugs or debt**, delete the entry from `BUGS_TO_BE_FIXED.md` or `Technical_Debt.md` and add an entry to `RESOLVED_HISTORY.md`. Do not leave resolved items in the open files.
- **When implementing features**, delete the entry from `FEATURE_IMPLEMENTATION_PLANS.md` and add an entry to `FEATURES_IMPLEMENTED_HISTORY.md`. Do not mark features as ✅ in the plans file; remove them.

---

## Session Log Archive Policy

All "Notable changes" session logs have been archived to [`docs/archive/session_changelogs.md`](docs/archive/session_changelogs.md). That file covers sessions from 2026-04-06 through 2026-04-27.

**Going forward:** When significant changes are made in a session, append a brief "Notable changes (session — YYYY-MM-DD, description)" entry to `docs/archive/session_changelogs.md`. Do NOT add session logs to this file (`cta_app_handoff_prompt.md`). This file should stay lean and orientation-focused.
