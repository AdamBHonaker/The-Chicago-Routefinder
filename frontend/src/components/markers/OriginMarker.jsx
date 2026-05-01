import React from "react";

/**
 * Origin / "FROM" marker.
 * Italic silcrow (§) inside a double-ruled ink square on a paper-coloured pad.
 * @param {Object} props
 * @param {string} [props.label] - Optional place name, set as italic Fraunces flag.
 * @param {"left"|"right"} [props.flagSide="right"] - Which side of the mark the label sits.
 * @param {string} [props.paperColor="#f4ead5"] - Paper backing colour (defaults to D2.bg).
 * @param {string} [props.inkColor="#1a1510"] - Ink colour (defaults to D2.ink).
 * @param {string} [props.muteColor="#8a7a60"] - Mute colour for the FROM kicker.
 */
export default function OriginMarker({
  label,
  fromLabel = "FROM",
  ariaLabel,
  flagSide = "right",
  paperColor = "#f4ead5",
  inkColor = "#1a1510",
  muteColor = "#8a7a60",
}) {
  const W = label ? 140 : 28;
  const H = label ? 40 : 28;
  const cx = flagSide === "right" ? 14 : W - 14;

  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      style={{ overflow: "visible", display: "block" }}
      aria-label={ariaLabel ?? (label ? `Origin: ${label}` : "Origin")}
      role="img"
    >
      {/* Paper backing — strokes must read on any tile fill */}
      <rect x={cx - 11} y={H / 2 - 11} width="22" height="22" fill={paperColor} />
      {/* Outer ink frame */}
      <rect x={cx - 11} y={H / 2 - 11} width="22" height="22"
        fill="none" stroke={inkColor} strokeWidth="2" />
      {/* Inset hairline (the editorial double-rule) */}
      <rect x={cx - 8} y={H / 2 - 8} width="16" height="16"
        fill="none" stroke={inkColor} strokeWidth="0.75" />
      {/* Italic silcrow */}
      <text x={cx} y={H / 2 + 5.5} fontSize="16" fontWeight="700" fill={inkColor}
        fontFamily='"Fraunces", Georgia, serif' fontStyle="italic" textAnchor="middle">
        §
      </text>

      {label && (
        <g>
          {/* Caps kicker */}
          <text
            x={flagSide === "right" ? cx + 16 : cx - 16}
            y={H / 2 - 3}
            fill={muteColor}
            fontSize="8"
            fontWeight="800"
            fontFamily='"Inter", system-ui, sans-serif'
            letterSpacing="1.5"
            textAnchor={flagSide === "right" ? "start" : "end"}
          >
            {fromLabel}
          </text>
          {/* Place name */}
          <text
            x={flagSide === "right" ? cx + 16 : cx - 16}
            y={H / 2 + 9}
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
