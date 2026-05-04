"""
Unit tests for GTFS-feed parsing functions in backend/transit_graph.py.

Each test writes a tiny synthetic GTFS fixture (parent stations, platforms,
bus stops, routes, trips, stop_times, transfers) into a temp directory,
points transit_graph.GTFS_DIR at it, and exercises the loader under test.

The lru_cache on the loaders is cleared in the autouse fixture so each test
sees fresh fixture data.

Covered:
  _load_all_stops
    - Parent stations (40000–49999, location_type=1) collected with name/lat/lon
    - Platform stops (30000–39999) recorded as platform→parent mapping
    - Bus stops (0–29999) collected with name/lat/lon
    - Rows with non-numeric stop_id are skipped
    - Rows with non-numeric lat/lon are skipped
    - location_type≠1 in 40000–49999 range is skipped

  _load_all_routes
    - route_type=1 → train_route_ids
    - Other route_types → bus_route_map
    - route_short_name fallback to route_id when missing
    - Empty route_id rows skipped

  _load_weekday_service_ids
    - All-five-weekday service flagged
    - Weekend-only service skipped
    - Missing calendar.txt → empty set
    - calendar_dates.txt add-exceptions: ≥3 weekday adds → included
    - <3 weekday adds → skipped (one-off services)

  _load_trips_unified
    - Train trips matched against train_route_ids
    - Bus trips matched against bus_route_ids
    - Weekday filter applied; non-weekday trips excluded
    - Fallback to all-trips when weekday filter yields none
    - Shape candidates collected unfiltered
    - Empty trip_id rows skipped

  _stream_all_stop_sequences
    - Trains: representative trip selected (longest, then closest-to-noon)
    - Trains: platform stop_ids resolved to parent mapids
    - Trains: stops sorted by stop_sequence
    - Buses: stops sorted; lookup metadata attached
    - Last-departure tracking across all trips
    - Rows for unknown bus stops dropped

  _load_transfer_edges
    - Platform IDs mapped to parent station IDs
    - Self-transfers dropped
    - Transfers to unknown stations dropped
    - min_transfer_time: < _TRANSFER_MINUTES floored; ≥ _TRANSFER_MINUTES preserved
    - Missing transfers.txt → empty list
"""

import csv
from pathlib import Path

import pytest

import transit_graph
from transit_graph import (
    _load_all_stops,
    _load_all_routes,
    _load_weekday_service_ids,
    _load_trips_unified,
    _stream_all_stop_sequences,
    _load_transfer_edges,
    _TRANSFER_MINUTES,
)


# ---------------------------------------------------------------------------
# Fixture infrastructure
# ---------------------------------------------------------------------------

def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    """Write rows as a UTF-8-BOM CSV (matches real CTA encoding)."""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


@pytest.fixture(autouse=True)
def _clear_loader_caches():
    """All GTFS loaders use lru_cache(maxsize=1) — must reset between tests."""
    _load_all_stops.cache_clear()
    _load_all_routes.cache_clear()
    _load_weekday_service_ids.cache_clear()
    yield
    _load_all_stops.cache_clear()
    _load_all_routes.cache_clear()
    _load_weekday_service_ids.cache_clear()


@pytest.fixture
def gtfs_dir(tmp_path, monkeypatch):
    """Empty tmp dir bound to transit_graph.GTFS_DIR."""
    monkeypatch.setattr(transit_graph, "GTFS_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# _load_all_stops
# ---------------------------------------------------------------------------

class TestLoadAllStops:
    HEADER = ["stop_id", "stop_name", "stop_lat", "stop_lon",
              "location_type", "parent_station"]

    def test_parent_stations_collected(self, gtfs_dir):
        _write_csv(gtfs_dir / "stops.txt", self.HEADER, [
            ["40900", "Howard",       "42.0190", "-87.6727", "1", ""],
            ["41660", "Lake",         "41.8853", "-87.6310", "1", ""],
        ])
        stations, _, _ = _load_all_stops()
        assert "40900" in stations
        assert stations["40900"]["name"] == "Howard"
        assert stations["40900"]["lat"] == pytest.approx(42.0190)
        assert stations["40900"]["lon"] == pytest.approx(-87.6727)
        assert "41660" in stations

    def test_platforms_mapped_to_parents(self, gtfs_dir):
        _write_csv(gtfs_dir / "stops.txt", self.HEADER, [
            ["40900", "Howard",       "42.0190", "-87.6727", "1", ""],
            ["30001", "Howard NB Platform", "42.0190", "-87.6727", "0", "40900"],
            ["30002", "Howard SB Platform", "42.0190", "-87.6727", "0", "40900"],
        ])
        _, mapping, _ = _load_all_stops()
        assert mapping["30001"] == "40900"
        assert mapping["30002"] == "40900"

    def test_bus_stops_collected(self, gtfs_dir):
        _write_csv(gtfs_dir / "stops.txt", self.HEADER, [
            ["1234", "Clark & Belmont", "41.9396", "-87.6588", "0", ""],
            ["5678", "State & Madison", "41.8819", "-87.6278", "0", ""],
        ])
        _, _, bus_stops = _load_all_stops()
        assert "1234" in bus_stops
        assert bus_stops["1234"]["name"] == "Clark & Belmont"
        assert "5678" in bus_stops

    def test_id_ranges_routed_correctly(self, gtfs_dir):
        _write_csv(gtfs_dir / "stops.txt", self.HEADER, [
            ["1234",  "Bus stop",  "41.94", "-87.65", "0", ""],          # bus
            ["30050", "Platform",  "42.01", "-87.67", "0", "40900"],     # platform
            ["40900", "Station",   "42.01", "-87.67", "1", ""],          # parent station
        ])
        stations, mapping, bus_stops = _load_all_stops()
        assert set(stations) == {"40900"}
        assert set(mapping)  == {"30050"}
        assert set(bus_stops) == {"1234"}

    def test_non_numeric_stop_id_skipped(self, gtfs_dir):
        _write_csv(gtfs_dir / "stops.txt", self.HEADER, [
            ["abc",   "Bad ID",   "41.0", "-87.0", "0", ""],
            ["40900", "Howard",   "42.0", "-87.6", "1", ""],
        ])
        stations, _, bus_stops = _load_all_stops()
        assert "40900" in stations
        assert bus_stops == {}

    def test_non_numeric_latlon_skipped(self, gtfs_dir):
        _write_csv(gtfs_dir / "stops.txt", self.HEADER, [
            ["40900", "Bad coords", "not-a-num", "-87.6", "1", ""],
            ["40901", "Good",       "42.0",      "-87.6", "1", ""],
        ])
        stations, _, _ = _load_all_stops()
        assert "40900" not in stations
        assert "40901" in stations

    def test_parent_range_with_location_type_not_1_skipped(self, gtfs_dir):
        # 40000-range stop with location_type=0 is NOT a parent — skipped
        _write_csv(gtfs_dir / "stops.txt", self.HEADER, [
            ["40500", "Not a parent", "42.0", "-87.6", "0", ""],
            ["40900", "Real parent",  "42.0", "-87.6", "1", ""],
        ])
        stations, _, _ = _load_all_stops()
        assert "40500" not in stations
        assert "40900" in stations

    def test_platform_without_parent_silently_skipped(self, gtfs_dir):
        _write_csv(gtfs_dir / "stops.txt", self.HEADER, [
            ["30100", "Orphan Platform", "42.0", "-87.6", "0", ""],   # no parent_station
        ])
        _, mapping, _ = _load_all_stops()
        assert mapping == {}


# ---------------------------------------------------------------------------
# _load_all_routes
# ---------------------------------------------------------------------------

class TestLoadAllRoutes:
    HEADER = ["route_id", "route_short_name", "route_type"]

    def test_train_routes_collected(self, gtfs_dir):
        _write_csv(gtfs_dir / "routes.txt", self.HEADER, [
            ["Red",  "Red Line",  "1"],
            ["Blue", "Blue Line", "1"],
        ])
        train_ids, bus_map, _ = _load_all_routes()
        assert train_ids == {"Red", "Blue"}
        assert bus_map == {}

    def test_bus_routes_collected(self, gtfs_dir):
        _write_csv(gtfs_dir / "routes.txt", self.HEADER, [
            ["22", "22", "3"],
            ["66", "66", "3"],
        ])
        train_ids, bus_map, _ = _load_all_routes()
        assert train_ids == set()
        assert bus_map == {"22": "22", "66": "66"}

    def test_mixed_routes(self, gtfs_dir):
        _write_csv(gtfs_dir / "routes.txt", self.HEADER, [
            ["Red", "Red Line", "1"],
            ["22",  "22",       "3"],
        ])
        train_ids, bus_map, _ = _load_all_routes()
        assert train_ids == {"Red"}
        assert bus_map == {"22": "22"}

    def test_short_name_fallback_to_route_id(self, gtfs_dir):
        # Empty short_name → bus_map value falls back to route_id
        _write_csv(gtfs_dir / "routes.txt", self.HEADER, [
            ["999", "", "3"],
        ])
        _, bus_map, _ = _load_all_routes()
        assert bus_map["999"] == "999"

    def test_empty_route_id_skipped(self, gtfs_dir):
        _write_csv(gtfs_dir / "routes.txt", self.HEADER, [
            ["",    "Phantom",  "1"],
            ["Red", "Red Line", "1"],
        ])
        train_ids, _, _ = _load_all_routes()
        assert train_ids == {"Red"}


# ---------------------------------------------------------------------------
# _load_weekday_service_ids
# ---------------------------------------------------------------------------

class TestLoadWeekdayServiceIds:
    CAL_HEADER = ["service_id", "monday", "tuesday", "wednesday", "thursday",
                  "friday", "saturday", "sunday", "start_date", "end_date"]
    DATES_HEADER = ["service_id", "date", "exception_type"]

    def test_full_weekday_service_included(self, gtfs_dir):
        _write_csv(gtfs_dir / "calendar.txt", self.CAL_HEADER, [
            ["WEEKDAY", "1", "1", "1", "1", "1", "0", "0", "20260101", "20261231"],
        ])
        ids = _load_weekday_service_ids()
        assert ids == {"WEEKDAY"}

    def test_weekend_only_service_excluded(self, gtfs_dir):
        _write_csv(gtfs_dir / "calendar.txt", self.CAL_HEADER, [
            ["WEEKEND", "0", "0", "0", "0", "0", "1", "1", "20260101", "20261231"],
        ])
        ids = _load_weekday_service_ids()
        assert "WEEKEND" not in ids

    def test_partial_weekday_service_excluded(self, gtfs_dir):
        # Mon-Thu only — missing Fri → not a true weekday service
        _write_csv(gtfs_dir / "calendar.txt", self.CAL_HEADER, [
            ["MON_THU", "1", "1", "1", "1", "0", "0", "0", "20260101", "20261231"],
        ])
        ids = _load_weekday_service_ids()
        assert "MON_THU" not in ids

    def test_missing_calendar_file_returns_empty(self, gtfs_dir):
        # No calendar.txt and no calendar_dates.txt → empty
        assert _load_weekday_service_ids() == set()

    def test_calendar_dates_three_weekday_adds_included(self, gtfs_dir):
        # No regular calendar.txt; service exists only via calendar_dates.txt
        _write_csv(gtfs_dir / "calendar_dates.txt", self.DATES_HEADER, [
            ["EXC1", "20260504", "1"],   # Mon
            ["EXC1", "20260505", "1"],   # Tue
            ["EXC1", "20260506", "1"],   # Wed
        ])
        ids = _load_weekday_service_ids()
        assert "EXC1" in ids

    def test_calendar_dates_two_weekday_adds_excluded(self, gtfs_dir):
        # Only 2 weekday adds — treated as one-off, not a recurring service
        _write_csv(gtfs_dir / "calendar_dates.txt", self.DATES_HEADER, [
            ["ONEOFF", "20260504", "1"],   # Mon
            ["ONEOFF", "20260505", "1"],   # Tue
        ])
        ids = _load_weekday_service_ids()
        assert "ONEOFF" not in ids

    def test_calendar_dates_remove_exceptions_ignored(self, gtfs_dir):
        # exception_type=2 (remove) should never count toward inclusion
        _write_csv(gtfs_dir / "calendar_dates.txt", self.DATES_HEADER, [
            ["WEEKDAY", "20260504", "2"],
            ["WEEKDAY", "20260505", "2"],
            ["WEEKDAY", "20260506", "2"],
        ])
        ids = _load_weekday_service_ids()
        assert ids == set()

    def test_weekend_dates_in_calendar_dates_excluded(self, gtfs_dir):
        # Saturday adds — even three of them shouldn't trigger inclusion
        _write_csv(gtfs_dir / "calendar_dates.txt", self.DATES_HEADER, [
            ["SAT_ONLY", "20260502", "1"],   # Sat
            ["SAT_ONLY", "20260509", "1"],   # Sat
            ["SAT_ONLY", "20260516", "1"],   # Sat
        ])
        assert _load_weekday_service_ids() == set()

    def test_calendar_and_calendar_dates_combined(self, gtfs_dir):
        _write_csv(gtfs_dir / "calendar.txt", self.CAL_HEADER, [
            ["WEEKDAY", "1", "1", "1", "1", "1", "0", "0", "20260101", "20261231"],
        ])
        _write_csv(gtfs_dir / "calendar_dates.txt", self.DATES_HEADER, [
            ["EXC", "20260504", "1"],
            ["EXC", "20260505", "1"],
            ["EXC", "20260506", "1"],
        ])
        ids = _load_weekday_service_ids()
        assert ids == {"WEEKDAY", "EXC"}


# ---------------------------------------------------------------------------
# _load_trips_unified
# ---------------------------------------------------------------------------

class TestLoadTripsUnified:
    TRIPS_HEADER = ["route_id", "service_id", "trip_id", "direction_id", "shape_id"]
    CAL_HEADER   = ["service_id", "monday", "tuesday", "wednesday", "thursday",
                    "friday", "saturday", "sunday", "start_date", "end_date"]

    def _seed_weekday_service(self, gtfs_dir, sid="WEEKDAY"):
        _write_csv(gtfs_dir / "calendar.txt", self.CAL_HEADER, [
            [sid, "1", "1", "1", "1", "1", "0", "0", "20260101", "20261231"],
        ])

    def test_train_trips_collected(self, gtfs_dir):
        self._seed_weekday_service(gtfs_dir)
        _write_csv(gtfs_dir / "trips.txt", self.TRIPS_HEADER, [
            ["Red", "WEEKDAY", "T1", "0", "shape_red_NB"],
            ["Red", "WEEKDAY", "T2", "1", "shape_red_SB"],
        ])
        train_route, train_dir, bus_route, bus_dir, shapes, used = _load_trips_unified(
            train_route_ids={"Red"}, bus_route_ids=set(),
        )
        assert train_route == {"T1": "Red", "T2": "Red"}
        assert train_dir   == {"T1": "0",   "T2": "1"}
        assert bus_route   == {}
        assert ("Red", "0") in shapes
        assert ("Red", "1") in shapes
        assert used == {"shape_red_NB", "shape_red_SB"}

    def test_bus_trips_collected(self, gtfs_dir):
        self._seed_weekday_service(gtfs_dir)
        _write_csv(gtfs_dir / "trips.txt", self.TRIPS_HEADER, [
            ["22", "WEEKDAY", "B1", "0", "shape_22"],
        ])
        _, _, bus_route, bus_dir, _, _ = _load_trips_unified(
            train_route_ids=set(), bus_route_ids={"22"},
        )
        assert bus_route == {"B1": "22"}
        assert bus_dir   == {"B1": "0"}

    def test_weekend_trips_excluded_when_weekday_present(self, gtfs_dir):
        self._seed_weekday_service(gtfs_dir, "WEEKDAY")
        _write_csv(gtfs_dir / "trips.txt", self.TRIPS_HEADER, [
            ["Red", "WEEKDAY", "T1", "0", "s1"],
            ["Red", "WEEKEND", "T2", "0", "s2"],   # WEEKEND not in calendar → excluded
        ])
        train_route, _, _, _, _, _ = _load_trips_unified(
            train_route_ids={"Red"}, bus_route_ids=set(),
        )
        # Only WEEKDAY trip kept
        assert train_route == {"T1": "Red"}

    def test_fallback_when_no_weekday_match(self, gtfs_dir):
        # No calendar.txt → no weekday service IDs → fallback to all trips
        _write_csv(gtfs_dir / "trips.txt", self.TRIPS_HEADER, [
            ["Red", "ANY",      "T1", "0", "s1"],
            ["Red", "WHATEVER", "T2", "1", "s2"],
        ])
        train_route, _, _, _, _, _ = _load_trips_unified(
            train_route_ids={"Red"}, bus_route_ids=set(),
        )
        # Fallback path keeps both trips
        assert train_route == {"T1": "Red", "T2": "Red"}

    def test_shape_candidates_unfiltered_by_service(self, gtfs_dir):
        # WEEKEND trip has its own shape — the shape candidates set must include
        # it even though the trip itself is filtered out of train_route mapping.
        self._seed_weekday_service(gtfs_dir)
        _write_csv(gtfs_dir / "trips.txt", self.TRIPS_HEADER, [
            ["Red", "WEEKDAY", "T1", "0", "shape_wd"],
            ["Red", "WEEKEND", "T2", "0", "shape_we"],
        ])
        _, _, _, _, shapes, used = _load_trips_unified(
            train_route_ids={"Red"}, bus_route_ids=set(),
        )
        assert "shape_wd" in used
        assert "shape_we" in used
        assert shapes[("Red", "0")] == {"shape_wd", "shape_we"}

    def test_empty_trip_id_skipped(self, gtfs_dir):
        self._seed_weekday_service(gtfs_dir)
        _write_csv(gtfs_dir / "trips.txt", self.TRIPS_HEADER, [
            ["Red", "WEEKDAY", "",   "0", "s1"],   # missing trip_id → skipped
            ["Red", "WEEKDAY", "T2", "0", "s2"],
        ])
        train_route, _, _, _, _, _ = _load_trips_unified(
            train_route_ids={"Red"}, bus_route_ids=set(),
        )
        assert train_route == {"T2": "Red"}

    def test_unknown_route_id_ignored(self, gtfs_dir):
        # Trips for route_ids not in train_route_ids OR bus_route_ids are dropped
        self._seed_weekday_service(gtfs_dir)
        _write_csv(gtfs_dir / "trips.txt", self.TRIPS_HEADER, [
            ["Red",     "WEEKDAY", "T1",      "0", "s1"],
            ["Unknown", "WEEKDAY", "T_other", "0", "s_other"],
        ])
        train_route, _, bus_route, _, _, _ = _load_trips_unified(
            train_route_ids={"Red"}, bus_route_ids=set(),
        )
        assert train_route == {"T1": "Red"}
        assert bus_route == {}


# ---------------------------------------------------------------------------
# _stream_all_stop_sequences
# ---------------------------------------------------------------------------

class TestStreamAllStopSequences:
    """
    Synthetic stop_times.txt used here only models what the streamer needs:
    it must read trip_id, stop_id, stop_sequence, arrival_time, departure_time.
    """

    HEADER = ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"]

    def test_train_sequence_resolved_to_parent_mapids(self, gtfs_dir):
        # Two platform stops, both children of the same parent station chain.
        # Streamer must map 30100→40100 and 30200→40200 via platform_to_parent.
        _write_csv(gtfs_dir / "stop_times.txt", self.HEADER, [
            ["T1", "12:00:00", "12:00:00", "30100", "1"],
            ["T1", "12:05:00", "12:05:00", "30200", "2"],
        ])
        train_sel, _, last_dep = _stream_all_stop_sequences(
            train_candidates={"T1": "Red"},
            train_dirs={"T1": "0"},
            bus_candidates={},
            bus_dirs={},
            platform_to_parent={"30100": "40100", "30200": "40200"},
            bus_stop_lookup={},
            bus_route_map={},
        )
        # Sequence preserved, platforms resolved to parents
        assert train_sel == {"T1": [("40100", 720.0), ("40200", 725.0)]}
        # Latest-departure tracker captured both stops in the same direction
        assert last_dep[("40100", "0")] == "12:00:00"
        assert last_dep[("40200", "0")] == "12:05:00"

    def test_train_representative_picks_longest_trip(self, gtfs_dir):
        # T1 and T2 serve (Red, dir 0); T1 has 2 stops, T2 has 3.
        # T2 must win on length even though T1 starts closer to noon.
        _write_csv(gtfs_dir / "stop_times.txt", self.HEADER, [
            ["T1", "12:00:00", "12:00:00", "30100", "1"],
            ["T1", "12:05:00", "12:05:00", "30200", "2"],
            ["T2", "11:30:00", "11:30:00", "30100", "1"],
            ["T2", "11:35:00", "11:35:00", "30200", "2"],
            ["T2", "11:40:00", "11:40:00", "30300", "3"],
        ])
        train_sel, _, _ = _stream_all_stop_sequences(
            train_candidates={"T1": "Red", "T2": "Red"},
            train_dirs={"T1": "0", "T2": "0"},
            bus_candidates={},
            bus_dirs={},
            platform_to_parent={"30100": "40100", "30200": "40200", "30300": "40300"},
            bus_stop_lookup={},
            bus_route_map={},
        )
        # Only the longer trip (T2) is kept as representative
        assert "T2" in train_sel
        assert "T1" not in train_sel
        assert len(train_sel["T2"]) == 3

    def test_train_stops_sorted_by_sequence(self, gtfs_dir):
        # Rows out of order — stop_sequence (not file order) defines path
        _write_csv(gtfs_dir / "stop_times.txt", self.HEADER, [
            ["T1", "12:10:00", "12:10:00", "30300", "3"],
            ["T1", "12:00:00", "12:00:00", "30100", "1"],
            ["T1", "12:05:00", "12:05:00", "30200", "2"],
        ])
        train_sel, _, _ = _stream_all_stop_sequences(
            train_candidates={"T1": "Red"},
            train_dirs={"T1": "0"},
            bus_candidates={},
            bus_dirs={},
            platform_to_parent={"30100": "40100", "30200": "40200", "30300": "40300"},
            bus_stop_lookup={},
            bus_route_map={},
        )
        ordered = train_sel["T1"]
        assert [parent for parent, _ in ordered] == ["40100", "40200", "40300"]

    def test_bus_sequence_resolves_metadata(self, gtfs_dir):
        _write_csv(gtfs_dir / "stop_times.txt", self.HEADER, [
            ["B1", "12:00:00", "12:00:00", "1234", "1"],
            ["B1", "12:08:00", "12:08:00", "5678", "2"],
        ])
        _, bus_result, _ = _stream_all_stop_sequences(
            train_candidates={},
            train_dirs={},
            bus_candidates={"B1": "22"},
            bus_dirs={"B1": "0"},
            platform_to_parent={},
            bus_stop_lookup={
                "1234": {"name": "Clark & Belmont", "lat": 41.94, "lon": -87.65},
                "5678": {"name": "State & Madison", "lat": 41.88, "lon": -87.62},
            },
            bus_route_map={"22": "22"},
        )
        # Keyed by (route_short_name, direction_id)
        seq = bus_result[("22", "0")]
        assert seq[0] == ("1234", "Clark & Belmont", 41.94, -87.65, 720.0)
        assert seq[1] == ("5678", "State & Madison", 41.88, -87.62, 728.0)

    def test_bus_unknown_stop_dropped(self, gtfs_dir):
        # Stop ID not present in bus_stop_lookup is dropped from the trip
        _write_csv(gtfs_dir / "stop_times.txt", self.HEADER, [
            ["B1", "12:00:00", "12:00:00", "1234",   "1"],
            ["B1", "12:08:00", "12:08:00", "GHOST",  "2"],   # unknown — dropped
            ["B1", "12:15:00", "12:15:00", "5678",   "3"],
        ])
        _, bus_result, _ = _stream_all_stop_sequences(
            train_candidates={},
            train_dirs={},
            bus_candidates={"B1": "22"},
            bus_dirs={"B1": "0"},
            platform_to_parent={},
            bus_stop_lookup={
                "1234": {"name": "Clark & Belmont", "lat": 41.94, "lon": -87.65},
                "5678": {"name": "State & Madison", "lat": 41.88, "lon": -87.62},
            },
            bus_route_map={"22": "22"},
        )
        seq = bus_result[("22", "0")]
        assert len(seq) == 2
        ids = [s[0] for s in seq]
        assert "GHOST" not in ids

    def test_last_departure_tracks_latest_per_station_direction(self, gtfs_dir):
        # Two trips on (Red, dir 0) departing 30100 — last_dep must reflect
        # the LATER departure (12:55), not the earlier (12:00).
        _write_csv(gtfs_dir / "stop_times.txt", self.HEADER, [
            ["T1", "12:00:00", "12:00:00", "30100", "1"],
            ["T2", "12:55:00", "12:55:00", "30100", "1"],
        ])
        _, _, last_dep = _stream_all_stop_sequences(
            train_candidates={"T1": "Red", "T2": "Red"},
            train_dirs={"T1": "0", "T2": "0"},
            bus_candidates={},
            bus_dirs={},
            platform_to_parent={"30100": "40100"},
            bus_stop_lookup={},
            bus_route_map={},
        )
        assert last_dep[("40100", "0")] == "12:55:00"

    def test_post_midnight_time_parsed(self, gtfs_dir):
        # GTFS allows hours > 24 for overnight service — must be preserved as time string.
        _write_csv(gtfs_dir / "stop_times.txt", self.HEADER, [
            ["T1", "25:30:00", "25:30:00", "30100", "1"],
        ])
        _, _, last_dep = _stream_all_stop_sequences(
            train_candidates={"T1": "Red"},
            train_dirs={"T1": "0"},
            bus_candidates={},
            bus_dirs={},
            platform_to_parent={"30100": "40100"},
            bus_stop_lookup={},
            bus_route_map={},
        )
        assert last_dep[("40100", "0")] == "25:30:00"


# ---------------------------------------------------------------------------
# _load_transfer_edges
# ---------------------------------------------------------------------------

class TestLoadTransferEdges:
    HEADER = ["from_stop_id", "to_stop_id", "transfer_type", "min_transfer_time"]

    def test_platform_ids_resolved_to_parents(self, gtfs_dir):
        _write_csv(gtfs_dir / "transfers.txt", self.HEADER, [
            ["30001", "30002", "0", "180"],   # platforms of 40900 ↔ 40901
        ])
        edges = _load_transfer_edges(
            platform_to_parent={"30001": "40900", "30002": "40901"},
            parent_stations={
                "40900": {"name": "A", "lat": 0, "lon": 0},
                "40901": {"name": "B", "lat": 0, "lon": 0},
            },
        )
        assert len(edges) == 1
        u, v, _ = edges[0]
        assert u == "40900"
        assert v == "40901"

    def test_self_transfer_dropped(self, gtfs_dir):
        # Both platforms map to the same parent → self-edge → dropped
        _write_csv(gtfs_dir / "transfers.txt", self.HEADER, [
            ["30001", "30002", "0", "60"],
        ])
        edges = _load_transfer_edges(
            platform_to_parent={"30001": "40900", "30002": "40900"},
            parent_stations={"40900": {"name": "A", "lat": 0, "lon": 0}},
        )
        assert edges == []

    def test_transfer_to_unknown_station_dropped(self, gtfs_dir):
        # Target parent (40999) is not in parent_stations → dropped
        _write_csv(gtfs_dir / "transfers.txt", self.HEADER, [
            ["30001", "30099", "0", "180"],
        ])
        edges = _load_transfer_edges(
            platform_to_parent={"30001": "40900", "30099": "40999"},
            parent_stations={"40900": {"name": "A", "lat": 0, "lon": 0}},
        )
        assert edges == []

    def test_minutes_floored_at_transfer_minimum(self, gtfs_dir):
        # min_transfer_time of 30 sec (0.5 min) — must be clamped to _TRANSFER_MINUTES
        _write_csv(gtfs_dir / "transfers.txt", self.HEADER, [
            ["30001", "30002", "0", "30"],
        ])
        edges = _load_transfer_edges(
            platform_to_parent={"30001": "40900", "30002": "40901"},
            parent_stations={
                "40900": {"name": "A", "lat": 0, "lon": 0},
                "40901": {"name": "B", "lat": 0, "lon": 0},
            },
        )
        _, _, minutes = edges[0]
        assert minutes == _TRANSFER_MINUTES

    def test_minutes_above_floor_preserved(self, gtfs_dir):
        # 600 sec = 10 min, well above the floor — must be preserved as 10.0
        _write_csv(gtfs_dir / "transfers.txt", self.HEADER, [
            ["30001", "30002", "0", "600"],
        ])
        edges = _load_transfer_edges(
            platform_to_parent={"30001": "40900", "30002": "40901"},
            parent_stations={
                "40900": {"name": "A", "lat": 0, "lon": 0},
                "40901": {"name": "B", "lat": 0, "lon": 0},
            },
        )
        _, _, minutes = edges[0]
        assert minutes == pytest.approx(10.0)

    def test_missing_transfers_file_returns_empty(self, gtfs_dir):
        # No transfers.txt file at all
        edges = _load_transfer_edges(
            platform_to_parent={},
            parent_stations={"40900": {"name": "A", "lat": 0, "lon": 0}},
        )
        assert edges == []

    def test_invalid_min_transfer_time_uses_floor(self, gtfs_dir):
        # Non-numeric min_transfer_time → ValueError → fallback to _TRANSFER_MINUTES
        _write_csv(gtfs_dir / "transfers.txt", self.HEADER, [
            ["30001", "30002", "0", "abc"],
        ])
        edges = _load_transfer_edges(
            platform_to_parent={"30001": "40900", "30002": "40901"},
            parent_stations={
                "40900": {"name": "A", "lat": 0, "lon": 0},
                "40901": {"name": "B", "lat": 0, "lon": 0},
            },
        )
        _, _, minutes = edges[0]
        assert minutes == _TRANSFER_MINUTES
