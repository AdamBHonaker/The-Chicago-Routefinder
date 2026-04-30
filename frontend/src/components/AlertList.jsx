import { useTranslation } from "react-i18next";

export default function AlertList({ alerts, onDismiss }) {
  const { t } = useTranslation();
  if (!alerts || alerts.length === 0) {
    return <p className="tab-empty">{t("alerts_empty")}</p>;
  }
  return (
    <ul className="tab-alerts-list">
      {alerts.map((a) => (
        <li key={a.alert_id} className={`tab-alert tab-alert--${(a.severity ?? "minor").toLowerCase()}`}>
          <div className="tab-alert-header">
            <span className="tab-alert-kicker">{a.severity ?? t("alerts_advisory")}</span>
            <button
              className="tab-alert-dismiss"
              onClick={() => onDismiss(a.alert_id)}
              aria-label={t("aria_dismiss")}
            >×</button>
          </div>
          <p className="tab-alert-headline">{a.headline}</p>
          {a.short_description && <p className="tab-alert-desc">{a.short_description}</p>}
        </li>
      ))}
    </ul>
  );
}
