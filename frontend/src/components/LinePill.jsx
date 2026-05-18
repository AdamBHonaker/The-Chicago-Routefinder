import { memo } from "react";
import { useTranslation } from "react-i18next";
import { getRouteColor, BUS_DIRECTION_COLORS } from "../constants.js";
import { lineTextColor, stripLineSuffix } from "../lineColors.js";

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

function LinePill({ line, isBus, lineCode, size = "sm" }) {
  const { t } = useTranslation();
  const bg = getRouteColor(line);
  const isBusRoute = isBus || (line in BUS_DIRECTION_COLORS);
  // Buses fall back to white text on their direction-colored background; only
  // the rail Yellow Line takes dark ink (canonical D2 readability rule).
  const textColor = isBusRoute ? "#fff" : lineTextColor(line);

  let label;
  if (isBusRoute) {
    label = lineCode ?? line;
  } else if (size === "lg") {
    label = line;
  } else {
    label = LINE_ABBREVS[line] ?? (stripLineSuffix(line) ?? "").slice(0, 2).toUpperCase();
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

export default memo(LinePill);
