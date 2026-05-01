import { useTranslation } from "react-i18next";

export default function SharedRouteBanner({ onDismiss }) {
  const { t } = useTranslation();
  return (
    <div className="shared-route-banner" role="status">
      <span className="shared-route-banner__text">{t("shared_banner_text")}</span>
      <button
        type="button"
        className="geo-denied-dismiss"
        onClick={onDismiss}
        aria-label={t("aria_dismiss")}
      >×</button>
    </div>
  );
}
