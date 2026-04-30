# Handoff: The Chicago Routefinder — Editorial Redesign

## Overview

This package is a **visual + interaction redesign** of the existing CTA Transit PWA (`AdamBHonaker/CTA-Transit-PWA`, frontend folder). It does **not** propose new features — every component, hook, and behavior in the current `frontend/src/` stays as-is. What changes is the **design language**: a typography-forward “editorial almanac” aesthetic that replaces the current default styling.

The product name in the redesign is **The Chicago Routefinder.** The existing `t("app_title")` key should be rebranded from “CTA Transit” to “The Chicago Routefinder” across all locale files.

## About the design files

The HTML files in `designs/` are **design references**, not production code. They are React/JSX prototypes loaded via Babel-in-browser, demonstrating intended look and behavior. The implementation task is to **recreate this design language inside the existing `frontend/` codebase** — same React 18 + Vite, same components, same hooks, same i18n, same `MapLibre` map. Replace `App.css` and per-component class styles; do not replace the application logic.

### Fidelity

**High-fidelity.** Pixel-perfect intent: exact hex values, font stack, type scale, spacing, and motion are specified. Recreate using regular CSS (the codebase uses plain `App.css`; introduce CSS variables for tokens).

## Target codebase

- **Stack:** React 18.3.1, Vite 6, plain CSS (`App.css`), `react-i18next`, `maplibre-gl`, `vite-plugin-pwa`
- **Entry:** `frontend/src/App.jsx`
- **Styles:** `frontend/src/App.css` (single global stylesheet, ~35 KB)
- **Components:** `frontend/src/components/`
- **Hooks:** `frontend/src/hooks/`
- **Tokens:** add a `:root { --… }` block at the top of `App.css` and use throughout

## What changes vs. what stays

### Changes (visual layer)

- Color palette — cream paper background, ink/rust/navy accents replace the current scheme
- Typography — Fraunces serif display + Inter UI caps + JetBrains Mono figures
- Layout rhythm — masthead + thick rule + drop-cap minutes + hairline section dividers
- **Navigation model** — replace the current single-column scroll with a **fixed bottom tab bar** (4 tabs: Home / Map / Alerts / Saved). See Tab Bar spec below.
- Component skins — `RouteCard`, `PinnedStopsBoard`, `ServiceAlertsBar`, `SettingsPanel`, `LocationInput`, `SavedRoutesPanel`, `WeatherStrip`, `LoadingSkeleton`, alerts, off-route banner, trip footer
- The 8 CTA line colors stay (they’re a transit standard) — only their *presentation* changes (rectangular pills with inset border, white-on-color, `Inter 900`)
- Existing emoji icons (🚶 ⭐ ⚙ 📌 📍 ⏱ ✓ ⇅) stay — they’re already wired through i18n strings

### Stays (logic layer — do not touch)

- All hooks: `useFavorites`, `useApiQuery`, `useLocalStorage`, `useFavorites` (BYOK idle-clear, GPS watchPosition, etc.)
- All utility files: `tripGeometry.js`, `fetchWithRetry.js`, `favorites.js`
- All API contracts: `/recommend`, `/alerts`, `/stop-arrivals`, `/ping`
- Constants: `LINE_COLORS`, `BUS_DIRECTION_COLORS`, `OFF_ROUTE_THRESHOLD_METERS`, etc.
- i18n: 22 languages including RTL (`ar`, `ur`, `ps`)
- Feature flags: `VITE_BYOK_ENABLED`, `aiEnabled` toggle, `walkSpeed`
- `MapView.jsx` MapLibre integration (the redesigned editorial figure-card overlays sit *over* the existing map; the map itself is unchanged)

## Design tokens

Add to top of `App.css`:

```css
:root {
  /* Paper stock */
  --paper:        #f2ece0;   /* primary background */
  --paper-bright: #fffbef;   /* featured panels, leading article */
  --paper-folio:  #e9e1d1;   /* secondary surfaces */

  /* Ink */
  --ink:          #171310;   /* primary type, rule lines */
  --ink-soft:     #4a3f32;   /* body copy on cream */
  --mute:         #7a6a54;   /* labels, italic body */
  --mute-fog:     #a89a82;   /* hairlines, deprioritised */

  /* Accents */
  --rust:         #9c2a1a;   /* delays, live, recommended mark */
  --navy:         #1a4d6f;   /* notices, advisories */
  --field:        #1f6d3b;   /* clear service */

  /* Cartographic */
  --lake:         #cedde2;
  --river:        #cbd4c5;

  /* Type */
  --serif:  "Fraunces", "GT Sectra", "Playfair Display", Georgia, serif;
  --sans:   "Inter", -apple-system, system-ui, sans-serif;
  --mono:   "JetBrains Mono", "IBM Plex Mono", ui-monospace, monospace;

  /* Rules */
  --rule:        1px solid var(--ink);
  --rule-thick:  2px solid var(--ink);
  --rule-double: 5px double var(--ink);
  --hairline:    1px solid var(--mute-fog);
}
```

Add Google Fonts to `index.html`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Fraunces:ital,opsz,wght@0,9..144,400..900;1,9..144,400..900&family=JetBrains+Mono:wght@400;500;600;700&display=swap" />
```

### Type ramp

|Role            |Family        |Size |Weight|Style                      |Notes                                                     |
|----------------|--------------|----:|-----:|---------------------------|----------------------------------------------------------|
|Display italic  |Fraunces      |48   |500   |italic                     |“The Chicago”                                             |
|Display         |Fraunces      |48   |700   |roman                      |“Routefinder”                                             |
|Headline        |Fraunces      |28   |700   |roman                      |screen titles                                             |
|Subhead italic  |Fraunces      |20   |400   |italic                     |“toward the Loop”                                         |
|Drop-cap minutes|Fraunces      |72–96|700   |italic                     |total trip time; capped at 56px below 360px viewport width|
|Body serif      |Fraunces      |15   |400   |roman                      |descriptions                                              |
|Body italic     |Fraunces      |14   |400   |italic                     |flavor copy                                               |
|UI caps label   |Inter         |10   |700   |uppercase, letter-spacing 2|section headers                                           |
|Mono figure     |JetBrains Mono|11–13|500   |tabular-nums               |times, ETAs                                               |

### CTA line colors (unchanged)

```js
LINE_COLORS = {
  "Red Line":    "#c60c30",
  "Blue Line":   "#00a1de",
  "Brown Line":  "#62361b",
  "Green Line":  "#009b3a",
  "Orange Line": "#f9461c",
  "Purple Line": "#522398",
  "Pink Line":   "#e27ea6",
  "Yellow Line": "#f9e300",  /* black text on this one */
}
```

## Components — redesign specs

### Line pill (`<LinePill>`)

Replaces inline `<span className="leg-pill" style={{background: color}}>`.

- Display: inline-flex, align/justify center
- Sizes: sm (h:20, minW:22, fs:9), md (h:26, minW:26, fs:11), lg (h:34, minW:34, fs:13)
- Background: `LINE_COLORS[line]` or `BUS_DIRECTION_COLORS[line]`
- Color: `#fff`, except Yellow Line → `#111`
- Font: `var(--sans)` 900, letter-spacing 1
- Border-radius: 2px (square-ish, not rounded)
- Inset shadow: `inset 0 0 0 1px rgba(0,0,0,0.25)`
- Content: 2-letter abbreviation (`RD`, `BL`, `BR`, `GR`, `OR`, `PU`, `PI`, `YL`) at sm; line name at lg; bus uses `line_code`

### Signal lamp (`<SignalLamp>`)

Replaces nothing — new addition. Conveys “live data” presence.

- 7×7 px circle, background `var(--rust)`, box-shadow `0 0 6px var(--rust), 0 0 0 1.5px var(--paper)`
- Animation: `flicker` 3.4s infinite step-end (defined below)
- Adjacent label: caps `var(--mute)` “Signal Verified · Live”

```css
@keyframes flicker {
  0%, 100% { opacity: 1 }
  45% { opacity: 1 }
  50% { opacity: 0.35 }
  55% { opacity: 0.9 }
  60% { opacity: 0.5 }
  65% { opacity: 1 }
}
```

Use on: header (whenever data has loaded successfully), Live Trip screen, Pinned Stops board, lock-screen widget.

### Special dispatch (`.special-dispatch`)

Replaces `.recommendation`, `.alert-item`, `.alerts-section`, `.off-route-banner`.

- Outer: 3px double `var(--ink)` border, 12/14 px padding, `var(--paper-bright)` background
- Inner pseudo: `::before` absolute 4px-inset 1px solid `rgba(23,19,16,0.18)`
- Caption (`.special-dispatch__kicker`): 9px `var(--sans)` 800, letter-spacing 1, uppercase, `var(--rust)` for delays / `var(--navy)` for notices / `var(--mute)` for minor
- Body: serif italic, 13/1.45

### Paper grain (`.paper-grain`)

Body background. Two layered radial-gradient dots:

```css
.paper-grain {
  background-color: var(--paper);
  background-image:
    radial-gradient(rgba(23,19,16,0.035) 1px, transparent 1px),
    radial-gradient(rgba(23,19,16,0.025) 1px, transparent 1px);
  background-size: 3px 3px, 7px 7px;
  background-position: 0 0, 1px 2px;
}
```

### Rules

- `.rule-hairline` — 1px `var(--ink)` (between list items)
- `.rule-thick`   — 2px `var(--ink)` (under masthead, section breaks)
- `.rule-double`  — 5px height, top + bottom 1px `var(--ink)` (chapter starts)
- `.rule-dashed`  — 1px dashed `var(--mute-fog)` (within cards)

### Buttons

- Primary (`.btn-primary` — replaces `<button type="submit">`, `start-trip-btn`):
  background `var(--ink)`, color `var(--paper)`, no border, padding 14/20, `var(--serif)` 15/600 italic, full width, cursor pointer.
  Label suggestion: replace “Find Route” / “Start Trip” copy with `t()` keys that read “Commence Journey ⟶” — but ship under existing i18n keys, just edit the English string in `frontend/public/locales/en/translation.json`.
- Secondary (`.btn-secondary` — `save-route-btn`, `swap-btn`, `geo-btn`):
  transparent background, 1px `var(--ink)` border, `var(--ink)` color, `var(--serif)` 14/500
- Ghost (`.btn-ghost` — `pin-btn`, `geo-denied-dismiss`):
  no border, mono `var(--mute)`

### Form (`.form`)

Replaces the current label/input layout.

- Wrapper: `.paper-grain-bright` panel, `var(--rule)` border, padding 14/16
- Each row: flex baseline gap 10, `from`/`to` italic serif 14 in a 36px width column on the left, then the input value as serif 19/600 (instead of an `<input>` look — use `LocationInput` with `border:none; background:transparent; font: 19px/1.2 var(--serif); font-weight: 600;`)
- Divider between rows: `1px dashed var(--mute-fog)`, padding 12/0

### LocationInput dropdown

Same component (`LocationInput.jsx`), restyled:

- Suggestions: `var(--paper-bright)` background, `var(--rule)` border, no rounded corners
- Each item: 12px padding, `var(--hairline)` separator, hover `var(--paper-folio)`
- Highlighted match: `var(--rust)` underline (no background change)

### RouteCard (`<RouteCard>`)

Replaces the entire current card chrome.

- **Card root** (`.route-card`): 16/22 px padding, `var(--hairline)` between cards, no shadow, no border-radius. Best card adds `background: var(--paper-bright)`. Selected card adds a 2px left border `var(--rust)`.
- **Best badge** (`.route-badge`): replace pill with caps “★ Recommended Path” — 9px Inter 800, letter-spacing 2, uppercase, `var(--rust)`.
- **Header** (`.route-card-header`): flex-start gap 16
  - **Drop-cap minutes**: 72px Fraunces 700 italic, letter-spacing -3, line-height 0.82. **Capped at 56px on viewports narrower than 360px** (`@media (max-width: 359px) { font-size: 56px }`).
  - **Right column**: caps “minutes total” + serif italic 14/1.35 description (“A direct ride. Next departure in 3 minutes.”) + line pills row
- **Chevron**: replace `▲ ▼` with serif “▿” / “▵” at 12px `var(--mute)`. Or remove — make the whole header click-to-expand with no glyph.
- **Legs** (`.route-legs`): single thin vertical rule on the left, 7×7 px square markers (color = leg’s line color, 1.5px `var(--ink)` border), hairline between legs. Walk legs use serif italic; transit legs use `<LinePill size="sm">` + serif 15/600 “from → to” + caption “{stops} stops · {direction}” in serif italic 11.
- **Trip footer** (`.route-card-trip-footer`): top border `var(--rule-thick)`, padding 14/0, primary “Commence Journey ⟶” or “End Trip”; on-vehicle toggle becomes a secondary button.
- **Off-route banner**: re-skin as `.special-dispatch` with `--rust` kicker “Advisory — You are off route” and two buttons inline (Reroute primary, Dismiss ghost).

### PinnedStopsBoard (`<PinnedStopsBoard>`)

Sits at top of main column above the form.

- Container: padding 12/22, hairline below
- Heading: caps “Pinned Stops” + signal lamp on the right
- Each stop: flex baseline, `<LinePill size="sm">` + serif 15/600 stop name + mono ETA right-aligned (“3m” “DUE”)
- Refresh button: ghost, mono `↺`, top right of section
- Unpin: ghost `×`, appears on hover on desktop, always visible on mobile

### ServiceAlertsBar (`<ServiceAlertsBar>`)

Stack of `.special-dispatch` blocks below pinned stops, above the form.

- Each: kicker is `Major` (rust) / `Minor` (navy) / `Advisory` (mute), serif italic body, mono “{when}” right side, dismiss `×` ghost top-right
- The page/section title for the full-screen Alerts view must use `var(--ink)` — **not** `var(--paper-bright)`

### SettingsPanel (`<SettingsPanel>`) — modal/sheet

Replaces current settings inline.

- Backdrop: `rgba(23,19,16,0.55)`, click-to-close
- Sheet: max-width 480px, full bleed paper, `var(--paper-bright)` card with `var(--rule-thick)` border, padding 24, masthead “⟡ Settings ⟡” caps + thick rule
- Sections:
  - **API Key (BYOK)** — caps label + serif italic 12 description (“Your Anthropic key, stored only in this tab and cleared after 30 minutes of inactivity.”) + minimal underline-style input
  - **Walk speed** — three radio chips: “Slow”, “Standard”, “Brisk” (border var(–ink), active fills with `var(--ink)` and uses `var(--paper)` text)
  - **AI recommendation** — single toggle row: serif label + native checkbox restyled as a square ink box that fills with `✓` when on
  - **Language** — restyle existing `<select>` with `var(--rule)` border, no chrome, serif 15
- Close: ghost `×` top right; primary “Save & close” at bottom

### SavedRoutesPanel (`<SavedRoutesPanel>`)

Same structure as Pinned Stops board, different content. Caps “Saved Voyages”, route entries: serif “{from} → {to}” + mono “{total}m” + line pills row + delete ghost `×`.

### WeatherStrip (`<WeatherStrip>`)

A subtle one-line band above results (or in the masthead area).

- Padding 8/22, `var(--hairline)` top + bottom
- Mono temperature + serif italic condition (“47° · partly cloudy, gusts from the lake”) + caps “weather” right-aligned in `var(--mute)`

### LoadingSkeleton (`<LoadingSkeleton>`)

Editorial skeleton: serif italic “Plotting…” + animated double rule (the lower line scrolls left-to-right).

```css
@keyframes plot-rule {
  0% { transform: translateX(-100%) }
  100% { transform: translateX(100%) }
}
```

### Header (top of app)

Replace the current `.header` block with a masthead:

- Top row: caps date (left) “Monday, April 28” + caps “Vol. IV · No. 112” (right). The volume/issue is a deterministic hash of `new Date()` — keep it; it sets the editorial tone.
- Thick rule
- Title: “The Chicago” (Fraunces 38/500 italic `var(--ink)`) + “Routefinder.” (Fraunces 38/700 `var(--ink)`, period in `var(--rust)`). **Both halves of the title must use `var(--ink)` — never `var(--paper-bright)` or any paper variant.**
- Tagline: serif italic 12, `var(--mute)` — replace `t(“tagline”)` English string with “A working guide to the trains, buses, and schedules of the city.”
- Controls row (settings ⚙, saved-routes ⭐, transit-mode `<select>`, language `<select>`): placed **below the title, above the origin/destination form** — not in the top-right of the masthead. Styled as ghost icon buttons / selects with hairline border, no rounded corners. This placement prevents horizontal overflow on narrow viewports.

### Tab bar (mobile — implement)

Replace the current single-column scroll model with a **fixed bottom tab bar** on mobile. Four tabs: **Home / Map / Alerts / Saved**.

- Fixed to bottom of viewport; `var(--rule-thick)` top border
- Background: `var(--paper-folio)`
- Tab label: serif 13; italic for inactive tab, roman + `var(--rust)` underline for active
- Icons: use existing emoji (📍 Home, 🗺 Map, ⚠ Alerts, ⭐ Saved) or plain text only — your call
- Add `padding-bottom` to the main scroll container equal to tab bar height (~56px) to prevent content overlap
- RTL: tab order reverses naturally with `dir="rtl"` — use logical flex properties

### Map overlays

The MapLibre map itself is unchanged. Add a floating `.map-train-card` panel top-right showing live vehicle info, and a bottom-left `.map-legend` line chip. These are pure CSS additions on top of the existing `<MapView>`.

**Vehicle label rules:**
- When on a train route: label reads **”Your Train”**
- When on a bus route: label reads **”Your Bus”**
- The label is driven by whether the active route uses `LINE_COLORS` (train) vs `BUS_DIRECTION_COLORS` (bus)
- The route name text beside the vehicle symbol (e.g. “Bus 78”, “Red Line”) uses `var(--ink)` — **never** a paper or muted color

## Screens (full inventory)

|#|Screen               |Source file in current codebase                    |Design file in this bundle|
|-|---------------------|---------------------------------------------------|--------------------------|
|1|Home / Search        |`App.jsx` (form + pinned stops + alerts)           |`Mobile.html` 01 Home     |
|2|Search autocomplete  |`LocationInput.jsx` dropdown                       |`Mobile.html` 02 Search   |
|3|Results (multi-route)|`App.jsx` `.routes-section`                        |`Mobile.html` 03 Results  |
|4|Live trip in progress|`RouteCard.jsx` + `App.jsx` trip state             |`Mobile.html` 04 Live Trip|
|5|Station detail       |(new — derive from `PinnedStopsBoard` arrival data)|`Mobile.html` 05 Station  |
|6|Service alerts list  |`ServiceAlertsBar.jsx` (expand into full screen)   |`Mobile.html` 06 Alerts   |
|7|Saved routes & places|`SavedRoutesPanel.jsx` + `LabelSavePanel.jsx`      |`Mobile.html` 07 Saved    |
|8|Lock-screen widget   |(PWA — no current code)                            |`Mobile.html` 08 Widget   |
|9|Desktop split view   |`App.jsx` `.layout--split`                         |`Desktop.html`            |

## Behaviors (preserve as-is)

- **GPS leg advancement** (60 m walk / 150 m on-vehicle): keep all logic in `App.jsx :: processTripPosition`. Only restyle the resulting “current leg” indicator — radar pulse on the active stop marker (SVG `<animate>` on `r` 4→16 + `opacity` 0.7→0).
- **Off-route detection** (400 m threshold): show as `.special-dispatch` with `--rust` kicker
- **BYOK idle clear** (30 min): unchanged; settings panel just hosts the field
- **i18n RTL** (`ar`, `ur`, `ps`): the redesign must work with `dir="rtl"`. Use logical CSS properties (`padding-inline`, `border-inline-start`, etc.) anywhere positional. The italic display works in RTL too.
- **Pinned arrivals refetch** (60 s): `useApiQuery` handles it. Add a small mono “↺ updated 12s ago” timestamp under the board if you want.
- **Service alert dismiss**: persists to `sessionStorage`. Keep.

## Motion & principles

Six rules to apply when in doubt. Reproduced from `D2Principles` in `designs/d2-system.jsx`:

1. **Read the city like a broadsheet** — the interface is a daily paper.
1. **Lead with the numeral** — minutes are the hero, italic serif, generous space.
1. **Italic softens, caps direct** — serif italic for voice, UI caps for wayfinding.
1. **Lamps, not sirens** — live state flickers at the edge.
1. **Place before route** — lake on the right, river bending through.
1. **A small red for consequence** — rust is reserved for live state, delays, and the recommended mark — never decorative.

## Files in this bundle

```
designs/
├── The Chicago Routefinder.html              ← full study, all four sections
├── The Chicago Routefinder - Cover.html       ← masthead + map plate
├── The Chicago Routefinder - Mobile.html      ← 8 phone screens
├── The Chicago Routefinder - Desktop.html     ← broadsheet split view
├── The Chicago Routefinder - Design System.html  ← type, color, components, principles
├── d2-editorial.jsx     ← all 9 screen components (D2Home, D2Search, D2Results, …)
├── d2-system.jsx        ← design-system specimen plates
├── data.jsx             ← shared LINE_COLORS, MOCK_RESULT, LIVE_TRIP, SAVED_PLACES
├── schematic-map.jsx    ← stylized line-map SVG
└── design-canvas.jsx    ← presentation chrome (Figma-ish — strip when implementing)
```

`design-canvas.jsx` is presentation chrome only — pan/zoom canvas with cards. The actual UI is in `d2-editorial.jsx`. When implementing, ignore the canvas wrapper and use the inner `<D2Home>`, `<D2Results>`, etc. as your visual reference.

## Implementation plan (suggested order)

1. **Tokens + fonts.** Add the `:root` block to `App.css`, add Google Fonts to `index.html`. Re-test that nothing visibly breaks.
1. **Header masthead.** Restyle `.header` in `App.css` — date + vol/issue, thick rule, two-weight title, tagline. Update `t("app_title")` to “The Chicago Routefinder” and the English `tagline` string.
1. **Tab bar.** Implement fixed bottom 4-tab nav (Home / Map / Alerts / Saved). Add `padding-bottom` to main scroll container.
1. **Form + LocationInput.** Restyle to the cream-paper editorial form.
1. **RouteCard.** This is the centerpiece. Drop-cap minutes (with 56px cap below 360px), hairline legs, line pills, special-dispatch advisory.
1. **Pinned Stops + Service Alerts + Weather.** Three small bands above the form.
1. **Settings + Saved Routes panels.** Modal sheets.
1. **Live Trip footer + off-route banner + radar-pulse current stop.**
1. **Loading skeleton + map overlays.**
1. **RTL pass.** Sweep for any `padding-left`, `text-align: left`, `transform: translateX` etc.
1. **Cleanup.** Remove the old token usages in `App.css` once everything’s migrated.

---

# Part II — Design System Reference

The first half of this README documents the *redesign of the existing app*. This second half is a **standalone design system reference** for designing and building **new** features in the same language. When in doubt, return to the **Six Principles** above and the **Composition Patterns** below.

## Voice & content rules

The editorial language has a specific voice. New copy should pass these tests.

### Voice tests

| Test | Pass | Fail |
|---|---|---|
| Reads like a broadsheet, not a CRUD app | "Plotting your journey…" | "Loading…" |
| Treats the rider as a reader, not a user | "A direct ride. Next departure in 3 minutes." | "1 transit option found." |
| Uses verbs of motion + place | "Toward the Loop", "Disembark at Monroe", "Underway" | "Going to Loop", "Stop", "Active" |
| Italic for voice, caps for direction | *"toward the Loop"* + `STATION` | "**toward the loop**" + `Station` |
| Specific over generic | "Five stops remain. The train is on schedule." | "5 stops · on time" |

### Copy patterns

- **Caps headers**: 1–3 words, never a sentence. `DISPATCHES`, `NEXT TRAINS`, `RECOMMENDED PATH`.
- **Italic body**: full sentences with periods. Set in Fraunces italic 13–15. "A working guide to the trains, buses, and schedules of the city."
- **Mono numerics**: tabular figures, no commas under 10000. `17:47`, `21m`, `№ 412`, `5 stops`.
- **Drop-cap minutes**: bare number, italic Fraunces. The label sits beside it, not under it.
- **Numerals → italic serif** when emphatic ("**14** *minutes to disembark*"); **mono** when in a list ("17:47 · 21m").
- **No emoji in body copy.** UI-control emoji (⚙ ⭐ 📌 🚶 ↺ ⇅) are fine where the existing app uses them; do not add new emoji to descriptions, alerts, or headlines.
- **Punctuation**: prefer **·** (middot) over commas in metadata rows. Em-dashes for asides. Periods at end of italic sentences.
- **Articles matter**. "The Chicago", not "Chicago". "A direct ride", not "Direct ride". Definite/indefinite articles soften the broadsheet voice.

### Naming patterns

When introducing new screen-level concepts, prefer editorial nouns:

| Concept | Editorial name |
|---|---|
| Settings | "Preferences" or "The Editor's Desk" (hard pivot — pick one) |
| Trip history | "The Logbook" |
| Notifications | "Dispatches" |
| Onboarding | "Foreword" or "First Issue" |
| Empty state | "Nothing filed yet." |
| 404 | "Page misplaced." |
| Error | "Dispatch failed." |
| Confirmation modal | "A small notice" |

These aren't mandatory but illustrate the register. New surface names should sit comfortably alongside *Underway*, *Disembark*, *Special Dispatch*, *Frequents*, *Saved Voyages*.

## Composition patterns (recipes)

Building blocks compose into recurring layouts. Use these as templates for new surfaces.

### Pattern 01 — Page scaffold

Every full-screen view follows the same skeleton:

```
[Caps kicker · 10px Inter, mute]            ← page locator ("PAGE 2 — DISPATCHES")
[Headline · Fraunces 28–34, italic + roman]  ← screen title
[Thick rule]                                 ← 2px ink under headline
[Italic standfirst · 13/1.55, mute]          ← optional one-sentence subtitle
[Content blocks · separated by hairline]
[Tab bar fixed bottom]
```

Mobile padding: 22px horizontal, 18–22px top, 80px bottom (clears tab bar).

### Pattern 02 — Form surface

For any data-entry surface (settings, search, login, fare entry):

- Wrap in a `var(--paper-bright)` panel with `var(--rule)` border, padding 14/16
- Each field: flex baseline gap 10
  - Left: italic serif 14 mute label in a 36–48px column ("from", "to", "key", "speed")
  - Right: serif 19/600 value, plain-looking input (`border:none; background:transparent;`)
- Between fields: `1px dashed var(--mute-fog)`, padding 12/0
- No explicit field borders. The panel's outer border + dashed dividers do the work.
- Submit button: full-width primary at bottom of panel, 14/20 padding, no margin top (let the dashed rule do it)

### Pattern 03 — List surface

For any vertical list (saved places, recent searches, station departures, alert feed):

- No card backgrounds. The list is a **ruled column**.
- Each item: padding 9–12 / 0, `border-bottom: var(--hairline)`. Last item: no border.
- Item layout: flex baseline
  - Optional prefix glyph (§1, §2, a., b., or `<LinePill size="sm">`)
  - Primary label: serif 16/600
  - Italic sub: serif italic 11–13, mute
  - Right: mono ETA / status caps

```
§1  Home                      3m
    Logan Square Blue stop
─────────────────────────────────
§2  Work                      11m
    Monroe Blue / Red stop
```

### Pattern 04 — Card stack

Sparingly used. Only when items genuinely benefit from being chunked (route results, suggested trips). Each card:

- `var(--paper-bright)` background + `var(--rule)` only on the **first/best** card
- All other cards: no background, hairline divider above and below
- Selected: 2px `var(--rust)` border-inline-start, no other styling change
- Padding: 16 horizontal, 22 vertical

### Pattern 05 — Special Dispatch (advisory block)

For anything that interrupts the reading flow: alerts, advisories, off-route warnings, error states, confirmations, info notices, onboarding hints.

- 3px **double** `var(--ink)` border (this is the diagnostic feature — never solid)
- 4px-inset 1px hairline frame inside (`::before` pseudo-element)
- `var(--paper-bright)` background, paper-grain pattern
- Caps kicker (9px Inter 800, letter-spacing 1):
  - `var(--rust)` for **delay / error / off-route / major**
  - `var(--navy)` for **notice / advisory / info**
  - `var(--mute)` for **minor / passive**
  - `var(--field)` for **clear / resolved / success**
- Italic body: serif 13/1.45, ink-soft
- Optional inline buttons at bottom right (primary + ghost)

This is the most reusable component. Reach for it whenever the reader needs to pause.

### Pattern 06 — Section with sidebar marginalia

For dense informational screens (station detail, fare zones, schedules):

- Two-column grid: 1fr / 1px / 1fr (or 2fr / 1px / 1fr for asymmetry)
- Vertical 1px ink rule between columns
- Left: caps header + ruled list
- Right: caps header + ruled list (or italic running prose)

Used in `D2Home` for FREQUENTS / DISPATCHES. Generalizes to any "two glances on one page."

### Pattern 07 — Hero numeral

When a single number is the answer: trip duration, ETA, fare, distance.

- Numeral: Fraunces italic 700, sized 52–96 px depending on prominence
  - 52: sidebar / desktop column
  - 64: lock-screen widget
  - 72: results card
  - 96: live trip header
- Letter-spacing: −3 (at 52–72) to −5 (at 96)
- Line-height: 0.82–0.85
- Label: italic serif 14–16 stacked to the **right**, two lines max
  - Top line: descriptor ("minutes")
  - Bottom line: object ("to disembark", "until departure", "to fare")
- Never center-align; always flush-left numeral with right-flush label

### Pattern 08 — Empty state

For "no data yet" surfaces (no saved places, no trip history, no alerts):

- Full-width hairline-bordered area, padding 40 vertical
- Centered:
  - Caps kicker `var(--mute)` ("Nothing filed yet.")
  - Italic serif 16 explanation ("Pin a stop or two from search results to see live arrivals here.")
  - Optional ghost CTA below

No illustrations. The cream paper *is* the illustration.

### Pattern 09 — Loading state

- Replace content with italic serif "Plotting…" / "Identifying…" / "Filing…"
- Below: a 1px hairline that animates from translateX(-100%) to translateX(100%) infinite, 1.4s ease-in-out
- Never spin a circle. Never use a progress bar with a percentage.
- For longer loads (>2s): switch to skeleton lines — 1px hairlines at 70% / 90% / 60% widths, faintly pulsing opacity 0.4 → 0.7 → 0.4

### Pattern 10 — Modal sheet

For surfaces requiring focus: settings, label-save, confirmation.

- Backdrop: `rgba(23,19,16,0.55)`, click-to-dismiss
- Sheet: max-width 480 (desktop) / full-bleed (mobile bottom-sheet style), `var(--paper-bright)`, `var(--rule-thick)` border
- Header: caps title centered between two `⟡` ornaments ("⟡ Preferences ⟡"), thick rule below
- Content: 24px padding, hairline-divided sections
- Close: ghost `×` top-right (32×32 hit target)
- Bottom action row: primary + ghost cancel, separated by `var(--rule-thick)` above

### Pattern 11 — Toast / snackbar (transient)

Avoid. The editorial language is calm — transient toasts feel jittery. Instead:
- Use a Special Dispatch block that auto-dismisses after 4 seconds with a fade
- Or update an inline status line in italic mute

If a toast is unavoidable (network errors during a trip), use a fixed-bottom-of-screen Special Dispatch with `var(--rust)` kicker, slide-up entry, fade-out exit.

### Pattern 12 — Step / wizard

For multi-step flows (onboarding, fare-card setup, multi-leg trip planning):

- Top: caps "STEP 2 OF 4" left, caps screen name right
- Headline below
- Content
- Bottom: ghost "← Back" + primary "Continue ⟶". Never use "Next" — always a verb of intent ("Continue", "Confirm", "Commence").

## Layout constants

| Token | Mobile | Desktop |
|---|---:|---:|
| Outer padding | 22 | 24 |
| Section vertical | 18–22 top, 10–14 bottom | 24/16 |
| Tab bar height | 56 | n/a |
| Modal max-width | 100vw | 480 |
| Form input height | 28 (visible text height) | 28 |
| Tap target min | 44 | 32 |
| Card padding | 16 / 22 | 20 / 24 |
| Item padding (in list) | 12 / 0 | 14 / 0 |
| Stack gap (between sections) | 18 | 24 |

## Iconography

The editorial language is **glyph-first, icon-last**. Order of preference:

1. **Typographic glyphs** — `→ ⟶ ↑ ↓ ↺ ⇅ ⟡ § № ★ ☉ ★ ✓ ×`
2. **Existing emoji already in i18n** — `🚶 ⭐ ⚙ 📌 📍 ⏱ ⚠`
3. **Hand-drawn 1px-stroke SVGs** — match the line weight of the typeface (0.06em). No filled shapes.
4. **No outline-icon-libraries** (no Lucide, Heroicons, Material). Their geometry is wrong for this aesthetic.

If you need a new icon: try a glyph first. Try a single italic letter second (Fraunces italic "i" inside a circle is more on-brand than a Lucide info icon).

## Color usage rules

| Color | Use | Don't |
|---|---|---|
| `--paper` | All backgrounds | Don't fill cards on cards (use paper-bright instead) |
| `--paper-bright` | Featured panels, modals | Don't use for the body |
| `--paper-folio` | Hairline-bordered subsections, alternating list rows | Don't use as a card |
| `--ink` | Type, rule lines, primary buttons | Don't tint to gray; use `--ink-soft` |
| `--ink-soft` | Body copy on cream | Don't use for headlines |
| `--mute` | Caps labels, italic body, deprioritised | Don't use for primary type |
| `--mute-fog` | Hairlines, dashed rules, placeholder text | Don't use for any actual type the user reads |
| `--rust` | **Live state, delays, recommended mark, errors.** Reserved. | Don't use decoratively. Don't use for buttons. Don't use for icons unrelated to consequence. |
| `--navy` | Notices, advisories, info | Don't use as accent on positive states |
| `--field` | Clear service, success, resolved | Don't use heavily — sparing green is more credible |
| `--lake` / `--river` | Map fills only | Don't use in UI chrome |

**Rule of thumb:** if you're tempted to add a third or fourth color to a screen, you're probably solving an information-hierarchy problem with color. Solve it with type + rule weight first.

## Motion catalog

| Animation | Use case | Duration | Easing | Notes |
|---|---|---:|---|---|
| `flicker` | Live state lamp, search caret | 3.4s (lamp) / 1s (caret) | step-end | infinite loop |
| `radar-pulse` | Current stop on Live Trip | 2s | linear | infinite loop, SVG `<animate>` |
| `plot-rule` | Loading state | 1.4s | ease-in-out | infinite loop |
| Page transition | Tab change | 220ms | ease-out | translateX 8px + fade |
| Sheet/modal in | Settings, save panel | 280ms | cubic-bezier(.2,.8,.2,1) | translateY 16px + fade |
| Card expand | Route legs reveal | 250ms | cubic-bezier(.2,.8,.2,1) | height auto |
| Hover (desktop) | Buttons, list items | 120ms | ease-out | background change only |
| Press (mobile) | Tap feedback | 80ms in / 200ms out | ease-out | opacity 1 → 0.7 → 1 |
| Number tick | ETA changes by 1 minute | 600ms | cubic-bezier(.2,.8,.2,1) | translateY 100% |

**All animations must respect `prefers-reduced-motion: reduce`.** Static fallbacks documented per-keyframe.

## Anti-patterns (don't do)

These are easy mistakes that break the language:

- **Drop shadows or elevation.** Depth comes from rule weight + paper grain. A shadow makes the design look like a Material redesign.
- **Pill / capsule buttons.** Buttons are square (radius 0–2px max).
- **Gradient anything.** No background gradients, no text gradients, no border gradients.
- **Sentence case caps headers.** Caps headers are *all caps*, period. Don't mix-case "Pinned Stops" → it must be `PINNED STOPS` or `Pinned Stops` in serif (no caps treatment at all).
- **Multiple accent colors on one surface.** One screen, one or two accent colors max. Rust + navy together is fine; rust + navy + green + orange is a Trapper Keeper.
- **Centered body copy.** Italic body sentences set left-aligned, ragged-right. Centered serif italic looks like a wedding invitation.
- **Sans-serif body.** Inter is for caps labels and mono is for figures. Body is always Fraunces.
- **Replacing the schematic with a generic gradient.** The lake + river orientation is core. If you simplify the map, keep at minimum a hairline lake edge on the right.
- **Decorative line pills on non-line surfaces.** Pills mean "this is a CTA line." Don't use them as colored badges for tags, categories, statuses.
- **Adding a primary brand color outside the four already defined.** No teal, no purple, no orange. Rust = consequence; navy = info; field = success; ink = everything else.
- **Adding "modern" UI tropes**: dark mode toggles, glassmorphism panels, animated gradients on CTAs, hero illustrations, mascots. None of it.

## Accessibility checklist

For any new component, verify:

- [ ] Color contrast: ink on paper = 15.4:1 (AAA), mute on paper = 4.7:1 (AA), rust on paper = 6.8:1 (AA), navy on paper = 7.2:1 (AA). New tints must clear 4.5:1 minimum.
- [ ] Caps text uses `text-transform: uppercase` in CSS, NOT pre-uppercased strings — screen readers handle the former better.
- [ ] Tap targets ≥ 44×44 px on mobile. If the visible element is smaller (e.g. line pills at 26 px), wrap in a 44×44 hit target.
- [ ] `prefers-reduced-motion: reduce` disables flicker, radar pulse, page transitions. Static fallbacks defined.
- [ ] `prefers-contrast: more` thickens hairlines to 2px and forces all `--mute` to `--ink-soft`.
- [ ] RTL: use logical CSS properties (`padding-inline-*`, `border-inline-*`, `margin-inline-*`). Italic display works in RTL.
- [ ] Live regions: ETA changes use `aria-live="polite"`. Off-route advisories use `aria-live="assertive"`.
- [ ] Keyboard: tab order matches visual order, focus rings are 2px `--rust` outline (offset 2px) — visible against cream, distinct from hover.
- [ ] Forms: every input has a programmatic label (the italic serif "from" / "to" must be `<label>` or `aria-label`).

## Designing a new feature — checklist

When Claude Code is asked to design something new in this language, walk through:

1. **What kind of surface is this?** Match to a Composition Pattern (01–12 above).
2. **What's the page scaffold?** Caps kicker + headline + thick rule + content. No exceptions.
3. **What's the hero element?** A numeral (Pattern 07)? A list (03)? A form (02)? Pick one focus per screen.
4. **Where's the live signal?** If data is live, place a `<SignalLamp>` at the top-right of the relevant section.
5. **What needs interruption?** Use a Special Dispatch (Pattern 05). Pick the right kicker color.
6. **What's the verb?** All actions are verbs of intent (Commence, Confirm, Disembark, File, Plot, Identify). Never "Submit", "OK", "Done".
7. **Does it need a new color?** No. Use what's defined.
8. **Does it need a new font?** No. Use what's defined.
9. **Could a glyph or italic letter replace this icon?** Almost always yes.
10. **Does it pass the voice tests?** Re-read copy aloud. If it sounds like a CRUD app, rewrite.

## Token reference (full)

```css
:root {
  /* — Paper — */
  --paper:        #f2ece0;
  --paper-bright: #fffbef;
  --paper-folio:  #e9e1d1;

  /* — Ink — */
  --ink:          #171310;
  --ink-soft:     #4a3f32;
  --mute:         #7a6a54;
  --mute-fog:     #a89a82;

  /* — Accents (semantic) — */
  --rust:         #9c2a1a;   /* consequence */
  --navy:         #1a4d6f;   /* notice */
  --field:        #1f6d3b;   /* clear */

  /* — Cartographic — */
  --lake:         #cedde2;
  --river:        #cbd4c5;

  /* — Type — */
  --serif:  "Fraunces", Georgia, serif;
  --sans:   "Inter", system-ui, sans-serif;
  --mono:   "JetBrains Mono", ui-monospace, monospace;

  /* — Type scale — */
  --fs-display:    48px;   --lh-display:    0.95;
  --fs-headline:   28px;   --lh-headline:   1.05;
  --fs-subhead:    20px;   --lh-subhead:    1.25;
  --fs-body:       15px;   --lh-body:       1.55;
  --fs-body-sm:    13px;   --lh-body-sm:    1.5;
  --fs-caps:       10px;   --lh-caps:       1.2;   --ls-caps:    2px;
  --fs-mono:       12px;   --lh-mono:       1.3;
  --fs-numeral-sm: 52px;
  --fs-numeral-md: 72px;
  --fs-numeral-lg: 96px;

  /* — Rules — */
  --rule:        1px solid var(--ink);
  --rule-thick:  2px solid var(--ink);
  --rule-double: 5px double var(--ink);
  --hairline:    1px solid var(--mute-fog);
  --dashed:      1px dashed var(--mute-fog);

  /* — Spacing scale (use multiples of 2) — */
  --sp-1:  2px;
  --sp-2:  4px;
  --sp-3:  8px;
  --sp-4:  12px;
  --sp-5:  16px;
  --sp-6:  22px;
  --sp-7:  32px;
  --sp-8:  48px;
  --sp-9:  72px;

  /* — Radii — */
  --r-0: 0;
  --r-1: 2px;   /* line pills only */

  /* — Motion — */
  --ease-out:   cubic-bezier(.2,.8,.2,1);
  --dur-quick:  120ms;
  --dur-base:   220ms;
  --dur-slow:   320ms;
}
```

## Resolved decisions

|Question                                  |Decision                                                                                                    |
|------------------------------------------|------------------------------------------------------------------------------------------------------------|
|App name / rebrand                        |**Rebrand.** `t("app_title")` → “The Chicago Routefinder” across all locales.                               |
|Tab bar                                   |**Implement.** Fixed bottom 4-tab bar (Home / Map / Alerts / Saved) replaces the single-column scroll model.|
|Vol/Issue masthead numbering              |**Keep.** Deterministic hash of `new Date()` for charm.                                                     |
|Drop-cap minutes overflow on small screens|**Cap at 56px** below 360px viewport width via `@media (max-width: 359px)`.                                 |