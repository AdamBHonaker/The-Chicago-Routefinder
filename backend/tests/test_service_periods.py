"""
Tests for the service-period graph variant machinery in transit_graph.py
(BUG-051).

Covers:
  _select_period
    - Each clock window resolves to its expected period name
    - Owl period covers post-22:00 and pre-05:00 every day
    - Weekend wins over weekday on Sat/Sun (except owl hours)
    - Naive datetimes are treated as Chicago-local
    - tz-aware datetimes get converted to Chicago time
    - None resolves via datetime.now(CHICAGO_TZ)

  _periods_for_trip
    - Weekday trip starting at noon → weekday_midday only
    - Weekday trip starting at GTFS 25:30 (= 01:30 next-day) → owl only,
      because day_offset=1 shifts the run-day onto a different calendar day
    - Weekend trip starting at noon → weekend only
    - Daily owl trip starting at 03:00 → owl (every-day period)

  _select_representative_trips
    - Filters trips by period — wrong-period trips are excluded
    - Picks longest sequence; tie-breaks by closeness to period.target_min
    - Bus rep selection: closest to period.target_min wins

  _build_graph (variant-aware)
    - Building two different periods yields distinct cached graphs
    - The same period twice returns the same (cached) graph object
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import transit_graph
from transit_graph import (
    _select_period,
    _periods_for_trip,
    _select_representative_trips,
    _CanonicalTripData,
    _build_graph,
    _PERIODS,
)
from utils import CHICAGO_TZ


# ---------------------------------------------------------------------------
# _select_period
# ---------------------------------------------------------------------------

class TestSelectPeriod:
    """All datetimes here are Chicago-local; weekday() is Python-standard:
    0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun."""

    def test_weekday_peak_am(self):
        # Wed 08:00
        assert _select_period(datetime(2026, 5, 13, 8, 0)) == "weekday_peak"

    def test_weekday_peak_pm(self):
        # Wed 17:00
        assert _select_period(datetime(2026, 5, 13, 17, 0)) == "weekday_peak"

    def test_weekday_midday(self):
        # Wed 12:00
        assert _select_period(datetime(2026, 5, 13, 12, 0)) == "weekday_midday"

    def test_weekday_evening(self):
        # Wed 20:30
        assert _select_period(datetime(2026, 5, 13, 20, 30)) == "weekday_evening"

    def test_weekend_midday(self):
        # Sat 13:00
        assert _select_period(datetime(2026, 5, 16, 13, 0)) == "weekend"
        # Sun 13:00
        assert _select_period(datetime(2026, 5, 17, 13, 0)) == "weekend"

    def test_owl_wraps_midnight(self):
        # Sat 03:00 — owl wins over weekend because owl is checked first
        assert _select_period(datetime(2026, 5, 16, 3, 0)) == "owl"
        # Wed 23:30
        assert _select_period(datetime(2026, 5, 13, 23, 30)) == "owl"
        # Sat 22:00 — boundary, owl
        assert _select_period(datetime(2026, 5, 16, 22, 0)) == "owl"

    def test_owl_endpoint_05_00_is_not_owl(self):
        # 05:00 sharp is no longer owl; it's morning service.
        # Weekday → midday (since 05:00 is pre-peak; covered by fallback).
        assert _select_period(datetime(2026, 5, 13, 5, 0)) == "weekday_midday"
        # Weekend → weekend
        assert _select_period(datetime(2026, 5, 16, 5, 0)) == "weekend"

    def test_naive_treated_as_chicago_local(self):
        # No tzinfo → assumed Chicago-local.
        assert _select_period(datetime(2026, 5, 13, 8, 0)) == "weekday_peak"

    def test_aware_converted_to_chicago(self):
        # 13:00 UTC on Wed 2026-05-13 = 08:00 CDT (Chicago is UTC-5 in May).
        dt_utc = datetime(2026, 5, 13, 13, 0, tzinfo=timezone.utc)
        assert _select_period(dt_utc) == "weekday_peak"

    def test_none_resolves_to_now(self):
        # The behavior with None should depend only on wall-clock; test that
        # it returns one of the known periods rather than crashing.
        period = _select_period(None)
        assert period in _PERIODS


# ---------------------------------------------------------------------------
# _periods_for_trip
# ---------------------------------------------------------------------------

class TestPeriodsForTrip:
    WEEKDAY_SIDS = {
        0: frozenset({"WK"}), 1: frozenset({"WK"}), 2: frozenset({"WK"}),
        3: frozenset({"WK"}), 4: frozenset({"WK"}),
        5: frozenset(), 6: frozenset(),
    }
    WEEKEND_SIDS = {
        i: frozenset() for i in range(5)
    } | {5: frozenset({"WE"}), 6: frozenset({"WE"})}
    DAILY_SIDS = {i: frozenset({"D"}) for i in range(7)}

    def test_weekday_noon_trip(self):
        # 720 = 12:00 → weekday_midday only.
        assert _periods_for_trip(720.0, "WK", self.WEEKDAY_SIDS) == {"weekday_midday"}

    def test_weekday_peak_am_trip(self):
        # 480 = 08:00 → weekday_peak only.
        assert _periods_for_trip(480.0, "WK", self.WEEKDAY_SIDS) == {"weekday_peak"}

    def test_weekday_late_evening_trip(self):
        # 1230 = 20:30 → weekday_evening only.
        assert _periods_for_trip(1230.0, "WK", self.WEEKDAY_SIDS) == {"weekday_evening"}

    def test_weekday_post_midnight_trip_lands_in_owl(self):
        # GTFS 25:30 = 1530 min → normalized 90 (01:30) and day_offset 1.
        # Weekday service shifted by +1 day → Tue,Wed,Thu,Fri,Sat. Owl applies
        # to every day, so the trip ends up in the owl variant — exactly the
        # post-midnight tail that the pre-BUG-051 engine lost.
        assert _periods_for_trip(1530.0, "WK", self.WEEKDAY_SIDS) == {"owl"}

    def test_weekend_noon_trip(self):
        # Sat 12:00 → weekend only.
        assert _periods_for_trip(720.0, "WE", self.WEEKEND_SIDS) == {"weekend"}

    def test_weekend_late_night_trip_lands_in_owl(self):
        # Sat 23:30 → owl (every-day period wins clock-wise).
        assert _periods_for_trip(1410.0, "WE", self.WEEKEND_SIDS) == {"owl"}

    def test_daily_owl_trip(self):
        # 180 = 03:00, daily service → owl only.
        assert _periods_for_trip(180.0, "D", self.DAILY_SIDS) == {"owl"}

    def test_unknown_sid_returns_empty(self):
        assert _periods_for_trip(720.0, "BOGUS", self.WEEKDAY_SIDS) == set()


# ---------------------------------------------------------------------------
# _select_representative_trips
# ---------------------------------------------------------------------------

def _make_canonical_data(
    *,
    train_seqs=None,
    train_first=None,
    train_route=None,
    train_dir=None,
    train_sid=None,
    bus_seqs=None,
    bus_first=None,
    bus_route=None,
    bus_dir=None,
    bus_sid=None,
    bus_route_map=None,
):
    return _CanonicalTripData(
        parent_stations={},
        platform_to_parent={},
        bus_route_map=bus_route_map or {},
        bus_stop_lookup={},
        train_seqs=train_seqs or {},
        train_first_dep=train_first or {},
        train_trip_route=train_route or {},
        train_trip_dir=train_dir or {},
        train_trip_sid=train_sid or {},
        bus_seqs=bus_seqs or {},
        bus_first_dep=bus_first or {},
        bus_trip_route=bus_route or {},
        bus_trip_dir=bus_dir or {},
        bus_trip_sid=bus_sid or {},
    )


class TestSelectRepresentativeTrips:

    @pytest.fixture(autouse=True)
    def _reset_canonical_midday_reps(self):
        # OPT-002 stashes the canonical midday rep selection in a process-wide
        # cache (transit_graph._canonical_midday_reps). When an earlier test
        # in the suite triggers warm_up() against the real CTA feed, the cache
        # holds production data and _select_representative_trips short-circuits
        # to it for the default (weekday_midday) period — overriding the
        # synthetic fixtures these tests construct. Clear before and after
        # each test so the class behaves identically regardless of collection
        # order.
        previous = transit_graph._canonical_midday_reps
        transit_graph._canonical_midday_reps = None
        try:
            yield
        finally:
            transit_graph._canonical_midday_reps = previous

    def _seed_weekday_only(self, monkeypatch):
        """Patch _load_service_ids_by_day to a fixed weekday-only mapping."""
        sids = {
            0: frozenset({"WK"}), 1: frozenset({"WK"}), 2: frozenset({"WK"}),
            3: frozenset({"WK"}), 4: frozenset({"WK"}),
            5: frozenset(), 6: frozenset(),
        }
        # Clear cache + patch so each test gets the fixture mapping.
        transit_graph._load_service_ids_by_day.cache_clear()
        monkeypatch.setattr(transit_graph, "_load_service_ids_by_day", lambda: sids)

    def test_filters_out_wrong_period(self, monkeypatch):
        self._seed_weekday_only(monkeypatch)
        data = _make_canonical_data(
            train_seqs={"T_midday": [("40100", 720.0), ("40200", 725.0)],
                        "T_owl":    [("40100", 1530.0), ("40200", 1535.0)]},
            train_first={"T_midday": 720.0, "T_owl": 1530.0},
            train_route={"T_midday": "Red", "T_owl": "Red"},
            train_dir={"T_midday": "0", "T_owl": "0"},
            train_sid={"T_midday": "WK", "T_owl": "WK"},
        )
        # Midday variant: only T_midday qualifies (T_owl belongs to owl).
        midday_train, _ = _select_representative_trips(data, "weekday_midday")
        assert "T_midday" in midday_train
        assert "T_owl" not in midday_train

        # Owl variant: only T_owl qualifies.
        owl_train, _ = _select_representative_trips(data, "owl")
        assert "T_owl" in owl_train
        assert "T_midday" not in owl_train

    def test_picks_longest_then_closest_to_target(self, monkeypatch):
        self._seed_weekday_only(monkeypatch)
        # Three weekday-midday-eligible trips on the same (route, dir):
        #   T_short   — 2 stops, starts 11:30 (closer to target 12:00)
        #   T_long_a  — 3 stops, starts 13:00
        #   T_long_b  — 3 stops, starts 11:50 (closer to target than T_long_a)
        # Expected: T_long_b — longest sequence beats short trips, and
        # within the longest-tied group the one closer to target wins.
        data = _make_canonical_data(
            train_seqs={
                "T_short":  [("40100", 690.0), ("40200", 695.0)],
                "T_long_a": [("40100", 780.0), ("40200", 785.0), ("40300", 790.0)],
                "T_long_b": [("40100", 710.0), ("40200", 715.0), ("40300", 720.0)],
            },
            train_first={"T_short": 690.0, "T_long_a": 780.0, "T_long_b": 710.0},
            train_route={k: "Red" for k in ("T_short", "T_long_a", "T_long_b")},
            train_dir={k: "0" for k in ("T_short", "T_long_a", "T_long_b")},
            train_sid={k: "WK" for k in ("T_short", "T_long_a", "T_long_b")},
        )
        selected, _ = _select_representative_trips(data, "weekday_midday")
        # The longest trip closest to noon (T_long_b) is the sole rep
        # for (Red, 0); the other two are pruned.
        assert "T_long_b" in selected
        assert selected["T_long_b"] == ("Red", "0")
        assert "T_short" not in selected
        assert "T_long_a" not in selected

    def test_bus_rep_closest_to_target(self, monkeypatch):
        self._seed_weekday_only(monkeypatch)
        # Bus rep selection uses min(|first_dep - target|), no length tie-break.
        # Midday target is 720; B_close starts 730, B_far starts 600.
        bus_stop_seq_close = [("1234", "Clark", 41.94, -87.65, 730.0)]
        bus_stop_seq_far   = [("1234", "Clark", 41.94, -87.65, 600.0)]
        data = _make_canonical_data(
            bus_seqs={"B_close": bus_stop_seq_close, "B_far": bus_stop_seq_far},
            bus_first={"B_close": 730.0, "B_far": 600.0},
            bus_route={"B_close": "22", "B_far": "22"},
            bus_dir={"B_close": "0", "B_far": "0"},
            bus_sid={"B_close": "WK", "B_far": "WK"},
            bus_route_map={"22": "22"},
        )
        _, bus_for_period = _select_representative_trips(data, "weekday_midday")
        # ("22", "0") sequence = the close trip's sequence (730 closer to 720 than 600).
        assert bus_for_period[("22", "0")] == bus_stop_seq_close


# ---------------------------------------------------------------------------
# _build_graph variant caching
# ---------------------------------------------------------------------------

class TestBuildGraphVariantCache:
    """The unified _build_graph(period_name) entrypoint caches per-period
    graphs in _variant_graphs. Same name returns the same object; different
    names produce distinct graphs."""

    def test_unknown_period_falls_back_to_default(self):
        # Don't actually build a fixture here — just ensure the lookup
        # path normalizes unknown names. Patch _build_graph itself so we
        # observe the period name resolution without triggering a real
        # GTFS load.
        with patch.object(transit_graph, "_variant_graphs", {}), \
             patch.object(transit_graph, "_load_canonical_trip_data") as load, \
             patch.object(transit_graph, "_select_representative_trips") as sel, \
             patch.object(transit_graph, "_assemble_graph") as asm:
            load.return_value = _make_canonical_data()
            sel.return_value = ({}, {})
            asm.return_value = object()  # any sentinel
            # Unknown name → routed to _DEFAULT_PERIOD ("weekday_midday").
            transit_graph._build_graph("not_a_real_period")
            # _select_representative_trips called with the default period.
            sel.assert_called_once()
            assert sel.call_args[0][1] == transit_graph._DEFAULT_PERIOD

    def test_same_period_returns_cached_object(self):
        with patch.object(transit_graph, "_variant_graphs", {}), \
             patch.object(transit_graph, "_load_canonical_trip_data") as load, \
             patch.object(transit_graph, "_select_representative_trips") as sel, \
             patch.object(transit_graph, "_assemble_graph") as asm:
            sentinel_data = _make_canonical_data()
            sentinel_data.parent_stations = {"40100": {"name": "x", "lat": 0, "lon": 0}}
            load.return_value = sentinel_data
            sel.return_value = ({}, {})
            sentinel_graph = object()
            asm.return_value = sentinel_graph

            G1, _ = transit_graph._build_graph("weekday_peak")
            G2, _ = transit_graph._build_graph("weekday_peak")
            assert G1 is G2
            # _assemble_graph called only once — second call is a cache hit.
            assert asm.call_count == 1

    def test_different_periods_produce_distinct_graphs(self):
        with patch.object(transit_graph, "_variant_graphs", {}), \
             patch.object(transit_graph, "_load_canonical_trip_data") as load, \
             patch.object(transit_graph, "_select_representative_trips") as sel, \
             patch.object(transit_graph, "_assemble_graph") as asm:
            load.return_value = _make_canonical_data()
            sel.return_value = ({}, {})
            # Different sentinel per call so we can tell them apart.
            results = [object(), object()]
            asm.side_effect = results

            G_peak, _ = transit_graph._build_graph("weekday_peak")
            G_owl,  _ = transit_graph._build_graph("owl")
            assert G_peak is results[0]
            assert G_owl  is results[1]
            assert G_peak is not G_owl


# ---------------------------------------------------------------------------
# BUG-051 acceptance — find_routes_with_status dispatches by departure_time
# ---------------------------------------------------------------------------

class TestFindRoutesDepartureTimeDispatch:
    """
    Acceptance check for the BUG-051 entry: a query at 12:00 PM Wed and a
    query at 03:00 AM Sat for the same O/D pair must resolve to different
    service-period variants. Pre-BUG-051 both queries fell on the single
    fixed-noon graph; post-fix they get distinct graphs.

    These tests don't run real routing — they verify that find_routes_with_
    status picks the right variant by inspecting which period name is passed
    through to _build_graph.
    """

    def test_wednesday_noon_selects_midday_variant(self):
        from transit_graph import find_routes_with_status
        import networkx as nx
        G = nx.DiGraph()
        stations = {}
        captured = {}

        def fake_build(period_name=None):
            captured["period"] = period_name
            return G, stations

        with patch.object(transit_graph, "_build_graph", side_effect=fake_build), \
             patch.object(transit_graph, "find_nearest_train_stations", return_value=[]), \
             patch.object(transit_graph, "find_nearest_bus_stops", return_value=[]):
            find_routes_with_status(
                42.019, -87.672, 41.885, -87.628,
                departure_time=datetime(2026, 5, 13, 12, 0),  # Wed noon
            )
        assert captured["period"] == "weekday_midday"

    def test_saturday_03_00_selects_owl_variant(self):
        from transit_graph import find_routes_with_status
        import networkx as nx
        G = nx.DiGraph()
        stations = {}
        captured = {}

        def fake_build(period_name=None):
            captured["period"] = period_name
            return G, stations

        with patch.object(transit_graph, "_build_graph", side_effect=fake_build), \
             patch.object(transit_graph, "find_nearest_train_stations", return_value=[]), \
             patch.object(transit_graph, "find_nearest_bus_stops", return_value=[]):
            find_routes_with_status(
                42.019, -87.672, 41.885, -87.628,
                departure_time=datetime(2026, 5, 16, 3, 0),  # Sat 03:00
            )
        assert captured["period"] == "owl"

    def test_no_departure_time_uses_clock(self):
        # When departure_time is omitted, _select_period(None) reads
        # datetime.now(CHICAGO_TZ). Whatever that resolves to must be a known
        # period, and _build_graph must be called with it.
        from transit_graph import find_routes_with_status
        import networkx as nx
        G = nx.DiGraph()
        stations = {}
        captured = {}

        def fake_build(period_name=None):
            captured["period"] = period_name
            return G, stations

        with patch.object(transit_graph, "_build_graph", side_effect=fake_build), \
             patch.object(transit_graph, "find_nearest_train_stations", return_value=[]), \
             patch.object(transit_graph, "find_nearest_bus_stops", return_value=[]):
            find_routes_with_status(42.019, -87.672, 41.885, -87.628)
        assert captured["period"] in _PERIODS
