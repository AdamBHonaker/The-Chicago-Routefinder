/**
 * TwoToneHeading component tests.
 *
 * Covered:
 *  - Italicizes the first word by default
 *  - italicWords=N italicizes the first N words
 *  - Single-token (CJK) headlines italicize the whole thing
 *  - capsKey omitted → no caps kicker
 *  - capsKey present → translated kicker rendered
 *  - ruleAfter=true → divider rule rendered (default)
 *  - ruleAfter=false → no divider rule
 *  - Optional id forwarded to the h2
 *  - Custom className appended to root
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import TwoToneHeading from "../components/TwoToneHeading.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => {
      // Test fixtures keyed off the prop value
      if (key === "h_two")    return "Two words";
      if (key === "h_four")   return "One Two Three Four";
      if (key === "h_single") return "Solo";
      if (key === "caps_x")   return "SECTION";
      return key;
    },
  }),
}));

describe("TwoToneHeading", () => {
  it("italicizes the first word and renders the rest in roman", () => {
    const { container } = render(<TwoToneHeading headingKey="h_two" />);
    expect(container.querySelector(".headline__italic").textContent).toBe("Two");
    // Rest of the headline is rendered as plain text alongside the italic span
    expect(container.querySelector(".headline").textContent).toBe("Two words");
  });

  it("italicizes the first N words when italicWords=N", () => {
    const { container } = render(<TwoToneHeading headingKey="h_four" italicWords={2} />);
    expect(container.querySelector(".headline__italic").textContent).toBe("One Two");
    expect(container.querySelector(".headline").textContent).toBe("One Two Three Four");
  });

  it("italicizes the whole heading for single-token (CJK) input", () => {
    const { container } = render(<TwoToneHeading headingKey="h_single" />);
    expect(container.querySelector(".headline__italic").textContent).toBe("Solo");
    // No rest token → headline contains only the italic span
    expect(container.querySelector(".headline").textContent).toBe("Solo");
  });

  it("omits the caps kicker when capsKey is not provided", () => {
    const { container } = render(<TwoToneHeading headingKey="h_two" />);
    expect(container.querySelector(".caps")).toBeNull();
  });

  it("renders the translated caps kicker when capsKey provided", () => {
    render(<TwoToneHeading capsKey="caps_x" headingKey="h_two" />);
    expect(screen.getByText("SECTION")).toBeInTheDocument();
  });

  it("renders the divider rule by default (ruleAfter=true)", () => {
    const { container } = render(<TwoToneHeading headingKey="h_two" />);
    expect(container.querySelector(".rule-thick")).toBeInTheDocument();
  });

  it("omits the divider rule when ruleAfter=false", () => {
    const { container } = render(<TwoToneHeading headingKey="h_two" ruleAfter={false} />);
    expect(container.querySelector(".rule-thick")).toBeNull();
  });

  it("forwards id prop to the h2", () => {
    const { container } = render(<TwoToneHeading headingKey="h_two" id="hero-h" />);
    expect(container.querySelector("h2").id).toBe("hero-h");
  });

  it("appends custom className to the root container", () => {
    const { container } = render(<TwoToneHeading headingKey="h_two" className="hero" />);
    expect(container.firstChild).toHaveClass("two-tone-heading");
    expect(container.firstChild).toHaveClass("hero");
  });
});
