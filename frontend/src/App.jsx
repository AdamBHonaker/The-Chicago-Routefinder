import { useState, useRef, useEffect, useMemo, useCallback } from "react";
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
import {
  BACKEND_URL,
  TRIP_GEO_OPTIONS,
  OFF_ROUTE_THRESHOLD_METERS,
  RETRY_DELAYS_MS,
  BYOK_IDLE_TIMEOUT_MS,
  REROUTE_SUPPRESSION_MS,
} from "./constants.js";
import LabelSavePanel from "./components/LabelSavePanel.jsx";
import LocationInput from "./components/LocationInput.jsx";
import SavedRoutesPanel from "./components/SavedRoutesPanel.jsx";
import { useApiQuery } from "./hooks/useApiQuery.js";
import { useLocalStorage } from "./hooks/useLocalStorage.js";
import { fetchWithRetry as _fetchWithRetry } from "./utils/fetchWithRetry.js";
import { haversineMeters, pointToSegmentMeters, legEndCoord, distanceToPath } from "./utils/tripGeometry.js";

// ---------------------------------------------------------------------------
// BYOK feature flag — set VITE_BYOK_ENABLED=true in frontend/.env to show
// the settings panel and include the user's key in requests.
// The backend must also have BYOK_ENABLED=true to honour the key.
// ---------------------------------------------------------------------------
const BYOK_ENABLED = import.meta.env.VITE_BYOK_ENABLED === "true";

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

function renderMarkdown(text) {
  // Strip common markdown so plain text reaches the rider
  return text
    .replace(/^#{1,3}\s+/gm, "")              // strip heading markers (# / ## / ###)
    .replace(/\*\*(.*?)\*\*/g, "$1")           // strip bold **text**
    .replace(/\*([^*]+)\*/g, "$1")             // strip italic *text*
    .replace(/_([^_]+)_/g, "$1")               // strip italic _text_
    .replace(/`([^`]+)`/g, "$1")               // strip inline code `text`
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")   // strip link [label](url) → label
    .replace(/^[-*>]\s+/gm, "")               // strip bullet / blockquote markers
    .trim();
}

// Trip-geometry helpers (haversineMeters, pointToSegmentMeters, legEndCoord,
// distanceToPath) are imported from utils/tripGeometry.js (TD-041).
const WALK_SPEED_FACTORS = { slow: 0.75, standard: 1.0, brisk: 1.25 };

// LabelSavePanel, LocationInput, and SavedRoutesPanel are in frontend/src/components/.


export default function App() {
  const { t, i18n } = useTranslation();

  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [transitMode, setTransitMode] = useState("All");

  const [result, setResult] = useState(null);   // { recommendation, routes }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [selectedRouteIndex, setSelectedRouteIndex] = useState(0);

  // BYOK state — key persisted to sessionStorage (clears on tab close, NOT across tabs).
  // sessionStorage and localStorage are equally readable by any same-origin JavaScript,
  // including supply-chain-compromised npm deps. Accepted trade-off for BYOK UX; feature
  // is opt-in and off by default (VITE_BYOK_ENABLED). Auto-cleared after idle timeout below.
  const [byokKey, setByokKey] = useState(() =>
    BYOK_ENABLED ? (sessionStorage.getItem("byok_api_key") || "") : ""
  );
  const [settingsOpen, setSettingsOpen] = useState(false);

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
  const activeAlertRoutes = useMemo(
    () => new Set(
      serviceAlerts
        .filter((a) => !dismissedAlertIds.has(a.alert_id))
        .flatMap((a) => a.routes)
        .map((r) => r.replace(" Line", ""))
    ),
    [serviceAlerts, dismissedAlertIds]
  );
  const visibleAlerts = useMemo(
    () => serviceAlerts.filter((a) => !dismissedAlertIds.has(a.alert_id)),
    [serviceAlerts, dismissedAlertIds]
  );

  // Fire-and-forget ping on mount for DAU counting — silent on failure.
  useEffect(() => { fetch(`${BACKEND_URL}/ping`); }, []);

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
    document.documentElement.dir = RTL_LANGS.has(i18n.language) ? "rtl" : "ltr";
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

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

  // Auto-clear BYOK key after 30 minutes of idle (no mouse/keyboard activity).
  // Only active when a key is actually stored. (BUG-014)
  useEffect(() => {
    if (!BYOK_ENABLED || !byokKey) return;
    let idleTimer;
    const resetTimer = () => {
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => {
        sessionStorage.removeItem("byok_api_key");
        setByokKey("");
      }, BYOK_IDLE_TIMEOUT_MS);
    };
    window.addEventListener("mousemove", resetTimer);
    window.addEventListener("keydown", resetTimer);
    resetTimer();
    return () => {
      clearTimeout(idleTimer);
      window.removeEventListener("mousemove", resetTimer);
      window.removeEventListener("keydown", resetTimer);
    };
  }, [byokKey]);

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
  const [tripActive, setTripActive]         = useState(false);
  const [userPosition, setUserPosition]     = useState(null);   // {lat, lng} | null
  const [activeLegIndex, setActiveLegIndex] = useState(null);   // number | null
  const [completedSteps, setCompletedSteps] = useState(new Set());
  const [isOffRoute, setIsOffRoute]         = useState(false);
  const [tripGeoError, setTripGeoError]     = useState(false);
  const [onVehicle, setOnVehicle]           = useState(false);
  const watchIdRef            = useRef(null);
  const suppressRerouteUntil  = useRef(0);
  // Ref mirror of activeLegIndex — lets the GPS effect read the current value
  // synchronously without queuing fake setActiveLegIndex updates. (OPT-FE-005)
  const activeLegIndexRef = useRef(null);
  // Ref mirror of onVehicle for synchronous reads in the GPS effect.
  const onVehicleRef = useRef(false);

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

  // Clear "on vehicle" whenever the active leg changes. `setOnVehicle` and
  // `onVehicleRef` are stable (state setter + ref) — omitting them is correct.
  useEffect(() => {
    setOnVehicle(false);
    onVehicleRef.current = false;
  }, [activeLegIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── GPS position update handler ────────────────────────────────────────────
  // processTripPosition — orchestrates all three GPS-triggered state updates
  // in a single named function so their ordering and interdependencies are
  // auditable in one place. (TD-036)
  //
  //   1. Leg advancement — when the user is within 60 m of the current leg's
  //      endpoint (150 m on a transit leg when "on vehicle" is toggled on,
  //      since GPS can lag behind a moving vehicle), activeLegIndex advances.
  //      We read activeLegIndexRef — not the state — so passes 2 and 3 see the
  //      already-advanced index from pass 1 within the same invocation.
  //
  //   2. Walk-step completion — for the active walk leg, any step whose start
  //      coordinate is within 30 m of the user is added to completedSteps (a
  //      Set keyed by "legIdx-stepIdx" strings).
  //
  //   3. Off-route detection — during walk legs only, distanceToPath() computes
  //      the minimum perpendicular distance to the leg path. Exceeding
  //      OFF_ROUTE_THRESHOLD_METERS shows the off-route banner. Skipped while
  //      the suppression timer is active (set when the user dismisses the banner).
  //
  // All three passes are independent — leg advancement shouldn't skip step
  // completion, and off-route detection should still run after a step completes.
  // ---------------------------------------------------------------------------
  function processTripPosition(pos, route) {
    const { legs } = route;

    // 1. Advance active leg when within proximity of its endpoint.
    let idx = activeLegIndexRef.current ?? 0;  // read ref, not state (OPT-FE-005)
    const leg = legs[idx];
    if (leg) {
      const end = legEndCoord(leg);
      // Wider radius when user confirmed on vehicle — GPS lags behind movement.
      const advanceRadius = (onVehicleRef.current && leg.type === "transit") ? 150 : 60;
      if (end && haversineMeters(pos, end) < advanceRadius) {
        const next = Math.min(idx + 1, legs.length - 1);
        if (next !== idx) {
          activeLegIndexRef.current = next;
          setActiveLegIndex(next);
          idx = next;
        }
      }
    }

    // 2. Walk step completion for the active walk leg.
    const activeLeg = legs[idx];
    if (activeLeg?.type === "walk" && activeLeg.directions?.length) {
      setCompletedSteps(prev => {
        let changed = false;
        const next = new Set(prev);
        activeLeg.directions.forEach((step, si) => {
          if (step.start_lat !== undefined && !next.has(`${idx}-${si}`)) {
            if (haversineMeters(pos, { lat: step.start_lat, lng: step.start_lon }) < 30) {
              next.add(`${idx}-${si}`);
              changed = true;
            }
          }
        });
        return changed ? next : prev;
      });
    }

    // 3. Off-route detection (only during walk legs).
    if (activeLeg?.type === "walk" && Date.now() > suppressRerouteUntil.current) {
      setIsOffRoute(distanceToPath(pos, activeLeg.path) > OFF_ROUTE_THRESHOLD_METERS);
    }
  }

  // Intentionally dep on `userPosition` only — all other values are accessed
  // via refs inside processTripPosition so this effect fires on GPS tick
  // without re-subscribing when unrelated state changes.
  useEffect(() => {
    if (!tripActive || !userPosition || !result) return;
    const route = result.routes?.[selectedRouteIndex];
    if (!route?.legs?.length) return;
    processTripPosition(userPosition, route);
  }, [userPosition]); // eslint-disable-line react-hooks/exhaustive-deps

  // Shared /recommend API call — used by both handleSubmit and handleReroute
  // so the request body, error handling, and setResult shape stay in one place.
  async function callRecommendAPI(originStr) {
    const res = await fetchWithRetry(
      `${BACKEND_URL}/recommend`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin:       originStr,
          destination:  destination.trim(),
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
    setResult({
      recommendation: data.recommendation != null ? renderMarkdown(data.recommendation) : null,
      routes: data.routes || [],
      alerts: data.alerts || [],
      originCoords: data.origin_coords,
      destCoords:   data.dest_coords,
      busDataPartial: (data.bus_errors > 0) && !(data.bus_arrivals?.length),
      weather: data.weather || null,
    });
  }

  function fadePhoto() {
    setPhotoFading(true);
    photoFadeTimer.current = setTimeout(() => {
      setPhotoMounted(false);
      setPhotoFading(false);
    }, 1000);
  }

  async function handleReroute() {
    if (!userPosition) return;
    const gpsOrigin = `${userPosition.lat.toFixed(6)},${userPosition.lng.toFixed(6)}`;

    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    setOrigin(gpsOrigin);
    setIsOffRoute(false);
    activeLegIndexRef.current = 0;
    setActiveLegIndex(0);
    setCompletedSteps(new Set());
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
      await callRecommendAPI(gpsOrigin);
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

  async function handleSubmit(e) {
    e.preventDefault();
    if (!origin.trim() || !destination.trim()) return;

    // Stop any active trip before starting a fresh search
    stopTrip();

    // Reset route save UI
    setSavingRoute(false);
    setRouteLimitError(false);

    // Cancel any in-flight request from a previous search
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    // Cancel any in-progress photo fade from a previous search
    if (photoFadeTimer.current) clearTimeout(photoFadeTimer.current);
    setSelectedRouteIndex(0);
    searchIdRef.current += 1;

    // Mount a fresh photo for this search (new key → new random pick)
    setPhotoKey((k) => k + 1);
    setPhotoMounted(true);
    setPhotoFading(false);

    setLoading(true);
    setError("");
    setResult(null);

    try {
      await callRecommendAPI(origin.trim());
      fadePhoto();
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message || t("error_generic"));
      fadePhoto();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <div className="layout layout--split">
        <div className="panel-cards">
          <header className="header">
            <div className="header-top">
              <h1>{t("app_title")}</h1>
              <div className="filters">
                <button
                  className={`settings-trigger${byokKey ? " settings-trigger--active" : ""}`}
                  onClick={() => setSettingsOpen((v) => !v)}
                  aria-label={byokKey ? t("aria_settings_active") : t("aria_settings")}
                  title={byokKey ? t("aria_settings_active") : t("aria_settings")}
                >
                  ⚙
                </button>
                <button
                  type="button"
                  className={`saved-routes-toggle${showSavedRoutes ? " saved-routes-toggle--open" : ""}`}
                  onClick={() => setShowSavedRoutes((v) => !v)}
                  aria-label={t("fav_saved_routes_heading")}
                  title={t("fav_saved_routes_heading")}
                >
                  ⭐
                </button>
                <select
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
                  value={i18n.language}
                  onChange={(e) => i18n.changeLanguage(e.target.value)}
                  aria-label={t("aria_language")}
                >
                  {SUPPORTED.map((code) => (
                    <option key={code} value={code}>{LANGUAGE_NAMES[code]}</option>
                  ))}
                </select>
              </div>
            </div>
            <p className="tagline">{t("tagline")}</p>
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

          {showSavedRoutes && (
            <SavedRoutesPanel
              savedRoutes={savedRoutes}
              onDeleteRoute={handleDeleteRoute}
              onRouteSelect={(orig, dest) => {
                setOrigin(orig);
                setDestination(dest);
                setShowSavedRoutes(false);
              }}
            />
          )}

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

            <form className="form" onSubmit={handleSubmit}>
              <label>
                <span>{t("label_from")}</span>
                <LocationInput
                  value={origin}
                  onChange={setOrigin}
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
                  onClick={() => { setOrigin(destination); setDestination(origin); }}
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
                          href="https://www.transitchicago.com/travel-information/alerts/"
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
                  <div className="off-route-banner" role="alert">
                    <span className="off-route-message">
                      {t("trip_off_route_message")}
                    </span>
                    <div className="off-route-actions">
                      <button
                        className="off-route-reroute-btn"
                        onClick={handleReroute}
                      >
                        {t("trip_reroute_btn")}
                      </button>
                      <button
                        className="off-route-dismiss-btn"
                        onClick={() => {
                          setIsOffRoute(false);
                          suppressRerouteUntil.current = Date.now() + REROUTE_SUPPRESSION_MS;
                        }}
                      >
                        {t("trip_dismiss_btn")}
                      </button>
                    </div>
                  </div>
                )}

                {result.routes.length > 0 && (
                  <section className="routes-section">
                    <div className="routes-section-header">
                      <h2 className="routes-heading">{t("route_options_heading")}</h2>
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
                        <RouteCard
                          key={`${searchIdRef.current}-${i}`}
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
                          onDismissTripGeoError={() => setTripGeoError(false)}
                          onVehicle={onVehicle && i === selectedRouteIndex}
                          onToggleVehicle={toggleOnVehicle}
                          pinnedStops={pinnedStops}
                          onPinToggle={handlePinToggle}
                          activeAlertRoutes={activeAlertRoutes}
                        />
                      );
                    })}
                  </section>
                )}
              </div>
            )}
          </main>
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
    </div>
  );
}
