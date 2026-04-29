import { useState, useRef, useEffect, useMemo } from "react";
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

  function handleUnpin(id) {
    setPinnedStops(unpinStop(id, pinnedStops));
  }

  function handlePinToggle(stopType, stopId, label, routeHint, currentlyPinned) {
    if (currentlyPinned) {
      const existing = pinnedStops.find((s) => s.type === stopType && s.stop_id === stopId);
      if (existing) setPinnedStops(unpinStop(existing.id, pinnedStops));
    } else {
      const next = pinStop(stopType, stopId, label, routeHint, pinnedStops);
      if (next !== null) setPinnedStops(next);
    }
  }

  function handleDeleteRoute(id) {
    setSavedRoutes(deleteRoute(id, savedRoutes));
  }

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
