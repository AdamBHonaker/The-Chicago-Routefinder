"""
Unit tests for dau.py.

Coverage targets:
  _today_chi:
    - Returns a string in YYYY-MM-DD format
    - Returns today's Chicago date

  _load / _save:
    - _load returns {} for missing file
    - _load returns {} for corrupted JSON
    - _load / _save round-trip

  record_visit / get_counts (async):
    - First unique visitor increments today's count
    - Same IP does not increment count twice
    - Different IPs are each counted
    - get_counts returns an empty dict when no visits recorded
"""

import json
import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo

import dau


CHICAGO_TZ = ZoneInfo("America/Chicago")


# ---------------------------------------------------------------------------
# _today_chi
# ---------------------------------------------------------------------------

def test_today_chi_format():
    result = dau._today_chi()
    # Must be YYYY-MM-DD
    datetime.strptime(result, "%Y-%m-%d")


def test_today_chi_matches_chicago_now():
    expected = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
    assert dau._today_chi() == expected


# ---------------------------------------------------------------------------
# _load / _save
# ---------------------------------------------------------------------------

def test_load_missing_file(tmp_path):
    with patch.object(dau, "DAU_FILE", tmp_path / "missing.json"):
        result = dau._load()
    assert result == {}


def test_load_corrupted_json(tmp_path):
    bad_file = tmp_path / "dau.json"
    bad_file.write_text("not-json{{", encoding="utf-8")
    with patch.object(dau, "DAU_FILE", bad_file):
        result = dau._load()
    assert result == {}


def test_save_and_load_roundtrip(tmp_path):
    dau_file = tmp_path / "dau.json"
    counts = {"2026-04-28": 42, "2026-04-27": 10}
    with patch.object(dau, "DAU_FILE", dau_file):
        dau._save(counts)
        result = dau._load()
    assert result == counts


# ---------------------------------------------------------------------------
# record_visit / get_counts (async)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_dau_state(tmp_path):
    """Reset in-memory DAU state and redirect file I/O to tmp_path."""
    dau_file = tmp_path / "dau.json"
    with patch.object(dau, "DAU_FILE", dau_file):
        dau._current_day = ""
        dau._seen_hashes = set()
        dau._base_count = 0
        dau._counts_cache.clear()
        dau._visitors_since_last_flush = 0
        yield


def _today_count():
    """Read today's count from the in-memory cache."""
    today = dau._today_chi()
    return dau._counts_cache.get(today, 0)


@pytest.mark.asyncio
async def test_first_visit_increments():
    await dau.record_visit("192.168.1.1")
    assert _today_count() >= 1


@pytest.mark.asyncio
async def test_duplicate_ip_not_counted_twice():
    await dau.record_visit("192.168.1.1")
    await dau.record_visit("192.168.1.1")
    assert _today_count() == 1


@pytest.mark.asyncio
async def test_different_ips_both_counted():
    await dau.record_visit("192.168.1.1")
    await dau.record_visit("10.0.0.1")
    assert _today_count() == 2


@pytest.mark.asyncio
async def test_get_counts_empty_initially():
    counts = await dau.get_counts()
    today = dau._today_chi()
    assert counts.get(today, 0) == 0
