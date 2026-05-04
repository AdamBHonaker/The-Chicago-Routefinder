// Pure helpers for the newspaper-style masthead. Kept module-private to
// Masthead.jsx; exported only so unit tests can drive them deterministically.

export function toRoman(n) {
  const vals = [10, 9, 5, 4, 1];
  const syms = ["X", "IX", "V", "IV", "I"];
  let r = "";
  for (let i = 0; i < vals.length; i++) {
    while (n >= vals[i]) { r += syms[i]; n -= vals[i]; }
  }
  return r;
}

export function dayOfYear(d) {
  return Math.floor((d - new Date(d.getFullYear(), 0, 0)) / 864e5);
}

export function formatMastheadDate(date) {
  return date.toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric",
  }).toUpperCase();
}

export function formatMastheadVol(date, epochYear) {
  return `VOL. ${toRoman(date.getFullYear() - epochYear)} · NO. ${dayOfYear(date)}`;
}

// Milliseconds until the next local-midnight, used to schedule a re-render
// so the masthead date rolls over without a manual reload.
export function msUntilNextMidnight(now = new Date()) {
  const next = new Date(now);
  next.setHours(24, 0, 0, 0);
  return next - now;
}
