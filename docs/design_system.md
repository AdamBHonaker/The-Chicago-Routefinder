# The Chicago Routefinder — Design System Reference

A standalone design system reference for designing and building new features in the Routefinder's editorial language. When in doubt, return to the **Six Principles** and the **Composition Patterns** below.

## Six principles

Apply when in doubt:

1. **Read the city like a broadsheet** — the interface is a daily paper.
2. **Lead with the numeral** — minutes are the hero, italic serif, generous space.
3. **Italic softens, caps direct** — serif italic for voice, UI caps for wayfinding.
4. **Lamps, not sirens** — live state flickers at the edge.
5. **Place before route** — lake on the right, river bending through.
6. **A small red for consequence** — rust is reserved for live state, delays, and the recommended mark — never decorative.

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

When designing something new in this language, walk through:

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

Tokens live in [frontend/src/styles/tokens.css](../frontend/src/styles/tokens.css). The canonical set:

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
