import { useTranslation } from "react-i18next";

/* SheetSegmentedControl — three-segment tab control rendered at the top of
 * the mobile bottom sheet. Replaces the desktop SideRail's nav role on
 * mobile (where a vertical rail doesn't fit). Same three sections as the
 * SideRail (no Map tab — the map is always visible behind the sheet on
 * mobile, so a Map segment would be redundant).
 *
 * Reuses existing i18n keys (tab_home / tab_alerts / tab_saved) so no
 * new translations are needed for the segment labels.
 */

const SEGMENTS = [
  { id: "home"   },
  { id: "alerts" },
  { id: "saved"  },
];

export default function SheetSegmentedControl({ activeTab, onTabChange }) {
  const { t } = useTranslation();
  return (
    <div className="sheet-segmented" role="tablist" aria-label={t("aria_main_nav")}>
      {SEGMENTS.map(({ id }) => {
        const active = activeTab === id;
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={active}
            aria-current={active ? "page" : undefined}
            className={`sheet-segmented__btn${active ? " sheet-segmented__btn--active" : ""}`}
            onClick={() => onTabChange(id)}
          >
            {t(`tab_${id}`)}
          </button>
        );
      })}
    </div>
  );
}
