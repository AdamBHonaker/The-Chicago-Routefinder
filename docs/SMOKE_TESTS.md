# Browser Smoke Test Checklist

One-shot manual verification of everything in [docs/TODO.md](TODO.md) that needs a real browser. Work top-to-bottom; each section corresponds to a single browser/device session so you only swap contexts twice.

Tick boxes as you go. When the whole file is green, delete the matching items from [docs/TODO.md](TODO.md).

> **Prerequisites**
> - Production app live at the Railway + Vercel URLs (already deployed).
> - `MAXMIND_LICENSE_KEY` set in Railway → Build Arguments (already done — [docs/TODO.md:69](TODO.md#L69)).
> - For the Chunk 7 autocomplete items: local `npm run dev` + `uvicorn main:app --reload` with **FEAT-019** address/intersection DB present locally.

---

## Session 1 — Desktop Chrome/Edge with DevTools

Open the production URL in a **fresh profile** (or Incognito) so cookies/storage start clean. Open DevTools (F12). Keep Console + Network + Application tabs handy.

### 1A. `/stats` dashboard — desktop

- [ ] **All six panels populate** ([docs/TODO.md:95](TODO.md#L95)) — DAU, Chicago metro, sessions/bounce/duration, peak-hours histogram, device split, traffic sources. Empty panels should show `—` + friendly message, not crash.
- [ ] **Chicago-metro share renders sensibly** ([docs/TODO.md:71](TODO.md#L71)) — number, not `—`. Confirms MaxMind DB loaded in production.
- [ ] **DAU number + 30-day trend bars render** ([docs/TODO.md:71](TODO.md#L71)).
- [ ] **Cream/charcoal palette matches the rest of the app** ([docs/TODO.md:71](TODO.md#L71)).
- [ ] **`/privacy` link in footer loads inline text** ([docs/TODO.md:97](TODO.md#L97)).

### 1B. `/stats` with JavaScript disabled

- [ ] DevTools → ⋮ → Settings → Preferences → Debugger → **Disable JavaScript** → reload `/stats`. Headline DAU + Chicago-metro % must render as plain text, not `—` ([docs/TODO.md:73](TODO.md#L73)). If `—`, the SSR path in [backend/main.py](../backend/main.py) `public_stats_page` is broken.
- [ ] Re-enable JavaScript before continuing.

### 1C. Session cookie cross-origin check

- [ ] DevTools → Application → Cookies → Railway backend domain. After page load, a **`sid` cookie** must be present ([docs/TODO.md:85](TODO.md#L85)).
- [ ] Submit a route request. The `sid` value **persists** (does not reset).
- [ ] If missing: check Railway `ALLOWED_ORIGINS` is the exact Vercel origin including scheme, and `Access-Control-Allow-Credentials: true` appears in `/ping` response headers (Network tab).

### 1D. Chunk 7 autocomplete (local dev — `npm run dev` + uvicorn)

Switch to `http://localhost:5173` (or whatever Vite prints). Source: [docs/TODO.md:59](TODO.md#L59).

- [ ] Type **"1060 W Addison"** → an `Address` badge row appears in the dropdown.
- [ ] Type **"Clark and Belmont"** → a `Cross-street` badge row appears.
- [ ] Type a station name → `Train` badge still appears.
- [ ] Focus the input with **empty value** → saved-locations dropdown opens; it is mutually exclusive with the autocomplete listbox.
- [ ] Geo button still reverse-geocodes to a readable location.
- [ ] Keyboard nav: ↑/↓ moves selection, Enter selects, Esc closes, Home/End jump.
- [ ] `aria-live` "Searching…" / result-count region updates correctly (use VoiceOver / NVDA / Narrator for one assistive-tech pass).
- [ ] Mobile bottom-sheet does NOT clip the dropdown — open DevTools device toolbar (Ctrl+Shift+M), choose a narrow viewport OR append `?force=mobile`, retest. The dropdown should portal-render and overflow the sheet.

### 1E. i18n spot-check on autocomplete badges

- [ ] Switch language to **`ar`** (RTL) — badges render correctly, no layout breakage.
- [ ] Switch language to **`zh`** (CJK) — badges render correctly, no glyph fallback.

### 1F. D2 design-system review — desktop 1440×900

Resize the window to 1440×900 (or thereabouts). Source: [docs/TODO.md:111](TODO.md#L111) and following.

**Tokens / global**
- [ ] **Body-sm + mono 1px bumps** — sweep route-meta, alert-headline, leg-duration, transfer-wait-note, dropdown items, weather-strip temp, settings copy for cramped/overflowing text.
- [ ] **Paper grain** — `.paper-grain-bright` (single-layer 4px stipple) looks subtly less textured than `.paper-grain` (two-layer 3px+7px).

**Components — desktop variants**
- [ ] **Wordmark stacked layout** — masthead: italic "The Chicago" / roman "Routefinder." with rust period, line-height 0.95, no mid-word wraps.
- [ ] **Route-card drop-cap** — recommended minute number: **52px / -2 letter-spacing / lh 0.85** at ≥801px.
- [ ] **★ Recommended Path kicker** — 9px sans 800 rust caps, **4px clear** before drop-cap on desktop. Localized on non-English locales.
- [ ] **Special-dispatch double-border frame** — trigger any alert. 3px double outer border + 1px inner-rectangle inset (4px from edge), paper-bright bg. Kicker color: rust=Major, mute=Minor, navy=Planned. Frame identical across severities.
- [ ] **Off-route banner** — start a trip, walk off path. Banner uses **navy** advisory kicker (not rust). Wording: "Advisory".
- [ ] **Desktop side rail** at ≥801px — 60px wide, vertical brand mark "THE CHICAGO ROUTEFINDER" bottom-to-top serif 14/700 caps. Four 32×32 H/M/A/S letter squares at bottom, 1px ink borders, active = ink fill / paper text.
- [ ] **§N saved-place markers** — focus origin/dest with saved locations present. Dropdown shows italic-serif "§1, §2, …".
- [ ] **Signal lamp halo** — 7×7 rust dot, 6px glow, 1.5px paper halo. With system `prefers-reduced-motion: reduce`, flicker pauses and lamp stays at full opacity.
- [ ] **Yellow-line pill** — when a route uses Yellow Line, pill shows "YL" in dark ink (#111) on yellow. Other line pills stay white-on-color.
- [ ] **Pill paddings** — sm/md/lg pills: 0 6px / 0 8px / 0 10px horizontal. Not cramped, not stretched.

### 1G. D2 design-system — mobile via DevTools device emulation

Toggle device toolbar (Ctrl+Shift+M), choose **iPhone SE (375×667)**.

- [ ] **Route-card drop-cap** at mobile — 72px / -3 / lh 0.82.
- [ ] **★ Recommended Path kicker** — 6px clear before drop-cap on mobile.
- [ ] **Mobile tab bar** at <801px — bottom bar: four serif word labels, italic 13/400 mute default, active tab roman 13/700 ink + 2px ink underline. Bar bg = paper, top border = 2px ink.
- [ ] **Resize through the 801px breakpoint** — drop-cap responsive switch is clean (no flash, no overlap).

### 1H. RTL + i18n cross-cutting

- [ ] Switch to one RTL locale (`ar`, `ur`, `ps`, `prs`, `aii`, `rhg`). Wordmark, mobile tab bar, side rail brand mark, special-dispatch frame, §N markers all render correctly with `dir="rtl"`. Italic-serif body flows right-to-left.
- [ ] **i18n recommended-path string** — switch through all 27 active locales, confirm the recommended route card shows the localized string. Spot-check: `ru`, `uk`, `zh`, `yue`, `ko`, `hi`, `gu`, `ne`, `ur`, `am`, `ksw`, `ar`, `ps`, `prs`, `aii`, `rhg`.
- [ ] **LocaleExpansion verification** — flip `VITE_CONTINENT_PICKER_ENABLED=true` in a Vercel preview. Walk through `am`, `ksw`, `rhg`, `aii`, `hi`, `gu`, `ne`, `ur`, `ar`, `ps`, `prs`, `zh`, `yue`, `ko` — no tofu boxes. Test the continent-picker keyboard + screen-reader flow on at least one RTL locale.
- [ ] **Editorial utility classes** reachable in DevTools (Elements → Computed): `.caps`, `.headline`, `.headline__italic`, `.rule-hair`, `.rule`, `.rule-thick`, `.rule-double`, `.rule-dashed`, `.tnum`, `.itinerary-dot`, `.masthead-title--lg`.

---

## Session 2 — Real mobile phone

DevTools emulation can't honestly cover OS chrome, PWA install, real touch, or adaptive-icon masking. Open the production URL on your actual phone.

### 2A. PWA install

- [ ] Install the app from Chrome/Edge mobile. Splash screen background = **paper `#f2ece0`**. OS chrome / status bar tinted **ink `#171310`**. ([docs/TODO.md:116](TODO.md#L116))
- [ ] On Android, app drawer icon (with adaptive-icon mask) renders correctly — the new `icon-512-maskable.png` should not look cropped.

### 2B. `/stats` mobile-responsive

- [ ] All six panels render at phone width; no horizontal scroll; numbers legible.

### 2C. Mobile tab bar — real touch

- [ ] Tap each of the four tabs. Transitions are clean; active state visually updates.

---

## Session 3 — Post-traffic sanity checks (no browser; runs over time)

These need real traffic to have accumulated. Run from your local machine; `DAU_ADMIN_TOKEN` is the admin secret.

### After ≥1 full Chicago day of production traffic

- [ ] `curl -H "Authorization: Bearer $DAU_ADMIN_TOKEN" https://the-chicago-routefinder.up.railway.app/admin/geography` returns non-empty `cities` and `metro`. ([docs/TODO.md:75](TODO.md#L75))
- [ ] Trigger a Railway redeploy. Re-hit the same endpoint. **Yesterday's counts persist** (today's resets — expected). Confirms Railway volume mounts `/app/data` for `geography.json`.
- [ ] `python backend/scripts/check_sessions.py $DAU_ADMIN_TOKEN` ([docs/TODO.md:87](TODO.md#L87)):
  - `sessions` ≤ DAU × 1.5
  - `avg_duration_seconds` in 30 s – 5 min
  - `bounce_rate_pct` in 30–70%
- [ ] `python backend/scripts/check_devices.py $DAU_ADMIN_TOKEN` ([docs/TODO.md:89](TODO.md#L89)) — mobile share >60% (>80% weekends). If desktop dominates, CDN/proxy is stripping User-Agent.

### After ~1 week of weekday traffic

- [ ] `python backend/scripts/check_hourly.py $DAU_ADMIN_TOKEN` ([docs/TODO.md:93](TODO.md#L93)) — clear peaks at 7–9 a.m. and 4–6 p.m. Chicago time. Peaks at 0:00 = timezone bug.
- [ ] `python backend/scripts/check_referrers.py $DAU_ADMIN_TOKEN` ([docs/TODO.md:91](TODO.md#L91)) — mostly `direct` early; press mentions appear in `other` long tail. If `direct` low and `other` contains your Vercel domain, `_OWN_HOSTNAMES` isn't picking up production — check `ALLOWED_ORIGINS`.

### After ~1–2 weeks of geography data

- [ ] `python backend/scripts/check_geography.py $DAU_ADMIN_TOKEN` ([docs/TODO.md:77](TODO.md#L77)) — compare per-city counts against `_CHICAGO_METRO_CITIES` in [backend/geography.py](../backend/geography.py). Add any real Chicago-area suburbs that are showing visits but missing from the frozenset. Change takes effect on next read; no migration needed.

---

## Known stylistic deviations to evaluate (decisions, not bugs)

These are existing choices flagged in [docs/TODO.md:144-147](TODO.md#L144-L147). Decide keep-or-fix; no urgency.

- [ ] `.geo-btn` uses `--mono` for "Use my location" — per principle should be italic serif. Keep (compact data feel) or change?
- [ ] `.psb-refresh-btn` uses `--mono` for ↻ — icon-only, neutral. Keep.
- [ ] `.share-btn` uses `--mono` for ↗ and "Copied!" — icon fine; "Copied!" text debatable.
- [ ] `.side-rail__title` uses serif + uppercase — SPEC-DEFINED EXCEPTION. No action.

---

## When done

Delete the corresponding items from [docs/TODO.md](TODO.md):
- Phase 6 optional custom domain — only if you completed it
- Post-Deployment Cleanup "Manual browser smoke test" line (autocomplete)
- All five Analytics Suite Phase 1 items
- All six Analytics Suite Phase 2 items
- All Visual Review items under "D2 Design System Alignment"

Leave the Ongoing Maintenance items (GTFS / Anthropic costs / CTA keys) — those recur.
