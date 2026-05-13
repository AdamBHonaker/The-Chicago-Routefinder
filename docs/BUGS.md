# Bugs To Be Fixed

Known issues catalogued for future fixing. Severity: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When a bug in this file is fixed, **delete its entry from this file** and add a corresponding entry to the **Bugs Fixed** section of [`docs/archive/RESOLVED_HISTORY.md`](archive/RESOLVED_HISTORY.md) documenting what was changed and how. This file should only ever contain bugs that have not yet been resolved.

---

## Routing Engine Review 2026-05-11 (1 bug remaining: 1 Medium)

Surfaced by a detailed audit of the intermodal routing engine against its stated goals. BUG-008 and BUG-009 from the same audit were fixed same-day; BUG-045, BUG-046, BUG-047, BUG-048, BUG-049, BUG-050, BUG-051 (Chunk 1 — tagged service-period graph variants), and BUG-053 were resolved later. The item below remains.

---

# BUG-052 · 🟡 Medium — No quantitative accuracy benchmark vs. a known-good source; correctness regressions are undetectable

**Files:** `backend/tests/test_routing_accuracy.py` (scaffold present; all real-route tests `@pytest.mark.skip`), `backend/tests/routing_harness.py` (determinism framework complete), `backend/tests/known_stops.py` (pre-loaded L-station coordinates, added 2026-05-12), `backend/scripts/probe_route.py` (CLI fixture-probing helper, added 2026-05-12)

## What is happening

The determinism harness (`routing_harness.py`) is complete and seven smoke tests pass, but the 10–15 golden-fixture tests that would compare engine output against authoritative Chicago routes are not authored. There is no comparison to OSRM, Valhalla, CTA's own trip planner, or curated GTFS-reference itineraries. Determinism is well covered; correctness against ground truth is not.

**Effect:** We cannot quantitatively answer "is the routing accurate to within X minutes for Y% of queries." Any future regression — a graph-construction change, a transfer-logic refactor, a new mode — could silently degrade routing quality, and the only signal would be a user complaint. BUG-008 was caught by a unit test only after the integration regression test was retrospectively added.

**Reproduction:** Run `pytest backend/tests/test_routing_accuracy.py -v`; observe every meaningful test marked skipped.

## Scaffold improvements (2026-05-12 — BUG-052 still open)

The fixtures still need human authoring with Chicago rider knowledge, but the activation energy to finish them has been lowered:

- `backend/tests/known_stops.py` pre-loads every CTA L parent station as a named `(lat, lon)` constant (e.g. `KNOWN_STOPS["LOGAN_SQUARE_BLUE"]`), pulled from `gtfs_data/stops.txt`. Authors no longer need to copy/paste coordinates per fixture.
- `backend/scripts/probe_route.py` is a read-only CLI that runs one scenario and prints the engine's `primary_modes` / `lines` / `transfers` / `total_minutes` plus all ranked alternatives, so an author can see what the engine actually does for a candidate OD pair before pinning an assertion. Usage: `python -m backend.scripts.probe_route --origin-stop LOGAN_SQUARE_BLUE --dest-stop GARFIELD_RED`.
- The module docstring in `test_routing_accuracy.py` now points at both helpers, adds a "probe before pinning" step to the authoring guide, and warns explicitly against silently encoding the engine's current output as the expected answer.
- `routing_harness.summarize_route()` was fixed (pre-existing bug in the layer-3 harness): it was returning `"transit"` for every transit leg because `TransitLeg` has no `mode` attribute, and `0.0` for `total_minutes` because `Route` exposes the value as `total_minutes_no_wait`. Now classifies legs as `"train"` / `"bus"` via `line_code` against the known CTA train codes and reads `total_minutes_no_wait`. Any assertion authored against `summarize_route`'s output would have been wrong before this fix.

## Fix approach (single chunk)

Author 10–15 Chicago O/D fixtures in `test_routing_accuracy.py` covering: single-line train, train+train transfer, bus→train, train→bus, bus+bus, walk-only, edge-of-service, late-night, weekend service, and out-of-coverage (paired with BUG-047). For each fixture capture:

1. **Route topology** (line sequence and transfer stations) — asserted exactly.
2. **Total time** — asserted within a tolerance band derived from the determinism harness's observed variance (~±2 min for in-coverage routes is reasonable).

Source ground truth from CTA's own trip planner or a manually ride-tested itinerary. Do NOT use Google Maps for transit ground truth — Google often combines suboptimally on CTA. Run as part of CI so regressions block merges.

Acceptance: ≥10 unskipped golden fixtures; each fails loudly if route topology changes; the suite runs in <30 seconds in CI.

---

# BUG-058 · 🟢 Low — Autocomplete suggestion list uses array index as React key

**Files:** `frontend/src/components/LocationInput.jsx` (line 219 — `acSuggestions.map((s, i) => <li key={i}>`)

**Will be incidentally fixed by Chunk 7 of the Geocoding & Autocomplete chunked plan** (see [FEATURE_PLANS.md](FEATURE_PLANS.md)). That chunk replaces `LocationInput`'s combobox guts with the ported generic `AddressAutocomplete.jsx` (WAI-ARIA combobox 1.1, portal-rendered, stable keys), so don't fix this independently — the whole call site goes away. Delete this entry when Chunk 7 ships.

## What is happening

The autocomplete dropdown keys list items by their index in `acSuggestions`. When the suggestion list updates (each keystroke replaces the list), React reuses the same `<li>` for slot 0, slot 1, … even though the underlying suggestion data is entirely different. The `aria-selected`, `className`, and child text update fine, but any per-item state (e.g. CSS transitions, future React state inside a more complex item component) carries over from the previous query's slot 0 to the new query's slot 0, which is wrong.

Index-as-key is also brittle if the rendering ever switches from "replace whole list" to "filter in place" — items would silently swap identity.

**Reproduction:** Add a CSS `transition: background-color 200ms` on `.saved-dropdown-item`. Type a query, observe a suggestion become highlighted. Type the next character; the new top suggestion inherits the highlight's transition state from the old slot 0 rather than starting clean.

## Fix approach (single chunk)

Key by suggestion value, which is stable across renders for the same underlying place:

```jsx
{acSuggestions.map((s, i) => (
  <li key={`${s.type}:${s.value}`} … >
    …
  </li>
))}
```

If duplicates by `value` are possible, append the index as a tie-breaker.

Acceptance: typing through queries reuses DOM nodes only when the same suggestion appears in two consecutive lists.

---
