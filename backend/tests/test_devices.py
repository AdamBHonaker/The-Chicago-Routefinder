"""Unit tests for devices.py."""

import json
import pytest
from unittest.mock import patch

import devices


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    devices_file = tmp_path / "devices.json"
    with patch.object(devices, "DEVICES_FILE", devices_file):
        devices._counts.clear()
        devices._current_day = ""
        devices._writes_since_flush = 0
        yield


# ---------------------------------------------------------------------------
# classify (pure function — runs without ua-parser installed)
# ---------------------------------------------------------------------------

def test_classify_none():
    assert devices.classify(None) == "unknown"


def test_classify_empty():
    assert devices.classify("") == "unknown"


def test_classify_iphone_is_mobile():
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
    assert devices.classify(ua) == "mobile"


def test_classify_android_is_mobile():
    ua = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Mobile"
    assert devices.classify(ua) == "mobile"


def test_classify_ipad_is_tablet():
    ua = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
    assert devices.classify(ua) == "tablet"


def test_classify_desktop_chrome():
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126"
    assert devices.classify(ua) == "desktop"


def test_classify_known_bot():
    ua = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    assert devices.classify(ua) == "bot"


def test_classify_curl_is_bot():
    assert devices.classify("curl/8.4.0") == "bot"


# ---------------------------------------------------------------------------
# record_visit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_visit_increments_bucket():
    bucket = await devices.record_visit("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)")
    assert bucket == "mobile"
    counts = await devices.get_counts()
    today = devices._today_chi()
    assert counts[today]["mobile"] == 1
    assert counts[today]["desktop"] == 0


@pytest.mark.asyncio
async def test_record_visit_unknown_bucket_for_empty_ua():
    bucket = await devices.record_visit(None)
    assert bucket == "unknown"
    counts = await devices.get_counts()
    today = devices._today_chi()
    assert counts[today]["unknown"] == 1


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_save_load_roundtrip(tmp_path):
    f = tmp_path / "devices.json"
    payload = {"2026-05-04": {"mobile": 12, "tablet": 1, "desktop": 4, "bot": 0, "unknown": 0}}
    with patch.object(devices, "DEVICES_FILE", f):
        devices._save(payload)
        result = devices._load()
    assert result == payload


def test_load_corrupt_returns_empty(tmp_path):
    f = tmp_path / "devices.json"
    f.write_text("{not json", encoding="utf-8")
    with patch.object(devices, "DEVICES_FILE", f):
        assert devices._load() == {}
