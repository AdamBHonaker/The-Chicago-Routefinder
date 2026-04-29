import { useTranslation } from "react-i18next";

export default function SavedRoutesPanel({ savedRoutes, onDeleteRoute, onRouteSelect, onClose }) {
  const { t } = useTranslation();
  return (
    <div className="settings-modal" role="dialog" aria-label={t("fav_saved_routes_heading")} aria-modal="true">
      <div className="settings-backdrop" onClick={onClose} aria-hidden="true" />
      <div className="settings-sheet paper-grain-bright">
        <div className="settings-sheet-header">
          <span className="settings-sheet-title">⟡ {t("fav_saved_routes_heading")} ⟡</span>
          <button
            className="settings-sheet-close"
            onClick={onClose}
            aria-label={t("aria_dismiss")}
          >
            ×
          </button>
        </div>
        <div className="settings-sheet-rule" aria-hidden="true" />

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
    </div>
  );
}
