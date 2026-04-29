import { getRouteColor } from "../constants.js";

const LINE_ABBREVS = {
  "Red Line":    "RD",
  "Blue Line":   "BL",
  "Brown Line":  "BR",
  "Green Line":  "GR",
  "Orange Line": "OR",
  "Purple Line": "PU",
  "Pink Line":   "PI",
  "Yellow Line": "YL",
};

export default function LinePill({ line, isBus, lineCode, size = "sm" }) {
  const bg = getRouteColor(line);
  const textColor = line === "Yellow Line" ? "#111" : "#fff";

  let label;
  if (isBus) {
    label = lineCode ?? line;
  } else if (size === "lg") {
    label = line;
  } else {
    label = LINE_ABBREVS[line] ?? (line ?? "").replace(" Line", "").slice(0, 2).toUpperCase();
  }

  return (
    <span
      className={`lin-pill lin-pill--${size}`}
      style={{ background: bg, color: textColor }}
      aria-label={isBus ? `Bus ${lineCode}` : line}
    >
      {label}
    </span>
  );
}
