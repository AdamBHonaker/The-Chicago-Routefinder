import { useState } from "react";
import { useTranslation } from "react-i18next";

const _SEVERITY_ORDER = { Major: 0, Minor: 1, Planned: 2 };

export default function ServiceAlertsBar({ alerts, onDismiss }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  if (!alerts || alerts.length === 0) return null;

  const sorted = [...alerts].sort(
    (a, b) => (_SEVERITY_ORDER[a.severity] ?? 3) - (_SEVERITY_ORDER[b.severity] ?? 3)
  );

  return (
    <div className="service-alerts-bar">
      <button
        className="service-alerts-toggle"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className="service-alerts-count">
          {t("alerts_active_count", { count: alerts.length })}
        </span>
        <span className="service-alerts-chevron">{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <ul className="service-alerts-list">
          {sorted.map((alert) => (
            <li
              key={alert.alert_id}
              className={`service-alert service-alert--${alert.severity.toLowerCase()}`}
            >
              <div className="service-alert-header">
                <span
                  className={`service-alert-severity service-alert-severity--${alert.severity.toLowerCase()}`}
                >
                  {alert.severity}
                </span>
                {alert.routes.length > 0 && (
                  <span className="service-alert-routes">
                    {alert.routes.join(", ")}
                  </span>
                )}
                <button
                  className="service-alert-dismiss"
                  onClick={() => onDismiss(alert.alert_id)}
                  aria-label={t("alerts_dismiss")}
                >
                  ✕
                </button>
              </div>
              <p className="service-alert-headline">{alert.headline}</p>
              {alert.short_description && (
                <p className="service-alert-desc">{alert.short_description}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
