# CTA Transit PWA

An AI-powered, real-time Chicago Transit Authority (CTA) route recommendation app. Built as a Progressive Web App (PWA) for mobile use.

## What it does

A user enters their origin and destination. The app:
1. Resolves both locations to nearby CTA stops via Google Maps geocoding
2. Runs a routing engine (GTFS + NetworkX + OSMnx) to calculate train and bus options including walking legs and transfers
3. Fetches live CTA train and bus arrival times to compute real wait times
4. Passes the ranked route options to Claude (Anthropic API) for a plain-English recommendation
5. Displays structured route cards with leg-by-leg breakdowns
6. Shows an interactive map with the route drawn on OpenFreeMap Positron tiles, including transit photos for featured stops

> **Design principle:** The AI layer handles explanation and reasoning — not raw routing. Routing is deterministic, calculated in code for accuracy. Claude's job is the last mile: turning correct, code-generated answers into helpful, conversational recommendations.

## Tech stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React (PWA), MapLibre GL JS, OpenFreeMap Positron tiles, Vite |
| **Backend** | Python, FastAPI, NetworkX, OSMnx, aiohttp |
| **AI** | Claude (`claude-sonnet-4-6`) via Anthropic Python SDK |
| **Data** | CTA GTFS (static schedules), CTA Bus & Train Tracker APIs (real-time) |
| **Hosting** | Railway (backend) + Vercel (frontend) |

## Local development

See [PYTHON_TERMINAL_TEST_STARTUP_INSTRUCTIONS.md](PYTHON_TERMINAL_TEST_STARTUP_INSTRUCTIONS.md) for step-by-step setup instructions.

### Required environment variables

**Backend** (`backend/.env`):
- `ANTHROPIC_API_KEY` — Anthropic API key for Claude
- `CTA_TRAIN_API_KEY` — CTA Train Tracker API key
- `CTA_BUS_API_KEY` — CTA Bus Tracker API key
- `GOOGLE_MAPS_API_KEY` — Google Maps Geocoding API key

**Frontend** (`frontend/.env.local`):
- `VITE_API_URL` — Backend URL (e.g. `http://localhost:8000` for local dev)

### Quick start

```bash
# Backend
cd backend
pip install -r requirements.txt
python fetch_gtfs.py          # download CTA GTFS data
python fetch_street_graph.py  # download Chicago street graph
uvicorn main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Project documentation

- [cta_app_handoff_prompt.md](cta_app_handoff_prompt.md) — Full project brief, architecture, decisions, and phase history
- [MAP_IMPLEMENTATION_PLAN.md](MAP_IMPLEMENTATION_PLAN.md) — Map feature design decisions and implementation plan
- [WEATHER&CROWDEDNESS_FEATURE_HANDOFF.md](WEATHER&CROWDEDNESS_FEATURE_HANDOFF.md) — Weather and crowdedness feature design
- [FEATURE_IMPLEMENTATION_PLANS.md](FEATURE_IMPLEMENTATION_PLANS.md) — Chunked implementation plans for major upcoming features
- [FUTURE_ENHANCEMENTS.md](FUTURE_ENHANCEMENTS.md) — Post-launch feature ideas and enhancements
- [BUGS_TO_BE_FIXED.md](BUGS_TO_BE_FIXED.md) — Known bugs catalogued by severity
- [HUMAN_TODO.md](HUMAN_TODO.md) — Tasks requiring human action (accounts, API keys, deployment steps)
