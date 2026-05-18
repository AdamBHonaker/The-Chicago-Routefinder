/* FEAT-018 — Schedules day-tabbed timetable view.
 *
 * Renders the per-stop published timetable across three day-tab buckets
 * (Weekday / Saturday / Sunday-or-Holiday). Defaults to today's bucket,
 * groups departure times by hour, and renders past times (current-day only)
 * in --ink-soft. A "↑ Now" pill scrolls the list to the current hour's
 * group on the active-and-today tab.
 *
 * Holiday detection mirrors the build-script rule: federal holidays where
 * CTA runs Sunday service fold into the Sunday tab. See
 * scripts/build_schedule_index.py for the canonical list.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

const BUCKETS = ["weekday", "saturday", "sunday"];

function isSundayServiceHoliday(d) {
  const m = d.getMonth() + 1;
  const day = d.getDate();
  if ((m === 1 && day === 1) || (m === 7 && day === 4) || (m === 12 && day === 25)) {
    return true;
  }
  // Memorial Day (last Mon of May).
  if (m === 5 && d.getDay() === 1) {
    const next = new Date(d);
    next.setDate(d.getDate() + 7);
    if (next.getMonth() + 1 !== 5) return true;
  }
  // Labor Day (first Mon of Sep).
  if (m === 9 && d.getDay() === 1 && day <= 7) return true;
  // Thanksgiving (fourth Thu of Nov).
  if (m === 11 && d.getDay() === 4 && day >= 22 && day <= 28) return true;
  return false;
}

function todaysBucket(now) {
  if (isSundayServiceHoliday(now)) return "sunday";
  const dow = now.getDay(); // 0 = Sun, 6 = Sat
  if (dow === 0) return "sunday";
  if (dow === 6) return "saturday";
  return "weekday";
}

function groupByHour(times) {
  const groups = new Map();
  for (const hhmm of times) {
    const hour = hhmm.slice(0, 2);
    const minute = hhmm.slice(3, 5);
    const list = groups.get(hour) || [];
    list.push(minute);
    groups.set(hour, list);
  }
  return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
}

function formatHourLabel(hour, t) {
  const h = parseInt(hour, 10);
  if (h === 0)  return t("schedule_hour_12am");
  if (h === 12) return t("schedule_hour_12pm");
  if (h < 12)   return `${h} ${t("schedule_am")}`;
  return `${h - 12} ${t("schedule_pm")}`;
}

export default function SchedulesView({
  route,
  direction,
  stop,
  onBack,
  onResetToRouteStep,
}) {
  const { t } = useTranslation();
  // `now` ticks once a minute while the today bucket is visible so the
  // past-time grey-out and the "↑ Now" target stay aligned with the wall
  // clock — leaving the view open across an hour boundary used to leave
  // already-departed times rendered as future. Off-day buckets don't need
  // the ticker so we gate the interval on (activeBucket === todayBucket).
  const [now, setNow] = useState(() => new Date());
  const todayBucket = useMemo(() => todaysBucket(now), [now]);
  const [activeBucket, setActiveBucket] = useState(todayBucket);
  const hourRefs = useRef({});

  useEffect(() => {
    if (activeBucket !== todayBucket) return undefined;
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, [activeBucket, todayBucket]);

  // Memoize directly on the stable inputs (OPT-FE-212). `times` is otherwise a
  // fresh array reference on every render when `stop.times?.[activeBucket]` is
  // falsy, defeating the memo on a per-render basis.
  const grouped = useMemo(
    () => groupByHour(stop.times?.[activeBucket] ?? []),
    [stop, activeBucket],
  );

  const currentHourStr   = String(now.getHours()).padStart(2, "0");
  const currentMinuteStr = String(now.getMinutes()).padStart(2, "0");
  const showNowPill = activeBucket === todayBucket && grouped.length > 0;

  function jumpToNow() {
    const target = grouped.find(([h]) => h >= currentHourStr) || grouped[grouped.length - 1];
    if (!target) return;
    const ref = hourRefs.current[target[0]];
    if (ref && typeof ref.scrollIntoView === "function") {
      ref.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  useEffect(() => {
    if (activeBucket === todayBucket && grouped.length > 0) {
      const target = grouped.find(([h]) => h >= currentHourStr);
      if (target) {
        const ref = hourRefs.current[target[0]];
        if (ref && typeof ref.scrollIntoView === "function") {
          ref.scrollIntoView({ block: "start" });
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section className="tool-view">
      <div className="tool-view__header">
        <button type="button" className="tool-view__back" onClick={onBack}>
          ← {t("tools_back")}
        </button>
        <button
          type="button"
          className="sched-view__route-header-btn"
          onClick={onResetToRouteStep}
          title={t("schedule_back_to_route_list")}
        >
          <span className="sched-view__route-header">
            {route.route_long_name} → {direction.headsign}
          </span>
        </button>
      </div>

      <p className="sched-view__empty" style={{ padding: 0, color: "var(--ink)" }}>
        {stop.name}
      </p>

      <div className="sched-view__tabs" role="tablist">
        {BUCKETS.map((b) => (
          <button
            key={b}
            type="button"
            role="tab"
            aria-selected={activeBucket === b}
            className={`sched-view__tab${activeBucket === b ? " sched-view__tab--active" : ""}`}
            onClick={() => setActiveBucket(b)}
          >
            {t(`schedule_tab_${b}`)}
          </button>
        ))}
      </div>

      {showNowPill && (
        <button
          type="button"
          className="sched-view__now"
          onClick={jumpToNow}
        >
          ↑ {t("schedule_now")}
        </button>
      )}

      {grouped.length === 0 ? (
        <p className="sched-view__empty">{t("schedule_no_service")}</p>
      ) : (
        <div className="sched-view__list">
          {grouped.map(([hour, minutes]) => (
            <div
              key={hour}
              className="sched-view__hour-group"
              ref={(el) => { hourRefs.current[hour] = el; }}
            >
              <span className="sched-view__hour-label">
                {formatHourLabel(hour, t)}
              </span>
              <div className="sched-view__minutes">
                {minutes.map((m) => {
                  const past = activeBucket === todayBucket && (
                    hour < currentHourStr ||
                    (hour === currentHourStr && m < currentMinuteStr)
                  );
                  return (
                    <span
                      key={`${hour}:${m}`}
                      className={`sched-view__minute tnum${past ? " sched-view__minute--past" : ""}`}
                    >
                      :{m}
                    </span>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
