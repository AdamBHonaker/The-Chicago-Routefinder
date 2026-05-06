/**
 * useRouteLayers — render a route's polylines and stop markers on a MapLibre map.
 *
 * Encapsulates the imperative source/layer bookkeeping that previously lived
 * inline in MapView.jsx. Tracked layer/source IDs are kept in owned refs;
 * lifecycle helpers come from `utils/mapLayerLifecycle.js` (TD-FE-020).
 * Style-load gating is handled internally — callers don't need to check
 * map.isStyleLoaded().
 *
 * The hook re-renders when map / route / originCoords / destCoords change.
 * On every change it clears prior layers via tracked IDs (try/catch guards
 * survive style reloads) before adding the new ones.
 *
 * Returns the layer-IDs ref so other effects (e.g. leg-muting) can call
 * map.setPaintProperty by ID without duplicating the naming convention.
 */
import { useEffect, useRef } from "react";
import { getRouteColor } from "../constants.js";
import { clearLayers, trackSource, trackLayer } from "../utils/mapLayerLifecycle.js";

const toGeo = ([lat, lon]) => [lon, lat];

const isValidCoord = (c) =>
  Array.isArray(c) && c.length === 2 &&
  typeof c[0] === "number" && isFinite(c[0]) &&
  typeof c[1] === "number" && isFinite(c[1]);

export const WALK_LINE_PAINT = {
  "line-color": "#888888",
  "line-width": 3,
  "line-dasharray": [2, 2],
};

function legColor(leg) {
  return getRouteColor(leg.line);
}

// Pass 1: per-leg LineString layers (dashed grey for walk, solid colored for transit).
// Pushes coordinates into allGeoCoords for auto-fit bounds.
function renderPolylines(map, legs, legGeoCoords, legColors, allGeoCoords, layerIds, sourceIds) {
  legs.forEach((leg, i) => {
    if (leg.type === "walk") {
      const coords = legGeoCoords[i];
      if (coords.length < 2) return;
      coords.forEach(c => allGeoCoords.push(c));
      trackSource(map, `route-walk-${i}`, {
        type: "geojson",
        data: { type: "Feature", geometry: { type: "LineString", coordinates: coords } },
      }, sourceIds);
      trackLayer(map, {
        id:     `route-walk-line-${i}`,
        type:   "line",
        source: `route-walk-${i}`,
        paint:  WALK_LINE_PAINT,
      }, layerIds);
    } else if (leg.type === "transit") {
      const coords = legGeoCoords[i];
      if (coords.length < 2) return;
      coords.forEach(c => allGeoCoords.push(c));
      trackSource(map, `route-transit-${i}`, {
        type: "geojson",
        data: { type: "Feature", geometry: { type: "LineString", coordinates: coords } },
      }, sourceIds);
      trackLayer(map, {
        id:     `route-transit-line-${i}`,
        type:   "line",
        source: `route-transit-${i}`,
        layout: { "line-cap": "round", "line-join": "round" },
        paint:  { "line-color": legColors[i], "line-width": 5 },
      }, layerIds);
    }
  });
}

// Pass 2: board/exit circles + evenly-sampled intermediate stop dots per transit leg.
// Rendered after polylines so circles sit on top.
function renderStopMarkers(map, legs, legGeoCoords, legColors, layerIds, sourceIds) {
  legs.forEach((leg, i) => {
    if (leg.type !== "transit") return;
    const color = legColors[i];

    const boardExit = [];
    if (isValidCoord(leg.from_coords)) boardExit.push({ coord: toGeo(leg.from_coords), label: `Board ${leg.line}`, color });
    if (isValidCoord(leg.to_coords))   boardExit.push({ coord: toGeo(leg.to_coords),   label: `Exit ${leg.line}`,  color });

    if (boardExit.length) {
      trackSource(map, `route-boardexit-${i}`, {
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
      trackLayer(map, {
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
        trackSource(map, `route-stops-${i}`, {
          type: "geojson",
          data: { type: "FeatureCollection", features: intermFeatures },
        }, sourceIds);
        trackLayer(map, {
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

function renderRoute(map, route, layerIds, sourceIds) {
  if (!route?.legs?.length) return;
  try {
    const { legs } = route;
    const legColors = legs.map(leg => leg.type === "transit" ? legColor(leg) : null);
    const legGeoCoords = legs.map(leg => {
      if (leg.type === "walk")    return (leg.path  ?? []).map(toGeo);
      if (leg.type === "transit") return (leg.shape ?? []).map(toGeo);
      return [];
    });
    const allGeoCoords = [];

    renderPolylines(map, legs, legGeoCoords, legColors, allGeoCoords, layerIds, sourceIds);
    renderStopMarkers(map, legs, legGeoCoords, legColors, layerIds, sourceIds);

    if (allGeoCoords.length > 0) {
      // Single-pass scalar mins/maxes; reduce-with-tuples allocated 4 sub-arrays
      // per coordinate, which adds up over long polylines (OPT-FE-205).
      let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
      for (let i = 0; i < allGeoCoords.length; i++) {
        const lon = allGeoCoords[i][0];
        const lat = allGeoCoords[i][1];
        if (lon < minLng) minLng = lon;
        if (lat < minLat) minLat = lat;
        if (lon > maxLng) maxLng = lon;
        if (lat > maxLat) maxLat = lat;
      }
      map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 60, animate: false });
    }
  } catch (err) {
    console.error("[useRouteLayers] renderRoute failed:", err);
  }
}

export function useRouteLayers(map, route) {
  const layerIds = useRef([]);
  const sourceIds = useRef([]);

  useEffect(() => {
    if (!map) return;

    const render = () => {
      clearLayers(map, layerIds.current, sourceIds.current);
      if (!route) return;
      renderRoute(map, route, layerIds.current, sourceIds.current);
    };

    if (map.isStyleLoaded()) {
      render();
      return () => clearLayers(map, layerIds.current, sourceIds.current);
    }
    map.once("load", render);
    return () => {
      map.off("load", render);
      clearLayers(map, layerIds.current, sourceIds.current);
    };
  }, [map, route]);

  return layerIds;
}
