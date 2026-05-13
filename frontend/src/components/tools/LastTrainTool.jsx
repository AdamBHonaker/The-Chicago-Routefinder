/* Last Train tool (Tools-hub sub-view).
 *
 * Three-step picker (Line → Direction → Station) mirroring SchedulesTool, but
 * scoped to train lines only and landing on a "last scheduled departure"
 * result view instead of a timetable. Reuses SchedulesPicker (via its titleKey
 * prop) and the same /schedule/* endpoints — the only Last-Train-specific
 * backend call is GET /last-departure on step-3 mount.
 *
 * After-departure behaviour: the backend marks `departed: true` with
 * `minutes_until: null`; we render "Already departed at HH:MM" without a
 * countdown line, per the Last-Train Decision-7 scope.
 */

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { BACKEND_URL } from "../../constants.js";
import SchedulesPicker from "./SchedulesPicker.jsx";

const PICKER_STEPS = { ROUTE: 0, DIRECTION: 1, STOP: 2, VIEW: 3 };

function formatTime12h(hhmm, t) {
  // Backend returns 24-hour "HH:MM" (with post-midnight runs already normalised
  // to 00:xx–02:xx). Render as 12-hour with locale-translated AM/PM.
  if (!hhmm || typeof hhmm !== "string" || !hhmm.includes(":")) return "";
  const [hStr, mStr] = hhmm.split(":");
  const h = parseInt(hStr, 10);
  const m = mStr.padStart(2, "0");
  if (isNaN(h)) return "";
  if (h === 0)  return `12:${m} ${t("schedule_am")}`;
  if (h < 12)   return `${h}:${m} ${t("schedule_am")}`;
  if (h === 12) return `12:${m} ${t("schedule_pm")}`;
  return `${h - 12}:${m} ${t("schedule_pm")}`;
}

function LastTrainResult({ route, direction, stop, onBack, onResetToRouteStep }) {
  const { t } = useTranslation();
  const [data, setData]   = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    const params = new URLSearchParams({
      route_id:     route.route_id,
      direction_id: String(direction.direction_id ?? "0"),
      stop_id:      stop.stop_id,
    });
    fetch(`${BACKEND_URL}/last-departure?${params.toString()}`)
      .then((r) => {
        if (r.status === 404) return { _notFound: true };
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((json) => { if (!cancelled) setData(json); })
      .catch((e)  => { if (!cancelled) setError(String(e)); });
    return () => { cancelled = true; };
  }, [route.route_id, direction.direction_id, stop.stop_id]);

  let body;
  if (error) {
    body = <p className="sched-view__empty">{t("last_train_load_error")}</p>;
  } else if (!data) {
    body = <p className="sched-view__empty">{t("last_train_loading")}</p>;
  } else if (data._notFound) {
    body = <p className="sched-view__empty">{t("last_train_no_data")}</p>;
  } else {
    const timeLabel = formatTime12h(data.time, t);
    const mu = data.minutes_until;
    let subtext;
    if (data.departed) {
      subtext = t("last_train_already_departed");
    } else if (mu == null) {
      subtext = "";
    } else {
      const h = Math.floor(mu / 60);
      const m = mu % 60;
      subtext = h > 0
        ? t("last_train_departs_in_hours",   { h, m })
        : t("last_train_departs_in_minutes", { m });
    }
    body = (
      <div className="last-train-result__card">
        <p className="last-train-result__time">
          {t("last_train_at", { time: timeLabel })}
        </p>
        {subtext && (
          <p className={`last-train-result__sub${data.departed ? " last-train-result__sub--departed" : ""}`}>
            {subtext}
          </p>
        )}
      </div>
    );
  }

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

      {body}
    </section>
  );
}

export default function LastTrainTool({ onBack }) {
  const { t } = useTranslation();
  const [manifest, setManifest] = useState(null);
  const [manifestError, setManifestError] = useState(null);

  const [step, setStep] = useState(PICKER_STEPS.ROUTE);
  const [selectedRoute, setSelectedRoute]           = useState(null);
  const [routeSchedule, setRouteSchedule]           = useState(null);
  const [routeScheduleError, setRouteScheduleError] = useState(null);
  const [selectedDirIdx, setSelectedDirIdx]         = useState(0);
  const [selectedStopIdx, setSelectedStopIdx]       = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetch(`${BACKEND_URL}/schedule/routes`)
      .then((r) => r.json())
      .then((data) => { if (!cancelled) setManifest(data); })
      .catch((e) => { if (!cancelled) setManifestError(String(e)); });
    return () => { cancelled = true; };
  }, []);

  // Manifest filtered to trains only — Last Train is rail-scoped.
  const trainManifest = useMemo(() => {
    if (!manifest) return null;
    return {
      ...manifest,
      routes: (manifest.routes || []).filter((r) => r.category === "train"),
    };
  }, [manifest]);

  function handlePickRoute(route) {
    setSelectedRoute(route);
    setRouteSchedule(null);
    setRouteScheduleError(null);
    setSelectedDirIdx(0);
    setSelectedStopIdx(0);
    setStep(PICKER_STEPS.DIRECTION);
    fetch(`${BACKEND_URL}/schedule/${encodeURIComponent(route.route_id)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setRouteSchedule(data);
        if (data.directions && data.directions.length === 1) {
          setSelectedDirIdx(0);
          setStep(PICKER_STEPS.STOP);
        }
      })
      .catch((e) => setRouteScheduleError(String(e)));
  }

  function handlePickDirection(idx) {
    setSelectedDirIdx(idx);
    setStep(PICKER_STEPS.STOP);
  }

  function handlePickStop(idx) {
    setSelectedStopIdx(idx);
    setStep(PICKER_STEPS.VIEW);
  }

  function handleBackOneStep() {
    if (step === PICKER_STEPS.VIEW)             setStep(PICKER_STEPS.STOP);
    else if (step === PICKER_STEPS.STOP)        setStep(PICKER_STEPS.DIRECTION);
    else if (step === PICKER_STEPS.DIRECTION) {
      setStep(PICKER_STEPS.ROUTE);
      setSelectedRoute(null);
      setRouteSchedule(null);
    } else onBack();
  }

  function handleResetToRouteStep() {
    setStep(PICKER_STEPS.ROUTE);
    setSelectedRoute(null);
    setRouteSchedule(null);
  }

  if (manifestError) {
    return (
      <section className="tool-view">
        <div className="tool-view__header">
          <button type="button" className="tool-view__back" onClick={onBack}>
            ← {t("tools_back")}
          </button>
          <h2 className="tool-view__title">{t("tools_last_train_headline")}</h2>
        </div>
        <p className="sched-view__empty">{t("tools_schedules_load_error")}</p>
      </section>
    );
  }

  if (!trainManifest) {
    return (
      <section className="tool-view">
        <div className="tool-view__header">
          <button type="button" className="tool-view__back" onClick={onBack}>
            ← {t("tools_back")}
          </button>
          <h2 className="tool-view__title">{t("tools_last_train_headline")}</h2>
        </div>
        <p className="sched-view__empty">{t("tools_schedules_loading")}</p>
      </section>
    );
  }

  if (step === PICKER_STEPS.VIEW && routeSchedule) {
    const direction = routeSchedule.directions[selectedDirIdx];
    const stop      = direction.stops[selectedStopIdx];
    return (
      <LastTrainResult
        route={routeSchedule}
        direction={direction}
        stop={stop}
        onBack={handleBackOneStep}
        onResetToRouteStep={handleResetToRouteStep}
      />
    );
  }

  return (
    <SchedulesPicker
      step={step}
      manifest={trainManifest}
      highlightRouteIds={null}
      selectedRoute={selectedRoute}
      routeSchedule={routeSchedule}
      routeScheduleError={routeScheduleError}
      selectedDirIdx={selectedDirIdx}
      onPickRoute={handlePickRoute}
      onPickDirection={handlePickDirection}
      onPickStop={handlePickStop}
      onBackOneStep={handleBackOneStep}
      onExit={onBack}
      titleKey="tools_last_train_headline"
    />
  );
}
