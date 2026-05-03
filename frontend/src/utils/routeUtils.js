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
  const seen = new Set();
  return legs
    .filter((l) => l.type === "transit")
    .filter((l) => {
      const isBus = l.line in BUS_DIRECTION_COLORS;
      const key = isBus ? `bus:${l.line_code}` : l.line;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((l) => ({
      line: l.line,
      isBus: l.line in BUS_DIRECTION_COLORS,
      lineCode: l.line_code,
    }));
}
