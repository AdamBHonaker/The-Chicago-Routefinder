import { useState } from "react";
import { useTranslation } from "react-i18next";
import { isValidByokKey } from "../constants.js";

const BYOK_ENABLED = import.meta.env.VITE_BYOK_ENABLED === "true";

const WALK_SPEEDS = ["slow", "standard", "brisk"];

export default function SettingsPanel({ apiKey, onSave, onClose, aiEnabled, onAiChange, walkSpeed, onWalkSpeedChange }) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(apiKey);
  const isValid = isValidByokKey(draft);

  return (
    <div className="settings-panel" role="dialog" aria-label={t("settings_title")}>
      <div className="settings-header">
        <h2 className="settings-title">{t("settings_title")}</h2>
        <button className="settings-close" onClick={onClose} aria-label={t("aria_close_settings")}>
          ✕
        </button>
      </div>

      <label className="setting-row">
        <span>{t("settings_ai_explanation_label")}</span>
        <input
          type="checkbox"
          checked={aiEnabled}
          onChange={(e) => onAiChange(e.target.checked)}
        />
      </label>
      <span className="settings-hint">
        {t("settings_ai_explanation_hint")}
      </span>

      <div className="setting-row">
        <span>{t("settings_walk_speed_label")}</span>
        <div className="walk-speed-toggle">
          {WALK_SPEEDS.map((speed) => (
            <button
              key={speed}
              className={`walk-speed-btn${walkSpeed === speed ? " walk-speed-btn--active" : ""}`}
              onClick={() => onWalkSpeedChange(speed)}
              type="button"
            >
              {t(`settings_walk_speed_${speed}`)}
            </button>
          ))}
        </div>
      </div>
      <span className="settings-hint">
        {t("settings_walk_speed_hint")}
      </span>

      {BYOK_ENABLED && (
        <>
          <div className="settings-warning" role="alert">
            {t("settings_byok_security_notice")}
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
