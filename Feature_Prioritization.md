# Feature Prioritization

Classification of each feature as **Bolt-On** (self-contained, no dependencies on other planned features) or **Structural** (depends on one or more other planned or unplanned features before it can be built or fully realized). Once a feature has been completed, it should be deleted from this file when updating documentation, and any features with a dependency on the completed feature should be updated to remove that portion of their dependencies.

---

## Chunked Features

### Feature B — Intermodal Routing (Train + Bus)
**Type: Structural**
Depends on:
- **Stable production deployment (Phase 6)** — the feature plan explicitly requires the app to be running stably before starting.
- **`get_bus_stop_sequences()`** — must be restructured to be called inside `_build_graph()`, changing warm-up ordering.
- Intersects with Feature C: once Feature B's unified graph is live, `find_bus_routes()` (which Feature C extends) becomes partially redundant and deduplication logic must be added.
- ~~Intersects with Feature A~~: Feature A is complete — `_path_to_route()` changes from Feature A are already in place. Feature B must be written against this post-A version.

---

### Feature D — Live Arrivals at Transfer Stop
**Type: Structural (soft dependency)**
The train-to-train half works independently today. The bus-transfer half depends on:
- **Feature C** (Bus+Bus Transfers) — bus transfer arrivals are only meaningful once bus transfer routes exist. ✅ Feature C is now complete, so this dependency is satisfied.

---


## Future Enhancements

### Feature H — Deduplicate Same-Line Station Candidates
**Type: Bolt-On**
No dependency on other planned features. Self-contained to `transit_graph.py` (and optionally `gtfs_loader.py`).

**Problem:** `find_nearest_train_stations()` returns up to 3 stations within the search radius sorted by walk time, with no awareness of whether they serve the same lines. When the user is near a stretch of a single-line corridor (e.g., Lawrence / Argyle / Berwyn are all Red Line only), all three get added as candidate origin nodes in `find_routes()`, producing near-duplicate routes that clutter the results.

**Correct behavior:** Within the candidate set, keep at most one station per unique transit line served. If all three nearby stations serve only the Red Line, keep the one with the shortest walk time. If a separate Brown Line station is also within range, keep it too — it represents a genuinely different routing option.

**Files touched:**
- `backend/transit_graph.py` — add deduplication helper and call it inside `find_routes()`
- `backend/gtfs_loader.py` — no changes required (deduplication happens after line info is available from the graph)

---

#### Chunk H-1 — Add `_dedup_stations_by_line()` helper in `transit_graph.py`

Add a module-level helper that takes the built graph `G` and a list of station dicts already sorted by walk time, then returns a deduplicated list:

```python
def _dedup_stations_by_line(G, stations: list[dict]) -> list[dict]:
    """
    Given stations sorted by ascending walk_minutes, keep only the closest
    station per unique set of lines served. Stations that introduce no new
    lines are dropped (they would produce near-duplicate routes).
    """
```

**Implementation detail:** For each station, determine which lines it serves by inspecting `G.edges(mapid, data=True)` and collecting the `"line"` attribute on each edge. Maintain a `covered_lines: set` as candidates are accepted. Accept a station if `station_lines - covered_lines` is non-empty (i.e., it contributes at least one line not yet covered). Add its lines to `covered_lines`. Skip otherwise.

Edge case: a station with no edges in the graph (shouldn't happen in practice, but if `mapid` is not a graph node) — include it rather than silently dropping it to avoid breaking routing in degenerate cases.

---

#### Chunk H-2 — Apply deduplication inside `find_routes()`

In `find_routes()` in `transit_graph.py`, apply `_dedup_stations_by_line()` to both `origin_stations` and `dest_stations` immediately after each list is sorted by walk time and before the `ORIGIN`/`DEST` virtual-node edges are added to the graph.

```python
# After origin_stations is populated and sorted:
origin_stations = _dedup_stations_by_line(G_base, origin_stations)

# After dest_stations is populated and sorted:
dest_stations = _dedup_stations_by_line(G_base, dest_stations)
```

Note: `_dedup_stations_by_line` receives `G_base` (the shared cached graph), not the thread-local copy `G`, because edge inspection is read-only and does not require the per-thread mutable copy.

---

#### Chunk H-3 — Manual verification

Test with origin `1131 W Winona St, Chicago, IL`:
- **Before fix:** Berwyn, Argyle, and Lawrence all appear as candidate origin stations → multiple near-identical Red Line routes shown.
- **After fix:** Only the closest Red Line station (by walk time) appears as a candidate → one clean Red Line option in results.

Also verify that a location near both a Red Line and a Brown Line station (e.g., near Belmont) still returns both stations as candidates, since they represent genuinely different routing options.

---

### Multi-Leg Train Routing — Gap 1 (Shared-Track Edge Deduplication)
**Type: Structural**
Modifies the same `_path_to_route()` logic that Feature B also restructures. The feature plan notes this is "out of scope for Feature B and should be addressed in a separate scoped session," but if Feature B is built first, this fix must be written against the post-B version of `_path_to_route()`. Depends on: **Feature B** (if building after intermodal routing is live).

---

### Multi-Leg Train Routing — Gap 2 (Bus Access/Egress to Train Stations)
**Type: Structural**
Explicitly deferred to Feature B — this gap is resolved as a natural consequence of the unified intermodal graph. Depends on: **Feature B**.

---

### Rate Limiting on `/recommend`
~~**Type: Bolt-On**~~
~~Standalone infrastructure change to `main.py` and `requirements.txt`. No dependency on any routing, geocoding, or UI feature. Must ship before or shortly after public launch.~~
**✅ Complete (2026-04-14)** — Code written; feature is OFF by default. Enable with `RATE_LIMIT_ENABLED=true` in Railway env vars before public launch.

---

### Bring Your Own API Key (BYOK)
~~**Type: Bolt-On (soft interaction)**~~
~~Self-contained `RouteRequest` field + per-request client logic on the backend, and a Settings panel on the frontend. No hard dependency on other features. Soft interaction with Rate Limiting: BYOK requests should bypass the global spend cap but still count against per-IP limits — this logic is trivial to add regardless of whether Rate Limiting is built first.~~
**✅ Complete (2026-04-14)** — Code written; feature is OFF by default. Enable with `BYOK_ENABLED=true` (Railway) + `VITE_BYOK_ENABLED=true` (Vercel) before activating for users.

---

### Feature I — CTA Alerts Integration
**Type: Bolt-On**
No dependency on other planned features. Self-contained to `cta_client.py`, `main.py`, and frontend display components. No API key needed — the CTA Alerts API is public.

**What it does:** After routes are calculated for a `/recommend` request, fetch active service alerts from the CTA Detailed Alerts API for every transit line/route involved in the ranked results. Surface disruptions (delays, route changes, elevator outages, reduced service) to the rider and include them in Claude's prompt so the recommendation can account for them.

**API endpoints (no key required):**
- Detailed Alerts: `http://www.transitchicago.com/api/1.0/detailed_alerts.aspx?outputType=JSON&routeid=<id>`
- Route id format: lowercase line color for trains (`red`, `blue`, `brn`, `g`, `org`, `p`, `pink`, `y`); bus route number as a string (`22`, `36`, etc.)
- Response shape: `{alerts: [{alert_id, headline, short_description, severity_score, impact, event_start, event_end, alert_url, impacted_service: [{service_id, service_name, service_type, ...}]}]}`
- No active-only filter parameter exists — the API returns only active/upcoming alerts by default

**Files touched:**
- `backend/cta_client.py` — new `get_alerts()` async function
- `backend/main.py` — fetch alerts after routing, add to prompt and response payload
- `frontend/src/App.jsx` — display alert badges/banners on result cards

---

#### Chunk I-1 — Backend: `get_alerts()` in `cta_client.py`

Add at the bottom of `cta_client.py` after the Bus Tracker section:

```python
ALERTS_BASE = "http://www.transitchicago.com/api/1.0/detailed_alerts.aspx"

# Maps app-internal line_code values to the lowercase routeid the Alerts API expects
_TRAIN_LINE_TO_ALERT_ID = {
    "Red": "red", "Blue": "blue", "Brn": "brn", "G": "g",
    "Org": "org", "P": "p", "Pink": "pink", "Y": "y",
}

async def _fetch_alerts_for_route(
    session: aiohttp.ClientSession,
    route_id: str,
) -> list[dict]:
    """Fetch active alerts for a single route id (train line or bus route number)."""
```

- `GET ALERTS_BASE?outputType=JSON&routeid=<route_id>`, timeout 5s
- On any exception or non-zero error code, return `[]` (alerts are supplemental — never crash routing for them)
- Parse each alert dict into: `{alert_id, headline, impact, severity_score, is_major: bool, event_end, affected_routes: [str]}`
  - `is_major`: `severity_score >= 7` (score is an int 1–10; 7+ represents "Major Alert" in CTA's own CSS classes)
  - `affected_routes`: list of `service_id` strings from `impacted_service`
  - `event_end`: raw string from API, or `None` if missing/blank

```python
async def get_alerts(route_ids: list[str]) -> list[dict]:
    """
    Fetch active CTA alerts for a list of route ids concurrently.
    route_ids are Alerts API ids: lowercase train color or bus route number.
    Deduplicates by alert_id (the same alert can affect multiple requested routes).
    Returns [] if route_ids is empty.
    """
```

- Fire one `_fetch_alerts_for_route` per route_id concurrently with `asyncio.gather`
- Deduplicate results by `alert_id` (keep first occurrence)
- Sort by `severity_score` descending so callers see the most severe alerts first
- Return the deduplicated, sorted list

---

#### Chunk I-2 — Backend: Wire alerts into `/recommend` in `main.py`

**Import:** add `get_alerts` to the `from cta_client import ...` line.

**Route ID extraction:** add a module-level helper `_alert_ids_from_routes(ranked_routes) -> list[str]`:
- Iterate all `TransitLeg` objects across all routes in `ranked_routes`
- For train legs: map `leg.line_code` through `_TRAIN_LINE_TO_ALERT_ID` (import the dict or duplicate the mapping locally)
- For bus legs: use `leg.line_code` directly (it is already the bus route number string)
- Return a deduplicated list; return `[]` if `ranked_routes` is empty

**Fetch alerts** in the `/recommend` handler, immediately after `ranked_routes` is finalized:

```python
alert_ids = _alert_ids_from_routes(ranked_routes)
alerts: list[dict] = await get_alerts(alert_ids) if alert_ids else []
```

**Update `build_prompt()`:** add an `alerts: list[dict] | None = None` parameter. If alerts is non-empty, append a section before the closing instruction line:

```
Active service alerts on your route:
  * <headline> [<impact>]  ← one line per alert, major alerts flagged with "⚠ MAJOR"
```

Only include alerts with `severity_score >= 5` in the prompt (low-severity elevator notices are noise for a routing recommendation).

**Add to response payload:**

```python
"alerts": [
    {
        "alert_id": a["alert_id"],
        "headline": a["headline"],
        "impact": a["impact"],
        "severity_score": a["severity_score"],
        "is_major": a["is_major"],
        "event_end": a["event_end"],
        "affected_routes": a["affected_routes"],
    }
    for a in alerts
],
```

**Cache note:** alerts fetch is cheap (one request per distinct line) and the existing 45-second response cache means alert data ages at most 45 seconds — no additional caching layer needed.

---

#### Chunk I-3 — Frontend: Display alerts in `App.jsx`

Read `response.alerts` from the `/recommend` response.

**If alerts is empty or missing:** render nothing extra — no UI change for the happy path.

**If alerts exist:** render a compact alert section below the Claude recommendation text and above the route cards. Style rules:
- Major alerts (`is_major: true` or `severity_score >= 7`): red/orange left border, bold headline
- Minor alerts (`severity_score` 5–6): yellow left border
- Each alert shows: headline text + impact type (e.g., "Reduced Service") in smaller muted text
- Cap display at 3 alerts; if more exist add "and N more" link (link to `alert_url` if available, otherwise `https://www.transitchicago.com/travel-information/alerts/`)
- No new component file needed — keep alert rendering inline in `App.jsx` unless the block exceeds ~40 lines, in which case extract to `AlertBanner.jsx`

**Manual verification steps:**
- Confirm that a route involving a line with a known active alert (check transitchicago.com/travel-information/alerts/ before testing) surfaces that alert in the UI
- Confirm that a route on a line with no active alerts renders nothing extra
- Confirm that the Claude recommendation text mentions the disruption when a major alert is present

