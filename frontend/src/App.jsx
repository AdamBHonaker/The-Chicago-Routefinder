import { useState, useRef, useEffect, useMemo, useCallback, Fragment } from "react";
import { useTranslation } from "react-i18next";
import "./App.css";
import MapView from "./MapView.jsx";
import { SUPPORTED } from "./i18n.js";
import TransitPhoto from "./components/TransitPhoto.jsx";
import LoadingSkeleton from "./components/LoadingSkeleton.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";
import RouteCard from "./components/RouteCard.jsx";
import PinnedStopsBoard from "./components/PinnedStopsBoard.jsx";
import ServiceAlertsBar from "./components/ServiceAlertsBar.jsx";
import WeatherStrip from "./components/WeatherStrip.jsx";
import { useFavorites } from "./hooks/useFavorites.js";
import { useTripTracker } from "./hooks/useTripTracker.js";
import { useByokIdleClear } from "./hooks/useByokIdleClear.js";
import {
  BACKEND_URL,
  RETRY_DELAYS_MS,
  BYOK_ENABLED,
  PHOTO_FADE_MS,
  MASTHEAD_EPOCH_YEAR,
} from "./constants.js";
import LabelSavePanel from "./components/LabelSavePanel.jsx";
import LocationInput from "./components/LocationInput.jsx";
import SavedRoutesPanel from "./components/SavedRoutesPanel.jsx";
import SharedRouteBanner from "./components/SharedRouteBanner.jsx";
import SideRail from "./components/SideRail.jsx";
import SignalLamp from "./components/SignalLamp.jsx";
import { useApiQuery } from "./hooks/useApiQuery.js";
import { useLocalStorage } from "./hooks/useLocalStorage.js";
import { fetchWithRetry as _fetchWithRetry } from "./utils/fetchWithRetry.js";
import { renderMarkdown } from "./utils/renderMarkdown.js";

// Thin wrapper so call-sites don't need to pass RETRY_DELAYS_MS explicitly.
// Full implementation and JSDoc live in utils/fetchWithRetry.js (TD-040).
function fetchWithRetry(url, options, onRetrying) {
  return _fetchWithRetry(url, options, RETRY_DELAYS_MS, onRetrying);
}

// Native-script names shown in the language selector so speakers can find their language.
const LANGUAGE_NAMES = {
  en:  "English",
  es:  "Español",
  fr:  "Français",
  it:  "Italiano",
  pl:  "Polski",
  ro:  "Română",
  uk:  "Українська",
  ru:  "Русский",
  zh:  "中文（普通话）",
  yue: "粤语",
  ja:  "日本語",
  ko:  "한국어",
  tl:  "Filipino",
  vi:  "Tiếng Việt",
  hi:  "हिंदी",
  gu:  "ગુજરાતી",
  pa:  "ਪੰਜਾਬੀ",
  ne:  "नेपाली",
  ur:  "اردو",
  ar:  "العربية",
  ps:  "پښتو",
  yo:  "Yorùbá",
};

const RTL_LANGS = new Set(["ar", "ur", "ps"]);

const WALK_SPEED_FACTORS = { slow: 0.75, standard: 1.0, brisk: 1.25 };

// LabelSavePanel, LocationInput, and SavedRoutesPanel are in frontend/src/components/.

// ── Masthead helpers ─────────────────────────────────────────────────────────
function _toRoman(n) {
  const vals = [10, 9, 5, 4, 1];
  const syms = ["X", "IX", "V", "IV", "I"];
  let r = "";
  for (let i = 0; i < vals.length; i++) {
    while (n >= vals[i]) { r += syms[i]; n -= vals[i]; }
  }
  return r;
}
function _dayOfYear(d) {
  return Math.floor((d - new Date(d.getFullYear(), 0, 0)) / 864e5);
}
const _now = new Date();
const MASTHEAD_DATE = _now.toLocaleDateString("en-US", {
  weekday: "long", month: "long", day: "numeric",
}).toUpperCase();
const MASTHEAD_VOL = `VOL. ${_toRoman(_now.getFullYear() - MASTHEAD_EPOCH_YEAR)} · NO. ${_dayOfYear(_now)}`;


export default function App() {
  const { t, i18n } = useTranslation();

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

  // Pinned Stops state managed by useFavorites above; arrivals fetched below.

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

  // Service Alerts state (Feature Service Alerts)
  const [serviceAlerts, setServiceAlerts] = useState([]);
  const [dismissedAlertIds, setDismissedAlertIds] = useState(() => {
    try {
      return new Set(JSON.parse(sessionStorage.getItem("dismissed_alert_ids") || "[]"));
    } catch {
      return new Set();
    }
  });
  const undismissedAlerts = useMemo(
    () => serviceAlerts.filter((a) => !dismissedAlertIds.has(a.alert_id)),
    [serviceAlerts, dismissedAlertIds]
  );
  const activeAlertRoutes = useMemo(
    () => new Set(
      undismissedAlerts
        .flatMap((a) => a.routes ?? [])
        .map((r) => r.replace(" Line", ""))
    ),
    [undismissedAlerts]
  );
  const currentRouteLines = useMemo(() => {
    const route = result?.routes?.[selectedRouteIndex];
    if (!route?.legs) return null;
    const lines = new Set();
    for (const leg of route.legs) {
      if (leg.type !== "transit") continue;
      const id = leg.line_code?.replace(" Line", "");
      if (id) lines.add(id);
    }
    return lines.size > 0 ? lines : null;
  }, [result, selectedRouteIndex]);

  const visibleAlerts = useMemo(() => {
    if (!currentRouteLines) return undismissedAlerts;
    return undismissedAlerts.filter((a) =>
      (a.routes ?? []).some((r) => currentRouteLines.has(r.replace(" Line", "")))
    );
  }, [undismissedAlerts, currentRouteLines]);

  // Fire-and-forget ping on mount for DAU counting — silent on failure.
  useEffect(() => { fetch(`${BACKEND_URL}/ping`).catch(() => {}); }, []);

  // Fetch service alerts on mount (Feature Service Alerts)
  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${BACKEND_URL}/alerts`, { signal: ctrl.signal })
      .then((res) => res.ok ? res.json() : { alerts: [] })
      .then((data) => setServiceAlerts(data.alerts || []))
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

  // RTL support — flip document direction when an RTL language is selected.
  useEffect(() => {
    const lang = i18n.resolvedLanguage ?? i18n.language;
    document.documentElement.dir = RTL_LANGS.has(lang) ? "rtl" : "ltr";
    document.documentElement.lang = lang;
  }, [i18n.resolvedLanguage, i18n.language]);

  function handleAiChange(value) {
    setAiEnabled(value);
  }

  function handleWalkSpeedChange(speed) {
    setWalkSpeed(speed);
  }

  function handleAlertDismiss(alertId) {
    setDismissedAlertIds((prev) => {
      const next = new Set(prev);
      next.add(alertId);
      try {
        sessionStorage.setItem("dismissed_alert_ids", JSON.stringify([...next]));
      } catch {}
      return next;
    });
  }

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

  // Photo state — managed entirely within handleSubmit via photoFadeTimer ref
  const [photoMounted, setPhotoMounted] = useState(false);
  const [photoFading, setPhotoFading] = useState(false);
  const [photoKey, setPhotoKey] = useState(0);  // increment to force new random photo
  const photoFadeTimer = useRef(null);
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

  // Shared /recommend API call — used by both performSearch and handleReroute
  // so the request body, error handling, and setResult shape stay in one place.
  // Returns the number of routes in the response (used by performSearch for route-index pre-selection).
  async function callRecommendAPI(originStr, destinationStr) {
    const res = await fetchWithRetry(
      `${BACKEND_URL}/recommend`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin:       originStr,
          destination:  destinationStr,
          transit_mode: transitMode,
          ai_enabled:   aiEnabled,
          language:     i18n.language,
          ...(BYOK_ENABLED && byokKey ? { anthropic_api_key: byokKey } : {}),
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

  function fadePhoto() {
    setPhotoFading(true);
    photoFadeTimer.current = setTimeout(() => {
      setPhotoMounted(false);
      setPhotoFading(false);
    }, PHOTO_FADE_MS);
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

    if (photoFadeTimer.current) clearTimeout(photoFadeTimer.current);
    setPhotoKey((k) => k + 1);
    setPhotoMounted(true);
    setPhotoFading(false);

    setLoading(true);
    setError("");
    setResult(null);

    try {
      await callRecommendAPI(gpsOrigin, destination.trim());
      fadePhoto();
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message || t("error_generic"));
      fadePhoto();
    } finally {
      setLoading(false);
    }
  }
  // ── End Feature Trip ──────────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (photoFadeTimer.current) clearTimeout(photoFadeTimer.current);
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

    if (photoFadeTimer.current) clearTimeout(photoFadeTimer.current);
    setSelectedRouteIndex(0);
    searchIdRef.current += 1;

    setPhotoKey((k) => k + 1);
    setPhotoMounted(true);
    setPhotoFading(false);

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const routeCount = await callRecommendAPI(fromStr, toStr);
      fadePhoto();
      pushUrlState(fromStr, toStr);
      if (preferredRouteIndex > 0 && routeCount > preferredRouteIndex) {
        setSelectedRouteIndex(preferredRouteIndex);
      }
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message || t("error_generic"));
      fadePhoto();
    } finally {
      setLoading(false);
    }
  }

  // Parse share URL params on mount and auto-submit the pre-filled search.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const from = params.get("from");
    const to = params.get("to");
    const routeIndex = parseInt(params.get("route") ?? "0", 10) || 0;
    if (from && to) {
      setOrigin(from);
      setDestination(to);
      setIsSharedLink(true);
      performSearch(from, to, routeIndex);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
          <header className="header">
            <div className="masthead-folio">
              <span className="masthead-folio-date">{MASTHEAD_DATE}</span>
              <span className="masthead-folio-vol">{MASTHEAD_VOL}</span>
              {result && result.routes.length > 0 && (
                <SignalLamp ariaLabel={t("psb_live_data")} className="masthead-signal" />
              )}
            </div>
            <div className="masthead-rule" aria-hidden="true" />
            <div className="masthead-title-row">
              <h1 className="masthead-title" aria-label={t("app_title")}>
                <span className="masthead-title-italic">The Chicago</span>
                <span className="masthead-title-roman"> Routefinder<span className="masthead-period">.</span></span>
              </h1>
            </div>
            <div className="masthead-controls">
              <button
                className={`btn-ghost-icon${byokKey ? " btn-ghost-icon--active" : ""}`}
                onClick={() => setSettingsOpen((v) => !v)}
                aria-label={byokKey ? t("aria_settings_active") : t("aria_settings")}
                title={byokKey ? t("aria_settings_active") : t("aria_settings")}
              >
                ⚙
              </button>
              <button
                type="button"
                className={`btn-ghost-icon${showSavedRoutes ? " btn-ghost-icon--active" : ""}`}
                onClick={() => setShowSavedRoutes((v) => !v)}
                aria-label={t("fav_saved_routes_heading")}
                title={t("fav_saved_routes_heading")}
              >
                ⭐
              </button>
              <select
                className="masthead-select"
                value={transitMode}
                onChange={(e) => setTransitMode(e.target.value)}
                aria-label={t("aria_transit_mode")}
              >
                <option value="All">{t("mode_all")}</option>
                <option value="Train">{t("mode_train")}</option>
                <option value="Bus">{t("mode_bus")}</option>
                <option value="Walk">{t("mode_walk")}</option>
              </select>
              <select
                className="masthead-select"
                value={i18n.resolvedLanguage ?? i18n.language}
                onChange={(e) => i18n.changeLanguage(e.target.value)}
                aria-label={t("aria_language")}
              >
                {SUPPORTED.map((code) => (
                  <option key={code} value={code}>{LANGUAGE_NAMES[code]}</option>
                ))}
              </select>
            </div>
            <p className="masthead-tagline">{t("tagline")}</p>
          </header>

          {settingsOpen && (
            <SettingsPanel
              apiKey={byokKey}
              onSave={handleSaveByokKey}
              onClose={() => setSettingsOpen(false)}
              aiEnabled={aiEnabled}
              onAiChange={handleAiChange}
              walkSpeed={walkSpeed}
              onWalkSpeedChange={handleWalkSpeedChange}
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
              {visibleAlerts.length === 0 ? (
                <p className="tab-empty">{t("alerts_empty")}</p>
              ) : (
                <ServiceAlertsBar
                  alerts={visibleAlerts}
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
                  <div className="special-dispatch special-dispatch--delay" role="alert">
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
          {photoMounted && (
            <TransitPhoto key={photoKey} fading={photoFading} />
          )}
          <MapView
            route={result?.routes?.[selectedRouteIndex] ?? null}
            originCoords={result?.originCoords ?? null}
            destCoords={result?.destCoords ?? null}
            userPosition={userPosition}
            tripActive={tripActive}
          />
        </div>
      </div>

      <nav className="tab-bar" aria-label={t("aria_main_nav")}>
        {[
          { id: "home",   icon: "📍", label: t("tab_home") },
          { id: "map",    icon: "🗺",  label: t("tab_map") },
          { id: "alerts", icon: "⚠",  label: t("tab_alerts") },
          { id: "saved",  icon: "⭐", label: t("tab_saved") },
        ].map(({ id, icon, label }) => (
          <button
            key={id}
            type="button"
            className={`tab-bar__tab${activeTab === id ? " tab-bar__tab--active" : ""}`}
            onClick={() => handleTabChange(id)}
            aria-current={activeTab === id ? "page" : undefined}
          >
            <span className="tab-bar__icon" aria-hidden="true">{icon}</span>
            <span className="tab-bar__label">{label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
