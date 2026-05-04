import { useState, useRef, useEffect, useMemo, useCallback, Fragment, lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import "./App.css";
// MapView pulls in maplibre-gl (~210 KB gz) — keep it out of the eager
// bundle. Suspense fallback is a blank panel (panel-map already has the
// app background colour) so cold loads don't flash a skeleton.
const MapView = lazy(() => import("./MapView.jsx"));
import LoadingSkeleton from "./components/LoadingSkeleton.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";
import RouteCard from "./components/RouteCard.jsx";
import PinnedStopsBoard from "./components/PinnedStopsBoard.jsx";
import ServiceAlertsBar from "./components/ServiceAlertsBar.jsx";
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
import SavedRoutesPanel from "./components/SavedRoutesPanel.jsx";
import SharedRouteBanner from "./components/SharedRouteBanner.jsx";
import SideRail from "./components/SideRail.jsx";
import { useApiQuery } from "./hooks/useApiQuery.js";
import { useLocalStorage } from "./hooks/useLocalStorage.js";
import { fetchWithRetry as _fetchWithRetry } from "./utils/fetchWithRetry.js";
import { renderMarkdown } from "./utils/renderMarkdown.js";
import { extractTransitLines } from "./utils/routeUtils.js";

// Thin wrapper so call-sites don't need to pass RETRY_DELAYS_MS explicitly.
// Full implementation and JSDoc live in utils/fetchWithRetry.js (TD-040).
function fetchWithRetry(url, options, onRetrying) {
  return _fetchWithRetry(url, options, RETRY_DELAYS_MS, onRetrying);
}

export default function App() {
  const { t, i18n } = useTranslation();
  useDocumentLanguage();

  const [origin, setOrigin] = useState("");
  const [originGeoCoords, setOriginGeoCoords] = useState(null);
  const [destination, setDestination] = useState("");
  const [transitMode, setTransitMode] = useState("All");

  const [result, setResult] = useState(null);   // { recommendation, routes }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [selectedRouteIndex, setSelectedRouteIndex] = useState(0);
  const [isSharedLink, setIsSharedLink] = useState(false);

  // BYOK state — key persisted to sessionStorage (clears on tab close, NOT across tabs).
  // sessionStorage and localStorage are equally readable by any same-origin JavaScript,
  // including supply-chain-compromised npm deps. Accepted trade-off for BYOK UX; feature
  // is opt-in and off by default (VITE_BYOK_ENABLED). Auto-cleared after idle timeout below.
  const [byokKey, setByokKey] = useState(() =>
    BYOK_ENABLED ? (sessionStorage.getItem("byok_api_key") || "") : ""
  );
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("home"); // mobile tab bar; ignored on desktop

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
  const pinnedArrivalsFetcher = useCallback((signal) => {
    const params = pinnedStops.map((s) => `stops=${s.type}:${s.stop_id}`).join("&");
    return fetch(`${BACKEND_URL}/stop-arrivals?${params}`, { signal });
  }, [pinnedStops]);
  const { data: pinnedArrivalsData, refetch: refetchPinnedArrivals } = useApiQuery(
    pinnedArrivalsFetcher,
    [pinnedStops],
    { refetchInterval: 60000, enabled: pinnedStops.length > 0 },
  );
  const pinnedArrivals = pinnedArrivalsData?.arrivals || {};

  // Service Alerts — fetch + dismissal state extracted to useServiceAlerts (TD-FE-006)
  const { undismissedAlerts, dismiss: handleAlertDismiss } = useServiceAlerts();

  const activeAlertRoutes = useMemo(
    () => new Set(
      undismissedAlerts
        .flatMap((a) => a.routes ?? [])
        .map((r) => r.replace(" Line", ""))
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
    return new Set(lines.map((l) => l.isBus ? l.lineCode : l.line?.replace(" Line", "")));
  }, [routeTransitLines, selectedRouteIndex]);

  const visibleAlerts = useMemo(() => {
    if (!currentRouteLines) return [];
    return undismissedAlerts.filter((a) =>
      (a.routes ?? []).some((r) => currentRouteLines.has(r.replace(" Line", "")))
    );
  }, [undismissedAlerts, currentRouteLines]);

  // Fire-and-forget ping on mount for DAU/session counting — silent on failure.
  // credentials: "include" sends/receives the FEAT-001 session cookie cross-origin
  // (Vercel → Railway). Backend CORS is configured with allow_credentials=True.
  useEffect(() => {
    fetch(`${BACKEND_URL}/ping`, { credentials: "include" }).catch(() => {});
  }, []);

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

  // ── Feature ArrivedToast ─────────────────────────────────────────────────
  const [showArrivedToast, setShowArrivedToast] = useState(false);

  // Reset toast when the trip ends.
  useEffect(() => {
    if (!tripActive) setShowArrivedToast(false);
  }, [tripActive]);

  // Auto-dismiss after 5 s; clear the timer on unmount or re-trigger.
  useEffect(() => {
    if (!showArrivedToast) return;
    const id = setTimeout(() => setShowArrivedToast(false), 5000);
    return () => clearTimeout(id);
  }, [showArrivedToast]);

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
    });
    return routes.length;
  }

  async function handleReroute() {
    if (!userPosition) return;
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

    await performSearch(originGeoCoords ?? origin.trim(), destination.trim());
  }

  const effectiveShowSavedRoutes = showSavedRoutes || activeTab === "saved";

  const handleTabChange = (id) => {
    setActiveTab(id);
    if (id !== "saved") setShowSavedRoutes(false);
  };

  return (
    <div className="app" data-active-tab={activeTab}>
      <div className="layout layout--split">
        <SideRail activeTab={activeTab} onTabChange={handleTabChange} />
        <div className="panel-cards paper-grain">
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
            <SettingsPanel
              apiKey={byokKey}
              onSave={handleSaveByokKey}
              onClose={() => setSettingsOpen(false)}
              aiEnabled={aiEnabled}
              onAiChange={setAiEnabled}
              walkSpeed={walkSpeed}
              onWalkSpeedChange={setWalkSpeed}
            />
          )}

          {effectiveShowSavedRoutes && (
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
                if (activeTab === "saved") setActiveTab("home");
              }}
            />
          )}

          {activeTab === "alerts" && (
            <main className="main tab-alerts-view">
              <TwoToneHeading
                capsKey="caps_advisories"
                headingKey="alerts_tab_heading"
                italicWords={1}
                className="tab-alerts-view__heading"
              />
              {undismissedAlerts.length === 0 ? (
                <p className="tab-empty">{t("alerts_empty")}</p>
              ) : (
                <ServiceAlertsBar
                  alerts={undismissedAlerts}
                  onDismiss={handleAlertDismiss}
                />
              )}
            </main>
          )}

          {activeTab !== "alerts" && activeTab !== "saved" && (
          <main className="main">
            <PinnedStopsBoard
              stops={pinnedStops}
              arrivals={pinnedArrivals}
              onUnpin={handleUnpin}
              onRefresh={refetchPinnedArrivals}
            />

            <ServiceAlertsBar
              alerts={visibleAlerts}
              onDismiss={handleAlertDismiss}
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
                  onClick={() => { setOrigin(destination); setDestination(origin); setOriginGeoCoords(null); }}
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

                {result.alerts?.length > 0 && (
                  <div className="alerts-section">
                    {result.alerts.slice(0, 3).map((alert) => (
                      <div
                        key={alert.alert_id}
                        className={`alert-item${alert.is_major ? " alert-item--major" : " alert-item--minor"}`}
                      >
                        <span className="alert-headline">{alert.headline}</span>
                        {alert.impact && (
                          <span className="alert-impact">{alert.impact}</span>
                        )}
                      </div>
                    ))}
                    {result.alerts.length > 3 && (
                      <p className="alerts-more">
                        <a
                          href="https://www.transitchicago.com/alerts/"
                          target="_blank"
                          rel="noreferrer"
                        >
                          {t("alerts_more", { count: result.alerts.length - 3 })}
                        </a>
                      </p>
                    )}
                  </div>
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
                        onClick={dismissOffRoute}
                      >
                        {t("trip_dismiss_btn")}
                      </button>
                    </div>
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
                            onSelect={() => { setSelectedRouteIndex(i); stopTrip(); }}
                            tripActive={tripActive && i === selectedRouteIndex}
                            activeLegIndex={activeLegIndex}
                            completedSteps={completedSteps}
                            onStartTrip={startTrip}
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
                          />
                        </Fragment>
                      );
                    })}
                  </section>
                )}
              </div>
            )}
          </main>
          )}
        </div>

        <div className="panel-map">
          <Suspense fallback={null}>
            <MapView
              route={result?.routes?.[selectedRouteIndex] ?? null}
              originCoords={result?.originCoords ?? null}
              destCoords={result?.destCoords ?? null}
              userPosition={userPosition}
              tripActive={tripActive}
              activeLegIndex={activeLegIndex}
              activeTab={activeTab}
              onArrived={() => setShowArrivedToast(true)}
            />
          </Suspense>
        </div>
      </div>

      {showArrivedToast && (
        <div
          className="special-dispatch special-dispatch--arrived"
          role="alert"
          onClick={() => setShowArrivedToast(false)}
        >
          <span className="special-dispatch__kicker">{t("map_arrived_kicker")}</span>
          <p className="special-dispatch__body">{t("map_arrived_body")}</p>
        </div>
      )}

      <nav className="tab-bar" aria-label={t("aria_main_nav")}>
        {[
          { id: "home",   label: t("tab_home") },
          { id: "map",    label: t("tab_map") },
          { id: "alerts", label: t("tab_alerts") },
          { id: "saved",  label: t("tab_saved") },
        ].map(({ id, label }) => (
          <button
            key={id}
            type="button"
            className={`tab-bar__tab${activeTab === id ? " tab-bar__tab--active" : ""}`}
            onClick={() => handleTabChange(id)}
            aria-current={activeTab === id ? "page" : undefined}
          >
            <span className="tab-bar__label">{label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
