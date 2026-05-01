# The Chicago Routefinder

An AI-powered, real-time Chicago Transit Authority (CTA) route recommendation app. Built as a Progressive Web App (PWA) for mobile use, styled under "The Chicago Routefinder" editorial almanac design system — cream paper, charcoal ink, Fraunces serif headlines, and hairline rules throughout.

## What it does

### Core routing
A user enters their origin and destination. The app:
1. Resolves both locations to nearby CTA stops via Google Maps geocoding, with autocomplete suggestions covering train stations, neighborhoods, and bus stops
2. Runs a routing engine (GTFS + NetworkX + OSMnx) to calculate train, bus, and intermodal options including walking legs and transfers — with street-network turn-by-turn walk directions and long/short block classification
3. Fetches live CTA train and bus arrival times to compute real wait times, including live arrivals at transfer stops
4. Optionally passes the ranked route options to Claude (Anthropic API) for a plain-English recommendation (AI layer is opt-in via the settings panel)
5. Displays structured route cards with leg-by-leg breakdowns, crowdedness estimates, and transfer wait countdowns
6. Shows an interactive map with the route drawn on OpenFreeMap Liberty tiles, including transit photos for featured stops

### Features
- **Live weather** — NWS weather strip (temperature, feels-like, precipitation badge, wind gusts, NWS alerts) above results; walk times automatically penalized for rain, snow, ice, extreme cold, and high gusts; Claude weighted to favor lower-exposure routes on bad-weather days
- **Service alerts** — Collapsible CTA service alerts bar above the search form with severity badges; affected route legs flagged with a ⚠ badge on route cards
- **Walk mode** — A dedicated Walk transit mode that skips all CTA calls and returns a street-network walking route with turn-by-turn directions and a map polyline
- **Pinned stops** — Pin any train station or bus stop from a result to a persistent home-screen arrivals board; each card shows live arrivals and a "Last train in X min" countdown badge for late-night use
- **GPS trip tracking** — "Start Trip" activates GPS following: active leg highlighted, walk steps checked off as the user passes them, off-route detection with a one-tap re-route from current position
- **Saved locations & routes** — Star any typed location or origin+destination pair; saved items appear in a quick-fill dropdown or one-tap panel
- **Multi-language** — 22 languages with RTL support; browser language auto-detected; Claude responds in the selected language
- **Walking speed** — Slow / Standard / Brisk pace selector in settings; applied to all walk legs and route ranking
- **BYOK** — Bring Your Own Anthropic API key (opt-in, sessionStorage only)
- **Rate limiting** — Per-IP sliding-window limiter (opt-in via Railway env var)

> **Design principle:** The AI layer handles explanation and reasoning — not raw routing. Routing is deterministic, calculated in code for accuracy. Claude's job is the last mile: turning correct, code-generated answers into helpful, conversational recommendations.

## Tech stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React (PWA), MapLibre GL JS v4, OpenFreeMap Liberty tiles, Vite, i18next (22 languages) |
| **Backend** | Python, FastAPI, NetworkX, OSMnx, scikit-learn, aiohttp |
| **AI** | Claude (`claude-sonnet-4-6` / `claude-haiku-4-5-20251001`) via Anthropic Python SDK |
| **Data** | CTA GTFS (static schedules), CTA Bus & Train Tracker APIs (real-time), CTA Alerts API, CTA Route Status API, NWS Weather API, Google Maps Geocoding API |
| **Hosting** | Railway (backend) + Vercel (frontend) |

## Local development

### Required environment variables

**Backend** (`backend/.env`) — required:
- `ANTHROPIC_API_KEY` — Anthropic API key for Claude
- `CTA_TRAIN_API_KEY` — CTA Train Tracker API key
- `CTA_BUS_API_KEY` — CTA Bus Tracker API key
- `GOOGLE_MAPS_API_KEY` — Google Maps Geocoding API key

**Backend** — optional (production tuning):
- `ALLOWED_ORIGINS` — Comma-separated CORS allowlist (production-critical; defaults to `*` in dev)
- `BYOK_ENABLED` — `true`/`false` toggle for the Bring-Your-Own-Key feature (defaults disabled)
- `RATE_LIMIT_ENABLED` — `true`/`false` toggle for the per-IP `/recommend` limiter (defaults disabled)
- `RATE_LIMIT_RPM`, `RATE_LIMIT_RPH` — Rate-limit thresholds (defaults: 10 req/min, 50 req/hour)
- `CLAUDE_SIMPLE_MODEL` — Override for the Haiku-class model (default `claude-haiku-4-5-20251001`)
- `CLAUDE_COMPLEX_MODEL` — Override for the Sonnet-class model (default `claude-sonnet-4-6`)
- `DAU_ADMIN_TOKEN` — Bearer token protecting `GET /admin/dau`
- `CTA_TRAIN_API_URL`, `CTA_BUS_API_URL` — Override CTA API base URLs (used by `active_routes.py`)
- `STREET_GRAPH_URL` — Release-asset URL the Dockerfile fetches `street_graph.graphml` from at build time

**Frontend** (`frontend/.env.local`):
- `VITE_BACKEND_URL` — Backend URL (e.g. `http://localhost:8000` for local dev; must include `https://` in production)

### Quick start

```bash
# Backend
cd backend
pip install -r requirements.txt
python fetch_gtfs.py          # download CTA GTFS data (street graph is pre-built via Git LFS)
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
| `GET /autocomplete?q=` | Location autocomplete (stations, neighborhoods, bus stops) |
| `GET /reverse-geocode?lat=&lon=` | GPS coordinate → human-readable address (Google Maps) |
| `GET /alerts` | CTA service alerts feed |
| `GET /weather` | NWS current conditions + alerts for the user's coordinates |
| `GET /pinned-arrivals` | Live arrivals for the home-screen pinned stops board |
| `GET /admin/dau` | Daily-unique-user counts (protected by `DAU_ADMIN_TOKEN` — internal/operator only) |

## Utility scripts

Standalone scripts in `backend/` that run independently of the server:

| Script | Purpose |
|--------|---------|
| `fetch_gtfs.py` | Download/update CTA GTFS static data to `backend/gtfs_data/` |
| `fetch_street_graph.py` | Download and cache the OSMnx Chicago pedestrian street graph (Linden/Dempster-Skokie → 95th/Dan Ryan, lakefront → Midway corridor). Run with `--force` to regenerate over an existing cache. |
| `fetch_station_exits.py` | Refresh `backend/station_exits.json` (per-station exit metadata used by Feature A train-station exit guidance). |
| `active_routes.py` | **Print all active CTA bus routes and train lines right now.** Uses Bus Tracker `/getroutes` (returns only in-service routes) and Train Tracker `/ttpositions` (active = has live train positions). Useful for debugging, data exploration, or verifying API keys. Run with `python active_routes.py` from the `backend/` directory — requires `CTA_TRAIN_API_KEY` and `CTA_BUS_API_KEY` in `backend/.env`. |

## Operational notes

- **Google Maps geocoding cap.** `backend/gtfs_loader.py` enforces a temporary monthly safety cap of 9,500 calls/month against the Google Maps Geocoding API to stay inside the free tier. The cap is opt-out tuning; remove or raise it via `HUMAN_TODO.md` once billing is wired up.
- **Rate limiting.** OFF by default. Set `RATE_LIMIT_ENABLED=true` (with optional `RATE_LIMIT_RPM` / `RATE_LIMIT_RPH` overrides) before opening up `/recommend` to public traffic.
- **Street graph hosting.** `backend/street_graph.graphml` is committed via Git LFS *and* hosted as a GitHub Release asset (downloaded at Docker build time). The runtime loads `street_graph_igraph.pkl` first and falls back to the graphml; if neither is present, walk routing falls back to Haversine estimates.

## Project documentation

- [cta_app_handoff_prompt.md](cta_app_handoff_prompt.md) — Full project brief, architecture, decisions, and phase history
- [docs/archive/MAP_IMPLEMENTATION_PLAN.md](docs/archive/MAP_IMPLEMENTATION_PLAN.md) — Map feature design decisions and implementation plan
- [FEATURE_IMPLEMENTATION_PLANS.md](FEATURE_IMPLEMENTATION_PLANS.md) — Chunked implementation plans for upcoming features and post-launch enhancement ideas
- [BUGS_TO_BE_FIXED.md](BUGS_TO_BE_FIXED.md) — Open bugs (0 🔴 high, 0 🟡 medium, 1 🟢 low); [RESOLVED_HISTORY.md](RESOLVED_HISTORY.md) — Log of all resolved bugs, paid-off technical debt, and implemented efficiency improvements
- [HUMAN_TODO.md](HUMAN_TODO.md) — Tasks requiring human action (accounts, API keys, deployment steps)
