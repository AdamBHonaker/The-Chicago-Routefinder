import { useState, useRef, useEffect, useCallback } from "react";
import {
  TRIP_GEO_OPTIONS,
  OFF_ROUTE_THRESHOLD_METERS,
  REROUTE_SUPPRESSION_MS,
  LEG_ADVANCE_RADIUS_M,
  LEG_ADVANCE_RADIUS_VEHICLE_M,
  WALK_STEP_PROXIMITY_M,
} from "../constants.js";
import { computeTripPositionUpdates } from "../utils/tripGeometry.js";
import {
  TRIP_STATE_KEY,
  loadPersistedTrip,
  savePersistedTrip,
  clearPersistedTrip,
} from "../utils/tripPersistence.js";

/**
 * Encapsulates the live trip-tracking state machine:
 *  - GPS watchPosition lifecycle (startTrip / stopTrip)
 *  - Leg advancement, walk-step completion, and off-route detection
 *  - "On vehicle" confirmation toggle
 *  - Reroute suppression timer
 *  - Trip-resume across PWA reloads (BUG-resume): durable fields persist to
 *    localStorage with a 4 h TTL; the watch effect auto-attaches when the
 *    rehydrated state has tripActive=true, so a backgrounded-then-evicted
 *    PWA picks up the trip on next open. See utils/tripPersistence.js.
 *
 * @param {{ result: object|null, selectedRouteIndex: number }} params
 * @returns {{
 *   tripActive: boolean,
 *   userPosition: {lat: number, lng: number, heading: number|null} | null,
 *   activeLegIndex: number | null,
 *   completedSteps: Set<string>,
 *   isOffRoute: boolean,
 *   tripGeoError: boolean,
 *   onVehicle: boolean,
 *   startTrip: () => void,
 *   stopTrip: () => void,
 *   toggleOnVehicle: () => void,
 *   dismissOffRoute: () => void,
 *   dismissTripGeoError: () => void,
 *   resetForReroute: () => void,
 * }}
 */
export function useTripTracker({ result, selectedRouteIndex }) {
  // Rehydrate durable fields from localStorage. Volatile fields (userPosition,
  // isOffRoute, tripGeoError, suppressRerouteUntil) start fresh — GPS will
  // repopulate them within seconds. Reading happens once at mount via the
  // lazy-init form of useState.
  const persisted = loadPersistedTrip(TRIP_STATE_KEY);
  const persistedActive       = persisted?.tripActive === true;
  const persistedLegIndex     = persistedActive ? (persisted.activeLegIndex ?? 0) : null;
  const persistedSteps        = persistedActive ? new Set(persisted.completedSteps ?? []) : new Set();
  const persistedOnVehicle    = persistedActive ? !!persisted.onVehicle : false;

  const [tripActive, setTripActive]         = useState(persistedActive);
  const [userPosition, setUserPosition]     = useState(null);
  const [activeLegIndex, setActiveLegIndex] = useState(persistedLegIndex);
  const [completedSteps, setCompletedSteps] = useState(persistedSteps);
  const [isOffRoute, setIsOffRoute]         = useState(false);
  const [tripGeoError, setTripGeoError]     = useState(false);
  const [onVehicle, setOnVehicle]           = useState(persistedOnVehicle);

  const watchIdRef           = useRef(null);
  const suppressRerouteUntil = useRef(0);
  // Ref mirrors for synchronous reads inside the GPS position effect (OPT-FE-005).
  const activeLegIndexRef    = useRef(persistedLegIndex);
  const onVehicleRef         = useRef(persistedOnVehicle);

  // Close over the latest completedSteps for the position updater without
  // adding it to the GPS effect's deps (which would re-subscribe needlessly).
  const completedStepsRef = useRef(completedSteps);
  useEffect(() => { completedStepsRef.current = completedSteps; }, [completedSteps]);

  // ── Persistence ────────────────────────────────────────────────────────
  // Re-serialise durable state on every change. When tripActive flips false
  // (stopTrip, PERMISSION_DENIED, etc.) the blob is cleared so the next mount
  // starts fresh. Quota / private-browsing failures are swallowed inside the
  // helpers — persistence is best-effort.
  useEffect(() => {
    if (!tripActive) {
      clearPersistedTrip(TRIP_STATE_KEY);
      return;
    }
    savePersistedTrip(TRIP_STATE_KEY, {
      tripActive: true,
      activeLegIndex,
      completedSteps: Array.from(completedSteps),
      onVehicle,
    });
  }, [tripActive, activeLegIndex, completedSteps, onVehicle]);

  // ── watchPosition lifecycle ────────────────────────────────────────────
  // Driven by `tripActive` so both fresh startTrip AND rehydration-on-mount
  // attach the watch via the same code path. Cleanup runs on tripActive→false
  // and on unmount, so stopTrip and a host unmount both tear down cleanly.
  useEffect(() => {
    if (!tripActive) return undefined;
    if (!navigator.geolocation) {
      setTripGeoError(true);
      setTripActive(false);
      return undefined;
    }
    // Defensive: clear any prior watch so a re-entrant attach cannot leak
    // a watchPosition handler whose ID we'd otherwise lose track of.
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setTripGeoError(false);
        setUserPosition({ lat: pos.coords.latitude, lng: pos.coords.longitude, heading: pos.coords.heading ?? null });
      },
      (err) => {
        console.error("[trip] GPS error:", err);
        if (err.code === err.PERMISSION_DENIED) {
          setTripGeoError(true);
          // Inline stopTrip's resets; setTripActive(false) lets this effect's
          // cleanup clear the watch on the next commit.
          setUserPosition(null);
          activeLegIndexRef.current = null;
          setActiveLegIndex(null);
          setCompletedSteps(new Set());
          setIsOffRoute(false);
          setOnVehicle(false);
          onVehicleRef.current = false;
          setTripActive(false);
        }
      },
      TRIP_GEO_OPTIONS,
    );
    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
  }, [tripActive]);

  // Stable handler identities (OPT-FE-209) so consumers that pass these into
  // memoized children (RouteCard, MapView) don't re-render on every GPS tick.
  // All deps are setState dispatchers (stable) or module-scope constants.
  const startTrip = useCallback(() => {
    if (!navigator.geolocation) {
      setTripGeoError(true);
      return;
    }
    activeLegIndexRef.current = 0;
    setActiveLegIndex(0);
    setCompletedSteps(new Set());
    setIsOffRoute(false);
    suppressRerouteUntil.current = 0;
    setOnVehicle(false);
    onVehicleRef.current = false;
    setTripActive(true); // watch effect attaches on next commit
  }, []);

  const stopTrip = useCallback(() => {
    setTripActive(false); // watch effect cleanup detaches + persist effect clears storage
    setUserPosition(null);
    activeLegIndexRef.current = null;
    setActiveLegIndex(null);
    setCompletedSteps(new Set());
    setIsOffRoute(false);
    setTripGeoError(false);
    setOnVehicle(false);
    onVehicleRef.current = false;
  }, []);

  const toggleOnVehicle = useCallback(() => {
    setOnVehicle(v => {
      onVehicleRef.current = !v;
      return !v;
    });
  }, []);

  const dismissOffRoute = useCallback(() => {
    setIsOffRoute(false);
    suppressRerouteUntil.current = Date.now() + REROUTE_SUPPRESSION_MS;
  }, []);

  const dismissTripGeoError = useCallback(() => {
    setTripGeoError(false);
  }, []);

  const resetForReroute = useCallback(() => {
    activeLegIndexRef.current = 0;
    setActiveLegIndex(0);
    setCompletedSteps(new Set());
    setIsOffRoute(false);
    suppressRerouteUntil.current = 0;
  }, []);

  // Clear "on vehicle" whenever the active leg changes.
  // setOnVehicle and onVehicleRef are stable — omitting them is correct.
  useEffect(() => {
    setOnVehicle(false);
    onVehicleRef.current = false;
  }, [activeLegIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  // GPS position → trip state updates.
  // Intentionally deps on `userPosition` only — all other values are read via
  // refs so this effect fires on GPS tick without re-subscribing on unrelated
  // state changes.
  useEffect(() => {
    if (!tripActive || !userPosition || !result) return;
    const route = result.routes?.[selectedRouteIndex];
    if (!route?.legs?.length) return;

    const { nextLegIdx, clearOffRoute, addedStepKeys, isOffRoute: offRoute } =
      computeTripPositionUpdates(userPosition, route.legs, {
        currentLegIdx:          activeLegIndexRef.current ?? 0,
        onVehicle:              onVehicleRef.current,
        suppressRerouteUntilMs: suppressRerouteUntil.current,
        completedSteps:         completedStepsRef.current,
        legAdvanceRadius:        LEG_ADVANCE_RADIUS_M,
        legAdvanceRadiusVehicle: LEG_ADVANCE_RADIUS_VEHICLE_M,
        walkStepProximity:       WALK_STEP_PROXIMITY_M,
        offRouteThreshold:       OFF_ROUTE_THRESHOLD_METERS,
      });

    if (nextLegIdx !== null) {
      activeLegIndexRef.current = nextLegIdx;
      setActiveLegIndex(nextLegIdx);
    }
    if (clearOffRoute) setIsOffRoute(false);
    if (addedStepKeys.length > 0) {
      setCompletedSteps(prev => {
        const next = new Set(prev);
        addedStepKeys.forEach(k => next.add(k));
        return next;
      });
    }
    if (offRoute !== null) setIsOffRoute(offRoute);
  }, [userPosition]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    tripActive,
    userPosition,
    activeLegIndex,
    completedSteps,
    isOffRoute,
    tripGeoError,
    onVehicle,
    startTrip,
    stopTrip,
    toggleOnVehicle,
    dismissOffRoute,
    dismissTripGeoError,
    resetForReroute,
  };
}
