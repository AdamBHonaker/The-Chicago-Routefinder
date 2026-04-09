# Bugs To Be Fixed

Known issues catalogued for future fixing. Severity: 🔴 High · 🟡 Medium · 🟢 Low.

---

## 🟡 Arrival lookup ignores train direction — FIX PRE-DEPLOYMENT

**File:** `backend/main.py` — `_build_arrival_lookup()` (line ~104); `_rank_routes()` (line ~114)

**What happens:** `_build_arrival_lookup` keys arrivals on `(line_code, station_mapid)`. The CTA Train Tracker API returns arrivals for all platforms at a station — both directions of the same line. When `_rank_routes` looks up wait time for the first boarding station, it gets the earliest arrival at that station regardless of direction. If a northbound Red Line train is due in 1 minute but you need southbound (due in 8 minutes), the route card shows a 1-minute wait and ranks the route accordingly — both wrong.

**Effect:** Wait times shown in route cards can be inaccurate when a line serves a station in both directions. Routes may be ranked by the wrong train's wait time, potentially surfacing a slower option as "best."

**Fix:** The CTA Train Tracker API returns `destNm` (destination name) for each arrival — e.g., "Howard" vs "95th/Dan Ryan" for Red Line. Use the route's final destination station to infer which direction is relevant and filter arrivals to only matching-direction trains before building the lookup. This requires threading destination information through from `find_routes()` into the ranking step.

---

## ✅ Synchronous blocking calls inside async request handler — FIXED

**Fixed in:** `backend/main.py` — both `resolve_location` calls and `_coords_for_location` calls wrapped in `await loop.run_in_executor(...)`; Anthropic call switched to `AsyncAnthropic.messages.create()`.

---

## ✅ No user-facing message when location is outside coverage area — FIXED

**Fixed in:** `backend/main.py` — added 400 check after `resolve_location(request.destination)` with explicit coverage area message.

---

## ✅ Anthropic client instantiated on every request — FIXED

**Fixed in:** `backend/main.py` — `AsyncAnthropic` client now instantiated once at module level as `_claude_client`, reused across all requests.

---

## ✅ Bus fullness filter may silently return zero results — FIXED + VERIFIED

**Fixed in:** `backend/cta_client.py` — `_fetch_bus_chunk()` now normalizes `psgld` at read time via `.replace(" ", "_").upper()` before storing it. `_FULLNESS_API_VALUES` in `main.py` already uses UPPER_SNAKE; a comment was added documenting the normalization contract.

**Live API finding (2026-04-09):** After testing 30+ predictions across multiple high-traffic routes and stops (Michigan Ave, State St, Belmont), `psgld` is consistently empty (`""`) in all CTA Bus Tracker v3 API responses. CTA includes the field in the JSON but does not currently populate it with load data. The normalization fix is still correct for future-proofing if CTA enables this data.

**UI action taken:** The Bus Fullness `<select>` in `frontend/src/App.jsx` is commented out but preserved in full. All backend filter logic (`_FULLNESS_API_VALUES`, the `bus_fullness` filter in `/recommend`, `psgld` normalization) is intact and ready. Re-enable the commented `<select>` block when CTA starts populating this field.

---

## 🟢 Missing validation for CTA_BUS_API_KEY when bus transit mode is requested

**File:** `backend/main.py` `/recommend` endpoint (lines ~280–285)

**What happens:** The endpoint checks for `CTA_TRAIN_API_KEY` and `ANTHROPIC_API_KEY` at startup, but not for `CTA_BUS_API_KEY`. If `transit_mode` includes "Bus" and `CTA_BUS_API_KEY` is not set, the code attempts to fetch bus arrivals anyway, resulting in an empty list. No error is raised, and the request proceeds with no bus data.

**Effect:** Users requesting bus options may get incomplete results without any indication that the bus API key is missing. The app appears to work but silently omits bus information.

**Fix:** Add a check similar to the train key: `if not bus_key: raise HTTPException(status_code=500, detail="CTA_BUS_API_KEY not configured in backend/.env")` if `request.transit_mode in ("Bus", "All")`.

---

## 🟢 Routing engine exception swallows traceback

**File:** `backend/main.py` lines 365–366

**What happens:** `except Exception as exc: print(f"[main] Routing engine error: {exc}")` logs only the exception message string, not the full stack trace. In production (Railway logs), diagnosing a routing failure requires a full traceback — the current log line shows only the top-level error with no context about which function failed or why.

**Fix:** Replace with `import traceback; traceback.print_exc()` or add `exc_info=True` if switching to the `logging` module.

---

## 🟢 Bus routing may use wrong direction sequence for stops served by multiple directions

**File:** `backend/transit_graph.py` — `find_bus_routes()` (around line 820); `get_bus_stop_sequences()` (around line 480)

**What happens:** Bus stop sequences are keyed by `(route_short_name, direction_id)` where `direction_id` is "0" or "1" from GTFS. The `board_index` maps each `stop_id` to the last encountered `(short_name, direction_id, index)` when building from sequences. If a bus stop is served by both directions of the same route, `board_index` only keeps the entry for the last direction processed. When matching a live bus arrival (which has a direction string like "Northbound"), the code uses the sequence for the wrong direction if the arrival's direction doesn't match the kept `direction_id`.

**Effect:** Bus routes may be calculated using the wrong stop sequence, leading to incorrect exit stop selection and in-vehicle times. The route may show boarding at the wrong position in the sequence or fail to find a valid route.

**Fix:** Modify `get_bus_stop_sequences()` to key sequences by `(route_short_name, direction_string)` instead of `direction_id`, but GTFS doesn't have direction strings. Alternatively, map the API's direction strings to GTFS `direction_id` per route, or ensure `board_index` handles multiple directions properly (e.g., by making it a list or dict of possibilities). Since bus arrivals include the direction string, use it to select the correct sequence.

---

## 🟢 PWA manifest `purpose: "any maskable"` on a single icon entry

**File:** `frontend/vite.config.js` line 31

**What happens:** The 512px icon entry uses `purpose: "any maskable"` — combining both purposes in one entry. The PWA spec and Chrome's installability criteria require these as two separate icon entries. Some validators, browser installs, and app store submissions reject the combined form, and the adaptive icon (maskable) may not display correctly on Android.

**Fix:** Split into two icon entries:
```js
{ src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
{ src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
```

---

## 🟢 No validation when origin and destination resolve to the same location

**File:** `backend/main.py` `/recommend` endpoint

**What happens:** If a user submits the same location for both origin and destination (or two locations that geocode to the same coordinates), the routing engine finds zero-length paths and returns empty results. No error message is shown — the UI renders a Claude recommendation with no route cards and no explanation.

**Fix:** After resolving both locations, check if the resolved coordinates are within ~100m of each other and return a 400 with a message like "Your origin and destination appear to be the same location."

---

## ✅ `osmnx` import inside `try` block masks misconfigured deployments — FIXED

**Fixed in:** `backend/walking.py` — `import osmnx as ox` moved to module level; removed from `_load_graph()` and from inside the `try` block in `walk_minutes()`. An import failure now raises immediately at startup rather than being silently caught and falling back to Haversine estimates.

---

## 🟢 `max_tokens=750` misaligned with prompt instruction "3-4 sentences"

**File:** `backend/main.py` line 382 (token limit); line ~266 (prompt instruction)

**What happens:** `max_tokens` was raised to 750 for testing. The Claude prompt still says "Keep it to 3-4 sentences — the rider is probably standing outside." Claude will usually respect the instruction, but with 750 tokens available it may occasionally write longer responses. In production, the two should be re-aligned.

**Note:** This is an intentional testing-phase setting — not a pre-launch bug. Re-align before public launch: either lower `max_tokens` to ~350–400 and/or update the prompt to match the intended response length.

---

## 🟢 Intermodal routing not supported (train + bus in one trip)

**Scope:** `backend/transit_graph.py`, `backend/main.py`

**What happens:** Train and bus routes are computed independently. A combined trip like "walk → Red Line → transfer to bus 36 → destination" is never surfaced as a structured route option. Claude may suggest such a combination in its text recommendation, but it won't appear as a route card with leg-by-leg breakdown and accurate timing.

**Why deferred:** The majority of Chicago trips are served by train-only or bus-only options. Claude can already suggest intermodal trips conversationally. Implementing true intermodal routing requires integrating bus stops and bus route edges into the NetworkX train graph — a significant architectural addition best done post-launch with real trip data to validate against.

**Future fix:** Add bus stop nodes and bus route edges to the NetworkX graph in `transit_graph.py`, along with transfer edges between train stations and nearby bus stops. The routing algorithm would then naturally find train+bus paths as part of `find_routes()`.

---

## ✅ Representative trip selection may use off-peak schedules — FIXED

**Fixed in:** `backend/transit_graph.py` — `_load_weekday_service_ids()` added; `_load_representative_trips()` now loads all weekday candidate trips per direction; `_stream_stop_sequences()` selects the trip whose first-stop arrival is closest to noon (720 min) per line/direction. Single pass through `stop_times.txt`.

---

## 🔴 No error handling around Claude API call — FIX PRE-DEPLOYMENT

**File:** `backend/main.py` lines 412–420

**What happens:** The `await _claude_client.messages.create(...)` call (line 412) has no try-except. Any network error, Anthropic rate limit, authentication failure, or API outage will propagate as an unhandled exception and return a generic 500 with no useful message. Additionally, `message.content[0].text` on line 420 is accessed without checking whether `message.content` is non-empty or whether the first element is a text block — a tool-use or error response from the API causes an IndexError or AttributeError.

**Effect:** A transient Anthropic API error crashes the entire `/recommend` endpoint with an opaque 500. Users see "Internal Server Error" with no recovery guidance. The existing routing engine try-except blocks (lines 379, 398) correctly catch routing errors, but the Claude call has no equivalent.

**Fix:**
```python
try:
    message = await _claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=750,
        messages=[{"role": "user", "content": prompt}],
    )
    text_block = next((c for c in message.content if hasattr(c, "text")), None)
    if not text_block:
        raise ValueError("No text block in Claude response")
    recommendation = text_block.text
except Exception as exc:
    import traceback; traceback.print_exc()
    raise HTTPException(status_code=502, detail=f"Claude API error: {exc}")
```

---

## 🟡 Frontend `res.json()` crashes on non-JSON error responses — FIX PRE-DEPLOYMENT

**File:** `frontend/src/App.jsx` lines 130–132

**What happens:** When the backend returns a non-OK response, the code calls `await res.json()` unconditionally. If the server returns HTML (e.g., a Railway/nginx 502 or 504 gateway error), `res.json()` throws a `SyntaxError`. That error propagates to the `catch` block, which shows the raw `SyntaxError: Unexpected token '<'...` message to the user instead of a helpful error.

**Effect:** Gateway errors (which will happen on Railway cold starts or deploy restarts) show a cryptic parse error to the user instead of "Service temporarily unavailable."

**Fix:**
```javascript
if (!res.ok) {
  let msg = `Error ${res.status}`;
  try {
    const data = await res.json();
    msg = data.detail || msg;
  } catch {
    msg = `Service error (${res.status} ${res.statusText})`;
  }
  throw new Error(msg);
}
```

---

## ✅ Bus stop IDs silently truncated to 10 — no batching — FIXED

**Fixed in:** `backend/cta_client.py` — extracted `_fetch_bus_chunk()` helper; `get_bus_arrivals()` now splits stop IDs into chunks of 10 and fires all chunks concurrently via `asyncio.gather`. Results merged and sorted by arrival time.
