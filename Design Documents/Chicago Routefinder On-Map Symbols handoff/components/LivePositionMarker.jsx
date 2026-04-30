// frontend/src/components/markers/LivePositionMarker.jsx
import React from "react";

/**
 * Live user position / "YOU" marker.
 * Compass needle pointing along the device bearing, inside a pulsing rust ring.
 * The pulse is suppressed under prefers-reduced-motion.
 *
 * @param {Object} props
 * @param {number} [props.heading=0] - Device bearing in degrees (0=N, 90=E).
 * @param {boolean} [props.hasHeading=true] - When false, the needle is hidden
 *                                            and only the ring + dot show
 *                                            (e.g. when GPS heading is unknown).
 * @param {string} [props.label] - Optional flag label (rare on live position).
 * @param {string} [props.paperColor="#f4ead5"]
 * @param {string} [props.inkColor="#1a1510"]
 * @param {string} [props.accentColor="#a8482a"] - Rust (D2.accent).
 * @param {string} [props.muteColor="#8a7a60"]
 */
export default function LivePositionMarker({
  heading = 0,
  hasHeading = true,
  label,
  paperColor = "#f4ead5",
  inkColor = "#1a1510",
  accentColor = "#a8482a",
  muteColor = "#8a7a60",
}) {
  const W = label ? 140 : 36;
  const H = label ? 44 : 36;
  const cx = label ? 18 : W / 2;
  const cy = H / 2;

  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      style={{ overflow: "visible", display: "block" }}
      aria-label={label ? `You: ${label}` : "Your position"}
      role="img"
    >
      <circle
        cx={cx}
        cy={cy}
        r="14"
        fill="none"
        stroke={accentColor}
        strokeWidth="1"
        opacity="0.45"
      >
        <animate
          attributeName="r"
          values="14;18;14"
          dur="2.4s"
          repeatCount="indefinite"
        />
        <animate
          attributeName="opacity"
          values="0.45;0;0.45"
          dur="2.4s"
          repeatCount="indefinite"
        />
      </circle>

      <circle cx={cx} cy={cy} r="11" fill={paperColor} stroke={accentColor} strokeWidth="1.5" />

      <line x1={cx} y1={cy - 11} x2={cx} y2={cy - 8} stroke={accentColor} strokeWidth="1" />
      <line x1={cx} y1={cy + 11} x2={cx} y2={cy + 8} stroke={accentColor} strokeWidth="1" />
      <line x1={cx - 11} y1={cy} x2={cx - 8} y2={cy} stroke={accentColor} strokeWidth="1" />
      <line x1={cx + 11} y1={cy} x2={cx + 8} y2={cy} stroke={accentColor} strokeWidth="1" />

      {hasHeading && (
        <g transform={`rotate(${heading} ${cx} ${cy})`} style={{ transition: "transform 200ms linear" }}>
          <path d={`M ${cx},${cy - 8} L ${cx + 3},${cy + 2} L ${cx},${cy} L ${cx - 3},${cy + 2} Z`} fill={accentColor} />
          <path d={`M ${cx},${cy + 8} L ${cx + 2},${cy + 2} L ${cx},${cy} L ${cx - 2},${cy + 2} Z`} fill={inkColor} opacity="0.4" />
        </g>
      )}

      <circle cx={cx} cy={cy} r="1.4" fill={inkColor} />

      {label && (
        <g>
          <text
            x={cx + 22}
            y={cy - 3}
            fill={muteColor}
            fontSize="8"
            fontWeight="800"
            fontFamily='"Inter", system-ui, sans-serif'
            letterSpacing="1.5"
          >
            YOU
          </text>
          <text
            x={cx + 22}
            y={cy + 10}
            fill={inkColor}
            fontSize="12"
            fontWeight="500"
            fontFamily='"Fraunces", Georgia, serif'
            fontStyle="italic"
          >
            {label}
          </text>
        </g>
      )}
    </svg>
  );
}
