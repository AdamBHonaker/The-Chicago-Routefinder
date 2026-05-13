/**
 * Trip-resume persistence (BUG: trip state lost when PWA is backgrounded
 * and the OS evicts the page).
 *
 * Two blobs are written together while a trip is active:
 *   - TRIP_STATE_KEY: tracker state (active flag, leg index, completed steps,
 *     onVehicle). Owned by useTripTracker.
 *   - TRIP_PLAN_KEY:  the route plan (origin/destination strings, full
 *     `result` payload, selectedRouteIndex). Owned by App.
 *
 * Both keys share a single TTL — 4 hours from the last write. That covers
 * any realistic single Chicago transit trip plus a long layover/errand, but
 * is short enough that yesterday's commute will not resurrect today.
 *
 * Volatile fields (userPosition, isOffRoute, tripGeoError, watchId,
 * suppressRerouteUntil) are intentionally NOT persisted — GPS will repopulate
 * within seconds and stale coords could mis-advance legs on resume.
 */

export const TRIP_STATE_KEY = "crf:tripState";
export const TRIP_PLAN_KEY  = "crf:tripPlan";
export const TRIP_TTL_MS    = 4 * 60 * 60 * 1000;

export function loadPersistedTrip(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed.savedAt !== "number") return null;
    if (Date.now() - parsed.savedAt > TRIP_TTL_MS) {
      try { localStorage.removeItem(key); } catch { /* noop */ }
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function savePersistedTrip(key, payload) {
  try {
    localStorage.setItem(
      key,
      JSON.stringify({ ...payload, savedAt: Date.now() }),
    );
  } catch {
    // Storage unavailable (quota / private browsing) — resume is best-effort.
  }
}

export function clearPersistedTrip(key) {
  try { localStorage.removeItem(key); } catch { /* noop */ }
}

export function clearAllTripPersistence() {
  clearPersistedTrip(TRIP_STATE_KEY);
  clearPersistedTrip(TRIP_PLAN_KEY);
}
