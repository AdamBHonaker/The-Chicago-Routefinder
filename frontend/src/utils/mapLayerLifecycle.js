/**
 * Shared MapLibre source/layer lifecycle helpers (TD-FE-020).
 *
 * Used by `useRouteLayers` (route polylines + stop circles) and
 * `useTransferConnectors` (dashed split-stop connectors). Each consumer hook
 * owns its own tracked-IDs refs and passes them in — these helpers are pure
 * lifecycle plumbing with no shared state of their own.
 *
 * `clearLayers` swallows missing-layer/missing-source errors so it tolerates:
 *   • style reloads (which detach all layers)
 *   • partial inits (style not loaded when render() ran)
 *   • duplicate teardown calls (StrictMode, abort during transition)
 */

export function clearLayers(map, layerIds, sourceIds) {
  for (const id of layerIds.splice(0)) {
    try { map.removeLayer(id); } catch { /* already gone */ }
  }
  for (const id of sourceIds.splice(0)) {
    try { map.removeSource(id); } catch { /* already gone */ }
  }
}

export function trackSource(map, id, data, sourceIds) {
  map.addSource(id, data);
  sourceIds.push(id);
}

export function trackLayer(map, cfg, layerIds) {
  map.addLayer(cfg);
  layerIds.push(cfg.id);
}
