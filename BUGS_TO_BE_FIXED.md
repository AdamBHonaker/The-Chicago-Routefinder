# Bugs To Be Fixed

Known issues catalogued for future fixing. Severity: 🔴 High · 🟡 Medium · 🟢 Low.

---

## ✅ `load_dotenv()` called after local module imports — FIXED

**Fixed in:** `backend/main.py` — `load_dotenv()` moved to before the `from gtfs_loader import ...` line.

`gtfs_loader.py` reads `GOOGLE_MAPS_API_KEY = os.getenv(...)` at module level (import time). When Python processes `from gtfs_loader import ...` in `main.py`, it immediately executes all of `gtfs_loader.py`. `load_dotenv()` was previously called after those imports, so the `.env` file had not yet been loaded into `os.environ` when `_GOOGLE_MAPS_API_KEY` was captured — causing it to always be `""` regardless of what was in `.env`. Moving `load_dotenv()` before the local imports ensures the environment is populated before any module reads from it.

---

## ✅ `line-cap` and `line-join` placed in MapLibre `paint` instead of `layout` — FIXED

**File:** `frontend/src/MapView.jsx` lines 101–108

**What happens:** In MapLibre GL JS, `line-cap` and `line-join` are **layout** properties, not paint properties. Placing them in the `paint` object silently ignores them. Transit route polylines render with sharp square ends and miter joins instead of the intended rounded style.

**Current (wrong):**
```js
paint: { "line-color": color, "line-width": 5, "line-cap": "round", "line-join": "round" },
```

**Fix:**
```js
layout: { "line-cap": "round", "line-join": "round" },
paint:  { "line-color": color, "line-width": 5 },
```

---

## ✅ `wait_minutes === 0` ("Due") shows no indicator in RouteCard — FIXED

**File:** `frontend/src/App.jsx` line 141

**What happens:** `const waitNote = route.wait_minutes > 0 ? ...` evaluates to `""` for both `null` (no live data) and `0` (train/bus Due right now). A rider whose train is arriving immediately sees no indication of that in the route card header, even though the Claude recommendation text says "Due." The backend already distinguishes these three cases correctly — the frontend card just doesn't match.

**Fix:**
```js
const waitNote =
  route.wait_minutes === null ? ""
  : route.wait_minutes === 0  ? " · Due now"
  : ` · ${route.wait_minutes} min wait`;
```

---

## ✅ No `AbortController` — stale results if user re-submits during a pending search — FIXED

**File:** `frontend/src/App.jsx` lines 215–260

**What happens:** If the user corrects their destination and presses "Get Route" while the previous fetch is still in-flight, both requests run concurrently. Whichever finishes last wins and calls `setResult()`. If the older search finishes after the newer one, the user sees stale results with no indication anything went wrong.

**Fix:** Add an `AbortController` ref, cancel the in-flight request at the start of each `handleSubmit`, and pass `signal: abortRef.current.signal` to `fetch`. In the catch block, ignore `AbortError` so a cancelled search doesn't surface as an error message.

```js
const abortRef = useRef(null);

// At the top of handleSubmit:
if (abortRef.current) abortRef.current.abort();
abortRef.current = new AbortController();

// In the fetch call:
const res = await fetch(`${BACKEND_URL}/recommend`, {
  ...,
  signal: abortRef.current.signal,
});

// In the catch block:
} catch (err) {
  if (err.name === "AbortError") return;
  setError(err.message || "Something went wrong. Please try again.");
}
```

---

## ✅ PWA service worker pre-caches all PNGs including transit photos — FIXED

**Fixed in:** `frontend/vite.config.js` — `globPatterns` now explicitly lists `icon-*.png` and `apple-touch-icon.png` instead of `**/*.png`, so only icon PNGs are pre-cached. A `StaleWhileRevalidate` runtime cache entry for `/transit-photos/` was added so photos load from cache when available and update in the background.

---

## ✅ `renderMarkdown` strips `**bold**` but not `*italic*` — FIXED

**File:** `frontend/src/App.jsx` lines 51–56

**What happens:** The `renderMarkdown` function strips `## headers` and `**bold**` but does not handle `*italic*` or `_italic_`. Claude's prompt instructs plain English but may occasionally italicize route names or times, leaving literal `*asterisks*` or `_underscores_` visible to riders in the recommendation text.

**Fix:** Add `.replace(/\*([^*]+)\*/g, "$1").replace(/_([^_]+)_/g, "$1")` to the chain.

---

## ✅ `_load_weekday_service_ids()` only checks Monday + Tuesday + Wednesday — FIXED

**File:** `backend/transit_graph.py` lines 175–178

**What happens:** The condition requires `monday == 1 AND tuesday == 1 AND wednesday == 1` but does not check Thursday or Friday. A GTFS service active only on Thursday–Friday would be excluded from the "weekday" representative trip pool, potentially selecting an off-peak or weekend schedule for that route instead.

**Fix:** Add `and row.get("thursday", "0").strip() == "1" and row.get("friday", "0").strip() == "1"` to the condition (or use `any` across all five weekday columns).

---

## ✅ Train arrival datetime: `.replace(tzinfo)` wrong for ISO strings with UTC offset — FIXED

**File:** `backend/cta_client.py` line 80

**What happens:** The `"T" in arr_str` branch calls `datetime.fromisoformat(arr_str).replace(tzinfo=CHICAGO_TZ)`. If the CTA API ever returns an ISO string with a timezone offset (e.g. `"2024-01-01T20:32:00+00:00"`), `fromisoformat` parses a UTC-aware datetime. `.replace(tzinfo=CHICAGO_TZ)` then re-labels the hours as Chicago time without converting them — making the arrival appear 5–6 hours off. CTA currently returns the space-separated format so this branch is rarely hit, but the bug exists as a latent time-bomb.

**Fix:**
```python
arr_dt = datetime.fromisoformat(arr_str)
if arr_dt.tzinfo is not None:
    arr_dt = arr_dt.astimezone(CHICAGO_TZ)
else:
    arr_dt = arr_dt.replace(tzinfo=CHICAGO_TZ)
```

---

## ✅ Destination walk times computed in wrong direction throughout — FIXED

**Files:** `backend/transit_graph.py` lines 991–994, `backend/gtfs_loader.py` line 558, `backend/transit_graph.py` line 1127

**What happens:** In three places, the walk time from a destination station/stop to the user's destination is computed with the arguments reversed — using `walk_minutes(dest_lat, dest_lon, station_lat, station_lon)` (destination → station) instead of the direction the user actually walks: `walk_minutes(station_lat, station_lon, dest_lat, dest_lon)` (station → destination). The displayed walk path (`street_walk_path`) is computed in the correct direction in all cases. On Chicago's largely bidirectional grid this produces the same result, but on one-way street segments the displayed walk time and the drawn path can diverge.

**Fix:** Swap the argument order in the three affected `walk_minutes()` calls so origin and destination match the direction of travel.

---

## ✅ `validate_and_report()` uses `encoding="utf-8"` instead of `"utf-8-sig"` — FIXED

**File:** `backend/fetch_gtfs.py` line 79

**What happens:** All GTFS file readers in `transit_graph.py` and `gtfs_loader.py` use `encoding="utf-8-sig"` to strip a potential BOM header. `validate_and_report()` uses plain `"utf-8"`. If CTA's GTFS zip contains BOM-prefixed files, the reported row count will be off by one (the BOM is counted as content in the first line). Low severity since this function is display-only, but creates an inconsistency in the file opening pattern.

**Fix:** Change `open(path, encoding="utf-8")` to `open(path, encoding="utf-8-sig")` in `validate_and_report()`.

---

## ✅ `G_base.copy()` called on every train routing request — FIXED

**Fixed in:** `backend/transit_graph.py` — added `import threading` and a module-level `_thread_local: threading.local`. `find_routes()` now keeps a thread-local copy of `G_base` (`_thread_local.G`) keyed by `id(G_base)`. The copy is created once per executor thread (FastAPI's thread pool is typically 4–16 workers) and reused for all subsequent requests on that thread. `__ORIGIN__` and `__DEST__` virtual nodes are added before routing and removed in a `finally` block to leave the thread-local graph clean for the next request.

---

## ✅ `_coords_for_location()` duplicates fuzzy-match logic from `resolve_location()` — FIXED

**Fixed in:** `backend/gtfs_loader.py` — added `_FUZZY_STOP_WORDS` (frozenset) and `fuzzy_match_neighborhood(query)` as a public module-level helper. `resolve_location()` now calls `fuzzy_match_neighborhood()` instead of reimplementing the loop inline. `backend/main.py` — imports `fuzzy_match_neighborhood` from `gtfs_loader`; `_coords_for_location()` uses it for step 2 instead of its own copy of the logic. The `SequenceMatcher` import and the inline `_STOP_WORDS` dict were removed from `main.py`.

---

## ✅ Redundant `walk_minutes` recomputation for destination stations in `find_routes()` — FIXED

**Fixed in:** `backend/transit_graph.py` `find_routes()` — the per-station `street_walk_minutes()` call and `dest_walk[mapid] = walk_min` overwrite inside the `dest_stations` loop were removed. `dest_walk` is now populated once from `dest_stations[*]["walk_minutes"]` (already computed by `find_nearest_train_stations(walk_to_station=False)` using the same function) and those values are used directly as edge weights when adding the station→DEST edges.

---

## ✅ `photoFadeTimer` ref not cleared on component unmount — FIXED

**File:** `frontend/src/App.jsx` lines 195–261

**What happens:** `photoFadeTimer.current = setTimeout(...)` sets a 1-second timer. There is no `useEffect` cleanup to cancel this timer if the `App` component unmounts while the timeout is pending. In React 18 StrictMode (active during development), components are intentionally mounted/unmounted/remounted to surface this class of bug. This triggers a state update on an unmounted instance, generating a console warning that can obscure real errors.

**Fix:** Add a `useEffect` cleanup:
```js
useEffect(() => {
  return () => { if (photoFadeTimer.current) clearTimeout(photoFadeTimer.current); };
}, []);
```

---

## 🟢 Missing validation for CTA_BUS_API_KEY when bus transit mode is requested

**Fixed in:** `backend/main.py` + `backend/transit_graph.py`

`_build_arrival_lookup` now returns `{(line_code, station_mapid): {destNm: earliest_minutes}}` — grouped by destination rather than taking the global earliest. `_rank_routes` now accepts `dest_lat`/`dest_lon` and uses a dot-product bearing test to select the correct direction: it computes the vector from the boarding station to the exit station, then for each available `destNm` computes the vector from the boarding station to that terminal (looked up via new `get_station_by_name()` in `transit_graph.py`), and picks the terminal whose direction most closely matches the route's direction of travel. Falls back to the earliest arrival if station coordinates are unavailable. Two new helpers added to `transit_graph.py`: `get_station_coords(mapid)` and `get_station_by_name(name)`, both backed by the already-cached `_build_graph()`.

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

## ✅ Missing validation for CTA_BUS_API_KEY when bus transit mode is requested — FIXED

**File:** `backend/main.py` `/recommend` endpoint (lines ~280–285)

**What happens:** The endpoint checks for `CTA_TRAIN_API_KEY` and `ANTHROPIC_API_KEY` at startup, but not for `CTA_BUS_API_KEY`. If `transit_mode` includes "Bus" and `CTA_BUS_API_KEY` is not set, the code attempts to fetch bus arrivals anyway, resulting in an empty list. No error is raised, and the request proceeds with no bus data.

**Effect:** Users requesting bus options may get incomplete results without any indication that the bus API key is missing. The app appears to work but silently omits bus information.

**Fix:** Add a check similar to the train key: `if not bus_key: raise HTTPException(status_code=500, detail="CTA_BUS_API_KEY not configured in backend/.env")` if `request.transit_mode in ("Bus", "All")`.

---

## ✅ Routing engine exception swallows traceback — FIXED

**File:** `backend/main.py` lines 365–366

**What happens:** `except Exception as exc: print(f"[main] Routing engine error: {exc}")` logs only the exception message string, not the full stack trace. In production (Railway logs), diagnosing a routing failure requires a full traceback — the current log line shows only the top-level error with no context about which function failed or why.

**Fix:** Replace with `import traceback; traceback.print_exc()` or add `exc_info=True` if switching to the `logging` module.

---

## ✅ Bus routing may use wrong direction sequence for stops served by multiple directions — FIXED

**Fixed in:** `backend/transit_graph.py` `find_bus_routes()` — `board_index` type changed from `dict[str, tuple[str, str, int]]` to `dict[str, list[tuple[str, str, int]]]`; population now uses `setdefault(..., []).append(...)` instead of plain assignment so all direction entries for a stop are preserved rather than overwriting. In the arrival loop, candidates are filtered to entries matching the arrival's route number, then all valid direction candidates are tried: each is scanned forward to find the best exit stop, and the direction whose exit stop is closest to the destination wins. `seen_route_dirs` is still checked per-candidate to avoid duplicates. `stops = sequences[route_dir_key]` is now assigned from the winning candidate after the selection loop.

---

## ✅ PWA manifest `purpose: "any maskable"` on a single icon entry — FIXED

**File:** `frontend/vite.config.js` line 31

**What happens:** The 512px icon entry uses `purpose: "any maskable"` — combining both purposes in one entry. The PWA spec and Chrome's installability criteria require these as two separate icon entries. Some validators, browser installs, and app store submissions reject the combined form, and the adaptive icon (maskable) may not display correctly on Android.

**Fix:** Split into two icon entries:
```js
{ src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
{ src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
```

---

## ✅ No validation when origin and destination resolve to the same location — FIXED

**File:** `backend/main.py` `/recommend` endpoint

**What happens:** If a user submits the same location for both origin and destination (or two locations that geocode to the same coordinates), the routing engine finds zero-length paths and returns empty results. No error message is shown — the UI renders a Claude recommendation with no route cards and no explanation.

**Fix:** After resolving both locations, check if the resolved coordinates are within ~100m of each other and return a 400 with a message like "Your origin and destination appear to be the same location."

---

## ✅ `osmnx` import inside `try` block masks misconfigured deployments — FIXED

**Fixed in:** `backend/walking.py` — `import osmnx as ox` moved to module level; removed from `_load_graph()` and from inside the `try` block in `walk_minutes()`. An import failure now raises immediately at startup rather than being silently caught and falling back to Haversine estimates.

---

## ✅ `max_tokens=750` misaligned with prompt instruction "3-4 sentences" — FIXED

**File:** `backend/main.py` line 382 (token limit); line ~266 (prompt instruction)

**What happens:** `max_tokens` was raised to 750 for testing. The Claude prompt still says "Keep it to 3-4 sentences — the rider is probably standing outside." Claude will usually respect the instruction, but with 750 tokens available it may occasionally write longer responses. In production, the two should be re-aligned.

**Note:** This is an intentional testing-phase setting — not a pre-launch bug. Re-align before public launch: either lower `max_tokens` to ~350–400 and/or update the prompt to match the intended response length.

---

## ✅ Representative trip selection may use off-peak schedules — FIXED

**Fixed in:** `backend/transit_graph.py` — `_load_weekday_service_ids()` added; `_load_representative_trips()` now loads all weekday candidate trips per direction; `_stream_stop_sequences()` selects the trip whose first-stop arrival is closest to noon (720 min) per line/direction. Single pass through `stop_times.txt`.

---

## ✅ No error handling around Claude API call — FIXED

**Fixed in:** `backend/main.py` — `_claude_client.messages.create()` wrapped in try/except; response text extracted via `next((c for c in message.content if hasattr(c, "text")), None)` to safely handle non-text blocks; raises HTTP 502 with the error message on any failure; full traceback printed to server logs.

---

## ✅ Frontend `res.json()` crashes on non-JSON error responses — FIXED

**Fixed in:** `frontend/src/App.jsx` — non-OK responses now attempt `res.json()` inside a try/catch; if parsing fails (e.g. Railway/nginx 502 returning HTML), falls back to `"Service error (502 Bad Gateway)"`. Users always see a readable message instead of a cryptic `SyntaxError`.

---

## ✅ Bus stop IDs silently truncated to 10 — no batching — FIXED

**Fixed in:** `backend/cta_client.py` — extracted `_fetch_bus_chunk()` helper; `get_bus_arrivals()` now splits stop IDs into chunks of 10 and fires all chunks concurrently via `asyncio.gather`. Results merged and sorted by arrival time.

---

## ✅ `prdctdn` value "APPROACHING" (and similar) silently drops bus arrival — FIXED

**Fixed in:** `backend/cta_client.py` — replaced `int(prdctdn)` with an `isdigit()` guard: numeric strings are parsed as before; `"DUE"`, `"APPROACHING"`, and any other non-numeric value all map to `0` minutes instead of raising `ValueError` and silently dropping the arrival.

---

## ✅ `wait=0` conflates "no arrival data" with "train is Due now" — FIXED

**Fixed in:** `backend/main.py` — `_rank_routes()` now initialises `wait: int | None = None` (no data) instead of `0`. The empty `dest_map` branch explicitly sets `wait = None`. `total` computation uses `wait if wait is not None else 0`. `_format_routes()` now has three branches: `wait is None` → no note, `wait == 0` → `"next train Due"` / `"next bus Due"`, `wait > 0` → `"next train in N min"` / `"next bus in N min"`.

---

## ✅ Bus shape lookup uses `route_short_name` instead of `route_id` — FIXED

**Fixed in:** `backend/transit_graph.py` `_build_shape_lookup()` — after building the primary `(route_id, direction_id)` entries, the function now reads `routes.txt` once more to get each route's `route_short_name`. For any bus route where `route_short_name != route_id`, an alias entry `(route_short_name, direction_id)` is added to `_shape_lookup` via `setdefault` (so an existing `route_id` entry is never overwritten). `find_bus_routes()` already calls `get_shape(short_name, did)` — no change needed there.

---

## ✅ Transfer `WalkLeg` missing turn-by-turn directions — FIXED

**Fixed in:** `backend/transit_graph.py` `_path_to_route()` — the inter-station transfer `WalkLeg` constructor now includes `directions=street_walk_directions(flat, flon, tlat, tlon)`, consistent with the origin and destination walk legs. Local variables `flat/flon/tlat/tlon` introduced to avoid duplicating the coordinate lookups.

---

## ✅ `geocode_google` not thread-safe under concurrent requests — FIXED

**Fixed in:** `backend/gtfs_loader.py` — added module-level `_geocode_lock = threading.Lock()` (imported `threading`). `geocode_google()` now uses a double-checked locking pattern: fast path reads the cache without a lock; slow path acquires the lock, re-checks the cache (so a second thread that waited doesn't make a second API call), then performs the network call, cache write, and counter increment inside the lock. All mutation of `_geocode_cache` and `_geocode_call_counter` is serialised.

---

## ✅ Unclosed file handle in `fetch_gtfs.py` validation step — FIXED

**Fixed in:** `backend/fetch_gtfs.py` `validate_and_report()` — bare `open(path, ...)` replaced with `with open(path, ...) as fh:` context manager. File handle is now released immediately after the row count, regardless of exceptions.
