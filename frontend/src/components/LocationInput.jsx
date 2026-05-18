// Composite location field for the route form.
//
// Wraps `AddressAutocomplete` (the generic typeahead, Chunk 7 of the
// Geocoding & Autocomplete plan) and layers on the features specific to
// this app's route form:
//
//   * Geo button below the input — single-shot reverse-geocoded geolocation
//   * Save-star button on top of the input — saves the current value as a
//     favorite (capped via `saveLocation` in favorites.js)
//   * Saved-locations dropdown — appears when the input is focused with
//     empty value AND saved locations exist; mutually exclusive with the
//     autocomplete listbox (autocomplete only fires for ≥2 chars)
//
// The autocomplete listbox + ARIA combobox plumbing live entirely in
// AddressAutocomplete. This component is intentionally a thin shell.

import { useRef, useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  BACKEND_URL,
  GEO_OPTIONS,
  GEO_ERROR_RESET_MS,
  GEO_UNAVAILABLE_RESET_MS,
  LIMIT_ERROR_DISMISS_MS,
  DROPDOWN_BLUR_DELAY_MS,
} from "../constants.js";
import { saveLocation, deleteLocation } from "../favorites.js";
import LabelSavePanel from "./LabelSavePanel.jsx";
import AddressAutocomplete from "./AddressAutocomplete.jsx";
import { fetchAutocomplete } from "../lib/autocompleteApi.js";

export default function LocationInput({
  value,
  onChange,
  onGeoCoords,
  placeholder,
  savedLocations,
  onSavedLocationsChange,
  showGeoBtn,
}) {
  const { t } = useTranslation();

  // Saved-locations panel state. Mutually exclusive with the AC listbox: the
  // panel only renders when value is empty (AC's MIN_QUERY_CHARS gate would
  // close the AC listbox in that state) and the input is focused. We track
  // both focus and AC-open via callbacks so a stray repaint can't show both.
  const [savedPanelOpen, setSavedPanelOpen] = useState(false);
  const [acOpen, setAcOpen] = useState(false);

  // Save-favorite panel state (the in-place "name this place" UI).
  const [savingMode, setSavingMode] = useState(false);
  const [labelDraft, setLabelDraft] = useState("");
  const [limitError, setLimitError] = useState(false);

  // Geo button state machine.
  const [geoState, setGeoState] = useState("idle"); // 'idle' | 'loading' | 'denied' | 'error'

  const timersRef = useRef({});
  const geoAbortRef = useRef(null);

  const isSaved = savedLocations.some((loc) => loc.value === value);
  const showStar = value.trim().length > 0;

  useEffect(
    () => () => {
      Object.values(timersRef.current).forEach(clearTimeout);
      if (geoAbortRef.current) geoAbortRef.current.abort();
    },
    [],
  );

  function handleAddressChange(next) {
    // Cancel any in-flight geo lookup so its async success callback can't
    // overwrite the user's typing once it eventually resolves.
    if (geoAbortRef.current) geoAbortRef.current.abort();
    onChange(next);
    onGeoCoords?.(null);
  }

  function handleGeoClick() {
    if (!navigator.geolocation) {
      setGeoState("error");
      timersRef.current.geo = setTimeout(
        () => setGeoState("idle"),
        GEO_ERROR_RESET_MS,
      );
      return;
    }
    setGeoState("loading");
    if (geoAbortRef.current) geoAbortRef.current.abort();
    const ctrl = new AbortController();
    geoAbortRef.current = ctrl;
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        if (ctrl.signal.aborted) return;
        const { latitude, longitude } = pos.coords;
        const coords = `${latitude.toFixed(6)},${longitude.toFixed(6)}`;
        // Always store the raw coordinates for routing — never re-geocode them.
        onGeoCoords?.(coords);
        // Set raw coords in the input immediately so the form can submit if
        // reverse geocoding is slow.
        onChange(coords);
        try {
          const res = await fetch(
            `${BACKEND_URL}/reverse-geocode?lat=${latitude.toFixed(6)}&lon=${longitude.toFixed(6)}`,
            { signal: ctrl.signal },
          );
          if (res.ok) {
            const data = await res.json();
            if (data.address && data.address !== coords) {
              // Update the display label only — routing still uses the raw
              // coords via onGeoCoords.
              onChange(data.address);
            }
          }
        } catch {
          // silently keep the raw coordinate fallback already set above
        }
        if (!ctrl.signal.aborted) setGeoState("idle");
      },
      (err) => {
        const isDenied = err.code === err.PERMISSION_DENIED;
        setGeoState(isDenied ? "denied" : "error");
        if (!isDenied) {
          timersRef.current.geo = setTimeout(
            () => setGeoState("idle"),
            GEO_UNAVAILABLE_RESET_MS,
          );
        }
      },
      GEO_OPTIONS,
    );
  }

  function handleStarClick() {
    if (isSaved) {
      const loc = savedLocations.find((l) => l.value === value);
      if (loc)
        onSavedLocationsChange(deleteLocation(loc.id, savedLocations));
    } else {
      setLabelDraft(value.slice(0, 30));
      setSavingMode(true);
    }
  }

  function handleSaveLabel() {
    const trimmedLabel = labelDraft.trim() || value.slice(0, 30);
    const next = saveLocation(trimmedLabel, value, savedLocations);
    if (next === null) {
      setLimitError(true);
      if (timersRef.current.limit) clearTimeout(timersRef.current.limit);
      timersRef.current.limit = setTimeout(() => {
        setLimitError(false);
        setSavingMode(false);
      }, LIMIT_ERROR_DISMISS_MS);
    } else {
      onSavedLocationsChange(next);
      setSavingMode(false);
    }
  }

  // Saved-locations panel opens only when the input is focused with an
  // empty value AND saved locations exist. AC owns the typed-query case.
  const showSavedPanel =
    savedPanelOpen &&
    !acOpen &&
    value.trim().length === 0 &&
    savedLocations.length > 0;

  return (
    <>
      <AddressAutocomplete
        value={value}
        onChange={handleAddressChange}
        getSuggestions={fetchAutocomplete}
        placeholder={placeholder}
        ariaLabel={placeholder}
        onOpen={() => setAcOpen(true)}
        onClose={() => setAcOpen(false)}
        onInputFocus={() => {
          if (timersRef.current.blur) clearTimeout(timersRef.current.blur);
          if (value.trim().length === 0 && savedLocations.length > 0) {
            setSavedPanelOpen(true);
          }
        }}
        onInputBlur={() => {
          if (timersRef.current.blur) clearTimeout(timersRef.current.blur);
          // Match the prior DROPDOWN_BLUR_DELAY_MS grace so a mouseDown on a
          // saved-row commits before the panel closes.
          timersRef.current.blur = setTimeout(
            () => setSavedPanelOpen(false),
            DROPDOWN_BLUR_DELAY_MS,
          );
        }}
        // The save-star renders as an absolutely-positioned adornment on top
        // of the input — same visual layout as before this refactor.
        inputAdornment={
          <>
            {showStar && !savingMode && (
              <button
                type="button"
                className={`star-btn${isSaved ? " star-btn--saved" : ""}`}
                onClick={handleStarClick}
                aria-label={
                  isSaved ? t("fav_unsave_location") : t("fav_save_location")
                }
                title={
                  isSaved ? t("fav_unsave_location") : t("fav_save_location")
                }
              >
                {isSaved ? "★" : "☆"}
              </button>
            )}
            {showSavedPanel && (
              <ul
                className="saved-dropdown"
                role="listbox"
                aria-label={t("aria_saved_locations")}
              >
                {savedLocations.slice(0, 5).map((loc, i) => (
                  <li
                    key={loc.id}
                    className="saved-dropdown-item"
                    role="option"
                    aria-selected={false}
                  >
                    {/* Editorial section marker (§N) — D2 spec replaces
                        home/work/star icons with italic-serif numerals
                        indexed from 1. Decorative. */}
                    <span className="saved-marker" aria-hidden="true">
                      {`§${i + 1}`}
                    </span>
                    <span
                      className="saved-dropdown-label"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        onChange(loc.value);
                        setSavedPanelOpen(false);
                      }}
                    >
                      {loc.label}
                    </span>
                    <button
                      type="button"
                      className="saved-dropdown-delete"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        const next = deleteLocation(loc.id, savedLocations);
                        onSavedLocationsChange(next);
                        if (next.length === 0) setSavedPanelOpen(false);
                      }}
                      aria-label={t("fav_delete")}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        }
      />
      {showGeoBtn && !savingMode && (
        <div className="geo-btn-row">
          <button
            type="button"
            className={`geo-btn${geoState === "loading" ? " geo-btn--loading" : ""}${
              geoState === "denied" || geoState === "error"
                ? " geo-btn--error"
                : ""
            }`}
            onClick={handleGeoClick}
            disabled={geoState === "loading"}
            aria-label={t("geo_btn_label")}
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" />
            </svg>
            {geoState === "loading"
              ? t("geo_loading")
              : geoState === "denied"
                ? t("geo_denied")
                : geoState === "error"
                  ? t("geo_error")
                  : t("geo_btn_label")}
          </button>
        </div>
      )}
      {showGeoBtn && geoState === "denied" && (
        <div className="geo-denied-banner" role="alert">
          <span>{t("geo_denied_help")}</span>
          <button
            type="button"
            className="geo-denied-dismiss"
            onClick={() => {
              if (timersRef.current.geo) clearTimeout(timersRef.current.geo);
              setGeoState("idle");
            }}
            aria-label={t("aria_dismiss")}
          >
            ×
          </button>
        </div>
      )}
      {savingMode && (
        <LabelSavePanel
          value={labelDraft}
          onChange={setLabelDraft}
          onSave={handleSaveLabel}
          onCancel={() => setSavingMode(false)}
          placeholder={t("fav_label_placeholder")}
          showError={limitError}
        />
      )}
    </>
  );
}
