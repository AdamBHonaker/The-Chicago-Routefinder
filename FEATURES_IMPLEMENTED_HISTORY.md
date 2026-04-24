# Features Implemented History

A log of features that have been designed and fully implemented. Entries are moved here from `FEATURE_IMPLEMENTATION_PLANS.md` when complete.

> **Process:** When a feature in `FEATURE_IMPLEMENTATION_PLANS.md` is finished, **delete its entry from that file** and add a corresponding entry here summarizing what was built. `FEATURE_IMPLEMENTATION_PLANS.md` should only ever contain features that have not yet been implemented.

---

## Feature Index

**Bolt-On** = self-contained, no dependencies on other planned features.
**Structural** = depends on one or more other features before it can be fully built or realized.

1. Feature A — Train Station Exit Guidance — **Bolt-On**
2. Feature C — Multi-Leg Bus Routing (Bus + Bus Transfers) — **Bolt-On**
3. Feature D — Live Arrivals at Transfer Stop — **Structural** (Dependency on Feature C)
4. Feature E — Walk Leg Street-Level Distance Detail — **Bolt-On**
5. Feature F — Street Abbreviation Normalization — **Bolt-On**
6. Feature G — Long/Short Block Classification — **Bolt-On** (Dependency on Feature E)
7. Feature B — Intermodal Routing (Train + Bus) — **Structural** (Dependency on Feature C)
8. Feature H — Deduplicate Same-Line Station Candidates — **Bolt-On** (Dependency on Feature B)
9. Feature I — CTA Alerts Integration — **Bolt-On**
10. Rate Limiting — **Bolt-On**
11. BYOK (Bring Your Own API Key) — **Bolt-On**
12. Claude Response Caching — **Bolt-On**
13. Multi-Leg Train Routing Gap 2 (Bus First/Last Mile) — **Structural** (Resolved by Feature B)
14. Feature J — Deprecate `find_bus_routes()` in Favor of Unified Graph — **Bolt-On** (Dependency on Feature B)
15. Claude Haiku for Simple Queries — **Bolt-On**
16. Multi-Leg Train Routing — Shared-Track Edge Deduplication — **Structural**
17. Feature Language — Multi-Language Support (i18n) — **Bolt-On**
18. Feature Trip — Live Trip-in-Progress Routing — **Bolt-On**
19. Feature Favorites — Saved Locations & Routes — **Bolt-On**
20. Feature DAU — Daily Unique User Counting — **Bolt-On**

---

# Feature A — Train Station Exit Guidance

**Completed: 2026-04-13**

**Overview:** Improved the final walk leg by identifying available exits at the alighting station, recommending the exit that minimises the remaining walk to the destination, and optionally letting the rider choose a different exit.

**What was implemented (5 chunks):**
- **Chunk 1 (Data):** One-time `fetch_station_exits.py` script queries Overpass API for all `railway=subway_entrance` nodes in Chicago, matches them to CTA parent stations by haversine distance, and writes `backend/station_exits.json` (`{mapid: [{label, lat, lon}, ...]}` format). File committed to repo and manually reviewed for the 10–15 most-used stations.
- **Chunk 2 (Backend — load):** `_load_station_exits()` in `transit_graph.py` reads `station_exits.json` at import time into module-level `_station_exits` dict. Public helper `get_station_exits(mapid)` returns exit list or `[]` if none known.
- **Chunk 3 (Backend — selection):** `best_exit(mapid, dest_lat, dest_lon)` scores each exit via `street_walk_minutes`, returns the exit dict with minimum walk time plus `"walk_minutes"` key, or `None` if no exits known (caller falls back to station centroid).
- **Chunk 4 (Backend — integration):** `_path_to_route()` uses exit coords as walk origin for the destination walk leg. `exit_label: str = ""` field added to `WalkLeg`. `"exit_label"` added to walk leg serialization in `/recommend` response.
- **Chunk 5 (Frontend):** `WalkLegItem` shows exit label between summary line and Steps toggle when `leg.exit_label` is present and `leg.to === "Your destination"`. Styled as small muted secondary line.

---

# Feature C — Multi-Leg Bus Routing (Bus + Bus Transfers)

**Completed: 2026-04-13**

**Overview:** Added `find_bus_transfer_routes()` for trips requiring a bus transfer (bus A → walk → bus B). Standalone function, not via the NetworkX graph. One transfer preferred, max two transfers; 0.25-mile max transfer walk; 7.5-min fixed estimate for leg-2 wait; activation gate only when `find_bus_routes()` returns no useful results.

**What was implemented (5 chunks):**
- **Chunk 1 (Startup — spatial grid):** `_bus_stop_grid` and `_bus_stop_coords` module-level dicts populated at import time. `_stops_near(lat, lon, radius_miles)` helper using 0.005° grid cells, ~9-cell bounding box, haversine post-filter.
- **Chunk 2 (Startup — stop-to-routes index):** `_stop_to_routes: dict[str, list[tuple]]` built by `_build_stop_to_routes()`, called from `warm_up()` after `get_bus_stop_sequences()`. Enables O(1) "which routes serve stop X?" lookup.
- **Chunk 3 (Algorithm):** `find_bus_transfer_routes()` — Pass 1 collects candidate transfer stops via haversine only (forward-progress filter, max 3 per live arrival). Pass 2 builds 5-leg `Route` objects via OSMnx for surviving candidates. Sort by `total + wait_A + 7.5`, return top `n_routes`.
- **Chunk 4 (Integration):** `find_bus_transfer_routes` imported in `main.py`. Called as fallback when `find_bus_routes()` returns empty results. No format changes to the response.
- **Chunk 5 (Frontend — verification):** 5-leg route cards, zero-minute transfer walk legs, and map dual-color bus segments all confirmed working.

---

# Feature D — Live Arrivals at Transfer Stop

**Completed: 2026-04-18**

**Overview:** Fetches live arrival data for the connecting service at each transfer stop and displays it inline on the route card. Replaces the fixed 7.5-minute estimate used by Feature C with real-time data. Also threads transfer arrival data into the Claude prompt so Claude can give accurate wait-time advice for transfer trips (e.g., "the Brown Line at Belmont is 4 min away — good connection").

**What was implemented (4 chunks):**
- **Chunk 1 (`backend/main.py`):** `async def _empty()` no-op coroutine used as a placeholder in `asyncio.gather` when transfer fetch is not needed. `_extract_transfer_stops(ranked_routes)` scans all routes for transfer `TransitLeg`s (legs where an earlier leg in the same route is also a `TransitLeg`), deduplicates across routes, and returns two collections: train station dicts `[{mapid, name}]` and bus `stop_id` strings. Called after routing finalization; results fed to `asyncio.gather(get_train_arrivals(...), get_bus_arrivals(...))` concurrently — one extra round-trip, ~300ms added latency.
- **Chunk 2 (`backend/transit_graph.py`, `backend/main.py`):** Added `transfer_wait_minutes: int | None = None` to `TransitLeg` dataclass. Added `_build_bus_transfer_lookup(bus_arrivals)` returning `{(route, stop_id): earliest_minutes}`. Extracted `_pick_wait(dest_map, from_mapid, to_mapid) -> int | None` helper containing the dot-product bearing test previously inlined in `_rank_routes()` — both call sites now use the shared helper. Transfer legs annotated in-place: train transfers via `_build_arrival_lookup` + `_pick_wait`; bus transfers via `_build_bus_transfer_lookup`. `"transfer_wait_minutes"` added to transit leg serialization in `/recommend` response.
- **Chunk 3 (`backend/main.py`):** `_format_transfer_arrivals(arrivals)` groups combined train+bus arrivals by stop name, shows up to 3 arrivals per stop in `"{line_code/route} → {destination}: {N} min"` format. `build_prompt()` gained `transfer_arrivals: list[dict] | None = None` parameter; when non-empty, inserts a "Live arrivals at transfer stop(s):" section after the route options block. Combined list passed as `transfer_train_arrivals + transfer_bus_arrivals`.
- **Chunk 4 (`frontend/src/App.jsx`, `frontend/src/App.css`):** `RouteLegs` detects transfer boarding legs via `legs.slice(0, i).some(l => l.type === 'transit')`. When `isTransferLeg && transfer_wait_minutes` is set, renders a `<span className="transfer-wait-note">⏱ Due</span>` or `⏱ N min wait` inline above the transit leg pill. Added `.transfer-wait-note` CSS rule (`display: block; color: #888; font-size: 0.75rem`). Non-transfer legs and legs with no live data are unaffected.

---

# Feature B — Intermodal Routing (Train + Bus in One Trip)

**Completed: 2026-04-16**

**Overview:** Extended `_build_graph()` to include bus stop nodes, bus transit edges, and bidirectional train↔bus walk edges, so `find_routes()` naturally surfaces intermodal paths (e.g. walk → Red Line → transfer to bus 36 → destination) via Dijkstra on the unified graph.

**What was implemented:**
- `_build_graph()` — added `node_type="train"` to existing train station nodes; `mode="train"` to all train transit edges; `line_code` attribute added to train transit edges.
- `_build_graph()` — bus stop nodes added (node_type="bus", lat, lon, name from stops.txt).
- `_build_graph()` — bus transit edges added for all route/direction pairs from cached bus stop sequences (mode="bus", line_code=route_short_name, edge_type="transit").
- `_build_graph()` — bidirectional train↔bus walk edges for every train station / bus stop pair within 0.15 miles and ≤5 min street walk (edge_type="walk", mode="walk").
- `_resolve_node()` helper added — resolves node name, lat, lon from either the stations dict (train) or graph node attributes (bus).
- `_path_to_route()` — all node metadata lookups updated to use `_resolve_node()`; new `edge_type == "walk"` handler added for mid-path train↔bus transfers; bus TransitLeg assembly uses `edge.get("line_code")`.
- `find_routes()` — virtual ORIGIN→bus_stop and bus_stop→DEST walk edges added so Dijkstra surfaces intermodal paths.
- `warm_up()` — logs graph size (nodes + edges) after `_build_graph()`.
- `main.py` — `find_routes()` called with `n_routes=5`; `_route_fingerprint()` deduplication added after merge-sort to prevent unified-graph bus-only routes from duplicating `find_bus_routes()` results.
- Module docstring updated to describe bus stop nodes and walk edges.
- `find_nearest_bus_stops` imported in transit_graph.py.

**Known gap (documented in plans):** Bus access/egress first/last-mile gap resolved by this feature. Shared-track edge deduplication (route label accuracy) is a separate gap documented in `FEATURE_IMPLEMENTATION_PLANS.md`.

---

# Feature H — Deduplicate Same-Line Station Candidates

**Completed: 2026-04-17**

**Overview:** When the user is near a stretch of a single-line corridor (e.g., Lawrence / Argyle / Berwyn are all Red Line only), `find_nearest_train_stations()` returned all three as candidate origin nodes, producing near-duplicate routes. Added `_dedup_stations_by_line()` to keep at most one station per unique set of transit lines served.

**What was implemented (3 chunks, all in `backend/transit_graph.py`):**
- **H-1:** `_dedup_stations_by_line(G, stations)` module-level helper. For each station sorted by walk_minutes, inspects `G.edges(mapid, data=True)` to collect the `"line"` attribute on all `edge_type="transit"` edges. Keeps the station if `station_lines - covered_lines` is non-empty; otherwise drops it. Stations with no edges always kept.
- **H-2:** In `find_routes()`, after both `origin_stations` and `dest_stations` are populated, applies `_dedup_stations_by_line(G_base, ...)` to each list before adding ORIGIN/DEST virtual-node edges.
- **H-3:** Manual verification — origin `1131 W Winona St` yields one Red Line candidate instead of three; origin near Belmont still yields both Red Line and Brown Line candidates.

---

# Feature I — CTA Alerts Integration

**Completed: 2026-04-17**

**Overview:** After routes are calculated, active service alerts are fetched from the CTA Detailed Alerts API for every transit line/route involved in the ranked results. Disruptions surfaced in the UI and included in Claude's prompt.

**What was implemented (3 chunks):**
- **I-1 (`cta_client.py`):** `ALERTS_BASE` URL constant, `_TRAIN_LINE_TO_ALERT_ID` dict (maps internal line_code → Alerts API route id), `_fetch_alerts_for_route(session, route_id)` (async fetch, timeout 5s, returns `[]` on error), `get_alerts(route_ids)` (concurrent gather, dedup by `alert_id`, sorted by `severity_score` descending).
- **I-2 (`main.py`):** `get_alerts` and `_TRAIN_LINE_TO_ALERT_ID` imported from `cta_client`. `_alert_ids_from_routes(ranked_routes)` helper extracts deduplicated Alerts API ids from all `TransitLeg`s. Alerts fetched after `ranked_routes` finalized. `build_prompt()` gained `alerts` param — alerts with `severity_score >= 5` appended as "Active service alerts on your route" block. `alerts` key added to response payload with 7 fields per alert.
- **I-3 (`App.jsx` / `App.css`):** `alerts` stored in result state. Rendered between recommendation text and route cards when non-empty. Major alerts (`is_major: true`) get red left border + bold red headline; minor alerts get yellow border. Capped at 3 with "and N more" link. Alert styles in `App.css` (`.alerts-section`, `.alert-item`, `.alert-item--major`, `.alert-item--minor`, `.alert-headline`, `.alert-impact`, `.alerts-more`).

---

# Feature E — Walk Leg Street-Level Distance Detail

**Completed: 2026-04-13**

**Overview:** Added block-count distance to each walk step so riders can understand and verify the walk without mentally converting minutes into distance. Target format: "Walk South along Broadway for 2 blocks / Head East along Wilson for 3 blocks".

**What was implemented (2 chunks):**
- **Chunk 1 (`backend/walking.py`):** Added `_CHICAGO_BLOCK_METERS = 80.0` constant, `_DIRECTION_FULL` dict (8 cardinal/intercardinal directions). Each step dict gains `"blocks": float` (rounded to nearest 0.5, min 0.5) and `"direction_full": str`. Fallback step also gets both fields. `@lru_cache` key unchanged.
- **Chunk 2 (`frontend/src/App.jsx`, `App.css`):** `formatBlocks(b)` helper. `WalkLegItem` step rendering replaced with prose format ("Walk"/"Head" + direction_full + "along" + street + blocks). Removed `.leg-step-arrow`, `.leg-step-dir`, `.leg-step-time` spans and CSS rules. Per-step minutes removed from display.

---

# Feature F — Street Abbreviation Normalization

**Completed: 2026-04-13**

**Overview:** Added a normalization pass in `resolve_location()` that expands USPS-standard street suffix abbreviations (e.g. "Ave" → "avenue", "Blvd." → "boulevard") before any matching. Reduces unnecessary Google API calls, improves `NEIGHBORHOOD_COORDS` hit rate, and produces stable geocode-cache keys.

**What was implemented (1 chunk, `backend/gtfs_loader.py`):**
- `_ABBR_MAP` dict and module-level compiled `_STREET_ABBR_RE` regex (sorted longest-first, word-boundary anchored, case-insensitive, handles period-terminated variants).
- `_normalize_street_abbr(query: str) -> str` private helper. Applied immediately after `q = query.lower().strip()` in `resolve_location()`. Google API call updated to pass normalized `q` for stable cache keys.
- Directional prefixes (N/S/E/W) intentionally excluded.

---

# Feature G — Long/Short Block Classification

**Completed: 2026-04-13**

**Overview:** Replaced the single `_CHICAGO_BLOCK_METERS = 80.0` approximation with accurate per-type constants: `_LONG_BLOCK_METERS = 201.17` (N-S axis, 1/8 mile) and `_SHORT_BLOCK_METERS = 100.58` (E-W cross streets, 1/16 mile). Each walk step is classified as long or short based on average OSM edge length; block count uses the correct constant.

**What was implemented (2 chunks):**
- **G-1 (`backend/walking.py`):** Replaced `_CHICAGO_BLOCK_METERS` with three constants. Added `edge_count` accumulator in inner loop. Classification: `avg_edge_m = total_length / edge_count`; threshold 150 m; selects correct `block_m` and sets `block_type = "long" | "short"`. Added `"block_type"` to step dict. Fallback path applies same threshold to `fallback_meters`.
- **G-2 (`frontend/src/App.jsx`):** Updated `formatBlocks(b, blockType)` to produce qualified label ("long block(s)" or "short block(s)"). Call site updated to pass `step.block_type`. Output: "Walk North along Clark for 2 long blocks" / "Head East along Chicago for 3 short blocks". Backward compatible when `blockType` absent.

---

# Rate Limiting on `/recommend` Endpoint

**Completed: 2026-04-14**

**Overview:** Zero-dependency in-memory sliding window rate limiter. Feature is OFF by default. Enable by setting `RATE_LIMIT_ENABLED=true` in Railway env vars.

**What was implemented (`backend/main.py` only):**
- `_RATE_LIMIT_ENABLED`, `_RATE_LIMIT_RPM` (default 10), `_RATE_LIMIT_RPH` (default 50) — env-var-driven config.
- `_rate_store: dict[str, collections.deque]` — in-memory per-IP timestamp store.
- `_client_ip(http_request)` — extracts real IP from `X-Forwarded-For` or falls back to `request.client.host`.
- `_check_rate_limit(ip)` — sliding-window check; returns True (allowed) or False (rate-limited); called before any I/O at top of `/recommend`.
- `/recommend` signature: `async def recommend(request: RouteRequest, http_request: Request)`.

**Known gap:** `_rate_store` and `_response_cache` are mutated without a lock — race condition under concurrent requests. Documented in `BUGS_TO_BE_FIXED.md`.

**Future:** Replace `_rate_store` with Redis-backed counter if Railway scales to multi-instance. Interface unchanged.

---

# Bring Your Own API Key (BYOK)

**Completed: 2026-04-14**

**Overview:** Lets technically savvy users supply their own Anthropic API key. Feature is OFF by default. Enable by setting `BYOK_ENABLED=true` in Railway AND `VITE_BYOK_ENABLED=true` in Vercel, then redeploy both services.

**What was implemented (`backend/main.py`, `frontend/src/App.jsx`, `frontend/src/App.css`):**

Backend:
- `anthropic_api_key: str | None = None` on `RouteRequest` with `@field_validator` (strips whitespace, rejects non-`sk-ant-` values with 400).
- `_BYOK_ENABLED` env flag. When false, field accepted but silently ignored.
- Per-request `anthropic.AsyncAnthropic(api_key=byok_key)` when BYOK key set; otherwise falls back to `_claude_client` singleton.

Frontend:
- `BYOK_ENABLED = import.meta.env.VITE_BYOK_ENABLED === "true"` compile-time flag.
- `SettingsPanel` component with gear icon ⚙ in header filters row. Modal-style panel with `type="password"` input, Save and Remove key buttons, inline format validation. Key stored in `sessionStorage` (clears on tab close).
- Fetch body spreads `{ anthropic_api_key: byokKey }` only when `BYOK_ENABLED && byokKey`.

---

# Claude Response Caching

**Completed: (date not recorded)**

**Overview:** Caches the full `/recommend` response for identical origin/destination/mode/bus_fullness queries within a 45-second TTL. Repeat requests for popular routes skip all upstream I/O.

**What was implemented (`backend/main.py`):**
- `_response_cache: dict[str, tuple[float, dict]]` — key → (expires_at, response dict).
- `_cache_key(origin, destination, transit_mode, bus_fullness)` — lowercased, joined with `"|"`.
- Cache check before any I/O at top of `/recommend`; lazy TTL eviction inline; 500-entry size cap (evicts entry nearest to expiry when full).
- `cache_hit: true` field added to cached responses (frontend wires the field but does not surface it to users).
- TTL: 45 seconds (short enough that live arrivals aren't materially stale; long enough to collapse burst traffic).

---

# Multi-Leg Train Routing — Gap 2 (Bus First/Last Mile)

**Completed: 2026-04-16 (resolved by Feature B)**

**Overview:** The origin and destination walk legs previously always used pedestrian walking. Taking a bus to a better-positioned train station was never considered.

**Resolution:** Feature B (Intermodal Routing) resolved this gap as a natural consequence of adding `ORIGIN→bus_stop` virtual walk edges in `find_routes()`. No separate implementation required.

---

# Feature J — Deprecate `find_bus_routes()` in Favor of Unified Graph

**Completed: 2026-04-18**

**Overview:** Removed the legacy standalone `find_bus_routes()` function. Direct bus-only routes now come exclusively from the unified NetworkX graph via `find_routes()` (added in Feature B); `find_bus_transfer_routes()` continues to handle bus+bus transfer itineraries the graph does not model. Eliminates two parallel bus-routing codepaths that had to be kept in sync as the graph evolved.

**What was implemented (3 chunks):**

- **Chunk 1 (Verification):** Confirmed that `find_routes()` over the unified graph surfaces direct-bus options of comparable quality to the deleted function for canonical test trips (Wicker Park↔Logan Square, Lincoln Square↔Lakeview, Pilsen↔Bridgeport). Route totals within tolerance; no nonsensical bus paths.
- **Chunk 2 (`main.py` restructure):** Removed the `find_bus_routes(...)` call and its activation-gate for `find_bus_transfer_routes()`. Bus routing block now calls `find_bus_transfer_routes()` unconditionally (subject to the existing `bus_arrivals and origin_bus_stops` guard) for both `"Bus"` and `"All"` modes with `n_routes=2`. Removed the `_route_fingerprint()` deduplication block — the unified graph and `find_bus_transfer_routes()` produce non-overlapping route types (direct vs. transfer) by design. Updated `_rank_bus_routes()` docstring to reference `find_bus_transfer_routes()` as its sole caller. Also dropped the legacy `if transit_mode != "Bus"` gate on `find_routes()` so the unified-graph call runs in every mode — it is now the sole source of direct bus-only itineraries. In Bus mode, results are post-filtered to drop any route that traverses a train `TransitLeg` (`line_code in LINE_NAMES`). Imports `LINE_NAMES` from `cta_client`.
- **Chunk 3 (cleanup):** Deleted `find_bus_routes()` from `transit_graph.py` (~205 lines). Removed the `find_bus_routes` symbol from the `main.py` import list. Updated the `_build_shape_lookup()` comment to cite `find_bus_transfer_routes()` as the remaining `get_shape(route_short_name, direction_id)` caller. Updated `find_bus_transfer_routes()` docstring (no longer gated by the legacy function) and the `_MAX_EXIT_DIST` comment. Updated the `stop_id` comment in `cta_client.py`. `grep -r "find_bus_routes" backend/` confirms zero remaining references.

**Net effect:** One less per-request bus-routing codepath, one fewer CTA Bus Tracker API-derived computation path to keep in sync, and a simpler merge in `main.py` (no fingerprint dedup step). Response schema and frontend are unchanged.

---

# Multi-Leg Train Routing — Shared-Track Edge Deduplication

**Completed: 2026-04-20**

**Overview:** Fixed a route-label accuracy bug on CTA segments where multiple train lines share the same physical track and station pair (e.g. Red/Purple between Howard and Belmont). Previously `_build_graph()` kept only the single fastest `route_id` per `(from_station, to_station)` edge, so a rider transferring to the Purple Line at Howard would still see the transit leg labelled "Red Line" through the shared section. Timing was always correct — only the displayed line name was wrong.

**What was implemented (1 chunk, `backend/transit_graph.py`):**

- **`_build_graph()`:** For every `(from_mapid, to_mapid)` edge that has more than one route candidate (i.e., shared-track segments), stores `all_routes: dict[route_id, (dir_id, line_name)]` as an edge attribute. Single-route edges get `all_routes=None` (no overhead). Edge weight, `route_id`, and all other attributes continue to reflect the fastest candidate.
- **`_last_transit_leg()` helper:** New module-level function that searches backward through the assembled `legs` list (past any intervening walk legs) to find the most recent `TransitLeg`. Used to detect the incoming line at the start of each new transit segment.
- **`_path_to_route()` — shared-track label correction block:** After reading the raw `route_id` and `line` from the first edge of a new transit group, checks: (a) there is an incoming `TransitLeg`, (b) the edge has `all_routes` metadata, (c) the incoming line_code differs from the edge's stored `route_id`, and (d) the incoming line_code is present in `all_routes`. If all four conditions hold, overrides `group_route`, `group_dir`, and `group_line` with the incoming line's values — so the leg is labelled with the line the rider is actually on.
- **`_path_to_route()` — merge-loop fix:** The while-loop that groups consecutive same-route edges previously broke on `next_edge.get("route_id") != group_route`. Updated to also accept edges where `group_route in next_edge.get("all_routes", {})`, so the Purple Line leg continues merging through Howard→Wilson→Montrose→… even though those edges store `route_id="Red"`.
- **`line_code` assignment fix:** Changed `line_code = edge.get("line_code") or group_route` to `line_code = group_route` so the `TransitLeg.line_code` field reflects the overridden value (not the raw edge attribute). This ensures shape lookup calls `get_shape(group_route, group_dir)` with the correct line.

**Correctness properties:**
- No override fires when there is no incoming transit leg (first leg of the trip): stored label used as-is.
- No override fires when the incoming line equals the stored `route_id`: already correct.
- No override fires when `all_routes` is None (non-shared-track edge): behavior unchanged.
- Override only fires when the incoming line actually appears in `all_routes` — prevents spurious relabelling on lines that genuinely diverge.
- Bus edges never have `all_routes` set (only train candidates are stored per edge), so bus leg labelling is unaffected.

---

# Claude Haiku for Simple Queries

**Completed: 2026-04-18**

**Overview:** Routes with exactly one option and a single direct `TransitLeg` (no transfers) are now handled by `claude-haiku-4-5-20251001` instead of `claude-sonnet-4-6`. Haiku is ~65% cheaper and fully capable of formatting a single-option recommendation; Sonnet is reserved for multi-option or multi-leg responses that need comparison reasoning.

**What was implemented:**

- Added `_is_simple_query(ranked_routes)` helper in `backend/main.py`. Returns `True` iff `len(ranked_routes) == 1` **and** that route contains exactly one `TransitLeg` (walk legs do not count). Conservative by design — any query with multiple routes, a transfer, or multiple same-line options falls through to Sonnet.
- Model selection branch in `/recommend` immediately before the `claude_client.messages.create(...)` call. Haiku uses `max_tokens=300`; Sonnet keeps `max_tokens=400`. The prompt is identical for both models — no prompt divergence to maintain.
- Stdout log line `[claude model=haiku|sonnet simple=True|False]` printed on every request for cost analysis.
- `"model_used": "haiku" | "sonnet"` added to the `/recommend` response dict. Frontend ignores it; exists for observability and future surfacing. The response cache stores it unchanged, so cache hits still return the correct `model_used` value from the original call.
- BYOK path uses the same classifier — whether the request uses a shared-quota key or a user-supplied key, the same `simple` determination picks the model.

**Out of scope (explicitly not done):** Haiku-specific prompt tuning; expanding "simple" to cover two same-line options; per-model cost tracking in the response; automatic Haiku→Sonnet fallback on low-confidence output (the classifier is conservative enough that this is not needed).

---

# Feature AI Toggle — Optional Claude Recommendation Layer

**Completed: 2026-04-20**

**Overview:** The Claude recommendation layer is now opt-in. The UI adds an "AI Explanation" toggle in the settings panel (off by default, persisted to `localStorage`). When off, the backend skips the Claude call entirely — no latency, no token spend, and `recommendation: null` is returned. When on, behavior is identical to before. The feature is designed so a paywall can be added later with a single auth check at the `if request.ai_enabled:` branch in `main.py`.

**What was implemented (2 chunks):**

- **Chunk 1 — Backend (`backend/main.py`):**
  - Added `ai_enabled: bool = False` field to `RouteRequest`. Defaults to `False` — old clients that omit the field get the safe default (no Claude call, no breakage).
  - Updated `_validate_api_keys()` to only require `ANTHROPIC_API_KEY` when `request.ai_enabled` is `True`. Non-AI requests no longer fail if the key is absent.
  - Updated `_cache_key()` to include `ai_enabled` in the key string so AI-on and AI-off responses are cached separately.
  - Wrapped the `_call_claude(...)` call in `if request.ai_enabled:`. When the flag is `False`, `recommendation` and `model_used` are both `None`. The response always includes `"recommendation": recommendation` (value is the string when AI ran, `None` otherwise).

- **Chunk 2 — Frontend (`frontend/src/App.jsx`, `frontend/src/App.css`):**
  - Added `aiEnabled` state, initialized from `localStorage.getItem("cta_ai_enabled") === "true"` (defaults to `false`).
  - Added `handleAiChange(value)` helper that updates both state and `localStorage`.
  - Added `ai_enabled: aiEnabled` to the `handleSubmit` fetch request body.
  - Updated `setResult` to store `null` (not `""`) when `data.recommendation` is `null`.
  - Added an "AI Explanation" labeled checkbox (`<label className="setting-row">`) to `SettingsPanel`, with a one-line hint below it. `SettingsPanel` now accepts `aiEnabled` and `onAiChange` props. The BYOK key section is conditionally rendered inside the panel when `BYOK_ENABLED` is true.
  - Removed the `BYOK_ENABLED` gate on the settings gear icon — the button now always shows so the AI toggle is always reachable.
  - Removed the `BYOK_ENABLED` gate on the `{settingsOpen && <SettingsPanel ...>}` render.
  - Gated `<div className="recommendation">` on `result.recommendation != null`. Moved `busDataPartial` warning outside the recommendation div so it still renders when AI is off.
  - Added `.setting-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; }` to `App.css`.

**Future paywall gate:** Add an auth check inside the `if request.ai_enabled:` block in `main.py`. No other code needs to change.

---

## Feature Trip — Live Trip-in-Progress Routing

**Completed: 2026-04-23**

**Overview:** After a rider selects a route card, a "Start Trip" button activates GPS tracking via `navigator.geolocation.watchPosition`. The app follows the user through each route leg, highlights the active leg and dims completed ones, marks individual walk steps complete as the user passes them, detects significant deviation from the planned route, and offers a one-tap re-route from the current GPS position. A "Stop Trip" button is always visible while tracking is active. Starting a new search automatically ends any in-progress trip.

**What was implemented (3 chunks):**

- **Chunk 1 — GPS tracking, trip activation UI, and map position dot:**
  - `App.jsx`: `tripActive`, `userPosition`, `watchIdRef` state/refs; `startTrip()` / `stopTrip()` helpers; "Start Trip" / "Stop Trip" buttons rendered in the selected route card footer; GPS watch options `{ enableHighAccuracy: true, maximumAge: 15000, timeout: 10000 }`; `stopTrip()` called at top of `handleSubmit` and when switching route cards; `userPosition` / `tripActive` passed to `MapView`.
  - `MapView.jsx`: `userPosition` and `tripActive` props accepted; when trip active, a blue circle (`#4A90E2`, radius 10, white stroke) is added as a GeoJSON source/layer `user-position-source`/`user-position-layer`; map `flyTo` centers on first GPS fix; subsequent position updates call `setData` rather than re-adding the layer; when trip stops, layer visibility set to `"none"` rather than removed (avoids MapLibre source-still-in-use errors); `userPosLayerRef` reset to `false` on map re-init.
  - `App.css`: `.route-card-trip-footer`, `.start-trip-btn` (blue, primary), `.stop-trip-btn` (muted/destructive).

- **Chunk 2 — Active leg tracking and walk step completion:**
  - `App.jsx`: `activeLegIndex` (default `null`, set to `0` on trip start) and `completedSteps` (`Set<string>`, keys `"legIdx-stepIdx"`) state; `haversineMeters(a, b)` inline 5-line Haversine; `legEndCoord(leg)` returns `{lat, lng}` from `leg.to_coords` (transit) or last `leg.path` point (walk); `useEffect([userPosition])` runs three functional `setActiveLegIndex` passes: (1) advance leg when within 60 m of its endpoint, (2) mark walk steps complete when within 30 m of `step.start_lat`/`start_lon`, (3) off-route detection; `activeLegIndex` / `completedSteps` passed via `RouteCard` → `RouteLegs` → `WalkLegItem`.
  - `RouteLegs`: accepts `activeLegIndex` and `completedSteps` props; applies `.leg-active` (blue left border) to active leg and `.leg-complete` (50% opacity + ✓ check icon) to completed legs.
  - `WalkLegItem`: accepts `completedSteps` and `extraClass`; renders ✓ + `.leg-step--complete` on steps whose key is in `completedSteps`.
  - `backend/walking.py`: Added `"start_lat": lat1, "start_lon": lon1` to every step dict in `_walk_directions_impl` (both street-routed path and Haversine fallback).

- **Chunk 3 — Off-route detection and re-route prompt:**
  - `App.jsx`: `isOffRoute` boolean state; `suppressRerouteUntil` ref (90 s suppression after dismiss); off-route fires only during walk legs when min distance to any leg endpoint exceeds 400 m; `handleReroute()` function submits GPS coords as origin without stopping the GPS watch (`setOrigin(gpsOrigin)`, fresh fetch, resets `activeLegIndex`/`completedSteps`); off-route banner rendered above route cards with "Re-route from here" and "Dismiss" buttons.
  - `backend/gtfs_loader.py`: `_COORD_RE` module-level regex + fast-path at top of `resolve_location()` so GPS coordinate strings (e.g. `"41.893450,-87.631200"`) bypass fuzzy matching and geocoding entirely, resolving directly to `find_nearest_train_stations` / `find_nearest_bus_stops`.
  - `App.css`: `.off-route-banner` (amber `#FFF3CD` background, `border-left: 4px solid #D97706`), `.off-route-message`, `.off-route-actions`, `.off-route-reroute-btn`, `.off-route-dismiss-btn`.

**Future iteration ideas (not implemented):**
- Live arrival countdown polling every 30 s during transit wait phase.
- Adaptive GPS polling rate (lower on walk legs, higher on transit legs).
- Shape-based off-route detection using the clipped GTFS shape polyline.
- Haptic / browser notification alerts for boarding nudges.

---

## Feature Language — Multi-Language Support (i18n)

**Completed: 2026-04-20**

**Overview:** Added full internationalization to the frontend UI and Claude's AI-generated recommendation text, supporting 22 languages including RTL scripts (Arabic, Urdu, Pashto). A language selector in the header persists to `localStorage` and automatically detects the browser language on first visit.

**What was implemented (6 chunks):**

- **Chunk 1 — i18n infrastructure (`frontend/src/i18n.js`, `frontend/src/main.jsx`, `frontend/public/locales/en/translation.json`):**
  - Installed `i18next`, `react-i18next`, `i18next-http-backend`, `i18next-browser-languagedetector`.
  - Created `frontend/src/i18n.js` with `SUPPORTED` list (22 language codes), `HttpBackend` for on-demand locale loading, `LanguageDetector` reading `localStorage["cta_language"]` then `navigator.language`, and `fallbackLng: "en"`.
  - Updated `frontend/src/main.jsx` to import `i18n.js` and wrap `<App />` in `<Suspense fallback={null}>`.
  - Created `frontend/public/locales/en/translation.json` with all 45 English strings.

- **Chunk 2 — String extraction (`frontend/src/App.jsx`):**
  - Added `useTranslation()` hook to all components: `WalkLegItem`, `RouteCard`, `SettingsPanel`, `LoadingSkeleton`, and main `App`.
  - `formatBlocks()` now accepts `t` as a third parameter, using `block_singular/plural`, `long_block_singular/plural`, `short_block_singular/plural` keys.
  - Replaced all 45+ hardcoded user-visible strings with `t("key")` or `t("key", { vars })` calls. Station names, line names, and CTA alert text are NOT translated (proper nouns).

- **Chunk 3 — Language selector (`frontend/src/App.jsx`):**
  - Added `LANGUAGE_NAMES` constant with native-script names (العربية, 中文, etc.) for all 22 languages.
  - Added `<select>` in `.filters` bar adjacent to transit mode selector, bound to `i18n.changeLanguage()`.
  - Added `useEffect` watching `i18n.language` to set `document.documentElement.dir` (rtl/ltr) and `document.documentElement.lang`. `RTL_LANGS = new Set(["ar", "ur", "ps"])`.

- **Chunk 4 — Translation files (`frontend/public/locales/{code}/translation.json`):**
  - Created machine-translated files for all 21 non-English languages: es, fr, it, pl, ro, uk, ru, zh, yue, ja, ko, tl, vi, hi, gu, pa, ne, ur, ar, ps, yo.
  - Japanese file includes parenthetical furigana on all kanji-heavy terms.
  - All non-English files include `"_comment": "machine-translated, review welcome"`.

- **Chunk 5 — Backend language pass-through (`backend/main.py`):**
  - Added `language: str | None = None` field to `RouteRequest`.
  - Added `LANGUAGE_NAMES` dict mapping all 22 codes to English names.
  - Extended `build_prompt()` with `language` parameter. Appends `"Respond in {language_name}."` for non-English languages; Japanese gets the extended furigana instruction.
  - Updated `_cache_key()` to include language so same-route queries in different languages cache separately.
  - Frontend `handleSubmit` now sends `language: i18n.language` in the request body.

- **Chunk 6 — RTL CSS (`frontend/src/App.css`):**
  - Added `[dir="rtl"]` overrides for `.header-top`, `.filters`, `.route-card-header`, `.route-card-summary`, `.leg`, `.leg-walk-body`, `.leg-steps` (border flips), `.alert-item` (border flips), `.settings-header`, `.settings-actions`, `.form label`.
  - No full CSS rewrite — only targeted overrides for confirmed RTL issues.

---

# Feature Favorites — Saved Locations & Routes

**Completed: 2026-04-23**

**Overview:** Added a localStorage-backed favorites system so repeat users can save named locations (e.g. "Home", "Work") that quick-fill either text field, and named routes (origin+destination pairs) that repopulate both fields with one tap. All state lives in the browser — no backend changes. Cap of 10 items per list.

**What was implemented (3 chunks):**

- **Chunk 1 — Data layer (`frontend/src/favorites.js`, new):** Pure utility module with no React dependency. `_load(key)` / `_save(key, arr)` private helpers backed by `localStorage`. Public exports: `getSavedLocations`, `saveLocation` (returns updated array or `null` on cap), `deleteLocation`, `getSavedRoutes`, `saveRoute` (same null-on-cap contract), `deleteRoute`. Cap is 10 items per list; IDs generated with `crypto.randomUUID()`.

- **Chunk 2 — Saved Locations UI (`frontend/src/App.jsx`, `frontend/src/App.css`):** New `LocationInput` component wraps each "From"/"To" field in a `.field-wrapper` (position: relative). A `☆` star button (absolute-positioned right) appears when the field has a non-empty value; turns amber `★` when the value is already saved. Clicking an unsaved field opens an inline label save panel (text input + Save/Cancel buttons; Enter saves, Escape cancels; blocks form submission). Clicking a saved field immediately removes it. Focusing a field with saved locations shows a `.saved-dropdown` (absolute, `z-index: 100`) listing up to 5 items with per-item `×` delete buttons; `onMouseDown` + `e.preventDefault()` ensures selection fires before `onBlur` closes the dropdown (150 ms debounce). Cap hit shows a 3-second inline error then auto-dismisses. RTL overrides flip star to left edge.

- **Chunk 3 — Saved Routes UI (`frontend/src/App.jsx`, `frontend/src/App.css`):** `⭐` toggle button added to the `.filters` bar; opens a `.saved-routes-panel` between the header and form listing all saved routes with "Go" (populates fields + closes panel) and `×` (deletes) buttons, plus an empty-state message. After a successful query, a "Save ☆" / "Saved ★" button appears in a `.routes-section-header` flex row alongside the "Route options" heading. Clicking to save opens an inline route-label save panel (same pattern as locations, 30-char max, pre-filled with `origin → destination`). Clicking to unsave immediately removes the matching entry. Route save UI resets on new query submission. 14 new i18n keys added to `frontend/public/locales/en/translation.json`; other locale files require manual translation review.

---

# Feature DAU — Daily Unique User Counting

**Completed: 2026-04-24**

**Overview:** Tracks how many unique users access the site per day as a single integer per day — the minimum viable growth signal. No personal data, behavioral data, or session information is persisted. Client IPs are HMAC-SHA256 hashed with a daily secret salt and kept only in an in-memory set for the current UTC day; when the day rolls over the set is discarded and only the final count is written to disk. Cross-day correlation is impossible because the daily salt changes.

**What was implemented (2 chunks):**

- **Chunk 1 — Backend counter (`backend/dau.py` new, `backend/main.py`):**
  - `backend/dau.py`: `DAU_FILE` path — `/app/data/dau.json` when `APP_ENV=production` (Railway persistent volume), `backend/data/dau.json` otherwise. `DAU_FILE.parent.mkdir(parents=True, exist_ok=True)` runs at module load. Module-level state: `_current_day: str`, `_seen_hashes: set[str]`, `_lock: asyncio.Lock`. `_load() -> dict[str, int]` — reads the JSON file, returns `{}` on missing or corrupt. `_save(counts)` — atomic write via `tempfile.mkstemp` + `os.replace`. `async def record_visit(ip)` — derives today's HMAC key from `DAILY_SALT + today_utc`, hashes the IP, checks if already in `_seen_hashes` (skip), flushes previous day's count on day rollover, adds hash to set, and saves the incremented count. `async def get_counts()` — returns `_load()`.
  - `backend/main.py`: Imported `dau` module. Added `Header` to FastAPI imports. Added `GET /ping` — calls `_client_ip()` (already honors `X-Forwarded-For` for Railway proxy), calls `await dau.record_visit(ip)`, returns `{"ok": True}`. Added `GET /admin/dau` — checks `Authorization: Bearer <DAU_ADMIN_TOKEN>` header (env var); returns `await dau.get_counts()`; returns 403 on mismatch or absent token. `DAILY_SALT` and `DAU_ADMIN_TOKEN` must be set in Railway env vars (values never committed).

- **Chunk 2 — Frontend ping (`frontend/src/App.jsx`):**
  - Added `useEffect(() => { fetch(\`${BACKEND_URL}/ping\`); }, [])` in the `App` component — fires once on mount, fire-and-forget (no await, no error handling, never blocks the UI).

**Railway setup required:**

- Add Railway persistent volume mounted at `/app/data`.
- Set env vars: `DAILY_SALT=<random-secret>`, `DAU_ADMIN_TOKEN=<random-secret>`, `APP_ENV=production`.

**Data access:** `GET /admin/dau` with `Authorization: Bearer <DAU_ADMIN_TOKEN>` returns the full `{"YYYY-MM-DD": count, ...}` JSON object.
