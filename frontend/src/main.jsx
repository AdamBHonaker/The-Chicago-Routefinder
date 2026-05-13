import { StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import "./index.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "./i18n.js";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ErrorBoundary>
      <Suspense fallback={null}>
        <App />
      </Suspense>
    </ErrorBoundary>
  </StrictMode>
);

// Warm the lazy MapView chunk during browser idle so it's already cached when
// <App> mounts <MapView>. React.lazy still controls render-time mounting; this
// only primes the module cache so the dynamic import resolves immediately.
// Without this, the MapView chunk download is sequential — it only starts
// after React resolves the lazy() boundary on first render.
if (typeof window !== "undefined") {
  const warm = () => { import("./MapView.jsx"); };
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(warm);
  } else {
    setTimeout(warm, 0);
  }
}
