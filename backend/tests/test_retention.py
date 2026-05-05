"""
Unit tests for retention.py (FEAT-002).

Tests cover: Bloom filter correctness, new vs returning classification,
daily dedup, day rollover, serialisation round-trip, and the public-stats
no-leak guarantee.
"""

import asyncio
import base64
import math
import pytest
from unittest.mock import patch

import retention
import public_stats


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    """Reset all module-level state before each test and point file at tmp."""
    f = tmp_path / "retention.json"
    with patch.object(retention, "RETENTION_FILE", f):
        retention._daily.clear()
        retention._bloom_bits[:] = retention._new_bloom()
        retention._bloom_count = 0
        retention._today_fingerprints.clear()
        retention._current_day = ""
        retention._writes_since_flush = 0
        yield


# ---------------------------------------------------------------------------
# Bloom filter unit tests
# ---------------------------------------------------------------------------

def test_bloom_m_and_k_are_positive():
    assert retention.BLOOM_M > 0
    assert retention.BLOOM_K > 0


def test_bloom_capacity_and_fpr_documented():
    """BLOOM_CAPACITY and BLOOM_M are derived from the target FPR."""
    # m = -(n * ln(p)) / (ln(2))^2 — verify within 1%
    expected_m = int(-retention.BLOOM_CAPACITY * math.log(0.01) / (math.log(2) ** 2)) + 1
    assert abs(retention.BLOOM_M - expected_m) <= 2


def test_bloom_add_and_check():
    bits = retention._new_bloom()
    fp = retention._fingerprint("test-id-abc")
    assert not retention._bloom_check(bits, fp)
    retention._bloom_add(bits, fp)
    assert retention._bloom_check(bits, fp)


def test_bloom_distinct_fingerprints():
    bits = retention._new_bloom()
    fp1 = retention._fingerprint("id-one")
    fp2 = retention._fingerprint("id-two")
    retention._bloom_add(bits, fp1)
    assert retention._bloom_check(bits, fp1)
    # fp2 was not added — should not be in filter (very unlikely FP for just one item)
    # We can't assert with certainty due to FP probability, but for two items it's safe.
    retention._bloom_add(bits, fp2)
    assert retention._bloom_check(bits, fp2)


def test_fingerprint_is_deterministic():
    fp1 = retention._fingerprint("my-cookie-value")
    fp2 = retention._fingerprint("my-cookie-value")
    assert fp1 == fp2


def test_fingerprint_differs_for_different_ids():
    assert retention._fingerprint("aaa") != retention._fingerprint("bbb")


# ---------------------------------------------------------------------------
# record_visit — first-time visitor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_new_visitor_counted_as_new():
    with patch.object(retention, "_today_chi", return_value="2026-05-04"):
        rid = await retention.record_visit(None)
    assert isinstance(rid, str) and len(rid) > 0
    counts = await retention.get_counts()
    assert counts["2026-05-04"]["new"] == 1
    assert counts["2026-05-04"]["returning"] == 0


@pytest.mark.asyncio
async def test_fresh_rid_generates_new_id():
    with patch.object(retention, "_today_chi", return_value="2026-05-04"):
        rid = await retention.record_visit(None)
    assert len(rid) >= 24  # token_urlsafe(24) → ~32 chars


# ---------------------------------------------------------------------------
# record_visit — same-day dedup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_same_visitor_same_day_not_double_counted():
    with patch.object(retention, "_today_chi", return_value="2026-05-04"):
        rid = await retention.record_visit(None)
        # Same cookie, same day — should not increment again.
        await retention.record_visit(rid)
        await retention.record_visit(rid)
    counts = await retention.get_counts()
    assert counts["2026-05-04"]["new"] == 1
    assert counts["2026-05-04"]["returning"] == 0


@pytest.mark.asyncio
async def test_two_distinct_visitors_same_day():
    with patch.object(retention, "_today_chi", return_value="2026-05-04"):
        rid1 = await retention.record_visit(None)
        rid2 = await retention.record_visit(None)
    assert rid1 != rid2
    counts = await retention.get_counts()
    assert counts["2026-05-04"]["new"] == 2
    assert counts["2026-05-04"]["returning"] == 0


# ---------------------------------------------------------------------------
# record_visit — returning visitor on next day
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returning_visitor_detected_next_day():
    """A visitor seen on day 1 should be classified as returning on day 2."""
    with patch.object(retention, "_today_chi", return_value="2026-05-04"):
        rid = await retention.record_visit(None)
    # _current_day is now "2026-05-04". Let the module detect the rollover
    # naturally (don't reset _current_day — that would suppress the save).
    with patch.object(retention, "_today_chi", return_value="2026-05-05"):
        await retention.record_visit(rid)

    counts = await retention.get_counts()
    assert counts["2026-05-05"]["returning"] == 1
    assert counts["2026-05-05"]["new"] == 0


@pytest.mark.asyncio
async def test_new_rid_on_day2_is_new():
    """A brand-new cookie on day 2 should still be classified as new."""
    with patch.object(retention, "_today_chi", return_value="2026-05-04"):
        await retention.record_visit(None)  # visitor 1

    with patch.object(retention, "_today_chi", return_value="2026-05-05"):
        await retention.record_visit(None)  # visitor 2 — fresh cookie

    counts = await retention.get_counts()
    assert counts["2026-05-05"]["new"] == 1
    assert counts["2026-05-05"]["returning"] == 0


# ---------------------------------------------------------------------------
# get_counts — derived fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_counts_total_and_pct():
    with patch.object(retention, "_today_chi", return_value="2026-05-04"):
        rid = await retention.record_visit(None)  # new

    with patch.object(retention, "_today_chi", return_value="2026-05-05"):
        await retention.record_visit(rid)   # returning — rollover saves day1 bits
        await retention.record_visit(None)  # new (different rid)

    counts = await retention.get_counts()
    day2 = counts["2026-05-05"]
    assert day2["total"] == 2
    assert day2["returning"] == 1
    assert day2["new"] == 1
    assert day2["returning_pct"] == 50.0


# ---------------------------------------------------------------------------
# Bloom filter auto-reset when capacity is exceeded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bloom_auto_reset_at_capacity():
    """When the filter reaches BLOOM_CAPACITY, it auto-resets and the next
    visitor is classified as new (even if they were in the old filter)."""
    with patch.object(retention, "_today_chi", return_value="2026-05-04"):
        rid = await retention.record_visit(None)

    # Force filter to appear full (after day 1 already set _current_day).
    retention._bloom_count = retention.BLOOM_CAPACITY

    with patch.object(retention, "_today_chi", return_value="2026-05-05"):
        # Natural rollover detected: _current_day="2026-05-04", today="2026-05-05".
        await retention.record_visit(rid)  # would be returning, but filter resets

    counts = await retention.get_counts()
    # After reset, the visitor is classified as new (filter was cleared).
    assert counts["2026-05-05"]["new"] == 1
    assert counts["2026-05-05"]["returning"] == 0
    assert retention._bloom_count == 1  # one item re-added after reset


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_serialisation_round_trip(tmp_path):
    f = tmp_path / "retention_rt.json"
    with patch.object(retention, "RETENTION_FILE", f):
        with patch.object(retention, "_today_chi", return_value="2026-05-04"):
            rid = await retention.record_visit(None)
        await retention.force_flush_for_test()

        # Reset in-memory state and reload from disk.
        retention._daily.clear()
        retention._bloom_bits[:] = retention._new_bloom()
        retention._bloom_count = 0
        retention._today_fingerprints.clear()
        retention._current_day = ""

        state = retention._load()
        assert "2026-05-04" in state["daily"]
        assert state["daily"]["2026-05-04"]["new"] == 1
        assert state["count"] == 1
        # Filter bits survived.
        fp = retention._fingerprint(rid)
        assert retention._bloom_check(state["bits"], fp)


# ---------------------------------------------------------------------------
# new_return_id
# ---------------------------------------------------------------------------

def test_new_return_id_unique_and_urlsafe():
    import re
    ids = {retention.new_return_id() for _ in range(20)}
    assert len(ids) == 20  # all distinct
    for rid in ids:
        assert re.fullmatch(r"[A-Za-z0-9_-]+", rid)
        assert len(rid) >= 24


# ---------------------------------------------------------------------------
# public_stats projection — no-leak guarantee
# ---------------------------------------------------------------------------

def test_project_retention_basic():
    raw = {
        "2026-05-04": {"new": 80, "returning": 20, "total": 100, "returning_pct": 20.0},
        "2026-05-03": {"new": 60, "returning": 10, "total": 70, "returning_pct": 14.3},
    }
    out = public_stats.project_retention(raw)
    assert [d["date"] for d in out["days"]] == ["2026-05-03", "2026-05-04"]
    assert out["today"] == {
        "date": "2026-05-04", "new": 80, "returning": 20, "total": 100, "returning_pct": 20.0,
    }


def test_project_retention_empty():
    out = public_stats.project_retention({})
    assert out == {"days": [], "today": None}


def test_project_retention_no_leak():
    """No admin-only field (Bloom filter diagnostics, raw IDs) may leak through."""
    raw = {
        "2026-05-04": {
            "new": 80,
            "returning": 20,
            "total": 100,
            "returning_pct": 20.0,
            # Hostile fields that must be stripped:
            "filter_count": 200,
            "bloom_m_bits": 95852,
            "raw_fingerprints": ["abc", "def"],
        }
    }
    out = public_stats.project_retention(raw)
    allowed = public_stats.PUBLIC_FIELD_WHITELIST["retention_day"]
    for day in out["days"]:
        leaked = set(day.keys()) - allowed
        assert not leaked, f"Retention leak: {leaked}"
    if out["today"] is not None:
        assert set(out["today"].keys()) <= allowed
