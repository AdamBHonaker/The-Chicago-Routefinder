import { lazy, Suspense, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import SignalLamp from "./SignalLamp.jsx";
import Wordmark from "./Wordmark.jsx";
// LanguagePicker pulls in 6 raw continent SVG strings — only load it when the
// continent picker is enabled and rendered (OPT-FE-204).
const LanguagePicker = lazy(() => import("./LanguagePicker/LanguagePicker.jsx"));
import {
  MASTHEAD_EPOCH_YEAR,
  CONTINENT_PICKER_ENABLED,
  TRANSLATION_FEEDBACK_URL,
} from "../constants.js";
import { SUPPORTED, LANGUAGE_NAMES, RESEARCH_LOCALES } from "../i18n.js";
import {
  formatMastheadDate,
  formatMastheadVol,
  msUntilNextMidnight,
} from "../utils/mastheadInfo.js";

// Newspaper-style masthead. Date and VOL are computed on render and re-rendered
// at local midnight (TD-FE-010) so a long-lived PWA session crossing midnight
// shows today's date instead of the load-time date.
//
// Language UI rules (Feature LocaleExpansion):
//   - Flat <select> ships by default. The continent-first LanguagePicker
//     replaces it when CONTINENT_PICKER_ENABLED is true.
//   - When the active locale is in RESEARCH_LOCALES (the 8 low-resource
//     codes), a machine-translated review badge renders below the picker.
//     The badge text comes from t("mt_review_notice"); it MUST appear in
//     the active locale, never English fallback. If a user sees it in
//     English, that's a missing translation in the locale's
//     translation.json — fix the file, not the UX.
export default function Masthead({
  liveDataActive,
  byokActive,
  showSavedRoutes,
  transitMode,
  onTransitModeChange,
  onToggleSettings,
  onToggleSavedRoutes,
}) {
  const { t, i18n } = useTranslation();
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setTimeout(() => setNow(new Date()), msUntilNextMidnight(new Date()));
    return () => clearTimeout(id);
  }, [now]);

  const mastheadDate = formatMastheadDate(now);
  const mastheadVol  = formatMastheadVol(now, MASTHEAD_EPOCH_YEAR);

  const activeCode = i18n.resolvedLanguage ?? i18n.language;
  const showMtBadge = RESEARCH_LOCALES.has(activeCode);

  return (
    <header className="header">
      <div className="masthead-folio">
        <span className="masthead-folio-date">{mastheadDate}</span>
        <span className="masthead-folio-vol">{mastheadVol}</span>
        {liveDataActive && (
          <SignalLamp ariaLabel={t("psb_live_data")} className="masthead-signal" />
        )}
      </div>
      <div className="masthead-rule" aria-hidden="true" />
      <div className="masthead-title-row">
        <Wordmark />
      </div>
      <div className="masthead-controls">
        <button
          className={`btn-ghost-icon${byokActive ? " btn-ghost-icon--active" : ""}`}
          onClick={onToggleSettings}
          aria-label={byokActive ? t("aria_settings_active") : t("aria_settings")}
          title={byokActive ? t("aria_settings_active") : t("aria_settings")}
        >
          ⚙
        </button>
        <button
          type="button"
          className={`btn-ghost-icon${showSavedRoutes ? " btn-ghost-icon--active" : ""}`}
          onClick={onToggleSavedRoutes}
          aria-label={t("fav_saved_routes_heading")}
          title={t("fav_saved_routes_heading")}
        >
          ⭐
        </button>
        <select
          className="masthead-select"
          value={transitMode}
          onChange={(e) => onTransitModeChange(e.target.value)}
          aria-label={t("aria_transit_mode")}
        >
          <option value="All">{t("mode_all")}</option>
          <option value="Train">{t("mode_train")}</option>
          <option value="Bus">{t("mode_bus")}</option>
          <option value="Walk">{t("mode_walk")}</option>
        </select>
        {CONTINENT_PICKER_ENABLED ? (
          <Suspense fallback={null}>
            <LanguagePicker />
          </Suspense>
        ) : (
          <select
            className="masthead-select"
            value={activeCode}
            onChange={(e) => i18n.changeLanguage(e.target.value)}
            aria-label={t("aria_language")}
          >
            {SUPPORTED.map((code) => (
              <option key={code} value={code}>{LANGUAGE_NAMES[code]}</option>
            ))}
          </select>
        )}
      </div>
      {showMtBadge && (
        <p className="mt-review-notice" role="note">
          {t("mt_review_notice")}
          <a href={TRANSLATION_FEEDBACK_URL} target="_blank" rel="noopener noreferrer">
            {t("feedback_link_label")}
          </a>
        </p>
      )}
      <p className="masthead-tagline">{t("tagline")}</p>
    </header>
  );
}
