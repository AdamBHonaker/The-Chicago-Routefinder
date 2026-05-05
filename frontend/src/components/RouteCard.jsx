import { useState, memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { LINE_COLORS, BUS_DIRECTION_COLORS, getRouteColor, SHARE_STATE_RESET_MS } from "../constants.js";
import LinePill from "./LinePill.jsx";
import { extractTransitLines } from "../utils/routeUtils.js";
// extractTransitLines is kept as a fallback for the rare case a caller mounts
// RouteCard without the precomputed `transitLines` prop (e.g. unit tests).

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
    const pathType = step.path_type;
    const preposition = (pathType === "crosswalk" || pathType === "pedestrian")
      ? t("step_through")
      : t("step_along");
    return (
      <li key={si} className={`leg-step${stepDone ? " leg-step--complete" : ""}`}>
        <span className="leg-step-text">
          {stepDone && <span className="leg-step-complete-check">✓</span>}
          {step.is_platform_transfer
            ? t("step_platform_transfer")
            : <>
                {si === 0 ? t("step_walk") : t("step_head")}
                {step.direction_full ? ` ${step.direction_full}` : ""}
                {step.street
                  ? <>{` ${t("step_along")} `}<span className="leg-step-street">{step.street}</span></>
                  : pathType
                  ? <>{` ${preposition} `}<span className="leg-step-street">{t(`path_type_${pathType}`)}</span></>
                  : null
                }
                {` ${t("step_for")} `}
                {formatBlocks(step.blocks ?? 1, step.block_type, t)}
              </>
          }
        </span>
      </li>
    );
  };

  return (
    <li key={index} className={`leg leg-walk${extraClass}`}>
      <span className="leg-minutes" aria-hidden="true">{leg.minutes}</span>
      <span className="leg-spine" aria-hidden="true">
        <span className="itinerary-dot" />
      </span>
      <span className="leg-content">
        {extraClass.includes("leg-complete") && <span className="leg-complete-check">✓</span>}
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
      </span>
    </li>
  );
}

function RouteLegs({ legs, initialWait, activeLegIndex, completedSteps, pinnedStops, onPinToggle, activeAlertRoutes, transferPoints, selectedTransferId, onSelectTransfer }) {
  const { t } = useTranslation();
  // Key by `${type}:${stop_id}` so bus stop_ids and train mapids never alias.
  const pinnedIds = useMemo(
    () => new Set(pinnedStops?.map((s) => `${s.type}:${s.stop_id}`) ?? []),
    [pinnedStops]
  );

  // Build lookup maps so transit leg rows know whether they're tappable.
  // boardingLegIndex → descriptor (walk-transit, transit-transit),
  // alightingLegIndex → descriptor (transit-walk only, boardingLegIndex is null there).
  const { transferByBoardingLeg, transferByAlightingLeg } = useMemo(() => {
    const boarding  = new Map();
    const alighting = new Map();
    for (const d of (transferPoints ?? [])) {
      if (d.boardingLegIndex != null)  boarding.set(d.boardingLegIndex, d);
      else if (d.alightingLegIndex != null) alighting.set(d.alightingLegIndex, d);
    }
    return { transferByBoardingLeg: boarding, transferByAlightingLeg: alighting };
  }, [transferPoints]);

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
        const xferWait = isTransferLeg ? leg.transfer_wait_minutes : initialWait;
        const xferNote =
          xferWait !== undefined && xferWait !== null
            ? (xferWait === 0 ? `⏱ ${t("wait_due")}` : `⏱ ${t("wait_minutes", { minutes: xferWait })}`)
            : null;

        const stopId    = leg.from_mapid;
        const stopType  = isBus ? "bus" : "train";
        const isPinned  = !!stopId && pinnedIds.has(`${stopType}:${stopId}`);
        const hasAlert  = activeAlertRoutes?.has(pillLabel);

        // Transfer-point interactivity: tappable during tripActive when this leg
        // corresponds to a boarding or alighting transfer point.
        const tpDescriptor = transferByBoardingLeg.get(i) ?? transferByAlightingLeg.get(i);
        const isTappable = !!(activeLegIndex !== null && tpDescriptor && onSelectTransfer);
        const tpId       = tpDescriptor ? `${tpDescriptor.alightingLegIndex ?? "s"}-${tpDescriptor.boardingLegIndex ?? "e"}` : null;
        const tpSelected = isTappable && selectedTransferId === tpId;

        const handleTransferToggle = isTappable
          ? () => onSelectTransfer(tpSelected ? null : tpId)
          : undefined;

        const dotStyle = { background: color };
        return (
          <li key={i} className={`leg leg-transit${legClass}`}>
            <span className="leg-minutes" aria-hidden="true">{leg.minutes}</span>
            {isTappable ? (
              <span
                className="leg-spine leg-spine--tappable"
                role="button"
                tabIndex={0}
                aria-pressed={tpSelected}
                aria-label={t("transfer_marker_aria", { station: tpDescriptor.stationName })}
                onClick={handleTransferToggle}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleTransferToggle(); } }}
              >
                <span className="itinerary-dot" style={dotStyle} />
              </span>
            ) : (
              <span className="leg-spine" aria-hidden="true">
                <span className="itinerary-dot" style={dotStyle} />
              </span>
            )}
            <span className="leg-content">
              {isDone && <span className="leg-complete-check">✓</span>}
              {xferNote && <span className="transfer-wait-note">{xferNote}</span>}
              <span className="leg-transit-row">
                <LinePill line={leg.line} isBus={isBus} lineCode={leg.line_code} size="sm" />
                {hasAlert && <span className="leg-alert-badge" title={t("aria_service_alert_active")}>⚠</span>}
                <span className="leg-text">
                  {leg.from} → {leg.to}
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
              </span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export default memo(function RouteCard({
  route, transitLines: transitLinesProp, index, isFirst, isSelected, onSelect,
  tripActive, activeLegIndex, completedSteps, onStartTrip, onStopTrip,
  tripGeoError, onDismissTripGeoError,
  onVehicle, onToggleVehicle,
  pinnedStops, onPinToggle, activeAlertRoutes,
  shareOrigin, shareDestination,
  transferPoints, selectedTransferId, onSelectTransfer,
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(isFirst);
  const [shareState, setShareState] = useState("idle");

  async function handleShare(e) {
    e.stopPropagation();
    const params = new URLSearchParams({ from: shareOrigin, to: shareDestination });
    if (index > 0) params.set("route", String(index));
    const shareUrl = `${window.location.origin}${window.location.pathname}?${params}`;

    const isMobile = navigator.share && /Mobi|Android/i.test(navigator.userAgent);
    if (isMobile) {
      try {
        await navigator.share({ title: t("share_title"), text: t("share_message"), url: shareUrl });
      } catch (err) {
        if (err.name !== "AbortError") { /* silently ignore */ }
      }
      return;
    }

    let copied = false;
    try {
      await navigator.clipboard.writeText(shareUrl);
      copied = true;
    } catch {
      // Fallback for non-secure contexts (navigator.clipboard requires HTTPS).
      // execCommand is deprecated but kept for local http://localhost dev sessions.
      const ta = document.createElement("textarea");
      ta.value = shareUrl;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { copied = document.execCommand("copy"); } catch { copied = false; }
      document.body.removeChild(ta);
    }
    if (copied) {
      setShareState("copied");
      setTimeout(() => setShareState("idle"), SHARE_STATE_RESET_MS);
    }
  }
  const activeLeg = (tripActive && activeLegIndex !== null) ? route.legs[activeLegIndex] : null;
  const isTransitLeg = activeLeg?.type === 'transit';
  const isBusActiveLeg = isTransitLeg && activeLeg.line in BUS_DIRECTION_COLORS;
  const transitLabel = isTransitLeg
    ? (isBusActiveLeg ? t("map_bus_label", { code: activeLeg.line_code }) : (activeLeg.line || ''))
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

  // Prefer the precomputed array passed by App.jsx (OPT-FE-104). Fall back to
  // local computation when callers (e.g. tests) mount RouteCard standalone.
  const transitLinesFallback = useMemo(
    () => (transitLinesProp ? null : extractTransitLines(route.legs)),
    [transitLinesProp, route.legs]
  );
  const transitLines = transitLinesProp ?? transitLinesFallback;

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
          <span className="route-minutes-label" aria-hidden="true">{t("label_min_total_short")}</span>
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
      <div className="route-card-actions">
        <button
          type="button"
          className={`share-btn${shareState === "copied" ? " share-btn--copied" : ""}`}
          onClick={handleShare}
          aria-label={t("aria_share_route")}
          title={t("aria_share_route")}
          aria-live="polite"
        >
          {shareState === "copied" ? t("share_copied") : "↗"}
        </button>
      </div>
      {expanded && (
        <RouteLegs
          legs={route.legs}
          initialWait={route.wait_minutes}
          activeLegIndex={isSelected ? activeLegIndex : null}
          completedSteps={isSelected ? completedSteps : null}
          pinnedStops={pinnedStops}
          onPinToggle={onPinToggle}
          activeAlertRoutes={activeAlertRoutes}
          transferPoints={isSelected ? transferPoints : undefined}
          selectedTransferId={isSelected ? selectedTransferId : null}
          onSelectTransfer={isSelected ? onSelectTransfer : undefined}
        />
      )}
      {isSelected && (
        <div className="route-card-trip-footer">
          {tripActive && isTransitLeg && (
            <button
              className={`on-vehicle-btn${onVehicle ? ' on-vehicle-btn--active' : ''}`}
              onClick={onToggleVehicle}
              aria-pressed={onVehicle}
              disabled={onVehicle}
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
