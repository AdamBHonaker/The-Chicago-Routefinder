import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import maplibregl from "maplibre-gl";
import { getRouteColor, BUS_DIRECTION_COLORS } from "./constants.js";
import LinePill from "./components/LinePill.jsx";

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

// renderOriginDestMarkers — Pass 3 of route rendering.
// Adds a blue origin dot and a dark destination dot using the explicit coord
// props if available, falling back to the first/last leg path point. (TD-037)
function renderOriginDestMarkers(map, legs, originCoords, destCoords, layerIds, sourceIds) {
  const originPt = originCoords
    ? [originCoords[1], originCoords[0]]   // [lat,lon] → [lon,lat]
    : (() => { const p = legs[0]?.path?.[0]; return p ? toGeo(p) : null; })();
  if (originPt) {
    _trackSource(map, "route-origin", {
      type: "geojson",
      data: { type: "Feature", geometry: { type: "Point", coordinates: originPt } },
    }, sourceIds);
    _trackLayer(map, {
      id:     "route-origin-circle",
      type:   "circle",
      source: "route-origin",
      paint:  {
        "circle-radius":       9,
        "circle-color":        "#4a9eff",
        "circle-stroke-width": 2,
        "circle-stroke-color": "#ffffff",
      },
    }, layerIds);
  }

  const lastLegPath = legs.length > 0 ? legs[legs.length - 1]?.path : null;
  const destPt = destCoords
    ? [destCoords[1], destCoords[0]]       // [lat,lon] → [lon,lat]
    : (lastLegPath?.length ? toGeo(lastLegPath[lastLegPath.length - 1]) : null);
  if (destPt) {
    _trackSource(map, "route-dest", {
      type: "geojson",
      data: { type: "Feature", geometry: { type: "Point", coordinates: destPt } },
    }, sourceIds);
    _trackLayer(map, {
      id:     "route-dest-circle",
      type:   "circle",
      source: "route-dest",
      paint:  {
        "circle-radius":       9,
        "circle-color":        "#222222",
        "circle-stroke-width": 2,
        "circle-stroke-color": "#ffffff",
      },
    }, layerIds);
  }
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
  renderOriginDestMarkers(map, legs, originCoords, destCoords, layerIds, sourceIds);

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
  const userPosLayerRef = useRef(false); // whether user-position layer has been added
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
      userPosLayerRef.current = false; // reset on new map instance
    }, 0);

    return () => {
      clearTimeout(timerId);
      map?.remove();
      mapRef.current = null;
    };
  // Intentionally empty deps: props (style, center, zoom) are construction-time
  // values; re-running this effect would destroy and recreate the WebGL context.
  }, []); // eslint-disable-line react-hooks/exhaustive-deps


  // Re-render route layers whenever the route prop changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const render = () => {
      clearRouteLayers(map, routeLayerIds.current, routeSourceIds.current);
      if (route) renderRoute(map, route, originCoords, destCoords, routeLayerIds.current, routeSourceIds.current);
    };

    if (map.isStyleLoaded()) {
      render();
    } else {
      // Style not yet loaded — defer until it is, clean up if route changes first
      map.once("load", render);
      return () => map.off("load", render);
    }
  // `renderRoute` and `clearRouteLayers` are stable module-level functions;
  // `routeLayerIds`/`routeSourceIds` are refs — none are reactive values.
  }, [route, originCoords, destCoords]); // eslint-disable-line react-hooks/exhaustive-deps

  // User position dot — shown during an active trip
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    function render() {
      if (tripActive && userPosition) {
        const geoData = {
          type: "Feature",
          geometry: { type: "Point", coordinates: [userPosition.lng, userPosition.lat] },
        };

        if (!userPosLayerRef.current) {
          map.addSource("user-position-source", { type: "geojson", data: geoData });
          map.addLayer({
            id:     "user-position-layer",
            type:   "circle",
            source: "user-position-source",
            paint:  {
              "circle-color":        "#4A90E2",
              "circle-radius":       10,
              "circle-stroke-width": 2,
              "circle-stroke-color": "#ffffff",
            },
          });
          userPosLayerRef.current = true;
          // Center map on first GPS fix
          map.flyTo({ center: [userPosition.lng, userPosition.lat], zoom: 15 });
        } else {
          map.getSource("user-position-source")?.setData(geoData);
          try { map.setLayoutProperty("user-position-layer", "visibility", "visible"); } catch {}
        }
      } else if (userPosLayerRef.current) {
        try { map.setLayoutProperty("user-position-layer", "visibility", "none"); } catch {}
      }
    }

    if (!map.isStyleLoaded()) {
      map.once("load", render);
      return () => map.off("load", render);
    }
    render();
  // `mapRef` and `userPosLayerRef` are refs, not reactive values — omitting them is correct.
  }, [tripActive, userPosition]); // eslint-disable-line react-hooks/exhaustive-deps

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
      {tripActive && primaryTransitLeg && (
        <div className="map-train-card">
          <div className="map-train-card__kicker">{t("map_underway")}</div>
          <div className="map-train-card__line">
            <LinePill
              line={primaryTransitLeg.line}
              isBus={primaryTransitLeg.line in BUS_DIRECTION_COLORS}
              lineCode={primaryTransitLeg.line_code}
              size="sm"
            />
            <span className="map-train-card__line-text">
              {primaryTransitLeg.line_code
                ? t("map_bus_label", { code: primaryTransitLeg.line_code })
                : primaryTransitLeg.line?.replace(" Line", "") + " Line"}
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
