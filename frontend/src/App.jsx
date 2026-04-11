import { useState, useRef, useEffect } from "react";
import "./App.css";
import MapView from "./MapView.jsx";

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

// ---------------------------------------------------------------------------
// Transit photo manifest — add entries here once photos are sourced (HUMAN_TODO)
// ---------------------------------------------------------------------------

const PHOTOS = [
  { src: "/transit-photos/red-line-howard.jpg",   caption: "Red Line — Howard" },
  { src: "/transit-photos/loop-elevated.jpg",      caption: "The Loop — Elevated Track" },
  { src: "/transit-photos/blue-line-ohare.jpg",    caption: "Blue Line — O'Hare" },
  { src: "/transit-photos/state-lake.jpg",         caption: "State/Lake — The Loop" },
  { src: "/transit-photos/wrigley-addison.jpg",    caption: "Addison — Wrigley Field" },
];

function TransitPhoto({ fading }) {
  const [photo] = useState(
    () => PHOTOS[Math.floor(Math.random() * PHOTOS.length)]
  );

  return (
    <div className={`transit-photo${fading ? " transit-photo--fading" : ""}`}>
      <img src={photo.src} alt={photo.caption} className="transit-photo-img" />
      <p className="transit-photo-caption">{photo.caption}</p>
    </div>
  );
}

function renderMarkdown(text) {
  // Strip markdown headers, bold, and italic
  return text
    .replace(/^#{1,3}\s+/gm, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .trim();
}

const DIRECTION_ARROWS = {
  N: "↑", NE: "↗", E: "→", SE: "↘", S: "↓", SW: "↙", W: "←", NW: "↖",
};

function WalkLegItem({ leg, index }) {
  const [stepsOpen, setStepsOpen] = useState(false);
  const hasSteps = leg.directions && leg.directions.length > 1;

  const label =
    leg.from === "Your location"
      ? `Walk ${leg.minutes} min to ${leg.to}`
      : leg.to === "Your destination"
      ? `Walk ${leg.minutes} min to your destination`
      : `Transfer — walk ${leg.minutes} min`;

  return (
    <li key={index} className="leg leg-walk">
      <span className="leg-icon">🚶</span>
      <span className="leg-walk-body">
        <span className="leg-text">{label}</span>
        {hasSteps && (
          <button
            className="leg-steps-toggle"
            onClick={() => setStepsOpen((v) => !v)}
            aria-expanded={stepsOpen}
          >
            {stepsOpen ? "Hide steps" : "Steps"}
          </button>
        )}
        {stepsOpen && (
          <ol className="leg-steps">
            {leg.directions.map((step, si) => (
              <li key={si} className="leg-step">
                <span className="leg-step-arrow">
                  {DIRECTION_ARROWS[step.direction] || "·"}
                </span>
                <span className="leg-step-text">
                  {step.direction && <span className="leg-step-dir">{step.direction}</span>}
                  {" on "}
                  <span className="leg-step-street">{step.street}</span>
                </span>
                <span className="leg-step-time">{step.minutes} min</span>
              </li>
            ))}
          </ol>
        )}
      </span>
    </li>
  );
}

function RouteLegs({ legs }) {
  return (
    <ol className="route-legs">
      {legs.map((leg, i) => {
        if (leg.type === "walk") {
          return <WalkLegItem key={i} leg={leg} index={i} />;
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

function RouteCard({ route, index, isFirst, isSelected, onSelect }) {
  const [expanded, setExpanded] = useState(isFirst);
  const waitNote =
    route.wait_minutes === null ? ""
    : route.wait_minutes === 0  ? " · Due now"
    : ` · ${route.wait_minutes} min wait`;
  const xferNote =
    route.transfers === 0
      ? "No transfers"
      : route.transfers === 1
      ? "1 transfer"
      : `${route.transfers} transfers`;

  return (
    <div className={`route-card${isFirst ? " route-card--best" : ""}${isSelected ? " route-card--selected" : ""}`}>
      <button
        className="route-card-header"
        onClick={() => { onSelect(); setExpanded((v) => !v); }}
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

  const [selectedRouteIndex, setSelectedRouteIndex] = useState(0);

  // Photo state — managed entirely within handleSubmit via photoFadeTimer ref
  const [photoMounted, setPhotoMounted] = useState(false);
  const [photoFading, setPhotoFading] = useState(false);
  const [photoKey, setPhotoKey] = useState(0);  // increment to force new random photo
  const photoFadeTimer = useRef(null);
  const abortRef = useRef(null);

  useEffect(() => {
    return () => { if (photoFadeTimer.current) clearTimeout(photoFadeTimer.current); };
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!origin.trim() || !destination.trim()) return;

    // Cancel any in-flight request from a previous search
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    // Cancel any in-progress photo fade from a previous search
    if (photoFadeTimer.current) clearTimeout(photoFadeTimer.current);
    setSelectedRouteIndex(0);

    // Mount a fresh photo for this search (new key → new random pick)
    setPhotoKey((k) => k + 1);
    setPhotoMounted(true);
    setPhotoFading(false);

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
        signal: abortRef.current.signal,
      });

      if (!res.ok) {
        let msg = `Service error (${res.status} ${res.statusText})`;
        try {
          const data = await res.json();
          msg = data.detail || msg;
        } catch {
          // Response body is not JSON (e.g. Railway/nginx 502 gateway error)
        }
        throw new Error(msg);
      }

      const data = await res.json();
      const routes = data.routes || [];

      setResult({
        recommendation: renderMarkdown(data.recommendation),
        routes,
        originCoords: data.origin_coords,
        destCoords:   data.dest_coords,
      });

      // Routes available — fade photo out, then remove it from DOM
      if (routes.length > 0) {
        setPhotoFading(true);
        photoFadeTimer.current = setTimeout(() => {
          setPhotoMounted(false);
          setPhotoFading(false);
        }, 1000);
      }
      // No routes — photo stays visible (loading state replaced by no-routes state)

    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <div className="layout layout--split">
        <div className="panel-cards">
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
                      <RouteCard
                        key={i}
                        route={route}
                        index={i}
                        isFirst={i === 0}
                        isSelected={i === selectedRouteIndex}
                        onSelect={() => setSelectedRouteIndex(i)}
                      />
                    ))}
                  </section>
                )}
              </div>
            )}
          </main>
        </div>

        <div className="panel-map">
          {photoMounted && (
            <TransitPhoto key={photoKey} fading={photoFading} />
          )}
          <MapView
            route={result?.routes?.[selectedRouteIndex] ?? null}
            visible={!!(result && result.routes.length > 0)}
          />
        </div>
      </div>
    </div>
  );
}
