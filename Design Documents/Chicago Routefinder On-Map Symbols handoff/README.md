# Map Markers — Implementation Handoff

A focused handoff for replacing the three on-map symbols (origin, destination, live user position) in **The Chicago Routefinder** with the editorial marks defined in *Specimen E · Map Marks*.

This package supplements the main design handoff. Read [the parent README](../design_handoff_routefinder/README.md) first if you haven't — it covers the full design language, tokens, and typography. **This document is scoped strictly to the three map symbols.**

---

## Why these three

The previous markers (a Blue Line dot, a black star, a pulsing accent disc) were all *circles with stuff inside* — silhouette collisions at small sizes, no semantic distinction. The new marks are deliberately **three orthogonal silhouettes** so they can never be confused at any zoom level:

| Mark | Silhouette | Reads as | Color |
|------|------------|----------|-------|
| **§ Origin** | Square | A *place from which* — fixed, lettered | Ink |
| **✦ Destination** | Ring (concentric) | A *precise spot to which* — measured | Ink |
| **➤ Live position** | Compass needle | The *rider underway* — directional | Rust |

Rust is reserved for live state. Origin and destination stay in pure ink — they're coordinates, not consequences.

---

## Visual reference

See **Specimen E · Map Marks** in `The Chicago Routefinder - Design System.html` (or the full study) for the canonical anatomy, sizing, and motion behavior. Open it side-by-side while implementing.

---

## Implementation decisions

The following decisions were made in a design review session on 2026-04-30. **Read this section before touching any code.**

### 1. MapLibre integration — Option A (imperative, not react-map-gl)

`MapView.jsx` uses raw `maplibre-gl` imperatively, not `react-map-gl/maplibre`. **Do not introduce `react-map-gl` as a dependency.** Mount the React marker components using `maplibregl.Marker({ element })` + `ReactDOM.createRoot`. See the [MapLibre integration](#maplibre-integration) section below for the full pattern.

### 2. CSS transition on SVG `transform`

The original handoff had the compass needle group using an SVG `transform` *attribute* with a `style={{ transition }}` alongside it. CSS transitions do not apply to SVG presentation attributes — the transition would be silently ignored. **Use CSS `transform` via `style` instead** (see the corrected `LivePositionMarker.jsx` below).

### 3. `useId` removed from LivePositionMarker

The original draft imported and called `useId()` but never used the value. It has been removed from the component below.

### 4. Reduced-motion CSS — scoped to marker class

The original rule `svg animate { animation-play-state: paused }` was too broad — it would freeze every `<animate>` in the app. The rule is now scoped to `.marker-live-position animate`. Note also that `animation-play-state` does not reliably pause SMIL `<animate>` elements in all browsers; the implementation uses `window.matchMedia` to conditionally skip rendering the `<animate>` nodes entirely.

### 5. Destination arrived state — yes, one-way latch

When the user is within ~50 m of the destination, the destination ring fills solid ink and a small italic "arrived" caption appears below. **Once triggered, it stays for the duration of the active trip** — no hysteresis, no revert. The `arrived` boolean prop is computed in `MapView.jsx` (haversine distance, 50 m threshold) and held in a `useRef` so it never reverts during the trip, even if GPS briefly drifts past 50 m. The prop is never lifted to `App.jsx`.

### 6. Intermediate transfer station marks — deferred, optional

Explicitly ruled out for this implementation. The polyline shape communicates the route; the existing board/exit circle rendering provides sufficient transfer context. Logged in `FEATURE_IMPLEMENTATION_PLANS.md` as an optional future consideration.

### 7. Heading smoothing — EMA included

Raw `position.coords.heading` jitters at low speeds. A **circular exponential moving average** (alpha = 0.3) is applied in `MapView.jsx` before the heading value reaches the marker. The helper is heading-wrap-aware (handles the 0°/360° boundary). See [Heading smoothing](#heading-smoothing) below.

---

## Drop-in SVG sources

Three self-contained SVG components. They're already correct on cream paper; they include a paper backing rect/circle so the strokes also read on lake blue, river green, or any MapLibre tile fill. Copy these as `.jsx` files into `frontend/src/components/markers/`.

### `OriginMarker.jsx`

Italic silcrow inside a double-ruled square. Renders at 22 × 22 px logical size; the SVG viewBox is centered at (0, 0) so MapLibre's `Marker` anchors it correctly.

```jsx
// frontend/src/components/markers/OriginMarker.jsx
import React from "react";

/**
 * Origin / "FROM" marker.
 * Italic silcrow (§) inside a double-ruled ink square on a paper-coloured pad.
 * @param {Object} props
 * @param {string} [props.label] - Optional place name, set as italic Fraunces flag.
 * @param {"left"|"right"} [props.flagSide="right"] - Which side of the mark the label sits.
 * @param {string} [props.paperColor="#f4ead5"] - Paper backing colour (defaults to D2.bg).
 * @param {string} [props.inkColor="#1a1510"] - Ink colour (defaults to D2.ink).
 * @param {string} [props.muteColor="#8a7a60"] - Mute colour for the FROM kicker.
 */
export default function OriginMarker({
  label,
  flagSide = "right",
  paperColor = "#f4ead5",
  inkColor = "#1a1510",
  muteColor = "#8a7a60",
}) {
  const W = label ? 140 : 28;
  const H = label ? 40 : 28;
  const cx = flagSide === "right" ? 14 : W - 14;

  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      style={{ overflow: "visible", display: "block" }}
      aria-label={label ? `Origin: ${label}` : "Origin"}
      role="img"
    >
      {/* Paper backing — strokes must read on any tile fill */}
      <rect x={cx - 11} y={H / 2 - 11} width="22" height="22" fill={paperColor} />
      {/* Outer ink frame */}
      <rect x={cx - 11} y={H / 2 - 11} width="22" height="22"
        fill="none" stroke={inkColor} strokeWidth="2" />
      {/* Inset hairline (the editorial double-rule) */}
      <rect x={cx - 8} y={H / 2 - 8} width="16" height="16"
        fill="none" stroke={inkColor} strokeWidth="0.75" />
      {/* Italic silcrow */}
      <text x={cx} y={H / 2 + 5.5} fontSize="16" fontWeight="700" fill={inkColor}
        fontFamily='"Fraunces", Georgia, serif' fontStyle="italic" textAnchor="middle">
        §
      </text>

      {label && (
        <g>
          {/* Caps kicker */}
          <text
            x={flagSide === "right" ? cx + 16 : cx - 16}
            y={H / 2 - 3}
            fill={muteColor}
            fontSize="8"
            fontWeight="800"
            fontFamily='"Inter", system-ui, sans-serif'
            letterSpacing="1.5"
            textAnchor={flagSide === "right" ? "start" : "end"}
          >
            FROM
          </text>
          {/* Place name */}
          <text
            x={flagSide === "right" ? cx + 16 : cx - 16}
            y={H / 2 + 9}
            fill={inkColor}
            fontSize="12"
            fontWeight="500"
            fontFamily='"Fraunces", Georgia, serif'
            fontStyle="italic"
            textAnchor={flagSide === "right" ? "start" : "end"}
          >
            {label}
          </text>
        </g>
      )}
    </svg>
  );
}
```

### `DestinationMarker.jsx`

Surveyor's target — concentric ring with crosshair and bullseye. Supports an `arrived` boolean: when true, the ring fills solid ink and an italic "arrived" caption appears below. The `arrived` state is a one-way latch managed by the parent — this component is purely presentational.

```jsx
// frontend/src/components/markers/DestinationMarker.jsx
import React from "react";

/**
 * Destination / "TO" marker.
 * Surveyor's crosshair target on a paper-coloured pad.
 * Label weight matches OriginMarker (500) — both are coordinates, neither is primary.
 *
 * @param {Object} props
 * @param {string} [props.label]
 * @param {"left"|"right"} [props.flagSide="right"]
 * @param {boolean} [props.arrived=false] - When true, fills the ring solid ink
 *                                          and shows an italic "arrived" caption.
 *                                          One-way latch — managed by the parent.
 * @param {string} [props.paperColor="#f4ead5"]
 * @param {string} [props.inkColor="#1a1510"]
 * @param {string} [props.muteColor="#8a7a60"]
 */
export default function DestinationMarker({
  label,
  flagSide = "right",
  paperColor = "#f4ead5",
  inkColor = "#1a1510",
  muteColor = "#8a7a60",
  arrived = false,
}) {
  const W = label ? 160 : 28;
  const H = label ? 40 : 28;
  const cx = flagSide === "right" ? 14 : W - 14;
  const cy = H / 2;

  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      style={{ overflow: "visible", display: "block" }}
      aria-label={
        arrived
          ? label ? `Arrived: ${label}` : "Arrived at destination"
          : label ? `Destination: ${label}` : "Destination"
      }
      role="img"
    >
      {/* Paper backing disc */}
      <circle cx={cx} cy={cy} r="13" fill={paperColor} />
      {/* Outer ink ring — fills solid on arrival */}
      <circle cx={cx} cy={cy} r="12" fill={arrived ? inkColor : "none"} stroke={inkColor} strokeWidth="2" />
      {/* Inset hairline — hidden on arrival (solid fill covers it) */}
      {!arrived && (
        <circle cx={cx} cy={cy} r="9" fill="none" stroke={inkColor} strokeWidth="0.75" />
      )}
      {/* Crosshair — four ticks, hidden on arrival */}
      {!arrived && (
        <>
          <line x1={cx - 12} y1={cy} x2={cx - 5.5} y2={cy} stroke={inkColor} strokeWidth="1.25" />
          <line x1={cx + 5.5} y1={cy} x2={cx + 12} y2={cy} stroke={inkColor} strokeWidth="1.25" />
          <line x1={cx} y1={cy - 12} x2={cx} y2={cy - 5.5} stroke={inkColor} strokeWidth="1.25" />
          <line x1={cx} y1={cy + 5.5} x2={cx} y2={cy + 12} stroke={inkColor} strokeWidth="1.25" />
        </>
      )}
      {/* Bullseye — paper-coloured on arrival so it reads against the filled ring */}
      <circle cx={cx} cy={cy} r="3" fill={arrived ? paperColor : inkColor} />

      {/* Arrived caption */}
      {arrived && (
        <text
          x={cx}
          y={cy + 22}
          fill={inkColor}
          fontSize="10"
          fontWeight="500"
          fontFamily='"Fraunces", Georgia, serif'
          fontStyle="italic"
          textAnchor="middle"
        >
          arrived
        </text>
      )}

      {label && !arrived && (
        <g>
          <text
            x={flagSide === "right" ? cx + 18 : cx - 18}
            y={cy - 3}
            fill={muteColor}
            fontSize="8"
            fontWeight="800"
            fontFamily='"Inter", system-ui, sans-serif'
            letterSpacing="1.5"
            textAnchor={flagSide === "right" ? "start" : "end"}
          >
            TO
          </text>
          <text
            x={flagSide === "right" ? cx + 18 : cx - 18}
            y={cy + 10}
            fill={inkColor}
            fontSize="12"
            fontWeight="500"
            fontFamily='"Fraunces", Georgia, serif'
            textAnchor={flagSide === "right" ? "start" : "end"}
          >
            {label}
          </text>
        </g>
      )}
    </svg>
  );
}
```

### `LivePositionMarker.jsx`

Compass needle inside a flickering rust ring. **Heading-aware** — pass the device bearing in degrees and the needle rotates. The pulse animation is suppressed under `prefers-reduced-motion` by not rendering the `<animate>` nodes at all (more reliable than `animation-play-state` for SMIL).

Note: heading should be **pre-smoothed by the parent** using the circular EMA helper before being passed here. This component is purely presentational.

```jsx
// frontend/src/components/markers/LivePositionMarker.jsx
import React from "react";

/**
 * Live user position / "YOU" marker.
 * Compass needle pointing along the device bearing, inside a pulsing rust ring.
 * Note: no flagSide prop — the label always extends to the right. The live marker
 * is a moving element and is always placed away from the route polyline, so a fixed
 * right-side label is acceptable. Add flagSide if that assumption ever changes.
 *
 * @param {Object} props
 * @param {number} [props.heading=0] - Device bearing in degrees (0=N, 90=E).
 *                                     Should be pre-smoothed by the parent via smoothHeading().
 * @param {boolean} [props.hasHeading=true] - When false, the needle is hidden
 *                                            and only the ring + dot show.
 * @param {boolean} [props.reducedMotion=false] - When true, suppresses <animate> nodes entirely.
 *                                                Parent should derive from window.matchMedia.
 * @param {string} [props.label]
 * @param {string} [props.paperColor="#f4ead5"]
 * @param {string} [props.inkColor="#1a1510"]
 * @param {string} [props.accentColor="#a8482a"] - Rust (D2.accent).
 * @param {string} [props.muteColor="#8a7a60"]
 */
export default function LivePositionMarker({
  heading = 0,
  hasHeading = true,
  reducedMotion = false,
  label,
  paperColor = "#f4ead5",
  inkColor = "#1a1510",
  accentColor = "#a8482a",
  muteColor = "#8a7a60",
}) {
  const W = label ? 140 : 36;
  const H = label ? 44 : 36;
  const cx = label ? 18 : W / 2;
  const cy = H / 2;

  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      className="marker-live-position"
      style={{ overflow: "visible", display: "block" }}
      aria-label={label ? `You: ${label}` : "Your position"}
      role="img"
    >
      {/* Pulse ring */}
      <circle
        cx={cx}
        cy={cy}
        r="14"
        fill="none"
        stroke={accentColor}
        strokeWidth="1"
        opacity="0.45"
      >
        {!reducedMotion && (
          <>
            <animate
              attributeName="r"
              values="14;18;14"
              dur="2.4s"
              repeatCount="indefinite"
            />
            <animate
              attributeName="opacity"
              values="0.45;0;0.45"
              dur="2.4s"
              repeatCount="indefinite"
            />
          </>
        )}
      </circle>

      {/* Paper backing for the compass card */}
      <circle cx={cx} cy={cy} r="11" fill={paperColor} stroke={accentColor} strokeWidth="1.5" />

      {/* Cardinal ticks (always-on orientation hint) */}
      <line x1={cx} y1={cy - 11} x2={cx} y2={cy - 8} stroke={accentColor} strokeWidth="1" />
      <line x1={cx} y1={cy + 11} x2={cx} y2={cy + 8} stroke={accentColor} strokeWidth="1" />
      <line x1={cx - 11} y1={cy} x2={cx - 8} y2={cy} stroke={accentColor} strokeWidth="1" />
      <line x1={cx + 11} y1={cy} x2={cx + 8} y2={cy} stroke={accentColor} strokeWidth="1" />

      {/* Compass needle — CSS transform so the transition actually works */}
      {hasHeading && (
        <g style={{
          transform: `rotate(${heading}deg)`,
          transformOrigin: `${cx}px ${cy}px`,
          transition: "transform 200ms linear",
        }}>
          {/* Forward (rust) blade */}
          <path d={`M ${cx},${cy - 8} L ${cx + 3},${cy + 2} L ${cx},${cy} L ${cx - 3},${cy + 2} Z`} fill={accentColor} />
          {/* Reverse (ink, soft) blade */}
          <path d={`M ${cx},${cy + 8} L ${cx + 2},${cy + 2} L ${cx},${cy} L ${cx - 2},${cy + 2} Z`} fill={inkColor} opacity="0.4" />
        </g>
      )}

      {/* Center pin */}
      <circle cx={cx} cy={cy} r="1.4" fill={inkColor} />

      {label && (
        <g>
          <text
            x={cx + 22}
            y={cy - 3}
            fill={muteColor}
            fontSize="8"
            fontWeight="800"
            fontFamily='"Inter", system-ui, sans-serif'
            letterSpacing="1.5"
            textAnchor="start"
          >
            YOU
          </text>
          <text
            x={cx + 22}
            y={cy + 10}
            fill={inkColor}
            fontSize="12"
            fontWeight="500"
            fontFamily='"Fraunces", Georgia, serif'
            fontStyle="italic"
            textAnchor="start"
          >
            {label}
          </text>
        </g>
      )}
    </svg>
  );
}
```

#### Reduced-motion CSS

Scoped to `.marker-live-position` so it cannot accidentally freeze other animated SVGs in the app. However, the preferred approach (already implemented in the component above) is to not render the `<animate>` nodes at all when `reducedMotion={true}` — `animation-play-state` does not reliably pause SMIL in all browsers. Keep this CSS as a belt-and-suspenders fallback only.

```css
@media (prefers-reduced-motion: reduce) {
  .marker-live-position animate {
    animation-play-state: paused !important;
  }
}
```

---

## Heading smoothing

Raw `position.coords.heading` jitters at low speeds. Apply a **circular exponential moving average** (alpha = 0.3) before passing the heading to `LivePositionMarker`. The helper handles the 0°/360° wrap-around correctly — a naive average of 350° and 10° would yield 180° without this.

```js
// Module-level utility in MapView.jsx
// alpha=0.3 means each new reading contributes 30%, history 70% — ~2–3 reading lag at 1 Hz GPS.
function smoothHeading(prev, next, alpha = 0.3) {
  const delta = ((next - prev + 540) % 360) - 180; // shortest angular path
  return (prev + alpha * delta + 360) % 360;
}
```

Usage in `MapView.jsx`:

```js
const smoothedHeadingRef = useRef(0);

// Inside the userPosition effect, before updating the marker:
if (Number.isFinite(userPosition.heading)) {
  smoothedHeadingRef.current = smoothHeading(
    smoothedHeadingRef.current,
    userPosition.heading,
  );
}
```

---

## MapLibre integration

`MapView.jsx` uses raw `maplibre-gl` imperatively — **do not introduce `react-map-gl` as a dependency**. Mount the marker components using `maplibregl.Marker` with a DOM element rendered by `ReactDOM.createRoot`.

```jsx
// frontend/src/MapView.jsx (additions)
import ReactDOM from "react-dom/client";
import OriginMarker from "./components/markers/OriginMarker";
import DestinationMarker from "./components/markers/DestinationMarker";
import LivePositionMarker from "./components/markers/LivePositionMarker";

// Detect reduced-motion preference once at module level.
// Intentional snapshot: the preference is evaluated at page load and not updated
// if the user toggles it mid-session. Acceptable for a transit app — a full reload
// picks up the change.
const prefersReducedMotion =
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Module-level utility — circular EMA for heading smoothing.
function smoothHeading(prev, next, alpha = 0.3) {
  const delta = ((next - prev + 540) % 360) - 180;
  return (prev + alpha * delta + 360) % 360;
}

// Haversine distance in metres between two {lat, lng} points.
function haversineMetres(a, b) {
  const R = 6_371_000;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) *
      Math.cos((b.lat * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
}

// Inside the MapView component, add these refs alongside the existing ones:
const originMarkerRef  = useRef(null); // { marker, root }
const destMarkerRef    = useRef(null);
const liveMarkerRef    = useRef(null);
const smoothedHeadingRef = useRef(0);
const arrivedRef       = useRef(false); // one-way latch

// Helper: create a maplibregl.Marker backed by a React root.
function mountMarker(map, Component, props, lngLat) {
  const el = document.createElement("div");
  const root = ReactDOM.createRoot(el);
  root.render(<Component {...props} />);
  const marker = new maplibregl.Marker({ element: el, anchor: "center" })
    .setLngLat(lngLat)
    .addTo(map);
  return { marker, root };
}

function removeMarker(ref) {
  ref.current?.marker.remove();
  ref.current?.root.unmount();
  ref.current = null;
}
```

### Rendering the markers

The code below belongs inside the existing `useEffect` in `MapView.jsx` that already watches `[origin, destination, userPosition, tripActive]` (or equivalent). Do not create a new effect — it would race with the map initialization effect.

Render in this order — origin → destination → user — so the user dot is always on top in MapLibre's DOM paint order.

```jsx
// Origin
if (origin) {
  removeMarker(originMarkerRef);
  originMarkerRef.current = mountMarker(
    map,
    OriginMarker,
    {},
    [origin.lng, origin.lat],
  );
}

// Destination
if (destination) {
  removeMarker(destMarkerRef);
  destMarkerRef.current = mountMarker(
    map,
    DestinationMarker,
    { arrived: arrivedRef.current },
    [destination.lng, destination.lat],
  );
}

// Live position (only during an active trip)
if (tripActive && userPosition) {
  // Smooth heading
  if (Number.isFinite(userPosition.heading)) {
    smoothedHeadingRef.current = smoothHeading(
      smoothedHeadingRef.current,
      userPosition.heading,
    );
  }

  // Arrived latch — 50 m threshold, never resets during trip
  if (!arrivedRef.current && destination) {
    const dist = haversineMetres(
      { lat: userPosition.lat, lng: userPosition.lng },
      { lat: destination.lat, lng: destination.lng },
    );
    if (dist <= 50) {
      arrivedRef.current = true;
      // Re-render destination marker in arrived state, preserving any props
      // that were passed at mount time (e.g. label). If label is omitted on-map
      // (the recommended path) this reduces to <DestinationMarker arrived={true} />.
      destMarkerRef.current?.root.render(
        <DestinationMarker arrived={true} label={destination?.name} />,
      );
    }
  }

  if (!liveMarkerRef.current) {
    liveMarkerRef.current = mountMarker(
      map,
      LivePositionMarker,
      {
        heading: smoothedHeadingRef.current,
        hasHeading: Number.isFinite(userPosition.heading),
        reducedMotion: prefersReducedMotion,
      },
      [userPosition.lng, userPosition.lat],
    );
  } else {
    // Update position and re-render props
    liveMarkerRef.current.marker.setLngLat([userPosition.lng, userPosition.lat]);
    liveMarkerRef.current.root.render(
      <LivePositionMarker
        heading={smoothedHeadingRef.current}
        hasHeading={Number.isFinite(userPosition.heading)}
        reducedMotion={prefersReducedMotion}
      />,
    );
  }
}
```

### Cleanup

When the trip ends or the component unmounts, remove all three markers and reset the latch:

```js
removeMarker(originMarkerRef);
removeMarker(destMarkerRef);
removeMarker(liveMarkerRef);
arrivedRef.current = false;
smoothedHeadingRef.current = 0;
```

### Anchoring notes

- **`anchor="center"`** for all three. The SVGs are designed with the geographic point at their centroid, not at a "pin tip" — these aren't drop pins.
- The optional flag label extends the SVG horizontally. **Omit `label` on the map** and surface the place name in the bottom-sheet route summary instead — this is the recommended path.
- **Z-order:** in MapLibre, marker DOM order = paint order. Render in this order: origin → destination → user position (so the user is always on top, even when standing on origin/destination).
- **Disable MapLibre's built-in `GeolocateControl` dot** if it is in use: `showUserLocation: false`. Render `<LivePositionMarker>` from your own state instead.

### Heading source

If you're using the browser Geolocation API, `position.coords.heading` is `null` when the device is stationary or doesn't have a compass. Pass `hasHeading={false}` when null — the needle hides and you get the static ring + center dot, still distinct from origin/destination.

---

## Tokens

These markers consume four tokens from the design system. If you've already wired the D2 tokens (see parent README), pass them through; otherwise the component defaults match D2:

| Token | Hex | Usage |
|-------|-----|-------|
| `paper` (`D2.bg`) | `#f4ead5` | Marker backing — must be the map's paper colour, not white |
| `ink` (`D2.ink`) | `#1a1510` | All non-live strokes + glyphs |
| `accent` (`D2.accent`) | `#a8482a` | **Live position only** — never on origin/destination |
| `mute` (`D2.mute`) | `#8a7a60` | Caps kicker on flag labels |

---

## Accessibility

- Each marker has `role="img"` and an `aria-label` derived from its kind + label. Screen readers announce e.g. "Origin: Logan Square."
- When arrived, `DestinationMarker` updates its `aria-label` to "Arrived: {label}" or "Arrived at destination."
- The compass needle's heading direction is **decorative for the visual user**; the screen reader doesn't announce it.
- Hit area: SVGs are visually 22–36 px. For tap targets (e.g. tap-to-recentre on user position), wrap in a transparent 44 × 44 button — don't enlarge the visible mark.

---

## Acceptance checklist

**Implemented 2026-04-30.**

- [x] `OriginMarker`, `DestinationMarker`, `LivePositionMarker` exist in `frontend/src/components/markers/`
- [x] Old circle/star/dot marker code is removed from `MapView.jsx` (`renderOriginDestMarkers`, the `user-position-layer` circle)
- [x] All three marks render with paper backings that read on lake blue and river green tiles
- [x] Live-position needle rotates with `position.coords.heading` updates, with 200 ms CSS transition
- [x] When heading is `null`, the needle is hidden but the ring + dot remain
- [x] Heading is pre-smoothed via the circular EMA helper before reaching `LivePositionMarker`
- [x] Pulse animation is not rendered (no `<animate>` nodes) when `reducedMotion={true}`
- [x] `label` prop is **omitted** on all three markers when mounted on the map; place names appear only in the bottom-sheet route summary (long labels overflow the fixed-width SVG viewBox)
- [x] Render order in DOM is origin → destination → user so that user is painted last (on top); verify by inspecting the MapLibre marker container
- [ ] If MapLibre `GeolocateControl` is in use, its built-in dot is disabled (`showUserLocation: false`) — `GeolocateControl` is not used in `MapView.jsx`; N/A
- [x] Each marker has a meaningful `aria-label` matching screen-reader expectations
- [x] Arrived state triggers at ≤ 50 m from destination and does not revert for the duration of the trip
- [x] `arrivedRef` and `smoothedHeadingRef` are reset when the trip ends
- [x] All marker React roots are unmounted (`root.unmount()`) on cleanup — no memory leaks
- [ ] Tap targets on interactive markers are at least 44 × 44 px — markers are currently presentational only (no tap handlers); add 44×44 wrapper if tap-to-recentre is added

---

## Test cases

1. **Stationary user, GPS just acquired** — origin §, destination ✦, and user ➤ all visible. User has `hasHeading={false}` (no needle), still distinguishable from origin/destination.
2. **User walking north** — needle points up, rotates smoothly to bearing changes via 200 ms CSS transition; EMA prevents needle jitter at slow walking pace.
3. **User standing at origin** — both marks render at the same coordinate; user is on top.
4. **Reduced motion** — pulse ring `<animate>` nodes are not rendered; needle and ring are static; everything else identical.
5. **Tile colour edge cases** — drag the map so the markers sit on the lake fill, then on the river. Strokes must remain legible because of the paper backing.
6. **No origin set** (just destination + user) — only two marks visible, no layout shift.
7. **Arrival** — simulate user within 50 m of destination: destination ring fills solid ink, "arrived" caption appears, `aria-label` updates. Walk away past 50 m: mark stays filled (latch held).
8. **Trip end** — markers removed, `arrivedRef` reset to false, `smoothedHeadingRef` reset to 0.
