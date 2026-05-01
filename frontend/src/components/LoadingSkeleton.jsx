import { useTranslation } from "react-i18next";

export default function LoadingSkeleton() {
  const { t } = useTranslation();
  return (
    <div className="skeleton-wrapper" aria-busy="true" aria-label={t("aria_loading")}>
      <p className="skeleton-plotting" aria-hidden="true">{t("loading_plotting")}</p>
      <div className="plot-rule" aria-hidden="true" />
      <div className="skeleton-ghost-line skeleton-ghost-line--long"  aria-hidden="true" />
      <div className="skeleton-ghost-line skeleton-ghost-line--medium" aria-hidden="true" />
      <div className="skeleton-ghost-line skeleton-ghost-line--short" aria-hidden="true" />
    </div>
  );
}
