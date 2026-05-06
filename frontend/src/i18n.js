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
// Locale-set rules (Feature LocaleExpansion):
//   - LANGUAGES is the canonical 76-entry list; missing translation files
//     fall back to English via i18next's `fallbackLng`. A row may exist in
//     LANGUAGES before its `public/locales/<code>/translation.json` lands.
//   - RESEARCH_LOCALES marks 8 low-resource codes that show the
//     machine-translated review badge below the language picker. The badge
//     copy is rendered via `t("mt_review_notice")` in the active locale and
//     MUST NOT appear in English fallback — when a research locale is missing
//     its translation file, that's a translate-missing.mjs gap to fill, not a
//     UX state to ship.
//   - LANGUAGES_BY_CONTINENT assigns each language to exactly one continent
//     for the continent-first picker. Identity is diaspora-aware (e.g.
//     `arz` Egyptian Arabic → Middle East rather than Africa, `mey`
//     Hassaniya Arabic → Africa, `en` → Americas as the primary Chicago
//     context). Antarctica is omitted; Oceania ships empty as a placeholder.
// ---------------------------------------------------------------------------
export const LANGUAGES = [
  // Originally shipped (22)
  { code: "en",  name: "English",          rtl: false },
  { code: "es",  name: "Español",          rtl: false },
  { code: "fr",  name: "Français",         rtl: false },
  { code: "it",  name: "Italiano",         rtl: false },
  { code: "pl",  name: "Polski",           rtl: false },
  { code: "ro",  name: "Română",           rtl: false },
  { code: "uk",  name: "Українська",       rtl: false },
  { code: "ru",  name: "Русский",          rtl: false },
  { code: "zh",  name: "中文（普通话）",    rtl: false },
  { code: "yue", name: "粤语",             rtl: false },
  { code: "ja",  name: "日本語",           rtl: false },
  { code: "ko",  name: "한국어",           rtl: false },
  { code: "tl",  name: "Filipino",         rtl: false },
  { code: "vi",  name: "Tiếng Việt",       rtl: false },
  { code: "hi",  name: "हिंदी",             rtl: false },
  { code: "gu",  name: "ગુજરાતી",          rtl: false },
  { code: "pa",  name: "ਪੰਜਾਬੀ",            rtl: false },
  { code: "ne",  name: "नेपाली",            rtl: false },
  { code: "ur",  name: "اردو",             rtl: true  },
  { code: "ar",  name: "العربية",          rtl: true  },
  { code: "ps",  name: "پښتو",             rtl: true  },
  { code: "yo",  name: "Yorùbá",           rtl: false },

  // LocaleExpansion — 54 new (translation files land per Chunks 2–12).
  { code: "ht",  name: "Kreyòl ayisyen",   rtl: false },
  { code: "my",  name: "မြန်မာ",            rtl: false },
  { code: "ksw", name: "ကညီ",              rtl: false },
  { code: "eky", name: "ꤊꤛꤢ꤬ꤜꤤ꤭",         rtl: false },
  { code: "am",  name: "አማርኛ",             rtl: false },
  { code: "ti",  name: "ትግርኛ",             rtl: false },
  { code: "prs", name: "دری",               rtl: true  },
  { code: "fa",  name: "فارسی",             rtl: true  },
  { code: "bs",  name: "Bosanski",         rtl: false },
  { code: "sr",  name: "Српски",           rtl: false },
  { code: "hr",  name: "Hrvatski",         rtl: false },
  { code: "lt",  name: "Lietuvių",         rtl: false },
  { code: "bn",  name: "বাংলা",            rtl: false },
  { code: "aii", name: "ܣܘܪܬ",              rtl: true  },
  { code: "el",  name: "Ελληνικά",         rtl: false },
  { code: "sw",  name: "Kiswahili",        rtl: false },
  { code: "th",  name: "ไทย",               rtl: false },
  { code: "sv",  name: "Svenska",          rtl: false },
  { code: "so",  name: "Soomaali",         rtl: false },
  { code: "he",  name: "עברית",             rtl: true  },
  { code: "tr",  name: "Türkçe",           rtl: false },
  { code: "arz", name: "مصرى",              rtl: true  },
  { code: "mr",  name: "मराठी",             rtl: false },
  { code: "te",  name: "తెలుగు",           rtl: false },
  { code: "ta",  name: "தமிழ்",             rtl: false },
  { code: "id",  name: "Bahasa Indonesia", rtl: false },
  { code: "de",  name: "Deutsch",          rtl: false },
  { code: "ha",  name: "Hausa",            rtl: false },
  { code: "pt",  name: "Português",        rtl: false },
  { code: "bho", name: "भोजपुरी",          rtl: false },
  { code: "kg",  name: "Kikongo",          rtl: false },
  { code: "lol", name: "Lomongo",          rtl: false },
  { code: "mey", name: "حسانية",            rtl: true  },
  { code: "af",  name: "Afrikaans",        rtl: false },
  { code: "xh",  name: "isiXhosa",         rtl: false },
  { code: "om",  name: "Afaan Oromoo",     rtl: false },
  { code: "nl",  name: "Nederlands",       rtl: false },
  { code: "mn",  name: "Монгол",           rtl: false },
  { code: "lo",  name: "ລາວ",               rtl: false },
  { code: "km",  name: "ខ្មែរ",              rtl: false },
  { code: "kn",  name: "ಕನ್ನಡ",             rtl: false },
  { code: "uz",  name: "Oʻzbekcha",        rtl: false },
  { code: "sd",  name: "سنڌي",              rtl: true  },
  { code: "ml",  name: "മലയാളം",           rtl: false },
  { code: "or",  name: "ଓଡ଼ିଆ",             rtl: false },
  { code: "mai", name: "मैथिली",           rtl: false },
  { code: "kmr", name: "Kurdî",            rtl: false },
  { code: "ckb", name: "کوردیی ناوەندی",   rtl: true  },
  { code: "ms",  name: "Bahasa Melayu",    rtl: false },
  { code: "ceb", name: "Cebuano",          rtl: false },
  { code: "nan", name: "閩南語",            rtl: false },
  { code: "kk",  name: "Қазақша",          rtl: false },
  { code: "si",  name: "සිංහල",            rtl: false },
  { code: "rhg", name: "𐴌𐴗𐴥𐴝𐴙𐴚",        rtl: true  },
];

export const SUPPORTED       = LANGUAGES.map((l) => l.code);
export const LANGUAGE_NAMES  = Object.fromEntries(LANGUAGES.map((l) => [l.code, l.name]));
export const RTL_LANGS       = new Set(LANGUAGES.filter((l) => l.rtl).map((l) => l.code));

// Low-resource locales whose translations are higher-uncertainty. The
// machine-translated review badge is rendered when one of these is active.
// Keep this set in sync with the "Low-resource flagged" list in
// docs/FEATURE_PLANS.md → Feature LocaleExpansion → Scoping decisions.
export const RESEARCH_LOCALES = new Set([
  "eky", "aii", "bho", "lol", "mey", "mai", "rhg", "ksw",
]);

// Continent assignment for the continent-first picker. Each language belongs
// to exactly one continent. Order within an array follows the Scoping
// decision 4 table in FEATURE_PLANS.md so the picker is reviewable against
// the spec at a glance.
export const LANGUAGES_BY_CONTINENT = {
  americas: ["en", "es", "ht", "pt"],
  europe:   ["fr", "it", "pl", "ro", "uk", "ru", "bs", "sr", "hr", "lt", "el", "sv", "de", "nl", "tr"],
  middle_east: ["ar", "ps", "he", "fa", "prs", "arz", "ckb", "kmr", "aii"],
  africa:   ["yo", "am", "ti", "sw", "so", "om", "ha", "xh", "af", "lol", "kg", "mey"],
  asia:     [
    "zh", "yue", "ja", "ko", "tl", "vi",
    "hi", "gu", "pa", "ne", "ur", "bn", "mr", "ta", "te", "ml", "kn", "or", "mai", "bho", "si", "sd",
    "th", "lo", "km", "my", "ksw", "eky",
    "id", "ms", "ceb", "nan",
    "mn", "kk", "uz", "rhg",
  ],
  oceania:  [],
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
