/**
 * LocationInput component tests.
 *
 * After Chunk 7 of the Geocoding & Autocomplete plan, LocationInput is a
 * thin shell around the generic AddressAutocomplete (combobox + listbox).
 * It still owns the save-star, save panel, geo button, and the
 * saved-locations dropdown (which is mutually exclusive with autocomplete
 * results — autocomplete fires only at ≥2 chars, saved-list shows only
 * with an empty value).
 *
 * Covers: rendering, geo button visibility, save flow, autocomplete
 * forwarding through the new `fetchAutocomplete` client, suggestion
 * selection via the underlying AddressAutocomplete.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useState } from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LocationInput from "../components/LocationInput.jsx";

// LocationInput is controlled; tests that simulate typing need a stateful
// shell so the `value` prop actually changes after a `fireEvent.change`.
function Harness({ initialValue = "", onChange: onChangeProp, ...rest }) {
  const [value, setValue] = useState(initialValue);
  function handleChange(next) {
    setValue(next);
    onChangeProp?.(next);
  }
  return <LocationInput {...rest} value={value} onChange={handleChange} />;
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key, opts) => (opts?.count ? `${key}:${opts.count}` : key),
  }),
}));

vi.mock("../favorites.js", () => ({
  saveLocation: vi.fn(),
  deleteLocation: vi.fn(),
}));

vi.mock("../lib/autocompleteApi.js", () => ({
  fetchAutocomplete: vi.fn(),
}));

import { fetchAutocomplete } from "../lib/autocompleteApi.js";

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

  it("renders a combobox input", () => {
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
    expect(
      screen.queryByRole("button", { name: /fav_save_location/ }),
    ).not.toBeInTheDocument();
  });

  it("shows the save star when value is non-empty", () => {
    render(<LocationInput {...BASE_PROPS} value="Howard" />);
    expect(
      screen.getByRole("button", { name: "fav_save_location" }),
    ).toBeInTheDocument();
  });

  it("shows saved star when value matches a saved location", () => {
    render(
      <LocationInput
        {...BASE_PROPS}
        value="Howard"
        savedLocations={[{ value: "Howard", label: "Howard" }]}
      />,
    );
    expect(
      screen.getByRole("button", { name: "fav_unsave_location" }),
    ).toBeInTheDocument();
  });

  it("opens the save panel when the unsaved star is clicked", () => {
    render(<LocationInput {...BASE_PROPS} value="Howard" />);
    fireEvent.click(screen.getByRole("button", { name: "fav_save_location" }));
    expect(screen.getByText("fav_save")).toBeInTheDocument();
  });

  it("forwards typed queries through fetchAutocomplete", async () => {
    fetchAutocomplete.mockResolvedValue([
      { value: "Howard", label: "Howard", type: "train" },
    ]);
    render(<Harness {...BASE_PROPS} />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "how" } });
    await waitFor(
      () => expect(fetchAutocomplete).toHaveBeenCalled(),
      { timeout: 1000 },
    );
    expect(fetchAutocomplete.mock.calls[0][0]).toBe("how");
  });

  it("commits onChange with the selected suggestion's value", async () => {
    fetchAutocomplete.mockResolvedValue([
      { value: "Howard", label: "Howard", type: "train" },
    ]);
    const onChange = vi.fn();
    render(<Harness {...BASE_PROPS} onChange={onChange} />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "how" } });
    const option = await screen.findByRole(
      "option",
      { name: /Howard/ },
      { timeout: 1000 },
    );
    fireEvent.mouseDown(option);
    expect(onChange).toHaveBeenCalledWith("Howard");
  });

  it("renders the saved-locations dropdown when focused with empty value", () => {
    render(
      <LocationInput
        {...BASE_PROPS}
        value=""
        savedLocations={[{ id: "1", value: "Howard", label: "Home" }]}
      />,
    );
    fireEvent.focus(screen.getByRole("combobox"));
    expect(screen.getByRole("listbox", { name: /aria_saved_locations/ })).toBeInTheDocument();
    expect(screen.getByText("Home")).toBeInTheDocument();
  });
});
