import { useTranslation } from "react-i18next";

export default function LabelSavePanel({ value, onChange, onSave, onCancel, placeholder, showError, prefix = "label" }) {
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
