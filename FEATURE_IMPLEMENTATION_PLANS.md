# Feature Implementation Plans

Chunked plans for upcoming major features. Work through each feature's chunks in order, one chunk per session or per commit. Do not start a chunk until all previous chunks are complete.

---

# Feature A — Train Station Exit Guidance

## Overview

Many CTA train stations have multiple exits spread across a city block. The app currently routes a rider to the alighting station's centroid coordinates and gives OSMnx walk directions from there. This feature improves the final walk leg by:

1. Identifying available exits at the alighting station
2. Recommending the exit that minimises the remaining walk to the destination
3. Optionally letting the rider choose a different exit and recalculating directions

**Status: ⬜ Not started**

---

## Data note — before starting any chunk

CTA GTFS `stops.txt` contains platform stops (30000–39999) and parent stations (40000–49999) but does **not** contain named exit locations. The best free source is OpenStreetMap `railway=subway_entrance` nodes. An Overpass API query can pull all Chicago CTA subway entrance nodes with their lat/lon and `ref` tag (which often names the exit, e.g. "Damen Ave / Milwaukee Ave").

Manual curation of the 15–20 most-used stations is an acceptable first pass and avoids a full OSM data pipeline.

---

## Chunk 1 — Data: Build exit coordinates file

**Files:** `backend/fetch_station_exits.py` (new), `backend/station_exits.json` (generated)

**What to build:**
- Write a one-time script `fetch_station_exits.py` that queries the Overpass API for all `railway=subway_entrance` nodes within Chicago's bounding box
- For each entrance node, extract: `osm_id`, `lat`, `lon`, `name` or `ref` (exit label), and the nearest CTA parent station mapid (by haversine distance to known station coordinates from `_load_parent_stations()`)
- Write results to `backend/station_exits.json` as:
  ```json
  {
    "40900": [
      {"label": "Damen Ave", "lat": 41.9099, "lon": -87.6789},
      {"label": "Milwaukee Ave", "lat": 41.9092, "lon": -87.6798}
    ]
  }
  ```
  where the key is the CTA parent station mapid.
- `station_exits.json` should be committed to the repo (it's small, static, manually correctable)
- After generating, manually review and correct any misassigned exits for the 10–15 most-used stations

**Notes:**
- Overpass query: `node["railway"="subway_entrance"](41.64,-87.94,42.02,-87.52)`
- If OSM coverage is sparse for a station, add entries manually — the JSON format is simple
- This script is run once (or re-run after OSM data improves); it does not run at server startup

---

## Chunk 2 — Backend: Load exit data at startup

**Files:** `backend/transit_graph.py`

**What to build:**
- Add `_load_station_exits() -> dict[str, list[dict]]` — reads `station_exits.json` at import time, returns `{mapid: [{label, lat, lon}, ...]}`. Returns `{}` gracefully if file not found (so the server still starts without exits data).
- Store result in module-level `_station_exits` dict (same pattern as `_shape_lookup`)
- Add public helper `get_station_exits(mapid: str) -> list[dict]` — returns the exit list for a station, or `[]` if none known
- Call nothing extra in `warm_up()` — this is loaded at import time (data is tiny, ~5 KB)

---

## Chunk 3 — Backend: Exit selection logic

**Files:** `backend/transit_graph.py`

**What to build:**
- Add `best_exit(mapid: str, dest_lat: float, dest_lon: float) -> dict | None`
  - Gets exits for the station via `get_station_exits(mapid)`
  - If no exits known: returns `None` (caller falls back to station centroid)
  - Scores each exit by `street_walk_minutes(exit_lat, exit_lon, dest_lat, dest_lon)`
  - Returns the exit dict with the minimum walk time, with an added `"walk_minutes"` key

**Notes:**
- `street_walk_minutes` is already imported and cached — no extra I/O
- Do not call `street_walk_directions` here — that happens in Chunk 4 once the exit is selected

---

## Chunk 4 — Backend: Thread exit into walk leg + API response

**Files:** `backend/transit_graph.py`, `backend/main.py`

**What to build:**

In `transit_graph.py`:
- In `_path_to_route()`, for the **destination walk leg** (when `to_node == DEST`):
  - Call `best_exit(from_node, dest_lat, dest_lon)`
  - If an exit is found: use its `(lat, lon)` as the walk origin instead of the station centroid; set `exit_label` on the `WalkLeg`
  - If no exit found: behaviour unchanged (station centroid as before)
- In `find_bus_routes()`, same change on the exit walk leg
- Add `exit_label: str = ""` field to `WalkLeg` dataclass

In `main.py`:
- Add `"exit_label": leg.exit_label` to the walk leg serialization in the `/recommend` response

**Notes:**
- `walk_directions` is called with the exit coords instead of station centroid — the street-level directions will now start from the right point
- `path_points` similarly uses exit coords as origin — the dashed walk line on the map will start from the exit, not the station centre

---

## Chunk 5 — Frontend: Show exit label on final walk leg

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`

**What to build:**
- In `WalkLegItem`: if `leg.exit_label` is present and `leg.to === "Your destination"`, show the exit label between the summary line and the Steps toggle:
  ```
  Walk 6 min to your destination
  Exit: Milwaukee Ave ›
  ↓ S on Milwaukee Ave · 2 min
  ↑ W on Dickens Ave · 1 min
  ```
- Style the exit label as a small secondary line (muted color, slightly smaller than the main leg text)
- The Steps toggle behaviour is unchanged — it expands/collapses the street-level directions below the exit label

**Future extension (Chunk 6, separate session):** Let the rider tap the exit label to see all available exits and pick a different one. This requires a client-side recalculation — the `available_exits` array would need to be included in the API response (add in Chunk 4 when ready to build this).

---

# Feature B — Intermodal Routing (Train + Bus in One Trip)

## Overview

Train and bus routes are currently found independently (`find_routes()` for trains, `find_bus_routes()` for buses) and merged by total time in `main.py`. A combined trip — walk → Red Line → transfer to bus 36 → destination — is never surfaced as a structured route card.

This feature integrates bus stops and bus route edges into the existing NetworkX graph so `find_routes()` naturally discovers train+bus paths alongside pure train paths.

**Status: ⬜ Not started**

**Prerequisite:** This is a significant architectural change. Do not start until Phase 6 deployment is complete and the app is running stably in production. Real usage patterns should inform whether intermodal routes are actually needed before investing this effort.

---

## Chunk 1 — Backend: Add bus stop nodes to the graph

**Files:** `backend/transit_graph.py`

**What to build:**
- In `_build_graph()`, after building the train graph, add bus parent stop nodes
- CTA bus stops (0–29999) are already loaded by `_load_bus_stop_lookup()` — reuse it
- Add each bus stop as a node: `G.add_node(stop_id, node_type="bus", lat=..., lon=...)`
- Do not add any edges yet — just nodes
- Update the module docstring to reflect that the graph now contains both train stations and bus stops

**Notes:**
- Bus stops number ~11,000 in CTA GTFS — adding them as nodes is cheap (NetworkX nodes are just dict entries)
- The existing `__ORIGIN__` / `__DEST__` virtual node pattern in `find_routes()` is unchanged

---

## Chunk 2 — Backend: Add bus route edges to the graph

**Files:** `backend/transit_graph.py`

**What to build:**
- After adding bus stop nodes, stream `stop_times.txt` for the representative bus trip per `(route_id, direction_id)` (this data is already computed in `get_bus_stop_sequences()` — reuse the sequence table rather than re-streaming)
- For each consecutive pair of stops in a bus sequence, add a directed transit edge:
  ```python
  G.add_edge(from_stop_id, to_stop_id,
             weight=leg_minutes,
             route_id=short_name,
             direction_id=did,
             line=direction_string,   # e.g. "Northbound"
             edge_type="transit",
             mode="bus")
  ```
- Add `mode="train"` to existing train transit edges for disambiguation
- Update `_path_to_route()` to handle `mode="bus"` transit edges — the leg assembly is the same as for trains but `line_code = route_short_name` (e.g. "36") and `line = direction_string`

**Notes:**
- Bus sequences are already in memory via `get_bus_stop_sequences()` — no extra file I/O
- `get_bus_stop_sequences()` must be called before `_build_graph()` completes (or graph build must depend on it). Currently `warm_up()` calls both — restructure so bus sequences are loaded first.

---

## Chunk 3 — Backend: Train-to-bus and bus-to-train transfer edges

**Files:** `backend/transit_graph.py`

**What to build:**
- After adding all nodes and transit edges, add transfer edges between train stations and nearby bus stops
- For each train station, find all bus stops within 0.15 miles (haversine) using `_haversine_miles`
- For each nearby bus stop, add bidirectional walk edges:
  ```python
  walk_min = street_walk_minutes(station_lat, station_lon, stop_lat, stop_lon)
  G.add_edge(station_mapid, bus_stop_id, weight=walk_min, edge_type="walk", route_id="walk")
  G.add_edge(bus_stop_id, station_mapid, weight=walk_min, edge_type="walk", route_id="walk")
  ```
- Cap at 5 min walk — any bus stop more than 5 min walk from a train station is not a useful transfer
- Log transfer edge count at startup alongside existing train/transit edge counts

**Notes:**
- 0.15 miles ≈ 240m — a comfortable transfer walk distance
- `street_walk_minutes` is cached — repeated calls for the same coordinate pairs are free
- This step is the performance-sensitive one: ~150 stations × up to ~20 nearby stops = ~3,000 walk time lookups at startup. Acceptable given the existing startup time of 30–90s.

---

## Chunk 4 — Backend: Update `_path_to_route` for mixed paths

**Files:** `backend/transit_graph.py`

**What to build:**
- `_path_to_route()` currently handles `edge_type in ("transit", "transfer", "walk")`. Extend it to correctly handle bus transit edges (`mode="bus"`) — the `TransitLeg` assembly is identical, just ensure `line` and `line_code` are set correctly for bus legs
- Handle the case where a path contains both train and bus transit legs with a walk transfer between them — the existing same-station transfer detection logic may need updating since bus stop IDs and train mapids are in different ID ranges and won't accidentally collide
- Bus-only paths found via the unified graph should be deduplicated against `find_bus_routes()` results — once intermodal routing is enabled, consider deprecating `find_bus_routes()` in favour of the unified graph (separate decision, document as a TODO)

---

## Chunk 5 — Backend: Update `find_routes()` and `main.py` integration

**Files:** `backend/transit_graph.py`, `backend/main.py`

**What to build:**

In `transit_graph.py`:
- Update `find_routes()` to also add origin→bus_stop walk edges and bus_stop→DEST walk edges (same pattern as the existing train station virtual edges), so the unified graph finds train+bus paths
- Increase `n_routes` default to 5 to surface intermodal options alongside pure train/bus options

In `main.py`:
- Once `find_routes()` returns intermodal routes, `find_bus_routes()` becomes partially redundant. For now: keep both, merge as before, deduplicate on identical route fingerprints (same sequence of line_codes and stop names)
- The response format is unchanged — legs already serialize correctly regardless of mode

---

## Chunk 6 — Frontend: Verify intermodal route cards render correctly

**Files:** `frontend/src/App.jsx`, `frontend/src/MapView.jsx`

**What to verify/fix:**
- Route cards with mixed train + bus legs should already render correctly — `RouteLegs` handles each leg by type, and bus legs already have `BUS_DIRECTION_COLORS` + `line_code` pill
- Map rendering: `renderRoute()` uses `leg.line` to pick color — verify `BUS_DIRECTION_COLORS` lookup works for bus legs within a mixed route
- Walk transfer legs between train station and bus stop should render as dashed gray walk segments on the map (same as other walk legs) — verify `leg.path` is populated for these
- Manual test: find a real Chicago trip that benefits from an intermodal route (e.g. Brown Line to Western, then bus 49 south) and confirm the route card and map look correct

---
