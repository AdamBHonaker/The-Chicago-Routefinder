"""
End-to-end routing accuracy suite (TD-BE-005, layer 1: golden fixtures).

================================================================================
  STATUS — REQUIRES HUMAN AUTHORING
================================================================================
This file is a **scaffold only**. The determinism harness it depends on
(`routing_harness.py`) is complete and covered by 7 passing smoke tests,
but the golden-route fixtures themselves are NOT YET AUTHORED.

A human with Chicago rider knowledge must verify the OD pairs and
assertions before this suite provides any regression protection.
Claude (or any tool without local Chicago knowledge) cannot author
these correctly — the fixtures encode judgment calls about what
counts as the "right" route, and those calls must come from someone
who actually rides the system.

To make finishing this less painful, two scaffolding pieces ship
alongside this file:

  - `backend/tests/known_stops.py`       — every CTA L parent station
                                           pre-loaded as a named
                                           (lat, lon) constant.
  - `backend/scripts/probe_route.py`     — CLI that runs one scenario
                                           and prints the engine's
                                           output in the shape this
                                           suite asserts on, so an
                                           author can sanity-check a
                                           candidate fixture before
                                           pinning an assertion.

Every placeholder test below is marked `@pytest.mark.skip` so CI does
not red-light on a stub. Each skip marker should be removed only when
the OD coordinates are pinned AND the expected shape has been
verified against rider-level intent — not just against whatever the
engine returns today.

================================================================================
  AUTHORING GUIDE — what a human author must do
================================================================================

## 1. Pick the OD pairs to cover

Target ~10–15 fixtures total. At minimum, cover one fixture per
category below. Categories with multiple plausible fixtures benefit
from two or three each, picked to stress different parts of the graph.

  | Category                  | What it tests                                  | Example                                            |
  |---------------------------|------------------------------------------------|----------------------------------------------------|
  | Single-line train         | One train line, no transfer logic              | Belmont → Roosevelt on the Red Line                |
  | Train+train transfer      | Cross-line transfer is preferred over bus     | Logan Square → Hyde Park (Blue→Red)                |
  | Bus → train               | Intermodal: bus feeds into rail               | A residential stop far from L → downtown           |
  | Train → bus               | Intermodal in the other direction             | Loop → a residential bus-only neighborhood         |
  | Bus + bus transfer        | Bus-only transfer wins when no rail is near  | A North-South bus to an East-West bus              |
  | Walk-only short hop       | Walking beats transit for <0.5 mi             | Two coffee shops 3 blocks apart                    |
  | Edge-of-service-area      | Routing still succeeds at the city boundary   | Far NW side → far SE side                          |
  | Late-night service        | Reduced calendar (Owl service)                | Same OD as a daytime fixture, frozen_at=2:00 AM    |
  | Weekend service           | Saturday/Sunday calendar selection            | Same OD as a daytime fixture, on a Saturday        |

## 2. Pin OD coordinates (do not rely on the geocoder)

The geocoder is a separate moving part — fixtures must not depend on
it. Three options, in order of preference:

  1. **Use a constant from `known_stops.py`** (next to this file). It
     pre-loads every CTA L parent station from `gtfs_data/stops.txt`
     under a readable name:

         from .known_stops import KNOWN_STOPS

         origin = KNOWN_STOPS["LOGAN_SQUARE_BLUE"]
         dest   = KNOWN_STOPS["GARFIELD_RED"]

     If the station you want is missing, add it to `known_stops.py`
     (do NOT inline a one-off lat/lon when the station exists in GTFS).

  2. **Pull a specific bus stop's lat/lon** directly from
     `backend/gtfs_data/stops.txt` and paste it inline with a comment
     naming the stop_id and rider-level intent.

  3. **Google Maps right-click → "What's here?"** for a non-stop anchor
     (an address, a building entrance). Paste the lat/lon inline.

Coordinates are (lat, lon) — note the order matches the harness; both
positive lat and negative lon for Chicago (e.g. `(41.929, -87.708)`
for Logan Square Blue Line).

## 3. Pick `frozen_at` deliberately

The frozen instant determines which GTFS service calendar is active.
Picking the wrong moment is the single most common source of confusing
golden-test failures.

  - **Default** to `WEEKDAY_MIDDAY` (Tuesday 2:30 PM). Most fixtures
    should use this — full service is running, headways are short,
    and the result is most stable.
  - For Owl / late-night fixtures, pick a time between 1:00 AM and
    4:00 AM on a weekday. Many lines run sub-frequency or are
    suspended entirely — assertions must match reality at that hour.
  - For weekend fixtures, pick a Saturday or Sunday afternoon. The
    Saturday and Sunday service_ids differ from weekday and from each
    other; verify your assertion holds for the specific day chosen.

If `frozen_at` falls outside the bundled GTFS feed's calendar window,
the routing graph will have no active service and every fixture will
return an empty result. If that starts happening, refresh the feed
(`python backend/fetch_gtfs.py`) and bump `WEEKDAY_MIDDAY` forward to
a date still inside the new feed's calendar.

## 4. Decide whether to pass canned arrival data

Leave `train_arrivals=[]` and `bus_arrivals=[]` (the defaults) unless
the assertion specifically depends on a live-wait outcome. The graph
falls back to scheduled headways when no live data is provided, and
that scheduled-time path is what most golden assertions should
exercise — it's the most reproducible.

Pass canned arrivals only when you are encoding an assertion like
"when the Red Line is 12 min away and the Blue Line is 2 min away,
the Blue Line should win." See `routing_harness.stub_cta_arrivals`
for the expected dict shape (it matches what
`cta_client._fetch_station_arrivals` / `_fetch_bus_chunk` produce).

## 5. Assert on SHAPE, not minutes

`ScenarioResult` exposes four summary fields:

  - `primary_modes` — ordered list like `["train", "train"]`
  - `lines`         — ordered list like `["Blue Line", "Red Line"]`
  - `transfers`     — integer
  - `total_minutes` — float (do NOT assert on this in golden tests)

Assertions on `total_minutes` will flake every time the GTFS feed is
refreshed, because scheduled-time headways drift by a minute or two
between feed versions. Stick to `primary_modes`, `lines`, and
`transfers` — those are the shape signals that catch real regressions.

If a fixture needs to assert "this route is faster than that route,"
read from `result.all_routes_raw` (the full ranked list) and compare
the relative ordering, not absolute times.

## 6. Handle failures correctly

When a previously-passing fixture starts to fail:

  - **DO NOT** blindly update the expected `lines` / `transfers` to
    match the new output. That defeats the entire purpose of the
    suite.
  - **DO** read the diff that caused it. If a recent change to the
    routing engine, scoring, or graph construction was intentional
    and changed the right route, update the fixture and note the
    reason in the test docstring.
  - If the failure happens after a GTFS refresh and a schedule
    actually changed (a line was rerouted, a stop was closed), update
    the fixture and note the feed version.
  - If the failure has no clear cause, do not update the fixture —
    treat it as a real regression and investigate.

## 6.5. Probe the engine before pinning an assertion

Before you write the expected `primary_modes` / `lines` / `transfers`
for a new fixture, run the engine yourself and eyeball what it returns:

    python -m backend.scripts.probe_route \\
        --origin-stop LOGAN_SQUARE_BLUE \\
        --dest-stop   GARFIELD_RED

That script prints the ranked alternatives in the same shape this
suite asserts on. **Read the output critically** — if the engine's
top route disagrees with your rider-level expectation, do NOT just
copy the engine's answer into the test. That would encode whatever
bug the engine has today as the "correct" behavior. Investigate the
disagreement first; the fixture exists to catch exactly this kind of
silent drift.

## 7. Removing the skip markers

When a fixture is fully authored:

  - Replace the placeholder `(0.0, 0.0)` coordinates with real ones.
  - Update the `description` to reflect the actual asserted behavior.
  - Delete the `@pytest.mark.skip(...)` decorator.
  - Run the fixture locally to confirm it passes before committing.

A partially-authored fixture (real coords, but assertion not yet
confirmed against a local run) should keep its skip marker with the
reason updated to explain what verification step is still pending.

================================================================================
  CHECKLIST FOR A NEW FIXTURE
================================================================================
  [ ] Category from the table above is covered (or this is a second
      fixture in a category that benefits from more coverage)
  [ ] OD coordinates pinned (not geocoded)
  [ ] `frozen_at` chosen deliberately — weekday-midday default unless
      the fixture is specifically testing reduced-service calendars
  [ ] Assertions use `primary_modes` / `lines` / `transfers` —
      NOT `total_minutes`
  [ ] Test runs locally and passes
  [ ] `@pytest.mark.skip` removed
  [ ] Test function name and docstring describe the rider-level
      expectation in plain English

================================================================================
"""

from datetime import datetime

import pytest

from utils import CHICAGO_TZ

from .known_stops import KNOWN_STOPS
from .routing_harness import RoutingScenario, run_scenario


# Representative weekday-midday moment used by fixtures that don't need
# a specific time. Pick something far enough into the future that the
# bundled GTFS feed is still active when the test is read, but not so
# far that the active service_id rotates off the calendar. If fixtures
# start returning empty results after a GTFS refresh, bump this date.
WEEKDAY_MIDDAY = datetime(2026, 6, 16, 14, 30, 0, tzinfo=CHICAGO_TZ)  # Tuesday 2:30 PM


# ---------------------------------------------------------------------------
# PLACEHOLDER FIXTURES — each test below has a rider-level intent encoded in
# its docstring but its assertion is NOT YET VERIFIED. Two of the three have
# OD coordinates pinned from `known_stops.py` so a human author can probe
# them immediately (see authoring guide step 6.5). Each skip marker should
# only be removed after `probe_route.py` confirms the assertion matches
# rider-level expectation — not just whatever the engine currently returns.
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="TD-BE-005 layer 1: assertion needs human verification — run probe_route.py and confirm before un-skipping")
@pytest.mark.asyncio
async def test_logan_square_to_garfield_red_prefers_blue_then_red():
    """Train+train transfer fixture — PLACEHOLDER (coords pinned, assertion pending).

    Rider-level expectation: from Logan Square (Blue Line) to Garfield
    (Red Line, near Washington Park / U of C area), the routing engine
    should pick Blue→Red over any bus-heavy alternative. This is one
    of the most-mentioned "obvious" transfers in Chicago — if the
    engine ever stops preferring it, something has gone wrong upstream.

    To finish authoring:
      1. Run `python -m backend.scripts.probe_route
             --origin-stop LOGAN_SQUARE_BLUE --dest-stop GARFIELD_RED`.
      2. Confirm the best route is in fact ["Blue Line", "Red Line"]
         with one transfer. If it is, remove the skip marker. If it is
         NOT, do not "fix" the assertion — investigate the disagreement.
      3. Consider whether a destination closer to Hyde Park proper
         (e.g. 51ST_GREEN, or a non-station U-of-C address) better
         encodes the rider intent.
    """
    scenario = RoutingScenario(
        frozen_at=WEEKDAY_MIDDAY,
        origin=KNOWN_STOPS["LOGAN_SQUARE_BLUE"],
        dest=KNOWN_STOPS["GARFIELD_RED"],
        description="Logan Square → Garfield (Red) should prefer Blue→Red over a bus chain",
    )
    result = await run_scenario(scenario)
    assert result.primary_modes == ["train", "train"]
    assert result.lines == ["Blue Line", "Red Line"]
    assert result.transfers == 1


@pytest.mark.skip(reason="TD-BE-005 layer 1: assertion needs human verification — run probe_route.py and confirm before un-skipping")
@pytest.mark.asyncio
async def test_single_line_train_no_transfers():
    """Single-line train fixture — PLACEHOLDER (coords pinned, assertion pending).

    Rider-level expectation: Belmont (Red) → Roosevelt (Red) — both
    clearly on the Red Line — should produce a one-line route with
    zero transfers. This is the simplest possible "single-line"
    assertion; if it fails, the merge-consecutive-edges logic in
    `_path_to_route` has regressed.

    To finish authoring: run `python -m backend.scripts.probe_route
    --origin-stop BELMONT_RED --dest-stop ROOSEVELT` and confirm the
    output before un-skipping. Note: BELMONT_RED is the shared
    Red/Brown/Purple station; the routing engine may pick Brown or
    Purple Express depending on time of day. The assertion uses
    `set(result.lines)` to allow that flexibility but still catch a
    spurious transfer.
    """
    scenario = RoutingScenario(
        frozen_at=WEEKDAY_MIDDAY,
        origin=KNOWN_STOPS["BELMONT_RED"],
        dest=KNOWN_STOPS["ROOSEVELT"],
        description="Belmont → Roosevelt should ride one line without transferring",
    )
    result = await run_scenario(scenario)
    assert result.transfers == 0
    assert len(set(result.lines)) == 1


@pytest.mark.skip(reason="TD-BE-005 layer 1: assertion needs human verification — pick a non-station OD <0.5 mi apart and confirm with probe_route.py")
@pytest.mark.asyncio
async def test_walk_only_short_hop_has_no_transit_legs():
    """Walk-only fixture — PLACEHOLDER.

    Rider-level expectation: when origin and destination are 3 blocks
    apart, the engine should return a walk-only route — no transit
    legs, no transfers.

    To author: pick two points <0.5 miles apart. Do NOT use two
    KNOWN_STOPS entries — L stations 0.5 mi apart on the same line
    can still produce a one-stop train ride, which is correct but
    not what this fixture is meant to assert. Use addresses or
    specific bus stop_ids on a corridor without an L station nearby.
    """
    scenario = RoutingScenario(
        frozen_at=WEEKDAY_MIDDAY,
        origin=(0.0, 0.0),   # TODO(human): origin coords (lat, lon)
        dest=(0.0, 0.0),     # TODO(human): dest coords <0.5 mi from origin
        description="A short hop within walking distance should return a walk-only route",
    )
    result = await run_scenario(scenario)
    assert result.primary_modes == []
    assert result.transfers == 0
