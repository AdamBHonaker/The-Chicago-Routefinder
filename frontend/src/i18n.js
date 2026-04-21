import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import HttpBackend from "i18next-http-backend";
import LanguageDetector from "i18next-browser-languagedetector";

const SUPPORTED = [
  "en","es","fr","it","pl","ro","uk","ru",
  "zh","yue","ja","ko","tl","vi","hi","gu",
  "pa","ne","ur","ar","ps","yo",
];

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
    interpolation: { escapeValue: false },
  });

export default i18n;
export { SUPPORTED };
