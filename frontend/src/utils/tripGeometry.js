/**
 * Trip geometry helpers — pure math functions used by the GPS tracking effect (TD-041).
 *
 * Extracted from App.jsx so they can be independently unit-tested without mounting
 * the full React component tree. These functions have no dependency on state or props.
 */

/**
 * Haversine great-circle distance between two lat/lng points (in metres).
 * @param {{ lat: number, lng: number }} a
 * @param {{ lat: number, lng: number }} b
 * @returns {number}
 */
export function haversineMeters(a, b) {
  const R = 6371000;
  const dLat = (b.lat - a.lat) * Math.PI / 180;
  const dLng = (b.lng - a.lng) * Math.PI / 180;
  const lat1r = a.lat * Math.PI / 180;
  const lat2r = b.lat * Math.PI / 180;
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(lat1r) * Math.cos(lat2r) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
}

/**
 * Minimum distance (metres) from point p to line segment a–b, using a flat-earth
 * approximation centred at the segment midpoint latitude. Accurate to <1 % error
 * over the distances relevant to Chicago city blocks (~100–500 m).
 * @param {{ lat: number, lng: number }} p
 * @param {{ lat: number, lng: number }} a  segment start
 * @param {{ lat: number, lng: number }} b  segment end
 * @returns {number}
 */
export function pointToSegmentMeters(p, a, b) {
  const toRad = x => x * Math.PI / 180;
  const cosLat = Math.cos(toRad((a.lat + b.lat) / 2));
  const scale = 6371000 * Math.PI / 180;
  const px = (p.lng - a.lng) * cosLat * scale;
  const py = (p.lat - a.lat) * scale;
  const dx = (b.lng - a.lng) * cosLat * scale;
  const dy = (b.lat - a.lat) * scale;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) return Math.sqrt(px * px + py * py);
  const t = Math.max(0, Math.min(1, (px * dx + py * dy) / lenSq));
  return Math.sqrt((px - t * dx) ** 2 + (py - t * dy) ** 2);
}

/**
 * Returns the endpoint coordinate of a route leg.
 * For transit legs: `to_coords` field ([lat, lng] tuple).
 * For walk legs: last point of the `path` polyline.
 * Returns null if the leg has no usable geometry.
 * @param {{ type: string, to_coords?: number[], path?: number[][] }} leg
 * @returns {{ lat: number, lng: number } | null}
 */
export function legEndCoord(leg) {
  if (leg.type === "transit") {
    const c = leg.to_coords;
    if (!c) return null;
    return { lat: c[0], lng: c[1] };
  }
  const path = leg.path;
  if (!path?.length) return null;
  const last = path[path.length - 1];
  return { lat: last[0], lng: last[1] };
}

/**
 * Compute the minimum perpendicular distance (metres) from a user position
 * to a walk leg's path polyline. Used for off-route detection.
 *
 * Returns Infinity when the path is absent or has no segments (single point
 * paths fall back to haversineMeters to the sole waypoint).
 *
 * @param {{ lat: number, lng: number }} userPosition
 * @param {number[][]} path  Array of [lat, lng] pairs
 * @returns {number}
 */
export function distanceToPath(userPosition, path) {
  if (!path?.length) return Infinity;
  if (path.length === 1) {
    return haversineMeters(userPosition, { lat: path[0][0], lng: path[0][1] });
  }
  let minDist = Infinity;
  for (let i = 0; i < path.length - 1; i++) {
    const a = { lat: path[i][0],     lng: path[i][1] };
    const b = { lat: path[i + 1][0], lng: path[i + 1][1] };
    minDist = Math.min(minDist, pointToSegmentMeters(userPosition, a, b));
  }
  return minDist;
}

/**
 * Pure trip-position computation — no React state or refs.
 * Calculates what state changes should result from a GPS position update and
 * returns them as plain values; the caller (App.jsx) applies them to state/refs.
 *
 * @param {{ lat: number, lng: number }} pos  Current GPS position
 * @param {object[]} legs  Route legs array
 * @param {object} ctx
 * @param {number}   ctx.currentLegIdx          Active leg index (from ref)
 * @param {boolean}  ctx.onVehicle              User confirmed on a transit vehicle
 * @param {number}   ctx.suppressRerouteUntilMs Epoch ms until reroute suppressed
 * @param {Set<string>} ctx.completedSteps      Current completed walk-step keys
 * @param {number}   ctx.legAdvanceRadius        Proximity to advance leg (m)
 * @param {number}   ctx.legAdvanceRadiusVehicle Wider proximity when on vehicle (m)
 * @param {number}   ctx.walkStepProximity       Proximity to mark step complete (m)
 * @param {number}   ctx.offRouteThreshold       Distance to flag off-route (m)
 * @param {number}  [ctx.nowMs]                  Current time (injectable for tests)
 * @returns {{
 *   nextLegIdx: number | null,
 *   clearOffRoute: boolean,
 *   addedStepKeys: string[],
 *   isOffRoute: boolean | null,
 * }}
 */
export function computeTripPositionUpdates(pos, legs, {
  currentLegIdx,
  onVehicle,
  suppressRerouteUntilMs,
  completedSteps,
  legAdvanceRadius,
  legAdvanceRadiusVehicle,
  walkStepProximity,
  offRouteThreshold,
  nowMs = Date.now(),
}) {
  let idx = currentLegIdx ?? 0;
  let nextLegIdx = null;
  let clearOffRoute = false;

  // 1. Leg advancement: advance when within proximity of the current leg's endpoint.
  const leg = legs[idx];
  if (leg) {
    const end = legEndCoord(leg);
    const radius = (onVehicle && leg.type === "transit") ? legAdvanceRadiusVehicle : legAdvanceRadius;
    if (end && haversineMeters(pos, end) < radius) {
      const next = Math.min(idx + 1, legs.length - 1);
      if (next !== idx) {
        nextLegIdx = next;
        idx = next;
        if (legs[next]?.type !== "walk") clearOffRoute = true;
      }
    }
  }

  // 2. Walk-step completion: mark steps complete when within proximity of their start.
  const activeLeg = legs[idx];
  const addedStepKeys = [];
  if (activeLeg?.type === "walk" && activeLeg.directions?.length) {
    activeLeg.directions.forEach((step, si) => {
      const key = `${idx}-${si}`;
      if (
        step.start_lat !== undefined &&
        step.start_lon !== undefined &&
        !completedSteps.has(key) &&
        haversineMeters(pos, { lat: step.start_lat, lng: step.start_lon }) < walkStepProximity
      ) {
        addedStepKeys.push(key);
      }
    });
  }

  // 3. Off-route detection: only during walk legs and outside suppression window.
  let isOffRoute = null;
  if (activeLeg?.type === "walk" && nowMs > suppressRerouteUntilMs) {
    isOffRoute = distanceToPath(pos, activeLeg.path) > offRouteThreshold;
  }

  return { nextLegIdx, clearOffRoute, addedStepKeys, isOffRoute };
}
