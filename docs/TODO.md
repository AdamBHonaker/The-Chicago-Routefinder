# Human To-Do List

Tasks that require human action — account creation, API keys, billing, etc.
Claude cannot do these. Check them off as you go.

> **Project owner email:** all accounts below are registered under `wayfarer.atlas@gmail.com`.

---

## Accounts to Create

- [x] **Railway** ✅ — backend hosting (free tier) — owner: `wayfarer.atlas@gmail.com`
- [x] **Vercel** ✅ — frontend hosting (free tier) — owner: `wayfarer.atlas@gmail.com`

---

## API Keys to Obtain

- [x] **CTA Train Tracker API key** ✅ — registered under `wayfarer.atlas@gmail.com`
- [x] **CTA Bus Tracker API key** ✅ — registered under `wayfarer.atlas@gmail.com`
- [x] **Anthropic API key** ✅ — console account: `wayfarer.atlas@gmail.com`
- [x] **Google Maps API key** ✅ — Google Cloud project owner: `wayfarer.atlas@gmail.com`
- [x] Also add to Railway dashboard env vars (Settings → Variables) before deploying

---

## Phase 6 — Deployment (do after accounts above are ready)

- [x] Deploy backend to Railway (see step-by-step in [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md))
- [x] Set environment variables in Railway dashboard:
  - `CTA_TRAIN_API_KEY`
  - `CTA_BUS_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GOOGLE_MAPS_API_KEY` ← required for address/landmark geocoding
  - `ALLOWED_ORIGINS` ← fill in after Vercel URL is known
- [x] Deploy frontend to Vercel (see step-by-step in [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md))
- [x] Set `VITE_BACKEND_URL` in Vercel dashboard → your Railway URL
- [x] Go back to Railway and set `ALLOWED_ORIGINS` → your Vercel URL, then redeploy
- [x] Update `frontend/.env.production` with the real Railway URL and commit
- [x] Test the live app end-to-end on the public URLs
- [ ] (Optional) Add a custom domain in Vercel dashboard → Settings → Domains --Maybe something like "Chicago Routefinder"

---

## Map UI — Post-Launch Checks

- [ ] **Confirm desktop split-panel width ratio** — currently set to 40% route cards / 60% map. Check this on a real desktop screen before deployment and adjust if needed.

- [ ] **Confirm mobile minimum heights** — currently set to route card panel min-height: 300px, map min-height: 350px. Test on a real mobile device before deployment and adjust if needed.

- [ ] **Source and provide transit location photos** (see [BUG-007 in docs/BUGS.md](BUGS.md)) — at least 10 photos needed for the loading/no-routes map panel. Decide on sourcing approach:
  - Option A: Take your own photos at CTA locations
  - Option B: Free stock photos from Unsplash or Wikimedia Commons (verify license per image)
  - Option C: Combination of both
  - Each photo needs a location name caption (e.g. "Addison · Red Line", "O'Hare · Blue Line", "95th/Dan Ryan · Red Line")
  - Once sourced, place images in `frontend/public/transit-photos/` and give Claude the list of filenames + captions to wire up

---

## Phase 7 — Monetization (future)

**Strategy:** House ads first (Phase 1) — no third-party ad scripts. Defer EthicalAds/Carbon Ads until the user base is established. Google AdSense deliberately avoided for now (auto-placed display ads are likely to clash with The Chicago Routefinder editorial design).

- [ ] Sign up for Amazon Associates (or a comparable affiliate program) to generate affiliate links for the house ad product list — see `docs/FEATURE_PLANS.md` → Feature Monetization → Affiliate Products Reference
- [ ] Set `VITE_HOUSE_AD_ENABLED=true`, `VITE_HOUSE_AD_URL`, and `VITE_HOUSE_AD_TEXT` in the Vercel dashboard after Claude wires up the AdSlot component
- [ ] After reaching meaningful traffic, evaluate EthicalAds (ethicalads.io) or Carbon Ads (carbonads.com) — both require applying with a live site and have traffic/content requirements

---

## Post-Deployment Cleanup

- [x] **Restore street-network walking graph (Feature K)** ✅ — Completed. `street_graph.graphml` uploaded as a GitHub Release asset; Dockerfile curl block re-enabled and pointed at the GitHub API asset endpoint. Street-routed walking is live in production.
- [ ] **Remove geocoding rate limit** — `backend/gtfs_loader.py` has a temporary 9,500 calls/month cap (`_GEOCODE_CALL_LIMIT`) to prevent accidental charges during testing. Once the app is live and call volume is understood, remove the cap: delete `_GEOCODE_CALL_LIMIT`, `_GEOCODE_COUNTER_PATH`, `_geocode_call_counter`, `_load_geocode_counter`, `_save_geocode_counter`, `_geocode_call_count`, `_increment_geocode_call_count`, and the guard block inside `geocode_google`. The large comment block above `_GEOCODE_CALL_LIMIT` marks all of these.

---

## Ongoing Maintenance

- [ ] **GTFS data** — CTA updates its static feed periodically. Railway re-downloads it on every deploy, but if you go weeks without deploying, restart the Railway service manually to pull fresh data.
- [ ] **Monitor Anthropic API costs** — check console.anthropic.com/usage monthly, especially after any public launch push
- [ ] **CTA API keys** — both are free but may require periodic renewal; check transitchicago.com if API calls start failing

---

## Visual Review — D2 Design System Alignment (2026-05-02)

The 19-phase D2 design system alignment landed without a browser running. Each item below should be confirmed with `npm run dev` at **375×667 (iPhone SE)** and **1440×900 (desktop)**. Tick when verified.

### Tokens / global

- [ ] **Body-sm and mono 1px bumps** — `--fs-body-sm` 13→14px and `--fs-mono` 12→13px ripple across ~30 components (route-meta, alert-headline, leg-duration, transfer-wait-note, dropdown items, weather-strip temp, settings copy). Quick sweep for any that look too tight, too loose, or now overflow their container.
- [ ] **PWA chrome** — install the app from a Chrome/Edge browser; confirm OS chrome is ink (`#171310`) and splash is paper (`#f2ece0`). The new `icon-512-maskable.png` should appear correctly when Android's adaptive-icon mask is applied.
- [ ] **Paper grain** — `.paper-grain-bright` switched from two-layer to single-layer 4px stipple per spec. Compare visually against `.paper-grain` (still two-layer at 3px+7px). Bright variant should look subtly less textured.

### Components

- [ ] **Wordmark stacked layout** — home masthead at mobile + desktop. Italic "The Chicago" line 1, roman "Routefinder." line 2 with rust period. Lines should sit tight (line-height 0.95) and not wrap mid-word at any width.
- [ ] **Route-card drop-cap responsive** — at desktop (≥801px) the minute number should be 52px / -2 letter-spacing / lh 0.85. At mobile it's 72px / -3 / lh 0.82. Resize the window through the breakpoint to confirm.
- [ ] **★ Recommended Path kicker** — recommended route card should show "★ Recommended Path" (now spec-text, no longer "Best") in 9px sans 800 rust caps with 6px clear before the drop-cap (4px on desktop). Localized on non-English locales.
- [ ] **Special-dispatch double-border frame** — trigger any service alert (Major / Minor / Planned). Confirm the 3px double outer border + 1px inner-rectangle inset (4px from edge), paper-bright background. Kicker color: rust for Major, mute (gray) for Minor, navy for Planned/Advisory. The frame itself should be identical on all three severities.
- [ ] **Off-route banner** — start a trip, walk off the path. Banner should now use the navy "advisory" kicker color (changed from rust). Confirm wording still reads "Advisory" and the visual treatment matches a Planned/Info severity rather than a Major delay.
- [ ] **Mobile tab bar** — at <801px width, bottom bar should show four serif word labels (no icons), italic 13/400 mute by default, with the active tab roman 13/700 ink + 2px ink underline. Bar background = paper, top border = 2px ink. Tap each tab to confirm transitions work.
- [ ] **Desktop side rail** — at ≥801px, left rail should be 60px wide, vertical brand mark "THE CHICAGO ROUTEFINDER" reading bottom-to-top in serif 14/700 caps, four 32×32 letter squares (H/M/A/S) at the bottom with 1px ink borders, active = ink fill / paper text.
- [ ] **§N saved-place markers** — focus the origin or destination input with saved locations present. Dropdown should show italic-serif "§1, §2, …" markers replacing the previous icon-less rows.
- [ ] **Signal lamp halo** — confirm 7×7 rust dot with 6px glow + 1.5px paper halo. Test under `prefers-reduced-motion: reduce` (system setting) — flicker should pause and lamp stays at full opacity.
- [ ] **Yellow-line pill** — when a route uses the Yellow Line, the pill should show "YL" in dark ink (#111) on yellow background (readable contrast). Other line pills stay white-on-color.
- [ ] **Pill paddings** — sm/md/lg pills now use 0 6px / 0 8px / 0 10px horizontal padding (per spec). Verify pills don't look cramped or oddly stretched at any size.

### Cross-cutting

- [ ] **RTL layouts** — switch language to Arabic, Urdu, or Pashto. The wordmark, mobile tab bar, side rail brand mark, special-dispatch frame, and §N markers should all render correctly with `dir="rtl"`. Italic-serif body copy should flow right-to-left.
- [ ] **i18n recommended-path string** — switch through all 22 locales and confirm the recommended route card shows the localized "Recommended Path" string. Spot-check Cyrillic (ru, uk), CJK (zh, yue, ja, ko), Indic (hi, gu, pa, ne, ur), and RTL (ar, ps, ur) for proper rendering.
- [ ] **Editorial utility classes unused but reachable** — `.caps`, `.headline`, `.headline__italic`, `.rule-hair`, `.rule`, `.rule-thick`, `.rule-double`, `.rule-dashed`, `.tnum`, `.itinerary-dot`, `.masthead-title--lg` should all exist and be inspectable in DevTools. They're reserved for the deferred panel-heading + itinerary-spine refactors and the cover/404 wordmark variant.

### Known stylistic deviations from the "Italic softens, caps direct" principle

These are existing choices, not regressions from the D2 alignment work, but worth a future revisit:

- [ ] `.geo-btn` — uses `--mono` for "Use my location" button text. Per principle, ghost-button text should be italic serif. Visually defensible (compact, "data" feel) but off-spec.
- [ ] `.psb-refresh-btn` — uses `--mono` for the refresh control. Mostly an icon (↻) so neutral.
- [ ] `.share-btn` — uses `--mono` for the "↗" glyph and "Copied!" status. Icon usage is fine; "Copied!" text in mono is debatable.
- [ ] `.side-rail__title` — uses serif + uppercase for the vertical brand mark. SPEC-DEFINED EXCEPTION — not a violation, just noting that it deviates from the general "caps = sans" rule by design.
