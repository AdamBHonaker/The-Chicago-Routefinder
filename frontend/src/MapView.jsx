import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import maplibregl from "maplibre-gl";
import { useLocalStorage } from "./hooks/useLocalStorage.js";
import { useMapMarker, mountMarker, removeMarker } from "./hooks/useMapMarker.jsx";
import { useRouteLayers } from "./hooks/useRouteLayers.js";
import { BUS_DIRECTION_COLORS } from "./constants.js";
import { haversineMeters } from "./utils/tripGeometry.js";
import LinePill from "./components/LinePill.jsx";
import OriginMarker from "./components/markers/OriginMarker.jsx";
import DestinationMarker from "./components/markers/DestinationMarker.jsx";
import LivePositionMarker from "./components/markers/LivePositionMarker.jsx";

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
// Component
// ---------------------------------------------------------------------------

export default function MapView({
  route          = null,
  originCoords   = null,
  destCoords     = null,
  userPosition   = null,
  tripActive     = false,
  activeLegIndex = null,
  activeTab      = "home",
  onArrived      = null,
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
  // Reactive mirror of map.getBearing(). MapLibre updates bearing imperatively
  // (drag-rotate, rotateTo, easeTo), so reading it during render alone leaves
  // bearing-derived UI (the compass rose below) stale until something else
  // re-renders. The `rotate` listener wired up in the map-init effect keeps
  // this in sync.
  const [mapBearing, setMapBearing] = useState(0);
  const [headingUp, setHeadingUp] = useLocalStorage("cta_heading_up", false);
  const [arrived, setArrived] = useState(false);

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

      // Mirror bearing into React state so bearing-derived UI re-renders when
      // the user drag-rotates or programmatic rotateTo/easeTo runs.
      mapInstance.on("rotate", () => setMapBearing(mapInstance.getBearing()));

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

      setMap(mapInstance);
    }, 0);

    return () => {
      clearTimeout(timerId);
      mapInstance?.remove();
      setMap(null);
    };
  // Intentionally empty deps: props (style, center, zoom) are construction-time
  // values; re-running this effect would destroy and recreate the WebGL context.
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Render route polylines + stop circles via the layer-management hook.
  useRouteLayers(map, route);

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
  useMapMarker(map, OriginMarker, { fromLabel: t("marker_from") }, originLngLat);
  useMapMarker(
    map,
    DestinationMarker,
    { arrived, toLabel: t("marker_to"), arrivedLabel: t("marker_arrived") },
    destLngLat,
  );

  // Feature RouteProgress — mute completed legs on the map.
  // Iterates legs 0..activeLegIndex-1 and dims their polyline/circle layers.
  // useRouteLayers clears all layers when the route changes so no reset needed.
  useEffect(() => {
    if (!map || !route?.legs || activeLegIndex == null || activeLegIndex <= 0) return;
    for (let i = 0; i < activeLegIndex; i++) {
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
          handleRelock();
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

  // On desktop, panel-map transitions in over 220ms (--dur-base). Notify
  // MapLibre after the transition so the WebGL framebuffer matches the new
  // container dimensions. Safe to call on every tab change — resize is cheap.
  useEffect(() => {
    if (!map) return;
    const id = setTimeout(() => map.resize(), 220);
    return () => clearTimeout(id);
  }, [map, activeTab]);

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
                : t("map_train_label", { color: primaryTransitLeg.line?.replace(" Line", "") })}
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
        <button
          className={`map-heading-btn${headingUp ? " map-heading-btn--active" : ""}`}
          onClick={handleToggleHeadingUp}
          aria-pressed={headingUp}
          aria-label={headingUp ? t("map_heading_north_btn") : t("map_heading_up_btn")}
        >
          <svg
            className="map-heading-btn__rose"
            width="16" height="16" viewBox="-8 -8 16 16"
            aria-hidden="true"
            style={{ transform: `rotate(${mapBearing}deg)` }}
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
      )}
    </div>
  );
}
