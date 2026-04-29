import { useTranslation } from "react-i18next";

export default function SavedRoutesPanel({ savedRoutes, onDeleteRoute, onRouteSelect }) {
  const { t } = useTranslation();
  return (
    <div className="saved-routes-panel">
      <div className="saved-routes-panel-header">
        <span className="saved-routes-panel-heading">{t("fav_saved_routes_heading")}</span>
      </div>
      {savedRoutes.length === 0 ? (
        <p className="saved-routes-empty">{t("fav_routes_empty")}</p>
      ) : (
        savedRoutes.map((route) => (
          <div key={route.id} className="saved-route-row">
            <span className="saved-route-label">{route.label}</span>
            <button
              type="button"
              className="saved-route-go"
              onClick={() => onRouteSelect(route.origin, route.destination)}
            >
              {t("fav_go")} →
            </button>
            <button
              type="button"
              className="saved-route-delete"
              onClick={() => onDeleteRoute(route.id)}
              aria-label={t("fav_delete")}
            >
              ×
            </button>
          </div>
        ))
      )}
    </div>
  );
}
