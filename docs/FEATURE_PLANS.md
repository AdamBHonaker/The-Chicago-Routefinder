# Feature Plans

Chunked plans for upcoming major features, followed by ideas deferred until post-launch. For chunked features, work through each chunk in order, one chunk per session or per commit. Do not start a chunk until all previous chunks are complete.

> **Process:** When a feature here is fully implemented, **delete its entry from this file** and add a corresponding entry to [`docs/archive/FEATURE_HISTORY.md`](archive/FEATURE_HISTORY.md) summarizing what was built. This file should only ever contain features that have not yet been implemented.

---

## Feature Index

**Bolt-On** = self-contained, no dependencies on other planned features.
**Structural** = depends on one or more other features before it can be fully built or realized.

**Chunked Implementation Plans** (in document order):
1. Feature Monetization — House Ads (overall Phase 7, sub-phase 1; third-party networks deferred) — **Bolt-On**
2. Feature TransferMarkers — Intermediate transfer station marks on the map for the active trip — **Bolt-On**
3. Feature PaceMetraCoverage — Pace + Metra service-area expansion of the walking street graph — **Structural** (depends on Pace/Metra being added to the transit graph)

---

## Chunked Implementation Plans

---

## Feature Monetization --- House Ads (overall Phase 7, sub-phase 1)

### Overview

Adds a house ad component to partially offset Railway hosting costs without compromising the Heritage Organic UI. The approach is deliberately conservative: house ads only in Phase 1 — no external ad scripts, no third-party cookies, no layout disruption. Third-party networks (EthicalAds, Carbon Ads) are deferred until the user base is meaningful. Google AdSense is explicitly avoided for now — auto-placed display ads carry a high risk of clashing with the cream/charcoal design and hurting retention.

**Target:** ~200 DAU × 2 searches/day = ~12k monthly impressions. Affiliate click-through revenue at modest conversion rates can partially offset hosting; the primary value in Phase 1 is building the slot and proving it doesn't hurt UX.

**Why it matters:** The app has real operational costs. The house ad is the minimal intervention that keeps the interface intact while creating a revenue path.

**Type: Bolt-On** --- frontend-only addition; no backend changes.

**Status: Not started**

**Prerequisites:**
- Railway + Vercel deployment live and stable (Phase 6 complete).

---

### Scoping decisions

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

### Chunk 1 --- House ad component

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`, `frontend/.env.example`, `frontend/.env.local`, `frontend/.env.production`

**What to build:**

- Add an `AdSlot` inline component (no separate file needed --- small enough to inline in App.jsx) that renders a static house ad `<a>` tag.
- Mount `AdSlot` at the bottom of the results list, inside the left panel, below the last RouteCard. Render only when results exist (`routes.length > 0`).
- Style per Heritage Organic: cream background, `--hairline` top-divider line, charcoal text. No heavy border or shadow. The slot must be indistinguishable in feel from the rest of the UI — it should look like a contextual tip, not a foreign element.
- `VITE_HOUSE_AD_URL` and `VITE_HOUSE_AD_TEXT` are configurable via Vercel env vars so the house ad can be updated without a redeploy.
- `VITE_HOUSE_AD_ENABLED` defaults to `false` in `.env` (off in local dev) and is set to `true` in Vercel after confirming the slot looks correct in production.

#### Implementation specifics

- **Mount point (exact):** Inside the `result.routes.length > 0 &&` block at [frontend/src/App.jsx:658-715](frontend/src/App.jsx#L658-L715), render `<AdSlot />` after the `result.routes.map(...)` and before the closing `</section>` (line 714). Additionally gate on `!tripActive` — during a live trip the panel collapses to a single selected card and an ad below it would feel out of place.
- **Design tokens to use** (defined at [frontend/src/App.css:1-68](frontend/src/App.css#L1-L68)): `--paper`, `--ink`, `--ink-soft`, `--rust` (link color), `--hairline` (top divider), `--serif` (italic editorial flavor), `--sans` for kicker, `--sp-3`/`--sp-4` for padding, `--fs-body-sm` body, `--fs-caps`/`--ls-caps` for the "SPONSORED" kicker. Do not introduce `--color-border` (that token does not exist — use `--hairline` for the divider).
- **Required `<a>` attributes:** `target="_blank"`, `rel="sponsored noopener noreferrer"`. Render a small "SPONSORED" caps kicker above the body copy so the disclosure is always visible (FTC affiliate-link guidance).
- **Env files to update:** [frontend/.env.example](frontend/.env.example), [frontend/.env.local](frontend/.env.local), [frontend/.env.production](frontend/.env.production). Add `VITE_HOUSE_AD_ENABLED` (default `false`), `VITE_HOUSE_AD_URL`, `VITE_HOUSE_AD_TEXT`. Read with `import.meta.env.VITE_*` (mirror the pattern at [frontend/src/MapView.jsx:16](frontend/src/MapView.jsx#L16)).
- **i18n note:** Wrap the "SPONSORED" kicker in `t("ad_sponsored_kicker")`; the ad copy itself comes from the env var (intentionally not translated — affiliate links are typically English/USD and per-market).
- **Mobile clearance:** Tab bar is `position: fixed; bottom: 0`. Verify the `AdSlot` does not get hidden behind it; the existing results column already pads for the tab bar — confirm the bottom padding is at least the slot height + tab-bar height before shipping.

#### Acceptance criteria

1. With `VITE_HOUSE_AD_ENABLED=false`, no `<a>` is rendered and there are no console warnings.
2. With it `true` and URL/TEXT set, the ad shows below the last RouteCard on the Home tab only.
3. The ad is hidden during an active trip (`tripActive === true`).
4. Lighthouse a11y score is unchanged from the pre-feature baseline.
5. The slot inherits `--paper` background and reads as part of the editorial column rather than a foreign element.

---

### Affiliate Products Reference (House Ad Candidates)

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

## Feature TransferMarkers --- Intermediate transfer station marks on the map

### Overview

During an active trip (after the rider taps "Start Route"), render small editorial marks on the map at every point where the rider changes mode or vehicle: rail↔rail, rail↔bus, bus↔bus, walk→transit, and transit→walk. These markers are the missing wayfinding piece between the route polyline (where the trip goes) and the existing O/§/✦ markers (where it starts and ends). The polyline already communicates the path; what it does not show is *the moment the rider has to do something* — get off, walk to a different platform or corner, board a different vehicle. Transfer markers make those moments visually addressable on the map and tappable from the itinerary spine.

The previous design decision (2026-04-30, On-Map Symbols handoff) ruled these out as clutter. This feature reverses that decision but keeps the underlying concern in scope: markers render *only for the selected route*, *only after Start Route*, and *only at meaningful mode/vehicle transitions* — never as ambient stop dots. Combined with the editorial glyph language and tap-only labels, the result is a map that stays sparse during browsing and gains exactly-as-much detail as the rider needs during execution.

**Why it matters:** At Clark/Lake, four lines converge across two levels — knowing *which* leg of the itinerary corresponds to *which* platform is the difference between a smooth transfer and a missed train. At a bus↔bus corner where boarding and alighting stops sit on different sides of the intersection, a single dot at the alighting stop hides the fact that the rider has to cross. These are the exact moments the editorial language was missing.

**Type: Bolt-On** --- frontend-only. The backend already exposes everything needed (verified 2026-05-03; see Prerequisites).

**Status: Not started**

**Prerequisites:**

- Phase 5 ItinerarySpine shipped (already complete — see [`docs/archive/FEATURE_HISTORY.md`](archive/FEATURE_HISTORY.md)).
- Phase 5 MapMarkers shipped (already complete) — provides the imperative `maplibregl.Marker` + `ReactDOM.createRoot` mounting pattern that this feature reuses.
- Backend `/recommend` response already includes per-leg `from_coords`, `to_coords`, `from_mapid`, `from`/`to` station names, `line_code`, and WalkLeg `path` arrays (verified at [backend/main.py:1128-1153](backend/main.py#L1128-L1153)). **No backend work is required.**

---

### Scoping decisions

These were settled during planning (2026-05-03). Re-opening any of them should be a deliberate choice, not drift.

1. **Scope of "transfer."** All five mode/vehicle transitions get marked: rail↔rail, rail↔bus, bus↔bus, walk→transit (boarding the first vehicle of the trip), and transit→walk (alighting the last vehicle of the trip). Walk→walk transitions don't exist in the leg model and are not a concern.

2. **Trigger / lifecycle.** Markers render *only* for the rider's currently selected route, *only* after `tripActive === true` (i.e., after Start Route is tapped). They **auto-clear** in three cases: trip ends, route is deselected, a new search runs. Browsing routes pre-trip never shows them.

3. **Glyph language — two distinct glyphs.**
   - **Transfer glyph** (rail↔rail, rail↔bus, bus↔bus): editorial double-ruled small circle in the Routefinder design language. Specs: paper backing `r=8`; outer ink ring `r=7` `strokeWidth=2`; inset hairline `r=5` `strokeWidth=0.75`; centered Fraunces-italic `×` glyph (~6px) reading as "crossing point." Smaller than DestinationMarker's 24px crosshair so it reads as supporting context, not as a third trip endpoint.
   - **Footprint dot** (walk→transit, transit→walk): minimal mark — paper underlay `r=4`, ink dot `r=2.5`, no center glyph. The adjacent dashed walking polyline (existing system primitive) does the semantic heavy lifting; the dot just terminates the dash cleanly atop the route line.

4. **Anchor and clustering rules.**
   - Rail↔rail: one marker per station, anchored at the station coords. Same-platform transfers (e.g., Red→Purple at Belmont) still get a marker — riders confirmed this is wanted, not redundant.
   - Bus↔bus where alighting and boarding stops are within ~30ft of each other (functionally same corner): one marker at the alighting stop, no connector line.
   - Bus↔bus where alighting and boarding stops are 30ft–~1 city block apart: one marker at the alighting stop, plus a short **dashed connector line** to the boarding stop. Connector spec: `strokeWidth=1.5`, `--ink-soft`, `strokeDasharray="4 4"`. The dashed style signals "short walk to a different corner" without competing with the dashed *walking-leg* line (which uses the existing `3 4` dasharray at 2px in `--ink`).
   - Bus↔bus where stops are >1 city block apart: backend should already insert a real `WalkLeg` between them. In that case, no transfer marker is drawn at the alighting stop — the standard transit→walk and walk→transit footprint dots cover both ends. **Verify this assumption holds during Chunk 1** (it depends on transit-graph leg construction).
   - Rail↔bus where the bus stop is across the street from the station entrance: same dashed-connector rule as bus↔bus split stops.

5. **Label.** Tap/click only. No always-on station name labels — at downtown super-stations (Clark/Lake, State/Lake, Jackson) always-on labels would stack and become illegible. Tap reveals a small flag callout in the existing OriginMarker label idiom (Inter caps kicker + Fraunces-italic place name); tap elsewhere or tap another marker dismisses it.

6. **Z-order**, bottom to top:
   1. Route polyline.
   2. Regular stop dots (if/when added — currently none).
   3. Transfer markers + footprint dots.
   4. Origin and Destination markers.
   5. LivePositionMarker.

7. **Spine ↔ map coupling — v1 is one-way (spine → map).** Tap a spine row in RouteCard → map flies to the corresponding transfer marker (`map.flyTo(coords, { duration: 400 })`) and the marker enters its **selected state**. Tap dismisses. Map → spine coupling is deferred — see "Deferred to v2" below for the case.

8. **Selected-state visual.** A third concentric outline offset 3px outside the marker's existing outer rule, drawn at `strokeWidth=0.75` in `--rust`. This is a direct extension of the system's existing layered-linework idiom (Origin already has 2px outer + 0.75 hairline inner; selection adds a 0.75 hairline outer). No animation — pulse would be the only animated element in the entire system and would clash with the editorial aesthetic.

9. **Passed-state visual.** As the LivePositionMarker passes a transfer point during a live trip (i.e., when `activeLegIndex` advances past the leg the marker terminates), the marker gains a thin black ring (`strokeWidth=1`, `--ink`) filled with `--ink`. Same grammar as selected-state, distinguishable by which ring/fill is involved.

10. **Backend.** Confirmed sufficient — no API or backend changes. All transfer points are derivable from adjacent leg pairs in the existing `/recommend` response.

---

### Deferred to v2

**Map → spine coupling.** Tapping a marker on the map could scroll the corresponding spine row into view and select it. Deferred for v1 because: (a) the implementation cost is asymmetric — it requires per-row refs in RouteCard's spine and `scrollIntoView()` logic, vs. spine→map's ~30 lines; (b) the natural rider workflow is "read itinerary → look at map," not the reverse; (c) during `tripActive`, the panel collapses to a single selected card and the spine is fully visible without scrolling, so the work mostly pays off in pre-trip browsing — but markers don't render pre-trip. Re-add to active scope if post-launch feedback shows riders tapping markers and expecting the spine to react.

**Differentiated glyphs per transit-mode pair.** All three of (rail↔rail, rail↔bus, bus↔bus) share one glyph in v1. Visually distinguishing them (e.g., different center marks) is over-engineering until users complain.

---

### Chunk 1 --- Transfer-point derivation utility (frontend, pure)

**Files:** `frontend/src/utils/deriveTransferPoints.js` (new), `frontend/src/utils/__tests__/deriveTransferPoints.test.js` (new).

**What to build:**

- A pure function `deriveTransferPoints(route)` that takes a route object (the shape returned by `/recommend`) and returns an array of transfer-point descriptors:
  ```
  { type: "rail-rail" | "rail-bus" | "bus-bus" | "walk-transit" | "transit-walk",
    coords: [lng, lat],
    boardingCoords: [lng, lat] | null,    // only set for split-stop bus↔bus / rail↔bus
    stationName: string,
    alightingLegIndex: number,            // index of the leg the rider gets off (or null for walk→transit at trip start)
    boardingLegIndex: number,             // index of the leg the rider gets on (or null for transit→walk at trip end)
    needsConnector: boolean,              // true if alight+board stops are 30ft–1 block apart
  }
  ```
- Walk adjacent leg pairs in `route.legs`. For each pair `(leg[i], leg[i+1])`:
  - WalkLeg → TransitLeg → emit `walk-transit` at `legs[i+1].from_coords`.
  - TransitLeg → WalkLeg → emit `transit-walk` at `legs[i].to_coords`.
  - TransitLeg → TransitLeg → emit `rail-rail`, `rail-bus`, or `bus-bus` based on whether each leg's `line_code` is in `LINE_NAMES` (rail) or not (bus). Use `legs[i+1].from_coords` as the anchor.
- For TransitLeg→TransitLeg pairs, compute distance between `legs[i].to_coords` and `legs[i+1].from_coords` using the haversine formula. Set `needsConnector=true` if distance is between ~10m and ~120m (one Chicago city block ≈ 100m). Set `boardingCoords` to `legs[i+1].from_coords` when `needsConnector` is true; otherwise null.

**Implementation specifics:**

- `LINE_NAMES` (rail line codes) is already in [frontend/src/lineColors.js](frontend/src/lineColors.js) — import it. Don't duplicate the list.
- Station-name resolution: prefer `legs[i].to` (the alighting station name string) for the marker label; fall back to `legs[i+1].from` if the former is missing.
- The function must be pure and synchronous. No fetching, no React, no map references. It's the testable kernel of this whole feature.

**Acceptance criteria:**

1. Unit tests cover all five transition types, the three bus↔bus stop-distance regimes (same-corner, split-stop, far-apart-with-walkleg), and the same-platform same-stop rail transfer (which still emits a marker).
2. A route with zero transfers (single TransitLeg sandwiched between two WalkLegs) returns exactly two descriptors: one `walk-transit`, one `transit-walk`.
3. A walk-only route (no TransitLegs) returns an empty array.
4. The function does not mutate its input.

---

### Chunk 2 --- Marker components (TransferMarker, FootprintMarker)

**Files:** `frontend/src/components/markers/TransferMarker.jsx` (new), `frontend/src/components/markers/FootprintMarker.jsx` (new).

**What to build:**

- `<TransferMarker />` — the editorial double-ruled circle. Props: `label?: string`, `state?: "default" | "selected" | "passed"`, `paperColor`, `inkColor`, `muteColor`, `accentColor` (default `--rust`). SVG structure mirroring [OriginMarker.jsx](frontend/src/components/markers/OriginMarker.jsx):
  - Paper backing `<circle r=8>`.
  - Outer ink ring `<circle r=7 strokeWidth=2 stroke={inkColor} fill="none">`.
  - Inset hairline `<circle r=5 strokeWidth=0.75 stroke={inkColor} fill="none">`.
  - Center `×` glyph as `<text>` in Fraunces-italic, fontSize=6, textAnchor=middle, fontWeight=700.
  - When `state="selected"`: add an outer `<circle r=10 strokeWidth=0.75 stroke={accentColor} fill="none">`.
  - When `state="passed"`: change inset hairline to `strokeWidth=1` and fill the inner area with `inkColor` (the `×` flips to `paperColor` for legibility).
  - Tap-label rendering: same idiom as OriginMarker — Inter caps kicker (`TRANSFER`) + Fraunces-italic station name. Only shown when `label` prop is set.
- `<FootprintMarker />` — minimal walk-transition mark. Props: `label?: string`, `state?: "default" | "selected" | "passed"`, same color props. SVG:
  - Paper backing `<circle r=4>`.
  - Ink dot `<circle r=2.5 fill={inkColor}>`.
  - When `state="selected"`: add `<circle r=6 strokeWidth=0.75 stroke={accentColor} fill="none">`.
  - When `state="passed"`: `<circle r=4 strokeWidth=1 stroke={inkColor} fill="none">` overlaid (a thin ring in ink, same grammar as TransferMarker passed state).
  - No center glyph, no kicker; the tap-label (when present) is just the Fraunces-italic station name in the OriginMarker flag idiom.

**Implementation specifics:**

- Match the `viewBox="0 0 W H" overflow="visible" display="block"` pattern from OriginMarker exactly so MapView's marker mounting (which uses `anchor: "center"`) places these at the correct pixel.
- Default color values: `paperColor="#f4ead5"`, `inkColor="#1a1510"`, `muteColor="#8a7a60"`, `accentColor="#b3502a"` (the rust hex used by `--rust` in [frontend/src/App.css](frontend/src/App.css) — verify before hardcoding).
- Both components must be `React.memo`-able — they will re-render when state changes during a live trip.

**Acceptance criteria:**

1. Visual review at 1× and 2× DPR confirms the marker reads cleanly on tile backgrounds matching `--paper`, lake blue, and street grey.
2. The three states (`default`, `selected`, `passed`) render distinctly without DOM remounting.
3. Tap-label appears flush against the marker (no gap or overlap) and its kicker matches OriginMarker's letter-spacing/font-weight.
4. No console warnings under React StrictMode.

---

### Chunk 3 --- Mount markers in MapView, gated on tripActive + selectedRoute

**Files:** [frontend/src/MapView.jsx](frontend/src/MapView.jsx) (modify).

**What to build:**

- Inside MapView, add a new `useEffect` that runs when `tripActive`, `route`, or `activeLegIndex` change. The effect:
  - If `!tripActive || !route` — clear any existing transfer markers and dashed connector lines, then return.
  - Otherwise, call `deriveTransferPoints(route)` and mount markers via the existing imperative pattern (`new maplibregl.Marker(...)` + `ReactDOM.createRoot` — see how OriginMarker is mounted around [MapView.jsx:66-77](frontend/src/MapView.jsx#L66-L77)).
- Track all transfer-marker instances and dashed-connector source/layer IDs in a ref (`transferMarkersRef`, `transferConnectorIdsRef`) so they can be cleaned up cleanly. Reuse the `_trackSource` / `_trackLayer` helpers if they're factored, or follow the same pattern.
- Compute `state` per descriptor each tick: `state="passed"` when `activeLegIndex > descriptor.alightingLegIndex` (the rider is past this transfer); otherwise `"default"`. Selected-state is owned by Chunk 4.
- Render dashed connector lines for descriptors with `needsConnector=true`: add a GeoJSON LineString source from `descriptor.coords` to `descriptor.boardingCoords`, layer with `line-dasharray: [4, 4]`, `line-width: 1.5`, `line-color: var(--ink-soft hex)`. Z-order: above the route polyline, below the markers (markers are DOM, so always above canvas layers).
- Set marker z-order via the maplibre `Marker` element's container `style.zIndex`: footprint/transfer markers below O/D, above polyline. Confirm O/D markers' z-index and use a value below them.

**Implementation specifics:**

- The `tripActive` and `activeLegIndex` props are already wired through MapView ([MapView.jsx:277-278](frontend/src/MapView.jsx#L277-L278)) and [App.jsx](frontend/src/App.jsx). No new props.
- Cleanup must be idempotent. The effect's cleanup function runs on every dep change, so it must remove all currently-mounted transfer markers and connector layers before the next mount pass. Failing to do this leaks DOM nodes during route deselection.
- StrictMode double-mount: follow the same `setTimeout(0)` pattern already used for O/D markers if needed. Verify by toggling `tripActive` rapidly in dev — no duplicate markers should appear.

**Acceptance criteria:**

1. Tapping Start Route on a multi-leg itinerary mounts one marker per derived transfer point, at correct coordinates.
2. Ending the trip, deselecting the route, or running a new search clears all transfer markers and connector lines — no orphan DOM nodes (verify in the React DevTools Components panel).
3. As the rider's `activeLegIndex` advances, passed transfers visually transition to the passed-state ring without remount flicker.
4. Bus↔bus split-stop transfers render exactly one marker plus one dashed connector. Same-corner bus↔bus transfers render exactly one marker, no connector.
5. Walk→transit and transit→walk render footprint dots, not transfer glyphs.

---

### Chunk 4 --- Spine→Map coupling (selected-state lifecycle)

**Files:** [frontend/src/components/RouteCard.jsx](frontend/src/components/RouteCard.jsx) (modify), [frontend/src/MapView.jsx](frontend/src/MapView.jsx) (modify), [frontend/src/App.jsx](frontend/src/App.jsx) (likely modify — to thread the selected-transfer-id state).

**What to build:**

- In RouteCard, the existing leg-spine rows ([RouteCard.jsx:62, 145](frontend/src/components/RouteCard.jsx#L62)) become tappable when `tripActive === true`. Each tap on a row whose corresponding leg-pair has a transfer marker emits a `selectedTransferId` (e.g., `${alightingLegIndex}-${boardingLegIndex}`).
- Lift `selectedTransferId` state to App.jsx (or wherever route + tripActive live), pass it down to MapView.
- In MapView, when `selectedTransferId` changes:
  - Find the matching descriptor in the most recent `deriveTransferPoints(route)` output.
  - `map.flyTo({ center: descriptor.coords, duration: 400 })`.
  - Re-render the corresponding marker with `state="selected"`. All other markers render with their default-or-passed state.
- Dismissal: tapping the same spine row again, tapping a different row, ending the trip, or running a new search clears `selectedTransferId`. (Tapping the marker itself does *not* dismiss in v1 — that's part of map→spine coupling, deferred.)

**Implementation specifics:**

- The leg-spine currently has `aria-hidden="true"` ([RouteCard.jsx:62](frontend/src/components/RouteCard.jsx#L62)) since it's decorative. When making rows interactive during `tripActive`, also remove the aria-hidden and add `role="button"` + `aria-pressed` reflecting selection. Keep accessibility in mind: rows that *aren't* transfer points (mid-leg rows) shouldn't be tappable.
- Selection state is per-route — switching routes (which clears via Chunk 3) must also clear `selectedTransferId`.
- `flyTo` should not run when the selected marker is already on-screen (skip if its coords are within the current map viewport with a small inset). Otherwise rapid spine taps cause jittery panning.

**Acceptance criteria:**

1. Tapping a transfer-point row in the active trip's spine pans the map to the marker and applies the selected-state ring.
2. Tapping the same row dismisses (selected-state ring disappears, no pan back).
3. Tapping a different transfer row pans + selects the new marker (and de-selects the previous).
4. Ending the trip, deselecting the route, or running a new search clears any selected state.
5. Mid-leg spine rows (rows that don't correspond to a transfer point) are not focusable/tappable and have no visual hover/press state.
6. Keyboard navigation: tab order through transfer rows works, Enter/Space activates.

---

## Consideration — Migrate MapView to react-map-gl/maplibre

### Context

During the On-Map Symbols implementation (2026-04-30), we chose **Option A** for marker integration: raw `maplibregl.Marker` + `ReactDOM.createRoot`, keeping the existing imperative MapLibre GL JS approach in `MapView.jsx`. The three editorial markers (§ origin, ✦ destination, ➤ live position) are now proper React SVG components mounted this way — see Feature MapMarkers in `FEATURE_HISTORY.md`.

`react-map-gl/maplibre` was considered but deferred because:
- The existing imperative approach is already well-managed (tracked layer/source IDs, `clearRouteLayers`, solid `useEffect` cleanup)
- The `setTimeout(0)` StrictMode fix, interaction lock system, and style error handler all work correctly and would need careful re-porting
- No user-facing correctness benefit — purely a developer ergonomics improvement

### When to reconsider

Migrate to `react-map-gl/maplibre` if any of the following arise:
- A new map feature requires complex layer/source lifecycle that the imperative approach struggles with
- Layer or source leaks appear in production (layers not cleaning up between route changes)
- The imperative `_trackSource`/`_trackLayer` pattern becomes hard to follow as MapView grows

### What migration would involve

1. Replace `new maplibregl.Map(...)` init block with `<Map>` component from `react-map-gl/maplibre`
2. Re-port the `setTimeout(0)` StrictMode WebGL fix (may not be needed — check react-map-gl version)
3. Replace `map.addSource`/`map.addLayer` calls with `<Source>`/`<Layer>` JSX children
4. Replace imperative `maplibregl.Marker` + `ReactDOM.createRoot` marker mounting with `<Marker>` wrappers
5. Re-port interaction lock system (`scrollZoom.disable()` etc.) via `<Map>` event handlers or `ref`
6. Re-port style error handling (`map.on("error", ...)`) via `<Map onError={...}>` prop

### Evaluation — 2026-05-03 (defer)

Re-evaluated against the trigger list above. **Outcome: defer, no triggers have fired.**

- **Trigger 1 (complex lifecycle):** Not fired. Heritage markers, walking-leg path types, and ItinerarySpine all shipped without strain on the imperative approach.
- **Trigger 2 (leaks in production):** Not fired. `clearRouteLayers` (MapView.jsx:92–100) with try/catch guards is holding.
- **Trigger 3 (`_trackSource`/`_trackLayer` hard to follow):** Borderline. MapView is 679 lines / 5 useEffects, but the tracking bookkeeping is ~20 lines — bulk lives in markers, heading-up, and lock state, none of which migration would reduce.

**Cost/benefit:** Net code reduction ~80–120 lines / ~15%, concentrated in marker mounting. Animations (`fitBounds`/`flyTo`/`easeTo`/`rotateTo`), interaction lock, leg-muting paint mutations, and heading-up logic remain imperative via `useMap()` ref even after migration. Risk is asymmetric: zero MapView tests means every edge case (StrictMode double-mount, GPS first-fix flyTo, leg muting on `activeLegIndex`, single-fire arrival callback, transient tile-error filtering) must be re-verified manually. The `setTimeout(0)` StrictMode fix exists for a real WebGL context-loss reason — trusting react-map-gl's handling without reproducing the original failure is a gamble.

**Cheaper interim path** if the bookkeeping starts to bother us, in priority order:
1. ~~Extract `_trackSource`/`_trackLayer`/`clearRouteLayers` + polyline/stop renderers into a `useRouteLayers(map, route)` hook.~~ **Done 2026-05-03** — see [frontend/src/hooks/useRouteLayers.js](../frontend/src/hooks/useRouteLayers.js).
2. ~~Extract marker mounting into a `useMapMarker(map, Component, props, coords)` hook.~~ **Done 2026-05-03** — see [frontend/src/hooks/useMapMarker.jsx](../frontend/src/hooks/useMapMarker.jsx). Origin and destination markers now declarative; live-position marker remains imperative (uses exported `mountMarker`/`removeMarker`) because its heading prop must update synchronously with the smoothed-heading ref.
3. Add a MapView smoke test that mounts with a fixture route and asserts no console errors. Builds the regression net we'd want before any future migration. **See dedicated consideration entry below.**

**Post-refactor state (2026-05-03):** MapView.jsx is now 427 lines (was 679, -37%). Imperative bookkeeping for layers and origin/dest markers is gone. The only remaining triggers that would justify a full react-map-gl migration are dynamic/data-driven layer composition or a leak surfacing.

**Re-add to active consideration if:** any planned feature needs dynamic/data-driven layer composition (toggleable layers, multi-trip overlays, custom raster tiles), MapView grows past ~900 lines, a real leak surfaces, or a second engineer joins and onboarding friction becomes a cost.

---

## Consideration — MapView smoke test (regression net for future migration)

### Context

During the 2026-05-03 evaluation of migrating MapView to react-map-gl, the largest single risk identified was **no automated regression net**: zero tests cover MapView, so any non-trivial change must be re-verified manually across animations, interaction lock, arrival callback, StrictMode double-mount, transient tile errors, and leg-muting paint mutations. The two interim hook extractions (`useMapMarker`, `useRouteLayers`) shipped without this safety net by relying on type-checking and manual smoke tests; that approach does not scale to a wholesale library swap.

A small smoke test would not exercise WebGL (jsdom has none), but it can catch the regressions that actually break in practice: thrown errors during mount, missing layer cleanup on unmount, hook-order violations, prop-shape mismatches, and console errors during a route swap.

### When to build it

Build the smoke test if **either** of the following becomes true:

1. **Migration to react-map-gl is approved.** The smoke test must land *before* the migration starts — not as part of it — so it can detect regressions introduced by the swap rather than codifying the migrated behavior.
2. **MapView grows past ~900 lines** (current: 427). At that size the manual-verification cost per change is high enough that a one-time test investment pays back. A second engineer joining the project hits this trigger early; solo development can tolerate a higher line count.

Until one of these fires, the test is not worth the maintenance cost — `maplibre-gl` would need to be mocked (jsdom has no WebGL), and the mock surface drifts as the library evolves.

### Scope when built

- New file: `frontend/src/__tests__/MapView.test.jsx`.
- Mock `maplibre-gl` at the module level: stub `Map`, `Marker`, and the methods MapView calls (`addSource`/`addLayer`/`removeLayer`/`removeSource`/`fitBounds`/`flyTo`/`easeTo`/`rotateTo`/`setPaintProperty`/`getBearing`/`isStyleLoaded`/`on`/`once`/`off`/`resize`/`triggerRepaint`/`remove` plus the six interaction-control namespaces).
- A reusable route fixture — derive from an existing backend test response or hand-write a minimal `{legs: [walk, transit, walk]}` shape covering both leg types.
- Assertions:
  1. Mounts with `route=null` without throwing or logging errors.
  2. Mounts with the fixture route, spy confirms `addSource`/`addLayer` called the expected number of times, no console errors.
  3. Re-renders with a different route — spy confirms previous layers removed before new ones added (catches the leak case).
  4. Unmounts cleanly — spy confirms `map.remove()` called, no console errors.
  5. With `tripActive=true` + `userPosition`, confirms `flyTo` called once on first fix, not on subsequent updates.
  6. With `arrived` triggered (userPosition within 50m of destCoords), confirms `onArrived` callback fires exactly once.
- Estimated effort: 2–3 hours including the maplibre mock.

### Out of scope

- Visual snapshot testing — WebGL output cannot be rendered in jsdom, and pixel-level testing has never paid back its maintenance cost on this project.
- Testing `useMapMarker` and `useRouteLayers` in isolation. They are tightly coupled to maplibre's lifecycle and a unit test would essentially re-test the mock. The smoke test exercises them through MapView, which is the correct integration boundary.

---

## Feature PaceMetraCoverage --- Pace + Metra service-area expansion

### Overview

Today the street-graph bbox covers Chicago city limits + Evanston (Purple Line). Western suburbs (Oak Park, Forest Park, Cicero, Skokie, Rosemont) and southern Chicago below ~100th St are excluded to keep the graph file size manageable. Pace (suburban bus) and Metra (commuter rail) extend across the six-county metropolitan area, but neither is currently routed by the app. When Pace and/or Metra are added to the transit graph, the walking street graph must expand correspondingly so that walk legs at Pace stops and Metra stations get accurate street-routed walk times instead of Haversine fallbacks.

**Type: Structural** --- depends on whichever transit-data feature first introduces Pace or Metra routing.

**Status: Deferred (no transit-data work for Pace/Metra is planned yet)**

### Scope when this is built

1. Determine the actual coverage area needed:
   - **Metra:** ~240 stations across 11 lines extending to Kenosha, Aurora, Joliet, etc. — covers ~6,000 sq mi if a full bbox is used.
   - **Pace:** ~600 routes across Cook + 5 collar counties — covers nearly the entire 8-county Chicagoland region.
2. Almost certainly **switch from a single rectangle to a polygon** (`ox.graph_from_polygon`). A rectangle big enough to contain Aurora to Kenosha would be ~80mi × 60mi and impractical.
3. Likely approach: union 0.25-mile buffers around each Metra station + 0.1-mile buffers around each Pace stop, converted to a multipolygon. See the train-only polygon approach considered (and rejected) in walking-paths work for prior art.
4. Memory and graph-load time will increase substantially. May need to shard the graph by region (north/south/west) and lazy-load per request, or move from in-process pickle to a tile server.

### Files this would touch

- `backend/utils.py` — bbox/polygon definition.
- `backend/fetch_street_graph.py` — switch from `graph_from_bbox` to `graph_from_polygon`; source Pace/Metra stop coords from their respective GTFS feeds.
- `backend/walking.py` — likely no change; still loads a single artifact.
- Deployment — pickle size will grow; verify Railway memory headroom and LFS quota.

### Prerequisites

- Pace and/or Metra integrated into the transit graph.
- Decision on whether to ship one expanded artifact or shard by region.

---

