# CTA Transit PWA — Session Changelogs

All "Notable changes" session entries from `cta_app_handoff_prompt.md`, archived here to keep the main handoff focused on current state.

> **Policy:** All future session notes ("Notable changes") should be appended to this file, NOT added to `cta_app_handoff_prompt.md`. The handoff document describes current state only.

> **Git history:** The full text of these entries also exists in git history on `cta_app_handoff_prompt.md` prior to the 2026-04-28 cleanup commit.

---

## 2026-04-06

Three bugs in `backend/main.py` were fixed before initial deployment:

1. **Async event loop blocking** — `resolve_location`, `_coords_for_location`, and the Anthropic call all now run off the event loop (`run_in_executor` / `AsyncAnthropic`). Server handles concurrent requests correctly.
2. **Out-of-coverage destination** — If the destination geocodes but has no CTA stops nearby, a clear 400 is returned explaining the coverage boundary. Previously the app silently returned empty results.
3. **Anthropic client singleton** — `_claude_client = anthropic.AsyncAnthropic(...)` is now instantiated once at module level instead of on every request.

---

## 2026-04-08

1. **Workbox production URL** — `vite.config.js` `runtimeCaching` pattern updated from `http://localhost:8000/.*` to `/\/(recommend|health)/` so the `NetworkOnly` rule applies to the Railway production URL.
2. **Stale comment removed** — `cta_client.py` module docstring updated; old Phase 4 TODO comment about bus stop IDs removed.
3. **Tech stack corrected** — Handoff tech stack section updated; `gtfs_kit`, `pandas`, `shapely` removed (not used — direct CSV parsing is used instead).
4. **`max_tokens` raised to 750** — Was 300. Raised for testing. *(Subsequently lowered to 400 to align with "3-4 sentences" prompt instruction — session 2026-04-10.)*
5. **Frontend request timeout removed** — `App.jsx` no longer imposes a 15-second `AbortController` timeout. *(An `AbortController` was subsequently re-added as a race condition guard on re-submit — session 2026-04-10.)*
6. **Rate limiting deferred** — Noted in documentation; intentionally not implemented during testing phase.

---

## 2026-04-09 — Off-peak trip selection + structured bus route cards

1. **Off-peak trip selection fixed** — `transit_graph.py`: `_load_weekday_service_ids()` added; `_load_representative_trips()` now loads all weekday candidate trips per direction; `_stream_stop_sequences()` selects the trip whose first-stop arrival is closest to noon per line/direction.
2. **Structured bus route cards built** — `transit_graph.py`: `get_bus_stop_sequences()` builds a `{(route_short_name, direction_id): [(stop_id, stop_name, lat, lon, arr_minutes), ...]}` table at startup. `find_bus_routes()` computes `Route` objects from live bus arrivals using stop_id-based direction resolution. `main.py`: train and bus routes merged into one ranked list, capped at 5; `_format_train_routes` renamed `_format_routes`; `line_code` added to leg serialization. `cta_client.py`: `stop_id` added to bus arrival dicts.
3. **Bus direction resolution confirmed** — stop_id approach correctly identifies southbound (and all directions) without any direction-string-to-direction_id mapping.
4. **Geocoding upgrade triggered** — Nominatim returns wrong/missing results for landmarks. Google Maps Geocoding API upgrade planned.
5. **Bus direction colors added** — `App.jsx`: `BUS_DIRECTION_COLORS` added for Northbound/Southbound/Eastbound/Westbound; bus leg pill shows route number (`line_code`) with direction-based color.
6. **`osmnx` import fixed** — `walking.py`: `import osmnx as ox` moved to module level.
7. **Bus stop ID batching fixed** — `cta_client.py`: `get_bus_arrivals()` now splits stop IDs into chunks of 10 and fires all chunks concurrently via `asyncio.gather`.
8. **`psgld` normalization added; Bus Fullness filter hidden** — `cta_client.py`: raw `psgld` value normalized to `UPPER_SNAKE` at read time. Live API testing confirmed CTA does not currently populate `psgld` — Bus Fullness `<select>` commented out in `App.jsx`.

---

## 2026-04-09 — Walk directions + enhancements

1. **Street-level walk directions** — `walking.py`: new `walk_directions(origin_lat, origin_lon, dest_lat, dest_lon) -> list[dict]` (lru_cache 512). Uses OSMnx shortest path, reads edge `name` + `length`, groups consecutive same-street edges, computes cardinal bearing per group, returns `[{"street": "Broadway", "direction": "S", "minutes": 1.2}, ...]`. Falls back to single unnamed step on error.
2. **`WalkLeg.directions` field** — `transit_graph.py`: `WalkLeg` gains `directions: list` field. `walk_directions` called on all walk legs.
3. **Directions serialized** — `main.py`: `"directions": leg.directions` added to walk leg in `/recommend` response.
4. **Steps toggle in route cards** — `RouteCard.jsx`: walk legs render as `WalkLegItem`. Single-step legs render inline (no toggle). Multi-step legs use expand/collapse toggle.

---

## 2026-04-09 — Pre-deployment bug fixes

1. **Claude API error handling** — `backend/main.py`: `_claude_client.messages.create()` wrapped in try/except; response text extracted safely; raises HTTP 502 on failure.
2. **Train direction-aware arrival lookup** — `backend/main.py` + `backend/transit_graph.py`: `_build_arrival_lookup` now returns `{(line_code, mapid): {destNm: minutes}}`. `_rank_routes` uses a dot-product bearing test to select correct direction from live arrivals.
3. **Frontend non-JSON error handling** — `frontend/src/App.jsx`: non-OK responses attempt `res.json()` in a try/catch; HTML gateway errors fall back to `"Service error (502 Bad Gateway)"`.

---

## 2026-04-09 — Google Maps geocoding

1. **Google Maps Geocoding API implemented** — `gtfs_loader.py`: `geocode_nominatim()` replaced with `geocode_google()`. API call uses Chicago bounding box bias + `components=country:US`. Persistent disk cache unchanged.
2. **Monthly geocode rate limiter added** — `_GEOCODE_CALL_LIMIT` defaults to 9,500 calls/month. Counter persisted to `geocode_counter.json`, resets automatically each calendar month. *(Promoted to proper env-var config `GEOCODE_MONTHLY_LIMIT` in TD-003, 2026-04-20.)*

---

## 2026-04-09 — Map feature Phase 5.6 complete

All 10 chunks of MAP_IMPLEMENTATION_PLAN.md implemented. Full map feature is live.

**Backend (Chunks 1–4):**
1. **GTFS shape lookup** — `transit_graph.py`: `_build_shape_lookup()` builds module-level `_shape_lookup` dict. Public API: `get_shape(route_id, direction_id)`.
2. **Shape clipping** — `transit_graph.py`: `clip_shape(shape_points, board_lat, board_lon, exit_lat, exit_lon)` returns the slice between boarding and exit points.
3. **Walk path geometry** — `walking.py`: `walk_path(origin_lat, origin_lon, dest_lat, dest_lon)` returns street-network path as `[[lat, lon], ...]`. lru_cache 512. Falls back to straight line.
4. **Geometry in API response** — `WalkLeg` gains `path_points`, `TransitLeg` gains `shape_points`. Transit edges store `direction_id`. `/recommend` response includes `shape`, `path`, `from_coords`, `to_coords` per leg and `origin_coords`, `dest_coords` at top level.

**Frontend (Chunks 5–10):**
5. **MapLibre + layout** — `maplibre-gl` installed; `App.jsx` restructured into `.layout.layout--split` with `.panel-cards` (40%) and `.panel-map` (60%). 800px breakpoint stacks vertically.
6. **TransitPhoto** — `PHOTOS` manifest in `App.jsx`. Random photo on mount, fades out when routes arrive.
7. **MapView init** — `MapView.jsx` created. All interaction handlers disabled by default. "🔓 Unlock map" button re-enables on click.
8. **Route rendering** — Two-pass: lines first (walk dashed gray, transit solid colored), then markers. `fitBounds({ padding: 60, animate: false })` after every render.
9. **Route card ↔ map** — `selectedRouteIndex` state in `App`. Clicking a card selects it and snaps the map to that route.
10. **Demo files deleted** — All `demo-*.html` files removed from repo root.

---

## 2026-04-10 — Comprehensive bug audit

A full two-pass bug audit across all backend and frontend files. All bugs documented in `BUGS_TO_BE_FIXED.md` were subsequently fixed.

**Fixed immediately:**
- **`load_dotenv()` import-order bug** — `backend/main.py`: `load_dotenv()` was called after `from gtfs_loader import ...`, meaning the Google Maps API key was always `""` regardless of `.env` contents. Fixed by moving `load_dotenv()` before local imports.

**🟡 Medium bugs catalogued and fixed (session 2026-04-10 batches):**
- `line-cap`/`line-join` placed in MapLibre `paint` instead of `layout` in `MapView.jsx`
- `wait_minutes === 0` ("Due") shows no indicator in `RouteCard`
- No `AbortController` on the `/recommend` fetch — race condition on re-submit
- PWA `globPatterns` includes all `*.png` files

**🟢 Low bugs catalogued and fixed:**
- `renderMarkdown` strips `**bold**` but not `*italic*`
- `_load_weekday_service_ids()` only checks Mon + Tue + Wed
- Train arrival datetime `.replace(tzinfo=...)` wrong for ISO strings with UTC offset
- Destination walk times computed in wrong direction
- `validate_and_report()` uses `encoding="utf-8"` instead of `"utf-8-sig"`
- `photoFadeTimer` ref not cleared on `App` unmount
- Routing exceptions swallow traceback
- Missing `CTA_BUS_API_KEY` validation when bus mode requested
- `max_tokens=750` misaligned with "3-4 sentences" prompt
- PWA manifest combined `"any maskable"` icon entry
- No validation when origin and destination resolve to the same location
- `G_base.copy()` called on every train routing request
- `_coords_for_location()` duplicates fuzzy-match logic from `resolve_location()`
- Redundant `walk_minutes` recomputation for destination stations
- Bus routing wrong direction sequence for stops served by multiple directions

---

## 2026-04-10 — Bug fix batches 1–3

**Batch 1 — 🟡 Frontend correctness:**
1. **`line-cap`/`line-join` moved to `layout`** — `MapView.jsx`: transit polylines now render with rounded caps and joins.
2. **`wait_minutes === 0` "Due now" indicator** — `App.jsx`: `RouteCard` now distinguishes `null` (no data), `0` ("Due now"), and `> 0` ("N min wait").
3. **`AbortController` race condition** — `App.jsx`: in-flight `/recommend` fetch is cancelled on re-submit; `AbortError` silently discarded.

**Batch 2 — 🟢 Quick fixes:**
4. **`renderMarkdown` italic stripping** — `App.jsx`: `*italic*` and `_italic_` now stripped.
5. **`photoFadeTimer` unmount cleanup** — `App.jsx`: `useEffect` cleanup cancels pending fade timer.
6. **Routing exception tracebacks** — `main.py`: both routing `except` blocks now call `traceback.print_exc()`.
7. **`CTA_BUS_API_KEY` validation** — `main.py`: raises HTTP 500 if bus key missing when bus mode requested.
8. **`validate_and_report()` encoding** — `fetch_gtfs.py`: `"utf-8"` → `"utf-8-sig"`.
9. **`max_tokens` re-aligned** — `main.py`: 750 → 400 to match "3-4 sentences" prompt.
10. **PWA manifest icon split** — `vite.config.js`: 512px icon split into `purpose: "any"` and `purpose: "maskable"` entries.
11. **Origin = destination guard** — `main.py`: returns HTTP 400 if resolved coords are within ~100m.

**Batch 3 — 🟢 Backend correctness:**
12. **`_load_weekday_service_ids()` full Mon–Fri check** — `transit_graph.py`: condition now checks all five weekday columns via `all(...)`.
13. **Train arrival datetime timezone handling** — `cta_client.py`: ISO strings with existing `tzinfo` converted via `.astimezone()` instead of `.replace()`.
14. **Destination walk direction** — `gtfs_loader.py` + `transit_graph.py`: `find_nearest_train_stations` gained `walk_to_station=False` parameter; walk computed station→destination (not destination→station).

---

## 2026-04-11 — Routing radius fixes + multi-leg bus scoped

1. **Train routing: progressive station radius expansion** — `transit_graph.py` `find_routes()`: both origin and destination station searches now use a progressive-expansion loop (0.25 → 0.5 → 0.75 → ... → 2.0 miles, +0.25 per step). Previously a hard 0.5-mile cap caused `dest_stations` to come back empty for addresses like "4201 N Troy Ave".
2. **Bus routing: progressive exit-stop threshold expansion** — `transit_graph.py` `find_bus_routes()`: the hard 0.5-mile exit-stop cutoff replaced with the same progressive-expansion approach. Restructured into two passes: Pass 1 collects the best exit stop per route+direction using haversine only; Pass 2 builds Route objects (OSMnx walk calls) only for surviving candidates.
3. **Multi-leg bus routing scoped** — Documented as Feature C in `FEATURE_IMPLEMENTATION_PLANS.md`.
4. **Multi-leg train routing gaps documented** — Train-to-train routing with line changes IS implemented. Documented two gaps: (a) shared-track edge deduplication can mis-label the line; (b) bus access to a better-positioned station not considered (addressed by Feature B).

---

## 2026-04-11 — Bug fix batch 4

1. **PWA `globPatterns` pre-cache fix** — `vite.config.js`: `globPatterns` now lists `icon-*.png` explicitly. `StaleWhileRevalidate` runtime cache added for `/transit-photos/`.
2. **Thread-local graph copy** — `transit_graph.py`: `find_routes()` keeps a thread-local copy of `G_base` (keyed by `id(G_base)`) created once per executor thread. Virtual nodes added before routing and removed in a `finally` block.
3. **`fuzzy_match_neighborhood()` shared helper** — `gtfs_loader.py`: `_FUZZY_STOP_WORDS` and `fuzzy_match_neighborhood()` extracted as a public module-level helper. `main.py` imports it. Single source of truth for threshold (0.95) and stop-word list.
4. **Redundant `walk_minutes` recomputation removed** — `transit_graph.py` `find_routes()`: `dest_walk` is populated once from values already computed by `find_nearest_train_stations(walk_to_station=False)`.
5. **Bus routing multi-direction `board_index` fix** — `transit_graph.py` `find_bus_routes()`: `board_index` type changed from `dict[str, tuple]` to `dict[str, list[tuple]]`; both direction entries stored when a stop appears in sequences for both directions.

---

## 2026-04-13 — Feature A — Train Station Exit Guidance (all 5 chunks)

1. **`fetch_station_exits.py` written + `station_exits.json` generated** — One-time script queries Overpass API for all `railway=subway_entrance` OSM nodes in Chicago's bounding box, matches each entrance to nearest CTA parent station by haversine (max 0.20 mi), writes `backend/station_exits.json`. Produced 367 exits across 130 of 143 parent stations.
2. **Exit data loaded at module import** (`transit_graph.py`) — Module-level `_station_exits: dict[str, list[dict]]` populated by `_load_station_exits()`. Logs entry count on startup. Returns `{}` gracefully if file is absent.
3. **`best_exit()` added** (`transit_graph.py`) — Scores all known exits for a station by `street_walk_minutes(exit_lat, exit_lon, dest_lat, dest_lon)` and returns the minimum-time exit dict with `walk_minutes` key.
4. **Exit threaded into walk legs** (`transit_graph.py`, `main.py`) — `WalkLeg` dataclass gains `exit_label: str = ""`. Destination walk leg calls `best_exit(from_node, dest_lat, dest_lon)`: if found, exit `(lat, lon)` replaces the station centroid as the walk origin. `main.py` serializes `"exit_label"`.
5. **Exit label displayed** (`App.jsx`, `App.css`) — `WalkLegItem` shows `Exit: <label>` in muted secondary text when `leg.exit_label` is present and `leg.to === "Your destination"`.

---

## 2026-04-13 — Feature E — Walk Leg Street-Level Distance Detail (both chunks)

1. **`_CHICAGO_BLOCK_METERS`, `_DIRECTION_FULL` added** — `walking.py`: `_CHICAGO_BLOCK_METERS = 80.0` and `_DIRECTION_FULL` dict (N→"North", NE→"Northeast", etc.) added at module level.
2. **`blocks` and `direction_full` added to each step dict** — `walking.py` `walk_directions()`: each step computes `blocks = max(0.5, round(total_length / 80.0 * 2) / 2)` and looks up `direction_full`. Both added to step dict.
3. **Step rendering replaced** — `App.jsx`: `DIRECTION_ARROWS` constant removed. `formatBlocks(b)` helper added. `WalkLegItem` step now renders: `{si === 0 ? "Walk" : "Head"} {direction_full} along {street} for {blocks}`.
4. **Obsolete CSS rules removed** — `App.css`: `.leg-step-arrow`, `.leg-step-dir`, and `.leg-step-time` rule blocks removed.

---

## 2026-04-13 — Feature C — Multi-Leg Bus Routing (all 5 chunks)

1. **Bus stop spatial grid index** — `transit_graph.py`: module-level `_bus_stop_grid` + `_bus_stop_coords` populated at import time. `_stops_near(lat, lon, radius_miles=0.25)` helper using 0.005° grid cells, haversine post-filter.
2. **Stop-to-routes index** — `transit_graph.py`: module-level `_stop_to_routes: dict[str, list[tuple]]` built by `_build_stop_to_routes()`. Enables O(1) "which routes serve stop X?" lookup.
3. **Transfer candidate algorithm** — `transit_graph.py`: new `find_bus_transfer_routes()`. Two-pass: Pass 1 identifies candidate transfer stops (haversine + `_stops_near` + `_stop_to_routes`); Pass 2 builds 5-leg `Route` objects via OSMnx for surviving candidates. Leg-2 wait estimated at 7.5 min (fixed). Routes pruned at 90 min.
4. **Integration** — `main.py`: `find_bus_transfer_routes` imported. Called when `find_bus_routes()` returns an empty list and `transit_mode` is Bus or All.
5. **Frontend verification** — 5-leg route cards, zero-minute same-stop transfer, map dual-color bus segments all confirmed working.

---

## 2026-04-13 — Feature F — Street Abbreviation Normalization

1. **`import re` added** — `gtfs_loader.py`.
2. **`_ABBR_MAP`, `_STREET_ABBR_RE`, `_normalize_street_abbr()` added** — Maps 15 USPS suffix abbreviations (blvd, pkwy, expy, terr, ter, hwy, ave, cir, st, dr, ln, ct, rd, pl, sq) to full forms. Sorted keys longest-first. Word-boundary-anchored case-insensitive regex with or without trailing period.
3. **`resolve_location()` updated** — Normalization applied before `geocode_google()` call so cache key is stable regardless of user-typed abbreviations.
4. **Directional prefixes intentionally excluded** — N, S, E, W, NW, NE, SW, SE not expanded (Google Maps handles them correctly; they appear in station names like "North/Clybourn").

---

## 2026-04-13 — Claude Response Caching

In-memory response caching implemented in `main.py`. Repeat `/recommend` requests skip all upstream I/O within a 45-second TTL window.

1. **`import time` added** — for `time.monotonic()`.
2. **`_response_cache`, `_CACHE_TTL_SECONDS`, `_CACHE_MAX_SIZE` added** — `_response_cache: dict[str, tuple[float, dict]] = {}`, TTL 45 s, max 500 entries.
3. **`_cache_key()` helper** — Normalizes `RouteRequest` fields into a `"|"`-delimited string.
4. **Cache check wired** — Cache lookup before any I/O; on hit returns with `"cache_hit": True` merged in. Stale entries evicted inline on miss.
5. **Cache write wired** — Response stored with `expires_at = monotonic() + 45`. If cache exceeds 500 entries, entry nearest expiry evicted before inserting.

---

## 2026-04-14 — Rate Limiting + BYOK

1. **Rate limiting added to `/recommend`** — `main.py`: `_RATE_LIMIT_ENABLED` (default `false`), `_RATE_LIMIT_RPM` (10/min per IP), `_RATE_LIMIT_RPH` (50/hr per IP). `_rate_store: dict[str, collections.deque]`. `_check_rate_limit(ip)` sliding-window check. Raises HTTP 429 on rejection. **Activate: `RATE_LIMIT_ENABLED=true` in Railway.**
2. **BYOK implemented end-to-end** — `main.py`: `_BYOK_ENABLED` (default `false`). `anthropic_api_key: str | None = None` in `RouteRequest` with `@field_validator` (trims whitespace, rejects non-`"sk-ant-"` values). Per-request `AsyncAnthropic(api_key=byok_key)` when BYOK key is set. **Activate: `BYOK_ENABLED=true` (Railway) + `VITE_BYOK_ENABLED=true` (Vercel).**
3. **BYOK settings panel** — `App.jsx`, `App.css`: `BYOK_ENABLED = import.meta.env.VITE_BYOK_ENABLED === "true"` compile-time flag. `SettingsPanel` component with `type="password"` input, inline validation, Save / Remove key buttons. Key stored in `sessionStorage` (clears on tab close). BYOK key spread into fetch body only when `BYOK_ENABLED && byokKey`.

---

## 2026-04-15 — 22 Bug Fixes + Production Deployment Fixes

**Production deployment fixes:**
1. **`/recommend` returned 404 on production** — `VITE_BACKEND_URL` was missing the `https://` prefix in the Vercel dashboard. Updated to full URL; `.env.production` corrected.
2. **Preview deployment URLs returned 401 on `manifest.webmanifest`** — Vercel Deployment Protection settings adjusted.

**Backend bug fixes:**
1. `_save_geocode_cache` — write-through replaced with dirty-flag + background-flush (30s daemon thread + atexit handler). *(Further optimized OPT-003: appends only new entries as JSONL to `geocode_cache.journal`.)*
2. `_fetch_bus_chunk` — returns sentinel `[{"_error": True, ...}]` on exception instead of `[]`.
3. `_rank_routes` — removed dead `dest_lat`/`dest_lon` parameters.
4. `_response_cache` — changed from `dict` to `collections.OrderedDict`; eviction uses `popitem(last=False)` (O(1)).
5. `_rate_store` — eviction loop keeps deques lean; empty deques retained.
6. BYOK cache collision — `_cache_key()` appends `"byok"` suffix when BYOK key present.
7. `prdctdn.isdigit()` — fixed `None` crash: `prd.get("prdctdn") or ""`.
8. `find_nearest_train_stations` / `find_nearest_bus_stops` — replaced full-catalog Haversine scan with `_spatial_index` grid/bucket. ~300× faster at 0.25-mi bus lookup.
9. `_save_geocode_counter` — atomic rename pattern added.
10. `_normalize_street_abbr` — added `(?=\s*(?:,|$))` lookahead to prevent false matches inside saint names.
11. `fuzzy_match_neighborhood` — `@lru_cache(maxsize=1024)` added; precomputed word→keys inverted index; `quick_ratio()` prefilter; 0.99 early-exit.
12. `min(G[u][v].values(), ...)` — changed `d.get("length", 0)` to `d.get("length", float("inf"))` so zero-length edges no longer win.
13. `walk_directions` fallback — always uses `"long"` block type.
14. `lru_cache` mutable-return warning comments added to `walk_minutes`, `walk_directions`, `walk_path`.
15. `get_station_by_name` — `@lru_cache(maxsize=512)` added.
16. Bus shape lookup — `_build_shape_lookup` now writes both `(route_id, direction_id)` and `(short_name, direction_id)` keys unconditionally.
17. Both `_stream_stop_sequences` and `get_bus_stop_sequences` use `defaultdict(list)`.
18. Transit edges — removed dead `all_routes=candidates` from `G.add_edge(...)`.

**Frontend bug fixes:**
19. BYOK API key — `localStorage` → `sessionStorage`.
20. `busFullness` dead state — removed.
21. `RouteCard` expanded state — `searchIdRef` counter; cards keyed `${searchId}-${i}` to reset on new search.
22. `TransitPhoto` onError — `failed` state; returns `null` on image load error.
23. `clearRouteLayers` — uses explicit `routeLayerIds`/`routeSourceIds` refs; works even when style is reloading.

---

## 2026-04-16 — Feature B — Intermodal Routing (Train + Bus in One Trip)

All 6 chunks implemented. Train+bus intermodal routes now surfaced automatically.

1. **Bus stop nodes added** — `_build_graph()`: ~11,000 bus stop nodes added with `node_type="bus"`.
2. **Bus transit edges added** — ~50,000+ directed bus transit edges added (`mode="bus"`, `line_code=route_short_name`).
3. **Train↔bus transfer walk edges** — Bidirectional walk edges between each train station and bus stops within 0.15 miles / ≤5 min street walk.
4. **`_resolve_node()` helper** — Resolves `(name, lat, lon)` for any node type.
5. **`_path_to_route()` updated** — New `edge_type == "walk"` handler for mid-path train↔bus transfers.
6. **`find_routes()` bus virtual edges** — `ORIGIN→bus_stop` and `bus_stop→DEST` virtual walk edges added.
7. **`warm_up()` graph size log** — Logs `Graph size: N nodes, M edges` after `_build_graph()`.
8. **`main.py` updates** — `find_routes()` called with `n_routes=5`; `_route_fingerprint()` deduplication added.

---

## 2026-04-16 — Unified stop_times stream + bus wait correctness

1. **Unified `stop_times.txt` stream** — `transit_graph.py`: `_stream_all_stop_sequences` processes train and bus trips in a single pass. Saves ~7–10 s on cold start.
2. **Bus wait normalisation** — `main.py`: `_rank_bus_routes()` added. Bus routes now express `wait` as `int | None` (0=Due, N=min away, None=no data) matching `_rank_routes()` output.

---

## 2026-04-17 — Feature I — CTA Alerts Integration (all 3 chunks)

1. **`get_alerts()` + helpers added to `cta_client.py`** — `ALERTS_BASE`, `_TRAIN_LINE_TO_ALERT_ID`, `_fetch_alerts_for_route()` (5s timeout; returns `[]` on error), and `get_alerts()` (concurrent gather, dedup by `alert_id`, sort by `severity_score` descending). No API key required.
2. **Alerts wired into `/recommend`** — `main.py`: `_alert_ids_from_routes()` helper extracts Alert API ids from all `TransitLeg`s. `get_alerts()` called after routing. `build_prompt()` gained `alerts` parameter — alerts with `severity_score >= 5` appended as "Active service alerts" block. `alerts` key added to response payload.
3. **Alert banners added to `App.jsx`** — Major alerts (`is_major: true`) get red left border; minor alerts get yellow border. Impact type shown in muted uppercase. Capped at 3 with "and N more" link.

---

## 2026-04-18 — Feature D — Live Arrivals at Transfer Stop (all 4 chunks)

1. **`transfer_wait_minutes` field added to `TransitLeg`** — `transit_graph.py`: new `transfer_wait_minutes: int | None = None` field. Defaults to `None` for non-transfer legs.
2. **`_pick_wait()` helper extracted** — `main.py`: dot-product bearing-test logic extracted as standalone `_pick_wait(dest_map, from_mapid, to_mapid) -> int | None`. Both `_rank_routes()` and transfer annotation loop use it.
3. **Transfer stop extraction and concurrent fetch** — `main.py`: `async def _empty()` no-op coroutine; `_extract_transfer_stops(ranked_routes)` scans all routes for transfer `TransitLeg`s; `asyncio.gather(get_train_arrivals(...), get_bus_arrivals(...))` ~300ms concurrent round-trip.
4. **Transfer legs annotated in-place** — `main.py`: `_build_bus_transfer_lookup(arrivals)` for bus transfer stops. Loops over ranked routes and annotates each transfer `TransitLeg.transfer_wait_minutes`.
5. **Claude prompt extended** — `main.py`: `_format_transfer_arrivals(arrivals)` groups by stop name. `build_prompt()` gained `transfer_arrivals` param; injects "Live arrivals at transfer stop(s):" section when non-empty.
6. **Frontend transfer wait badge** — `App.jsx`: `RouteLegs` renders `⏱ Due` or `⏱ N min wait` above the transit leg pill for transfer boarding legs. `.transfer-wait-note { display: block; color: #888; font-size: 0.75rem }` added to `App.css`.

---

## 2026-04-18 — `_ABBR_MAP` duplicate-key vulnerability hardened

1. **`_ABBR_MAP` converted to pair-tuple + built dict** — `gtfs_loader.py`: defined as `_ABBR_PAIRS: tuple[tuple[str, str], ...]`; `_ABBR_MAP = dict(_ABBR_PAIRS)`.
2. **Import-time assertion** — `assert len(_ABBR_MAP) == len(_ABBR_PAIRS)` raises at module import if any abbreviation is listed twice.
3. **Downstream usage unchanged** — `_sorted_abbrs`, `_STREET_ABBR_RE`, `_expand()` continue to read from `_ABBR_MAP`.

---

## 2026-04-18 — Bus-mode transfer routing always runs

1. **Transfer branch always runs in `transit_mode="Bus"`** — `main.py`: removed the `if not bus_ranked:` gate. Bus mode now calls both `find_bus_routes()` (via unified graph) and `find_bus_transfer_routes()` unconditionally, concatenates results, then sort + top-5 + fingerprint-dedup.
2. **Transfer candidate count lowered 3 → 2** — Cost-control measure since transfer call now runs on every Bus-mode request.
3. **In `transit_mode="All"` original emptiness-gated fallback retained** — unified train graph provides intermodal backstop; transfer call is latency-expensive.

---

## 2026-04-18 — Bug fix batch 5

1. **BUG-001 fixed** — `fetch_station_exits.py`: expanded `try` block to cover `float(stop_lat)` / `float(stop_lon)` and dict assignment. Catches `(ValueError, KeyError)`.
2. **BUG-002 fixed** — `fetch_gtfs.py`: changed `rows = sum(1 for _ in fh) - 1` to `rows = max(0, sum(1 for _ in fh) - 1)`.
3. **BUG-008 fixed** — `App.jsx`: added `|| ""` guard at the `renderMarkdown` call site.
4. **BUG-003 investigated — false positive, no fix** — `walking.py` `_cardinal()`: `math.atan2(dlon, dlat)` is mathematically correct for clockwise compass bearing from north. The suggested `atan2(dlat, dlon)` would swap North and East. Closed.

---

## 2026-04-18 — Efficiency improvements OPT-012/013/014/018

1. **Persistent HTTP session for geocoding (OPT-012)** — `gtfs_loader.py`: module-level `_http_session = requests.Session()`. `geocode_google()` reuses keep-alive TCP/SSL connection.
2. **`heapq.nsmallest` replaces full sort (OPT-013)** — `gtfs_loader.py`: `find_nearest_train_stations()` and `find_nearest_bus_stops()` use `heapq.nsmallest(max_results, hits, key=...)`. O(n log k) vs O(n log n). `import heapq` added.
3. **Original query string preserved as `matched_name` (OPT-014)** — `gtfs_loader.py`: `original_query = query.strip()` captured before lowercasing. Both exact-match and geocoding branches return `original_query` as `matched_name`.
4. **`legColor(leg)` computed once per transit leg (OPT-018)** — `MapView.jsx`: `const legColors = legs.map(...)` precomputed before Pass 1 loop. Two object-lookup chains per transit leg per render eliminated.

---

## 2026-04-20 — TD-002 — `recommend()` decomposed into focused helpers

1. **Seven focused helpers extracted** — `backend/main.py`: `_validate_api_keys()`, `_resolve_locations()`, `_fetch_arrivals()`, `_run_routing()`, `_fetch_transfer_arrivals()`, `_call_claude()`, `_format_response()`.
2. **`recommend()` is now an ~85-line thin coordinator** — rate-limit check → BYOK client selection → cache check → sequential helper calls → cache write → return. No behavior change.

---

## 2026-04-20 — `_rate_store` + `_response_cache` race condition fixed

1. **`_store_lock = asyncio.Lock()` added** — Single module-level `asyncio.Lock` protects both `_rate_store` and `_response_cache`.
2. **Rate-limit check + cache read wrapped in `async with _store_lock:`** — Prevents concurrent requests with the same cache key from both seeing a miss and launching the full expensive pipeline (stampede).
3. **Cache write wrapped in a second `async with _store_lock:`** — Prevents two concurrent responses both seeing `len > _CACHE_MAX_SIZE` and each evicting a different entry (double-pop).
4. **`_check_rate_limit` docstring updated** — "Callers must hold `_store_lock` before calling this function."

---

## 2026-04-20 — Technical debt TD-010 through TD-014 resolved

1. **`SpatialGrid` class extracted to `utils.py` (TD-010)** — Generic cell-based spatial index replacing two independent implementations in `gtfs_loader.py` and `transit_graph.py`.
2. **Magic numbers named and moved to module level (TD-011)** — `main.py`: `_SAME_LOCATION_THRESHOLD_DEG2`. `transit_graph.py`: seven function-local constants to module level with named sections.
3. **`lru_cache` mutable-list latent bug fixed (TD-012)** — `walk_directions` and `walk_path` renamed to private `_walk_directions_impl` / `_walk_path_impl` (still `@lru_cache`, return immutable tuples). Public wrappers return fresh lists.
4. **Module-level globals lifecycle documented (TD-013)** — Added "Module-level state — initialization contract" comment block to `transit_graph.py`.
5. **Street-graph bounding-box expansion TODO replaced with actionable checklist (TD-014)** — `utils.py`: four-step expansion guide documenting coverage bounds, target coordinates, and Railway memory check.

---

## 2026-04-20 — Efficiency improvement OPT-010

Pre-computed entrance and station trig in `fetch_station_exits.py`.

1. **Station trig pre-computed at load time (OPT-010a)** — `load_parent_stations()` stores `rlat`, `rlon`, `cos_lat` alongside each station. Each station pays `radians` + `cos` once instead of once per entrance.
2. **Entrance trig pre-computed before inner loop (OPT-010b)** — In `build_exits`, entrance radians and `cos(rlat)` computed once per entrance before the inner station loop.
3. **Local `_haversine_precomputed` helper** — Accepts pre-converted radians directly, skipping `math.radians`/`math.cos` in inner loop.

Eliminates ~450k redundant trig operations across a full dataset run.

---

## 2026-04-22 — Minimum transfer-walk floor

1. **`_build_graph()` intermodal walk edges** — `transit_graph.py`: `walk_min = max(walk_min, _TRANSFER_MINUTES)` applied after Haversine estimate and before the `_TRANSFER_WALK_CAP_MIN` gate.
2. **`_build_transfer_routes()` bus-to-bus transfers** — `transit_graph.py`: `transfer_walk_min = max(transfer_walk_min, _TRANSFER_MINUTES)` applied after `street_walk_minutes()` call. Prevents sub-minute OSMnx walks from producing unrealistically short transfer legs.

---

## 2026-04-23 — Feature Trip — Live Trip-in-Progress Routing (all 3 chunks)

1. **GPS tracking + trip activation UI** — `App.jsx`: `tripActive`, `userPosition`, `activeLegIndex`, `completedSteps`, `isOffRoute` state; `watchIdRef`, `suppressRerouteUntil` refs; `startTrip()` / `stopTrip()` helpers; "Start Trip" / "Stop Trip" buttons in selected route card footer. `MapView.jsx`: blue circle user-position dot, `flyTo` on first GPS fix, `setData` on update, `visibility: "none"` when trip stops.
2. **Active leg tracking and walk step completion** — `App.jsx`: `useEffect([userPosition])` three-pass structure: (1) advance `activeLegIndex` when within 60m of leg endpoint; (2) mark walk steps complete when within 30m of `step.start_lat`/`start_lon`; (3) off-route detection when perpendicular distance from user to nearest walk leg path segment exceeds 400m, subject to 90s suppression after dismiss. `RouteLegs`: applies `.leg-active` / `.leg-complete`. `backend/walking.py`: `"start_lat"` + `"start_lon"` added to every step dict.
3. **Off-route banner + re-route** — `App.jsx`: `isOffRoute` triggers amber banner; "Re-route from here" submits GPS coords as origin without stopping GPS watch; "Dismiss" suppresses re-prompt for 90s. `backend/gtfs_loader.py`: `_COORD_RE` module-level regex + fast-path at top of `resolve_location()` so GPS coordinate strings bypass fuzzy matching and geocoding.

---

## 2026-04-23 — BUG-008 + BUG-009 fixes

1. **BUG-008 fixed — rate limiter no longer discards first timestamp after hourly gap** — `main.py` `_check_rate_limit()`: removed `if not window: del _rate_store[ip]` block. Empty deques now retained in `_rate_store` at O(1) cost.
2. **BUG-009 fixed — duplicate `_haversine_walk_minutes` definition removed** — `walking.py`: deleted the first (verbose) definition at old line 171–186. The compact definition at line 409 is now the only one.

---

## 2026-04-24 — Efficiency improvements OPT-001/002/003 (LRU/map/route)

1. **LRU cache promotion on hit (OPT-001)** — `main.py`: inside the `async with _store_lock:` read block, `_response_cache.move_to_end(key)` now called before returning a cache hit. Hot entries are now at the MRU end.
2. **Pre-transform all leg coordinates once in `renderRoute` (OPT-002)** — `MapView.jsx`: `const legGeoCoords = legs.map(...)` precomputed before Pass 1. Reduces coordinate array allocations by ~50–60% for typical multi-leg routes.
3. **`first_transit_leg_index` on `Route` dataclass (OPT-003)** — `transit_graph.py`: new `first_transit_leg_index: int | None = None` field on `Route`. `_rank_routes()` reads it as O(1) index instead of O(legs) scan per route.

---

## 2026-04-24 — Technical debt TD-012 through TD-015

1. **Central routing config `backend/config.py` created (TD-012)** — 16 routing constants across 4 categories (transit graph, intermodal walk-edge tuning, walking speed/blocks, CTA API). All support env-var overrides.
2. **`frontend/src/components/` extracted (TD-013)** — 6 inline sub-components extracted from `App.jsx` into `TransitPhoto.jsx`, `RouteCard.jsx`, `SettingsPanel.jsx`, `LoadingSkeleton.jsx`. `App.jsx` reduced from 1,165 to ~917 lines.
3. **Retry logic for `/recommend` fetch (TD-014)** — `fetchWithRetry(url, options, onRetrying)` added to `App.jsx`. Retries up to 3 times with 1s → 2s → 4s delays on 5xx and network failures.
4. **Geocoding cache age-based eviction (TD-015)** — `gtfs_loader.py`: `geocode_cache_ages.json` sidecar tracks insertion timestamps. Entries older than `GEOCODE_MAX_AGE_DAYS` (default 90, env-var configurable) evicted at startup, weekly in background, and on compaction.

---

## 2026-04-27 — Technical debt TD-028 through TD-033 (frontend App.jsx + MapView.jsx)

1. **GPS useEffect algorithm documented (TD-028)** — Added 25-line comment block above `userPosition` effect explaining three-pass structure, `activeLegIndexRef` rationale, expanded transit-leg radius, and why three independent passes are used.
2. **`renderMarkdown` regex comments (TD-029)** — Trailing inline comments added to all seven `.replace()` calls.
3. **`fetchWithRetry` JSDoc expanded (TD-030)** — Full JSDoc with parameters + "Retry policy" section explaining why 4xx/AbortError are not retried.
4. **MapView StrictMode comment expanded (TD-031)** — `setTimeout(0)` comment explains WebGL2 GPU-process deferral and exactly how the timer prevents double-initialization.
5. **`callRecommendAPI` + `fadePhoto` extracted (TD-032)** — Both `handleSubmit` and `handleReroute` now call these helpers instead of duplicating ~60 lines of identical logic.
6. **TD-033 (photo fade duplication) resolved as side effect of TD-032** — `fadePhoto()` extraction covered both duplication sites.

---

## 2026-04-27 — Efficiency improvements OPT-FE-001/002/003

1. **GPS effect no fake state updates (OPT-FE-001)** — `App.jsx`: GPS effect now reads `activeLegIndexRef.current` directly. Blocks 2 and 3 make no `setActiveLegIndex` calls when leg hasn't advanced, eliminating spurious no-op state updates on every GPS tick.
2. **`RouteCard` memoized (OPT-FE-002)** — `RouteCard` wrapped with `React.memo`. Non-selected cards receive unchanged primitive props and skip re-renders on GPS ticks (~1s interval during active trips).
3. **`favorites.js` mutations accept in-memory array (OPT-FE-003)** — `saveLocation`, `deleteLocation`, `saveRoute`, `deleteRoute`, `pinStop`, `unpinStop` now accept the caller's current in-memory array as a parameter instead of re-reading localStorage on every mutation.

---

## 2026-04-27 — Efficiency improvements OPT-FE-004/005

1. **Module-scope trip helpers (OPT-FE-004)** — `WALK_SPEED_FACTORS`, `haversineMeters`, `pointToSegmentMeters`, `legEndCoord` moved from inside `App` component to module scope, eliminating per-render object/function allocation.
2. **`activeLegIndexRef` eliminates fake state updates (OPT-FE-005)** — `useRef(null)` mirror of `activeLegIndex`. Effect reads ref directly; `setActiveLegIndex` called at most once per tick when leg genuinely advances. Ref kept in sync in `startTrip`, `stopTrip`, `handleReroute`.

---

## 2026-04-27 — Efficiency improvements OPT-001/002/003 (backend)

1. **Non-blocking DAU saves (OPT-001)** — `dau.py`: module-level `_counts_cache` initialized at import. `record_visit()` updates `_counts_cache` in memory and offloads write to `run_in_executor`. Eliminates 2 blocking disk ops per unique visitor.
2. **Autocomplete prefix index (OPT-002)** — `main.py`: `_build_autocomplete_index()` builds `_ac_prefix_index` (dict mapping 2/3-char lowercase word prefix → `(tier, score, suggestion)` entries). `/autocomplete` does O(1) dict lookup + filter instead of O(n) linear scan.
3. **Parallel coord resolution (OPT-003)** — `main.py`: replaced two sequential `await loop.run_in_executor(...)` calls in `_resolve_locations()` with `asyncio.gather(...)`. Origin and destination coordinate lookups now run concurrently.

---

## 2026-04-27 — BUG-024 direct bus zero-wait fix

**Bus wait time in unified-graph ranking** — `main.py`: `_build_arrival_lookup()` now accepts optional `bus_arrivals` and `bus_stop_walk_map` parameters. Bus arrivals keyed `(route, stop_id)` to match the `(line_code, from_mapid)` key used by `_rank_routes()` for bus `TransitLeg`s. Before this fix, direct bus routes from `find_routes()` always received `wait = None` — buses looked 5–15 min faster than reality and consistently ranked first.

---

## 2026-04-27 — Feature Weather — Live Weather Integration (all 3 chunks)

**`backend/weather_service.py` (new):**
1. **Data models** — `PrecipitationType` enum, `PrecipitationInfo`, `WindInfo`, `CurrentWeather`, `ForecastPoint`, `WeatherContext`. All `pydantic.BaseModel`.
2. **WeatherService + caches** — `get_weather_context(lat, lon)`. NWS two-step: `/points/{lat},{lon}` (24h TTLCache) → `forecastHourly` + `/alerts/active` (12min TTLCache, fetched concurrently). `_parse_wind()`, `_feels_like()`, `_parse_precip()`. `User-Agent: CTA-Transit-PWA/1.0 (adambhonaker@gmail.com)`.

**`backend/main.py`:**
3. **Module-level singleton** — `weather_service = WeatherService()`.
4. **`_safe_weather(origin_coords)`** — async helper; returns `None` on any exception. Non-fatal.
5. **`_format_weather_for_prompt(weather, hint="")`** — one-line summary. Appends `Weather alerts:` if `weather.alerts` non-empty. Gust note shown only for gusts ≥15 mph.
6. **Fetch order** — Standalone `await _safe_weather()` before `_run_routing()` so precip factor can be applied. Alerts and route statuses remain gathered concurrently.
7. **`build_prompt()` extended** — New `weather: WeatherContext | None = None` param. End-of-prompt instruction updated to incorporate weather naturally.
8. **Walk mode** — weather fetched concurrently alongside walk engine calls.

`backend/requirements.txt`: `cachetools>=5.3` added.

---

## 2026-04-27 — Feature Pinned Stops + Feature Last Train (all chunks)

**Backend (`transit_graph.py`, `main.py`):**
1. **`_stream_all_stop_sequences` 3-tuple return** — Accumulates `_last_departure: dict[tuple[str,str], str]` during the unified streaming pass. `get_last_departure(mapid, direction_id)` public helper exposed.
2. **`from_mapid` on TransitLeg serialization** — `_format_response()` now includes `"from_mapid": leg.from_mapid`.
3. **`GET /stop-arrivals` endpoint** — Repeated `stops=type:stop_id` query params; gathers train + bus arrivals concurrently; caps at 3 per stop; 30s OrderedDict TTL cache (200-entry cap).
4. **Last-train extension** — `_parse_gtfs_time_mins(t)` handles 24:xx/25:xx. `_last_dep_minutes(mapid, now_chicago)` checks both directions; `/stop-arrivals` includes `"last_departure_minutes": int` per train stop when 0–120 min.

**Frontend:**
5. **`favorites.js` extension** — `cta_pinned_stops` localStorage key; `getPinnedStops`, `pinStop` (10-stop cap), `unpinStop`, `isStopPinned`.
6. **`PinnedStopsBoard.jsx`** (new) — Header + refresh button. Per-stop card: label, route_hint badge, up to 3 `ArrivalPill` sub-components, unpin button. Last-train badge: amber (>15 min) / red (≤15 min). Returns `null` when no stops pinned.
7. **`RouteCard.jsx` pin button** — 📍/📌 toggle on each transit leg; derives `stopId = leg.from_mapid`; calls `onPinToggle` prop.
8. **`App.jsx` wiring** — `pinnedStops` + `pinnedArrivals` state; `fetchPinnedArrivals()`; `handlePinToggle()`; `PinnedStopsBoard` mounted above search form.

---

## 2026-04-27 — Technical debt TD-033 through TD-037

1. **`LabelSavePanel` reusable component (TD-034)** — Extracted reusable inline label-save panel shared between saved-locations and saved-routes flows in `App.jsx`.
2. **Favorites state moved to `useFavorites` hook (TD-035)** — `frontend/src/hooks/useFavorites.js` wraps `favorites.js` CRUD with `useState`. Called in `App.jsx`.
3. **GPS position logic consolidated (TD-036)** — `processTripPosition()` module-scope function in `App.jsx` consolidating the three-pass GPS effect logic.
4. **MapView `_renderRouteInner` split (TD-037)** — Split into `renderPolylines()`, `renderStopMarkers()`, `renderOriginDestMarkers()` named sub-functions in `MapView.jsx`.

---

## 2026-04-27 — BUG-008/009 (walking.py and weather_service.py)

1. **BUG-009 fixed — `_load_graph()` sets `_graph_load_failed` on coordinate-array errors** — `walking.py`: wrapped coordinate-array construction and `cKDTree` build in `try/except Exception`. On failure, logs error, sets `_graph_load_failed = True`, returns `None`. Prevents repeated lock re-entry on corrupt pickle.
2. **BUG-008 fixed — `WeatherContext.fetched_at` uses timezone-aware Chicago local time** — `weather_service.py`: replaced `datetime.utcnow()` with `datetime.now(ZoneInfo("America/Chicago"))`. Eliminates `DeprecationWarning` and `TypeError` when compared to timezone-aware datetimes.

---

## 2026-04-27 — BUG-009 — DAU restart data-loss fix

**BUG-009 fixed — DAU count for today no longer resets to zero on server restart** — `dau.py`: added `_base_count: int = 0`. On day initialisation, `_base_count` set to `_load().get(today, 0)`. All writes use `_base_count + len(_seen_hashes)`. Previously: 100 visitors before restart + 5 afterward = **5**. After fix: **105**.

---

## 2026-04-27 — Efficiency improvements OPT-004/005/006/007

1. **Shared `aiohttp.ClientSession` (OPT-004)** — `cta_client.py`: module-level `_session`, `init_session()`, `close_session()`. All four API functions use the shared session. `main.py` lifespan calls init/close at startup/shutdown.
2. **`dau.py` in-memory counts cache (OPT-005)** — Module-level `_counts_cache = _load()` at import. `record_visit()` updates in memory; `_save` offloaded to `run_in_executor`. Day rollover still reloads from disk once.
3. **Single `stops.txt` pass in `_build_graph` (OPT-006)** — `transit_graph.py`: new `_load_station_data()` reads `stops.txt` once and returns both `parent_stations` and `platform_to_parent`. Old thin wrappers kept for test compatibility.
4. **Early-exit per-minute rate-limit scan (OPT-007)** — `main.py` `_check_rate_limit()`: right-to-left loop that breaks when it hits a timestamp older than 60s. Reduces average scan from O(all_hourly) to O(recent_requests).

---

## 2026-04-27 — Technical debt TD-043/047 (code quality + error boundary + i18n)

1. **eslint-disable explanations (TD-043, TD-044)** — `App.jsx` and `MapView.jsx`: expanded comments above each `eslint-disable-line react-hooks/exhaustive-deps` suppression explaining why the dep array is intentionally incomplete for the mount/render/position effects.
2. **React error boundary (TD-045)** — `frontend/src/components/ErrorBoundary.jsx` (new): class-based error boundary with `getDerivedStateFromError` and `componentDidCatch`. Friendly fallback (bus emoji + "Something went wrong" + "Refresh page" button). `<App>` wrapped in `<ErrorBoundary>` in `main.jsx`.
3. **`PinnedStopsBoard` i18n (TD-046)** — Replaced hardcoded "Pinned Stops", "No arrivals", "Last train in N min" with `t()` calls. Keys `pinned_stops_heading`, `no_arrivals`, `last_train_in` added to all 22 locale files.
4. **`RouteCard` pin/unpin i18n (TD-047)** — `RouteLegs`: replaced `title`/`aria-label` template strings with `t("pin_stop", { stop })` / `t("unpin_stop", { stop })`. Keys added to all 22 locale files.

---

## 2026-04-27 — Technical debt TD-048/049/050 (i18n + type safety) ✅ ALL RESOLVED

1. **Off-route banner i18n (TD-048)** — `App.jsx`: replaced three hardcoded English strings with `t("trip_off_route_message")`, `t("trip_reroute_btn")`, `t("trip_dismiss_btn")`. All 22 locale files updated.
2. **SettingsPanel i18n (TD-049)** — `SettingsPanel.jsx`: replaced `"AI Explanation"`, feature hint, and BYOK security notice with `t("settings_ai_explanation_label")`, `t("settings_ai_explanation_hint")`, `t("settings_byok_security_notice")`. All 22 locale files updated.
3. **Strict type checking enabled (TD-050)** — `frontend/jsconfig.json`: `"strict": false` → `"strict": true`. No new IDE errors introduced.

---

## Completed: Feature G — Long/Short Block Classification (2026-04-13)

Walk step directions now distinguish Chicago's two standard block sizes.

**Backend (`walking.py`):**
- Replaced `_CHICAGO_BLOCK_METERS = 80.0` with three constants: `_LONG_BLOCK_METERS = 201.17`, `_SHORT_BLOCK_METERS = 100.58`, `_BLOCK_TYPE_THRESHOLD = 150.0`.
- Edge-grouping loop now tracks `edge_count` alongside `total_length`.
- After each segment is merged, classifies as long or short by comparing `avg_edge_m = total_length / edge_count` to the 150m threshold.
- Emits `"block_type": "long" | "short"` on every step dict, including Haversine fallback.

**Frontend (`App.jsx`):**
- `formatBlocks(b, blockType)` updated to accept `blockType` — produces "2 long blocks", "3 short blocks", or plain "N block(s)" when absent.

---

## Completed: Structured Bus Route Cards (Phase 5.5) — 2026-04-09

Full bus routing architecture for reference:

**Bus stop sequence table** (`transit_graph.py`): Streams `stop_times.txt` once, builds `{(route_short_name, direction_id): [(stop_id, stop_name, lat, lon, arr_minutes), ...]}` for 246 route/direction pairs.

**Direct bus routing** (via unified graph, Feature J/B): Feature J deprecated standalone `find_bus_routes()`. Direct bus itineraries surfaced by `find_routes()` over ~11k bus nodes + ~50k bus transit edges. In Bus mode, `main.py` post-filters ranked list to drop any route containing a train leg.

**Bus+bus transfer routing** (`find_bus_transfer_routes()`): Handles bus A → walk → bus B. Called unconditionally when `transit_mode` is "Bus" or "All". `n_routes=2`.

**`main.py` integration**: Train routing for Train/All modes; bus routing for Bus/All modes. Results capped at 5 combined. `_format_routes()` handles both train and bus leg formatting. `line_code` in leg serialization.

**`cta_client.py`**: `stop_id` added to bus arrival dicts; batches into chunks of 10 via `asyncio.gather`; `psgld` normalized to UPPER_SNAKE.

**`App.jsx`**: `BUS_DIRECTION_COLORS` added. Bus Fullness `<select>` commented out — CTA `psgld` always empty as of initial implementation.
