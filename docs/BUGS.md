# Bugs To Be Fixed

Known issues catalogued for future fixing. Severity: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When a bug in this file is fixed, **delete its entry from this file** and add a corresponding entry to the **Bugs Fixed** section of [`docs/archive/RESOLVED_HISTORY.md`](archive/RESOLVED_HISTORY.md) documenting what was changed and how. This file should only ever contain bugs that have not yet been resolved.

---

## Routing Engine Review 2026-05-11 (6 bugs: 3 Medium, 3 Low)

Surfaced by a detailed audit of the intermodal routing engine against its stated goals. BUG-008 and BUG-009 from the same audit were fixed same-day; the items below remain.

---

# BUG-045 · 🟡 Medium — Precipitation/cold walk penalty not applied to transit-graph walk-edge weights

**Files:** `backend/main.py` (lines 798–799, `_run_routing`), `backend/transit_graph.py` (graph build — intermodal walk edges), `backend/walking.py` (street-graph walking)

## What is happening

`_precip_walk_factor()` in `main.py:798` correctly derates the user's effective walking speed in rain, snow, ice, extreme cold, or high gusts. But that derated speed is only consumed by `_scale_walk_legs()`, which multiplies the **already-selected** route's walk-leg minutes after `find_routes()` returns. The transit graph's walk-edge weights — both the intermodal train↔bus walk edges built at startup with baseline 3 mph (`config.TRANSFER_WALK_CAP_MIN`, `DETOUR_FACTOR`) and the virtual ORIGIN/DEST walk edges added per request — are never refreshed for weather.

**Effect:** In bad weather, Dijkstra still treats a 4-minute dry-weather walk as 4 minutes during selection, even though that walk now costs the rider 5–6 minutes. The engine can pick a route with a long walk to a faster bus over a shorter walk to a slightly slower train, simply because it underestimates the walk cost during selection. The displayed totals are correct (post-scaling), but the *route choice* is biased toward walk-heavy itineraries in adverse weather.

**Reproduction:** Submit `/recommend` requests for the same O/D pair under simulated dry vs. heavy-rain weather contexts. Compare the chosen primary route. If the route with the shorter walk leg ever loses to a route with a longer walk leg purely because the longer-walk route has a faster transit segment, the bug is observable.

**Why it slipped:** The precipitation factor was bolted on top of the existing walk-speed scaling, which itself was always applied post-routing. The architectural assumption — that walk costs are uniform during selection and only personalized at display time — held when the only personalization was a user preference. Weather makes that assumption wrong, because the user's *actual* trip time differs from the graph-edge cost.

## Fix approach (split into 3 chunks)

This is a non-trivial fix because the graph is built once at startup and shared across requests under a lock. Three sequential chunks are recommended:

**Chunk 1 — Pass weather factor into routing.**
Plumb `effective_speed` (or `precip_factor` separately from user `walk_speed`) into `find_routes()` and `find_bus_transfer_routes()`. Inside those functions, scale the **virtual ORIGIN/DEST walk edges** (added per call) by `1 / effective_speed` before running Dijkstra. The shared intermodal walk edges in the cached graph remain untouched.

Acceptance: virtual-edge weights reflect weather; route selection at the origin/destination boundary changes when weather degrades.

**Chunk 2 — Scale intermodal walk edges per request.**
The walk edges between train stations and bus stops live inside the cached graph and currently can't be reweighted without rebuilding. Two options — pick one in implementation:

- (a) **Per-request edge-weight override**: pass a `weight_multiplier` dict into Dijkstra (NetworkX supports a weight-function callback) that multiplies any `edge_type == "walk"` edge by `1 / effective_speed`. No graph mutation; safest under the existing routing lock.
- (b) **Tiered walk-edge cache**: maintain a small set of pre-built graph variants keyed by rounded precip factor (e.g. 1.0, 1.1, 1.2, 1.4). Adds memory, avoids per-request callback overhead.

Recommend (a) — single graph, no extra memory on Railway free tier.

Acceptance: under heavy-rain weather, a Red Line → Bus 36 intermodal route is correctly down-ranked vs. a Red Line single-leg route if the intermodal transfer walk now exceeds the differential transit time.

**Chunk 3 — Walking-graph street-walk minutes already correct (verify).**
`walking.py:walk_minutes()` returns minutes at baseline `WALKING_SPEED_MPS`. The post-routing `_scale_walk_legs()` rescales these for display. Confirm that nothing in chunks 1–2 double-counts the precip factor on walk legs that are *already* scaled at the main.py layer. Add an integration test: a single walk-only route in heavy rain should have its display minutes equal `baseline_minutes / (walk_speed × precip_factor)` exactly once.

---

# BUG-046 · 🟡 Medium — Live-wait direction selection fragile at near-orthogonal terminal vectors

**File:** `backend/main.py` (lines 392–412, `_pick_wait`)

## What is happening

When a boarding station serves multiple terminals (e.g., Red Line Howard vs. 95th/Dan Ryan at Belmont), `_pick_wait()` picks the correct directional arrival by computing the dot product between two 2D bearing vectors:

- `(dlat, dlon)`: boarding station → exit station (the rider's intended direction)
- `(tlat, tlon)`: boarding station → terminal of each arrival group

The arrival group with the largest positive dot product wins. This works cleanly when the rider's intended direction is strongly aligned with one terminal. It breaks down in two cases:

1. **Near-orthogonal vectors:** When the exit station is roughly perpendicular to both terminals (e.g., a Loop transfer where you're getting off after one stop), both dot products can be small and close in magnitude. The "winner" is then determined by floating-point noise.

2. **Very short boarding→exit vectors:** When the rider is making a one- or two-stop hop, `(dlat, dlon)` is small and the dot product collapses toward zero, again making the comparison noise-sensitive.

**Effect:** The route's displayed first-leg wait can be drawn from the wrong direction's arrival board. The route itself is still chosen correctly (selection doesn't depend on `_pick_wait`), but the rider sees a misleading "next train in N minutes" — they walk to the platform expecting one train and the other one shows up.

**Reproduction:** Trace a route with first transit leg State/Lake → Clark/Lake (one stop on Red Line). Compare `_pick_wait`'s choice against the actual northbound vs. southbound arrival boards. With realistic GTFS coords the dot-product margin is often <0.0001.

## Fix approach (single chunk)

Replace the raw dot product with a **normalized cosine similarity plus a minimum-margin guard**:

1. Normalize both vectors to unit length before the dot product (range −1…+1).
2. If the difference between the top two normalized scores is below a threshold (e.g., 0.15), fall back to the earliest arrival across both directions — that's the safer default and matches user expectations ("show me whichever train is coming sooner when the direction is genuinely ambiguous").
3. If the boarding→exit vector has magnitude below a threshold (e.g., one-stop hop), use the **next downstream station's** coordinates instead of the exit's, to get a longer baseline vector.

Step 3 needs the route's transit-leg stop sequence, which is already available in the `Route` object — pass the second stop's mapid into `_pick_wait` when the leg has more than one stop.

Acceptance: a unit test on Belmont → Fullerton (Red Line, one stop south) correctly picks the 95th-direction arrival; a unit test on Clark/Lake → State/Lake (Loop, near-orthogonal) falls back to earliest arrival.

---

# BUG-047 · 🟡 Medium — `find_routes()` returns empty list silently when origin/destination is >2 mi from transit

**File:** `backend/transit_graph.py` (lines 1495–1508, progressive radius expansion in `find_routes`)

## What is happening

When the caller doesn't pre-resolve origin/destination stations, `find_routes()` expands its search radius in 0.25-mile increments up to 2.0 miles (`for _r in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0):`). If no train station is within 2.0 miles, the loop exits and the function returns `[]`. The same applies to the destination side.

The caller in `main.py:_run_routing` catches no exception (none is raised), sees an empty `raw_routes`, and proceeds. Downstream, the ranked-routes list stays empty, Claude gets an empty list, and the user sees either "no routes found" or — depending on the frontend — a blank state with no explanation.

**Effect:** A user in Oak Park, far-south Beverly, or any out-of-coverage area gets the same UX as a transient backend error. They have no way to know whether the engine failed, the location was misgeocoded, or they're genuinely out of coverage.

**Reproduction:** Submit `/recommend` with an origin in Oak Park (well outside the STREET_GRAPH bbox) and a destination downtown. The response will list no routes with no error message.

## Fix approach (split into 2 chunks)

**Chunk 1 — Raise a typed signal from `find_routes()`.**
Define a small result object (or a sentinel) that distinguishes:
- `OutOfCoverage(side="origin" | "destination" | "both", max_radius_searched=2.0)`
- `NoRoutesFound()` (origin and destination both reachable but no path)
- Normal list of routes

`find_routes()` returns this; `_run_routing` inspects it. Keep the existing `list[Route]` for the success case (don't break callers that already work) by adding a parallel method or a richer return.

Acceptance: unit tests verify each of the three outcomes for crafted inputs.

**Chunk 2 — Surface the signal through the API and UI.**
- `main.py` should populate a structured field on the `/recommend` response (`status: "out_of_coverage"` with details).
- Claude's prompt should receive the same signal so it can write a helpful explanation ("You're outside our Chicago coverage area — try a CTA station nearby.").
- Frontend should render a clear empty state when `status != "ok"`.

Acceptance: an Oak Park origin gets a user-facing message explaining the coverage limit, not a blank result.

---

# BUG-048 · 🟢 Low — Walking-graph fallback to Haversine swallows all exceptions silently

**File:** `backend/walking.py` (line 454, `walk_minutes`; lines 466–468, `_walk_directions_impl`; analogous fallback in `_walk_path_impl`)

## What is happening

```python
try:
    path = _get_shortest_path(origin_lat, origin_lon, dest_lat, dest_lon)
    if path is None:
        raise RuntimeError("path unavailable")
    ...
except Exception:
    return _haversine_walk_minutes(...)
```

The bare `except Exception:` triggers for any failure — point outside graph bbox (legitimate), graph not loaded yet (race during eviction/reload — legitimate), graph corruption (a real bug we'd want to know about), or an unexpected igraph error (real bug). All cases return a Haversine straight-line estimate, with no log line.

**Effect:** If the pickled graph artifact gets corrupted in a deploy, every routing request silently degrades to straight-line walks. Display minutes will be roughly 25% off (no detour factor), turn-by-turn directions will be empty, and there's no telemetry signal. We'd discover the failure from a user complaint, not from logs.

**Reproduction:** Rename `street_graph_igraph.pkl` to a corrupted file and `street_graph.graphml` likewise; restart backend. All walking calls return Haversine with no log indication.

## Fix approach (single chunk)

Distinguish the legitimate "path unavailable" sentinel from real exceptions:

1. Treat `RuntimeError("path unavailable")` (the explicit raise for `path is None`) as expected and silent — this is the legitimate out-of-bbox case.
2. For any other exception type, log a single warning line including the exception class and message **before** falling back. Throttle to once per minute per (origin_cell, exception_class) so a corrupted graph doesn't flood logs.
3. Add a module-level counter `_haversine_fallback_due_to_error` that increments on the non-sentinel path; expose it via the existing `/health` or `/metrics` endpoint if one exists.

Acceptance: an injected exception during testing produces exactly one log line per cooldown window and increments the counter; legitimate out-of-bbox calls remain silent.

---

# BUG-049 · 🟢 Low — No timeout on Dijkstra calls in routing or walking layers

**Files:** `backend/walking.py` (line 412, `G.get_shortest_paths`), `backend/transit_graph.py` (Yen's `nx.shortest_simple_paths` call inside `find_routes`)

## What is happening

Both shortest-path calls run to completion with no time budget:

- `walking.py:412` — `igraph.Graph.get_shortest_paths()` against a graph of ~150k vertices.
- `transit_graph.py` — `nx.shortest_simple_paths()` is a generator implementing Yen's k-shortest algorithm; it can iterate many candidate paths before yielding the first one if the graph is densely connected.

In normal operation both complete in well under a second. The risk is in degenerate cases: a malformed graph after a future schema change, an unusually dense origin/destination neighborhood, or a request that hits an as-yet-unseen pathological topology. Without a timeout, a single hung request can hold the routing lock (`transit_graph.py:_routing_lock` serializes concurrent calls) and stall the entire backend.

**Effect:** Low probability today, but the failure mode is severe — one stuck request blocks all subsequent routing.

## Fix approach (split into 2 chunks)

**Chunk 1 — Wrap NetworkX Yen's with a deadline.**
`nx.shortest_simple_paths` is a generator. Wrap consumption in a `time.monotonic()` deadline check inside the path-acceptance loop in `find_routes()`. If the deadline passes mid-iteration, return whatever routes have been accepted so far (could be zero). Pick a deadline ~3× the observed p99 latency (probably 2–3 seconds is safe).

Acceptance: a test injecting a slow custom-weight callback verifies the deadline triggers and the function returns partial results without hanging.

**Chunk 2 — Bound the igraph walking call.**
igraph's `get_shortest_paths` has no native timeout. Options:

- (a) Run it in a thread with a `concurrent.futures` deadline; on timeout, the thread continues to completion but the caller returns the Haversine fallback. (Wasted CPU on the orphaned thread but caller is unblocked.)
- (b) Pre-flight check: if origin and destination are >X miles apart (Haversine), skip the graph entirely. This addresses the practical risk (degenerate cross-city queries) without needing real cancellation.

Recommend (b) for simplicity — most legitimate walks are <2 miles; pathological cases are large distances. Hard-cap at 5 miles; beyond that, Haversine + detour factor is fine for an upper bound, and we should be routing transit anyway.

Acceptance: a synthetic 50-mile walk-only request completes in <100 ms via Haversine; normal walks (<5 mi) unaffected.

---

# BUG-050 · 🟢 Low — Bus-transfer scoring logic fragmented across `transit_graph.py` and `main.py`

**Files:** `backend/transit_graph.py` (`find_bus_transfer_routes` — `_LEG2_WAIT_ESTIMATE`, sort key), `backend/main.py` (`_run_routing` rebuild step at lines 855–864, `_apply_transfer_wait_estimates` at lines 458–490)

## What is happening

The total-time computation for bus+bus transfer routes is spread across three independent code locations:

1. `find_bus_transfer_routes()` computes a sort key including `_LEG2_WAIT_ESTIMATE` (= `TRANSFER_PENALTY_MINUTES`).
2. `_run_routing()` rebuilds the total after walk-speed scaling, adding the per-transfer penalty back in (this is the BUG-008 fix).
3. `_apply_transfer_wait_estimates()` subtracts the penalty and re-adds the live wait (or the same penalty as fallback).

All three must use the same constant and the same arithmetic convention to stay consistent. BUG-008 was a direct consequence of one of these three locations being out of sync — when the rebuild step was first written, it omitted the penalty term, breaking the invariant that `_apply_transfer_wait_estimates` relies on.

**Effect:** No active bug today (BUG-008 is fixed), but the next change in this area — a different leg-2 estimate, a per-route headway-aware penalty, or any refactor of the wait-application order — risks re-introducing the same class of bug. The fix is well-commented now, but commented coupling is the weakest form of invariant.

## Fix approach (refactor — split into 3 chunks)

**Chunk 1 — Encapsulate the total-minutes formula in one function.**
Add `transit_graph.compute_route_total(route, first_leg_wait, transfer_waits, walk_speed_factor) -> float`. This becomes the single arithmetic authority. All three sites call it; none of them does arithmetic on `total_minutes_no_wait` directly.

Acceptance: greppin the codebase for `total_minutes_no_wait +` returns zero hits outside the new function.

**Chunk 2 — Make `_LEG2_WAIT_ESTIMATE` a named function default and remove duplication.**
Either:
- Inline `_LEG2_WAIT_ESTIMATE` as a default parameter to `compute_route_total`, removing the module-level constant.
- Or move it to `config.py` alongside `TRANSFER_PENALTY_MINUTES` with a docstring explaining when each is used.

Acceptance: there is exactly one definition of the leg-2 estimate in the codebase.

**Chunk 3 — Add a property-based invariant test.**
Write a test that constructs synthetic bus+bus routes with random walk-leg minutes and random live transfer waits, then asserts: `displayed_total == sum(walk_minutes) + sum(transit_minutes) + first_leg_wait + sum(transfer_waits)`. This holds regardless of the internal estimate-handling order, so it would have caught BUG-008 directly.

Acceptance: invariant test passes; deliberately introducing a 3-min asymmetry (the original BUG-008) makes it fail.

---
