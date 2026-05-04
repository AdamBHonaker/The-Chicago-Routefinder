"""Unit tests for hourly.py."""

import pytest
from unittest.mock import patch

import hourly


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    f = tmp_path / "hourly.json"
    with patch.object(hourly, "HOURLY_FILE", f):
        hourly._counts.clear()
        hourly._current_day = ""
        hourly._writes_since_flush = 0
        yield


@pytest.mark.asyncio
async def test_record_recommend_increments_current_hour():
    with patch.object(hourly, "_now_hour_chi", return_value=14):
        await hourly.record_recommend()
        await hourly.record_recommend()
    counts = await hourly.get_counts()
    today = hourly._today_chi()
    arr = counts[today]
    assert len(arr) == 24
    assert arr[14] == 2
    assert arr[15] == 0
    assert sum(arr) == 2


@pytest.mark.asyncio
async def test_record_recommend_separate_hours():
    with patch.object(hourly, "_now_hour_chi", return_value=8):
        await hourly.record_recommend()
    with patch.object(hourly, "_now_hour_chi", return_value=17):
        await hourly.record_recommend()
        await hourly.record_recommend()
    today = hourly._today_chi()
    arr = (await hourly.get_counts())[today]
    assert arr[8] == 1
    assert arr[17] == 2


def test_load_corrupt_returns_empty(tmp_path):
    f = tmp_path / "hourly.json"
    f.write_text("{garbage", encoding="utf-8")
    with patch.object(hourly, "HOURLY_FILE", f):
        assert hourly._load() == {}


def test_load_coerces_wrong_length_to_zero_array(tmp_path):
    """Defense against an old on-disk record from a future schema change."""
    f = tmp_path / "hourly.json"
    f.write_text('{"2026-05-04": [1, 2, 3]}', encoding="utf-8")  # length 3
    with patch.object(hourly, "HOURLY_FILE", f):
        out = hourly._load()
    assert len(out["2026-05-04"]) == 24
    assert all(v == 0 for v in out["2026-05-04"])


def test_save_load_roundtrip(tmp_path):
    f = tmp_path / "hourly.json"
    payload = {"2026-05-04": [0] * 24}
    payload["2026-05-04"][9] = 5
    with patch.object(hourly, "HOURLY_FILE", f):
        hourly._save(payload)
        out = hourly._load()
    assert out == payload
