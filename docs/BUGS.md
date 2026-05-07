# Bugs To Be Fixed

Known issues catalogued for future fixing. Severity: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When a bug in this file is fixed, **delete its entry from this file** and add a corresponding entry to the **Bugs Fixed** section of [`docs/archive/RESOLVED_HISTORY.md`](archive/RESOLVED_HISTORY.md) documenting what was changed and how. This file should only ever contain bugs that have not yet been resolved.

---

## Bug Scan — 2026-05-06 (backend)

> Scanned: `backend/` (all `.py` files, ~11.8k lines across 30 modules — utils, config, route_scoring, rate_limit, dau, hourly, devices, referrers, sessions, funnel, retention, events, geography, analytics_store, middleware, public_stats, routes/admin, routes/stats, cta_client, weather_service, crowdedness, fetch_gtfs, fetch_station_exits, fetch_street_graph, active_routes, prompt_builder, walking, transit_graph, gtfs_loader, main)
> Found: 6 bug(s) — 5 🟡 Medium, 1 🟢 Low

---

### BUG-004 · 🟡 Day-rollover loses unflushed `hourly` increments
- **File**: [backend/hourly.py](../backend/hourly.py#L63-L68)
- **Line(s)**: 63–68
- **Severity**: Medium
- **Description**: When the Chicago day rolls over inside `record_recommend()`, the handler calls `_load()` and replaces the in-memory `_counts` dict via `_counts.clear()` + `_counts.update(new_counts)` **without first flushing pending in-memory writes to disk**. Any of the previous day's increments accumulated since the last batch flush (up to `_FLUSH_EVERY_N_WRITES - 1 = 19`) are silently discarded. Compare with [`geography.py:189-198`](../backend/geography.py#L189-L198), which correctly flushes first and then *merges* rather than replacing.
- **Reproduction**: Issue 1–19 `/recommend` requests just before midnight Chicago time so they fall within the same flush window. At midnight, the next request triggers the rollover branch and the unflushed counts are lost.
- **Suggested Fix**: Mirror the `geography.py` pattern — flush `_counts` to disk if `_writes_since_flush > 0`, then read disk into `new_counts`, then merge with `_counts` preserving in-memory rows the disk lacks (e.g. `for d, v in new_counts.items(): if d not in _counts: _counts[d] = v`).

---

### BUG-005 · 🟡 Day-rollover loses unflushed `devices` increments
- **File**: [backend/devices.py](../backend/devices.py#L96-L101)
- **Line(s)**: 96–101
- **Severity**: Medium
- **Description**: Same root cause as BUG-004. `record_visit()` reloads from disk via `_counts.clear()` + `_counts.update(new_counts)` on day rollover without first flushing pending writes. Up to 19 device-classification increments from the previous day can be lost on each rollover.
- **Reproduction**: Same as BUG-004 — issue analytics-eligible requests in the final flush window of the day.
- **Suggested Fix**: Flush-first-then-merge; copy the pattern from `geography.py:189-198`.

---

### BUG-006 · 🟡 Day-rollover loses unflushed `referrers` increments
- **File**: [backend/referrers.py](../backend/referrers.py#L124-L129)
- **Line(s)**: 124–129
- **Severity**: Medium
- **Description**: Same pattern as BUG-004 / BUG-005. `record_visit()` clears and replaces `_counts` from disk on day rollover, dropping up to 19 unflushed referrer-bucket increments. The hostname long-tail in the `other` bucket is also subject to loss.
- **Reproduction**: Same as BUG-004.
- **Suggested Fix**: Flush-first-then-merge; copy the `geography.py:189-198` pattern.

---

### BUG-007 · 🟡 Day-rollover loses unflushed `events` increments
- **File**: [backend/events.py](../backend/events.py#L90-L95)
- **Line(s)**: 90–95
- **Severity**: Medium
- **Description**: Same root cause as BUG-004 through BUG-006. `record()` reloads from disk on day rollover without first flushing pending writes, losing up to 19 named-event counts (e.g. `recommend_submitted`, `route_selected`, `trip_completed`) from the previous day. Because events are the headline funnel metric, lost counts directly distort the public dashboard's "recommendations served / sessions" rate at the day boundary.
- **Reproduction**: Fire a few allowlisted events via `POST /events` during the final flush window before midnight Chicago.
- **Suggested Fix**: Flush-first-then-merge; copy the `geography.py:189-198` pattern.

---

### BUG-008 · 🟡 Bus+bus transfer route totals understated by `TRANSFER_PENALTY_MINUTES`
- **File**: [backend/main.py](../backend/main.py#L838-L842)
- **Line(s)**: main.py 838–842 (interacts with [`_apply_transfer_wait_estimates`](../backend/main.py#L455-L487) and [`find_bus_transfer_routes`](../backend/transit_graph.py#L2085-L2215))
- **Severity**: Medium
- **Description**: `find_bus_transfer_routes()` returns `sort_key = total_no_wait + wait_min_A + _LEG2_WAIT_ESTIMATE` where `_LEG2_WAIT_ESTIMATE = TRANSFER_PENALTY_MINUTES = 3`. In `_run_routing`, the post-walk-scaling rebuild on lines 838–842 replaces the total with `route.total_minutes_no_wait + (w or 0)` — silently dropping the 3-min leg-2 estimate. Then `_apply_transfer_wait_estimates()` runs and assumes the estimate IS in the total: `adjusted = total - route.transfers * TRANSFER_PENALTY_MINUTES + (live or fallback)`. Net result for bus+bus routes (`transfers == 1`):
  - Without live data: `adjusted = total - 3 + 3 = total` (should be `total + 3`)
  - With live data: `adjusted = total - 3 + live` (should be `total + live`)

  Either way, bus+bus transfer routes appear ~3 minutes faster than they should, both in ranking and in the displayed `total_minutes`. They will out-rank otherwise-equivalent train/intermodal routes that correctly include the leg-2 estimate.
- **Reproduction**: Submit a `/recommend` for an origin/destination pair where `find_bus_transfer_routes()` returns at least one candidate. Compare the displayed `total_minutes` against the sum of leg minutes plus first-leg wait — the on-screen total will be 3 minutes lower than the legs sum to.
- **Suggested Fix**: Either (a) keep the leg-2 estimate in the rebuilt total: `(route.total_minutes_no_wait + (w or 0) + TRANSFER_PENALTY_MINUTES, ...)`, OR (b) special-case bus+bus routes in `_apply_transfer_wait_estimates` so the subtraction step is skipped when the total never included the penalty. Option (a) is the smaller change and keeps ranking consistent across all route shapes.

---

### BUG-009 · 🟢 `find_bus_transfer_routes` docstring says 7.5-min leg-2 wait, code uses 3
- **File**: [backend/transit_graph.py](../backend/transit_graph.py#L2247-L2248)
- **Line(s)**: 2247–2248 (docstring) vs [2085](../backend/transit_graph.py#L2085) (constant)
- **Severity**: Low
- **Description**: The docstring states "Sorting key includes a fixed 7.5-min estimate for the leg-2 wait (half of a typical 15-min CTA headway)." but `_LEG2_WAIT_ESTIMATE = TRANSFER_PENALTY_MINUTES`, which evaluates to 3.0 (per [utils.py:14](../backend/utils.py#L14)). The 7.5-min figure in the docstring is stale — there is no 7.5 anywhere in the code path.
- **Reproduction**: Read the docstring vs the constant value.
- **Suggested Fix**: Update the docstring to match the actual 3-min estimate, or change `_LEG2_WAIT_ESTIMATE` to 7.5 if that better matches CTA bus headways. If the value is changed, the BUG-008 fix should still keep the constant consistent across the rebuild and the apply step.

---


## Bug Scan — 2026-05-07 (backend)

> Scanned: `backend/` — `events.py`, `analytics_store.py`, `utils.py`, `sessions.py`, `rate_limit.py`, `main.py`, `dau.py`, `geography.py`, `funnel.py`, `middleware.py`, `devices.py`, `retention.py`, `cta_client.py`, `weather_service.py`, `route_scoring.py`, `walking.py`, `routes/admin.py`, `routes/stats.py`, `active_routes.py`, `hourly.py`, `referrers.py`, `prompt_builder.py`, `public_stats.py`, `gtfs_loader.py`, `transit_graph.py` (skim). Focus on logic, runtime, and integration bugs not already in this file.
> Found: 5 bug(s) — 2 🟡 Medium, 3 🟢 Low. **All resolved 2026-05-07** — see `docs/archive/RESOLVED_HISTORY.md`.

---
