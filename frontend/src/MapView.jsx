import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";

// ---------------------------------------------------------------------------
// Map defaults — overridable via props for future view modes
// ---------------------------------------------------------------------------

const DEFAULT_STYLE  = "https://tiles.openfreemap.org/styles/liberty";
const DEFAULT_CENTER = [-87.654, 41.966]; // Uptown, Chicago
const DEFAULT_ZOOM   = 13;

// ---------------------------------------------------------------------------
// Line color tables (mirrors App.jsx — used here for map layer paint)
// ---------------------------------------------------------------------------

const LINE_COLORS = {
  "Red Line":    "#c60c30",
  "Blue Line":   "#00a1de",
  "Brown Line":  "#62361b",
  "Green Line":  "#009b3a",
  "Orange Line": "#f9461c",
  "Purple Line": "#522398",
  "Pink Line":   "#e27ea6",
  "Yellow Line": "#f9e300",
};

const BUS_DIRECTION_COLORS = {
  Northbound: "#1565c0",
  Southbound: "#4e342e",
  Eastbound:  "#00695c",
  Westbound:  "#ef6c00",
};

function legColor(leg) {
  return LINE_COLORS[leg.line] ?? BUS_DIRECTION_COLORS[leg.line] ?? "#4a9eff";
}

// Backend returns [lat, lon]; GeoJSON / MapLibre expects [lon, lat].
const toGeo = ([lat, lon]) => [lon, lat];

// ---------------------------------------------------------------------------
// Layer management helpers
// ---------------------------------------------------------------------------

function clearRouteLayers(map) {
  if (!map.isStyleLoaded()) return;
  const style = map.getStyle();

  // Layers must be removed before their sources
  for (const layer of style.layers) {
    if (layer.id.startsWith("route-")) map.removeLayer(layer.id);
  }
  for (const sourceId of Object.keys(style.sources)) {
    if (sourceId.startsWith("route-")) map.removeSource(sourceId);
  }
}

// ---------------------------------------------------------------------------
// Route rendering
// ---------------------------------------------------------------------------

function renderRoute(map, route, originCoords, destCoords) {
  const { legs } = route;
  if (!legs?.length) return;

  // Accumulate every coordinate for auto-fit bounds (in GeoJSON [lon, lat] order)
  const allGeoCoords = [];

  // ── Pass 1: polylines ────────────────────────────────────────────────────

  legs.forEach((leg, i) => {
    if (leg.type === "walk") {
      const coords = (leg.path ?? []).map(toGeo);
      if (coords.length < 2) return;
      coords.forEach(c => allGeoCoords.push(c));

      map.addSource(`route-walk-${i}`, {
        type: "geojson",
        data: { type: "Feature", geometry: { type: "LineString", coordinates: coords } },
      });
      map.addLayer({
        id:     `route-walk-line-${i}`,
        type:   "line",
        source: `route-walk-${i}`,
        paint:  { "line-color": "#888888", "line-width": 3, "line-dasharray": [2, 2] },
      });

    } else if (leg.type === "transit") {
      const coords = (leg.shape ?? []).map(toGeo);
      if (coords.length < 2) return;
      coords.forEach(c => allGeoCoords.push(c));

      const color = legColor(leg);
      map.addSource(`route-transit-${i}`, {
        type: "geojson",
        data: { type: "Feature", geometry: { type: "LineString", coordinates: coords } },
      });
      map.addLayer({
        id:     `route-transit-line-${i}`,
        type:   "line",
        source: `route-transit-${i}`,
        layout: { "line-cap": "round", "line-join": "round" },
        paint:  { "line-color": color, "line-width": 5 },
      });
    }
  });

  // ── Pass 2: markers (rendered after all lines so they sit on top) ─────────

  legs.forEach((leg, i) => {
    if (leg.type === "transit") {
      const color = legColor(leg);

      // Board / exit stop markers
      const boardExit = [];
      if (leg.from_coords) boardExit.push({ coord: toGeo(leg.from_coords), label: `Board ${leg.line}`, color });
      if (leg.to_coords)   boardExit.push({ coord: toGeo(leg.to_coords),   label: `Exit ${leg.line}`,  color });

      if (boardExit.length) {
        map.addSource(`route-boardexit-${i}`, {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: boardExit.map(({ coord, label, color: c }) => ({
              type: "Feature",
              geometry:   { type: "Point", coordinates: coord },
              properties: { label, color: c },
            })),
          },
        });
        map.addLayer({
          id:     `route-boardexit-circle-${i}`,
          type:   "circle",
          source: `route-boardexit-${i}`,
          paint:  {
            "circle-radius":       7,
            "circle-color":        ["get", "color"],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });
      }

      // Intermediate stops — evenly sampled from the clipped shape
      const shape = leg.shape ?? [];
      if (shape.length > 10) {
        const step = Math.max(3, Math.floor(shape.length / 10));
        const intermFeatures = [];
        for (let j = step; j < shape.length - step; j += step) {
          intermFeatures.push({
            type: "Feature",
            geometry:   { type: "Point", coordinates: toGeo(shape[j]) },
            properties: { color },
          });
        }

        if (intermFeatures.length) {
          map.addSource(`route-stops-${i}`, {
            type: "geojson",
            data: { type: "FeatureCollection", features: intermFeatures },
          });
          map.addLayer({
            id:     `route-stops-circle-${i}`,
            type:   "circle",
            source: `route-stops-${i}`,
            paint:  {
              "circle-radius":       4,
              "circle-color":        "#ffffff",
              "circle-stroke-width": 2,
              "circle-stroke-color": ["get", "color"],
            },
          });
        }
      }
    }
  });

  // Origin dot — use explicit originCoords prop; fall back to first leg path
  const originPt = originCoords
    ? [originCoords[1], originCoords[0]]   // [lat,lon] → [lon,lat]
    : (() => { const p = legs[0]?.path?.[0]; return p ? toGeo(p) : null; })();
  if (originPt) {
    map.addSource("route-origin", {
      type: "geojson",
      data: { type: "Feature", geometry: { type: "Point", coordinates: originPt } },
    });
    map.addLayer({
      id:     "route-origin-circle",
      type:   "circle",
      source: "route-origin",
      paint:  {
        "circle-radius":       9,
        "circle-color":        "#4a9eff",
        "circle-stroke-width": 2,
        "circle-stroke-color": "#ffffff",
      },
    });
  }

  // Destination dot — use explicit destCoords prop; fall back to last leg path
  const destPt = destCoords
    ? [destCoords[1], destCoords[0]]       // [lat,lon] → [lon,lat]
    : (() => { const lp = legs[legs.length - 1]?.path; return lp?.length ? toGeo(lp[lp.length - 1]) : null; })();
  if (destPt) {
    map.addSource("route-dest", {
      type: "geojson",
      data: { type: "Feature", geometry: { type: "Point", coordinates: destPt } },
    });
    map.addLayer({
      id:     "route-dest-circle",
      type:   "circle",
      source: "route-dest",
      paint:  {
        "circle-radius":       9,
        "circle-color":        "#222222",
        "circle-stroke-width": 2,
        "circle-stroke-color": "#ffffff",
      },
    });
  }

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
  style        = DEFAULT_STYLE,
  center       = DEFAULT_CENTER,
  zoom         = DEFAULT_ZOOM,
}) {
  const containerRef = useRef(null);
  const mapRef       = useRef(null);
  const [unlocked, setUnlocked] = useState(false);
  const [styleError, setStyleError] = useState(false);

  // Initialize map once after the container div mounts.
  //
  // React 18 StrictMode (dev only) double-invokes effects: run → cleanup → run.
  // MapLibre GL v5 uses WebGL2 and its context isn't fully released synchronously
  // by map.remove(), so the immediate second init produces a silent black canvas.
  //
  // Fix: defer initialization with setTimeout(0). StrictMode's cleanup cancels
  // the first timer before it fires; only the second effect's timer survives,
  // by which point the previous WebGL context is fully torn down.
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
        }
      });

      // Clear the error banner once the map successfully loads or updates data
      map.on("data", (e) => {
        if (e.isSourceLoaded) {
          setStyleError(false);
        }
      });

      mapRef.current = map;
    }, 0);

    return () => {
      clearTimeout(timerId);
      map?.remove();
      mapRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps


  // Re-render route layers whenever the route prop changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const render = () => {
      clearRouteLayers(map);
      if (route) renderRoute(map, route, originCoords, destCoords);
    };

    if (map.isStyleLoaded()) {
      render();
    } else {
      // Style not yet loaded — defer until it is, clean up if route changes first
      map.once("load", render);
      return () => map.off("load", render);
    }
  }, [route, originCoords, destCoords]); // eslint-disable-line react-hooks/exhaustive-deps

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

  return (
    <div className="map-view map-view--visible">
      <div ref={containerRef} className="map-container" />
      {styleError && (
        <div className="map-error">
          Map tiles unavailable — check your connection or try again later.
        </div>
      )}
      {route && !unlocked && !styleError && (
        <button className="map-unlock-btn" onClick={handleUnlock}>
          🔓 Unlock map
        </button>
      )}
    </div>
  );
}
