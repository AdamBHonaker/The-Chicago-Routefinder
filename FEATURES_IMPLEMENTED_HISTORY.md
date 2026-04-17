# Features Implemented History

A log of features that have been designed and fully implemented. Entries are moved here from `FEATURE_IMPLEMENTATION_PLANS.md` when complete.

> **Process:** When a feature in `FEATURE_IMPLEMENTATION_PLANS.md` is finished, **delete its entry from that file** and add a corresponding entry here summarizing what was built. `FEATURE_IMPLEMENTATION_PLANS.md` should only ever contain features that have not yet been implemented.

---

## Feature Index

**Bolt-On** = self-contained, no dependencies on other planned features.
**Structural** = depends on one or more other features before it can be fully built or realized.

1. Feature A — Train Station Exit Guidance — **Bolt-On**
2. Feature C — Multi-Leg Bus Routing (Bus + Bus Transfers) — **Bolt-On**
3. Feature E — Walk Leg Street-Level Distance Detail — **Bolt-On**
4. Feature F — Street Abbreviation Normalization — **Bolt-On**
5. Feature G — Long/Short Block Classification — **Bolt-On** (Dependency on Feature E)
6. Feature B — Intermodal Routing (Train + Bus) — **Structural** (Dependency on Feature C)
7. Feature H — Deduplicate Same-Line Station Candidates — **Bolt-On** (Dependency on Feature B)
8. Feature I — CTA Alerts Integration — **Bolt-On**
9. Rate Limiting — **Bolt-On**
10. BYOK (Bring Your Own API Key) — **Bolt-On**
11. Claude Response Caching — **Bolt-On**
12. Multi-Leg Train Routing Gap 2 (Bus First/Last Mile) — **Structural** (Resolved by Feature B)

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
