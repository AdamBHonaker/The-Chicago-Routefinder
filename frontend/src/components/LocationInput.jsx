import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  BACKEND_URL,
  GEO_OPTIONS,
  AC_DEBOUNCE_MS,
  DROPDOWN_BLUR_DELAY_MS,
  GEO_ERROR_RESET_MS,
  GEO_UNAVAILABLE_RESET_MS,
  LIMIT_ERROR_DISMISS_MS,
} from "../constants.js";
import { saveLocation, deleteLocation } from "../favorites.js";
import LabelSavePanel from "./LabelSavePanel.jsx";

export default function LocationInput({ value, onChange, onGeoCoords, placeholder, savedLocations, onSavedLocationsChange, showGeoBtn }) {
  const { t } = useTranslation();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [savingMode, setSavingMode] = useState(false);
  const [labelDraft, setLabelDraft] = useState("");
  const [limitError, setLimitError] = useState(false);
  const [geoState, setGeoState] = useState("idle"); // 'idle' | 'loading' | 'denied' | 'error'
  const timersRef = useRef({});
  const [acSuggestions, setAcSuggestions] = useState([]);
  const [acActiveIndex, setAcActiveIndex] = useState(-1);
  const acAbortRef = useRef(null);

  const isSaved = savedLocations.some((loc) => loc.value === value);
  const showStar = value.trim().length > 0;

  useEffect(() => () => {
    Object.values(timersRef.current).forEach(clearTimeout);
    if (acAbortRef.current) acAbortRef.current.abort();
  }, []);

  function fetchAcSuggestions(query) {
    if (timersRef.current.acDebounce) clearTimeout(timersRef.current.acDebounce);
    if (acAbortRef.current) acAbortRef.current.abort();
    if (query.trim().length < 2) {
      setAcSuggestions([]);
      setAcActiveIndex(-1);
      return;
    }
    timersRef.current.acDebounce = setTimeout(async () => {
      const ctrl = new AbortController();
      acAbortRef.current = ctrl;
      try {
        const res = await fetch(
          `${BACKEND_URL}/autocomplete?q=${encodeURIComponent(query.trim())}`,
          { signal: ctrl.signal }
        );
        if (!res.ok) return;
        const data = await res.json();
        setAcSuggestions(data.suggestions || []);
        setAcActiveIndex(-1);
      } catch (err) {
        if (err.name !== "AbortError") setAcSuggestions([]);
      }
    }, AC_DEBOUNCE_MS);
  }

  function selectAcSuggestion(suggestion) {
    onChange(suggestion.value);
    setAcSuggestions([]);
    setAcActiveIndex(-1);
    if (timersRef.current.acDebounce) clearTimeout(timersRef.current.acDebounce);
    if (acAbortRef.current) acAbortRef.current.abort();
  }

  function handleGeoClick() {
    if (!navigator.geolocation) {
      setGeoState("error");
      timersRef.current.geo = setTimeout(() => setGeoState("idle"), GEO_ERROR_RESET_MS);
      return;
    }
    setGeoState("loading");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        const coords = `${latitude.toFixed(6)},${longitude.toFixed(6)}`;
        // Always store the raw coordinates for routing — never re-geocode them.
        onGeoCoords?.(coords);
        // Set raw coords in the input immediately so the form can submit if reverse geocoding is slow.
        onChange(coords);
        try {
          const res = await fetch(
            `${BACKEND_URL}/reverse-geocode?lat=${latitude.toFixed(6)}&lon=${longitude.toFixed(6)}`
          );
          if (res.ok) {
            const data = await res.json();
            if (data.address && data.address !== coords) {
              // Update the display label only — routing still uses the raw coords via onGeoCoords.
              onChange(data.address);
            }
          }
        } catch {
          // silently keep the raw coordinate fallback already set above
        }
        setGeoState("idle");
      },
      (err) => {
        const isDenied = err.code === err.PERMISSION_DENIED;
        setGeoState(isDenied ? "denied" : "error");
        if (!isDenied) {
          timersRef.current.geo = setTimeout(() => setGeoState("idle"), GEO_UNAVAILABLE_RESET_MS);
        }
      },
      GEO_OPTIONS
    );
  }

  function handleStarClick() {
    if (isSaved) {
      const loc = savedLocations.find((l) => l.value === value);
      if (loc) onSavedLocationsChange(deleteLocation(loc.id, savedLocations));
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
      timersRef.current.limit = setTimeout(() => { setLimitError(false); setSavingMode(false); }, LIMIT_ERROR_DISMISS_MS);
    } else {
      onSavedLocationsChange(next);
      setSavingMode(false);
    }
  }

  return (
    <>
      <div className="field-wrapper">
        <input
          type="search"
          inputMode="search"
          enterKeyHint="go"
          placeholder={placeholder}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            onGeoCoords?.(null);
            fetchAcSuggestions(e.target.value);
          }}
          onFocus={() => {
            if (value.trim().length >= 2) {
              fetchAcSuggestions(value);
            } else if (savedLocations.length > 0) {
              setDropdownOpen(true);
            }
          }}
          onBlur={() => {
            timersRef.current.blur = setTimeout(() => {
              setDropdownOpen(false);
              setAcSuggestions([]);
              setAcActiveIndex(-1);
            }, DROPDOWN_BLUR_DELAY_MS);
          }}
          onKeyDown={(e) => {
            if (acSuggestions.length === 0) return;
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setAcActiveIndex(i => Math.min(i + 1, acSuggestions.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setAcActiveIndex(i => Math.max(i - 1, -1));
            } else if (e.key === "Enter" && acActiveIndex >= 0) {
              e.preventDefault();
              selectAcSuggestion(acSuggestions[acActiveIndex]);
            } else if (e.key === "Escape") {
              setAcSuggestions([]);
              setAcActiveIndex(-1);
            }
          }}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="words"
        />
        {showStar && !savingMode && (
          <button
            type="button"
            className={`star-btn${isSaved ? " star-btn--saved" : ""}`}
            onClick={handleStarClick}
            aria-label={isSaved ? t("fav_unsave_location") : t("fav_save_location")}
            title={isSaved ? t("fav_unsave_location") : t("fav_save_location")}
          >
            {isSaved ? "★" : "☆"}
          </button>
        )}
        {acSuggestions.length > 0 && (
          <ul className="saved-dropdown" role="listbox" aria-label={t("aria_location_suggestions")}>
            {acSuggestions.map((s, i) => (
              <li
                key={i}
                className={`saved-dropdown-item${i === acActiveIndex ? " saved-dropdown-item--active" : ""}`}
                role="option"
                aria-selected={i === acActiveIndex}
                onMouseDown={(e) => { e.preventDefault(); selectAcSuggestion(s); }}
              >
                <span className="saved-dropdown-label">{s.label}</span>
                <span className="ac-type-badge">
                  {s.type === "train" ? t("ac_type_train") : s.type === "bus" ? t("ac_type_bus") : t("ac_type_place")}
                </span>
              </li>
            ))}
          </ul>
        )}
        {dropdownOpen && savedLocations.length > 0 && acSuggestions.length === 0 && (
          <ul className="saved-dropdown" role="listbox">
            {savedLocations.slice(0, 5).map((loc) => (
              <li key={loc.id} className="saved-dropdown-item" role="option">
                <span
                  className="saved-dropdown-label"
                  onMouseDown={(e) => { e.preventDefault(); onChange(loc.value); setDropdownOpen(false); }}
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
                    if (next.length === 0) setDropdownOpen(false);
                  }}
                  aria-label={t("fav_delete")}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {showGeoBtn && !savingMode && (
        <div className="geo-btn-row">
          <button
            type="button"
            className={`geo-btn${geoState === "loading" ? " geo-btn--loading" : ""}${geoState === "denied" || geoState === "error" ? " geo-btn--error" : ""}`}
            onClick={handleGeoClick}
            disabled={geoState === "loading"}
            aria-label={t("geo_btn_label")}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
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
          >×</button>
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
