# Feature Plans & Future Enhancements

Chunked plans for upcoming major features, followed by ideas deferred until post-launch. For chunked features, work through each chunk in order, one chunk per session or per commit. Do not start a chunk until all previous chunks are complete.

> **Process:** When a feature here is fully implemented, **delete its entry from this file** and add a corresponding entry to [`FEATURES_IMPLEMENTED_HISTORY.md`](FEATURES_IMPLEMENTED_HISTORY.md) summarizing what was built. This file should only ever contain features that have not yet been implemented.

---

## Feature Index

**Bolt-On** = self-contained, no dependencies on other planned features.
**Structural** = depends on one or more other features before it can be fully built or realized.

1. Feature J — Deprecate `find_bus_routes()` — **Bolt-On** (Dependency on Feature B, now complete)
2. Feature D — Live Arrivals at Transfer Stop — **Structural** (soft dependency on Feature C, now satisfied)
3. Multi-Leg Train Routing Gap 1 — Shared-Track Edge Deduplication — **Structural** (Dependency on Feature B, now complete)
4. Claude Haiku for Simple Queries — **Bolt-On**

---

# Chunked Implementation Plans

---

# Feature J — Deprecate `find_bus_routes()` in Favor of Unified Graph

> **Note:** Labeled Feature J to avoid collision with Feature H (Deduplicate Same-Line Station Candidates) in `Feature_Prioritization.md`.

## Overview

Feature B added bus stop nodes and bus transit edges to the NetworkX graph, so `find_routes()` now surfaces bus-only paths alongside intermodal ones. The standalone `find_bus_routes()` function — which pre-dates the unified graph — is now partially redundant. This feature removes it, restructures the bus routing block in `main.py` to call `find_bus_transfer_routes()` unconditionally, and cleans up all downstream references.

**Why it matters:** Two parallel codepaths that find bus routes (one via the unified graph, one via `find_bus_routes()`) must be kept in sync as the graph evolves. Removing `find_bus_routes()` eliminates ~200 lines of routing logic, one CTA Bus Tracker API call per request, and a deduplication step that exists only to reconcile the two codepaths.

**Type: Bolt-On** — self-contained cleanup to `transit_graph.py`, `main.py`, and `cta_client.py`. No dependency on any planned feature beyond Feature B (which is complete).

**Status: ⬜ Not started**

**Prerequisites:** Feature B must be complete and verified in production. Do not begin until unified-graph bus-only routes have been manually validated on real Chicago trips.

---

## Scoping decisions — resolved

1. **Keep `find_bus_transfer_routes()`.** It provides bus+bus transfer routes (bus A → walk → bus B) that the unified graph does not model — bus-to-bus walk transfers are not represented as graph edges. This function stays and becomes the sole bus-routing entry point in `main.py`.

2. **Call `find_bus_transfer_routes()` unconditionally.** Currently it is only called when `find_bus_routes()` returns empty or poor results. After this feature, it is called unconditionally whenever `transit_mode` is `"Bus"` or `"All"`, subject to the existing `bus_arrivals and origin_bus_stops` guard. Direct-bus results are already found by `find_routes()` on the unified graph; `find_bus_transfer_routes()` handles bus+bus transfer trips that the graph still cannot surface.

3. **Live arrival data is already covered.** `find_bus_routes()` queried `bus_arrivals` for real-time first-leg wait. `find_bus_transfer_routes()` returns the same `(total, wait_min, route)` tuple where `wait_min` is the live wait for bus A — so the live wait on the first boarding leg is preserved.

4. **Progressive exit-stop threshold is dropped.** `find_bus_routes()` applied a two-pass haversine filter to prune buses that don't make meaningful progress toward the destination. The unified graph relies on Dijkstra edge weights instead. Route quality must be validated during Chunk 1 verification before removing this filter. If the unified graph surfaces obviously poor bus-only paths, address the graph's edge weighting before proceeding to Chunk 2.

5. **`_rank_bus_routes()` is retained for `find_bus_transfer_routes()`.** It normalises wait semantics across bus results. Its docstring and comments referencing `find_bus_routes()` as a caller must be updated to reference `find_bus_transfer_routes()` only.

6. **Deduplication logic in `main.py` is removed.** The `_route_fingerprint()` deduplication added by Feature B exists solely to prevent unified-graph bus-only routes from duplicating `find_bus_routes()` results. Once `find_bus_routes()` is removed, that deduplication step can also be removed — the unified graph and `find_bus_transfer_routes()` produce non-overlapping route types by design (direct bus vs. bus+bus transfer).

---

## Chunk 1 — Verification: Confirm unified graph covers direct-bus route quality

**Files:** None (read-only verification)

**What to verify:**

Run the following test queries against the live app and inspect the returned routes. For each query, confirm that `find_routes()` via the unified graph returns at least one direct-bus result of comparable quality to what `find_bus_routes()` currently returns.

| Test query | What to check |
|---|---|
| Wicker Park → Logan Square (short direct bus) | Unified graph returns bus 56 or 72 as a direct option |
| Lincoln Square → Lakeview (crosstown bus) | Route card shows a direct bus, not just train options |
| Pilsen → Bridgeport (bus-only neighborhood pair) | At least one bus result with a reasonable total time |
| Trip where find_bus_routes() currently returns empty | `find_bus_transfer_routes()` still returns transfer options after the gate changes |

**Acceptance criteria for proceeding to Chunk 2:**
- Unified graph surfaces at least one direct-bus option for each test query above
- Total times are within 10% of what `find_bus_routes()` currently returns for the same query
- No obviously nonsensical bus paths (e.g. a bus route that travels away from the destination before turning around)

If the unified graph fails these checks, stop and file a scoped fix for the graph's bus edge weighting before continuing.

**Notes:**
- The `_route_fingerprint()` deduplication added by Feature B is still active during this verification — both codepaths are running in parallel, so there is no risk of regression
- Check Railway logs for any `find_bus_routes()` errors or empty-result cases that would indicate coverage gaps

---

## Chunk 2 — Restructure bus routing block in `main.py`

**Files:** `backend/main.py`

**What to build:**
- Remove the `find_bus_routes(...)` call from the bus routing block (~line 649). The entire `bus_routes = find_bus_routes(...)` call and its immediate result-handling are removed.
- Call `find_bus_transfer_routes()` unconditionally (not as a fallback) whenever `transit_mode` is `"Bus"` or `"All"`, subject to the existing `bus_arrivals and origin_bus_stops` guard:
  ```python
  if bus_arrivals and origin_bus_stops:
      transfer_routes = await loop.run_in_executor(
          executor,
          find_bus_transfer_routes,
          origin_lat, origin_lon, dest_lat, dest_lon,
          bus_arrivals, origin_bus_stops,
      )
  else:
      transfer_routes = []
  ```
- Remove the activation-gate logic that previously checked whether `find_bus_routes()` returned empty results before calling `find_bus_transfer_routes()`.
- Remove the `_route_fingerprint()` deduplication block — it is no longer needed once `find_bus_routes()` is gone (unified-graph results and `find_bus_transfer_routes()` results are non-overlapping by design).
- Remove the `find_bus_routes` import from the `from transit_graph import ...` line (~line 25).
- Update the docstring and inline comments in `_rank_bus_routes()` (~lines 337, 340, 348) to reference `find_bus_transfer_routes()` as its sole caller; remove any reference to `find_bus_routes()`.

**Notes:**
- The `bus_arrivals and origin_bus_stops` guard is unchanged — `find_bus_transfer_routes()` still requires live arrival data and a non-empty origin stop list.
- After this change, bus-only direct routes come exclusively from `find_routes()` (unified graph); bus+bus transfer routes come exclusively from `find_bus_transfer_routes()`. The merge-sort over `ranked_routes` already handles both lists.
- Run the same test queries from Chunk 1 after this change and confirm no regression.

---

## Chunk 3 — Remove `find_bus_routes()` definition and clean up all references

**Files:** `backend/transit_graph.py`, `backend/cta_client.py`

**What to build:**

In `transit_graph.py`:
- Remove the `find_bus_routes(...)` function definition (~line 1361, ~200 lines). The entire function body is deleted.
- Update the comment in `_build_shape_lookup()` (~line 627) that reads `"find_bus_routes() calls get_shape(route_short_name, direction_id)"`. If `find_bus_transfer_routes()` also calls `get_shape()`, update the comment to name it as the caller; otherwise remove the reference entirely.
- Update the docstring and inline comments inside `find_bus_transfer_routes()` (~lines 1584, 1600, 1610) that reference `find_bus_routes()` as the activation-gate caller. Update to reflect that `find_bus_transfer_routes()` is now called unconditionally from `main.py`.

In `cta_client.py`:
- Update the comment on the field at ~line 203: `"# GTFS stop ID — used by find_bus_routes()"`. If the field is still used by `find_bus_transfer_routes()` or another caller, update the comment to name the new caller. If it is not used by any remaining caller, remove the comment.

**Notes:**
- After deletion, run a repo-wide search for `find_bus_routes` to confirm no remaining references: `grep -r "find_bus_routes" backend/`
- Run the full Feature B verification checklist after the removal to confirm no routing regressions — intermodal, bus-only, and bus+bus transfer routes should all continue to work correctly.

---

# Feature D — Live Arrivals at Transfer Stop

## Overview

When a route requires a transfer — train-to-train (already supported via the NetworkX graph) or bus-to-bus (Feature C) — the app currently shows only scheduled times for the connecting service. The rider has no way to know whether the connecting train or bus is 1 minute away or 12 minutes away when they arrive at the transfer stop.

This feature fetches live arrival data for the connecting service at the transfer stop(s) in each ranked route, threads that data through the Claude prompt and the API response, and displays it inline on the route card.

**Why it matters:** A route requiring a 10-minute transfer wait is materially different from one where the connection is 2 minutes away. Without this data, Claude cannot give accurate time advice for transfer trips, and the rider cannot compare transfer options on real-time footing. Feature C explicitly deferred this as a known limitation ("7.5 min fixed estimate"); Feature D closes that gap.

**Type: Structural (soft dependency)** — the train-to-train half works independently today. The bus-transfer half depends on Feature C (Bus+Bus Transfers), which is now complete, so this dependency is satisfied.

**Status: ⬜ Not started**

**Prerequisites:** No hard prerequisites — train-to-train transfer routing already works. Feature D is most impactful after Feature C (bus+bus transfers) is built, but the train-transfer half is independently useful and can be implemented first.

---

## Scoping decisions — resolved

1. **Which legs get live arrivals?** Only the 2nd and subsequent `TransitLeg`s in a route (i.e., legs where the rider is waiting at a transfer stop, not the first boarding leg). The first leg's wait is already handled by `route.wait_minutes` via `_rank_routes()`.

2. **Transfer stop identification:** After `ranked_routes` is computed, scan each route's legs. A `TransitLeg` is a transfer boarding leg if any earlier leg in the same route is also a `TransitLeg`. Implemented as a helper `_extract_transfer_stops(ranked_routes)` that returns two deduped lists: train station dicts `[{mapid, name}]` and bus stop_id strings. Dedup by mapid/stop_id across all routes before calling the API — one call per unique stop, not per route.

3. **Train vs. bus leg identification:** A `TransitLeg` is a train leg if its `line_code` is in `LINE_NAMES` (the dict in `cta_client.py`: Red, Blue, Brn, G, Org, P, Pink, Y). A bus leg has a `line_code` that is a route number string (e.g. "36", "49"). Bus `from_mapid` values are in the 0–29999 range (GTFS stop IDs); train `from_mapid` values are in the 40000–49999 range. Either check works; prefer `line_code in LINE_NAMES`.

4. **Arrival direction filter at transfer stop:** Reuse `_build_arrival_lookup()` for train transfers — it already returns `{(line_code, station_mapid): {destNm: earliest_minutes}}` and the bearing-based direction filter in `_rank_routes()` handles multi-direction stations. For bus transfers: add a simple `_build_bus_transfer_lookup(arrivals) -> dict[tuple[str, str], int]` keyed by `(route, stop_id)` → earliest arrival minutes (bus arrivals at a specific stop_id are already direction-filtered by the API).

5. **When to fetch:** After `ranked_routes` is computed and before `build_prompt()` is called. Run `get_train_arrivals(transfer_train_stations, train_key)` and `get_bus_arrivals(transfer_bus_stop_ids, bus_key)` concurrently via `asyncio.gather`. Only call if the respective API key is set and the list is non-empty. Total added latency: one extra concurrent API round-trip (~300ms).

6. **`bus_fullness` filter:** Do NOT apply the origin-side `bus_fullness` filter to transfer bus arrivals. The rider has no choice of bus at a transfer stop — they board whatever arrives next.

7. **Serialization:** Add `"transfer_wait_minutes": int | null` to each `TransitLeg` dict in the `/recommend` response. This is `None` if no live data was returned. The existing `"wait_minutes"` on the route object (first-leg wait) is unchanged.

8. **Claude prompt:** Add a short "Live arrivals at transfer stop(s):" section to `build_prompt()` when transfer arrival data is present, formatted similarly to the existing origin arrivals section. This allows Claude to give accurate transfer-wait advice (e.g. "the Brown Line at Belmont is 4 min away when you'd arrive — good connection").

9. **Frontend:** Show `transfer_wait_minutes` inline on the transfer `TransitLeg` in `RouteLegs`. If the preceding leg in the list is a `WalkLeg` with `from === to` (same-station transfer) or is any non-first transit leg: render a small secondary line "~X min wait" (or "Due") immediately above the transit leg summary, styled as muted text — same visual weight as the route header's wait note but scoped to the individual leg.

---

## Chunk 1 — Backend: Extract transfer stops and fetch live arrivals

**Files:** `backend/main.py`

**What to build:**
- Add `_extract_transfer_stops(ranked_routes: list[tuple]) -> tuple[list[dict], list[str]]`:
  - Iterates each `(total, wait, route)` in `ranked_routes`
  - For each route, identifies `TransitLeg` objects where at least one earlier leg in `route.legs` is also a `TransitLeg`
  - Train legs (`leg.line_code in LINE_NAMES`): collect `{"mapid": leg.from_mapid, "name": leg.from_station}` — dedup by `mapid`
  - Bus legs: collect `leg.from_mapid` as a stop_id string — dedup
  - Returns `(train_transfer_stations, bus_transfer_stop_ids)`
- After `ranked_routes` is computed (after both train and bus routing blocks), call:
  ```python
  transfer_train_stations, transfer_bus_stop_ids = _extract_transfer_stops(ranked_routes)
  transfer_train_arrivals, transfer_bus_arrivals = await asyncio.gather(
      get_train_arrivals(transfer_train_stations, train_key) if transfer_train_stations and train_key else _empty(),
      get_bus_arrivals(transfer_bus_stop_ids, bus_key) if transfer_bus_stop_ids and bus_key else _empty(),
  )
  ```

**Notes:**
- If `ranked_routes` is empty, both return lists will be empty — no API calls made
- Define a small `async def _empty(): return []` helper and use it in place of real calls when the list is empty. Avoid `asyncio.coroutine` (deprecated).
- Import `LINE_NAMES` from `cta_client` (it's already a module-level dict there) — or duplicate the set of train line codes as a constant in `main.py`. Either is fine; importing is cleaner.

---

## Chunk 2 — Backend: Annotate transit legs and serialize transfer wait

**Files:** `backend/transit_graph.py`, `backend/main.py`

**What to build:**

In `transit_graph.py`:
- Add `transfer_wait_minutes: int | None = None` field to `TransitLeg` dataclass (after existing fields)

In `main.py`:
- Add `_build_bus_transfer_lookup(bus_arrivals: list[dict]) -> dict[tuple[str, str], int]`:
  - Returns `{(route, stop_id): earliest_minutes}` — one entry per `(route, stop_id)` pair, taking `min` across all matching arrivals
- After fetching transfer arrivals, build lookups:
  ```python
  train_xfer_lookup = _build_arrival_lookup(transfer_train_arrivals)
  bus_xfer_lookup   = _build_bus_transfer_lookup(transfer_bus_arrivals)
  ```
- Annotate transfer legs in-place. For each route in `ranked_routes`:
  ```python
  seen_transit = False
  for leg in route.legs:
      if isinstance(leg, TransitLeg):
          if seen_transit:
              if leg.line_code in LINE_NAMES:
                  dest_map = train_xfer_lookup.get((leg.line_code, leg.from_mapid), {})
                  leg.transfer_wait_minutes = _pick_wait(dest_map, leg.from_mapid, leg.to_mapid)
              else:
                  leg.transfer_wait_minutes = bus_xfer_lookup.get((leg.line_code, leg.from_mapid))
          seen_transit = True
  ```
  Extract the bearing filter into a shared helper `_pick_wait(dest_map, from_mapid, to_mapid) -> int | None` so it can be reused here and in `_rank_routes()`. This refactor removes the duplicate direction-selection logic.
- Add `"transfer_wait_minutes": leg.transfer_wait_minutes` to the `TransitLeg` dict in the `/recommend` response serialization

**Notes:**
- `_pick_wait` should accept an empty `dest_map` and return `None` (no live data) — same fallback as the existing `_rank_routes` wait-resolution logic
- The annotation modifies `Route.legs` in place after ranking — this is safe because the route objects are not reused after the response is built

---

## Chunk 3 — Backend: Include transfer arrivals in Claude prompt

**Files:** `backend/main.py`

**What to build:**
- Add `_format_transfer_arrivals(arrivals: list[dict]) -> str`:
  - Groups arrivals by `station` (train) or `stop_name` (bus)
  - For each stop, lists up to 3 next arrivals: `"  {line}/{route} → {destination}: {minutes} min"` (or "Due")
  - Returns a multi-line string, one stop per group header
- Extend `build_prompt()` signature: add `transfer_arrivals: list[dict] | None = None`
- In `build_prompt()`, if `transfer_arrivals` is non-empty, insert section after the origin arrivals blocks:
  ```
  Live arrivals at transfer stop(s):
  {_format_transfer_arrivals(transfer_arrivals)}
  ```
- In `main.py`, pass `transfer_arrivals = transfer_train_arrivals + transfer_bus_arrivals` to `build_prompt()`

**Notes:**
- Combined list is fine — `_format_transfer_arrivals` groups by stop name regardless of mode
- If `transfer_arrivals` is empty or `None`, the section is omitted entirely — no prompt change for non-transfer routes

---

## Chunk 4 — Frontend: Show transfer wait inline in route card

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`

**What to build:**
- In `RouteLegs`, before rendering a transit leg, check if it is a transfer boarding leg:
  ```js
  const isTransferLeg = legs.slice(0, i).some(l => l.type === 'transit');
  ```
- If `isTransferLeg && leg.transfer_wait_minutes !== undefined && leg.transfer_wait_minutes !== null`:
  - Render a small annotation immediately above the transit leg pill:
    ```
    ⏱ Due  /  ⏱ 4 min wait
    ```
  - Use a `<span className="transfer-wait-note">` element inserted just before the `<li>` for the transit leg, or as the first child inside it
- Style `.transfer-wait-note` in `App.css`: same muted color as secondary text elsewhere, `font-size: 0.75rem`, no extra margin (sits flush above the transit leg)
- If `transfer_wait_minutes === 0`: show "Due" (not "0 min wait")
- Do not change the route card header — `waitNote` continues to reflect only the first-leg wait

**Notes:**
- The existing `waitNote` in the route card header is for `route.wait_minutes` — leave it unchanged
- This feature only adds UI when `transfer_wait_minutes` is populated; non-transfer routes and routes with no live data are unaffected
- Manual test: find a real Chicago trip requiring a train-to-train transfer (e.g. Wicker Park → Evanston: Blue Line → Red Line at Clark/Lake) and verify the wait badge appears on the Red Line leg and updates with live data

---

# Future Enhancements

Post-launch ideas and improvements. These are not bugs — the app works correctly without them. Prioritize after Phase 6 deployment based on user feedback and real usage patterns.

---

## Multi-Leg Train Routing — Shared-Track Edge Deduplication (Route Label Accuracy)

**What happens:** For each `(from_station, to_station)` edge, `_build_graph()` keeps only the single fastest route_id. On segments where multiple CTA lines share the same track and stations (e.g. Red/Brown between Belmont and Fullerton, or Red/Purple between Howard and Belmont), the edge is labelled with whichever line was fastest in the representative GTFS trip. If a rider transfers to the other line at the shared-track start station, `_path_to_route()` sees no route_id change on the shared segment and cannot detect the correct line.

**Practical effect:** Route cards on shared-track trips may show the wrong line name for the shared segment (e.g. "Red Line" when the rider is on the "Brown Line" through the shared section). Timing is still correct — only the label can be wrong.

**Future fix:** Retain separate edges per route_id for shared-track pairs in `_build_graph()`, then handle deduplication during `_path_to_route()` using incoming line context.

> **Note:** The original approach of storing `all_routes` metadata on edges was removed in the 2026-04-15 audit (`G.add_edge(..., all_routes=candidates)` removed as dead code — the field was never read). Any implementation of this fix must use the alternative approach: store multiple edges per shared-track pair and select the correct one in `_path_to_route()` based on the incoming `TransitLeg`'s `line_code`.

**Type: Structural** — modifies `_path_to_route()`. Feature B is complete — any fix here must be written against the post-B version of `_path_to_route()` (which uses `_resolve_node()` for all node metadata). No additional dependency blockers remain.

**Status: ⬜ Not started**

---

### Verification — confirm the bug before implementing

Before any code changes, run these test queries and inspect leg labels in the JSON response:

| Trip | Shared segment to watch |
|---|---|
| Linden → Evanston/Davis (Purple Exp → Red) | Howard → Belmont: should say "Purple Line", not "Red Line" |
| O'Hare → Howard, then Howard → Belmont | If routed via Red, shared segment should say "Red Line" |
| Kimball → Merchandise Mart (Brown, all-elevated) | Belmont → Fullerton segment, if applicable |

Log the `line` field on each `TransitLeg` in the returned route. If mis-labelling is absent or rare, the fix may not be worth the complexity. If it fires consistently on the Purple/Red shared segment, proceed.

---

### Chunk 1 — Fix `_path_to_route()` to use incoming line context

**File:** `backend/transit_graph.py`

**What to change:**

The transit-leg grouping block always uses `edge.get("route_id")` and `edge.get("line")` as the canonical label for the leg. The fix: before committing to that label, check whether the incoming line (from the previous `TransitLeg`) is also a valid candidate for this edge, and prefer it if so.

```python
def _last_transit_leg(legs: list) -> TransitLeg | None:
    for leg in reversed(legs):
        if isinstance(leg, TransitLeg):
            return leg
    return None
```

In the transit-leg grouping block, after reading `group_route = edge.get("route_id", "")`:

> **Important:** `all_routes` is NOT available on edges — it was removed as dead code in the 2026-04-15 audit. The correct approach is to first update `_build_graph()` to store multiple edges per shared-track station pair (one per route_id), then use incoming line context in `_path_to_route()` to select the right one.

```python
incoming = _last_transit_leg(legs)
if incoming and incoming.line_code == edge.get("route_id"):
    pass  # already on the right edge — no override needed
elif incoming:
    # check if there is a parallel edge for the incoming line_code
    # (implementation depends on chosen graph storage approach)
    pass
```

The while-loop that merges consecutive edges uses `next_edge.get("route_id") != group_route` as the break condition — this is unchanged.

Shape lookup at the end of the block calls `get_shape(group_route, group_dir)`. After the override, `group_route` and `group_dir` should carry the correct incoming-line values.

**Edge cases:**
- First transit leg (no `incoming`): no override needed; stored label is used as-is.
- Same-station transfer WalkLeg between two transit legs: `_last_transit_leg` finds the previous `TransitLeg` correctly because it searches backward past walk legs.

**Test after:** Re-run the verification queries above. Purple Line through the Howard–Belmont segment should now label as "Purple Line".

---

## Claude Haiku for Simple Queries

**What:** Route queries with only one clear option (e.g. a single direct train, no transfers) don't need Sonnet-level reasoning. Haiku is ~65% cheaper and fast enough for straightforward recommendations.

**Benefit:** Meaningful cost reduction at scale with no user-facing quality loss on simple routes.

**Type: Bolt-On** — self-contained change to `main.py`. No dependencies on any other planned feature.

**Status: ⬜ Not started**

---

### Scoping

#### Definition of "simple"

A query is **simple** if both conditions hold after routing completes:

1. `ranked_routes` contains exactly **one** route.
2. That route contains exactly **one** `TransitLeg` (no transfer — a direct ride from origin to destination).

This is the most conservative definition: Claude's only job is to format the result and give a departure time. There is no comparison between options, no transfer tradeoff, no "ride A then B" complexity. Any query with multiple routes or a transfer leg uses Sonnet.

Intentionally **not** included in the simple definition:
- Two routes on the same line (e.g. two direct Red Line options) — still requires comparison reasoning.
- One route with multiple `TransitLeg`s but no walk between them — still a transfer, still Sonnet.
- Walk-only legs (`WalkLeg`) do not count against the TransitLeg limit; a route with one `WalkLeg` + one `TransitLeg` is still simple.

#### Classifier function

Add `_is_simple_query(ranked_routes: list[tuple]) -> bool` in `main.py`:

```python
def _is_simple_query(ranked_routes: list[tuple]) -> bool:
    if len(ranked_routes) != 1:
        return False
    _, _, route = ranked_routes[0]
    transit_legs = [leg for leg in route.legs if isinstance(leg, TransitLeg)]
    return len(transit_legs) == 1
```

Call it after `ranked_routes` is finalized and before `build_prompt()`.

#### Model selection

```python
model = (
    "claude-haiku-4-5-20251001"
    if _is_simple_query(ranked_routes)
    else "claude-sonnet-4-6"
)
message = await _claude_client.messages.create(
    model=model,
    max_tokens=300 if model.startswith("claude-haiku") else 400,
    messages=[{"role": "user", "content": prompt}],
)
```

`max_tokens=300` for Haiku: a single-route direct recommendation fits comfortably in 300 tokens. Sonnet keeps 400 for complex multi-route responses.

No changes to the prompt itself — the same `build_prompt()` output is sent to both models.

#### Logging

```python
print(f"[claude model={'haiku' if model.startswith('claude-haiku') else 'sonnet'} simple={_is_simple_query(ranked_routes)}]")
```

#### Response field

Add `"model_used": "haiku" | "sonnet"` to the `/recommend` response dict. The frontend ignores this field initially — it exists for log-based cost analysis and future observability.

#### BYOK interaction

BYOK keys work with all Claude models. Apply the same model-selection logic regardless of whether the request uses a BYOK key or the server key.

#### Cache interaction

The response cache stores the full response including `model_used`. On a cache hit, Claude is not called at all — model selection is irrelevant.

#### Files to change

- `backend/main.py` — add `_is_simple_query()` helper; add model selection and `max_tokens` branching before the `_claude_client.messages.create()` call; add `model_used` to the response dict; add the stdout log line.

#### Out of scope

- Prompt differences between Haiku and Sonnet (same prompt for both — diverging prompts adds maintenance cost with no clear benefit)
- Expanding the "simple" definition to cover two-route same-line queries (deferred; measure quality first)
- Per-model cost tracking in the response or UI
- Automatic fallback from Haiku to Sonnet on low-confidence responses (not needed; the classifier is conservative by design)
