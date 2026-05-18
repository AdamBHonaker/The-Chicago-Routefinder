import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { LINE_COLORS } from "../lineColors.js";

// Multi-select filter pair for the Notices & Delays tab. Two buttons in a row,
// each opening a popover of checkboxes (mirrors LanguagePicker's
// button-opens-popover pattern, but multi-select instead of single-select).
//
// Props:
//   selectedLines / selectedBuses : Set<string>
//   onSelectedLinesChange / onSelectedBusesChange : (Set<string>) => void
//   availableBusRoutes : string[]   // derived from current /alerts feed
//
// Sort order for bus routes: numerics ascending, then express (X*), then
// night (N*), then other letter-prefixed routes alphabetically.
function sortBusRoutes(routes) {
  const num = [];
  const express = [];
  const night = [];
  const other = [];
  for (const r of routes) {
    const head = r[0];
    if (head >= "0" && head <= "9") num.push(r);
    else if (head === "X" || head === "x") express.push(r);
    else if (head === "N" || head === "n") night.push(r);
    else other.push(r);
  }
  num.sort((a, b) => {
    const ai = parseInt(a, 10);
    const bi = parseInt(b, 10);
    if (ai !== bi) return ai - bi;
    return a.localeCompare(b);
  });
  express.sort();
  night.sort();
  other.sort();
  return [...num, ...express, ...night, ...other];
}

const L_LINES = Object.keys(LINE_COLORS);

function FilterButton({
  open,
  onToggle,
  label,
  countLabel,
  ariaLabel,
  selectedCount,
  buttonRef,
}) {
  return (
    <button
      ref={buttonRef}
      type="button"
      className="alerts-filter__trigger masthead-select"
      aria-haspopup="menu"
      aria-expanded={open}
      aria-label={ariaLabel}
      onClick={onToggle}
    >
      {selectedCount > 0 ? countLabel : label}
    </button>
  );
}

// Shared popover shell for both filter categories (TD-FE-023).
// Owns the wrapper + list + clear-button scaffolding; the per-row visual
// (color swatch + label vs. mono code label) is supplied by renderRow.
// helpText / emptyText are optional and used only by the bus popover.
function FilterPopover({
  variant, ariaLabel, items, selected, toggleItem, clearLabel, onClear,
  renderRow, helpText, emptyText,
}) {
  return (
    <div
      className={`alerts-filter__popover alerts-filter__popover--${variant}`}
      role="menu"
      aria-label={ariaLabel}
    >
      {helpText && <p className="alerts-filter__help">{helpText}</p>}
      {items.length === 0 && emptyText ? (
        <p className="alerts-filter__empty">{emptyText}</p>
      ) : (
        <ul className="alerts-filter__list" role="none">
          {items.map((key) => {
            const checked = selected.has(key);
            return (
              <li key={key} role="none">
                <label
                  className={
                    "alerts-filter__row" + (checked ? " alerts-filter__row--checked" : "")
                  }
                  role="menuitemcheckbox"
                  aria-checked={checked}
                >
                  <input
                    type="checkbox"
                    className="alerts-filter__checkbox"
                    checked={checked}
                    onChange={() => toggleItem(key)}
                  />
                  {renderRow(key)}
                </label>
              </li>
            );
          })}
        </ul>
      )}
      {selected.size > 0 && (
        <button type="button" className="alerts-filter__clear" onClick={onClear}>
          {clearLabel}
        </button>
      )}
    </div>
  );
}

export default function AlertsFilterBar({
  selectedLines,
  selectedBuses,
  onSelectedLinesChange,
  onSelectedBusesChange,
  availableBusRoutes,
}) {
  const { t } = useTranslation();
  const [openPanel, setOpenPanel] = useState(null); // "l" | "bus" | null
  const containerRef = useRef(null);
  const lButtonRef = useRef(null);
  const busButtonRef = useRef(null);

  // Memo on availableBusRoutes (OPT-FE-210) — popover-toggle setStates and
  // checkbox ticks otherwise re-sort every render.
  const sortedBuses = useMemo(
    () => sortBusRoutes(availableBusRoutes ?? []),
    [availableBusRoutes],
  );

  useEffect(() => {
    if (!openPanel) return undefined;
    function onDocClick(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpenPanel(null);
      }
    }
    function onKey(e) {
      if (e.key === "Escape") {
        const which = openPanel;
        setOpenPanel(null);
        if (which === "l") lButtonRef.current?.focus();
        else if (which === "bus") busButtonRef.current?.focus();
      }
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [openPanel]);

  function toggleLine(name) {
    const next = new Set(selectedLines);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    onSelectedLinesChange(next);
  }

  function toggleBus(code) {
    const next = new Set(selectedBuses);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    onSelectedBusesChange(next);
  }

  return (
    <div className="alerts-filter" ref={containerRef}>
      <FilterButton
        open={openPanel === "l"}
        onToggle={() => setOpenPanel(openPanel === "l" ? null : "l")}
        label={t("alerts_filter_l_label")}
        countLabel={t("alerts_filter_l_count", { count: selectedLines.size })}
        ariaLabel={t("alerts_filter_l_aria")}
        selectedCount={selectedLines.size}
        buttonRef={lButtonRef}
      />

      <FilterButton
        open={openPanel === "bus"}
        onToggle={() => setOpenPanel(openPanel === "bus" ? null : "bus")}
        label={t("alerts_filter_bus_label")}
        countLabel={t("alerts_filter_bus_count", { count: selectedBuses.size })}
        ariaLabel={t("alerts_filter_bus_aria")}
        selectedCount={selectedBuses.size}
        buttonRef={busButtonRef}
      />

      {openPanel === "l" && (
        <FilterPopover
          variant="l"
          ariaLabel={t("alerts_filter_l_aria")}
          items={L_LINES}
          selected={selectedLines}
          toggleItem={toggleLine}
          clearLabel={t("alerts_filter_clear")}
          onClear={() => onSelectedLinesChange(new Set())}
          renderRow={(name) => (
            <>
              <span
                className="alerts-filter__swatch"
                aria-hidden="true"
                style={{ background: LINE_COLORS[name] }}
              />
              <span className="alerts-filter__row-label">{name} Line</span>
            </>
          )}
        />
      )}

      {openPanel === "bus" && (
        <FilterPopover
          variant="bus"
          ariaLabel={t("alerts_filter_bus_aria")}
          items={sortedBuses}
          selected={selectedBuses}
          toggleItem={toggleBus}
          clearLabel={t("alerts_filter_clear")}
          onClear={() => onSelectedBusesChange(new Set())}
          helpText={t("alerts_bus_filter_help")}
          emptyText={t("alerts_empty")}
          renderRow={(code) => (
            <span className="alerts-filter__row-label alerts-filter__row-label--mono">
              {code}
            </span>
          )}
        />
      )}
    </div>
  );
}
