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
  }

  render() {
    if (this.state.hasError) {
      return <FallbackUI />;
    }
    return this.props.children;
  }
}
