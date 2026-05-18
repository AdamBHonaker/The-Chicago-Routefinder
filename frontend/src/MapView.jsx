import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import maplibregl from "maplibre-gl";
import { useMapMarker, mountMarker, removeMarker } from "./hooks/useMapMarker.jsx";
import { useRouteLayers } from "./hooks/useRouteLayers.js";
import { useTransferConnectors } from "./hooks/useTransferConnectors.js";
import { BUS_DIRECTION_COLORS, PANEL_MAP_RESIZE_DELAY_MS } from "./constants.js";
import { stripLineSuffix } from "./lineColors.js";
import { haversineMeters } from "./utils/tripGeometry.js";
import LinePill from "./components/LinePill.jsx";
import OriginMarker from "./components/markers/OriginMarker.jsx";
import DestinationMarker from "./components/markers/DestinationMarker.jsx";
import LivePositionMarker from "./components/markers/LivePositionMarker.jsx";
import TransferMarker from "./components/markers/TransferMarker.jsx";
import FootprintMarker from "./components/markers/FootprintMarker.jsx";

// ---------------------------------------------------------------------------
// Map defaults — overridable via props for future view modes
// ---------------------------------------------------------------------------

const DEFAULT_STYLE  = import.meta.env.VITE_MAP_STYLE_URL || "https://tiles.openfreemap.org/styles/liberty";
const DEFAULT_CENTER = [-87.654, 41.966]; // Uptown, Chicago
const DEFAULT_ZOOM   = 13;

// Distance from destCoords (in metres) at which we latch the "arrived" state.
const ARRIVED_THRESHOLD_M = 50;

// All MapLibre interaction handlers we toggle as a group when locking/unlocking
// the map (TD-FE-009). Source of truth — adding a new handler means adding it
// here, not editing three call-sites.
const INTERACTION_HANDLERS = [
  "scrollZoom",
  "dragPan",
  "dragRotate",
  "doubleClickZoom",
  "touchZoomRotate",
  "keyboard",
];

function setMapInteractive(map, enabled) {
  for (const name of INTERACTION_HANDLERS) {
    map[name][enabled ? "enable" : "disable"]();
  }
}

// Backend returns [lat, lon]; GeoJSON / MapLibre expects [lon, lat].
const swapLngLat = ([lat, lon]) => [lon, lat];

// Intentional snapshot: evaluated at page load, not updated mid-session.
// A full reload picks up any change to the OS reduced-motion preference.
const prefersReducedMotion =
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Resolved once at module load — the design system token does not change at
// runtime, so the per-effect getComputedStyle call (a forced style flush) was
// wasted work on every leg advance.
const MUTE_COLOR =
  (typeof window !== "undefined"
    ? getComputedStyle(document.documentElement).getPropertyValue("--mute").trim()
    : "") || "#8a7a60";

// Returns "NW 315°" style string using locale-aware cardinal abbreviations.
function getBearingLabel(heading, t) {
  const dirs = ["n", "ne", "e", "se", "s", "sw", "w", "nw"];
  const idx = Math.round(((heading % 360) + 360) % 360 / 45) % 8;
  const deg = Math.round(((heading % 360) + 360) % 360);
  return `${t(`compass_${dirs[idx]}`)} ${deg}°`;
}

// Circular exponential moving average for heading smoothing.
// alpha=0.3 → each new reading contributes 30%, history 70% (~2–3 reading lag at 1 Hz GPS).
// Handles the 0°/360° wrap-around correctly — a naive average of 350° and 10° yields 180°.
function smoothHeading(prev, next, alpha = 0.3) {
  const delta = ((next - prev + 540) % 360) - 180;
  return (prev + alpha * delta + 360) % 360;
}

// Runs the body once the map's style is loaded, and returns a cleanup that
// detaches the deferred listener if the effect tears down before "load" fires.
function whenStyleReady(map, body) {
  if (map.isStyleLoaded()) {
    body();
    return () => {};
  }
  map.once("load", body);
  return () => map.off("load", body);
}

// ---------------------------------------------------------------------------
// Transfer marker helpers
// ---------------------------------------------------------------------------

const FOOTPRINT_TYPES = new Set(["walk-transit", "transit-walk"]);

// Stable empty array used when no transferPoints prop is supplied. A fresh `[]`
// per render would re-fire useTransferConnectors' clear/render cycle on every
// MapView re-render, even when no trip is active.
const EMPTY_TRANSFER_POINTS = Object.freeze([]);

function transferPointKey(d) {
  return `${d.alightingLegIndex ?? "s"}-${d.boardingLegIndex ?? "e"}`;
}

// A transfer is "passed" when activeLegIndex has advanced past the alighting leg
// (or past the boarding leg for walk-transit, which has no alighting leg).
function isPassedDescriptor(activeLegIndex, descriptor) {
  if (activeLegIndex == null) return false;
  const ref = descriptor.alightingLegIndex ?? descriptor.boardingLegIndex;
  if (ref == null) return false;
  return activeLegIndex > ref;
}

// Wrapper that calls useMapMarker once per descriptor. Returns null — the hook
// handles the imperative MapLibre marker; this component only manages lifecycle.
function TransferPointMount({ map, descriptor, activeLegIndex, selectedTransferId, onSelectTransfer }) {
  const id         = transferPointKey(descriptor);
  const isSelected = selectedTransferId === id;
  const isPassed   = isPassedDescriptor(activeLegIndex, descriptor);
  const state      = isSelected && isPassed ? "passed-selected"
                   : isSelected             ? "selected"
                   : isPassed               ? "passed"
                   : "default";
  const label     = isSelected ? descriptor.stationName : undefined;
  const isFootprint = FOOTPRINT_TYPES.has(descriptor.type);
  const direction = descriptor.type === "walk-transit" ? "walk-to-transit"
                  : descriptor.type === "transit-walk" ? "transit-to-walk"
                  : undefined;
  const props = isFootprint ? { state, direction, label } : { state, label };

  // Stable refs so the onMount click handler always sees the latest values
  // without needing to close over them at mount time.
  const onSelectRef = useRef(onSelectTransfer);
  const isSelectedRef = useRef(isSelected);
  onSelectRef.current    = onSelectTransfer;
  isSelectedRef.current  = isSelected;

  const onMount = useMemo(() => (marker) => {
    marker.getElement().addEventListener("click", (e) => {
      e.stopPropagation();
      onSelectRef.current(isSelectedRef.current ? null : id);
    });
  }, [id]); // id is stable for the lifetime of this component instance

  useMapMarker(
    map,
    isFootprint ? FootprintMarker : TransferMarker,
    props,
    descriptor.coords,
    { className: "marker-transfer-wrapper", onMount },
  );
  return null;
}

// CompassRose — the heading-up toggle button + rotating-rose SVG.
// Lives in its own component so the bearing state's "rotate" listener only
// re-renders this small subtree, not the entire MapView (OPT-FE-202). The
// label reads `smoothedHeadingRef.current` directly; the rotate event fires
// frequently enough during heading-up mode that the label stays in sync.
function CompassRose({ map, headingUp, onToggle, smoothedHeadingRef, t }) {
  const [bearing, setBearing] = useState(() => map?.getBearing() ?? 0);
  useEffect(() => {
    if (!map) return;
    const handler = () => setBearing(map.getBearing());
    map.on("rotate", handler);
    return () => map.off("rotate", handler);
  }, [map]);
  return (
    <button
      className={`map-heading-btn${headingUp ? " map-heading-btn--active" : ""}`}
      onClick={onToggle}
      aria-pressed={headingUp}
      aria-label={headingUp ? t("map_heading_north_btn") : t("map_heading_up_btn")}
    >
      <svg
        className="map-heading-btn__rose"
        width="16" height="16" viewBox="-8 -8 16 16"
        aria-hidden="true"
        style={{ transform: `rotate(${bearing}deg)` }}
      >
        <polygon points="0,-7 -2.5,-2 2.5,-2" fill={headingUp ? "var(--rust)" : "var(--ink)"} />
        <polygon points="0,7 -2.5,2 2.5,2" fill="var(--mute-fog)" />
        <line x1="0" y1="-7" x2="0" y2="7" stroke={headingUp ? "var(--rust)" : "var(--ink)"} strokeWidth="1" />
      </svg>
      <span className="map-heading-btn__label">
        {headingUp
          ? getBearingLabel(smoothedHeadingRef.current, t)
          : t("map_heading_up_btn")}
      </span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function MapView({
  route                = null,
  originCoords         = null,
  destCoords           = null,
  userPosition         = null,
  tripActive           = false,
  activeLegIndex       = null,
  activeTab            = "home",
  cardsColumnWidth     = null,
  mapPadding           = null,
  sheetSnap            = null,
  onArrived            = null,
  selectedTransferId   = null,
  onSelectTransfer     = null,
  transferPoints       = null,
  style          = DEFAULT_STYLE,
  center         = DEFAULT_CENTER,
  zoom           = DEFAULT_ZOOM,
}) {
  const { t } = useTranslation();
  const containerRef = useRef(null);
  const [map, setMap] = useState(null);
  const liveMarkerRef      = useRef(null); // imperative — see useMapMarker.js
  const smoothedHeadingRef = useRef(0);    // circular EMA state for heading
  const firstFixDoneRef    = useRef(false); // gate for one-time flyTo on first GPS fix
  const [unlocked, setUnlocked] = useState(false);
  const [styleError, setStyleError] = useState(false);
  // Bearing is consumed only by <CompassRose>, which subscribes to the map's
  // "rotate" event itself. Keeping it out of MapView state stops every
  // rotateTo / drag-rotate frame from re-rendering the entire MapView tree
  // (OPT-FE-202).
  // headingUp is a transient in-trip preference: the trip-end teardown effect
  // below resets it to false on every trip-end, so persisting across sessions
  // would be silently clobbered on the next page load. Plain useState matches
  // the teardown semantics — heading-up always starts off when a trip begins.
  const [headingUp, setHeadingUp] = useState(false);
  const [arrived, setArrived] = useState(false);

  // Stable ref to the latest handleRelock — read at click time by the
  // live-position marker's listener, which is attached once at marker mount and
  // would otherwise close over a stale `userPosition` from the first render.
  const handleRelockRef = useRef(null);

  // Initialize map once after the container div mounts.
  //
  // In development, React 18 StrictMode double-invokes every effect:
  //   mount → (cleanup) → mount
  // This is intentional to surface side-effect bugs, but it breaks MapLibre:
  // WebGL2 context teardown is deferred to the browser's GPU process and is
  // NOT complete by the time map.remove() returns synchronously. The immediate
  // second init therefore tries to create a new WebGL2 context while the old
  // one still occupies the canvas, producing a silent blank (black) map.
  //
  // Fix: defer init with setTimeout(0).
  // StrictMode's cleanup fires synchronously and calls clearTimeout() on the
  // first timer before it fires. Only the second effect's timer survives to
  // the next task queue slot, by which point the GPU process has finished
  // tearing down the previous WebGL2 context.
  //
  // In production, StrictMode is not active and effects run exactly once, so
  // this setTimeout adds no observable latency — it merely defers init past
  // any synchronous DOM measurements that share the same task.
  useEffect(() => {
    let mapInstance = null;
    let canvas = null;
    let onContextLost = null;
    let onContextRestored = null;

    const timerId = setTimeout(() => {
      const container = containerRef.current;
      if (!container) return;

      mapInstance = new maplibregl.Map({
        container,
        style,
        center,
        zoom,
        // Don't bail on software-rendered WebGL2 contexts (some Windows GPU drivers)
        failIfMajorPerformanceCaveat: false,
      });

      // Lock all interactions by default
      setMapInteractive(mapInstance, false);

      // After style loads: resize + repaint so the WebGL framebuffer is presented
      // correctly when the container starts at opacity:0.
      mapInstance.once("load", () => {
        mapInstance.resize();
        mapInstance.triggerRepaint();
      });

      mapInstance.on("error", (e) => {
        console.error("[MapView] map error:", e?.error ?? e);
        // Only latch the error banner for style *document* failures — not
        // transient per-tile 404s or network blips, which self-recover.
        const status = e?.error?.status;
        const isStyleSource = e?.sourceId === "openmaptiles" ||
                              e?.error?.message?.toLowerCase().includes("style");
        if (isStyleSource && (status === 0 || (status >= 400 && status < 600))) {
          setStyleError(true);
          mapInstance.once("styledata", () => setStyleError(false));
        }
      });

      // FEAT-012 (decision #8): defensive WebGL context-loss recovery. With the
      // unified panel-swap pattern the canvas stays mounted on Home/Saved/Alerts
      // tabs, slightly increasing context-loss exposure on low-memory devices.
      // preventDefault() on `webglcontextlost` is required for the browser to
      // fire the matching `webglcontextrestored` event; on restoration we call
      // resize() so MapLibre rebuilds its framebuffer for the current container.
      canvas = mapInstance.getCanvas();
      onContextLost = (e) => {
        e.preventDefault();
        console.warn("[MapView] webgl context lost — pausing render");
      };
      onContextRestored = () => {
        console.warn("[MapView] webgl context restored — resizing");
        mapInstance.resize();
        mapInstance.triggerRepaint();
      };
      canvas.addEventListener("webglcontextlost", onContextLost, false);
      canvas.addEventListener("webglcontextrestored", onContextRestored, false);

      setMap(mapInstance);
    }, 0);

    return () => {
      clearTimeout(timerId);
      if (canvas && onContextLost) {
        canvas.removeEventListener("webglcontextlost", onContextLost);
        canvas.removeEventListener("webglcontextrestored", onContextRestored);
      }
      mapInstance?.remove();
      setMap(null);
    };
  // Intentionally empty deps: props (style, center, zoom) are construction-time
  // values; re-running this effect would destroy and recreate the WebGL context.
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Render route polylines + stop circles via the layer-management hook.
  useRouteLayers(map, route, mapPadding);

  // Reset arrived latch when the route or destination changes.
  useEffect(() => {
    setArrived(false);
  }, [route, destCoords]);

  // Resolve origin/destination lngLats. Explicit prop first, then fall back to
  // the first/last path point of the route.
  const originLngLat = originCoords
    ? [originCoords[1], originCoords[0]]
    : (() => { const p = route?.legs?.[0]?.path?.[0]; return p ? swapLngLat(p) : null; })();
  const lastLeg = route?.legs?.[route.legs.length - 1];
  const destLngLat = destCoords
    ? [destCoords[1], destCoords[0]]
    : (lastLeg?.path?.length ? swapLngLat(lastLeg.path[lastLeg.path.length - 1]) : null);

  // Origin / destination markers — declarative; the hook owns createRoot/unmount.
  useMapMarker(map, OriginMarker, { fromLabel: t("marker_from") }, originLngLat,
    { className: "marker-origin-wrapper" });
  useMapMarker(
    map,
    DestinationMarker,
    { arrived, toLabel: t("marker_to"), arrivedLabel: t("marker_arrived") },
    destLngLat,
    { className: "marker-destination-wrapper" },
  );

  // Transfer points are derived once in App.jsx (OPT-FE-201) and passed in as a
  // prop. Defensive fallback to an empty array means MapView can still render
  // when mounted without the prop (e.g. unit tests, future view modes).
  const tp = transferPoints ?? EMPTY_TRANSFER_POINTS;

  // Dashed connector lines for split-stop transfers (managed canvas layers).
  useTransferConnectors(map, tp);

  // flyTo the selected transfer marker when selection changes, unless it's already
  // visible. Using selectedTransferId as the sole trigger: when the marker itself
  // was tapped, its coords are on-screen, so the inset check suppresses the pan.
  useEffect(() => {
    if (!map || !selectedTransferId || !tp.length) return;
    const descriptor = tp.find(d => transferPointKey(d) === selectedTransferId);
    if (!descriptor) return;
    const [lng, lat] = descriptor.coords;
    const b = map.getBounds();
    const w = b.getEast()  - b.getWest();
    const h = b.getNorth() - b.getSouth();
    const inset = 0.1;
    const offScreen =
      lng < b.getWest()  + w * inset || lng > b.getEast()  - w * inset ||
      lat < b.getSouth() + h * inset || lat > b.getNorth() - h * inset;
    if (offScreen) map.flyTo({ center: [lng, lat], duration: 400 });
  }, [map, selectedTransferId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Clear selection when the rider taps empty map (not a marker — MapLibre DOM
  // markers stop click propagation to the canvas, so this only fires on empty areas).
  useEffect(() => {
    if (!map || !onSelectTransfer) return;
    const handler = () => onSelectTransfer(null);
    map.on("click", handler);
    return () => map.off("click", handler);
  }, [map, onSelectTransfer]);

  // Feature RouteProgress — mute completed legs on the map.
  // Idempotent via a watermark ref (OPT-FE-213): only legs above the highest
  // previously-muted index get their paint properties touched on each advance.
  // useRouteLayers clears all layers when the route changes, so on route swap
  // we reset the watermark to -1.
  const mutedWatermarkRef = useRef(-1);
  useEffect(() => { mutedWatermarkRef.current = -1; }, [route]);
  useEffect(() => {
    if (!map || !route?.legs || activeLegIndex == null || activeLegIndex <= 0) return;
    const start = Math.max(0, mutedWatermarkRef.current + 1);
    for (let i = start; i < activeLegIndex; i++) {
      const leg = route.legs[i];
      const lineId = leg.type === "walk"
        ? `route-walk-line-${i}`
        : `route-transit-line-${i}`;
      if (map.getLayer(lineId)) {
        map.setPaintProperty(lineId, "line-color", MUTE_COLOR);
        map.setPaintProperty(lineId, "line-opacity", leg.type === "walk" ? 0.4 : 0.35);
      }
      const circleId = `route-boardexit-circle-${i}`;
      if (map.getLayer(circleId)) {
        map.setPaintProperty(circleId, "circle-opacity", 0.3);
      }
    }
    mutedWatermarkRef.current = Math.max(mutedWatermarkRef.current, activeLegIndex - 1);
  }, [map, activeLegIndex, route]);

  // ── Trip live position — split into focused effects (TD-FE-008) ──
  // The previous single 88-line effect mixed arrived detection, marker lifecycle,
  // camera follow, heading-up rotation, and teardown. Each concern now lives in
  // its own effect with the smallest dep set that keeps it correct.

  // Arrived latch — set once when the user is within ARRIVED_THRESHOLD_M of
  // destCoords. Reset by the route/destCoords effect above.
  useEffect(() => {
    if (!tripActive || !userPosition || !destCoords || arrived) return;
    const dist = haversineMeters(
      { lat: userPosition.lat, lng: userPosition.lng },
      { lat: destCoords[0], lng: destCoords[1] }, // destCoords is [lat, lon]
    );
    if (dist <= ARRIVED_THRESHOLD_M) {
      setArrived(true);
      onArrived?.();
    }
  }, [tripActive, userPosition, destCoords, arrived, onArrived]);

  // Live marker lifecycle + camera follow + heading-up rotation.
  // Imperative because the heading prop must update in lock-step with the
  // smoothedHeadingRef (a ref, intentionally non-reactive to avoid re-rendering
  // MapView at GPS rate). Skipped while no live data is available.
  useEffect(() => {
    if (!map || !tripActive || !userPosition) return;

    return whenStyleReady(map, () => {
      if (Number.isFinite(userPosition.heading)) {
        smoothedHeadingRef.current = smoothHeading(
          smoothedHeadingRef.current,
          userPosition.heading,
        );
      }

      // Adjust heading for current map bearing so the needle always points in
      // the world direction of travel, regardless of map rotation.
      const displayHeading = (smoothedHeadingRef.current + map.getBearing() + 360) % 360;
      const markerProps = {
        heading: displayHeading,
        hasHeading: Number.isFinite(userPosition.heading),
        reducedMotion: prefersReducedMotion,
        youLabel: t("marker_you"),
      };

      if (!liveMarkerRef.current) {
        liveMarkerRef.current = mountMarker(
          map,
          LivePositionMarker,
          markerProps,
          [userPosition.lng, userPosition.lat],
          { className: "marker-live-position-wrapper" },
        );
        liveMarkerRef.current.marker.getElement().addEventListener("click", (event) => {
          event.stopPropagation();
          handleRelockRef.current?.();
        });
        if (!firstFixDoneRef.current) {
          firstFixDoneRef.current = true;
          map.flyTo({ center: [userPosition.lng, userPosition.lat], zoom: 15 });
        }
        return;
      }

      liveMarkerRef.current.marker.setLngLat([userPosition.lng, userPosition.lat]);
      liveMarkerRef.current.root.render(<LivePositionMarker {...markerProps} />);
      if (unlocked) return;

      map.easeTo({ center: [userPosition.lng, userPosition.lat] });
      // Rotate map to face direction of travel in heading-up mode.
      // 1° guard prevents sub-degree GPS wobble from triggering rapid rotateTo calls.
      if (headingUp && Number.isFinite(smoothedHeadingRef.current)) {
        const target = -smoothedHeadingRef.current;
        if (Math.abs(map.getBearing() - target) >= 1) {
          map.rotateTo(target, { duration: 200 });
        }
      }
    });
  // handleRelock is stable (closes only over `map`/`userPosition` which are deps).
  }, [map, tripActive, userPosition, unlocked, headingUp, t]); // eslint-disable-line react-hooks/exhaustive-deps

  // Trip-end teardown — clear marker, reset transient refs, reset bearing.
  // Runs when tripActive transitions to false (or map unmounts).
  useEffect(() => {
    if (!map || tripActive) return;
    removeMarker(liveMarkerRef);
    smoothedHeadingRef.current = 0;
    firstFixDoneRef.current = false;
    setHeadingUp(false);
    map.rotateTo(0, { duration: 300 });
  }, [map, tripActive, setHeadingUp]);

  // On desktop the cards/map split is user-resizable via .panel-splitter; on
  // mobile, tab changes swap the visible panel. In both cases the map's
  // containing column may change width, so notify MapLibre after the relevant
  // transition or drag tick. PANEL_MAP_RESIZE_DELAY_MS mirrors --dur-base.
  // Resize is cheap; safe to call on every change.
  useEffect(() => {
    if (!map) return;
    const id = setTimeout(() => map.resize(), PANEL_MAP_RESIZE_DELAY_MS);
    return () => clearTimeout(id);
  }, [map, activeTab]);

  // Splitter drag — resize on every committed value change. The rAF throttling
  // happens upstream in PanelSplitter; here we just react.
  useEffect(() => {
    if (!map || cardsColumnWidth == null) return;
    map.resize();
  }, [map, cardsColumnWidth]);

  // Mobile bottom-sheet snap change — visible map area shrinks/grows when
  // the user drags the sheet between snap points. Debounced via the same
  // PANEL_MAP_RESIZE_DELAY_MS that the activeTab effect uses, so MapLibre
  // measures the new container after the sheet's CSS transition completes.
  useEffect(() => {
    if (!map || sheetSnap == null) return;
    const id = setTimeout(() => map.resize(), PANEL_MAP_RESIZE_DELAY_MS);
    return () => clearTimeout(id);
  }, [map, sheetSnap]);

  function handleUnlock() {
    if (!map) return;
    setMapInteractive(map, true);
    setUnlocked(true);
  }

  function handleRelock() {
    if (!map) return;
    setMapInteractive(map, false);
    setUnlocked(false);
    if (userPosition) {
      map.easeTo({ center: [userPosition.lng, userPosition.lat] });
    }
  }
  handleRelockRef.current = handleRelock;

  function handleToggleHeadingUp() {
    if (!map) return;
    if (headingUp) {
      map.rotateTo(0, { duration: 300 });
      setHeadingUp(false);
    } else {
      setHeadingUp(true);
    }
  }

  // Derive distinct transit legs for overlays. Memoised on `route` since this
  // feeds two map overlays (train card + legend) and MapView re-renders at GPS
  // rate during a trip; without memoisation the dedup work ran on every tick.
  const distinctTransitLegs = useMemo(() => {
    if (!route) return [];
    const seen = new Set();
    const out = [];
    for (const l of route.legs) {
      if (l.type !== "transit") continue;
      if (seen.has(l.line)) continue;
      seen.add(l.line);
      out.push(l);
    }
    return out;
  }, [route]);
  const primaryTransitLeg = distinctTransitLegs[0] ?? null;

  return (
    <div className="map-view map-view--visible">
      {route && tripActive && tp.map(d => (
        <TransferPointMount
          key={transferPointKey(d)}
          map={map}
          descriptor={d}
          activeLegIndex={activeLegIndex}
          selectedTransferId={selectedTransferId}
          onSelectTransfer={onSelectTransfer}
        />
      ))}
      <div ref={containerRef} className="map-container" />
      {styleError && (
        <div className="map-error">
          {t("map_tiles_error")}
        </div>
      )}
      {route && !unlocked && !styleError && (
        <button className="map-unlock-btn" onClick={handleUnlock}>
          {t("map_unlock_btn")}
        </button>
      )}
      {route && tripActive && unlocked && !styleError && (
        <button className="map-relock-btn" onClick={handleRelock}>
          {t("map_relock_btn")}
        </button>
      )}
      {primaryTransitLeg && (
        <div className="map-train-card">
          <div className="map-train-card__kicker">{t(primaryTransitLeg.line in BUS_DIRECTION_COLORS ? "map_your_bus" : "map_your_train")}</div>
          <div className="map-train-card__line">
            <LinePill
              line={primaryTransitLeg.line}
              isBus={primaryTransitLeg.line in BUS_DIRECTION_COLORS}
              lineCode={primaryTransitLeg.line_code}
              size="sm"
            />
            <span className="map-train-card__line-text">
              {primaryTransitLeg.line in BUS_DIRECTION_COLORS
                ? t("map_bus_label", { code: primaryTransitLeg.line_code })
                : t("map_train_label", { color: stripLineSuffix(primaryTransitLeg.line) })}
            </span>
          </div>
          <div className="map-train-card__desc">
            {primaryTransitLeg.from} → {primaryTransitLeg.to}
          </div>
        </div>
      )}
      {distinctTransitLegs.length > 0 && (
        <div className="map-legend">
          {distinctTransitLegs.map((leg, i) => (
            <div key={i} className="map-legend-chip">
              <LinePill
                line={leg.line}
                isBus={leg.line in BUS_DIRECTION_COLORS}
                lineCode={leg.line_code}
                size="sm"
              />
              <span className="map-legend-name">
                {leg.line_code ? t("map_bus_label", { code: leg.line_code }) : leg.line}
              </span>
            </div>
          ))}
        </div>
      )}
      {tripActive && !styleError && (
        <CompassRose
          map={map}
          headingUp={headingUp}
          onToggle={handleToggleHeadingUp}
          smoothedHeadingRef={smoothedHeadingRef}
          t={t}
        />
      )}
    </div>
  );
}
