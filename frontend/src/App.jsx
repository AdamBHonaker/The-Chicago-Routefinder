import { useState } from "react";
import "./App.css";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

const LINE_COLORS = {
  "Red Line":    "#c60c30",
  "Blue Line":   "#00a1de",
  "Brown Line":  "#62361b",
  "Green Line":  "#009b3a",
  "Orange Line": "#f9461c",
  "Purple Line": "#522398",
  "Pink Line":   "#e27ea6",
  "Yellow Line": "#f9e300",
};

const BUS_DIRECTION_COLORS = {
  Northbound: "#1565c0",
  Southbound: "#4e342e",
  Eastbound:  "#00695c",
  Westbound:  "#ef6c00",
};

function renderMarkdown(text) {
  // Strip markdown headers (## Foo → plain text) and bold (**foo** → foo)
  return text
    .replace(/^#{1,3}\s+/gm, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .trim();
}

function RouteLegs({ legs }) {
  return (
    <ol className="route-legs">
      {legs.map((leg, i) => {
        if (leg.type === "walk") {
          const label =
            leg.from === "Your location"
              ? `Walk ${leg.minutes} min to ${leg.to}`
              : leg.to === "Your destination"
              ? `Walk ${leg.minutes} min to your destination`
              : `Transfer — walk ${leg.minutes} min`;
          return (
            <li key={i} className="leg leg-walk">
              <span className="leg-icon">🚶</span>
              <span className="leg-text">{label}</span>
            </li>
          );
        }
        const isBus = leg.line in BUS_DIRECTION_COLORS;
        const color = isBus
          ? BUS_DIRECTION_COLORS[leg.line]
          : (LINE_COLORS[leg.line] || "#4a9eff");
        const pillLabel = isBus
          ? leg.line_code
          : leg.line?.replace(" Line", "");
        return (
          <li key={i} className="leg leg-transit">
            <span className="leg-pill" style={{ background: color }}>
              {pillLabel}
            </span>
            <span className="leg-text">
              {leg.from} → {leg.to}
              <span className="leg-duration"> · {leg.minutes} min</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function RouteCard({ route, index, isFirst }) {
  const [expanded, setExpanded] = useState(isFirst);
  const waitNote = route.wait_minutes > 0 ? ` · ${route.wait_minutes} min wait` : "";
  const xferNote =
    route.transfers === 0
      ? "No transfers"
      : route.transfers === 1
      ? "1 transfer"
      : `${route.transfers} transfers`;

  return (
    <div className={`route-card ${isFirst ? "route-card--best" : ""}`}>
      <button
        className="route-card-header"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <div className="route-card-summary">
          {isFirst && <span className="route-badge">Best</span>}
          <span className="route-total">{route.total_minutes} min total</span>
          <span className="route-meta">{xferNote}{waitNote}</span>
        </div>
        <span className="route-chevron">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && <RouteLegs legs={route.legs} />}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="skeleton-wrapper" aria-busy="true" aria-label="Finding your route">
      <div className="skeleton skeleton-line skeleton-line--long" />
      <div className="skeleton skeleton-line skeleton-line--medium" />
      <div className="skeleton skeleton-line skeleton-line--short" />
      <div className="skeleton skeleton-card" />
    </div>
  );
}

export default function App() {
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [transitMode, setTransitMode] = useState("All");
  const [busFullness, setBusFullness] = useState("All");

  const [result, setResult] = useState(null);   // { recommendation, routes }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    if (!origin.trim() || !destination.trim()) return;

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await fetch(`${BACKEND_URL}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin,
          destination,
          transit_mode: transitMode,
          bus_fullness: busFullness,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Something went wrong.");
      }

      const data = await res.json();
      setResult({
        recommendation: renderMarkdown(data.recommendation),
        routes: data.routes || [],
      });
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-top">
          <h1>CTA Transit</h1>
          <div className="filters">
            <select
              value={transitMode}
              onChange={(e) => setTransitMode(e.target.value)}
              aria-label="Transit mode"
            >
              <option value="All">All modes</option>
              <option value="Train">Train</option>
              <option value="Bus">Bus</option>
            </select>
            {/* Bus fullness filter — hidden until CTA populates the psgld field
                in Bus Tracker API responses. All current responses return psgld=""
                so the filter has no effect. Re-enable when CTA enables the data.
            <select
              value={busFullness}
              onChange={(e) => setBusFullness(e.target.value)}
              aria-label="Bus fullness"
            >
              <option value="All">Any fullness</option>
              <option value="Empty">Empty</option>
              <option value="Half-Full">Half-full</option>
              <option value="Full">Full</option>
            </select>
            */}
          </div>
        </div>
        <p className="tagline">Stop thinking about how to get there. Just go.</p>
      </header>

      <main className="main">
        <form className="form" onSubmit={handleSubmit}>
          <label>
            <span>From</span>
            <input
              type="search"
              inputMode="search"
              enterKeyHint="go"
              placeholder="Neighborhood, address, or building"
              value={origin}
              onChange={(e) => setOrigin(e.target.value)}
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="words"
            />
          </label>

          <label>
            <span>To</span>
            <input
              type="search"
              inputMode="search"
              enterKeyHint="go"
              placeholder="Neighborhood, address, or building"
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="words"
            />
          </label>

          <button type="submit" disabled={loading}>
            {loading ? "Finding your route…" : "Get Route"}
          </button>
        </form>

        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}

        {loading && <LoadingSkeleton />}

        {result && !loading && (
          <div className="results">
            <div className="recommendation">
              <p>{result.recommendation}</p>
            </div>

            {result.routes.length > 0 && (
              <section className="routes-section">
                <h2 className="routes-heading">Route options</h2>
                {result.routes.map((route, i) => (
                  <RouteCard key={i} route={route} index={i} isFirst={i === 0} />
                ))}
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
