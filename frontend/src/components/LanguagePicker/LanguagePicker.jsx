import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  CONTINENT_IDS,
  LANGUAGES_BY_CONTINENT,
  LANGUAGE_NAMES,
} from "../../i18n.js";
import africaSvg from "../../assets/continents/africa.svg?raw";
import americasSvg from "../../assets/continents/americas.svg?raw";
import asiaSvg from "../../assets/continents/asia.svg?raw";
import europeSvg from "../../assets/continents/europe.svg?raw";
import middleEastSvg from "../../assets/continents/middle-east.svg?raw";
import oceaniaSvg from "../../assets/continents/oceania.svg?raw";

// SEC-002: parse the bundled SVG into a React-controlled `{viewBox, d}` shape
// at module load instead of feeding the raw string to `dangerouslySetInnerHTML`.
// Each continent silhouette is a single `<path>` (Natural Earth → manually
// optimized); extracting viewBox and `d` lets us render with JSX so any
// hostile attribute (`onclick=...`, `<script>` smuggled in via a future asset
// swap or supply-chain compromise) is stripped by React's element model.
function parseContinentSvg(raw) {
  const viewBox = raw.match(/viewBox="([^"]+)"/)?.[1] ?? "0 0 100 100";
  const d       = raw.match(/<path[^>]*\bd="([^"]+)"/)?.[1] ?? "";
  return { viewBox, d };
}

// ---------------------------------------------------------------------------
// LanguagePicker — Feature LocaleExpansion, Chunk 15.
//
// A 2-step picker that replaces the flat 76-entry <select> when
// VITE_CONTINENT_PICKER_ENABLED=true.
//
//   Step 1: 6 continent tiles (custom SVG silhouettes from
//           src/assets/continents/, stroke=currentColor so they recolor
//           in light/dark/high-contrast modes).
//   Step 2: scoped vertical menu of languages assigned to that continent.
//
// Continent assignment lives in i18n.js → LANGUAGES_BY_CONTINENT and is
// diaspora-aware: languages spoken across multiple continents (e.g. es, pt)
// appear in each relevant continent list.
// Continents with zero languages (currently Oceania) are filtered out of
// the grid and appear automatically once languages are added to their array.
//
// Persistence: i18n.changeLanguage() writes to localStorage["cta_language"]
// via the existing LanguageDetector config — no schema change here.
// ---------------------------------------------------------------------------
const CONTINENT_SVG = {
  africa:      parseContinentSvg(africaSvg),
  americas:    parseContinentSvg(americasSvg),
  asia:        parseContinentSvg(asiaSvg),
  europe:      parseContinentSvg(europeSvg),
  middle_east: parseContinentSvg(middleEastSvg),
  oceania:     parseContinentSvg(oceaniaSvg),
};

export default function LanguagePicker() {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [continent, setContinent] = useState(null);
  const containerRef = useRef(null);
  const triggerRef = useRef(null);

  const activeCode = i18n.resolvedLanguage ?? i18n.language;
  const activeLabel = LANGUAGE_NAMES[activeCode] ?? activeCode;

  useEffect(() => {
    if (!open) return undefined;
    function onDocClick(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
        setContinent(null);
      }
    }
    function onKey(e) {
      if (e.key === "Escape") {
        if (continent) {
          setContinent(null);
        } else {
          setOpen(false);
          triggerRef.current?.focus();
        }
      }
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, continent]);

  function handleSelect(code) {
    i18n.changeLanguage(code);
    setOpen(false);
    setContinent(null);
    triggerRef.current?.focus();
  }

  return (
    <div className="language-picker" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        className="masthead-select language-picker-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("aria_language")}
        onClick={() => {
          if (open) {
            setOpen(false);
            setContinent(null);
          } else {
            setOpen(true);
          }
        }}
      >
        {activeLabel}
      </button>

      {open && !continent && (
        <div
          className="language-picker-popover language-picker-popover--continents"
          role="menu"
          aria-label={t("aria_language")}
        >
          {CONTINENT_IDS.filter((id) => (LANGUAGES_BY_CONTINENT[id] ?? []).length > 0).map((id) => {
            const langs = LANGUAGES_BY_CONTINENT[id] ?? [];
            const labelKey = `continent_${id}`;
            return (
              <button
                key={id}
                type="button"
                role="menuitem"
                className="continent-tile"
                aria-label={t(labelKey)}
                title={t(labelKey)}
                onClick={() => setContinent(id)}
              >
                <span className="continent-tile-svg" aria-hidden="true">
                  <svg
                    viewBox={CONTINENT_SVG[id].viewBox}
                    fill="currentColor"
                    stroke="none"
                  >
                    <path d={CONTINENT_SVG[id].d} />
                  </svg>
                </span>
                <span className="continent-tile-label">{t(labelKey)}</span>
                {langs.length === 0 && (
                  <span className="continent-tile-count" aria-hidden="true">·</span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {open && continent && (
        <div
          className="language-picker-popover language-picker-popover--languages"
          role="menu"
          aria-label={t(`continent_${continent}`)}
        >
          <button
            type="button"
            className="language-picker-back"
            onClick={() => setContinent(null)}
          >
            ← {t("continent_picker_back")}
          </button>
          <ul className="language-picker-list" role="none">
            {LANGUAGES_BY_CONTINENT[continent].map((code) => (
              <li key={code} role="none">
                <button
                  type="button"
                  role="menuitemradio"
                  aria-checked={code === activeCode}
                  className={
                    "language-picker-item" +
                    (code === activeCode ? " language-picker-item--active" : "")
                  }
                  onClick={() => handleSelect(code)}
                >
                  {LANGUAGE_NAMES[code] ?? code}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
