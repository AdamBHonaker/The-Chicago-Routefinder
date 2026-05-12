# Feature Plans

Chunked plans for upcoming major features, followed by ideas deferred until post-launch. For chunked features, work through each chunk in order, one chunk per session or per commit. Do not start a chunk until all previous chunks are complete.

> **Process:** When a feature here is fully implemented, **delete its entry from this file** and add a corresponding entry to [`docs/archive/FEATURE_HISTORY.md`](archive/FEATURE_HISTORY.md) summarizing what was built. This file should only ever contain features that have not yet been implemented.

---

## Feature Index

**Bolt-On** = self-contained, no dependencies on other planned features.
**Structural** = depends on one or more other features before it can be fully built or realized.

**Chunked Implementation Plans** (in document order):

1. Feature Monetization — House Ads (overall Phase 7, sub-phase 1; third-party networks deferred) — **Bolt-On**
2. Feature PaceMetraCoverage — Pace + Metra service-area expansion of the walking street graph — **Structural** (depends on Pace/Metra being added to the transit graph)

**Analytics Suite — Privacy-Preserving Reach & Engagement Metrics** — ✅ **Complete 2026-05-04.** All nine features (FEAT-001 through FEAT-009) fully implemented across four build phases. Public dashboard live at `/stats`; admin endpoints at `/admin/*`. Three accompanying Considerations (third-party analytics, DAU reconciliation, GeoIP) all resolved. See [docs/archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md) for the full implementation record and [docs/ANALYTICS_MAINTENANCE.md](ANALYTICS_MAINTENANCE.md) for ongoing maintenance notes.

**Standalone Features** (not part of a chunked plan or the analytics suite):

- FEAT-011 — Expand location autocomplete to cover all locations (street addresses + POIs) — **Bolt-On**. Decisions captured (10/10) on 2026-05-06; split into FEAT-011a (scaffolding + addresses tier) and FEAT-011b (POI tier).
  - FEAT-011a — Scaffolding + addresses tier. Ready to implement.
  - FEAT-011b — POI tier (additive on 011a's scaffolding). Ready to implement after 011a ships.
- ~~FEAT-012 — Mobile UI polish to match desktop's editorial refinement — **Bolt-On**.~~ ✅ **Resolved 2026-05-05.** See [docs/archive/RESOLVED_HISTORY.md](archive/RESOLVED_HISTORY.md).
- FEAT-013 — Curated Chicago Public Library tier in autocomplete — **Bolt-On**. Scoped, ready to implement after FEAT-011a ships.
- FEAT-014 — Fallback-learning cache (persistent + index-promotion) — **Bolt-On**. Scoping stub; ready to revisit after FEAT-011a accumulates production traffic data.
- FEAT-015 — Bus-stop platform-level disambiguation in autocomplete — **Bolt-On**. Scoping stub; ready to revisit after FEAT-011 ships.
- FEAT-017 — Remove redundant `line_code` edge attribute from transit graph — **Bolt-On**. Scoping stub; `line_code` is always identical to `route_id` on every edge. Audit consumers and remove the duplicate attribute to trim ~1–2 MB from the in-memory transit graph.

---

## Chunked Implementation Plans

---

## Feature Monetization --- House Ads (overall Phase 7, sub-phase 1)

### Overview

Adds a house ad component to partially offset Railway hosting costs without compromising the Heritage Organic UI. The approach is deliberately conservative: house ads only in Phase 1 — no external ad scripts, no third-party cookies, no layout disruption. Direct local sponsorships are the primary Phase 2 play once DAU supports it; CPM networks (EthicalAds, Carbon Ads) are treated as fallback fill rather than a primary revenue source, because the app's hyperlocal Chicago commuter audience is a poor match for those networks' developer-focused advertiser pool. Google AdSense and other programmatic display networks are explicitly avoided — auto-placed display ads carry a high risk of clashing with the cream/charcoal design and hurting retention.

**Target:** ~200 DAU × 2 searches/day = ~12k monthly impressions. Realistic Phase 1 revenue is **~$5/month** from affiliate conversions; the primary value in Phase 1 is building the slot, proving it doesn't hurt UX, and laying groundwork for the higher-revenue direct-sponsorship play once traffic grows. See **Revenue Projections & Post-Phase-1 Roadmap** below for the full DAU-keyed progression.

**Why it matters:** The app has real operational costs. The house ad is the minimal intervention that keeps the interface intact while creating a revenue path.

**Type: Bolt-On** --- frontend-only addition; no backend changes.

**Status:** In progress — Chunk 1 (house ad component) shipped 2026-05-05 behind `VITE_HOUSE_AD_ENABLED` (default `false`). Phase 2/2b/3 work (direct sponsorships, Chicago-specific affiliates, EthicalAds fallback) remains, gated on DAU growth.

**Prerequisites:**

- Railway + Vercel deployment live and stable (Phase 6 complete).

---

### Scoping decisions

1. **Ad provider — phased approach.**
   - **Phase 1 (now, ~200 DAU):** House ads only — affiliate links to commuter products. A static `<a>` tag — no external scripts, no third-party cookies, fully styled to the Heritage Organic system. Affiliate URL and copy controlled via Vercel env vars so they can be swapped without a redeploy.
   - **Phase 2 (~500+ DAU):** **Direct local sponsorships, sold by hand.** Same `AdSlot` component, swap copy monthly. Target Chicago coffee shops, breweries, bookstores, neighborhood restaurants, and independent retailers near major stations (Logan Square, Pilsen, Andersonville, Hyde Park). Pricing: $50–$200/month flat-rate per sponsor. This is the only model where the app's small, hyperlocal audience is a feature rather than a discount, and it preserves the editorial voice. Stack with a tip-jar link (Buy Me a Coffee or similar) below the slot — non-competing.
   - **Phase 2b (~1,500+ DAU):** Add Chicago-specific affiliate partnerships beyond Amazon — Divvy/Lyft bike-share referrals (if/when offered), CTAGifts.com, Block Club Chicago / Choose Chicago subscriptions. Conversion rates run 3–5× generic Amazon links because the audience match is exact.
   - **Phase 3 (~50k+ monthly pageviews):** Reapply to **EthicalAds** as a fallback fill for unsold direct-sponsor inventory. Their text-only units are the only network creatives that can be styled to coexist with the Heritage palette without screaming "ad." Realistic CPM for a non-developer audience is $0.50–$1.50, so this is supplementary, not primary. **Carbon Ads** is invite-only and almost certainly will not accept a non-developer-audience publisher — do not plan around it.
   - **Programmatic display networks (AdSense / Mediavine / Raptive / Ezoic):** Permanently deferred. Auto-placement guarantees creative clash with the Heritage Organic visual language. Revisit only if the design system itself is being rethought.

2. **Placement.** Single slot at the bottom of the results panel (below the last route card), so it appears naturally as users scroll through recommendations. Not in the header, not blocking the route search form. Do not render on the empty/loading state — showing an ad when the page has no content creates a poor first impression.

3. **Loading order.** House ad is a static `<a>` tag — no async loading concern. Direct local sponsorships in Phase 2 reuse the same static-`<a>` mechanism, so loading order remains a non-issue. If EthicalAds is enabled in Phase 3, load its script after the main transit data fetch completes and results are rendered.

4. **Analytics.** No heavy analytics. A simple click-through counter can be added later as a lightweight Railway route (POST /house-ad-click) — defer until traffic warrants it.

5. **Privacy.** House ads have no cookie/fingerprinting concerns. Direct local sponsorships in Phase 2 are also cookie-free (still a static `<a>`). If EthicalAds is enabled in Phase 3, add a brief footer disclosure ("This app uses EthicalAds to display ads") for US-only audiences; add a full consent banner only if EU traffic becomes significant.

6. **Ad dimensions.** House ad is a flex-row banner that fills the panel width naturally. No hardcoded IAB sizes.

7. **Tasteful sponsor card principles** *(applies to Phase 2 direct sponsorships and forward).* These are non-negotiables for any sponsor placed in the slot, alongside the styling and FTC-disclosure rules already captured above:
   - **One sponsor at a time.** No carousel, no rotation within a session, no programmatic auction. The slot shows a single sponsor for the contracted period (typically one month), then is swapped manually.
   - **No animation, no autoplay, no flashing, no GIF.** If a sponsor's creative requires motion to land, they're not the right sponsor for this slot — decline and refund rather than degrade the page.
   - **Editorial tip voice, not ad copy.** Copy reads like a one-line recommendation written by the maintainer, e.g. *"Stop at Bow Truss on the way home from Damen — open until 8pm, two blocks from the Blue Line."* Not *"Bow Truss Coffee — Best Coffee in Chicago! Click here!"* The maintainer rewrites or refuses copy that doesn't fit the voice; this is part of the value the sponsor is buying.
   - **Maintainer veto on sponsor fit.** Even if a sponsor pays, the maintainer reserves the right to decline based on values misalignment (predatory businesses, design clash, anything that would feel wrong to recommend to a friend). This veto is structural, not occasional — it is what protects the slot's credibility, which is the only reason the slot is worth anything to a sponsor in the first place.
   - **Hyperlocal relevance preferred.** Sponsors near specific stations the audience uses outperform generic citywide sponsors, because the recommendation reads as situated rather than broadcast.
   - **No tracking pixels or third-party scripts**, ever. A click-through count is the only telemetry. Sponsors who require their own pixel are politely declined; this is a hard line, not a negotiation point.

---

### Chunk 1 --- House ad component ✅ Shipped 2026-05-05

**Shipped:**

- `AdSlot` defined inline at the top of [frontend/src/App.jsx](../frontend/src/App.jsx); reads `HOUSE_AD_ENABLED` / `HOUSE_AD_URL` / `HOUSE_AD_TEXT` from [frontend/src/constants.js](../frontend/src/constants.js). Mounted inside the `result.routes.length > 0` section after the route map and before `</section>`, gated on `!tripActive`. The rendered `<a>` carries `target="_blank"` and `rel="sponsored noopener noreferrer"` and a "SPONSORED" caps kicker (FTC affiliate-link guidance).
- New stylesheet [frontend/src/styles/house-ad.css](../frontend/src/styles/house-ad.css) (registered in `App.css`): cream `--paper` background, `--hairline` top divider, italic `--serif` body so the slot reads as a maintainer-voice tip rather than a foreign element. No animation, no shadow, no accent fill.
- New translation key `ad_sponsored_kicker` in [frontend/public/locales/en/translation.json](../frontend/public/locales/en/translation.json), backfilled into all 22 existing locales. Ad copy itself is intentionally not translated (affiliate URL/text are en-US per scoping decision).
- Env vars added to [frontend/.env.example](../frontend/.env.example), [frontend/.env.local](../frontend/.env.local), [frontend/.env.production](../frontend/.env.production): `VITE_HOUSE_AD_ENABLED` (default `false`), `VITE_HOUSE_AD_URL`, `VITE_HOUSE_AD_TEXT`. Vercel env-var table in `PROJECT_CONTEXT.md` updated to match.

**Outstanding:** end-to-end QA in a Vercel preview — confirm the slot inherits `--paper`, sits clear of the fixed tab bar on mobile, and Lighthouse a11y is unchanged before flipping `VITE_HOUSE_AD_ENABLED=true` in production.

---

### Chunk 1 spec (preserved for reference)

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
- **Env files to update:** [frontend/.env.example](frontend/.env.example), [frontend/.env.local](frontend/.env.local), [frontend/.env.production](frontend/.env.production). Add `VITE_HOUSE_AD_ENABLED` (default `false`), `VITE_HOUSE_AD_URL`, `VITE_HOUSE_AD_TEXT`. Read with `import.meta.env.VITE_*` (mirror the pattern at [frontend/src/MapView.jsx:18](frontend/src/MapView.jsx#L18)).
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

**Product categories & examples:**

- **Safety & Tech:** Anker 313 Power Bank (PowerCore 10K); Skullcandy Fat Stash 2; Shokz OpenDots ONE; Apple AirTag / Tile Mate.
- **Weather-proofing:** Repel Windproof Travel Umbrella; Sorel Emelie III; Hunter Commando Boots; North Face Etip Gloves.
- **Commuter kit:** Nordace Siena; Travelon Anti-Theft Heritage; Zojirushi Stainless Steel Mug; CTA-themed gear (CTAGifts.com).

**Top 2026 commuter tech comparison:**

| Item | Top Pick | Key Benefit |
| :--- | :--- | :--- |
| **Noise Canceling** | Sony WH-1000XM6 | Best-in-class for blocking "L" screeching. |
| **Safety Audio** | Shokz OpenDots ONE | Hear "Doors Closing" announcements clearly. |
| **Power** | Nestout 15000mAh | Rugged and drop-proof for city sidewalks. |
| **Reading** | Kindle Paperwhite | Waterproof (great for rainy platforms). |

**Copy tips:** mention how items solve specific Chicago pain points (e.g., surviving transfers at Clark/Lake, windy Blue Line platforms).

---

### Revenue Projections & Post-Phase-1 Roadmap

#### Phase 1 baseline (house affiliate, ~12k monthly impressions)

Funnel math at current target traffic (~200 DAU × 2 searches/day):

| Stage | Assumed range | Result |
| :--- | :--- | :--- |
| Impressions | — | 12,000 (planning ceiling; actual is lower since the slot is hidden during active trips and on empty states) |
| CTR | 0.3% – 1.0% | 36 – 120 clicks |
| Affiliate conversion | 3% – 8% (Amazon Associates, 24h cookie) | 1 – 10 orders |
| Avg. order value | $25 – $80 | — |
| Commission rate | ~3% electronics / ~4.5% apparel — blend ~3.5% | $0.88 – $3.60/order |

- **Conservative:** ~$1–$3/month
- **Realistic mid-case** (0.5% CTR, 5% conversion, $40 AOV): **~$5/month** (~$60/yr)
- **Optimistic:** ~$25–$40/month

**Risks specific to Phase 1:** Amazon Associates requires 3 qualifying sales in 180 days or the account is closed — at the conservative end, account viability is itself a risk. Expect the tracker described in scoping decision #4 to be needed before Phase 2 begins, so direct-sponsor pitches have hard CTR data to quote.

#### Why CPM networks are a poor primary fit at any DAU

| Network | Headline CPM | Realistic CPM (this app) | Verdict |
| :--- | :--- | :--- | :--- |
| EthicalAds | $2.50 – $5.00 (dev audiences) | $0.50 – $1.50 (non-dev audience, lots of unsold house-fill) | Fallback fill only |
| Carbon Ads | $3 – $5 EPM | N/A — invite-only, rejects non-developer audiences | Do not plan around |
| AdSense / Mediavine / Raptive | Varies | Aesthetic loss outweighs revenue at any DAU | Permanently deferred |

Both EthicalAds and Carbon Ads price inventory based on advertiser demand for **developers**. CTA riders aren't who SaaS/dev-tool advertisers pay premium CPMs to reach. Even at 50k+ pageviews, EthicalAds tops out around $30–50/month for this audience — useful as fill, not as a revenue strategy.

#### DAU-keyed revenue progression

| DAU | Recommended approach | Realistic monthly |
| :--- | :--- | :--- |
| ~200 (now) | Phase 1 house affiliate as scoped | ~$5 |
| ~500 | Add tip jar; pitch 1–2 local sponsors directly | ~$50–$150 |
| ~1,500 | Rotate 2–3 local sponsors monthly; layer in Chicago-specific affiliates; reapply to EthicalAds as fallback fill | ~$200–$500 |
| ~5,000+ | Sell slot via a small-pub broker (BuySellAds direct, not Carbon); consider a second slot on the route detail screen | ~$500–$1,500 |

The highest-revenue *and* best-fit path is **direct local sponsorships sold by hand** — it requires sales effort the networks don't, but it's the only model where the small Chicago-specific audience is a feature rather than a discount. Networks should remain a fallback for unsold inventory, never the primary play.

#### What stays the same across all phases

- **Single slot, end of results column, hidden during active trips** — placement constraints from scoping decision #2 carry through every phase. If a second slot is added at ~5k DAU, it goes on the route detail screen, not the home view.
- **No third-party cookies / no fingerprinting** until at least Phase 3, and only if EthicalAds is enabled. EU consent banner stays deferred unless EU traffic becomes significant.
- **Heritage Organic styling is non-negotiable.** Any sponsor or network unit that cannot be made to read as "part of the editorial column" gets rejected, regardless of CPM.

## Consideration — Migrate MapView to react-map-gl/maplibre

### Context

During the On-Map Symbols implementation (2026-04-30), we chose **Option A** for marker integration: raw `maplibregl.Marker` + `ReactDOM.createRoot`, keeping the existing imperative MapLibre GL JS approach in `MapView.jsx`. The three editorial markers (§ origin, ✦ destination, ➤ live position) are now proper React SVG components mounted this way — see Feature MapMarkers in `FEATURE_HISTORY.md`.

`react-map-gl/maplibre` was considered but deferred because:

- The existing imperative approach is already well-managed (tracked layer/source IDs, `clearRouteLayers`, solid `useEffect` cleanup)
- The `setTimeout(0)` StrictMode fix, interaction lock system, and style error handler all work correctly and would need careful re-porting
- No user-facing correctness benefit — purely a developer ergonomics improvement

### When to reconsider

Migrate to `react-map-gl/maplibre` if any of the following arise:

- A new map feature requires complex layer/source lifecycle that the hook approach struggles with (e.g., dynamic data-driven layer composition, user-toggleable overlays, multi-source raster layers)
- Layer or source leaks appear in production (layers not cleaning up between route changes)
- The `useRouteLayers` / `useMapMarker` hooks themselves become hard to follow as more map features are added

### What migration would involve (post-2026-05-03 refactor)

1. Replace `new maplibregl.Map(...)` init block in MapView with `<Map>` component from `react-map-gl/maplibre`
2. Re-port the `setTimeout(0)` StrictMode WebGL fix (may not be needed — check react-map-gl version)
3. Rewrite [useRouteLayers.js](../frontend/src/hooks/useRouteLayers.js) to render `<Source>`/`<Layer>` JSX children instead of imperative `addSource`/`addLayer`. The hook's external API can stay similar; the internals become declarative
4. Rewrite [useMapMarker.jsx](../frontend/src/hooks/useMapMarker.jsx) to wrap react-map-gl's `<Marker>`. Origin/Destination consumers shouldn't need changes. The live-position marker's imperative `mountMarker`/`removeMarker` exports either become unnecessary (if react-map-gl handles synchronous prop updates differently) or get retained as a manual ref into the marker DOM
5. Re-port interaction lock system (`scrollZoom.disable()` etc.) via `<Map>` event handlers or `ref`
6. Re-port style error handling (`map.on("error", ...)`) via `<Map onError={...}>` prop

### Evaluation — 2026-05-03 (defer)

Re-evaluated against the trigger list above. **Outcome: defer, no triggers have fired.**

- **Trigger 1 (complex lifecycle):** Not fired. Heritage markers, walking-leg path types, and ItinerarySpine all shipped without strain on the imperative approach.
- **Trigger 2 (leaks in production):** Not fired. `clearRouteLayers` with try/catch guards is holding (since the refactor, this lives in [useRouteLayers.js](../frontend/src/hooks/useRouteLayers.js); at time of evaluation it was inline at MapView.jsx:92–100).
- **Trigger 3 (`_trackSource`/`_trackLayer` hard to follow):** Borderline at time of evaluation — MapView was 679 lines / 5 useEffects, with ~20 lines of tracking bookkeeping. The post-evaluation hook extraction (see "Cheaper interim path" below) addressed this directly: bookkeeping is now encapsulated in `useRouteLayers`, MapView is 427 lines.

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

## Consideration — Playwright E2E suite for maplibre + geolocation paths

### Context

The 2026-05-04 testing expansion (see [archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md) for the test-suite buildout) brought the project from 218 to 651 tests across backend (393) and frontend (258) layers. Coverage is now strong everywhere a pure-logic / mocked-IO test pays back: GTFS parsing, graph construction, CTA client response handling, all 15 React components without map dependencies, all utils, and 4 of 7 hooks.

What remains uncovered is the slice that genuinely needs a real browser — maplibre WebGL rendering, geolocation, service worker, and the App.jsx orchestration that wires them together:

- **`MapView.jsx`** (427 lines) — maplibre lifecycle, layer add/remove, fitBounds/flyTo, leg muting.
- **`components/markers/*.jsx`** (3 files) — DestinationMarker, LivePositionMarker, OriginMarker — render via maplibre's marker portal.
- **`hooks/useMapMarker.jsx`, `useRouteLayers.js`** — direct maplibre Map manipulation.
- **`hooks/useTripTracker.js`** — wraps `navigator.geolocation.watchPosition`, off-route detection, and live map layer updates.
- **`App.jsx`** — top-level state machine, i18n bootstrapping, route between home/map/alerts/saved tabs.

Unit-testing these would require ~80–120 lines of maplibre mock per file. The mocks would test the mocks, not the code. Playwright with a real Chromium and stubbed geolocation is the right tool — it also subsumes the "MapView smoke test" consideration above (Playwright would catch every regression that mocked smoke test was scoped for, plus actual WebGL output, plus interaction lock, plus geolocation-driven flows that no unit test can reach).

### When to build it

Build the E2E suite if **any** of the following becomes true:

1. **A maplibre / geolocation regression ships to prod undetected** — that's the empirical signal that manual QA has stopped catching the class of bug Playwright would.
2. **MapView migration to react-map-gl is approved** — Playwright then replaces the proposed mocked smoke test as the regression net (build the E2E suite *before* the migration starts).
3. **A second contributor joins the project** — manual QA across 23 i18n locales × 5 device classes × 3 tab states does not scale; codified golden-path coverage becomes worth its maintenance cost at that point.

Until one of these fires, the cost (~1–2 days initial setup + ongoing flake mitigation + CI runtime) outweighs the benefit for a solo project where manual QA is still tractable.

### Scope when built

- New directory: `frontend/e2e/` with one spec per user-facing flow.
- Playwright config: Chromium primary, mobile-Chromium for the small-screen geometry (the side-rail collapses below 768px).
- Stubbed externals:
  - `navigator.geolocation` via `context.grantPermissions(["geolocation"])` + `context.setGeolocation({ lat, lon })`.
  - Backend `/recommend`, `/stop-arrivals`, `/health`, `/alerts` via `page.route()` returning fixtures (reuse the JSON shapes from existing backend tests).
  - Anthropic / weather / CTA APIs are not called by Playwright — backend responses are stubbed at the `/recommend` boundary.
- Specs to land first (in priority order):
  1. **`route-search.spec.js`** — origin + destination text search → recommend response → MapView mounts → route polyline visible → arrival rows render.
  2. **`live-tracking.spec.js`** — start trip from a route → mock geolocation watchPosition → confirm `LivePositionMarker` appears, off-route detection fires when position diverges >400 m, arrival callback fires within 50 m of destination.
  3. **`tab-navigation.spec.js`** — SideRail tab switching across home/map/alerts/saved preserves state, focus order is correct, aria-current updates.
  4. **`pinned-stops.spec.js`** — pin a stop → arrivals refresh → unpin → state persists across reload via localStorage.
  5. **`shared-route.spec.js`** — load `/?from=…&to=…` URL → SharedRouteBanner appears → dismiss removes banner without losing the route.
  6. **`byok-key.spec.js`** — open settings → enter sk-ant-… key → save → trigger idle-clear (fast-forward via Playwright's `page.clock`) → confirm key removed from sessionStorage.
- Estimated effort: 1.5–2 days for initial setup + first 3 specs; +0.5 day per additional spec.
- CI integration: GitHub Actions workflow runs Playwright on PRs that touch `frontend/src/MapView.jsx`, `frontend/src/hooks/useTripTracker.js`, `frontend/src/components/markers/`, or `frontend/src/App.jsx`. Full suite runs nightly.

### Out of scope

- Visual regression / pixel-diff testing — same rationale as the mocked smoke test consideration above (high maintenance cost, low signal-to-noise on a typography-driven UI that legitimately changes often).
- Cross-browser testing beyond Chromium — Firefox/Safari add ~3× the runtime and have historically not surfaced bugs that Chromium missed for this app.
- Backend integration tests via Playwright — backend already has 393 unit + endpoint tests; running the full backend in CI for each Playwright spec would be slower without adding signal.

### Cross-reference

Supersedes the **MapView smoke test (regression net for future migration)** consideration immediately above when the E2E suite is built — Playwright's real-browser coverage is a strict superset of what the mocked smoke test would catch.

---

## Feature PaceMetraCoverage --- Pace + Metra service-area expansion

### Overview

Today the street-graph bbox covers Chicago city limits + Evanston (Purple Line). Western suburbs (Oak Park, Forest Park, Cicero, Skokie, Rosemont) and southern Chicago below ~100th St are excluded to keep the graph file size manageable. Pace (suburban bus) and Metra (commuter rail) extend across the six-county metropolitan area, but neither is currently routed by the app. When Pace and/or Metra are added to the transit graph, the walking street graph must expand correspondingly so that walk legs at Pace stops and Metra stations get accurate street-routed walk times instead of Haversine fallbacks.

**Type: Structural** --- depends on whichever transit-data feature first introduces Pace or Metra routing.

**Status:** Deferred (no transit-data work for Pace/Metra is planned yet)

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

## Standalone Features

---

### FEAT-011 --- Expand location autocomplete to cover all locations (street addresses + POIs)

**Type:** Bolt-On

**Status:** Decisions captured (10/10 as of 2026-05-06). Final consistency audit complete; entry restructured below into FEAT-011a (scaffolding + addresses tier) and FEAT-011b (POI tier) per Decision 3. Two spawned FEATs (FEAT-014 fallback-learning cache, FEAT-015 bus-stop dedupe) drafted separately.

**User story / motivation:** As a rider, I want the origin/destination autocomplete to suggest *any* location I might want to travel to or from — specific street addresses (e.g. "1234 N Milwaukee Ave"), businesses and points of interest (e.g. "Wrigley Field", "Whole Foods Lincoln Park"), and individual bus stops at named intersections — not just the curated list of train stations, neighborhoods, and deduplicated bus stop names. Today, anything outside that curated list only resolves *after* form submission via Google Geocoding, which means the user gets no inline confirmation that the place they're typing is recognized.

**Current coverage (for context):**

- `/autocomplete` ([backend/main.py:1999-2036](../backend/main.py#L1999-L2036)) returns up to 8 suggestions from a static prefix index built at startup ([backend/main.py:312-358](../backend/main.py#L312-L358)).
- Three sources, in tier order: train station names → `NEIGHBORHOOD_COORDS` keys → bus stop names (deduped by name, so multiple stops sharing a name collapse to one).
- Free-form addresses are resolvable via Google Geocoding ([backend/gtfs_loader.py:644](../backend/gtfs_loader.py#L644)) on submit, but never autocompleted.
- The `GOOGLE_MAPS_API_KEY` env var is already wired up ([backend/.env.example](../backend/.env.example)).

**Acceptance criteria (final, post-decision-walkthrough):**

After all of FEAT-011a, FEAT-011b, and FEAT-013 ship (FEAT-013 is its own entry but depends on FEAT-011a's scaffolding):

- Tier-priority order in the autocomplete dropdown is: train station → neighborhood → bus stop → library → address (TIGER) → POI (OSM) → Google fallback. (Library tier ships in FEAT-013; address tier in 011a; POI tier in 011b; Google fallback ships in 011a.)
- Typing partial street addresses (e.g. "1234 N Milwaukee Ave") biased to the Chicago metro returns inline address suggestions sourced from US Census TIGER/Line, with interpolated coordinates. (FEAT-011a)
- Typing well-known Chicago POIs (e.g. "Wrigley Field", "Art Institute", "Whole Foods Lincoln Park") returns matching inline suggestions sourced from a filtered Geofabrik OSM extract. (FEAT-011b)
- Existing tiers (train stations, neighborhoods, bus stops) continue to rank above all new tiers — riders looking for a station should not have to scroll past a coffee shop with the same name.
- Suggestion `type` badges in the dropdown extend to cover the new categories — `address`, `poi`, `library` — each with a dedicated translated string and consistent badge styling. See [frontend/src/components/LocationInput.jsx:222-225](../frontend/src/components/LocationInput.jsx#L222-L225).
- Each tier is capped at `AUTOCOMPLETE_PER_TIER_CAP` entries (default `3`) before lower tiers are pulled in, ensuring lower tiers are not starved. Within-tier ranking is prefix-position → length-asc → alphabetical (Decision 7.A).
- Cross-tier dedupe: when the same canonical entity appears in two tiers (matched by normalized name OR coords within 50m), the higher-priority tier wins. (Decision 7.C)
- The Google fallback path is invoked **only when** prefix length ≥ `AUTOCOMPLETE_FALLBACK_MIN_PREFIX_LEN` (default `4`) AND the local index returned fewer than `AUTOCOMPLETE_FALLBACK_LOCAL_THRESHOLD` matches (default `3`). (Decision 2)
- A hard daily cap (`AUTOCOMPLETE_FALLBACK_DAILY_CAP`, default `1000`) bounds Google fallback spend; on cap-hit the endpoint silently degrades to local-only for the rest of the UTC day. (Decision 2)
- The existing geocode rate-limit bucket continues to gate `/autocomplete` traffic; the Google fallback path is additionally gated by `AUTOCOMPLETE_FALLBACK_PER_IP_RATE`. No new bypass paths. (Decision 2)
- Frontend generates an opaque `session_id` UUID on `LocationInput` focus and submits it with each `/autocomplete` request and on submit. Backend translates this into a Google session token internally so the entire typing-plus-selection session bills as one billable unit. (Decision 4)
- Suggestion shape is uniform: `{ display, secondary, type, value, coords }`. Local-tier suggestions include `coords` inline and resolve with zero round-trips on submit. Google fallback suggestions carry `place_id` in `value` and resolve via a `/resolve` endpoint that calls Place Details with the cached session token. (Decision 5)
- Server-side caches: `/autocomplete` Google fallback responses cached LRU by `(normalized_prefix, location_bias)` with 1h TTL (`AUTOCOMPLETE_GOOGLE_CACHE_TTL_SEC`, default `3600`; size cap `AUTOCOMPLETE_GOOGLE_CACHE_MAX_ENTRIES`, default `10000`); Place Details responses cached LRU by `place_id` with indefinite-within-process-lifetime TTL (`RESOLVE_CACHE_MAX_ENTRIES`, default `5000`). (Decision 6)
- Failure modes: Google `/autocomplete` errors fall back to stale-cache-then-local-only silently; Google `/resolve` errors degrade through `geocode_google()` and only surface a user-facing error if both paths fail; sustained Google failures trip a circuit breaker (`AUTOCOMPLETE_FALLBACK_BREAKER_THRESHOLD`=5 consecutive failures, `AUTOCOMPLETE_FALLBACK_BREAKER_COOLDOWN_SEC`=300). (Decision 8)
- Privacy: `docs/PRIVACY.md` is updated to (a) correct the existing inaccurate "no third-party processor" claim and (b) document the new Google Places fallback flow specifically. (Decision 9)
- A global env-var opt-out (`AUTOCOMPLETE_FALLBACK_ENABLED`, default `true`) disables all Google fallback paths when set to `false`. (Decision 9)
- No API keys are exposed to the frontend — frontend hits only `/autocomplete` and `/resolve`.
- The build script `scripts/build_geo_index.py` produces the static prefix-index artifact from TIGER + OSM; runs as a monthly cron, manually triggerable. (Decision 6.A)
- Bus-stop tier behavior is **unchanged** by FEAT-011 — the existing dedupe-by-name pass is preserved. Platform-level disambiguation is tracked separately as FEAT-015. (Decision 10)

**Scope split: FEAT-011a vs FEAT-011b**

The single FEAT-011 work is split into two sequential PRs per Decision 3.

*FEAT-011a — Scaffolding + Addresses tier (ships first):*
- New `scripts/build_geo_index.py` with TIGER fetch + processing (and CPL refresh subcommand stub for FEAT-013)
- New `backend/places.py` (or similar) holding the Google Places + Place Details client, session-token map, autocomplete cache, resolution cache, circuit breaker
- Backend index loader extended with a generic N-tier registration pattern; the **TIGER address tier** is registered as the first new tier
- New `/autocomplete` merge logic, fallback-trigger evaluation, per-tier cap, dedupe rules
- New `/resolve` endpoint
- All 11 env vars added to `backend/.env.example`
- Frontend `LocationInput.jsx` polymorphic suggestion handling (inline coords vs `/resolve` round-trip), `session_id` generation
- Frontend `App.css` badge styling for `address` (plus shared base styles for future badges)
- `frontend/public/locales/*/translation.json` — `address` badge string across all 27 locales
- `docs/PRIVACY.md` — Decision 9 updates
- Tests: TIGER ingestion, merge ranking, fallback-trigger conditions, daily-cap behavior, breaker state transitions, `/resolve` polymorphic dispatch, cache LRU behavior, env-var disable

*FEAT-011b — POI tier (ships after 011a, depends on its scaffolding):*
- `scripts/build_geo_index.py` extended with OSM Geofabrik extract fetch + tag filtering + ranking
- Backend index loader: register the **OSM POI tier** on the existing scaffolding (additive)
- Frontend `App.css` badge styling for `poi`
- `frontend/public/locales/*/translation.json` — `poi` badge string across all 27 locales
- Tests: OSM ingestion, POI ranking heuristic, library-vs-POI dedupe (Decision 7.C)
- No new env vars, no scaffolding changes, no fallback-policy changes

**Files likely touched (consolidated, by FEAT half):**

*FEAT-011a:*
- `backend/main.py` — index loader generalization, `/autocomplete` merge + fallback policy, new `/resolve` endpoint, env-var reads, session-token map, breaker state
- `backend/places.py` (new) — Google Places client, autocomplete cache, Place Details cache, circuit breaker
- `scripts/build_geo_index.py` (new) — TIGER fetch + processing; CPL refresh subcommand stub (for FEAT-013)
- `backend/.env.example` — 11 new env vars
- `backend/static_data/geo_index.bin` (new artifact path; format TBD during implementation — static fixture, must NOT live under `backend/data/` because Railway overlays that path with the persistent analytics volume)
- `backend/tests/` — extensive new tests
- `frontend/src/components/LocationInput.jsx` — `session_id` generation, polymorphic resolution
- `frontend/src/App.css` — `address` badge + shared base
- `frontend/public/locales/*/translation.json` — `autocomplete.badge.address` across 27 locales
- `docs/PRIVACY.md` — Decision 9 updates

*FEAT-011b:*
- `backend/main.py` — POI tier registration (additive)
- `backend/places.py` or new `backend/poi.py` — OSM tag filter, ranking heuristic
- `scripts/build_geo_index.py` — OSM Geofabrik download + processing
- `backend/tests/` — POI-specific tests
- `frontend/src/App.css` — `poi` badge
- `frontend/public/locales/*/translation.json` — `autocomplete.badge.poi` across 27 locales

**Decisions captured (in progress — sequence walked via `/resolve-item`, latest first):**

1. **Provider choice (Q1) → Hybrid: self-built static index + Google fallback.** *Captured 2026-05-06.*
   - **Primary path:** extend the existing static prefix index ([backend/main.py:312-358](../backend/main.py#L312-L358)) with two new tiers built from free, license-clean datasets:
     - **Addresses tier** — US Census **TIGER/Line** address-range data for Cook County (and likely the surrounding collar counties to match the routing service area). Provides street segments with address ranges, supporting interpolated lat/lng for arbitrary numbered addresses.
     - **POI tier** — filtered Chicago-metro **OpenStreetMap** extract from Geofabrik, restricted to relevant tags (`amenity`, `shop`, `tourism`, `leisure`, `office`, `landmark`, etc.), ranked by tag importance.
   - Both new tiers are loaded into memory at backend startup, served from the same prefix-index pattern as existing tiers. A new `scripts/build_geo_index.py` downloads + processes the source data into a compact on-disk artifact; refresh cadence is monthly automated cron (settled in Decision 6.A).
   - **Fallback path:** Google Places Autocomplete (New) is invoked **only** when the local index returns no/insufficient suggestions for a given prefix. Reuses the existing `GOOGLE_MAPS_API_KEY` already wired up in [backend/.env.example](../backend/.env.example).
   - **Rationale:** zero variable cost for the dominant query shape (Chicago landmarks, chains, intersections, addresses), with Google preserving long-tail business coverage. Architecturally consistent with the existing static-index pattern — no new running service, no new operational surface area. Self-hosted geocoders (Nominatim, Photon) were considered and rejected because they introduce a sidecar process the rest of the codebase has deliberately avoided.
   - **Cascading effects on later decisions:**
     - Q2 (cost) reshapes into "fallback policy / cost ceiling" — what threshold triggers Google, what's the spend cap.
     - Q3 (session tokens) still applies to the Google fallback path only.
     - Q5 (resolution path) now varies by tier: local tiers can carry coords directly; Google fallback may carry `place_id`.
     - Q8 (privacy) narrows substantially — most typing never leaves the backend.
     - Q9 (failure mode) only matters on the fallback path; local index is always available.
     - Q10 (split) becomes easier to bundle since both new tiers share one index.
   - **Spawned follow-up:** **FEAT-014** ("Fallback-learning cache") — when Google returns a result, store it permanently and promote it into the static index so subsequent searches hit the local path. Per maintainer direction this is tracked as a feature, not an optimization. Drafted as a scoping stub on 2026-05-06.

2. **Fallback policy & cost ceiling (Q2, reshaped) → Combined trigger (D+B) + combined ceiling (F+H), all values driven by env vars.** *Captured 2026-05-06.*
   - **Trigger conditions** — Google Places Autocomplete is invoked **only when ALL of** the following hold:
     - Prefix length ≥ `AUTOCOMPLETE_FALLBACK_MIN_PREFIX_LEN` characters (default `4`).
     - Local index returned fewer than `AUTOCOMPLETE_FALLBACK_LOCAL_THRESHOLD` suggestions (default `3`).
   - **Spend ceiling** — two layers, both required:
     - **Hard daily cap:** `AUTOCOMPLETE_FALLBACK_DAILY_CAP` Google fallback calls per UTC day (default `1000`). When the cap is reached, the autocomplete endpoint silently degrades to local-only for the rest of the day. The cap event is logged so the maintainer can adjust.
     - **Per-IP rate limit:** the existing geocode rate-limit bucket is extended to gate the Google fallback path of `/autocomplete`. New env var `AUTOCOMPLETE_FALLBACK_PER_IP_RATE` (default — match the existing geocode bucket policy) allows independent tuning if needed.
   - **All four values are env-var-driven** so they can be tuned in production without a code deploy. Defaults above are the chosen starting points; document them in [backend/.env.example](../backend/.env.example) when implementing.
   - **Rationale:** min-prefix-length cuts the dominant "cheap" wasted-call category (1–3 char prefixes). The "<3 local matches" threshold preserves UX when local already shows good options. The hard daily cap is the non-negotiable circuit breaker against bugs/abuse; per-IP rate limiting bounds single-actor cost. Tunable env vars mean the maintainer can ratchet defaults up or down based on observed traffic without redeploying.
   - **No cascading effects on later decisions** — these tunables apply at the integration layer.

3. **Split or not (Q10) → Split into FEAT-011a (scaffolding + addresses tier) → FEAT-011b (POI tier).** *Captured 2026-05-06.*
   - **FEAT-011a scope:** the build pipeline (`scripts/build_geo_index.py` or similar), the index loader changes that accept N tiers via a generic registration pattern, the new `/autocomplete` merge logic + Google fallback policy + 4 env vars from Decision 2, the frontend type-handling for new suggestion types, the i18n badge keys for `address` (and `library` and `poi` slots reserved), and the **TIGER addresses tier** itself.
   - **FEAT-011b scope:** the OSM POI extract processing, tag-filtering rules, ranking heuristic, and registration as a new tier on the existing scaffolding. Strictly additive — no scaffolding or fallback-policy changes expected.
   - **Rationale:** TIGER processing is more deterministic than OSM POI tag judgment (cleaner schema, less ranking design); building the scaffolding under controlled conditions de-risks 011b. The intermediate state (after 011a, before 011b) is a strict superset of today's behavior — train + neighborhood + stop + addresses + Google fallback for unknowns — with no regressions. Splitting also matches the project's preferred tight PR cadence.
   - **Operational benefit:** 011a will produce real autocomplete traffic data the maintainer can use to tune the Decision 2 env-var defaults (especially the daily cap) before 011b ships and changes traffic patterns.
   - **No cascading effects on later decisions** — remaining decisions apply equally to both halves.

4. **Session tokens for Google fallback (Q3) → Yes; opaque frontend session_id, backend manages Google session tokens internally.** *Captured 2026-05-06.*
   - **Frontend behavior:** generates `session_id = crypto.randomUUID()` on `LocationInput` focus; resets on blur-then-refocus. Sends as a query param on each `/autocomplete` request and on form submit. Frontend has zero knowledge that this maps to a Google session token.
   - **Backend behavior:** maintains an in-memory TTL'd map `session_id → (google_session_token, expires_at)` with a 3-minute TTL matching Google's documented session lifetime. On Google fallback: looks up an existing token for the `session_id` or mints a new UUID; reuses across all fallback calls within the session. On submit (resolution): if the picked suggestion is a Google fallback result, the cached `google_session_token` is included on the Place Details call to close the session as a single billable unit. Periodic sweep evicts expired entries.
   - **Edge cases:**
     - If a `session_id` reaches submit time but Google was never called (rider's pick came from a local tier), no token was ever minted and no Place Details call is made. Zero cost.
     - If the cached token has expired (rider sat idle >3 min between typing and submit), the backend mints a fresh token for the resolution call and accepts that this single resolved selection is billed as its own session. Logs a metric.
   - **Rationale:** session tokens are ~10× cheaper on resolved long-tail sessions than per-request billing (8–12 keystrokes worth of Autocomplete + 1 Place Details, all bundled into one billable unit at ~$0.003 vs ~$0.028 per session). Decision 2's daily cap of 1000 fallback calls is sized assuming session tokens — without them, the same dollar budget covers ~10× fewer rider sessions. Frontend opacity (option C over option A) preserves the hybrid abstraction so a future provider swap doesn't require frontend changes.
   - **No cascading effects on later decisions** — Decision 5 (resolution path) is independently shaped by tier semantics.

5. **Resolution path (Q5) → Polymorphic suggestions: local tiers carry inline `coords`; Google fallback carries `place_id` only and resolves via a `/resolve` round-trip on submit.** *Captured 2026-05-06.*
   - **Suggestion shape (uniform across tiers):** `{ display, secondary, type, value, coords }`. `coords` is `{ lat, lng }` for local-tier suggestions and `null` for Google fallback. `value` is opaque to the frontend — a stable local ID for local tiers, a Google `place_id` for Google fallback. `type` drives both the badge UI and the resolution dispatch.
   - **Frontend submit logic:** `const coords = picked.coords ?? await resolveSelection(picked, sessionId);` — single line, two branches, no provider awareness.
   - **Backend `/resolve` endpoint:** dispatches on `type`. `google_fallback` → calls Place Details with the session token from Decision 4 to close the session as a single billable unit, returns coords. Other types are not expected to reach `/resolve` (they short-circuit on the frontend); reaching it is treated as a defensive error.
   - **Free-text submits** (rider types and hits enter without picking a suggestion) are unchanged from today and continue to flow through the existing `geocode_google` path in [backend/gtfs_loader.py:644](../backend/gtfs_loader.py#L644). Different code path; not affected by this decision.
   - **Rationale:** A is the only option consistent with the architecture wins from earlier decisions. Pre-resolving Google suggestions on the typing path (option B) would defeat session tokens (~$0.005 × N suggestions × N keystrokes); routing local resolutions through the backend (option C) would tax every submit with an unnecessary round-trip and waste the in-memory cost benefit of Decision 1. A keeps the common case (local picks) instant and zero-cost, and pushes resolution work to the only path where it's needed.
   - **No cascading effects on later decisions** — Decision 6 (cache policy) builds on this shape but does not modify it.

6. **Cache & refresh policy (Q4) → Three-surface policy: monthly build cron (A1), 1h server-side autocomplete LRU (B2), in-memory indefinite Place Details LRU (C2). All persistence-grade caching deferred to the spawned fallback-learning FEAT.** *Captured 2026-05-06.*
   - **6.A Build artifact refresh cadence (A1):** monthly automated cron rebuild of TIGER + OSM into the static index artifact via `scripts/build_geo_index.py`; CPL refresh ad-hoc only (per FEAT-013, run when notified of a branch change). Source-data churn rates make monthly the right granularity — TIGER updates annually, OSM POI churn between months is dominated by long-tail businesses Google fallback already covers, CPL changes every few years.
   - **6.B Google autocomplete response cache (B2):** in-memory LRU keyed by `(normalized_prefix, location_bias)`, TTL 1h. Env-tunable: `AUTOCOMPLETE_GOOGLE_CACHE_TTL_SEC` (default `3600`), `AUTOCOMPLETE_GOOGLE_CACHE_MAX_ENTRIES` (default `10000`). Within-rider re-typing gets free hits; popular prefixes accumulate cross-session benefit; 1h bounds the stale-data window. Memory ceiling is ~1MB at default cap.
   - **6.C Place Details resolution cache (C2):** in-memory LRU keyed by Google `place_id`, storing `(lat, lng, display_name, formatted_address)`. Indefinite TTL within process lifetime; cleared on restart. Env-tunable: `RESOLVE_CACHE_MAX_ENTRIES` (default `5000`). Persistent storage (SQLite / on-disk JSON) is **explicitly deferred** to the spawned fallback-learning FEAT, which is the right home for the storage decisions and the index-promotion mechanics.
   - **In-memory index lifetime (not a real decision, noted for completeness):** the loaded prefix index lives for the lifetime of the backend process. Rebuilding the artifact + restarting is the upgrade path; no hot reload.
   - **Rationale:** matches each cache surface's freshness need to its actual change rate. Defers all the engineering work that pulls in a persistence layer (SQLite location, deploy implications, migration story) to the spawned fallback-learning FEAT, keeping FEAT-011a's scope tight.
   - **No cascading effects on later decisions.**

7. **Ranking rules (Q7) → Within-tier: prefix-position → length-asc → alphabetical (A4). Cross-tier slots: per-tier soft cap, default 3, env-tunable (B2). Cross-tier dedupe: higher-priority tier wins, dedup key = normalized name OR coords <50m (C3). Fuzzy matching: deferred to a future FEAT (D3).** *Captured 2026-05-06.*
   - **Final priority order** (after FEAT-011a, FEAT-011b, FEAT-013 ship): train station → neighborhood → bus stop → library → address (TIGER) → POI (OSM) → Google fallback.
   - **7.A Within-tier ranking (A4):** three-key comparator — (1) prefix-position score (matches at start of name beat mid-word matches), (2) length-asc (shorter canonical names first), (3) alphabetical tiebreak. Implementable as ~10 lines on top of the existing prefix-trie.
   - **7.B Cross-tier slot allocation (B2):** tier-greedy fill from highest-priority tier, but each tier capped at `AUTOCOMPLETE_PER_TIER_CAP` entries (default `3`) before descending. Endpoint still returns up to 8 total. Guarantees lower tiers (libraries, addresses, POIs) aren't starved by an over-matching higher tier.
   - **7.C Cross-tier dedupe (C3):** when the same canonical entity appears in two tiers, the higher-priority tier wins. Dedup key fires on (a) exact normalized name match (lowercase, strip punctuation, fold whitespace), OR (b) coords proximity within 50m. Catches realistic collisions (libraries-vs-OSM, train-stations-vs-OSM) without merging genuinely different entities at the same intersection.
   - **7.D Fuzzy matching / typo tolerance (D3):** out of scope for FEAT-011. Today's prefix-exact behavior is preserved across all new tiers. Fuzzy matching is acknowledged as a desirable future improvement and would be its own FEAT (different index structure, different perf profile, different test surface).
   - **No cascading effects on later decisions.**

8. **Failure mode (Q9) → Three-scenario graceful degradation: stale-cache-then-silent-local-only on `/autocomplete` (A4→A1), two-tier graceful fallback on `/resolve` (B4), simple circuit breaker on sustained outage (C2).** *Captured 2026-05-06.*
   - **8.A `/autocomplete` failure (Google errors during typing):** on Google error or timeout, the backend first looks up the prefix in the Decision 6.B autocomplete LRU **ignoring TTL** — if a stale entry exists, serve it and log the staleness. If no cache hit, silently degrade to local-only (return whatever the local index produced). The rider sees fewer-than-expected suggestions but the existing post-submit `geocode_google` path still resolves anything they ultimately type. No user-visible error.
   - **8.B `/resolve` failure (Google errors after a Google pick was selected):** two-tier graceful degradation. (1) On Place Details error, fall back to the existing `geocode_google()` path in [backend/gtfs_loader.py:644](../backend/gtfs_loader.py#L644) using the suggestion's display string. (2) Only if `geocode_google` also fails do we surface a user-facing error. Place Details failures are usually transient and `geocode_google` is a cheap, well-tested existing path.
   - **8.C Sustained outage (circuit breaker):** simple consecutive-failure counter. After `AUTOCOMPLETE_FALLBACK_BREAKER_THRESHOLD` consecutive failures (default `5`), the breaker opens and Google fallback calls return immediately as if Google were unreachable (which routes them through 8.A's silent-degradation path). After `AUTOCOMPLETE_FALLBACK_BREAKER_COOLDOWN_SEC` (default `300`), a single probe is sent; success closes the breaker, failure doubles the cooldown (capped at e.g. 1h). Breaker state transitions are logged so the maintainer can see outage windows.
   - **Rationale:** autocomplete failures are low-stakes (post-submit catches anything); `/resolve` failures matter more because the rider has already chosen — graceful path through `geocode_google` reuses existing infrastructure. Circuit breaker prevents the daily cap from being burned on guaranteed-failed calls during sustained outages and reduces typing-path latency when Google is unavailable.
   - **No cascading effects on later decisions.**

9. **Privacy disclosure (Q8) → Document in `docs/PRIVACY.md` only (A1), specific detail level + correct existing inaccuracy (B3), global env-var opt-out (C3).** *Captured 2026-05-06.*
   - **9.A Disclosure location (A1):** updates land in `docs/PRIVACY.md` only. No in-app notice or inline indicator near the location input. Per-rider opt-out toggle (sub-decision C2) is deferred to a future polish FEAT — adds 22+ locale strings, settings-panel UI, frontend persistence, and backend cookie-honoring work that is outside this scope.
   - **9.B Detail level (B3):** the PRIVACY.md update both adds a new section disclosing the FEAT-011 Google Places fallback **and** corrects an existing inaccuracy. Concretely:
     - **Existing language to revise** ([docs/PRIVACY.md:144-145](../PRIVACY.md)): "All data is stored on the same Railway-hosted backend… No data is sent to a third-party processor." This claim is currently misleading because `geocode_google()` already forwards typed addresses on submit. Replace with accurate language that names the Google APIs and the conditions under which typed text is forwarded.
     - **New section to add** (working title: "Geocoding & autocomplete (Google Maps APIs)"): documents (a) the existing Google Geocoding flow on free-text submits, (b) the new Google Places Autocomplete (New) flow as fallback when local has <3 matches AND prefix ≥4 chars (per Decision 2), (c) the Place Details flow on Google-suggestion picks (per Decision 5). Lists what is sent (typed prefix; deployment outbound IP; opaque session UUID from Decision 4) and what is not sent (no `returnId`, no session cookie, no rider identifier). Notes that retention of this data is governed by Google's own policies; the local LRU caches (Decision 6.B, 6.C) are evicted on process restart.
   - **9.C User-facing control (C3):** new env var `AUTOCOMPLETE_FALLBACK_ENABLED` (default `true`). When set to `false`, the backend skips all Google Places fallback paths and behaves as local-index-only (riders typing exotic queries get fewer/no inline suggestions; submit-path `geocode_google` is unaffected). Useful for self-hosters with stricter privacy postures, for emergency disabling, and for testing local-only behavior in development. Per-rider opt-out (C2) is acknowledged as a worthwhile future FEAT but not in scope here.
   - **FEAT-013 (CPL libraries) note:** keeps all data local (in-repo `cpl_locations.json`, ad-hoc `--refresh-cpl` against `data.cityofchicago.org` only when manually triggered). No runtime third-party data flow. Not separately disclosed in PRIVACY.md unless FEAT-013 ever gains a runtime-fetch mode.
   - **Rationale:** correcting the existing PRIVACY.md inaccuracy is consistent with the maintainer's strong privacy posture throughout the rest of that doc. The env-var opt-out costs almost nothing to implement and gives self-hosters a real control. Per-rider toggles and inline indicators are deliberately deferred so FEAT-011a's scope stays tight.
   - **No cascading effects on later decisions.**

10. **Bus-stop dedupe (Q6) → Spawn as its own FEAT-015; FEAT-011 keeps existing bus-stop dedupe behavior unchanged.** *Captured 2026-05-06.*
    - **Decision:** the existing bus-stop tier's dedupe-by-name pass is **not modified** by FEAT-011a or FEAT-011b. New tiers (addresses, POIs, library) are added alongside the bus-stop tier without touching how it is built.
    - **Spawned:** FEAT-015 (Bus-stop platform-level disambiguation). Drafted as a thin scoping stub — the open question is whether to un-dedupe entirely, expose individual platforms via an expandable group, or some hybrid. Resolution is partly evidence-driven (depends on observed dropdown usage patterns once FEAT-011 ships a richer mix of suggestion types).
    - **Rationale:** orthogonal to the address/POI/library expansion. The original Q6 wording itself flagged this as splittable. Bundling it into FEAT-011 would re-scope a feature whose decisions are otherwise complete, and would introduce UX questions (direction badges, accessibility-tier handling, expandable-group affordance) that have no architectural overlap with FEAT-011's mission.
    - **No cascading effects on later decisions.**

**Open questions:** None. All ten original open questions have been resolved into the captured decisions above. A final consistency audit on 2026-05-06 found no contradictions across decisions and applied two cleanups: (a) renamed `GOOGLE_FALLBACK_BREAKER_*` env vars to `AUTOCOMPLETE_FALLBACK_BREAKER_*` for naming consistency with the rest of the autocomplete-fallback family, and (b) clarified that each FEAT owns its tier's i18n strings (FEAT-011a → `address`, FEAT-013 → `library`, FEAT-011b → `poi`).

**Spawned FEATs (drafted separately):**

- **FEAT-014 — Fallback-learning cache.** Persistent cross-restart cache of resolved Google place_ids, with eventual promotion of high-frequency entries into the static prefix index. Per maintainer direction, tracked as a feature, not an optimization. Depends on FEAT-011a.
- **FEAT-015 — Bus-stop platform-level disambiguation.** Open question whether to un-dedupe the bus-stop tier so each platform/direction is its own suggestion, or expose them via an expandable group. Resolution is partly evidence-driven once FEAT-011 ships.

**When to revisit:** Ready to invoke `/resolve-item FEAT-011a`. After 011a ships and a few weeks of production traffic data accumulate, invoke `/resolve-item FEAT-011b` (POI tier — strictly additive, no scaffolding changes expected). FEAT-013 (libraries) can ship in parallel with 011b. FEAT-014 and FEAT-015 are sequenced after FEAT-011a/b at the maintainer's discretion.

---

### FEAT-012 --- Mobile UI polish to match desktop's editorial refinement

**Type:** Bolt-On --- frontend-only (CSS + small component touch-ups); no backend changes.

**Status:** ✅ **Resolved 2026-05-05** via `/resolve-item FEAT-012`. Implementation summary in [docs/archive/RESOLVED_HISTORY.md](archive/RESOLVED_HISTORY.md). Lighthouse mobile baseline (decision #12) deferred to a manual run from the PR's Vercel preview — the developer environment cannot execute Lighthouse against deployed previews.

**User story / motivation:** The desktop UI is the project's signature: a Heritage Organic editorial aesthetic — serif drop-caps, hairline rules, paper-grain texture, italic/roman typographic interplay, and disciplined `var(--dur-*)` transitions. Mobile is functionally complete and uses the same design tokens, but feels noticeably less refined: most polish primitives (touch feedback, motion, safe-area awareness, intermediate-breakpoint typography) didn't propagate down. As a rider on a phone, I want the app to feel as deliberately crafted as the desktop version — not as a "responsive afterthought."

**Current state (for context):**

- Mobile breakpoint is a single `@media (max-width: 800px)` block in [frontend/src/styles/layout.css:174-261](../frontend/src/styles/layout.css#L174-L261), with smaller fragments in `form.css`, `route-cards.css`, `settings.css`, and `map.css`.
- Mobile uses screen-swap navigation: a fixed 4-tab bottom tab bar (`Home / Map / Alerts / Saved`), `display:none` on inactive panels driven by `[data-active-tab]` attribute selectors.
- Heritage Organic tokens are defined in [frontend/src/styles/tokens.css](../frontend/src/styles/tokens.css). Desktop uses these consistently; mobile partially.
- 38 `:hover` rules exist project-wide; only **2** `:active` rules. (Audit: greppable across `frontend/src/styles/*.css`.)
- Map overlay positions in [frontend/src/styles/map.css](../frontend/src/styles/map.css) use literal `14px` / `10px` values without `env(safe-area-inset-*)`.

**Audit summary — where mobile falls short of desktop:**

1. **Touch-state parity:** only 2 `:active` states vs. 38 `:hover` rules — most interactive elements give no tactile feedback on touch. `.pin-btn`, `.leg-steps-toggle`, route-card header button, share/save buttons all lack `:active`.
2. **Hardcoded values instead of design tokens:** tab bar padding is `10px 6px 4px`; tab-bar height is `56px` literal coupled into a `padding-bottom: calc(56px + ...)` elsewhere ([layout.css:196, :233](../frontend/src/styles/layout.css#L196)). Form labels hardcoded `80px` width ([form.css:21](../frontend/src/styles/form.css#L21)).
3. **Map overlays ignore mobile safe-areas:** legend, train card, compass button use literal `14px` offsets ([map.css:48, :76, :141](../frontend/src/styles/map.css#L48)) — on notched devices and 320px viewports they collide and obscure each other; no `env(safe-area-inset-*)` use.
4. **Settings sheet UX:** bottom-sheet (`align-items: flex-end`) capped at `80dvh` with the close button non-sticky — content longer than the cap creates a scroll-trap where dismissing requires scrolling back to the top ([settings.css:43-71](../frontend/src/styles/settings.css#L43)).
5. **Drop-cap sizing has a gap:** 72px at `<359px` and `<800px` but no intermediate breakpoint, so 375–767px devices (iPhone SE through iPad Mini) all use 72px and feel oversized. Desktop drops to 52px above 800px.
6. **Tab bar lacks scroll-position memory:** panels hide via `display:none`, which discards scroll position on tab re-entry. (Verify via repro before claiming.)
7. **Motion gaps on mobile:** most `:hover` micro-interactions never translate to `:active`; tab switch is a plain `display:none` swap with no fade/slide. Desktop has a panel fade+slide animation ([layout.css:131-150](../frontend/src/styles/layout.css#L131)) — mobile inherits none of it.
8. **Map button sizing:** hardcoded `10px` padding evaluating to ~32px height ([map.css:23, :151](../frontend/src/styles/map.css#L23)) — below the 44px touch-target floor used elsewhere.

All gaps are within the existing design system's vocabulary — the fix is **applying tokens consistently and propagating polish primitives mobile didn't inherit yet**, not redesigning anything.

**Scoping decisions (decisions #1–#7 are guardrails set during initial scoping; decisions #8–#14 are the seven open-question resolutions made during the second-pass review):**

1. **Single FEAT vs. chunked.** Treat as a single bolt-on. All work lives in `frontend/src/styles/*.css` plus a small handful of component touch-ups; sub-areas are independent and can land in any order. Split into chunks **only if** the diff exceeds ~600 LOC during implementation (proposed split: FEAT-012a touch-state + tokens, FEAT-012b map overlays + safe-area, FEAT-012c motion + settings sheet).
2. **Aesthetic guardrails (do not violate).** No border-radius on cards/buttons, no box-shadows, no vibrant non-palette colors, no gradient fills. Touch states must use existing tokens (paper-folio for hover-equivalent backgrounds, ink-soft for pressed states). The mobile UI must not begin to look like a generic "mobile-first" app — the editorial flatness is the brand.
3. **No new layout patterns.** Keep the screen-swap tab-bar architecture. No drawers, swipe gestures, or pull-to-refresh in this FEAT — those are separate proposals.
4. **Intermediate drop-cap breakpoint.** Add a `@media (min-width: 401px) and (max-width: 800px)` step that reduces drop-cap to ~60px (between mobile 72px and desktop 52px), keeping italic Fraunces and tightened tracking. ([route-cards.css:106-112](../frontend/src/styles/route-cards.css#L106-L112))
5. **Tab-bar height as a token.** Introduce `--tab-bar-height: 56px` in `tokens.css` and replace the existing literal usages so the calc() in `.panel-cards` no longer goes stale if the tab bar grows.
6. **Motion budget.** Reuse `--dur-quick` (120ms) and `--dur-base` (220ms) only. No new keyframes. Tab-swap fade/slide reuses the existing desktop panel transition pattern from [layout.css:131-150](../frontend/src/styles/layout.css#L131).
7. **i18n.** No new strings; this is a pure styling/state pass.
8. **Tab-swap mechanism (decided).** Unify mobile and desktop on a single panel-swap pattern: replace the mobile `display:none` rules at [layout.css:208-211](../frontend/src/styles/layout.css#L208-L211) with the existing desktop `visibility:hidden + opacity:0 + transform` pattern from [layout.css:138-150](../frontend/src/styles/layout.css#L138-L150), adapted for the mobile flex layout (inactive panel becomes `position: absolute; inset: 0` so it does not claim flex space). This preserves scroll position natively (panels stay mounted), avoids JS scroll-memory plumbing, and reuses the existing `map.resize()` on tab change at [MapView.jsx:450](../frontend/src/MapView.jsx#L450). Add a defensive `webglcontextlost` / `webglcontextrestored` listener to [MapView.jsx](../frontend/src/MapView.jsx) (~10 lines) since keeping the canvas mounted on Home/Saved/Alerts tabs slightly increases context-loss exposure on low-memory devices.
9. **Tab-swap motion direction (decided).** Non-directional fade + 8px slide using `--dur-base` (220ms) and `--ease-out`, mirroring the desktop panel transition at [layout.css:138-150](../frontend/src/styles/layout.css#L138-L150) verbatim. No directional state, no new keyframes, no asymmetry between desktop and mobile. Rationale: the editorial Heritage Organic aesthetic is a printed broadside, not a mobile-native app; directional swipes are the wrong visual grammar.
10. **Settings sheet close affordance (decided).** Make `.settings-sheet-footer` ([settings.css:267-271](../frontend/src/styles/settings.css#L267-L271)) `position: sticky; bottom: 0` on mobile so the existing "Done" button ([settings.css:273-286](../frontend/src/styles/settings.css#L273-L286)) remains reachable at any scroll depth in a long sheet. Keep the existing top-right close X visually at 32×32px but expand its hit area to 44×44px (e.g., increased padding or `::before` pseudo-element) so it meets the 44×44 touch-target rule without visually dominating the sheet header. Backdrop tap-outside remains the secondary dismiss path. Rationale: a sticky form-footer is a printed-form pattern that fits the editorial aesthetic; drag-to-dismiss is too app-native and too much net-new motion vocabulary.
11. **Map overlay collision rule for narrow viewports (decided).** Below 400px, prevent bottom-edge collision between `.map-legend` and `.map-heading-btn` by reserving a compass-width corridor on the legend's right edge (e.g., `.map-legend { right: calc(var(--map-compass-width, 100px) + var(--sp-4)); }`) so both overlays read as a coordinated bottom rail without DOM restructuring or flex-wrap. Keep the legend as separately absolutely-positioned (no shared container, no `flex-wrap` over a tall column-flex child) — this avoids unverifiable wrap-on-wrap behavior across CTA-line counts and i18n string lengths. Add defensive `overflow: hidden; text-overflow: ellipsis` on `.map-legend-name` (currently `white-space: nowrap` at [map.css:70](../frontend/src/styles/map.css#L70)) for pathologically long localized line names. No legend hidden, no text shrinking, no new affordances, no JSX changes — ~6 lines of CSS. Rationale: achieves Option A's visual outcome (unified bottom rail) without Option A's wrap-behavior risk; preserves all functionality and a11y at the smallest viewports.
12. **Lighthouse baseline capture (decided).** Step 0 of `/resolve-item FEAT-012`: run Lighthouse Mobile (Chrome DevTools, default Moto G4 profile, slow-4G throttling) twice on the Vercel preview of `main` for the Home-tab empty-form state, take the median perf + a11y scores, and record both numbers in the PR description. After implementation, re-run from the PR's Vercel preview and assert that perf and a11y are each within **±2 points of baseline** (tolerance accommodates Vercel preview run-to-run variance; not a softening of the regression net). Do not add a `PERFORMANCE_BASELINES.md` ledger or wire up Lighthouse CI in this FEAT — those are properly their own follow-ups if the maintainer wants ongoing perf protection.
13. **Intermediate drop-cap value (decided).** Use **60px** at the new `@media (min-width: 401px) and (max-width: 800px)` breakpoint, with `letter-spacing: -3px` and `line-height: 0.83` (preserves phone-italics character; do *not* tighten to desktop's -2px). Add a `--drop-cap-tablet: 60px` token in [tokens.css:50-53](../frontend/src/styles/tokens.css#L50-L53) alongside the existing `--drop-cap-desktop`/`--drop-cap-mobile`/`--drop-cap-hero` trio. Resulting ladder: ≤359px → 56, 360–400px → 72, 401–800px → 60, ≥801px → 52. Rationale: 60 is the clean midpoint between mobile 72 and desktop 52; reads as "a touch trimmed" at 414px without losing phone-hero character, and clearly distinct from desktop at 768px.
14. **`:active` color rule (decided).** Family-specific pressed states mirror the existing family-specific hover system. **Three rules:** (a) **Ghost buttons** (transparent → `--paper-folio` on hover; classes include `.side-rail__tab`, `.tab-bar__tab`, `.btn-ghost-icon`, `.map-unlock-btn`, `.map-relock-btn`, `.map-heading-btn`, `.saved-dropdown-item`): pressed inverts to `background: var(--ink); color: var(--paper)` — editorial "ink presses paper," zero new tokens. (b) **Primary ink-fill buttons** (`opacity: var(--opacity-hover)` on hover; classes include `.settings-done-btn`, `.settings-byok-save`, `.label-save-btn`): pressed deepens to `opacity: var(--opacity-pressed)`. Add a single new token `--opacity-pressed: 0.7` in [tokens.css](../frontend/src/styles/tokens.css). (c) **Icon/link buttons** (`color: mute → rust`/`ink` on hover; classes include `.star-btn`, `.saved-dropdown-delete`, `.settings-sheet-close`, `.settings-byok-clear`, `.geo-denied-dismiss`): **no additional `:active` rule** — these are too small for color-flash to register meaningfully on tap; the existing `:focus-visible` ring plus the hover transition is sufficient. **Inline documentation required:** at the top of each style file that defines `:active` rules, add a brief comment block explaining the three-family system (ghost / ink-fill / icon-link) and which family this file's classes belong to, so future maintainers don't have to re-derive the rule when adding new buttons. Rationale: existing hover system is already family-specific; press states should mirror that structure rather than impose a one-size rule that fights the existing language.

**Acceptance criteria:**

*Touch-state parity (per family rules from decision #14)*

- **Ghost buttons** (every `:hover` rule that swaps to `--paper-folio` or `--paper-bright`): each has a corresponding `:active` rule that inverts to `background: var(--ink); color: var(--paper)`. Pressed feedback is visible within 50ms on tap on a real iOS Safari and Android Chrome device.
- **Primary ink-fill buttons** (every `:hover` rule using `opacity: var(--opacity-hover)`): each has a corresponding `:active` rule using new token `--opacity-pressed` (0.7).
- **Icon/link buttons** (color-shift on hover): no `:active` rule added; rely on existing `:focus-visible` ring + hover transition. This is intentional per decision #14 and must be documented inline.
- New token `--opacity-pressed: 0.7` added to [tokens.css](../frontend/src/styles/tokens.css).
- **Inline documentation:** every style file that adds new `:active` rules opens with a brief comment block explaining the three-family system (ghost / ink-fill / icon-link) and which family this file's classes belong to.

*Spacing token discipline*

- Zero raw pixel values in mobile CSS for spacing/sizing where a `--sp-*` or new `--tab-bar-height` token applies. Hardcoded `14px`, `10px`, `80px`, `56px` audit cleared.
- Form label width ([form.css:21](../frontend/src/styles/form.css#L21)) becomes a CSS variable or shrinks responsively below 400px width; very-narrow viewports (320–360px) gain back at least 24px of horizontal label-to-input space.

*Map overlay safe-area + sizing*

- Legend, train card, and compass button respect `env(safe-area-inset-top/right/bottom/left)`; nothing clips behind a notch or status-bar area on iPhone 14/15-class devices.
- Map overlay buttons meet a 44×44px minimum touch target (current ~32px). Visual sizing can stay tight via inner padding while the hit-area expands.
- Below 400px, `.map-legend` reserves a compass-width corridor on its right edge (per decision #11) so legend and compass form a coordinated bottom rail without colliding. `.map-legend-name` gains defensive `overflow: hidden; text-overflow: ellipsis` for pathologically long localized line names.
- New token `--map-compass-width` added to [tokens.css](../frontend/src/styles/tokens.css) (or hardcoded fallback in the calc()) so the legend's reserved corridor stays in sync with the compass button's actual width.
- On 320px-wide viewports, no two map overlays visually collide with default content.

*Typography*

- A new intermediate drop-cap breakpoint exists at `@media (min-width: 401px) and (max-width: 800px)` using **60px** with `letter-spacing: -3px` and `line-height: 0.83` (per decision #13). New token `--drop-cap-tablet: 60px` added to [tokens.css](../frontend/src/styles/tokens.css#L50-L53) alongside the existing `--drop-cap-desktop`/`--drop-cap-mobile`/`--drop-cap-hero` trio.
- Visual diff at 414px (iPhone Pro Max) and 768px (iPad Mini portrait) shows the drop-cap proportional to surrounding meta text rather than dominating it.
- Tabular numerals confirmed active on all numeric mobile output (departures, walk minutes, fares).

*Settings sheet UX*

- `.settings-sheet-footer` is `position: sticky; bottom: 0` on mobile (per decision #10), so the existing "Done" button remains reachable at any scroll depth when sheet content overflows `80dvh`.
- The top-right close X stays visually 32×32px but expands its hit area to 44×44px (via padding or `::before` pseudo-element) so it meets the 44×44 touch-target rule.
- Backdrop tap-outside continues to dismiss the sheet (existing behavior — verify still wired).
- Sheet entrance respects `prefers-reduced-motion`.

*Motion parity*

- Tab-swap on mobile applies a non-directional 220ms fade + 8px slide using the existing `--dur-base` and `--ease-out`, mirroring the desktop panel transition at [layout.css:138-150](../frontend/src/styles/layout.css#L138-L150) verbatim (per decisions #8 and #9). `prefers-reduced-motion` collapses to instant swap.
- Mobile `display: none` rules at [layout.css:208-211](../frontend/src/styles/layout.css#L208-L211) are replaced with the desktop `visibility:hidden + opacity:0 + transform` pattern, adapted for the mobile flex layout (inactive panel becomes `position: absolute; inset: 0`).
- No new `@keyframes` are introduced.

*Map canvas resilience (per decision #8)*

- A defensive `webglcontextlost` / `webglcontextrestored` listener pair is added to [MapView.jsx](../frontend/src/MapView.jsx). On context loss: prevent default and stop the existing render loop. On restoration: re-create the MapLibre style and re-call `map.resize()`. Verified by manually triggering context loss via Chrome DevTools "Lose context" button on the WebGL inspector and confirming the canvas recovers without a page reload.

*Tab-bar polish*

- `--tab-bar-height` token in `tokens.css`; both the tab-bar `min-height` and the `.panel-cards` `padding-bottom: calc(...)` reference it.
- Scroll position on the Home/Saved/Alerts tabs is preserved when the user switches tabs and returns. This is achieved via the unified panel-swap pattern from decision #8 — inactive panels stay mounted (`visibility: hidden; opacity: 0; transform`) so the browser preserves `scrollTop` natively; no JS scroll-memory plumbing required. Verify via manual repro on iOS Safari and Android Chrome.

*Regression net*

- **Step 0 of `/resolve-item`:** capture pre-FEAT mobile Lighthouse baseline (Chrome DevTools, Moto G4 profile, slow-4G throttling) twice on the Vercel preview of `main` for the Home-tab empty-form state; record median perf + a11y scores in the PR description (per decision #12).
- Post-implementation Lighthouse mobile run from the PR's Vercel preview shows perf and a11y each **within ±2 points of baseline** (tolerance for run-to-run variance, not a softening).
- Existing Vitest + Playwright suites (`frontend/src/tests/`) all pass; manual smoke on the four tabs at 360, 414, 768, and desktop widths shows no broken layouts.

**Files likely touched:**

- `frontend/src/styles/layout.css` (mobile block; tab-bar; replace `display:none` with `visibility:hidden + transform` per decision #8; tab-swap motion per decision #9; safe-area)
- `frontend/src/styles/tokens.css` (introduce `--tab-bar-height: 56px`, `--touch-min: 44px`, `--opacity-pressed: 0.7`, `--drop-cap-tablet: 60px`, `--map-compass-width`)
- `frontend/src/styles/map.css` (overlay positioning, safe-area, button hit-areas, legend right-edge corridor per decision #11, `text-overflow: ellipsis` on `.map-legend-name`)
- `frontend/src/styles/route-cards.css` (intermediate drop-cap breakpoint at 401–800px using `--drop-cap-tablet` per decision #13; `:active` states for header button and inline buttons per decision #14)
- `frontend/src/styles/form.css` (responsive label width; `:active` parity per decision #14)
- `frontend/src/styles/settings.css` (sticky `.settings-sheet-footer` on mobile per decision #10; expanded 44×44 hit area on close X; `:active` parity per decision #14)
- `frontend/src/styles/pinned-stops-and-alerts.css`, `frontend/src/styles/favorites.css`, `frontend/src/styles/share.css`, `frontend/src/styles/masthead.css` (`:active` parity for pins/saves/shares/ghost icons per decision #14)
- `frontend/src/MapView.jsx` (defensive `webglcontextlost` / `webglcontextrestored` listener pair per decision #8 — ~10 lines)
- `frontend/src/App.jsx` (no JS scroll-memory needed — decision #8 makes the unified panel-swap pattern CSS-only; touch this file *only* if the `data-active-tab` selector wiring needs adjustment for the mobile flex-vs-grid divergence)
- `frontend/src/tests/` (small behavioral tests for `:active` rules per family if practical; manual smoke for scroll-memory and webgl-recovery — those are hard to assert in Vitest/Playwright without flakiness)

**Open questions:** None — all seven original open questions have been resolved into scoping decisions #8–#14 above.

**When to revisit:** Ready to invoke `/resolve-item FEAT-012`. If the diff exceeds ~600 LOC during implementation, pause and split into FEAT-012a (touch-state + tokens), FEAT-012b (map overlays + safe-area), FEAT-012c (motion + settings sheet) before continuing.

---

### FEAT-013 --- Curated Chicago Public Library tier in autocomplete

**Type:** Bolt-On

**Status:** Scoped, ready to implement after FEAT-011a ships. Decisions captured 2026-05-06 via the `/resolve-item FEAT-011` walk-through (this feature was spawned mid-walk-through). No further scoping needed before implementation.

**Dependency:** FEAT-011a. This feature requires the generic N-tier registration pattern that FEAT-011a introduces in the static prefix index loader. Cannot ship before FEAT-011a; can ship in parallel with or before FEAT-011b.

**User story / motivation:** Chicago Public Library branches are high-confidence civic destinations that riders frequently route to. Today they're only resolvable post-submit via Google Geocoding (e.g., "Harold Washington Library Center" works on submit but never autocompletes inline). After FEAT-011b they would be partially covered by the OSM POI tier, but OSM coverage of CPL branches is incomplete and lacks the official, branded names CPL itself uses. As a rider typing "Sulzer," I want the Conrad Sulzer Regional Library branch to appear inline as a recognized destination — with the same curated, deliberate feel as the existing train station and neighborhood tiers, not buried in a generic POI list.

**Current coverage (for context):**

- CPL branches today: only resolvable via post-submit Google Geocoding, no inline autocomplete.
- After FEAT-011b ships: partially covered by the OSM POI tier (OSM has `amenity=library` tagging for most but not all CPL branches; names are inconsistent — some say "Chicago Public Library — Sulzer", others just "Sulzer Regional").
- This FEAT supersedes that partial coverage with a curated, authoritative tier.

**Acceptance criteria:**

- All ~80 CPL branches appear as inline autocomplete suggestions when the rider types any prefix of the official branch name (e.g., "wash", "harold", "sulz", "cha" → Chicago Lawn).
- Suggestions render with a dedicated `library` badge, styled consistently with existing badges (`station`, `neighborhood`, `stop`).
- The tier ranks **above** TIGER addresses (FEAT-011a) and OSM POIs (FEAT-011b) but **below** the existing transit-focused tiers (train station, neighborhood, bus stop). Concretely: train → neighborhood → stop → **library** → address → POI → Google fallback.
- When the same branch appears in both the curated CPL tier and the OSM POI tier (post-FEAT-011b), the curated entry wins and the OSM duplicate is suppressed.
- Selecting a library suggestion resolves to coordinates without any external API call (lat/lng is in the static artifact).
- Branch data lives in a static, in-repo JSON file; no runtime/build dependency on `data.cityofchicago.org`.

**Files likely touched:**

- `backend/static_data/cpl_locations.json` (new — static artifact, ~80 entries, committed to repo as source of truth — must live under `static_data/` not `data/` because Railway's persistent volume overlays `/app/data` at runtime)
- `scripts/build_geo_index.py` (extends the FEAT-011a build script with a `--refresh-cpl` subcommand that fetches the latest data from the Chicago Open Data Portal "Libraries — Locations, Hours and Contact Information" dataset and overwrites the JSON file)
- `backend/main.py` (registers the CPL tier with the index loader; small dedupe rule for the OSM-overlap case)
- `frontend/src/components/LocationInput.jsx` (handles `library` suggestion type)
- `frontend/src/App.css` (badge styling for the `library` type, consistent with existing badges)
- `frontend/public/locales/*/translation.json` (new key `autocomplete.badge.library` rolled out across all 27 locales)
- `backend/tests/` (CPL fixture, ranking tests, OSM-dedupe test)

**Data source:**

- **Authoritative:** static `backend/static_data/cpl_locations.json` committed to the repo. ~80 entries, <50KB. Source-of-truth artifact.
- **Refresh path:** `scripts/build_geo_index.py --refresh-cpl` fetches the current dataset from `data.cityofchicago.org` ("Libraries — Locations, Hours and Contact Information") and overwrites the JSON file. The maintainer runs this ad-hoc — annually, or when notified of a CPL branch change. No CI dependency on the city portal.
- **Rationale for static-with-refresh-script over live fetching:** ~80 entries that change every few years. Static asset is fully reproducible, license-clean, and immune to portal outages. The refresh script provides automation when needed without coupling production builds to an external service.

**Fields stored per branch:**

- `name` — official branch name (e.g., "Harold Washington Library Center", "Conrad Sulzer Regional Library")
- `address` — formatted street address (used as the secondary line in the dropdown, not as a search target)
- `lat`, `lng` — coordinates
- `branch_code` — the city's stable identifier (used as the suggestion `value` for resolution and as the dedupe key against OSM)

Hours, phone, branch type, and other CPL metadata are explicitly **out of scope** — this is a routing app, not a library directory.

**Tier placement:**

- New tier inserted between the existing bus-stop tier and the FEAT-011a addresses tier.
- Final ranking after all of FEAT-011a, FEAT-011b, and FEAT-013 ship: train station → neighborhood → bus stop → **library (this FEAT)** → address (FEAT-011a) → POI (FEAT-011b) → Google fallback.

**Out of scope:**

- Other civic destination types (parks, schools, post offices, museums, fire stations). Each would warrant its own curated tier or be left to the OSM POI tier. If the maintainer decides to extend the curated-civic-tier pattern later, that's its own FEAT.
- Hours, phone, and branch metadata.
- Live status (open/closed, holiday closures) — not a routing concern.

**When to revisit:** After FEAT-011a ships. At that point this entry should be straightforward to invoke via `/resolve-item FEAT-013` with no further scoping.

---

### FEAT-014 --- Fallback-learning cache (persistent + index-promotion)

**Type:** Bolt-On

**Status:** Scoped, ready to revisit after FEAT-011a ships and accumulates a few weeks of production traffic data. Spawned 2026-05-06 from the FEAT-011 decision walk-through (Decision 1 cascading effect). Per maintainer direction this is tracked as a feature, not an optimization.

**Dependency:** FEAT-011a. This feature builds on top of the in-memory `RESOLVE_CACHE_MAX_ENTRIES` LRU and the autocomplete cache from Decision 6 — turning them from process-lifetime caches into persistent, learning structures.

**User story / motivation:** When a rider searches for a long-tail location (e.g., a small business not in OSM, a specific address not in TIGER), FEAT-011a's hybrid invokes Google Places as fallback and pays per session. Today's caches (Decision 6.B autocomplete LRU; Decision 6.C Place Details LRU) save cost within a single backend process lifetime but evict on restart. This FEAT extends those caches to (a) survive restarts via persistent storage, and (b) **promote frequently-resolved entries into the static prefix index** so subsequent searches hit the local path entirely — the long-term effect being a system that gets cheaper over time as it learns the popular Chicago long-tail.

**Current coverage (for context):**

- Decision 6.B: 1h-TTL LRU of autocomplete responses, in-memory only, evicted on process restart.
- Decision 6.C: indefinite-within-process-lifetime LRU of Place Details responses, in-memory only, evicted on process restart.
- After FEAT-014: both become persistent, and a promotion mechanism elevates high-frequency entries into the static index.

**Acceptance criteria:**

- Resolved Google place_ids and their `(lat, lng, display_name, formatted_address)` data are persisted to disk (SQLite or on-disk JSON — TBD during scoping refresh) and survive backend process restarts.
- A promotion mechanism: any cached entry that has been resolved more than `LEARNING_PROMOTION_THRESHOLD` times (env-tunable, default e.g. `5`) is added to the static prefix index on the next monthly rebuild via `scripts/build_geo_index.py`. Once promoted, it's served from the local path with zero Google calls.
- Promotion is permitted under Google's Places API (New) Terms — only the cacheable fields (`place_id`, `location`, `formattedAddress`, `displayName`) are persisted. Hours/ratings/photos are explicitly never stored.
- A refresh-on-hit policy revalidates promoted entries older than `LEARNING_REFRESH_DAYS` (default e.g. `180`) — when such an entry is hit, the cached result is served immediately and a background revalidation against Google updates the entry. Bounds stale-data risk for closed/relocated POIs.
- The autocomplete LRU from Decision 6.B optionally upgrades from in-memory to persistent (decision deferred to scoping refresh — not strictly required for the index-promotion mechanism).
- Backend startup loads persisted entries into the working caches.
- Maintainer-facing diagnostic: a small admin endpoint or CLI command shows top N most-hit promoted entries, top N pending-promotion candidates, and total Google calls saved.

**Files likely touched:**

- `backend/places.py` (new persistence layer; or `backend/learning_cache.py` as a sibling module)
- `backend/data/learning_cache.sqlite` or `backend/data/learning_cache.json` (new persisted artifact — storage format TBD)
- `scripts/build_geo_index.py` (extend to merge promoted entries into the static artifact at rebuild time)
- `backend/main.py` (cache wiring; admin endpoint for diagnostics)
- `backend/.env.example` (`LEARNING_PROMOTION_THRESHOLD`, `LEARNING_REFRESH_DAYS`, possibly others)
- `backend/tests/` (persistence round-trip, promotion threshold behavior, refresh-on-hit, ToS-compliant fields-only)
- `docs/PRIVACY.md` (note that resolved place data is persisted across restarts)

**Open questions (for future scoping refresh — do not assume any answer below is final):**

1. **Storage format.** SQLite vs. on-disk JSON. SQLite is more queryable and atomic but pulls in another file format and migration path. JSON is simpler but slower to read at startup if the cache grows.
2. **Promotion threshold value.** 5 hits? 10? Should it be based on hits-per-week to deweight ancient one-time queries?
3. **Refresh cadence.** Refresh-on-hit (lazy) vs. periodic background sweep (eager). Lazy is simpler; eager catches stale POIs even for entries no one is currently searching.
4. **Autocomplete LRU persistence.** Should Decision 6.B's autocomplete cache also persist, or only the resolution cache (Decision 6.C)? Resolution cache has higher cost-per-entry; autocomplete cache has higher hit-rate-per-entry.
5. **Eviction policy for persistent store.** LRU on access? Size-bounded with FIFO? Time-bounded (purge entries older than X)?
6. **Promotion competition.** What happens if a Google-promoted entry's name conflicts with an existing static-index entry (e.g., a POI promotion creates a duplicate of a library)? Decision 7.C's dedupe rules likely handle this but should be re-checked in scoping.
7. **Privacy disclosure update.** PRIVACY.md mentions Google fallback (FEAT-011's Decision 9). Persistent cache likely needs a brief mention — what is persisted, for how long, can it be deleted?

**When to revisit:** After FEAT-011a has been in production for a few weeks. Real cache-hit-rate data and resolved-place-id frequency distribution will inform the promotion threshold and storage decisions. This entry should be tightened (open questions resolved, ACs become firm) before invoking `/resolve-item`.

---

### FEAT-015 --- Bus-stop platform-level disambiguation in autocomplete

**Type:** Bolt-On

**Status:** Scoping stub. Spawned 2026-05-06 from FEAT-011 Decision 10. Open question awaiting evidence-driven resolution after FEAT-011 ships.

**Dependency:** None hard. Likely sequenced after FEAT-011 so the maintainer can observe how riders use the richer post-FEAT-011 dropdown before deciding the right disambiguation pattern.

**User story / motivation:** The current bus-stop tier in `/autocomplete` dedupes by name — multiple physical stops at the same intersection (e.g., "Belmont & Clark" — NB, SB, EB, WB platforms) collapse to a single suggestion. This is generally the right call for casual riders who think in terms of intersections, but obscures useful structure for: (a) power users who know the platform they need, (b) accessibility-aware routing where specific platforms have specific accessibility states, (c) schedule lookups tied to a specific direction. The open question is whether to surface that structure, and how.

**Current coverage (for context):**

- Bus-stop tier today: deduped by name in [backend/main.py:312-358](../backend/main.py#L312-L358).
- After FEAT-011: bus-stop tier behavior is **explicitly preserved** (Decision 10) — addresses, POIs, and library tiers are added without touching it.

**Open questions (to resolve in a future scoping walk-through):**

1. **Un-dedupe entirely.** Each platform becomes its own suggestion. Pros: maximum precision. Cons: ~4× more bus-stop entries, dropdown clutter for ambiguous picks.
2. **Expandable group.** Single deduped suggestion in the dropdown; selecting it expands a secondary picker showing each platform. Pros: keeps the dropdown clean for casual riders, exposes detail for power users. Cons: new UX pattern not used elsewhere in the app.
3. **Direction badges.** Display each platform with a small directional indicator (NB, SB, EB, WB). Compact but assumes riders understand cardinal direction at the stop level.
4. **Hybrid.** Dedupe only when platforms are co-located (within ~15m); show separate entries when they're physically distinct. Catches the "Belmont & Clark has 4 SBC platforms" case while preserving the "Cottage Grove & 47th has 2 stops on opposite corners" case.
5. **Accessibility-tier disambiguation.** Show platforms with their accessibility metadata (wheelchair-accessible, has bench, has shelter, etc.). Probably its own FEAT given the data-collection scope.

**Provisional acceptance criteria (to firm up in scoping):**

- Riders typing a deduped intersection name see meaningful platform-level information (whether by un-dedupe, expand, or hybrid — TBD).
- Behavior under the existing dedupe-by-name pass remains discoverable for riders who don't want platform-level detail.
- No regression in autocomplete latency.

**Files likely touched (provisional):**

- `backend/main.py` (modify the existing bus-stop dedupe pass)
- `frontend/src/components/LocationInput.jsx` (UX pattern for expanded/disambiguated entries, if going that route)
- `frontend/src/App.css` (styling for the chosen UX)
- `frontend/public/locales/*/translation.json` (any new direction or platform labels — 27 locales)
- `backend/tests/`

**When to revisit:** After FEAT-011 has shipped and accumulated some weeks of usage data. Observed dropdown-pick patterns for bus-stop suggestions (do riders often pick a deduped entry and immediately re-route? do they search for direction-specific names like "Belmont southbound"?) will inform which option is right.

---

### FEAT-016 --- Translate the new alerts-flow strings across all 27 locales

**Type:** Bolt-On --- frontend-only data work; no logic, component, or backend changes.

**Status:** Scoping stub. Spawned 2026-05-07 alongside the alerts-flow rework that introduced the [`RouteAlertsBanner`](../frontend/src/components/RouteAlertsBanner.jsx) and [`AlertsFilterBar`](../frontend/src/components/AlertsFilterBar.jsx) components. The parent FEAT shipped English-only strings; non-English locales fall back to English at runtime via i18next.

**Dependency:** Parent alerts-flow FEAT must ship first (and the new keys must be present in `frontend/public/locales/en/translation.json`).

**User story / motivation:** The parent FEAT added 14 new i18n keys (banner present/absent, filter labels, filter prompts, helper text). These are wrapped in `useTranslation().t()` calls so they're translation-ready, but only the English `translation.json` was populated. Riders on non-English locales currently see English copy in two new high-traffic surfaces: (a) the banner above each route's results column, and (b) the Notices & Delays tab heading. Bringing the new keys up to the locale-coverage bar already established by FEAT for the rest of the app (commit `680f077 — Locale expansion (22→76)…`) restores parity.

**Keys to translate (per `frontend/public/locales/en/translation.json`):**

- `route_alerts_banner_present`
- `route_alerts_banner_present_cta`
- `route_alerts_banner_present_aria`
- `route_alerts_banner_absent`
- `alerts_filter_l_label`
- `alerts_filter_bus_label`
- `alerts_filter_l_count` (uses `{{count}}` interpolation)
- `alerts_filter_bus_count` (uses `{{count}}` interpolation)
- `alerts_filter_l_aria`
- `alerts_filter_bus_aria`
- `alerts_filter_clear`
- `alerts_filter_prompt`
- `alerts_filter_empty_for_selection`
- `alerts_bus_filter_help`

**Provisional scoping notes:**

1. **Translation source.** Use the same translation pipeline used for the 22→76 locale expansion. The locale set was retrenched to 27 Chicago-focused languages on 2026-05-11. The 3 `RESEARCH_LOCALES` flagged in [i18n.js](../frontend/src/i18n.js) (`aii`, `ksw`, `rhg`) should continue to surface the `mt-review-notice` MT badge for these keys.
2. **Editorial register.** Source English follows the project's period-newspaper register: declarative, em-dashes preferred, no exclamation points, "notices" in user-facing copy (matching `alerts_tab_heading: "Notices & Delays"`). Translators should preserve that voice — these are short copy, so a single tonal misstep is disproportionately visible.
3. **Pluralisation.** `alerts_filter_l_count` and `alerts_filter_bus_count` use simple `{{count}}` interpolation today (e.g., "L (2)"). Languages with non-trivial plural rules — Russian, Polish, Arabic — may want explicit `_one` / `_few` / `_many` variants per i18next pluralisation conventions. Decide per-locale during translation.
4. **The unicode arrow.** `route_alerts_banner_present_cta` ends with `⟶` (long right arrow). RTL locales (`ar`, `ur`, `ps`, `prs`, `aii`, `rhg`) should mirror to `⟵` or rely on the `[dir="rtl"]` automatic mirror — verify rendering in the per-locale review.
5. **No code changes required** in this FEAT. All component code in the parent FEAT is already i18n-ready (variables passed via `t(key, { count })`, no string concatenation across JSX nodes).

**Acceptance criteria:**

- All 14 keys present in every `frontend/public/locales/<locale>/translation.json` file (27 locales).
- Spot-check on the 3 `RESEARCH_LOCALES` (`aii`, `ksw`, `rhg`) confirms the MT badge surfaces correctly when these keys render.
- Manual switch to at least one RTL locale (e.g., `ar`) and one CJK locale (e.g., `zh`) confirms the banner and the filter popover render without layout breakage or dangling English fallbacks.

**Files likely touched:**

- `frontend/public/locales/*/translation.json` (27 files)

**When to revisit:** Schedule alongside the next routine locale-coverage pass, or sooner if rider analytics show non-English usage of the Notices & Delays surface.

---

### FEAT-017 --- Remove redundant `line_code` edge attribute from transit graph

**Type:** Bolt-On — backend-only refactor; no frontend changes.

**Status:** Scoping stub. Identified during memory-reduction audit on 2026-05-11.

**Background:** Every edge in `G_base` (the NetworkX DiGraph built in `backend/transit_graph.py`) carries a `line_code` attribute that is always set to the same value as `route_id` on the same edge (e.g., both are `"Red"`, `"22"`, etc.). This has been a duplicate attribute since graph construction was written. With ~25,000 edges in the transit graph, removing the attribute saves ~1–2 MB of in-memory overhead.

**Work required:**

1. Grep all read sites for `line_code` across `backend/transit_graph.py`, `backend/main.py`, and any other consumer files.
2. For each consumer, verify that substituting `route_id` produces identical behavior.
3. Remove `line_code=best_route` (and its equivalents) from every `G.add_edge(...)` call in `transit_graph.py`.
4. Update all read sites to use `route_id` instead.

**Acceptance criteria:**

- `line_code` no longer appears as a key in any edge's attribute dict after graph construction.
- All routing and display logic that previously read `line_code` reads `route_id` instead and produces identical output.
- Existing routing integration tests pass unchanged.

**Files likely touched:**

- `backend/transit_graph.py` — `add_edge` calls
- `backend/main.py` — any edge attribute reads referencing `line_code`

**When to revisit:** Low priority — savings are modest. Worth bundling with a future transit graph refactor pass.

---

## Consideration — Geocoding Provider Migration (Google Maps → alternatives)

### Context

The app currently uses Google Maps Geocoding API for both forward geocoding (address → lat/lon in `geocode_google()`) and reverse geocoding (lat/lon → address in `reverse_geocode_google()`), both in `backend/gtfs_loader.py`. Pricing is **$5 per 1,000 calls** after Google's free tier (~28,000 calls/month under the $200 monthly credit, though that credit's terms have changed; safe to assume billable above 9.5k calls). A `_GEOCODE_CALL_LIMIT` safety cap of ~9,500 calls/month exists in code as a temporary guard against runaway billing during the pre-public-launch period; removal of that cap is a known production-blocker before any real growth push (tracked in TODO.md).

At current traffic (~200 DAU target), Google's free tier is comfortable. The decision point arrives between **5,000 and 10,000 DAU**, where geocoding alone becomes the dominant operating cost and starts to compete with revenue:

| DAU | Approx geocode calls/month | Google Maps cost/month |
| :-- | :-- | :-- |
| 1,000 | ~60,000 | ~$160–$300 (depending on free-tier terms) |
| 5,000 | ~300,000 | ~$1,400 |
| 10,000 | ~600,000 | ~$3,000 |
| 50,000 | ~3,000,000 | ~$15,000 |

These numbers assume ~2 unique geocode requests per session × ~30 sessions/user/month × cache hit rate ~50% (the existing `_geocode_cache` halves the wire calls). Cache hit rate may improve at higher traffic as common addresses recur, but the order of magnitude holds.

### Why this matters

Operating costs at 10k DAU under Google Maps would consume **all plausible monthly revenue under the values constraints** (free + no UX-degrading ads). Direct local sponsorships at 10k DAU realistically produce $500–$2,000/month gross; a $3,000/month geocoding bill turns the app cash-negative at exactly the scale where it should be self-sustaining. **The geocoding provider is therefore the binding economic constraint on growth, not the monetization strategy.**

### Provider comparison

| Provider | Forward geocode price | Autocomplete | POI quality (Chicago) | Address quality (Chicago) | Self-host? | Verdict |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| **Google Maps** (current) | $5 / 1k after free tier | ✅ Excellent (Places Autocomplete is a separate $2.83 / 1k product) | ✅ Best in class ("the bean" → Cloud Gate) | ✅ Best in class | No | Premium quality, premium price |
| **Mapbox Geocoding** | $0.75 / 1k after 100k free/month | ✅ Good (Mapbox Search JS) | 🟡 Good in dense urban; weaker on long-tail POIs | ✅ Excellent in Chicago | No | **Likely best fit for this app at 1k–50k DAU** |
| **Geoapify** | ~$0.50 / 1k (3k free/day) | ✅ Built-in autocomplete API | 🟡 OSM-derived; POI coverage variable | ✅ Good | Optional | Cheap; smaller player; quality gaps possible |
| **LocationIQ** | ~$0.25 / 1k (5k free/day) | ✅ Yes | 🟡 OSM-derived | ✅ Good | No | Cheapest hosted option; lower brand stability |
| **MapTiler Geocoding** | ~$0.50 / 1k (free tier varies) | ✅ Yes | 🟡 OSM + curated | ✅ Good | No | Reasonable middle ground |
| **Photon** (hosted Pelias-lite) | Free (public endpoint, no SLA) | ✅ Yes | 🟡 OSM-derived | ✅ Good | Optional | Acceptable for low-volume; **never** a production primary |
| **Nominatim** (self-host) | Free + infra cost | 🟡 Slow autocomplete unless tuned | 🟡 OSM-derived | ✅ Excellent for street addresses | Yes (~16–32 GB RAM for continental US) | Free at scale, heavy ops burden |
| **Pelias** (self-host) | Free + infra cost | ✅ Best-in-class autocomplete | ✅ Federates Nominatim + OpenAddresses + Who's on First + Geonames | ✅ Excellent | Yes (multi-service stack) | Best self-host quality, highest ops burden |

### Recommended migration path

**Phase A (≤ 5k DAU):** Stay on Google Maps. Quality is excellent; costs are tolerable; the 9,500-call cap should be removed or raised before any public-launch push (this is a separate todo, not part of the migration).

**Phase B (5k–25k DAU): Migrate to Mapbox.** This is the sweet spot for the app:

- ~7× cheaper than Google
- Quality on Chicago addresses and major POIs is competitive
- No self-hosting burden
- Mapbox Search JS provides drop-in autocomplete that integrates cleanly with the existing `LocationInput.jsx` autocomplete fetch pattern
- One round of POI testing before committing — search for: "the bean", "Wrigley Field", "Garfield Park Conservatory", "Chinatown", "Promontory Point", "Pequod's Pizza", "Cloud Gate". If results match Google's intent on ≥ 80% of the test set, proceed
- Keep Google Maps as a fallback for the remaining ≤ 20% of long-tail POI queries that Mapbox handles poorly. Implement provider failover, not full replacement

**Phase C (25k+ DAU or multi-city): Self-host Pelias.** Worth considering only if both:

1. Mapbox costs exceed $500/month (≈ 700k requests/month)
2. The app has ≥ 1 part-time technical contributor or the maintainer has time for ops work

Pelias has the best autocomplete UX of the open-source options and federates multiple address sources, which becomes important when expanding beyond Chicago (OSM coverage varies by metro). Until both conditions are met, Mapbox + Google fallback wins on operational simplicity.

### Will alternatives support the existing autocomplete feature?

**Yes, with caveats.** The current `LocationInput.jsx` autocomplete pattern (debounced fetch on input change, AbortController for in-flight cancellation) is provider-agnostic — only the backend endpoint and response shape need to change.

- **Mapbox Search JS** has native autocomplete and a similar debounce-friendly REST endpoint. Direct drop-in.
- **Pelias** `/v1/autocomplete` is purpose-built for typeahead; arguably better than Google for partial-token matching.
- **Nominatim** `/search?q=...` works but is slower and not optimized for keystroke-rate queries; rate limits on the free public instance are aggressive. Self-hosted Nominatim is fine but requires Photon or a custom autocomplete layer for good UX.
- **Geoapify, LocationIQ, MapTiler** all expose autocomplete endpoints with documented response shapes.

**Address-level coverage** is where OSM-derived providers occasionally fall short — they may resolve "1234 W Roscoe" but miss "1234½ W Roscoe" (rear units, garden apartments). Google handles these. In a city with substantial multi-unit housing, this matters; budget a quality test before committing. The existing `geocode_cache` insulates against repeated misses on the same address but does not solve first-encounter failures.

### Migration scope estimate

- **Mapbox migration:** ~1 day. Replace `geocode_google()` and `reverse_geocode_google()` internals; keep the same function signatures so callers don't change. Update env vars (`MAPBOX_TOKEN`). Update the per-IP rate-limit bucket name from `_GEOCODE_*` (still fine — it's just a name). Update `LocationInput.jsx` autocomplete fetch URL/parser. Run the Chicago POI quality test set against both providers and document which queries fail Mapbox, so the fallback layer is informed.
- **Google fallback layer:** ~0.5 day. Wrap the Mapbox call with a "if no results, retry on Google" pattern. Track the fallback hit rate; if it stays below 5%, eventually drop the fallback.
- **Self-hosted Pelias:** ~1–2 weeks initial. Docker compose stack, planet OSM extract import, monitoring, backup, refresh strategy. Not worth it until the cost trigger fires.

### When to start

Trigger this migration when **any** of the following becomes true:

1. The app crosses ~3,000 DAU sustained, and the geocoding cap removal is imminent
2. A serious press push is planned (Block Club, WBEZ, *Reader*) that could spike traffic past the cap
3. Geographic expansion (Pace+Metra coverage area, or other metros) is approved — adds geocoding load by enlarging the input space
4. Google Maps pricing changes (their free-tier terms have shifted before)

Until one fires, the Mapbox migration is documented and ready, but not built.

---

## Consideration — Geographic Expansion Revenue Model

### Context

The app is currently CTA-only. Pace + Metra are in the planned feature list (`Feature PaceMetraCoverage` above) but not yet built. Beyond Chicagoland, expansion to other Midwest metros (Milwaukee, Twin Cities, Detroit, Cleveland, Cincinnati, Columbus) has been raised as a possible direction. This consideration documents the revenue and cost assumptions behind that direction so future decisions can reference concrete numbers rather than vibes.

### Total addressable market (TAM) by expansion stage

These figures are **weekday transit ridership** drawn from public agency reporting (NTD, agency dashboards) ca. 2024–2025. They are upper bounds on app TAM; realistic capture is a small fraction of the total.

| Stage | Adds (weekday riders) | Cumulative TAM | Realistic 3-year DAU capture (1–3% of TAM) |
| :-- | :-- | :-- | :-- |
| **CTA only** (today) | 750k–900k | 750k–900k | 7,500–27,000 DAU (cap) |
| **+ Pace + Metra** (Chicagoland complete) | ~150k Pace + ~150k Metra → ~300k | ~1.05M–1.2M | 10,500–36,000 DAU (cap) |
| **+ Milwaukee (MCTS)** | ~120k–150k | ~1.2M–1.35M | 12,000–40,500 DAU (cap) |
| **+ Twin Cities (Metro Transit)** | ~200k–250k | ~1.4M–1.6M | 14,000–48,000 DAU (cap) |
| **+ Detroit (DDOT + SMART)** | ~80k–110k | ~1.5M–1.7M | 15,000–51,000 DAU (cap) |
| **+ Cleveland + Cincinnati + Columbus** | ~150k–220k combined | ~1.65M–1.92M | 16,500–57,600 DAU (cap) |
| **+ Midwest secondary (Madison, St. Louis, Indianapolis, Louisville)** | ~160k–220k combined | ~1.81M–2.14M | 18,100–64,200 DAU (cap) |
| **+ West Coast tier (Portland, Seattle, Boise)** | ~625k–780k combined | ~2.44M–2.92M | 24,400–87,600 DAU (cap) |

**Crucial caveats:**

- These are **caps**, not forecasts. Realistic 3-year capture from a standing start with no marketing budget is closer to **0.3%–1%** of TAM, not 3%. So divide the rightmost column by ~3 for a likely real-world DAU range.
- Capture rate is not uniform across cities. Chicago capture will be highest because it's the home market with local press potential, civic-tech community presence (Chi Hack Night), and the maintainer's local knowledge. Out-of-market capture rates run roughly **half** of in-market.
- **Each city has a different "best transit app already" landscape** — see the competitive landscape table below. Markets with a strong incumbent (Twin Cities, Seattle, Portland) suppress capture rates by roughly half again versus markets with fragmented or weak incumbents (Milwaukee, Cleveland, Boise).
- **The Seattle and Portland additions are the largest single TAM jumps in the entire ladder.** Together they add more weekday riders than the original Midwest set (Milwaukee + Twin Cities + Detroit + Cleveland + Cincinnati + Columbus) combined. The competitive cost — not the demand side — is what makes them hard.
- **Boise is included for completeness but is borderline net-negative on solo maintenance time.** ~3k–5k weekday riders is below the ~800–1,200 DAU break-even threshold noted in the revenue insights below. Worth it only if used as a low-risk Pacific NW beachhead before Portland/Seattle, or if a local contributor appears.

### Competitive landscape per market

For each candidate metro, the dominant transit app(s) already in use by riders, and the resulting barrier-to-entry for a new entrant. "Transit (the app)" refers to the Montreal-built Transit app (transitapp.com), which is the de facto cross-city incumbent in most North American mid-sized markets.

| City | Dominant transit app(s) | Notes | Incumbent barrier |
| :-- | :-- | :-- | :-- |
| Chicago | Ventra (fares only) + Transit (the app) + Google Maps | No dominant Chicago-built consumer routing app; the wedge is "local routing tuned for Chicago" | LOW |
| Milwaukee | Ride MCTS (official) + Google Maps | Transit app present but not dominant; agency app is fares + tracker | LOW–MEDIUM |
| Twin Cities | Transit (the app, dominant) + Metro Transit (official) | Heavy organic Transit-app adoption; strong MN civic-tech community | HIGH |
| Detroit | Transit (the app) + DART (regional fares) | DDOT/SMART fragmentation favors apps that unify both; agency apps weak | MEDIUM |
| Cleveland | Transit (the app) + RTA CLEvelandTransitApp | Agency tech is dated; Transit dominant for routing | MEDIUM |
| Cincinnati | Transit (the app) + Cincy EZRide (fares) | Metro app lags; Transit dominant for routing | MEDIUM |
| Columbus | Transit (the app) + COTA Bus Pass (fares) | COTA app fares-only; Transit dominant for routing | MEDIUM |
| Madison | Transit (the app) + Madison Metro (official) | College-driven ridership; UW students skew toward Google Maps and Transit | MEDIUM |
| St. Louis | Transit (the app) + Metro On The Go (official) | Transit dominant; official app weak; MetroLink integration matters | MEDIUM |
| Indianapolis | IndyGo MyStop (official) + Transit (the app) | Post–Red Line BRT investment made the agency app unusually entrenched | MEDIUM–HIGH |
| Louisville | TARC Tracker (official) + Transit (the app) | Both have modest adoption; smaller market with low app saturation | LOW–MEDIUM |
| Portland | TriMet (official, best-in-class) + PDX Bus (loyal niche) + Transit | TriMet's official app is unusually polished for an agency tool — high replacement bar | HIGH |
| Seattle | OneBusAway (originated at UW; civic institution) + Transit + Google Maps | OneBusAway has near-universal name recognition among Seattle riders; very loyal users | HIGHEST |
| Boise | Transit (the app) + Google Maps; Token Transit (fares) | Small market, little app saturation; lowest competitive friction in the list | LOW (but TAM is tiny) |

**What this means for capture and prioritization:**

1. **Easy markets (LOW–MEDIUM barrier):** Milwaukee, Cleveland, Cincinnati, Columbus, St. Louis, Louisville, Boise. Realistic capture closer to the upper end of the 0.3–1% real-world band.
2. **Hard markets (HIGH–HIGHEST barrier):** Twin Cities, Indianapolis, Portland, Seattle. Effective strategy is "complement, not replace" the incumbent — focus on routing edge cases the incumbent handles poorly (e.g., multi-agency transfers, walk-leg quality, accessibility routing) rather than head-to-head feature parity.
3. **The OneBusAway moat in Seattle is the single biggest entry-cost factor in the entire expansion ladder.** It is not just an app — it is part of local civic identity. Worth modeling Seattle separately from Portland in any future revenue projection.
4. **Indianapolis is an under-recognized hard market.** IndyGo's investment in MyStop alongside the Red Line BRT rollout has produced an incumbent with stronger adoption than peer Midwest agencies. Don't assume mid-Midwest = soft incumbent.

> Note: the revenue impact table below currently models cumulative stages only through the original Midwest set. Extending it to the Midwest secondary and West Coast tiers requires per-city sponsor-yield assumptions that have not yet been gathered, and is left as future work.

### Revenue impact assumptions

Revenue does not scale linearly with DAU across geographies. The model below uses different yields per channel per geography:

**Per-DAU monthly yield estimates by channel:**

| Channel | Chicago yield | Out-of-market yield | Reason for the gap |
| :-- | :-- | :-- | :-- |
| Direct local sponsorships | $0.10–$0.30 / DAU | $0.02–$0.08 / DAU | Sales relationships are local; out-of-market sponsors require a local sales partner or remote-sales effort with much lower close rates |
| Donations / tip jar | $0.02–$0.05 / DAU | $0.02–$0.04 / DAU | Roughly geography-neutral once user is engaged |
| GitHub Sponsors | flat (~$50–$300/mo total) | flat (same pool) | Tied to open-source visibility, not DAU geography |
| Tasteful affiliates (Divvy, Ventra, transit gear) | $0.01–$0.04 / DAU | $0.005–$0.02 / DAU | Lower out-of-market because Divvy/Ventra are Chicago-specific; need per-city affiliate setup |
| EthicalAds (fallback fill) | $0.005–$0.015 / DAU | $0.005–$0.015 / DAU | Geography-neutral; CPM is a function of advertiser demand, not rider city |

**Stacked revenue at realistic capture (0.5% of TAM, 24-month horizon):**

| Stage | Realistic DAU | Approx gross monthly | Approx Mapbox + Railway cost | Net monthly |
| :-- | :-- | :-- | :-- | :-- |
| CTA only | 4,000 | $400–$1,200 | $80–$120 | **$300–$1,000** |
| + Pace + Metra | 5,500 | $600–$1,800 | $120–$180 | **$450–$1,600** |
| + Milwaukee | 6,200 | $640–$1,950 | $130–$200 | **$500–$1,750** |
| + Twin Cities | 7,500 | $750–$2,300 | $150–$240 | **$580–$2,050** |
| + Detroit | 8,200 | $810–$2,500 | $170–$270 | **$640–$2,200** |
| + all listed Midwest | 9,500 | $920–$2,800 | $190–$320 | **$700–$2,500** |

### Key insights from the table

1. **Pace + Metra is by far the highest-leverage expansion.** It adds ~40% to DAU and ~50% to revenue without leaving the local sponsorship sales territory or requiring a new affiliate setup. This is the expansion to do first, no debate.
2. **Each out-of-market city adds revenue, but at diminishing returns relative to ongoing maintenance load.** Adding Milwaukee adds ~$50–$150/month net but adds ~5 hours/month of GTFS / real-time API / agency-relationship maintenance forever. The break-even DAU per added city is roughly **800–1,200 DAU** of new traffic in that city; below that, the city is net-negative on time.
3. **Sponsor sales becomes impractical past 2 cities solo.** Donations + EthicalAds + GitHub Sponsors + per-city affiliates scale across geographies; sponsor sales does not. After Chicago + one other, the realistic monetization mix shifts heavily toward the passive channels.
4. **The user's stated $400/month-net target is achievable inside Chicagoland alone**, with no out-of-market expansion required. Reaching it depends almost entirely on (a) Pace + Metra shipping, (b) any meaningful distribution push, and (c) the geocoding migration to keep costs down — not on geographic breadth.

### What would change these numbers

**Upward pressure:**
- One major press hit (Block Club, *Reader*, WBEZ, *Streetsblog Chicago*) — empirically these can 5–10× DAU within a week, and a fraction sticks
- Open-sourcing the routing engine — pulls in GitHub Sponsors and inbound consulting that aren't in the table
- A civic grant — lump-sum income that amortizes over a year independent of DAU
- A formal partnership with an agency (CTA pilot, Active Trans Alliance partnership, Code for America brigade endorsement) — adds credibility and distribution

**Downward pressure:**
- Failure to ship Pace + Metra — caps Chicagoland revenue at ~60% of the table's "Pace + Metra added" row
- Per-city maintenance burden compounds — every added city without a local contributor degrades data freshness and increases bug surface
- Google Maps cost wall hits before geocoding migration — at 5k+ DAU on Google, the cost line wipes out the revenue gain from any expansion stage
- Solo burnout on sponsor sales — most likely failure mode for the "Modest sustainable side income" path

### Recommendation

Expansion should follow this priority order, and stop when income stabilizes at the maintainer's target:

1. **Pace + Metra** — clear win, ship as planned
2. **Geocoding migration to Mapbox** — operational prerequisite for any push past ~5k DAU
3. **Distribution push within Chicagoland** (press, Chi Hack Night talk, Reddit, civic-tech network) — measure DAU and net income for 6 months
4. **If $400/month net is hit and stable**, stop expanding. Maintenance discipline matters more than growth at this point
5. **If $400/month net is not hit after step 3**, then evaluate Twin Cities or Milwaukee as the next add — pick whichever metro has either weaker incumbent app coverage (Milwaukee) or a personal/community connection (lower acquisition cost). Skip Detroit/Cleveland/Cincinnati/Columbus unless a local contributor materializes for that metro

**Skip-or-defer signal:** If after step 3 the realistic DAU in Chicagoland is still below 1,500 after 12 months of distribution effort, geographic expansion will not fix the underlying problem (which is distribution, not market size). At that point the right move is to reconsider distribution strategy, not to add cities.

---
