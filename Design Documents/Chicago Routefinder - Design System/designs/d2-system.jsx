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

Object.assign(window, {
  D2Swatch, D2Type, D2Colors, D2Components, D2Principles, D2MapPlate,
});
