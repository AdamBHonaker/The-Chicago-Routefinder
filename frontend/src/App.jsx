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
import { saveLocation, deleteLocation } from "./favorites.js";
import { useFavorites } from "./hooks/useFavorites.js";
import {
  GEO_OPTIONS,
  TRIP_GEO_OPTIONS,
  OFF_ROUTE_THRESHOLD_METERS,
  RETRY_DELAYS_MS,
  BYOK_IDLE_TIMEOUT_MS,
  REROUTE_SUPPRESSION_MS,
} from "./constants.js";
import { useApiQuery } from "./hooks/useApiQuery.js";
import { useLocalStorage } from "./hooks/useLocalStorage.js";
import { fetchWithRetry as _fetchWithRetry } from "./utils/fetchWithRetry.js";
import { haversineMeters, pointToSegmentMeters, legEndCoord, distanceToPath } from "./utils/tripGeometry.js";

// Falls back to localhost:8000 so `npm run dev` works out-of-the-box without a .env.local.
// Production builds always have VITE_BACKEND_URL set via .env.production / Vercel env vars.
// See frontend/.env.example for documentation. (TD-019)
const BACKEND_URL  = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

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

// ---------------------------------------------------------------------------
// LabelSavePanel — shared inline panel for naming and saving a favourite.
// Used by LocationInput (saving a location) and the route-save section.
// Pass prefix="route-label" to use the route-label-save-* CSS classes. (TD-034)
// ---------------------------------------------------------------------------

function LabelSavePanel({ value, onChange, onSave, onCancel, placeholder, showError, prefix = "label" }) {
  const { t } = useTranslation();
  return (
    <div className={`${prefix}-save-panel`}>
      <input
        type="text"
        className={`${prefix}-save-input`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); onSave(); }
          if (e.key === "Escape") onCancel();
        }}
        maxLength={30}
        placeholder={placeholder}
        autoFocus
      />
      <button type="button" className={`${prefix}-save-btn`} onClick={onSave}>
        {t("fav_save")}
      </button>
      <button type="button" className={`${prefix}-cancel-btn`} onClick={onCancel}>
        {t("fav_cancel")}
      </button>
      {showError && <span className="fav-limit-error">{t("fav_limit_reached")}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// LocationInput — wraps a text field with a saved-location star and dropdown.
//
// State-management flow (TD-027):
//   1. Editing — user types; each keystroke calls fetchAcSuggestions() which
//      debounces 200 ms then fires the /autocomplete endpoint via an
//      AbortController (previous in-flight request is cancelled first).
//   2. Autocomplete — results land in acSuggestions; ArrowUp/Down move
//      acActiveIndex; Enter or onMouseDown commits selectAcSuggestion().
//   3. Saved-location dropdown — when the field is focused with fewer than
//      2 chars but saved locations exist, the starred-locations list opens
//      (dropdownOpen=true). It collapses when acSuggestions appear.
//   4. Star / save — handleStarClick toggles saving mode; handleSaveLabel
//      commits the typed label to favorites.js persistence.
//   5. Blur timing — onBlur uses a 150 ms setTimeout before collapsing the
//      dropdown so that onMouseDown on a list item fires before the list
//      unmounts (a React synthetic-event ordering constraint).
// ---------------------------------------------------------------------------

function LocationInput({ value, onChange, placeholder, savedLocations, onSavedLocationsChange, showGeoBtn }) {
  const { t } = useTranslation();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [savingMode, setSavingMode] = useState(false);
  const [labelDraft, setLabelDraft] = useState("");
  const [limitError, setLimitError] = useState(false);
  const [geoState, setGeoState] = useState("idle"); // 'idle' | 'loading' | 'denied' | 'error'
  const limitTimerRef = useRef(null);
  const geoTimerRef = useRef(null);

  // Autocomplete state
  const [acSuggestions, setAcSuggestions] = useState([]);
  const [acActiveIndex, setAcActiveIndex] = useState(-1);
  const acDebounceRef = useRef(null);
  const acAbortRef = useRef(null);

  const isSaved = savedLocations.some((loc) => loc.value === value);
  const showStar = value.trim().length > 0;

  useEffect(() => () => {
    if (limitTimerRef.current) clearTimeout(limitTimerRef.current);
    if (geoTimerRef.current) clearTimeout(geoTimerRef.current);
    if (acDebounceRef.current) clearTimeout(acDebounceRef.current);
    if (acAbortRef.current) acAbortRef.current.abort();
  }, []);

  function fetchAcSuggestions(query) {
    if (acDebounceRef.current) clearTimeout(acDebounceRef.current);
    if (acAbortRef.current) acAbortRef.current.abort();
    if (query.trim().length < 2) {
      setAcSuggestions([]);
      setAcActiveIndex(-1);
      return;
    }
    acDebounceRef.current = setTimeout(async () => {
      const ctrl = new AbortController();
      acAbortRef.current = ctrl;
      try {
        const res = await fetch(
          `${BACKEND_URL}/autocomplete?q=${encodeURIComponent(query.trim())}`,
          { signal: ctrl.signal }
        );
        if (!res.ok) return;
        const data = await res.json();
        setAcSuggestions(data.suggestions || []);
        setAcActiveIndex(-1);
      } catch (err) {
        if (err.name !== "AbortError") setAcSuggestions([]);
      }
    }, 200);
  }

  function selectAcSuggestion(suggestion) {
    onChange(suggestion.value);
    setAcSuggestions([]);
    setAcActiveIndex(-1);
    if (acDebounceRef.current) clearTimeout(acDebounceRef.current);
    if (acAbortRef.current) acAbortRef.current.abort();
  }

  function handleGeoClick() {
    if (!navigator.geolocation) {
      setGeoState("error");
      geoTimerRef.current = setTimeout(() => setGeoState("idle"), 3000);
      return;
    }
    setGeoState("loading");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords = `${pos.coords.latitude.toFixed(6)},${pos.coords.longitude.toFixed(6)}`;
        onChange(coords);
        setGeoState("idle");
      },
      (err) => {
        const isDenied = err.code === err.PERMISSION_DENIED;
        setGeoState(isDenied ? "denied" : "error");
        if (!isDenied) {
          geoTimerRef.current = setTimeout(() => setGeoState("idle"), 4000);
        }
      },
      GEO_OPTIONS
    );
  }

  function handleStarClick() {
    if (isSaved) {
      const loc = savedLocations.find((l) => l.value === value);
      if (loc) onSavedLocationsChange(deleteLocation(loc.id, savedLocations));
    } else {
      setLabelDraft(value.slice(0, 30));
      setSavingMode(true);
    }
  }

  function handleSaveLabel() {
    const trimmedLabel = labelDraft.trim() || value.slice(0, 30);
    const next = saveLocation(trimmedLabel, value, savedLocations);
    if (next === null) {
      setLimitError(true);
      if (limitTimerRef.current) clearTimeout(limitTimerRef.current);
      limitTimerRef.current = setTimeout(() => { setLimitError(false); setSavingMode(false); }, 3000);
    } else {
      onSavedLocationsChange(next);
      setSavingMode(false);
    }
  }

  return (
    <>
      <div className="field-wrapper">
        <input
          type="search"
          inputMode="search"
          enterKeyHint="go"
          placeholder={placeholder}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            fetchAcSuggestions(e.target.value);
          }}
          onFocus={() => {
            if (value.trim().length >= 2) {
              fetchAcSuggestions(value);
            } else if (savedLocations.length > 0) {
              setDropdownOpen(true);
            }
          }}
          onBlur={() => setTimeout(() => {
            setDropdownOpen(false);
            setAcSuggestions([]);
            setAcActiveIndex(-1);
          }, 150)}
          onKeyDown={(e) => {
            if (acSuggestions.length === 0) return;
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setAcActiveIndex(i => Math.min(i + 1, acSuggestions.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setAcActiveIndex(i => Math.max(i - 1, -1));
            } else if (e.key === "Enter" && acActiveIndex >= 0) {
              e.preventDefault();
              selectAcSuggestion(acSuggestions[acActiveIndex]);
            } else if (e.key === "Escape") {
              setAcSuggestions([]);
              setAcActiveIndex(-1);
            }
          }}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="words"
        />
        {showStar && !savingMode && (
          <button
            type="button"
            className={`star-btn${isSaved ? " star-btn--saved" : ""}`}
            onClick={handleStarClick}
            aria-label={isSaved ? t("fav_unsave_location") : t("fav_save_location")}
            title={isSaved ? t("fav_unsave_location") : t("fav_save_location")}
          >
            {isSaved ? "★" : "☆"}
          </button>
        )}
        {acSuggestions.length > 0 && (
          <ul className="saved-dropdown" role="listbox" aria-label="Location suggestions">
            {acSuggestions.map((s, i) => (
              <li
                key={i}
                className={`saved-dropdown-item${i === acActiveIndex ? " saved-dropdown-item--active" : ""}`}
                role="option"
                aria-selected={i === acActiveIndex}
                onMouseDown={(e) => { e.preventDefault(); selectAcSuggestion(s); }}
              >
                <span className="saved-dropdown-label">{s.label}</span>
                <span className="ac-type-badge">
                  {s.type === "train" ? "Train" : s.type === "bus" ? "Bus" : "Place"}
                </span>
              </li>
            ))}
          </ul>
        )}
        {dropdownOpen && savedLocations.length > 0 && acSuggestions.length === 0 && (
          <ul className="saved-dropdown" role="listbox">
            {savedLocations.slice(0, 5).map((loc) => (
              <li key={loc.id} className="saved-dropdown-item" role="option">
                <span
                  className="saved-dropdown-label"
                  onMouseDown={(e) => { e.preventDefault(); onChange(loc.value); setDropdownOpen(false); }}
                >
                  {loc.label}
                </span>
                <button
                  type="button"
                  className="saved-dropdown-delete"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    const next = deleteLocation(loc.id, savedLocations);
                    onSavedLocationsChange(next);
                    if (next.length === 0) setDropdownOpen(false);
                  }}
                  aria-label={t("fav_delete")}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {showGeoBtn && !savingMode && (
        <div className="geo-btn-row">
          <button
            type="button"
            className={`geo-btn${geoState === "loading" ? " geo-btn--loading" : ""}${geoState === "denied" || geoState === "error" ? " geo-btn--error" : ""}`}
            onClick={handleGeoClick}
            disabled={geoState === "loading"}
            aria-label={t("geo_btn_label")}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
            </svg>
            {geoState === "loading"
              ? t("geo_loading")
              : geoState === "denied"
              ? t("geo_denied")
              : geoState === "error"
              ? t("geo_error")
              : t("geo_btn_label")}
          </button>
        </div>
      )}
      {showGeoBtn && geoState === "denied" && (
        <div className="geo-denied-banner" role="alert">
          <span>{t("geo_denied_help")}</span>
          <button
            type="button"
            className="geo-denied-dismiss"
            onClick={() => {
              if (geoTimerRef.current) clearTimeout(geoTimerRef.current);
              setGeoState("idle");
            }}
            aria-label="Dismiss"
          >×</button>
        </div>
      )}
      {savingMode && (
        <LabelSavePanel
          value={labelDraft}
          onChange={setLabelDraft}
          onSave={handleSaveLabel}
          onCancel={() => setSavingMode(false)}
          placeholder={t("fav_label_placeholder")}
          showError={limitError}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// SavedRoutesPanel — collapsible panel listing saved origin/destination pairs.
// ---------------------------------------------------------------------------

function SavedRoutesPanel({ savedRoutes, onDeleteRoute, onRouteSelect }) {
  const { t } = useTranslation();
  return (
    <div className="saved-routes-panel">
      <p className="saved-routes-panel-heading">{t("fav_saved_routes_heading")}</p>
      {savedRoutes.length === 0 ? (
        <p className="saved-routes-empty">{t("fav_routes_empty")}</p>
      ) : (
        savedRoutes.map((route) => (
          <div key={route.id} className="saved-route-row">
            <span className="saved-route-label">{route.label}</span>
            <button
              type="button"
              className="saved-route-go"
              onClick={() => onRouteSelect(route.origin, route.destination)}
            >
              {t("fav_go")}
            </button>
            <button
              type="button"
              className="saved-route-delete"
              onClick={() => onDeleteRoute(route.id)}
              aria-label={t("fav_delete")}
            >
              ×
            </button>
          </div>
        ))
      )}
    </div>
  );
}

export default function App() {
  const { t, i18n } = useTranslation();

  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [transitMode, setTransitMode] = useState("All");

  const [result, setResult] = useState(null);   // { recommendation, routes }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [selectedRouteIndex, setSelectedRouteIndex] = useState(0);

  // BYOK state — key persisted to sessionStorage (clears on tab close, safer than
  // localStorage which any script on the origin could read).
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
    routeLimitError,
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
    ),
    [serviceAlerts, dismissedAlertIds]
  );

  // Fire-and-forget ping on mount for DAU counting — silent on failure.
  useEffect(() => { fetch(`${BACKEND_URL}/ping`); }, []);

  // Fetch service alerts on mount (Feature Service Alerts)
  useEffect(() => {
    fetch(`${BACKEND_URL}/alerts`)
      .then((res) => res.ok ? res.json() : { alerts: [] })
      .then((data) => setServiceAlerts(data.alerts || []))
      .catch(() => {});
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
                {/* Bus fullness filter — hidden until CTA populates the psgld field
                    in Bus Tracker API responses. All current responses return psgld=""
                    so the filter has no effect. Re-enable when CTA enables the data:
                    1. Restore: const [busFullness, setBusFullness] = useState("All");
                    2. Add bus_fullness: busFullness to the request body in handleSubmit.
                    3. Uncomment this select.
                <select
                  value={busFullness}
                  onChange={(e) => setBusFullness(e.target.value)}
                  aria-label="Bus fullness"
                >
                  <option value="All">Any fullness</option>
                  <option value="Empty">Empty</option>
                  <option value="Half-Full">Half-full</option>
                  <option value="Full">Full</option>
                </select>
                */}
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
              alerts={serviceAlerts.filter((a) => !dismissedAlertIds.has(a.alert_id))}
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
