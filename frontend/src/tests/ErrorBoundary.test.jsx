/**
 * ErrorBoundary component tests.
 *
 * Covered:
 *  - Renders children when no error thrown
 *  - Catches a child render error and shows fallback UI
 *  - Reload button is present in fallback UI
 *  - componentDidCatch logs the error
 *  - Multiple children render normally when no error
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import ErrorBoundary from "../components/ErrorBoundary.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => {
      if (key === "error_boundary_title") return "Something went wrong";
      if (key === "error_boundary_hint")  return "Try reloading the page.";
      if (key === "error_boundary_btn")   return "Reload";
      return key;
    },
  }),
}));

function Bomb({ message = "kaboom" }) {
  throw new Error(message);
}

describe("ErrorBoundary", () => {
  let consoleErrSpy;

  beforeEach(() => {
    // React logs caught errors to console.error during render — silence to keep
    // test output clean while still spying for the componentDidCatch assertion.
    consoleErrSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrSpy.mockRestore();
  });

  it("renders children when no error is thrown", () => {
    render(
      <ErrorBoundary>
        <p>Healthy child</p>
      </ErrorBoundary>
    );
    expect(screen.getByText("Healthy child")).toBeInTheDocument();
  });

  it("renders multiple children unchanged when none throw", () => {
    render(
      <ErrorBoundary>
        <p>One</p>
        <p>Two</p>
      </ErrorBoundary>
    );
    expect(screen.getByText("One")).toBeInTheDocument();
    expect(screen.getByText("Two")).toBeInTheDocument();
  });

  it("shows the fallback title when a child throws", () => {
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("shows the fallback hint", () => {
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    );
    expect(screen.getByText("Try reloading the page.")).toBeInTheDocument();
  });

  it("renders the reload button in fallback UI", () => {
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    );
    expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();
  });

  it("logs the caught error via console.error", () => {
    render(
      <ErrorBoundary>
        <Bomb message="explicit failure" />
      </ErrorBoundary>
    );
    // ErrorBoundary's componentDidCatch produces a console.error tagged with the prefix
    const tagged = consoleErrSpy.mock.calls.find(
      (args) => typeof args[0] === "string" && args[0].includes("[ErrorBoundary]")
    );
    expect(tagged).toBeDefined();
  });

  it("hides the original child once the error is caught", () => {
    function HealthySibling() {
      return <p>Sibling content</p>;
    }
    render(
      <ErrorBoundary>
        <HealthySibling />
        <Bomb />
      </ErrorBoundary>
    );
    expect(screen.queryByText("Sibling content")).toBeNull();
  });
});
