import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import "./App.css";
import MapView from "./MapView.jsx";
import { SUPPORTED } from "./i18n.js";
import TransitPhoto from "./components/TransitPhoto.jsx";
import LoadingSkeleton from "./components/LoadingSkeleton.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";
import RouteCard from "./components/RouteCard.jsx";
import {
  getSavedLocations,
  saveLocation,
  deleteLocation,
  getSavedRoutes,
  saveRoute,
  deleteRoute,
} from "./favorites.js";

const BACKEND_URL  = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// BYOK feature flag — set VITE_BYOK_ENABLED=true in frontend/.env to show
// the settings panel and include the user's key in requests.
// The backend must also have BYOK_ENABLED=true to honour the key.
// ---------------------------------------------------------------------------
const BYOK_ENABLED = import.meta.env.VITE_BYOK_ENABLED === "true";

// ---------------------------------------------------------------------------
// Retry helper for the /recommend endpoint (TD-014)
// Retries up to 3 times with 1 s, 2 s, 4 s delays on 5xx and network errors.
// 4xx errors and AbortError are not retried (not transient).
// ---------------------------------------------------------------------------
const _RETRY_DELAYS = [1000, 2000, 4000];

async function fetchWithRetry(url, options, onRetrying) {
  for (let attempt = 0; attempt <= _RETRY_DELAYS.length; attempt++) {
    if (options.signal?.aborted) throw new DOMException("Aborted", "AbortError");
    let res;
    try {
      res = await fetch(url, options);
    } catch (err) {
      if (err.name === "AbortError") throw err;
      if (attempt < _RETRY_DELAYS.length) {
        onRetrying?.(attempt + 1);
        await new Promise(r => setTimeout(r, _RETRY_DELAYS[attempt]));
        continue;
      }
      throw err;
    }
    if (res.ok || res.status < 500) return res; // success or non-retryable client error
    if (attempt < _RETRY_DELAYS.length) {
      onRetrying?.(attempt + 1);
      await new Promise(r => setTimeout(r, _RETRY_DELAYS[attempt]));
      continue;
    }
    return res; // exhausted retries — caller handles the error response
  }
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
    .replace(/^#{1,3}\s+/gm, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/^[-*>]\s+/gm, "")
    .trim();
}

// ---------------------------------------------------------------------------
// LocationInput — wraps a text field with a saved-location star and dropdown.
// ---------------------------------------------------------------------------

function LocationInput({ value, onChange, placeholder, savedLocations, onSavedLocationsChange }) {
  const { t } = useTranslation();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [savingMode, setSavingMode] = useState(false);
  const [labelDraft, setLabelDraft] = useState("");
  const [limitError, setLimitError] = useState(false);
  const limitTimerRef = useRef(null);

  const isSaved = savedLocations.some((loc) => loc.value === value);
  const showStar = value.trim().length > 0;

  useEffect(() => () => { if (limitTimerRef.current) clearTimeout(limitTimerRef.current); }, []);

  function handleStarClick() {
    if (isSaved) {
      const loc = savedLocations.find((l) => l.value === value);
      if (loc) onSavedLocationsChange(deleteLocation(loc.id));
    } else {
      setLabelDraft(value.slice(0, 30));
      setSavingMode(true);
    }
  }

  function handleSaveLabel() {
    const trimmedLabel = labelDraft.trim() || value.slice(0, 30);
    const next = saveLocation(trimmedLabel, value);
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
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => { if (savedLocations.length > 0) setDropdownOpen(true); }}
          onBlur={() => setTimeout(() => setDropdownOpen(false), 150)}
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
        {dropdownOpen && savedLocations.length > 0 && (
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
                    const next = deleteLocation(loc.id);
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
      {savingMode && (
        <div className="label-save-panel">
          <input
            type="text"
            className="label-save-input"
            value={labelDraft}
            onChange={(e) => setLabelDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { e.preventDefault(); handleSaveLabel(); }
              if (e.key === "Escape") setSavingMode(false);
            }}
            maxLength={30}
            placeholder={t("fav_label_placeholder")}
            autoFocus
          />
          <button type="button" className="label-save-btn" onClick={handleSaveLabel}>
            {t("fav_save")}
          </button>
          <button type="button" className="label-cancel-btn" onClick={() => setSavingMode(false)}>
            {t("fav_cancel")}
          </button>
          {limitError && <span className="fav-limit-error">{t("fav_limit_reached")}</span>}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// SavedRoutesPanel — collapsible panel listing saved origin/destination pairs.
// ---------------------------------------------------------------------------

function SavedRoutesPanel({ savedRoutes, onSavedRoutesChange, onRouteSelect }) {
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
              onClick={() => onSavedRoutesChange(deleteRoute(route.id))}
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

  // AI toggle — persisted to localStorage so it survives page reloads.
  // Defaults to false (off) so new users get faster route cards without AI latency.
  const [aiEnabled, setAiEnabled] = useState(
    () => localStorage.getItem("cta_ai_enabled") === "true"
  );

  // Favorites state — synced to localStorage on every save/delete.
  const [savedLocations, setSavedLocations] = useState(() => getSavedLocations());
  const [savedRoutes, setSavedRoutes] = useState(() => getSavedRoutes());
  const [showSavedRoutes, setShowSavedRoutes] = useState(false);

  // Route save UI — inline label input that appears in the results section.
  const [savingRoute, setSavingRoute] = useState(false);
  const [routeLabelDraft, setRouteLabelDraft] = useState("");
  const [routeLimitError, setRouteLimitError] = useState(false);
  const routeLimitTimerRef = useRef(null);

  // Fire-and-forget ping on mount for DAU counting — silent on failure.
  useEffect(() => { fetch(`${BACKEND_URL}/ping`); }, []);

  // RTL support — flip document direction when an RTL language is selected.
  useEffect(() => {
    document.documentElement.dir = RTL_LANGS.has(i18n.language) ? "rtl" : "ltr";
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

  useEffect(() => () => { if (routeLimitTimerRef.current) clearTimeout(routeLimitTimerRef.current); }, []);

  // Derived state — whether the current query's route is already saved.
  const currentOrigin = origin.trim();
  const currentDest = destination.trim();
  const currentRouteSaved = savedRoutes.some(
    (r) => r.origin === currentOrigin && r.destination === currentDest
  );

  function handleToggleSaveRoute() {
    if (currentRouteSaved) {
      const entry = savedRoutes.find(
        (r) => r.origin === currentOrigin && r.destination === currentDest
      );
      if (entry) setSavedRoutes(deleteRoute(entry.id));
    } else {
      setRouteLabelDraft(`${currentOrigin} → ${currentDest}`.slice(0, 30));
      setSavingRoute(true);
    }
  }

  function handleSaveRoute() {
    const label = routeLabelDraft.trim() || `${currentOrigin} → ${currentDest}`.slice(0, 30);
    const next = saveRoute(label, currentOrigin, currentDest);
    if (next === null) {
      setRouteLimitError(true);
      if (routeLimitTimerRef.current) clearTimeout(routeLimitTimerRef.current);
      routeLimitTimerRef.current = setTimeout(() => {
        setRouteLimitError(false);
        setSavingRoute(false);
      }, 3000);
    } else {
      setSavedRoutes(next);
      setSavingRoute(false);
      setRouteLimitError(false);
    }
  }

  function handleAiChange(value) {
    setAiEnabled(value);
    localStorage.setItem("cta_ai_enabled", String(value));
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
      }, 30 * 60 * 1000);
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
  const watchIdRef            = useRef(null);
  const suppressRerouteUntil  = useRef(0);

  function haversineMeters(a, b) {
    const R = 6371000;
    const dLat = (b.lat - a.lat) * Math.PI / 180;
    const dLng = (b.lng - a.lng) * Math.PI / 180;
    const lat1r = a.lat * Math.PI / 180;
    const lat2r = b.lat * Math.PI / 180;
    const s = Math.sin(dLat / 2) ** 2 + Math.cos(lat1r) * Math.cos(lat2r) * Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
  }

  function legEndCoord(leg) {
    if (leg.type === "transit") {
      const c = leg.to_coords;
      if (!c) return null;
      return { lat: c[0], lng: c[1] };
    }
    const path = leg.path;
    if (!path?.length) return null;
    const last = path[path.length - 1];
    return { lat: last[0], lng: last[1] };
  }

  function startTrip() {
    if (!navigator.geolocation) return;
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => setUserPosition({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      (err) => console.error("[trip] GPS error:", err),
      { enableHighAccuracy: true, maximumAge: 15000, timeout: 10000 },
    );
    setTripActive(true);
    setActiveLegIndex(0);
    setCompletedSteps(new Set());
    setIsOffRoute(false);
    suppressRerouteUntil.current = 0;
  }

  function stopTrip() {
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    setTripActive(false);
    setUserPosition(null);
    setActiveLegIndex(null);
    setCompletedSteps(new Set());
    setIsOffRoute(false);
  }

  // Process each GPS position update while trip is active.
  useEffect(() => {
    if (!tripActive || !userPosition || !result) return;
    const route = result.routes?.[selectedRouteIndex];
    if (!route?.legs?.length) return;

    // 1. Advance active leg when within 60 m of its endpoint.
    setActiveLegIndex(prev => {
      if (prev === null) return prev;
      const leg = route.legs[prev];
      if (!leg) return prev;
      const end = legEndCoord(leg);
      if (!end) return prev;
      if (haversineMeters(userPosition, end) < 60)
        return Math.min(prev + 1, route.legs.length - 1);
      return prev;
    });

    // 2. Walk step completion for the active walk leg.
    setActiveLegIndex(current => {
      const idx = current ?? 0;
      const activeLeg = route.legs[idx];
      if (activeLeg?.type === "walk" && activeLeg.directions?.length) {
        setCompletedSteps(prev => {
          let changed = false;
          const next = new Set(prev);
          activeLeg.directions.forEach((step, si) => {
            if (step.start_lat !== undefined && !next.has(`${idx}-${si}`)) {
              if (haversineMeters(userPosition, { lat: step.start_lat, lng: step.start_lon }) < 30) {
                next.add(`${idx}-${si}`);
                changed = true;
              }
            }
          });
          return changed ? next : prev;
        });
      }
      return current; // no change to activeLegIndex
    });

    // 3. Off-route detection (only during walk legs).
    setActiveLegIndex(current => {
      const idx = current ?? 0;
      const activeLeg = route.legs[idx];
      if (activeLeg?.type === "walk" && Date.now() > suppressRerouteUntil.current) {
        const minDist = route.legs.reduce((min, leg) => {
          const end = legEndCoord(leg);
          return end ? Math.min(min, haversineMeters(userPosition, end)) : min;
        }, Infinity);
        setIsOffRoute(minDist > 400);
      }
      return current;
    });
  }, [userPosition]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleReroute() {
    if (!userPosition) return;
    const gpsOrigin = `${userPosition.lat.toFixed(6)},${userPosition.lng.toFixed(6)}`;

    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    setOrigin(gpsOrigin);
    setIsOffRoute(false);
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
      const res = await fetchWithRetry(
        `${BACKEND_URL}/recommend`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            origin:       gpsOrigin,
            destination:  destination.trim(),
            transit_mode: transitMode,
            ai_enabled:   aiEnabled,
            language:     i18n.language,
            ...(BYOK_ENABLED && byokKey ? { anthropic_api_key: byokKey } : {}),
          }),
          signal: abortRef.current.signal,
        },
        (attempt) => setError(`Network error — retrying... (${attempt}/${_RETRY_DELAYS.length})`),
      );

      if (!res.ok) {
        let msg = `Service error (${res.status} ${res.statusText})`;
        try { const data = await res.json(); msg = data.detail || msg; } catch {}
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
      });

      setPhotoFading(true);
      photoFadeTimer.current = setTimeout(() => {
        setPhotoMounted(false);
        setPhotoFading(false);
      }, 1000);
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message || t("error_generic"));
      setPhotoFading(true);
      photoFadeTimer.current = setTimeout(() => {
        setPhotoMounted(false);
        setPhotoFading(false);
      }, 1000);
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
      const res = await fetchWithRetry(
        `${BACKEND_URL}/recommend`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            origin:       origin.trim(),
            destination:  destination.trim(),
            transit_mode: transitMode,
            ai_enabled:   aiEnabled,
            language:     i18n.language,
            ...(BYOK_ENABLED && byokKey ? { anthropic_api_key: byokKey } : {}),
          }),
          signal: abortRef.current.signal,
        },
        (attempt) => setError(`Network error — retrying... (${attempt}/${_RETRY_DELAYS.length})`),
      );

      if (!res.ok) {
        let msg = `Service error (${res.status} ${res.statusText})`;
        try {
          const data = await res.json();
          msg = data.detail || msg;
        } catch {
          // Response body is not JSON (e.g. Railway/nginx 502 gateway error)
        }
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
      });

      // Fade photo out once loading completes, regardless of result
      setPhotoFading(true);
      photoFadeTimer.current = setTimeout(() => {
        setPhotoMounted(false);
        setPhotoFading(false);
      }, 1000);

    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message || t("error_generic"));
      // Also fade photo on errors so it doesn't block map interaction
      setPhotoFading(true);
      photoFadeTimer.current = setTimeout(() => {
        setPhotoMounted(false);
        setPhotoFading(false);
      }, 1000);
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
            />
          )}

          {showSavedRoutes && (
            <SavedRoutesPanel
              savedRoutes={savedRoutes}
              onSavedRoutesChange={setSavedRoutes}
              onRouteSelect={(orig, dest) => {
                setOrigin(orig);
                setDestination(dest);
                setShowSavedRoutes(false);
              }}
            />
          )}

          <main className="main">
            <form className="form" onSubmit={handleSubmit}>
              <label>
                <span>{t("label_from")}</span>
                <LocationInput
                  value={origin}
                  onChange={setOrigin}
                  placeholder={t("placeholder_location")}
                  savedLocations={savedLocations}
                  onSavedLocationsChange={setSavedLocations}
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
                      You appear to be off your planned route.
                    </span>
                    <div className="off-route-actions">
                      <button
                        className="off-route-reroute-btn"
                        onClick={handleReroute}
                      >
                        Re-route from here
                      </button>
                      <button
                        className="off-route-dismiss-btn"
                        onClick={() => {
                          setIsOffRoute(false);
                          suppressRerouteUntil.current = Date.now() + 90_000;
                        }}
                      >
                        Dismiss
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
                      <div className="route-label-save-panel">
                        <input
                          type="text"
                          className="route-label-save-input"
                          value={routeLabelDraft}
                          onChange={(e) => setRouteLabelDraft(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") { e.preventDefault(); handleSaveRoute(); }
                            if (e.key === "Escape") setSavingRoute(false);
                          }}
                          maxLength={30}
                          placeholder={t("fav_route_label_placeholder")}
                          autoFocus
                        />
                        <button type="button" className="route-label-save-btn" onClick={handleSaveRoute}>
                          {t("fav_save")}
                        </button>
                        <button type="button" className="route-label-cancel-btn" onClick={() => setSavingRoute(false)}>
                          {t("fav_cancel")}
                        </button>
                        {routeLimitError && <span className="fav-limit-error">{t("fav_limit_reached")}</span>}
                      </div>
                    )}
                    {result.routes.map((route, i) => (
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
                      />
                    ))}
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
