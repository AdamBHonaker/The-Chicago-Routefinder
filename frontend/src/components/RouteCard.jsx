import { useState, memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { LINE_COLORS, BUS_DIRECTION_COLORS, getRouteColor } from "../constants.js";
import LinePill from "./LinePill.jsx";

function formatBlocks(b, blockType, t) {
  if (!blockType) return b === 1 ? `1 ${t("block_singular")}` : `${b} ${t("block_plural")}`;
  if (blockType === "long") return `${b} ${b === 1 ? t("long_block_singular") : t("long_block_plural")}`;
  return `${b} ${b === 1 ? t("short_block_singular") : t("short_block_plural")}`;
}

function WalkLegItem({ leg, index, completedSteps, extraClass = "" }) {
  const { t } = useTranslation();
  const [stepsOpen, setStepsOpen] = useState(false);
  const dirCount = leg.directions?.length ?? 0;
  const hasSteps = dirCount > 0;
  const isMultiStep = dirCount > 1;

  const label =
    leg.from === "Your location"
      ? t("walk_from_origin", { minutes: leg.minutes, to: leg.to })
      : leg.to === "Your destination"
      ? t("walk_to_destination", { minutes: leg.minutes })
      : t("walk_transfer", { minutes: leg.minutes });

  const showExit = leg.exit_label && leg.to === "Your destination";

  const renderStep = (step, si) => {
    const stepDone = completedSteps?.has(`${index}-${si}`);
    return (
      <li key={si} className={`leg-step${stepDone ? " leg-step--complete" : ""}`}>
        <span className="leg-step-text">
          {stepDone && <span className="leg-step-complete-check">✓</span>}
          {si === 0 ? t("step_walk") : t("step_head")}
          {step.direction_full ? ` ${step.direction_full}` : ""}
          {` ${t("step_along")} `}
          <span className="leg-step-street">{step.street}</span>
          {` ${t("step_for")} `}
          {formatBlocks(step.blocks ?? 1, step.block_type, t)}
        </span>
      </li>
    );
  };

  return (
    <li key={index} className={`leg leg-walk${extraClass}`}>
      {extraClass.includes("leg-complete") && <span className="leg-complete-check">✓</span>}
      <span className="leg-icon">🚶</span>
      <span className="leg-walk-body">
        <span className="leg-text">{label}</span>
        {showExit && (
          <span className="leg-exit-label">{t("exit_label_prefix")} {leg.exit_label}</span>
        )}
        {hasSteps && !isMultiStep && (
          <ol className="leg-steps leg-steps--inline">
            {renderStep(leg.directions[0], 0)}
          </ol>
        )}
        {isMultiStep && (
          <button
            className="leg-steps-toggle"
            onClick={() => setStepsOpen((v) => !v)}
            aria-expanded={stepsOpen}
          >
            {stepsOpen ? t("steps_hide") : t("steps_show")}
          </button>
        )}
        {isMultiStep && stepsOpen && (
          <ol className="leg-steps">
            {leg.directions.map(renderStep)}
          </ol>
        )}
      </span>
    </li>
  );
}

function RouteLegs({ legs, activeLegIndex, completedSteps, pinnedStops, onPinToggle, activeAlertRoutes }) {
  const { t } = useTranslation();
  // Key by `${type}:${stop_id}` so bus stop_ids and train mapids never alias.
  const pinnedIds = useMemo(
    () => new Set(pinnedStops?.map((s) => `${s.type}:${s.stop_id}`) ?? []),
    [pinnedStops]
  );
  let seenTransit = false;
  return (
    <ol className="route-legs">
      {legs.map((leg, i) => {
        const isActive = activeLegIndex !== null && i === activeLegIndex;
        const isDone   = activeLegIndex !== null && i < activeLegIndex;
        const legClass = isActive ? " leg-active" : isDone ? " leg-complete" : "";

        if (leg.type === "walk") {
          return (
            <WalkLegItem
              key={i}
              leg={leg}
              index={i}
              completedSteps={completedSteps}
              extraClass={legClass}
            />
          );
        }
        const isBus = leg.line in BUS_DIRECTION_COLORS;
        const color = getRouteColor(leg.line);
        const pillLabel = isBus
          ? leg.line_code
          : leg.line?.replace(" Line", "");
        const isTransferLeg = seenTransit;
        seenTransit = true;
        const xferWait = leg.transfer_wait_minutes;
        const xferNote =
          isTransferLeg && xferWait !== undefined && xferWait !== null
            ? (xferWait === 0 ? "⏱ Due" : `⏱ ${xferWait} min wait`)
            : null;

        const stopId    = leg.from_mapid;
        const stopType  = isBus ? "bus" : "train";
        const isPinned  = !!stopId && pinnedIds.has(`${stopType}:${stopId}`);
        const hasAlert  = activeAlertRoutes?.has(pillLabel);

        return (
          <li key={i} className={`leg leg-transit${legClass}`}>
            {isDone && <span className="leg-complete-check">✓</span>}
            {xferNote && <span className="transfer-wait-note">{xferNote}</span>}
            <LinePill line={leg.line} isBus={isBus} lineCode={leg.line_code} size="sm" />
            {hasAlert && <span className="leg-alert-badge" title="Service alert active">⚠</span>}
            <span className="leg-text">
              {leg.from} → {leg.to}
              <span className="leg-duration"> · {leg.minutes} min</span>
            </span>
            {stopId && onPinToggle && (
              <button
                className={`pin-btn${isPinned ? " pin-btn--pinned" : ""}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onPinToggle(stopType, stopId, leg.from, leg.line_code || "", isPinned);
                }}
                title={isPinned ? t("unpin_stop", { stop: leg.from }) : t("pin_stop", { stop: leg.from })}
                aria-label={isPinned ? t("unpin_stop", { stop: leg.from }) : t("pin_stop", { stop: leg.from })}
              >
                {isPinned ? "📌" : "📍"}
              </button>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export default memo(function RouteCard({
  route, index, isFirst, isSelected, onSelect,
  tripActive, activeLegIndex, completedSteps, onStartTrip, onStopTrip,
  tripGeoError, onDismissTripGeoError,
  onVehicle, onToggleVehicle,
  pinnedStops, onPinToggle, activeAlertRoutes,
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(isFirst);
  const activeLeg = (tripActive && activeLegIndex !== null) ? route.legs[activeLegIndex] : null;
  const isTransitLeg = activeLeg?.type === 'transit';
  const transitLabel = isTransitLeg
    ? (activeLeg.line_code ? `Bus ${activeLeg.line_code}` : (activeLeg.line || ''))
    : '';
  const waitNote =
    route.wait_minutes == null ? ""
    : route.wait_minutes === 0  ? ` · ${t("wait_due")}`
    : ` · ${t("wait_minutes", { minutes: route.wait_minutes })}`;
  const transfers = route.transfers ?? 0;
  const xferNote =
    transfers === 0
      ? t("label_no_transfers")
      : transfers === 1
      ? t("label_1_transfer")
      : t("label_n_transfers", { count: transfers });

  const transitLines = useMemo(() => {
    const seen = new Set();
    return route.legs
      .filter(l => l.type === "transit")
      .filter(l => { if (seen.has(l.line)) return false; seen.add(l.line); return true; })
      .map(l => ({ line: l.line, isBus: l.line in BUS_DIRECTION_COLORS, lineCode: l.line_code }));
  }, [route.legs]);

  return (
    <div className={`route-card${isFirst ? " route-card--best paper-grain-bright" : ""}${isSelected ? " route-card--selected" : ""}`}>
      <button
        className="route-card-header"
        onClick={() => { onSelect(); setExpanded((v) => !v); }}
        aria-expanded={expanded}
        aria-label={`${route.total_minutes} minutes total, ${xferNote}${waitNote}`}
      >
        <div className="route-card-left">
          <span className="route-minutes" aria-hidden="true">{route.total_minutes}</span>
        </div>
        <div className="route-card-right">
          {isFirst && <span className="route-badge">★ {t("badge_best")}</span>}
          <span className="route-minutes-label" aria-hidden="true">MIN TOTAL</span>
          <span className="route-meta">{xferNote}{waitNote}</span>
          {transitLines.length > 0 && (
            <div className="route-pills-row" aria-hidden="true">
              {transitLines.map((tl, i) => (
                <LinePill key={i} line={tl.line} isBus={tl.isBus} lineCode={tl.lineCode} size="sm" />
              ))}
            </div>
          )}
        </div>
        <span className="route-chevron" aria-hidden="true">{expanded ? "▿" : "▵"}</span>
      </button>
      {expanded && (
        <RouteLegs
          legs={route.legs}
          activeLegIndex={isSelected ? activeLegIndex : null}
          completedSteps={isSelected ? completedSteps : null}
          pinnedStops={pinnedStops}
          onPinToggle={onPinToggle}
          activeAlertRoutes={activeAlertRoutes}
        />
      )}
      {isSelected && (
        <div className="route-card-trip-footer">
          {tripActive && isTransitLeg && (
            <button
              className={`on-vehicle-btn${onVehicle ? ' on-vehicle-btn--active' : ''}`}
              onClick={onToggleVehicle}
              aria-pressed={onVehicle}
            >
              {onVehicle
                ? t('on_vehicle_active', { line: transitLabel })
                : t('on_vehicle_prompt', { line: transitLabel })}
            </button>
          )}
          {tripActive ? (
            <button className="stop-trip-btn" onClick={onStopTrip}>
              {t("route_stop_trip")}
            </button>
          ) : (
            <button className="start-trip-btn" onClick={onStartTrip}>
              {t("route_start_trip")}
            </button>
          )}
          {tripGeoError && (
            <div className="trip-geo-error" role="alert">
              <span>{t("geo_trip_denied")}</span>
              <button
                type="button"
                className="geo-denied-dismiss"
                onClick={onDismissTripGeoError}
                aria-label={t("aria_dismiss")}
              >×</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
});
