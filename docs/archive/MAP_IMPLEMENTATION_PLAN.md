# Map Implementation Plan

> **STATUS: COMPLETE** — All 10 chunks implemented 2026-04-09. Phase 5.6 is done.

Decisions finalized 2026-04-09. All chunks below are designed to be worked on and completed independently, in the order listed. Do not start a chunk until all previous chunks are complete.

---

## Confirmed Design Decisions

| Decision | Choice |
|---|---|
| Map library | MapLibre GL JS v4 (v5 had WebGL2 init issues in React StrictMode) |
| Tile style | OpenFreeMap Liberty (`https://tiles.openfreemap.org/styles/liberty`) — Positron dropped; had null-typed expression errors in MapLibre v4/v5 |
| Route geometry | GTFS shape data (pre-computed at startup) — both train and bus |
| Walking leg geometry | OSMnx street network (already loaded) |
| Layout | Split panel — route cards left (40%), map right (60%) |
| Mobile breakpoint | 800px — collapses to stacked (cards top, map bottom) |
| Mobile min-heights | Route cards: 300px · Map: 350px |
| Route panel scroll | Independent (`overflow-y: auto`) — map stays fixed |
| Default route shown | Best route (index 0) |
| Route switching | User selects a route card → map snaps instantly to that route |
| Map initial state | Auto-fit to full route with padding on load and on route switch |
| Map unlock | "🔓 Unlock map" button, top-left within route padding. Disappears once unlocked. |
| Station dots | Train and bus intermediate stops — small colored dots |
| Station labels | Train and bus stop names — visible at zoom ≥ 15 only |
| Loading / no-routes state | Random transit photo (one per request), fills map panel with caption |
| Photo → map transition | Map pre-loads behind photo; photo fades out over 1 second |
| Route switching animation | Instant snap (no fly animation) |

**Pre-deployment checks (see HUMAN_TODO.md):**
- Confirm 40/60 panel ratio on real desktop screen
- Confirm 300px/350px min-heights on real mobile device
- Source and provide ≥ 10 transit photos

---

## Chunk 1 — Backend: Pre-compute GTFS shape lookup

**Files:** `backend/transit_graph.py`

**What to build:**
- At startup, parse `shapes.txt` into `shape_id → [[lat, lon], ...]`
- Parse `trips.txt` to build `(route_id, direction_id) → shape_id` mapping
- Build final lookup: `(route_id, direction_id) → [[lat, lon], ...]`
- For both train and bus routes (shapes.txt covers all CTA routes)
- Store in a module-level dict, populated during `warm_up()` alongside the existing graph build
- No per-request computation — lookup only at request time

**Output:** A function `get_shape(route_id, direction_id) -> list[list[float]] | None`

**Notes:**
- `shapes.txt` is large but still static — stream it like `stop_times.txt`, never load fully into memory
- Shape point order in `shapes.txt` is defined by `shape_pt_sequence` — must be sorted

---

## Chunk 2 — Backend: Shape clipping (board stop → exit stop)

**Files:** `backend/transit_graph.py`

**What to build:**
- Given a full route shape and two stop coordinates (boarding, exit), clip the shape to only the segment between those two stops
- Method: find the shape point closest to the boarding stop (by distance), find the shape point closest to the exit stop, return the slice between them
- This is done at request time (fast — just an index slice after two nearest-point lookups)
- Must handle the case where `get_shape()` returns `None` — fall back to a straight line between the two stops

**Output:** A function `clip_shape(shape_points, board_lat, board_lon, exit_lat, exit_lon) -> list[list[float]]`

---

## Chunk 3 — Backend: OSMnx walk geometry per leg

**Files:** `backend/walking.py`, `backend/main.py`

**What to build:**
- Add a new function `walk_path(origin_lat, origin_lon, dest_lat, dest_lon) -> list[list[float]]`
- Uses the already-loaded OSMnx graph to return the actual street-network path as a list of `[lat, lon]` points (not just the travel time)
- Returns a straight line between the two points as fallback if routing fails (same fallback logic as `walk_minutes()`)
- Cache with `lru_cache` keyed on the same 4 coordinates as `walk_minutes()`

**Notes:**
- `nx.shortest_path()` returns a list of node IDs — convert to coordinates using `G.nodes[node]['y']` (lat) and `G.nodes[node]['x']` (lon)
- This is called once per walk leg per request — acceptable cost since the graph is already in memory

---

## Chunk 4 — Backend: Thread geometry into `/recommend` response

**Files:** `backend/main.py`, `backend/transit_graph.py`

**What to build:**
- Update `TransitLeg` to carry `shape_points: list[list[float]]` — the clipped GTFS shape for that leg
- Update `WalkLeg` to carry `path_points: list[list[float]]` — the OSMnx street path for that leg
- Populate both during route construction in `find_routes()` and `find_bus_routes()`
- Serialize into the `/recommend` response under each leg:
  ```json
  {
    "type": "transit",
    "line": "Red Line",
    "line_code": "Red",
    "from": "Addison",
    "to": "Lake",
    "minutes": 18,
    "from_coords": [41.9473, -87.6534],
    "to_coords": [41.8846, -87.6278],
    "shape": [[41.9473, -87.6534], ..., [41.8846, -87.6278]]
  }
  ```
  ```json
  {
    "type": "walk",
    "from": "Your location",
    "to": "Addison",
    "minutes": 4,
    "path": [[41.9557, -87.6716], ..., [41.9473, -87.6534]]
  }
  ```
- Also include `origin_coords` and `dest_coords` at the top level of the response

**Notes:**
- If shape data is unavailable for a leg, fall back to `[from_coords, to_coords]` (straight line) — never omit the field
- Response size will increase — acceptable for a PWA (shapes are compact coordinate arrays)

---

## Chunk 5 — Frontend: Install MapLibre and restructure layout

**Files:** `frontend/package.json`, `frontend/src/App.jsx`, `frontend/src/App.css`

**What to build:**
- Install `maplibre-gl` via npm
- Restructure the app layout into a `layout` container with two panels:
  - `.panel-cards` — left, 40% width, `overflow-y: auto`, independent scroll
  - `.panel-map` — right, 60% width, fixed height (fills remaining viewport)
- At ≤ 800px breakpoint: panels stack vertically (cards top, map bottom)
  - Cards: `min-height: 300px`
  - Map: `min-height: 350px`
- The layout switch is implemented as a CSS class (e.g. `layout--split`, `layout--stacked`) so future view options can be added by swapping the class
- Map panel always present in the DOM (hidden or showing photo state before results)
- Import MapLibre CSS in `main.jsx` or `App.jsx`

---

## Chunk 6 — Frontend: Transit photo loading state

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`, `frontend/public/transit-photos/`

**What to build:**
- A `<TransitPhoto>` component that:
  - Picks one photo randomly from the available set on mount (one per request, not rotating)
  - Fills the map panel with `object-fit: cover`
  - Shows a caption bar at the bottom with the location name (no overlay — caption is below or on a clean strip)
- Shown when: `loading === true` OR `result !== null && result.routes.length === 0`
- When results with routes arrive: photo fades out over 1 second, revealing the pre-loaded map behind it
  - Implement as: both photo and map exist in the DOM simultaneously; map has `opacity: 0` initially; on results, map transitions to `opacity: 1` while photo transitions to `opacity: 0`, then photo is removed from DOM
- Photo manifest: a hardcoded array of `{ src, caption }` objects — easy to extend when more photos are added

**Dependency:** Requires photos to exist in `frontend/public/transit-photos/` (HUMAN_TODO item). Component can be built and tested with placeholder images first.

---

## Chunk 7 — Frontend: Map component (MapLibre init + base layer)

**Files:** `frontend/src/MapView.jsx` (new), `frontend/src/App.css`

**What to build:**
- A `<MapView route={route} />` component
- Initializes a MapLibre map with:
  - Style: `https://tiles.openfreemap.org/styles/liberty` *(Positron was dropped — see decisions table above)*
  - Initial center: Chicago (`[-87.65, 41.85]`), zoom 11 (shown before route data)
  - Navigation controls disabled by default (map is locked)
- Exposes a "🔓 Unlock map" button, absolutely positioned top-left within the route padding area
  - On click: enables map interaction (`map.scrollZoom.enable()`, `map.dragPan.enable()`, etc.), button disappears
- Map instance created once on component mount, held in a `useRef`
- Component accepts a `route` prop (the full route object from the API response)
- Cleans up map on unmount

**Notes:**
- MapLibre map must be initialized inside a `useEffect` after the container div is mounted
- The component should be structured so the map style, center, and zoom are easily configurable props for future view modes

---

## Chunk 8 — Frontend: Route rendering (shapes, dots, labels)

**Files:** `frontend/src/MapView.jsx`

**What to build:**
- When `route` prop changes, clear all existing route layers/sources and re-render:

**Walk legs:**
- Dashed gray polyline (`#888`, width 3, dasharray `[2, 2]`) from `leg.path` coordinates

**Transit legs:**
- Solid colored polyline from `leg.shape` coordinates, color from `LINE_COLORS` / `BUS_DIRECTION_COLORS`
- Line width: 5

**Markers:**
- Origin: blue dot (`#4a9eff`)
- Destination: dark dot (`#222`)
- Board stops: colored dot matching line color, labeled "Board [Line]"
- Exit stops: colored dot matching line color, labeled "Exit [Line]"

**Intermediate stops (from shape data):**
- Small circle markers (radius 4, white fill, colored border) at each intermediate stop coordinate
- Stop name label: visible only at zoom ≥ 15 (use MapLibre zoom-dependent layer visibility)

**Auto-fit:**
- After rendering, call `map.fitBounds(bounds, { padding: 60 })` where bounds = bounding box of all route coordinates
- `padding: 60` on all sides — adequate but not excessive

**Notes:**
- Use MapLibre `GeoJSON` sources + `line`/`circle`/`symbol` layers — not Leaflet-style imperative markers
- All sources/layers must be named with a consistent prefix (e.g. `route-`) so they can be reliably cleared on route change
- Intermediate stop coordinates come from the shape data — pick stops from the clipped shape at evenly spaced intervals, or thread the actual stop list through from the backend (simpler: thread the list)

---

## Chunk 9 — Frontend: Route card → map interaction

**Files:** `frontend/src/App.jsx`, `frontend/src/MapView.jsx`

**What to build:**
- Lift selected route index into `App` state (`selectedRouteIndex`, default `0`)
- Pass `routes[selectedRouteIndex]` to `<MapView>`
- Clicking a `<RouteCard>` sets `selectedRouteIndex` to that card's index
- Visual indicator on the selected card (e.g. highlighted border or checkmark)
- Map re-renders instantly when `route` prop changes (no animation — instant snap via `fitBounds` with `animate: false`)
- Photo → map transition triggers when first results arrive (Chunk 6 behavior), regardless of which card is selected

---

## Chunk 10 — Cleanup: Remove demo files

**Files:** repo root

**What to build:**
- Delete `demo-straight-lines.html`, `demo-gtfs-shapes.html`, `demo-carto-positron.html`, `demo-openfreemap-liberty.html`, `demo-openfreemap-positron.html`
- These were for design decision-making only and should not ship

---

## Implementation order summary

```
Chunk 1  → Pre-compute GTFS shapes (backend, startup)          ✅ done
Chunk 2  → Shape clipping per leg (backend, request-time)       ✅ done
Chunk 3  → OSMnx walk path geometry (backend)                   ✅ done
Chunk 4  → Thread geometry into API response (backend)          ✅ done
--- backend complete ---
Chunk 5  → Install MapLibre + layout restructure (frontend)     ✅ done
Chunk 6  → Transit photo loading state (frontend)               ✅ done
Chunk 7  → MapView component init (frontend)                    ✅ done
Chunk 8  → Route rendering: shapes, dots, labels (frontend)     ✅ done
Chunk 9  → Route card ↔ map interaction (frontend)              ✅ done
--- map feature complete ---
Chunk 10 → Delete demo files (cleanup)                          ✅ done
```
