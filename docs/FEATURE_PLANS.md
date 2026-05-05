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
3. Feature LocaleExpansion — 22 → 76 languages + continent-first language picker + machine-translated review badge + design-system-aligned non-Latin fonts — **Bolt-On**

**Analytics Suite — Privacy-Preserving Reach & Engagement Metrics** — ✅ **Complete 2026-05-04.** All nine features (FEAT-001 through FEAT-009) fully implemented across four build phases. Public dashboard live at `/stats`; admin endpoints at `/admin/*`. Three accompanying Considerations (third-party analytics, DAU reconciliation, GeoIP) all resolved. See [docs/archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md) for the full implementation record and [docs/ANALYTICS_MAINTENANCE.md](ANALYTICS_MAINTENANCE.md) for ongoing maintenance notes.

**Standalone Features** (not part of a chunked plan or the analytics suite):

- FEAT-011 — Expand location autocomplete to cover all locations (street addresses + POIs) — **Bolt-On**. Scoped, decisions pending.

---

## Chunked Implementation Plans

---

## Feature Monetization --- House Ads (overall Phase 7, sub-phase 1)

### Overview

Adds a house ad component to partially offset Railway hosting costs without compromising the Heritage Organic UI. The approach is deliberately conservative: house ads only in Phase 1 — no external ad scripts, no third-party cookies, no layout disruption. Direct local sponsorships are the primary Phase 2 play once DAU supports it; CPM networks (EthicalAds, Carbon Ads) are treated as fallback fill rather than a primary revenue source, because the app's hyperlocal Chicago commuter audience is a poor match for those networks' developer-focused advertiser pool. Google AdSense and other programmatic display networks are explicitly avoided — auto-placed display ads carry a high risk of clashing with the cream/charcoal design and hurting retention.

**Target:** ~200 DAU × 2 searches/day = ~12k monthly impressions. Realistic Phase 1 revenue is **~$5/month** from affiliate conversions; the primary value in Phase 1 is building the slot, proving it doesn't hurt UX, and laying groundwork for the higher-revenue direct-sponsorship play once traffic grows. See **Revenue Projections & Post-Phase-1 Roadmap** below for the full DAU-keyed progression.

**Why it matters:** The app has real operational costs. The house ad is the minimal intervention that keeps the interface intact while creating a revenue path.

**Type: Bolt-On** --- frontend-only addition; no backend changes.

**Status:** Not started

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

## Feature LocaleExpansion --- 22 → 76 languages + continent picker

### Overview

Expand i18n coverage from 22 to 76 languages (54 net additions; Romanian `ro` already shipped) to serve transit-dependent, low-English-proficiency populations that mainstream apps (Google Maps, Apple Maps, Transit) leave unserved — particularly refugee resettlement communities, smaller Chicago diasporas with strong local presence, and globally-spoken languages that round out global coverage.

The expansion bundles three companion concerns that must ship together to land well:

1. **Discoverability** — 76 languages in a flat dropdown is overwhelming. A **continent-first picker** (6 continent silhouettes → drill down to languages of that region) keeps the surface scannable and reflects diaspora identity better than an alphabetical mega-list.
2. **Honesty about translation quality** — 8 of the new locales are very low-resource for machine translation (Karen variants, Mongo, Hassaniya Arabic, Bhojpuri, Maithili, Hanifi Rohingya, Assyrian Neo-Aramaic). Each gets a **machine-translated review badge** localized into the target language (never shown in English) plus a feedback affordance so native speakers can flag issues.
3. **Visual coherence** — new non-Latin scripts must render in fonts that match the **Heritage Organic** design system (Inter / Fraunces / JetBrains Mono pairing). Default Noto Sans fallbacks are the safe baseline but visually generic; font selection deserves design research, not a Google Fonts dump.

**Type: Bolt-On** — frontend-only. No backend changes. The existing `scripts/translate-missing.mjs` pipeline and Vite/i18next plumbing already handle the mechanics.

**Status:** Not started.

**Prerequisites:** None.

---

### Scoping decisions

#### 1. The 54 new locales

| # | Language | Code | Native name | RTL | Script | Low-resource |
|---|---|---|---|---|---|---|
| 1 | Haitian Creole | `ht` | Kreyòl ayisyen | — | Latin | — |
| 2 | Burmese | `my` | မြန်မာ | — | Myanmar | — |
| 3 | S'gaw Karen | `ksw` | ကညီ | — | Myanmar (Karen) | ✓ |
| 4 | Karenni / Red Karen | `eky` | ꤊꤛꤢ꤬ꤜꤤ꤭ | — | Kayah Li | ✓ |
| 5 | Amharic | `am` | አማርኛ | — | Ethiopic | — |
| 6 | Tigrinya | `ti` | ትግርኛ | — | Ethiopic | — |
| 7 | Dari | `prs` | دری | RTL | Arabic | — |
| 8 | Persian (Farsi) | `fa` | فارسی | RTL | Arabic | — |
| 9 | Bosnian | `bs` | Bosanski | — | Latin | — |
| 10 | Serbian | `sr` | Српски | — | Cyrillic | — |
| 11 | Croatian | `hr` | Hrvatski | — | Latin | — |
| 12 | Lithuanian | `lt` | Lietuvių | — | Latin | — |
| 13 | Bengali | `bn` | বাংলা | — | Bengali | — |
| 14 | Assyrian Neo-Aramaic | `aii` | ܣܘܪܬ | RTL | Syriac | ✓ |
| 15 | Greek | `el` | Ελληνικά | — | Greek | — |
| 16 | Swahili | `sw` | Kiswahili | — | Latin | — |
| 17 | Thai | `th` | ไทย | — | Thai | — |
| 18 | Swedish | `sv` | Svenska | — | Latin | — |
| 19 | Somali | `so` | Soomaali | — | Latin | — |
| 20 | Hebrew | `he` | עברית | RTL | Hebrew | — |
| 21 | Turkish | `tr` | Türkçe | — | Latin | — |
| 22 | Egyptian Arabic | `arz` | مصرى | RTL | Arabic | — |
| 23 | Marathi | `mr` | मराठी | — | Devanagari | — |
| 24 | Telugu | `te` | తెలుగు | — | Telugu | — |
| 25 | Tamil | `ta` | தமிழ் | — | Tamil | — |
| 26 | Indonesian | `id` | Bahasa Indonesia | — | Latin | — |
| 27 | German | `de` | Deutsch | — | Latin | — |
| 28 | Hausa | `ha` | Hausa | — | Latin | — |
| 29 | Portuguese | `pt` | Português | — | Latin | — |
| 30 | Bhojpuri | `bho` | भोजपुरी | — | Devanagari | ✓ |
| 31 | Kongo | `kg` | Kikongo | — | Latin | — |
| 32 | Mongo (Lomongo) | `lol` | Lomongo | — | Latin | ✓ |
| 33 | Hassaniya Arabic | `mey` | حسانية | RTL | Arabic | ✓ |
| 34 | Afrikaans | `af` | Afrikaans | — | Latin | — |
| 35 | Xhosa | `xh` | isiXhosa | — | Latin | — |
| 36 | Oromo | `om` | Afaan Oromoo | — | Latin | — |
| 37 | Dutch | `nl` | Nederlands | — | Latin | — |
| 38 | Mongolian | `mn` | Монгол | — | Cyrillic | — |
| 39 | Lao | `lo` | ລາວ | — | Lao | — |
| 40 | Khmer | `km` | ខ្មែរ | — | Khmer | — |
| 41 | Kannada | `kn` | ಕನ್ನಡ | — | Kannada | — |
| 42 | Uzbek | `uz` | Oʻzbekcha | — | Latin | — |
| 43 | Sindhi | `sd` | سنڌي | RTL | Arabic | — |
| 44 | Malayalam | `ml` | മലയാളം | — | Malayalam | — |
| 45 | Odia | `or` | ଓଡ଼ିଆ | — | Odia | — |
| 46 | Maithili | `mai` | मैथिली | — | Devanagari | ✓ |
| 47 | Kurmanji Kurdish | `kmr` | Kurdî | — | Latin | — |
| 48 | Sorani Kurdish | `ckb` | کوردیی ناوەندی | RTL | Arabic | — |
| 49 | Malay | `ms` | Bahasa Melayu | — | Latin | — |
| 50 | Cebuano | `ceb` | Cebuano | — | Latin | — |
| 51 | Hokkien (Min Nan) | `nan` | 閩南語 | — | Han | — |
| 52 | Kazakh | `kk` | Қазақша | — | Cyrillic | — |
| 53 | Sinhala | `si` | සිංහල | — | Sinhala | — |
| 54 | Rohingya | `rhg` | 𐴌𐴗𐴥𐴝𐴙𐴚 | RTL | Hanifi Rohingya | ✓ |

**Romanian (`ro`) is already supported** — skipped.

**Karen split:** S'gaw Karen and Karenni / Red Karen are separate non-mutually-intelligible languages with distinct Chicago refugee communities — both ship.

**Kurdish split:** Kurmanji (Latin script, Turkey/Syria diaspora) and Sorani / Central Kurdish (Arabic script, RTL, Iraq/Iran diaspora) use different writing systems — a single `ku` entry cannot serve both, so both ship.

**RTL additions (9):** `prs`, `fa`, `aii`, `he`, `arz`, `mey`, `sd`, `ckb`, `rhg`. Existing RTL: `ar`, `ur`, `ps`. Final RTL set has 12 codes.

**Low-resource flagged (8):** `eky`, `aii`, `bho`, `lol`, `mey`, `mai`, `rhg`, `ksw`. These get the machine-translated review badge.

#### 2. Machine-translated review badge

- New translation keys in [frontend/public/locales/en/translation.json](../frontend/public/locales/en/translation.json):
  - `mt_review_notice` — short notice text shown below the language picker when the active locale is in `RESEARCH_LOCALES`. Example English copy: *"This language was machine-translated and may have errors. Help us improve it — report a translation issue."*
  - `feedback_link_label` — short label for the feedback CTA. Example: *"Report a translation issue."*
- The badge is **always rendered using `t("mt_review_notice")`**, so when a Karenni speaker selects Karenni, the notice itself appears in Karenni. **Never show the badge in English fallback** — if the translation is missing for a low-resource locale, that's a translation script bug to fix, not a UX behavior to ship.
- The `feedback_link_label` points at a feedback target. Day-one acceptable target: a `mailto:` link to the project email or a GitHub Issues link. A first-class user-feedback feature (settings-panel form) is **out of scope** for this entry; tracked separately as a follow-up consideration (see Out of Scope below).

#### 3. Variant-sensitive translation prompts

The existing `scripts/translate-missing.mjs` accepts per-locale instruction notes. These must be added before any low-resource or ambiguous locale is translated:

| Code | Instruction note |
|---|---|
| `arz` | Translate into Egyptian Arabic colloquial (Masri). NOT Modern Standard Arabic. |
| `ksw` | Translate into S'gaw Karen specifically (variant written in Burmese-derived Karen script). NOT Karenni / Red Karen. |
| `eky` | Translate into Karenni / Red Karen, Kayah Li script. NOT S'gaw Karen. |
| `kmr` | Translate into Kurmanji Kurdish using Latin (Hawar) alphabet. NOT Sorani. |
| `ckb` | Translate into Sorani / Central Kurdish using Arabic script. NOT Kurmanji. |
| `lol` | Translate into Mongo / Lomongo, the Bantu language of the Democratic Republic of the Congo. NOT Mongolian (`mn`). |
| `mey` | Translate into Hassaniya Arabic dialect (Mauritania / Western Sahara). NOT MSA. |
| `nan` | Translate into Hokkien (Min Nan) using traditional Han characters as used in Taiwan/Fujian. NOT Cantonese (`yue`) or Mandarin (`zh`). |
| `rhg` | Translate into Rohingya using Hanifi Rohingya script. |
| `aii` | Translate into Modern Assyrian Neo-Aramaic (Sureth) using Syriac script. |
| `bho` | Translate into Bhojpuri using Devanagari script. NOT Hindi. |
| `mai` | Translate into Maithili using Devanagari script. NOT Hindi. |

#### 4. Continent picker model — 6 continents

**Continents:** Africa · Americas · Asia · Europe · Middle East · Oceania.

Antarctica is excluded (no native-language community). Middle East is split out from Asia because the linguistic cluster (Arabic family, Farsi/Dari, Hebrew, Kurdish, Aramaic, Pashto) is large enough to warrant its own bucket and reflects how Chicago diaspora communities self-identify. Oceania currently has zero assigned languages — the tile remains in the grid for design symmetry and shows a "Languages of Oceania coming soon — Tok Pisin, Māori, Sāmoan, ʻŌlelo Hawaiʻi planned" placeholder when tapped.

Each language is assigned to **exactly one** continent for picker purposes. A user looking for English finds it under Americas (primary Chicago context); Spanish under Americas (Latin American Chicago demographics); Hassaniya Arabic under Africa (Mauritania); Egyptian Arabic under Middle East (regional cultural identity).

**Assignment table for all 76 languages:**

- **Americas (4):** `en`, `es`, `ht`, `pt`
- **Europe (15):** `fr`, `it`, `pl`, `ro`, `uk`, `ru`, `bs`, `sr`, `hr`, `lt`, `el`, `sv`, `de`, `nl`, `tr`
- **Middle East (9):** `ar`, `ps`, `he`, `fa`, `prs`, `arz`, `ckb`, `kmr`, `aii`
- **Africa (12):** `yo`, `am`, `ti`, `sw`, `so`, `om`, `ha`, `xh`, `af`, `lol`, `kg`, `mey`
- **Asia (36):** `zh`, `yue`, `ja`, `ko`, `tl`, `vi`, `hi`, `gu`, `pa`, `ne`, `ur`, `bn`, `mr`, `ta`, `te`, `ml`, `kn`, `or`, `mai`, `bho`, `si`, `sd`, `th`, `lo`, `km`, `my`, `ksw`, `eky`, `id`, `ms`, `ceb`, `nan`, `mn`, `kk`, `uz`, `rhg`
- **Oceania (0):** placeholder tile only

#### 5. Continent visual style

- Custom-drawn outline silhouettes, charcoal stroke (`--ink`) on cream (`--paper`), no fill, no inline labels. Stroke weight matches `--hairline`.
- Source SVGs designed for this app — not lifted from a generic library — so the line quality, vertex simplification, and proportion harmonize with the rest of the UI.
- Each tile is a square with an aria-label and a hover/focus tooltip showing the continent name in the active locale (`t("continent_africa")`, `t("continent_americas")`, etc.).
- Stored in `frontend/src/assets/continents/` as 6 SVG files with a normalized viewBox so they render identically at 64px (mobile) and 128px (desktop).

#### 6. Font strategy — design-system-aligned, not blanket Noto

Rather than dropping in `Noto Sans <Script>` for every new script, **research-driven selection**: for each non-Latin script in the new set, evaluate at least 3 candidate web fonts and choose one whose proportion, x-height, contrast, and stroke modulation harmonize with **Inter** (sans body) and **Fraunces** (serif headlines). Document each selection with a one-line rationale.

Candidate families to consider (Noto Sans `<Script>` is the safe baseline if no better match exists):

| Script | Candidate families to evaluate |
|---|---|
| Arabic (extends `ar`/`ur`/`ps` + new `prs`/`fa`/`arz`/`mey`/`sd`/`ckb`) | Vazirmatn, IBM Plex Sans Arabic, Cairo, Noto Sans Arabic |
| Hebrew (`he`) | Heebo (Inter sibling), Frank Ruhl Libre (Fraunces sibling), Rubik, Noto Sans Hebrew |
| Greek (`el`) | Inter already covers Greek; verify before adding fallback |
| Cyrillic (`sr`/`mn`/`kk` — extends existing `ru`/`uk`) | Inter already covers Cyrillic; verify before adding fallback |
| Devanagari (`mr`/`bho`/`mai` — extends `hi`/`gu`/`pa`/`ne`) | Mukta, Hind family, Anek Devanagari, Noto Sans Devanagari |
| Bengali (`bn`) | Hind Siliguri, Anek Bangla, Noto Sans Bengali |
| Tamil (`ta`) | Hind Madurai, Anek Tamil, Noto Sans Tamil |
| Telugu (`te`) | Anek Telugu, Hind Guntur, Noto Sans Telugu |
| Kannada (`kn`) | Anek Kannada, Hind Vadodara, Noto Sans Kannada |
| Malayalam (`ml`) | Anek Malayalam, Manjari, Noto Sans Malayalam |
| Odia (`or`) | Anek Odia, Noto Sans Oriya |
| Sinhala (`si`) | Noto Sans Sinhala (limited alternatives) |
| Thai (`th`) | Sarabun (Inter-aligned), Mitr (geometric), Kanit, Noto Sans Thai |
| Lao (`lo`) | Noto Sans Lao, Phetsarath OT (limited alternatives) |
| Khmer (`km`) | Hanuman, Battambang, Noto Sans Khmer |
| Myanmar (`my`/`ksw`) | Padauk, Myanmar Text, Noto Sans Myanmar |
| Kayah Li (`eky`) | Noto Sans Kayah Li (essentially the only option) |
| Ethiopic (`am`/`ti`) | Abyssinica SIL, Noto Sans Ethiopic |
| Syriac (`aii`) | Noto Sans Syriac (limited alternatives) |
| Han (`nan` — extends `zh`/`yue`/`ja`/`ko` system fallbacks) | Noto Sans CJK; verify if explicit loading is needed for Hokkien |
| Hanifi Rohingya (`rhg`) | Noto Sans Hanifi Rohingya — **availability uncertain.** If Google Fonts does not host it, document fallback to system font with a code comment; this is a known acceptable gap. |

All imports use Google Fonts CSS with `unicode-range` so browsers only download a script's woff2 when a glyph in that range renders. Initial cost: ~17 small CSS requests; zero font binary downloads until a non-English locale is selected.

CSP allowlist already covers `fonts.googleapis.com` and `fonts.gstatic.com` ([frontend/index.html](../frontend/index.html) — verify before each font addition).

#### 7. Continent picker rolls out behind a feature flag

`VITE_CONTINENT_PICKER_ENABLED` env var, default `false` in dev, set `true` in Vercel after the picker is verified end-to-end. This decouples picker rollout from translation completion — translations can ship chunk-by-chunk under the existing flat `<select>`, and the picker flips on once Chunks 14–15 are done.

#### 8. Tests

No new automated tests required. Existing component tests mock `react-i18next` (returning the key as the translation) and continue to pass with no change. Each chunk's acceptance criteria include manual verification steps.

---

### Chunk 1 --- Scaffolding + machine-translated badge UI

**Files:** [frontend/src/i18n.js](../frontend/src/i18n.js), [frontend/public/locales/en/translation.json](../frontend/public/locales/en/translation.json), [frontend/src/components/Masthead.jsx](../frontend/src/components/Masthead.jsx), [scripts/translate-missing.mjs](../scripts/translate-missing.mjs)

**What to build:**

- Append all 54 new rows to the `LANGUAGES` array in `i18n.js` with `{ code, name, rtl }` fields. Until each translation chunk lands, missing-key fallback to English is acceptable; the picker shows the entry but the app reads English.
- Add `RESEARCH_LOCALES = new Set([...])` next to `RTL_LANGS`, listing the 8 low-resource codes.
- Add `mt_review_notice` and `feedback_link_label` to `frontend/public/locales/en/translation.json`.
- In `Masthead.jsx`, render a small notice element below the language `<select>`, gated on `RESEARCH_LOCALES.has(currentLang)`. Use `t("mt_review_notice")` and a link with `t("feedback_link_label")` pointing at a `mailto:` or GitHub Issues URL (define via env var so it can be swapped without code change).
- Extend `scripts/translate-missing.mjs` locale-name map with the 54 new English names + the per-locale instruction notes from Scoping decision 3.
- Run the script for the **22 existing locales only** (just to fill the 2 new keys into already-shipped languages) — do not generate the 54 new locale files yet.

**Acceptance:**

1. Picker shows 76 entries, native names rendered correctly (some glyphs may render in system-fallback fonts until Chunk 13 ships fonts).
2. Switching to a non-existing translation file gracefully falls back to English (i18next default behavior — verify in DevTools no console errors, just `404` on the missing translation.json which i18next handles).
3. Switching to a low-resource code shows the badge — currently in English fallback because no translation file exists yet for those codes; this is expected and gets fixed by chunks 5/7/9/11 when those locale files land.
4. Existing 22 locales show the new keys translated correctly.

---

### Chunks 2–12 --- Translation rollout (≤5 languages per chunk)

**Files (per chunk):** new `frontend/public/locales/<code>/translation.json` files generated by the translation script.

**Process for each chunk:**

1. Confirm the locale-name + variant-instruction entries are present in `scripts/translate-missing.mjs` (added in Chunk 1).
2. With `ANTHROPIC_API_KEY` set, run `node scripts/translate-missing.mjs` filtered to the chunk's codes (extend the script to accept a code allowlist via CLI arg if not already supported — minor enhancement).
3. Eyeball-review each generated file: confirm glyphs are in the correct script (catch obvious failures where Claude returned text in a related higher-resource language), confirm `{{vars}}` and emoji/symbols (🔓 ☆ ★ ■ ▶ ⟶ — ·) survived, confirm RTL files contain natural RTL prose without inserted bidi markers.
4. Build (`npm run build` in `frontend/`) and switch to each new locale in the running app — confirm no missing-key warnings for the chunk's codes.
5. RTL chunks: confirm `<html dir="rtl">` toggles via `useDocumentLanguage` hook and that `rtl-a11y.css` rules apply.

**Chunk schedule:**

| Chunk | Codes | Theme |
|---|---|---|
| 2 | `de`, `sv`, `nl`, `pt`, `lt` | Western/Northern Europe (Latin) |
| 3 | `hr`, `bs`, `sr`, `el`, `tr` | SE Europe + Greek + Turkish (mixed Latin/Cyrillic/Greek) |
| 4 | `he`, `fa`, `prs`, `ckb`, `kmr` | Middle East — Hebrew, Persian family, Kurdish (4 RTL + 1 Latin) |
| 5 | `arz`, `sd`, `mey`, `aii`, `rhg` | Arabic-script + Aramaic + Rohingya (5 RTL, 4 low-resource) |
| 6 | `bn`, `mr`, `ta`, `te`, `ml` | South Asian Indic — batch 1 (5 distinct scripts) |
| 7 | `kn`, `or`, `mai`, `bho`, `si` | South Asian Indic — batch 2 (3 low-resource) |
| 8 | `th`, `lo`, `km`, `my`, `id` | Mainland SE Asia + Indonesian |
| 9 | `ms`, `ceb`, `ksw`, `eky`, `nan` | Maritime SE Asia + Karen variants + Hokkien (2 low-resource) |
| 10 | `am`, `ti`, `sw`, `so`, `om` | East Africa |
| 11 | `ha`, `xh`, `af`, `lol`, `kg` | West/Southern Africa + Bantu (1 low-resource) |
| 12 | `mn`, `kk`, `uz`, `ht` | Central Asia + Caribbean (4 codes — final translation chunk) |

**Per-chunk acceptance:**

1. Each `translation.json` exists with all keys present (currently 184 keys: 182 original + 2 added in Chunk 1; verify count matches `en.json` at chunk-execution time).
2. `{{interpolation}}` placeholders intact in every translated value.
3. Symbols preserved exactly: 🔓 ☆ ★ ■ ▶ ⟶ — ·.
4. RTL locales: text reads naturally right-to-left in browser; no embedded bidi control characters added by the model.
5. For low-resource codes: `mt_review_notice` and `feedback_link_label` are translated into the target language (not English); badge displays correctly.
6. Build succeeds; no console warnings for missing keys when each new locale is selected.
7. Spot-check at least one interpolation key (e.g., `walk_from_origin`) and one symbol key (e.g., the favorites star) per locale.

---

### Chunk 13 --- Font research + integration

**Files:** [frontend/index.html](../frontend/index.html), [frontend/src/styles/tokens.css](../frontend/src/styles/tokens.css)

**What to build:**

- For each script in the table at Scoping decision 6, evaluate ≥3 candidate fonts side-by-side with Inter and Fraunces. Capture screenshots for the design record. Pick the family whose x-height, stroke contrast, and proportion best harmonize.
- Document each selection with a one-line rationale in a code comment near the font import block in `index.html`.
- Add segmented Google Fonts `<link rel="stylesheet">` imports for each chosen family, using `display=swap` and weight ranges that match Inter's loaded weights (400, 500, 600, 700, 800, 900) where the family supports them.
- Update `--sans` chain in `tokens.css` to include the chosen non-Latin families before the system fallbacks.
- For **Hanifi Rohingya**: confirm Google Fonts availability at execution time. If available, add it. If not, leave a code comment documenting the fallback to system font as a known gap; do not block this chunk on it.
- Verify CSP `font-src` and `style-src` already permit `fonts.googleapis.com` and `fonts.gstatic.com`; no widening expected.

**Acceptance:**

1. Switch to one locale per script (sample list: `my`, `am`, `bn`, `ta`, `th`, `km`, `he`, `ckb`, `si`, `mr`) — every glyph renders, no tofu boxes.
2. Side-by-side with English UI on the same page (e.g., the `app_title` in the masthead vs a route-card), the non-Latin script reads as a coherent design partner to Inter — not as a stylistic mismatch.
3. Lighthouse performance score on the home page does not drop more than 2 points from pre-chunk baseline (font CSS is small; fonts themselves only download for the active locale).
4. CSP report-only logs show no font-related violations.

---

### Chunk 14 --- Continent picker SVGs (design)

**Files:** new `frontend/src/assets/continents/{africa,americas,asia,europe,middle-east,oceania}.svg`

**What to build:**

- 6 outline SVGs designed in this app's visual language. Stroke weight matches `--hairline`; stroke color uses `currentColor` so the picker can recolor based on light/dark/high-contrast mode.
- Normalized viewBox (e.g., `0 0 100 100`) so all 6 render at consistent visual weight in the same tile size.
- Vertex count simplified for crispness at 64px (mobile) — over-detailed coastlines turn to mush at small sizes.
- Middle East boundary: depict Arabian Peninsula + Iran + Anatolia + Levant. Document the boundary choice in a code comment at the top of the SVG so future contributors don't argue with it.

**Acceptance:**

1. Each SVG renders identically in stroke weight/style at 64px and 128px.
2. Visually balanced as a 2×3 or 3×2 grid (eye check — none of the 6 dominates the others through accidental weight or scale).
3. Renders correctly in light mode (charcoal stroke on cream), dark mode (cream stroke on charcoal — via `currentColor`), and high-contrast mode (no fill bleed).
4. No external library dependencies.

---

### Chunk 15 --- Continent picker UI

**Files:** [frontend/src/components/Masthead.jsx](../frontend/src/components/Masthead.jsx), [frontend/src/i18n.js](../frontend/src/i18n.js), [frontend/src/styles/tokens.css](../frontend/src/styles/tokens.css) or a new component file under `frontend/src/components/LanguagePicker/`

**What to build:**

- New `LanguagePicker` component implementing 2-step flow:
  - Step 1: 6-tile grid of continent SVGs. Each tile is a `<button>` with aria-label `t("continent_<id>")` and a tooltip showing the continent name in the active locale.
  - Step 2: scoped list of languages for the chosen continent, rendered as a vertical menu with each item showing the native name. Selecting one calls `i18n.changeLanguage(code)` and dismisses the picker.
  - Back affordance to return to the continent grid without selecting.
- Add `LANGUAGES_BY_CONTINENT` static map in `i18n.js` per the Scoping decision 4 assignment table.
- Add 6 new keys to `en.json` for continent labels: `continent_africa`, `continent_americas`, `continent_asia`, `continent_europe`, `continent_middle_east`, `continent_oceania`. Also add `continent_picker_back`, `continent_oceania_placeholder`. These get translated as part of a small follow-up `translate-missing.mjs` run for all 76 locales after this chunk.
- Feature flag: read `import.meta.env.VITE_CONTINENT_PICKER_ENABLED`. When `false`, render the existing flat `<select>` (current code). When `true`, render `LanguagePicker`.
- Keep state in `localStorage` under existing `cta_language` key — no schema change.
- Full keyboard navigation: Tab through continent tiles, Enter to enter, Esc to back out, arrow keys within the language list.
- Screen reader: announce both steps clearly. The continent grid is a `<menu>` of `<button>`s; the language list is a listbox or menu of options. Test with NVDA/VoiceOver.

**Acceptance:**

1. With flag off, behavior is identical to today's `<select>`.
2. With flag on, all 76 languages are reachable via continent → language. No language is orphaned.
3. Empty Oceania tile shows the "coming soon" placeholder when tapped.
4. Keyboard-only flow works: Tab to picker, Enter to open, Tab/arrow through tiles, Enter to drill in, Tab/arrow through languages, Enter to select.
5. Screen reader pass: NVDA reads the continent name on tile focus, then enters the language menu and reads each native name on focus. Verify on at least one RTL locale (e.g., Hebrew) that focus order remains logical.
6. Switching back to a previously-selected language preserves correctly across reload.
7. No regression in the existing language-switch flow used by deep-link URLs or programmatic `i18n.changeLanguage` calls.

---

### Chunk 16 --- Documentation + cleanup

**Files:** [README.md](../README.md), [docs/PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), this file ([docs/FEATURE_PLANS.md](FEATURE_PLANS.md)), [docs/archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md)

**What to build:**

- Update README language count from "22 languages" to "76 languages."
- Add a short README paragraph describing the continent picker.
- Update `PROJECT_CONTEXT.md` language count and any RTL count.
- Per the FEATURE_PLANS.md process at the top of this file, **delete this entry** from FEATURE_PLANS.md and add a corresponding summary entry to [docs/archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md) describing what shipped: 54 new locales, machine-translated badge, design-system-aligned non-Latin fonts, and the continent-first language picker.

**Acceptance:**

1. README and `PROJECT_CONTEXT.md` reflect 76-language reality.
2. This entry no longer appears in `FEATURE_PLANS.md`.
3. A summary entry exists in `FEATURE_HISTORY.md` with file pointers and ship date.
4. Feature Index in this file's header is updated to remove entry #3.

---

### Out of scope (followups, tracked separately)

- **First-class user feedback feature** — a settings-panel form / Slack webhook / Linear-issue-creating endpoint where users can submit translation corrections (or any feedback) without leaving the app. Day-one implementation uses a `mailto:` or GitHub Issues link via the `feedback_link_label` string. Promote to its own feature plan once translation feedback volume justifies the effort.
- **Self-hosting Noto Sans + chosen design-aligned fonts for SRI / CSP tightening** — flagged in [frontend/index.html](../frontend/index.html) as a long-term mitigation; not blocking this feature.
- **Native-speaker translation review program** — community workflow for soliciting and incorporating native speaker corrections, especially for the 8 low-resource locales. Depends on the user-feedback feature above.
- **Oceania locale rollout** — Tok Pisin, Māori, Sāmoan, ʻŌlelo Hawaiʻi, Tongan, Fijian. Track as a follow-up locale wave.
- **Per-locale translation memory / glossary** — durable fixed-translation list (e.g., neighborhood names, line names) so the translation script never paraphrases proper nouns. The existing `KEEP_ENGLISH` set is a proto-version; promote to a structured glossary once translation volume warrants.

---

## Standalone Features

---

### FEAT-011 --- Expand location autocomplete to cover all locations (street addresses + POIs)

**Type:** Bolt-On

**Status:** Scoped, decisions pending. **All design choices below are still under discussion** — do not start implementation until the open questions are resolved with the maintainer in a future session.

**User story / motivation:** As a rider, I want the origin/destination autocomplete to suggest *any* location I might want to travel to or from — specific street addresses (e.g. "1234 N Milwaukee Ave"), businesses and points of interest (e.g. "Wrigley Field", "Whole Foods Lincoln Park"), and individual bus stops at named intersections — not just the curated list of train stations, neighborhoods, and deduplicated bus stop names. Today, anything outside that curated list only resolves *after* form submission via Google Geocoding, which means the user gets no inline confirmation that the place they're typing is recognized.

**Current coverage (for context):**

- `/autocomplete` ([backend/main.py:1999-2036](../backend/main.py#L1999-L2036)) returns up to 8 suggestions from a static prefix index built at startup ([backend/main.py:312-358](../backend/main.py#L312-L358)).
- Three sources, in tier order: train station names → `NEIGHBORHOOD_COORDS` keys → bus stop names (deduped by name, so multiple stops sharing a name collapse to one).
- Free-form addresses are resolvable via Google Geocoding ([backend/gtfs_loader.py:644](../backend/gtfs_loader.py#L644)) on submit, but never autocompleted.
- The `GOOGLE_MAPS_API_KEY` env var is already wired up ([backend/.env.example](../backend/.env.example)).

**Acceptance criteria (provisional — subject to revision when decisions are made):**

- Typing partial street addresses biased to the Chicago bbox returns plausible address suggestions inline before submit.
- Typing well-known Chicago POIs (e.g. "Wrigley Field", "Art Institute", "Whole Foods …") returns matching suggestions, not just neighborhood-level fallbacks.
- Existing tiers (train stations, neighborhoods, bus stops) continue to rank above generic address/POI suggestions when both match — riders looking for a station should not have to scroll past a coffee shop with the same name.
- Suggestion `type` badges in the dropdown extend to cover the new categories (e.g. `address`, `poi`) so the UI distinguishes them visually. See [frontend/src/components/LocationInput.jsx:222-225](../frontend/src/components/LocationInput.jsx#L222-L225).
- The existing geocode rate-limit bucket continues to gate `/autocomplete` traffic; no new bypass paths.
- Selecting an address/POI suggestion resolves to coordinates without a second user-visible round-trip (either via `place_id` carried in the suggestion `value`, or via the existing `geocode_google` call on submit — TBD).
- Whatever third-party API is chosen, responses are cached server-side by lowercased query so that incremental typing (`"linc"` → `"lincol"` → `"lincoln"`) does not multiply outbound API calls.
- No API keys are exposed to the frontend — the frontend continues to hit only `/autocomplete`.

**Files likely touched:**

- `backend/main.py` (extend `/autocomplete` to merge static-index results with external suggestions; add response cache)
- `backend/gtfs_loader.py` (or a new `backend/places.py`) for the third-party API client and caching
- `backend/.env.example` (document any new env vars — e.g. `PLACES_API_KEY` if separate from `GOOGLE_MAPS_API_KEY`)
- `backend/tests/` (new tests covering merge ranking, cache behavior, rate-limit interaction)
- `frontend/src/components/LocationInput.jsx` (handle new suggestion `type` values, possibly carry `place_id` through to submit)
- `frontend/public/locales/*/translation.json` (new badge labels for `address` / `poi` types — 22+ languages)
- `frontend/src/App.css` (badge styling for new types if visually distinguished)

**Open questions (all still being decided — do not assume any answer below is final):**

1. **Provider choice.** Google Places Autocomplete (New) is the natural fit since the API key is already provisioned and Chicago bbox biasing is straightforward. Alternative: Nominatim (OSM) — free, but slower, rate-limited, and weaker on businesses. Mapbox Search is a third option. **No decision yet.**
2. **Cost tolerance.** Google Places Autocomplete is billed per session-token (or per request without one). At expected typing volume even with caching, this introduces a non-trivial recurring cost on what is currently a near-zero-cost typing path. Need to confirm the maintainer is OK with this before committing to Google. Cost ceiling / monthly budget cap to set?
3. **Session tokens vs. per-request billing.** Session tokens batch a typing session + final selection into one billable unit (cheaper if the user selects a result), but require the frontend to generate and pass a token per session. Worth the extra plumbing?
4. **Cache TTL.** 1h? 24h? Forever (with size cap)? Address validity drifts very slowly; POI names drift faster (businesses close). A static TTL is simplest; a per-source TTL is more accurate.
5. **Resolution path.** Carry `place_id` in suggestion `value` for an exact lookup on submit (avoids a re-geocode but means `value` is no longer a human-readable string the user can edit), OR keep `value` as the display label and re-geocode on submit (one extra API call, but `value` stays editable and the existing flow is preserved).
6. **Bus-stop coverage gaps.** Independent of the address/POI work: should we also de-dedupe bus stops so each individual stop at a named intersection is its own suggestion? This is orthogonal — could be its own FEAT — and may be worth splitting out.
7. **Ranking when external + internal results collide.** Tier 0–2 (train/neighborhood/bus) clearly outrank addresses. But what about a Places result for "Wrigley Field" vs. the neighborhood "Wrigleyville" — both tier-1-ish in user intent? Need a concrete merge rule.
8. **Privacy.** The frontend never sees the third-party API directly, but the backend forwards user typing to Google. Document this in `docs/PRIVACY.md` if/when shipped — typing is more sensitive than the existing IP-based geo lookup since it can include addresses the user may not yet have visited.
9. **Failure mode.** If the external API errors or rate-limits, do we (a) silently fall back to static-only suggestions, (b) surface a small inline indicator, or (c) something else?
10. **Should this be split into multiple FEATs?** Address autocomplete and POI autocomplete have different cost profiles (POIs are more expensive on most providers) and different resolution complexity. They may warrant separate sequential entries.

**When to revisit:** Next conversation where the maintainer wants to make the provider/cost decisions. Once those are settled, this entry should be tightened (acceptance criteria become firm, open questions collapse, possibly split into FEAT-011a/b) before invoking `/resolve-item`.

---
