import React from "react";
import { useTranslation } from "react-i18next";

/**
 * Editorial transfer marker — a double-ruled small circle with a Fraunces-italic
 * × glyph at center. Renders at points where the rider changes vehicle/mode
 * during an active trip (rail↔rail, rail↔bus, bus↔bus).
 *
 * State semantics:
 *   - "default" — neutral, tap to select
 *   - "selected" — adds a hairline outline 3px outside the outer rule (ink, not rust)
 *   - "passed"   — punched-ticket idiom: outer ring + ink-filled interior
 *   - selected + passed stack: passed fill plus an outer selected ring at r=10
 *
 * The design system reserves rust strictly for the live-position ring; selected
 * and passed both use ink. State is conveyed by layered linework, not color.
 *
 * @param {Object} props
 * @param {string}  [props.label]      Optional station name (renders as flag).
 * @param {"default"|"selected"|"passed"} [props.state="default"]
 * @param {"left"|"right"} [props.flagSide="right"]
 * @param {string}  [props.paperColor]
 * @param {string}  [props.inkColor]
 * @param {string}  [props.muteColor]
 * @param {string}  [props.ariaLabel]
 */
function TransferMarkerImpl({
  label,
  state = "default",
  flagSide = "right",
  paperColor = "#f4ead5",
  inkColor = "#1a1510",
  muteColor = "#8a7a60",
  ariaLabel,
}) {
  const { t } = useTranslation();
  const isPassed   = state === "passed";
  const isSelected = state === "selected";

  // Marker box is 22x22 around center; widen for label.
  const W = label ? 140 : 22;
  const H = label ? 40  : 22;
  const cx = flagSide === "right" ? 11 : W - 11;
  const cy = H / 2;

  // aria-label: when not provided, build from i18n template based on state.
  const ariaResolved = ariaLabel ?? (
    label
      ? (isPassed
          ? t("transfer_marker_aria_passed", { station: label })
          : t("transfer_marker_aria",        { station: label }))
      : t("transfer_marker_aria_default", { defaultValue: "Transfer" })
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
      {/* Passed-state outer ring (drawn first so subsequent shapes paint on top) */}
      {isPassed && (
        <circle cx={cx} cy={cy} r={9} fill="none" stroke={inkColor} strokeWidth="1" />
      )}
      {/* Paper backing */}
      <circle cx={cx} cy={cy} r={8} fill={paperColor} />
      {/* Passed-state interior ink fill (sits behind the inset hairline) */}
      {isPassed && (
        <circle cx={cx} cy={cy} r={5} fill={inkColor} />
      )}
      {/* Outer ink ring */}
      <circle cx={cx} cy={cy} r={7} fill="none" stroke={inkColor} strokeWidth="2" />
      {/* Inset hairline */}
      <circle cx={cx} cy={cy} r={5} fill="none" stroke={inkColor} strokeWidth="0.75" />
      {/* Center glyph: Fraunces italic ×. On passed fill, draw in paper for legibility. */}
      <text
        x={cx} y={cy + 2.2}
        fontSize="6"
        fontWeight="700"
        fill={isPassed ? paperColor : inkColor}
        fontFamily='"Fraunces", Georgia, serif'
        fontStyle="italic"
        textAnchor="middle"
      >
        ×
      </text>
      {/* Selected-state outer ring (drawn after passed ring so it sits outside it) */}
      {isSelected && (
        <circle cx={cx} cy={cy} r={10} fill="none" stroke={inkColor} strokeWidth="0.75" />
      )}

      {label && (
        <g>
          <text
            x={flagSide === "right" ? cx + 14 : cx - 14}
            y={cy - 3}
            fill={muteColor}
            fontSize="8"
            fontWeight="800"
            fontFamily='"Inter", system-ui, sans-serif'
            letterSpacing="1.5"
            textAnchor={flagSide === "right" ? "start" : "end"}
          >
            {t("transfer_marker_kicker")}
          </text>
          <text
            x={flagSide === "right" ? cx + 14 : cx - 14}
            y={cy + 9}
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

const TransferMarker = React.memo(TransferMarkerImpl);
export default TransferMarker;
