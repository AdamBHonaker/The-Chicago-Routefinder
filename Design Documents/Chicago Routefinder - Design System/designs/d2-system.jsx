// Design System section for The Transit Almanac (Direction 2)
// Editorial specimen: type ramp · color plates · line pills ·
// components · motion notes. All rendered on cream paper stock.

function D2Swatch({ hex, name, note }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0" }}>
      <div style={{ width: 28, height: 28, background: hex, border: `1px solid ${D2.rule}`, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: D2.serif, fontSize: 13, fontWeight: 600 }}>{name}</div>
        {note && (
          <div style={{ fontFamily: D2.serif, fontStyle: "italic", fontSize: 11, color: D2.mute }}>
            {note}
          </div>
        )}
      </div>
      <div style={{ fontFamily: D2.mono, fontSize: 10, color: D2.mute }}>{hex}</div>
    </div>
  );
}

// ── Typography plate ──────────────────────────────────────────────────────
function D2Type() {
  const rows = [
    { label: "Display Italic", font: D2.serif, size: 48, weight: 500, italic: true, sample: "The Chicago" },
    { label: "Display",        font: D2.serif, size: 48, weight: 700, sample: "Routefinder" },
    { label: "Headline",       font: D2.serif, size: 28, weight: 700, sample: "Notices & Delays" },
    { label: "Subhead italic", font: D2.serif, size: 20, weight: 400, italic: true, sample: "toward the Loop" },
    { label: "Body serif",     font: D2.serif, size: 15, weight: 400,
      sample: "Board the Blue Line from Logan Square. Alight at Monroe and walk four minutes east." },
    { label: "Body italic",    font: D2.serif, size: 14, weight: 400, italic: true,
      sample: "The train is on schedule. Five stops remain." },
    { label: "Caps · UI labels", font: D2.sans, size: 10, weight: 700, caps: true, sample: "recommended path" },
    { label: "Mono · figures",   font: D2.mono, size: 13, weight: 500, sample: "17:47 · 21m · № 412" },
  ];
  return (
    <div className="d2-grain" style={{ height: "100%", padding: 24, fontFamily: D2.sans, color: D2.ink, overflow: "hidden" }}>
      <D2Caps>Specimen · A</D2Caps>
      <h2 style={{ fontFamily: D2.serif, fontSize: 28, fontWeight: 700, letterSpacing: -0.6, margin: "4px 0 8px" }}>
        <span style={{ fontStyle: "italic", fontWeight: 400 }}>On</span> Typography
      </h2>
      <div className="d2-rule-thick" />
      <div style={{ marginTop: 12 }}>
        {rows.map((r, i) => (
          <div key={i} style={{ padding: "10px 0", borderBottom: `1px solid ${D2.mute2}` }}>
            <div style={{
              fontFamily: r.font, fontSize: r.size, fontWeight: r.weight,
              fontStyle: r.italic ? "italic" : "normal",
              textTransform: r.caps ? "uppercase" : "none",
              letterSpacing: r.caps ? 2 : (r.size >= 28 ? -0.8 : 0),
              lineHeight: 1.1, color: D2.ink,
            }}>{r.sample}</div>
            <div style={{
              fontSize: 10, letterSpacing: 1.5, textTransform: "uppercase",
              color: D2.mute, marginTop: 6, fontWeight: 700,
            }}>
              {r.label} · {r.font.split(",")[0].replaceAll('"', "")} · {r.size}/{r.weight}{r.italic ? " italic" : ""}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Color plate ───────────────────────────────────────────────────────────
function D2Colors() {
  const palette = [
    { hex: D2.bg,     name: "Paper Stock",     note: "Primary background · cream" },
    { hex: D2.paper,  name: "Bright Card",     note: "Featured panels · leading article" },
    { hex: D2.bg2,    name: "Folio",           note: "Secondary surfaces" },
    { hex: D2.ink,    name: "Ink",             note: "Primary type · rule lines" },
    { hex: D2.ink2,   name: "Ink Soft",        note: "Body copy on cream" },
    { hex: D2.mute,   name: "Mute",            note: "Labels · italic body" },
    { hex: D2.mute2,  name: "Mute Fog",        note: "Hairlines · deprioritised" },
    { hex: D2.accent, name: "Rust",            note: "Delays · live · recommended mark" },
    { hex: D2.accent2,name: "Navy",            note: "Notices · advisories" },
    { hex: D2.good,   name: "Field",           note: "Clear service" },
    { hex: D2.lake,   name: "Lake",            note: "Cartographic · Michigan" },
    { hex: D2.river,  name: "River",           note: "Cartographic · Chicago" },
  ];
  return (
    <div className="d2-grain" style={{
      height: "100%", padding: 24, fontFamily: D2.sans, color: D2.ink,
      display: "flex", flexDirection: "column", overflow: "hidden",
    }}>
      <D2Caps>Specimen · B</D2Caps>
      <h2 style={{ fontFamily: D2.serif, fontSize: 28, fontWeight: 700, letterSpacing: -0.6, margin: "4px 0 8px" }}>
        <span style={{ fontStyle: "italic", fontWeight: 400 }}>The</span> Palette
      </h2>
      <div className="d2-rule-thick" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", columnGap: 20, marginTop: 8 }}>
        {palette.map((s) => <D2Swatch key={s.hex} {...s} />)}
      </div>

      <D2Caps style={{ marginTop: 14 }}>Transit Lines</D2Caps>
      <div className="d2-rule" style={{ marginTop: 4 }} />
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
        gap: 10, marginTop: 10,
      }}>
        {Object.entries(LINE_COLORS).map(([name, hex]) => (
          <div key={name} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <D2Pill line={name} code={name.slice(0, 2).toUpperCase()} size="sm" />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontFamily: D2.serif, fontSize: 12, fontWeight: 600 }}>{name}</div>
              <div style={{ fontFamily: D2.mono, fontSize: 9, color: D2.mute }}>{hex}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Components plate ──────────────────────────────────────────────────────
function D2Components() {
  return (
    <div className="d2-grain d2-scroll" style={{
      height: "100%", padding: 24, fontFamily: D2.sans, color: D2.ink,
      display: "flex", flexDirection: "column", overflow: "auto",
    }}>
      <D2Caps>Specimen · C</D2Caps>
      <h2 style={{ fontFamily: D2.serif, fontSize: 28, fontWeight: 700, letterSpacing: -0.6, margin: "4px 0 8px" }}>
        <span style={{ fontStyle: "italic", fontWeight: 400 }}>Selected</span> Components
      </h2>
      <div className="d2-rule-thick" />

      {/* Line pills */}
      <D2Caps style={{ marginTop: 14 }}>Line pills · sm · md · lg</D2Caps>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
        <D2Pill line="Blue" code="BL" size="sm" />
        <D2Pill line="Blue" code="BL" />
        <D2Pill line="Blue" code="BLUE" size="lg" />
        <D2Pill line="Red"  code="RD" />
        <D2Pill line="Brown" code="BR" />
        <D2Pill line="Green" code="GR" />
        <D2Pill line="Yellow" code="YL" />
      </div>

      {/* Signal lamp */}
      <D2Caps style={{ marginTop: 18 }}>Signal lamp · live indicator</D2Caps>
      <div style={{ marginTop: 6, display: "flex", gap: 16, flexWrap: "wrap" }}>
        <D2Lamp />
        <D2Lamp label="Dispatch · Offline" />
        <D2Lamp label="Arriving" />
      </div>
      <div style={{ fontFamily: D2.serif, fontStyle: "italic", fontSize: 12, color: D2.mute, marginTop: 6 }}>
        Flickers on a 3.4-second step cycle. Conveys presence without shouting.
      </div>

      {/* Drop-cap duration */}
      <D2Caps style={{ marginTop: 18 }}>Drop-cap duration</D2Caps>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginTop: 8 }}>
        <div style={{ fontFamily: D2.serif, fontSize: 72, fontWeight: 700, lineHeight: 0.82, letterSpacing: -3, fontStyle: "italic" }}>27</div>
        <div style={{ paddingTop: 6 }}>
          <D2Caps>minutes total</D2Caps>
          <div style={{ fontFamily: D2.serif, fontSize: 13, fontStyle: "italic", color: D2.ink2, marginTop: 6 }}>
            A direct ride. Next departure in 3 minutes.
          </div>
        </div>
      </div>

      {/* Special dispatch */}
      <D2Caps style={{ marginTop: 18 }}>Special dispatch · advisory</D2Caps>
      <div className="d2-special" style={{ marginTop: 8 }}>
        <div style={{ fontSize: 9, fontWeight: 800, letterSpacing: 1, color: D2.accent, marginBottom: 4, textTransform: "uppercase" }}>
          Advisory
        </div>
        <div style={{ fontFamily: D2.serif, fontStyle: "italic", fontSize: 13, lineHeight: 1.45 }}>
          The vertical lift at <b style={{ fontStyle: "normal" }}>Jackson Station</b> is non-operational.
        </div>
      </div>

      {/* Buttons */}
      <D2Caps style={{ marginTop: 18 }}>Buttons</D2Caps>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 8 }}>
        <button style={{
          background: D2.ink, color: D2.bg, border: "none", padding: "12px 16px",
          fontFamily: D2.serif, fontSize: 14, fontWeight: 600, fontStyle: "italic", cursor: "pointer",
        }}>Commence Journey ⟶</button>
        <button style={{
          background: "transparent", color: D2.ink, border: `1px solid ${D2.rule}`,
          padding: "12px 16px", fontFamily: D2.serif, fontSize: 14, fontWeight: 500, cursor: "pointer",
        }}>Save this route</button>
      </div>

      {/* Rules */}
      <D2Caps style={{ marginTop: 18 }}>Rules</D2Caps>
      <div style={{ marginTop: 8 }}>
        <div className="d2-rule" />
        <div style={{ fontSize: 9, color: D2.mute, margin: "4px 0 8px" }}>hairline · 1px</div>
        <div className="d2-rule-thick" />
        <div style={{ fontSize: 9, color: D2.mute, margin: "4px 0 8px" }}>thick · 2px · section divider</div>
        <div className="d2-rule-double" />
        <div style={{ fontSize: 9, color: D2.mute, marginTop: 4 }}>double · chapter break</div>
      </div>
    </div>
  );
}

// ── Motion & principles ───────────────────────────────────────────────────
function D2Principles() {
  const principles = [
    { n: "I",   t: "Read the city like a broadsheet",
      b: "The interface is a daily paper, set fresh each morning. Every ride earns a column, every delay a dispatch." },
    { n: "II",  t: "Lead with the numeral",
      b: "Minutes are the hero. Typeset them large, in italic serif, with generous white space around." },
    { n: "III", t: "Italic softens, caps direct",
      b: "Serif italic for voice, UI caps for wayfinding. Never the other way around." },
    { n: "IV",  t: "Lamps, not sirens",
      b: "Live state flickers at the edge. The interface should feel watched-over, not surveilled." },
    { n: "V",   t: "Place before route",
      b: "Lake on the right, river bending through. Stations labelled like landmarks." },
    { n: "VI",  t: "A small red for consequence",
      b: "Rust red is reserved for live state, delay, and the recommended mark — nothing decorative." },
  ];
  return (
    <div className="d2-grain" style={{
      height: "100%", padding: 24, fontFamily: D2.sans, color: D2.ink, overflow: "hidden",
      display: "flex", flexDirection: "column",
    }}>
      <D2Caps>Specimen · D</D2Caps>
      <h2 style={{ fontFamily: D2.serif, fontSize: 28, fontWeight: 700, letterSpacing: -0.6, margin: "4px 0 8px" }}>
        <span style={{ fontStyle: "italic", fontWeight: 400 }}>Six</span> Principles
      </h2>
      <div className="d2-rule-thick" />
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 1fr", columnGap: 20, rowGap: 4, marginTop: 12 }}>
        {principles.map((p) => (
          <div key={p.n} style={{
            padding: "10px 0 12px", borderBottom: `1px solid ${D2.mute2}`,
          }}>
            <div style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
              <span style={{
                fontFamily: D2.serif, fontStyle: "italic", fontSize: 18, color: D2.accent, fontWeight: 600,
              }}>{p.n}.</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: D2.serif, fontSize: 15, fontWeight: 700, lineHeight: 1.2 }}>
                  {p.t}
                </div>
                <div style={{
                  fontFamily: D2.serif, fontStyle: "italic", fontSize: 12, color: D2.ink2,
                  marginTop: 4, lineHeight: 1.45,
                }}>{p.b}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Map plate (full bleed schematic) ──────────────────────────────────────
function D2MapPlate() {
  return (
    <div style={{ height: "100%", background: D2.paper, position: "relative", overflow: "hidden" }}>
      <div style={{
        position: "absolute", top: 16, left: 20, right: 20,
        display: "flex", justifyContent: "space-between", alignItems: "baseline", zIndex: 2,
      }}>
        <D2Caps>Plate II — The System</D2Caps>
        <D2Caps>N ↑ · not to scale</D2Caps>
      </div>
      <div style={{ position: "absolute", top: 42, left: 0, right: 0, bottom: 40 }}>
        <SchematicMap theme="paper" />
      </div>
      <div style={{
        position: "absolute", bottom: 12, left: 20, right: 20,
        textAlign: "center", fontFamily: D2.serif, fontStyle: "italic", fontSize: 11, color: D2.mute,
      }}>
        Fig. II — A schematic of the eight lines, shown with the lake and river for orientation.
      </div>
    </div>
  );
}

// ── Map markers plate (origin · destination · live position) ─────────────
function D2MapMarkers() {
  return (
    <div className="d2-grain d2-scroll" style={{
      height: "100%", padding: 24, fontFamily: D2.sans, color: D2.ink, overflow: "auto",
    }}>
      <D2Caps>Specimen · E</D2Caps>
      <h2 style={{ fontFamily: D2.serif, fontSize: 28, fontWeight: 700, letterSpacing: -0.6, margin: "4px 0 8px" }}>
        <span style={{ fontStyle: "italic", fontWeight: 400 }}>Three</span> Map Marks
      </h2>
      <div className="d2-rule-thick" />
      <div style={{ fontFamily: D2.serif, fontStyle: "italic", fontSize: 13, color: D2.ink2, marginTop: 10, lineHeight: 1.5 }}>
        Three orthogonal silhouettes — square, ring, compass — so origin, destination,
        and the rider's live position can never be mistaken for one another.
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 18, marginTop: 18 }}>

        {/* §  ORIGIN — silcrow inside square ink frame */}
        <div>
          <D2Caps>I — From</D2Caps>
          <div className="d2-rule" style={{ marginTop: 4, marginBottom: 14 }} />
          <div style={{
            background: D2.bg, height: 130, position: "relative", border: `1px solid ${D2.mute2}`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg width="120" height="120" viewBox="-30 -30 60 60">
              <defs>
                <pattern id="grid-fr" width="6" height="6" patternUnits="userSpaceOnUse">
                  <path d="M 6 0 L 0 0 0 6" fill="none" stroke={D2.mute2} strokeWidth="0.4"/>
                </pattern>
              </defs>
              <rect x="-30" y="-30" width="60" height="60" fill="url(#grid-fr)" />
              {/* paper backing */}
              <rect x="-11" y="-11" width="22" height="22" fill={D2.bg} />
              {/* outer ink frame */}
              <rect x="-11" y="-11" width="22" height="22" fill="none" stroke={D2.ink} strokeWidth="2" />
              {/* inset hairline */}
              <rect x="-8" y="-8" width="16" height="16" fill="none" stroke={D2.ink} strokeWidth="0.75" />
              {/* italic silcrow */}
              <text x="0" y="5.5" fontSize="16" fontWeight="700" fill={D2.ink}
                fontFamily={D2.serif} fontStyle="italic" textAnchor="middle">§</text>
            </svg>
          </div>
          <div style={{ fontFamily: D2.serif, fontStyle: "italic", fontSize: 12, color: D2.ink2, lineHeight: 1.5, marginTop: 8 }}>
            Italic silcrow inside a double-ruled square. Reads as a <i>place from which</i> —
            fixed, lettered, archived in the index.
          </div>
          <div style={{ fontFamily: D2.mono, fontSize: 10, color: D2.mute, marginTop: 6 }}>
            22 × 22 px · ink 2px · inset 0.75px · paper bg
          </div>
        </div>

        {/* ✦  DESTINATION — crosshair target */}
        <div>
          <D2Caps>II — To</D2Caps>
          <div className="d2-rule" style={{ marginTop: 4, marginBottom: 14 }} />
          <div style={{
            background: D2.bg, height: 130, position: "relative", border: `1px solid ${D2.mute2}`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg width="120" height="120" viewBox="-30 -30 60 60">
              <rect x="-30" y="-30" width="60" height="60" fill="url(#grid-fr)" />
              <circle r="13" fill={D2.bg} />
              <circle r="12" fill="none" stroke={D2.ink} strokeWidth="2" />
              <circle r="9" fill="none" stroke={D2.ink} strokeWidth="0.75" />
              <line x1="-12" y1="0" x2="-5.5" y2="0" stroke={D2.ink} strokeWidth="1.25" />
              <line x1="5.5" y1="0" x2="12" y2="0" stroke={D2.ink} strokeWidth="1.25" />
              <line x1="0" y1="-12" x2="0" y2="-5.5" stroke={D2.ink} strokeWidth="1.25" />
              <line x1="0" y1="5.5" x2="0" y2="12" stroke={D2.ink} strokeWidth="1.25" />
              <circle r="3" fill={D2.ink} />
            </svg>
          </div>
          <div style={{ fontFamily: D2.serif, fontStyle: "italic", fontSize: 12, color: D2.ink2, lineHeight: 1.5, marginTop: 8 }}>
            Surveyor's target — concentric ring with crosshair and bullseye.
            Reads as a <i>precise spot to which</i> — measured, exact.
          </div>
          <div style={{ fontFamily: D2.mono, fontSize: 10, color: D2.mute, marginTop: 6 }}>
            ⌀ 24 px · ring 2px · hairline 0.75px · centre 6 px
          </div>
        </div>

        {/* ➤  LIVE POSITION — compass needle in flickering rust ring */}
        <div>
          <D2Caps>III — You</D2Caps>
          <div className="d2-rule" style={{ marginTop: 4, marginBottom: 14 }} />
          <div style={{
            background: D2.bg, height: 130, position: "relative", border: `1px solid ${D2.mute2}`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg width="120" height="120" viewBox="-30 -30 60 60">
              <rect x="-30" y="-30" width="60" height="60" fill="url(#grid-fr)" />
              {/* outer flicker ring */}
              <circle r="14" fill="none" stroke={D2.accent} strokeWidth="1" opacity="0.45">
                <animate attributeName="r" values="14;18;14" dur="2.4s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.45;0;0.45" dur="2.4s" repeatCount="indefinite" />
              </circle>
              {/* compass card */}
              <circle r="11" fill={D2.bg} stroke={D2.accent} strokeWidth="1.5" />
              {/* tick marks at N,S,E,W */}
              <line x1="0" y1="-11" x2="0" y2="-8" stroke={D2.accent} strokeWidth="1" />
              <line x1="0" y1="11" x2="0" y2="8" stroke={D2.accent} strokeWidth="1" />
              <line x1="-11" y1="0" x2="-8" y2="0" stroke={D2.accent} strokeWidth="1" />
              <line x1="11" y1="0" x2="8" y2="0" stroke={D2.accent} strokeWidth="1" />
              {/* compass needle pointing to bearing — north-east-ish */}
              <g transform="rotate(35)">
                <path d="M 0,-8 L 3,2 L 0,0 L -3,2 Z" fill={D2.accent} />
                <path d="M 0,8 L 2,2 L 0,0 L -2,2 Z" fill={D2.ink} opacity="0.4" />
              </g>
              {/* center pin */}
              <circle r="1.4" fill={D2.ink} />
            </svg>
          </div>
          <div style={{ fontFamily: D2.serif, fontStyle: "italic", fontSize: 12, color: D2.ink2, lineHeight: 1.5, marginTop: 8 }}>
            Compass needle inside a flickering rust ring. Reads as the
            <i> rider underway</i> — directional, mobile, watched-over.
          </div>
          <div style={{ fontFamily: D2.mono, fontSize: 10, color: D2.mute, marginTop: 6 }}>
            ⌀ 22 px · needle ↑ heading · pulse 2.4s · accent rust
          </div>
        </div>

      </div>

      {/* Anatomy notes */}
      <D2Caps style={{ marginTop: 22 }}>Anatomy &amp; rules</D2Caps>
      <div className="d2-rule" style={{ marginTop: 4 }} />
      <ul style={{
        fontFamily: D2.serif, fontStyle: "italic", fontSize: 13, color: D2.ink2,
        margin: "10px 0 0 0", padding: 0, listStyle: "none",
      }}>
        <li style={{ padding: "6px 0", borderBottom: `1px solid ${D2.mute2}` }}>
          <b style={{ fontStyle: "normal", color: D2.ink }}>Paper backing.</b> Every mark sits on a paper-coloured pad
          so its strokes read against any map fill — cream, lake blue, river green.
        </li>
        <li style={{ padding: "6px 0", borderBottom: `1px solid ${D2.mute2}` }}>
          <b style={{ fontStyle: "normal", color: D2.ink }}>Caps kicker, serif name.</b> Optional flag pairs caps
          <span style={{ fontFamily: D2.sans, fontSize: 10, fontWeight: 800, letterSpacing: 1.5, margin: "0 4px" }}>FROM</span>
          <span style={{ fontFamily: D2.sans, fontSize: 10, fontWeight: 800, letterSpacing: 1.5, margin: "0 4px" }}>TO</span>
          <span style={{ fontFamily: D2.sans, fontSize: 10, fontWeight: 800, letterSpacing: 1.5, margin: "0 4px" }}>YOU</span>
          with the place name set in italic Fraunces 11/500.
        </li>
        <li style={{ padding: "6px 0", borderBottom: `1px solid ${D2.mute2}` }}>
          <b style={{ fontStyle: "normal", color: D2.ink }}>Rust is reserved.</b> Only the live-position ring uses
          <span style={{ color: D2.accent, fontWeight: 700, fontStyle: "normal" }}> rust</span>. Origin and
          destination stay in pure ink — they aren't consequences, they're coordinates.
        </li>
        <li style={{ padding: "6px 0" }}>
          <b style={{ fontStyle: "normal", color: D2.ink }}>Reduced motion.</b> The rust pulse is suppressed under
          <span style={{ fontFamily: D2.mono, fontSize: 11, color: D2.ink, fontStyle: "normal" }}> prefers-reduced-motion</span>;
          the ring stays at full 14 px opacity 0.45.
        </li>
      </ul>
    </div>
  );
}

Object.assign(window, {
  D2Swatch, D2Type, D2Colors, D2Components, D2Principles, D2MapPlate, D2MapMarkers,
});
