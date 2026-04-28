import { useTranslation } from "react-i18next";
import { LINE_COLORS, getRouteColor } from "../constants.js";

function ArrivalPill({ route, destination, minutes }) {
  const isTrainLine = route in LINE_COLORS;
  const color = getRouteColor(route, "#555");
  const label = isTrainLine ? route.replace(" Line", "") : route;
  const due = minutes === 0 ? "Due" : `${minutes} min`;
  return (
    <span className="psb-arrival">
      <span className="psb-arrival-pill" style={{ background: color }}>{label}</span>
      <span className="psb-arrival-dest">{destination}</span>
      <span className="psb-arrival-due">{due}</span>
    </span>
  );
}

export default function PinnedStopsBoard({ stops, arrivals, onUnpin, onRefresh }) {
  const { t } = useTranslation();
  if (!stops || stops.length === 0) return null;

  return (
    <div className="psb">
      <div className="psb-header">
        <span className="psb-title">{t("pinned_stops_heading")}</span>
        <button className="psb-refresh-btn" onClick={onRefresh} title="Refresh arrivals">
          ↻
        </button>
      </div>
      <div className="psb-cards">
        {stops.map((stop) => {
          const data = arrivals?.[stop.stop_id];
          const arrList = data?.arrivals ?? [];
          const lastMin = data?.last_departure_minutes;
          const showLastTrain = lastMin !== undefined && lastMin !== null;

          return (
            <div key={stop.id} className="psb-card">
              <div className="psb-card-header">
                <span className="psb-stop-label">{stop.label}</span>
                <span className="psb-route-hint">{stop.route_hint}</span>
                <button
                  className="psb-unpin-btn"
                  onClick={() => onUnpin(stop.id)}
                  title="Unpin stop"
                  aria-label={`Unpin ${stop.label}`}
                >
                  ×
                </button>
              </div>
              <div className="psb-arrivals">
                {arrList.length === 0 ? (
                  <span className="psb-no-arrivals">{t("no_arrivals")}</span>
                ) : (
                  arrList.map((a, i) => (
                    <ArrivalPill
                      key={i}
                      route={a.route}
                      destination={a.destination}
                      minutes={a.minutes}
                    />
                  ))
                )}
              </div>
              {showLastTrain && (
                <div className={`psb-last-train${lastMin <= 15 ? " psb-last-train--urgent" : ""}`}>
                  {t("last_train_in", { min: lastMin })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
