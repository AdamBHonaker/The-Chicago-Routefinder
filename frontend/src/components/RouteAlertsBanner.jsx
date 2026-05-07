import { useTranslation } from "react-i18next";

// Quieted replacement for the always-visible ServiceAlertsBar above the form.
// Renders a single banner inside the results column after a search:
//   • hasAlerts: clickable button → parent navigates to the Notices & Delays tab
//     with the route's L lines and bus routes pre-selected.
//   • !hasAlerts: static <p>, not in the tab order, no hover/active styling.
// Visual treatment reuses .special-dispatch--advisory (alerts present) and a
// new .special-dispatch--quiet modifier (no alerts) so no new editorial
// vocabulary is introduced.
export default function RouteAlertsBanner({ hasAlerts, onView }) {
  const { t } = useTranslation();

  if (hasAlerts) {
    return (
      <button
        type="button"
        className="route-alerts-banner route-alerts-banner--present special-dispatch special-dispatch--advisory"
        aria-label={t("route_alerts_banner_present_aria")}
        onClick={onView}
      >
        <span className="special-dispatch__kicker">{t("caps_advisories")}</span>
        <span className="route-alerts-banner__body">
          {t("route_alerts_banner_present")}
        </span>
        <span className="route-alerts-banner__cta">
          {t("route_alerts_banner_present_cta")}
        </span>
      </button>
    );
  }

  return (
    <p className="route-alerts-banner route-alerts-banner--absent special-dispatch special-dispatch--quiet">
      <span className="special-dispatch__kicker">{t("caps_advisories")}</span>
      <span className="route-alerts-banner__body">
        {t("route_alerts_banner_absent")}
      </span>
    </p>
  );
}
