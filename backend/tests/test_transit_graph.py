"""
Unit tests for pure functions in backend/transit_graph.py.

All tests here exercise deterministic, I/O-free logic.  No GTFS files are
read, no graph is built, and no CTA APIs are called.  Tests that would
require the full graph (find_routes, warm_up, etc.) are intentionally
excluded — those are integration-level concerns.

Covered:
  - _bearing_to_direction()   — cardinal direction from two lat/lon pairs
  - _parse_gtfs_time()        — GTFS HH:MM:SS → float minutes
  - clip_shape()              — shape-point clipping between stops
  - Route dataclass           — total_minutes_no_wait property, summary()
  - WalkLeg / TransitLeg      — field defaults and leg_type
  - _dedup_stations_by_line() — same-line station deduplication
"""

import pytest
import networkx as nx

from transit_graph import (
    _bearing_to_direction,
    _parse_gtfs_time,
    clip_shape,
    Route,
    WalkLeg,
    TransitLeg,
    _dedup_stations_by_line,
)


# ---------------------------------------------------------------------------
# _bearing_to_direction
# ---------------------------------------------------------------------------

class TestBearingToDirection:
    def test_northbound(self):
        # Moving north: increase latitude, same longitude
        assert _bearing_to_direction(41.88, -87.63, 42.00, -87.63) == "Northbound"

    def test_southbound(self):
        assert _bearing_to_direction(42.00, -87.63, 41.88, -87.63) == "Southbound"

    def test_eastbound(self):
        # Moving east: decrease longitude (less negative) at same latitude
        assert _bearing_to_direction(41.88, -87.90, 41.88, -87.60) == "Eastbound"

    def test_westbound(self):
        assert _bearing_to_direction(41.88, -87.60, 41.88, -87.90) == "Westbound"

    def test_degenerate_same_point_returns_northbound_fallback(self):
        # Identical coords → degenerate bearing; spec says return "Northbound"
        assert _bearing_to_direction(41.88, -87.63, 41.88, -87.63) == "Northbound"

    def test_return_type_is_string(self):
        result = _bearing_to_direction(41.88, -87.63, 41.90, -87.65)
        assert isinstance(result, str)

    def test_result_is_one_of_four_cardinals(self):
        cardinals = {"Northbound", "Southbound", "Eastbound", "Westbound"}
        result = _bearing_to_direction(41.88, -87.63, 41.90, -87.65)
        assert result in cardinals

    def test_diagonal_northeast_is_eastbound_or_northbound(self):
        # 45-degree NE diagonal should land on one of those two
        result = _bearing_to_direction(41.88, -87.63, 41.93, -87.58)
        assert result in {"Northbound", "Eastbound"}

    def test_diagonal_southwest_is_southbound_or_westbound(self):
        result = _bearing_to_direction(41.93, -87.58, 41.88, -87.63)
        assert result in {"Southbound", "Westbound"}


# ---------------------------------------------------------------------------
# _parse_gtfs_time
# ---------------------------------------------------------------------------

class TestParseGtfsTime:
    def test_midnight(self):
        assert _parse_gtfs_time("00:00:00") == 0.0

    def test_noon(self):
        assert _parse_gtfs_time("12:00:00") == 720.0

    def test_hour_and_minutes(self):
        assert _parse_gtfs_time("08:30:00") == 8 * 60 + 30.0

    def test_with_seconds(self):
        # 30 seconds = 0.5 minutes
        assert _parse_gtfs_time("08:30:30") == pytest.approx(8 * 60 + 30.5)

    def test_past_midnight_gtfs_convention(self):
        # CTA overnight trips use hours > 24 in GTFS
        assert _parse_gtfs_time("25:00:00") == 25 * 60.0

    def test_end_of_day(self):
        assert _parse_gtfs_time("23:59:59") == pytest.approx(23 * 60 + 59 + 59 / 60)

    def test_leading_zero_hours(self):
        assert _parse_gtfs_time("09:05:00") == 9 * 60 + 5.0

    def test_whitespace_stripped(self):
        assert _parse_gtfs_time("  12:00:00  ") == 720.0


# ---------------------------------------------------------------------------
# clip_shape
# ---------------------------------------------------------------------------

class TestClipShape:
    def test_none_shape_returns_straight_line(self):
        result = clip_shape(None, 41.88, -87.63, 41.90, -87.65)
        assert result == [[41.88, -87.63], [41.90, -87.65]]

    def test_empty_shape_returns_straight_line(self):
        result = clip_shape([], 41.88, -87.63, 41.90, -87.65)
        assert result == [[41.88, -87.63], [41.90, -87.65]]

    def test_clipped_result_is_list_of_pairs(self):
        shape = [[41.80, -87.60], [41.85, -87.62], [41.90, -87.64], [41.95, -87.66]]
        result = clip_shape(shape, 41.85, -87.62, 41.90, -87.64)
        assert isinstance(result, list)
        for pt in result:
            assert isinstance(pt, list)
            assert len(pt) == 2

    def test_clip_returns_subset_of_shape(self):
        shape = [[41.80, -87.60], [41.85, -87.62], [41.90, -87.64], [41.95, -87.66]]
        result = clip_shape(shape, 41.85, -87.62, 41.90, -87.64)
        # Every returned point should appear in the original shape
        for pt in result:
            assert pt in shape

    def test_result_has_at_least_two_points(self):
        shape = [[41.80, -87.60], [41.85, -87.62], [41.90, -87.64]]
        result = clip_shape(shape, 41.80, -87.60, 41.90, -87.64)
        assert len(result) >= 2

    def test_reverse_trip_reverses_segment(self):
        # A shape going south→north; a trip going north→south should reverse it
        shape = [[41.80, -87.60], [41.85, -87.62], [41.90, -87.64]]
        # Board at lat 41.90 (north), exit at lat 41.80 (south)
        result = clip_shape(shape, 41.90, -87.64, 41.80, -87.60)
        assert len(result) >= 2
        # First returned latitude should be >= last (traveling south)
        assert result[0][0] >= result[-1][0]

    def test_same_nearest_point_returns_straight_line(self):
        # All shape points at the same location → board_idx == exit_idx → fallback
        shape = [[41.88, -87.63]] * 5
        result = clip_shape(shape, 41.88, -87.63, 41.90, -87.65)
        assert result == [[41.88, -87.63], [41.90, -87.65]]

    def test_single_point_shape_returns_straight_line(self):
        shape = [[41.88, -87.63]]
        result = clip_shape(shape, 41.88, -87.63, 41.90, -87.65)
        assert result == [[41.88, -87.63], [41.90, -87.65]]


# ---------------------------------------------------------------------------
# Route dataclass
# ---------------------------------------------------------------------------

class TestRoute:
    def test_total_minutes_no_wait_sums_transit_and_walk(self):
        r = Route(transit_minutes=20.0, walk_minutes_total=8.0)
        assert r.total_minutes_no_wait == 28.0

    def test_total_minutes_no_wait_all_zeros(self):
        r = Route()
        assert r.total_minutes_no_wait == 0.0

    def test_default_transfers_zero(self):
        r = Route()
        assert r.transfers == 0

    def test_default_legs_empty(self):
        r = Route()
        assert r.legs == []

    def test_default_first_transit_leg_index_none(self):
        r = Route()
        assert r.first_transit_leg_index is None

    def test_summary_includes_walk_leg(self):
        r = Route(
            legs=[WalkLeg(from_name="Start", to_name="Station", minutes=5.0)],
            transit_minutes=0.0,
            walk_minutes_total=5.0,
        )
        summary = r.summary()
        assert "Walk" in summary

    def test_summary_includes_transit_leg(self):
        r = Route(
            legs=[
                TransitLeg(
                    line="Red Line", line_code="Red",
                    from_station="Howard", from_mapid="40900",
                    to_station="Lake", to_mapid="41660",
                    minutes=30.0,
                )
            ],
            transit_minutes=30.0,
            walk_minutes_total=0.0,
        )
        summary = r.summary()
        assert "Red Line" in summary
        assert "Howard" in summary
        assert "Lake" in summary

    def test_summary_contains_total_time(self):
        r = Route(transit_minutes=20.0, walk_minutes_total=5.0)
        summary = r.summary()
        assert "total excl. wait" in summary
        assert "25" in summary


# ---------------------------------------------------------------------------
# WalkLeg / TransitLeg dataclasses
# ---------------------------------------------------------------------------

class TestWalkLeg:
    def test_leg_type_is_walk(self):
        leg = WalkLeg(from_name="A", to_name="B", minutes=3.0)
        assert leg.leg_type == "walk"

    def test_default_path_points_empty(self):
        leg = WalkLeg(from_name="A", to_name="B", minutes=3.0)
        assert leg.path_points == []

    def test_default_directions_empty(self):
        leg = WalkLeg(from_name="A", to_name="B", minutes=3.0)
        assert leg.directions == []

    def test_default_exit_label_empty(self):
        leg = WalkLeg(from_name="A", to_name="B", minutes=3.0)
        assert leg.exit_label == ""

    def test_custom_exit_label(self):
        leg = WalkLeg(from_name="A", to_name="B", minutes=3.0, exit_label="NE Exit")
        assert leg.exit_label == "NE Exit"


class TestTransitLeg:
    def _make_leg(self, **kwargs):
        defaults = dict(
            line="Red Line", line_code="Red",
            from_station="Howard", from_mapid="40900",
            to_station="Lake", to_mapid="41660",
            minutes=25.0,
        )
        return TransitLeg(**{**defaults, **kwargs})

    def test_leg_type_is_transit(self):
        assert self._make_leg().leg_type == "transit"

    def test_default_shape_points_empty(self):
        assert self._make_leg().shape_points == []

    def test_default_transfer_wait_none(self):
        assert self._make_leg().transfer_wait_minutes is None

    def test_transfer_wait_settable(self):
        leg = self._make_leg()
        leg.transfer_wait_minutes = 7
        assert leg.transfer_wait_minutes == 7

    def test_fields_accessible(self):
        leg = self._make_leg()
        assert leg.line == "Red Line"
        assert leg.line_code == "Red"
        assert leg.from_station == "Howard"
        assert leg.to_station == "Lake"
        assert leg.minutes == 25.0


# ---------------------------------------------------------------------------
# _dedup_stations_by_line
# ---------------------------------------------------------------------------

class TestDedupStationsByLine:
    """
    _dedup_stations_by_line keeps the closest station per set of unique transit
    lines.  A station that only adds lines already covered by a closer station
    is dropped.
    """

    def _graph_with_edges(self, edges: list[tuple]) -> nx.DiGraph:
        """Build a DiGraph from (u, v, data) triples."""
        G = nx.DiGraph()
        for u, v, data in edges:
            G.add_edge(u, v, **data)
        return G

    def test_single_station_always_kept(self):
        G = self._graph_with_edges([
            ("A", "B", {"line": "Red Line", "edge_type": "transit"}),
        ])
        result = _dedup_stations_by_line(G, [{"mapid": "A", "walk_minutes": 2.0}])
        assert len(result) == 1

    def test_two_stations_same_line_keeps_closer(self):
        G = self._graph_with_edges([
            ("A", "B", {"line": "Red Line", "edge_type": "transit"}),
            ("C", "D", {"line": "Red Line", "edge_type": "transit"}),
        ])
        stations = [
            {"mapid": "A", "walk_minutes": 2.0},   # closer
            {"mapid": "C", "walk_minutes": 8.0},   # farther, same line
        ]
        result = _dedup_stations_by_line(G, stations)
        assert len(result) == 1
        assert result[0]["mapid"] == "A"

    def test_two_stations_different_lines_both_kept(self):
        G = self._graph_with_edges([
            ("A", "B", {"line": "Red Line", "edge_type": "transit"}),
            ("C", "D", {"line": "Blue Line", "edge_type": "transit"}),
        ])
        stations = [
            {"mapid": "A", "walk_minutes": 2.0},
            {"mapid": "C", "walk_minutes": 5.0},
        ]
        result = _dedup_stations_by_line(G, stations)
        assert len(result) == 2
        mapids = {s["mapid"] for s in result}
        assert mapids == {"A", "C"}

    def test_station_not_in_graph_always_included(self):
        G = nx.DiGraph()   # empty graph — no nodes, no edges
        stations = [{"mapid": "GHOST", "walk_minutes": 1.0}]
        result = _dedup_stations_by_line(G, stations)
        assert len(result) == 1
        assert result[0]["mapid"] == "GHOST"

    def test_transfer_edges_not_counted_as_new_line(self):
        # Transfer edges have edge_type="transfer", not "transit" —
        # they should not contribute to the covered-lines set.
        G = self._graph_with_edges([
            ("A", "B", {"line": "Red Line",  "edge_type": "transit"}),
            ("A", "C", {"line": "Red Line",  "edge_type": "transfer"}),  # transfer, ignored
            ("D", "E", {"line": "Red Line",  "edge_type": "transit"}),
        ])
        stations = [
            {"mapid": "A", "walk_minutes": 2.0},
            {"mapid": "D", "walk_minutes": 5.0},   # same transit line as A
        ]
        result = _dedup_stations_by_line(G, stations)
        assert len(result) == 1

    def test_empty_stations_returns_empty(self):
        G = nx.DiGraph()
        assert _dedup_stations_by_line(G, []) == []

    def test_order_is_preserved(self):
        G = self._graph_with_edges([
            ("A", "B", {"line": "Red Line",  "edge_type": "transit"}),
            ("C", "D", {"line": "Blue Line", "edge_type": "transit"}),
            ("E", "F", {"line": "Green Line", "edge_type": "transit"}),
        ])
        stations = [
            {"mapid": "A", "walk_minutes": 1.0},
            {"mapid": "C", "walk_minutes": 2.0},
            {"mapid": "E", "walk_minutes": 3.0},
        ]
        result = _dedup_stations_by_line(G, stations)
        assert [s["mapid"] for s in result] == ["A", "C", "E"]
