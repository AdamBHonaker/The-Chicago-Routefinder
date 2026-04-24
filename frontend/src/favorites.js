// Location schema: { id: string, label: string, value: string }
// Route schema:    { id: string, label: string, origin: string, destination: string }

const LOC_KEY   = "cta_saved_locations";
const ROUTE_KEY = "cta_saved_routes";
const MAX_ITEMS = 10;

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
export function saveLocation(label, value) {
  const arr = _load(LOC_KEY);
  if (arr.length >= MAX_ITEMS) return null;
  const next = [...arr, { id: crypto.randomUUID(), label, value }];
  _save(LOC_KEY, next);
  return next;
}

export function deleteLocation(id) {
  const next = _load(LOC_KEY).filter((loc) => loc.id !== id);
  _save(LOC_KEY, next);
  return next;
}

export function getSavedRoutes() { return _load(ROUTE_KEY); }

// Returns updated array, or null if the cap is already reached.
export function saveRoute(label, origin, destination) {
  const arr = _load(ROUTE_KEY);
  if (arr.length >= MAX_ITEMS) return null;
  const next = [...arr, { id: crypto.randomUUID(), label, origin, destination }];
  _save(ROUTE_KEY, next);
  return next;
}

export function deleteRoute(id) {
  const next = _load(ROUTE_KEY).filter((r) => r.id !== id);
  _save(ROUTE_KEY, next);
  return next;
}
