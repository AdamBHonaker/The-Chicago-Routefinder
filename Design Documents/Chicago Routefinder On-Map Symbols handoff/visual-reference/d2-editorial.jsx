// Direction 2 — The Transit Almanac
// Editorial / printed transit-map language. Cream paper stock, Fraunces
// serif display, rules + drop-caps + italic body copy.
// Original design (not a CTA product); lines are named by color family only.

const D2 = {
  bg: "#f2ece0", // cream paper
  bg2: "#e9e1d1", // darker cream (rail, panels)
  paper: "#fffbef", // bright card stock
  ink: "#171310",
  ink2: "#4a3f32",
  mute: "#7a6a54",
  mute2: "#a89a82",
  rule: "#1a1510",
  accent: "#9c2a1a", // rust — alerts, live, accent
  accent2: "#1a4d6f", // navy — notices
  good: "#1f6d3b",
  lake: "#cedde2", // pale lake blue
  river: "#cbd4c5", // pale river green
  serif: '"Fraunces","GT Sectra","Playfair Display", Georgia, serif',
  sans: '"Inter", -apple-system, system-ui, sans-serif',
  mono: '"JetBrains Mono","IBM Plex Mono", ui-monospace, monospace'
};

// Inject shared CSS for grain + flicker. One-time.
if (typeof document !== "undefined" && !document.getElementById("d2-styles")) {
  const s = document.createElement("style");
  s.id = "d2-styles";
  s.textContent = `
    @keyframes d2-flicker {
      0%, 100% { opacity: 1; }
      45% { opacity: 1; }
      50% { opacity: 0.35; }
      55% { opacity: 0.9; }
      60% { opacity: 0.5; }
      65% { opacity: 1; }
    }
    @keyframes d2-radar {
      0%   { r: 4;  opacity: 0.8; }
      100% { r: 16; opacity: 0;   }
    }
    .d2-grain {
      background-color: ${D2.bg};
      background-image:
        radial-gradient(rgba(26,21,16,0.035) 1px, transparent 1px),
        radial-gradient(rgba(26,21,16,0.025) 1px, transparent 1px);
      background-size: 3px 3px, 7px 7px;
      background-position: 0 0, 1px 2px;
    }
    .d2-grain-paper {
      background-color: ${D2.paper};
      background-image:
        radial-gradient(rgba(26,21,16,0.03) 1px, transparent 1px);
      background-size: 4px 4px;
    }
    .d2-lamp {
      display: inline-block; width: 7px; height: 7px; border-radius: 50%;
      background: ${D2.accent};
      box-shadow: 0 0 6px ${D2.accent}, 0 0 0 1.5px ${D2.bg};
      animation: d2-flicker 3.4s infinite step-end;
    }
    .d2-special {
      border: 3px double ${D2.rule}; padding: 12px 14px; background: ${D2.paper};
      position: relative;
    }
    .d2-special::before {
      content: ""; position: absolute; top: 4px; left: 4px; right: 4px; bottom: 4px;
      border: 1px solid rgba(26,21,16,0.18); pointer-events: none;
    }
    .d2-rule { height: 1px; background: ${D2.rule}; }
    .d2-rule-thick { height: 2px; background: ${D2.rule}; }
    .d2-rule-double {
      height: 5px; border-top: 1px solid ${D2.rule};
      border-bottom: 1px solid ${D2.rule};
    }
    .d2-dash { border-top: 1px dashed ${D2.mute2}; }
    .d2-tnum { font-variant-numeric: tabular-nums; }
    .d2-caps {
      font-size: 10px; letter-spacing: 2px; text-transform: uppercase;
      font-weight: 700; color: ${D2.mute}; font-family: ${D2.sans};
    }
    .d2-caps-ink { color: ${D2.ink}; }
    .d2-caps-accent { color: ${D2.accent}; }
    .d2-caps-accent2 { color: ${D2.accent2}; }
    .d2-scroll::-webkit-scrollbar { display: none; }
    .d2-scroll { scrollbar-width: none; }
  `;
  document.head.appendChild(s);
}

// ── Shared micro-components ───────────────────────────────────────────────

function D2Pill({ line, code, size = "md" }) {
  const bg = LINE_COLORS[line] || D2.ink;
  const color = line === "Yellow" ? "#111" : "#fff";
  const dims = size === "sm" ?
  { h: 20, minW: 22, fs: 9, pad: "0 6px" } :
  size === "lg" ?
  { h: 34, minW: 34, fs: 13, pad: "0 10px" } :
  { h: 26, minW: 26, fs: 11, pad: "0 8px" };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      minWidth: dims.minW, height: dims.h, padding: dims.pad,
      background: bg, color, fontFamily: D2.sans, fontWeight: 900,
      fontSize: dims.fs, letterSpacing: 1, borderRadius: 2,
      boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.25)"
    }}>{code || line.slice(0, 2).toUpperCase()}</span>);

}

function D2Caps({ children, tone = "mute", style = {} }) {
  const map = { mute: D2.mute, ink: D2.ink, accent: D2.accent, accent2: D2.accent2 };
  return (
    <div style={{
      fontSize: 10, letterSpacing: 2, textTransform: "uppercase",
      fontWeight: 700, color: map[tone] || D2.mute, fontFamily: D2.sans, ...style
    }}>{children}</div>);

}

function D2Lamp({ label = "Signal Verified · Live" }) {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <span className="d2-lamp" />
      <span style={{
        fontSize: 9, fontWeight: 700, letterSpacing: 2, textTransform: "uppercase",
        color: D2.mute, fontFamily: D2.sans
      }}>{label}</span>
    </div>);

}

function D2Masthead({ issue = "No. 112", vol = "Vol. IV", date = "Monday, April 20" }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "baseline",
      fontSize: 10, letterSpacing: 2, textTransform: "uppercase",
      color: D2.mute, fontWeight: 700, fontFamily: D2.sans
    }}>
      <span>{date}</span>
      <span>{vol} · {issue}</span>
    </div>);

}

function D2Footer({ children = "⟡ Printed in Chicago · For the daily rider ⟡" }) {
  return (
    <div style={{
      padding: "10px 22px 14px", marginTop: "auto",
      fontSize: 9, color: D2.mute, letterSpacing: 1.8, textTransform: "uppercase",
      fontFamily: D2.sans, fontWeight: 700, textAlign: "center",
      borderTop: `2px solid ${D2.rule}`
    }}>{children}</div>);

}

// A cleaner editorial tab bar used at the bottom of every screen
function D2TabBar({ active = "home" }) {
  const tabs = [
  { id: "home", label: "Home" },
  { id: "map", label: "Map" },
  { id: "alerts", label: "Alerts" },
  { id: "saved", label: "Saved" }];

  return (
    <div style={{
      borderTop: `2px solid ${D2.rule}`, background: D2.bg,
      display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
      paddingBottom: 10
    }}>
      {tabs.map((t) =>
      <div key={t.id} style={{
        padding: "10px 6px 4px", textAlign: "center",
        fontFamily: D2.serif, fontSize: 13,
        fontStyle: active === t.id ? "normal" : "italic",
        fontWeight: active === t.id ? 700 : 400,
        color: active === t.id ? D2.ink : D2.mute,
        borderBottom: active === t.id ? `2px solid ${D2.ink}` : "2px solid transparent",
        marginBottom: -2
      }}>{t.label}</div>
      )}
    </div>);

}

// ── Home ──────────────────────────────────────────────────────────────────
function D2Home() {
  return (
    <div className="d2-grain" style={{
      height: "100%", color: D2.ink, fontFamily: D2.sans,
      display: "flex", flexDirection: "column", overflow: "hidden"
    }}>
      {/* Masthead */}
      <div style={{ padding: "20px 22px 12px" }}>
        <D2Masthead />
        <div className="d2-rule-thick" style={{ marginTop: 8, marginBottom: 14 }} />
        <h1 style={{
          fontFamily: D2.serif, fontSize: 38, fontWeight: 500, letterSpacing: -1.2,
          lineHeight: 0.95, fontStyle: "italic", margin: 0
        }}>The Chicago</h1>
        <h1 style={{
          fontFamily: D2.serif, fontSize: 38, fontWeight: 700, letterSpacing: -1.2,
          lineHeight: 0.95, margin: "2px 0 0"
        }}>Routefinder<span style={{ color: D2.accent }}>.</span></h1>
        <div style={{
          fontSize: 12, color: D2.mute, marginTop: 10, fontStyle: "italic",
          fontFamily: D2.serif
        }}>
          A working guide to the trains, buses, and schedules of the city.
        </div>
      </div>

      {/* Trip composer */}
      <div style={{ padding: "4px 22px" }}>
        <D2Caps style={{ marginBottom: 10 }}>Plot a journey</D2Caps>
        <div className="d2-grain-paper" style={{
          border: `1px solid ${D2.rule}`, padding: "14px 16px"
        }}>
          <div style={{
            display: "flex", alignItems: "baseline", gap: 10,
            paddingBottom: 12, borderBottom: `1px dashed ${D2.mute2}`
          }}>
            <span style={{
              fontFamily: D2.serif, fontStyle: "italic", fontSize: 14,
              color: D2.mute, width: 36
            }}>from</span>
            <span style={{ fontFamily: D2.serif, fontSize: 19, fontWeight: 600, flex: 1 }}>
              Logan Square
            </span>
            <span style={{ fontSize: 10, color: D2.mute2 }}>●</span>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, paddingTop: 12 }}>
            <span style={{
              fontFamily: D2.serif, fontStyle: "italic", fontSize: 14,
              color: D2.mute, width: 36
            }}>to</span>
            <span style={{
              fontFamily: D2.serif, fontSize: 19, fontWeight: 500, flex: 1,
              color: D2.mute2, fontStyle: "italic"
            }}>a destination…</span>
          </div>
        </div>
      </div>

      {/* Two-column editorial */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1px 1fr", gap: 16,
        padding: "20px 22px 4px", flex: 1, overflow: "hidden"
      }}>
        <div>
          <D2Caps style={{ marginBottom: 8 }}>Frequents</D2Caps>
          <div className="d2-rule" />
          {SAVED_PLACES.slice(0, 3).map((p) =>
          <div key={p.id} style={{
            padding: "9px 0", borderBottom: `1px solid ${D2.mute2}`
          }}>
              <div style={{ fontFamily: D2.serif, fontSize: 16, fontWeight: 600 }}>
                {p.label}
              </div>
              <div style={{ fontSize: 10, color: D2.mute, marginTop: 1 }}>{p.sub}</div>
            </div>
          )}
        </div>
        <div style={{ background: D2.rule, width: 1 }} />
        <div>
          <D2Caps style={{ marginBottom: 8 }}>Dispatches</D2Caps>
          <div className="d2-rule" />
          <div style={{ padding: "9px 0", borderBottom: `1px solid ${D2.mute2}` }}>
            <div style={{
              fontSize: 9, fontWeight: 800, letterSpacing: 1.5,
              color: D2.accent, textTransform: "uppercase", marginBottom: 3
            }}>Delay</div>
            <div style={{ fontFamily: D2.serif, fontSize: 13, lineHeight: 1.3 }}>
              Red Line single-tracking through the weekend.
            </div>
          </div>
          <div style={{ padding: "9px 0" }}>
            <div style={{
              fontSize: 9, fontWeight: 800, letterSpacing: 1.5,
              color: D2.accent2, textTransform: "uppercase", marginBottom: 3
            }}>Notice</div>
            <div style={{ fontFamily: D2.serif, fontSize: 13, lineHeight: 1.3 }}>
              Blue Line overnight schedule changes May 1.
            </div>
          </div>
        </div>
      </div>

      {/* Signal + tabs */}
      <div style={{ padding: "10px 22px 8px", textAlign: "center" }}>
        <D2Lamp />
      </div>
      <D2TabBar active="home" />
    </div>);

}

// ── Search (destination entry) ────────────────────────────────────────────
function D2Search() {
  const query = "Art In";
  const suggestions = [
  { label: "Art Institute of Chicago", sub: "111 S Michigan Ave · 0.3 mi from Monroe", kind: "destination" },
  { label: "Art on Armitage", sub: "4125 W Armitage · café", kind: "destination" },
  { label: "Artemisia Gallery", sub: "1709 W Chicago · gallery", kind: "destination" }];

  const recents = [
  { from: "Home", to: "Merchandise Mart" },
  { from: "Wicker Park", to: "O'Hare Terminal 2" }];

  return (
    <div className="d2-grain" style={{
      height: "100%", color: D2.ink, fontFamily: D2.sans,
      display: "flex", flexDirection: "column", overflow: "hidden"
    }}>
      <div style={{ padding: "18px 22px 10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button style={{
            background: "transparent", border: `1px solid ${D2.rule}`,
            width: 30, height: 30, borderRadius: 0, fontSize: 14, color: D2.ink, cursor: "pointer"
          }}>←</button>
          <D2Caps>Identify destination</D2Caps>
        </div>
        <div className="d2-rule-thick" style={{ marginTop: 10 }} />
      </div>

      <div style={{ padding: "4px 22px 12px" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, padding: "8px 0" }}>
          <span style={{
            fontFamily: D2.serif, fontStyle: "italic", fontSize: 14,
            color: D2.mute, width: 36
          }}>to</span>
          <span style={{ fontFamily: D2.serif, fontSize: 24, fontWeight: 600, flex: 1 }}>
            {query}<span style={{
              display: "inline-block", width: 2, height: 22, background: D2.accent,
              marginLeft: 2, verticalAlign: "-3px", animation: "d2-flicker 1s infinite step-end"
            }} />
          </span>
        </div>
        <div className="d2-rule" />
      </div>

      <div className="d2-scroll" style={{ flex: 1, overflow: "auto" }}>
        <div style={{ padding: "0 22px" }}>
          <D2Caps style={{ margin: "4px 0 6px" }}>Matches</D2Caps>
          {suggestions.map((s, i) =>
          <div key={i} style={{
            padding: "12px 0", borderBottom: `1px solid ${D2.mute2}`,
            display: "flex", alignItems: "baseline", gap: 12
          }}>
              <span style={{
              fontFamily: D2.serif, fontStyle: "italic", color: D2.mute,
              fontSize: 11, width: 18
            }}>{String.fromCharCode(97 + i)}.</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: D2.serif, fontSize: 17, fontWeight: 600 }}>
                  {s.label}
                </div>
                <div style={{ fontSize: 11, color: D2.mute, marginTop: 2, fontStyle: "italic", fontFamily: D2.serif }}>
                  {s.sub}
                </div>
              </div>
              <span style={{ color: D2.mute, fontSize: 14 }}>→</span>
            </div>
          )}
        </div>

        <div style={{ padding: "18px 22px 8px" }}>
          <D2Caps style={{ marginBottom: 6 }}>Lately</D2Caps>
          {recents.map((r, i) =>
          <div key={i} style={{
            padding: "10px 0", borderBottom: `1px solid ${D2.mute2}`,
            display: "flex", justifyContent: "space-between", alignItems: "baseline"
          }}>
              <span style={{ fontFamily: D2.serif, fontSize: 15 }}>
                {r.from} <span style={{ color: D2.mute, fontStyle: "italic" }}>to</span> {r.to}
              </span>
              <span style={{ fontSize: 10, color: D2.mute, fontFamily: D2.mono }}>↺</span>
            </div>
          )}
        </div>
      </div>

      <D2TabBar active="home" />
    </div>);

}

// ── Results ───────────────────────────────────────────────────────────────
function D2Results({ expandedIndex = 0 }) {
  return (
    <div className="d2-grain" style={{
      height: "100%", color: D2.ink, fontFamily: D2.sans,
      display: "flex", flexDirection: "column", overflow: "hidden"
    }}>
      <div style={{ padding: "18px 22px 10px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button style={{
              background: "transparent", border: `1px solid ${D2.rule}`,
              width: 28, height: 28, fontSize: 13, color: D2.ink, cursor: "pointer"
            }}>←</button>
            <D2Caps>Results · 5:47 PM</D2Caps>
          </div>
          <D2Lamp label="Live" />
        </div>
        <div style={{
          fontFamily: D2.serif, fontSize: 22, fontWeight: 500, lineHeight: 1.2,
          letterSpacing: -0.6, marginTop: 10
        }}>
          Logan Square <span style={{ color: D2.mute, fontStyle: "italic" }}>to</span> the Art Institute
        </div>
        <div className="d2-rule-thick" style={{ marginTop: 10 }} />
      </div>

      <div className="d2-scroll" style={{ flex: 1, overflow: "auto" }}>
        {MOCK_RESULT.routes.map((route, i) => {
          const isLead = i === expandedIndex;
          return (
            <div key={route.id} style={{
              padding: "16px 22px",
              borderBottom: `1px solid ${D2.mute2}`,
              background: isLead ? D2.paper : "transparent"
            }}>
              {i === 0 &&
              <div style={{
                fontSize: 9, letterSpacing: 2, textTransform: "uppercase",
                color: D2.accent, fontWeight: 800, marginBottom: 6
              }}>★ Recommended Path</div>
              }
              <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
                <div style={{
                  fontFamily: D2.serif, fontSize: 72, fontWeight: 700,
                  lineHeight: 0.82, letterSpacing: -3, color: D2.ink, fontStyle: "italic"
                }}>{route.total}</div>
                <div style={{ flex: 1, paddingTop: 6 }}>
                  <D2Caps>minutes total</D2Caps>
                  <div style={{
                    fontFamily: D2.serif, fontSize: 14, fontStyle: "italic",
                    color: D2.ink2, marginTop: 6, lineHeight: 1.35
                  }}>
                    {route.transfers === 0 ? "A direct ride." : `With ${route.transfers} transfer.`}
                    {" "}Next departure in {route.wait === 0 ? "moments" : `${route.wait} minutes`}.
                  </div>
                  <div style={{
                    display: "flex", gap: 6, marginTop: 10, alignItems: "center", flexWrap: "wrap"
                  }}>
                    {route.legs.filter((l) => l.type === "transit").map((leg, j) =>
                    <D2Pill key={j} line={leg.line} code={leg.code} />
                    )}
                  </div>
                </div>
              </div>

              {/* Special dispatch — only under the recommended path */}
              {isLead && i === 0 &&
              <div className="d2-special" style={{ marginTop: 14 }}>
                  <div style={{
                  fontSize: 9, fontWeight: 800, letterSpacing: 1,
                  color: D2.accent, marginBottom: 4, textTransform: "uppercase"
                }}>Special Dispatch — Advisory</div>
                  <div style={{ fontFamily: D2.serif, fontStyle: "italic", fontSize: 13, lineHeight: 1.45 }}>
                    The vertical lift at <b style={{ fontStyle: "normal" }}>Jackson Station</b> is
                    non-operational. Patrons requiring step-free access should alight at
                    <b style={{ fontStyle: "normal" }}> Monroe</b>.
                  </div>
                </div>
              }

              {isLead &&
              <div style={{
                marginTop: 16, paddingTop: 14, borderTop: `1px dashed ${D2.mute2}`
              }}>
                  <D2Caps style={{ marginBottom: 10 }}>The Itinerary</D2Caps>
                  {route.legs.map((leg, k) =>
                <div key={k} style={{ display: "flex", gap: 14, marginBottom: 10 }}>
                      <div style={{
                    fontFamily: D2.mono, fontSize: 11, color: D2.mute,
                    width: 40, paddingTop: 4, textAlign: "right"
                  }} className="d2-tnum">
                        {leg.minutes}m
                      </div>
                      <div style={{
                    width: 1, background: D2.rule, flexShrink: 0, position: "relative"
                  }}>
                        <div style={{
                      position: "absolute", top: 8, left: -3, width: 7, height: 7,
                      background: leg.type === "walk" ? D2.bg : LINE_COLORS[leg.line] || D2.ink,
                      border: `1.5px solid ${D2.rule}`
                    }} />
                      </div>
                      <div style={{ flex: 1, paddingTop: 2 }}>
                        {leg.type === "walk" ?
                    <>
                            <div style={{ fontFamily: D2.serif, fontSize: 15, fontStyle: "italic", color: D2.ink2 }}>
                              Walk {leg.from === "Your location" ? `to ${leg.to}` :
                        leg.to === "Your destination" ? "to your destination" : "to transfer"}.
                            </div>
                            {leg.exit &&
                      <div style={{ fontSize: 11, color: D2.mute, marginTop: 2 }}>
                                Exit via {leg.exit}.
                              </div>
                      }
                          </> :

                    <>
                            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                              <D2Pill line={leg.line} code={leg.code} size="sm" />
                              <span style={{ fontFamily: D2.serif, fontSize: 15, fontWeight: 600 }}>
                                {leg.from} → {leg.to}
                              </span>
                            </div>
                            <div style={{
                        fontSize: 11, color: D2.mute, marginTop: 4, fontStyle: "italic",
                        fontFamily: D2.serif
                      }}>
                              {leg.stops ? `${leg.stops} stops` : ""}
                              {leg.direction ? ` · ${leg.direction}` : ""}
                            </div>
                          </>
                    }
                      </div>
                    </div>
                )}
                  <button style={{
                  marginTop: 10, background: D2.ink, color: D2.bg, border: "none",
                  padding: "14px 20px", fontFamily: D2.serif, fontSize: 15, fontWeight: 600,
                  letterSpacing: 0.3, cursor: "pointer", width: "100%",
                  fontStyle: "italic"
                }}>Commence Journey ⟶</button>
                </div>
              }
            </div>);

        })}
      </div>
    </div>);

}

// ── Live trip ─────────────────────────────────────────────────────────────
function D2LiveTrip() {
  return (
    <div className="d2-grain" style={{
      height: "100%", color: D2.ink, fontFamily: D2.sans,
      display: "flex", flexDirection: "column", overflow: "hidden"
    }}>
      <div style={{ padding: "18px 22px 10px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="d2-lamp" />
            <D2Caps tone="accent">Underway</D2Caps>
          </div>
          <D2Caps>Train №412</D2Caps>
        </div>
        <h1 style={{
          fontFamily: D2.serif, fontSize: 28, fontWeight: 700, letterSpacing: -0.8,
          marginTop: 6, lineHeight: 1
        }}>
          <span style={{ fontStyle: "italic", fontWeight: 400 }}>Toward</span> the Art Institute
        </h1>
        <div className="d2-rule-thick" style={{ marginTop: 12 }} />
      </div>

      {/* Countdown hero */}
      <div style={{ padding: "4px 22px 18px" }}>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 14 }}>
          <span style={{
            fontFamily: D2.serif, fontSize: 96, fontWeight: 700, letterSpacing: -5,
            lineHeight: 0.82, fontStyle: "italic", display: "inline-block",
            paddingRight: 8
          }}>{LIVE_TRIP.minutesToArrival}</span>
          <span style={{
            fontFamily: D2.serif, fontSize: 16, fontStyle: "italic", color: D2.mute,
            paddingBottom: 10, lineHeight: 1.2
          }}>minutes<br />to disembark</span>
        </div>
        <div style={{
          fontFamily: D2.serif, fontStyle: "italic", fontSize: 13, color: D2.ink2,
          marginTop: 14
        }}>
          Five stops remain. The train is <b style={{ fontStyle: "normal" }}>on schedule</b>.
        </div>
      </div>

      {/* Stops */}
      <div className="d2-scroll" style={{ flex: 1, overflow: "auto", padding: "0 22px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, whiteSpace: "nowrap" }}>
          <D2Pill line="Blue" code="BL" size="sm" />
          <span style={{ fontSize: 10, letterSpacing: 2, textTransform: "uppercase", color: D2.mute, fontWeight: 700 }}>
            Blue line · inbound
          </span>
        </div>
        <div className="d2-rule" />
        {LIVE_TRIP.stops.map((s, i) => {
          const c = s.status === "past" ? D2.mute2 :
          s.status === "current" ? D2.accent :
          s.status === "exit" ? D2.ink :
          D2.ink2;
          const eta = s.status === "current" ? "NOW" :
          s.status === "exit" ? "DISEMBARK" :
          s.status === "upcoming" ? `${i - 4}m` : null;
          return (
            <div key={i} style={{
              display: "flex", alignItems: "center", padding: "10px 0",
              borderBottom: `1px solid ${D2.mute2}`
            }}>
              <div style={{
                width: 14, display: "flex", justifyContent: "center", marginRight: 10,
                position: "relative"
              }}>
                {s.status === "current" ?
                <svg width="22" height="22" viewBox="0 0 22 22" style={{ position: "absolute", top: -4, left: -4 }}>
                    <circle cx="11" cy="11" r="4" fill={D2.accent} />
                    <circle cx="11" cy="11" r="4" fill="none" stroke={D2.accent} strokeWidth="1.5"
                  style={{ transformOrigin: "11px 11px" }}>
                      <animate attributeName="r" from="4" to="11" dur="2s" repeatCount="indefinite" />
                      <animate attributeName="opacity" from="0.7" to="0" dur="2s" repeatCount="indefinite" />
                    </circle>
                  </svg> :
                s.status === "exit" ?
                <div style={{ width: 14, height: 14, background: D2.ink }} /> :

                <div style={{
                  width: 8, height: 8, borderRadius: 4, border: `1.5px solid ${c}`,
                  background: s.status === "past" ? c : "transparent"
                }} />
                }
              </div>
              <div style={{
                flex: 1, fontFamily: D2.serif,
                fontSize: s.status === "current" || s.status === "exit" ? 18 : 15,
                fontWeight: s.status === "current" || s.status === "exit" ? 700 : 400,
                color: c,
                textDecoration: s.status === "past" ? "line-through" : "none",
                fontStyle: s.status === "past" ? "italic" : "normal"
              }}>{s.name}</div>
              {eta &&
              <span style={{
                fontFamily: D2.mono, fontSize: s.status === "current" ? 10 : 11,
                letterSpacing: s.status === "current" ? 2 : 0,
                color: c, fontWeight: 700
              }}>{eta}</span>
              }
            </div>);

        })}
      </div>

      <div style={{ padding: "12px 22px" }}>
        <button style={{
          width: "100%", background: D2.ink, color: D2.bg, border: "none", padding: "14px 20px",
          fontFamily: D2.serif, fontSize: 15, fontWeight: 600, cursor: "pointer",
          fontStyle: "italic"
        }}>Alert me before my stop ⟶</button>
      </div>
    </div>);

}

// ── Alerts ────────────────────────────────────────────────────────────────
function D2Alerts() {
  const alerts = [
  { level: "major", line: "Red", when: "Sat · Sun", headline: "Weekend track work between Howard & Belmont",
    body: "Northbound trains single-track through the weekend. Expect delays of ten to fifteen minutes; consider the Brown Line as an alternate." },
  { level: "minor", line: "Red", when: "Ongoing", headline: "Jackson elevator out of service",
    body: "Use Monroe or Roosevelt for step-free access. Service resumption expected by the 28th." },
  { level: "info", line: "Blue", when: "From May 1", headline: "New overnight schedule",
    body: "Trains will run every fifteen minutes between 1 and 4 AM, seven days a week." },
  { level: "info", line: "Brown", when: "Tue", headline: "Addison reopens after platform repair",
    body: "The inbound platform returns to service Tuesday morning. Thank you for your patience." }];

  const toneFor = (lvl) => lvl === "major" ? D2.accent : lvl === "minor" ? D2.mute : D2.accent2;
  const labelFor = (lvl) => lvl === "major" ? "Major" : lvl === "minor" ? "Minor" : "Advisory";

  return (
    <div className="d2-grain" style={{
      height: "100%", color: D2.ink, fontFamily: D2.sans,
      display: "flex", flexDirection: "column", overflow: "hidden"
    }}>
      <div style={{ padding: "20px 22px 12px" }}>
        <D2Caps>Page 2 — Dispatches</D2Caps>
        <h1 style={{
          fontFamily: D2.serif, fontSize: 32, fontWeight: 700, letterSpacing: -1,
          marginTop: 6, lineHeight: 0.95
        }}>
          <span style={{ fontStyle: "italic", fontWeight: 400 }}>Notices</span> &amp; Delays
        </h1>
        <div className="d2-rule-thick" style={{ marginTop: 12 }} />
        <div style={{
          fontFamily: D2.serif, fontStyle: "italic", fontSize: 12, color: D2.mute, marginTop: 8
        }}>Updated hourly from the dispatch feed.</div>
      </div>

      <div className="d2-scroll" style={{ flex: 1, overflow: "auto", padding: "0 22px" }}>
        {alerts.map((a, i) =>
        <article key={i} style={{
          padding: "14px 0",
          borderBottom: i === alerts.length - 1 ? "none" : `1px solid ${D2.mute2}`
        }}>
            <div style={{
            display: "flex", alignItems: "baseline", gap: 10, marginBottom: 6,
            justifyContent: "space-between"
          }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                <D2Pill line={a.line} code={a.line.slice(0, 2).toUpperCase()} size="sm" />
                <span style={{
                fontSize: 9, letterSpacing: 2, textTransform: "uppercase",
                color: toneFor(a.level), fontWeight: 800
              }}>{labelFor(a.level)}</span>
              </div>
              <span style={{ fontSize: 10, color: D2.mute, fontFamily: D2.mono }}>{a.when}</span>
            </div>
            <h2 style={{
            fontFamily: D2.serif, fontSize: 19, fontWeight: 600, letterSpacing: -0.4,
            lineHeight: 1.2, margin: 0
          }}>{a.headline}</h2>
            <p style={{
            fontFamily: D2.serif, fontSize: 13.5, color: D2.ink2, lineHeight: 1.55,
            marginTop: 6, fontStyle: i % 2 === 1 ? "italic" : "normal"
          }}>{a.body}</p>
          </article>
        )}
      </div>
      <D2TabBar active="alerts" />
    </div>);

}

// ── Saved ─────────────────────────────────────────────────────────────────
function D2Saved() {
  const places = [
  { label: "Home", sub: "2132 N Kedzie Blvd · Logan Square", time: "14m via Blue" },
  { label: "Work", sub: "Merchandise Mart · River North", time: "22m via Brown" },
  { label: "Chicago Athletic", sub: "12 S Michigan Ave", time: "28m via Blue" },
  { label: "Mom's", sub: "Rogers Park · Morse Red Line", time: "46m via Red" }];

  const routes = [
  { title: "Home → Work", pills: ["Blue", "Brown"], total: 28, ok: true },
  { title: "Work → Home", pills: ["Brown", "Blue"], total: 26, ok: true },
  { title: "Home → O'Hare", pills: ["Blue"], total: 38, ok: false }];

  return (
    <div className="d2-grain" style={{
      height: "100%", color: D2.ink, fontFamily: D2.sans,
      display: "flex", flexDirection: "column", overflow: "hidden"
    }}>
      <div style={{ padding: "20px 22px 10px" }}>
        <D2Caps>Page 4 — The Index</D2Caps>
        <h1 style={{
          fontFamily: D2.serif, fontSize: 32, fontWeight: 700, letterSpacing: -1,
          marginTop: 6, lineHeight: 0.95
        }}>
          <span style={{ fontStyle: "italic", fontWeight: 400 }}>Saved</span> Voyages
        </h1>
        <div className="d2-rule-thick" style={{ marginTop: 12 }} />
      </div>

      <div className="d2-scroll" style={{ flex: 1, overflow: "auto", padding: "8px 22px 14px" }}>
        <D2Caps style={{ marginBottom: 6 }}>Places</D2Caps>
        {places.map((p, i) =>
        <div key={i} style={{
          padding: "10px 0", borderBottom: `1px solid ${D2.mute2}`,
          display: "flex", alignItems: "baseline", gap: 10
        }}>
            <span style={{
            fontFamily: D2.serif, fontStyle: "italic", color: D2.mute, fontSize: 11, width: 18
          }}>§{i + 1}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: D2.serif, fontSize: 16, fontWeight: 600 }}>{p.label}</div>
              <div style={{
              fontSize: 11, color: D2.mute, marginTop: 2, fontStyle: "italic", fontFamily: D2.serif
            }}>{p.sub}</div>
            </div>
            <span style={{ fontFamily: D2.mono, fontSize: 11, color: D2.ink2 }}>{p.time}</span>
          </div>
        )}

        <D2Caps style={{ margin: "18px 0 6px" }}>Routes</D2Caps>
        {routes.map((r, i) =>
        <div key={i} style={{
          padding: "12px 0", borderBottom: `1px solid ${D2.mute2}`
        }}>
            <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "baseline"
          }}>
              <div style={{ fontFamily: D2.serif, fontSize: 16, fontWeight: 600 }}>{r.title}</div>
              <div style={{ fontFamily: D2.mono, fontSize: 12, fontWeight: 700 }} className="d2-tnum">
                {r.total}m
              </div>
            </div>
            <div style={{ display: "flex", gap: 6, marginTop: 8, alignItems: "center" }}>
              {r.pills.map((line) =>
            <D2Pill key={line} line={line} code={line.slice(0, 2).toUpperCase()} size="sm" />
            )}
              <span style={{
              fontSize: 10, letterSpacing: 2, textTransform: "uppercase", fontWeight: 700,
              color: r.ok ? D2.good : D2.accent, marginLeft: 6
            }}>
                {r.ok ? "Clear" : "Delayed"}
              </span>
            </div>
          </div>
        )}
      </div>
      <D2TabBar active="saved" />
    </div>);

}

// ── Station detail ────────────────────────────────────────────────────────
function D2Station() {
  const deps = [
  { line: "Blue", dir: "Toward Forest Park", eta: 3, crowd: "Light" },
  { line: "Blue", dir: "Toward O'Hare", eta: 6, crowd: "Moderate" },
  { line: "Blue", dir: "Toward Forest Park", eta: 11, crowd: "—" },
  { line: "Blue", dir: "Toward O'Hare", eta: 14, crowd: "—" }];

  return (
    <div className="d2-grain" style={{
      height: "100%", color: D2.ink, fontFamily: D2.sans,
      display: "flex", flexDirection: "column", overflow: "hidden"
    }}>
      <div style={{ padding: "18px 22px 10px" }}>
        <D2Caps>Station · Kedzie Branch</D2Caps>
        <h1 style={{
          fontFamily: D2.serif, fontSize: 34, fontWeight: 700, letterSpacing: -1,
          marginTop: 6, lineHeight: 0.95
        }}>Logan Square</h1>
        <div style={{
          fontFamily: D2.serif, fontStyle: "italic", fontSize: 13, color: D2.mute, marginTop: 6
        }}>
          Blue Line, elevated · Milwaukee &amp; Kedzie &amp; Logan
        </div>
        <div className="d2-rule-thick" style={{ marginTop: 12 }} />
      </div>

      <div style={{ padding: "4px 22px 12px" }}>
        <D2Caps style={{ marginBottom: 8 }}>Next trains</D2Caps>
        {deps.map((d, i) =>
        <div key={i} style={{
          display: "flex", alignItems: "center", gap: 12, padding: "12px 0",
          borderBottom: `1px solid ${D2.mute2}`
        }}>
            <D2Pill line={d.line} code={d.line.slice(0, 2).toUpperCase()} />
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: D2.serif, fontSize: 15, fontWeight: 600 }}>{d.dir}</div>
              <div style={{
              fontFamily: D2.serif, fontSize: 11, color: D2.mute, fontStyle: "italic", marginTop: 2
            }}>Car occupancy: {d.crowd}</div>
            </div>
            <div style={{
            fontFamily: D2.serif, fontSize: 28, fontWeight: 700, fontStyle: "italic",
            letterSpacing: -1, lineHeight: 1
          }} className="d2-tnum">
              {d.eta}<span style={{ fontSize: 11, color: D2.mute, fontStyle: "normal", marginLeft: 2 }}>m</span>
            </div>
          </div>
        )}
      </div>

      <div style={{ padding: "4px 22px 0" }}>
        <div className="d2-special">
          <div style={{ fontSize: 9, fontWeight: 800, letterSpacing: 1, color: D2.accent2, textTransform: "uppercase", marginBottom: 4 }}>
            Station note
          </div>
          <div style={{ fontFamily: D2.serif, fontStyle: "italic", fontSize: 13, lineHeight: 1.45 }}>
            Elevator in service. Warming shelter open on the inbound platform until April 30.
          </div>
        </div>
      </div>

      <div style={{ padding: "12px 22px 0", flex: 1 }}>
        <D2Caps style={{ marginBottom: 6 }}>Nearby</D2Caps>
        {["Logan Square Farmers Market · 0.1 mi", "Lula Cafe · 0.2 mi", "CTA Bus №76 Diversey · at stop"].map((x, i) =>
        <div key={i} style={{
          padding: "9px 0", borderBottom: `1px solid ${D2.mute2}`,
          fontFamily: D2.serif, fontSize: 14
        }}>{x}</div>
        )}
      </div>

      <D2TabBar active="map" />
    </div>);

}

// ── Widget / lock-screen glance ───────────────────────────────────────────
function D2Widget() {
  return (
    <div style={{
      height: "100%", background: "#0a0906", padding: 24,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: D2.sans
    }}>
      <div style={{ color: "#fff", width: "100%" }}>
        <div style={{
          fontSize: 10, letterSpacing: 3, textTransform: "uppercase",
          color: "rgba(255,255,255,0.5)", fontWeight: 700
        }}>09:42</div>
        <div style={{ marginTop: 12 }}>
          <div className="d2-grain-paper" style={{
            border: `1px solid ${D2.rule}`, padding: 16, color: D2.ink
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <D2Caps>The Chicago Routefinder</D2Caps>
              <D2Lamp />
            </div>
            <div className="d2-rule-thick" style={{ margin: "8px 0 10px" }} />
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <span style={{
                fontFamily: D2.serif, fontSize: 64, fontWeight: 700, letterSpacing: -3,
                lineHeight: 0.85, fontStyle: "italic"
              }}>14</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: D2.serif, fontSize: 14, fontWeight: 600 }}>
                  minutes to Monroe
                </div>
                <div style={{
                  fontFamily: D2.serif, fontStyle: "italic", fontSize: 12, color: D2.mute, marginTop: 2
                }}>
                  Blue Line · inbound · on schedule
                </div>
              </div>
            </div>
            <div style={{
              marginTop: 12, paddingTop: 10, borderTop: `1px dashed ${D2.mute2}`,
              display: "flex", justifyContent: "space-between", alignItems: "center"
            }}>
              <div style={{ display: "flex", gap: 6 }}>
                <D2Pill line="Blue" code="BL" size="sm" />
                <span style={{ fontFamily: D2.serif, fontStyle: "italic", fontSize: 12, color: D2.mute }}>
                  train № 412
                </span>
              </div>
              <span style={{ fontFamily: D2.mono, fontSize: 11, color: D2.ink }}>5 stops →</span>
            </div>
          </div>
        </div>
      </div>
    </div>);

}

// ── Desktop ───────────────────────────────────────────────────────────────
function D2Desktop() {
  return (
    <div className="d2-grain" style={{
      height: "100%", color: D2.ink, fontFamily: D2.sans,
      display: "flex", overflow: "hidden"
    }}>
      {/* Left rail */}
      <div style={{
        width: 60, borderRight: `2px solid ${D2.rule}`, padding: "20px 0",
        display: "flex", flexDirection: "column", alignItems: "center", gap: 18,
        flexShrink: 0
      }}>
        <div style={{
          writingMode: "vertical-rl", transform: "rotate(180deg)",
          fontFamily: D2.serif, fontSize: 14, fontWeight: 700, letterSpacing: 2,
          textTransform: "uppercase"
        }}>THE CHICAGO ROUTEFINDER

        </div>
        <div style={{ flex: 1 }} />
        {["H", "M", "A", "S"].map((c, i) =>
        <div key={i} style={{
          width: 32, height: 32, border: `1px solid ${D2.rule}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: D2.serif, fontWeight: 600, fontSize: 14,
          background: i === 0 ? D2.ink : "transparent",
          color: i === 0 ? D2.bg : D2.ink
        }}>{c}</div>
        )}
      </div>

      {/* Results column */}
      <div style={{
        width: 420, borderRight: `2px solid ${D2.rule}`, display: "flex",
        flexDirection: "column", flexShrink: 0
      }}>
        <div style={{ padding: "22px 24px 10px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <D2Caps>Mon · Apr 20</D2Caps>
            <D2Caps>5:47 PM</D2Caps>
          </div>
          <h1 style={{
            fontFamily: D2.serif, fontSize: 28, fontWeight: 500, letterSpacing: -0.8,
            lineHeight: 1, marginTop: 10, fontStyle: "italic"
          }}>Logan Square</h1>
          <h1 style={{
            fontFamily: D2.serif, fontSize: 28, fontWeight: 700, letterSpacing: -0.8,
            lineHeight: 1, marginTop: 2
          }}>to the Art Institute</h1>
          <div className="d2-rule-thick" style={{ marginTop: 12 }} />
        </div>

        <div className="d2-scroll" style={{ flex: 1, overflow: "auto" }}>
          {MOCK_RESULT.routes.map((route, i) =>
          <div key={route.id} style={{
            padding: "14px 24px", borderBottom: `1px solid ${D2.mute2}`,
            background: i === 0 ? D2.paper : "transparent"
          }}>
              {i === 0 &&
            <div style={{
              fontSize: 9, letterSpacing: 2, textTransform: "uppercase",
              color: D2.accent, fontWeight: 800, marginBottom: 4
            }}>★ Recommended</div>
            }
              <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
                <div style={{
                fontFamily: D2.serif, fontSize: 52, fontWeight: 700, fontStyle: "italic",
                letterSpacing: -2, lineHeight: 0.85
              }}>{route.total}</div>
                <div style={{ flex: 1, paddingTop: 4 }}>
                  <D2Caps>minutes · {route.transfers === 0 ? "direct" : `${route.transfers} transfer`}</D2Caps>
                  <div style={{ display: "flex", gap: 6, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
                    {route.legs.filter((l) => l.type === "transit").map((leg, j) =>
                  <D2Pill key={j} line={leg.line} code={leg.code} size="sm" />
                  )}
                    <span style={{
                    fontFamily: D2.serif, fontStyle: "italic", fontSize: 12, color: D2.mute, marginLeft: 4
                  }}>
                      next in {route.wait === 0 ? "moments" : `${route.wait} min`}
                    </span>
                  </div>
                  {i === 0 &&
                <div style={{
                  fontFamily: D2.serif, fontSize: 13.5, fontStyle: "italic", color: D2.ink2,
                  marginTop: 10, lineHeight: 1.45
                }}>
                      Board at Logan Square toward the Loop; alight at Monroe and walk four minutes east through Millennium Park.
                    </div>
                }
                </div>
              </div>
            </div>
          )}
        </div>

        <div style={{ padding: "12px 24px", borderTop: `2px solid ${D2.rule}` }}>
          <D2Lamp />
        </div>
      </div>

      {/* Map + figure */}
      <div style={{ flex: 1, padding: 20, display: "flex", flexDirection: "column" }}>
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "baseline",
          marginBottom: 10
        }}>
          <D2Caps>Plate I — Topographical Representation</D2Caps>
          <D2Caps>N ↑ · not to scale</D2Caps>
        </div>
        <div style={{
          flex: 1, background: D2.paper, border: `2px solid ${D2.rule}`, overflow: "hidden",
          position: "relative"
        }}>
          <SchematicMap theme="paper" />
          <div style={{
            position: "absolute", top: 14, right: 14, background: "rgba(255,251,239,0.95)",
            border: `1px solid ${D2.rule}`, padding: "10px 12px", maxWidth: 220
          }}>
            <div style={{
              fontSize: 9, letterSpacing: 2, textTransform: "uppercase",
              color: D2.mute, fontWeight: 700
            }}>Your train</div>
            <div style={{
              fontFamily: D2.serif, fontSize: 14, fontWeight: 600, marginTop: 4
            }}>
              Train № 412 · <span style={{ fontStyle: "italic", fontWeight: 400 }}>3 min away</span>
            </div>
            <div className="d2-dash" style={{ margin: "8px 0" }} />
            <div style={{
              fontFamily: D2.serif, fontStyle: "italic", fontSize: 11, color: D2.mute, lineHeight: 1.4
            }}>
              Inbound via the Blue Line, passing Division toward Monroe.
            </div>
          </div>
          <div style={{
            position: "absolute", bottom: 14, left: 14, background: "rgba(255,251,239,0.95)",
            border: `1px solid ${D2.rule}`, padding: "8px 12px"
          }}>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <D2Pill line="Blue" code="BL" size="sm" />
              <span style={{ fontFamily: D2.serif, fontSize: 12, fontWeight: 600 }}>Blue Line</span>
              <span style={{ fontFamily: D2.serif, fontSize: 11, fontStyle: "italic", color: D2.mute }}>
                9 stations shown
              </span>
            </div>
          </div>
        </div>
        <div style={{
          fontFamily: D2.serif, fontStyle: "italic", fontSize: 11, color: D2.mute,
          textAlign: "center", marginTop: 8
        }}>
          Fig. I — Route from Logan Square to the Art Institute, with active train position relative to the Chicago River and Lake Michigan.
        </div>
      </div>
    </div>);

}

Object.assign(window, {
  D2, D2Pill, D2Caps, D2Lamp, D2Masthead, D2Footer, D2TabBar,
  D2Home, D2Search, D2Results, D2LiveTrip, D2Alerts, D2Saved, D2Station, D2Widget, D2Desktop
});