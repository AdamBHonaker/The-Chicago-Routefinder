/**
 * AddressAutocomplete component tests.
 *
 * Covers: ARIA combobox wiring, debounce, abort-on-keystroke, keyboard nav,
 * pointer selection, type-badge rendering, and the host onOpen/onClose
 * callbacks LocationInput depends on.
 *
 * Uses `positioning="absolute"` to keep the listbox inside the wrapper so
 * @testing-library can query it via `within(wrapper)` instead of through
 * the portal.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AddressAutocomplete from "../components/AddressAutocomplete.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key, opts) => (opts?.count ? `${key}:${opts.count}` : key),
  }),
}));

// Most tests need a controlled input that actually reflects user typing.
// AddressAutocomplete is a controlled component, so without an enclosing
// state holder its `value` prop never changes and the dropdown never opens.
function Harness({ initial = "", onChange: onChangeProp, ...rest }) {
  const [value, setValue] = useState(initial);
  function handleChange(next) {
    setValue(next);
    onChangeProp?.(next);
  }
  return (
    <AddressAutocomplete
      {...rest}
      value={value}
      onChange={handleChange}
      positioning="absolute"
      debounceMs={10}
    />
  );
}

describe("AddressAutocomplete", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders an input with ARIA combobox attributes", () => {
    render(<Harness getSuggestions={vi.fn()} ariaLabel="Where to?" />);
    const input = screen.getByRole("combobox");
    expect(input).toHaveAttribute("aria-autocomplete", "list");
    expect(input).toHaveAttribute("aria-expanded", "false");
    expect(input).toHaveAttribute("aria-controls");
  });

  it("calls onChange when the user types", () => {
    const onChange = vi.fn();
    render(<Harness getSuggestions={vi.fn()} onChange={onChange} />);
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "Howard" },
    });
    expect(onChange).toHaveBeenCalledWith("Howard");
  });

  it("does not call getSuggestions for single-character queries", async () => {
    const getSuggestions = vi.fn().mockResolvedValue([]);
    render(<Harness getSuggestions={getSuggestions} />);
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "h" },
    });
    await new Promise((r) => setTimeout(r, 60));
    expect(getSuggestions).not.toHaveBeenCalled();
  });

  it("fetches suggestions for ≥2 chars after debounce", async () => {
    const getSuggestions = vi.fn().mockResolvedValue([
      { label: "Howard", value: "Howard", type: "train" },
    ]);
    render(<Harness getSuggestions={getSuggestions} />);
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "ho" },
    });
    await waitFor(() => expect(getSuggestions).toHaveBeenCalled(), {
      timeout: 500,
    });
    expect(getSuggestions.mock.calls[0][0]).toBe("ho");
  });

  it("renders address-type and intersection-type suggestions with badges", async () => {
    const getSuggestions = vi.fn().mockResolvedValue([
      { label: "1060 W Addison St", value: "1060 W Addison St", type: "address" },
      {
        label: "N Clark St & W Belmont Ave",
        value: "N Clark St & W Belmont Ave",
        type: "intersection",
      },
    ]);
    render(<Harness getSuggestions={getSuggestions} />);
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "1060" },
    });
    const addressItem = await screen.findByRole(
      "option",
      { name: /1060 W Addison St/ },
      { timeout: 500 },
    );
    expect(addressItem.textContent).toContain("ac_type_address");
    const intersectionItem = screen.getByRole("option", {
      name: /Clark St & W Belmont Ave/,
    });
    expect(intersectionItem.textContent).toContain("ac_type_intersection");
  });

  it("commits selection on mousedown (preempts blur)", async () => {
    const getSuggestions = vi.fn().mockResolvedValue([
      { label: "Howard", value: "Howard", type: "train" },
    ]);
    const onChange = vi.fn();
    const onSelect = vi.fn();
    render(
      <Harness
        getSuggestions={getSuggestions}
        onChange={onChange}
        onSelect={onSelect}
      />,
    );
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "ho" },
    });
    const item = await screen.findByRole(
      "option",
      { name: /Howard/ },
      { timeout: 500 },
    );
    fireEvent.mouseDown(item);
    expect(onChange).toHaveBeenCalledWith("Howard");
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ label: "Howard", type: "train" }),
    );
  });

  it("commits highlighted suggestion on Enter", async () => {
    const getSuggestions = vi.fn().mockResolvedValue([
      { label: "Howard", value: "Howard", type: "train" },
      { label: "Hollywood", value: "Hollywood", type: "train" },
    ]);
    const onChange = vi.fn();
    render(<Harness getSuggestions={getSuggestions} onChange={onChange} />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "ho" } });
    await screen.findByRole("option", { name: /Howard/ }, { timeout: 500 });
    // ArrowDown twice → Hollywood highlighted (active was -1, +1, +1 → 1)
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenLastCalledWith("Hollywood");
  });

  it("Escape closes the listbox", async () => {
    const getSuggestions = vi.fn().mockResolvedValue([
      { label: "Howard", value: "Howard", type: "train" },
    ]);
    render(<Harness getSuggestions={getSuggestions} />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "ho" } });
    await screen.findByRole("option", { name: /Howard/ }, { timeout: 500 });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(input).toHaveAttribute("aria-expanded", "false");
  });

  it("calls onOpen when the listbox renders with results", async () => {
    const onOpen = vi.fn();
    const getSuggestions = vi.fn().mockResolvedValue([
      { label: "Howard", value: "Howard", type: "train" },
    ]);
    render(<Harness getSuggestions={getSuggestions} onOpen={onOpen} />);
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "ho" },
    });
    await waitFor(() => expect(onOpen).toHaveBeenCalled(), { timeout: 500 });
  });

  it("aborts an in-flight fetch when a fresh keystroke arrives", async () => {
    let firstAbortListener;
    const getSuggestions = vi.fn().mockImplementation((q, { signal }) => {
      if (q === "ho") {
        firstAbortListener = vi.fn();
        signal.addEventListener("abort", firstAbortListener);
        return new Promise(() => {}); // never resolves
      }
      return Promise.resolve([]);
    });
    render(<Harness getSuggestions={getSuggestions} />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "ho" } });
    await waitFor(
      () => expect(getSuggestions).toHaveBeenCalledTimes(1),
      { timeout: 500 },
    );
    fireEvent.change(input, { target: { value: "how" } });
    await waitFor(() => expect(firstAbortListener).toHaveBeenCalled(), {
      timeout: 500,
    });
  });

  it("renders the inputAdornment slot", () => {
    render(
      <Harness
        getSuggestions={vi.fn()}
        inputAdornment={<span data-testid="star">★</span>}
      />,
    );
    expect(screen.getByTestId("star")).toBeInTheDocument();
  });
});
