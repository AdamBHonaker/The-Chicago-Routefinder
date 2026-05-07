import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BACKEND_URL } from "../constants.js";

const DISMISSED_KEY = "dismissed_alert_ids";

function loadDismissed() {
  try {
    return new Set(JSON.parse(sessionStorage.getItem(DISMISSED_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

// Owns the service-alerts feature: fetch on mount, dismissal persistence in
// sessionStorage, and the derived `undismissedAlerts` list. Extracted from
// App.jsx (TD-FE-006). Exposes `refetch()` so callers can re-pull the feed
// when the user navigates to a surface that should reflect the latest data
// (e.g., opening the Notices & Delays tab).
export function useServiceAlerts() {
  const [serviceAlerts, setServiceAlerts] = useState([]);
  const [dismissedAlertIds, setDismissedAlertIds] = useState(loadDismissed);
  const inFlightRef = useRef(null);

  const refetch = useCallback(() => {
    if (inFlightRef.current) inFlightRef.current.abort();
    const ctrl = new AbortController();
    inFlightRef.current = ctrl;
    return fetch(`${BACKEND_URL}/alerts`, { signal: ctrl.signal })
      .then((res) => res.ok ? res.json() : { alerts: [] })
      .then((data) => setServiceAlerts(data.alerts || []))
      .catch(() => {})
      .finally(() => {
        if (inFlightRef.current === ctrl) inFlightRef.current = null;
      });
  }, []);

  useEffect(() => {
    refetch();
    return () => inFlightRef.current?.abort();
  }, [refetch]);

  function dismiss(alertId) {
    setDismissedAlertIds((prev) => {
      const next = new Set(prev);
      next.add(alertId);
      try {
        sessionStorage.setItem(DISMISSED_KEY, JSON.stringify([...next]));
      } catch {}
      return next;
    });
  }

  const undismissedAlerts = useMemo(
    () => serviceAlerts.filter((a) => !dismissedAlertIds.has(a.alert_id)),
    [serviceAlerts, dismissedAlertIds]
  );

  return { undismissedAlerts, dismiss, refetch };
}
