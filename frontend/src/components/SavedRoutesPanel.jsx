import { useTranslation } from "react-i18next";
import TwoToneHeading from "./TwoToneHeading.jsx";

export default function SavedRoutesPanel({ savedRoutes, onDeleteRoute, onRouteSelect, onClose }) {
  const { t } = useTranslation();
  return (
    <div className="settings-modal" role="dialog" aria-label={t("fav_saved_routes_heading")} aria-modal="true">
      <div className="settings-backdrop" onClick={onClose} aria-hidden="true" />
      <div className="settings-sheet paper-grain-bright">
        <div className="settings-sheet-header settings-sheet-header--two-tone">
          <TwoToneHeading
            capsKey="caps_bookmarks"
            headingKey="fav_saved_routes_heading"
            italicWords={1}
          />
          <button
            className="settings-sheet-close"
            onClick={onClose}
            aria-label={t("aria_dismiss")}
          >
            ×
          </button>
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
    </div>
  );
}
