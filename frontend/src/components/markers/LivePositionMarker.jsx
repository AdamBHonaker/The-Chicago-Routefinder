import React from "react";

/**
 * Live user position / "YOU" marker.
 * Compass needle pointing along the device bearing, inside a pulsing rust ring.
 * Note: no flagSide prop — the label always extends to the right. The live marker
 * is a moving element and is always placed away from the route polyline, so a fixed
 * right-side label is acceptable. Add flagSide if that assumption ever changes.
 *
 * @param {Object} props
 * @param {number} [props.heading=0] - Device bearing in degrees (0=N, 90=E).
 *                                     Should be pre-smoothed by the parent via smoothHeading().
 * @param {boolean} [props.hasHeading=true] - When false, the needle is hidden
 *                                            and only the ring + dot show.
 * @param {boolean} [props.reducedMotion=false] - When true, suppresses <animate> nodes entirely.
 *                                                Parent should derive from window.matchMedia.
 * @param {string} [props.label]
 * @param {string} [props.paperColor="#f4ead5"]
 * @param {string} [props.inkColor="#1a1510"]
 * @param {string} [props.accentColor="#a8482a"] - Rust (D2.accent).
 * @param {string} [props.muteColor="#8a7a60"]
 */
export default function LivePositionMarker({
  heading = 0,
  hasHeading = true,
  reducedMotion = false,
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
      className="marker-live-position"
      style={{ overflow: "visible", display: "block" }}
      aria-label={label ? `You: ${label}` : "Your position"}
      role="img"
    >
      {/* Pulse ring */}
      <circle
        cx={cx}
        cy={cy}
        r="14"
        fill="none"
        stroke={accentColor}
        strokeWidth="1"
        opacity="0.45"
      >
        {!reducedMotion && (
          <>
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
          </>
        )}
      </circle>

      {/* Paper backing for the compass card */}
      <circle cx={cx} cy={cy} r="11" fill={paperColor} stroke={accentColor} strokeWidth="1.5" />

      {/* Cardinal ticks (always-on orientation hint) */}
      <line x1={cx} y1={cy - 11} x2={cx} y2={cy - 8} stroke={accentColor} strokeWidth="1" />
      <line x1={cx} y1={cy + 11} x2={cx} y2={cy + 8} stroke={accentColor} strokeWidth="1" />
      <line x1={cx - 11} y1={cy} x2={cx - 8} y2={cy} stroke={accentColor} strokeWidth="1" />
      <line x1={cx + 11} y1={cy} x2={cx + 8} y2={cy} stroke={accentColor} strokeWidth="1" />

      {/* Compass needle — CSS transform so the transition actually works */}
      {hasHeading && (
        <g style={{
          transform: `rotate(${heading}deg)`,
          transformOrigin: `${cx}px ${cy}px`,
          transition: "transform 200ms linear",
        }}>
          {/* Forward (rust) blade */}
          <path d={`M ${cx},${cy - 8} L ${cx + 3},${cy + 2} L ${cx},${cy} L ${cx - 3},${cy + 2} Z`} fill={accentColor} />
          {/* Reverse (ink, soft) blade */}
          <path d={`M ${cx},${cy + 8} L ${cx + 2},${cy + 2} L ${cx},${cy} L ${cx - 2},${cy + 2} Z`} fill={inkColor} opacity="0.4" />
        </g>
      )}

      {/* Center pin */}
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
            textAnchor="start"
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
            textAnchor="start"
          >
            {label}
          </text>
        </g>
      )}
    </svg>
  );
}
