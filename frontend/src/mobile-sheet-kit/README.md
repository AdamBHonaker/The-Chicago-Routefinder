# mobile-sheet-kit

A portable, project-agnostic mobile bottom-sheet UI for React. Adapted from the Passage walking-route app.

- **No dependencies** beyond React.
- **Theming via CSS custom properties** — bind `--bsk-*` vars to your project's design tokens.
- **i18n via props** — no hardcoded user-facing strings.
- **Configurable storage key** — multiple host projects in one workspace won't collide.
- **~500 LOC total**, including the velocity-aware drag math and body-scroll handoff.

## What you get

A draggable bottom sheet that snaps between three (configurable) heights, with the map / primary content always visible behind it:

```
┌──────────────────────────────────────────────┐
│  optional <masthead/>  (floating, top edge)  │
│                                              │
│      [ map content shows through here ]      │
│                                              │
│  ╭────────────────────────────────────────╮  │
│  │  drag handle                           │  │
│  │  sheet body — snap 0 / 1 / 2           │  │
│  ╰────────────────────────────────────────╯  │
└──────────────────────────────────────────────┘
```

## Required CSS variables

Bind these to your project's design tokens (see `tokens.example.css`):

| Var | Purpose | Required |
|---|---|---|
| `--bsk-paper` | Sheet background | yes |
| `--bsk-ink` | Hairline + text color | yes |
| `--bsk-mute-fog` | Drag-handle pill color | yes |
| `--bsk-rule` | Sheet's top border (full shorthand) | yes |
| `--bsk-ease` | Snap-settle easing curve | yes |
| `--bsk-dur` | Snap-settle duration | yes |
| `--bsk-safe-bottom` | Bottom safe-area inset | yes |
| `--bsk-safe-top` | Top safe-area inset (for masthead) | optional |
| `--bsk-shadow` | Sheet drop shadow | optional |
| `--bsk-handle-focus` | Drag-handle focus-ring color | optional |

## Quickstart

```jsx
import { MobileLayout, useMediaQuery } from "./mobile-sheet-kit";
import "./mobile-sheet-kit/bottom-sheet.css";
import "./mobile-sheet-kit-host.css";  // your --bsk-* bindings

function App() {
  const isMobile = useMediaQuery("(max-width: 800px)");
  const [snap, setSnap] = useState(0);
  const [mapPadding, setMapPadding] = useState(null);

  return (
    <div className="app">
      {/* render the map ONCE at the App level so it survives breakpoint flips */}
      <div className={isMobile ? "map-host map-host--mobile" : "map-host map-host--desktop"}>
        <MapView mapPadding={isMobile ? mapPadding : null} />
      </div>

      {isMobile ? (
        <MobileLayout
          storageKey="myapp:sheetSnap"
          handleLabel={t("drag_to_resize")}
          snap={snap}
          onSnapChange={setSnap}
          onObscuredChange={(px) =>
            setMapPadding({ top: 80, bottom: px + 16, left: 16, right: 16 })
          }
        >
          {/* your form, results, directions, etc. */}
        </MobileLayout>
      ) : (
        <DesktopLayout />
      )}
    </div>
  );
}
```

## Prop reference

### `<BottomSheet>`

```ts
{
  open?: boolean = true
  snapPoints?: Array<string | number> = ["140px", "50dvh", "88dvh"]
  snap?: number                     // controlled snap index
  defaultSnap?: number = 1          // uncontrolled initial
  onSnapChange?: (idx: number) => void
  obscuredAreaCallback?: (px: number) => void
  handleLabel?: string = "Drag to resize panel"
  children: ReactNode
  style?: React.CSSProperties
  className?: string
}
```

Snap-point strings accept `px` / `%` (of parent height) / `dvh` / `vh`. `decideSnap` and `resolveSnapPx` are exported for unit tests.

### `<MobileLayout>`

```ts
{
  masthead?: ReactNode              // optional floating header
  map?: ReactNode                   // optional full-bleed map slot
  snap?: number                     // controlled
  defaultSnap?: number = 0          // uncontrolled
  onSnapChange?: (idx: number) => void
  onObscuredChange?: (px: number) => void
  snapPoints?: Array<string | number>
  storageKey: string                // REQUIRED, e.g. "myapp:sheetSnap"
  handleLabel?: string
  children: ReactNode
}
```

Two integration patterns:

- **(a) Pass `map`** — kit renders a full-bleed map slot inside `.mobile-shell`. Simpler, but the map's React identity changes if you flip in/out of `<MobileLayout>` at a breakpoint.
- **(b) Don't pass `map`** — kit renders just the sheet (and optional masthead). You position the map yourself outside `<MobileLayout>`, e.g. inside an absolutely-positioned `.map-host` at the App level. **Recommended** when the map's identity must survive breakpoint flips (MapLibre / Mapbox lose their WebGL context when remounted).

### `useMediaQuery(query)`

SSR-safe `window.matchMedia` subscription hook. Returns `false` until mounted in a browser.

### `createSheetSnapStore(storageKey)`

Returns `{ load, save }` bound to a `localStorage` key. Out-of-range or unparseable values load as `null`. `save` rejects out-of-range indices and survives storage-disabled environments (Safari private mode).

## Persistence model

`MobileLayout` writes to localStorage **only on user-initiated drag releases**, debounced 500 ms. Programmatic snap changes pass through `onSnapChange` for the host to handle but are not persisted. This prevents auto-promote behaviors (e.g. "open sheet to half when search results arrive") from polluting the user's preferred opening height across sessions.

If your host needs a different policy, drive snap as a controlled prop and call `createSheetSnapStore` yourself.

## Map-padding pattern

`onObscuredChange(px)` fires on every settle with the px height of the visible sheet. Translate that into your map library's `padding` option for `fitBounds` / `cameraForBounds` so route polylines and place markers stay visible above the sheet:

```js
onObscuredChange={(bottomPx) =>
  setMapPadding({ top: 80, bottom: bottomPx + 16, left: 16, right: 16 })
}
```

For MapLibre / Mapbox, also call `map.resize()` on snap changes — the visible map area shrinks/grows when the sheet height changes.

## i18n

The kit ships zero hardcoded user-facing strings. Pass pre-translated text via props:

```jsx
<MobileLayout handleLabel={t("drag_to_resize")} ...>
```

The drag handle's `aria-label` is set from `handleLabel`. Internal segmented controls / nav elements are NOT part of the kit — those live in your project so they can use whatever i18n stack you have.

## Browser support

- **Pointer events** — all evergreen browsers.
- **`100dvh`** — Safari 15.4+. Falls back to `100vh` on older Safari (slightly wrong with the URL bar but functional).
- **`navigator.vibrate`** — Android Chrome only. iOS Safari ignores silently. Feature-detected.
- **`prefers-reduced-motion`** — honored: snap settle becomes 0 ms, velocity flick falls back to nearest snap, no haptic vibration.

## Limits / non-goals

- Not a modal. No focus trap. The sheet is a layered tray over the map; keyboard users can still tab into the map.
- Not a desktop component. Use a different layout above your mobile breakpoint.
- No built-in loading states or empty content rendering — the kit just hosts whatever children you pass.
- No drag-to-dismiss to fully hidden. Snap 0 is the smallest sheet height; below that the sheet is `open={false}` and removed from DOM.

## File layout

```
mobile-sheet-kit/
  index.js              — re-exports
  BottomSheet.jsx       — the draggable sheet primitive
  MobileLayout.jsx      — shell composition + persistence
  useMediaQuery.js      — SSR-safe matchMedia hook
  sheetSnap.js          — createSheetSnapStore factory
  bottom-sheet.css      — sheet + shell styles, --bsk-* themed
  tokens.example.css    — example host bindings
  README.md             — this file
```

## Future extraction

This kit is currently embedded inside the consumer project for fast iteration. Once stable it can be lifted into its own repo / npm package:

1. Copy `mobile-sheet-kit/` to a new repo. Add `package.json` with `peerDependencies: { react: ">=18" }`.
2. Build with `vite --mode lib` (or rollup); export `index.js` + `bottom-sheet.css` + `tokens.example.css`.
3. Consumers `npm install` it, then `import { MobileLayout } from "@your-scope/mobile-sheet-kit"` and `@import` the CSS.

The kit is intentionally written so this extraction requires zero source changes — only packaging.
