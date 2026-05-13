import { useTranslation } from "react-i18next";

const TABS = [
  { id: "home",   code: "H" },
  { id: "alerts", code: "A" },
  { id: "tools",  code: "T" },  // FEAT-018: was "saved" (S)
];

export default function SideRail({ activeTab, onTabChange }) {
  const { t } = useTranslation();
  return (
    <aside className="side-rail" aria-hidden={false}>
      <nav className="side-rail__nav" aria-label={t("aria_main_nav")}>
        <span className="side-rail__title" aria-hidden="true">{t("app_title")}</span>
        <span className="side-rail__spacer" aria-hidden="true" />
        {TABS.map(({ id, code }) => (
          <button
            key={id}
            type="button"
            className={`side-rail__tab${activeTab === id ? " side-rail__tab--active" : ""}`}
            onClick={() => onTabChange(id)}
            aria-current={activeTab === id ? "page" : undefined}
            aria-label={t(`tab_${id}`)}
            title={t(`tab_${id}`)}
          >
            {code}
          </button>
        ))}
      </nav>
    </aside>
  );
}
