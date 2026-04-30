import React from "react";

/**
 * Destination / "TO" marker.
 * Surveyor's crosshair target on a paper-coloured pad.
 * Label weight matches OriginMarker (500) — both are coordinates, neither is primary.
 *
 * @param {Object} props
 * @param {string} [props.label]
 * @param {"left"|"right"} [props.flagSide="right"]
 * @param {boolean} [props.arrived=false] - When true, fills the ring solid ink
 *                                          and shows an italic "arrived" caption.
 *                                          One-way latch — managed by the parent.
 * @param {string} [props.paperColor="#f4ead5"]
 * @param {string} [props.inkColor="#1a1510"]
 * @param {string} [props.muteColor="#8a7a60"]
 */
export default function DestinationMarker({
  label,
  flagSide = "right",
  paperColor = "#f4ead5",
  inkColor = "#1a1510",
  muteColor = "#8a7a60",
  arrived = false,
}) {
  const W = label ? 160 : 28;
  const H = label ? 40 : 28;
  const cx = flagSide === "right" ? 14 : W - 14;
  const cy = H / 2;

  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      style={{ overflow: "visible", display: "block" }}
      aria-label={
        arrived
          ? label ? `Arrived: ${label}` : "Arrived at destination"
          : label ? `Destination: ${label}` : "Destination"
      }
      role="img"
    >
      {/* Paper backing disc */}
      <circle cx={cx} cy={cy} r="13" fill={paperColor} />
      {/* Outer ink ring — fills solid on arrival */}
      <circle cx={cx} cy={cy} r="12" fill={arrived ? inkColor : "none"} stroke={inkColor} strokeWidth="2" />
      {/* Inset hairline — hidden on arrival (solid fill covers it) */}
      {!arrived && (
        <circle cx={cx} cy={cy} r="9" fill="none" stroke={inkColor} strokeWidth="0.75" />
      )}
      {/* Crosshair — four ticks, hidden on arrival */}
      {!arrived && (
        <>
          <line x1={cx - 12} y1={cy} x2={cx - 5.5} y2={cy} stroke={inkColor} strokeWidth="1.25" />
          <line x1={cx + 5.5} y1={cy} x2={cx + 12} y2={cy} stroke={inkColor} strokeWidth="1.25" />
          <line x1={cx} y1={cy - 12} x2={cx} y2={cy - 5.5} stroke={inkColor} strokeWidth="1.25" />
          <line x1={cx} y1={cy + 5.5} x2={cx} y2={cy + 12} stroke={inkColor} strokeWidth="1.25" />
        </>
      )}
      {/* Bullseye — paper-coloured on arrival so it reads against the filled ring */}
      <circle cx={cx} cy={cy} r="3" fill={arrived ? paperColor : inkColor} />

      {/* Arrived caption */}
      {arrived && (
        <text
          x={cx}
          y={cy + 22}
          fill={inkColor}
          fontSize="10"
          fontWeight="500"
          fontFamily='"Fraunces", Georgia, serif'
          fontStyle="italic"
          textAnchor="middle"
        >
          arrived
        </text>
      )}

      {label && !arrived && (
        <g>
          <text
            x={flagSide === "right" ? cx + 18 : cx - 18}
            y={cy - 3}
            fill={muteColor}
            fontSize="8"
            fontWeight="800"
            fontFamily='"Inter", system-ui, sans-serif'
            letterSpacing="1.5"
            textAnchor={flagSide === "right" ? "start" : "end"}
          >
            TO
          </text>
          <text
            x={flagSide === "right" ? cx + 18 : cx - 18}
            y={cy + 10}
            fill={inkColor}
            fontSize="12"
            fontWeight="500"
            fontFamily='"Fraunces", Georgia, serif'
            textAnchor={flagSide === "right" ? "start" : "end"}
          >
            {label}
          </text>
        </g>
      )}
    </svg>
  );
}
