import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import HttpBackend from "i18next-http-backend";
import LanguageDetector from "i18next-browser-languagedetector";

// ---------------------------------------------------------------------------
// Single source of truth for supported languages.
//   - code: BCP-47 language tag (matches the `frontend/public/locales/{code}/`
//           translation file directory)
//   - name: native-script display name shown in the language selector
//   - rtl:  document direction is flipped to "rtl" when this language is active
// Adding a language: drop a translation.json under public/locales/<code>/ and
// append a row here.
//
// Locale-set rules (retrenched 2026-05-11 from 76 → 27):
//   - LANGUAGES is the canonical 27-entry list, focused on languages with
//     meaningful Chicago rider populations. Translation files for removed
//     locales are preserved under frontend/locales-archive/ (outside the
//     Vite public/ root so they do not ship to production). To re-enable a
//     locale: move its folder back into public/locales/ and append a row
//     to LANGUAGES below.
//   - RESEARCH_LOCALES marks 3 low-resource codes that show the
//     machine-translated review badge below the language picker. The badge
//     copy is rendered via `t("mt_review_notice")` in the active locale and
//     MUST NOT appear in English fallback — when a research locale is missing
//     its translation file, that's a translate-missing.mjs gap to fill, not a
//     UX state to ship.
//   - LANGUAGES_BY_CONTINENT assigns each language to one or more continents
//     for the continent-first picker. Identity is diaspora-aware (e.g.
//     `prs` Dari → Middle East, `aii` Assyrian → Middle East,
//     `en` → Americas as the primary Chicago context). Languages spoken
//     across multiple continents (e.g. `es`, `pt`) appear in each.
//     Antarctica is omitted; Oceania is currently empty and is filtered out
//     of the picker (see LanguagePicker.jsx). Add a language entry here to
//     make the Oceania tile appear.
// ---------------------------------------------------------------------------
export const LANGUAGES = [
  // Originally shipped
  { code: "en",  name: "English",          rtl: false },
  { code: "es",  name: "Español",          rtl: false },
  { code: "fr",  name: "Français",         rtl: false },
  { code: "pl",  name: "Polski",           rtl: false },
  { code: "ro",  name: "Română",           rtl: false },
  { code: "uk",  name: "Українська",       rtl: false },
  { code: "ru",  name: "Русский",          rtl: false },
  { code: "zh",  name: "中文（普通话）",    rtl: false },
  { code: "yue", name: "粤语",             rtl: false },
  { code: "ko",  name: "한국어",           rtl: false },
  { code: "tl",  name: "Filipino",         rtl: false },
  { code: "vi",  name: "Tiếng Việt",       rtl: false },
  { code: "hi",  name: "हिंदी",             rtl: false },
  { code: "gu",  name: "ગુજરાતી",          rtl: false },
  { code: "ne",  name: "नेपाली",            rtl: false },
  { code: "ur",  name: "اردو",             rtl: true  },
  { code: "ar",  name: "العربية",          rtl: true  },
  { code: "ps",  name: "پښتو",             rtl: true  },
  { code: "yo",  name: "Yorùbá",           rtl: false },

  // Chicago-focused additions
  { code: "ht",  name: "Kreyòl ayisyen",   rtl: false },
  { code: "ksw", name: "ကညီ",              rtl: false },
  { code: "am",  name: "አማርኛ",             rtl: false },
  { code: "prs", name: "دری",               rtl: true  },
  { code: "bs",  name: "Bosanski",         rtl: false },
  { code: "aii", name: "ܣܘܪܬ",              rtl: true  },
  { code: "pt",  name: "Português",        rtl: false },
  { code: "rhg", name: "𐴌𐴗𐴥𐴝𐴙𐴚",        rtl: true  },
];

export const SUPPORTED       = LANGUAGES.map((l) => l.code);
export const LANGUAGE_NAMES  = Object.fromEntries(LANGUAGES.map((l) => [l.code, l.name]));
export const RTL_LANGS       = new Set(LANGUAGES.filter((l) => l.rtl).map((l) => l.code));

// Low-resource locales whose translations are higher-uncertainty. The
// machine-translated review badge is rendered when one of these is active.
export const RESEARCH_LOCALES = new Set([
  "aii", "ksw", "rhg",
]);

// Continent assignment for the continent-first picker. Each language belongs
// to exactly one continent. Order within an array follows Chicago demographic
// significance within that continent.
export const LANGUAGES_BY_CONTINENT = {
  americas:    ["en", "es", "ht", "pt"],
  europe:      ["es", "pt", "fr", "pl", "ro", "uk", "bs"],
  middle_east: ["ar", "ps", "prs", "aii"],
  africa:      ["yo", "am"],
  asia:        ["ru", "zh", "yue", "ko", "tl", "vi", "hi", "gu", "ne", "ur", "ksw", "rhg"],
  oceania:     [],
};

export const CONTINENT_IDS = ["africa", "americas", "asia", "europe", "middle_east", "oceania"];

i18n
  .use(HttpBackend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: "en",
    supportedLngs: SUPPORTED,
    backend: { loadPath: "/locales/{{lng}}/translation.json" },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "cta_language",
    },
    // escapeValue: false is safe ONLY because translation strings come from
    // static .json files committed to this repo (loaded via the http-backend
    // from /locales) — the values are trusted, not user-controlled. If you
    // ever switch to a remote/dynamic translation source, re-enable escaping
    // (or sanitize on the way in) to prevent stored XSS.
    interpolation: { escapeValue: false },
  });

export default i18n;
