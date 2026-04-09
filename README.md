# CTA Transit PWA

An AI-powered, real-time Chicago Transit Authority (CTA) route recommendation app. Built as a Progressive Web App (PWA) for mobile use.

## What it does

A user enters their origin and destination. The app:
1. Resolves both locations to nearby CTA stops
2. Runs a routing engine (GTFS + NetworkX + OSMnx) to calculate train and bus options including walking legs and transfers
3. Fetches live CTA arrival times to compute real wait times
4. Passes the ranked route options to Claude (Anthropic API) for a plain-English recommendation
5. Displays structured route cards with leg-by-leg breakdowns and a map view

## Tech stack

- **Frontend:** React (PWA), MapLibre GL JS, OpenFreeMap Positron tiles
- **Backend:** Python, FastAPI, NetworkX, OSMnx, aiohttp
- **AI:** Claude (`claude-sonnet-4-6`) via Anthropic Python SDK
- **Hosting:** Railway (backend) + Vercel (frontend)

## Local development

See `PYTHON_TERMINAL_TEST_STARTUP_INSTRUCTIONS.md` for step-by-step instructions to run the app locally.

## Project documentation

- `cta_app_handoff_prompt.md` — Full project brief, architecture, decisions, and phase history
- `MAP_IMPLEMENTATION_PLAN.md` — Map feature design decisions and implementation plan (Phase 5.6, current)
- `BUGS_TO_BE_FIXED.md` — Known bugs catalogued by severity
- `HUMAN_TODO.md` — Tasks requiring human action (accounts, API keys, deployment steps)
