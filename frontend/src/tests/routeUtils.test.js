/**
 * Unit tests for utils/routeUtils.js — extractTransitLines.
 *
 * Coverage:
 *  - Returns empty array when given no transit legs
 *  - Walk legs filtered out
 *  - Train lines deduplicated by `line` (e.g. "Red Line")
 *  - Bus lines deduplicated by `line_code` (so direction changes count as one)
 *  - Bus vs train distinguished by BUS_DIRECTION_COLORS membership
 *  - Order preserved (first occurrence wins)
 *  - Output shape: { line, isBus, lineCode }
 */

import { describe, it, expect } from "vitest";
import { extractTransitLines } from "../utils/routeUtils.js";

const walk    = ()                          => ({ type: "walk" });
const train   = (line)                      => ({ type: "transit", line, line_code: line.split(" ")[0] });
const bus     = (direction, code)           => ({ type: "transit", line: direction, line_code: code });

describe("extractTransitLines", () => {
  it("returns an empty array when given no legs", () => {
    expect(extractTransitLines([])).toEqual([]);
  });

  it("filters out walk legs", () => {
    expect(extractTransitLines([walk(), walk()])).toEqual([]);
  });

  it("returns one entry per unique train line", () => {
    const result = extractTransitLines([train("Red Line"), train("Blue Line")]);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ line: "Red Line",  isBus: false, lineCode: "Red"  });
    expect(result[1]).toEqual({ line: "Blue Line", isBus: false, lineCode: "Blue" });
  });

  it("deduplicates the same train line that appears twice", () => {
    // Same train line on both transit legs (common when a route drops to street and reboards)
    const result = extractTransitLines([train("Red Line"), walk(), train("Red Line")]);
    expect(result).toHaveLength(1);
    expect(result[0].line).toBe("Red Line");
  });

  it("classifies bus legs by BUS_DIRECTION_COLORS membership", () => {
    // Backend sends `line: "Northbound"` for bus legs (one of Northbound/Southbound/Eastbound/Westbound)
    const result = extractTransitLines([bus("Northbound", "22")]);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ line: "Northbound", isBus: true, lineCode: "22" });
  });

  it("deduplicates bus legs by line_code, not by direction word", () => {
    // Two legs of the same #22 bus, opposite directions — must collapse to one entry
    const result = extractTransitLines([bus("Northbound", "22"), bus("Southbound", "22")]);
    expect(result).toHaveLength(1);
    expect(result[0].lineCode).toBe("22");
  });

  it("keeps two different bus routes separate even if same direction", () => {
    const result = extractTransitLines([bus("Northbound", "22"), bus("Northbound", "66")]);
    expect(result).toHaveLength(2);
    expect(result.map((r) => r.lineCode)).toEqual(["22", "66"]);
  });

  it("preserves first-occurrence order across mixed legs", () => {
    const legs = [
      walk(),
      train("Blue Line"),
      walk(),
      bus("Eastbound", "66"),
      train("Red Line"),
      train("Blue Line"),    // dup — dropped
    ];
    const result = extractTransitLines(legs);
    expect(result.map((r) => r.line)).toEqual(["Blue Line", "Eastbound", "Red Line"]);
  });
});
