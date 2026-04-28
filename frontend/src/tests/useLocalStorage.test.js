/**
 * Unit tests for useLocalStorage hook (TD-039).
 *
 * Coverage targets:
 *  - Returns defaultValue when key is absent
 *  - Returns stored value on subsequent renders
 *  - setValue persists to localStorage
 *  - setValue accepts a function (updater pattern)
 *  - setValue(null) removes the key
 *  - Corrupted JSON in localStorage falls back to defaultValue
 *  - Silent storage failure does not throw (quota / private browsing)
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLocalStorage } from "../hooks/useLocalStorage.js";

// ---------------------------------------------------------------------------
// localStorage mock
// ---------------------------------------------------------------------------
beforeEach(() => {
  const store = {};
  vi.stubGlobal("localStorage", {
    getItem:    (k) => (k in store ? store[k] : null),
    setItem:    (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
    clear:      () => { Object.keys(store).forEach(k => delete store[k]); },
  });
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useLocalStorage", () => {
  it("returns defaultValue when key is absent", () => {
    const { result } = renderHook(() => useLocalStorage("test_key", "default"));
    expect(result.current[0]).toBe("default");
  });

  it("returns stored JSON value when key exists", () => {
    localStorage.setItem("test_key", JSON.stringify(42));
    const { result } = renderHook(() => useLocalStorage("test_key", 0));
    expect(result.current[0]).toBe(42);
  });

  it("setValue stores the value and updates state", () => {
    const { result } = renderHook(() => useLocalStorage("test_key", "initial"));
    act(() => result.current[1]("updated"));
    expect(result.current[0]).toBe("updated");
    expect(JSON.parse(localStorage.getItem("test_key"))).toBe("updated");
  });

  it("setValue accepts an updater function", () => {
    const { result } = renderHook(() => useLocalStorage("counter", 0));
    act(() => result.current[1](n => n + 1));
    expect(result.current[0]).toBe(1);
    act(() => result.current[1](n => n + 1));
    expect(result.current[0]).toBe(2);
  });

  it("setValue(null) removes the key from localStorage", () => {
    localStorage.setItem("test_key", JSON.stringify("hello"));
    const { result } = renderHook(() => useLocalStorage("test_key", "default"));
    act(() => result.current[1](null));
    expect(localStorage.getItem("test_key")).toBeNull();
  });

  it("returns defaultValue when stored JSON is corrupted", () => {
    localStorage.setItem("test_key", "not-valid-json{{");
    const { result } = renderHook(() => useLocalStorage("test_key", "fallback"));
    expect(result.current[0]).toBe("fallback");
  });

  it("does not throw when localStorage.setItem throws (quota exceeded)", () => {
    vi.stubGlobal("localStorage", {
      getItem:    () => null,
      setItem:    () => { throw new Error("QuotaExceededError"); },
      removeItem: () => {},
    });
    const { result } = renderHook(() => useLocalStorage("test_key", 0));
    expect(() => act(() => result.current[1](99))).not.toThrow();
    // State updates in memory despite storage failure
    expect(result.current[0]).toBe(99);
  });

  it("persists objects (not just primitives)", () => {
    const { result } = renderHook(() => useLocalStorage("obj_key", {}));
    act(() => result.current[1]({ foo: "bar", count: 3 }));
    expect(result.current[0]).toEqual({ foo: "bar", count: 3 });
    expect(JSON.parse(localStorage.getItem("obj_key"))).toEqual({ foo: "bar", count: 3 });
  });
});
