# The Chicago Routefinder

**Live app:** https://the-chicago-routefinder.vercel.app/

An AI-powered, real-time Chicago Transit Authority (CTA) route recommendation app. Built as a Progressive Web App (PWA) for mobile use, styled under "The Chicago Routefinder" editorial almanac design system — cream paper, charcoal ink, Fraunces serif headlines, and hairline rules throughout.

## What it does

### Core routing

A user enters their origin and destination. The app:

1. Resolves both locations to nearby CTA stops via a local-first geocoder cascade (curated landmark dict → fuzzy neighborhood match → local Chicago OSM address + intersection corpus → LocationIQ fallback for misses), with autocomplete suggestions covering train stations, neighborhoods, addresses, intersections, and bus stops
2. Runs a routing engine (GTFS + NetworkX + OSMnx) to calculate train, bus, and intermodal options including walking legs and transfers — with street-network turn-by-turn walk directions and long/short block classification
3. Fetches live CTA train and bus arrival times to compute real wait times, including live arrivals at transfer stops
4. Optionally passes the ranked route options to Claude (Anthropic API) for a plain-English recommendation (AI layer is opt-in via the settings panel)
5. Displays structured route cards with leg-by-leg breakdowns, crowdedness estimates, and transfer wait countdowns
6. Shows an interactive map with the route drawn on OpenFreeMap Liberty tiles, with editorial markers (§ origin, ✦ destination, ➤ live position) and a service-alert-aware leg-muting overlay

### Features

- **Live weather** — NWS weather strip (temperature, feels-like, precipitation badge, wind gusts, NWS alerts) above results; walk times automatically penalized for rain, snow, ice, extreme cold, and high gusts; Claude weighted to favor lower-exposure routes on bad-weather days
- **Service alerts** — Collapsible CTA service alerts bar above the search form with severity badges; affected route legs flagged with a ⚠ badge on route cards
- **Walk mode** — A dedicated Walk transit mode that skips all CTA calls and returns a street-network walking route with turn-by-turn directions and a map polyline
- **Pinned stops** — Pin any train station or bus stop from a result to a persistent home-screen arrivals board; each card shows live arrivals and a "Last train in X min" countdown badge for late-night use
- **GPS trip tracking** — "Start Trip" activates GPS following: active leg highlighted, walk steps checked off as the user passes them, off-route detection with a one-tap re-route from current position
- **Saved locations & routes** — Star any typed location or origin+destination pair; saved items appear in a quick-fill dropdown or one-tap panel
- **Multi-language** — 27 Chicago-focused languages with full RTL support across 6 RTL codes (`ur`, `ar`, `ps`, `prs`, `aii`, `rhg`); continent-first language picker (feature-flagged) with diaspora-aware groupings; machine-translated review badge for low-resource locales (`aii`, `ksw`, `rhg`); browser language auto-detected; Claude responds in the selected language
- **Walking speed** — Slow / Standard / Brisk pace selector in settings; applied to all walk legs and route ranking
- **BYOK** — Bring Your Own Anthropic API key (opt-in, sessionStorage only)
- **Rate limiting** — Per-IP sliding-window limiter (opt-in via Railway env var)

> **Design principle:** The AI layer handles explanation and reasoning — not raw routing. Routing is deterministic, calculated in code for accuracy. Claude's job is the last mile: turning correct, code-generated answers into helpful, conversational recommendations.

## Tech stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React (PWA), MapLibre GL JS v4, OpenFreeMap Liberty tiles, Vite, i18next (27 languages) |
| **Backend** | Python, FastAPI, NetworkX (transit graph), igraph (walking graph), OSMnx, scikit-learn, aiohttp |
| **AI** | Claude (`claude-sonnet-4-6` / `claude-haiku-4-5-20251001`) via Anthropic Python SDK |
| **Data** | CTA GTFS (static schedules), CTA Bus & Train Tracker APIs (real-time), CTA Alerts API, CTA Route Status API, NWS Weather API, LocationIQ Geocoding API (Tier-5 fallback in a local-first geocoder cascade) |
| **Hosting** | Railway (backend) + Vercel (frontend) |

## Local development

### Required environment variables

**Backend** (`backend/.env`) — required:

- `ANTHROPIC_API_KEY` — Anthropic API key for Claude
- `CTA_TRAIN_API_KEY` — CTA Train Tracker API key
- `CTA_BUS_API_KEY` — CTA Bus Tracker API key

**Backend** — optional (production tuning):

- `ALLOWED_ORIGINS` — Comma-separated CORS allowlist (production-critical; defaults to `*` in dev)
- `BYOK_ENABLED` — `true`/`false` toggle for the Bring-Your-Own-Key feature (defaults disabled)
- `RATE_LIMIT_ENABLED` — `true`/`false` toggle for the per-IP `/recommend` limiter (defaults disabled)
- `RATE_LIMIT_RPM`, `RATE_LIMIT_RPH` — Rate-limit thresholds (defaults: 10 req/min, 50 req/hour)
- `CLAUDE_SIMPLE_MODEL` — Override for the Haiku-class model (default `claude-haiku-4-5-20251001`)
- `CLAUDE_COMPLEX_MODEL` — Override for the Sonnet-class model (default `claude-sonnet-4-6`)
- `DAU_ADMIN_TOKEN` — Bearer token protecting all `GET /admin/*` analytics endpoints
- `DAILY_SALT` — Daily-rotating HMAC salt used by the DAU + sessions counters (production-required)
- `MAXMIND_LICENSE_KEY` — Free MaxMind license key (Railway *Build Argument*, not a runtime env var). Without it the Dockerfile skips the GeoLite2-City download and the FEAT-003 geography panel reads `—`.
- `LOCATIONIQ_API_KEY` — LocationIQ API key used by Tier 5 of the local-first geocoder cascade. Missing key silently disables Tier 5 (local-only behaviour).
- `LOCATIONIQ_ENABLED` — `true`/`false` kill switch for Tier 5 (default `true`).
- `LOCATIONIQ_DAILY_CAP` — UTC-day call ceiling for LocationIQ (default `4900`; ~100-call headroom under the 5,000/day free tier).
- `LOCATIONIQ_CACHE_TTL_DAYS` — Age in days after which `cached_forward` / `cached_reverse` rows are swept at FastAPI startup (default `90`, `0` disables eviction).
- `CTA_TRAIN_API_URL`, `CTA_BUS_API_URL` — Override CTA API base URLs (used by `active_routes.py`)
- `STREET_GRAPH_URL` — Release-asset URL the Dockerfile fetches `street_graph_igraph.pkl` from at build time

**Frontend** (`frontend/.env.local`):

- `VITE_BACKEND_URL` — Backend URL (e.g. `http://localhost:8000` for local dev; must include `https://` in production)

### Quick start

```bash
# Backend
cd backend
pip install -r requirements.txt
python fetch_gtfs.py          # download CTA GTFS data
python fetch_street_graph.py  # build the OSMnx street graph (one-time, ~3–10 min)
python ../scripts/build_schedule_index.py  # build the published-schedule index (FEAT-018)
uvicorn main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Backend API surface

The FastAPI server (`backend/main.py`) exposes:

| Endpoint | Purpose |
|---|---|
| `POST /recommend` | Main routing endpoint — origin/destination + transit mode → ranked route options + optional Claude recommendation |
| `GET /health` | Liveness probe |
| `GET /ping` | Lightweight no-op endpoint used to issue/refresh the analytics session cookie |
| `POST /events` | Frontend-fired analytics events (allowlisted names only — see `backend/events.py`) |
| `GET /autocomplete?q=` | Location autocomplete (train stations, neighborhoods, intersections, bus stops, addresses) |
| `GET /reverse-geocode?lat=&lon=` | GPS coordinate → human-readable address (local-first cascade: cached_reverse → nearest neighborhood → nearest OSM address → LocationIQ fallback) |
| `GET /alerts` | CTA service alerts feed |
| `GET /stop-arrivals` | Live arrivals for the home-screen pinned stops board |
| `GET /last-departure` | Last-train-of-the-day lookup for the FEAT-018 "Last Train" tool — given route/direction/station, returns the final scheduled departure time |
| `GET /schedule/routes` | Schedule picker manifest — all CTA routes with categories + reverse stop→routes index (FEAT-018) |
| `GET /schedule/{route_id}` | Full published schedule for a route, bucketed by direction → stop → service-day (FEAT-018) |
| `GET /admin/dau` | Daily-unique-user counts (protected by `DAU_ADMIN_TOKEN` — internal/operator only) |
| `GET /admin/geography` | Per-day per-city visitor counts + Chicago-metro rollup (FEAT-003, `DAU_ADMIN_TOKEN`) |
| `GET /admin/sessions` | Per-day session aggregates: count, total duration, bounces, derived avg-duration + bounce-rate (FEAT-001, `DAU_ADMIN_TOKEN`) |
| `GET /admin/hourly` | Per-day 24-int `/recommend` histogram in Chicago tz (FEAT-004, `DAU_ADMIN_TOKEN`) |
| `GET /admin/devices` | Per-day mobile/tablet/desktop/bot/unknown bucket counts (FEAT-005, `DAU_ADMIN_TOKEN`) |
| `GET /admin/referrers` | Per-day direct/search/social/other bucket counts + per-hostname `other` long-tail table (FEAT-008, `DAU_ADMIN_TOKEN`) |
| `GET /admin/events` | Per-day allowlisted event counts (FEAT-006, `DAU_ADMIN_TOKEN`) |
| `GET /admin/funnel` | Per-day funnel-stage cumulative arrays + derived conversion rates (FEAT-007, `DAU_ADMIN_TOKEN`) |
| `GET /admin/retention` | Per-day new vs returning visitor counts + Bloom-filter utilisation (FEAT-002, `DAU_ADMIN_TOKEN`) |
| `GET /stats` | **Public** dashboard page (HTML). Live engagement numbers — DAU, Chicago metro, sessions/bounce/duration, peak hours, device split, traffic sources, events, funnel, new/returning. No third-party scripts. (FEAT-009) |
| `GET /stats/{dau,geography,sessions,hourly,devices,referrers,events,funnel,retention}` | Public-safe JSON projections of the corresponding admin endpoints — only the whitelisted fields per [backend/public_stats.py](backend/public_stats.py) leave the server. |
| `GET /privacy` | Plain-text privacy notes shown via the `/stats` footer link. |

## Utility scripts

Standalone scripts that run independently of the server:

| Script | Purpose |
|--------|---------|
| `backend/fetch_gtfs.py` | Download/update CTA GTFS static data to `backend/gtfs_data/` |
| `backend/fetch_street_graph.py` | Download and cache the OSMnx Chicago pedestrian street graph (Howard St → 95th/Dan Ryan, lakefront → Austin Blvd, plus a narrow Purple Line corridor through Evanston to Linden). Run with `--force` to regenerate over an existing cache. |
| `backend/fetch_station_exits.py` | Refresh `backend/station_exits.json` (per-station exit metadata used by Feature A train-station exit guidance). |
| `backend/active_routes.py` | **Print all active CTA bus routes and train lines right now.** Uses Bus Tracker `/getroutes` (returns only in-service routes) and Train Tracker `/ttpositions` (active = has live train positions). Useful for debugging, data exploration, or verifying API keys. Requires `CTA_TRAIN_API_KEY` and `CTA_BUS_API_KEY` in `backend/.env`. |
| `backend/scripts/check_dau.py` | **Fetch daily unique visitor counts from the production backend.** Usage: `python backend/scripts/check_dau.py <DAU_ADMIN_TOKEN>` |
| `backend/scripts/check_geography.py` | **Per-day Chicago-metro share + per-city table** from `/admin/geography`. Usage: `python backend/scripts/check_geography.py <DAU_ADMIN_TOKEN>` |
| `backend/scripts/check_sessions.py` | **Per-day sessions / avg duration / bounce rate** from `/admin/sessions`. Usage: `python backend/scripts/check_sessions.py <DAU_ADMIN_TOKEN>` |
| `backend/scripts/check_hourly.py` | **Per-day hour-of-day ASCII bar chart** from `/admin/hourly`. Usage: `python backend/scripts/check_hourly.py <DAU_ADMIN_TOKEN>` |
| `backend/scripts/check_devices.py` | **Per-day device-class table** from `/admin/devices`. Usage: `python backend/scripts/check_devices.py <DAU_ADMIN_TOKEN>` |
| `backend/scripts/check_referrers.py` | **Per-day traffic-source breakdown + top-10 `other` hostnames** from `/admin/referrers`. Usage: `python backend/scripts/check_referrers.py <DAU_ADMIN_TOKEN>` |
| `backend/scripts/check_events.py` | **Per-day allowlisted-event counts** from `/admin/events`. Usage: `python backend/scripts/check_events.py <DAU_ADMIN_TOKEN>` |
| `backend/scripts/check_funnel.py` | **Per-day funnel-stage cumulative arrays + derived conversion rates** from `/admin/funnel`. Usage: `python backend/scripts/check_funnel.py <DAU_ADMIN_TOKEN>` |
| `backend/scripts/check_retention.py` | **Per-day new vs returning visitor counts + Bloom-filter utilisation banner** from `/admin/retention`. Usage: `python backend/scripts/check_retention.py <DAU_ADMIN_TOKEN>` |
| `backend/scripts/fetch_geolite.py` | Download the MaxMind GeoLite2-City database used by the FEAT-003 geography panel. |

## Operational notes

- **LocationIQ geocoding cap.** Free-text geocoding runs the local-first five-tier cascade in `backend/geocoding.py`. Tier 5 (LocationIQ) is bounded by `LOCATIONIQ_DAILY_CAP` (default 4,900/UTC day, ~100 below the free-tier ceiling of 5,000) plus a 60→120→240→300 s circuit breaker on HTTP 429. When the cap is hit, the cascade silently degrades to local-only for the remainder of the UTC day.
- **Rate limiting.** OFF by default. Set `RATE_LIMIT_ENABLED=true` (with optional `RATE_LIMIT_RPM` / `RATE_LIMIT_RPH` overrides) before opening up `/recommend` to public traffic.
- **Street graph hosting.** Both `backend/street_graph.graphml` and `backend/street_graph_igraph.pkl` are gitignored. The pkl is hosted as an asset on the `street-graph` GitHub Release and pulled at Docker build time (see `backend/Dockerfile`). For local development, run `python backend/fetch_street_graph.py` to build both files from OpenStreetMap. The runtime loads the pkl first and falls back to the graphml; if neither is present, walk routing falls back to Haversine estimates.

## Project documentation

- [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) — Full project brief, architecture, decisions, and phase history
- [docs/FEATURE_PLANS.md](docs/FEATURE_PLANS.md) — Chunked implementation plans for upcoming features and post-launch enhancement ideas
- [docs/BUGS.md](docs/BUGS.md) — Open bugs (0 🔴 high, 3 🟡 medium, 1 🟢 low)
- [docs/TODO.md](docs/TODO.md) — Tasks requiring human action (accounts, API keys, deployment steps)
- [docs/SMOKE_TESTS.md](docs/SMOKE_TESTS.md) — One-shot browser-smoke checklist for everything in TODO.md that needs a real browser
- [docs/TECH_DEBT.md](docs/TECH_DEBT.md) — Known technical debt items
- [docs/EFFICIENCY.md](docs/EFFICIENCY.md) — Optimization notes and efficiency improvements
- [docs/SECURITY.md](docs/SECURITY.md) — Open security/dependency findings (SEC-XXX from code review, DEP-XXX from dependency audits)
- [docs/PRIVACY.md](docs/PRIVACY.md) — Privacy notes for the analytics suite (DAU, geography, sessions, hourly, devices, referrers, public dashboard)
- [docs/ANALYTICS_MAINTENANCE.md](docs/ANALYTICS_MAINTENANCE.md) — Per-feature analytics-suite maintenance notes (dependency upkeep, GeoLite2 refresh cadence, panel-add/redact procedure)
- [docs/USER_ACQUISITION.md](docs/USER_ACQUISITION.md) — Marketing / growth playbook for getting people to know the app exists and install it
- [docs/design_system.md](docs/design_system.md) — Standalone design-system reference (Six Principles, voice rules, composition patterns) for new-feature work
