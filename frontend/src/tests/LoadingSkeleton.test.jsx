/**
 * LoadingSkeleton component tests.
 *
 * Covered:
 *  - Wrapper has aria-busy="true" for assistive tech
 *  - Translated aria-label is attached for screen readers
 *  - Plotting message text rendered
 *  - Three ghost lines rendered for the placeholder visual
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import LoadingSkeleton from "../components/LoadingSkeleton.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => {
      if (key === "aria_loading")     return "Loading routes";
      if (key === "loading_plotting") return "Plotting your trip";
      return key;
    },
  }),
}));

describe("LoadingSkeleton", () => {
  it("sets aria-busy on the wrapper", () => {
    const { container } = render(<LoadingSkeleton />);
    expect(container.firstChild).toHaveAttribute("aria-busy", "true");
  });

  it("attaches translated aria-label", () => {
    const { container } = render(<LoadingSkeleton />);
    expect(container.firstChild).toHaveAttribute("aria-label", "Loading routes");
  });

  it("renders the plotting message", () => {
    render(<LoadingSkeleton />);
    expect(screen.getByText("Plotting your trip")).toBeInTheDocument();
  });

  it("renders three ghost-line placeholders", () => {
    const { container } = render(<LoadingSkeleton />);
    expect(container.querySelectorAll(".skeleton-ghost-line")).toHaveLength(3);
  });
});
