"""
Determinism harness for end-to-end routing accuracy tests.

# Why this exists
# ---------------
# `find_routes()` / `find_bus_transfer_routes()` are non-deterministic in
# production because they read two live signals:
#   1. Wall-clock "now"   — picks the active GTFS service calendar
#                           (weekday vs. Saturday vs. Sunday vs. special),
#                           and is used to convert raw `arrT` timestamps
#                           into `arrives_in_minutes` integers.
#   2. CTA real-time APIs — `get_train_arrivals()` and `get_bus_arrivals()`
#                           hit lapi.transitchicago.com and ctabustracker.com
#                           and return different data every few seconds.
#
# A golden-route test like "Logan Square → Hyde Park should prefer
# Blue → Red over a 3-bus chain" must give the same answer in every CI run
# regardless of when CI runs. This module provides the two seams that make
# that possible:
#
#   - `frozen_chicago_now(dt)`           — freezes `datetime.now()` (and
#                                          `time.time()`) project-wide via
#                                          freezegun so service-calendar
#                                          selection is reproducible.
#   - `stub_cta_arrivals(...)`            — patches the two arrival-fetcher
#                                          coroutines that `main.recommend()`
#                                          awaits, so canned train and bus
#                                          arrivals replace the live API.
#   - `RoutingScenario` + `run_scenario` — convenience wrapper that bundles
#                                          a frozen moment, canned arrivals,
#                                          and an OD pair, then exercises
#                                          the real Chicago graph end-to-end
#                                          and returns a normalized result
#                                          suitable for golden assertions.
#
# Authoring golden fixtures themselves is intentionally **not** done here —
# those require rider judgment about Chicago routes (see TD-BE-005, layer 1).
# This module only provides the infrastructure that future golden tests
# will sit on top of.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Iterator
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from utils import CHICAGO_TZ


# ---------------------------------------------------------------------------
# Frozen "now"
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def frozen_chicago_now(when: datetime) -> Iterator[datetime]:
    """
    Freeze wall-clock time for the duration of the `with` block.

    `when` must be a timezone-aware datetime in `CHICAGO_TZ`. Inside the
    block, every call to `datetime.now(CHICAGO_TZ)`, `datetime.utcnow()`,
    and `time.time()` returns the same instant — across `main.py`,
    `cta_client.py`, `transit_graph.py`, and any other module that reads
    the clock.

    Yields the frozen datetime back so tests can use it in arrival
    fixtures (e.g. `arrT = when + timedelta(minutes=5)`).
    """
    if when.tzinfo is None:
        raise ValueError(
            "frozen_chicago_now requires a tz-aware datetime; "
            "pass datetime(..., tzinfo=CHICAGO_TZ)"
        )
    with freeze_time(when):
        yield when


# ---------------------------------------------------------------------------
# Canned CTA arrivals
# ---------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def stub_cta_arrivals(
    train_arrivals: list[dict] | None = None,
    bus_arrivals: list[dict] | None = None,
    n_train_errors: int = 0,
    n_bus_errors: int = 0,
) -> AsyncIterator[None]:
    """
    Patch `main.get_train_arrivals` and `main.get_bus_arrivals` so the
    code under test sees canned arrival data instead of hitting the live
    CTA APIs.

    Each canned arrival dict should match the shape produced by
    `cta_client._fetch_station_arrivals` / `cta_client._fetch_bus_chunk`
    — see those functions for the exact keys (`type`, `line_code`,
    `station_mapid`, `arrives_in_minutes`, etc. for trains; `route`,
    `stop_id`, `arrives_in_minutes`, `psgld`, etc. for buses).

    `n_*_errors` lets a fixture simulate partial API failures (the second
    element of the (arrivals, n_errors) tuple both fetchers return).

    Why patch at `main.*` and not `cta_client.*`?
    `main.py` does `from cta_client import get_train_arrivals, ...` —
    that binds names into `main`'s namespace. Patching `cta_client.get_*`
    would not affect the already-bound names inside `main`. We also patch
    `cta_client.*` so direct unit tests against the client see the stub.
    """
    train_arrivals = list(train_arrivals or [])
    bus_arrivals   = list(bus_arrivals or [])

    async def _fake_train(*_args, **_kwargs):
        return train_arrivals, n_train_errors

    async def _fake_bus(*_args, **_kwargs):
        return bus_arrivals, n_bus_errors

    with patch("main.get_train_arrivals", new=_fake_train), \
         patch("main.get_bus_arrivals",   new=_fake_bus), \
         patch("cta_client.get_train_arrivals", new=_fake_train), \
         patch("cta_client.get_bus_arrivals",   new=_fake_bus):
        yield


# ---------------------------------------------------------------------------
# Routing scenario bundle
# ---------------------------------------------------------------------------

@dataclass
class RoutingScenario:
    """
    A reproducible inputs bundle for one end-to-end routing assertion.

    `frozen_at` is the wall-clock instant the scenario simulates (used
    for service-calendar selection inside transit_graph).

    `origin` / `dest` are (lat, lon) tuples — production resolves these
    from text via `gtfs_loader.resolve_location()`, but golden tests
    should pin them to coordinates so the test does not depend on the
    geocoder.

    `train_arrivals` / `bus_arrivals` are the canned API responses;
    leave empty to simulate "no live data available" (the routing
    engine has graph-walk fallbacks).

    `description` is human-readable context surfaced in assertion
    failures — use it to record what real-Chicago expectation the
    scenario is encoding (e.g. "Logan Square → Hyde Park, midday
    Tuesday, expect Blue→Red transfer").
    """
    frozen_at: datetime
    origin: tuple[float, float]
    dest: tuple[float, float]
    description: str
    train_arrivals: list[dict] = field(default_factory=list)
    bus_arrivals: list[dict] = field(default_factory=list)
    n_routes: int = 3

    def __post_init__(self) -> None:
        if self.frozen_at.tzinfo is None:
            raise ValueError("RoutingScenario.frozen_at must be tz-aware")


@dataclass
class ScenarioResult:
    """
    Output of `run_scenario()`. Holds enough to express golden
    assertions without leaking internal Route object shape into tests.

    `primary_modes` is the ordered list of transit modes in the best
    route (e.g. ['train', 'train'] for a Blue→Red trip, ['bus'] for a
    bus-only trip, [] for walk-only).

    `lines` is the ordered list of human-readable lines/routes used in
    the best route — e.g. ['Blue Line', 'Red Line'] or ['66', '4'].

    `transfers` is `max(0, n_transit_legs - 1)`.

    `total_minutes` is the best route's total travel time (transit +
    walk, no wait penalty — matching `find_routes()`'s sort key).

    `all_routes_raw` retains the raw Route objects in case a test needs
    to drill deeper than the summary fields.
    """
    primary_modes: list[str]
    lines: list[str]
    transfers: int
    total_minutes: float
    all_routes_raw: list[Any]


# CTA train line_code values per `cta_client.LINE_NAMES`. Anything not in
# this set is treated as a bus route (numeric/short bus route IDs like
# "66", "X9", "N5"). Kept inline so this module does not pull cta_client
# at import time — golden tests should be able to summarize a route
# without touching the network-fetching module.
_TRAIN_LINE_CODES = frozenset({"Red", "Blue", "Brn", "G", "Org", "P", "Pink", "Y"})


def _leg_mode(leg: Any) -> str:
    """
    Classify a TransitLeg as 'train' or 'bus' from its `line_code`.

    Falls back to 'transit' if `line_code` is missing — that should not
    happen in production, but the fallback keeps `summarize_route` robust
    against future TransitLeg shape changes.
    """
    code = getattr(leg, "line_code", None)
    if code is None:
        return "transit"
    return "train" if code in _TRAIN_LINE_CODES else "bus"


def summarize_route(route: Any) -> tuple[list[str], list[str], int, float]:
    """
    Reduce a Route object to (modes, lines, transfers, total_minutes).

    Kept in this module rather than on `Route` itself so the golden
    suite controls its own assertion shape — changes to `Route`'s
    internals don't silently shift golden expectations.

    `modes` is derived from `TransitLeg.line_code` against the known set
    of CTA train line codes — train codes produce "train", everything
    else produces "bus". `total_minutes` reads `Route.total_minutes_no_wait`
    (the property, not a bare attribute) so it matches what `find_routes`
    sorts on. Golden tests should still NOT assert on `total_minutes`
    — see the authoring guide in `test_routing_accuracy.py`.
    """
    transit_legs = [
        leg for leg in route.legs
        if getattr(leg, "__class__", type(None)).__name__ == "TransitLeg"
    ]
    modes = [_leg_mode(leg) for leg in transit_legs]
    lines = [getattr(leg, "line", "") for leg in transit_legs]
    transfers = max(0, len(transit_legs) - 1)
    total = float(
        getattr(route, "total_minutes_no_wait", None)
        or getattr(route, "total_minutes", 0.0)
    )
    return modes, lines, transfers, total


async def run_scenario(scenario: RoutingScenario) -> ScenarioResult:
    """
    Execute one scenario against the real Chicago graph.

    Loads `transit_graph` (which reads `backend/gtfs_data/`), freezes
    time, stubs the CTA fetchers, and calls `find_routes()` with the
    scenario's OD pair. Returns a `ScenarioResult` summarizing the best
    route.

    Bus-to-bus transfer routes (which production gets from
    `find_bus_transfer_routes()`) are intentionally not merged in here —
    if a golden assertion needs to cover that path, write a dedicated
    helper that calls `find_bus_transfer_routes()` directly. Keeping
    `run_scenario()` focused on `find_routes()` matches how the two
    functions are tested separately at the invariant layer
    (TD-BE-005 layer 2, `test_graph_construction.py`).
    """
    # Imported lazily so `transit_graph` (which reads gtfs_data at import
    # time) is not loaded when this module is merely inspected.
    from transit_graph import find_routes

    with frozen_chicago_now(scenario.frozen_at):
        async with stub_cta_arrivals(
            train_arrivals=scenario.train_arrivals,
            bus_arrivals=scenario.bus_arrivals,
        ):
            routes = find_routes(
                origin_lat=scenario.origin[0],
                origin_lon=scenario.origin[1],
                dest_lat=scenario.dest[0],
                dest_lon=scenario.dest[1],
                n_routes=scenario.n_routes,
            )

    if not routes:
        return ScenarioResult(
            primary_modes=[],
            lines=[],
            transfers=0,
            total_minutes=0.0,
            all_routes_raw=[],
        )

    modes, lines, transfers, total = summarize_route(routes[0])
    return ScenarioResult(
        primary_modes=modes,
        lines=lines,
        transfers=transfers,
        total_minutes=total,
        all_routes_raw=list(routes),
    )


# ---------------------------------------------------------------------------
# Smoke tests for the harness itself
# ---------------------------------------------------------------------------

class TestFrozenChicagoNow:
    """Sanity checks that freezegun is wired correctly."""

    def test_freezes_datetime_now(self):
        target = datetime(2026, 6, 15, 14, 30, 0, tzinfo=CHICAGO_TZ)
        with frozen_chicago_now(target):
            assert datetime.now(CHICAGO_TZ).replace(microsecond=0) == target

    def test_rejects_naive_datetime(self):
        with pytest.raises(ValueError):
            with frozen_chicago_now(datetime(2026, 6, 15, 14, 30, 0)):
                pass


class TestStubCtaArrivals:
    """Sanity checks that arrival fetchers are patched in `main`'s namespace."""

    @pytest.mark.asyncio
    async def test_patches_main_get_train_arrivals(self):
        import main
        canned = [{"type": "train", "line_code": "Blue", "arrives_in_minutes": 4}]
        async with stub_cta_arrivals(train_arrivals=canned):
            result, n_err = await main.get_train_arrivals([], "fake-key")
        assert result == canned
        assert n_err == 0

    @pytest.mark.asyncio
    async def test_patches_main_get_bus_arrivals_with_errors(self):
        import main
        canned = [{"type": "bus", "route": "66", "arrives_in_minutes": 2}]
        async with stub_cta_arrivals(bus_arrivals=canned, n_bus_errors=2):
            result, n_err = await main.get_bus_arrivals([], "fake-key")
        assert result == canned
        assert n_err == 2

    @pytest.mark.asyncio
    async def test_patch_unwinds_after_block(self):
        import main
        original = main.get_train_arrivals
        async with stub_cta_arrivals(train_arrivals=[]):
            pass
        assert main.get_train_arrivals is original


class TestRoutingScenario:
    def test_post_init_rejects_naive_datetime(self):
        with pytest.raises(ValueError):
            RoutingScenario(
                frozen_at=datetime(2026, 6, 15, 14, 30, 0),
                origin=(41.92, -87.70),
                dest=(41.79, -87.59),
                description="naive tz should fail",
            )

    def test_defaults_to_empty_arrivals(self):
        scenario = RoutingScenario(
            frozen_at=datetime(2026, 6, 15, 14, 30, 0, tzinfo=CHICAGO_TZ),
            origin=(41.92, -87.70),
            dest=(41.79, -87.59),
            description="no live data",
        )
        assert scenario.train_arrivals == []
        assert scenario.bus_arrivals == []
        assert scenario.n_routes == 3
