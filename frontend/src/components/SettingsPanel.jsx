import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { isValidByokKey } from "../constants.js";

const BYOK_ENABLED = import.meta.env.VITE_BYOK_ENABLED === "true";
const WALK_SPEEDS = ["slow", "standard", "brisk"];

export default function SettingsPanel({
  apiKey, onSave, onClose,
  aiEnabled, onAiChange,
  walkSpeed, onWalkSpeedChange,
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(apiKey);
  // Re-sync the input when the parent clears apiKey externally (e.g. BYOK
  // idle-clear timer fires while the panel is still open). Without this, a
  // stale value would remain visible and a Save would re-install the old key.
  useEffect(() => { setDraft(apiKey); }, [apiKey]);
  const isValid = isValidByokKey(draft);

  return (
    <div className="settings-modal" role="dialog" aria-label={t("settings_title")} aria-modal="true">
      <div className="settings-backdrop" onClick={onClose} aria-hidden="true" />
      <div className="settings-sheet">

        {/* Sheet header */}
        <div className="settings-sheet-header">
          <span className="settings-sheet-title">⟡ {t("settings_title")} ⟡</span>
          <button
            className="settings-sheet-close"
            onClick={onClose}
            aria-label={t("aria_close_settings")}
          >
            ×
          </button>
        </div>
        <div className="settings-sheet-rule" aria-hidden="true" />

        {/* AI recommendation */}
        <div className="settings-section">
          <label className="settings-ai-row">
            <input
              type="checkbox"
              className="settings-checkbox-native"
              checked={aiEnabled}
              onChange={(e) => onAiChange(e.target.checked)}
            />
            <span className="settings-checkbox-custom" aria-hidden="true" />
            <span className="settings-ai-label">
              <span className="settings-section-caps">{t("settings_ai_explanation_label")}</span>
              <span className="settings-section-hint">{t("settings_ai_explanation_hint")}</span>
            </span>
          </label>
        </div>

        {/* Walk speed */}
        <div className="settings-section">
          <span className="settings-section-caps">{t("settings_walk_speed_label")}</span>
          <span className="settings-section-hint">{t("settings_walk_speed_hint")}</span>
          <div className="settings-speed-row">
            {WALK_SPEEDS.map((speed) => (
              <button
                key={speed}
                type="button"
                className={`settings-speed-btn${walkSpeed === speed ? " settings-speed-btn--active" : ""}`}
                onClick={() => onWalkSpeedChange(speed)}
              >
                {t(`settings_walk_speed_${speed}`)}
              </button>
            ))}
          </div>
        </div>

        {/* BYOK API key */}
        {BYOK_ENABLED && (
          <div className="settings-section">
            <div className="settings-warning" role="alert">
              {t("settings_byok_security_notice")}
            </div>
            <label className="settings-label">
              <span className="settings-section-caps">{t("settings_label_api_key")}</span>
              <span className="settings-section-hint">{t("settings_hint_api_key")}</span>
              <input
                type="password"
                className={`settings-key-input${!isValid ? " settings-key-input--error" : ""}`}
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
            <div className="settings-byok-actions">
              <button
                className="settings-byok-save"
                onClick={() => { onSave(draft.trim()); onClose(); }}
                disabled={!isValid}
              >
                {t("settings_btn_save")}
              </button>
              {apiKey && (
                <button
                  className="settings-byok-clear"
                  onClick={() => { onSave(""); onClose(); }}
                >
                  {t("settings_btn_remove_key")}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="settings-sheet-footer">
          <button className="settings-done-btn" onClick={onClose}>
            {t("settings_btn_close")} ×
          </button>
        </div>

      </div>
    </div>
  );
}
