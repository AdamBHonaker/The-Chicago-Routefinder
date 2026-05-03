import { useMemo } from "react";
import { useTranslation } from "react-i18next";

const SEVERITY_ORDER = { Major: 0, Minor: 1, Planned: 2 };

// D2 spec: Major = rust kicker (consequence), Minor = mute kicker (gray ink),
// Planned/Advisory = navy kicker (notice). Modifier names mirror severity for
// clarity; CSS in App.css maps each to the correct kicker color.
function severityMeta(severity) {
  if (severity === "Major") return { labelKey: "alerts_severity_major",    modifier: "major" };
  if (severity === "Minor") return { labelKey: "alerts_severity_minor",    modifier: "minor" };
  return                          { labelKey: "alerts_severity_advisory", modifier: "advisory" };
}

export default function ServiceAlertsBar({ alerts, onDismiss }) {
  const { t } = useTranslation();

  const sorted = useMemo(
    () => [...(alerts ?? [])].sort(
      (a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3)
    ),
    [alerts]
  );

  if (!alerts || alerts.length === 0) return null;

  return (
    <div className="alerts-stack">
      {sorted.map((alert) => {
        const { labelKey, modifier } = severityMeta(alert.severity);
        return (
          <div
            key={alert.alert_id}
            className={`special-dispatch special-dispatch--${modifier}`}
          >
            <div className="special-dispatch__header">
              <span className="special-dispatch__kicker">{t(labelKey)}</span>
              {(alert.routes?.length ?? 0) > 0 && (
                <span className="special-dispatch__routes">
                  {alert.routes.join(" · ")}
                </span>
              )}
              <button
                className="special-dispatch__dismiss"
                onClick={() => onDismiss(alert.alert_id)}
                aria-label={t("alerts_dismiss")}
              >
                ×
              </button>
            </div>
            <p className="special-dispatch__body">{alert.headline}</p>
            {alert.short_description && (
              <p className="special-dispatch__desc">{alert.short_description}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
