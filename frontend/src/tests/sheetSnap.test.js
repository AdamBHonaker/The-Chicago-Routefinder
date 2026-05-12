/**
 * createSheetSnapStore tests.
 *
 * Covered:
 *  - Round-trip: save then load returns the same valid index
 *  - Loads null when key absent
 *  - Loads null when stored value is out of range or unparseable
 *  - Save rejects out-of-range indices
 *  - Two stores with different keys are isolated
 *  - Survives a thrown localStorage (Safari private mode simulation)
 *  - Throws on missing storageKey
 */

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { createSheetSnapStore } from "../utils/sheetSnap.js";

describe("createSheetSnapStore", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("round-trips a valid index", () => {
    const store = createSheetSnapStore("test:snap");
    expect(store.save(2)).toBe(true);
    expect(store.load()).toBe(2);
  });

  it("returns null when no value is stored", () => {
    const store = createSheetSnapStore("test:snap");
    expect(store.load()).toBe(null);
  });

  it("returns null for out-of-range stored values", () => {
    localStorage.setItem("test:snap", "9");
    const store = createSheetSnapStore("test:snap");
    expect(store.load()).toBe(null);
  });

  it("returns null for unparseable stored values", () => {
    localStorage.setItem("test:snap", "abc");
    const store = createSheetSnapStore("test:snap");
    expect(store.load()).toBe(null);
  });

  it("rejects out-of-range indices on save", () => {
    const store = createSheetSnapStore("test:snap");
    expect(store.save(-1)).toBe(false);
    expect(store.save(99)).toBe(false);
    expect(localStorage.getItem("test:snap")).toBe(null);
  });

  it("isolates two stores by key", () => {
    const a = createSheetSnapStore("app-a:snap");
    const b = createSheetSnapStore("app-b:snap");
    a.save(0);
    b.save(2);
    expect(a.load()).toBe(0);
    expect(b.load()).toBe(2);
  });

  it("returns null when localStorage throws on get", () => {
    const original = Storage.prototype.getItem;
    Storage.prototype.getItem = () => { throw new Error("storage disabled"); };
    try {
      const store = createSheetSnapStore("test:snap");
      expect(store.load()).toBe(null);
    } finally {
      Storage.prototype.getItem = original;
    }
  });

  it("returns false when localStorage throws on set", () => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = () => { throw new Error("storage disabled"); };
    try {
      const store = createSheetSnapStore("test:snap");
      expect(store.save(1)).toBe(false);
    } finally {
      Storage.prototype.setItem = original;
    }
  });

  it("throws when storageKey is missing", () => {
    expect(() => createSheetSnapStore()).toThrow();
    expect(() => createSheetSnapStore("")).toThrow();
  });
});
