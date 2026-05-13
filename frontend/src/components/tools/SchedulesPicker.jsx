/* FEAT-018 — Schedules three-step picker.
 *
 * Step 0 (route): scrollable categorized list — Train Lines → Bus Frequent
 *                 Service → Bus Express → Bus Regular.
 * Step 1 (direction): pick from the route's direction list (auto-advances
 *                     in SchedulesTool when there's only one direction).
 * Step 2 (stop): ordered stop list along the chosen direction.
 *
 * Pure presentational: state lives in SchedulesTool.
 */

import { useTranslation } from "react-i18next";

const CATEGORY_ORDER = [
  { id: "train",        i18nKey: "schedule_section_train"        },
  { id: "bus_frequent", i18nKey: "schedule_section_bus_frequent" },
  { id: "bus_express",  i18nKey: "schedule_section_bus_express"  },
  { id: "bus_regular",  i18nKey: "schedule_section_bus_regular"  },
];

function PickerHeader({ title, onBack, backLabel }) {
  return (
    <div className="tool-view__header">
      <button type="button" className="tool-view__back" onClick={onBack}>
        ← {backLabel}
      </button>
      <h2 className="tool-view__title">{title}</h2>
    </div>
  );
}

function pillColor(route) {
  // GTFS route_color is the authoritative pill color (CTA's published taxonomy
  // — same hex values used by both train lines and bus routes in the manifest).
  const c = (route.color || "").trim();
  if (!c) return "#666";
  return c.startsWith("#") ? c : `#${c}`;
}

function RouteList({ routes, highlightRouteIds, onPick, t }) {
  const grouped = new Map();
  for (const r of routes) {
    const list = grouped.get(r.category) || [];
    list.push(r);
    grouped.set(r.category, list);
  }
  return (
    <div className="sched-picker">
      {CATEGORY_ORDER.map(({ id, i18nKey }) => {
        const items = grouped.get(id);
        if (!items || items.length === 0) return null;
        return (
          <section key={id} className="sched-picker__section">
            <h3 className="sched-picker__section-title">{t(i18nKey)}</h3>
            <ul className="sched-picker__list">
              {items.map((r) => {
                const hl = highlightRouteIds?.has(r.route_id);
                return (
                  <li key={r.route_id}>
                    <button
                      type="button"
                      className={`sched-picker__row${hl ? " sched-picker__row--highlight" : ""}`}
                      onClick={() => onPick(r)}
                    >
                      <span
                        className="sched-picker__pill"
                        style={{ background: pillColor(r) }}
                      >
                        {r.short_name}
                      </span>
                      <span className="sched-picker__long">{r.long_name}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function DirectionList({ directions, onPick, t }) {
  return (
    <ul className="sched-picker__list">
      {directions.map((d, idx) => (
        <li key={d.direction_id || idx}>
          <button
            type="button"
            className="sched-picker__row"
            onClick={() => onPick(idx)}
          >
            <span className="sched-picker__long">
              → {d.headsign || t("schedule_direction_unknown")}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function StopList({ stops, onPick }) {
  return (
    <ul className="sched-picker__list">
      {stops.map((s, idx) => (
        <li key={s.stop_id}>
          <button
            type="button"
            className="sched-picker__row"
            onClick={() => onPick(idx)}
          >
            <span className="sched-picker__long">{s.name}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function SchedulesPicker({
  step,
  manifest,
  highlightRouteIds,
  selectedRoute,
  routeSchedule,
  routeScheduleError,
  selectedDirIdx,
  onPickRoute,
  onPickDirection,
  onPickStop,
  onBackOneStep,
  onExit,
  titleKey = "tools_schedules_headline",
}) {
  const { t } = useTranslation();

  if (step === 0) {
    return (
      <section className="tool-view">
        <PickerHeader
          title={t(titleKey)}
          onBack={onExit}
          backLabel={t("tools_back")}
        />
        <RouteList
          routes={manifest.routes}
          highlightRouteIds={highlightRouteIds}
          onPick={onPickRoute}
          t={t}
        />
      </section>
    );
  }

  if (step === 1) {
    return (
      <section className="tool-view">
        <PickerHeader
          title={selectedRoute?.long_name || t(titleKey)}
          onBack={onBackOneStep}
          backLabel={t("tools_back")}
        />
        {routeScheduleError && (
          <p className="sched-view__empty">{t("tools_schedules_load_error")}</p>
        )}
        {!routeSchedule && !routeScheduleError && (
          <p className="sched-view__empty">{t("tools_schedules_loading")}</p>
        )}
        {routeSchedule && (
          <DirectionList
            directions={routeSchedule.directions}
            onPick={onPickDirection}
            t={t}
          />
        )}
      </section>
    );
  }

  if (step === 2) {
    const direction = routeSchedule?.directions[selectedDirIdx];
    return (
      <section className="tool-view">
        <PickerHeader
          title={direction?.headsign
            ? `→ ${direction.headsign}`
            : (selectedRoute?.long_name || t(titleKey))}
          onBack={onBackOneStep}
          backLabel={t("tools_back")}
        />
        {direction?.stops && (
          <StopList stops={direction.stops} onPick={onPickStop} />
        )}
      </section>
    );
  }

  return null;
}
