import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import "./App.css";
import MapView from "./MapView.jsx";
import { LINE_COLORS, BUS_DIRECTION_COLORS } from "./constants.js";
import { SUPPORTED } from "./i18n.js";

const BACKEND_URL  = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// BYOK feature flag — set VITE_BYOK_ENABLED=true in frontend/.env to show
// the settings panel and include the user's key in requests.
// The backend must also have BYOK_ENABLED=true to honour the key.
// ---------------------------------------------------------------------------
const BYOK_ENABLED = import.meta.env.VITE_BYOK_ENABLED === "true";

// ---------------------------------------------------------------------------
// Transit photo manifest — add entries here once photos are sourced (HUMAN_TODO)
// ---------------------------------------------------------------------------

const PHOTOS = [
  { src: "/transit-photos/red-line-howard.jpg",   caption: "Red Line — Howard" },
  { src: "/transit-photos/loop-elevated.jpg",      caption: "The Loop — Elevated Track" },
  { src: "/transit-photos/blue-line-ohare.jpg",    caption: "Blue Line — O'Hare" },
  { src: "/transit-photos/state-lake.jpg",         caption: "State/Lake — The Loop" },
  { src: "/transit-photos/wrigley-addison.jpg",    caption: "Addison — Wrigley Field" },
];

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

function TransitPhoto({ fading }) {
  const [photo] = useState(
    () => PHOTOS[Math.floor(Math.random() * PHOTOS.length)]
  );
  const [failed, setFailed] = useState(false);

  if (failed) return null;

  return (
    <div className={`transit-photo${fading ? " transit-photo--fading" : ""}`}>
      <img
        src={photo.src}
        alt={photo.caption}
        className="transit-photo-img"
        onError={() => setFailed(true)}
      />
      <p className="transit-photo-caption">{photo.caption}</p>
    </div>
  );
}

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

function formatBlocks(b, blockType, t) {
  if (!blockType) return b === 1 ? `1 ${t("block_singular")}` : `${b} ${t("block_plural")}`;
  if (blockType === "long") return `${b} ${b === 1 ? t("long_block_singular") : t("long_block_plural")}`;
  return `${b} ${b === 1 ? t("short_block_singular") : t("short_block_plural")}`;
}

function WalkLegItem({ leg, index }) {
  const { t } = useTranslation();
  const [stepsOpen, setStepsOpen] = useState(false);
  const hasSteps = leg.directions && leg.directions.length > 1;

  const label =
    leg.from === "Your location"
      ? t("walk_from_origin", { minutes: leg.minutes, to: leg.to })
      : leg.to === "Your destination"
      ? t("walk_to_destination", { minutes: leg.minutes })
      : t("walk_transfer", { minutes: leg.minutes });

  const showExit = leg.exit_label && leg.to === "Your destination";

  return (
    <li key={index} className="leg leg-walk">
      <span className="leg-icon">🚶</span>
      <span className="leg-walk-body">
        <span className="leg-text">{label}</span>
        {showExit && (
          <span className="leg-exit-label">{t("exit_label_prefix")} {leg.exit_label}</span>
        )}
        {hasSteps && (
          <button
            className="leg-steps-toggle"
            onClick={() => setStepsOpen((v) => !v)}
            aria-expanded={stepsOpen}
          >
            {stepsOpen ? t("steps_hide") : t("steps_show")}
          </button>
        )}
        {stepsOpen && (
          <ol className="leg-steps">
            {leg.directions.map((step, si) => (
              <li key={si} className="leg-step">
                <span className="leg-step-text">
                  {si === 0 ? t("step_walk") : t("step_head")}
                  {step.direction_full ? ` ${step.direction_full}` : ""}
                  {` ${t("step_along")} `}
                  <span className="leg-step-street">{step.street}</span>
                  {` ${t("step_for")} `}
                  {formatBlocks(step.blocks ?? 1, step.block_type, t)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </span>
    </li>
  );
}

function RouteLegs({ legs }) {
  let seenTransit = false;
  return (
    <ol className="route-legs">
      {legs.map((leg, i) => {
        if (leg.type === "walk") {
          return <WalkLegItem key={i} leg={leg} index={i} />;
        }
        const isBus = leg.line in BUS_DIRECTION_COLORS;
        const color = isBus
          ? BUS_DIRECTION_COLORS[leg.line]
          : (LINE_COLORS[leg.line] || "#4a9eff");
        const pillLabel = isBus
          ? leg.line_code
          : leg.line?.replace(" Line", "");
        const isTransferLeg = seenTransit;
        seenTransit = true;
        const xferWait = leg.transfer_wait_minutes;
        const xferNote =
          isTransferLeg && xferWait !== undefined && xferWait !== null
            ? (xferWait === 0 ? "⏱ Due" : `⏱ ${xferWait} min wait`)
            : null;
        return (
          <li key={i} className="leg leg-transit">
            {xferNote && <span className="transfer-wait-note">{xferNote}</span>}
            <span className="leg-pill" style={{ background: color }}>
              {pillLabel}
            </span>
            <span className="leg-text">
              {leg.from} → {leg.to}
              <span className="leg-duration"> · {leg.minutes} min</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function RouteCard({ route, index, isFirst, isSelected, onSelect }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(isFirst);
  const waitNote =
    route.wait_minutes === null ? ""
    : route.wait_minutes === 0  ? ` · ${t("wait_due")}`
    : ` · ${t("wait_minutes", { minutes: route.wait_minutes })}`;
  const xferNote =
    route.transfers === 0
      ? t("label_no_transfers")
      : route.transfers === 1
      ? t("label_1_transfer")
      : t("label_n_transfers", { count: route.transfers });

  return (
    <div className={`route-card${isFirst ? " route-card--best" : ""}${isSelected ? " route-card--selected" : ""}`}>
      <button
        className="route-card-header"
        onClick={() => { onSelect(); setExpanded((v) => !v); }}
        aria-expanded={expanded}
      >
        <div className="route-card-summary">
          {isFirst && <span className="route-badge">{t("badge_best")}</span>}
          <span className="route-total">{t("label_min_total", { minutes: route.total_minutes })}</span>
          <span className="route-meta">{xferNote}{waitNote}</span>
        </div>
        <span className="route-chevron">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && <RouteLegs legs={route.legs} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// BYOK Settings Panel
// Only rendered when BYOK_ENABLED === true and the user opens the panel.
// ---------------------------------------------------------------------------

function SettingsPanel({ apiKey, onSave, onClose, aiEnabled, onAiChange }) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(apiKey);
  const isValid = !draft.trim() || draft.trim().startsWith("sk-ant-");

  return (
    <div className="settings-panel" role="dialog" aria-label={t("settings_title")}>
      <div className="settings-header">
        <h2 className="settings-title">{t("settings_title")}</h2>
        <button className="settings-close" onClick={onClose} aria-label={t("aria_close_settings")}>
          ✕
        </button>
      </div>

      <label className="setting-row">
        <span>AI Explanation</span>
        <input
          type="checkbox"
          checked={aiEnabled}
          onChange={(e) => onAiChange(e.target.checked)}
        />
      </label>
      <span className="settings-hint">
        When on, Claude adds a plain-English summary of your route options.
      </span>

      {BYOK_ENABLED && (
        <>
          <div className="settings-warning" role="alert">
            <strong>⚠ Security notice:</strong> Your key is stored in this browser. Only use this feature on trusted personal devices.
          </div>
          <label className="settings-label">
            <span className="settings-label-text">{t("settings_label_api_key")}</span>
            <span className="settings-hint">{t("settings_hint_api_key")}</span>
            <input
              type="password"
              className={`settings-input${!isValid ? " settings-input--error" : ""}`}
              placeholder="sk-ant-…"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoComplete="off"
              spellCheck={false}
            />
            {!isValid && (
              <span className="settings-error">{t("settings_error_key_format")}</span>
            )}
          </label>
          <div className="settings-actions">
            <button
              className="settings-save"
              onClick={() => { onSave(draft.trim()); onClose(); }}
              disabled={!isValid}
            >
              {t("settings_btn_save")}
            </button>
            {apiKey && (
              <button
                className="settings-clear"
                onClick={() => { onSave(""); onClose(); }}
              >
                {t("settings_btn_remove_key")}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function LoadingSkeleton() {
  const { t } = useTranslation();
  return (
    <div className="skeleton-wrapper" aria-busy="true" aria-label={t("aria_loading")}>
      <div className="skeleton skeleton-line skeleton-line--long" />
      <div className="skeleton skeleton-line skeleton-line--medium" />
      <div className="skeleton skeleton-line skeleton-line--short" />
      <div className="skeleton skeleton-card" />
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

  // RTL support — flip document direction when an RTL language is selected.
  useEffect(() => {
    document.documentElement.dir = RTL_LANGS.has(i18n.language) ? "rtl" : "ltr";
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

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

  // Photo state — managed entirely within handleSubmit via photoFadeTimer ref
  const [photoMounted, setPhotoMounted] = useState(false);
  const [photoFading, setPhotoFading] = useState(false);
  const [photoKey, setPhotoKey] = useState(0);  // increment to force new random photo
  const photoFadeTimer = useRef(null);
  const abortRef = useRef(null);
  // Incremented on every new search so RouteCard instances are remounted,
  // resetting their expanded state to the isFirst default.
  const searchIdRef = useRef(0);

  useEffect(() => {
    return () => {
      if (photoFadeTimer.current) clearTimeout(photoFadeTimer.current);
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!origin.trim() || !destination.trim()) return;

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
      const res = await fetch(`${BACKEND_URL}/recommend`, {
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
      });

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

          <main className="main">
            <form className="form" onSubmit={handleSubmit}>
              <label>
                <span>{t("label_from")}</span>
                <input
                  type="search"
                  inputMode="search"
                  enterKeyHint="go"
                  placeholder={t("placeholder_location")}
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                  autoComplete="off"
                  autoCorrect="off"
                  autoCapitalize="words"
                />
              </label>

              <label>
                <span>{t("label_to")}</span>
                <input
                  type="search"
                  inputMode="search"
                  enterKeyHint="go"
                  placeholder={t("placeholder_location")}
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  autoComplete="off"
                  autoCorrect="off"
                  autoCapitalize="words"
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

                {result.routes.length > 0 && (
                  <section className="routes-section">
                    <h2 className="routes-heading">{t("route_options_heading")}</h2>
                    {result.routes.map((route, i) => (
                      <RouteCard
                        key={`${searchIdRef.current}-${i}`}
                        route={route}
                        index={i}
                        isFirst={i === 0}
                        isSelected={i === selectedRouteIndex}
                        onSelect={() => setSelectedRouteIndex(i)}
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
          />
        </div>
      </div>
    </div>
  );
}
