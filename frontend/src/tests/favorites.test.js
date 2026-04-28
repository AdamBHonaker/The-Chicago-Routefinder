/**
 * Unit tests for favorites.js persistence functions (TD-042).
 *
 * Coverage targets:
 *  saveLocation / getSavedLocations:
 *    - save/load round-trip
 *    - MAX_ITEMS cap (returns null when at limit)
 *    - Duplicate values are NOT prevented at the location level (labels differ)
 *
 *  deleteLocation:
 *    - Removes correct item by id, leaves others intact
 *
 *  saveRoute / getSavedRoutes:
 *    - save/load round-trip
 *    - MAX_ITEMS cap
 *
 *  deleteRoute:
 *    - Removes correct item by id
 *
 *  pinStop / getPinnedStops / unpinStop:
 *    - Pin a stop and retrieve it
 *    - Duplicate stop_id is silently ignored (returns existing array, not null)
 *    - MAX_ITEMS cap (returns null when at limit)
 *    - unpinStop removes correct entry
 *
 *  Error recovery:
 *    - Corrupted JSON in localStorage falls back to empty array
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  getSavedLocations, saveLocation, deleteLocation,
  getSavedRoutes,   saveRoute,   deleteRoute,
  getPinnedStops,   pinStop,     unpinStop,
} from "../favorites.js";

// ---------------------------------------------------------------------------
// localStorage mock
// ---------------------------------------------------------------------------
beforeEach(() => {
  // Reset to a clean in-memory localStorage before each test.
  const store = {};
  vi.stubGlobal("localStorage", {
    getItem:    (k) => (k in store ? store[k] : null),
    setItem:    (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
    clear:      () => { Object.keys(store).forEach(k => delete store[k]); },
  });
  // crypto.randomUUID is used to generate IDs
  vi.stubGlobal("crypto", { randomUUID: vi.fn().mockImplementation(() =>
    Math.random().toString(36).slice(2)
  )});
});

// ---------------------------------------------------------------------------
// getSavedLocations / saveLocation / deleteLocation
// ---------------------------------------------------------------------------
describe("getSavedLocations", () => {
  it("returns empty array when localStorage is empty", () => {
    expect(getSavedLocations()).toEqual([]);
  });

  it("returns empty array when stored JSON is corrupted", () => {
    localStorage.setItem("cta_saved_locations", "not-valid-json{{");
    expect(getSavedLocations()).toEqual([]);
  });
});

describe("saveLocation", () => {
  it("saves a location and returns the updated array", () => {
    const result = saveLocation("Home", "123 Main St", []);
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({ label: "Home", value: "123 Main St" });
  });

  it("persists so getSavedLocations reads it back", () => {
    const saved = saveLocation("Work", "456 Loop Plaza", []);
    expect(getSavedLocations()).toEqual(saved);
  });

  it("returns null when the MAX_ITEMS cap (10) is already reached", () => {
    let current = [];
    for (let i = 0; i < 10; i++) {
      current = saveLocation(`Place ${i}`, `addr ${i}`, current);
    }
    expect(current).toHaveLength(10);
    const overflow = saveLocation("Extra", "overflow addr", current);
    expect(overflow).toBeNull();
  });

  it("allows saving at exactly MAX_ITEMS - 1 (9 items)", () => {
    let current = [];
    for (let i = 0; i < 9; i++) current = saveLocation(`P${i}`, `a${i}`, current);
    const result = saveLocation("Tenth", "tenth addr", current);
    expect(result).toHaveLength(10);
    expect(result).not.toBeNull();
  });
});

describe("deleteLocation", () => {
  it("removes the matching id and keeps others", () => {
    let current = saveLocation("Home", "123 Main", []);
    current = saveLocation("Work", "456 Loop", current);
    const idToDelete = current[0].id;
    const next = deleteLocation(idToDelete, current);
    expect(next).toHaveLength(1);
    expect(next[0].label).toBe("Work");
  });

  it("persists the deletion", () => {
    let current = saveLocation("Home", "123 Main", []);
    const id = current[0].id;
    deleteLocation(id, current);
    expect(getSavedLocations()).toEqual([]);
  });

  it("is a no-op when the id does not exist", () => {
    let current = saveLocation("Home", "123 Main", []);
    const next = deleteLocation("non-existent-id", current);
    expect(next).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// getSavedRoutes / saveRoute / deleteRoute
// ---------------------------------------------------------------------------
describe("saveRoute", () => {
  it("saves a route and returns the updated array", () => {
    const result = saveRoute("Home → Work", "Home", "Work", []);
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({ label: "Home → Work", origin: "Home", destination: "Work" });
  });

  it("persists so getSavedRoutes reads it back", () => {
    const saved = saveRoute("Route A", "A", "B", []);
    expect(getSavedRoutes()).toEqual(saved);
  });

  it("returns null when MAX_ITEMS is reached", () => {
    let current = [];
    for (let i = 0; i < 10; i++) current = saveRoute(`R${i}`, `o${i}`, `d${i}`, current);
    expect(saveRoute("Extra", "oE", "dE", current)).toBeNull();
  });
});

describe("deleteRoute", () => {
  it("removes the matching route by id", () => {
    let current = saveRoute("A → B", "A", "B", []);
    current = saveRoute("C → D", "C", "D", current);
    const idToDelete = current[0].id;
    const next = deleteRoute(idToDelete, current);
    expect(next).toHaveLength(1);
    expect(next[0].origin).toBe("C");
  });
});

// ---------------------------------------------------------------------------
// getPinnedStops / pinStop / unpinStop / isStopPinned
// ---------------------------------------------------------------------------
describe("getPinnedStops", () => {
  it("returns empty array when nothing is pinned", () => {
    expect(getPinnedStops()).toEqual([]);
  });
});

describe("pinStop", () => {
  it("pins a stop and returns the updated array", () => {
    const result = pinStop("train", "40380", "O'Hare", "Blue Line", []);
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({ type: "train", stop_id: "40380", label: "O'Hare" });
  });

  it("persists so getPinnedStops reads it back", () => {
    const pinned = pinStop("train", "40380", "O'Hare", "Blue Line", []);
    expect(getPinnedStops()).toEqual(pinned);
  });

  it("silently skips duplicate stop_id (returns existing array unchanged)", () => {
    let current = pinStop("train", "40380", "O'Hare", "Blue Line", []);
    const again = pinStop("train", "40380", "O'Hare", "Blue Line", current);
    // Returns the existing array reference, not null
    expect(again).toBe(current);
    expect(again).toHaveLength(1);
  });

  it("returns null when MAX_ITEMS is reached", () => {
    let current = [];
    for (let i = 0; i < 10; i++) {
      current = pinStop("bus", `stop_${i}`, `Stop ${i}`, "79", current);
    }
    expect(current).toHaveLength(10);
    const overflow = pinStop("bus", "stop_overflow", "Overflow", "79", current);
    expect(overflow).toBeNull();
  });
});

describe("unpinStop", () => {
  it("removes the matching stop by id", () => {
    let current = pinStop("train", "40380", "O'Hare", "Blue Line", []);
    current = pinStop("train", "40900", "Clark/Lake", "Blue Line", current);
    const idToRemove = current[0].id;
    const next = unpinStop(idToRemove, current);
    expect(next).toHaveLength(1);
    expect(next[0].stop_id).toBe("40900");
  });

  it("persists the unpin", () => {
    let current = pinStop("train", "40380", "O'Hare", "Blue Line", []);
    const id = current[0].id;
    unpinStop(id, current);
    expect(getPinnedStops()).toEqual([]);
  });
});

