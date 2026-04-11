import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";

// ---------------------------------------------------------------------------
// Map defaults — overridable via props for future view modes
// ---------------------------------------------------------------------------

const DEFAULT_STYLE  = "https://tiles.openfreemap.org/styles/positron";
const DEFAULT_CENTER = [-87.65, 41.85]; // Chicago
const DEFAULT_ZOOM   = 11;

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

function renderRoute(map, route) {
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

  // Origin dot — first point of first leg's path
  const firstPath = legs[0]?.path ?? [];
  if (firstPath.length) {
    const originCoord = toGeo(firstPath[0]);
    map.addSource("route-origin", {
      type: "geojson",
      data: { type: "Feature", geometry: { type: "Point", coordinates: originCoord } },
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

  // Destination dot — last point of last leg's path
  const lastPath = legs[legs.length - 1]?.path ?? [];
  if (lastPath.length) {
    const destCoord = toGeo(lastPath[lastPath.length - 1]);
    map.addSource("route-dest", {
      type: "geojson",
      data: { type: "Feature", geometry: { type: "Point", coordinates: destCoord } },
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
  route   = null,
  visible = false,
  style   = DEFAULT_STYLE,
  center  = DEFAULT_CENTER,
  zoom    = DEFAULT_ZOOM,
}) {
  const containerRef = useRef(null);
  const mapRef       = useRef(null);
  const [unlocked, setUnlocked] = useState(false);

  // Initialize map once after the container div mounts
  useEffect(() => {
    const map = new maplibregl.Map({
      container: containerRef.current,
      style,
      center,
      zoom,
    });

    // Lock all interactions by default
    map.scrollZoom.disable();
    map.dragPan.disable();
    map.dragRotate.disable();
    map.doubleClickZoom.disable();
    map.touchZoomRotate.disable();
    map.keyboard.disable();

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-render route layers whenever the route prop changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const render = () => {
      clearRouteLayers(map);
      if (route) renderRoute(map, route);
    };

    if (map.isStyleLoaded()) {
      render();
    } else {
      // Style not yet loaded — defer until it is, clean up if route changes first
      map.once("load", render);
      return () => map.off("load", render);
    }
  }, [route]);

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
    <div className={`map-view${visible ? " map-view--visible" : ""}`}>
      <div ref={containerRef} className="map-container" />
      {visible && !unlocked && (
        <button className="map-unlock-btn" onClick={handleUnlock}>
          🔓 Unlock map
        </button>
      )}
    </div>
  );
}
