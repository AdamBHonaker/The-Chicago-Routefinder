/**
 * SharedRouteBanner component tests.
 *
 * Covered:
 *  - Banner text rendered
 *  - role="status" so screen readers announce it
 *  - Dismiss button present with translated aria-label
 *  - Click on dismiss invokes onDismiss callback
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SharedRouteBanner from "../components/SharedRouteBanner.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => {
      if (key === "shared_banner_text") return "Shared route loaded";
      if (key === "aria_dismiss")       return "Dismiss";
      return key;
    },
  }),
}));

describe("SharedRouteBanner", () => {
  it("renders the banner text", () => {
    render(<SharedRouteBanner onDismiss={() => {}} />);
    expect(screen.getByText("Shared route loaded")).toBeInTheDocument();
  });

  it("uses role='status' so it is announced by screen readers", () => {
    render(<SharedRouteBanner onDismiss={() => {}} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders the dismiss button with translated aria-label", () => {
    render(<SharedRouteBanner onDismiss={() => {}} />);
    expect(screen.getByRole("button", { name: "Dismiss" })).toBeInTheDocument();
  });

  it("invokes onDismiss when the button is clicked", () => {
    const onDismiss = vi.fn();
    render(<SharedRouteBanner onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
