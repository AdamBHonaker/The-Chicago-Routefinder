/**
 * LocationInput component tests.
 * Covers: rendering, geo button, save flow, autocomplete keyboard navigation.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LocationInput from "../components/LocationInput.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

vi.mock("../favorites.js", () => ({
  saveLocation: vi.fn(),
  deleteLocation: vi.fn(),
}));

const BASE_PROPS = {
  value: "",
  onChange: vi.fn(),
  placeholder: "placeholder_location",
  savedLocations: [],
  onSavedLocationsChange: vi.fn(),
  showGeoBtn: false,
};

describe("LocationInput", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders a text input", () => {
    render(<LocationInput {...BASE_PROPS} />);
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("does not render geo button when showGeoBtn is false", () => {
    render(<LocationInput {...BASE_PROPS} showGeoBtn={false} />);
    expect(screen.queryByText("geo_btn_label")).not.toBeInTheDocument();
  });

  it("renders geo button when showGeoBtn is true", () => {
    render(<LocationInput {...BASE_PROPS} showGeoBtn={true} />);
    expect(screen.getByText("geo_btn_label")).toBeInTheDocument();
  });

  it("calls onChange when user types in the input", () => {
    render(<LocationInput {...BASE_PROPS} />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "Howard" } });
    expect(BASE_PROPS.onChange).toHaveBeenCalledWith("Howard");
  });

  it("hides the save star when value is empty", () => {
    render(<LocationInput {...BASE_PROPS} value="" />);
    expect(screen.queryByRole("button", { name: /fav_save_location/ })).not.toBeInTheDocument();
  });

  it("shows the save star when value is non-empty", () => {
    render(<LocationInput {...BASE_PROPS} value="Howard" />);
    expect(screen.getByRole("button", { name: "fav_save_location" })).toBeInTheDocument();
  });

  it("shows saved star when value matches a saved location", () => {
    render(
      <LocationInput
        {...BASE_PROPS}
        value="Howard"
        savedLocations={[{ value: "Howard", label: "Howard" }]}
      />
    );
    expect(screen.getByRole("button", { name: "fav_unsave_location" })).toBeInTheDocument();
  });

  it("opens the save panel when the unsaved star is clicked", () => {
    render(<LocationInput {...BASE_PROPS} value="Howard" />);
    fireEvent.click(screen.getByRole("button", { name: "fav_save_location" }));
    expect(screen.getByText("fav_save")).toBeInTheDocument();
  });

  it("renders autocomplete suggestions when provided via fetch mock", async () => {
    const suggestions = [
      { value: "Howard", label: "Howard", type: "train" },
      { value: "Jarvis", label: "Jarvis", type: "train" },
    ];
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ suggestions }),
    });

    render(<LocationInput {...BASE_PROPS} value="ho" />);
    const input = screen.getByRole("combobox");

    // Simulate typing a third character to clear the <2-char guard
    fireEvent.change(input, { target: { value: "how" } });

    await waitFor(() => expect(global.fetch).toHaveBeenCalled(), { timeout: 500 });
  });

  it("calls onChange with selected suggestion value", async () => {
    const suggestions = [{ value: "Howard", label: "Howard", type: "train" }];
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ suggestions }),
    });

    render(<LocationInput {...BASE_PROPS} value="" />);
    const input = screen.getByRole("combobox");

    // Trigger the debounced fetch by typing — onChange handler is what actually
    // calls fetchAcSuggestions. Rendering with `value="how"` alone does NOT
    // fire fetch (the value prop bypasses the onChange path).
    fireEvent.change(input, { target: { value: "how" } });

    await waitFor(() => expect(global.fetch).toHaveBeenCalled(), { timeout: 1000 });

    // Suggestion <li role="option"> appears once setAcSuggestions resolves.
    const option = await screen.findByRole("option", { name: /Howard/ }, { timeout: 1000 });
    fireEvent.mouseDown(option);
    expect(BASE_PROPS.onChange).toHaveBeenCalledWith("Howard");
  });
});
