// Generic typeahead combobox shared by the route form's LocationInput.
//
// Data source is pluggable: pass `getSuggestions(query, { signal })` and the
// component handles debounce, in-flight cancellation, keyboard navigation,
// pointer + touch selection, and portal rendering so the listbox can escape
// `overflow: hidden` ancestors and the mobile bottom-sheet's transform clip.
//
// Suggestion shape (this app's backend, matches what `/autocomplete` returns):
//   { label: string, value: string, type: string }
// Anything else on the object is passed through to `onSelect` untouched.
//
// Implements the WAI-ARIA combobox pattern (1.1 inline variant): the input
// owns the listbox via `aria-controls`, `aria-expanded` reflects open state,
// and the highlighted option is announced via `aria-activedescendant` so a
// screen reader follows the arrow-key cursor without focus moving off the
// input. WAI-ARIA Authoring Practices §3.5 "Combobox", inline pattern.

import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { AC_DEBOUNCE_MS } from "../constants.js";

const MIN_QUERY_CHARS = 2;
// Breathing room between the listbox and the viewport edge / soft keyboard.
// 16 keeps the bottom row legible above iOS Safari's keyboard accessory bar
// and gives the bottom-sheet's safe-area inset a little air.
const VIEWPORT_MARGIN_PX = 16;
const DEFAULT_MAX_HEIGHT_PX = 320;

export default function AddressAutocomplete({
  value,
  onChange,
  onSelect,
  getSuggestions,
  placeholder = "",
  ariaLabel,
  inputClassName,
  disabled = false,
  autoFocus = false,
  enterKeyHint = "go",
  debounceMs = AC_DEBOUNCE_MS,
  // "portal" (default) renders the listbox into document.body so it can
  // escape `overflow: hidden` and transform-clipping ancestors (the mobile
  // bottom sheet). "absolute" keeps the listbox inside the wrapper for
  // tests or callers that already provide a non-clipping shell.
  positioning = "portal",
  // Allow callers (mainly tests) to pin the listbox id deterministically.
  listboxId: listboxIdProp,
  inputRef: inputRefProp,
  // Optional wrapper class so callers can scope styles to one host instance.
  wrapperClassName = "",
  // Optional pre-rendered prefix slot inside the wrapper (used by the host
  // to position a save-star button on top of the input). Slot is rendered
  // AFTER the input so the input's box can be positioned absolutely.
  inputAdornment = null,
  // Public callbacks for the open/close lifecycle. LocationInput uses these
  // to suppress its own saved-locations dropdown while autocomplete is open.
  onOpen,
  onClose,
  // Pass-through focus/blur callbacks on the underlying input. Used by
  // hosts (LocationInput) to drive sibling UI (saved-locations dropdown)
  // without having to attach their own focus listeners.
  onInputFocus,
  onInputBlur,
}) {
  const { t } = useTranslation();
  const reactId = useId();
  const listboxId = listboxIdProp || `ac-${reactId.replace(/[:]/g, "_")}`;
  const inputRefLocal = useRef(null);
  const inputRef = inputRefProp || inputRefLocal;
  const wrapperRef = useRef(null);
  const abortRef = useRef(null);
  const debounceRef = useRef(null);
  const lastQueryRef = useRef("");

  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [loading, setLoading] = useState(false);

  // Surface open transitions to the host. Used by LocationInput to mute its
  // saved-locations dropdown when autocomplete results are showing.
  useEffect(() => {
    if (open) onOpen?.();
    else onClose?.();
  }, [open, onOpen, onClose]);

  // Reset highlight whenever the dropdown closes or the list changes.
  useEffect(() => {
    if (!open) setActive(-1);
  }, [open]);

  const abortInFlight = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const fetchFor = useCallback(
    async (q) => {
      if (!getSuggestions) return;
      const trimmed = (q || "").trim();
      if (trimmed.length < MIN_QUERY_CHARS) {
        setSuggestions([]);
        setLoading(false);
        return;
      }
      abortInFlight();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      lastQueryRef.current = trimmed;
      setLoading(true);
      try {
        const result = await getSuggestions(trimmed, { signal: ctrl.signal });
        // Drop out-of-order responses: only commit if the query that fired
        // this fetch is still the most recent one. Without this guard, slow
        // network + fast typing renders an obviously-stale list.
        if (lastQueryRef.current !== trimmed) return;
        setSuggestions(Array.isArray(result) ? result : []);
      } catch (err) {
        if (err?.name === "AbortError") return;
        // Soft-fail: an autocomplete error must never break typing. Surface
        // an empty list so the input remains usable.
        setSuggestions([]);
      } finally {
        // Only the current (non-superseded) fetch flips loading off — an
        // aborted fetch settling here would briefly clear the "Searching…"
        // SR announcement while a fresher fetch is still in flight, causing
        // a `true → false → true` flicker.
        if (abortRef.current === ctrl) {
          abortRef.current = null;
          setLoading(false);
        }
      }
    },
    [getSuggestions, abortInFlight],
  );

  // Debounced effect: every value change schedules a fetch; a fresh keystroke
  // clears the prior timer so we only call once per quiet window.
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    if (!open) return;
    const t = setTimeout(() => fetchFor(value), debounceMs);
    debounceRef.current = t;
    return () => clearTimeout(t);
  }, [value, open, debounceMs, fetchFor]);

  // Cleanup on unmount: cancel any pending timer + in-flight fetch.
  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      abortInFlight();
    },
    [abortInFlight],
  );

  function commitSelection(suggestion) {
    if (!suggestion) return;
    onChange?.(suggestion.value ?? suggestion.label);
    onSelect?.(suggestion);
    setOpen(false);
    setSuggestions([]);
    setActive(-1);
    abortInFlight();
  }

  function handleChange(e) {
    const next = e.target.value;
    onChange?.(next);
    if (!open) setOpen(true);
  }

  function handleFocus(e) {
    onInputFocus?.(e);
    if (value && value.trim().length >= MIN_QUERY_CHARS) {
      setOpen(true);
    }
  }

  function handleBlur(e) {
    onInputBlur?.(e);
    // If focus moves into one of our suggestion items, don't close — the
    // items use `onMouseDown` / `onTouchStart` to preempt blur, but a
    // screen-reader user navigating with VoiceOver focuses items too. In
    // portal mode the listbox lives in document.body, so match it by id
    // as well as by wrapper containment.
    const next = e.relatedTarget;
    if (next) {
      if (wrapperRef.current?.contains(next)) return;
      const escaped =
        typeof CSS !== "undefined" && CSS.escape
          ? CSS.escape(listboxId)
          : listboxId.replace(/"/g, '\\"');
      if (next.closest?.(`#${escaped}`)) return;
    }
    setOpen(false);
  }

  function handleKeyDown(e) {
    // Open the listbox on first arrow press even when closed — matches
    // every browser-native combobox's behavior.
    if ((e.key === "ArrowDown" || e.key === "ArrowUp") && !open && value) {
      setOpen(true);
      return;
    }
    if (!open) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (suggestions.length === 0) return;
      setActive((i) => (i + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (suggestions.length === 0) return;
      setActive((i) => (i <= 0 ? suggestions.length - 1 : i - 1));
    } else if (e.key === "Enter") {
      // Only swallow Enter when there's an active highlight to commit.
      // Otherwise let the form's default submit fire — matches the prior
      // raw-input behavior where Enter submitted the route form.
      if (active >= 0 && active < suggestions.length) {
        e.preventDefault();
        commitSelection(suggestions[active]);
      }
    } else if (e.key === "Escape") {
      if (open) {
        e.preventDefault();
        setOpen(false);
        setActive(-1);
      }
    } else if (e.key === "Home" && suggestions.length) {
      setActive(0);
    } else if (e.key === "End" && suggestions.length) {
      setActive(suggestions.length - 1);
    }
  }

  const activeId = useMemo(
    () =>
      active >= 0 && suggestions[active]
        ? `${listboxId}-opt-${active}`
        : undefined,
    [active, suggestions, listboxId],
  );

  // ── Portal positioning ────────────────────────────────────────────────
  // Track the input's bounding rect + visualViewport size so the fixed
  // listbox stays anchored under the input through page scroll, window
  // resize, iOS soft-keyboard open/close, page scroll under the visual
  // viewport, and bottom-sheet drag (the sheet uses transform, so the
  // input's getBoundingClientRect picks up the new position immediately).
  // The listbox is hidden via display:none until the first measurement lands.
  const [pos, setPos] = useState(null);
  const renderedListboxOpen = open && suggestions.length > 0;
  const portalEnabled =
    positioning === "portal" && typeof window !== "undefined";

  useLayoutEffect(() => {
    if (!portalEnabled || !renderedListboxOpen) {
      setPos(null);
      return;
    }
    function update() {
      const el = inputRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      // Prefer visualViewport.height — on iOS Safari it shrinks when the
      // soft keyboard opens, which is exactly the bound we want for the
      // dropdown's `max-height` so the bottom row stays above the keyboard.
      const vv = window.visualViewport;
      const viewportH = vv ? vv.height : window.innerHeight;
      const viewportTop = vv ? vv.offsetTop : 0;
      const spaceBelow =
        viewportTop + viewportH - rect.bottom - VIEWPORT_MARGIN_PX;
      const spaceAbove = rect.top - viewportTop - VIEWPORT_MARGIN_PX;
      // Flip above only when there is meaningfully more room there AND not
      // enough below for even three rows. 132 px ≈ 3 × 44 px rows.
      const flip = spaceBelow < 132 && spaceAbove > spaceBelow;
      const maxHeight = Math.max(
        88,
        Math.min(DEFAULT_MAX_HEIGHT_PX, flip ? spaceAbove : spaceBelow),
      );
      setPos({
        top: flip ? rect.top - maxHeight - 2 : rect.bottom + 2,
        left: rect.left,
        width: rect.width,
        maxHeight,
      });
    }
    update();
    // High-frequency scroll/resize events (capture-phase ancestor scroll,
    // bottom-sheet drag, iOS visualViewport keyboard transitions) can fire
    // 60+ times per second. Coalesce through requestAnimationFrame so the
    // measurement runs at most once per frame regardless of event density.
    let rafId = 0;
    const scheduleUpdate = () => {
      if (rafId) return;
      rafId = requestAnimationFrame(() => {
        rafId = 0;
        update();
      });
    };
    // Capture-phase scroll listener so any ancestor's scroll triggers a
    // reposition without each container having to opt in.
    window.addEventListener("scroll", scheduleUpdate, true);
    window.addEventListener("resize", scheduleUpdate);
    const vv = window.visualViewport;
    vv?.addEventListener("resize", scheduleUpdate);
    vv?.addEventListener("scroll", scheduleUpdate);
    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      window.removeEventListener("scroll", scheduleUpdate, true);
      window.removeEventListener("resize", scheduleUpdate);
      vv?.removeEventListener("resize", scheduleUpdate);
      vv?.removeEventListener("scroll", scheduleUpdate);
    };
  }, [portalEnabled, renderedListboxOpen, suggestions.length, inputRef]);

  // Position the listbox: portal mode uses the measured rect; absolute mode
  // (test-fixture / inline opt-out) keeps the existing `.saved-dropdown`
  // CSS-driven flow that was load-bearing before this refactor.
  const listboxStyle = portalEnabled
    ? pos
      ? {
          position: "fixed",
          top: pos.top,
          left: pos.left,
          width: pos.width,
          maxHeight: pos.maxHeight,
        }
      : { display: "none" }
    : undefined;

  const listbox = renderedListboxOpen ? (
    <ul
      id={listboxId}
      className="saved-dropdown"
      role="listbox"
      aria-label={t("aria_location_suggestions")}
      style={listboxStyle}
    >
      {suggestions.map((s, i) => (
        <li
          key={`${s.type || "x"}:${s.value || s.label}:${i}`}
          id={`${listboxId}-opt-${i}`}
          role="option"
          aria-selected={i === active}
          className={
            "saved-dropdown-item" +
            (i === active ? " saved-dropdown-item--active" : "")
          }
          // mousedown + touchstart so the selection fires *before* the
          // input's blur — otherwise blur would close the listbox before
          // click ever lands. Both events preventDefault to stop the touch
          // from also re-focusing the underlying scroll layer.
          onMouseDown={(e) => {
            e.preventDefault();
            commitSelection(s);
          }}
          onTouchStart={(e) => {
            e.preventDefault();
            commitSelection(s);
          }}
          onMouseEnter={() => setActive(i)}
        >
          <span className="saved-dropdown-label">{s.label}</span>
          {s.type && (
            <span
              className={`ac-type-badge ac-type-badge--${s.type}`}
              aria-hidden="true"
            >
              {badgeLabel(t, s.type)}
            </span>
          )}
        </li>
      ))}
    </ul>
  ) : null;

  return (
    <div
      className={`field-wrapper${wrapperClassName ? ` ${wrapperClassName}` : ""}`}
      ref={wrapperRef}
    >
      <input
        ref={inputRef}
        type="search"
        className={inputClassName}
        value={value ?? ""}
        placeholder={placeholder}
        onChange={handleChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        autoFocus={autoFocus}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="words"
        spellCheck={false}
        inputMode="search"
        enterKeyHint={enterKeyHint}
        role="combobox"
        aria-label={ariaLabel}
        aria-autocomplete="list"
        aria-controls={listboxId}
        aria-expanded={open && suggestions.length > 0}
        aria-activedescendant={activeId}
      />
      {inputAdornment}
      {portalEnabled
        ? listbox && createPortal(listbox, document.body)
        : listbox}
      {/* Status region kept visually hidden so screen readers announce the
          result count without crowding the visual layout. */}
      <span className="sr-only" role="status" aria-live="polite">
        {loading
          ? t("ac_status_searching")
          : suggestions.length > 0 && open
            ? t("ac_status_results", { count: suggestions.length })
            : ""}
      </span>
    </div>
  );
}

// Compact i18n labels for the type pill on the right of each row. Falls
// back to a generic "Place" key for any new type the backend ships.
function badgeLabel(t, type) {
  switch (type) {
    case "train":
      return t("ac_type_train");
    case "bus":
      return t("ac_type_bus");
    case "address":
      return t("ac_type_address");
    case "intersection":
      return t("ac_type_intersection");
    case "neighborhood":
      return t("ac_type_neighborhood");
    default:
      return t("ac_type_place");
  }
}
