import { useTranslation } from "react-i18next";

export default function LoadingSkeleton() {
  const { t } = useTranslation();
  return (
    <div className="skeleton-wrapper" aria-busy="true" aria-label={t("aria_loading")}>
      <div className="skeleton skeleton-line skeleton-line--long" />
      <div className="skeleton skeleton-line skeleton-line--medium" />
      <div className="skeleton skeleton-line skeleton-line--short" />
      <div className="skeleton skeleton-card" />
    </div>
  );
}
