"""
Unit tests for geography.py.

The MaxMind reader is stubbed via the module-level ``_city_for_ip`` so tests
don't need an actual GeoLite2 DB. We test the privacy floor, the metro
rollup, and the per-day rollover logic without touching geoip2.
"""

import json
import pytest
from unittest.mock import patch

import geography


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    geo_file = tmp_path / "geography.json"
    with patch.object(geography, "GEO_FILE", geo_file):
        geography._counts.clear()
        geography._current_day = ""
        geography._writes_since_flush = 0
        geography._reader = None
        yield


# ---------------------------------------------------------------------------
# _project_day (privacy floor)
# ---------------------------------------------------------------------------

def test_privacy_floor_buckets_rare_cities():
    raw = {"Chicago": 200, "Evanston": 50, "Pingree Grove": 2, "Sycamore": 1}
    out = geography._project_day(raw)
    assert out["Chicago"] == 200
    assert out["Evanston"] == 50
    assert "Pingree Grove" not in out
    assert "Sycamore" not in out
    assert out["Other"] == 3


def test_privacy_floor_passthrough_when_all_above_threshold():
    raw = {"Chicago": 100, "Evanston": 20}
    out = geography._project_day(raw)
    assert out == {"Chicago": 100, "Evanston": 20}


def test_privacy_floor_threshold_exactly_at_cutoff():
    # Threshold is 5: counts == 5 stay (>= threshold); counts < 5 bucket.
    raw = {"Chicago": 100, "Skokie": geography._OTHER_BUCKET_THRESHOLD,
           "Rare": geography._OTHER_BUCKET_THRESHOLD - 1}
    out = geography._project_day(raw)
    assert out["Skokie"] == geography._OTHER_BUCKET_THRESHOLD
    assert "Rare" not in out
    assert out["Other"] == geography._OTHER_BUCKET_THRESHOLD - 1


# ---------------------------------------------------------------------------
# chicago_metro_share
# ---------------------------------------------------------------------------

def test_metro_share_counts_metro_cities():
    raw = {"Chicago": 100, "Evanston": 20, "Naperville": 10, "Madison": 5, "Other": 0}
    metro, total = geography.chicago_metro_share(raw)
    assert metro == 130
    assert total == 135


def test_metro_share_case_insensitive():
    raw = {"CHICAGO": 50, "chicago": 50}
    metro, total = geography.chicago_metro_share(raw)
    assert metro == 100
    assert total == 100


def test_metro_share_empty():
    metro, total = geography.chicago_metro_share({})
    assert metro == 0
    assert total == 0


# ---------------------------------------------------------------------------
# record_visit / get_counts (async)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_visit_increments_city():
    with patch.object(geography, "_city_for_ip", return_value="Chicago"):
        await geography.record_visit("1.2.3.4")
        await geography.record_visit("5.6.7.8")
    counts = await geography.get_counts()
    today = geography._today_chi()
    # Two Chicago visits — below the privacy floor of 5 → bucketed into "Other".
    assert counts[today].get("Other", 0) == 2


@pytest.mark.asyncio
async def test_record_visit_none_city_noops():
    with patch.object(geography, "_city_for_ip", return_value=None):
        await geography.record_visit("10.0.0.1")
    counts = await geography.get_counts()
    today = geography._today_chi()
    assert counts.get(today, {}) == {}


@pytest.mark.asyncio
async def test_get_metro_summary_share_percent():
    # 6 Chicago + 4 Madison → 60% metro, 10 total. Both above zero so neither
    # bucketed; metro rollup uses raw counts not floored counts.
    def fake_city_for_ip(ip):
        return "Chicago" if ip.startswith("1.") else "Madison"

    with patch.object(geography, "_city_for_ip", side_effect=fake_city_for_ip):
        for i in range(6):
            await geography.record_visit(f"1.0.0.{i}")
        for i in range(4):
            await geography.record_visit(f"2.0.0.{i}")

    summary = await geography.get_metro_summary()
    today = geography._today_chi()
    assert summary[today]["metro"] == 6
    assert summary[today]["total"] == 10
    assert summary[today]["share_pct"] == 60.0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_save_load_roundtrip(tmp_path):
    geo_file = tmp_path / "geography.json"
    payload = {"2026-05-04": {"Chicago": 100, "Evanston": 20}}
    with patch.object(geography, "GEO_FILE", geo_file):
        geography._save(payload)
        result = geography._load()
    assert result == payload


def test_load_missing_returns_empty(tmp_path):
    with patch.object(geography, "GEO_FILE", tmp_path / "missing.json"):
        assert geography._load() == {}


def test_load_corrupt_returns_empty(tmp_path):
    bad = tmp_path / "geography.json"
    bad.write_text("{not json", encoding="utf-8")
    with patch.object(geography, "GEO_FILE", bad):
        assert geography._load() == {}
