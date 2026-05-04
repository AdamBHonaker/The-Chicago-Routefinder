"""
Unit tests for sessions.py.

Sessions involve time-sensitive behaviour (idle timeout, daily salt rotation),
so the tests freeze ``time.time`` and the Chicago-date helper at known values
and drive the module forward by mutating those mocks between calls.
"""

import time as _time
import pytest
from unittest.mock import patch

import sessions


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    f = tmp_path / "sessions.json"
    with patch.object(sessions, "SESSIONS_FILE", f):
        sessions._daily.clear()
        sessions._active.clear()
        sessions._current_day = ""
        sessions._writes_since_flush = 0
        yield


# ---------------------------------------------------------------------------
# new_session_id / hashing
# ---------------------------------------------------------------------------

def test_new_session_id_is_unique_and_urlsafe():
    a = sessions.new_session_id()
    b = sessions.new_session_id()
    assert a != b
    # url-safe base64: only [A-Za-z0-9_-]
    import re
    assert re.fullmatch(r"[A-Za-z0-9_-]+", a)
    assert len(a) >= 24  # token_urlsafe(24) → ~32 chars


def test_hash_changes_when_day_changes():
    sid = "abc123"
    h1 = sessions._hash_sid(sid, "2026-05-04")
    h2 = sessions._hash_sid(sid, "2026-05-05")
    assert h1 != h2


# ---------------------------------------------------------------------------
# touch — basic flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_touch_with_no_cookie_creates_new_session():
    sid = await sessions.touch(None, is_recommend=False)
    assert isinstance(sid, str) and len(sid) > 0
    # Active map has exactly one session with recommend_count=0.
    assert len(sessions._active) == 1
    state = next(iter(sessions._active.values()))
    assert state["recommend_count"] == 0


@pytest.mark.asyncio
async def test_touch_with_existing_cookie_reuses_session():
    sid = await sessions.touch(None, is_recommend=False)
    sid2 = await sessions.touch(sid, is_recommend=True)
    assert sid == sid2
    assert len(sessions._active) == 1
    state = next(iter(sessions._active.values()))
    assert state["recommend_count"] == 1


@pytest.mark.asyncio
async def test_touch_with_unknown_cookie_starts_fresh():
    """A cookie value the server doesn't recognise (e.g. one issued
    yesterday whose hash no longer matches) should start a new session."""
    sid = await sessions.touch("forged-or-stale-cookie", is_recommend=False)
    assert sid != "forged-or-stale-cookie"
    assert len(sessions._active) == 1


# ---------------------------------------------------------------------------
# Bounce + duration finalisation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_idle_timeout_finalises_session_as_bounce():
    """A session with zero or one /recommend that goes idle is a bounce."""
    real_time = _time.time
    t0 = real_time()
    with patch.object(sessions.time, "time", return_value=t0):
        sid = await sessions.touch(None, is_recommend=True)  # 1 recommend → bounce
    # Jump forward past the idle timeout.
    with patch.object(sessions.time, "time", return_value=t0 + sessions.IDLE_TIMEOUT_SECONDS + 60):
        await sessions.touch(None, is_recommend=False)  # any new request triggers idle cleanup

    today = sessions._today_chi()
    bucket = sessions._daily[today]
    assert bucket["sessions"] == 1
    assert bucket["bounces"] == 1


@pytest.mark.asyncio
async def test_idle_timeout_finalises_engaged_session_not_a_bounce():
    """Two or more /recommend → not a bounce."""
    real_time = _time.time
    t0 = real_time()
    with patch.object(sessions.time, "time", return_value=t0):
        sid = await sessions.touch(None, is_recommend=True)
    with patch.object(sessions.time, "time", return_value=t0 + 30):
        await sessions.touch(sid, is_recommend=True)
    with patch.object(sessions.time, "time", return_value=t0 + sessions.IDLE_TIMEOUT_SECONDS + 60):
        await sessions.touch(None, is_recommend=False)

    today = sessions._today_chi()
    bucket = sessions._daily[today]
    assert bucket["sessions"] == 1
    assert bucket["bounces"] == 0
    # Duration is from start (t0) to last_seen (t0+30).
    assert 25 <= bucket["total_duration_seconds"] <= 35


# ---------------------------------------------------------------------------
# get_counts derived fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_counts_decorates_avg_and_bounce_rate():
    sessions._daily["2026-05-04"] = {
        "sessions": 4, "total_duration_seconds": 400, "bounces": 1,
    }
    out = await sessions.get_counts()
    day = out["2026-05-04"]
    assert day["sessions"] == 4
    assert day["avg_duration_seconds"] == 100.0
    assert day["bounce_rate_pct"] == 25.0


@pytest.mark.asyncio
async def test_get_counts_zero_sessions_no_division_by_zero():
    sessions._daily["2026-05-04"] = {"sessions": 0, "total_duration_seconds": 0, "bounces": 0}
    out = await sessions.get_counts()
    assert out["2026-05-04"]["avg_duration_seconds"] == 0.0
    assert out["2026-05-04"]["bounce_rate_pct"] == 0.0
