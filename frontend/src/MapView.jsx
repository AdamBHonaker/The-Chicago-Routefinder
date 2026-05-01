import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ReactDOM from "react-dom/client";
import maplibregl from "maplibre-gl";
import { getRouteColor, BUS_DIRECTION_COLORS } from "./constants.js";
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

function legColor(leg) {
  return getRouteColor(leg.line);
}

// Backend returns [lat, lon]; GeoJSON / MapLibre expects [lon, lat].
const toGeo = ([lat, lon]) => [lon, lat];

// Returns true only for a two-element array where both values are finite numbers.
// Guards against null, undefined, empty arrays, [null, null], and plain objects.
const isValidCoord = (c) =>
  Array.isArray(c) && c.length === 2 &&
  typeof c[0] === "number" && isFinite(c[0]) &&
  typeof c[1] === "number" && isFinite(c[1]);

// ---------------------------------------------------------------------------
// Marker utilities
// ---------------------------------------------------------------------------

// Intentional snapshot: evaluated at page load, not updated mid-session.
// A full reload picks up any change to the OS reduced-motion preference.
const prefersReducedMotion =
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Circular exponential moving average for heading smoothing.
// alpha=0.3 → each new reading contributes 30%, history 70% (~2–3 reading lag at 1 Hz GPS).
// Handles the 0°/360° wrap-around correctly — a naive average of 350° and 10° yields 180°.
function smoothHeading(prev, next, alpha = 0.3) {
  const delta = ((next - prev + 540) % 360) - 180;
  return (prev + alpha * delta + 360) % 360;
}

// Mount a React component as a MapLibre marker at the given [lng, lat].
// Returns { marker, root } — keep the reference to update props or remove later.
function mountMarker(map, Component, props, lngLat) {
  const el = document.createElement("div");
  const root = ReactDOM.createRoot(el);
  root.render(<Component {...props} />);
  const marker = new maplibregl.Marker({ element: el, anchor: "center" })
    .setLngLat(lngLat)
    .addTo(map);
  return { marker, root };
}

// Remove a marker previously created by mountMarker and clear the ref.
function removeMarker(ref) {
  ref.current?.marker.remove();
  ref.current?.root.unmount();
  ref.current = null;
}

// ---------------------------------------------------------------------------
// Layer management helpers
// ---------------------------------------------------------------------------

/**
 * Remove all route layers/sources whose IDs are tracked in the provided arrays,
 * then clear those arrays.  Does NOT call map.isStyleLoaded() — we use the
 * tracked ID lists so old layers are never left behind even when the style
 * reloads mid-session.  try/catch guards against layers that were never added
 * (e.g. because style wasn't loaded when renderRoute ran).
 */
function clearRouteLayers(map, layerIds, sourceIds) {
  // Layers must be removed before their sources
  for (const id of layerIds.splice(0)) {
    try { map.removeLayer(id); } catch { /* already gone or style reloaded */ }
  }
  for (const id of sourceIds.splice(0)) {
    try { map.removeSource(id); } catch { /* already gone or style reloaded */ }
  }
}

/** Thin wrappers that add a source/layer AND record the ID for later cleanup. */
function _trackSource(map, id, data, sourceIds) {
  map.addSource(id, data);
  sourceIds.push(id);
}

function _trackLayer(map, cfg, layerIds) {
  map.addLayer(cfg);
  layerIds.push(cfg.id);
}

// ---------------------------------------------------------------------------
// Route rendering
// ---------------------------------------------------------------------------

function renderRoute(map, route, originCoords, destCoords, layerIds, sourceIds) {
  if (!route?.legs?.length) return;
  try {
    _renderRouteInner(map, route, originCoords, destCoords, layerIds, sourceIds);
  } catch (err) {
    console.error("[MapView] renderRoute failed:", err);
  }
}

// renderPolylines — Pass 1 of route rendering.
// Adds one LineString layer per leg (dashed grey for walk, solid colored for transit).
// Pushes all rendered coordinates into allGeoCoords for auto-fit bounds. (TD-037)
function renderPolylines(map, legs, legGeoCoords, legColors, allGeoCoords, layerIds, sourceIds) {
  legs.forEach((leg, i) => {
    if (leg.type === "walk") {
      const coords = legGeoCoords[i];
      if (coords.length < 2) return;
      coords.forEach(c => allGeoCoords.push(c));
      _trackSource(map, `route-walk-${i}`, {
        type: "geojson",
        data: { type: "Feature", geometry: { type: "LineString", coordinates: coords } },
      }, sourceIds);
      _trackLayer(map, {
        id:     `route-walk-line-${i}`,
        type:   "line",
        source: `route-walk-${i}`,
        paint:  { "line-color": "#888888", "line-width": 3, "line-dasharray": [2, 2] },
      }, layerIds);
    } else if (leg.type === "transit") {
      const coords = legGeoCoords[i];
      if (coords.length < 2) return;
      coords.forEach(c => allGeoCoords.push(c));
      _trackSource(map, `route-transit-${i}`, {
        type: "geojson",
        data: { type: "Feature", geometry: { type: "LineString", coordinates: coords } },
      }, sourceIds);
      _trackLayer(map, {
        id:     `route-transit-line-${i}`,
        type:   "line",
        source: `route-transit-${i}`,
        layout: { "line-cap": "round", "line-join": "round" },
        paint:  { "line-color": legColors[i], "line-width": 5 },
      }, layerIds);
    }
  });
}

// renderStopMarkers — Pass 2 of route rendering.
// Adds board/exit circle markers and evenly-sampled intermediate stop dots
// for each transit leg. Rendered after polylines so markers sit on top. (TD-037)
function renderStopMarkers(map, legs, legGeoCoords, legColors, layerIds, sourceIds) {
  legs.forEach((leg, i) => {
    if (leg.type !== "transit") return;
    const color = legColors[i];

    // Board / exit stop markers — guard against missing or malformed coordinate arrays.
    const boardExit = [];
    if (isValidCoord(leg.from_coords)) boardExit.push({ coord: toGeo(leg.from_coords), label: `Board ${leg.line}`, color });
    if (isValidCoord(leg.to_coords))   boardExit.push({ coord: toGeo(leg.to_coords),   label: `Exit ${leg.line}`,  color });

    if (boardExit.length) {
      _trackSource(map, `route-boardexit-${i}`, {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: boardExit.map(({ coord, label, color: c }) => ({
            type: "Feature",
            geometry:   { type: "Point", coordinates: coord },
            properties: { label, color: c },
          })),
        },
      }, sourceIds);
      _trackLayer(map, {
        id:     `route-boardexit-circle-${i}`,
        type:   "circle",
        source: `route-boardexit-${i}`,
        paint:  {
          "circle-radius":       7,
          "circle-color":        ["get", "color"],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      }, layerIds);
    }

    // Intermediate stops — evenly sampled from the clipped shape.
    const geoShape = legGeoCoords[i];
    if (geoShape.length > 10) {
      const step = Math.max(3, Math.floor(geoShape.length / 10));
      const intermFeatures = [];
      for (let j = step; j < geoShape.length - step; j += step) {
        intermFeatures.push({
          type: "Feature",
          geometry:   { type: "Point", coordinates: geoShape[j] },
          properties: { color },
        });
      }
      if (intermFeatures.length) {
        _trackSource(map, `route-stops-${i}`, {
          type: "geojson",
          data: { type: "FeatureCollection", features: intermFeatures },
        }, sourceIds);
        _trackLayer(map, {
          id:     `route-stops-circle-${i}`,
          type:   "circle",
          source: `route-stops-${i}`,
          paint:  {
            "circle-radius":       4,
            "circle-color":        "#ffffff",
            "circle-stroke-width": 2,
            "circle-stroke-color": ["get", "color"],
          },
        }, layerIds);
      }
    }
  });
}


function _renderRouteInner(map, route, originCoords, destCoords, layerIds, sourceIds) {
  const { legs } = route;

  // Precompute per-leg colors once to avoid re-invoking legColor in each pass.
  const legColors = legs.map(leg => leg.type === "transit" ? legColor(leg) : null);

  // Pre-transform all path/shape coordinates once — avoids repeated .map(toGeo).
  const legGeoCoords = legs.map(leg => {
    if (leg.type === "walk")    return (leg.path  ?? []).map(toGeo);
    if (leg.type === "transit") return (leg.shape ?? []).map(toGeo);
    return [];
  });

  // Accumulate rendered coordinates for auto-fit bounds (GeoJSON [lon, lat] order).
  const allGeoCoords = [];

  renderPolylines(map, legs, legGeoCoords, legColors, allGeoCoords, layerIds, sourceIds);
  renderStopMarkers(map, legs, legGeoCoords, legColors, layerIds, sourceIds);

  // ── Auto-fit: snap to bounding box of all route coordinates ───────────────
  if (allGeoCoords.length > 0) {
    const bounds = allGeoCoords.reduce(
      ([sw, ne], [lon, lat]) => [
        [Math.min(sw[0], lon), Math.min(sw[1], lat)],
        [Math.max(ne[0], lon), Math.max(ne[1], lat)],
      ],
      [[Infinity, Infinity], [-Infinity, -Infinity]],
    );
    map.fitBounds(bounds, { padding: 60, animate: false });
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function MapView({
  route        = null,
  originCoords = null,
  destCoords   = null,
  userPosition = null,
  tripActive   = false,
  style        = DEFAULT_STYLE,
  center       = DEFAULT_CENTER,
  zoom         = DEFAULT_ZOOM,
}) {
  const { t } = useTranslation();
  const containerRef  = useRef(null);
  const mapRef        = useRef(null);
  const routeLayerIds  = useRef([]);   // tracked IDs set during renderRoute
  const routeSourceIds = useRef([]);
  const originMarkerRef    = useRef(null); // { marker, root } for OriginMarker
  const destMarkerRef      = useRef(null); // { marker, root } for DestinationMarker
  const liveMarkerRef      = useRef(null); // { marker, root } for LivePositionMarker
  const smoothedHeadingRef = useRef(0);    // circular EMA state for heading
  const arrivedRef         = useRef(false); // one-way latch: destination arrived
  const [unlocked, setUnlocked] = useState(false);
  const [styleError, setStyleError] = useState(false);

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
    let map = null;

    const timerId = setTimeout(() => {
      const container = containerRef.current;
      if (!container) return;

      map = new maplibregl.Map({
        container,
        style,
        center,
        zoom,
        // Don't bail on software-rendered WebGL2 contexts (some Windows GPU drivers)
        failIfMajorPerformanceCaveat: false,
      });

      // Lock all interactions by default
      map.scrollZoom.disable();
      map.dragPan.disable();
      map.dragRotate.disable();
      map.doubleClickZoom.disable();
      map.touchZoomRotate.disable();
      map.keyboard.disable();

      // After style loads: resize + repaint so the WebGL framebuffer is presented
      // correctly when the container starts at opacity:0.
      map.once("load", () => {
        map.resize();
        map.triggerRepaint();
      });

      map.on("error", (e) => {
        console.error("[MapView] map error:", e?.error ?? e);
        // Only latch the error banner for style *document* failures — not
        // transient per-tile 404s or network blips, which self-recover.
        const status = e?.error?.status;
        const isStyleSource = e?.sourceId === "openmaptiles" ||
                              e?.error?.message?.toLowerCase().includes("style");
        if (isStyleSource && (status === 0 || (status >= 400 && status < 600))) {
          setStyleError(true);
          map.once("styledata", () => setStyleError(false));
        }
      });

      mapRef.current = map;
    }, 0);

    return () => {
      clearTimeout(timerId);
      map?.remove();
      mapRef.current = null;
    };
  // Intentionally empty deps: props (style, center, zoom) are construction-time
  // values; re-running this effect would destroy and recreate the WebGL context.
  }, []); // eslint-disable-line react-hooks/exhaustive-deps


  // Re-render route layers and origin/destination markers whenever route/coords change.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const render = () => {
      // Clear previous polylines/stop markers and React origin/dest markers.
      clearRouteLayers(map, routeLayerIds.current, routeSourceIds.current);
      removeMarker(originMarkerRef);
      removeMarker(destMarkerRef);
      arrivedRef.current = false;

      if (!route) return;

      renderRoute(map, route, originCoords, destCoords, routeLayerIds.current, routeSourceIds.current);

      // Resolve origin lngLat — explicit prop first, then first path point of first leg.
      const originLngLat = originCoords
        ? [originCoords[1], originCoords[0]]
        : (() => { const p = route.legs?.[0]?.path?.[0]; return p ? toGeo(p) : null; })();

      // Resolve dest lngLat — explicit prop first, then last path point of last leg.
      const lastLeg = route.legs?.[route.legs.length - 1];
      const destLngLat = destCoords
        ? [destCoords[1], destCoords[0]]
        : (lastLeg?.path?.length ? toGeo(lastLeg.path[lastLeg.path.length - 1]) : null);

      // Render order: origin first, destination second — user position (live effect) last.
      if (originLngLat) {
        originMarkerRef.current = mountMarker(map, OriginMarker, { fromLabel: t("marker_from") }, originLngLat);
      }
      if (destLngLat) {
        destMarkerRef.current = mountMarker(map, DestinationMarker, {
          arrived: false,
          toLabel: t("marker_to"),
          arrivedLabel: t("marker_arrived"),
        }, destLngLat);
      }
    };

    if (map.isStyleLoaded()) {
      render();
    } else {
      // Style not yet loaded — defer until it is, clean up if route changes first.
      map.once("load", render);
      return () => map.off("load", render);
    }
  // `renderRoute`, `clearRouteLayers`, `mountMarker`, `removeMarker` are stable module-level
  // functions; refs are not reactive values — omitting them is correct.
  }, [route, originCoords, destCoords]); // eslint-disable-line react-hooks/exhaustive-deps

  // Live position marker — shown during an active trip.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    function render() {
      if (tripActive && userPosition) {
        // Smooth the raw heading before it reaches the marker.
        if (Number.isFinite(userPosition.heading)) {
          smoothedHeadingRef.current = smoothHeading(
            smoothedHeadingRef.current,
            userPosition.heading,
          );
        }

        // Arrived latch — 50 m threshold, never resets during a trip.
        if (!arrivedRef.current && destCoords) {
          const dist = haversineMeters(
            { lat: userPosition.lat, lng: userPosition.lng },
            { lat: destCoords[0], lng: destCoords[1] }, // destCoords is [lat, lon]
          );
          if (dist <= 50) {
            arrivedRef.current = true;
            destMarkerRef.current?.root.render(
              <DestinationMarker arrived={true} arrivedLabel={t("marker_arrived")} />,
            );
          }
        }

        const markerProps = {
          heading: smoothedHeadingRef.current,
          hasHeading: Number.isFinite(userPosition.heading),
          reducedMotion: prefersReducedMotion,
        };

        if (!liveMarkerRef.current) {
          liveMarkerRef.current = mountMarker(
            map,
            LivePositionMarker,
            { ...markerProps, youLabel: t("marker_you") },
            [userPosition.lng, userPosition.lat],
          );
          // Center map on first GPS fix.
          map.flyTo({ center: [userPosition.lng, userPosition.lat], zoom: 15 });
        } else {
          liveMarkerRef.current.marker.setLngLat([userPosition.lng, userPosition.lat]);
          liveMarkerRef.current.root.render(<LivePositionMarker {...markerProps} youLabel={t("marker_you")} />);
          // Keep user centered while map is locked during an active trip.
          if (!unlocked) {
            map.easeTo({ center: [userPosition.lng, userPosition.lat] });
          }
        }
      } else {
        // Trip ended or no position — tear down marker and reset transient state.
        removeMarker(liveMarkerRef);
        smoothedHeadingRef.current = 0;
        arrivedRef.current = false;
      }
    }

    if (!map.isStyleLoaded()) {
      map.once("load", render);
      return () => map.off("load", render);
    }
    render();
  // `mapRef`, refs, and module-level helpers are not reactive values — omitting is correct.
  // `destCoords` is intentionally omitted: the arrived latch resets via the route effect
  // when destCoords changes, and the latch only ever needs the coord at latch-check time.
  }, [tripActive, userPosition, unlocked]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleUnlock() {
    const map = mapRef.current;
    if (!map) return;
    map.scrollZoom.enable();
    map.dragPan.enable();
    map.dragRotate.enable();
    map.doubleClickZoom.enable();
    map.touchZoomRotate.enable();
    map.keyboard.enable();
    setUnlocked(true);
  }

  // Derive distinct transit legs for overlays — display computation only, no hooks.
  const distinctTransitLegs = route
    ? route.legs
        .filter((l) => l.type === "transit")
        .filter((l, i, arr) => arr.findIndex((x) => x.line === l.line) === i)
    : [];
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
    </div>
  );
}
