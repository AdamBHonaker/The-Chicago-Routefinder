"""Unit tests for referrers.py."""

import pytest
from unittest.mock import patch

import referrers


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    f = tmp_path / "referrers.json"
    with patch.object(referrers, "REFERRERS_FILE", f):
        referrers._counts.clear()
        referrers._current_day = ""
        referrers._writes_since_flush = 0
        yield


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------

def test_classify_empty_is_direct():
    assert referrers.classify(None) == ("direct", None)
    assert referrers.classify("") == ("direct", None)


def test_classify_self_referral_is_direct():
    own = frozenset({"cta-transit.example.com"})
    assert referrers.classify("https://cta-transit.example.com/path", own_hostnames=own) == ("direct", None)


def test_classify_google_is_search():
    bucket, host = referrers.classify("https://www.google.com/search?q=cta")
    assert bucket == "search"
    assert host == "www.google.com"


def test_classify_google_co_uk_is_search():
    bucket, host = referrers.classify("https://www.google.co.uk/")
    assert bucket == "search"


def test_classify_duckduckgo_is_search():
    bucket, host = referrers.classify("https://duckduckgo.com/?q=test")
    assert bucket == "search"


def test_classify_facebook_is_social():
    bucket, host = referrers.classify("https://m.facebook.com/")
    assert bucket == "social"


def test_classify_twitter_x_is_social():
    assert referrers.classify("https://x.com/foo")[0] == "social"
    assert referrers.classify("https://twitter.com/foo")[0] == "social"
    assert referrers.classify("https://t.co/abc")[0] == "social"


def test_classify_unknown_host_is_other():
    bucket, host = referrers.classify("https://chicagotribune.com/article/123")
    assert bucket == "other"
    assert host == "chicagotribune.com"


def test_classify_strips_path_and_query():
    # The hostname returned should never include path or query.
    bucket, host = referrers.classify("https://example.com/very/deep/path?utm_source=secret")
    assert host == "example.com"


def test_classify_garbage_input_is_direct():
    bucket, host = referrers.classify("not a url")
    assert bucket == "direct"
    assert host is None


# ---------------------------------------------------------------------------
# record_visit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_visit_buckets_correctly():
    await referrers.record_visit(None)                                   # direct
    await referrers.record_visit("https://www.google.com/")              # search
    await referrers.record_visit("https://reddit.com/r/chicago")         # social
    await referrers.record_visit("https://chicagotribune.com/foo")       # other:chicagotribune.com
    await referrers.record_visit("https://chicagotribune.com/bar")       # other:chicagotribune.com again
    counts = await referrers.get_counts()
    today = referrers._today_chi()
    day = counts[today]
    assert day["direct"] == 1
    assert day["search"] == 1
    assert day["social"] == 1
    assert day["other"] == {"chicagotribune.com": 2}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_save_load_roundtrip(tmp_path):
    f = tmp_path / "referrers.json"
    payload = {"2026-05-04": {"direct": 12, "search": 5, "social": 2, "other": {"foo.com": 3}}}
    with patch.object(referrers, "REFERRERS_FILE", f):
        referrers._save(payload)
        result = referrers._load()
    assert result == payload
