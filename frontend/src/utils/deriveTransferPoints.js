/**
 * Derive transfer-point descriptors from a /recommend route response.
 *
 * Pure, synchronous, no React or map references. The testable kernel of the
 * TransferMarkers feature (FEATURE_PLANS.md → Feature TransferMarkers, Chunk 1).
 *
 * Conventions:
 *  - Backend leg `from_coords` / `to_coords` are `[lat, lng]` tuples.
 *  - Returned descriptor `coords` / `boardingCoords` are `[lng, lat]` (GeoJSON /
 *    maplibre convention) so callers can pass them directly to map APIs.
 *  - `originCoords` and `destinationCoords` inputs are `[lng, lat]` to match.
 */
import { LINE_COLORS } from "../constants.js";
import { haversineMeters } from "./tripGeometry.js";

const SAME_CORNER_M = 9;        // ~30 ft — same-corner / O-D suppression radius
const ONE_BLOCK_M  = 120;       // ~one Chicago city block

function isRailLeg(leg) {
  return leg?.type === "transit" && leg.line in LINE_COLORS;
}

function isTransitLeg(leg) {
  return leg?.type === "transit";
}

function isWalkLeg(leg) {
  return leg?.type === "walk";
}

// Backend coords are [lat, lng]; descriptor coords are [lng, lat].
function flip(latLng) {
  if (!latLng) return null;
  return [latLng[1], latLng[0]];
}

function metersBetweenLngLat(a, b) {
  return haversineMeters(
    { lat: a[1], lng: a[0] },
    { lat: b[1], lng: b[0] },
  );
}

/**
 * @param {{ legs: Array<object> }} route - /recommend route shape
 * @param {{ originCoords?: number[]|null, destinationCoords?: number[]|null }} opts
 *   originCoords/destinationCoords as [lng, lat] tuples; if omitted, no O/D
 *   suppression is applied (footprints near trip endpoints will still emit).
 * @returns {Array<object>} transfer-point descriptors
 */
export function deriveTransferPoints(route, opts = {}) {
  const { originCoords = null, destinationCoords = null } = opts;
  if (!route?.legs?.length) return [];
  const legs = route.legs;
  const out = [];

  for (let i = 0; i < legs.length - 1; i++) {
    const a = legs[i];
    const b = legs[i + 1];

    if (isWalkLeg(a) && isTransitLeg(b)) {
      const coords = flip(b.from_coords);
      if (!coords) continue;
      out.push({
        type: "walk-transit",
        coords,
        boardingCoords: null,
        stationName: b.from ?? a.to ?? "",
        alightingLegIndex: null,
        boardingLegIndex: i + 1,
        needsConnector: false,
      });
      continue;
    }

    if (isTransitLeg(a) && isWalkLeg(b)) {
      const coords = flip(a.to_coords);
      if (!coords) continue;
      out.push({
        type: "transit-walk",
        coords,
        boardingCoords: null,
        stationName: a.to ?? b.from ?? "",
        alightingLegIndex: i,
        boardingLegIndex: null,
        needsConnector: false,
      });
      continue;
    }

    if (isTransitLeg(a) && isTransitLeg(b)) {
      const alight = flip(a.to_coords);
      const board  = flip(b.from_coords);
      if (!board) continue;

      const aRail = isRailLeg(a);
      const bRail = isRailLeg(b);
      const type = aRail && bRail ? "rail-rail"
                 : !aRail && !bRail ? "bus-bus"
                 : "rail-bus";

      const dist = alight ? metersBetweenLngLat(alight, board) : 0;
      const needsConnector = dist > SAME_CORNER_M && dist <= ONE_BLOCK_M;

      out.push({
        type,
        coords: alight ?? board,
        boardingCoords: needsConnector ? board : null,
        stationName: a.to ?? b.from ?? "",
        alightingLegIndex: i,
        boardingLegIndex: i + 1,
        needsConnector,
      });
    }
  }

  if (!originCoords && !destinationCoords) return out;

  return out.filter((d) => {
    if (d.type !== "walk-transit" && d.type !== "transit-walk") return true;
    if (originCoords && metersBetweenLngLat(d.coords, originCoords) <= SAME_CORNER_M) return false;
    if (destinationCoords && metersBetweenLngLat(d.coords, destinationCoords) <= SAME_CORNER_M) return false;
    return true;
  });
}
