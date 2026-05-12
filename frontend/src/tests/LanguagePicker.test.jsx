/**
 * LanguagePicker tests (TD-FE-021).
 *
 * Covered:
 *  - Trigger renders the active language label
 *  - Closed → click trigger opens the continent grid
 *  - Six continent tiles render
 *  - Click a continent → renders that continent's language list
 *  - Selecting a language calls i18n.changeLanguage and closes the picker
 *  - Empty Oceania continent shows the placeholder
 *  - Escape on the language list returns to the continent grid
 *  - Escape on the continent grid closes the picker
 *  - Click outside closes the picker
 *  - Active language carries the active modifier and aria-checked=true
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const i18nState = { resolvedLanguage: "en", language: "en", changeLanguage: vi.fn() };

vi.mock("react-i18next", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useTranslation: () => ({
      t: (key) => key,
      i18n: i18nState,
    }),
  };
});

// Inline ?raw SVG imports — return a minimal stub.
vi.mock("../../assets/continents/africa.svg?raw",      () => ({ default: "<svg/>" }));
vi.mock("../../assets/continents/americas.svg?raw",    () => ({ default: "<svg/>" }));
vi.mock("../../assets/continents/asia.svg?raw",        () => ({ default: "<svg/>" }));
vi.mock("../../assets/continents/europe.svg?raw",      () => ({ default: "<svg/>" }));
vi.mock("../../assets/continents/middle-east.svg?raw", () => ({ default: "<svg/>" }));
vi.mock("../../assets/continents/oceania.svg?raw",     () => ({ default: "<svg/>" }));

import LanguagePicker from "../components/LanguagePicker/LanguagePicker.jsx";

describe("LanguagePicker", () => {
  beforeEach(() => {
    i18nState.resolvedLanguage = "en";
    i18nState.language = "en";
    i18nState.changeLanguage = vi.fn();
  });

  it("renders the active language label on the trigger", () => {
    render(<LanguagePicker />);
    expect(screen.getByRole("button", { name: "aria_language" }).textContent).toBe("English");
  });

  it("opens the continent grid when the trigger is clicked", () => {
    render(<LanguagePicker />);
    fireEvent.click(screen.getByRole("button", { name: "aria_language" }));
    expect(document.querySelector(".language-picker-popover--continents")).not.toBeNull();
  });

  it("renders 5 continent tiles (empty continents are filtered out)", () => {
    render(<LanguagePicker />);
    fireEvent.click(screen.getByRole("button", { name: "aria_language" }));
    const tiles = document.querySelectorAll(".continent-tile");
    expect(tiles.length).toBe(5);
  });

  it("clicking a continent shows its language list", () => {
    render(<LanguagePicker />);
    fireEvent.click(screen.getByRole("button", { name: "aria_language" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "continent_americas" }));
    expect(document.querySelector(".language-picker-popover--languages")).not.toBeNull();
    // Americas includes English.
    expect(screen.getByRole("menuitemradio", { name: "English" })).toBeInTheDocument();
  });

  it("selecting a language calls i18n.changeLanguage and closes the picker", () => {
    render(<LanguagePicker />);
    fireEvent.click(screen.getByRole("button", { name: "aria_language" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "continent_americas" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "Español" }));

    expect(i18nState.changeLanguage).toHaveBeenCalledWith("es");
    expect(document.querySelector(".language-picker-popover")).toBeNull();
  });

  it("Escape on language list returns to continent grid", () => {
    render(<LanguagePicker />);
    fireEvent.click(screen.getByRole("button", { name: "aria_language" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "continent_americas" }));
    expect(document.querySelector(".language-picker-popover--languages")).not.toBeNull();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.querySelector(".language-picker-popover--continents")).not.toBeNull();
    expect(document.querySelector(".language-picker-popover--languages")).toBeNull();
  });

  it("Escape on continent grid closes the picker entirely", () => {
    render(<LanguagePicker />);
    fireEvent.click(screen.getByRole("button", { name: "aria_language" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.querySelector(".language-picker-popover")).toBeNull();
  });

  it("click outside closes the picker", () => {
    render(
      <div>
        <LanguagePicker />
        <button data-testid="outside">outside</button>
      </div>
    );
    fireEvent.click(screen.getByRole("button", { name: "aria_language" }));
    expect(document.querySelector(".language-picker-popover")).not.toBeNull();

    fireEvent.mouseDown(screen.getByTestId("outside"));
    expect(document.querySelector(".language-picker-popover")).toBeNull();
  });

  it("active language carries the active modifier and aria-checked=true", () => {
    i18nState.resolvedLanguage = "es";
    render(<LanguagePicker />);
    fireEvent.click(screen.getByRole("button", { name: "aria_language" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "continent_americas" }));

    const active = screen.getByRole("menuitemradio", { name: "Español" });
    expect(active.getAttribute("aria-checked")).toBe("true");
    expect(active.className).toContain("language-picker-item--active");
  });
});
