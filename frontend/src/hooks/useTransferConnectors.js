/**
 * useTransferConnectors — render dashed connector lines for split-stop transfers.
 *
 * For bus↔bus or rail↔bus transfers where the alighting and boarding stops are
 * 30ft–1 block apart, a short dashed line connects the two stops using the same
 * dash idiom as walking-leg polylines (WALK_LINE_PAINT from useRouteLayers).
 *
 * Mirrors useRouteLayers lifecycle: tracks layer/source IDs in owned refs,
 * clears + re-renders on dep change, gates on map.isStyleLoaded().
 * Does NOT import _trackSource/_trackLayer from useRouteLayers — each hook owns
 * its own tracked-IDs lifecycle.
 */
import { useEffect, useRef } from "react";
import { WALK_LINE_PAINT } from "./useRouteLayers.js";

function clearLayers(map, layerIds, sourceIds) {
  for (const id of layerIds.splice(0)) {
    try { map.removeLayer(id); } catch { /* already gone */ }
  }
  for (const id of sourceIds.splice(0)) {
    try { map.removeSource(id); } catch { /* already gone */ }
  }
}

function trackSource(map, id, data, sourceIds) {
  map.addSource(id, data);
  sourceIds.push(id);
}

function trackLayer(map, cfg, layerIds) {
  map.addLayer(cfg);
  layerIds.push(cfg.id);
}

export function useTransferConnectors(map, descriptors) {
  const layerIds  = useRef([]);
  const sourceIds = useRef([]);

  useEffect(() => {
    if (!map) return;

    const render = () => {
      clearLayers(map, layerIds.current, sourceIds.current);
      const connectors = (descriptors ?? []).filter(d => d.needsConnector && d.boardingCoords);
      connectors.forEach((d, i) => {
        const srcId   = `transfer-connector-${i}`;
        const layerId = `transfer-connector-line-${i}`;
        trackSource(map, srcId, {
          type: "geojson",
          data: {
            type: "Feature",
            geometry: { type: "LineString", coordinates: [d.coords, d.boardingCoords] },
          },
        }, sourceIds.current);
        trackLayer(map, {
          id:     layerId,
          type:   "line",
          source: srcId,
          paint:  WALK_LINE_PAINT,
        }, layerIds.current);
      });
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
  }, [map, descriptors]);
}
