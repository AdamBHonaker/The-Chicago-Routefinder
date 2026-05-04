import { useEffect, useMemo, useState } from "react";
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
// App.jsx (TD-FE-006).
export function useServiceAlerts() {
  const [serviceAlerts, setServiceAlerts] = useState([]);
  const [dismissedAlertIds, setDismissedAlertIds] = useState(loadDismissed);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${BACKEND_URL}/alerts`, { signal: ctrl.signal })
      .then((res) => res.ok ? res.json() : { alerts: [] })
      .then((data) => setServiceAlerts(data.alerts || []))
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

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

  return { undismissedAlerts, dismiss };
}
