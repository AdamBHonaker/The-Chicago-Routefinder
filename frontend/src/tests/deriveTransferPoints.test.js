import { describe, it, expect } from "vitest";
import { deriveTransferPoints } from "../utils/deriveTransferPoints.js";

// Helpers — backend leg shape uses [lat, lng] coords.
const transit = (line, fromName, fromLatLng, toName, toLatLng) => ({
  type: "transit",
  line,
  line_code: line,
  from: fromName,
  to: toName,
  from_coords: fromLatLng,
  to_coords: toLatLng,
});

const walk = (fromName, fromLatLng, toName, toLatLng) => ({
  type: "walk",
  line: "walk",
  from: fromName,
  to: toName,
  path: [fromLatLng, toLatLng],
});

// Chicago-ish reference points (lat, lng).
const CLARK_LAKE = [41.8856, -87.6306];
const STATE_LAKE = [41.8857, -87.6278];          // ~240m east of Clark/Lake
const CLARK_LAKE_NEAR = [41.8857, -87.6307];     // ~15m from CLARK_LAKE — split-stop
const CLARK_LAKE_SAME = [41.88561, -87.63061];   // ~1m from CLARK_LAKE — same-corner
const ORIGIN_LATLNG = [41.8800, -87.6300];
const DEST_LATLNG   = [41.8900, -87.6300];
const ORIGIN_LNGLAT = [ORIGIN_LATLNG[1], ORIGIN_LATLNG[0]];
const DEST_LNGLAT   = [DEST_LATLNG[1],   DEST_LATLNG[0]];

describe("deriveTransferPoints", () => {
  it("returns [] for a walk-only route (no transit legs)", () => {
    const route = { legs: [walk("A", ORIGIN_LATLNG, "B", DEST_LATLNG)] };
    expect(deriveTransferPoints(route)).toEqual([]);
  });

  it("returns [] for empty / missing input", () => {
    expect(deriveTransferPoints(null)).toEqual([]);
    expect(deriveTransferPoints({})).toEqual([]);
    expect(deriveTransferPoints({ legs: [] })).toEqual([]);
  });

  it("emits walk-transit and transit-walk for walk → transit → walk", () => {
    const route = {
      legs: [
        walk("Origin", ORIGIN_LATLNG, "Clark/Lake", CLARK_LAKE),
        transit("Red Line", "Clark/Lake", CLARK_LAKE, "State/Lake", STATE_LAKE),
        walk("State/Lake", STATE_LAKE, "Dest", DEST_LATLNG),
      ],
    };
    const out = deriveTransferPoints(route);
    expect(out).toHaveLength(2);
    expect(out[0].type).toBe("walk-transit");
    expect(out[0].coords).toEqual([CLARK_LAKE[1], CLARK_LAKE[0]]);
    expect(out[0].boardingLegIndex).toBe(1);
    expect(out[1].type).toBe("transit-walk");
    expect(out[1].coords).toEqual([STATE_LAKE[1], STATE_LAKE[0]]);
    expect(out[1].alightingLegIndex).toBe(1);
  });

  it("emits rail-rail at the boarding station for two rail legs", () => {
    const route = {
      legs: [
        transit("Red Line",  "A", CLARK_LAKE, "Clark/Lake", CLARK_LAKE),
        transit("Blue Line", "Clark/Lake", CLARK_LAKE, "B", STATE_LAKE),
      ],
    };
    const [d] = deriveTransferPoints(route);
    expect(d.type).toBe("rail-rail");
    expect(d.needsConnector).toBe(false);   // same coords → 0m
    expect(d.boardingCoords).toBeNull();
    expect(d.coords).toEqual([CLARK_LAKE[1], CLARK_LAKE[0]]);
  });

  it("same-platform rail transfer (same coords) still emits a marker", () => {
    const route = {
      legs: [
        transit("Red Line",    "A", CLARK_LAKE, "Belmont", CLARK_LAKE),
        transit("Purple Line", "Belmont", CLARK_LAKE, "B", STATE_LAKE),
      ],
    };
    const out = deriveTransferPoints(route);
    expect(out).toHaveLength(1);
    expect(out[0].type).toBe("rail-rail");
  });

  it("bus-bus same-corner (<10m) emits one marker, no connector", () => {
    const route = {
      legs: [
        transit("Northbound", "A", CLARK_LAKE, "Stop1", CLARK_LAKE),
        transit("Eastbound",  "Stop2", CLARK_LAKE_SAME, "B", STATE_LAKE),
      ],
    };
    const [d] = deriveTransferPoints(route);
    expect(d.type).toBe("bus-bus");
    expect(d.needsConnector).toBe(false);
    expect(d.boardingCoords).toBeNull();
  });

  it("bus-bus split-stop (10m–120m) emits one marker plus a connector", () => {
    const route = {
      legs: [
        transit("Northbound", "A", CLARK_LAKE, "Stop1", CLARK_LAKE),
        transit("Eastbound",  "Stop2", CLARK_LAKE_NEAR, "B", STATE_LAKE),
      ],
    };
    const [d] = deriveTransferPoints(route);
    expect(d.type).toBe("bus-bus");
    expect(d.needsConnector).toBe(true);
    expect(d.boardingCoords).toEqual([CLARK_LAKE_NEAR[1], CLARK_LAKE_NEAR[0]]);
  });

  it("bus-bus far-apart (>120m) emits no connector — backend should insert WalkLeg", () => {
    const route = {
      legs: [
        transit("Northbound", "A", CLARK_LAKE, "Stop1", CLARK_LAKE),
        transit("Eastbound",  "Stop2", STATE_LAKE, "B", STATE_LAKE),
      ],
    };
    const [d] = deriveTransferPoints(route);
    expect(d.type).toBe("bus-bus");
    expect(d.needsConnector).toBe(false);
    expect(d.boardingCoords).toBeNull();
  });

  it("rail-bus mixed transfer is typed correctly", () => {
    const route = {
      legs: [
        transit("Red Line",   "A", CLARK_LAKE, "Stop1", CLARK_LAKE),
        transit("Northbound", "Stop2", CLARK_LAKE, "B", STATE_LAKE),
      ],
    };
    const [d] = deriveTransferPoints(route);
    expect(d.type).toBe("rail-bus");
  });

  it("O/D suppression: footprints within 9m of origin/destination are filtered", () => {
    const route = {
      legs: [
        walk("Origin", ORIGIN_LATLNG, "Stop", ORIGIN_LATLNG),
        transit("Red Line", "Stop", ORIGIN_LATLNG, "End", DEST_LATLNG),
        walk("End", DEST_LATLNG, "Dest", DEST_LATLNG),
      ],
    };
    const out = deriveTransferPoints(route, {
      originCoords: ORIGIN_LNGLAT,
      destinationCoords: DEST_LNGLAT,
    });
    expect(out).toEqual([]);
  });

  it("O/D suppression boundary: 9m from origin is suppressed; 15m is retained", () => {
    // 0.0001° lat ≈ 11.1m; 0.00007° ≈ 7.8m; 0.00014° ≈ 15.6m.
    const NEAR = [ORIGIN_LATLNG[0] + 0.00007, ORIGIN_LATLNG[1]];   // ~7.8m
    const FAR  = [ORIGIN_LATLNG[0] + 0.00014, ORIGIN_LATLNG[1]];   // ~15.6m
    const mk = (boardLatLng) => ({
      legs: [
        walk("Origin", ORIGIN_LATLNG, "Stop", boardLatLng),
        transit("Red Line", "Stop", boardLatLng, "End", DEST_LATLNG),
        walk("End", DEST_LATLNG, "Dest", DEST_LATLNG),
      ],
    });
    const opts = { originCoords: ORIGIN_LNGLAT, destinationCoords: DEST_LNGLAT };

    const nearOut = deriveTransferPoints(mk(NEAR), opts);
    expect(nearOut.find(d => d.type === "walk-transit")).toBeUndefined();

    const farOut = deriveTransferPoints(mk(FAR), opts);
    expect(farOut.find(d => d.type === "walk-transit")).toBeDefined();
  });

  it("mid-trip footprints (between two transit legs separated by a walk) are not suppressed", () => {
    const MID = [41.8870, -87.6300];
    const route = {
      legs: [
        walk("Origin", ORIGIN_LATLNG, "Stop1", ORIGIN_LATLNG),
        transit("Red Line", "Stop1", ORIGIN_LATLNG, "Stop2", MID),
        walk("Stop2", MID, "Stop3", MID),
        transit("Blue Line", "Stop3", MID, "Stop4", DEST_LATLNG),
        walk("Stop4", DEST_LATLNG, "Dest", DEST_LATLNG),
      ],
    };
    const out = deriveTransferPoints(route, {
      originCoords: ORIGIN_LNGLAT,
      destinationCoords: DEST_LNGLAT,
    });
    // O/D footprints suppressed; the mid-trip transit-walk + walk-transit pair survives.
    expect(out.map(d => d.type).sort()).toEqual(["transit-walk", "walk-transit"]);
  });

  it("does not mutate its input", () => {
    const route = {
      legs: [
        walk("Origin", ORIGIN_LATLNG, "Clark/Lake", CLARK_LAKE),
        transit("Red Line", "Clark/Lake", CLARK_LAKE, "State/Lake", STATE_LAKE),
        walk("State/Lake", STATE_LAKE, "Dest", DEST_LATLNG),
      ],
    };
    const snapshot = JSON.parse(JSON.stringify(route));
    deriveTransferPoints(route, {
      originCoords: ORIGIN_LNGLAT,
      destinationCoords: DEST_LNGLAT,
    });
    expect(route).toEqual(snapshot);
  });
});
