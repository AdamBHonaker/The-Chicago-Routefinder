import { memo } from "react";
import { useTranslation } from "react-i18next";
import { TRAIN_LINE_CODE_TO_NAME } from "../lineColors.js";
import LinePill from "./LinePill.jsx";
import SignalLamp from "./SignalLamp.jsx";
import TwoToneHeading from "./TwoToneHeading.jsx";

const ArrivalRow = memo(function ArrivalRow({ route, destination, minutes }) {
  const { t } = useTranslation();
  // /stop-arrivals sends train arrivals with the raw CTA `rt` code (e.g. "Red",
  // "Brn", "G") in `route`. Bus arrivals send the bus route number/letter.
  // Resolve trains via TRAIN_LINE_CODE_TO_NAME so the rail pill picks up the
  // correct color, abbreviation, and aria-label.
  const trainLineName = TRAIN_LINE_CODE_TO_NAME[route];
  const isBus = !trainLineName;
  const due = minutes === 0 ? t("wait_due_short") : `${minutes}m`;
  return (
    <div className="psb-arrival">
      <LinePill
        line={isBus ? route : trainLineName}
        isBus={isBus}
        lineCode={isBus ? route : undefined}
        size="sm"
      />
      <span className="psb-arrival-dest">{destination}</span>
      <span className="psb-arrival-due">{due}</span>
    </div>
  );
});

function PinnedStopsBoard({ stops, arrivals, onUnpin, onRefresh }) {
  const { t } = useTranslation();
  if (!stops || stops.length === 0) return null;

  return (
    <section className="psb">
      <div className="psb-header psb-header--two-tone">
        <TwoToneHeading
          capsKey="caps_stops"
          headingKey="pinned_stops_heading"
          italicWords={1}
        />
        <div className="psb-header-right">
          <SignalLamp
            ariaLabel={t("psb_live_data")}
            label={t("signal_lamp_label")}
          />
          <button
            className="psb-refresh-btn"
            onClick={onRefresh}
            title={t("psb_refresh")}
            aria-label={t("psb_refresh")}
          >
            ↺
          </button>
        </div>
      </div>

      <div className="psb-cards">
        {stops.map((stop) => {
          const data = arrivals?.[`${stop.type}:${stop.stop_id}`];
          const arrList = data?.arrivals ?? [];
          const lastMin = data?.last_departure_minutes;
          const showLastTrain = lastMin !== undefined && lastMin !== null;

          return (
            <div key={stop.id} className="psb-card">
              <div className="psb-card-header">
                <span className="psb-stop-label">{stop.label}</span>
                {stop.route_hint && (
                  <span className="psb-route-hint">{stop.route_hint}</span>
                )}
                <button
                  className="psb-unpin-btn"
                  onClick={() => onUnpin(stop.id)}
                  title={t("psb_unpin_stop")}
                  aria-label={t("unpin_stop", { stop: stop.label })}
                >
                  ×
                </button>
              </div>

              <div className="psb-arrivals">
                {arrList.length === 0 ? (
                  <span className="psb-no-arrivals">{t("no_arrivals")}</span>
                ) : (
                  arrList.map((a, i) => (
                    <ArrivalRow
                      key={`${a.route}|${a.destination}|${a.minutes}|${i}`}
                      route={a.route}
                      destination={a.destination}
                      minutes={a.minutes}
                    />
                  ))
                )}
              </div>

              {showLastTrain && (
                <p className={`psb-last-train${lastMin <= 15 ? " psb-last-train--urgent" : ""}`}>
                  {t("last_train_in", { min: lastMin })}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

// Memoized so unrelated App-state changes (search submission, BYOK toggle,
// transfer selection) don't cause this board to re-render and rebuild every
// ArrivalRow JSX subtree. Props are scalars / stable refs (OPT-FE-207).
export default memo(PinnedStopsBoard);
