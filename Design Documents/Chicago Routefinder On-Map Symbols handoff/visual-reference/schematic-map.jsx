// SchematicMap — stylized CTA-style schematic that all designs share.
// Not a real map; a typography-forward subway-map diagram showing
// Logan Square → Art Institute via the Blue Line.

function SchematicMap({
  theme = "dark",          // "dark" | "light" | "paper" | "board" | "brand"
  activeLine = "Blue",
  showLabels = true,
  showLegend = true,
  compact = false,
  style = {},
}) {
  const palettes = {
    dark:  { bg: "#0e0e10", ink: "#e8e8ec", mute: "#5a5a62", station: "#1c1c22", inactive: "#2a2a30", lake: "#143244", river: "#2a3a2a" },
    light: { bg: "#fafaf6", ink: "#1a1a1a", mute: "#888",    station: "#fff",     inactive: "#d8d5cc", lake: "#cedde2", river: "#cbd4c5" },
    paper: { bg: "#f2ece0", ink: "#1a1510", mute: "#8a7a60", station: "#fffbef",  inactive: "#c9bfa8", lake: "#cedde2", river: "#cbd4c5" },
    board: { bg: "#0a0906", ink: "#ffb347", mute: "#6b4a1a", station: "#1a1306",  inactive: "#3a2a10", lake: "#152028", river: "#1c2418" },
    brand: { bg: "#f5f3ee", ink: "#111",    mute: "#888",    station: "#fff",     inactive: "#d0ccc2", lake: "#cedde2", river: "#cbd4c5" },
  };
  const p = palettes[theme] || palettes.dark;
  const C = {
    Red: "#c60c30", Blue: "#00a1de", Brown: "#62361b", Green: "#009b3a",
    Orange: "#f9461c", Purple: "#522398", Pink: "#e27ea6", Yellow: "#f9e300",
  };

  // Station layout (coordinate-system: 600×420 viewbox)
  // Lines drawn as clean orthogonal segments, like a real transit map.
  const stations = {
    LoganSq:    { x: 80,  y: 110, label: "Logan Square" },
    California: { x: 130, y: 150, label: "California" },
    Western:    { x: 180, y: 180, label: "Western" },
    Damen:      { x: 225, y: 205, label: "Damen" },
    Division:   { x: 270, y: 225, label: "Division" },
    Chicago:    { x: 320, y: 240, label: "Chicago" },
    ClarkLake:  { x: 390, y: 260, label: "Clark/Lake" },
    Washington: { x: 420, y: 290, label: "Washington" },
    Monroe:     { x: 440, y: 320, label: "Monroe" }, // DESTINATION exit
    Jackson:    { x: 440, y: 350, label: "Jackson" },
    // Red line (vertical-ish on right)
    Fullerton:  { x: 500, y: 170 },
    Belmont:    { x: 510, y: 120 },
    RooseveltR: { x: 450, y: 380 },
    // Brown extension north
    Addison:    { x: 550, y: 90 },
    // Green line (crosses loop)
    RooseveltG: { x: 380, y: 380 },
  };

  const ART_INSTITUTE = { x: 470, y: 330 };
  const YOU = { x: 50,  y: 100 };

  // Line paths — orthogonal polylines
  const bluePath = [
    "LoganSq","California","Western","Damen","Division","Chicago","ClarkLake","Washington","Monroe","Jackson"
  ];
  const redPath  = ["Belmont","Fullerton","ClarkLake","Monroe","Jackson","RooseveltR"];
  const brownPath= ["Addison","Belmont","Fullerton","ClarkLake","Washington","LoganSq"]; // purely visual
  const greenPath= ["ClarkLake","Washington","RooseveltG"];

  const toPoints = (names) => names.map(n => stations[n]).filter(Boolean);
  const pointsAttr = (pts) => pts.map(p => `${p.x},${p.y}`).join(" ");

  const lineOn = (name) => name === activeLine;
  const lineOpacity = (name) => (activeLine && !lineOn(name) ? 0.22 : 1);
  const lineWidth = (name) => (lineOn(name) ? 6 : 4);

  // Stations along active route (Logan Square → Monroe on Blue)
  const activeStations = bluePath.slice(0, bluePath.indexOf("Monroe") + 1);

  return (
    <svg
      viewBox="0 0 600 420"
      preserveAspectRatio="xMidYMid meet"
      style={{
        display: "block",
        width: "100%",
        height: "100%",
        background: p.bg,
        ...style,
      }}
    >
      {/* Subtle grid */}
      <defs>
        <pattern id={`grid-${theme}`} width="30" height="30" patternUnits="userSpaceOnUse">
          <path d="M 30 0 L 0 0 0 30" fill="none" stroke={p.mute} strokeOpacity="0.12" strokeWidth="0.5" />
        </pattern>
        <filter id="glow"><feGaussianBlur stdDeviation="3" /></filter>
      </defs>
      <rect width="600" height="420" fill={`url(#grid-${theme})`} />

      {/* Geographic orientation — visible in paper theme only */}
      {theme === "paper" && (
        <>
          <defs>
            <pattern id="lake-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="6" stroke={p.lake} strokeWidth="1" />
            </pattern>
          </defs>
          <rect x="520" y="0" width="80" height="420" fill="url(#lake-hatch)" />
          <text x="560" y="210" fill={p.mute} fontSize="9" fontWeight="800"
            textAnchor="middle" letterSpacing="4"
            style={{ writingMode: "vertical-rl", opacity: 0.7 }}>LAKE MICHIGAN</text>
          <polyline points="380,0 380,220 410,260 520,260" fill="none"
            stroke={p.river} strokeWidth="12" strokeOpacity="0.45" />
          <text x="386" y="60" fill={p.mute} fontSize="8" fontWeight="700"
            letterSpacing="2" opacity="0.55">CHICAGO RIVER</text>
        </>
      )}

      {/* Inactive lines first */}
      <polyline points={pointsAttr(toPoints(brownPath))} fill="none"
        stroke={C.Brown} strokeWidth={lineWidth("Brown")} strokeOpacity={lineOpacity("Brown")}
        strokeLinejoin="round" strokeLinecap="round" />
      <polyline points={pointsAttr(toPoints(greenPath))} fill="none"
        stroke={C.Green} strokeWidth={lineWidth("Green")} strokeOpacity={lineOpacity("Green")}
        strokeLinejoin="round" strokeLinecap="round" />
      <polyline points={pointsAttr(toPoints(redPath))} fill="none"
        stroke={C.Red} strokeWidth={lineWidth("Red")} strokeOpacity={lineOpacity("Red")}
        strokeLinejoin="round" strokeLinecap="round" />

      {/* Active (Blue) line — glow underlay */}
      {lineOn("Blue") && (
        <polyline points={pointsAttr(toPoints(bluePath))} fill="none"
          stroke={C.Blue} strokeWidth="14" strokeOpacity="0.25" filter="url(#glow)"
          strokeLinejoin="round" strokeLinecap="round" />
      )}
      <polyline points={pointsAttr(toPoints(bluePath))} fill="none"
        stroke={C.Blue} strokeWidth={lineWidth("Blue")} strokeOpacity={lineOpacity("Blue")}
        strokeLinejoin="round" strokeLinecap="round" />

      {/* Station dots */}
      {Object.entries(stations).map(([key, s]) => {
        const isActive = activeStations.includes(key);
        const isTerminal = key === "LoganSq" || key === "Monroe";
        return (
          <g key={key}>
            <circle cx={s.x} cy={s.y} r={isTerminal ? 6 : isActive ? 4.5 : 3}
              fill={p.station}
              stroke={isActive ? C.Blue : p.mute}
              strokeWidth={isActive ? 2.5 : 1.5}
              opacity={isActive ? 1 : 0.55} />
          </g>
        );
      })}

      {/* Walking dashes: Monroe → Art Institute */}
      <line x1={stations.Monroe.x} y1={stations.Monroe.y} x2={ART_INSTITUTE.x} y2={ART_INSTITUTE.y}
        stroke={p.ink} strokeWidth="2" strokeDasharray="3 4" strokeOpacity="0.8" />
      {/* Walking dashes: YOU → Logan Square */}
      <line x1={YOU.x} y1={YOU.y} x2={stations.LoganSq.x} y2={stations.LoganSq.y}
        stroke={p.ink} strokeWidth="2" strokeDasharray="3 4" strokeOpacity="0.8" />

      {/* ── Origin marker — "Departure" §
            Editorial mark: italic § (section/silcrow) inside a square ink frame.
            Reads as "the place from which" — not pinned, not mobile.            */}
      <g transform={`translate(${YOU.x} ${YOU.y})`}>
        {/* paper backing so the rule reads on any map fill */}
        <rect x="-11" y="-11" width="22" height="22" fill={p.station} />
        {/* outer ink frame */}
        <rect x="-11" y="-11" width="22" height="22" fill="none" stroke={p.ink} strokeWidth="2" />
        {/* inset hairline (the editorial "double rule" frame) */}
        <rect x="-8" y="-8" width="16" height="16" fill="none" stroke={p.ink} strokeWidth="0.75" />
        {/* italic silcrow */}
        <text x="0" y="5.5" fontSize="16" fontWeight="700" fill={p.ink}
          fontFamily="Fraunces, Georgia, serif" fontStyle="italic" textAnchor="middle">§</text>
        {showLabels && (
          <>
            {/* tiny flag label: caps kicker FROM, serif name below */}
            <text x="-15" y="-15" fill={p.mute} fontSize="7.5" fontWeight="800"
              fontFamily="Inter, system-ui" letterSpacing="1.5" textAnchor="end">FROM</text>
            <text x="-15" y="-4" fill={p.ink} fontSize="11" fontWeight="500"
              fontFamily="Fraunces, Georgia, serif" fontStyle="italic" textAnchor="end">Logan Sq.</text>
          </>
        )}
      </g>

      {/* ── Destination marker — "Arrival" ✦
            Editorial mark: target — concentric ink ring + crosshair + small fill.
            Reads as "the precise spot to which" — surveyed, fixed.            */}
      <g transform={`translate(${ART_INSTITUTE.x} ${ART_INSTITUTE.y})`}>
        {/* paper backing */}
        <circle r="13" fill={p.station} />
        {/* outer ink ring */}
        <circle r="12" fill="none" stroke={p.ink} strokeWidth="2" />
        {/* inset hairline */}
        <circle r="9" fill="none" stroke={p.ink} strokeWidth="0.75" />
        {/* crosshair */}
        <line x1="-12" y1="0" x2="-5.5" y2="0" stroke={p.ink} strokeWidth="1.25" />
        <line x1="5.5" y1="0" x2="12" y2="0" stroke={p.ink} strokeWidth="1.25" />
        <line x1="0" y1="-12" x2="0" y2="-5.5" stroke={p.ink} strokeWidth="1.25" />
        <line x1="0" y1="5.5" x2="0" y2="12" stroke={p.ink} strokeWidth="1.25" />
        {/* center bullseye */}
        <circle r="3" fill={p.ink} />
      </g>
      {showLabels && (
        <g transform={`translate(${ART_INSTITUTE.x + 16} ${ART_INSTITUTE.y})`}>
          <text fill={p.mute} y="-7" fontSize="7.5" fontWeight="800"
            fontFamily="Inter, system-ui" letterSpacing="1.5">TO</text>
          <text fill={p.ink} y="6" fontSize="11" fontWeight="700"
            fontFamily="Fraunces, Georgia, serif">Art Institute</text>
        </g>
      )}

      {/* Key station labels on active route */}
      {showLabels && (
        <>
          <text x={stations.LoganSq.x + 9} y={stations.LoganSq.y - 6}
            fill={p.ink} fontSize="10" fontWeight="600"
            fontFamily="-apple-system,system-ui">Logan Square</text>
          <text x={stations.Monroe.x + 9} y={stations.Monroe.y - 4}
            fill={p.ink} fontSize="10" fontWeight="600"
            fontFamily="-apple-system,system-ui">Monroe</text>
          {!compact && (
            <>
              <text x={stations.Damen.x} y={stations.Damen.y + 16}
                fill={p.mute} fontSize="8.5" fontFamily="-apple-system,system-ui">Damen</text>
              <text x={stations.Chicago.x} y={stations.Chicago.y + 16}
                fill={p.mute} fontSize="8.5" fontFamily="-apple-system,system-ui">Chicago</text>
              <text x={stations.ClarkLake.x} y={stations.ClarkLake.y - 6}
                fill={p.mute} fontSize="8.5" fontFamily="-apple-system,system-ui">Clark/Lake</text>
            </>
          )}
        </>
      )}

      {/* Legend — matches the new editorial markers */}
      {showLegend && !compact && (
        <g transform="translate(20, 360)">
          <rect width="220" height="50" fill={p.station} fillOpacity="0.92" stroke={p.ink} strokeWidth="0.75" />
          {/* hairline frame */}
          <rect x="3" y="3" width="214" height="44" fill="none" stroke={p.ink} strokeWidth="0.4" />

          {/* § origin */}
          <g transform="translate(16, 18)">
            <rect x="-7" y="-7" width="14" height="14" fill="none" stroke={p.ink} strokeWidth="1.4" />
            <text x="0" y="3.5" fontSize="10" fontWeight="700" fill={p.ink}
              fontFamily="Fraunces, Georgia, serif" fontStyle="italic" textAnchor="middle">§</text>
          </g>
          <text x="32" y="22" fill={p.ink} fontSize="9.5" fontWeight="700"
            fontFamily="Inter, system-ui" letterSpacing="1.5">FROM</text>

          {/* ✦ destination */}
          <g transform="translate(16, 38)">
            <circle r="7.5" fill="none" stroke={p.ink} strokeWidth="1.4" />
            <line x1="-7.5" y1="0" x2="-3.5" y2="0" stroke={p.ink} strokeWidth="1" />
            <line x1="3.5" y1="0" x2="7.5" y2="0" stroke={p.ink} strokeWidth="1" />
            <line x1="0" y1="-7.5" x2="0" y2="-3.5" stroke={p.ink} strokeWidth="1" />
            <line x1="0" y1="3.5" x2="0" y2="7.5" stroke={p.ink} strokeWidth="1" />
            <circle r="2" fill={p.ink} />
          </g>
          <text x="32" y="42" fill={p.ink} fontSize="9.5" fontWeight="700"
            fontFamily="Inter, system-ui" letterSpacing="1.5">TO</text>

          {/* Active line indicator */}
          <line x1="120" y1="22" x2="160" y2="22" stroke={C.Blue} strokeWidth="3" />
          <text x="166" y="25" fill={p.ink} fontSize="9" fontWeight="700"
            fontFamily="Inter, system-ui" letterSpacing="1">BL TO LOOP</text>

          {/* Walking indicator */}
          <line x1="120" y1="40" x2="160" y2="40" stroke={p.ink} strokeWidth="1.5" strokeDasharray="2 3" />
          <text x="166" y="43" fill={p.mute} fontSize="9" fontWeight="700"
            fontFamily="Inter, system-ui" letterSpacing="1">WALK</text>
        </g>
      )}
    </svg>
  );
}

// A more minimal version for thumbnails and small cards
function MiniRouteDiagram({ route, theme = "dark", style = {} }) {
  const palettes = {
    dark:  { ink: "#e8e8ec", mute: "#5a5a62" },
    light: { ink: "#1a1a1a", mute: "#888" },
    paper: { ink: "#1a1510", mute: "#8a7a60" },
    board: { ink: "#ffb347", mute: "#6b4a1a" },
    brand: { ink: "#111",    mute: "#888" },
  };
  const p = palettes[theme] || palettes.dark;
  const C = {
    Red: "#c60c30", Blue: "#00a1de", Brown: "#62361b", Green: "#009b3a",
    Orange: "#f9461c", Purple: "#522398", Pink: "#e27ea6", Yellow: "#f9e300",
    Bus: "#4a5a6a",
  };

  const W = 300, H = 28;
  const pad = 8;
  const innerW = W - pad * 2;
  const n = route.legs.length;

  let x = pad;
  const segments = route.legs.map((leg, i) => {
    const share = leg.minutes / route.total;
    const w = innerW * share;
    const seg = { x, w, leg };
    x += w;
    return seg;
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ display: "block", width: "100%", height: 28, ...style }}>
      {segments.map((s, i) => {
        const leg = s.leg;
        const color = leg.type === "walk"
          ? p.mute
          : (C[leg.line] || C.Bus);
        return (
          <g key={i}>
            {leg.type === "walk" ? (
              <line x1={s.x} y1={H/2} x2={s.x + s.w} y2={H/2}
                stroke={color} strokeWidth="3" strokeDasharray="2 3" />
            ) : (
              <rect x={s.x} y={H/2 - 4} width={s.w} height="8" rx="4" fill={color} />
            )}
            {leg.type === "transit" && (
              <text x={s.x + s.w / 2} y={H/2 + 3} fontSize="8" fontWeight="700"
                fill={leg.line === "Yellow" ? "#222" : "#fff"}
                textAnchor="middle" fontFamily="-apple-system,system-ui">
                {leg.code}
              </text>
            )}
          </g>
        );
      })}
      {/* Endpoint dots */}
      <circle cx={pad} cy={H/2} r="3" fill={p.ink} />
      <circle cx={W - pad} cy={H/2} r="3" fill={p.ink} />
    </svg>
  );
}

Object.assign(window, { SchematicMap, MiniRouteDiagram });
