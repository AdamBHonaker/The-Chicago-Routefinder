/* FEAT-018 — Saved Locations tool (Tools-hub sub-view).
 *
 * Surfaces both saved routes and pinned stops in one place inside the
 * Tools-hub frame. The saved-stop rows expose a "Schedule →" affordance
 * (FEAT-018 Decision 10) that hands control to SchedulesTool with the
 * stop's id pre-seeded for picker pre-highlighting.
 *
 * Existing saved-pin behaviour (pin/unpin via PinnedStopsBoard on the Home
 * tab and the saved-routes modal off the Masthead) is untouched — this
 * view is an additional surface, not a replacement.
 */

import { useTranslation } from "react-i18next";

export default function SavedLocationsTool({
  onBack,
  savedRoutes,
  pinnedStops,
  onDeleteRoute,
  onRouteSelect,
  onUnpin,
  onViewSchedule,
}) {
  const { t } = useTranslation();
  const hasRoutes = savedRoutes && savedRoutes.length > 0;
  const hasStops  = pinnedStops && pinnedStops.length > 0;

  return (
    <section className="tool-view">
      <div className="tool-view__header">
        <button
          type="button"
          className="tool-view__back"
          onClick={onBack}
        >
          ← {t("tools_back")}
        </button>
        <h2 className="tool-view__title">{t("tools_saved_headline")}</h2>
      </div>

      {!hasRoutes && !hasStops && (
        <p className="sched-view__empty">{t("tools_saved_empty")}</p>
      )}

      {hasStops && (
        <div className="saved-tool__section">
          <h3 className="saved-tool__caps">{t("tools_saved_stops_section")}</h3>
          {pinnedStops.map((stop) => (
            <div key={stop.id} className="saved-stop-row">
              <span className="saved-stop-row__label">{stop.label}</span>
              {onViewSchedule && (
                <button
                  type="button"
                  className="saved-stop-row__schedule"
                  onClick={() => onViewSchedule(stop.stop_id)}
                >
                  {t("tools_view_schedule")} →
                </button>
              )}
              <button
                type="button"
                className="saved-stop-row__schedule"
                onClick={() => onUnpin(stop.id)}
              >
                {t("tools_unpin")}
              </button>
            </div>
          ))}
        </div>
      )}

      {hasRoutes && (
        <div className="saved-tool__section">
          <h3 className="saved-tool__caps">{t("tools_saved_routes_section")}</h3>
          {savedRoutes.map((route) => (
            <div key={route.id} className="saved-stop-row">
              <span className="saved-stop-row__label">{route.label}</span>
              <button
                type="button"
                className="saved-stop-row__schedule"
                onClick={() => onRouteSelect(route.origin, route.destination)}
              >
                {t("fav_go")} →
              </button>
              <button
                type="button"
                className="saved-stop-row__schedule"
                onClick={() => onDeleteRoute(route.id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
