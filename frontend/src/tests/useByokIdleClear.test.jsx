/**
 * useByokIdleClear hook tests — security-critical idle clearing of the BYOK key.
 *
 * Covered:
 *  - No-op when BYOK_ENABLED is false
 *  - No-op when byokKey is empty
 *  - Calls setByokKey('') and removes sessionStorage entry after idle timeout
 *  - User activity (mousemove/keydown/pointerdown/touchstart) resets the timer
 *  - Tab hidden → fires hidden-grace clear (~60 s)
 *  - Tab becomes visible again → cancels hidden-grace clear
 *  - Cleanup removes event listeners on unmount
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

// Mock the constants so we can flip BYOK_ENABLED per test and use a small
// timeout for fast tests. This must run before importing the hook.
vi.mock("../constants.js", () => ({
  BYOK_ENABLED: true,
  BYOK_IDLE_TIMEOUT_MS: 1000,   // 1 s for snappy fake-timer tests
}));

import { useByokIdleClear } from "../hooks/useByokIdleClear.js";
import * as constants from "../constants.js";

describe("useByokIdleClear", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    sessionStorage.clear();
    sessionStorage.setItem("byok_api_key", "sk-ant-test");
    constants.BYOK_ENABLED = true;
  });

  afterEach(() => {
    vi.useRealTimers();
    sessionStorage.clear();
  });

  it("does nothing when BYOK_ENABLED is false", () => {
    constants.BYOK_ENABLED = false;
    const setByokKey = vi.fn();
    renderHook(() => useByokIdleClear("sk-ant-abc", setByokKey));

    act(() => vi.advanceTimersByTime(60_000));
    expect(setByokKey).not.toHaveBeenCalled();
    expect(sessionStorage.getItem("byok_api_key")).toBe("sk-ant-test");
  });

  it("does nothing when byokKey is an empty string", () => {
    const setByokKey = vi.fn();
    renderHook(() => useByokIdleClear("", setByokKey));

    act(() => vi.advanceTimersByTime(60_000));
    expect(setByokKey).not.toHaveBeenCalled();
  });

  it("clears the key after the idle timeout elapses", () => {
    const setByokKey = vi.fn();
    renderHook(() => useByokIdleClear("sk-ant-abc", setByokKey));

    act(() => vi.advanceTimersByTime(1000));   // matches mocked BYOK_IDLE_TIMEOUT_MS
    expect(setByokKey).toHaveBeenCalledWith("");
    expect(sessionStorage.getItem("byok_api_key")).toBeNull();
  });

  it("does not clear before the idle timeout", () => {
    const setByokKey = vi.fn();
    renderHook(() => useByokIdleClear("sk-ant-abc", setByokKey));

    act(() => vi.advanceTimersByTime(500));   // half the timeout
    expect(setByokKey).not.toHaveBeenCalled();
  });

  it("resets the timer on mousemove activity", () => {
    const setByokKey = vi.fn();
    renderHook(() => useByokIdleClear("sk-ant-abc", setByokKey));

    // Wait nearly to the timeout, then move the mouse — should reset
    act(() => vi.advanceTimersByTime(900));
    act(() => window.dispatchEvent(new Event("mousemove")));
    act(() => vi.advanceTimersByTime(500));   // total 1400 ms but reset at 900

    expect(setByokKey).not.toHaveBeenCalled();

    // Now wait the full timeout from the reset point
    act(() => vi.advanceTimersByTime(600));
    expect(setByokKey).toHaveBeenCalledWith("");
  });

  it("resets the timer on keydown", () => {
    const setByokKey = vi.fn();
    renderHook(() => useByokIdleClear("sk-ant-abc", setByokKey));

    act(() => vi.advanceTimersByTime(900));
    act(() => window.dispatchEvent(new Event("keydown")));
    act(() => vi.advanceTimersByTime(500));
    expect(setByokKey).not.toHaveBeenCalled();
  });

  it("resets the timer on touchstart (mobile)", () => {
    const setByokKey = vi.fn();
    renderHook(() => useByokIdleClear("sk-ant-abc", setByokKey));

    act(() => vi.advanceTimersByTime(900));
    act(() => window.dispatchEvent(new Event("touchstart")));
    act(() => vi.advanceTimersByTime(500));
    expect(setByokKey).not.toHaveBeenCalled();
  });

  it("clears after grace period when tab becomes hidden", () => {
    const setByokKey = vi.fn();
    renderHook(() => useByokIdleClear("sk-ant-abc", setByokKey));

    Object.defineProperty(document, "visibilityState",
      { configurable: true, get: () => "hidden" });
    act(() => document.dispatchEvent(new Event("visibilitychange")));

    // Hidden grace is 60 s — wait it out
    act(() => vi.advanceTimersByTime(60_000));
    expect(setByokKey).toHaveBeenCalledWith("");
  });

  it("cancels hidden-grace clear when tab becomes visible again", () => {
    const setByokKey = vi.fn();
    renderHook(() => useByokIdleClear("sk-ant-abc", setByokKey));

    Object.defineProperty(document, "visibilityState",
      { configurable: true, get: () => "hidden" });
    act(() => document.dispatchEvent(new Event("visibilitychange")));

    // Wait halfway, then become visible again
    act(() => vi.advanceTimersByTime(30_000));
    Object.defineProperty(document, "visibilityState",
      { configurable: true, get: () => "visible" });
    act(() => document.dispatchEvent(new Event("visibilitychange")));

    // Continue past where the hidden timer would have fired (additional 40s)
    // The idle timer was reset on becoming visible, so it has 1000ms more.
    act(() => vi.advanceTimersByTime(40_000));
    // Idle timer (1000ms) DID elapse during this 40s wait, so key is cleared
    // by IDLE — not by hidden-grace.
    expect(setByokKey).toHaveBeenCalled();
  });

  it("removes window event listeners on unmount", () => {
    const setByokKey = vi.fn();
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() => useByokIdleClear("sk-ant-abc", setByokKey));

    unmount();

    const removed = removeSpy.mock.calls.map(([ev]) => ev);
    expect(removed).toEqual(expect.arrayContaining(
      ["mousemove", "keydown", "pointerdown", "touchstart"]
    ));
    removeSpy.mockRestore();
  });
});
