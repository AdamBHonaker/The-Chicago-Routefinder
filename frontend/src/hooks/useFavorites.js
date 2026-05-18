import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import {
  getSavedLocations,
  getSavedRoutes,
  saveRoute,
  deleteRoute,
  getPinnedStops,
  pinStop,
  unpinStop,
} from "../favorites.js";
import { LIMIT_ERROR_DISMISS_MS } from "../constants.js";

// ---------------------------------------------------------------------------
// useFavorites — encapsulates all localStorage-backed favourites state:
// saved locations, saved routes, pinned stops, and the route-save UI.
// Extracted from App.jsx to separate concerns (TD-035).
//
// Note: pinnedArrivals data fetching is intentionally NOT here — it is managed
// by the useApiQuery hook in App.jsx so it gets auto-refresh and loading state.
// ---------------------------------------------------------------------------

export function useFavorites({ origin, destination }) {
  const [savedLocations, setSavedLocations] = useState(() => getSavedLocations());
  const [savedRoutes, setSavedRoutes]         = useState(() => getSavedRoutes());
  const [showSavedRoutes, setShowSavedRoutes] = useState(false);
  const [pinnedStops, setPinnedStops]         = useState(() => getPinnedStops());

  // Route-save inline UI state
  const [savingRoute, setSavingRoute]         = useState(false);
  const [routeLabelDraft, setRouteLabelDraft] = useState("");
  const [routeLimitError, setRouteLimitError] = useState(false);
  const routeLimitTimerRef = useRef(null);

  const currentOrigin = origin.trim();
  const currentDest   = destination.trim();
  const currentRouteSaved = useMemo(
    () => savedRoutes.some((r) => r.origin === currentOrigin && r.destination === currentDest),
    [savedRoutes, currentOrigin, currentDest]
  );

  useEffect(() => () => {
    if (routeLimitTimerRef.current) clearTimeout(routeLimitTimerRef.current);
  }, []);

  // Stable handler identities (OPT-FE-209): consumers in App.jsx forward these
  // to memoized children, so an unstable reference would defeat memoization
  // every render. Use the functional setState form so we don't need the
  // current array in the dep list.
  const handleUnpin = useCallback((id) => {
    setPinnedStops((prev) => unpinStop(id, prev));
  }, []);

  const handlePinToggle = useCallback((stopType, stopId, label, routeHint, currentlyPinned) => {
    setPinnedStops((prev) => {
      if (currentlyPinned) {
        const existing = prev.find((s) => s.type === stopType && s.stop_id === stopId);
        return existing ? unpinStop(existing.id, prev) : prev;
      }
      const next = pinStop(stopType, stopId, label, routeHint, prev);
      return next ?? prev;
    });
  }, []);

  const handleDeleteRoute = useCallback((id) => {
    setSavedRoutes((prev) => deleteRoute(id, prev));
  }, []);

  function handleToggleSaveRoute() {
    if (currentRouteSaved) {
      const entry = savedRoutes.find(
        (r) => r.origin === currentOrigin && r.destination === currentDest
      );
      if (entry) setSavedRoutes(deleteRoute(entry.id, savedRoutes));
    } else {
      setRouteLabelDraft(`${currentOrigin} → ${currentDest}`.slice(0, 30));
      setSavingRoute(true);
    }
  }

  function handleSaveRoute() {
    const label = routeLabelDraft.trim() || `${currentOrigin} → ${currentDest}`.slice(0, 30);
    const next = saveRoute(label, currentOrigin, currentDest, savedRoutes);
    if (next === null) {
      setRouteLimitError(true);
      if (routeLimitTimerRef.current) clearTimeout(routeLimitTimerRef.current);
      routeLimitTimerRef.current = setTimeout(() => {
        setRouteLimitError(false);
        setSavingRoute(false);
      }, LIMIT_ERROR_DISMISS_MS);
    } else {
      setSavedRoutes(next);
      setSavingRoute(false);
      setRouteLimitError(false);
    }
  }

  return {
    savedLocations, setSavedLocations,
    savedRoutes,
    showSavedRoutes, setShowSavedRoutes,
    pinnedStops,
    savingRoute, setSavingRoute,
    routeLabelDraft, setRouteLabelDraft,
    routeLimitError, setRouteLimitError,
    currentRouteSaved,
    handleUnpin,
    handlePinToggle,
    handleDeleteRoute,
    handleToggleSaveRoute,
    handleSaveRoute,
  };
}
