// frontend/src/lineColors.js
//
// Canonical CTA line colors — single source of truth.
// Mirrors `Chicago Routefinder - Design System/designs/data.jsx`.
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
