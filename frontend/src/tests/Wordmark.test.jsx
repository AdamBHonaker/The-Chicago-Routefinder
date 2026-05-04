/**
 * Wordmark component tests.
 *
 * Covered:
 *  - Renders the brand text "The Chicago Routefinder"
 *  - Translated aria-label attached
 *  - size="md" (default) → base masthead class only
 *  - size="lg" → adds the lg modifier class
 *  - Renders the period sigil
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Wordmark from "../components/Wordmark.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => key === "app_title" ? "The Chicago Routefinder" : key,
  }),
}));

describe("Wordmark", () => {
  it("renders both halves of the editorial lockup", () => {
    render(<Wordmark />);
    expect(screen.getByText("The Chicago")).toBeInTheDocument();
    expect(screen.getByText(/Routefinder/)).toBeInTheDocument();
  });

  it("attaches translated aria-label on the heading", () => {
    render(<Wordmark />);
    expect(screen.getByLabelText("The Chicago Routefinder")).toBeInTheDocument();
  });

  it("uses the base masthead class at default size 'md'", () => {
    const { container } = render(<Wordmark />);
    const heading = container.querySelector("h1");
    expect(heading).toHaveClass("masthead-title");
    expect(heading).not.toHaveClass("masthead-title--lg");
  });

  it("adds the lg modifier when size='lg'", () => {
    const { container } = render(<Wordmark size="lg" />);
    const heading = container.querySelector("h1");
    expect(heading).toHaveClass("masthead-title");
    expect(heading).toHaveClass("masthead-title--lg");
  });

  it("renders the rust period sigil", () => {
    const { container } = render(<Wordmark />);
    expect(container.querySelector(".masthead-period")).toBeInTheDocument();
  });
});
