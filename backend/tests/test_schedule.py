"""Tests for FEAT-018 schedule build script + endpoint classifier."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Route-category classifier (Decision 8)
# ---------------------------------------------------------------------------

def test_classify_train_route():
    from schedule import classify_route
    assert classify_route("1", "c60c30") == "train"


def test_classify_bus_express():
    from schedule import classify_route
    assert classify_route("3", "b71234") == "bus_express"
    # Case-insensitive on color hex.
    assert classify_route("3", "B71234") == "bus_express"


def test_classify_bus_frequent():
    from schedule import classify_route
    assert classify_route("3", "414145") == "bus_frequent"


def test_classify_bus_regular_default():
    from schedule import classify_route
    # CTA's "regular" color is 99999C but any unknown color falls into
    # bus_regular for route_type=3.
    assert classify_route("3", "99999C") == "bus_regular"
    assert classify_route("3", "") == "bus_regular"
    assert classify_route("3", "deadbe") == "bus_regular"


def test_classify_other_route_type():
    from schedule import classify_route
    assert classify_route("2", "ffffff") == "other"


# ---------------------------------------------------------------------------
# HH:MM normalisation (build script helper)
# ---------------------------------------------------------------------------

def test_normalise_hhmm_basic():
    import build_schedule_index as b
    assert b._normalise_hhmm("07:13:00") == "07:13"
    assert b._normalise_hhmm("23:59:00") == "23:59"


def test_normalise_hhmm_past_midnight():
    import build_schedule_index as b
    # GTFS 24:15 represents the 12:15am trip that "belongs" to the prior
    # service day's tail — collapsed back into 0–23 so it groups under "0".
    assert b._normalise_hhmm("24:15:00") == "00:15"
    assert b._normalise_hhmm("25:30:00") == "01:30"


def test_normalise_hhmm_malformed():
    import build_schedule_index as b
    assert b._normalise_hhmm("bad") is None
    assert b._normalise_hhmm("") is None


# ---------------------------------------------------------------------------
# Holiday detector (Decision 7 — federal holidays fold into Sunday bucket)
# ---------------------------------------------------------------------------

def test_sunday_service_holidays_fixed():
    import build_schedule_index as b
    import datetime
    assert b._is_sunday_service_holiday(datetime.date(2026, 1, 1))     # New Year
    assert b._is_sunday_service_holiday(datetime.date(2026, 7, 4))     # July 4
    assert b._is_sunday_service_holiday(datetime.date(2026, 12, 25))   # Xmas


def test_sunday_service_holidays_floating():
    import build_schedule_index as b
    import datetime
    # 2026: Memorial Day = May 25 (last Mon), Labor Day = Sep 7 (first Mon),
    # Thanksgiving = Nov 26 (fourth Thu).
    assert b._is_sunday_service_holiday(datetime.date(2026, 5, 25))
    assert b._is_sunday_service_holiday(datetime.date(2026, 9, 7))
    assert b._is_sunday_service_holiday(datetime.date(2026, 11, 26))
    # Random Monday in May that isn't the last Mon should NOT match.
    assert not b._is_sunday_service_holiday(datetime.date(2026, 5, 4))
    # Random weekday should NOT match.
    assert not b._is_sunday_service_holiday(datetime.date(2026, 3, 15))


# ---------------------------------------------------------------------------
# End-to-end build against a fixture GTFS slice
# ---------------------------------------------------------------------------

def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.write_text(
        ",".join(header) + "\n" + "\n".join(",".join(r) for r in rows) + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def fixture_gtfs(tmp_path, monkeypatch):
    """Tiny synthetic GTFS feed for the build-script structure test."""
    gtfs = tmp_path / "gtfs"
    gtfs.mkdir()

    _write_csv(gtfs / "routes.txt",
        ["agency_id", "route_id", "route_short_name", "route_long_name",
         "route_type", "route_url", "route_color", "route_text_color"],
        [
            ["50066", "Red", "Red", "Red Line", "1", "", "c60c30", "ffffff"],
            ["50066", "22",  "22",  "Clark",   "3", "", "414145", "ffffff"],
            ["50066", "X9",  "X9",  "Ashland Express", "3", "", "b71234", "ffffff"],
        ],
    )
    _write_csv(gtfs / "calendar.txt",
        ["service_id", "monday", "tuesday", "wednesday", "thursday",
         "friday", "saturday", "sunday", "start_date", "end_date"],
        [
            ["WK", "1", "1", "1", "1", "1", "0", "0", "20260101", "20261231"],
            ["SA", "0", "0", "0", "0", "0", "1", "0", "20260101", "20261231"],
            ["SU", "0", "0", "0", "0", "0", "0", "1", "20260101", "20261231"],
        ],
    )
    _write_csv(gtfs / "calendar_dates.txt",
        ["service_id", "date", "exception_type"],
        [
            # July 4 is a Sunday-service holiday — fold WK into sunday.
            ["WK", "20260704", "1"],
            # Random non-holiday added date — should NOT shift bucket.
            ["WK", "20260615", "1"],
        ],
    )
    _write_csv(gtfs / "stops.txt",
        ["stop_id", "stop_code", "stop_name", "stop_desc", "stop_lat",
         "stop_lon", "location_type", "parent_station", "wheelchair_boarding"],
        [
            ["1001", "1001", "Howard", "", "42.019", "-87.672", "0", "", "1"],
            ["1002", "1002", "Belmont", "", "41.940", "-87.653", "0", "", "1"],
            ["1003", "1003", "95th",   "", "41.722", "-87.624", "0", "", "1"],
        ],
    )
    _write_csv(gtfs / "trips.txt",
        ["route_id", "service_id", "trip_id", "direction_id", "block_id",
         "shape_id", "direction", "wheelchair_accessible", "schd_trip_id"],
        [
            ["Red", "WK", "T_WK_S", "0", "", "", "South", "1", ""],
            ["Red", "SA", "T_SA_S", "0", "", "", "South", "1", ""],
            ["Red", "WK", "T_WK_N", "1", "", "", "North", "1", ""],
        ],
    )
    _write_csv(gtfs / "stop_times.txt",
        ["trip_id", "arrival_time", "departure_time", "stop_id",
         "stop_sequence", "stop_headsign", "pickup_type", "shape_dist_traveled"],
        [
            # Southbound weekday: Howard → Belmont → 95th
            ["T_WK_S", "08:00:00", "08:00:00", "1001", "1", "95th/Dan Ryan", "0", "0"],
            ["T_WK_S", "08:15:00", "08:15:00", "1002", "2", "95th/Dan Ryan", "0", "0"],
            ["T_WK_S", "08:45:00", "08:45:00", "1003", "3", "95th/Dan Ryan", "0", "0"],
            # Southbound saturday: same shape but different time
            ["T_SA_S", "09:00:00", "09:00:00", "1001", "1", "95th/Dan Ryan", "0", "0"],
            ["T_SA_S", "09:15:00", "09:15:00", "1002", "2", "95th/Dan Ryan", "0", "0"],
            # Northbound weekday: 95th → Howard
            ["T_WK_N", "10:00:00", "10:00:00", "1003", "1", "Howard", "0", "0"],
            ["T_WK_N", "10:30:00", "10:30:00", "1001", "2", "Howard", "0", "0"],
        ],
    )

    import build_schedule_index as b
    out = tmp_path / "out"
    monkeypatch.setattr(b, "GTFS_DIR", gtfs)
    monkeypatch.setattr(b, "OUT_DIR", out)
    b.build()
    return out


def test_build_emits_per_route_files(fixture_gtfs):
    assert (fixture_gtfs / "Red.json").exists()
    assert (fixture_gtfs / "22.json").exists() is False, \
        "Route 22 has no trips in the fixture — should not emit a file."


def test_build_red_route_structure(fixture_gtfs):
    data = json.loads((fixture_gtfs / "Red.json").read_text(encoding="utf-8"))
    assert data["route_id"] == "Red"
    assert data["category"] == "train"
    # Two directions (0 = south, 1 = north).
    dirs = {d["direction_id"]: d for d in data["directions"]}
    assert set(dirs) == {"0", "1"}
    south = dirs["0"]
    # Stop ordering must follow stop_sequence.
    seq_order = [s["stop_id"] for s in south["stops"]]
    assert seq_order == ["1001", "1002", "1003"]
    # Headsign captured.
    assert south["headsign"] == "95th/Dan Ryan"


def test_build_service_day_bucketing(fixture_gtfs):
    data = json.loads((fixture_gtfs / "Red.json").read_text(encoding="utf-8"))
    south = next(d for d in data["directions"] if d["direction_id"] == "0")
    howard = south["stops"][0]
    assert howard["times"]["weekday"] == ["08:00"]
    assert howard["times"]["saturday"] == ["09:00"]
    # July 4 calendar_dates override on WK service folds those trips into sunday.
    assert "08:00" in howard["times"]["sunday"]


def test_build_manifest_structure(fixture_gtfs):
    m = json.loads((fixture_gtfs / "_manifest.json").read_text(encoding="utf-8"))
    rids = {r["route_id"] for r in m["routes"]}
    # Red Line had trips so it ships in the manifest; 22/X9 had no trips.
    assert "Red" in rids
    # Reverse stop→routes index populated.
    assert m["stop_routes"]["1001"] == ["Red"]


def test_build_category_ordering(fixture_gtfs):
    """Manifest orders trains before bus categories (picker section order)."""
    # The fixture only emits Red — extend with a bus trip would be heavier;
    # we just confirm the train comes first when present.
    m = json.loads((fixture_gtfs / "_manifest.json").read_text(encoding="utf-8"))
    assert m["routes"][0]["category"] == "train"
