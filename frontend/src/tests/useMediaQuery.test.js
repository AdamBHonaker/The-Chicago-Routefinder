/**
 * useMediaQuery hook tests.
 *
 * Covered:
 *  - Returns the initial match state synchronously
 *  - Re-renders when the underlying media query toggles
 *  - Cleans up the listener on unmount
 *  - Re-subscribes when the query string changes
 *  - SSR-safe (returns false when window is undefined — exercised via a
 *    matchMedia-less environment)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useMediaQuery } from "../mobile-sheet-kit/useMediaQuery.js";

function makeMatchMediaMock() {
  const listeners = new Map();
  const state = { matches: false };
  const mql = {
    get matches() { return state.matches; },
    media: "",
    addEventListener: vi.fn((event, fn) => {
      if (!listeners.has(event)) listeners.set(event, new Set());
      listeners.get(event).add(fn);
    }),
    removeEventListener: vi.fn((event, fn) => {
      listeners.get(event)?.delete(fn);
    }),
    dispatch: (event, payload) => {
      listeners.get(event)?.forEach(fn => fn(payload));
    },
  };
  const matchMedia = vi.fn(query => {
    mql.media = query;
    return mql;
  });
  return { mql, matchMedia, state };
}

describe("useMediaQuery", () => {
  let original;

  beforeEach(() => {
    original = window.matchMedia;
  });

  afterEach(() => {
    window.matchMedia = original;
  });

  it("returns the initial match state synchronously", () => {
    const { mql, matchMedia, state } = makeMatchMediaMock();
    state.matches = true;
    window.matchMedia = matchMedia;
    const { result } = renderHook(() => useMediaQuery("(max-width: 800px)"));
    expect(result.current).toBe(true);
    expect(mql.addEventListener).toHaveBeenCalledWith("change", expect.any(Function));
  });

  it("re-renders when the media query toggles", () => {
    const { mql, matchMedia, state } = makeMatchMediaMock();
    window.matchMedia = matchMedia;
    const { result } = renderHook(() => useMediaQuery("(max-width: 800px)"));
    expect(result.current).toBe(false);
    act(() => {
      state.matches = true;
      mql.dispatch("change", { matches: true });
    });
    expect(result.current).toBe(true);
  });

  it("removes the listener on unmount", () => {
    const { mql, matchMedia } = makeMatchMediaMock();
    window.matchMedia = matchMedia;
    const { unmount } = renderHook(() => useMediaQuery("(max-width: 800px)"));
    unmount();
    expect(mql.removeEventListener).toHaveBeenCalledWith("change", expect.any(Function));
  });

  it("re-subscribes when the query string changes", () => {
    const { matchMedia } = makeMatchMediaMock();
    window.matchMedia = matchMedia;
    const { rerender } = renderHook(({ q }) => useMediaQuery(q), {
      initialProps: { q: "(max-width: 800px)" },
    });
    expect(matchMedia).toHaveBeenCalledWith("(max-width: 800px)");
    rerender({ q: "(max-width: 480px)" });
    expect(matchMedia).toHaveBeenCalledWith("(max-width: 480px)");
  });

  it("returns false when matchMedia is unavailable", () => {
    delete window.matchMedia;
    const { result } = renderHook(() => useMediaQuery("(max-width: 800px)"));
    expect(result.current).toBe(false);
  });
});
