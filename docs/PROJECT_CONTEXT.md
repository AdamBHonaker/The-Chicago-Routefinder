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
- `requests` — CTA API HTTP calls + LocationIQ (Tier-5 geocoding fallback)
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
- LocationIQ API key — Tier-5 geocoding fallback (free tier, 5,000 calls/day; cap defaults to 4,900) ✅

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

This is the single canonical reference for all ad/monetization decisions. The implementation plan in `FEATURE_PLANS.md` → Feature Monetization follows from these decisions.

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

See [`docs/USER_ACQUISITION.md`](USER_ACQUISITION.md) for the full user acquisition strategy.

---

## Build Status

All phases through 6.5 are complete (deploy live since 2026-04-14; Weather & Crowdedness shipped 2026-04-27). Phase 7 — Monetization (House Ads) — Chunk 1 (`AdSlot` component) shipped 2026-05-05 behind `VITE_HOUSE_AD_ENABLED` (default `false`). Subsequent monetization sub-phases remain — see [`docs/FEATURE_PLANS.md`](FEATURE_PLANS.md) → Feature Monetization.

---

## Features Implemented

See [`docs/archive/FEATURE_HISTORY.md`](archive/FEATURE_HISTORY.md) for the full record of all 44 completed features (plus the four Analytics Suite phases 22a–22d).

---

## Known Pending Items

Open bugs: [`docs/BUGS.md`](BUGS.md) · Technical debt: [`docs/TECH_DEBT.md`](TECH_DEBT.md) · Upcoming features: [`docs/FEATURE_PLANS.md`](FEATURE_PLANS.md). When resolved, move entries to [`docs/archive/RESOLVED_HISTORY.md`](archive/RESOLVED_HISTORY.md).

---

## Deployment Status

**Backend → Railway:** ✅ Live at `https://the-chicago-routefinder.up.railway.app`

**Frontend → Vercel:** ✅ Live at `https://the-chicago-routefinder.vercel.app/`

| Env var | Where | Notes |
|---------|-------|-------|
| `CTA_TRAIN_API_KEY` | Railway | ✅ Set |
| `CTA_BUS_API_KEY` | Railway | ✅ Set |
| `ANTHROPIC_API_KEY` | Railway | ✅ Set |
| `LOCATIONIQ_API_KEY` | Railway | ✅ Set (Tier-5 geocoder; missing key silently disables Tier 5) |
| `ALLOWED_ORIGINS` | Railway | ✅ Set (Vercel URL) |
| `VITE_BACKEND_URL` | Vercel | ✅ Set (Railway URL with `https://`) |
| `RATE_LIMIT_ENABLED` | Railway | `true` to activate rate limiting |
| `BYOK_ENABLED` | Railway | `true` to activate BYOK |
| `VITE_BYOK_ENABLED` | Vercel | `true` to activate BYOK on frontend |
| `LOCATIONIQ_DAILY_CAP` | Railway | UTC-day call ceiling; default 4,900 (free-tier headroom) |
| `LOCATIONIQ_ENABLED` | Railway | Set `false` to disable Tier 5 entirely (kill switch) |
| `LOCATIONIQ_CACHE_TTL_DAYS` | Railway | Age in days after which `cached_forward` / `cached_reverse` rows are swept at FastAPI startup; default 90, `0` disables eviction (TD-051) |
| `CLAUDE_COMPLEX_MODEL` | Railway | Default `claude-sonnet-4-6` |
| `CLAUDE_SIMPLE_MODEL` | Railway | Default `claude-haiku-4-5-20251001` |
| `APP_ENV` | Railway | `production` for DAU tracking |
| `DAILY_SALT` | Railway | Random secret for DAU HMAC hashing |
| `DAU_ADMIN_TOKEN` | Railway | Bearer token protecting all `GET /admin/*` analytics endpoints (dau, geography, sessions, hourly, devices, referrers, events, funnel, retention) |
| `GITHUB_TOKEN` | Railway build arg | PAT with Contents:Read — needed for Dockerfile to pull street graph from GitHub Release street-graph-v1 |
| `MAXMIND_LICENSE_KEY` | Railway build arg | Free MaxMind key — Dockerfile downloads GeoLite2-City.mmdb for FEAT-003 (geography). If unset, geography counting silently no-ops at runtime. **Currently unset** to save ~60–80 MB of Railway memory; re-add when traffic warrants restoring city-level analytics. |
| `RESPONSE_CACHE_ENABLED` | Railway | Default `true`. Set `false` to bypass the `/recommend` TTL response cache (~5–25 MB RAM savings). Currently set to `false` to reduce memory while traffic is low; flip back to `true` when caching becomes worth the footprint. |
| `VITE_CONTINENT_PICKER_ENABLED` | Vercel | `true` to flip the continent-first language picker on. Default `false` — flat 27-entry `<select>` renders. Locale set retrenched 2026-05-11 to 27 Chicago-focused languages; flip to `true` once in-browser verification of glyph rendering passes. |
| `VITE_TRANSLATION_FEEDBACK_URL` | Vercel | Override target for the machine-translated review badge feedback link. Default `mailto:wayfarer.atlas@gmail.com?subject=Translation%20issue`. Swap to a GitHub Issues URL if a structured intake is preferred. |
| `VITE_HOUSE_AD_ENABLED` | Vercel | `true` to render the house ad slot below the route list. Default `false` — slot is hidden. Feature Monetization Chunk 1 shipped 2026-05-05 behind this flag. |
| `VITE_HOUSE_AD_URL` | Vercel | Affiliate URL for the house ad. Read at build time (Vite). Leave blank to suppress the slot even when the flag is on. |
| `VITE_HOUSE_AD_TEXT` | Vercel | Editorial-voice copy shown in the house ad slot. Intentionally not translated (affiliate links are typically en-US). |

**Analytics persistent volume:** Add a Railway persistent volume mounted at `/app/data` so the analytics counters (`dau.json`, `geography.json`, `sessions.json`, `hourly.json`, `devices.json`, `referrers.json`, `events.json`, `funnel.json`, `retention.json`) survive container restarts.

---

## Geocoding Strategy

Free-text location resolution lives in `backend/geocoding.py` (Chunk 5, built 2026-05-14) as a five-tier cascade. Each tier returns coords on hit; the caller never sees which tier won.

1. **Coord-pair regex** — `"41.88, -87.63"` bypasses all geocoding
2. **`NEIGHBORHOOD_COORDS` exact match** — curated landmarks dict from `backend/static_data/neighborhoods.json`
3. **Fuzzy `NEIGHBORHOOD_COORDS` match** — ≥0.95 SequenceMatcher similarity + meaningful-word guard
4. **`local_search.forward()`** — FTS5 over the 409k Chicago OSM addresses + 24.5k intersections in `chicago_geocode.db`
5. **LocationIQ `/search`** — hosted fallback, biased to Chicago viewbox with `bounded=1`; results cached durably (positive + negative) in `cached_forward`

Reverse geocoding (`reverse_geocode_point`, also in `geocoding.py`): cached_reverse hit → nearest neighborhood within 200 m (KDTree) → nearest OSM address within 50 m (`local_search.nearest_address`) → LocationIQ `/reverse` → `"lat,lon"` string fallback.

**Implementation notes:**

- `resolve_location(query)` returns `tuple[float, float] | None`. Raises `LocationOutsideChicagoError` (out-of-bbox) or `GeocoderDegradedError` (Tier-5 breaker open) when applicable; `main.py` translates these to 400 / 503 respectively.
- Shared 60→120→240→300s circuit breaker around Tier 5; trips on HTTP 429, probes on first call after cool-off.
- UTC-day cap (`LOCATIONIQ_DAILY_CAP=4900`, configurable) — silent degrade-to-local-only on cap hit; one warning per day. `LOCATIONIQ_ENABLED=false` disables Tier 5 entirely (kill switch).
- PII redaction in logs: typed query text is hashed (`q#abcd1234ef`); coords are quantized to ~1 km.
- Tier-1/2/3 results land in-bbox by construction. Tier-4 (`local_search`) is gated by the in_bbox_only filter; Tier-5 results are bbox-checked at response parse time.
- Cache lives in the same `chicago_geocode.db` SQLite file `local_search` reads — separate read-only + WAL-write connections so concurrent reads never block cache inserts.
- Cache TTL eviction (TD-051, 2026-05-15): `geocoding.evict_cache_older_than(days)` runs once at FastAPI startup via the lifespan hook in `main.py`, deleting `cached_forward` / `cached_reverse` rows whose `fetched_at` is older than `LOCATIONIQ_CACHE_TTL_DAYS` (default 90). Set the env var to `0` to disable eviction. Cheap one-shot `DELETE` per table; the design choice of startup-time (vs background timer) is documented inline since the write rate is bounded by `LOCATIONIQ_DAILY_CAP`.

**Migrating from the old Google flow:** `gtfs_loader.geocode_google`, `reverse_geocode_google`, the monthly call counter, the JSON cache (`geocode_cache.json` + journal + ages sidecar), the daily flush thread, and `_restrict_perms` were all deleted in Chunk 5 (2026-05-14) — pure deletion, no shims. Legacy on-disk cache files (`geocode_cache.json` + journal + ages sidecar + counter) are absorbed into `cached_forward` by `backend/scripts/migrate_geocode_cache.py` (Chunk 10, 2026-05-14); after the maintainer spot-checks the result, `--cleanup` deletes the legacy files. The whole Geocoding & Autocomplete chunked plan **fully shipped 2026-05-15** — see [docs/archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md) for the complete history.

**Local-first geocode corpus (see [FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md) for the full implementation history):**

- The `backend/static_data/chicago_geocode.db` SQLite/FTS5 store holds the address + intersection corpus + the `cached_forward` / `cached_reverse` LocationIQ-hit cache. First build completed 2026-05-12: 55 MB, 409,490 addresses + 24,573 intersections + the FTS5 mirrors.
- Rebuild quarterly by running, in either order:
  - `python backend/scripts/build_address_points.py` — ~5–10 min wall clock; 17 Overpass chunks
  - `python backend/scripts/build_intersections.py` — ~1–3 min wall clock; 2 Overpass queries + Shapely STRtree
- Both scripts are idempotent: they DELETE their target table and rewrite. Safe to rerun anytime.
- DB is gitignored. Local builds only; production builds will pull a published artifact (mechanism TBD).
- `backend/local_search.py` (Chunk 4, built 2026-05-14) is the read-only query layer over the DB plus the in-memory neighborhood + train + bus indexes. Exposes `autocomplete()`, `forward()`, `nearest_address()`, and a cross-street parser. Tier order is `train_station > neighborhood > intersection > bus_stop > address` with a Decision-8 per-tier soft cap (default 3) and cross-tier dedupe. Wired into `geocoding.resolve_location` (Tier 4) since Chunk 5 and into the `/autocomplete` endpoint since Chunk 6. The endpoint response shape is unchanged (`{label, value, type}`) with two new type values that ship for the first time: `address` and `intersection`.
- Frontend (Chunk 7, built 2026-05-14): `frontend/src/components/AddressAutocomplete.jsx` is the generic typeahead (portal-rendered listbox, visualViewport-aware positioning, ARIA combobox 1.1 inline pattern, abort-on-keystroke, out-of-order-response guard, debounce). `frontend/src/lib/autocompleteApi.js` is the thin `fetchAutocomplete(query, { signal })` client over `GET /autocomplete`. `LocationInput.jsx` composes the generic combobox and adds the save-star, save-favorite panel, geo button, and saved-locations dropdown (mutually exclusive with autocomplete results). i18n keys (Chunk 7 shipped English, Chunk 8 shipped 26 non-English translations 2026-05-14, all 27 locales now have parity): `ac_type_address`, `ac_type_intersection`, `ac_type_neighborhood`, `ac_status_searching`, `ac_status_results` / `ac_status_results_plural`, `aria_saved_locations`. The 3 `RESEARCH_LOCALES` (`aii`, `ksw`, `rhg`) get best-effort translations; the runtime `mt_review_notice` banner in Masthead.jsx is shown automatically when any of those locales is active.

---

## Current File Structure

```text
The-Chicago-Routefinder/
├── .gitignore
├── README.md
├── CLAUDE.md                           ← Claude Code project instructions
├── docs/
│   ├── PROJECT_CONTEXT.md              ← This file
│   ├── BUGS.md                         ← Open bugs only; delete entry here when fixed
│   ├── TECH_DEBT.md                    ← Open technical debt only; delete entry here when resolved
│   ├── EFFICIENCY.md                   ← Open efficiency improvements only; delete entry here when implemented
│   ├── FEATURE_PLANS.md                ← Pending features only; delete entry here when shipped
│   ├── SECURITY.md                     ← Open security/dependency findings only (SEC-XXX, DEP-XXX); delete entry here when remediated
│   ├── TODO.md                         ← Tasks requiring human action (accounts, API keys, deploy steps)
│   ├── SMOKE_TESTS.md                  ← One-shot browser-smoke checklist for everything in TODO.md that needs a real browser; delete matching TODO items as boxes go green
│   ├── PRIVACY.md                      ← Privacy notes (mirrored to backend/public_stats.py PRIVACY_TEXT; sync enforced by test_privacy_sync.py)
│   ├── ANALYTICS_MAINTENANCE.md        ← Per-feature analytics-suite maintenance notes (FEAT-001 … FEAT-009)
│   ├── USER_ACQUISITION.md             ← Marketing / growth playbook for getting people to know the app exists and install it
│   ├── design_system.md                ← Standalone design-system reference (Six Principles, voice rules, composition patterns) for new-feature work
│   └── archive/                        ← Frozen historical records (do not append)
│       ├── RESOLVED_HISTORY.md         ← Combined log: Bugs Fixed + Technical Debt Paid Off + Efficiency Improvements Implemented
│       ├── FEATURE_HISTORY.md            ← All implemented features with full chunk-by-chunk detail
│       └── session_changelogs.md       ← All "Notable changes" session logs
├── Human Documentation/
│   ├── Saved Prompts.md                ← Reusable prompts for recurring workflows
│   └── PYTHON_TERMINAL_TEST_STARTUP_INSTRUCTIONS.md  ← How to run backend + frontend locally
├── backend/
│   ├── .env                            ← API keys (never commit)
│   ├── main.py                         ← FastAPI app wiring + lifespan + /recommend, /health, /ping, /autocomplete, /alerts, /reverse-geocode, /stop-arrivals, /last-departure (admin/stats endpoints live in routes/; /schedule endpoints live in schedule.py)
│   ├── rate_limit.py                   ← Per-IP /recommend RPM/RPH + rolling-24h + geocode-bucket sliding-window limiter; _client_ip extractor
│   ├── middleware.py                   ← register_middlewares(): request-size cap, security headers, privacy-preserving analytics dispatcher
│   ├── prompt_builder.py               ← build_prompt() + LANGUAGE_NAMES + crowdedness labels + route/weather/transfer formatting helpers
│   ├── analytics_store.py              ← Shared persistence skeleton (today_chi/data_file/safe_load_json/atomic_write_json) for the 6 daily-aggregate counters
│   ├── routes/
│   │   ├── admin.py                    ← /admin/{dau,geography,sessions,hourly,devices,referrers} APIRouter + DAU_ADMIN_TOKEN gate
│   │   └── stats.py                    ← /stats, /stats/{dau,geography,sessions,hourly,devices,referrers}, /privacy APIRouter (geocode-bucket rate-limited)
│   ├── config.py                       ← Central routing constants (17 named values, all env-var overridable)
│   ├── utils.py                        ← haversine_miles(), SpatialGrid, Chicago bbox constants, chicago_bbox_contains(), METERS_PER_MILE
│   ├── gtfs_loader.py                  ← GTFS stop loader + nearest-station/stop spatial queries + NEIGHBORHOOD_COORDS landmark dict + fuzzy_match_neighborhood lru_cache wrapper. All free-text geocoding now lives in geocoding.py (Chunk 5).
│   ├── geocoding.py                    ← Forward + reverse geocoder cascade (coord→neighborhood→fuzzy→local_search→LocationIQ); shared 60→300s circuit breaker; UTC-day cap; SQLite cached_forward / cached_reverse with NEG_HIT sentinel; LocationOutsideChicagoError + GeocoderDegradedError; PII-redacted logs.
│   ├── local_search.py                 ← Read-only query layer over chicago_geocode.db (FTS5 addresses + intersections) plus in-memory neighborhood + GTFS train/bus indexes. Tier-greedy fill (Decision 8) with per-tier soft cap + cross-tier dedupe; cross-street parser; nearest_address(radius_m).
│   ├── geocode_text.py                 ← Shared text normalization: normalize_street_name/normalize_address (corpus canonicalization), _normalize_street_abbr (query canonicalization), parameterized fuzzy_match_neighborhood. Used by both runtime resolution and ingest scripts. Single source of truth so ingest + query canonicalize identically.
│   ├── transit_graph.py                ← Service-period-tagged NetworkX graph variants (weekday peak / midday / evening / weekend / owl, BUG-051); find_routes()/find_routes_with_status() with optional departure_time; find_bus_transfer_routes(); shape/exit helpers
│   ├── walking.py                      ← igraph street routing; walk_minutes/path/directions; lru_cache; Haversine fallback
│   ├── cta_client.py                   ← Async CTA Train + Bus Tracker clients; alerts feed; shared aiohttp session
│   ├── weather_service.py              ← NWS two-step weather fetch; WeatherContext Pydantic model
│   ├── crowdedness.py                  ← Crowdedness estimator: time-period/day-type enums + psgld-first heuristic
│   ├── route_scoring.py                ← Weather-adjusted ranking weights; prompt-only hint injection
│   ├── dau.py                          ← HMAC-SHA256 privacy-safe DAU counter; batched writes to /app/data/dau.json
│   ├── geography.py                    ← FEAT-003: per-day per-city counter via MaxMind GeoLite2-City; privacy floor + Chicago-metro rollup; /app/data/geography.json
│   ├── sessions.py                     ← FEAT-001: random sid cookie (httpOnly Secure, SameSite=None in prod / Lax in dev, 30-min sliding TTL); idle-finalised session aggregates; /app/data/sessions.json
│   ├── hourly.py                       ← FEAT-004: per-day 24-int /recommend histogram in Chicago tz; /app/data/hourly.json
│   ├── devices.py                      ← FEAT-005: ua-parser-driven mobile/tablet/desktop/bot/unknown buckets; raw UA never persisted; /app/data/devices.json
│   ├── referrers.py                    ← FEAT-008: Referer hostname → direct/search/social/other buckets; path/query stripped pre-storage; /app/data/referrers.json
│   ├── events.py                       ← FEAT-006: allowlisted event-name counter (POST /events); /app/data/events.json
│   ├── funnel.py                       ← FEAT-007: per-day funnel-stage cumulative arrays driven by sessions.py finalisation hooks; /app/data/funnel.json
│   ├── retention.py                    ← FEAT-002: 90-day returnId cookie + Bloom-filter new-vs-returning aggregator; /app/data/retention.json
│   ├── public_stats.py                 ← FEAT-009: public-safe projection of admin counters + /stats HTML page (no third-party scripts) + /privacy text
│   ├── fetch_gtfs.py                   ← Script: download/update CTA GTFS data
│   ├── fetch_street_graph.py           ← Script: build OSMnx street graph + emit igraph pickle
│   ├── fetch_station_exits.py          ← Script: build station_exits.json from Overpass OSM data
│   ├── scripts/                        ← Repo-root-importable utility scripts (ingest, migrations, ops). Run via `python backend/scripts/<name>.py`.
│   │   ├── _geocode_db.py              ← SQLite schema for chicago_geocode.db (addresses, intersections, FTS5 mirrors, cached_forward, cached_reverse); connect() applies schema idempotently. `--init` creates an empty DB.
│   │   ├── build_address_points.py     ← Ingest: Overpass → addresses + addresses_fts. 17 chunks across the main Chicago box + Purple Line corridor. Quarterly rebuild.
│   │   ├── build_intersections.py      ← Ingest: Overpass named highways → Shapely STRtree → intersections + intersections_fts. Quarterly rebuild.
│   │   └── migrate_geocode_cache.py    ← One-shot migrator (Chunk 10 of the Geocoding & Autocomplete plan): legacy geocode_cache.json + journal + ages sidecar → cached_forward rows with bounded synthetic timestamps. Run-once marker, `--force`, `--cleanup`, `--dry-run`.
│   ├── schedule.py                     ← FEAT-018: /schedule/routes + /schedule/{route_id} endpoints + route-category classifier
│   ├── schedule_data/                  ← FEAT-018 build artifacts: per-route schedule JSON + _manifest.json (gitignored payload, regenerated via scripts/build_schedule_index.py)
│   ├── active_routes.py                ← Diagnostic: print all active CTA routes right now
│   ├── railway.toml                    ← Railway deployment config
│   ├── Dockerfile                      ← Railway build recipe; pulls street_graph from GitHub Release at build time
│   ├── requirements.txt
│   ├── station_exits.json              ← ~367 OSM subway entrances for 130 stations; loaded at startup
│   ├── geocode_cache.json              ← Legacy Google geocode cache (gitignored, code reading it removed in Chunk 5 of the Geocoding & Autocomplete plan; on-disk file absorbed into `cached_forward` by `scripts/migrate_geocode_cache.py` 2026-05-14; awaiting maintainer's `--cleanup` invocation to delete)
│   ├── geocode_cache.journal           ← Legacy append-only JSONL delta (gitignored; absorbed by the migrator; deleted via `--cleanup`)
│   ├── geocode_cache_ages.json         ← Legacy per-entry insertion-time sidecar (gitignored; was used as the `fetched_at` source during migration; deleted via `--cleanup`)
│   ├── geocode_counter.json            ← Legacy monthly Google API call counter (gitignored; the counter was retired in Chunk 5 in favor of negative-cache + 429 breaker + `LOCATIONIQ_DAILY_CAP`; on-disk file deleted via `--cleanup`)
│   ├── .geocode_cache_migrated         ← Run-once marker written by `scripts/migrate_geocode_cache.py` (gitignored); blocks re-run without `--force`
│   ├── gtfs_data/                      ← Downloaded GTFS files (gitignored)
│   ├── static_data/                    ← Committed/built fixtures that survive deploys (counterpart to data/ which Railway's persistent volume overlays).
│   │   ├── neighborhoods.json          ← Curated neighborhood/landmark coordinates (NEIGHBORHOOD_COORDS source); human-edited, version-controlled.
│   │   └── chicago_geocode.db          ← Local-first geocoder SQLite/FTS5 store (gitignored, ~55 MB at first build — 409k addresses + 24.5k intersections in the routing bbox; built quarterly by scripts/build_address_points.py + build_intersections.py).
│   ├── street_graph.graphml            ← OSMnx graph source (gitignored, ~227 MB; Chicago + Evanston bbox; built locally by fetch_street_graph.py)
│   └── street_graph_igraph.pkl         ← igraph runtime pickle (gitignored, ~47 MB; hosted on the "street-graph" GitHub Release, fetched at Docker build); preferred over graphml at runtime
├── scripts/
│   ├── build_schedule_index.py         ← FEAT-018: parses backend/gtfs_data/ → emits per-route schedule JSON + manifest into backend/schedule_data/. Re-run after every backend/fetch_gtfs.py refresh.
│   └── translate-missing.mjs           ← Node script: fills in untranslated i18n keys across all non-English locales via Anthropic API (requires ANTHROPIC_API_KEY)
└── frontend/
    ├── index.html                      ← PWA meta tags, theme color, apple-touch-icon
    ├── package.json
    ├── vite.config.js                  ← VitePWA plugin config, manifest, service worker
    ├── .env.local                      ← Local dev env vars (gitignored)
    ├── .env.production                 ← Production env vars — update VITE_BACKEND_URL before deploy
    ├── src/
    │   ├── main.jsx                    ← Entry point; i18n Suspense wrapper
    │   ├── i18n.js                     ← i18next config: 27 active language codes (Chicago-focused; 49 inactive translation files preserved under frontend/locales-archive/ for easy re-enabling), RESEARCH_LOCALES (3 low-resource codes), LANGUAGES_BY_CONTINENT, HttpBackend, LanguageDetector
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
    │   ├── tests/                      ← Vitest + jsdom frontend test suite (45 files, 423 tests)
    │   │   ├── *.test.jsx              ← 27 component tests (covers all non-map top-level + LanguagePicker + SchedulesTool + App.mobile) + 6 JSX-mounted hook tests
    │   │   ├── *.test.js               ← 9 util tests (7 from utils/ + src/ analytics + src/ favorites) + 3 JS-style hook tests
    │   │   └── setup.js                ← jest-dom matcher registration
    │   ├── assets/
    │   │   └── continents/             ← 6 outline SVG silhouettes for the continent-first language picker (Feature LocaleExpansion). stroke=currentColor so they recolor in light/dark/high-contrast modes.
    │   ├── lib/
    │   │   └── autocompleteApi.js      ← fetchAutocomplete(query, { signal }) client over GET /autocomplete (Chunk 7 of the Geocoding & Autocomplete plan); 5s timeout backstop, caller-signal forwarding for abort-on-keystroke
    │   ├── components/
    │   │   ├── AddressAutocomplete.jsx ← Generic typeahead combobox (Chunk 7): portal-rendered listbox, visualViewport-aware positioning for iOS soft-keyboard + bottom-sheet drag, ARIA combobox 1.1 inline pattern, abort-on-keystroke + out-of-order-response guard, debounce, host onOpen/onClose/onInputFocus/onInputBlur callbacks, inputAdornment slot
    │   │   ├── LocationInput.jsx       ← Composes AddressAutocomplete; layers on save-star, save-favorite panel, geo button (with reverse-geocode), saved-locations dropdown (mutually exclusive with autocomplete — autocomplete fires only at ≥2 chars, saved list shows only with empty value)
    │   │   ├── RouteCard.jsx           ← Route card with walk legs, transit legs, pin button; React.memo wrapped
    │   │   ├── PinnedStopsBoard.jsx    ← Live arrivals board for pinned stops
    │   │   ├── WeatherStrip.jsx        ← Compact NWS weather bar; alert amber bar; returns null when weather is null
    │   │   ├── ServiceAlertsBar.jsx    ← CTA service alerts panel: collapsed by default, expand to show cards
    │   │   ├── SettingsPanel.jsx       ← BYOK / AI-toggle / walk-speed dialog
    │   │   ├── Masthead.jsx            ← Newspaper-style header: folio, wordmark, transit-mode/language pickers, machine-translated review badge for low-resource locales
    │   │   ├── LanguagePicker/         ← Continent-first language picker (feature-flagged via VITE_CONTINENT_PICKER_ENABLED) — 2-step flow with continent grid + scoped language list
    │   │   ├── ToolsHub.jsx            ← FEAT-018: Tools tab body — renders the tool-card grid + delegates to a sub-view component when a card is tapped
    │   │   ├── tools/                  ← FEAT-018 sub-views — SavedLocationsTool, SchedulesTool (with SchedulesPicker + SchedulesView), LastTrainTool (reuses SchedulesPicker via its titleKey prop; landing view fetches /last-departure on station-tap). Register new tools by adding an entry to ToolsHub's TOOLS array.
    │   │   └── LoadingSkeleton.jsx     ← Loading skeleton animation
    │   └── MapView.jsx                 ← MapLibre GL JS map; renderPolylines + stop/origin/dest markers; user position dot
    ├── public/
    │   ├── icon-192.png
    │   ├── icon-512.png
    │   ├── icon-512-maskable.png       ← PWA maskable icon (purpose: maskable)
    │   ├── apple-touch-icon.png
    │   └── locales/                    ← 27 active Chicago-focused language JSON files (retrenched 2026-05-11 from 76)
    └── locales-archive/                ← 49 inactive locale JSON files preserved outside the Vite public/ root so they do not ship to production. Re-enable a locale by moving its folder back into public/locales/ and appending a row to LANGUAGES in src/i18n.js.
```

---

## Automated Test Suite

**Combined: 1,099 tests** — backend 676 (pytest, 31 files) + frontend 423 (Vitest + jsdom, 45 files). Count verified 2026-05-18; the suite was last fully green 2026-05-06, with the failures since then catalogued as BUG-059 / BUG-060 / BUG-061 in [`docs/BUGS.md`](BUGS.md).

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
| **Graph routing** | `test_transit_graph.py`, `test_graph_construction.py`, `test_service_periods.py` | Pure helpers (bearing, time parse, dedup) + `_path_to_route` and `find_routes` against hand-built fixture graphs. `test_service_periods.py` covers the BUG-051 service-period machinery: `_select_period` window classification, `_periods_for_trip` post-midnight day-shift, `_select_representative_trips` filter-and-tiebreak, per-variant graph cache lifecycle, and the `find_routes_with_status` dispatch acceptance (Wed 12:00 → `weekday_midday`, Sat 03:00 → `owl`). |
| **Routing accuracy** *(in progress)* | `routing_harness.py`, `test_routing_accuracy.py`, `known_stops.py`, `backend/scripts/probe_route.py` | Determinism harness (`frozen_chicago_now`, `stub_cta_arrivals`, `RoutingScenario` / `run_scenario`, `summarize_route`) covered by 7 smoke tests — complete. Layer-1 golden fixtures (Chicago O/D pairs with expected `primary_modes` / `lines` / `transfers`) are scaffolded but still require human authoring with Chicago rider knowledge; placeholders ship `@pytest.mark.skip`. `known_stops.KNOWN_STOPS` pre-loads CTA L parent stations as `(lat, lon)` constants; `probe_route.py` is a CLI that prints engine output for a candidate OD so an author can sanity-check before pinning an assertion. Open as BUG-052 / TD-BE-005. |
| **CTA API client** | `test_cta_client.py` | Train/Bus/Alerts/Routes parsing with mocked `aiohttp.ClientSession`; CTA dict-vs-list quirks, error sentinels, dedup |
| **FastAPI app** | `test_main_helpers.py`, `test_endpoints.py` | `_cache_key`, rate limiter, prompt builder, `RouteRequest` validators, `/recommend` + `/stop-arrivals` + `/last-departure` contract via `TestClient` |
| **Analytics** | `test_devices.py`, `test_events.py`, `test_funnel.py`, `test_geography.py`, `test_hourly.py`, `test_privacy_sync.py`, `test_public_stats.py`, `test_referrers.py`, `test_retention.py`, `test_sessions.py` | All FEAT-001 through FEAT-009 modules, the `/stats` projection layer, and the privacy-doc sync guard |

### Frontend coverage (`frontend/src/tests/`)

| Layer | What's covered |
| --- | --- |
| **Components (top-level: 24 of 28; plus 2 subdirectory components)** | Covered top-level: AddressAutocomplete, AlertsFilterBar, BottomSheet, ErrorBoundary, LabelSavePanel, LinePill, LoadingSkeleton, LocationInput, Masthead, MobileLayout, PanelSplitter, PinnedStopsBoard, RouteAlertsBanner, RouteCard, SavedRoutesPanel, ServiceAlertsBar, SettingsPanel, SharedRouteBanner, SheetSegmentedControl, SideRail, SignalLamp, TwoToneHeading, WeatherStrip, Wordmark. Subdirectories also covered: `LanguagePicker/LanguagePicker` and `tools/SchedulesTool`. Not covered: AdSlot, ArrivedToast, InstallPrompt, ToolsHub; plus the other four `tools/*` (LastTrainTool, SavedLocationsTool, SchedulesPicker, SchedulesView) and all `markers/*` (5 files — maplibre-dependent). |
| **Utils (7 of 10, plus 2 root-level src/ utilities)** | Covered in `utils/`: deriveTransferPoints, fetchWithRetry, renderMarkdown, routeUtils, sheetSnap, tripGeometry, validateShareInput. Also covered (live in `src/` not `utils/`): analytics, favorites. Not covered: mapLayerLifecycle, mastheadInfo, tripPersistence. |
| **Hooks (9 of 14)** | Covered: useApiQuery, useByokIdleClear, useDocumentLanguage, useFavorites, useLocalStorage, useMediaQuery, useServiceAlerts, useShareLink, useTripTracker. Not covered: useAlertsTabFilter, useCardsColumnWidth, useMapMarker, useRouteLayers, useTransferConnectors (last three maplibre-dependent). |
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

- **maplibre-gl-dependent code** — `MapView.jsx`, `markers/*`, `useMapMarker`, `useRouteLayers`, `useTransferConnectors`. Each would need ~100 lines of brittle WebGL mocks. The right tool is Playwright with a real browser; see [FEATURE_PLANS.md → Consideration — Playwright E2E suite for maplibre + geolocation paths](FEATURE_PLANS.md). (`useTripTracker` is *covered* — its maplibre touches are narrow enough to mock; the genuine map-lifecycle hooks are the three listed.)
- **`App.jsx`** — top-level orchestration. Better tested as E2E than unit.
- **`warm_up()` / live `_build_graph()`** — exercised indirectly via the GTFS-parsing tests of every loader it calls.
- **`find_bus_transfer_routes`** — large, real-graph-dependent. Defer until the bus-to-bus path becomes a reliability concern.

---

## Where to Resume

The app is live on Railway + Vercel. All phases through 6.5 are complete; Feature Heritage, MapMarkers, and NorthExpansion/SouthExpansion shipped 2026-05-01. Feature HeadingTwoTone and Feature ItinerarySpine shipped 2026-05-03, completing the deferred D2 design-system work for panel headings and itinerary leg rows. Feature LocaleExpansion shipped 2026-05-05/06: i18n coverage went from 22 → 76 languages, with a continent-first picker (feature-flagged), a machine-translated review badge for low-resource locales, and Inter-aligned non-Latin web fonts. Locale set retrenched to 27 Chicago-focused languages on 2026-05-11; the 27 active translation files live in `frontend/public/locales/` and the 49 inactive ones are preserved under `frontend/locales-archive/` (outside the Vite `public/` root so they do not ship to production). Re-enable a locale by moving its folder back into `public/locales/` and appending a row to `LANGUAGES` in `frontend/src/i18n.js`.

**Next steps (in order):**

1. (Optional) Add a custom domain in Vercel → Settings → Domains.
2. (Optional) Flip `VITE_CONTINENT_PICKER_ENABLED=true` in a Vercel preview to verify the LocaleExpansion font rendering and continent picker UX before promoting to production. See `docs/TODO.md` for the verification checklist.
3. **Phase 7 — Monetization:** Chunk 1 (`AdSlot`) shipped 2026-05-05 behind `VITE_HOUSE_AD_ENABLED` (default `false`). Outstanding: Vercel-preview QA before flipping the flag in production, plus the Phase 2/2b/3 work documented in `docs/FEATURE_PLANS.md` → Feature Monetization. See "Monetization Strategy — Full Decision Record" below for the canonical decision record.

**Bug status:** 0 🔴 high + 3 🟡 medium + 1 🟢 low — see [`docs/BUGS.md`](BUGS.md).
**Technical debt status:** 1 item open (🟢 low) plus 1 deferred low-priority item (TD-BE-004) — see [`docs/TECH_DEBT.md`](TECH_DEBT.md).

---

## Development Guidelines

- **Never start coding without reading the relevant files first.** The codebase is large and has evolved significantly. Always read the file(s) you plan to edit before writing any changes.
- **Routing accuracy is non-negotiable.** Every bug introduced into the routing engine is a real navigation failure for a real rider. Be conservative with routing changes.
- **The unified NetworkX graph is the canonical routing surface.** `find_bus_routes()` was deprecated and removed by Feature J. All routing goes through `find_routes()` on the unified graph, plus `find_bus_transfer_routes()` for bus+bus transfers. `find_routes_with_status()` (BUG-047) is the typed variant that distinguishes `ok` / `out_of_coverage` / `no_path`; `_run_routing` uses it and propagates a `routing_status` object into both the `/recommend` JSON response and the Claude prompt so out-of-coverage queries surface a clear explanation instead of an unexplained blank. Both routing entry points accept an `effective_speed` parameter (BUG-045) — `_run_routing` passes `walk_speed × _precip_walk_factor(weather)` so Dijkstra derates `edge_type == "walk"` weights via a per-request weight callback (no graph mutation) and selection reflects the rider's actual walking pace in rain, snow, or extreme cold; `_scale_walk_legs()` remains the single authority that scales `WalkLeg.minutes` for display, so the precip factor enters each leg exactly once.
- **The street graph uses igraph, not NetworkX.** `walking.py` loads `street_graph_igraph.pkl` (igraph) not the graphml directly. The KDTree is built from LCC vertices only.
- **BYOK and Rate Limiting are code-complete but OFF by default.** Do not activate them without explicit instruction.
- **i18n is live in 27 languages** (Chicago-focused; retrenched 2026-05-11 from 76). The `LANGUAGES` array in `frontend/src/i18n.js` is the single source of truth — adding a language means adding a row there and dropping a `frontend/public/locales/<code>/translation.json` file. Any new user-facing string in React components must have keys added to all 27 active locale files; run `node scripts/translate-missing.mjs` (with `ANTHROPIC_API_KEY` set) to backfill new keys across every locale at once. The continent-first picker (`VITE_CONTINENT_PICKER_ENABLED`) is wired up but off by default — flip it on in Vercel after in-browser verification of glyph rendering for the non-Latin locales. Three locales (`aii`, `ksw`, `rhg`) are low-resource and surface the machine-translated review badge to riders via the `feedback_link_label` link.
- **When resolving bugs or debt**, delete the entry from `BUGS.md` or `TECH_DEBT.md` and add an entry to `RESOLVED_HISTORY.md`. Do not leave resolved items in the open files.
- **When implementing features**, delete the entry from `FEATURE_PLANS.md` and add an entry to `FEATURE_HISTORY.md`. Do not mark features as ✅ in the plans file; remove them.

---

Session logs → [`docs/archive/session_changelogs.md`](docs/archive/session_changelogs.md). Do not add session logs to this file.
