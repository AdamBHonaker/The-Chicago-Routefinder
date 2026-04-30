import { useState, useRef, useEffect } from "react";
import {
  TRIP_GEO_OPTIONS,
  OFF_ROUTE_THRESHOLD_METERS,
  REROUTE_SUPPRESSION_MS,
  LEG_ADVANCE_RADIUS_M,
  LEG_ADVANCE_RADIUS_VEHICLE_M,
  WALK_STEP_PROXIMITY_M,
} from "../constants.js";
import { computeTripPositionUpdates } from "../utils/tripGeometry.js";

/**
 * Encapsulates the live trip-tracking state machine:
 *  - GPS watchPosition lifecycle (startTrip / stopTrip)
 *  - Leg advancement, walk-step completion, and off-route detection
 *  - "On vehicle" confirmation toggle
 *  - Reroute suppression timer
 *
 * @param {{ result: object|null, selectedRouteIndex: number }} params
 * @returns {{
 *   tripActive: boolean,
 *   userPosition: {lat: number, lng: number} | null,
 *   activeLegIndex: number | null,
 *   completedSteps: Set<string>,
 *   isOffRoute: boolean,
 *   tripGeoError: boolean,
 *   onVehicle: boolean,
 *   startTrip: () => void,
 *   stopTrip: () => void,
 *   toggleOnVehicle: () => void,
 *   dismissOffRoute: () => void,
 *   resetForReroute: () => void,
 * }}
 */
export function useTripTracker({ result, selectedRouteIndex }) {
  const [tripActive, setTripActive]         = useState(false);
  const [userPosition, setUserPosition]     = useState(null);
  const [activeLegIndex, setActiveLegIndex] = useState(null);
  const [completedSteps, setCompletedSteps] = useState(new Set());
  const [isOffRoute, setIsOffRoute]         = useState(false);
  const [tripGeoError, setTripGeoError]     = useState(false);
  const [onVehicle, setOnVehicle]           = useState(false);

  const watchIdRef           = useRef(null);
  const suppressRerouteUntil = useRef(0);
  // Ref mirrors for synchronous reads inside the GPS position effect (OPT-FE-005).
  const activeLegIndexRef    = useRef(null);
  const onVehicleRef         = useRef(false);

  // Close over the latest completedSteps for the position updater without
  // adding it to the GPS effect's deps (which would re-subscribe needlessly).
  const completedStepsRef = useRef(completedSteps);
  useEffect(() => { completedStepsRef.current = completedSteps; }, [completedSteps]);

  function startTrip() {
    if (!navigator.geolocation) {
      setTripGeoError(true);
      return;
    }
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setTripGeoError(false);
        setUserPosition({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      },
      (err) => {
        console.error("[trip] GPS error:", err);
        if (err.code === err.PERMISSION_DENIED) {
          setTripGeoError(true);
          stopTrip();
        }
      },
      TRIP_GEO_OPTIONS,
    );
    setTripActive(true);
    activeLegIndexRef.current = 0;
    setActiveLegIndex(0);
    setCompletedSteps(new Set());
    setIsOffRoute(false);
    suppressRerouteUntil.current = 0;
    setOnVehicle(false);
    onVehicleRef.current = false;
  }

  function stopTrip() {
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    setTripActive(false);
    setUserPosition(null);
    activeLegIndexRef.current = null;
    setActiveLegIndex(null);
    setCompletedSteps(new Set());
    setIsOffRoute(false);
    setTripGeoError(false);
    setOnVehicle(false);
    onVehicleRef.current = false;
  }

  function toggleOnVehicle() {
    setOnVehicle(v => {
      onVehicleRef.current = !v;
      return !v;
    });
  }

  function dismissOffRoute() {
    setIsOffRoute(false);
    suppressRerouteUntil.current = Date.now() + REROUTE_SUPPRESSION_MS;
  }

  function dismissTripGeoError() {
    setTripGeoError(false);
  }

  function resetForReroute() {
    activeLegIndexRef.current = 0;
    setActiveLegIndex(0);
    setCompletedSteps(new Set());
    setIsOffRoute(false);
    suppressRerouteUntil.current = 0;
  }

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
