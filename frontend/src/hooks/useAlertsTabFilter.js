import { useMemo, useState, useCallback } from "react";
import { LINE_COLORS, stripLineSuffix } from "../lineColors.js";

// Encapsulates the Notices & Delays tab's filter state.
//
// - selectedLines / selectedBuses are session-scoped multi-select Sets
//   (L-line names like "Red"/"Blue"; bus route codes like "22"/"X9").
//   Not persisted — matches the dismissal state's session-only lifetime.
// - availableBusRoutes is derived from the live alerts feed: anything in an
//   alert's `routes` array that isn't a known L line is treated as a bus.
// - filteredAlertsForTab is the union of both selection sets applied to the
//   undismissed feed. When both selections are empty, returns [] so the UI
//   can show its "pick a line/bus" prompt.
// - viewRouteAlerts(routeLineCodes) pre-fills both selection Sets from a
//   Set<string> of route codes (mix of L-line names + bus codes), splitting
//   them into the correct selection by membership in LINE_COLORS.
export function useAlertsTabFilter(undismissedAlerts, currentRouteLines) {
  const [selectedLines, setSelectedLines] = useState(() => new Set());
  const [selectedBuses, setSelectedBuses] = useState(() => new Set());

  const availableBusRoutes = useMemo(() => {
    const out = new Set();
    for (const a of undismissedAlerts) {
      for (const r of a.routes ?? []) {
        const stripped = stripLineSuffix(r);
        if (!(stripped in LINE_COLORS)) out.add(stripped);
      }
    }
    return [...out];
  }, [undismissedAlerts]);

  const filteredAlertsForTab = useMemo(() => {
    if (selectedLines.size === 0 && selectedBuses.size === 0) return [];
    return undismissedAlerts.filter((a) =>
      (a.routes ?? []).some((r) => {
        const stripped = stripLineSuffix(r);
        return selectedLines.has(stripped) || selectedBuses.has(stripped);
      })
    );
  }, [undismissedAlerts, selectedLines, selectedBuses]);

  const seedFromRoute = useCallback(() => {
    const lines = new Set();
    const buses = new Set();
    if (currentRouteLines) {
      for (const code of currentRouteLines) {
        if (code in LINE_COLORS) lines.add(code);
        else buses.add(code);
      }
    }
    setSelectedLines(lines);
    setSelectedBuses(buses);
  }, [currentRouteLines]);

  return {
    selectedLines,
    setSelectedLines,
    selectedBuses,
    setSelectedBuses,
    availableBusRoutes,
    filteredAlertsForTab,
    seedFromRoute,
  };
}
