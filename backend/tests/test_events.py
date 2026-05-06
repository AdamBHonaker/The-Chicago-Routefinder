"""Unit tests for events.py (FEAT-006)."""

import pytest
from unittest.mock import patch

import events


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    f = tmp_path / "events.json"
    with patch.object(events, "EVENTS_FILE", f):
        events._counts.clear()
        events._current_day = ""
        events._writes_since_flush = 0
        yield


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------

def test_allowlist_contains_documented_events():
    """The eight names documented in docs/FEATURE_PLANS.md FEAT-006 must all
    be in the allowlist; a future contributor reading the scope should not
    find a name listed there that the code rejects."""
    expected = {
        "app_loaded",
        "recommend_submitted",
        "recommend_returned",
        "route_selected",
        "start_route_tapped",
        "map_opened",
        "house_ad_clicked",
        "trip_completed",
    }
    assert events.EVENT_ALLOWLIST == frozenset(expected)


def test_is_allowed():
    assert events.is_allowed("recommend_submitted") is True
    assert events.is_allowed("not_a_real_event") is False
    assert events.is_allowed("") is False


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_increments_counter():
    await events.record("recommend_submitted")
    await events.record("recommend_submitted")
    await events.record("route_selected")
    counts = await events.get_counts()
    today = events._today_chi()
    assert counts[today]["recommend_submitted"] == 2
    assert counts[today]["route_selected"] == 1


@pytest.mark.asyncio
async def test_record_rejects_unknown_name():
    """record() asserts on unknown names so a future contributor cannot
    bypass the API-edge allowlist by calling record() directly."""
    with pytest.raises(ValueError):
        await events.record("definitely_not_allowed")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_load_corrupt_returns_empty(tmp_path):
    f = tmp_path / "events.json"
    f.write_text("{garbage", encoding="utf-8")
    with patch.object(events, "EVENTS_FILE", f):
        assert events._load() == {}


def test_load_coerces_non_dict_day(tmp_path):
    """Defense against a malformed on-disk record."""
    f = tmp_path / "events.json"
    f.write_text(
        '{"2026-05-04": "not a dict", "2026-05-05": {"app_loaded": 3}}',
        encoding="utf-8",
    )
    with patch.object(events, "EVENTS_FILE", f):
        out = events._load()
    # Bad day dropped, good day preserved.
    assert "2026-05-04" not in out
    assert out["2026-05-05"] == {"app_loaded": 3}


def test_save_load_roundtrip(tmp_path):
    f = tmp_path / "events.json"
    payload = {"2026-05-04": {"recommend_submitted": 12, "trip_completed": 3}}
    with patch.object(events, "EVENTS_FILE", f):
        events._save(payload)
        out = events._load()
    assert out == payload


@pytest.mark.asyncio
async def test_day_rollover_preserves_unflushed_increments():
    """Regression test: BUG-007 — day rollover used to clobber unflushed counts."""
    day_a = "2026-05-05"
    day_b = "2026-05-06"

    with patch.object(events, "_today_chi", return_value=day_a):
        await events.record("recommend_submitted")
        await events.record("recommend_returned")
        await events.record("route_selected")

    assert events._counts[day_a]["recommend_submitted"] == 1
    assert events._counts[day_a]["recommend_returned"] == 1
    assert events._counts[day_a]["route_selected"] == 1
    assert events._writes_since_flush == 3  # not yet flushed (default 20)

    with patch.object(events, "_today_chi", return_value=day_b):
        await events.record("trip_completed")

    counts = await events.get_counts()
    # Day A's funnel-stage events must survive the rollover.
    assert counts[day_a]["recommend_submitted"] == 1
    assert counts[day_a]["recommend_returned"] == 1
    assert counts[day_a]["route_selected"] == 1
    assert counts[day_b]["trip_completed"] == 1
