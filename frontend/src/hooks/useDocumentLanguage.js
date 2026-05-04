import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { RTL_LANGS } from "../i18n.js";

// Mirrors the active i18next language onto <html lang> and flips <html dir>
// to "rtl" when the language is in RTL_LANGS. Extracted from App.jsx
// (TD-FE-006). Pure side-effect hook — returns nothing.
export function useDocumentLanguage() {
  const { i18n } = useTranslation();
  useEffect(() => {
    const lang = i18n.resolvedLanguage ?? i18n.language;
    document.documentElement.dir = RTL_LANGS.has(lang) ? "rtl" : "ltr";
    document.documentElement.lang = lang;
  }, [i18n.resolvedLanguage, i18n.language]);
}
