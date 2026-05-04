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
// ---------------------------------------------------------------------------
export const LANGUAGES = [
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
];

export const SUPPORTED       = LANGUAGES.map((l) => l.code);
export const LANGUAGE_NAMES  = Object.fromEntries(LANGUAGES.map((l) => [l.code, l.name]));
export const RTL_LANGS       = new Set(LANGUAGES.filter((l) => l.rtl).map((l) => l.code));

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
