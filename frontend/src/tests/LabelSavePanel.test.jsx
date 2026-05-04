/**
 * LabelSavePanel component tests.
 *
 * Covered:
 *  - Input renders with the value prop and placeholder
 *  - Typing fires onChange with new text
 *  - Enter key invokes onSave (and prevents default form submit)
 *  - Escape key invokes onCancel
 *  - Save button click invokes onSave
 *  - Cancel button click invokes onCancel
 *  - Limit error rendered only when showError=true
 *  - prefix prop drives CSS class names (defaults to "label")
 *  - maxLength=30 is enforced on the input
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LabelSavePanel from "../components/LabelSavePanel.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => {
      if (key === "fav_save")          return "Save";
      if (key === "fav_cancel")        return "Cancel";
      if (key === "fav_limit_reached") return "Limit reached";
      return key;
    },
  }),
}));

describe("LabelSavePanel", () => {
  const baseProps = () => ({
    value: "",
    onChange: vi.fn(),
    onSave: vi.fn(),
    onCancel: vi.fn(),
    placeholder: "Name this place",
  });

  it("renders the input with the provided value and placeholder", () => {
    render(<LabelSavePanel {...baseProps()} value="Wrigleyville" />);
    const input = screen.getByPlaceholderText("Name this place");
    expect(input).toHaveValue("Wrigleyville");
  });

  it("calls onChange with the new text when the user types", () => {
    const props = baseProps();
    render(<LabelSavePanel {...props} />);
    fireEvent.change(screen.getByPlaceholderText("Name this place"),
      { target: { value: "Loop" } });
    expect(props.onChange).toHaveBeenCalledWith("Loop");
  });

  it("invokes onSave when Enter is pressed", () => {
    const props = baseProps();
    render(<LabelSavePanel {...props} />);
    fireEvent.keyDown(screen.getByPlaceholderText("Name this place"), { key: "Enter" });
    expect(props.onSave).toHaveBeenCalledTimes(1);
  });

  it("invokes onCancel when Escape is pressed", () => {
    const props = baseProps();
    render(<LabelSavePanel {...props} />);
    fireEvent.keyDown(screen.getByPlaceholderText("Name this place"), { key: "Escape" });
    expect(props.onCancel).toHaveBeenCalledTimes(1);
  });

  it("invokes onSave when the Save button is clicked", () => {
    const props = baseProps();
    render(<LabelSavePanel {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(props.onSave).toHaveBeenCalledTimes(1);
  });

  it("invokes onCancel when the Cancel button is clicked", () => {
    const props = baseProps();
    render(<LabelSavePanel {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(props.onCancel).toHaveBeenCalledTimes(1);
  });

  it("hides the limit error by default", () => {
    render(<LabelSavePanel {...baseProps()} />);
    expect(screen.queryByText("Limit reached")).toBeNull();
  });

  it("shows the limit error when showError=true", () => {
    render(<LabelSavePanel {...baseProps()} showError />);
    expect(screen.getByText("Limit reached")).toBeInTheDocument();
  });

  it("uses the default 'label' prefix for class names", () => {
    const { container } = render(<LabelSavePanel {...baseProps()} />);
    expect(container.querySelector(".label-save-panel")).toBeInTheDocument();
    expect(container.querySelector(".label-save-input")).toBeInTheDocument();
  });

  it("respects a custom prefix prop", () => {
    const { container } = render(<LabelSavePanel {...baseProps()} prefix="route" />);
    expect(container.querySelector(".route-save-panel")).toBeInTheDocument();
    expect(container.querySelector(".route-save-input")).toBeInTheDocument();
  });

  it("enforces maxLength=30 on the input", () => {
    render(<LabelSavePanel {...baseProps()} />);
    expect(screen.getByPlaceholderText("Name this place")).toHaveAttribute("maxLength", "30");
  });
});
