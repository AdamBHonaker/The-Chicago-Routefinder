import { BUS_DIRECTION_COLORS } from "../constants.js";

/**
 * Returns a deduplicated array of transit legs from a route's legs array,
 * structured for pill display. Bus routes are keyed by line_code; train lines
 * by line name — so the same service doesn't appear twice when a route boards
 * at the same line mid-journey.
 *
 * @param {Array} legs - Route legs from the /recommend API response
 * @returns {{ line: string, isBus: boolean, lineCode: string }[]}
 */
export function extractTransitLines(legs) {
  // Single-pass dedup so isBus is computed once per leg and we touch the
  // legs array once instead of three times (OPT-FE-206).
  const seen = new Set();
  const out = [];
  for (let i = 0; i < legs.length; i++) {
    const l = legs[i];
    if (l.type !== "transit") continue;
    const isBus = l.line in BUS_DIRECTION_COLORS;
    const key = isBus ? `bus:${l.line_code}` : l.line;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ line: l.line, isBus, lineCode: l.line_code });
  }
  return out;
}
