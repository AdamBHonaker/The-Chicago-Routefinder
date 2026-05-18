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
3. CSP Hardening — Drop `style-src 'unsafe-inline'` (SEC-003 remediation) — **Structural**. Scoped 2026-05-14 (5/5 decisions); 8 chunks. Eliminates inline `style="..."` attributes across six React surfaces; final chunk flips the production CSP atomically. The previously-sequenced "Geocoding & Autocomplete — Local-First Cascade" plan fully shipped 2026-05-15 — the new `AddressAutocomplete.jsx` (Chunk 7 of that plan) introduces one dynamic-positioning `style={listboxStyle}` on the portaled listbox that this plan will need to refactor along with the other surfaces (e.g., to a CSS custom-property + class pattern). See [docs/archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md) for the geocoding history record.

**Analytics Suite — Privacy-Preserving Reach & Engagement Metrics** — ✅ **Complete 2026-05-04.** All nine features (FEAT-001 through FEAT-009) fully implemented across four build phases. Public dashboard live at `/stats`; admin endpoints at `/admin/*`. Three accompanying Considerations (third-party analytics, DAU reconciliation, GeoIP) all resolved. See [docs/archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md) for the full implementation record and [docs/ANALYTICS_MAINTENANCE.md](ANALYTICS_MAINTENANCE.md) for ongoing maintenance notes.

**Standalone Features** (not part of a chunked plan or the analytics suite):

- FEAT-013 — Curated Chicago Public Library tier in autocomplete — **Bolt-On**. Scoped; unblocked 2026-05-14 (Chunk 4 of the Geocoding & Autocomplete plan shipped, full plan completed 2026-05-15). Ready to implement.
- FEAT-015 — Bus-stop platform-level disambiguation in autocomplete — **Bolt-On**. Scoping stub; eligible to revisit (Geocoding & Autocomplete plan fully shipped 2026-05-15).
- FEAT-016 — Translate the new alerts-flow strings across all 27 locales — **Bolt-On**. Scoping stub; parent alerts-flow FEAT shipped English-only on 2026-05-07, so non-English locales currently fall back to English in the new banner + filter surfaces. Pure data work — 14 keys × 27 locales, no code changes.
- **FEAT-019 — Ship `chicago_geocode.db` to production (GitHub Release + Dockerfile curl)** — **Bolt-On** but **🔴 production-blocking for the user-visible part of the Geocoding & Autocomplete plan**. Scoping stub filed 2026-05-15. The chunked plan shipped code-complete but `backend/static_data/chicago_geocode.db` is gitignored and not delivered to the Railway container — so in production `local_search._connect()` returns None, Tier 4 of the cascade silently no-ops, `/autocomplete` returns only train stations + neighborhoods + bus stops (no addresses, no intersections), and every submit-time forward resolution that misses Tiers 1–3 goes straight to LocationIQ. Maintainer's chosen approach: Option A — upload the built DB as a GitHub Release asset and add a Dockerfile `curl` step mirroring the existing `street_graph.graphml` pattern.

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
- New translation key `ad_sponsored_kicker` in [frontend/public/locales/en/translation.json](../frontend/public/locales/en/translation.json), backfilled into all 27 existing locales. Ad copy itself is intentionally not translated (affiliate URL/text are en-US per scoping decision).
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

The 2026-05-04 testing expansion (see [archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md) for the test-suite buildout) brought the project from 218 to 651 tests; the suite has continued to grow to **1,099 tests across backend (676) and frontend (423) layers** as of 2026-05-18. Coverage is now strong everywhere a pure-logic / mocked-IO test pays back: GTFS parsing, graph construction, CTA client response handling, all 15 React components without map dependencies, all utils, and 4 of 7 hooks.

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

## CSP Hardening — Drop `style-src 'unsafe-inline'` (SEC-003 remediation)

### Overview

Removes `'unsafe-inline'` from CSP `style-src` by eliminating every dynamic React-emitted `style="..."` attribute. The fix is **not a single code change** — it is an architectural pattern shift: replace inline styles with build-time-generated CSS classes for discrete dynamic values (rail line colors, GTFS bus `route_color`, marker rotations in 15° steps, BottomSheet snap states), and a tightly-scoped CSSOM helper writing into a single hashed `<style>` block for the small set of continuous gesture-driven values (BottomSheet drag-in-progress height, App resizable column width). After this lands, the CSP collapses to `style-src 'self' 'sha256-<empty-style-hash>' https://fonts.googleapis.com` — uniformly enforced across Chrome, Safari, and Firefox, with no reliance on the partial-coverage CSP Level 3 `style-src-attr` directive.

**Goals:**

1. Close the `style-src 'unsafe-inline'` defense-in-depth gap called out in [`docs/SECURITY.md`](SECURITY.md) SEC-003 across all major browsers, including Safari (which as of 2026 does not enforce `style-src-attr`).
2. Keep the deploy topology static-HTML on Vercel — no shift to edge middleware required.
3. Establish a single, lint-enforceable pattern so new components naturally land CSP-clean and don't re-introduce the gap.

**Type: Structural** — touches the frontend build pipeline (a new generated stylesheet), six React surfaces (LinePill, SchedulesPicker, MapView markers + bearing rotation, BottomSheet, App resizable column, AlertsFilterBar plus the long-tail), and the CSP itself. Multiple PRs across multiple chunks.

**Status:** Scoped; 5 decisions captured 2026-05-14. The sequencing dependency — Geocoding & Autocomplete chunked plan — fully shipped 2026-05-15, so this plan is now eligible to invoke. SEC-003 is severity 🟢 Low and explicitly defense-in-depth (not a live exploit path), so no security urgency. Note: the new `AddressAutocomplete.jsx` from Geocoding Chunk 7 introduces one `style={listboxStyle}` inline-style on the portaled listbox that Chunk 2/3 of this plan will need to refactor (e.g., CSS custom-property + class pattern) alongside the six surfaces originally scoped.

**Prerequisites:**

- Geocoding & Autocomplete chunked plan fully complete through Chunk 10. ✅ Completed 2026-05-15.
- Knowledge of the SHA-256 of the empty `<style>` block (well-known: `47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=`) — added to the CSP in Chunk 8.

---

### Scoping decisions

1. **Architectural path (Q1) → Frontend refactor; drop `'unsafe-inline'` entirely.** *Captured 2026-05-14.*
   - Path A (edge-injected nonce CSP via a Vercel middleware) was rejected: it would require `style-src-attr 'unsafe-inline'` for the React-emitted `style="..."` attributes (nonces don't apply to style attributes), and Safari does not enforce `style-src-attr` as of 2026 — Safari users would still effectively have `unsafe-inline` on every style attribute.
   - Path D (defer indefinitely; document only) — the path the existing SEC-003 entry recommends as a fallback — is explicitly superseded by this plan.
   - **Rationale:** uniform browser coverage; no runtime middleware that can silently re-introduce `'unsafe-inline'` via a bug or misconfig; composable end-state (`style-src 'self' 'sha256-<known>' fonts.googleapis.com` with no attribute carve-outs); easy to lint-enforce going forward (grep for `style={` in `frontend/src/`).

2. **Per-tick marker-bearing rotation (Q2) → Build-time-generated 15° stepped rotation classes.** *Captured 2026-05-14.*
   - Generate 24 classes at build (`.rot-0` … `.rot-345`); marker JSX picks `Math.round(bearing / 15) * 15`. No runtime CSS injection on this surface.
   - Rejected: constructable stylesheets + `adoptedStyleSheets` (Safari 16.4 cutoff — silent rotation failure on older iPhones); CSSOM `insertRule` on the marker surface (adds an unnecessary runtime CSS-string-construction surface that takes attacker-influenceable GPS bearing values).
   - **Rationale:** cleanest CSP end-state; universal browser support; visual cost is below the perceptual floor for a ~16-pixel arrow marker (GPS heading noise in urban canyons routinely exceeds 15° between samples).

3. **GTFS bus `route_color` values (~150 dynamic hex colors) (Q3) → Build-time enumerate from GTFS.** *Captured 2026-05-14.*
   - At frontend build, read the bundled GTFS `routes.txt`, emit one class per unique `route_color` (`.bus-color-<HEX> { background:#<HEX> }`) into a generated stylesheet. Components map `route.color` → class name. New CTA `route_color`s require a frontend rebuild — already part of the quarterly GTFS refresh cadence.
   - **Rationale:** matches the Decision 2 pattern (build-time enumeration over runtime injection); ~150 classes is a trivial bundle-size impact (~5 KB raw, ~1 KB gzipped); the bundled GTFS data is the source of truth, and rebuilds are already scheduled.

4. **Rollout strategy (Q4) → Incremental refactor, atomic CSP flip at the end.** *Captured 2026-05-14.*
   - Chunks 2–6 refactor components one surface at a time without changing the CSP. Chunk 7 verifies the post-refactor state by enabling a stricter CSP locally in dev. Chunk 8 flips the production CSP in a single small PR.
   - Rejected: intermediate `style-src-attr 'unsafe-inline'` stepping stone (two CSP flips for limited additional safety; not worth the operational complexity); big-bang single PR (unreviewable diff; high regression risk).
   - **Rationale:** small, reviewable per-component PRs; atomic security cutover; honors the project policy at [frontend/index.html:14-15](../frontend/index.html#L14-L15) of never regressing to `Content-Security-Policy-Report-Only` in production (verification happens via local dev with a temporarily stricter meta tag, not in production telemetry).

5. **Sequencing vs the Geocoding & Autocomplete chunked plan (Q5) → Run entirely after Geocoding ships.** *Captured 2026-05-14.*
   - SEC-003 is severity 🟢 Low and explicitly defense-in-depth — no live exploit path. The delay carries no security cost worth the cost of interrupting in-flight work or retrofitting the new `AddressAutocomplete` (Geocoding Chunk 7) twice.
   - **Rationale:** avoids retrofit churn; keeps maintainer focus on the in-flight plan; this plan picks up cleanly once Geocoding finishes.

---

### Final-pass consistency audit (2026-05-14)

- **Decisions 1+2+3 (refactor + build-time stepped rotation + build-time GTFS colors) all align on the same pattern** — discrete dynamic values become generated CSS classes; no runtime CSS injection for the high-traffic sites. Coherent.
- **Continuous gesture-driven sites are not covered by Decisions 2/3 directly.** BottomSheet drag-in-progress height and App resizable column width have continuous value ranges; build-time enumeration would force visual quantization (a UX regression on smooth-drag interactions). These two sites use a small CSSOM helper that writes a `:root { --<var>: <value> }` rule into a single hashed `<style>` block — narrowly scoped, numeric-input-only, single audited surface. Captured as Chunk 5.
- **Decisions 1+4 (full refactor + atomic flip) interact cleanly with the project's no-report-only-in-production rule** — the verification step in Chunk 7 is dev-only via a temporarily stricter meta tag, then Chunk 8 lands the same tightening in production with high confidence.
- **Decision 5 (after Geocoding ships)** — no chunk in this plan has a code dependency on any Geocoding chunk; the sequencing is purely about avoiding retrofit cost on `AddressAutocomplete`. A one-line note could be added to the Geocoding plan's Chunk 7 reminding the implementer not to introduce new `style="..."` attributes if avoidable, but this is a low-priority polish — even if `AddressAutocomplete` ships with inline styles, this plan's Chunk 6 sweeps them.
- **SEC-003's "Suggested Fix" wording is partially obsolete.** It currently recommends `'unsafe-inline'` be left in place and the residual risk documented. This plan supersedes that recommendation. SEC-003 remains unchanged in `docs/SECURITY.md` until Chunk 8 ships; then SEC-003 is deleted and a resolved-history entry is added to `docs/archive/RESOLVED_HISTORY.md` per the security-file resolution process. A cross-reference line in SEC-003 noting this plan's existence is optional polish, not blocking.

No contradictions found.

---

### Chunked implementation plan

Each chunk is independently checkpointable: after each, the app builds, tests pass, and the **production CSP remains unchanged** with `'unsafe-inline'` in `style-src`. Only Chunk 8 changes the CSP.

#### Chunk 1 --- Infrastructure: build-time CSS generation + CSSOM helper

**Files created:** `frontend/scripts/generate-dynamic-css.mjs` (build-time generator); `frontend/src/styles/dynamic.generated.css` (generator output, gitignored); `frontend/src/lib/dynamicStyle.js` (CSSOM helper for continuous values); `frontend/src/tests/dynamicStyle.test.js`.

**Files modified:** `frontend/vite.config.js` (run generator as a build plugin / pre-build hook); [frontend/index.html](../frontend/index.html) (add `<style id="dyn-style"></style>` empty block near the CSP meta tag, with a comment recording the SHA-256 of empty content); `.gitignore` (add `frontend/src/styles/dynamic.generated.css`).

**What ships:**

- Generator reads the bundled GTFS `routes.txt` (bus `route_color`s — ~150 unique values) and a small hand-list of rail line colors (8 lines), and emits:
  - `.bus-color-<HEX> { background:#<HEX>; }` per unique bus color.
  - `.rail-color-<NAME> { background:<hex>; color:<text-color>; }` per rail line (using the existing `lineColors.js` source-of-truth values).
  - `.rot-0`, `.rot-15`, …, `.rot-345` (24 rotation classes).
  - 3 BottomSheet snap classes (`.sheet-peek`, `.sheet-half`, `.sheet-full`) using the existing snap heights.
- `dynamicStyle.js` exports `setStyleVar(name, value)`: validates that `name` matches `/^--[a-z][a-z0-9-]*$/` and `value` is a bounded number with an allowed unit suffix (`px`, `deg`, `%`); writes a `:root { --<name>: <value>; }` rule into `#dyn-style.sheet` via `deleteRule`/`insertRule`. No string-interpolation of attacker-controlled data.
- A comment near the CSP meta tag in `index.html` records the SHA-256 of the empty `<style>` block content (`47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=`) so Chunk 8 can paste it in.

**Checkpoint signal:** `npm run build` succeeds; `dynamic.generated.css` is emitted with the expected class counts (8 rail, ~150 bus, 24 rotation, 3 snap); `dynamicStyle` unit tests pass; no behavior change in the running app (no component yet uses the new pieces).

**Why first:** Every component-refactor chunk depends on the generator output and/or the CSSOM helper.

#### Chunk 2 --- `LinePill` rail + bus pills → generated classes

**Files modified:** [frontend/src/components/LinePill.jsx](../frontend/src/components/LinePill.jsx).

**What ships:**

- Replace `style={{ background: bg, color: textColor, ...fontStyle }}` at [frontend/src/components/LinePill.jsx:42](../frontend/src/components/LinePill.jsx#L42) with class-based composition. Rail pills use `.rail-color-<name>`; bus pills use `.bus-color-<hex>`.
- The conditional `fontStyle` adjustment (smaller font for ≥3-char labels in `sm`/`md` sizes) becomes two utility classes in the existing static stylesheet (`.lin-pill--font-7`, `.lin-pill--font-9`) instead of inline `style={fontSize, letterSpacing}`.
- Existing component tests updated; add coverage for the rail-vs-bus class branching.

**Checkpoint signal:** Visual diff on rail pills (all 8 lines) and a sample of bus pills (~5 routes) shows no change. Devtools confirms no `style=` attribute on rendered `<span>` elements.

**Why second:** Smallest component, biggest occurrence count across the UI — establishes the pattern.

#### Chunk 3 --- `SchedulesPicker` route pill backgrounds → generated bus-color classes

**Files modified:** [frontend/src/components/tools/SchedulesPicker.jsx](../frontend/src/components/tools/SchedulesPicker.jsx) and any same-file inline-style call sites.

**What ships:**

- Replace `style={{ background: pillColor(r) }}` at [frontend/src/components/tools/SchedulesPicker.jsx:74](../frontend/src/components/tools/SchedulesPicker.jsx#L74) with `className={`pill bus-color-${r.color}`}` (or the rail-color equivalent for rail routes).
- Any other inline-style sites in the same component swept opportunistically.

**Checkpoint signal:** Schedules picker renders identically; manual spot-check across rail + ~5 bus routes; no `style=` attributes on route pills.

**Why third:** Same pattern as Chunk 2, separate component — isolates the diff for review.

#### Chunk 4 --- `MapView` markers + bearing rotation → generated rotation classes

**Files modified:** [frontend/src/MapView.jsx](../frontend/src/MapView.jsx); [frontend/src/hooks/useMapMarker.jsx](../frontend/src/hooks/useMapMarker.jsx); any marker-emitting helper.

**What ships:**

- All `transform: rotate(${bearing}deg)` inline style attributes replaced with `className={`mk rot-${Math.round(bearing / 15) * 15 % 360}`}`. The `% 360` handles negative bearings and the 345 → 360 boundary.
- Static and dynamic inline styles in marker components (per SEC-003's "marker components — assorted static and dynamic styles") swept at the same time.
- Unit test that the bearing math snaps correctly at boundary values (0, 7.5, 15, 352.5, 360, negative bearings).

**Checkpoint signal:** Live-trip tracking shows a visibly stable arrow; bearing-snap quantization not perceptible to the eye. No `style=` attributes on marker elements at any point during a live trip.

**Why fourth:** Largest single component touch (markers are emitted in several places) — done after the simpler pill chunks have validated the discrete-class pattern.

#### Chunk 5 --- Continuous gesture-driven values → CSSOM helper

**Files modified:** [frontend/src/components/BottomSheet.jsx](../frontend/src/components/BottomSheet.jsx); [frontend/src/App.jsx](../frontend/src/App.jsx); [frontend/src/hooks/useCardsColumnWidth.js](../frontend/src/hooks/useCardsColumnWidth.js); [frontend/src/App.css](../frontend/src/App.css) (consume the new CSS variables).

**What ships:**

- `BottomSheet`: at rest the sheet uses the discrete snap classes from Chunk 1 (`.sheet-peek` / `.sheet-half` / `.sheet-full`). During an active drag, `setStyleVar('--sheet-height', `${px}px`)` updates the CSSOM rule in `#dyn-style`. On release, the helper clears `--sheet-height` and the appropriate snap class takes over.
- App resizable column: replace `element.style.setProperty('--cards-col-width', `${width}px`)` with `setStyleVar('--cards-col-width', `${width}px`)`.
- The existing CSS rules in `App.css` that consume these variables (e.g., `.cards-col { width: var(--cards-col-width, 360px); }`) continue working — they read from the `:root` scope where the helper writes the rules.
- Behavior tests for both gesture flows (drag + resize) including release / restore paths.

**Checkpoint signal:** Smooth drag on mobile bottom sheet; smooth resize on the desktop column divider. Devtools confirms no `style=` attributes on the sheet or column elements at any point during or after the gesture.

**Why fifth:** Introduces the CSSOM helper into real use only after Chunks 2–4 have validated the discrete-class path works. The two sites in this chunk are the only ones in the app that need the CSSOM mechanism.

#### Chunk 6 --- Remaining residual inline-style sites

**Files modified:** [frontend/src/components/AlertsFilterBar.jsx](../frontend/src/components/AlertsFilterBar.jsx); plus any other call site surfaced by a fresh `grep -rn "style={" frontend/src/` audit.

**What ships:**

- Each residual `style={...}` is either converted to a class (if discrete) or routed through `setStyleVar` (if continuous-numeric).
- Static inline styles (no dynamic input) are moved into the appropriate component stylesheet.
- Final `grep -rn "style={" frontend/src/` returns zero matches in component code (or only the documented exceptions, none expected).

**Checkpoint signal:** The grep returns clean; app behavior unchanged in a manual sweep across all main flows.

**Why sixth:** The long-tail. Easier to enumerate once the named bulk has been refactored.

#### Chunk 7 --- Dev verification under stricter CSP

**Files modified:** documentation only — add a `docs/SECURITY_NOTES.md` ops entry (or extend an existing ops doc) describing the procedure.

**What ships:**

- A documented dev procedure: replace the `style-src` line in `frontend/index.html` locally with `style-src 'self' 'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=' https://fonts.googleapis.com` (no `'unsafe-inline'`); run the dev server; exercise each main flow with the devtools console open (search → results → trip-tracking → schedules picker → alerts tab → settings → bottom-sheet drag → column resize) on Chrome, Safari, Firefox; capture any reported CSP violations.
- **Gating:** if violations are found, add additional component-level chunks before Chunk 8 and re-run the verification. Chunk 8 cannot proceed until verification is clean across all three browsers.

**Checkpoint signal:** Manual exercise of all main flows under the stricter CSP shows zero violations in the devtools console across Chrome, Safari, and Firefox.

**Why seventh:** Final safety net before flipping production. The project explicitly forbids report-only in production, so this dev-only stricter-CSP procedure is the substitute.

#### Chunk 8 --- Flip production CSP; archive SEC-003

**Files modified:** [frontend/index.html](../frontend/index.html) (remove `'unsafe-inline'` from `style-src`; add `'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='`; update the CSP comment to remove the SEC-003 rationale and replace it with a resolved-history note); [docs/SECURITY.md](SECURITY.md) (delete the SEC-003 entry); [docs/archive/RESOLVED_HISTORY.md](archive/RESOLVED_HISTORY.md) (add a resolved-history entry summarizing the architectural pattern and call-site sweep).

**What ships:**

- Final CSP: `style-src 'self' 'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=' https://fonts.googleapis.com`.
- SEC-003 deleted from `docs/SECURITY.md`; archived entry in `docs/archive/RESOLVED_HISTORY.md` references this plan's chunk list as the implementation record.
- One-paragraph caveat in the resolved-history entry: PWA-installed clients running an older service-worker may serve the old HTML with the old CSP until the service worker updates. Standard SW-update lifecycle applies — no special remediation, but worth recording.

**Checkpoint signal:** Production deploy. Devtools `Security` tab shows no `'unsafe-inline'` in `style-src`. Live-app smoke test on Chrome + Safari + Firefox shows zero CSP violations across the main flows. SEC-003 is gone from `docs/SECURITY.md` and present in `docs/archive/RESOLVED_HISTORY.md`. This entire entry is then deleted from `FEATURE_PLANS.md` and a summary added to `docs/archive/FEATURE_HISTORY.md`.

**Why last:** Atomic security cutover. All preceding chunks are pure refactors with no security-posture change; this one flips the bit.

---

### Out of scope (explicit non-goals)

- **Removing `'unsafe-inline'` from `script-src`.** Already not present (`script-src 'self'` per [frontend/index.html:33](../frontend/index.html#L33)). Nothing to do.
- **Self-hosting Google Fonts to drop the `https://fonts.googleapis.com` allowance from `style-src`.** Separate concern — the existing index.html font-loading comment (lines 59–67) covers the rationale and the SRI / self-host follow-up. Not in this plan.
- **Adding Subresource Integrity for fonts.** Same separate-concern carve-out.
- **`script-src-elem` / `script-src-attr` granular controls.** No scripts are inline-emitted today; not in scope.
- **Migrating CSP from `<meta http-equiv>` to a Vercel response header.** Useful for future-tuning the CSP without an HTML rebuild — the index.html comment at lines 13–14 already notes this as a future-tunability improvement. Stands alone as a follow-up; not required for this fix.
- **Edge-rendered nonce CSP infrastructure (the rejected Path A).** Permanently deferred. Revisit only if (a) the deploy is already moving off static-HTML hosting for an unrelated reason, AND (b) browser support for `style-src-attr` reaches parity with the rest of CSP Level 3 (Safari is the holdout as of 2026).

### When to revisit

The sequencing prerequisite — Geocoding & Autocomplete chunked plan — fully shipped 2026-05-15, so this plan is now eligible. Invoke Chunk 1 of this plan via `/resolve-item` (or equivalent) and work the chunks in order. After Chunk 8 ships, this entire entry is deleted from `FEATURE_PLANS.md`; SEC-003 is deleted from `docs/SECURITY.md` and summarized in `docs/archive/RESOLVED_HISTORY.md`.

---

## Standalone Features

---

### FEAT-013 --- Curated Chicago Public Library tier in autocomplete

**Type:** Bolt-On

**Status:** Scoped, ready to implement. Dependency satisfied 2026-05-14 when Chunk 4 of the Geocoding & Autocomplete plan shipped (`backend/local_search.py`); the full plan completed 2026-05-15. Decisions originally captured 2026-05-06 via the `/resolve-item FEAT-011` walk-through; retargeted 2026-05-12 onto the Passage-mirror SQLite/FTS5 scaffolding (FEAT-011 was superseded by that chunked plan, now archived in [FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md)).

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

**Status:** Scoping stub. Spawned 2026-05-06 from FEAT-011 Decision 10 (FEAT-011 was subsequently superseded by the Geocoding & Autocomplete chunked plan, which fully shipped 2026-05-15 — see [docs/archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md)). Now eligible to scope; revisit after the richer post-cascade autocomplete dropdown has accumulated some weeks of usage data.

**Dependency:** None hard. Sequencing rationale: the maintainer should first observe how riders use the addresses + intersections + neighborhoods + stations dropdown the chunked plan delivered before deciding the right disambiguation pattern for bus-stop platforms.

**User story / motivation:** The current bus-stop tier in `/autocomplete` dedupes by name — multiple physical stops at the same intersection (e.g., "Belmont & Clark" — NB, SB, EB, WB platforms) collapse to a single suggestion. This is generally the right call for casual riders who think in terms of intersections, but obscures useful structure for: (a) power users who know the platform they need, (b) accessibility-aware routing where specific platforms have specific accessibility states, (c) schedule lookups tied to a specific direction. The open question is whether to surface that structure, and how.

**Current coverage (for context):**

- Bus-stop tier today: deduped by name in [backend/local_search.py](../backend/local_search.py) `_ensure_in_mem_index` (the post-Chunk-4 location of the dedupe pass; pre-Chunk-6 it lived in `backend/main.py:312-358`).
- The 2026-05-15 Geocoding & Autocomplete cascade explicitly preserved the bus-stop tier's deduped-by-name behavior (Decision 10) — addresses, intersections, and the eventual library tier slot in without touching it.

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

**When to revisit:** After the Geocoding & Autocomplete cascade (which superseded FEAT-011, shipped 2026-05-15) has accumulated some weeks of usage data. Observed dropdown-pick patterns for bus-stop suggestions (do riders often pick a deduped entry and immediately re-route? do they search for direction-specific names like "Belmont southbound"?) will inform which option is right.

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

### FEAT-019 --- Ship `chicago_geocode.db` to production (GitHub Release + Dockerfile curl)

**Type:** Bolt-On (operational / deployment plumbing). **🔴 Production-blocking for the user-visible part of the Geocoding & Autocomplete plan.**

**Status:** Scoping stub filed 2026-05-15. Maintainer plans to use **Option A** (GitHub Release + Dockerfile curl), mirroring the existing pattern used for `street_graph.graphml`. Implementation deferred — maintainer will pick this up.

**Why this exists:** The Geocoding & Autocomplete chunked plan (fully shipped 2026-05-15, see [docs/archive/FEATURE_HISTORY.md](archive/FEATURE_HISTORY.md)) introduced `backend/static_data/chicago_geocode.db` — a 55 MB SQLite/FTS5 store containing 409 k addresses + 24.5 k intersections plus the `cached_forward` / `cached_reverse` LocationIQ cache. The DB is **gitignored** (too large, derived artifact) and the Dockerfile does not pull it in. Net effect in production right now:

- `local_search._connect()` returns `None` because the DB file isn't present → **Tier 4 (local SQLite address + intersection search) silently no-ops**.
- `geocoding._cache_connect()` returns `None` for the same reason → **`cached_forward` / `cached_reverse` writes silently no-op**, so every LocationIQ hit re-hits LocationIQ on the next encounter (cache is effectively disabled).
- `/autocomplete` returns only train stations + neighborhoods + bus stops; the new `address` and `intersection` types are wired in the response schema but never have rows to populate them. The headline new capability of the plan (typing "1234 N Damen" → inline address suggestion) **does not work in production** even though the code is complete.
- Submit-time forward resolution for any query that misses Tiers 1–3 goes straight to LocationIQ. `LOCATIONIQ_DAILY_CAP=4900` budget burns faster than designed at growth.

**Acceptance criteria:**

- `chicago_geocode.db` is fetched into `backend/static_data/` during the Docker image build, with **build-arg-driven asset resolution** so a stale Release URL never silently ships an empty image.
- The first `/autocomplete` request after a fresh deploy returns address-type and intersection-type suggestions (verifies Tier 4 is live).
- `geocoding.geocode_external` writes to `cached_forward` on a Tier-5 hit, and a follow-up identical query short-circuits via the cache (verifies the writer connection works).
- The Dockerfile build still completes in under 5 minutes (the existing budget); the 55 MB download adds < 30 s on Railway's network.

**Fix approach (single chunk):**

1. **Local:** rebuild the DB if stale (`python backend/scripts/build_address_points.py` + `build_intersections.py`), then sanity-check row counts (`addresses` ~ 409 k, `intersections` ~ 24.5 k).
2. **GitHub Release:** create a `chicago-geocode-db-YYYY-MM-DD` release (or attach to the existing release that ships `street_graph.graphml`) and upload `chicago_geocode.db` as an asset. Capture the asset ID.
3. **Dockerfile:** add a `curl` step modeled on the existing `street_graph.graphml` block (lines ~22–60). Use a build-arg `GEOCODE_DB_ASSET_ID` so the asset reference can be rotated without code churn. Reuse the same `GITHUB_TOKEN` build-arg pattern + the same security mitigations (fine-grained PAT, contents:read only, rotated after public push). Cache-invalidation via a `CACHEBUST_GEOCODE_DB` build-arg.
4. **Image-layer placement:** copy the DB into `/app/backend/static_data/chicago_geocode.db` so it lands at the path `_cache_connect()` and `local_search._connect()` already look for.
5. **Verification step in the Dockerfile:** after the curl, run a small Python one-liner (`python -c "import sqlite3; conn = sqlite3.connect('backend/static_data/chicago_geocode.db'); n = conn.execute('SELECT COUNT(*) FROM addresses').fetchone()[0]; assert n > 100_000, n"`) so a corrupt download fails the build instead of silently producing a broken deploy.
6. **Rebuild cadence:** the corpus is OSM-derived and ages slowly; quarterly is plenty. Document the rebuild + upload pipeline in the script's docstring or a short `docs/OPERATIONS.md` section.

**Decisions deferred to scoping (when invoked):**

- Whether to bundle the DB with the existing `street_graph.graphml` release tag or give the DB its own tag (separate cadence — street graph rebuilds rarely, DB rebuilds quarterly).
- Whether to bake an integrity-check (sha256 sum stored as a sibling release asset) into the Dockerfile, beyond the row-count assertion. Probably yes; cheap.
- Whether to expose a `DB_BUILD_DATE` build-arg that becomes a runtime-readable string surfaced on `/health` or `/stats` so operators can see which corpus build is live.

**Files likely touched:**

- `backend/Dockerfile` (new curl + verify block)
- `backend/scripts/_geocode_db.py` (maybe — add a `verify()` helper used by both the migrator and the Dockerfile)
- `docs/PROJECT_CONTEXT.md` (Geocoding Strategy section: remove the "DB shipping mechanism is pending" caveat)
- `docs/PRIVACY.md` — TD-051's TTL eviction shipped 2026-05-15, so when FEAT-019 lands the privacy doc no longer needs the redeploy-wipe caveat (it's already been removed); revisit only if FEAT-019 changes where the DB lives at runtime in a way that affects the cache-rows description.
- `.github/workflows/` (optional: GitHub Action to rebuild + upload the asset on a quarterly schedule — could defer)

**When to revisit:** Soon. This is the last piece between "code-complete" and "feature-actually-live-for-users." Until it ships, the Geocoding & Autocomplete chunked plan is shipped on paper but invisible to riders.

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
- LocationIQ free-tier ceiling hit before paid-tier migration — the geocoding migration off Google Maps shipped 2026-05-15, so this is now a Tier-5-capacity question rather than a Google-Maps-billing one. The local-first cascade keeps most queries off LocationIQ, but at expansion-stage DAU the 5,000/UTC-day free-tier ceiling becomes the new cost wall; paid-tier LocationIQ or a self-hosted geocoder must be in place before scaling past that threshold
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
