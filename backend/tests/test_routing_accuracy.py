"""
End-to-end routing accuracy suite (TD-BE-005, layer 1: golden fixtures).

================================================================================
  STATUS — REQUIRES HUMAN AUTHORING
================================================================================
This file is a **scaffold only**. The determinism harness it depends on
(`routing_harness.py`) is complete and covered by 7 passing smoke tests,
but the golden-route fixtures themselves are NOT YET AUTHORED.

A human with Chicago rider knowledge must fill in the OD pairs before
this suite provides any regression protection. Claude (or any tool
without local Chicago knowledge) cannot author these correctly — the
fixtures encode judgment calls about what counts as the "right" route,
and those calls must come from someone who actually rides the system.

Every placeholder test below is marked `@pytest.mark.skip` so CI does
not red-light on a stub. Each skip marker should be removed only when
the OD coordinates and expected shape have been filled in.

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
it. Capture coordinates by:

  - Google Maps right-click → "What's here?" → copy the lat/lon.
  - Or pull a known stop's lat/lon from `backend/gtfs_data/stops.txt`.

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

from .routing_harness import RoutingScenario, run_scenario


# Representative weekday-midday moment used by fixtures that don't need
# a specific time. Pick something far enough into the future that the
# bundled GTFS feed is still active when the test is read, but not so
# far that the active service_id rotates off the calendar. If fixtures
# start returning empty results after a GTFS refresh, bump this date.
WEEKDAY_MIDDAY = datetime(2026, 6, 16, 14, 30, 0, tzinfo=CHICAGO_TZ)  # Tuesday 2:30 PM


# ---------------------------------------------------------------------------
# PLACEHOLDER FIXTURES — every test below requires a human to fill in OD
# coordinates and remove the skip marker. See the authoring guide above.
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="TD-BE-005 layer 1: awaiting human-authored OD coords (see module docstring)")
@pytest.mark.asyncio
async def test_logan_square_to_hyde_park_prefers_blue_then_red():
    """Train+train transfer fixture — PLACEHOLDER.

    Rider-level expectation: from Logan Square (Blue Line) to Hyde Park
    (Red Line area), the routing engine should pick Blue→Red over any
    bus-heavy alternative. This is one of the most-mentioned "obvious"
    transfers in Chicago — if the engine ever stops preferring it,
    something has gone wrong upstream.

    To author: replace the (0.0, 0.0) coords with the actual Logan
    Square Blue Line stop and a Hyde Park destination (e.g. 53rd & S
    Lake Park, or a U of C address). See authoring guide step 2.
    """
    scenario = RoutingScenario(
        frozen_at=WEEKDAY_MIDDAY,
        origin=(0.0, 0.0),   # TODO(human): Logan Square coords (lat, lon)
        dest=(0.0, 0.0),     # TODO(human): Hyde Park coords (lat, lon)
        description="Logan Square → Hyde Park should prefer Blue→Red over a 3-bus chain",
    )
    result = await run_scenario(scenario)
    assert result.primary_modes == ["train", "train"]
    assert result.lines == ["Blue Line", "Red Line"]
    assert result.transfers == 1


@pytest.mark.skip(reason="TD-BE-005 layer 1: awaiting human-authored OD coords (see module docstring)")
@pytest.mark.asyncio
async def test_single_line_train_no_transfers():
    """Single-line train fixture — PLACEHOLDER.

    Rider-level expectation: two points both clearly served by the
    same train line should produce a one-line route with zero
    transfers (e.g. Belmont → Roosevelt, both Red Line).

    To author: pick two well-known stops on the same line. See
    authoring guide step 2.
    """
    scenario = RoutingScenario(
        frozen_at=WEEKDAY_MIDDAY,
        origin=(0.0, 0.0),   # TODO(human): origin coords on a single train line
        dest=(0.0, 0.0),     # TODO(human): dest coords on the same line
        description="Two stops on the same line should not introduce a transfer",
    )
    result = await run_scenario(scenario)
    assert result.transfers == 0
    assert len(set(result.lines)) == 1


@pytest.mark.skip(reason="TD-BE-005 layer 1: awaiting human-authored OD coords (see module docstring)")
@pytest.mark.asyncio
async def test_walk_only_short_hop_has_no_transit_legs():
    """Walk-only fixture — PLACEHOLDER.

    Rider-level expectation: when origin and destination are 3 blocks
    apart, the engine should return a walk-only route — no transit
    legs, no transfers.

    To author: pick two points <0.5 miles apart. See authoring guide
    step 2.
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
