import React from "react";
import { useTranslation } from "react-i18next";

/**
 * Footprint marker — minimal walk-transition mark used at walk→transit
 * (boarding the first vehicle) and transit→walk (alighting the last vehicle).
 *
 * The adjacent dashed walking polyline does the semantic heavy lifting; the
 * dot just terminates the dash cleanly atop the route line. No center glyph,
 * no caps kicker — only an italic-Fraunces station name appears as a flag
 * when `label` is set and the marker is in selected state.
 *
 * @param {Object} props
 * @param {string}  [props.label]     Optional station name (renders as flag).
 * @param {"default"|"selected"|"passed"} [props.state="default"]
 * @param {"walk-to-transit"|"transit-to-walk"} [props.direction]
 *   Used to pick the right aria-label template; falls back to a generic key.
 * @param {"left"|"right"} [props.flagSide="right"]
 * @param {string}  [props.paperColor]
 * @param {string}  [props.inkColor]
 * @param {string}  [props.ariaLabel]
 */
function FootprintMarkerImpl({
  label,
  state = "default",
  direction,
  flagSide = "right",
  paperColor = "#f4ead5",
  inkColor = "#1a1510",
  ariaLabel,
}) {
  const { t } = useTranslation();
  const isPassed   = state === "passed";
  const isSelected = state === "selected";

  const W = label ? 140 : 12;
  const H = label ? 40  : 12;
  const cx = flagSide === "right" ? 6 : W - 6;
  const cy = H / 2;

  const ariaKey = direction === "walk-to-transit"
    ? (isPassed ? "footprint_marker_aria_walk_to_transit_passed" : "footprint_marker_aria_walk_to_transit")
    : direction === "transit-to-walk"
      ? (isPassed ? "footprint_marker_aria_transit_to_walk_passed" : "footprint_marker_aria_transit_to_walk")
      : null;

  const ariaResolved = ariaLabel ?? (
    ariaKey
      ? t(ariaKey, { station: label ?? "" })
      : t("footprint_marker_aria_default", { defaultValue: "Walk transition" })
  );

  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      style={{ overflow: "visible", display: "block" }}
      aria-label={ariaResolved}
      role="img"
    >
      {/* Passed-state outer ring */}
      {isPassed && (
        <circle cx={cx} cy={cy} r={4} fill="none" stroke={inkColor} strokeWidth="1" />
      )}
      {/* Paper backing */}
      <circle cx={cx} cy={cy} r={4} fill={paperColor} />
      {/* Ink dot (also reads as the punched fill in passed-state at this scale) */}
      <circle cx={cx} cy={cy} r={2.5} fill={inkColor} />
      {/* Selected-state outer ring */}
      {isSelected && (
        <circle cx={cx} cy={cy} r={6} fill="none" stroke={inkColor} strokeWidth="0.75" />
      )}

      {label && (
        <g>
          <text
            x={flagSide === "right" ? cx + 9 : cx - 9}
            y={cy + 4}
            fill={inkColor}
            fontSize="12"
            fontWeight="500"
            fontFamily='"Fraunces", Georgia, serif'
            fontStyle="italic"
            textAnchor={flagSide === "right" ? "start" : "end"}
          >
            {label}
          </text>
        </g>
      )}
    </svg>
  );
}

const FootprintMarker = React.memo(FootprintMarkerImpl);
export default FootprintMarker;
