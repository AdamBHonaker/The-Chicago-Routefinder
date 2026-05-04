"""
Tests for the public-stats projection (FEAT-009 v1).

The most important assertion is the **no-leak guarantee**: the public output
must contain only fields explicitly whitelisted in
``public_stats.PUBLIC_FIELD_WHITELIST``. If a future contributor adds a new
admin-only field to the underlying counters, this test fails before that
field can reach the public dashboard.
"""

import pytest

import public_stats


# ---------------------------------------------------------------------------
# project_dau
# ---------------------------------------------------------------------------

def test_project_dau_basic_shape():
    raw = {"2026-05-02": 10, "2026-05-04": 25, "2026-05-03": 17}
    out = public_stats.project_dau(raw)
    assert "days" in out
    assert "today" in out
    # Days returned in chronological order.
    assert [d["date"] for d in out["days"]] == ["2026-05-02", "2026-05-03", "2026-05-04"]
    # Today is the latest entry.
    assert out["today"] == {"date": "2026-05-04", "count": 25}


def test_project_dau_empty():
    out = public_stats.project_dau({})
    assert out == {"days": [], "today": None}


def test_project_dau_no_leak():
    """No field outside the whitelist may appear in any DAU day entry."""
    raw = {"2026-05-04": 10}
    out = public_stats.project_dau(raw)
    allowed = public_stats.PUBLIC_FIELD_WHITELIST["dau_day"]
    for day in out["days"]:
        assert set(day.keys()) <= allowed, f"DAU leak: {set(day.keys()) - allowed}"
    if out["today"] is not None:
        assert set(out["today"].keys()) <= allowed


# ---------------------------------------------------------------------------
# project_geography
# ---------------------------------------------------------------------------

def test_project_geography_basic_shape():
    raw = {
        "2026-05-04": {"metro": 80, "total": 100, "share_pct": 80.0},
        "2026-05-03": {"metro": 50, "total": 60, "share_pct": 83.3},
    }
    out = public_stats.project_geography(raw)
    assert [d["date"] for d in out["days"]] == ["2026-05-03", "2026-05-04"]
    assert out["today"] == {"date": "2026-05-04", "metro": 80, "total": 100, "share_pct": 80.0}


def test_project_geography_empty():
    out = public_stats.project_geography({})
    assert out == {"days": [], "today": None}


def test_project_geography_strips_per_city_table():
    """Even if upstream accidentally smuggles in a 'cities' field, projection drops it."""
    raw = {
        "2026-05-04": {
            "metro": 80, "total": 100, "share_pct": 80.0,
            # Hostile field — must NOT pass through.
            "cities": {"Chicago": 80, "Wilmette": 1},
            # Another hostile field.
            "raw_ip_hashes": ["abc", "def"],
        }
    }
    out = public_stats.project_geography(raw)
    allowed = public_stats.PUBLIC_FIELD_WHITELIST["geo_metro_day"]
    for day in out["days"]:
        leaked = set(day.keys()) - allowed
        assert not leaked, f"Geography leak: {leaked}"


def test_project_geography_no_leak_today_field():
    raw = {"2026-05-04": {"metro": 1, "total": 2, "share_pct": 50.0, "secret": "x"}}
    out = public_stats.project_geography(raw)
    allowed = public_stats.PUBLIC_FIELD_WHITELIST["geo_metro_day"]
    if out["today"] is not None:
        leaked = set(out["today"].keys()) - allowed
        assert not leaked, f"Geography today leak: {leaked}"


# ---------------------------------------------------------------------------
# project_sessions
# ---------------------------------------------------------------------------

def test_project_sessions_drops_admin_only_fields():
    raw = {
        "2026-05-04": {
            "sessions": 100, "total_duration_seconds": 12000, "bounces": 30,
            "avg_duration_seconds": 120.0, "bounce_rate_pct": 30.0,
            # Hostile field — must NOT pass through.
            "session_id_hashes": ["abc", "def"],
        }
    }
    out = public_stats.project_sessions(raw)
    allowed = public_stats.PUBLIC_FIELD_WHITELIST["sessions_day"]
    for day in out["days"]:
        leaked = set(day.keys()) - allowed
        assert not leaked, f"sessions leak: {leaked}"
    # Raw bounces/duration should not appear in public output.
    assert "total_duration_seconds" not in out["today"]
    assert "bounces" not in out["today"]


# ---------------------------------------------------------------------------
# project_hourly
# ---------------------------------------------------------------------------

def test_project_hourly_basic_shape():
    raw = {"2026-05-04": [0] * 24}
    raw["2026-05-04"][9] = 5
    raw["2026-05-04"][17] = 12
    out = public_stats.project_hourly(raw)
    assert out["today"]["total"] == 17
    assert out["today"]["hours"][9] == 5
    assert out["today"]["hours"][17] == 12


def test_project_hourly_skips_malformed_arrays():
    raw = {
        "2026-05-04": [1, 2, 3],            # length 3 — skipped
        "2026-05-05": [0] * 24,             # valid
        "2026-05-06": "not a list",         # type wrong — skipped
    }
    out = public_stats.project_hourly(raw)  # type: ignore[arg-type]
    assert [d["date"] for d in out["days"]] == ["2026-05-05"]


def test_project_hourly_no_leak():
    raw = {"2026-05-04": [0] * 24}
    out = public_stats.project_hourly(raw)
    allowed = public_stats.PUBLIC_FIELD_WHITELIST["hourly_day"]
    for day in out["days"]:
        leaked = set(day.keys()) - allowed
        assert not leaked, f"hourly leak: {leaked}"


# ---------------------------------------------------------------------------
# project_devices
# ---------------------------------------------------------------------------

def test_project_devices_drops_bot_and_unknown():
    raw = {"2026-05-04": {"mobile": 100, "tablet": 5, "desktop": 30, "bot": 999, "unknown": 7}}
    out = public_stats.project_devices(raw)
    today = out["today"]
    allowed = public_stats.PUBLIC_FIELD_WHITELIST["devices_day"]
    leaked = set(today.keys()) - allowed
    assert not leaked, f"devices leak: {leaked}"
    assert "bot" not in today
    assert "unknown" not in today
    # Total is sum of public buckets only.
    assert today["total"] == 135


def test_project_devices_no_leak_hostile_input():
    raw = {"2026-05-04": {
        "mobile": 1, "tablet": 0, "desktop": 0,
        "secret_ua_strings": ["evil"],  # hostile field — must not pass through
    }}
    out = public_stats.project_devices(raw)  # type: ignore[arg-type]
    allowed = public_stats.PUBLIC_FIELD_WHITELIST["devices_day"]
    for day in out["days"]:
        leaked = set(day.keys()) - allowed
        assert not leaked, f"devices hostile-input leak: {leaked}"


# ---------------------------------------------------------------------------
# project_referrers
# ---------------------------------------------------------------------------

def test_project_referrers_collapses_other_long_tail():
    raw = {"2026-05-04": {
        "direct": 50, "search": 30, "social": 10,
        "other": {"chicagotribune.com": 5, "obscure-blog.example": 2},
    }}
    out = public_stats.project_referrers(raw)
    today = out["today"]
    # Long-tail hostnames must not leak.
    assert "chicagotribune.com" not in str(today)
    assert "obscure-blog.example" not in str(today)
    # ``other`` becomes an int (sum).
    assert today["other"] == 7
    assert today["total"] == 97


def test_project_referrers_no_leak():
    raw = {"2026-05-04": {
        "direct": 1, "search": 0, "social": 0,
        "other": {"a.com": 1},
        "secret_field": "evil",  # hostile field — must not pass through
    }}
    out = public_stats.project_referrers(raw)  # type: ignore[arg-type]
    allowed = public_stats.PUBLIC_FIELD_WHITELIST["referrers_day"]
    for day in out["days"]:
        leaked = set(day.keys()) - allowed
        assert not leaked, f"referrers leak: {leaked}"


# ---------------------------------------------------------------------------
# render_html — minimal sanity
# ---------------------------------------------------------------------------

def test_render_html_self_contained():
    html = public_stats.render_html()
    # No third-party scripts on the public dashboard — load-bearing privacy claim.
    lower = html.lower()
    assert "http://" not in lower
    assert "https://" not in lower
    # Must reference all six public endpoints the page hydrates from.
    for path in ("/stats/dau", "/stats/geography", "/stats/sessions",
                 "/stats/hourly", "/stats/devices", "/stats/referrers"):
        assert path in html


def test_privacy_text_self_contained():
    """The /privacy text served from public_stats.PRIVACY_TEXT should not
    reference any external URLs (it would defeat the no-third-party claim)."""
    lower = public_stats.PRIVACY_TEXT.lower()
    assert "http://" not in lower
    assert "https://" not in lower
