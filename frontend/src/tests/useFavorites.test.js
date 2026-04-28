/**
 * Unit tests for useFavorites hook (TD-035).
 *
 * Coverage targets:
 *  - Initial state loaded from localStorage via favorites.js
 *  - handlePinToggle pins an unpinned stop
 *  - handlePinToggle unpins a pinned stop
 *  - handleToggleSaveRoute enters saving mode when route not saved
 *  - handleToggleSaveRoute removes route when already saved
 *  - handleSaveRoute commits the label and exits saving mode
 *  - handleSaveRoute at MAX_ITEMS sets routeLimitError
 *  - handleDeleteRoute removes a route from state
 *  - handleUnpin removes a stop from pinnedStops
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useFavorites } from "../hooks/useFavorites.js";

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
  vi.stubGlobal("crypto", {
    randomUUID: vi.fn().mockImplementation(() => Math.random().toString(36).slice(2)),
  });
});

function renderFavorites(origin = "Home", destination = "Work") {
  return renderHook(() => useFavorites({ origin, destination }));
}

// ---------------------------------------------------------------------------
// Pin / unpin
// ---------------------------------------------------------------------------

describe("handlePinToggle", () => {
  it("pins a stop when not currently pinned", () => {
    const { result } = renderFavorites();
    act(() => {
      result.current.handlePinToggle("train", "40380", "O'Hare", "Blue Line", false);
    });
    expect(result.current.pinnedStops).toHaveLength(1);
    expect(result.current.pinnedStops[0].stop_id).toBe("40380");
  });

  it("unpins a stop when currently pinned", () => {
    const { result } = renderFavorites();
    act(() => {
      result.current.handlePinToggle("train", "40380", "O'Hare", "Blue Line", false);
    });
    expect(result.current.pinnedStops).toHaveLength(1);
    act(() => {
      result.current.handlePinToggle("train", "40380", "O'Hare", "Blue Line", true);
    });
    expect(result.current.pinnedStops).toHaveLength(0);
  });
});

describe("handleUnpin", () => {
  it("removes the stop by id", () => {
    const { result } = renderFavorites();
    act(() => {
      result.current.handlePinToggle("bus", "1234", "Bus Stop", "22", false);
    });
    const id = result.current.pinnedStops[0].id;
    act(() => {
      result.current.handleUnpin(id);
    });
    expect(result.current.pinnedStops).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Route save / delete
// ---------------------------------------------------------------------------

describe("handleToggleSaveRoute", () => {
  it("enters saving mode when route is not saved", () => {
    const { result } = renderFavorites("Home", "Work");
    act(() => {
      result.current.handleToggleSaveRoute();
    });
    expect(result.current.savingRoute).toBe(true);
  });

  it("removes the route when it is already saved", () => {
    const { result } = renderFavorites("Home", "Work");
    act(() => result.current.handleToggleSaveRoute());
    act(() => result.current.handleSaveRoute());
    expect(result.current.savedRoutes).toHaveLength(1);
    act(() => result.current.handleToggleSaveRoute());
    expect(result.current.savedRoutes).toHaveLength(0);
  });
});

describe("handleSaveRoute", () => {
  it("saves the route and exits saving mode", () => {
    const { result } = renderFavorites("Home", "Work");
    act(() => result.current.handleToggleSaveRoute());
    act(() => result.current.handleSaveRoute());
    expect(result.current.savingRoute).toBe(false);
    expect(result.current.savedRoutes).toHaveLength(1);
    expect(result.current.savedRoutes[0].origin).toBe("Home");
    expect(result.current.savedRoutes[0].destination).toBe("Work");
  });

  it("uses routeLabelDraft when set", () => {
    const { result } = renderFavorites("Home", "Work");
    act(() => result.current.handleToggleSaveRoute());
    act(() => result.current.setRouteLabelDraft("Morning Commute"));
    act(() => result.current.handleSaveRoute());
    expect(result.current.savedRoutes[0].label).toBe("Morning Commute");
  });

  it("sets routeLimitError when MAX_ITEMS (10) is reached", async () => {
    vi.useFakeTimers();
    const { result } = renderFavorites("Home", "Work");
    for (let i = 0; i < 10; i++) {
      act(() => result.current.handleToggleSaveRoute());
      act(() => {
        result.current.setRouteLabelDraft(`Route ${i}`);
        result.current.handleSaveRoute();
      });
      // Reset saved state check by changing origin each time
    }
    // At this point savedRoutes has 1 entry (same origin/dest); repeat to exceed cap
    // Simulate a pre-filled localStorage with 10 routes
    const tenRoutes = Array.from({ length: 10 }, (_, i) => ({
      id: `id-${i}`, label: `R${i}`, origin: `o${i}`, destination: `d${i}`,
    }));
    localStorage.setItem("cta_saved_routes", JSON.stringify(tenRoutes));
    const { result: result2 } = renderFavorites("NewOrigin", "NewDest");
    act(() => result2.current.handleToggleSaveRoute());
    act(() => result2.current.handleSaveRoute());
    expect(result2.current.routeLimitError).toBe(true);
    vi.useRealTimers();
  });
});

describe("handleDeleteRoute", () => {
  it("removes the route by id", () => {
    const { result } = renderFavorites("Home", "Work");
    act(() => result.current.handleToggleSaveRoute());
    act(() => result.current.handleSaveRoute());
    const id = result.current.savedRoutes[0].id;
    act(() => result.current.handleDeleteRoute(id));
    expect(result.current.savedRoutes).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// currentRouteSaved
// ---------------------------------------------------------------------------

describe("currentRouteSaved", () => {
  it("is false when route not saved", () => {
    const { result } = renderFavorites("A", "B");
    expect(result.current.currentRouteSaved).toBe(false);
  });

  it("is true after saving", () => {
    const { result } = renderFavorites("A", "B");
    act(() => result.current.handleToggleSaveRoute());
    act(() => result.current.handleSaveRoute());
    expect(result.current.currentRouteSaved).toBe(true);
  });
});
