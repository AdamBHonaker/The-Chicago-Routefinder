import { useTranslation } from "react-i18next";
import { getRouteColor, BUS_DIRECTION_COLORS } from "../constants.js";

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
  const { t } = useTranslation();
  const bg = getRouteColor(line);
  const textColor = line === "Yellow Line" ? "#111" : "#fff";
  const isBusRoute = isBus || (line in BUS_DIRECTION_COLORS);

  let label;
  if (isBusRoute) {
    label = lineCode ?? line;
  } else if (size === "lg") {
    label = line;
  } else {
    label = LINE_ABBREVS[line] ?? (line ?? "").replace(" Line", "").slice(0, 2).toUpperCase();
  }

  const len = (label ?? "").length;
  const fontStyle = (size === "sm" || size === "md") && len >= 3
    ? { fontSize: size === "sm" ? "7px" : "9px", letterSpacing: 0 }
    : {};

  return (
    <span
      className={`lin-pill lin-pill--${size}`}
      style={{ background: bg, color: textColor, ...fontStyle }}
      aria-label={isBusRoute ? t("map_bus_label", { code: lineCode }) : line}
    >
      {label}
    </span>
  );
}
