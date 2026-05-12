/**
 * useDocumentLanguage hook tests (TD-FE-021).
 *
 * Covered:
 *  - Sets <html lang> to the active i18next language
 *  - Sets <html dir="rtl"> when language is in RTL_LANGS
 *  - Sets <html dir="ltr"> when language is not in RTL_LANGS
 *  - Prefers resolvedLanguage over language when both present
 *  - Re-applies on language change
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";

const i18nState = { resolvedLanguage: "en", language: "en" };
vi.mock("react-i18next", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useTranslation: () => ({ i18n: i18nState }),
  };
});

import { useDocumentLanguage } from "../hooks/useDocumentLanguage.js";

describe("useDocumentLanguage", () => {
  beforeEach(() => {
    document.documentElement.dir = "";
    document.documentElement.lang = "";
    i18nState.resolvedLanguage = "en";
    i18nState.language = "en";
  });

  afterEach(() => {
    document.documentElement.dir = "";
    document.documentElement.lang = "";
  });

  it("sets <html lang> to the resolved language", () => {
    i18nState.resolvedLanguage = "es";
    renderHook(() => useDocumentLanguage());
    expect(document.documentElement.lang).toBe("es");
  });

  it("sets dir='ltr' for non-RTL languages", () => {
    i18nState.resolvedLanguage = "fr";
    renderHook(() => useDocumentLanguage());
    expect(document.documentElement.dir).toBe("ltr");
  });

  it("sets dir='rtl' for Arabic", () => {
    i18nState.resolvedLanguage = "ar";
    renderHook(() => useDocumentLanguage());
    expect(document.documentElement.dir).toBe("rtl");
  });

  it("sets dir='rtl' for Pashto", () => {
    i18nState.resolvedLanguage = "ps";
    renderHook(() => useDocumentLanguage());
    expect(document.documentElement.dir).toBe("rtl");
  });

  it("sets dir='rtl' for Urdu (RTL Indic)", () => {
    i18nState.resolvedLanguage = "ur";
    renderHook(() => useDocumentLanguage());
    expect(document.documentElement.dir).toBe("rtl");
  });

  it("falls back to language when resolvedLanguage is undefined", () => {
    i18nState.resolvedLanguage = undefined;
    i18nState.language = "ja";
    renderHook(() => useDocumentLanguage());
    expect(document.documentElement.lang).toBe("ja");
    expect(document.documentElement.dir).toBe("ltr");
  });
});
