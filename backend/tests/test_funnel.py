"""Unit tests for funnel.py (FEAT-007)."""

import pytest
from unittest.mock import patch

import funnel


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    f = tmp_path / "funnel.json"
    with patch.object(funnel, "FUNNEL_FILE", f):
        funnel._counts.clear()
        funnel._writes_since_flush = 0
        yield


# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

def test_funnel_stages_order():
    """The canonical stage order must match the advertiser-facing narrative."""
    assert funnel.FUNNEL_STAGES[0] == "app_loaded"
    assert funnel.FUNNEL_STAGES[2] == "recommend_returned"
    assert funnel.FUNNEL_STAGES[-1] == "trip_completed"
    assert len(funnel.FUNNEL_STAGES) == 6


def test_stage_index_known():
    assert funnel.stage_index("app_loaded") == 0
    assert funnel.stage_index("recommend_returned") == 2
    assert funnel.stage_index("trip_completed") == 5


def test_stage_index_unknown():
    assert funnel.stage_index("not_a_stage") == -1
    assert funnel.stage_index("") == -1


def test_is_stage():
    assert funnel.is_stage("recommend_submitted") is True
    assert funnel.is_stage("house_ad_clicked") is False


# ---------------------------------------------------------------------------
# record_finalized
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_finalized_noop_on_negative_stage():
    await funnel.record_finalized("2026-05-04", -1)
    counts = await funnel.get_counts()
    assert "2026-05-04" not in counts


@pytest.mark.asyncio
async def test_record_finalized_increments_cumulative_stages():
    """A session ending at stage 2 should increment stages 0, 1, and 2."""
    await funnel.record_finalized("2026-05-04", 2)
    counts = await funnel.get_counts()
    arr = counts["2026-05-04"]
    assert arr[0] == 1  # app_loaded
    assert arr[1] == 1  # recommend_submitted
    assert arr[2] == 1  # recommend_returned
    assert arr[3] == 0  # route_selected — not reached
    assert arr[4] == 0
    assert arr[5] == 0


@pytest.mark.asyncio
async def test_record_finalized_multiple_sessions():
    """100 sessions at stage 0, 97 reach stage 2, 40 reach stage 5."""
    for _ in range(100):
        await funnel.record_finalized("2026-05-04", 0)
    for _ in range(97):
        await funnel.record_finalized("2026-05-04", 2)
    for _ in range(40):
        await funnel.record_finalized("2026-05-04", 5)
    counts = await funnel.get_counts()
    arr = counts["2026-05-04"]
    # Cumulative "at least" counts:
    # Stage 0: 100 + 97 + 40 = 237
    assert arr[0] == 237
    # Stage 2: 97 + 40 = 137
    assert arr[2] == 137
    # Stage 5: 40
    assert arr[5] == 40


@pytest.mark.asyncio
async def test_record_finalized_clamps_to_num_stages():
    """Stage index beyond the array length must not raise or corrupt state."""
    await funnel.record_finalized("2026-05-04", 100)
    counts = await funnel.get_counts()
    # All six slots should be 1 (clamped to _NUM_STAGES).
    assert counts["2026-05-04"] == [1] * 6


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_load_corrupt_returns_empty(tmp_path):
    f = tmp_path / "funnel.json"
    f.write_text("{garbage", encoding="utf-8")
    with patch.object(funnel, "FUNNEL_FILE", f):
        assert funnel._load() == {}


def test_load_skips_wrong_length(tmp_path):
    """Arrays with the wrong number of stages are skipped (schema mismatch)."""
    import json
    f = tmp_path / "funnel.json"
    f.write_text(json.dumps({
        "2026-05-04": [1, 2, 3],       # wrong length — 3, not 6
        "2026-05-05": [10, 9, 8, 7, 6, 5],  # correct
    }), encoding="utf-8")
    with patch.object(funnel, "FUNNEL_FILE", f):
        out = funnel._load()
    assert "2026-05-04" not in out
    assert out["2026-05-05"] == [10, 9, 8, 7, 6, 5]


@pytest.mark.asyncio
async def test_save_load_roundtrip(tmp_path):
    f = tmp_path / "funnel.json"
    payload = {"2026-05-04": [100, 97, 95, 80, 60, 40]}
    with patch.object(funnel, "FUNNEL_FILE", f):
        funnel._save(payload)
        out = funnel._load()
    assert out == payload


# ---------------------------------------------------------------------------
# Integration with sessions: advance_funnel_stage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_advance_funnel_stage_updates_session(tmp_path):
    """After advance_funnel_stage, the session's funnel_stage field is updated."""
    import sessions
    sf = tmp_path / "sessions.json"
    ff = tmp_path / "funnel2.json"
    with patch.object(sessions, "SESSIONS_FILE", sf), \
         patch.object(funnel, "FUNNEL_FILE", ff):
        sessions._daily.clear()
        sessions._active.clear()
        sessions._current_day = ""
        sessions._writes_since_flush = 0
        funnel._counts.clear()

        # Create a session by touching with a known sid.
        raw_sid = await sessions.touch(None, is_recommend=False)
        # At this point funnel_stage should be -1 (just created).
        h = sessions._hash_sid(raw_sid, sessions._today_chi())
        assert sessions._active[h]["funnel_stage"] == -1

        # Advance to app_loaded (stage 0).
        await sessions.advance_funnel_stage(raw_sid, "app_loaded")
        assert sessions._active[h]["funnel_stage"] == 0

        # Advance to recommend_returned (stage 2) — should skip over stage 1.
        await sessions.advance_funnel_stage(raw_sid, "recommend_returned")
        assert sessions._active[h]["funnel_stage"] == 2

        # A lower-stage event must NOT roll back the stage.
        await sessions.advance_funnel_stage(raw_sid, "recommend_submitted")
        assert sessions._active[h]["funnel_stage"] == 2


@pytest.mark.asyncio
async def test_advance_funnel_stage_unknown_sid_is_noop(tmp_path):
    """An unknown SID must not raise or create a phantom entry."""
    import sessions
    sf = tmp_path / "sessions.json"
    with patch.object(sessions, "SESSIONS_FILE", sf):
        sessions._active.clear()
        await sessions.advance_funnel_stage("no-such-sid", "app_loaded")
        # No crash, no entry created.
        assert len(sessions._active) == 0


@pytest.mark.asyncio
async def test_advance_funnel_stage_non_stage_event_is_noop(tmp_path):
    """An event that is not a funnel stage must not change funnel_stage."""
    import sessions
    sf = tmp_path / "sessions.json"
    with patch.object(sessions, "SESSIONS_FILE", sf):
        sessions._daily.clear()
        sessions._active.clear()
        sessions._current_day = ""
        raw_sid = await sessions.touch(None, is_recommend=False)
        h = sessions._hash_sid(raw_sid, sessions._today_chi())
        await sessions.advance_funnel_stage(raw_sid, "house_ad_clicked")
        assert sessions._active[h]["funnel_stage"] == -1
