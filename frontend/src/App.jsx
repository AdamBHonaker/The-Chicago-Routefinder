import { useState, useRef, useEffect, useMemo, useCallback, Fragment, lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import "./App.css";
import AdSlot from "./components/AdSlot.jsx";
import ArrivedToast from "./components/ArrivedToast.jsx";
import { useCardsColumnWidth, SIDE_RAIL_WIDTH } from "./hooks/useCardsColumnWidth.js";
import { useAlertsTabFilter } from "./hooks/useAlertsTabFilter.js";
// MapView pulls in maplibre-gl (~210 KB gz) — keep it out of the eager
// bundle. Suspense fallback is a blank panel (panel-map already has the
// app background colour) so cold loads don't flash a skeleton.
const MapView = lazy(() => import("./MapView.jsx"));
import LoadingSkeleton from "./components/LoadingSkeleton.jsx";
// SettingsPanel + SavedRoutesPanel are only opened on user click (gear / star)
// — keep them out of the eager bundle (OPT-FE-204).
const SettingsPanel    = lazy(() => import("./components/SettingsPanel.jsx"));
const SavedRoutesPanel = lazy(() => import("./components/SavedRoutesPanel.jsx"));
// FEAT-018: ToolsHub replaces the body of the (renamed) "Tools" tab.
const ToolsHub = lazy(() => import("./components/ToolsHub.jsx"));
import RouteCard from "./components/RouteCard.jsx";
import PinnedStopsBoard from "./components/PinnedStopsBoard.jsx";
import ServiceAlertsBar from "./components/ServiceAlertsBar.jsx";
import RouteAlertsBanner from "./components/RouteAlertsBanner.jsx";
import AlertsFilterBar from "./components/AlertsFilterBar.jsx";
import TwoToneHeading from "./components/TwoToneHeading.jsx";
import WeatherStrip from "./components/WeatherStrip.jsx";
import Masthead from "./components/Masthead.jsx";
import { useFavorites } from "./hooks/useFavorites.js";
import { useTripTracker } from "./hooks/useTripTracker.js";
import { useByokIdleClear } from "./hooks/useByokIdleClear.js";
import { useServiceAlerts } from "./hooks/useServiceAlerts.js";
import { useShareLink } from "./hooks/useShareLink.js";
import { useDocumentLanguage } from "./hooks/useDocumentLanguage.js";
import {
  BACKEND_URL,
  RETRY_DELAYS_MS,
  BYOK_ENABLED,
  WALK_SPEED_FACTORS,
} from "./constants.js";
import LabelSavePanel from "./components/LabelSavePanel.jsx";
import LocationInput from "./components/LocationInput.jsx";
import SharedRouteBanner from "./components/SharedRouteBanner.jsx";
import InstallPrompt from "./components/InstallPrompt.jsx";
import SideRail from "./components/SideRail.jsx";
import PanelSplitter from "./components/PanelSplitter.jsx";
import SheetSegmentedControl from "./components/SheetSegmentedControl.jsx";
import { MobileLayout } from "./components/MobileLayout.jsx";
import { useMediaQuery } from "./hooks/useMediaQuery.js";
import { createSheetSnapStore } from "./utils/sheetSnap.js";
import { useApiQuery } from "./hooks/useApiQuery.js";
import { useLocalStorage } from "./hooks/useLocalStorage.js";
import { fetchWithRetry as _fetchWithRetry } from "./utils/fetchWithRetry.js";
import { renderMarkdown } from "./utils/renderMarkdown.js";
import { extractTransitLines } from "./utils/routeUtils.js";
import { stripLineSuffix } from "./lineColors.js";
import { deriveTransferPoints } from "./utils/deriveTransferPoints.js";
import {
  TRIP_PLAN_KEY,
  TRIP_STATE_KEY,
  loadPersistedTrip,
  savePersistedTrip,
  clearPersistedTrip,
} from "./utils/tripPersistence.js";
import { track } from "./analytics.js";

// Thin wrapper so call-sites don't need to pass RETRY_DELAYS_MS explicitly.
// Full implementation and JSDoc live in utils/fetchWithRetry.js (TD-040).
function fetchWithRetry(url, options, onRetrying) {
  return _fetchWithRetry(url, options, RETRY_DELAYS_MS, onRetrying);
}

export default function App() {
  const { t, i18n } = useTranslation();
  useDocumentLanguage();

  // Rehydrate the in-flight trip's plan if a fresh (within 4 h) blob exists.
  // Paired with useTripTracker's TRIP_STATE_KEY rehydration; both are written
  // together while tripActive=true and cleared together on stopTrip. See
  // utils/tripPersistence.js for the rationale and TTL.
  //
  // Defensive: if the plan blob is gone (TTL expired or never written due to
  // quota) but a stale tracker blob remains, drop the tracker blob too so the
  // hook does not boot into a tripActive=true state with no route to render.
  // useMemo runs before the useTripTracker call below — so the cleanup lands
  // before the hook reads its own persisted state on mount.
  const persistedPlan = useMemo(() => {
    const plan = loadPersistedTrip(TRIP_PLAN_KEY);
    if (!plan) clearPersistedTrip(TRIP_STATE_KEY);
    return plan;
  }, []);

  const [origin, setOrigin] = useState(persistedPlan?.origin ?? "");
  const [originGeoCoords, setOriginGeoCoords] = useState(null);
  const [destination, setDestination] = useState(persistedPlan?.destination ?? "");
  const [transitMode, setTransitMode] = useState("All");

  const [result, setResult] = useState(persistedPlan?.result ?? null);   // { recommendation, routes }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [selectedRouteIndex, setSelectedRouteIndex] = useState(persistedPlan?.selectedRouteIndex ?? 0);
  const [isSharedLink, setIsSharedLink] = useState(false);

  // BYOK state — key persisted to sessionStorage (clears on tab close, NOT across tabs).
  // sessionStorage and localStorage are equally readable by any same-origin JavaScript,
  // including supply-chain-compromised npm deps. Accepted trade-off for BYOK UX; feature
  // is opt-in and off by default (VITE_BYOK_ENABLED). Auto-cleared after idle timeout below.
  const [byokKey, setByokKey] = useState(() =>
    BYOK_ENABLED ? (sessionStorage.getItem("byok_api_key") || "") : ""
  );
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("home"); // mobile tab bar; on desktop drives cards-column content (Home/Alerts/Tools)

  // Desktop cards-column width — extracted to useCardsColumnWidth (TD-FE-020).
  const {
    width: cardsColumnWidth,
    setWidth: setCardsColumnWidth,
    max: cardsColumnMax,
    min: CARDS_MIN_WIDTH,
  } = useCardsColumnWidth();

  // ── Mobile bottom-sheet state ────────────────────────────────────────────
  // Below 800px the layout swaps to a Passage-style full-bleed map + draggable
  // bottom sheet. The sheet replaces the 4-tab bottom bar — Home / Alerts /
  // Saved live as segments inside the sheet, the map is always visible behind.
  // Sheet snap: 0=peek (140px), 1=half (50dvh), 2=full (88dvh). Persistence
  // factory below; only USER drags persist (auto-promotes don't pollute the
  // user's preferred opening height).
  const SHEET_STORAGE_KEY = "crf:sheetSnap";
  const sheetSnapStore = useMemo(() => createSheetSnapStore(SHEET_STORAGE_KEY), []);
  const isMobile = useMediaQuery("(max-width: 800px)");
  const [sheetSnap, setSheetSnap] = useState(() => sheetSnapStore.load() ?? 0);
  const [mapPadding, setMapPadding] = useState(null);
  const lastResultRef = useRef(null);
  const userMovedSheetRef = useRef(false);

  const handleSheetSnapChange = useCallback((idx) => {
    userMovedSheetRef.current = true;
    setSheetSnap(idx);
  }, []);

  // 80px top reserves room for the floating masthead; +16 bottom keeps the
  // polyline visually clear of the sheet's top edge.
  const handleObscuredChange = useCallback((bottomPx) => {
    setMapPadding({ top: 80, bottom: bottomPx + 16, left: 16, right: 16 });
  }, []);

  // AI toggle — persisted to localStorage via useLocalStorage (TD-039).
  // Defaults to false (off) so new users get faster route cards without AI latency.
  const [aiEnabled, setAiEnabled] = useLocalStorage("cta_ai_enabled", false);

  // Walk speed preference — "slow" / "standard" / "brisk", persisted to localStorage (TD-039).
  const [walkSpeed, setWalkSpeed] = useLocalStorage("cta_walk_speed", "standard");

  // Favourites state — managed by useFavorites hook (TD-035)
  const {
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
  } = useFavorites({ origin, destination });

  // Pinned-stop arrivals — fetched via useApiQuery (TD-038) so loading/error
  // state is managed centrally and the board auto-refreshes every 60 s.
  // Derive a stable identity key from the pinned-stop set (OPT-FE-215) so the
  // query only re-subscribes when the actual set of stops changes — reorders
  // and equivalent array re-creations don't trigger redundant abort+refetch.
  const pinnedStopsKey = useMemo(
    () => pinnedStops.map((s) => `${s.type}:${s.stop_id}`).sort().join("|"),
    [pinnedStops],
  );
  const pinnedArrivalsFetcher = useCallback((signal) => {
    const params = pinnedStops.map((s) => `stops=${s.type}:${s.stop_id}`).join("&");
    return fetch(`${BACKEND_URL}/stop-arrivals?${params}`, { signal });
  }, [pinnedStops]);
  const { data: pinnedArrivalsData, refetch: refetchPinnedArrivals } = useApiQuery(
    pinnedArrivalsFetcher,
    [pinnedStopsKey],
    { refetchInterval: 60000, enabled: pinnedStops.length > 0 },
  );
  const pinnedArrivals = pinnedArrivalsData?.arrivals || {};

  // Service Alerts — fetch + dismissal state extracted to useServiceAlerts (TD-FE-006)
  const { undismissedAlerts, dismiss: handleAlertDismiss, refetch: refetchServiceAlerts } = useServiceAlerts();

  const activeAlertRoutes = useMemo(
    () => new Set(
      undismissedAlerts
        .flatMap((a) => a.routes ?? [])
        .map(stripLineSuffix)
    ),
    [undismissedAlerts]
  );
  // One pass per route, computed once and shared with each RouteCard for its
  // pill row (OPT-FE-104). Indexed array keyed by route position.
  const routeTransitLines = useMemo(
    () => (result?.routes ?? []).map((r) => extractTransitLines(r.legs ?? [])),
    [result]
  );

  const currentRouteLines = useMemo(() => {
    const lines = routeTransitLines[selectedRouteIndex];
    if (!lines?.length) return null;
    return new Set(lines.map((l) => l.isBus ? l.lineCode : stripLineSuffix(l.line)));
  }, [routeTransitLines, selectedRouteIndex]);

  const visibleAlerts = useMemo(() => {
    if (!currentRouteLines) return [];
    return undismissedAlerts.filter((a) =>
      (a.routes ?? []).some((r) => currentRouteLines.has(stripLineSuffix(r)))
    );
  }, [undismissedAlerts, currentRouteLines]);

  // Notices & Delays tab — state + derivations extracted to useAlertsTabFilter (TD-FE-020).
  const {
    selectedLines: alertsTabSelectedLines,
    setSelectedLines: setAlertsTabSelectedLines,
    selectedBuses: alertsTabSelectedBuses,
    setSelectedBuses: setAlertsTabSelectedBuses,
    availableBusRoutes,
    filteredAlertsForTab,
    seedFromRoute: seedAlertsTabFromCurrentRoute,
  } = useAlertsTabFilter(undismissedAlerts, currentRouteLines);

  // Banner click handler: pre-select the current route's L lines and bus
  // routes, then swap the cards-column to the Notices & Delays tab.
  function viewRouteAlerts() {
    seedAlertsTabFromCurrentRoute();
    setActiveTab("alerts");
  }

  // Fire-and-forget ping on mount for DAU/session counting — silent on failure.
  // credentials: "include" sends/receives the FEAT-001 session cookie cross-origin
  // (Vercel → Railway). Backend CORS is configured with allow_credentials=True.
  useEffect(() => {
    fetch(`${BACKEND_URL}/ping`, { credentials: "include" }).catch(() => {});
    track("app_loaded");
  }, []);

  // Refetch the alerts feed every time the user opens the Notices & Delays
  // tab, so the filter renders against the freshest CTA data even on long
  // sessions where the initial fetch happened many minutes ago.
  useEffect(() => {
    if (activeTab === "alerts") refetchServiceAlerts();
  }, [activeTab, refetchServiceAlerts]);

  // ── Sheet auto-promote (route arrival) ───────────────────────────────────
  // When a route result arrives on mobile, nudge the sheet from peek (0) to
  // half (1) so the user immediately sees the routes without having to drag.
  // Skip if the user has manually moved the sheet this session
  // (userMovedSheetRef) so we don't fight their intent. Auto-promotes are
  // NOT persisted — only manual settles are. Trip-start auto-promote lives
  // after the useTripTracker destructure, where tripActive is in scope.
  useEffect(() => {
    if (!isMobile) return;
    if (result && !lastResultRef.current && !userMovedSheetRef.current) {
      setSheetSnap(prev => prev === 0 ? 1 : prev);
    }
    lastResultRef.current = result;
  }, [result, isMobile]);

  function handleSaveByokKey(key) {
    setByokKey(key);
    if (key) {
      sessionStorage.setItem("byok_api_key", key);
    } else {
      sessionStorage.removeItem("byok_api_key");
    }
  }

  // Auto-clear BYOK key after idle (BUG-014) — logic lives in useByokIdleClear.
  useByokIdleClear(byokKey, setByokKey);

  const abortRef = useRef(null);
  // Incremented on every new search so RouteCard instances are remounted,
  // resetting their expanded state to the isFirst default.
  const searchIdRef = useRef(0);

  // ── Feature Trip — Live Trip-in-Progress ──────────────────────────────────
  const {
    tripActive, userPosition, activeLegIndex, completedSteps,
    isOffRoute, tripGeoError, onVehicle,
    startTrip, stopTrip, toggleOnVehicle, dismissOffRoute, dismissTripGeoError, resetForReroute,
  } = useTripTracker({ result, selectedRouteIndex });

  // Stable per-RouteCard callbacks (OPT-FE-209 / OPT-007). RouteCard is memo()'d,
  // but inline arrows in the .map() block below would mint fresh function refs on
  // every App render — including every GPS tick during a trip — defeating the
  // memo and re-rendering the full leg/step subtree at ~1 Hz. The remaining
  // hook-sourced callbacks (stopTrip, toggleOnVehicle, dismissTripGeoError,
  // setSelectedTransferId) are already stable via useCallback inside their
  // owning hooks or as useState setters.
  const handleRouteSelect = useCallback((i) => {
    setSelectedRouteIndex(i);
    stopTrip();
    track("route_selected");
  }, [stopTrip]);
  const handleStartTripWithTrack = useCallback(() => {
    track("start_route_tapped");
    startTrip();
  }, [startTrip]);

  // Persist the route plan (origin/destination/result/selectedRouteIndex)
  // alongside useTripTracker's state blob while a trip is active, so the
  // PWA can resume mid-trip if the OS evicts the page. Clears on
  // tripActive=false so abandoned plans don't leak past the trip's lifetime.
  useEffect(() => {
    if (tripActive && result) {
      savePersistedTrip(TRIP_PLAN_KEY, { origin, destination, result, selectedRouteIndex });
    } else if (!tripActive) {
      clearPersistedTrip(TRIP_PLAN_KEY);
    }
  }, [tripActive, origin, destination, result, selectedRouteIndex]);

  // ── Feature TransferMarkers — selected transfer ID ────────────────────────
  const [selectedTransferId, setSelectedTransferId] = useState(null);

  // Clear selection when the trip ends, a different route is selected, or a new
  // search runs — any of these make the current selection stale or irrelevant.
  useEffect(() => {
    setSelectedTransferId(null);
  }, [tripActive, selectedRouteIndex, result]);

  // Fire trip_off_route on each false→true transition. The dep on isOffRoute
  // means the effect re-runs only when the flag flips, and the if-guard skips
  // the false-side transitions — so a user who drifts, dismisses, recovers,
  // and drifts again logs two separate events (intended diagnostic behavior).
  useEffect(() => {
    if (isOffRoute) track("trip_off_route");
  }, [isOffRoute]);

  // Sheet auto-promote on trip start (mobile). Same guard as the route-
  // arrival promote above. See "Sheet auto-promote" comment for rationale.
  useEffect(() => {
    if (!isMobile || !tripActive || userMovedSheetRef.current) return;
    setSheetSnap(prev => prev === 0 ? 1 : prev);
  }, [tripActive, isMobile]);

  // Derive transfer points for the active trip so RouteCard can make spine rows
  // interactive. Mirrors the derivation MapView does internally, using the same
  // pure function so transfer IDs are identical on both sides.
  const selectedRoute = result?.routes?.[selectedRouteIndex] ?? null;
  const tripTransferPoints = useMemo(() => {
    if (!tripActive || !selectedRoute) return [];
    const oC = result?.originCoords ?? null;
    const dC = result?.destCoords ?? null;
    return deriveTransferPoints(selectedRoute, {
      originCoords:      oC ? [oC[1], oC[0]] : null,
      destinationCoords: dC ? [dC[1], dC[0]] : null,
    });
  // result?.originCoords / destCoords are stable array refs inside a given result object.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tripActive, selectedRoute, result?.originCoords, result?.destCoords]);
  // ── End Feature TransferMarkers ───────────────────────────────────────────

  // ── Feature ArrivedToast — show/hide + auto-dismiss live in ArrivedToast.
  // Bump this counter from the MapView arrival callback to trigger the toast.
  const [arrivedSignal, setArrivedSignal] = useState(0);

  // Shared /recommend API call — used by both performSearch and handleReroute
  // so the request body, error handling, and setResult shape stay in one place.
  // Returns the number of routes in the response (used by performSearch for route-index pre-selection).
  async function callRecommendAPI(originStr, destinationStr) {
    // BYOK key travels in the Authorization header rather than the body so it
    // is never JSON-serialized into a payload that proxies, the service worker,
    // or back/forward cache might retain.
    const headers = { "Content-Type": "application/json" };
    if (BYOK_ENABLED && byokKey) {
      headers["Authorization"] = `Bearer ${byokKey}`;
    }
    const res = await fetchWithRetry(
      `${BACKEND_URL}/recommend`,
      {
        method: "POST",
        headers,
        // Carries the FEAT-001 session cookie so /recommend counts as part
        // of the same session that /ping started. Without this, /recommend
        // would create a fresh session every call and bounce-rate would
        // be permanently 100%.
        credentials: "include",
        body: JSON.stringify({
          origin:       originStr,
          destination:  destinationStr,
          transit_mode: transitMode,
          ai_enabled:   aiEnabled,
          language:     i18n.language,
          ...(WALK_SPEED_FACTORS[walkSpeed] !== 1.0 ? { walk_speed: WALK_SPEED_FACTORS[walkSpeed] } : {}),
        }),
        signal: abortRef.current.signal,
      },
      (attempt) => setError(`Network error — retrying... (${attempt}/${RETRY_DELAYS_MS.length})`),
    );

    if (!res.ok) {
      let msg = `Service error (${res.status} ${res.statusText})`;
      try { const d = await res.json(); msg = d.detail || msg; } catch {} // body may not be JSON (e.g. nginx 502)
      throw new Error(msg);
    }

    const data = await res.json();
    const routes = data.routes || [];
    setResult({
      recommendation: data.recommendation != null ? renderMarkdown(data.recommendation) : null,
      routes,
      alerts: data.alerts || [],
      originCoords: data.origin_coords,
      destCoords:   data.dest_coords,
      busDataPartial: (data.bus_errors > 0) && !(data.bus_arrivals?.length),
      weather: data.weather || null,
      // BUG-047: capture coverage status so the UI can show an explicit empty
      // state when the rider's origin/destination is outside CTA coverage.
      routingStatus: data.routing_status || null,
    });
    return routes.length;
  }

  async function handleReroute() {
    if (!userPosition) return;
    track("trip_rerouted");
    const gpsOrigin = `${userPosition.lat.toFixed(6)},${userPosition.lng.toFixed(6)}`;

    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    setOrigin(gpsOrigin);
    resetForReroute();
    setSelectedRouteIndex(0);
    searchIdRef.current += 1;

    setLoading(true);
    setError("");
    setResult(null);

    try {
      await callRecommendAPI(gpsOrigin, destination.trim());
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message || t("error_generic"));
    } finally {
      setLoading(false);
    }
  }
  // ── End Feature Trip ──────────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  function pushUrlState(from, to) {
    const params = new URLSearchParams({ from, to });
    window.history.replaceState(null, "", `${window.location.pathname}?${params}`);
  }

  async function performSearch(fromStr, toStr, preferredRouteIndex = 0) {
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    setSelectedRouteIndex(0);
    searchIdRef.current += 1;

    // Re-arm sheet auto-promote: a fresh search should bump the sheet from
    // peek to half on result arrival, even if the user manually settled it
    // earlier in the session. lastResultRef must reset so the
    // !lastResultRef.current && result check fires on the next setResult.
    userMovedSheetRef.current = false;
    lastResultRef.current = null;

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const routeCount = await callRecommendAPI(fromStr, toStr);
      pushUrlState(fromStr, toStr);
      if (preferredRouteIndex > 0 && routeCount > preferredRouteIndex) {
        setSelectedRouteIndex(preferredRouteIndex);
      }
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message || t("error_generic"));
    } finally {
      setLoading(false);
    }
  }

  // Auto-submit a search when the URL contains valid ?from / ?to params (TD-FE-006).
  useShareLink(({ from, to, routeIndex }) => {
    setOrigin(from);
    setDestination(to);
    setIsSharedLink(true);
    performSearch(from, to, routeIndex);
  });

  async function handleSubmit(e) {
    e.preventDefault();
    if (!origin.trim() || !destination.trim()) return;

    stopTrip();
    setSavingRoute(false);
    setRouteLimitError(false);
    setIsSharedLink(false);

    track("recommend_submitted");
    await performSearch(originGeoCoords ?? origin.trim(), destination.trim());
  }

  // The legacy Masthead "saved routes" overlay still surfaces saved routes
  // via SavedRoutesPanel; FEAT-018 swapped the dedicated tab for a Tools-hub
  // sub-view, so the tab itself no longer auto-opens the panel.
  const effectiveShowSavedRoutes = showSavedRoutes;

  const handleTabChange = (id) => {
    setActiveTab(id);
    if (id !== "tools") setShowSavedRoutes(false);
  };

  // ── sidebarContents ──────────────────────────────────────────────────────
  // The form / results / alerts / saved content. Identical in mobile and
  // desktop branches — desktop nests it inside .panel-cards__inner; mobile
  // nests it inside the bottom sheet (with a SheetSegmentedControl prepended
  // to replace the desktop side rail's tab navigation).
  const sidebarContents = (
    <>
          <Masthead
            liveDataActive={!!(result && result.routes.length > 0)}
            byokActive={!!byokKey}
            showSavedRoutes={showSavedRoutes}
            transitMode={transitMode}
            onTransitModeChange={setTransitMode}
            onToggleSettings={() => setSettingsOpen((v) => !v)}
            onToggleSavedRoutes={() => setShowSavedRoutes((v) => !v)}
          />

          {settingsOpen && (
            <Suspense fallback={null}>
              <SettingsPanel
                apiKey={byokKey}
                onSave={handleSaveByokKey}
                onClose={() => setSettingsOpen(false)}
                aiEnabled={aiEnabled}
                onAiChange={setAiEnabled}
                walkSpeed={walkSpeed}
                onWalkSpeedChange={setWalkSpeed}
              />
            </Suspense>
          )}

          {effectiveShowSavedRoutes && (
            <Suspense fallback={null}>
              <SavedRoutesPanel
                savedRoutes={savedRoutes}
                onDeleteRoute={handleDeleteRoute}
                onRouteSelect={(orig, dest) => {
                  setOrigin(orig);
                  setDestination(dest);
                  setShowSavedRoutes(false);
                  setActiveTab("home");
                }}
                onClose={() => {
                  setShowSavedRoutes(false);
                  if (activeTab === "tools") setActiveTab("home");
                }}
              />
            </Suspense>
          )}

          {activeTab === "alerts" && (
            <main className="main tab-alerts-view">
              <div className="tab-alerts-view__heading-row">
                <TwoToneHeading
                  capsKey="caps_advisories"
                  headingKey="alerts_tab_heading"
                  italicWords={1}
                  className="tab-alerts-view__heading"
                />
                <div className="tab-alerts-view__filter-bar">
                  <AlertsFilterBar
                    selectedLines={alertsTabSelectedLines}
                    selectedBuses={alertsTabSelectedBuses}
                    onSelectedLinesChange={setAlertsTabSelectedLines}
                    onSelectedBusesChange={setAlertsTabSelectedBuses}
                    availableBusRoutes={availableBusRoutes}
                  />
                </div>
              </div>
              {alertsTabSelectedLines.size === 0 && alertsTabSelectedBuses.size === 0 ? (
                <p className="tab-alerts-view__prompt">
                  {undismissedAlerts.length === 0
                    ? t("alerts_filter_prompt_empty_feed")
                    : t("alerts_filter_prompt_with_count", { count: undismissedAlerts.length })}
                </p>
              ) : filteredAlertsForTab.length === 0 ? (
                <p className="tab-alerts-view__prompt">{t("alerts_filter_empty_for_selection")}</p>
              ) : (
                <ServiceAlertsBar
                  alerts={filteredAlertsForTab}
                  onDismiss={handleAlertDismiss}
                />
              )}
            </main>
          )}

          {activeTab === "tools" && (
            <Suspense fallback={null}>
              <ToolsHub
                savedRoutes={savedRoutes}
                pinnedStops={pinnedStops}
                onDeleteRoute={handleDeleteRoute}
                onRouteSelect={(orig, dest) => {
                  setOrigin(orig);
                  setDestination(dest);
                  setActiveTab("home");
                }}
                onUnpin={handleUnpin}
              />
            </Suspense>
          )}

          {activeTab !== "alerts" && activeTab !== "tools" && (
          <main className="main">
            <PinnedStopsBoard
              stops={pinnedStops}
              arrivals={pinnedArrivals}
              onUnpin={handleUnpin}
              onRefresh={refetchPinnedArrivals}
            />

            {isSharedLink && (
              <SharedRouteBanner onDismiss={() => setIsSharedLink(false)} />
            )}

            <form className="form paper-grain-bright" onSubmit={handleSubmit}>
              <label>
                <span>{t("label_from")}</span>
                <LocationInput
                  value={origin}
                  onChange={setOrigin}
                  onGeoCoords={setOriginGeoCoords}
                  placeholder={t("placeholder_location")}
                  savedLocations={savedLocations}
                  onSavedLocationsChange={setSavedLocations}
                  showGeoBtn
                />
              </label>

              <div className="swap-row">
                <button
                  type="button"
                  className="swap-btn"
                  onClick={() => {
                    // If origin came from geolocation, preserve the precise
                    // raw "lat,lon" string in the new destination so the
                    // backend routes from the actual GPS fix rather than
                    // re-geocoding the reverse-geocoded address label.
                    const newDestination = originGeoCoords ?? origin;
                    setOrigin(destination);
                    setDestination(newDestination);
                    setOriginGeoCoords(null);
                  }}
                  aria-label={t("swap_directions")}
                  title={t("swap_directions")}
                >
                  ⇅
                </button>
              </div>

              <label>
                <span>{t("label_to")}</span>
                <LocationInput
                  value={destination}
                  onChange={setDestination}
                  placeholder={t("placeholder_location")}
                  savedLocations={savedLocations}
                  onSavedLocationsChange={setSavedLocations}
                />
              </label>

              <button type="submit" disabled={loading}>
                {loading ? t("btn_finding_route") : t("btn_get_route")}
              </button>
            </form>

            {error && (
              <div className="error" role="alert">
                {error}
              </div>
            )}

            {loading && <LoadingSkeleton />}

            {result && !loading && (
              <div className="results">
                <RouteAlertsBanner
                  hasAlerts={visibleAlerts.length > 0}
                  onView={viewRouteAlerts}
                />
                <WeatherStrip weather={result.weather} />
                {result.recommendation != null && (
                <div className="recommendation">
                  <p>{result.recommendation}</p>
                </div>
              )}
              {result.busDataPartial && (
                <p className="data-warning">
                  {t("bus_data_partial")}
                </p>
              )}

                {isOffRoute && (
                  <div className="special-dispatch special-dispatch--advisory" role="alert">
                    <span className="special-dispatch__kicker">{t("alerts_severity_advisory")}</span>
                    <p className="special-dispatch__body">{t("trip_off_route_message")}</p>
                    <div className="special-dispatch__actions">
                      <button className="start-trip-btn" onClick={handleReroute}>
                        {t("trip_reroute_btn")}
                      </button>
                      <button
                        className="btn-ghost-text"
                        onClick={() => { track("off_route_dismissed"); dismissOffRoute(); }}
                      >
                        {t("trip_dismiss_btn")}
                      </button>
                    </div>
                  </div>
                )}

                {result.routes.length === 0 && result.routingStatus?.status === "out_of_coverage" && (
                  <div className="special-dispatch special-dispatch--advisory" role="alert">
                    <span className="special-dispatch__kicker">{t("out_of_coverage_kicker")}</span>
                    <p className="special-dispatch__body">{t("out_of_coverage_message")}</p>
                  </div>
                )}

                {result.routes.length > 0 && (
                  <section className="routes-section">
                    <div className="routes-section-header">
                      <h2 className="routes-heading">{t("route_recommended_heading")}</h2>
                      <button
                        type="button"
                        className={`save-route-btn${currentRouteSaved ? " save-route-btn--saved" : ""}`}
                        onClick={handleToggleSaveRoute}
                      >
                        {currentRouteSaved ? t("fav_saved_route") : t("fav_save_route")}
                      </button>
                    </div>
                    {savingRoute && (
                      <LabelSavePanel
                        prefix="route-label"
                        value={routeLabelDraft}
                        onChange={setRouteLabelDraft}
                        onSave={handleSaveRoute}
                        onCancel={() => setSavingRoute(false)}
                        placeholder={t("fav_route_label_placeholder")}
                        showError={routeLimitError}
                      />
                    )}
                    {result.routes.map((route, i) => {
                      if (tripActive && i !== selectedRouteIndex) return null;
                      return (
                        <Fragment key={`${searchIdRef.current}-${i}`}>
                          {i === 1 && (
                            <h2 className="routes-heading routes-heading--alternates">
                              {t("route_alternates_heading")}
                            </h2>
                          )}
                          <RouteCard
                            route={route}
                            transitLines={routeTransitLines[i]}
                            index={i}
                            isFirst={i === 0}
                            isSelected={i === selectedRouteIndex}
                            onSelect={handleRouteSelect}
                            tripActive={tripActive && i === selectedRouteIndex}
                            activeLegIndex={activeLegIndex}
                            completedSteps={completedSteps}
                            onStartTrip={handleStartTripWithTrack}
                            onStopTrip={stopTrip}
                            tripGeoError={tripGeoError && i === selectedRouteIndex}
                            onDismissTripGeoError={dismissTripGeoError}
                            onVehicle={onVehicle && i === selectedRouteIndex}
                            onToggleVehicle={toggleOnVehicle}
                            pinnedStops={pinnedStops}
                            onPinToggle={handlePinToggle}
                            activeAlertRoutes={activeAlertRoutes}
                            shareOrigin={origin}
                            shareDestination={destination}
                            transferPoints={i === selectedRouteIndex ? tripTransferPoints : undefined}
                            selectedTransferId={i === selectedRouteIndex ? selectedTransferId : null}
                            onSelectTransfer={setSelectedTransferId}
                          />
                        </Fragment>
                      );
                    })}
                    {!tripActive && <AdSlot kicker={t("ad_sponsored_kicker")} />}
                  </section>
                )}
              </div>
            )}
          </main>
          )}
    </>
  );

  // mapNode is rendered ONCE at the App level so it survives breakpoint
  // flips without remounting MapLibre (which would blank the WebGL canvas
  // and re-fetch tiles). The .map-host wrapper toggles between mobile
  // (full-bleed inset:0) and desktop (positioned to fill the .panel-map
  // grid cell) — see styles/bottom-sheet-host.css.
  const mapNode = (
    <Suspense fallback={null}>
      <MapView
        route={result?.routes?.[selectedRouteIndex] ?? null}
        originCoords={result?.originCoords ?? null}
        destCoords={result?.destCoords ?? null}
        userPosition={userPosition}
        tripActive={tripActive}
        activeLegIndex={activeLegIndex}
        cardsColumnWidth={cardsColumnWidth}
        activeTab={activeTab}
        mapPadding={isMobile ? mapPadding : null}
        sheetSnap={isMobile ? sheetSnap : null}
        onArrived={() => { track("trip_completed"); setArrivedSignal((n) => n + 1); }}
        selectedTransferId={selectedTransferId}
        onSelectTransfer={setSelectedTransferId}
        transferPoints={tripTransferPoints}
      />
    </Suspense>
  );

  return (
    <div
      className={`app${isMobile ? " app--mobile" : ""}`}
      data-active-tab={activeTab}
      style={{ "--cards-col-width": `${cardsColumnWidth}px` }}
    >
      <div className={isMobile ? "map-host map-host--mobile" : "map-host map-host--desktop"}>
        {mapNode}
      </div>

      {isMobile ? (
        <MobileLayout
          storageKey={SHEET_STORAGE_KEY}
          handleLabel={t("bottom_sheet_handle_label")}
          snap={sheetSnap}
          onSnapChange={handleSheetSnapChange}
          onObscuredChange={handleObscuredChange}
        >
          <SheetSegmentedControl activeTab={activeTab} onTabChange={handleTabChange} />
          {sidebarContents}
        </MobileLayout>
      ) : (
        <div className="layout layout--split">
          <SideRail activeTab={activeTab} onTabChange={handleTabChange} />
          <div className="panel-cards paper-grain">
            <div className="panel-cards__inner">
              {sidebarContents}
            </div>
          </div>
          <PanelSplitter
            value={cardsColumnWidth}
            min={CARDS_MIN_WIDTH}
            max={cardsColumnMax}
            offsetLeft={SIDE_RAIL_WIDTH}
            onChange={setCardsColumnWidth}
            onCommit={setCardsColumnWidth}
          />
          {/* Layout placeholder for the .panel-map grid cell. The visible
              MapView lives in .map-host--desktop above, positioned to
              fill this cell. Kept in DOM so the .layout--split grid math
              (4 columns) stays simple. */}
          <div className="panel-map" aria-hidden="true" />
        </div>
      )}

      <InstallPrompt />

      <ArrivedToast arrivedSignal={arrivedSignal} tripActive={tripActive} />
    </div>
  );
}
