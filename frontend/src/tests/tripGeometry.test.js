/**
 * Unit tests for trip geometry helpers (TD-041).
 *
 * Coverage targets:
 *  haversineMeters:
 *    - Same point → 0 m
 *    - Known distance between two Chicago intersections (~matched to OSM)
 *    - Symmetry (a→b == b→a)
 *
 *  pointToSegmentMeters:
 *    - Point at segment midpoint → ~0 m
 *    - Point at segment start → 0 m
 *    - Point perpendicular to segment
 *    - Degenerate segment (a==b) → falls back to point distance
 *    - Clamping: point beyond segment end returns distance to endpoint
 *
 *  legEndCoord:
 *    - Transit leg with to_coords
 *    - Transit leg missing to_coords → null
 *    - Walk leg with non-empty path → last point
 *    - Walk leg with empty path → null
 *
 *  distanceToPath:
 *    - Empty path → Infinity
 *    - Single-point path → haversine distance to that point
 *    - Multi-segment path: point near segment returns small distance
 *    - Off-route detection boundary: >400 m triggers flag
 */

import { describe, it, expect } from "vitest";
import {
  haversineMeters,
  pointToSegmentMeters,
  legEndCoord,
  distanceToPath,
} from "../utils/tripGeometry.js";

// ---------------------------------------------------------------------------
// haversineMeters
// ---------------------------------------------------------------------------
describe("haversineMeters", () => {
  it("returns 0 for the same point", () => {
    const p = { lat: 41.88, lng: -87.63 };
    expect(haversineMeters(p, p)).toBeCloseTo(0, 1);
  });

  it("is symmetric", () => {
    const a = { lat: 41.88, lng: -87.63 };
    const b = { lat: 41.89, lng: -87.64 };
    expect(haversineMeters(a, b)).toBeCloseTo(haversineMeters(b, a), 2);
  });

  it("returns ~111 m for 0.001° latitude difference at fixed lng", () => {
    // 1° lat ≈ 111,195 m, so 0.001° ≈ 111.2 m
    const a = { lat: 41.880, lng: -87.630 };
    const b = { lat: 41.881, lng: -87.630 };
    expect(haversineMeters(a, b)).toBeCloseTo(111.2, 0);
  });

  it("returns ~80 m for 0.001° longitude difference at Chicago latitude", () => {
    // cos(41.88°) ≈ 0.744 → 0.001° lng ≈ 82.7 m
    const a = { lat: 41.880, lng: -87.630 };
    const b = { lat: 41.880, lng: -87.629 };
    const d = haversineMeters(a, b);
    expect(d).toBeGreaterThan(70);
    expect(d).toBeLessThan(95);
  });
});

// ---------------------------------------------------------------------------
// pointToSegmentMeters
// ---------------------------------------------------------------------------
describe("pointToSegmentMeters", () => {
  const a = { lat: 41.880, lng: -87.630 };
  const b = { lat: 41.881, lng: -87.630 }; // ~111 m north of a

  it("returns ~0 for point at segment start", () => {
    expect(pointToSegmentMeters(a, a, b)).toBeCloseTo(0, 1);
  });

  it("returns ~0 for point at segment end", () => {
    expect(pointToSegmentMeters(b, a, b)).toBeCloseTo(0, 1);
  });

  it("returns ~0 for point at segment midpoint", () => {
    const mid = { lat: 41.8805, lng: -87.630 };
    expect(pointToSegmentMeters(mid, a, b)).toBeCloseTo(0, 1);
  });

  it("handles a point perpendicular to the segment (offset east by ~82 m)", () => {
    // Point displaced ~82 m east of midpoint; dist to segment should be ~82 m
    const mid = { lat: 41.8805, lng: -87.629 }; // ~0.001° east
    const dist = pointToSegmentMeters(mid, a, b);
    expect(dist).toBeGreaterThan(60);
    expect(dist).toBeLessThan(100);
  });

  it("clamps to endpoint when point is beyond segment end", () => {
    // Point 0.002° north (past end of segment)
    const beyond = { lat: 41.882, lng: -87.630 };
    const distToSeg = pointToSegmentMeters(beyond, a, b);
    const distToEnd = haversineMeters(beyond, b);
    expect(distToSeg).toBeCloseTo(distToEnd, 1);
  });

  it("falls back to point distance when segment is degenerate (a==b)", () => {
    const p = { lat: 41.8805, lng: -87.630 };
    const distToSeg = pointToSegmentMeters(p, a, a);
    const distToPoint = haversineMeters(p, a);
    expect(distToSeg).toBeCloseTo(distToPoint, 1);
  });
});

// ---------------------------------------------------------------------------
// legEndCoord
// ---------------------------------------------------------------------------
describe("legEndCoord", () => {
  it("returns to_coords for a transit leg", () => {
    const leg = { type: "transit", to_coords: [41.88, -87.63] };
    expect(legEndCoord(leg)).toEqual({ lat: 41.88, lng: -87.63 });
  });

  it("returns null for transit leg with missing to_coords", () => {
    expect(legEndCoord({ type: "transit" })).toBeNull();
    expect(legEndCoord({ type: "transit", to_coords: null })).toBeNull();
  });

  it("returns last path point for a walk leg", () => {
    const leg = {
      type: "walk",
      path: [[41.880, -87.630], [41.881, -87.629], [41.882, -87.628]],
    };
    expect(legEndCoord(leg)).toEqual({ lat: 41.882, lng: -87.628 });
  });

  it("returns null for walk leg with empty path", () => {
    expect(legEndCoord({ type: "walk", path: [] })).toBeNull();
    expect(legEndCoord({ type: "walk" })).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// distanceToPath — and off-route detection boundary
// ---------------------------------------------------------------------------
describe("distanceToPath", () => {
  it("returns Infinity for a null/empty path", () => {
    const user = { lat: 41.880, lng: -87.630 };
    expect(distanceToPath(user, null)).toBe(Infinity);
    expect(distanceToPath(user, [])).toBe(Infinity);
  });

  it("uses haversineMeters for a single-point path", () => {
    const user  = { lat: 41.881, lng: -87.630 };
    const path  = [[41.880, -87.630]];
    const d = distanceToPath(user, path);
    expect(d).toBeCloseTo(haversineMeters(user, { lat: 41.880, lng: -87.630 }), 1);
  });

  it("returns a small distance for a point on a two-segment path", () => {
    const path = [
      [41.880, -87.630],
      [41.881, -87.630],
      [41.882, -87.630],
    ];
    // Midpoint of the path — should be ~0 m from the polyline
    const user = { lat: 41.881, lng: -87.630 };
    expect(distanceToPath(user, path)).toBeCloseTo(0, 1);
  });

  it("returns a large distance for a point far from the path", () => {
    const path = [[41.880, -87.630], [41.881, -87.630]];
    // Point ~1.1 km east
    const user = { lat: 41.8805, lng: -87.620 };
    expect(distanceToPath(user, path)).toBeGreaterThan(500);
  });

  // Off-route detection boundary test (the logic in App.jsx: dist > 400 → off-route)
  it("correctly straddles the 400 m off-route threshold", () => {
    // Create a simple north-south path segment
    const path = [[41.880, -87.630], [41.890, -87.630]]; // ~1.1 km long

    // User point exactly on the path → on-route
    const onRoute = { lat: 41.885, lng: -87.630 };
    expect(distanceToPath(onRoute, path)).toBeLessThan(400);

    // User point ~830 m east of path midpoint → off-route
    // 0.01° lng at 41.885° ≈ 0.01 * cos(41.885°) * 111195 ≈ 827 m
    const offRoute = { lat: 41.885, lng: -87.620 };
    expect(distanceToPath(offRoute, path)).toBeGreaterThan(400);
  });
});
