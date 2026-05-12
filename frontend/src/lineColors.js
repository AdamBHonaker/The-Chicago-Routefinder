// frontend/src/lineColors.js
//
// Canonical CTA line colors — single source of truth.
// Mirrors `Design Documents/design-system/data.jsx`.
// Do NOT add, remove, or recolor lines without updating the design system in lockstep.

export const LINE_COLORS = {
  Red:    "#c60c30",
  Blue:   "#00a1de",
  Brown:  "#62361b",
  Green:  "#009b3a",
  Orange: "#f9461c",
  Purple: "#522398",
  Pink:   "#e27ea6",
  Yellow: "#f9e300",
};

// Maps the raw CTA Train Tracker `rt` code (as returned by the backend's
// /stop-arrivals endpoint in each train arrival's `route` field) to the
// canonical "<Color> Line" name used by LINE_COLORS / LINE_ABBREVS / pills.
// Source: backend/cta_client.py:LINE_NAMES.
export const TRAIN_LINE_CODE_TO_NAME = {
  Red:  "Red Line",
  Blue: "Blue Line",
  Brn:  "Brown Line",
  G:    "Green Line",
  Org:  "Orange Line",
  P:    "Purple Line",
  Pink: "Pink Line",
  Y:    "Yellow Line",
};

// Accepts either bare ("Red") or backend-style ("Red Line"). Returns bare.
function normalizeLine(line) {
  if (!line) return line;
  return line.endsWith(" Line") ? line.slice(0, -5) : line;
}

// Yellow text on Yellow pill is unreadable; spec assigns dark ink for it.
// Returns the correct foreground color for any line.
export function lineTextColor(line) {
  return normalizeLine(line) === "Yellow" ? "#111111" : "#ffffff";
}

// Bus is not a rail line; spec falls back to ink.
export function lineColor(line) {
  return LINE_COLORS[normalizeLine(line)] ?? "#171310"; // --ink
}
