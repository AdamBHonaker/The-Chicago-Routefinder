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

**Analytics Suite — Privacy-Preserving Reach & Engagement Metrics** (in document order):

1. ~~FEAT-001 — Sessions counter — **Bolt-On**~~ **Done 2026-05-04** — see [backend/sessions.py](../backend/sessions.py).
2. FEAT-002 — New vs returning visitors — **Bolt-On**
3. ~~FEAT-003 — Approximate geography from IP (city bucketing) — **Bolt-On**~~ **Done 2026-05-04** — see [backend/geography.py](../backend/geography.py).
4. ~~FEAT-004 — Hour-of-day distribution — **Bolt-On**~~ **Done 2026-05-04** — see [backend/hourly.py](../backend/hourly.py).
5. ~~FEAT-005 — Device class (mobile/tablet/desktop) — **Bolt-On**~~ **Done 2026-05-04** — see [backend/devices.py](../backend/devices.py).
6. FEAT-006 — Event tracking (named behavioral counters) — **Bolt-On**
7. FEAT-007 — Funnel completion — **Structural** (depends on FEAT-001 + FEAT-006)
8. ~~FEAT-008 — Referrer / traffic source — **Bolt-On**~~ **Done 2026-05-04** — see [backend/referrers.py](../backend/referrers.py).
9. FEAT-009 — Public stats dashboard — **Structural** (pulls from FEAT-001 through FEAT-008 endpoints; can ship incrementally). **v1 + Phase 2 panels done 2026-05-04** — `/stats` now surfaces DAU, Chicago-metro, sessions/bounce/duration, peak-hours histogram, device split, and traffic-source split. Remaining panels (FEAT-002 returning visitors, FEAT-006 events, FEAT-007 funnel) get appended as those features land. See [backend/public_stats.py](../backend/public_stats.py).

**Standalone Features** (not part of a chunked plan or the analytics suite):

- FEAT-011 — Expand location autocomplete to cover all locations (street addresses + POIs) — **Bolt-On**. Scoped, decisions pending.

Plus three considerations, **all resolved as of 2026-05-04**: third-party analytics (Plausible/Fathom) **rejected** — replaced by FEAT-009 on infrastructure we control; **DAU remains the privacy-respecting source-of-truth** (no third-party reconciliation needed since A was rejected); **GeoIP integration ships as FEAT-003**. The Considerations sections at the end of this doc are preserved as the audit trail for those decisions, not as open items.

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

---

## Feature TransferMarkers --- Intermediate transfer station marks on the map

### Overview

During an active trip (after the rider taps "Start Route"), render small editorial marks on the map at every point where the rider changes mode or vehicle: rail↔rail, rail↔bus, bus↔bus, walk→transit, and transit→walk. These markers are the missing wayfinding piece between the route polyline (where the trip goes) and the existing O/§/✦ markers (where it starts and ends). The polyline already communicates the path; what it does not show is *the moment the rider has to do something* — get off, walk to a different platform or corner, board a different vehicle. Transfer markers make those moments visually addressable on the map and tappable from the itinerary spine.

The previous design decision (2026-04-30, On-Map Symbols handoff) ruled these out as clutter. This feature reverses that decision but keeps the underlying concern in scope: markers render *only for the selected route*, *only after Start Route*, and *only at meaningful mode/vehicle transitions* — never as ambient stop dots. Combined with the editorial glyph language and tap-only labels, the result is a map that stays sparse during browsing and gains exactly-as-much detail as the rider needs during execution.

**Why it matters:** At Clark/Lake, four lines converge across two levels — knowing *which* leg of the itinerary corresponds to *which* platform is the difference between a smooth transfer and a missed train. At a bus↔bus corner where boarding and alighting stops sit on different sides of the intersection, a single dot at the alighting stop hides the fact that the rider has to cross. These are the exact moments the editorial language was missing.

**Type: Bolt-On** --- frontend-only. The backend already exposes everything needed (verified 2026-05-03; see Prerequisites).

**Status:** Chunks 1 & 2 complete (2026-05-04). Chunks 3 & 4 pending.
- ✅ **Chunk 1** — `frontend/src/utils/deriveTransferPoints.js` + `frontend/src/tests/deriveTransferPoints.test.js` (13 tests passing).
- ✅ **Chunk 2** — `frontend/src/components/markers/TransferMarker.jsx`, `frontend/src/components/markers/FootprintMarker.jsx`. 7 i18n keys (`transfer_marker_kicker`, `transfer_marker_aria`, `transfer_marker_aria_passed`, `footprint_marker_aria_walk_to_transit`, `footprint_marker_aria_walk_to_transit_passed`, `footprint_marker_aria_transit_to_walk`, `footprint_marker_aria_transit_to_walk_passed`) added to `en/translation.json`; non-English locales pending regeneration via `node scripts/translate-missing.mjs`.
- ⏳ **Chunk 3** — Mount markers in MapView via `useMapMarker`; new `useTransferConnectors` hook for dashed connector layers.
- ⏳ **Chunk 4** — Bidirectional spine↔map selection coupling; lift `selectedTransferId` to App.jsx.

Two minor deviations from spec that landed in Chunks 1–2:
1. Test file lives at `frontend/src/tests/deriveTransferPoints.test.js` (not `__tests__/`) — matches existing project convention.
2. Rail-leg detection imports `LINE_COLORS` from `frontend/src/constants.js` rather than `LINE_NAMES` from `lineColors.js` (the latter does not exist; `LINE_COLORS` keys `"Red Line"`-style match backend leg `line` values).

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
   - **Footprint suppression near O/D.** A footprint dot is suppressed when its coords are within ~30ft of the OriginMarker or DestinationMarker. In those cases the O/D marker carries the semantic load and a separate footprint dot would visually compete. Mid-trip footprint dots (walk legs *between* two transit legs, if any exist) are unaffected.

4. **Anchor and clustering rules.**
   - Rail↔rail: one marker per station, anchored at the station coords. Same-platform transfers (e.g., Red→Purple at Belmont) still get a marker — riders confirmed this is wanted, not redundant.
   - Bus↔bus where alighting and boarding stops are within ~30ft of each other (functionally same corner): one marker at the alighting stop, no connector line.
   - Bus↔bus where alighting and boarding stops are 30ft–~1 city block apart: one marker at the alighting stop, plus a short **dashed connector line** to the boarding stop. **Connector dash matches the walking-leg dash convention exactly** (`strokeDasharray="3 4"`, `strokeWidth=2`, `stroke=--ink`, `opacity=0.8` — see [schematic-map.jsx:147-151](../Design%20Documents/Chicago%20Routefinder%20-%20Design%20System/designs/schematic-map.jsx#L147-L151)). Rationale: the design system has a single dashed-line idiom meaning "you walk this," and a 30ft–1block stop-to-stop transfer is semantically a short walk. Inventing a second dash variant would dilute a clean system rule for no semantic gain.
   - Bus↔bus where stops are >1 city block apart: backend should already insert a real `WalkLeg` between them. In that case, no transfer marker is drawn at the alighting stop — the standard transit→walk and walk→transit footprint dots cover both ends. **Verify this assumption holds during Chunk 1** (it depends on transit-graph leg construction).
   - Rail↔bus where the bus stop is at or directly adjacent to the station entrance (≤30ft): one marker at the rail station, no connector line.
   - Rail↔bus where the bus stop is across the street from the station entrance (30ft–1 block): same dashed-connector rule as bus↔bus split stops.
   - Rail↔bus where the bus stop is >1 city block from the station: backend should already insert a `WalkLeg`; same as the bus↔bus far-apart case.

5. **Label and tap-to-select.** Tap/click only. No always-on station name labels — at downtown super-stations (Clark/Lake, State/Lake, Jackson) always-on labels would stack and become illegible. Tapping a marker performs two actions atomically: (a) reveals a small flag callout in the existing OriginMarker label idiom (Inter caps kicker + Fraunces-italic place name), and (b) puts the marker in selected-state (see Scoping #7, #8). The label and selected-state are bound — they appear and dismiss together. Dismissal sources: tapping the same marker again, tapping a different marker, tapping a spine row that toggles selection off, tapping empty map, ending the trip, or running a new search.

6. **Z-order**, bottom to top:
   1. Route polyline.
   2. Regular stop dots (if/when added — currently none).
   3. Transfer markers + footprint dots.
   4. Origin and Destination markers.
   5. LivePositionMarker.

7. **Spine ↔ map selection coupling — bidirectional.** A single `selectedTransferId` is the source of truth and can be set from either side:
   - **From the spine:** Tapping a transfer-point row in RouteCard sets `selectedTransferId` and triggers `map.flyTo({ center: descriptor.coords, duration: 400 })`. The marker enters selected-state and shows its tap-label.
   - **From the map:** Tapping a transfer marker sets `selectedTransferId`, shows the marker's tap-label, and puts the marker in selected-state. **No `flyTo`** — the marker is already on-screen if the rider just tapped it. The spine row's `aria-pressed` updates to reflect the selection.

   Either source dismisses identically (see Scoping #5). What remains deferred to v2 is **map → spine scrolling** — automatically scrolling the corresponding spine row into view when a marker is tapped. This is only meaningful pre-trip when the spine could be off-screen, but markers don't render pre-trip; in `tripActive` mode the panel collapses to a single card with the spine fully visible. See "Deferred to v2" below.

8. **Selected-state visual.** A third concentric outline offset 3px outside the marker's existing outer rule, drawn at `strokeWidth=0.75` in **`--ink`** (not rust). The Routefinder design system's anatomy rules ([d2-system.jsx:421-424](../Design%20Documents/Chicago%20Routefinder%20-%20Design%20System/designs/d2-system.jsx#L421-L424)) reserve rust *exclusively* for the live-position ring: *"Origin and destination stay in pure ink — they aren't consequences, they're coordinates."* Transfer markers are coordinates, not consequences, so they stay in ink. State is communicated through layered linework (more rules, different weights), not through accent color. No animation — pulse would be the only animated element in the entire system and would clash with the editorial aesthetic.

9. **Passed-state visual.** As the LivePositionMarker passes a transfer point during a live trip (i.e., when `activeLegIndex` advances past the leg the marker terminates), the marker is "stamped through" — a punched-ticket idiom in `--ink`. Per-glyph specs (Chunk 2 is the authoritative SVG reference):
   - **TransferMarker:** prepend an outer ring at `r=9` (`strokeWidth=1`, `--ink`), drawn outside the existing 2px outer rule at `r=7`. Fill the area inside the inset hairline with `--ink`. The center `×` glyph re-renders in `--paper` for legibility on the ink fill.
   - **FootprintMarker:** prepend an outer ring at `r=4` (`strokeWidth=1`, `--ink`), tracing the edge of the existing unstroked paper backing. The interior `r=2.5` ink dot already provides the punched-fill appearance at this scale; no additional fill is added.
   - In both glyphs, all original strokes/dots remain — the marker's identity is preserved.
   - Distinguishable from selected-state (also `--ink` + outer ring) by the interior fill: **passed = filled, selected = hollow**. The two states can stack — a passed marker that gets selected shows both the passed fill and an additional selected outer ring at `r=10` on TransferMarker (`r=6` on FootprintMarker).

10. **Backend.** Confirmed sufficient — no API or backend changes. All transfer points are derivable from adjacent leg pairs in the existing `/recommend` response.

---

### Deferred to v2

**Map → spine auto-scroll.** Tapping a marker on the map already sets `selectedTransferId` and shows the spine row's `aria-pressed` state in v1 (see Scoping #7). What's deferred is **automatically scrolling the corresponding spine row into view** when the marker is tapped. The implementation requires per-row refs in RouteCard's spine and `scrollIntoView()` logic. Deferred because: (a) the natural rider workflow is "read itinerary → look at map," not the reverse; (b) during `tripActive`, the panel collapses to a single selected card with the spine fully visible — there's nothing to scroll to; (c) the work mostly pays off in pre-trip browsing, but markers don't render pre-trip. Re-add to active scope if post-launch feedback shows riders tapping markers and expecting the spine to scroll.

**Differentiated glyphs per transit-mode pair.** All three of (rail↔rail, rail↔bus, bus↔bus) share one glyph in v1. Visually distinguishing them (e.g., different center marks) is over-engineering until users complain.

**Station name translation.** v1 leaves CTA station names in their canonical English form (proper nouns, matching how OriginMarker/DestinationMarker handle their `label` prop today). A future feature could translate or transliterate station names per locale — e.g., providing pinyin/zhuyin for Chinese readers, Cyrillic transliterations for Russian readers, or localized common-usage names where they exist. This requires a station-name dictionary keyed by `mapid` per locale and would touch tap-labels, aria-labels, and any station-name strings rendered in RouteCard. Defer until a real i18n localization pass for non-English locales is being scoped — translating proper nouns out-of-context risks worse legibility than leaving them in their original form.

---

### Chunk 1 --- Transfer-point derivation utility (frontend, pure)

**Files:** `frontend/src/utils/deriveTransferPoints.js` (new), `frontend/src/utils/__tests__/deriveTransferPoints.test.js` (new).

**What to build:**

- A pure function `deriveTransferPoints(route, { originCoords, destinationCoords })` that takes a route object (the shape returned by `/recommend`) plus the trip's origin/destination coordinates, and returns an array of transfer-point descriptors:

  ```js
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
- **O/D suppression pass.** Before returning, filter out any `walk-transit` or `transit-walk` descriptor whose `coords` are within ~30ft (~9m haversine) of `originCoords` or `destinationCoords`. The OriginMarker and DestinationMarker carry the semantic load at trip endpoints; a footprint dot stacked on top would visually compete. Mid-trip footprint descriptors (those not adjacent to O/D) are unaffected.

**Implementation specifics:**

- `LINE_NAMES` (rail line codes) is already in [frontend/src/lineColors.js](frontend/src/lineColors.js) — import it. Don't duplicate the list.
- Station-name resolution: prefer `legs[i].to` (the alighting station name string) for the marker label; fall back to `legs[i+1].from` if the former is missing.
- The function must be pure and synchronous. No fetching, no React, no map references. It's the testable kernel of this whole feature.

**Acceptance criteria:**

1. Unit tests cover all five transition types, the three bus↔bus stop-distance regimes (same-corner, split-stop, far-apart-with-walkleg), and the same-platform same-stop rail transfer (which still emits a marker).
2. A route with zero transfers (single TransitLeg sandwiched between two WalkLegs) where the WalkLegs start/end *more than* 30ft from the trip endpoints returns exactly two descriptors: one `walk-transit`, one `transit-walk`. When those WalkLegs start/end *within* 30ft of `originCoords`/`destinationCoords` (the typical case — backend snaps trip endpoints to the rider's input), the O/D suppression pass returns zero descriptors.
3. A walk-only route (no TransitLegs) returns an empty array.
4. The function does not mutate its input.
5. A unit test covers the O/D suppression boundary: a footprint at exactly 9m from `originCoords` is suppressed; one at 15m is retained.

---

### Chunk 2 --- Marker components (TransferMarker, FootprintMarker)

**Files:** `frontend/src/components/markers/TransferMarker.jsx` (new), `frontend/src/components/markers/FootprintMarker.jsx` (new).

**What to build:**

- `<TransferMarker />` — the editorial double-ruled circle. Props: `label?: string`, `state?: "default" | "selected" | "passed"`, `paperColor`, `inkColor`, `muteColor`. **No `accentColor` prop** — the design system reserves rust for the live-position ring only ([d2-system.jsx:421-424](../Design%20Documents/Chicago%20Routefinder%20-%20Design%20System/designs/d2-system.jsx#L421-L424)); selected/passed state both use `inkColor`. SVG structure mirroring [OriginMarker.jsx](frontend/src/components/markers/OriginMarker.jsx):
  - Paper backing `<circle r=8>`.
  - Outer ink ring `<circle r=7 strokeWidth=2 stroke={inkColor} fill="none">`.
  - Inset hairline `<circle r=5 strokeWidth=0.75 stroke={inkColor} fill="none">`.
  - Center `×` glyph as `<text>` in Fraunces-italic, fontSize=6, textAnchor=middle, fontWeight=700.
  - When `state="passed"`: prepend a `<circle r=9 strokeWidth=1 stroke={inkColor} fill="none">` (the punched-ticket outer ring) and add an inner `<circle r=5 fill={inkColor}>` *behind* the inset hairline so the area inside the hairline reads as ink-filled. The center `×` glyph re-renders with `fill={paperColor}` for legibility on the ink fill.
  - When `state="selected"`: add an outer `<circle r=10 strokeWidth=0.75 stroke={inkColor} fill="none">` *outside* any passed-state ring. (Selected and passed can stack — a rider can tap the spine row for a transfer they've already passed; the marker shows both treatments.)
  - Tap-label rendering: same idiom as OriginMarker — Inter caps kicker + Fraunces-italic station name. Only shown when `label` prop is set. **All user-facing strings are i18n-wrapped** — see Implementation specifics below.
- `<FootprintMarker />` — minimal walk-transition mark. Props: `label?: string`, `state?: "default" | "selected" | "passed"`, same color props (no `accentColor`). SVG:
  - Paper backing `<circle r=4>`.
  - Ink dot `<circle r=2.5 fill={inkColor}>`.
  - When `state="passed"`: prepend a `<circle r=4 strokeWidth=1 stroke={inkColor} fill="none">` outer ring; the existing `r=2.5` ink dot already fills the interior, so no fill change needed (the dot itself reads as the punched fill at this scale).
  - When `state="selected"`: add `<circle r=6 strokeWidth=0.75 stroke={inkColor} fill="none">` *outside* any passed-state ring.
  - No center glyph, no kicker; the tap-label (when present) is just the Fraunces-italic station name in the OriginMarker flag idiom.

**Implementation specifics:**

- Match the `viewBox="0 0 W H" overflow="visible" display="block"` pattern from OriginMarker exactly so MapView's marker mounting (which uses `anchor: "center"`) places these at the correct pixel.
- Default color values: `paperColor="#f4ead5"`, `inkColor="#1a1510"`, `muteColor="#8a7a60"`. No rust default — see Scoping #8 (rust is reserved for live-position).
- Both components must be `React.memo`-able — they will re-render when state changes during a live trip.
- **i18n.** All user-facing strings go through `react-i18next`'s `useTranslation()`:
  - The TransferMarker's caps kicker is `t("transfer_marker_kicker")` (English source: `"TRANSFER"`).
  - Tap-label station names come from leg data (`stationName` on the descriptor) and are not translated — CTA station names are proper nouns and are left in their canonical form, matching how OriginMarker/DestinationMarker handle their `label` prop.
  - `aria-label` for each marker is built from a translated template, e.g. `t("transfer_marker_aria", { station: stationName })` → `"Transfer at {{station}}"`. Same pattern for `t("footprint_marker_aria_walk_to_transit", { station })` and `t("footprint_marker_aria_transit_to_walk", { station })`. Add the new keys to [frontend/public/locales/en/translation.json](frontend/public/locales/en/translation.json) and any other locale files present.
  - **State-change announcements for screen readers.** When a marker transitions to `passed` or `selected` state, the `aria-label` should reflect the state — e.g. `t("transfer_marker_aria_passed", { station })` → `"Passed transfer at {{station}}"`. Avoid `aria-live` regions (would announce on every state tick); state changes are conveyed via the marker's own updated `aria-label`.

**Acceptance criteria:**

1. Visual review at 1× and 2× DPR confirms the marker reads cleanly on tile backgrounds matching `--paper`, lake blue, and street grey.
2. The three states (`default`, `selected`, `passed`) render distinctly without DOM remounting. Passed + selected stack correctly (both treatments visible simultaneously).
3. Tap-label appears flush against the marker (no gap or overlap) and its kicker matches OriginMarker's letter-spacing/font-weight.
4. No console warnings under React StrictMode.
5. All translation keys (`transfer_marker_kicker`, `transfer_marker_aria`, `transfer_marker_aria_passed`, `footprint_marker_aria_walk_to_transit`, `footprint_marker_aria_transit_to_walk`, plus passed variants) exist in every locale file under `frontend/public/locales/`. Missing-key warnings would surface in dev console — none should appear.
6. Selected and passed states use `--ink` only; no `--rust` appears anywhere in either component's rendered SVG (grep verification).

---

### Chunk 3 --- Mount markers in MapView, gated on tripActive + selectedRoute

**Files:** [frontend/src/MapView.jsx](frontend/src/MapView.jsx) (modify).

**What to build:**

- Inside MapView, mount transfer markers using the **declarative `useMapMarker` hook** ([frontend/src/hooks/useMapMarker.jsx](../frontend/src/hooks/useMapMarker.jsx)) — the same pattern Origin/Destination markers now use. Because the hook can't be called in a loop, factor a small `<TransferMarker descriptor={...} state={...} />` child component that wraps a single `useMapMarker(map, TransferGlyph, props, lngLat)` call, then `route && tripActive && transferPoints.map(d => <TransferMarker key=... />)` from MapView.
- For the dashed connector lines (line/source layers, not DOM markers), add a parallel hook **`useTransferConnectors(map, descriptors)`** at [frontend/src/hooks/](../frontend/src/hooks/) that mirrors [useRouteLayers.js](../frontend/src/hooks/useRouteLayers.js): tracks layer/source IDs in refs, clears + re-renders on dep change, gates on `map.isStyleLoaded()`. Do not export `_trackSource` / `_trackLayer` from useRouteLayers — duplicate the helpers inside the new hook so each owns its own tracked-IDs lifecycle.
- Compute `state` per descriptor each render: `state="passed"` when `activeLegIndex > descriptor.alightingLegIndex` (the rider is past this transfer); otherwise `"default"`. Pass through props to the marker component — the hook re-renders the React subtree on prop change. Selected-state is owned by Chunk 4.
- Connector layer spec: GeoJSON LineString from `descriptor.coords` to `descriptor.boardingCoords`. **Paint must match the existing walking-leg dashed-line styling exactly** — `line-dasharray: [3, 4]`, `line-width: 2`, `line-color: var(--ink hex)`, `line-opacity: 0.8`. Reuse whatever paint object the existing walking-leg layer already defines (likely in [useRouteLayers.js](../frontend/src/hooks/useRouteLayers.js)) — do not duplicate or fork the spec; if needed, lift it to a shared constant. Z-order: above route polyline, below markers (markers are DOM, always above canvas layers).
- Set marker z-order via the maplibre `Marker` element's container `style.zIndex`: footprint/transfer markers below O/D, above polyline. Confirm O/D markers' z-index and use a value below them. Pass `className` via the `useMapMarker` `options` arg so a per-marker stylesheet rule can set z-index.

**Implementation specifics:**

- The `tripActive` and `activeLegIndex` props are already wired through MapView ([MapView.jsx:56-57](frontend/src/MapView.jsx#L56-L57)) and [App.jsx](frontend/src/App.jsx). No new props.
- Cleanup is handled by `useMapMarker` automatically — when `tripActive` flips false, the parent stops rendering the `<TransferMarker>` children, which unmounts the hooks and tears down the maplibre markers + ReactDOM roots. The connector hook clears tracked layers on dep change. Manual ref-based cleanup is no longer needed.
- StrictMode double-mount: handled inside `useMapMarker` via standard effect cleanup (the hook removes the marker on cleanup before the second mount creates a new one). The `setTimeout(0)` workaround is **only** needed for the WebGL map init in MapView — it does **not** apply to markers. Verify by toggling `tripActive` rapidly in dev — no duplicate markers should appear.
- For the rare case where a transfer marker's prop must update synchronously with a non-reactive ref (none expected for transfer markers — `state` is reactive), `useMapMarker.jsx` exports imperative `mountMarker`/`removeMarker` escape hatches; the live-position marker uses these. Don't reach for them unless a frame of lag in prop updates is actually a problem.

**Acceptance criteria:**

1. Tapping Start Route on a multi-leg itinerary mounts one marker per derived transfer point, at correct coordinates.
2. Ending the trip, deselecting the route, or running a new search clears all transfer markers and connector lines — no orphan DOM nodes (verify in the React DevTools Components panel).
3. As the rider's `activeLegIndex` advances, passed transfers visually transition to the passed-state ring without remount flicker.
4. Bus↔bus split-stop transfers render exactly one marker plus one dashed connector. Same-corner bus↔bus transfers render exactly one marker, no connector. **Connector dashes are visually indistinguishable from walking-leg dashes** (same dasharray, weight, color, opacity) — both clearly distinguishable from the solid colored route polyline.
5. Walk→transit and transit→walk render footprint dots, not transfer glyphs. Footprints near O/D (within ~30ft) are suppressed per Scoping #3.

---

### Chunk 4 --- Bidirectional selection coupling (spine ↔ map)

**Files:** [frontend/src/components/RouteCard.jsx](frontend/src/components/RouteCard.jsx) (modify), [frontend/src/MapView.jsx](frontend/src/MapView.jsx) (modify), [frontend/src/App.jsx](frontend/src/App.jsx) (modify — to host the `selectedTransferId` state).

**What to build:**

- **Shared state.** Lift `selectedTransferId` to App.jsx (alongside `route` and `tripActive`). Format: `"${alightingLegIndex}-${boardingLegIndex}"`. Pass down to both RouteCard (so spine rows can read + write it) and MapView (so markers can read + write it).
- **Spine source — RouteCard.** The existing leg-spine rows ([RouteCard.jsx:62, 145](frontend/src/components/RouteCard.jsx#L62)) become tappable when `tripActive === true` *and* the row corresponds to a transfer point (i.e., its leg-pair appears in `deriveTransferPoints(route)`). On tap:
  - If the row's transfer ID equals current `selectedTransferId` → clear `selectedTransferId` (toggle off).
  - Otherwise → set `selectedTransferId` to this row's ID. MapView reacts by flying to the marker and rendering it in selected-state with its tap-label visible.
- **Map source — TransferMarker / FootprintMarker.** Add an `onClick` to each rendered marker (via the wrapper component that calls `useMapMarker`). On tap:
  - If the marker's transfer ID equals current `selectedTransferId` → clear `selectedTransferId` (toggle off).
  - Otherwise → set `selectedTransferId` to this marker's ID. **No `flyTo`** — the rider just tapped this marker, so it's already on-screen.
  - The marker's tap-label visibility is driven entirely by `selectedTransferId === thisMarker.id`. No separate "label visible" state — selected-state and label-visible are the same thing.
- **MapView selection effect.** When `selectedTransferId` changes:
  - Find the matching descriptor in the latest `deriveTransferPoints(route)` output.
  - If the change came from the spine (or App-level reset) and the marker is off-screen, `map.flyTo({ center: descriptor.coords, duration: 400 })`. Skip `flyTo` if the marker's coords are within the current viewport with a small inset (the marker source was probably the marker itself, or it's already visible).
  - Re-render the matching marker with `state="selected"` (which renders the tap-label per Chunk 2). All other markers render in their default-or-passed state.
- **Dismissal sources** (all clear `selectedTransferId` to `null`): toggle on the same source (spine row or marker), trip ends, route deselected, new search runs, **tap on empty map** (add a `map.on("click", ...)` handler that clears `selectedTransferId` if the click target is *not* a marker).

**Implementation specifics:**

- The leg-spine currently has `aria-hidden="true"` ([RouteCard.jsx:62](frontend/src/components/RouteCard.jsx#L62)) since it's decorative. When making transfer rows interactive during `tripActive`, remove `aria-hidden` *only on rows that are tappable* and add `role="button"` + `aria-pressed={transferId === selectedTransferId}`. Mid-leg rows (rows not corresponding to a transfer point) stay `aria-hidden="true"` and non-interactive.
- Skip-on-screen check: implement via `map.getBounds().contains(coords)` with a small inset (~10% of viewport). Avoid jittery pans on rapid spine taps.
- Marker `onClick` must `stopPropagation` to prevent the empty-map click handler from immediately clearing the selection that was just set.
- Selection persists across passed-state transitions: if the rider has selected a marker and then `activeLegIndex` advances past it, the marker shows both selected + passed treatments simultaneously (Chunk 2 spec already covers this).
- All user-facing text (spine row labels, marker tap-labels, aria-pressed states) is i18n-wrapped per Chunk 2 conventions. Add any new keys (e.g., `t("transfer_row_aria_pressed", { station })` if needed beyond the existing marker keys) to all locale files.

**Acceptance criteria:**

1. Tapping a transfer-point row in the active trip's spine sets selection: marker pans into view if needed, renders in selected-state, shows its tap-label, and the spine row's `aria-pressed` becomes `"true"`.
2. Tapping a transfer marker on the map sets selection: marker renders in selected-state, shows its tap-label, the spine row's `aria-pressed` becomes `"true"`, **no map pan occurs**.
3. Tapping the same source again (spine row or marker) clears selection: tap-label disappears, selected-state ring disappears, no map pan.
4. Tapping a different transfer row or marker switches selection: previous marker de-selects, new marker selects (with `flyTo` only when the source is the spine and the new marker is off-screen).
5. Tapping empty map clears any selection.
6. Ending the trip, deselecting the route, or running a new search clears any selection.
7. Mid-leg spine rows (rows that don't correspond to a transfer point) are not focusable/tappable and remain `aria-hidden="true"`.
8. Keyboard navigation: tab order through transfer rows works, Enter/Space activates. Markers themselves are reached via map keyboard navigation only if maplibre-gl supports it; otherwise the spine is the keyboard-accessible entry point.
9. A passed marker that's selected shows both treatments simultaneously (passed fill + selected outer ring); de-selecting reverts to passed-only.
10. Marker `onClick` does not propagate to the empty-map handler — selecting a marker does not immediately clear the selection.

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

## Analytics Suite — Privacy-Preserving Reach & Engagement Metrics

### Overview

Eight bolt-on features that expand the existing DAU counter into an advertiser-ready reach + engagement dashboard, **without compromising the privacy-first stance**. All eight follow the same hard rules:

- **No persistent cross-day user identifiers** (the one borderline exception — FEAT-002's Bloom filter — is explicitly flagged in its scope).
- **No fingerprinting** of any kind (canvas, fonts, audio, WebGL).
- **No third-party tracking scripts.** Third-party analytics is treated separately as Consideration A below.
- **Aggregate-only storage where possible.** Per-user state lives in memory and is discarded at session/day boundaries.
- **Hash any per-user identifiers with the daily-rotating salt** already used in [backend/dau.py](../backend/dau.py).
- **Privacy implications must be documented per feature**, both inline in the module docstring and in [docs/PRIVACY.md](PRIVACY.md) (or `README.md` if no privacy doc exists yet).
- **Maintenance implications must be documented per feature.** Because this suite is being built in-house specifically to avoid the recurring cost and vendor risk of a third-party analytics tool (see Consideration A below), each feature must ship with detailed, current documentation of every expected ongoing maintenance task — dependency updates (`geoip2`, `ua-parser`, chart libraries), DB refreshes (GeoLite2 monthly cadence, search/social hostname lists), threshold and sizing decisions that need revisiting as DAU grows (Bloom filter sizing, "Other" bucket cutoff, rate limits), salt-rotation expectations, and any operational alarms. This documentation lives inline in the module docstring **and** is consolidated in a shared `docs/ANALYTICS_MAINTENANCE.md` (created with the first feature; appended to as each subsequent feature lands), so the entire suite is supportable on an ongoing basis without re-deriving each module's quirks from code. A feature is not "done" until its maintenance section is written.

The features can mostly be shipped independently. FEAT-007 (funnel) is the only one with hard dependencies (FEAT-001 + FEAT-006). FEAT-009 (public dashboard) reads from the others' endpoints and can ship incrementally as panels become available.

### Recommended build order

The numbering of FEAT-001 through FEAT-009 is **document order, not build order** — don't follow it mechanically. Build in commercial-impact phases, each phase ending at a point where the public dashboard is independently pitchable to a local advertiser, so the project can pause between phases without leaving a half-finished commercial story.

**Phase 1 — Differentiated stat + minimum viable dashboard.** ✅ **Done 2026-05-04.**

1. ~~**FEAT-003** (Geography). The "X% Chicago metro" number is the suite's differentiated commercial claim and is unavailable from any third-party tool. This is why it's first, even though numerical order would push it third.~~ **Done 2026-05-04** — see [backend/geography.py](../backend/geography.py).
2. ~~**FEAT-009 v1** — minimal `/stats` page with DAU + Chicago-metro panels only. Establishes the public dashboard surface and gives an immediate artifact to send to advertisers.~~ **Done 2026-05-04** — see [backend/public_stats.py](../backend/public_stats.py); page at `/stats`.

*Pitchable after Phase 1: Chicago-metro reach + DAU, on infrastructure we control.* **Live as of 2026-05-04.**

**Phase 2 — Engagement basics.** ✅ **Done 2026-05-04.**

3. ~~**FEAT-001** (Sessions). Foundational — supplies the `sessionId` cookie that FEAT-006 uses and is a hard prerequisite for FEAT-007.~~ **Done 2026-05-04** — see [backend/sessions.py](../backend/sessions.py).
4. ~~**FEAT-004** (Hour-of-day), **FEAT-005** (Device class), **FEAT-008** (Referrers). All small middleware extensions on the same code path; batch them in any internal order.~~ **Done 2026-05-04** — see [backend/hourly.py](../backend/hourly.py), [backend/devices.py](../backend/devices.py), [backend/referrers.py](../backend/referrers.py). All four are wired through a shared `_analytics_middleware` in [backend/main.py](../backend/main.py) on `/ping` and `/recommend`.

*Pitchable after Phase 2: sessions, bounce, duration, peak hours, mobile-first split, traffic sources.* **Live as of 2026-05-04 at `/stats`.**

**Phase 3 — Headline engagement metric.**

5. **FEAT-006** (Events). Bigger feature; requires frontend `track()` instrumentation at multiple call sites.
6. **FEAT-007** (Funnel). Depends on FEAT-001 + FEAT-006. Produces the "X% of sessions reach a result" number, which is the single engagement metric advertisers care most about.

> **Reminder:** As each Phase 3 feature lands, **append a corresponding panel to FEAT-009** before considering the feature complete. The phase is not done until the dashboard surfaces event volumes and the funnel chart — the funnel panel is the headline number for advertiser pitches and must be visible on `/stats`.

*Pitchable after Phase 3: full engagement story with funnel completion.*

**Phase 4 — Retention (gated on an explicit privacy decision).**

7. **FEAT-002** (New vs returning). The only feature with an unresolved privacy concern — the cross-day Bloom filter is flagged in its own scope as "confirm acceptable before building." Do not start until that confirmation is given. If the answer is no, the feature is dropped without affecting any other.

> **Reminder:** If FEAT-002 is built, **append a new-vs-returning panel to FEAT-009** before considering the feature complete. If FEAT-002 is dropped, lock FEAT-009 at its post-Phase-3 state and note the deliberate omission in the dashboard footer (so the absence is a recorded privacy decision, not an oversight).

*Pitchable after Phase 4: full retention story (or final dashboard ships without it).*

---

### FEAT-001 --- Sessions counter

**Status:** ✅ Done 2026-05-04. See [backend/sessions.py](../backend/sessions.py), [backend/tests/test_sessions.py](../backend/tests/test_sessions.py), [docs/PRIVACY.md](PRIVACY.md), [docs/ANALYTICS_MAINTENANCE.md](ANALYTICS_MAINTENANCE.md). Resolution recorded in [docs/archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md). Decisions baked in: bounce = fewer than 2 `/recommend` requests; idle timeout = 30 min; `DAILY_SALT` reused (no separate `SESSION_SALT`); session end via server-side idle timeout, not frontend `beforeunload`.

**Type:** Bolt-On

**User story / motivation:** As the site owner, I want to know how many *sessions* (not just unique IPs) hit the app per day, plus average session length and bounce rate, so I can quote engagement metrics to potential advertisers without compromising the existing privacy-first stance.

**Acceptance criteria:**

- Middleware records session start (first request from a new sessionId) and session end (idle timeout / explicit close).
- Session ID is a short-lived random token (UUID v4), set in an `httpOnly` `Secure` `SameSite=Lax` cookie with a 30-min sliding TTL. Not persisted across days; cookie expires server-side and client-side at midnight Chicago time at the latest.
- Server stores only an aggregate-per-day record: `{date, sessions: int, total_duration_seconds: int, bounces: int}`. No per-session row. Sessions/day, avg session length, and bounce rate are derived from those three numbers.
- Bounce = a session that recorded only one `/recommend` request. Definition documented in the privacy section.
- New admin endpoint `GET /admin/sessions` (token-protected like `/admin/dau`) returns the daily aggregates.
- New CLI script `backend/scripts/check_sessions.py` mirroring `check_dau.py`.
- Privacy section (in docstring + `docs/PRIVACY.md` or `README.md`) explicitly states: no PII, no cross-day correlation, sessionId hashed with daily-rotating salt before any internal logging, cookie cleared at end of Chicago day.

**Files likely touched:**

- `backend/main.py` (new middleware + admin endpoint)
- `backend/sessions.py` (new — mirrors `dau.py` structure)
- `backend/scripts/check_sessions.py` (new)
- `backend/tests/test_sessions.py` (new)
- `backend/.env.example` (document the session salt env var if separate from `DAILY_SALT`)
- `frontend/src/api.js` (or wherever fetch is configured) — ensure `credentials: "include"` on requests
- `README.md` and/or new `docs/PRIVACY.md` (privacy implications section)

**Open questions:**

- Reuse the existing `DAILY_SALT` for session-ID hashing, or introduce a separate `SESSION_SALT`? Reuse keeps secret-management simple but couples two systems' rotation cadence.
- Bounce definition: "only one `/recommend` request" or also "session length < 10s"? Different definitions yield different industry-comparable numbers.
- Does "session end" need an explicit `beforeunload` ping from the frontend, or is server-side idle timeout (30 min after last request) sufficient? Idle-timeout is simpler but inflates avg session length by ~30 min for the last visit.

---

### FEAT-002 --- New vs returning visitors

**Type:** Bolt-On

**User story / motivation:** As the site owner, I want to know what percentage of visitors come back across multiple days, so I can prove stickiness/retention to advertisers.

**Acceptance criteria:**

- A 90-day random opaque ID is set in an `httpOnly` `Secure` `SameSite=Lax` cookie (`returnIdRaw`). The raw value never reaches application code beyond the middleware that hashes it.
- Server hashes `returnIdRaw` with the existing daily-rotating salt before any storage or comparison. The hashed value is the only thing stored.
- Daily aggregate: `{date, new: int, returning: int}`. "Returning" = the hashed-with-today's-salt ID was probably seen on at least one of the previous N days.
- Implementation note: since the salt rotates, naive lookup fails; instead, store a small **rolling 90-day Bloom filter** of yesterday's hashes (re-hashed with each new day's salt). The Bloom filter is the only persistent cross-day artifact.
- Bloom filter false-positive rate documented (target ≤1%, sized for expected DAU growth).
- Admin endpoint `GET /admin/retention` returns daily aggregates.
- No raw IDs are persisted, only the daily-keyed Bloom filter and aggregate counts.
- Privacy section explicitly addresses the tradeoff: this *does* introduce limited cross-day correlation (the Bloom filter), but only in aggregate — you can ask "is this hash possibly in the set?" not "who is this user."

**Files likely touched:**

- `backend/main.py` (middleware extension)
- `backend/retention.py` (new)
- `backend/scripts/check_retention.py` (new)
- `backend/tests/test_retention.py` (new)
- `frontend/src/api.js` (cookie handling)
- `docs/PRIVACY.md` and `README.md`

**Open questions:**

- The Bloom filter is a meaningful privacy compromise relative to the rest of the stack. Confirm acceptable before building. Alternative: skip this feature entirely and rely on Consideration A (Plausible/Fathom) for retention metrics — they handle returning-user math without us holding the cross-day artifact.
- Does the `returnIdRaw` cookie trigger GDPR/CCPA disclosure requirements, even though it's opaque? Likely yes if EU traffic exists. Defer until EU traffic is non-trivial?
- 90 days is industry-standard for "returning user." Should we use 30 days for tighter retention reporting and a smaller filter footprint?

---

### FEAT-003 --- Approximate geography from IP

**Status:** ✅ Done 2026-05-04. See [backend/geography.py](../backend/geography.py), [backend/tests/test_geography.py](../backend/tests/test_geography.py), [docs/PRIVACY.md](PRIVACY.md), [docs/ANALYTICS_MAINTENANCE.md](ANALYTICS_MAINTENANCE.md). Resolution recorded in [docs/archive/RESOLVED_HISTORY.md](archive/RESOLVED_HISTORY.md).

**Type:** Bolt-On

**User story / motivation:** As the site owner, I want to prove "X% of traffic is Chicago metro" to local advertisers, since that hyperlocal alignment is the app's primary commercial differentiator. (Cross-reference Consideration C below — this feature *is* the implementation of that exploration item.)

**Acceptance criteria:**

- Server-side GeoIP lookup using MaxMind **GeoLite2-City** (free, attribution required). Library: `geoip2` Python SDK.
- IP-to-city resolution happens **once per request, in-memory only**. No mapping of IP → city is persisted; only the per-day city counter is.
- Daily aggregate: `{date, cities: {"Chicago": 142, "Evanston": 18, "Oak Park": 7, "Other": 22}}`. Cities below a threshold (e.g., <5 unique IPs/day) bucket into "Other" to prevent re-identification of rare visitors.
- "Chicago metro" rollup is derived at read-time, not stored: cities matching a hardcoded Chicago-MSA list (Cook + collar counties) sum into a metro-level number for advertiser reporting.
- Admin endpoint `GET /admin/geography` returns the aggregates.
- The GeoLite2 database file (~70MB) is downloaded at Docker build time from MaxMind's free distribution URL (requires a free MaxMind license key) or vendored via Git LFS. Refreshed monthly (MaxMind updates the DB on Tuesdays).
- Privacy section states: city lookup is computed from the IP we already see in the request; no IP is stored alongside the city; the daily counter is the only artifact.

**Files likely touched:**

- `backend/main.py` (middleware integration)
- `backend/geography.py` (new)
- `backend/scripts/check_geography.py` (new)
- `backend/tests/test_geography.py` (new)
- `backend/Dockerfile` (download GeoLite2 DB at build time)
- `backend/.env.example` (`MAXMIND_LICENSE_KEY` env var)
- `backend/requirements.txt` (`geoip2` dependency)
- `docs/PRIVACY.md`, `README.md`

**Open questions:**

- MaxMind license key: free tier requires email signup and EULA acceptance. Acceptable?
- Alternative: `geoip-lite` (open-source, no signup) but accuracy is lower and the DB is older. Worth a head-to-head accuracy test on a small sample of known IPs before committing?
- "Other" bucket threshold: 3? 5? Below 5, statistically significant geographic data starts getting drowned in noise. Above 5, rare suburbs disappear into "Other" and we lose the long-tail data that proves "Pingree Grove and Sycamore use this app."

---

### FEAT-004 --- Hour-of-day distribution

**Status:** ✅ Done 2026-05-04. See [backend/hourly.py](../backend/hourly.py), [backend/tests/test_hourly.py](../backend/tests/test_hourly.py). Decision baked in: increments fire on `/recommend` only (the truer engagement signal), not on every request.

**Type:** Bolt-On

**User story / motivation:** As the site owner, I want a 24-hour usage histogram so I can show advertisers when peak engagement happens (commuter rush hours), enabling time-targeted ad placement and better commercial positioning.

**Acceptance criteria:**

- Per-day aggregate: `{date, hours: [0,0,5,12,...,3,1]}` (24 ints, indexed 0–23, in Chicago timezone).
- Increment happens server-side at request time using `datetime.now(CHICAGO_TZ).hour`. No client work.
- Admin endpoint `GET /admin/hourly` returns the histogram.
- New CLI script `backend/scripts/check_hourly.py` prints a simple ASCII bar chart per day.
- No per-request log; only the daily 24-int array.
- Privacy implications: identical to existing DAU counter (counts only, no PII).

**Files likely touched:**

- `backend/main.py` (middleware extension; reuse the same code path as DAU recording)
- `backend/hourly.py` (new — small module, probably <60 lines)
- `backend/scripts/check_hourly.py` (new)
- `backend/tests/test_hourly.py` (new)

**Open questions:**

- Count *all* requests or only `/recommend`? Counting all inflates with health checks; counting only `/recommend` is the truer "engagement" signal but excludes app load. Likely the latter.
- Merge into `dau.py` as a second field on the same daily record, or keep as a separate module? Separate keeps each module simple; merged saves a write-batch flush per request.

---

### FEAT-005 --- Device class

**Status:** ✅ Done 2026-05-04. See [backend/devices.py](../backend/devices.py), [backend/tests/test_devices.py](../backend/tests/test_devices.py). Decisions baked in: iPad-in-desktop-mode classifies as desktop (industry convention); bots are bucketed but excluded from the public split; if `ua-parser` is unavailable a heuristic fallback runs so the counter still produces sensible buckets.

**Type:** Bolt-On

**User story / motivation:** As the site owner, I want to know the mobile/tablet/desktop split of users so I can right-size ad creative dimensions and prove the audience is mobile-first (which it should be, given this is a transit app).

**Acceptance criteria:**

- Server-side User-Agent parsing using `ua-parser` Python library.
- Bucketing: `mobile`, `tablet`, `desktop`, `bot`, `unknown`. Bots are excluded from the daily counter (they shouldn't reach `/recommend` in practice but defense-in-depth).
- Daily aggregate: `{date, devices: {"mobile": 134, "tablet": 8, "desktop": 47}}`.
- Admin endpoint `GET /admin/devices` returns aggregates.
- User-Agent strings are **not stored** — only the bucket the parser produced.
- Privacy implications: User-Agent is sent on every HTTP request anyway; we're discarding it after extracting one categorical value. No new tracking surface.

**Files likely touched:**

- `backend/main.py` (middleware extension)
- `backend/devices.py` (new)
- `backend/scripts/check_devices.py` (new)
- `backend/tests/test_devices.py` (new)
- `backend/requirements.txt` (`ua-parser` dependency)

**Open questions:**

- `ua-parser` regex DB needs periodic updates. Pin a version or auto-update with each deploy?
- iPad in desktop-mode UA (Safari's default since iPadOS 13) — count as tablet or desktop? Industry convention is "desktop" — accept that.

---

### FEAT-006 --- Event tracking (named behavioral counters)

**Type:** Bolt-On

**User story / motivation:** As the site owner, I want to count meaningful in-app events (recommend_clicked, route_selected, map_opened, start_route_tapped, ad_slot_clicked, etc.) so I can quote action volumes to advertisers — "X recommendations served per day" matters more to a buyer than raw visitor count.

**Acceptance criteria:**

- New backend endpoint `POST /events` accepts `{name: string, sessionId?: string}`. Allowlist of event names enforced server-side; unknown names rejected with 400.
- Daily aggregate: `{date, events: {"recommend_clicked": 312, "route_selected": 287, ...}}`. No per-event row, no per-session trail.
- If `sessionId` is supplied (FEAT-001 must be live), the event participates in FEAT-007's funnel-completion calculation — but the per-session event sequence is **not** persisted; only a transient flag like "this session has reached state X" lives in memory until the session ends, then is discarded.
- Frontend wraps a small `track(eventName)` helper that fires-and-forgets to `/events`. No retry queue, no offline buffer — analytics is best-effort.
- Admin endpoint `GET /admin/events` returns aggregates.
- Initial event allowlist (subject to revision):
  - `app_loaded`
  - `recommend_submitted`
  - `recommend_returned` (server-side; fires when `/recommend` returns successfully — no client work needed)
  - `route_selected`
  - `start_route_tapped`
  - `map_opened`
  - `house_ad_clicked`
  - `trip_completed`
- Per-IP rate limit on `/events` to prevent metric poisoning.
- Privacy: event names are non-PII categorical; `sessionId` is the same ephemeral cookie-bound ID from FEAT-001, hashed with daily salt before any storage.

**Files likely touched:**

- `backend/main.py` (new endpoint)
- `backend/events.py` (new)
- `backend/scripts/check_events.py` (new)
- `backend/tests/test_events.py` (new)
- `frontend/src/api.js` or new `frontend/src/analytics.js` — `track(name)` helper
- `frontend/src/App.jsx` (call `track()` at appropriate event sites)
- `frontend/src/MapView.jsx` (track `map_opened`)
- `frontend/src/components/RouteCard.jsx` (track `route_selected`)

**Open questions:**

- Build before FEAT-001 and ship event-counts-only (no funnel), or after FEAT-001 so FEAT-007 unblocks immediately?
- Allowlist as a hardcoded constant or env-configurable? Hardcoded is simpler and safer; env-configurable lets you ship new events without a redeploy.
- Server-side events too (e.g., `recommend_failed_no_route`)? Useful for ops dashboards but blurs the "user behavior" framing.

---

### FEAT-007 --- Funnel completion

**Type: Structural** --- depends on FEAT-001 (sessions) + FEAT-006 (events).

**User story / motivation:** As the site owner, I want to report "X% of sessions reached the 'got a result' state." This is the headline engagement metric advertisers care about, since it proves users get value from the site rather than bouncing.

**Acceptance criteria:**

- A funnel is defined as an ordered list of event names. Initial funnel: `app_loaded → recommend_submitted → recommend_returned → route_selected → start_route_tapped → trip_completed`.
- For each session, track the **highest funnel stage reached** in memory only (one int per active session). When the session ends (FEAT-001 timeout), increment the day's `funnel_completions[stage]` counter and discard the session-level state.
- Daily aggregate: `{date, funnel: [100, 97, 95, 80, 60, 40]}` (stage-by-stage counts; conversion rates derived at read time).
- Admin endpoint `GET /admin/funnel` returns the funnel data.
- The "got a result" milestone for advertiser reporting is `recommend_returned` — this is the engagement-proof number to quote externally.
- No per-session event log is ever persisted. The stage counter is the only thing that survives session end.
- Privacy: identical to FEAT-001 + FEAT-006, no new PII surface.

**Files likely touched:**

- `backend/main.py` (extension)
- `backend/funnel.py` (new — coordinates with `events.py` and `sessions.py`)
- `backend/scripts/check_funnel.py` (new)
- `backend/tests/test_funnel.py` (new)

**Open questions:**

- The funnel sequence is editorial — confirm the canonical order. Some milestones (e.g., `start_route_tapped` requires `route_selected`) imply order automatically; others are softer.
- Funnel definition in code or config? Config is more flexible but is over-engineering for a single-funnel system.
- Hard dependency on both FEAT-001 and FEAT-006. Flag clearly so this isn't started prematurely.

---

### FEAT-008 --- Referrer / traffic source

**Status:** ✅ Done 2026-05-04. See [backend/referrers.py](../backend/referrers.py), [backend/tests/test_referrers.py](../backend/tests/test_referrers.py). Decisions baked in: search/social hostname lists hardcoded (they churn slowly); UTM params deliberately *not* captured to avoid the tracking surface; per-hostname `other` table is admin-only and stripped at the public projection; self-referrals (host appears in `ALLOWED_ORIGINS`) bucket as `direct`.

**Type:** Bolt-On

**User story / motivation:** As the site owner, I want to know where traffic is coming from (direct, search, social, other) so I can quote "X% organic search" to advertisers and decide where to invest acquisition effort.

**Acceptance criteria:**

- Server-side parsing of the `Referer` header on the first request of a session (or on app load if FEAT-001 not yet live).
- Bucketing rules:
  - **Direct** — Referer header empty or absent.
  - **Search** — Referer hostname matches a known search-engine list (`google.*, bing.*, duckduckgo.com, yahoo.com, ecosia.org, brave.com, kagi.com`).
  - **Social** — Referer hostname matches a known social list (`facebook.com, x.com, twitter.com, t.co, instagram.com, threads.net, reddit.com, *.reddit.com, linkedin.com, lnkd.in, tiktok.com, youtube.com, m.youtube.com`).
  - **Other** — anything else, stored as the bare hostname (no path/query) so we can see e.g. `chicagotribune.com` if they ever link to us.
- Daily aggregate: `{date, sources: {"direct": 90, "search": 41, "social": 12, "other": {"chicagotribune.com": 5, "transitchicago.com": 3}}}`.
- Path and query string are **stripped** before storage to avoid accidental capture of UTM params containing PII.
- Admin endpoint `GET /admin/referrers` returns aggregates.
- Privacy: Referer headers are sent by the browser on every cross-site nav anyway; we're recording the hostname only, in aggregate.

**Files likely touched:**

- `backend/main.py` (middleware)
- `backend/referrers.py` (new)
- `backend/scripts/check_referrers.py` (new)
- `backend/tests/test_referrers.py` (new)

**Open questions:**

- Hardcoded constants or env-configurable for the search/social hostname lists? Hardcoded is fine; the list churns slowly.
- "First-of-session" vs "every-request" counting? If FEAT-001 isn't live yet, fall back to "first request from a new IP per day" using `_seen_hashes` from `dau.py`.
- Capture UTM params (`utm_source`, `utm_campaign`)? Useful for marketing-campaign attribution but cross into the "tracking" space — they're often used to identify specific outreach. Default: skip UTM, capture hostname only. Re-add as a separate feature if a marketing campaign actually launches.

---

### FEAT-009 --- Public stats dashboard

**Status:** v1 ✅ Done 2026-05-04 — `/stats` is live with DAU + Chicago-metro panels, served from [backend/public_stats.py](../backend/public_stats.py). No third-party scripts. The no-leak projection test in [backend/tests/test_public_stats.py](../backend/tests/test_public_stats.py) is the load-bearing safety check.

**Phase 2 panels** ✅ Done 2026-05-04 — `/stats` now also surfaces sessions/bounce/duration (FEAT-001), peak-hours histogram (FEAT-004), device split (FEAT-005), and traffic sources (FEAT-008). Six no-leak assertions in `test_public_stats.py` cover the full whitelist. Server-side rendering injects today's headline numbers for all six panels so the noscript fallback shows real data.

Remaining panels (FEAT-002 returning visitors, FEAT-006 events, FEAT-007 funnel) get appended per the procedure in [docs/ANALYTICS_MAINTENANCE.md](ANALYTICS_MAINTENANCE.md) as those features land.

**Type: Structural** --- pulls from FEAT-001 through FEAT-008 admin endpoints. Can ship incrementally as those features land, but is most valuable once the suite is largely complete.

**User story / motivation:** As the site owner, I want a public, link-shareable stats page on our own domain so prospective advertisers can see live engagement numbers without me sending screenshots, and so the privacy-first stance is provable end-to-end (the data lives on infrastructure we control, not a third-party tool). This is the artifact that replaces the "shareable Plausible/Fathom dashboard" advantage cited in Consideration A — it lets us reject Consideration A without giving up the advertiser-facing surface that motivated it.

**Acceptance criteria:**

- New public endpoints under `/stats/*` (no token gate) that mirror the existing `/admin/*` endpoints but return only the safe-to-publish aggregate fields. Per-day raw rows, salts, internal flags, and any field that could enable re-identification of a rare visitor are stripped server-side. The projection from admin shape to public shape lives in one module so the redaction logic is testable in isolation.
- New public HTML page at `/stats` (no auth) that fetches from those endpoints and renders panels for: DAU trend, sessions/bounce/duration (FEAT-001), new-vs-returning split (FEAT-002), Chicago-metro % + city table (FEAT-003), 24-hour usage histogram (FEAT-004), device class split (FEAT-005), event volumes (FEAT-006), funnel chart (FEAT-007), traffic-source breakdown (FEAT-008).
- Charts rendered with a small client-side library (Chart.js, uPlot, or hand-rolled SVG — choice deferred to implementation). Total page weight target: <200KB gzipped.
- Progressive enhancement: with JS disabled the page must still show today's headline numbers (DAU, sessions, Chicago-metro %, funnel-completion %) as plain text. Interactive charts can be JS-only.
- Visual style aligns with the existing Heritage Organic palette (cream/charcoal). Mobile-responsive — this dashboard will get opened on phones during pitch conversations.
- Footer links to `docs/PRIVACY.md` and explicitly states "no third-party scripts on this page." This is part of the advertiser pitch, not boilerplate.
- Cache headers: 5-minute public cache on the JSON endpoints to absorb traffic without hammering the backend on every page load.
- Per-IP rate limit on the public endpoints (defense against scrapers; the data is already public but a bot loop shouldn't turn it into a load problem).
- A test asserting that no admin-only field leaks through the public projection. This is the load-bearing safety check for the whole feature.
- Maintenance section per the suite-level rule above: chart-library upgrade cadence, when to add a new panel as new FEATs land, what to do if a panel needs to be redacted because a privacy concern surfaces post-launch.

**Files likely touched:**

- `backend/main.py` (new public endpoints; explicit stripping of admin-only fields)
- `backend/public_stats.py` (new — owns the projection from admin aggregates to public-safe shape)
- `backend/tests/test_public_stats.py` (new — must include the no-leak assertion)
- `frontend/src/StatsPage.jsx` and `frontend/src/StatsPage.css` (new)
- `frontend/src/main.jsx` or router config (new `/stats` route)
- `frontend/package.json` (chart library dependency, once chosen)
- `README.md` (link the public dashboard so it's discoverable)
- `docs/PRIVACY.md` (note the public dashboard exists and exactly what fields it exposes)
- `docs/ANALYTICS_MAINTENANCE.md` (chart-library upgrade notes, panel-redaction runbook)

**Open questions:**

- Build incrementally (ship a minimal `/stats` page once FEAT-001 lands, add panels as features ship) or wait until the suite is complete and ship all panels at once? Incremental ships value sooner but creates a half-empty page that's awkward to send to advertisers in the interim.
- Chart library: Chart.js (mature, ~60KB), uPlot (smaller/faster, ~40KB, less polished), or hand-rolled SVG (zero dep, more work). Defer until the first panel is being implemented so the choice is informed by the actual chart shapes needed.
- Expose historical depth (last 30 days, last 90 days) or only "today" + short trend lines? Historical is more useful to advertisers but enlarges the surface for accidental disclosure of a rare event in a quiet bucket.
- Real-time visitor widget (Plausible-style "X people online now") — include in scope or treat as a follow-up FEAT-010? Probably follow-up; it requires a new in-memory rolling-window counter that doesn't exist yet, and it's the one Plausible feature most worth replicating later.
- URL strategy: `/stats` on the same domain (cleanest, matches the "all on our infra" pitch) or `stats.example.com` subdomain (slightly better cache isolation). Default to same-domain unless deployment forces otherwise.

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

## Consideration --- Adopt a privacy-respecting third-party analytics service (Plausible / Fathom)

### Decision (2026-05-04): Rejected

The privacy-first stance is the app's primary commercial differentiator for local advertisers, and the absoluteness of "zero third-party scripts" is a sharper, more defensible claim than "one privacy-respecting third-party script." Adopting Plausible or Fathom would weaken that pitch in exchange for development-time savings worth less than the strategic cost.

The strongest case for adoption — a public, link-shareable dashboard advertisers can be sent directly — is replicated by **FEAT-009 (Public stats dashboard)** above, on infrastructure we control end-to-end. The Chicago-metro rollup that motivated the suite cannot be sourced from a generic third-party tool anyway, so the GeoIP build (FEAT-003) is unavoidable; once that's in place, the marginal cost of building the rest of the suite is small.

The Context, Tradeoffs, and When-to-revisit sections below are preserved as the audit trail for this decision. They are not active items. Revisit only if the project's maintenance situation changes materially (e.g., the maintainer can no longer absorb ongoing infra work and the recurring SaaS cost becomes the better tradeoff).

### Context

[Plausible](https://plausible.io) and [Fathom](https://usefathom.com) are commercial, privacy-respecting analytics services that ship most of FEAT-001 through FEAT-008's value as a single `<script>` tag, for ~$9/mo at this app's traffic level. Both are cookie-free, GDPR-friendly, and avoid the IP-fingerprinting and cross-site tracking that motivated rejecting Google Analytics from the start. Both also offer **public-shareable dashboards** — meaning a link to live numbers can be sent directly to a prospective advertiser as a sales tool, without exporting screenshots.

The reason this is a Consideration rather than a `FEAT-XXX` is that adopting it would partially or wholly obviate the analytics suite above. A decision is needed before — or in parallel with — building any of FEAT-001 through FEAT-008.

### Tradeoffs

**For adopting:**

- Eliminates ~6 of the 8 features above (sessions, returning users, geography, device class, referrers, hour-of-day all come standard).
- Shareable dashboard is itself an advertiser-facing artifact.
- Maintained externally — no upgrade path for parsing libraries, GeoIP DBs, etc.
- ~$9/mo at current traffic; predictable cost.

**Against adopting:**

- Adds a third-party script to the frontend (a deviation from the current zero-third-party stance, even if Plausible/Fathom are the most defensible options).
- Funnel/event tracking (FEAT-006/007) on Plausible's free tier is limited; full funnel features cost more.
- Local-only metrics (e.g., "Chicago metro %" — see Consideration C) are hard to extract from a generic third-party tool; a server-side GeoIP integration may still be needed alongside it.
- A third party holds the data, even if they don't profile users.

### When to revisit

Before starting FEAT-001. If adopted, FEAT-001 / 002 / 004 / 005 / 008 likely get cancelled; FEAT-003 (geography) probably still ships server-side for the Chicago-metro pitch; FEAT-006 / 007 (events + funnel) get reassessed against Plausible's "Goals" or Fathom's "Events" features.

---

## Consideration --- Keep the existing DAU counter as the privacy-respecting source-of-truth

### Decision (2026-05-04): Resolved — moot

Consideration A was rejected, so there is no third-party tool to reconcile against. [backend/dau.py](../backend/dau.py) is already the canonical privacy-respecting DAU source and remains so. The "don't delete it" guidance below stands trivially — it is the source-of-truth, not a redundancy. No reconciliation cadence needs formalizing.

The Context and Why-keep-it sections below are preserved as the audit trail for this decision.

### Context

If Consideration A is adopted, the existing [backend/dau.py](../backend/dau.py) counter becomes redundant on its face. **Don't delete it.** Treat it as the canonical reconciliation source: a fully-owned, fully-private daily uniques number we control end-to-end and can defend without external dependencies.

### Why keep it

- **Reconciliation against the third-party tool.** If Plausible/Fathom and our own counter diverge significantly (>15%), one of them is probably miscounting (ad blockers blocking the third-party script, our middleware miscounting CDN edge requests, etc.). Having both surfaces the discrepancy.
- **Insurance against vendor change.** If Plausible/Fathom raises prices, gets acquired, or changes its privacy stance, we still have an unbroken DAU history.
- **The "privacy-first" claim is more credible** if there's a no-third-party-script counter we can point to as the floor of what we measure ourselves.

### When to revisit

If Consideration A is *not* adopted, this is moot — DAU is already the source-of-truth. If Consideration A *is* adopted, formalize the reconciliation cadence (e.g., monthly sanity check) and document the expected divergence band.

---

## Consideration --- Add server-side GeoIP city bucketing to the existing DAU counter

### Decision (2026-05-04): Resolved — ship as FEAT-003

With Consideration A rejected, FEAT-003 is the **single highest-priority feature in the analytics suite**. The "X% Chicago metro" stat is the most differentiated thing this app can offer a local advertiser and cannot be sourced from any third-party tool, including Plausible or Fathom. Build FEAT-003 first (or at least early) within the suite — its acceptance criteria, files, and open questions are documented in full above.

The Context and Cross-reference sections below are preserved as the audit trail; they are not separate work items.

### Context

This consideration **overlaps directly with FEAT-003**. They are not separate proposals — FEAT-003 *is* the implementation of this consideration. It's listed here because the recommendation framing positioned it as one of three "next steps to explore," and removing it would lose the cross-reference for someone reading the considerations list end-to-end.

### Cross-reference

See **FEAT-003 — Approximate geography from IP** above for the full scope, acceptance criteria, files, and open questions.

### Why it appears in both places

- As a `FEAT-XXX`: it's a fully scoped, ready-to-build bolt-on.
- As a Consideration: it's also one of the three "highest-leverage exploration items" called out as the most defensible single move for advertiser-reach proof, regardless of whether Considerations A and B go forward.

If Consideration A (Plausible/Fathom) is rejected, FEAT-003 is the single highest-priority feature in the analytics suite — the "X% Chicago metro" stat is hard to get any other way and is the most differentiated thing this app can offer a local advertiser.

---
