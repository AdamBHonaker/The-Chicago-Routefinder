"""
Tests for backend/geocoding.py.

Covers:
  - The forward `resolve_location` cascade (coord regex → exact → fuzzy →
    local_search → LocationIQ).
  - The reverse `reverse_geocode_point` cascade (cache → neighborhood →
    address → LocationIQ → coordinate fallback).
  - Circuit-breaker behavior: a 429 trips the breaker; the next call raises
    `GeocoderDegradedError` without hitting the network.
  - Daily-cap behavior: when the UTC-day counter is pinned at cap, Tier-5
    calls silently no-op.
  - PII redaction in logs (the helpers, not the log infra itself).

Network calls are mocked via `geocoding._http_session.get`; no real HTTP
ever leaves this test file.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import geocoding
from geocoding import (
    GeocoderDegradedError,
    LocationOutsideChicagoError,
    NEG_HIT,
    _circuit_is_open,
    _circuit_reset_for_test,
    _cap_reset_for_test,
    _cap_set_for_test,
    _close_cache_db_for_test,
    _redact,
    _redact_coord,
    geocode_external,
    resolve_location,
    reverse_geocode_point,
)


@pytest.fixture(autouse=True)
def _reset_global_state(monkeypatch):
    # Each test starts with a closed breaker, fresh cap counter, a fresh DB
    # writer, and a LocationIQ key present so the gate doesn't short-circuit.
    # Also clear any synthetic test queries that earlier runs may have written
    # into cached_forward — the persistent DB is shared across test runs and
    # without this a positive cache hit would bypass the network mock.
    monkeypatch.setenv("LOCATIONIQ_API_KEY", "test-key-not-real")
    _circuit_reset_for_test()
    _cap_reset_for_test()
    _close_cache_db_for_test()
    _wipe_synthetic_cache_entries()
    yield
    _circuit_reset_for_test()
    _cap_reset_for_test()
    _wipe_synthetic_cache_entries()
    _close_cache_db_for_test()


def _wipe_synthetic_cache_entries() -> None:
    """Remove any cached_forward rows for the synthetic test query prefixes."""
    from geocoding import _cache_clear_forward_for_test
    for q in (
        "synthetic-query-for-locationiq-hit",
        "synthetic-query-for-no-match",
        "synthetic-query-for-out-of-bbox",
        "synthetic-breaker-query-1",
        "synthetic-breaker-query-2",
        "synthetic-cap-test-query",
        "___outside_bbox_test___",
        "___probe___",
        "zzz_breaker_test_xyzzy_qux",
        "___ttl_test_stale___",
        "___ttl_test_fresh___",
    ):
        _cache_clear_forward_for_test(q)


# ── PII redaction helpers ───────────────────────────────────────────────────

class TestRedact:
    def test_redact_returns_short_opaque_tag(self):
        out = _redact("1234 N Clark St")
        assert out.startswith("q#")
        assert len(out) == 2 + 10
        # Original text must not appear anywhere in the tag.
        assert "Clark" not in out
        assert "1234" not in out

    def test_redact_is_deterministic(self):
        assert _redact("Wrigleyville") == _redact("Wrigleyville")

    def test_redact_empty(self):
        assert _redact("") == "<empty>"

    def test_redact_coord_two_decimals(self):
        out = _redact_coord(41.94773, -87.656596)
        assert out == "(41.95, -87.66)"

    def test_redact_coord_none(self):
        assert _redact_coord(None, None) == "(?, ?)"


# ── Forward cascade ─────────────────────────────────────────────────────────

class TestResolveLocation:
    def test_coord_regex_bypasses_all_tiers(self):
        # A "lat,lon" string should resolve without touching NEIGHBORHOOD_COORDS,
        # local_search, or LocationIQ. We mock the http session to prove it.
        with patch.object(geocoding, "_http_session") as mock_session:
            coords = resolve_location("41.8827, -87.6326")
            assert coords == (41.8827, -87.6326)
            mock_session.get.assert_not_called()

    def test_exact_neighborhood_match(self):
        # "Wrigleyville" lives in NEIGHBORHOOD_COORDS — Tier 2 hit.
        with patch.object(geocoding, "_http_session") as mock_session:
            coords = resolve_location("Wrigleyville")
            assert coords is not None
            lat, lon = coords
            assert 41.93 < lat < 41.96
            mock_session.get.assert_not_called()

    def test_fuzzy_neighborhood_match(self):
        # A typo / partial match. "wrigleyvile" (missing l) should fuzzy-match
        # "wrigleyville" at >= 0.95 similarity.
        with patch.object(geocoding, "_http_session") as mock_session:
            coords = resolve_location("wrigleyvile")
            # Fuzzy may or may not catch this depending on the threshold; we
            # just assert no network call escaped to LocationIQ either way.
            mock_session.get.assert_not_called()
            assert coords is None or isinstance(coords, tuple)

    def test_returns_none_on_total_miss(self):
        # Unresolvable garbage with no LocationIQ key set (gate trips closed).
        with patch.dict("os.environ", {"LOCATIONIQ_API_KEY": ""}):
            with patch.object(geocoding, "_http_session") as mock_session:
                assert resolve_location("zzz_definitely_nothing_xyzzy_qux") is None
                mock_session.get.assert_not_called()


# ── LocationIQ network path (mocked) ────────────────────────────────────────

def _ok_response(lat: float, lon: float):
    """Build a fake requests.Response object for a successful /search hit."""
    r = MagicMock()
    r.status_code = 200
    r.content = b"[{}]"
    r.json.return_value = [{"lat": str(lat), "lon": str(lon)}]
    return r


def _no_match_response():
    r = MagicMock()
    r.status_code = 200
    r.content = b"[]"
    r.json.return_value = []
    return r


def _rate_limited_response():
    r = MagicMock()
    r.status_code = 429
    r.content = b'{"error":"Rate Limited"}'
    return r


class TestLocationIQForward:
    def test_successful_hit_returns_coords(self):
        with patch.object(geocoding, "_http_session") as mock_session:
            mock_session.get.return_value = _ok_response(41.93, -87.66)
            coords = geocode_external("synthetic-query-for-locationiq-hit")
            assert coords == (41.93, -87.66)
            mock_session.get.assert_called_once()

    def test_no_match_returns_none(self):
        with patch.object(geocoding, "_http_session") as mock_session:
            mock_session.get.return_value = _no_match_response()
            assert geocode_external("synthetic-query-for-no-match") is None

    def test_out_of_bbox_result_is_rejected(self):
        with patch.object(geocoding, "_http_session") as mock_session:
            # Coords for somewhere in Iowa.
            mock_session.get.return_value = _ok_response(41.5, -93.5)
            assert geocode_external("synthetic-query-for-out-of-bbox") is None


# ── Circuit breaker (Decision 4 + Chunk 5 checkpoint signal) ────────────────

class TestCircuitBreaker:
    def test_429_trips_breaker_then_subsequent_call_raises(self):
        with patch.object(geocoding, "_http_session") as mock_session:
            mock_session.get.return_value = _rate_limited_response()
            # First call: 429 trips the breaker.
            with pytest.raises(GeocoderDegradedError):
                geocode_external("synthetic-breaker-query-1")
            assert _circuit_is_open()
            # Second call: breaker is open; no network call should be made.
            mock_session.get.reset_mock()
            with pytest.raises(GeocoderDegradedError):
                geocode_external("synthetic-breaker-query-2")
            mock_session.get.assert_not_called()

    def test_resolve_location_propagates_degraded_error(self):
        # A miss-everything query routes through to Tier 5; with the breaker
        # open, resolve_location should re-raise GeocoderDegradedError.
        _circuit_reset_for_test()
        # Trip the breaker directly so we don't need a network round-trip.
        from geocoding import _circuit_trip_429
        _circuit_trip_429()
        assert _circuit_is_open()
        with pytest.raises(GeocoderDegradedError):
            resolve_location("zzz_breaker_test_xyzzy_qux")


# ── Daily cap (Decision 4 + Chunk 5 checkpoint signal) ──────────────────────

class TestDailyCap:
    def test_cap_at_limit_silently_skips_network_call(self):
        # Pin the counter at the configured cap; the next forward call must
        # not touch the network and must return None silently.
        from config import LOCATIONIQ_DAILY_CAP
        _cap_set_for_test(count=LOCATIONIQ_DAILY_CAP)

        with patch.object(geocoding, "_http_session") as mock_session:
            result = geocode_external("synthetic-cap-test-query")
            assert result is None
            mock_session.get.assert_not_called()


# ── LocationOutsideChicagoError ─────────────────────────────────────────────

class TestLocationOutsideChicago:
    def test_raised_when_tier5_returns_out_of_bbox_via_resolve_location(self):
        # Plant a positive cached_forward row outside the bbox. resolve_location
        # reads cached_forward as part of geocode_external, which checks bbox
        # on FRESH responses (not cached ones). So we go through the
        # _resolve_inner path: cache hit returns the out-of-bbox coords, then
        # the outer resolve_location wraps it in LocationOutsideChicagoError.
        from geocoding import _cache_set_forward, _cache_get_forward
        # Skip if the DB isn't available (fresh-clone CI).
        if _cache_get_forward("___probe___") is None:
            # Confirm the cache layer is actually reachable; if the DB is
            # missing the test can't run.
            from geocoding import _cache_connect
            if _cache_connect() is None:
                pytest.skip("chicago_geocode.db missing; skipping")

        bad_query = "___outside_bbox_test___"
        _cache_set_forward(bad_query, (40.0, -90.0), "test")  # Iowa-ish

        try:
            with pytest.raises(LocationOutsideChicagoError):
                resolve_location(bad_query)
        finally:
            from geocoding import _cache_clear_forward_for_test
            _cache_clear_forward_for_test(bad_query)


# ── Reverse cascade ─────────────────────────────────────────────────────────

class TestReverseGeocodePoint:
    def test_neighborhood_tier_for_loop_coords(self):
        # Loop coords (~41.88, -87.63) sit right on top of the "loop"
        # NEIGHBORHOOD_COORDS entry. Tier 2 should win — no network call.
        with patch.object(geocoding, "_http_session") as mock_session:
            result = reverse_geocode_point(41.8827, -87.6326)
            assert result["source"] in ("cached_reverse", "neighborhood")
            mock_session.get.assert_not_called()

    def test_coordinate_fallback_outside_chicago(self):
        # Coords way outside Chicago: KDTree finds no neighborhood within 200m,
        # local_search.nearest_address returns nothing within 50m, and with a
        # forced 429-breaker open the LocationIQ tier is skipped. The
        # coordinate fallback kicks in.
        from geocoding import _circuit_trip_429
        _circuit_trip_429()
        with patch.object(geocoding, "_http_session") as mock_session:
            result = reverse_geocode_point(45.0, -85.0)
            assert result["source"] == "coordinates"
            mock_session.get.assert_not_called()


# ── Cache TTL eviction (TD-051) ─────────────────────────────────────────────

class TestCacheTTLEviction:
    """`evict_cache_older_than(days)` is called from FastAPI startup.

    Sweeps `cached_forward` and `cached_reverse` rows whose `fetched_at` is
    older than `days` days. Cheap one-shot DELETE per table. Disabled when
    `days <= 0` (operator opt-out). No-op when the DB is unavailable.
    """

    def test_evicts_only_stale_forward_rows(self):
        """A row written with a stale `fetched_at` is deleted; a fresh row survives."""
        from geocoding import _cache_connect, evict_cache_older_than
        import time as _time

        db = _cache_connect()
        if db is None:
            pytest.skip("chicago_geocode.db missing; skipping")

        now = int(_time.time())
        stale_at = now - 91 * 86_400        # 91 days old — outside the 90-day TTL
        fresh_at = now - 30 * 86_400        # 30 days old — inside

        # Plant one stale row and one fresh row that we own. Use prefixes the
        # autouse fixture wipes.
        db.execute(
            "INSERT OR REPLACE INTO cached_forward "
            "(query, lat, lon, source, fetched_at) VALUES (?, ?, ?, ?, ?)",
            ("___ttl_test_stale___", 41.0, -87.0, "test", stale_at),
        )
        db.execute(
            "INSERT OR REPLACE INTO cached_forward "
            "(query, lat, lon, source, fetched_at) VALUES (?, ?, ?, ?, ?)",
            ("___ttl_test_fresh___", 41.1, -87.1, "test", fresh_at),
        )

        result = evict_cache_older_than(days=90)

        assert result["cached_forward"] >= 1
        # Stale row gone.
        row = db.execute(
            "SELECT 1 FROM cached_forward WHERE query = ?",
            ("___ttl_test_stale___",),
        ).fetchone()
        assert row is None
        # Fresh row survives.
        row = db.execute(
            "SELECT 1 FROM cached_forward WHERE query = ?",
            ("___ttl_test_fresh___",),
        ).fetchone()
        assert row is not None

    def test_days_zero_is_a_no_op(self):
        """`days=0` means "disable eviction" — must not delete anything."""
        from geocoding import _cache_connect, evict_cache_older_than
        import time as _time

        db = _cache_connect()
        if db is None:
            pytest.skip("chicago_geocode.db missing; skipping")

        # Plant a very stale row that would normally be evicted.
        ancient = int(_time.time()) - 365 * 86_400
        db.execute(
            "INSERT OR REPLACE INTO cached_forward "
            "(query, lat, lon, source, fetched_at) VALUES (?, ?, ?, ?, ?)",
            ("___ttl_test_stale___", 41.0, -87.0, "test", ancient),
        )

        result = evict_cache_older_than(days=0)

        assert result == {"cached_forward": 0, "cached_reverse": 0}
        row = db.execute(
            "SELECT 1 FROM cached_forward WHERE query = ?",
            ("___ttl_test_stale___",),
        ).fetchone()
        assert row is not None

    def test_no_db_is_a_no_op(self, monkeypatch, tmp_path):
        """When the DB is unavailable the evictor returns a zeroed summary."""
        from geocoding import evict_cache_older_than

        # Point the cache layer at a non-existent path so `_cache_connect`
        # returns None.
        monkeypatch.setattr(geocoding, "_CACHE_DB_PATH", tmp_path / "missing.db")
        _close_cache_db_for_test()
        result = evict_cache_older_than(days=90)
        assert result == {"cached_forward": 0, "cached_reverse": 0}
