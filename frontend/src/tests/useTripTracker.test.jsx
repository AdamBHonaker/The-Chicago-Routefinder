import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTripTracker } from "../hooks/useTripTracker.js";
import { TRIP_STATE_KEY, TRIP_TTL_MS } from "../utils/tripPersistence.js";

// Two-leg fixture: walk from origin to a transit board point, then a single
// transit leg to the destination. Coordinates are real Chicago lat/lng so
// haversine distances match production behaviour.
const WALK_BOARD = { lat: 41.881832, lng: -87.623177 }; // The Bean
const TRANSIT_DEST = { lat: 41.879500, lng: -87.629800 };

const TWO_LEG_RESULT = {
  routes: [
    {
      legs: [
        {
          type: "walk",
          path: [
            [41.881100, -87.622500],
            [WALK_BOARD.lat, WALK_BOARD.lng],
          ],
          directions: [{ blocks: 1 }],
        },
        {
          type: "transit",
          line: "Red Line",
          path: [
            [WALK_BOARD.lat, WALK_BOARD.lng],
            [TRANSIT_DEST.lat, TRANSIT_DEST.lng],
          ],
        },
      ],
    },
  ],
};

let watchCallbacks;

function fakeGeolocation() {
  watchCallbacks = { success: null, error: null, options: null, cleared: false };
  return {
    watchPosition: (success, error, options) => {
      watchCallbacks.success = success;
      watchCallbacks.error = error;
      watchCallbacks.options = options;
      return 42;
    },
    clearWatch: (id) => {
      if (id === 42) watchCallbacks.cleared = true;
    },
  };
}

function emitPosition({ lat, lng, heading = null }) {
  act(() => {
    watchCallbacks.success({
      coords: { latitude: lat, longitude: lng, heading },
    });
  });
}

beforeEach(() => {
  Object.defineProperty(globalThis.navigator, "geolocation", {
    configurable: true,
    value: fakeGeolocation(),
  });
  localStorage.removeItem(TRIP_STATE_KEY);
});

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.removeItem(TRIP_STATE_KEY);
});

describe("useTripTracker", () => {
  it("starts with all flags off and no watch registered", () => {
    const { result } = renderHook(() =>
      useTripTracker({ result: TWO_LEG_RESULT, selectedRouteIndex: 0 })
    );
    expect(result.current.tripActive).toBe(false);
    expect(result.current.userPosition).toBe(null);
    expect(result.current.activeLegIndex).toBe(null);
    expect(result.current.completedSteps.size).toBe(0);
    expect(watchCallbacks.success).toBe(null);
  });

  it("startTrip subscribes to geolocation and seeds active leg 0", () => {
    const { result } = renderHook(() =>
      useTripTracker({ result: TWO_LEG_RESULT, selectedRouteIndex: 0 })
    );
    act(() => result.current.startTrip());
    expect(result.current.tripActive).toBe(true);
    expect(result.current.activeLegIndex).toBe(0);
    expect(watchCallbacks.success).toBeTypeOf("function");
  });

  it("stopTrip clears the watch and resets tracker state", () => {
    const { result } = renderHook(() =>
      useTripTracker({ result: TWO_LEG_RESULT, selectedRouteIndex: 0 })
    );
    act(() => result.current.startTrip());
    emitPosition({ lat: 41.881100, lng: -87.622500 });
    expect(result.current.userPosition).toMatchObject({ lat: 41.881100, lng: -87.622500 });

    act(() => result.current.stopTrip());
    expect(result.current.tripActive).toBe(false);
    expect(result.current.userPosition).toBe(null);
    expect(result.current.activeLegIndex).toBe(null);
    expect(watchCallbacks.cleared).toBe(true);
  });

  it("advances active leg when the user reaches a leg endpoint", () => {
    const { result } = renderHook(() =>
      useTripTracker({ result: TWO_LEG_RESULT, selectedRouteIndex: 0 })
    );
    act(() => result.current.startTrip());

    // Stand at the boarding point — walk leg endpoint, within LEG_ADVANCE_RADIUS_M.
    emitPosition(WALK_BOARD);
    expect(result.current.activeLegIndex).toBe(1);
  });

  it("flags off-route when the user is far from every walk segment", () => {
    const { result } = renderHook(() =>
      useTripTracker({ result: TWO_LEG_RESULT, selectedRouteIndex: 0 })
    );
    act(() => result.current.startTrip());
    emitPosition({ lat: 41.851, lng: -87.700 }); // ~6 km off, well past 400 m
    expect(result.current.isOffRoute).toBe(true);
  });

  it("dismissOffRoute suppresses re-trigger for the suppression window", () => {
    const { result } = renderHook(() =>
      useTripTracker({ result: TWO_LEG_RESULT, selectedRouteIndex: 0 })
    );
    act(() => result.current.startTrip());
    emitPosition({ lat: 41.851, lng: -87.700 });
    expect(result.current.isOffRoute).toBe(true);

    act(() => result.current.dismissOffRoute());
    expect(result.current.isOffRoute).toBe(false);

    // Subsequent off-route position should remain suppressed (no re-trigger).
    emitPosition({ lat: 41.852, lng: -87.701 });
    expect(result.current.isOffRoute).toBe(false);
  });

  it("on-vehicle confirmation toggles and resets when the leg changes", () => {
    const { result } = renderHook(() =>
      useTripTracker({ result: TWO_LEG_RESULT, selectedRouteIndex: 0 })
    );
    act(() => result.current.startTrip());

    act(() => result.current.toggleOnVehicle());
    expect(result.current.onVehicle).toBe(true);

    // Force a leg change via a position at the leg endpoint.
    emitPosition(WALK_BOARD);
    expect(result.current.activeLegIndex).toBe(1);
    expect(result.current.onVehicle).toBe(false);
  });

  it("treats PERMISSION_DENIED as a fatal error and stops the trip", () => {
    const { result } = renderHook(() =>
      useTripTracker({ result: TWO_LEG_RESULT, selectedRouteIndex: 0 })
    );
    // Silence the diagnostic console.error the hook emits on geolocation failure.
    vi.spyOn(console, "error").mockImplementation(() => {});
    act(() => result.current.startTrip());

    act(() => {
      watchCallbacks.error({ code: 1, PERMISSION_DENIED: 1 });
    });
    // stopTrip() runs synchronously after the error path and unsubscribes the watch.
    expect(result.current.tripActive).toBe(false);
    expect(watchCallbacks.cleared).toBe(true);
  });

  it("persists trip state to localStorage while active and clears on stop", () => {
    const { result } = renderHook(() =>
      useTripTracker({ result: TWO_LEG_RESULT, selectedRouteIndex: 0 })
    );
    expect(localStorage.getItem(TRIP_STATE_KEY)).toBe(null);

    act(() => result.current.startTrip());
    const saved = JSON.parse(localStorage.getItem(TRIP_STATE_KEY));
    expect(saved.tripActive).toBe(true);
    expect(saved.activeLegIndex).toBe(0);
    expect(saved.savedAt).toBeTypeOf("number");

    // Advancing the leg should update the persisted blob.
    emitPosition(WALK_BOARD);
    const savedAfter = JSON.parse(localStorage.getItem(TRIP_STATE_KEY));
    expect(savedAfter.activeLegIndex).toBe(1);

    act(() => result.current.stopTrip());
    expect(localStorage.getItem(TRIP_STATE_KEY)).toBe(null);
  });

  it("rehydrates an in-progress trip from a fresh persisted blob and re-attaches the watch", () => {
    localStorage.setItem(TRIP_STATE_KEY, JSON.stringify({
      tripActive: true,
      activeLegIndex: 1,
      completedSteps: ["leg0:step0"],
      onVehicle: true,
      savedAt: Date.now() - 60_000, // 1 minute ago — well within TTL
    }));

    const { result } = renderHook(() =>
      useTripTracker({ result: TWO_LEG_RESULT, selectedRouteIndex: 0 })
    );
    expect(result.current.tripActive).toBe(true);
    expect(result.current.activeLegIndex).toBe(1);
    expect(result.current.completedSteps.has("leg0:step0")).toBe(true);
    // Watch effect attached on mount without an explicit startTrip call.
    expect(watchCallbacks.success).toBeTypeOf("function");
  });

  it("ignores a stale persisted blob older than the TTL", () => {
    localStorage.setItem(TRIP_STATE_KEY, JSON.stringify({
      tripActive: true,
      activeLegIndex: 1,
      completedSteps: [],
      onVehicle: false,
      savedAt: Date.now() - (TRIP_TTL_MS + 60_000),
    }));

    const { result } = renderHook(() =>
      useTripTracker({ result: TWO_LEG_RESULT, selectedRouteIndex: 0 })
    );
    expect(result.current.tripActive).toBe(false);
    expect(result.current.activeLegIndex).toBe(null);
    // Stale blob is removed by the loader on first read.
    expect(localStorage.getItem(TRIP_STATE_KEY)).toBe(null);
  });

  it("does not stop the trip on a non-permission GPS error", () => {
    const { result } = renderHook(() =>
      useTripTracker({ result: TWO_LEG_RESULT, selectedRouteIndex: 0 })
    );
    vi.spyOn(console, "error").mockImplementation(() => {});
    act(() => result.current.startTrip());

    act(() => {
      watchCallbacks.error({ code: 2, PERMISSION_DENIED: 1 }); // POSITION_UNAVAILABLE
    });
    expect(result.current.tripActive).toBe(true);
    expect(watchCallbacks.cleared).toBe(false);
  });
});
