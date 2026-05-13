/* FEAT-018 — Schedules tool (Tools-hub sub-view).
 *
 * Drives the three-step route→direction→stop picker (SchedulesPicker) and
 * then renders the day-tabbed timetable (SchedulesView). Owns the data
 * fetches for /schedule/routes (cached for the lifetime of the sub-view)
 * and /schedule/{route_id} (refetched each time a new route is selected).
 *
 * The "seed" prop carries optional pre-state from a saved-stop "Schedule →"
 * tap (Decision 10): a stop_id whose serving routes are visually
 * pre-highlighted in step 1 and auto-selected at step 3 if the chosen
 * route serves that stop.
 */

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { BACKEND_URL } from "../../constants.js";
import SchedulesPicker from "./SchedulesPicker.jsx";
import SchedulesView   from "./SchedulesView.jsx";

const PICKER_STEPS = { ROUTE: 0, DIRECTION: 1, STOP: 2, VIEW: 3 };

export default function SchedulesTool({ onBack, seed }) {
  const { t } = useTranslation();
  const [manifest, setManifest] = useState(null);
  const [manifestError, setManifestError] = useState(null);

  const [step, setStep] = useState(PICKER_STEPS.ROUTE);
  const [selectedRoute, setSelectedRoute]         = useState(null); // manifest entry
  const [routeSchedule, setRouteSchedule]         = useState(null); // full schedule
  const [routeScheduleError, setRouteScheduleError] = useState(null);
  const [selectedDirIdx, setSelectedDirIdx]       = useState(0);
  const [selectedStopIdx, setSelectedStopIdx]     = useState(0);

  // Fetch manifest once on mount.
  useEffect(() => {
    let cancelled = false;
    fetch(`${BACKEND_URL}/schedule/routes`)
      .then((r) => r.json())
      .then((data) => { if (!cancelled) setManifest(data); })
      .catch((e) => { if (!cancelled) setManifestError(String(e)); });
    return () => { cancelled = true; };
  }, []);

  // Routes that serve the seeded stop (for picker pre-highlight).
  const highlightRouteIds = useMemo(() => {
    if (!seed?.stopId || !manifest?.stop_routes) return null;
    const ids = manifest.stop_routes[seed.stopId];
    return ids ? new Set(ids) : null;
  }, [seed, manifest]);

  function handlePickRoute(route) {
    setSelectedRoute(route);
    setRouteSchedule(null);
    setRouteScheduleError(null);
    setStep(PICKER_STEPS.DIRECTION);
    fetch(`${BACKEND_URL}/schedule/${encodeURIComponent(route.route_id)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setRouteSchedule(data);
        // Auto-advance when there's only one direction.
        if (data.directions && data.directions.length === 1) {
          setSelectedDirIdx(0);
          // If the seeded stop is on this direction, auto-pick it.
          if (seed?.stopId) {
            const idx = data.directions[0].stops.findIndex(
              (s) => s.stop_id === seed.stopId,
            );
            if (idx >= 0) {
              setSelectedStopIdx(idx);
              setStep(PICKER_STEPS.VIEW);
              return;
            }
          }
          setStep(PICKER_STEPS.STOP);
        }
      })
      .catch((e) => setRouteScheduleError(String(e)));
  }

  function handlePickDirection(idx) {
    setSelectedDirIdx(idx);
    // If a seeded stop is on this direction, auto-jump to schedule view.
    if (seed?.stopId && routeSchedule) {
      const stopIdx = routeSchedule.directions[idx].stops.findIndex(
        (s) => s.stop_id === seed.stopId,
      );
      if (stopIdx >= 0) {
        setSelectedStopIdx(stopIdx);
        setStep(PICKER_STEPS.VIEW);
        return;
      }
    }
    setStep(PICKER_STEPS.STOP);
  }

  function handlePickStop(idx) {
    setSelectedStopIdx(idx);
    setStep(PICKER_STEPS.VIEW);
  }

  function handleBackOneStep() {
    if (step === PICKER_STEPS.VIEW)        setStep(PICKER_STEPS.STOP);
    else if (step === PICKER_STEPS.STOP)   setStep(PICKER_STEPS.DIRECTION);
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
          <h2 className="tool-view__title">{t("tools_schedules_headline")}</h2>
        </div>
        <p className="sched-view__empty">{t("tools_schedules_load_error")}</p>
      </section>
    );
  }

  if (!manifest) {
    return (
      <section className="tool-view">
        <div className="tool-view__header">
          <button type="button" className="tool-view__back" onClick={onBack}>
            ← {t("tools_back")}
          </button>
          <h2 className="tool-view__title">{t("tools_schedules_headline")}</h2>
        </div>
        <p className="sched-view__empty">{t("tools_schedules_loading")}</p>
      </section>
    );
  }

  // Step 3 (VIEW): timetable.
  if (step === PICKER_STEPS.VIEW && routeSchedule) {
    const direction = routeSchedule.directions[selectedDirIdx];
    const stop      = direction.stops[selectedStopIdx];
    return (
      <SchedulesView
        route={routeSchedule}
        direction={direction}
        stop={stop}
        onBack={handleBackOneStep}
        onResetToRouteStep={handleResetToRouteStep}
      />
    );
  }

  // Steps 0–2: picker.
  return (
    <SchedulesPicker
      step={step}
      manifest={manifest}
      highlightRouteIds={highlightRouteIds}
      selectedRoute={selectedRoute}
      routeSchedule={routeSchedule}
      routeScheduleError={routeScheduleError}
      selectedDirIdx={selectedDirIdx}
      onPickRoute={handlePickRoute}
      onPickDirection={handlePickDirection}
      onPickStop={handlePickStop}
      onBackOneStep={handleBackOneStep}
      onResetToRouteStep={handleResetToRouteStep}
      onExit={onBack}
    />
  );
}

export { PICKER_STEPS };
