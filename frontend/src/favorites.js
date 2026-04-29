// Location schema:     { id: string, label: string, value: string }
// Route schema:        { id: string, label: string, origin: string, destination: string }
// Pinned stop schema:  { id: string, type: "train"|"bus", stop_id: string, label: string, route_hint: string }

const LOC_KEY    = "cta_saved_locations";
const ROUTE_KEY  = "cta_saved_routes";
const PINNED_KEY = "cta_pinned_stops";
// 10 keeps localStorage payload small and the dropdown list scannable without scrolling.
const MAX_ITEMS  = 10;

function _load(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || "[]");
  } catch {
    return [];
  }
}

function _save(key, arr) {
  localStorage.setItem(key, JSON.stringify(arr));
}

export function getSavedLocations() { return _load(LOC_KEY); }

// Returns updated array, or null if the cap is already reached.
export function saveLocation(label, value, current) {
  if (current.length >= MAX_ITEMS) return null;
  const next = [...current, { id: crypto.randomUUID(), label, value }];
  _save(LOC_KEY, next);
  return next;
}

export function deleteLocation(id, current) {
  const next = current.filter((loc) => loc.id !== id);
  _save(LOC_KEY, next);
  return next;
}

export function getSavedRoutes() { return _load(ROUTE_KEY); }

// Returns updated array, or null if the cap is already reached.
export function saveRoute(label, origin, destination, current) {
  if (current.length >= MAX_ITEMS) return null;
  const next = [...current, { id: crypto.randomUUID(), label, origin, destination }];
  _save(ROUTE_KEY, next);
  return next;
}

export function deleteRoute(id, current) {
  const next = current.filter((r) => r.id !== id);
  _save(ROUTE_KEY, next);
  return next;
}

export function getPinnedStops() { return _load(PINNED_KEY); }

// Returns updated array, or null if the cap is already reached.
// Duplicate check matches on both type AND stop_id — bus stop_ids and train mapids
// are separate namespaces and can collide on the same numeric value.
export function pinStop(type, stop_id, label, route_hint, current) {
  if (current.some((s) => s.type === type && s.stop_id === stop_id)) return current;
  if (current.length >= MAX_ITEMS) return null;
  const next = [...current, { id: crypto.randomUUID(), type, stop_id, label, route_hint }];
  _save(PINNED_KEY, next);
  return next;
}

export function unpinStop(id, current) {
  const next = current.filter((s) => s.id !== id);
  _save(PINNED_KEY, next);
  return next;
}

