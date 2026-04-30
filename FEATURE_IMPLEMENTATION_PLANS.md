# Feature Plans

Chunked plans for upcoming major features, followed by ideas deferred until post-launch. For chunked features, work through each chunk in order, one chunk per session or per commit. Do not start a chunk until all previous chunks are complete.

> **Process:** When a feature here is fully implemented, **delete its entry from this file** and add a corresponding entry to [`FEATURES_IMPLEMENTED_HISTORY.md`](FEATURES_IMPLEMENTED_HISTORY.md) summarizing what was built. This file should only ever contain features that have not yet been implemented.

---

## Feature Index

**Bolt-On** = self-contained, no dependencies on other planned features.
**Structural** = depends on one or more other features before it can be fully built or realized.

**Chunked Implementation Plans** (in document order):
1. Feature NorthExpansion — North Side 0.25-Mile Walking Radius Expansion — **Structural** (depends on Feature K ✅)
2. Feature SouthExpansion — South Side 0.25-Mile Walking Radius Expansion — **Structural** (depends on Feature K ✅)
3. Feature Monetization — House Ads (Phase 1; third-party networks deferred) — **Bolt-On**
4. Feature TabTransition — Tab-change page transition animation — **Bolt-On**
5. Feature ReLock — Re-lock / "Follow Me" Map Button — **Bolt-On**
6. Feature ArrivedToast — Arrived Notification Toast — **Bolt-On** (pairs naturally with Feature ReLock)
7. Feature TapRecentre — Tap Live Position Marker to Re-lock — **Bolt-On** (depends on Feature ReLock)
8. Feature RouteProgress — Grey Out Completed Route Legs — **Bolt-On**
9. Feature HeadingUp — Heading-Up Map Orientation — **Bolt-On**

---

# Chunked Implementation Plans

---

# Feature NorthExpansion — North Side 0.25-Mile Walking Radius Expansion

## Overview

The street walking graph currently covers Howard St (42.019) as its northern boundary, which means Yellow Line stations in Skokie and all Purple Line stations north of Howard (in Evanston) fall outside the OSM pedestrian network. Routing to/from those stations still works — they are already nodes in the transit graph loaded from GTFS — but walking times at those stations use Haversine straight-line estimates rather than street-routed values, and walk directions collapse to a single generic step.

This feature expands the street graph bounding box northward to cover a 0.25-mile pedestrian radius around every station on the Yellow Line (Howard → Dempster-Skokie) and Purple Line north of Howard (South Blvd → Linden).

**Stations newly covered by accurate walk routing:**

| Line | Stations | Northernmost coord |
|---|---|---|
| Yellow | Howard, Oakton-Skokie, Dempster-Skokie | 42.038, -87.751 |
| Purple (north of Howard) | South Blvd, Main, Dempster, Davis, Foster, Noyes, Central, Linden | 42.078, -87.690 |

**New bounding box (north and west edges only):**

| Constant | Current | New |
|---|---|---|
| `STREET_GRAPH_NORTH` | `42.0190` | `42.0830` |
| `STREET_GRAPH_WEST` | `-87.7260` | `-87.7570` |

South and east edges unchanged.

**Estimated storage impact** (density-adjusted for Evanston/Skokie suburban street density ~65% of Chicago):

| File | Current | Estimated new | Increase |
|---|---|---|---|
| `street_graph.graphml` | 79 MB | ~101 MB | +22 MB |
| `street_graph_igraph.pkl` | 16 MB | ~21 MB | +5 MB |

**Runtime RAM:** igraph expands to roughly 3-4x its file size in memory; expect ~+15-20 MB resident.

**Type: Structural** — the street graph file must be re-hosted after regeneration. Depends on Feature K (street graph restoration in production) so the expanded file can actually be deployed.

**Status: Not started**

**Prerequisites:**
- Feature K complete (expanded graphml must be uploadable to the chosen host and reachable from the Railway Dockerfile).

---

## Scoping decisions

1. **Bbox values.** Values above are derived from station coordinates + 0.25-mile buffer. Accept as specified or adjust if Railway memory budget tightens.

2. **Combined vs. separate regeneration.** If Feature SouthExpansion is implemented in the same session, regenerate the graph once with both north and south boundaries updated rather than regenerating twice.

---

## Chunk 1 — Update bbox constants

**Files:** `backend/utils.py`

Update `STREET_GRAPH_NORTH` to `42.0830` and `STREET_GRAPH_WEST` to `-87.7570`. Update the comment block above the constants to reflect the new coverage: "Howard St → Linden/Dempster-Skokie (north), Lakefront (east), Dempster-Skokie (west)".

No other code changes are needed — `fetch_street_graph.py` already reads `STREET_GRAPH_BBOX_OSMNX` from `utils.py`.

---

## Chunk 2 — Regenerate street graph locally

**Files:** `backend/street_graph.graphml`, `backend/street_graph_igraph.pkl`

Run `python fetch_street_graph.py --force` from the `backend/` directory. This downloads the expanded OSM pedestrian network (~3-10 min depending on connection), consolidates intersections, saves `street_graph.graphml`, and builds `street_graph_igraph.pkl`.

Verify after completion:
- `street_graph.graphml` is ~95-110 MB (not an LFS pointer).
- `street_graph_igraph.pkl` is ~19-23 MB.
- Log output confirms node/edge counts increased vs. the previous graph.

If running Feature SouthExpansion in the same session, do Chunk 1 of both features before running this step.

---

## Chunk 3 — Re-upload and verify in production

**Files:** Feature K host (GitHub Release or equivalent), `backend/Dockerfile` (if pinned tag changes)

Upload the new `street_graph.graphml` to the same host used by Feature K. If Feature K pins to a specific release tag, create a new tag (e.g. `street-graph-v2`) and update the `STREET_GRAPH_URL` ARG in the Dockerfile.

Trigger a Railway redeploy. Confirm in build logs that the graph downloads at the expected size. Confirm in runtime startup logs that the graph loads successfully. Spot-check a trip to/from Linden or Dempster-Skokie: walk directions should use named streets rather than a single generic step.

---

# Feature SouthExpansion — South Side 0.25-Mile Walking Radius Expansion

## Overview

The street walking graph currently stops at ~41.856 (approximately 18th–20th St), which is just north of the Red Line's Cermak-Chinatown station and well above the Green, Orange, and Red line southern terminals. All south-side stations below that boundary have Haversine-only walk accuracy.

This feature expands the street graph bounding box southward (and slightly westward for the Orange Line's Midway corridor) to cover a 0.25-mile pedestrian radius around every CTA train station south of the current boundary.

**Stations newly covered by accurate walk routing (partial list):**

| Line | Stations south of boundary |
|---|---|
| Red | Cermak-Chinatown, Sox-35th, 47th, Garfield, 63rd, 69th, 79th, 87th, 95th/Dan Ryan |
| Green | 43rd, Indiana, 47th, King Drive, Cottage Grove, Oakwood/63rd, Garfield, 51st |
| Orange | Halsted, Ashland, 35th/Archer, Western, Kedzie, Pulaski, Midway |

**New bounding box (south and west edges only):**

| Constant | Current | New |
|---|---|---|
| `STREET_GRAPH_SOUTH` | `41.8560` | `41.7180` |
| `STREET_GRAPH_WEST` | `-87.7260` | `-87.7450` |

North and east edges unchanged. The western boundary nudges slightly to cover the Orange Line's Midway terminal (~-87.737) with a 0.25-mile buffer.

**Estimated storage impact** (density-adjusted for South Side urban density ~75% of North Side/Loop):

| File | Current | Estimated new | Increase |
|---|---|---|---|
| `street_graph.graphml` | 79 MB | ~129 MB | +50 MB |
| `street_graph_igraph.pkl` | 16 MB | ~26 MB | +10 MB |

**Runtime RAM:** igraph expands to roughly 3-4x its file size in memory; expect ~+30-40 MB resident. Verify Railway memory headroom before deploying — this is the larger of the two expansions.

**Type: Structural** — the street graph file must be re-hosted after regeneration. Depends on Feature K (street graph restoration in production).

**Status: Not started**

**Prerequisites:**
- Feature K complete.
- Railway memory headroom confirmed (current igraph ~50-65 MB resident; expanded ~80-105 MB resident; ensure total process stays under Railway plan limit).

---

## Scoping decisions

1. **Bbox values.** Values above derived from station coordinates + 0.25-mile buffer. If Railway memory is tight, consider a more conservative south boundary (e.g. `41.770`, covering through 79th St Red Line) and expand in a second pass once memory budget is confirmed.

2. **Combined vs. separate regeneration.** If Feature NorthExpansion is implemented in the same session, regenerate the graph once with both boundaries updated.

3. **Memory validation.** Before uploading to production, load the new `street_graph_igraph.pkl` locally and check resident memory with `tracemalloc` or `psutil`. Abort if the graph would push the Railway process over its memory limit.

---

## Chunk 1 — Update bbox constants

**Files:** `backend/utils.py`

Update `STREET_GRAPH_SOUTH` to `41.7180` and `STREET_GRAPH_WEST` to `-87.7450`. Update the comment block above the constants to reflect the new coverage: "Linden/Dempster-Skokie (north, if NorthExpansion done) or Howard St (north) → 95th/Dan Ryan (south), Lakefront (east), Midway corridor (west)".

No other code changes needed.

---

## Chunk 2 — Regenerate street graph locally

**Files:** `backend/street_graph.graphml`, `backend/street_graph_igraph.pkl`

Run `python fetch_street_graph.py --force` from the `backend/` directory.

Verify after completion:
- `street_graph.graphml` is ~120-140 MB (not an LFS pointer stub).
- `street_graph_igraph.pkl` is ~24-28 MB.
- Log output confirms node/edge counts increased.

Optionally validate memory before proceeding to Chunk 3:
```python
import pickle, tracemalloc
tracemalloc.start()
with open("street_graph_igraph.pkl", "rb") as f:
    data = pickle.load(f)
current, peak = tracemalloc.get_traced_memory()
print(f"Peak: {peak / 1024 / 1024:.1f} MB")
```
If peak exceeds ~350 MB, revisit the south boundary per scoping decision 1.

---

## Chunk 3 — Re-upload and verify in production

**Files:** Feature K host (GitHub Release or equivalent), `backend/Dockerfile` (if pinned tag changes)

Upload the new `street_graph.graphml` to the Feature K host. Create a new release tag if pinned (e.g. `street-graph-v2`, or `street-graph-v3` if NorthExpansion was already deployed as v2). Update `STREET_GRAPH_URL` in the Dockerfile if the tag changed.

Trigger a Railway redeploy. Watch build logs for expected file size. Watch runtime startup logs for successful graph load. Spot-check a trip to/from 95th/Dan Ryan and a trip to/from Midway: walk directions should name actual streets rather than a single generic step.

---

# Feature Monetization --- House Ads (Phase 1)

## Overview

Adds a house ad component to partially offset Railway hosting costs without compromising the Heritage Organic UI. The approach is deliberately conservative: house ads only in Phase 1 — no external ad scripts, no third-party cookies, no layout disruption. Third-party networks (EthicalAds, Carbon Ads) are deferred until the user base is meaningful. Google AdSense is explicitly avoided for now — auto-placed display ads carry a high risk of clashing with the cream/charcoal design and hurting retention.

**Target:** ~200 DAU × 2 searches/day = ~12k monthly impressions. Affiliate click-through revenue at modest conversion rates can partially offset hosting; the primary value in Phase 1 is building the slot and proving it doesn't hurt UX.

**Why it matters:** The app has real operational costs. The house ad is the minimal intervention that keeps the interface intact while creating a revenue path.

**Type: Bolt-On** --- frontend-only addition; no backend changes.

**Status: Not started**

**Prerequisites:**
- Railway + Vercel deployment live and stable (Phase 6 complete).

---

## Scoping decisions

1. **Ad provider — phased approach.**
   - **Phase 1 (now):** House ads only. A static `<a>` tag — no external scripts, no third-party cookies, fully styled to the Heritage Organic system. Affiliate URL and copy controlled via Vercel env vars so they can be swapped without a redeploy.
   - **Phase 2 (after meaningful user base):** Evaluate EthicalAds or Carbon Ads. Both serve text-only, developer-targeted units with clean aesthetics that are far less intrusive than display ads. Apply only after confirming traffic warrants it and that units can blend with the cream/charcoal system.
   - **Google AdSense:** Deliberately deferred. Auto-placed display ads are very likely to break the Heritage Organic visual language and erode user trust. Revisit only if revenue is critically needed and aesthetic/layout controls are guaranteed.

2. **Placement.** Single slot at the bottom of the results panel (below the last route card), so it appears naturally as users scroll through recommendations. Not in the header, not blocking the route search form. Do not render on the empty/loading state — showing an ad when the page has no content creates a poor first impression.

3. **Loading order.** House ad is a static `<a>` tag — no async loading concern. If a third-party network is added in Phase 2, load its script after the main transit data fetch completes and results are rendered.

4. **Analytics.** No heavy analytics. A simple click-through counter can be added later as a lightweight Railway route (POST /house-ad-click) — defer until traffic warrants it.

5. **Privacy.** House ads have no cookie/fingerprinting concerns. If a third-party network is adopted in Phase 2, add a brief footer disclosure ("This app uses [network] to display ads") for US-only audiences; add a full consent banner only if EU traffic becomes significant.

6. **Ad dimensions.** House ad is a flex-row banner that fills the panel width naturally. No hardcoded IAB sizes.

---

## Chunk 1 --- House ad component

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`

**What to build:**

- Add an `AdSlot` inline component (no separate file needed --- small enough to inline in App.jsx) that renders a static house ad `<a>` tag.
- Mount `AdSlot` at the bottom of the results list, inside the left panel, below the last RouteCard. Render only when results exist (`routes.length > 0`).
- Style per Heritage Organic: cream background, `--color-border` top-divider line, charcoal text. No heavy border or shadow. The slot must be indistinguishable in feel from the rest of the UI — it should look like a contextual tip, not a foreign element.
- `VITE_HOUSE_AD_URL` and `VITE_HOUSE_AD_TEXT` are configurable via Vercel env vars so the house ad can be updated without a redeploy.
- `VITE_HOUSE_AD_ENABLED` defaults to `false` in `.env` (off in local dev) and is set to `true` in Vercel after confirming the slot looks correct in production.

---

## Affiliate Products Reference (House Ad Candidates)

Content strategy: contextual, local, and utility-focused affiliate items matching Chicago commuter needs — battery, weather, noise, and safety. Use these for the `VITE_HOUSE_AD_URL` / `VITE_HOUSE_AD_TEXT` env vars.

**Product categories & examples**
- **Safety & Tech:** Anker 313 Power Bank (PowerCore 10K); Skullcandy Fat Stash 2; Shokz OpenDots ONE; Apple AirTag / Tile Mate.
- **Weather-proofing:** Repel Windproof Travel Umbrella; Sorel Emelie III; Hunter Commando Boots; North Face Etip Gloves.
- **Commuter kit:** Nordace Siena; Travelon Anti-Theft Heritage; Zojirushi Stainless Steel Mug; CTA-themed gear (CTAGifts.com).

**Top 2026 commuter tech comparison**

| Item | Top Pick | Key Benefit |
| :--- | :--- | :--- |
| **Noise Canceling** | Sony WH-1000XM6 | Best-in-class for blocking "L" screeching. |
| **Safety Audio** | Shokz OpenDots ONE | Hear "Doors Closing" announcements clearly. |
| **Power** | Nestout 15000mAh | Rugged and drop-proof for city sidewalks. |
| **Reading** | Kindle Paperwhite | Waterproof (great for rainy platforms). |

**Copy tips:** mention how items solve specific Chicago pain points (e.g., surviving transfers at Clark/Lake, windy Blue Line platforms).

---

# Feature TabTransition — Tab-change page transition animation

## Overview

The editorial design system specifies a page transition when the user switches tabs: `translateX(8px)` + `opacity` fade, 220ms, `ease-out`. This is the only motion in the design system that is triggered by navigation rather than data state. It has not been implemented because the current tab-switching mechanism (toggling `display: none` / `display: flex` via `[data-active-tab]` CSS selectors) is **incompatible with CSS transitions** — you cannot transition from or to `display: none`.

**Type: Bolt-On** — CSS/JSX only; no backend changes, no hook changes.

**Status: Not started**

**Prerequisites:**
- The desktop SideRail and mobile tab bar are both implemented and stable (done as of the `claude/align-frontend-design-system-EQdPg` branch, commit `4964172`).

---

## The core constraint — why this is non-trivial

`display: none` causes an element to be removed from the layout and compositing entirely. CSS transitions ignore the `display` property; they cannot interpolate between `none` and `block`/`flex`. The moment `display: none` is applied, the element disappears instantly — no fade, no slide.

The current visibility mechanism in `App.css` is:

```css
[data-active-tab="map"] .panel-cards { display: none; }
[data-active-tab="home"] .panel-map,
[data-active-tab="alerts"] .panel-map,
[data-active-tab="saved"] .panel-map { display: none; }
```

These rules are also responsible for collapsing the desktop grid from 3 columns to 2 when `panel-map` is hidden:

```css
[data-active-tab="map"] .layout--split,
[data-active-tab="alerts"] .layout--split,
[data-active-tab="saved"] .layout--split {
  grid-template-columns: 60px 1fr;
}
```

Any approach that replaces `display: none` with opacity/visibility tricks must also preserve this grid collapse — otherwise the hidden panel still occupies layout space and breaks the 2/3-column switching.

---

## Recommended approach

Replace the `display: none` mechanism with a two-phase opacity + pointer-events strategy combined with a `visibility: hidden` delayed via `transition-delay`. This allows CSS transitions to run before the element is removed from the accessibility tree.

### Step 1 — Replace display: none rules in App.css

Remove the existing `[data-active-tab]` `display: none` rules. Replace with:

```css
/* Hidden panel state — still participates in grid layout but invisible */
.panel-cards,
.panel-map {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
  transition:
    opacity var(--dur-base) var(--ease-out),
    visibility 0s linear 0s;           /* visibility changes instantly at start */
}

[data-active-tab="map"] .panel-cards,
[data-active-tab="home"] .panel-map,
[data-active-tab="alerts"] .panel-map,
[data-active-tab="saved"] .panel-map {
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition:
    opacity var(--dur-base) var(--ease-out),
    visibility 0s linear var(--dur-base); /* delay visibility until fade is done */
}
```

The `visibility: hidden` approach removes the panel from keyboard tab order and screen-reader traversal (like `display: none`) but does NOT remove it from layout — the grid column still exists and holds its width.

### Step 2 — Preserve the desktop grid collapse

Because `visibility: hidden` keeps the panel in layout, the grid will NOT auto-collapse when `panel-cards` or `panel-map` is hidden. You must keep the `grid-template-columns` collapse rules:

```css
[data-active-tab="map"] .layout--split,
[data-active-tab="alerts"] .layout--split,
[data-active-tab="saved"] .layout--split {
  grid-template-columns: 60px 1fr;
}
```

**This is the key danger:** if the grid column containing the hidden panel still occupies space (because `visibility: hidden` keeps it in layout), the `panel-map` `1fr` column will be narrower than intended on the "home" tab. The grid-template-columns rule must still explicitly remove the `panel-cards` column when only the map is shown.

Verify on desktop that:
- Home tab: 3 columns (`60px 420px 1fr`) — both panels visible
- Map tab: 2 columns (`60px 1fr`) — panel-cards opacity:0/visibility:hidden AND grid collapses
- Alerts/Saved tabs: 2 columns (`60px 1fr`) — panel-map hidden AND grid collapses

### Step 3 — Add translateX slide to the entering panel

The design spec calls for a subtle `translateX(8px)` on entry — the panel slides in 8px as it fades in. Apply this to both panels so whichever becomes visible slides in from the right:

```css
.panel-cards,
.panel-map {
  transform: translateX(0);
  transition:
    opacity var(--dur-base) var(--ease-out),
    transform var(--dur-base) var(--ease-out),
    visibility 0s linear 0s;
}

[data-active-tab="map"] .panel-cards,
[data-active-tab="home"] .panel-map,
[data-active-tab="alerts"] .panel-map,
[data-active-tab="saved"] .panel-map {
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transform: translateX(8px);
  transition:
    opacity var(--dur-base) var(--ease-out),
    transform var(--dur-base) var(--ease-out),
    visibility 0s linear var(--dur-base);
}
```

When the active tab changes and a panel transitions from hidden → visible, it begins at `translateX(8px) opacity:0` (set by the outgoing CSS rule) and immediately transitions to `translateX(0) opacity:1`. The 8px slide gives the directional sense of pages turning.

### Step 4 — Suppress on mobile

On mobile the panels are stacked vertically (single-column flex layout). The translateX slide is meaningless and may look glitchy when panels stack. Wrap the transition declarations in a desktop-only block:

```css
@media (min-width: 801px) {
  .panel-cards,
  .panel-map {
    /* transition rules here */
  }
}
```

The mobile `@media (max-width: 800px)` block already overrides layout to `display: flex; flex-direction: column`, which means panels are always in the same layout plane — visibility toggling is handled there separately and should remain `display: none` / `display: flex` on mobile (no transition needed).

### Step 5 — Respect prefers-reduced-motion

```css
@media (prefers-reduced-motion: reduce) {
  .panel-cards,
  .panel-map {
    transition: none;
  }
}
```

---

## Things to test after implementation

1. **Desktop — all 4 tab switches** confirm slide-in visible on each panel change.
2. **Desktop — grid layout** confirm the hidden column does not eat into the visible panel's width on each active tab (measure with browser DevTools grid inspector).
3. **Mobile — no transition glitch** switch tabs quickly on a real device; panels should snap (no partial opacity states from the desktop transition bleed-through).
4. **MapLibre map** — the map canvas must not flicker when `panel-map` transitions in. MapLibre re-renders when its container changes size; use `map.resize()` after the transition ends if a flicker is observed. The existing `setTimeout(0)` init workaround may interact with the transition timing.
5. **Keyboard / screen reader** — tab order must not land on hidden panel's focusable children. Confirm `visibility: hidden` is suppressing them (it should; `display: none` alternatives like `aria-hidden` may be needed if not).
6. **Live trip active** — during an active trip, the route card is in `panel-cards`. Switching to the Map tab should hide the card gracefully and not interrupt the GPS watchPosition loop.

---

## Why this was deferred

The transition cannot be added as a simple CSS one-liner because the current `display: none` architecture is load-bearing for the grid collapse. Changing it requires careful verification of the desktop layout at every tab combination. The risk of a subtle layout regression (e.g. the map being 60px narrower than intended on home tab) outweighs the purely cosmetic benefit of a 220ms slide. Implement this during a focused layout QA session where all 4 tabs × desktop + mobile + RTL can be verified before merging.

---

# Consideration — Migrate MapView to react-map-gl/maplibre

## Context

During the On-Map Symbols implementation (2026-04-30), we chose **Option A** for marker integration: raw `maplibregl.Marker` + `ReactDOM.createRoot`, keeping the existing imperative MapLibre GL JS approach in `MapView.jsx`. The three editorial markers (§ origin, ✦ destination, ➤ live position) are now proper React SVG components mounted this way — see Feature MapMarkers in `FEATURES_IMPLEMENTED_HISTORY.md`.

`react-map-gl/maplibre` was considered but deferred because:
- The existing imperative approach is already well-managed (tracked layer/source IDs, `clearRouteLayers`, solid `useEffect` cleanup)
- The `setTimeout(0)` StrictMode fix, interaction lock system, and style error handler all work correctly and would need careful re-porting
- No user-facing correctness benefit — purely a developer ergonomics improvement

## When to reconsider

Migrate to `react-map-gl/maplibre` if any of the following arise:
- A new map feature requires complex layer/source lifecycle that the imperative approach struggles with
- Layer or source leaks appear in production (layers not cleaning up between route changes)
- The imperative `_trackSource`/`_trackLayer` pattern becomes hard to follow as MapView grows

## What migration would involve

1. Replace `new maplibregl.Map(...)` init block with `<Map>` component from `react-map-gl/maplibre`
2. Re-port the `setTimeout(0)` StrictMode WebGL fix (may not be needed — check react-map-gl version)
3. Replace `map.addSource`/`map.addLayer` calls with `<Source>`/`<Layer>` JSX children
4. Replace imperative `maplibregl.Marker` + `ReactDOM.createRoot` marker mounting with `<Marker>` wrappers
5. Re-port interaction lock system (`scrollZoom.disable()` etc.) via `<Map>` event handlers or `ref`
6. Re-port style error handling (`map.on("error", ...)`) via `<Map onError={...}>` prop

---

# Consideration (Optional) — Intermediate Transfer Station Marks on Map

## Decision

During the On-Map Symbols handoff (2026-04-30), intermediate transfer station marks were explicitly **ruled out** for the initial implementation. The polyline shape already communicates the route; the existing board/exit circle rendering provides sufficient transfer context. Adding more marks was judged to clutter the editorial language without meaningful navigational benefit.

## When to reconsider

Only revisit if user research or feedback indicates riders are confused about where to transfer. The bar should be high — a cluttered map is a worse outcome than a sparse one in the editorial design language.

## If implemented

- Use a smaller mark than the origin/destination markers (suggested: 8–10 px, no label)
- Render only at board/exit points for each transit leg, not at every intermediate stop
- Must not visually compete with the origin § and destination ✦ marks
- Z-order: transfer marks below destination, above polylines

---

# Feature ReLock — Re-lock / "Follow Me" Map Button

## Overview

Once a user unlocks the map during an active trip to look around, there is no way to resume position-following without ending the trip. The unlock button (`map-unlock-btn`) disappears after the first tap and `unlocked` stays `true` for the trip's duration. A "Follow me" / "↻ Follow" button that re-engages position-following closes this loop.

**Type: Bolt-On** — all position-following logic (`map.easeTo`, the `unlocked` state, the live marker) already exists; this feature is purely a UI control wired to `setUnlocked(false)`.

## Behaviour

- Button appears only during an active trip (`tripActive && unlocked`).
- Tapping it calls `setUnlocked(false)`, which causes the live position effect to resume `map.easeTo()` on the next GPS update.
- The button disappears again once following resumes (same visibility condition: `tripActive && unlocked`).
- Editorial style: same hairline/cream/serif-italic treatment as the existing `map-unlock-btn` — they are inverse states of each other.

## Chunk 1 — UI control

**Files:** `frontend/src/MapView.jsx`, `frontend/src/App.css`

In the `MapView` JSX, add a button alongside the existing `map-unlock-btn`:

```jsx
{route && tripActive && unlocked && !styleError && (
  <button className="map-relock-btn" onClick={() => setUnlocked(false)}>
    ↻ Follow
  </button>
)}
```

Add `.map-relock-btn` CSS — same base as `.map-unlock-btn` but positioned bottom-right (or top-left, away from the unlock button's position). Verify both buttons never appear simultaneously (`map-unlock-btn` shows when `!unlocked`, `map-relock-btn` when `unlocked`).

---

# Feature ArrivedToast — Arrived Notification Toast

## Overview

The destination arrived latch fires silently — the ✦ ring fills solid ink, but nothing draws the user's eye to the screen. Riders watching the street or their phone lock screen miss the visual cue entirely. A brief editorial toast that auto-dismisses after ~5 seconds completes the trip arc.

**Type: Bolt-On** — the `arrivedRef` flip already fires in the live position effect; this feature adds a React state flag and a styled `<div>`. No new GPS or routing logic needed.

**Pairs naturally with Feature ReLock** — implement in the same session if both are being built.

## Behaviour

- When `arrivedRef.current` flips to `true`, also set a React state flag `arrivedToast: true` in `MapView` (or lift to `App.jsx` if the toast should appear over the full UI rather than just the map).
- Toast auto-dismisses after 5 seconds (`setTimeout` clearing the flag).
- Toast is also dismissible by tap.
- Does not re-trigger if the user re-plans a route and arrives again — the latch reset on trip end handles that.

## Chunk 1 — Toast state and trigger

**Files:** `frontend/src/MapView.jsx`

Add `const [showArrivedToast, setShowArrivedToast] = useState(false)`. In the live position effect, alongside `arrivedRef.current = true`, call `setShowArrivedToast(true)`.

```js
if (dist <= 50) {
  arrivedRef.current = true;
  setShowArrivedToast(true);
  destMarkerRef.current?.root.render(<DestinationMarker arrived={true} />);
}
```

In the trip-end cleanup block, also call `setShowArrivedToast(false)`.

## Chunk 2 — Toast UI and CSS

**Files:** `frontend/src/MapView.jsx`, `frontend/src/App.css`

```jsx
{showArrivedToast && (
  <div className="map-arrived-toast" onClick={() => setShowArrivedToast(false)}>
    <span className="map-arrived-toast__kicker">ARRIVED</span>
    <span className="map-arrived-toast__body">You have reached your destination.</span>
  </div>
)}
```

Editorial style: cream paper, ink border (hairline), Fraunces italic body, Inter 800 caps kicker (rust). Positioned top-center of the map. `@keyframes` fade-in from `opacity: 0` → `1` over 300 ms; fade-out can be CSS-driven or timer-driven. Add `prefers-reduced-motion` suppression of the fade animation.

---

# Feature TapRecentre — Tap Live Position Marker to Re-lock

## Overview

Tapping the ➤ live position marker re-engages map following — an alternative entry point to Feature ReLock that feels natural to users who instinctively tap the "you are here" indicator. The acceptance checklist in the On-Map Symbols handoff already noted this as a future interactive feature requiring a 44×44 tap target wrapper.

**Type: Bolt-On** — depends on Feature ReLock (shares the same `setUnlocked(false)` call). Implement after Feature ReLock is in place.

## Chunk 1 — Add click handler to live marker element

**Files:** `frontend/src/MapView.jsx`

`mountMarker` creates a `div` element and passes it to `maplibregl.Marker`. After `mountMarker` returns, attach a click listener to the element:

```js
liveMarkerRef.current = mountMarker(map, LivePositionMarker, markerProps, [lng, lat]);
liveMarkerRef.current.marker.getElement().addEventListener("click", () => {
  setUnlocked(false);
});
```

## Chunk 2 — 44×44 tap target

**Files:** `frontend/src/App.css`

The `LivePositionMarker` SVG is 36×36 px. Wrap the marker element in a larger transparent hit area:

```css
.marker-live-position-wrapper {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
```

Update `mountMarker` call for the live marker to set `el.className = "marker-live-position-wrapper"` before rendering the component into it.

---

# Feature RouteProgress — Grey Out Completed Route Legs

## Overview

As the user advances along a route, walk and transit polylines they have already passed shift to a muted visual state — the same pattern as `.leg-complete` in the route card, applied to the map. This gives a clear sense of progress and reduces cognitive load by de-emphasising past legs.

**Type: Bolt-On** — the route polyline layers are already rendered per-leg; changing their paint properties is a single `map.setPaintProperty()` call per layer. The challenge is detecting which leg the user is currently on.

## Behaviour

- A leg is "complete" when the user has passed its terminal point (exit stop for transit legs, final path point for walk legs) within a configurable radius (suggested: 80 m).
- Completed walk legs: `line-color` → `var(--mute)` equivalent hex, `line-opacity` → 0.4, `line-dasharray` unchanged.
- Completed transit legs: `line-color` → muted version of leg color (reduce saturation, e.g. mix with `#8a7a60`), `line-opacity` → 0.35.
- The current leg stays fully rendered.
- Board/exit circle markers for completed legs also mute (reduce opacity to 0.3).

## Chunk 1 — Leg completion detection

**Files:** `frontend/src/MapView.jsx`

Add a `completedLegsRef = useRef(new Set())` alongside the existing refs. In the live position effect, after the arrived latch check, iterate the route legs and check haversine distance to each leg's terminal point. When within 80 m, add the leg index to `completedLegsRef.current`.

## Chunk 2 — Apply muted paint to completed layers

**Files:** `frontend/src/MapView.jsx`

When `completedLegsRef.current` gains a new entry, call `map.setPaintProperty()` on the corresponding layer IDs (`route-walk-line-{i}`, `route-transit-line-{i}`, `route-boardexit-circle-{i}`). Layer IDs follow the existing naming convention from `_renderRouteInner`.

---

# Feature HeadingUp — Heading-Up Map Orientation

## Overview

The map currently stays north-up throughout a trip. Many navigation apps rotate the map to face the direction of travel (heading-up), which some riders find more intuitive when following turn-by-turn walk directions. The smoothed heading is already computed every GPS cycle; the only missing pieces are a `map.rotateTo()` call and a toggle UI.

**Type: Bolt-On** — no new GPS or heading logic; `smoothedHeadingRef.current` is already available in the live position effect.

## Behaviour

- Off by default — north-up is the existing behaviour and is less disorienting for the many riders who just glance at the map.
- A toggle button (e.g. a compass rose icon) switches between north-up and heading-up.
- In heading-up mode, `map.rotateTo(-smoothedHeadingRef.current, { duration: 200 })` is called alongside `map.easeTo()` on each GPS update.
- Rotation only applies while the map is locked (following). If the user unlocks the map, rotation stops.
- A compass rose indicator (or the button itself) shows current bearing so the user can orient themselves.

## Design notes

- The ➤ compass needle in `LivePositionMarker` always points the direction of travel relative to the SVG's own frame. In heading-up mode the map is rotated so that "up" is forward — the needle should still visually point "up" (forward), which means the needle's CSS rotation should account for the map bearing offset. Specifically: `headingProp = smoothedHeading - mapBearing`, where `mapBearing` is read via `map.getBearing()`.
- In north-up mode, `mapBearing = 0` so the needle angle equals the raw smoothed heading — no change from current behaviour.

## Chunk 1 — Toggle state and map rotation

**Files:** `frontend/src/MapView.jsx`

Add `const [headingUp, setHeadingUp] = useState(false)`. In the live position effect, after `map.easeTo()`:

```js
if (headingUp && Number.isFinite(smoothedHeadingRef.current)) {
  map.rotateTo(-smoothedHeadingRef.current, { duration: 200 });
}
```

## Chunk 2 — Needle bearing correction

**Files:** `frontend/src/MapView.jsx`

Pass an adjusted heading to `LivePositionMarker` that accounts for the current map bearing:

```js
const displayHeading = (smoothedHeadingRef.current - map.getBearing() + 360) % 360;
```

Pass `displayHeading` as the `heading` prop instead of `smoothedHeadingRef.current`.

## Chunk 3 — Toggle UI

**Files:** `frontend/src/MapView.jsx`, `frontend/src/App.css`

Add a compass toggle button to the map overlay (top-left, clear of the unlock/re-lock buttons). Show current bearing numerically (e.g. "NW 315°") or via a rotated compass rose SVG. Reset map bearing to 0 when switching back to north-up mode (`map.rotateTo(0, { duration: 300 })`).

---

# Consideration (Optional) — Intermediate Transfer Station Marks on Map
