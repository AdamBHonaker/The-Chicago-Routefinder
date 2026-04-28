// ---------------------------------------------------------------------------
// Geolocation option objects — used in both the one-shot location detect flow
// (handleGeoClick) and the live trip-tracking watchPosition call (startTrip).
// Keeping them as named constants prevents the two call-sites from drifting
// apart (e.g. mismatched maximumAge values — TD-021).
// ---------------------------------------------------------------------------
export const GEO_OPTIONS = {
  enableHighAccuracy: true,
  timeout: 10000,
  maximumAge: 30000, // tolerate a 30-s cached fix for one-shot detection
};

export const TRIP_GEO_OPTIONS = {
  enableHighAccuracy: true,
  timeout: 10000,
  maximumAge: 15000, // tighter cache for live trip tracking — fresher fixes
};

// ---------------------------------------------------------------------------
// Off-route detection threshold (TD-020).
// A walk path segment farther than this means the user has left the route.
// 400 m chosen as the smallest distance that avoids false positives on
// typical Chicago city blocks (~200 m) while still triggering usefully early.
// ---------------------------------------------------------------------------
export const OFF_ROUTE_THRESHOLD_METERS = 400;

// ---------------------------------------------------------------------------
// Back-off delays for fetchWithRetry (TD-022).
// Three attempts: 1 s → 2 s → 4 s. Only used on 5xx / network errors.
// ---------------------------------------------------------------------------
export const RETRY_DELAYS_MS = [1000, 2000, 4000];

export const LINE_COLORS = {
  "Red Line":    "#c60c30",
  "Blue Line":   "#00a1de",
  "Brown Line":  "#62361b",
  "Green Line":  "#009b3a",
  "Orange Line": "#f9461c",
  "Purple Line": "#522398",
  "Pink Line":   "#e27ea6",
  "Yellow Line": "#f9e300",
};

export const BUS_DIRECTION_COLORS = {
  Northbound: "#1565c0",
  Southbound: "#4e342e",
  Eastbound:  "#00695c",
  Westbound:  "#ef6c00",
};

// ---------------------------------------------------------------------------
// BYOK API key validation (TD-023).
// Anthropic keys currently begin with "sk-ant-". If Anthropic changes the key
// format, update this predicate and revisit when upgrading the Anthropic SDK.
// ---------------------------------------------------------------------------
export function isValidByokKey(key) {
  const trimmed = key.trim();
  return trimmed === "" || trimmed.startsWith("sk-ant-");
}

// ---------------------------------------------------------------------------
// BYOK idle-clear timeout (TD-026).
// Security parameter: the user's API key is wiped from sessionStorage after
// this many milliseconds of mouse/keyboard inactivity. 30 minutes is long
// enough for an active session but limits exposure on a shared or unattended
// device. Do not raise without a documented security review.
// ---------------------------------------------------------------------------
export const BYOK_IDLE_TIMEOUT_MS = 30 * 60 * 1000;

// ---------------------------------------------------------------------------
// Reroute suppression window (TD-025).
// After the user dismisses the off-route banner, automatic rerouting is
// suppressed for this many milliseconds. 90 s gives enough time to complete a
// crossing or deliberate detour before the system re-evaluates the route.
// ---------------------------------------------------------------------------
export const REROUTE_SUPPRESSION_MS = 90_000;
