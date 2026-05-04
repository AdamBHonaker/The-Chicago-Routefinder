/**
 * SignalLamp component tests.
 *
 * Covered:
 *  - Renders the lamp dot
 *  - Optional label rendered when provided
 *  - aria-label attached only when ariaLabel prop given (a11y semantics)
 *  - role="img" attached only when ariaLabel given; absent otherwise
 *  - className prop appends to the row class
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SignalLamp from "../components/SignalLamp.jsx";

describe("SignalLamp", () => {
  it("renders the lamp dot element", () => {
    const { container } = render(<SignalLamp />);
    expect(container.querySelector(".signal-lamp")).toBeInTheDocument();
  });

  it("renders a label when one is given", () => {
    render(<SignalLamp label="On time" />);
    expect(screen.getByText("On time")).toBeInTheDocument();
  });

  it("omits the label element when no label prop is provided", () => {
    const { container } = render(<SignalLamp />);
    expect(container.querySelector(".signal-lamp__label")).toBeNull();
  });

  it("attaches aria-label and role='img' when ariaLabel given", () => {
    render(<SignalLamp ariaLabel="Service running normally" />);
    const lamp = screen.getByLabelText("Service running normally");
    expect(lamp).toHaveAttribute("role", "img");
  });

  it("omits aria-label and role when ariaLabel is missing", () => {
    const { container } = render(<SignalLamp />);
    const lamp = container.querySelector(".signal-lamp");
    expect(lamp).not.toHaveAttribute("aria-label");
    expect(lamp).not.toHaveAttribute("role");
  });

  it("appends a custom className to the row container", () => {
    const { container } = render(<SignalLamp className="custom-cls" />);
    const row = container.querySelector(".signal-lamp-row");
    expect(row).toHaveClass("signal-lamp-row");
    expect(row).toHaveClass("custom-cls");
  });

  it("does not append an empty string when className is omitted", () => {
    const { container } = render(<SignalLamp />);
    const row = container.querySelector(".signal-lamp-row");
    // Trailing space would indicate the empty-string branch failed
    expect(row.className).toBe("signal-lamp-row");
  });
});
