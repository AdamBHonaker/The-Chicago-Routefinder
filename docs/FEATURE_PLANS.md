# Feature Plans

This file holds three kinds of forward-looking planning entries: **Chunked Implementation Plans** for upcoming major features (work through each chunk in order, one chunk per session or per commit; do not start a chunk until all previous chunks are complete), **Standalone Features** scoped as single bolt-on or structural items (FEAT-NNN), and **Considerations** — design directions evaluated and deferred, with explicit triggers for when to revisit.

> **Process:** When a feature here is fully implemented, **delete its entry from this file** and add a corresponding entry to [`docs/archive/FEATURE_HISTORY.md`](archive/FEATURE_HISTORY.md) (or to [`docs/archive/RESOLVED_HISTORY.md`](archive/RESOLVED_HISTORY.md) when the work fits the bug/tech-debt/efficiency log better) summarizing what was built. This file should only ever contain features that have not yet been implemented.

---

## Feature Index

**Bolt-On** = self-contained, no dependencies on other planned features.
**Structural** = depends on one or more other features before it can be fully built or realized.

**Chunked Implementation Plans** (in document order):

1. Feature Monetization — House Ads (overall Phase 7, sub-phase 1; third-party networks deferred) — **Bolt-On**. Chunk 1 shipped 2026-05-05 behind `VITE_HOUSE_AD_ENABLED=false`; Chunk 1.1 polish pass + Phase 2/2b/3 work remain.
2. Feature PaceMetraCoverage — Pace + Metra service-area expansion of the walking street graph — **Structural** (depends on Pace/Metra being added to the transit graph)
3. Geocoding & Autocomplete — Local-First Cascade (Passage-mirror) — **Structural**. Decisions captured 2026-05-12 (9/9); 10 chunks scoped. Supersedes FEAT-011 / 011a / 011b, FEAT-014, and the Mapbox migration Consideration. Ready to invoke Chunk 1.

**Analytics Suite — Privacy-Preserving Reach & Engagement Metrics** — ✅ **Complete 2026-05-04.** All nine features (FEAT-001 through FEAT-009) fully implemented across four build phases. Public dashboard live at `/stats`; admin endpoints at `/admin/*`. Three accompanying Considerations (third-party analytics, DAU reconciliation, GeoIP) all resolved. See [docs/archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md) for the full implementation record and [docs/ANALYTICS_MAINTENANCE.md](ANALYTICS_MAINTENANCE.md) for ongoing maintenance notes.

**Standalone Features** (not part of a chunked plan or the analytics suite):

- FEAT-013 — Curated Chicago Public Library tier in autocomplete — **Bolt-On**. Scoped, ready to implement after the Geocoding & Autocomplete chunked plan's Chunk 4 (`local_search.py`) ships.
- FEAT-015 — Bus-stop platform-level disambiguation in autocomplete — **Bolt-On**. Scoping stub; ready to revisit after the Geocoding & Autocomplete chunked plan ships.
- FEAT-016 — Translate the new alerts-flow strings across all 27 locales — **Bolt-On**. Scoping stub; parent alerts-flow FEAT shipped English-only on 2026-05-07, so non-English locales currently fall back to English in the new banner + filter surfaces. Pure data work — 14 keys × 27 locales, no code changes.

**Considerations** (design directions evaluated and deferred, with explicit revisit triggers):

- Migrate MapView to react-map-gl/maplibre — last evaluated 2026-05-03 (defer). Drift watch: MapView.jsx at 660 lines as of 2026-05-12, approaching the ~900-line migration trigger.
- MapView smoke test (regression net for future migration) — build only if react-map-gl migration is approved OR MapView grows past ~900 lines. Superseded by the Playwright E2E entry below once that is built.
- Playwright E2E suite for maplibre + geolocation paths — build if a maplibre/geolocation regression ships undetected, react-map-gl migration is approved, or a second contributor joins.
- Geographic Expansion Revenue Model — reference numbers for Pace+Metra and out-of-market expansion. Pace+Metra is the highest-leverage expansion; out-of-market expansion is gated on hitting the maintainer's revenue target inside Chicagoland first.

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

### Post-Chunk-1 audit findings (2026-05-12)

Audit of the shipped Chunk 1 against current code surfaced items below. Items are tech-debt-style follow-ups to fold into a Chunk 1.1 polish pass before flipping `VITE_HOUSE_AD_ENABLED=true` in production, or into Phase 2 work.

**Must-fix before production enable:**

1. **`referrerpolicy="no-referrer"` on the `<a>`.** Route page URL contains origin/destination — a user's real-world locations. Without this attribute, that URL is sent to Amazon as the `Referer` header on click. Privacy regression on a privacy-marketed app. One attribute fixes it.
2. **`javascript:` URL guard.** React does not sanitize `href` against `javascript:` URIs. If `VITE_HOUSE_AD_URL` is mistyped or the Vercel dashboard is compromised, `javascript:fetch(...)` executes on click. Add `if (!url.startsWith("https://")) return null;` at the top of `AdSlot`.
3. **A11y sponsored disclosure for screen readers.** The visual "SPONSORED" kicker is fine for sighted users, but screen readers reading the link text alone give blind users no signal. Two acceptable patterns (pick one, don't combine): (a) `aria-label={``Sponsored: ${text}``}` on the `<a>` plus `aria-hidden="true"` on the kicker `<span>`, or (b) leave the `<a>` without `aria-label` and let the kicker `<span>` containing the localized "SPONSORED" text be read normally. Recommendation: (b) — keeps the disclosure inside i18n via `t("ad_sponsored_kicker")`.
4. **Amazon Operating Agreement §5 phrase.** `rel="sponsored"` + "SPONSORED" satisfies FTC 16 CFR 255 in spirit, but Amazon Associates Operating Agreement §5 requires the literal phrase **"As an Amazon Associate I earn from qualifying purchases"** to appear on the page. Missing it is grounds for account closure independent of FTC rules. Recommendation: add to [docs/PRIVACY.md](PRIVACY.md) and the `PRIVACY_TEXT` constant in [backend/public_stats.py](../backend/public_stats.py) (both must update together — they are intentionally not auto-synced).
5. **Privacy double surface.** Sending users to `amazon.com/dp/...?tag=...` invokes Amazon's tracking, which contradicts the "no third-party tracking" promise. Add a one-sentence note to both [docs/PRIVACY.md](PRIVACY.md) and `PRIVACY_TEXT` at [backend/public_stats.py](../backend/public_stats.py): "Outbound sponsored links are fulfilled by their destination (currently Amazon) and may be tracked by them under their own privacy policy."

**Free wins to ship in the polish pass:**

6. **Click telemetry (one line).** `house_ad_clicked` is **already allowlisted** in [backend/events.py](../backend/events.py) with a comment confirming it's reserved for this surface. Wire `onClick={() => track("house_ad_clicked")}` on the `<a>` tag — entire change. No backend work needed.
7. **Impression telemetry (~5 lines).** Add `"house_ad_impression"` to the `EVENT_ALLOWLIST` frozenset in [backend/events.py](../backend/events.py); in `AdSlot`, fire `track("house_ad_impression")` once per session via `useEffect`, gated on a `sessionStorage` flag so re-renders don't inflate the count. Without this, CTR has to be back-derived from `/recommend` volume and isn't real CTR. The Phase-2 sponsor pitches will need real CTR data, so the longer this is deferred the less data is available when needed.

**Should resolve:**

8. **`ENABLED` env var is a string.** `import.meta.env.VITE_HOUSE_AD_ENABLED` is the literal string `"false"`, which is truthy. Confirm `=== "true"` comparison in `AdSlot`.
9. **Empty-string runtime guards.** If `ENABLED=true` ships with `URL=""` or `TEXT=""`, an empty link or blank clickable banner renders. Add guards alongside the `https://` check from item 2.
10. **Lighthouse a11y baseline.** AC #4 says "unchanged from pre-feature baseline" but no baseline number is recorded. Run Lighthouse on production `main` first, write the number into the doc so AC #4 is verifiable.
11. **Amazon Associates rejection/closure fallback.** The Phase 1 scope flags the 3-sales-in-180-days risk but provides no contingency. If the account is rejected or closed, all live affiliate URLs become non-monetizing. Pre-pick a fallback URL/text pair (tip jar, Block Club affiliate, or a "sponsor this slot" `mailto:` link) so the slot doesn't have to be killed via env-var-disable when that happens.
12. **PWA service-worker caching caveat.** The scope advertises "swap copy without redeploy" via env vars. True only with caveats: `import.meta.env` values are baked into the JS bundle at Vite build, and the service worker serves stale bundles. A change to `VITE_HOUSE_AD_URL` requires a Vercel redeploy AND propagation through the SW cache. Worth one sentence in expectations.

**Pre-implementation actions outside the codebase (carryover from audit):**

- **Apply for Amazon Associates.** Approval can take several business days; the resulting tracking ID belongs in `.env.production` on the same deploy that enables the slot. See [docs/TODO.md](TODO.md).
- **Decide where the Amazon Op Agreement phrase lives** (item 4). Recommendation: privacy page only. Re-evaluate if Associates flags placement.

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

**Post-refactor state (2026-05-03):** MapView.jsx dropped to 427 lines (was 679, -37%). Imperative bookkeeping for layers and origin/dest markers is gone.

**Drift update (2026-05-12):** MapView.jsx has grown back to **660 lines** (+233 / +55% from the post-refactor baseline), bringing it within striking distance of the 900-line migration trigger. Growth was buried in commit `4132ae0 Major overhaul`. The 900-line trigger is no longer a comfortable distance away — re-evaluate at the next major map-feature add.

**Re-add to active consideration if:** any planned feature needs dynamic/data-driven layer composition (toggleable layers, multi-trip overlays, custom raster tiles), MapView grows past ~900 lines, a real leak surfaces, or a second engineer joins and onboarding friction becomes a cost.

---

## Consideration — MapView smoke test (regression net for future migration)

### Context

During the 2026-05-03 evaluation of migrating MapView to react-map-gl, the largest single risk identified was **no automated regression net**: zero tests cover MapView, so any non-trivial change must be re-verified manually across animations, interaction lock, arrival callback, StrictMode double-mount, transient tile errors, and leg-muting paint mutations. The two interim hook extractions (`useMapMarker`, `useRouteLayers`) shipped without this safety net by relying on type-checking and manual smoke tests; that approach does not scale to a wholesale library swap.

A small smoke test would not exercise WebGL (jsdom has none), but it can catch the regressions that actually break in practice: thrown errors during mount, missing layer cleanup on unmount, hook-order violations, prop-shape mismatches, and console errors during a route swap.

### When to build it

Build the smoke test if **either** of the following becomes true:

1. **Migration to react-map-gl is approved.** The smoke test must land *before* the migration starts — not as part of it — so it can detect regressions introduced by the swap rather than codifying the migrated behavior.
2. **MapView grows past ~900 lines** (as of 2026-05-12: **660 lines**, up from 427 at this consideration's writing). At that size the manual-verification cost per change is high enough that a one-time test investment pays back. A second engineer joining the project hits this trigger early; solo development can tolerate a higher line count. The trigger is closer than this consideration's original framing implied.

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

- **`MapView.jsx`** (660 lines as of 2026-05-12; was 427 when this consideration was written) — maplibre lifecycle, layer add/remove, fitBounds/flyTo, leg muting.
- **`components/markers/*.jsx`** (3 files) — DestinationMarker, LivePositionMarker, OriginMarker — render via maplibre's marker portal.
- **`hooks/useMapMarker.jsx`, `useRouteLayers.js`** — direct maplibre Map manipulation.
- **`hooks/useTripTracker.js`** — wraps `navigator.geolocation.watchPosition`, off-route detection, and live map layer updates.
- **`App.jsx`** — top-level state machine, i18n bootstrapping, route between home/map/alerts/tools tabs.

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
2. **Extend the existing union-of-boxes polygon** in [backend/fetch_street_graph.py:99-113](../backend/fetch_street_graph.py#L99-L113). The polygon infrastructure (`unary_union` of a main Chicago box + a Purple Line corridor strip, fed to `ox.graph_from_polygon`) already exists as of the 2026-05-12 Polygon Union commit — no rectangle-to-polygon switch is needed. A rectangle big enough to contain Aurora to Kenosha would be ~80mi × 60mi and impractical, so the union approach already in place is the right primitive to extend.
3. Likely approach: union 0.25-mile buffers around each Metra station + 0.1-mile buffers around each Pace stop with the existing main + corridor boxes. Note that `unary_union` will collapse touching geometries into a single `Polygon`; if buffers remain disjoint from the Chicago box the result becomes a `MultiPolygon`, which `graph_from_polygon` accepts but may need verification at osmnx's query-area limits.
4. Memory and graph-load time will increase substantially. May need to shard the graph by region (north/south/west) and lazy-load per request, or move from in-process pickle to a tile server.

### Files this would touch

- `backend/utils.py` — owns the corner constants (`STREET_GRAPH_*`, `PURPLE_LINE_CORRIDOR_*`); add new constants for Pace/Metra buffer radii if used.
- `backend/fetch_street_graph.py` — extend `_build_coverage_polygon()` ([line 99-113](../backend/fetch_street_graph.py#L99-L113)) to union Pace/Metra station/stop buffers with the existing main + corridor boxes; source Pace/Metra stop coords from their respective GTFS feeds.
- `backend/walking.py` — likely no change; still loads a single artifact.
- Deployment — pickle size will grow; verify Railway memory headroom and LFS quota.

### Prerequisites

- Pace and/or Metra integrated into the transit graph.
- Decision on whether to ship one expanded artifact or shard by region.

---

## Geocoding & Autocomplete — Local-First Cascade (Passage-mirror)

### Overview

Migrates the project's geocoding + autocomplete stack from a hosted-first model (Google Maps Geocoding API for both forward and reverse; in-memory prefix index for `/autocomplete` with no address coverage) to a **local-first cascade backed by a single SQLite/FTS5 database**, with **LocationIQ** as an optional hosted fallback. Mirrors the design shipped in the Passage project at `c:\GitHub\Passage\`.

**Goals:**

1. Eliminate per-request hosted-geocoder cost as the dominant operating expense at growth.
2. Make `/autocomplete` instant and address-aware — typing "1234 N Damen" or "Damen & Milwaukee" returns inline suggestions for the first time.
3. Keep working when the network is unhappy — local tiers serve while the breaker is open.
4. Replace the in-memory prefix index + JSON cache + monthly call counter with a single SQLite file holding the corpus *and* the persistent cache.

**Type: Structural** — touches backend resolution, autocomplete endpoint, frontend combobox, i18n, privacy doc; introduces a new ingest pipeline and a quarterly rebuild cadence.

**Status:** Decisions captured (9/9 as of 2026-05-12). Final consistency audit complete. Supersedes FEAT-011 / FEAT-011a / FEAT-011b (which scoped a TIGER + Google + static-index approach), FEAT-014 (subsumed by `cached_forward` + negative-cache), and the deferred "Geocoding Provider Migration (Google Maps → Mapbox)" Consideration (directly replaced). FEAT-013 (curated CPL libraries) and FEAT-015 (bus-stop platform disambiguation) survive — FEAT-013 retargets onto Chunk 4 of this plan; FEAT-015 is orthogonal.

**Prerequisites:**

- LocationIQ account + API key provisioned (free tier is 5,000 requests/day, sufficient at current and near-term DAU).
- Disk space for `backend/static_data/chicago_geocode.db` — estimate ~150–250MB once both addresses (~600–900k rows) and intersections (~50k rows) are ingested with FTS5 mirror tables.

---

### Reference design (Passage)

Before reading this plan, the canonical reference implementation lives in:

- `c:\GitHub\Passage\backend\geocoding.py` — Tier-1/2/3 cascade, LocationIQ client, 429 circuit breaker, SQLite-backed forward+reverse cache, KDTree neighborhood reverse, fuzzy matcher
- `c:\GitHub\Passage\backend\local_search.py` — autocomplete + forward + nearest_address against the SQLite store; ranking, dedupe, cross-street parser
- `c:\GitHub\Passage\backend\geocode_text.py` — shared `normalize_street_name` / `normalize_address` used at both ingest and query time
- `c:\GitHub\Passage\backend\scripts\_geocode_db.py` — single-file SQLite schema (addresses, intersections, addresses_fts, intersections_fts, cached_forward, cached_reverse)
- `c:\GitHub\Passage\backend\scripts\build_address_points.py`, `build_intersections.py` — quarterly ingest scripts (Overpass for addresses; pedestrian graph for intersections)
- `c:\GitHub\Passage\backend\scripts\migrate_geocode_cache.py` — one-shot migrator from legacy JSON cache
- `c:\GitHub\Passage\backend\main.py` lines ~320–383 — GET /autocomplete endpoint shape
- `c:\GitHub\Passage\frontend\src\components\AddressAutocomplete.jsx` + `frontend\src\lib\autocompleteApi.js` — generic, pluggable-data-source typeahead combobox; WAI-ARIA combobox 1.1 inline pattern
- `c:\GitHub\Passage\CLAUDE.md` — "Geocoding (local-first cascade)" and "Address autocomplete" sections

---

### Architecture to port

**Forward resolution cascade** (`resolve_location`):

1. Coord-pair regex (instant)
2. Exact `NEIGHBORHOOD_COORDS` dict (curated landmarks + neighborhoods — kept as the Python dict; small, version-controlled, human-edited)
3. Fuzzy match against `NEIGHBORHOOD_COORDS` (SequenceMatcher, threshold 0.95, inverted-word-index prefilter)
4. `local_search.forward()` → SQLite/FTS5 over Chicago OSM addresses (~600–900k rows) + intersections (~50k rows)
5. LocationIQ `/v1/search` — optional; missing API key or `LOCATIONIQ_ENABLED=false` makes Tier 5 return `None`

**Reverse resolution cascade** (`reverse_geocode_point`):

1. `cached_reverse` SQLite hit (lat/lon quantized to 1e5)
2. KDTree-nearest neighborhood within ~200m → label
3. `local_search.nearest_address` within ~50m (bbox prefilter + Haversine sort)
4. LocationIQ `/v1/reverse` (cached on success)
5. Coordinate-string fallback (never cached)

**Key invariants copied verbatim from Passage:**

- **One SQLite file** at `backend/static_data/chicago_geocode.db` holds all four tables: `addresses`, `intersections`, `cached_forward`, `cached_reverse`. Plain (non-content-linked) FTS5 mirror tables `addresses_fts` and `intersections_fts` — easier ingest, costs a few MB.
- **DB location matters.** Must live under `backend/static_data/`, NOT `backend/data/`. Railway's persistent analytics volume overlays `backend/data/` at runtime, which would destroy the corpus on every deploy.
- **Two connections to the same DB.** `local_search.py` opens read-only with `mode=ro` + mmap (128 MB); `geocoding.py` opens a writeable connection in WAL mode for cache writes. Concurrent reads never block cache inserts.
- **Negative cache.** Misses are stored as rows with `lat`/`lon` = `NULL` — `_cache_get_forward` returns a `NEG_HIT` sentinel so the network is never re-queried for known-bad strings.
- **Shared 429 circuit breaker.** Forward + reverse both gate on the same `_circuit_open_until`. Exponential backoff 60→120→240s, capped at 300s. First post-cool-off call probes; success closes the breaker. Tier-4 (local) results still serve while the breaker is open. Raise a dedicated `GeocoderDegradedError` only when the request would have needed Tier 5.
- **Shared text normalization.** `normalize_street_name` and `normalize_address` are imported by both the ingest scripts and the runtime. Anything that builds a row also defines the query canonicalization — never let those drift.
- **`/autocomplete` endpoint: local-only.** No hosted supplement of any kind. Submit-time forward still cascades through LocationIQ for queries the local layer misses.
- **Source priority ranking:** neighborhood > intersection > address > place. Within a source, exact > prefix; in-bbox > out-of-bbox; ties break toward Chicago center via Haversine.
- **Per-tier soft cap = 3, total cap = 8.** Each tier capped at `AUTOCOMPLETE_PER_TIER_CAP` (default `3`) before lower tiers are pulled in, preventing any tier from starving others.
- **Cross-tier dedupe.** Same canonical entity in two tiers (matched by normalized name OR coords within 50m) → higher-priority tier wins. Within a source, dedupe by quantized coord and (source, label).
- **Privacy.** User-typed queries are SHA-256 redacted (`q#abcd1234ef`) in logs.
- **Coverage gating.** Anything that resolves outside the Chicago bbox raises `LocationOutsideChicagoError` — distinct from `None` (= "not found").
- **Cost ceiling.** `LOCATIONIQ_DAILY_CAP=4900` UTC-day counter (in-process, cheap) silently degrades Tier 5 to local-only when cap is hit. Leaves ~100-call headroom under the 5,000/day free-tier ceiling for clock skew / race conditions. Defense against a runaway-bug cost incident the 429 breaker can't catch.
- **Env-var opt-out.** `LOCATIONIQ_ENABLED=true` by default. Setting `false` disables Tier 5 entirely (self-hoster privacy control + emergency kill switch).

**Frontend pattern.** `AddressAutocomplete.jsx` is generic. Takes a `getSuggestions(query, { signal })` async function. Handles debounce (150ms), abort-on-keystroke, keyboard + pointer + touch selection. Renders via portal to escape `overflow: hidden` / transform clipping ancestors (relevant for the mobile bottom sheet). WAI-ARIA combobox 1.1 inline pattern (`role="combobox"`, `aria-controls`, `aria-expanded`, `aria-activedescendant`). `LocationInput.jsx` becomes a thin wrapper that adds the geo button, saved-location items, and form integration.

---

### Scoping decisions

1. **Hosted geocoder provider (Q1) → LocationIQ.** *Captured 2026-05-12.*
   - LocationIQ replaces Google for the Tier-5 fallback. Existing `geocode_google` / `reverse_geocode_google` removed (no pluggable interface, no Google retention as fallback — explicitly rejected as overengineering).
   - **Env var:** `LOCATIONIQ_API_KEY`. Missing key makes Tier 5 silently return `None`.
   - **Rationale:** mirrors Passage exactly; friendlier caching terms (LocationIQ has no equivalent of Google's 30-day cache-retention clause that the existing 90-day TTL already violates); free-tier ceiling of 5,000 req/day is more than sufficient given negative-cache + local-corpus coverage.

2. **Monthly call counter (Q2) → Drop the monthly counter; keep a daily cap.** *Captured 2026-05-12 (revised after FEAT-011a Decision 2 review).*
   - Drop `GEOCODE_MONTHLY_LIMIT` + `geocode_counter.json` + monthly-rollover logic — legacy Google bookkeeping.
   - Add `LOCATIONIQ_DAILY_CAP` (default `4900`, UTC day, in-process counter). On cap hit, Tier 5 silently degrades to local-only for the remainder of the day; event is logged.
   - **Why a daily cap, not just the breaker:** the Passage 429 breaker only protects against provider-side throttling. A runaway-bug or attack hammering LocationIQ inside our own cache-miss paths could rack costs before the breaker fires. The daily cap is a non-negotiable circuit against bug/abuse cost incidents — captured reasoning from the prior FEAT-011a Decision 2.
   - **Why 4900 and not 5000:** leaves ~100-call headroom under the LocationIQ free-tier daily ceiling for clock skew (server vs. LocationIQ's clock for the day boundary) and concurrency races between simultaneous cap-checks.

3. **Address + intersection corpus scope (Q3) → Chicago city limits, addresses + intersections.** *Captured 2026-05-12.*
   - Overpass for addresses (`addr:housenumber` + `addr:street` nodes/ways) within the Chicago city polygon. Estimate ~600–900k rows.
   - Intersections derived from the existing pedestrian/street graph (`backend/fetch_street_graph.py` output). Estimate ~50k rows.
   - **Quarterly rebuild** via two ingest scripts; DB output gitignored.
   - **Rationale:** matches Passage's proven scope; intersections are too useful in Chicago ("Damen & Milwaukee") to skip; suburb buffer deferred to a follow-up if real users hit the edge.

4. **Existing JSON cache migration (Q4) → One-shot migrator into SQLite.** *Captured 2026-05-12.*
   - `scripts/migrate_geocode_cache.py` reads `backend/geocode_cache.json`, re-normalizes each key through the new `geocode_text` module (canonicalization differs from Google's raw key), inserts into `cached_forward` with bounded synthetic timestamps so the TTL eviction sweep doesn't immediately wipe them.
   - Pre-warms LocationIQ cache; preserves months of real-user query→coord pairs (provider-agnostic — coords are just lat/lon).
   - One-time run with a `.migrated` marker file; refuses to re-run unless `--force` is passed.
   - **Rationale:** small (~2 hours of work), meaningfully softens the launch by keeping Tier 5 cold longer.

5. **`/autocomplete` Tier-5 supplement (Q5) → Local-only, no supplement.** *Captured 2026-05-12.*
   - Passage's digit-prefix supplement (fire a LocationIQ call when local <3 results AND first token is digit-prefixed) is **not ported**.
   - **Rationale:** with a full Chicago address+intersection corpus, the supplement's marginal recall improvement is tiny; autocomplete fires on every keystroke (debounced 150ms), making it the highest-volume endpoint by orders of magnitude — even a 1% leak rate dwarfs all other LocationIQ traffic. Submit-time forward still cascades through Tier 5, so anything autocomplete misses still gets resolved when the user presses Go. Revisit if production metrics show real recall gaps.

6. **Frontend combobox approach (Q6) → Port `AddressAutocomplete` generic + refactor `LocationInput` to compose it.** *Captured 2026-05-12.*
   - New `frontend/src/components/AddressAutocomplete.jsx` + `frontend/src/lib/autocompleteApi.js` ported from Passage. Generic combobox owns ARIA combobox 1.1, portal rendering, abort-on-keystroke, debounce.
   - `LocationInput.jsx` refactored to compose `AddressAutocomplete`, retaining its geo button, save-location flow, and saved-locations dropdown items.
   - **Rationale:** ARIA combobox + portal + abort is a self-contained correctness concern; separating it from form-binding logic is the only exception to the "don't extract abstractions prematurely" instinct that's warranted here. Brings across Passage's existing test suite for the component.

7. **Reverse-geocoding local tiers (Q7) → Full cascade: cache + neighborhood + nearest_address + LocationIQ.** *Captured 2026-05-12.*
   - All four tiers as listed in the architecture section. Data is already local once Chunks 3+4 ship.
   - **Rationale:** geo-button latency drops from ~100–300ms (hosted round-trip) to <10ms for the vast majority of locations. Cascade implementation is ~80 lines on data we already have. Geo button is one of the most-used interactions in the app.

8. **Per-tier soft cap + cross-tier dedupe rules (Q8, implied by FEAT-011a Decisions 7+9) → Adopt.** *Captured 2026-05-12.*
   - **Per-tier soft cap:** `AUTOCOMPLETE_PER_TIER_CAP` (default `3`); endpoint total cap `8`. Tier-greedy fill from highest-priority tier with the cap enforced before descending.
   - **Cross-tier dedupe:** higher-priority tier wins when the same canonical entity appears in two tiers. Dedupe key = (a) exact normalized name match OR (b) coords within 50m.
   - **Rationale:** explicit caps are cleaner than relying on ranking alone; FEAT-011a captured the same reasoning and the rule is portable across the new architecture.

9. **Privacy + opt-out (Q9) → PRIVACY.md correction + new LocationIQ section + `LOCATIONIQ_ENABLED` env opt-out.** *Captured 2026-05-12.*
   - Fix the existing inaccurate "no third-party processor" claim in `docs/PRIVACY.md` ([docs/PRIVACY.md:144-145](../PRIVACY.md)).
   - Add a new section ("Geocoding & autocomplete (LocationIQ)") documenting: (a) forward calls on submit when the local cascade falls through to Tier 5; (b) reverse calls when the geo-button reverse cascade falls through to Tier 5; (c) the daily cap behavior; (d) what is and is not sent (typed text; deployment outbound IP; no rider identifier; no session cookie).
   - `LOCATIONIQ_ENABLED` env var (default `true`). When `false`, the backend skips Tier 5 entirely and behaves as local-only. Useful for self-hosters with stricter privacy postures, emergency disabling, and local-only dev testing.
   - **Rationale:** privacy correction is mandatory regardless of provider choice; the env-var opt-out is FEAT-011a's already-decided posture, retargeted at LocationIQ.

---

### Final-pass consistency audit (2026-05-12)

- **Decisions 1+2+5 (LocationIQ, daily cap, no AC supplement) consistently minimize hosted exposure** — coherent.
- **Decisions 3+7 (full corpus, full reverse cascade) both lean on the SQLite layer being complete** — chunk sequencing must place corpus ingest (Chunk 3) before reverse-cascade wiring (Chunk 5). Plan reflects this.
- **Decision 4 + Decision 1 (migrator + LocationIQ swap)** — migrator absorbs Google-resolved query→coord pairs; coords are provider-agnostic, so safe.
- **Decision 6 + Decision 5 (generic combobox + local-only AC)** — generic component takes a `getSuggestions` function; in this app it always points at local `/autocomplete`. Coherent.
- **Decision 8 (per-tier cap + cross-tier dedupe)** — applies inside `local_search.autocomplete`; doesn't conflict with any other decision.
- **Decision 9 + Decision 2 (privacy + daily cap)** — daily cap behavior is part of what PRIVACY.md must disclose. Wording in Chunk 9 will cover both.

No contradictions found.

---

### Chunked implementation plan

Each chunk is independently checkpointable: after each, the app builds, tests pass, and we pause for review before the next chunk starts. Chunks are ordered so each one delivers something useful or strictly enables the next.

#### Chunk 1 --- Shared text normalization module

**Files created:** `backend/geocode_text.py`

**Files modified:** `backend/gtfs_loader.py` (re-export from new module for back-compat *within this chunk only*; removed in Chunk 10)

**What ships:**

- Port `normalize_street_name(name)` and `normalize_address(addr)` from Passage verbatim (compound directionals, USPS suffix expansion, punctuation/whitespace collapse).
- Move `_normalize_street_abbr` + `fuzzy_match_neighborhood` here too. Existing call sites in `gtfs_loader.py` and `main.py` updated to import from `backend.geocode_text`.
- Unit tests ported from Passage's normalize tests, retargeted at this project's import paths.

**Checkpoint signal:** All existing tests pass. No behavior change yet. `pytest backend/tests` green.

**Why first:** Every downstream chunk (ingest, local_search, cascade) consumes these helpers. Establishing the single source of truth here means ingest and runtime can't drift.

#### Chunk 2 --- SQLite schema + DB scaffolding

**Files created:** `backend/scripts/_geocode_db.py` (schema definition + connection helpers); `backend/static_data/` directory (must be `static_data/` not `data/` per Railway constraint); `.gitignore` additions.

**Files modified:** `.gitignore` (add `backend/static_data/*.db*`).

**What ships:**

- Schema for `addresses`, `intersections`, `addresses_fts` + `intersections_fts` (plain non-content-linked FTS5), `cached_forward`, `cached_reverse`.
- Connection helpers: `open_readonly()` (mode=ro + 128MB mmap), `open_writeable()` (WAL).
- Empty DB initialization script.
- Schema tests: open empty DB, confirm tables exist, confirm FTS5 is available in the SQLite build.

**Checkpoint signal:** `python -m backend.scripts._geocode_db --init` creates an empty DB at `backend/static_data/chicago_geocode.db`; schema test passes; nothing else changes.

**Why second:** Pure infrastructure. Lets later chunks land ingest + queries against a stable, tested schema.

#### Chunk 3 --- Address + intersection ingest scripts

**Files created:** `backend/scripts/build_address_points.py`, `backend/scripts/build_intersections.py`.

**Files modified:** none in runtime path.

**What ships:**

- `build_address_points.py`: Overpass query over the existing routing bbox (`STREET_GRAPH_*` constants in `utils.py` — main Chicago box + Evanston Purple Line corridor) for `nwr["addr:housenumber"]["addr:street"]` features. Chunked into a 4×4 grid (16 sub-bboxes) with 180s per-chunk Overpass timeout, 10s sleep between chunks, 3 retries with 15s exponential backoff. Normalize each row via Chunk-1 helpers. Bulk-insert into `addresses` + `addresses_fts`. Resumable / idempotent.
- `build_intersections.py`: Overpass query over the same bbox for every named `highway=*` way (one query, `timeout:300`). Pedestrian-graph artifact (`street_graph_igraph.pkl`) is **not** used — OSMnx's `consolidate_intersections` strips names from collapsed-node edges, so the artifact is unsuitable as a source (per Passage's design note). Compute true geometric crossings with Shapely STRtree over the LineStrings; emit one row per (canonical name A, canonical name B, lat, lon) intersection point. Normalize, insert into `intersections` + `intersections_fts`.
- Quarterly run instructions added to `docs/PROJECT_CONTEXT.md` (one-line ops note).

**Checkpoint signal:** Run both scripts on dev machine. Resulting DB has ~400–900k addresses and ~25–50k intersections (Chicago's actual OSM `addr:housenumber` density came in toward the low end on the first build — 409k addresses + 24.5k intersections, 55 MB total). FTS5 queries against it return sensible results from a manual probe.

**Status:** ✅ Built 2026-05-12. DB lives at `backend/static_data/chicago_geocode.db`.

**Why third:** Builds the corpus needed by Chunks 4 and 6. No runtime code touches the DB yet — production keeps using Google.

#### Chunk 4 --- `local_search.py` module

**Files created:** `backend/local_search.py`.

**Files modified:** none.

**What ships:**

- `autocomplete(query, limit=8, per_tier_cap=3, in_bbox_only=True)` — FTS5 over addresses + intersections, union with neighborhood/station results, apply Passage's ranking + Decision-8 per-tier soft cap + Decision-8 cross-tier dedupe.
- `forward(query)` — same FTS5 layer, returns top-ranked coord.
- `nearest_address(lat, lon, radius_m=50)` — bbox-prefilter on `addresses` (simple lat/lon range) + Haversine sort.
- Cross-street parser (`"Damen & Milwaukee"` → intersections table lookup).
- Tests ported from Passage's `test_local_search.py`, retargeted.

**Checkpoint signal:** Module is import-tested and unit-tested. Not yet called from any endpoint. No production behavior change.

**Why fourth:** Self-contained query layer. Validating it in isolation before wiring into endpoints keeps the integration chunk small.

#### Chunk 5 --- Forward + reverse cascade + LocationIQ client

**Files created:** `backend/geocoding.py` (replaces `gtfs_loader.geocode_google` / `reverse_geocode_google`).

**Files modified:** `backend/main.py` (`_resolve_locations` and share-link path swap `resolve_location`/`coords_for_location` to the new module's `resolve_location`); `backend/gtfs_loader.py` (delete `geocode_google`, `reverse_geocode_google`, `_geocode_call_counter` plumbing, JSON cache load/save — pure deletion, no shims); `backend/config.py` (remove `GEOCODE_MONTHLY_LIMIT` and friends; add `LOCATIONIQ_API_KEY`, `LOCATIONIQ_DAILY_CAP`, `LOCATIONIQ_ENABLED` env-var docs).

**What ships:**

- `LocationIQClient` with shared 60→120→240→300s circuit breaker + probe-on-first-call-after-cooloff.
- `LOCATIONIQ_DAILY_CAP=4900` UTC-day counter; silent degrade-to-local-only on cap hit; log on cap-cross.
- `LOCATIONIQ_ENABLED` env opt-out wiring.
- `cached_forward` / `cached_reverse` read+write helpers; negative-cache sentinel (`NEG_HIT`).
- `resolve_location(query)` cascade: coord-regex → NEIGHBORHOOD_COORDS exact → fuzzy → `local_search.forward()` → LocationIQ.
- `reverse_geocode_point(lat, lon)` cascade: cached_reverse → KDTree-neighborhood (≤200m) → `local_search.nearest_address` (≤50m) → LocationIQ.
- `LocationOutsideChicagoError` raised when resolution lands outside the Chicago bbox.
- `GeocoderDegradedError` raised only when a Tier-5 call would have been needed and the breaker is open.
- SHA-256 query redaction in logs (`q#abcd1234ef`).
- `/reverse-geocode` endpoint updated to call new `reverse_geocode_point`.
- Existing tests updated to mock the new client where they mocked Google.

**Checkpoint signal:** All routing flows still work end-to-end against the new cascade. Tier-5 hit rate observably low in dev. Breaker behavior verified by injecting a 429 in a test. Daily-cap behavior verified by injecting a counter-at-cap state.

**Why fifth:** This is the big switchover. By landing it after Chunks 1–4, the new module has all its dependencies (normalize, schema, corpus, query layer) and the swap is a relatively localized edit at the call sites.

#### Chunk 6 --- `/autocomplete` endpoint rewrite

**Files modified:** `backend/main.py` (`/autocomplete` handler swapped to call `local_search.autocomplete`; remove `_build_autocomplete_index`, `_ac_master`, `_ac_prefix_index` — entirely superseded by FTS5).

**What ships:**

- `/autocomplete` now returns addresses + intersections + neighborhoods + stations (a real upgrade over today's stations-only output).
- No hosted supplement (Decision 5).
- Existing rate-limit bucket preserved.
- Endpoint shape unchanged for the frontend (`{ suggestions: [{ label, value, type }] }`) plus new `type` values: `address`, `intersection`.
- Tests updated; new tests for the address + intersection suggestion paths.

**Checkpoint signal:** Typing "1234 N Damen" in the existing `LocationInput` produces address suggestions for the first time. Backend tests green.

**Why sixth:** Once the corpus + `local_search` are in place, this is a contained endpoint swap that delivers immediate user-visible value while the frontend is still the old component.

#### Chunk 7 --- Frontend: port `AddressAutocomplete` + refactor `LocationInput`

**Files created:** `frontend/src/components/AddressAutocomplete.jsx`, `frontend/src/lib/autocompleteApi.js`, `frontend/src/tests/AddressAutocomplete.test.jsx`.

**Files modified:** `frontend/src/components/LocationInput.jsx` (refactored to compose `AddressAutocomplete`; keeps geo button, save-location flow, saved-locations dropdown items); `frontend/src/tests/LocationInput.test.jsx` (updated for the composed structure); `frontend/src/App.css` (badge styling for `address` and `intersection` types).

**What ships:**

- Generic `AddressAutocomplete` with portal rendering, abort-on-keystroke, 150ms debounce, full ARIA combobox 1.1.
- `autocompleteApi.js` provides `getSuggestions(query, { signal })` against `GET /autocomplete`.
- `LocationInput.jsx` becomes a thin shell around the generic combobox; existing tests updated.
- Mobile bottom-sheet overflow/clipping issues that may exist today get fixed for free via portal rendering.

**Checkpoint signal:** Manual test in browser. Typing in the route form shows addresses + intersections + stations + neighborhoods. Saved-locations + geo button still work. Keyboard nav + screen-reader announcements correct. Mobile bottom-sheet does not clip the dropdown.

**Why seventh:** Backend already delivers the right shape after Chunk 6, so this is a pure frontend swap with no backend dependency.

#### Chunk 8 --- i18n badge translations across 27 locales

**Files modified:** `frontend/public/locales/*/translation.json` (all 27 locales).

**What ships:**

- New i18n keys: `autocomplete.badge.address`, `autocomplete.badge.intersection`.
- Translations across all 27 locales using the same translation pipeline as prior locale work.
- 3 `RESEARCH_LOCALES` (`aii`, `ksw`, `rhg`) surface the `mt-review-notice` MT badge on these keys.

**Checkpoint signal:** All 27 locale files contain both keys. Spot-check on RTL (`ar`) and CJK (`zh`) confirms render without layout breakage.

**Why eighth:** Pure data work. Can in principle ship alongside Chunk 7, but separating it keeps the frontend code review focused.

#### Chunk 9 --- PRIVACY.md updates

**Files modified:** `docs/PRIVACY.md`.

**What ships:**

- Correct the existing inaccurate "no third-party processor" claim ([docs/PRIVACY.md:144-145](../PRIVACY.md)) — at this point in the migration it is true that LocationIQ is reached only in narrow fallback conditions, but it is still a third-party processor.
- New section ("Geocoding & autocomplete (LocationIQ)") documenting:
  - When LocationIQ is called (forward Tier 5 on submit fallthrough; reverse Tier 5 on geo-button fallthrough).
  - What is sent: typed prefix; deployment outbound IP. No rider identifier; no session cookie.
  - What is cached locally and for how long (90-day TTL on `cached_forward` and `cached_reverse`; `NEG_HIT` rows for known-bad strings).
  - The `LOCATIONIQ_DAILY_CAP=4900` UTC-day cap behavior — what happens after the cap is hit (silent degrade to local-only for the rest of the day).
  - The `LOCATIONIQ_ENABLED=false` env opt-out (for self-hosters with stricter privacy postures).
- Note that LocationIQ's own retention is governed by LocationIQ's privacy policy.

**Checkpoint signal:** PRIVACY.md is accurate end-to-end with the new architecture. Existing inaccuracy is corrected.

**Why ninth:** Mandatory but small. Lands after the code paths exist so the doc describes deployed reality, not planned reality.

#### Chunk 10 --- One-shot cache migrator + final cleanup

**Files created:** `backend/scripts/migrate_geocode_cache.py`.

**Files deleted (after migrator runs):** `backend/geocode_cache.json`, `backend/geocode_cache.journal`, `backend/geocode_cache_ages.json`, `backend/geocode_counter.json`.

**What ships:**

- Migrator reads the JSON cache, re-normalizes each key via `geocode_text`, inserts into `cached_forward` with bounded synthetic timestamps (so TTL eviction doesn't immediately wipe them).
- Run-once safety: writes a `.migrated` marker file; refuses to re-run without `--force`.
- Final removal of Chunk-1 re-export shims from `gtfs_loader.py`.
- Docs note in `docs/PROJECT_CONTEXT.md` (or ops-notes location) explaining the one-time run.

**Checkpoint signal:** Run the migrator locally. `cached_forward` row count jumps by however many entries were in the JSON file. Spot-check that previously-cached queries now resolve from SQLite without hitting LocationIQ. JSON cache files are deleted from the repo.

**Why last:** Pure data move with no code dependency. Deferring this until the new cascade is fully live means the migrator is writing into a well-tested, real schema.

---

### Out of scope (explicit non-goals)

- **Suburb / regional expansion of the corpus.** Decision 3 chose Chicago city limits. Follow-up if real users hit the edge.
- **LocationIQ supplement on `/autocomplete`.** Decision 5 deferred. Revisit only if production metrics show real recall gaps.
- **POI tier (the FEAT-011b half).** Not in this plan. If wanted later, becomes an additive tier in `local_search.autocomplete` sourced from a Geofabrik OSM extract (`amenity`, `shop`, `tourism`, `leisure`, etc.). Decision deferred — own follow-up FEAT.
- **Fuzzy matching beyond `NEIGHBORHOOD_COORDS`.** Today's prefix-exact behavior is preserved across new tiers. Cross-tier fuzzy matching is a desirable future improvement with a different perf profile.
- **Tier-hit-rate telemetry.** None in Passage; can be added later if needed.
- **Backwards-compatibility shims for `geocode_google` / the JSON cache after Chunk 10.** No shims per maintainer preference.

### When to revisit

Ready to invoke implementation in chunk-by-chunk sequence — Chunk 1 first. After Chunk 10 ships, this entire entry is deleted from FEATURE_PLANS.md and a summary added to `docs/archive/FEATURE_HISTORY.md`. FEAT-013 (CPL libraries) and FEAT-015 (bus-stop platform disambiguation) become eligible to resume — FEAT-013 retargets onto Chunk 4's `local_search.autocomplete` as one more curated source.

---

## Standalone Features

---

### FEAT-013 --- Curated Chicago Public Library tier in autocomplete

**Type:** Bolt-On

**Status:** Scoped, ready to implement after the Geocoding & Autocomplete chunked plan's Chunk 4 (`local_search.py`) ships. Decisions originally captured 2026-05-06 via the `/resolve-item FEAT-011` walk-through; retargeted 2026-05-12 onto the Passage-mirror SQLite/FTS5 scaffolding (FEAT-011 was superseded by that chunked plan).

**Dependency:** Geocoding & Autocomplete chunked plan, Chunk 4 (`local_search.autocomplete`). CPL becomes one more curated source merged into the ranking — slots in alongside `NEIGHBORHOOD_COORDS` as a curated tier above OSM-derived addresses/intersections.

**User story / motivation:** Chicago Public Library branches are high-confidence civic destinations that riders frequently route to. Today they're only resolvable post-submit via Google Geocoding (e.g., "Harold Washington Library Center" works on submit but never autocompletes inline). As a rider typing "Sulzer," I want the Conrad Sulzer Regional Library branch to appear inline as a recognized destination — with the same curated, deliberate feel as the existing train station and neighborhood tiers, not buried in a generic OSM-address result.

**Current coverage (for context):**

- CPL branches today: only resolvable via post-submit Google Geocoding, no inline autocomplete.
- After the Geocoding & Autocomplete chunked plan ships: CPL branches may show up incidentally if an OSM `amenity=library` node carries the right name, but coverage is incomplete and naming is inconsistent.
- This FEAT supersedes that incidental coverage with a curated, authoritative tier.

**Acceptance criteria:**

- All ~80 CPL branches appear as inline autocomplete suggestions when the rider types any prefix of the official branch name (e.g., "wash", "harold", "sulz", "cha" → Chicago Lawn).
- Suggestions render with a dedicated `library` badge, styled consistently with existing badges (`station`, `neighborhood`, `stop`, `address`, `intersection`).
- The tier ranks **above** OSM-derived addresses and intersections but **below** the existing transit-focused tiers (train station, neighborhood, bus stop). Concretely: train → neighborhood → stop → **library** → intersection → address → LocationIQ fallback.
- When the same branch appears in both the curated CPL tier and an incidental OSM address row, the curated entry wins via the cross-tier dedupe rule (normalized-name match OR coords within 50m).
- Selecting a library suggestion resolves to coordinates without any external API call (lat/lng is in the static artifact).
- Branch data lives in a static, in-repo JSON file; no runtime/build dependency on `data.cityofchicago.org`.

**Files likely touched:**

- `backend/static_data/cpl_locations.json` (new — static artifact, ~80 entries, committed to repo as source of truth — must live under `static_data/` not `data/` because Railway's persistent volume overlays `/app/data` at runtime)
- `backend/scripts/refresh_cpl.py` (new — fetches the latest data from the Chicago Open Data Portal "Libraries — Locations, Hours and Contact Information" dataset and overwrites the JSON file; ad-hoc, not on a CI schedule)
- `backend/local_search.py` (loads CPL entries at startup; merges into `autocomplete` ranking as a curated tier above OSM addresses/intersections; small dedupe rule for the OSM-overlap case)
- `frontend/src/components/AddressAutocomplete.jsx` or its consumer (handles `library` suggestion type — likely no code change if the generic combobox already dispatches on `type`)
- `frontend/src/App.css` (badge styling for the `library` type, consistent with existing badges)
- `frontend/public/locales/*/translation.json` (new key `autocomplete.badge.library` rolled out across all 27 locales)
- `backend/tests/` (CPL fixture, ranking tests, OSM-dedupe test)

**Data source:**

- **Authoritative:** static `backend/static_data/cpl_locations.json` committed to the repo. ~80 entries, <50KB. Source-of-truth artifact.
- **Refresh path:** `backend/scripts/refresh_cpl.py` fetches the current dataset from `data.cityofchicago.org` ("Libraries — Locations, Hours and Contact Information") and overwrites the JSON file. The maintainer runs this ad-hoc — annually, or when notified of a CPL branch change. No CI dependency on the city portal.
- **Rationale for static-with-refresh-script over live fetching:** ~80 entries that change every few years. Static asset is fully reproducible, license-clean, and immune to portal outages. The refresh script provides automation when needed without coupling production builds to an external service.

**Fields stored per branch:**

- `name` — official branch name (e.g., "Harold Washington Library Center", "Conrad Sulzer Regional Library")
- `address` — formatted street address (used as the secondary line in the dropdown, not as a search target)
- `lat`, `lng` — coordinates
- `branch_code` — the city's stable identifier (used as the suggestion `value` for resolution and as the dedupe key against OSM)

Hours, phone, branch type, and other CPL metadata are explicitly **out of scope** — this is a routing app, not a library directory.

**Tier placement:**

- New curated tier inserted between the existing bus-stop tier and the OSM-derived intersection/address tiers.
- Final ranking after this FEAT ships on top of the Geocoding & Autocomplete chunked plan: train station → neighborhood → bus stop → **library (this FEAT)** → intersection → address → LocationIQ fallback.

**Out of scope:**

- Other civic destination types (parks, schools, post offices, museums, fire stations). Each would warrant its own curated tier or be left to incidental OSM coverage. If the maintainer decides to extend the curated-civic-tier pattern later, that's its own FEAT.
- Hours, phone, and branch metadata.
- Live status (open/closed, holiday closures) — not a routing concern.

**When to revisit:** After the Geocoding & Autocomplete chunked plan's Chunk 4 ships. At that point this entry should be straightforward to invoke via `/resolve-item FEAT-013` with no further scoping.

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
