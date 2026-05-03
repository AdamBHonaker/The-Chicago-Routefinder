// ---------------------------------------------------------------------------
// Backend URL — falls back to localhost:8000 so `npm run dev` works without .env.local.
// Production builds always have VITE_BACKEND_URL set via .env.production / Vercel env vars.
// ---------------------------------------------------------------------------
export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Timing constants for LocationInput and related UI (TD-014).
// Named so the two different 3000 ms uses are distinguishable at call-sites.
// ---------------------------------------------------------------------------
export const AC_DEBOUNCE_MS          = 200;   // autocomplete keypress debounce
export const DROPDOWN_BLUR_DELAY_MS  = 150;   // blur→close delay so mousedown fires first
export const GEO_ERROR_RESET_MS      = 3000;  // geo unavailable / no-API error reset
export const GEO_UNAVAILABLE_RESET_MS = 4000; // non-denied geo error reset (longer grace)
export const LIMIT_ERROR_DISMISS_MS  = 3000;  // save-limit banner auto-dismiss

// ---------------------------------------------------------------------------
// Geolocation option objects — used in both the one-shot location detect flow
// (handleGeoClick) and the live trip-tracking watchPosition call (startTrip).
// Keeping them as named constants prevents the two call-sites from drifting
// apart (e.g. mismatched maximumAge values — TD-021).
// ---------------------------------------------------------------------------
export const GEO_OPTIONS = {
  enableHighAccuracy: true,
  timeout: 10000,
  maximumAge: 0, // always request a fresh fix — stale cached positions can resolve to IP-based location near the Loop
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

// Backend sends line names with a " Line" suffix; canonical hex values live in
// src/lineColors.js (mirrors the design system's data.jsx). This map adapts the
// API-style key to the same hex values.
import { LINE_COLORS as D2_LINE_COLORS } from "./lineColors.js";

export const LINE_COLORS = {
  "Red Line":    D2_LINE_COLORS.Red,
  "Blue Line":   D2_LINE_COLORS.Blue,
  "Brown Line":  D2_LINE_COLORS.Brown,
  "Green Line":  D2_LINE_COLORS.Green,
  "Orange Line": D2_LINE_COLORS.Orange,
  "Purple Line": D2_LINE_COLORS.Purple,
  "Pink Line":   D2_LINE_COLORS.Pink,
  "Yellow Line": D2_LINE_COLORS.Yellow,
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
// Route color lookup — shared by RouteCard, PinnedStopsBoard, and MapView (TD-012).
// Checks LINE_COLORS first (train lines), then BUS_DIRECTION_COLORS, then fallback.
// ---------------------------------------------------------------------------
export function getRouteColor(line, fallback = "#4a9eff") {
  return LINE_COLORS[line] ?? BUS_DIRECTION_COLORS[line] ?? fallback;
}

// ---------------------------------------------------------------------------
// Reroute suppression window (TD-025).
// After the user dismisses the off-route banner, automatic rerouting is
// suppressed for this many milliseconds. 90 s gives enough time to complete a
// crossing or deliberate detour before the system re-evaluates the route.
// ---------------------------------------------------------------------------
export const REROUTE_SUPPRESSION_MS = 90_000;

// ---------------------------------------------------------------------------
// Trip-tracking proximity thresholds (TD-106).
// Used by processTripPosition in App.jsx. Kept here so all GPS-related
// thresholds are tuneable in one file.
//   - LEG_ADVANCE_RADIUS_M: snap to the next leg when within this distance
//     of the current leg's endpoint.
//   - LEG_ADVANCE_RADIUS_VEHICLE_M: wider radius when the user has confirmed
//     they are on a transit vehicle, since GPS lags behind a moving vehicle.
//   - WALK_STEP_PROXIMITY_M: mark a walk-step complete when the user is
//     within this distance of its start coordinate.
// ---------------------------------------------------------------------------
export const LEG_ADVANCE_RADIUS_M         = 60;
export const LEG_ADVANCE_RADIUS_VEHICLE_M = 150;
export const WALK_STEP_PROXIMITY_M        = 30;

// ---------------------------------------------------------------------------
// Photo fade-out duration (TD-108).
// Must match the CSS transition duration on `.transit-photo--fading` in App.css.
// ---------------------------------------------------------------------------
export const PHOTO_FADE_MS = 1000;

// ---------------------------------------------------------------------------
// Share button reset delay — how long the "Copied" state shows before
// reverting to the share icon in RouteCard.
// ---------------------------------------------------------------------------
export const SHARE_STATE_RESET_MS = 2000;

// ---------------------------------------------------------------------------
// Masthead epoch year (TD-109). The newspaper-style "VOL." number on the
// header is computed as (currentYear - MASTHEAD_EPOCH_YEAR). The epoch is the
// year this project was first published.
// ---------------------------------------------------------------------------
export const MASTHEAD_EPOCH_YEAR = 2022;

// ---------------------------------------------------------------------------
// BYOK feature flag — set VITE_BYOK_ENABLED=true in frontend/.env to show
// the settings panel and include the user's key in requests.
// The backend must also have BYOK_ENABLED=true to honour the key.
// ---------------------------------------------------------------------------
export const BYOK_ENABLED = import.meta.env.VITE_BYOK_ENABLED === "true";
