/**
 * useFavorites hook tests (TD-FE-021).
 *
 * The underlying favorites.js module is covered by favorites.test.js. This
 * file covers the hook-layer state machine: route-save UI flow, the
 * currentRouteSaved derivation, and the route-limit timer.
 *
 * Covered:
 *  - Initialises savedLocations / savedRoutes / pinnedStops from storage
 *  - currentRouteSaved=true when a saved route matches origin/destination
 *  - currentRouteSaved=false for an unmatched pair
 *  - handleToggleSaveRoute opens the inline save panel with a default label
 *  - handleSaveRoute saves and closes the panel
 *  - handleSaveRoute trips the limit error when 10 routes are already saved
 *  - The route-limit error auto-clears after LIMIT_ERROR_DISMISS_MS
 *  - handleToggleSaveRoute on an already-saved route deletes it
 *  - handleDeleteRoute removes by id
 *  - handleUnpin removes a pinned stop
 *  - handlePinToggle pins a new stop
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

vi.mock("../constants.js", async () => {
  const actual = await vi.importActual("../constants.js");
  return { ...actual, LIMIT_ERROR_DISMISS_MS: 1000 };
});

import { useFavorites } from "../hooks/useFavorites.js";

const LOC_KEY    = "cta_saved_locations";
const ROUTE_KEY  = "cta_saved_routes";
const PINNED_KEY = "cta_pinned_stops";

function seed(key, arr) {
  localStorage.setItem(key, JSON.stringify(arr));
}

describe("useFavorites", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  it("initialises from localStorage", () => {
    seed(LOC_KEY, [{ id: "1", label: "Home", value: "1 N State" }]);
    seed(ROUTE_KEY, [{ id: "r1", label: "Commute", origin: "A", destination: "B" }]);
    seed(PINNED_KEY, [{ id: "p1", type: "train", stop_id: "40380", label: "Wilson", route_hint: "" }]);

    const { result } = renderHook(() =>
      useFavorites({ origin: "A", destination: "B" })
    );

    expect(result.current.savedLocations).toHaveLength(1);
    expect(result.current.savedRoutes).toHaveLength(1);
    expect(result.current.pinnedStops).toHaveLength(1);
  });

  it("computes currentRouteSaved=true for a matching pair", () => {
    seed(ROUTE_KEY, [{ id: "r1", label: "X", origin: "Wilson", destination: "Belmont" }]);
    const { result } = renderHook(() =>
      useFavorites({ origin: "Wilson", destination: "Belmont" })
    );
    expect(result.current.currentRouteSaved).toBe(true);
  });

  it("computes currentRouteSaved=false for an unmatched pair", () => {
    const { result } = renderHook(() =>
      useFavorites({ origin: "A", destination: "B" })
    );
    expect(result.current.currentRouteSaved).toBe(false);
  });

  it("handleToggleSaveRoute opens the save panel with a default label", () => {
    const { result } = renderHook(() =>
      useFavorites({ origin: "Wilson", destination: "Belmont" })
    );
    act(() => result.current.handleToggleSaveRoute());
    expect(result.current.savingRoute).toBe(true);
    expect(result.current.routeLabelDraft).toBe("Wilson → Belmont");
  });

  it("handleSaveRoute persists and closes the panel", () => {
    const { result } = renderHook(() =>
      useFavorites({ origin: "Wilson", destination: "Belmont" })
    );
    act(() => result.current.handleToggleSaveRoute());
    act(() => result.current.handleSaveRoute());
    expect(result.current.savingRoute).toBe(false);
    expect(result.current.savedRoutes).toHaveLength(1);
    expect(result.current.savedRoutes[0].origin).toBe("Wilson");
  });

  it("trips the limit error when 10 routes are already saved", () => {
    const ten = Array.from({ length: 10 }, (_, i) => ({
      id: `r${i}`, label: `R${i}`, origin: `O${i}`, destination: `D${i}`,
    }));
    seed(ROUTE_KEY, ten);
    const { result } = renderHook(() =>
      useFavorites({ origin: "New", destination: "Pair" })
    );
    act(() => result.current.handleToggleSaveRoute());
    act(() => result.current.handleSaveRoute());
    expect(result.current.routeLimitError).toBe(true);
    expect(result.current.savedRoutes).toHaveLength(10);
  });

  it("auto-clears the route-limit error after LIMIT_ERROR_DISMISS_MS", () => {
    const ten = Array.from({ length: 10 }, (_, i) => ({
      id: `r${i}`, label: `R${i}`, origin: `O${i}`, destination: `D${i}`,
    }));
    seed(ROUTE_KEY, ten);
    const { result } = renderHook(() =>
      useFavorites({ origin: "New", destination: "Pair" })
    );
    act(() => result.current.handleToggleSaveRoute());
    act(() => result.current.handleSaveRoute());
    expect(result.current.routeLimitError).toBe(true);

    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.routeLimitError).toBe(false);
    expect(result.current.savingRoute).toBe(false);
  });

  it("handleToggleSaveRoute on an already-saved route deletes it", () => {
    seed(ROUTE_KEY, [{ id: "r1", label: "X", origin: "Wilson", destination: "Belmont" }]);
    const { result } = renderHook(() =>
      useFavorites({ origin: "Wilson", destination: "Belmont" })
    );
    expect(result.current.currentRouteSaved).toBe(true);
    act(() => result.current.handleToggleSaveRoute());
    expect(result.current.savedRoutes).toHaveLength(0);
  });

  it("handleDeleteRoute removes by id", () => {
    seed(ROUTE_KEY, [
      { id: "r1", label: "A", origin: "X", destination: "Y" },
      { id: "r2", label: "B", origin: "P", destination: "Q" },
    ]);
    const { result } = renderHook(() =>
      useFavorites({ origin: "", destination: "" })
    );
    act(() => result.current.handleDeleteRoute("r1"));
    expect(result.current.savedRoutes).toHaveLength(1);
    expect(result.current.savedRoutes[0].id).toBe("r2");
  });

  it("handleUnpin removes a pinned stop", () => {
    seed(PINNED_KEY, [
      { id: "p1", type: "train", stop_id: "40380", label: "Wilson", route_hint: "" },
      { id: "p2", type: "bus",   stop_id: "1234",  label: "Bus",    route_hint: "22" },
    ]);
    const { result } = renderHook(() =>
      useFavorites({ origin: "", destination: "" })
    );
    act(() => result.current.handleUnpin("p1"));
    expect(result.current.pinnedStops).toHaveLength(1);
    expect(result.current.pinnedStops[0].id).toBe("p2");
  });

  it("handlePinToggle pins a new stop", () => {
    const { result } = renderHook(() =>
      useFavorites({ origin: "", destination: "" })
    );
    act(() =>
      result.current.handlePinToggle("train", "40380", "Wilson", "Red", false)
    );
    expect(result.current.pinnedStops).toHaveLength(1);
    expect(result.current.pinnedStops[0].stop_id).toBe("40380");
  });

  it("handlePinToggle on a pinned stop unpins it", () => {
    seed(PINNED_KEY, [
      { id: "p1", type: "train", stop_id: "40380", label: "Wilson", route_hint: "" },
    ]);
    const { result } = renderHook(() =>
      useFavorites({ origin: "", destination: "" })
    );
    act(() =>
      result.current.handlePinToggle("train", "40380", "Wilson", "", true)
    );
    expect(result.current.pinnedStops).toHaveLength(0);
  });
});
