import { Component } from "react";
import { useTranslation } from "react-i18next";

function FallbackUI() {
  const { t } = useTranslation();
  return (
    <div className="error-boundary">
      <div className="error-boundary__icon">🚌</div>
      <h1 className="error-boundary__title">
        {t("error_boundary_title")}
      </h1>
      <p className="error-boundary__hint">
        {t("error_boundary_hint")}
      </p>
      <button
        className="error-boundary__btn"
        onClick={() => window.location.reload()}
      >
        {t("error_boundary_btn")}
      </button>
    </div>
  );
}

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("[ErrorBoundary] Uncaught render error:", error, info.componentStack);
    // Optional remote reporting: when VITE_ERROR_REPORT_URL is set at build time
    // we POST a stripped-down crash report so silent prod failures surface.
    // Deliberately minimal — no stack-trace contents, no user input — just
    // error name/message and the React component path. Fire-and-forget; if the
    // reporter itself errors we swallow it so the fallback UI still renders.
    const reportUrl = import.meta.env.VITE_ERROR_REPORT_URL;
    if (reportUrl) {
      try {
        const body = JSON.stringify({
          name: String(error?.name || "Error").slice(0, 100),
          message: String(error?.message || "").slice(0, 500),
          componentStack: String(info?.componentStack || "").slice(0, 2000),
          url: window.location.pathname,
          ts: Date.now(),
        });
        fetch(reportUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body,
          keepalive: true,
          credentials: "omit",
        }).catch(() => {});
      } catch {
        // Reporter must never throw — fallback UI must still render.
      }
    }
  }

  render() {
    if (this.state.hasError) {
      return <FallbackUI />;
    }
    return this.props.children;
  }
}
