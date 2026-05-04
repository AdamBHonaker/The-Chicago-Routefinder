"""
Unit tests for pure helper functions in backend/main.py.

All helpers tested here are I/O-free and do not touch CTA APIs, Claude,
or the file system.  Tests that require live data are out of scope.

Covered:
  - _cache_key()             — deterministic cache key construction
  - _check_rate_limit()      — sliding-window rate limiter logic
  - _is_simple_query()       — simple vs. complex query classification
  - _alert_ids_from_routes() — deduped alert IDs from a route list
  - build_prompt()           — prompt text generation
  - _format_routes()         — route list → text block for Claude
  - RouteRequest validators  — Pydantic model field validation
"""

import collections
import time
import pytest
from unittest.mock import patch

# main.py is imported once per session; the lifespan function and warm_up are
# never invoked, so no GTFS loading or CTA API calls occur.
from main import (
    _cache_key,
    _check_rate_limit,
    _is_simple_query,
    _alert_ids_from_routes,
    build_prompt,
    _format_routes,
    RouteRequest,
    _rate_store,
)
from transit_graph import Route, WalkLeg, TransitLeg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _transit_leg(line_code: str = "Red", line: str = "Red Line",
                 from_station: str = "Howard", to_station: str = "Lake",
                 minutes: float = 20.0) -> TransitLeg:
    return TransitLeg(
        line=line, line_code=line_code,
        from_station=from_station, from_mapid="40900",
        to_station=to_station, to_mapid="41660",
        minutes=minutes,
    )


def _walk_leg(from_name: str = "Your location", to_name: str = "Howard",
              minutes: float = 5.0) -> WalkLeg:
    return WalkLeg(from_name=from_name, to_name=to_name, minutes=minutes)


def _simple_route() -> Route:
    """One walk + one transit + one walk — the canonical 'simple' itinerary."""
    legs = [
        _walk_leg("Your location", "Howard", 5.0),
        _transit_leg(),
        _walk_leg("Lake", "Your destination", 3.0),
    ]
    return Route(legs=legs, transit_minutes=20.0, walk_minutes_total=8.0,
                 first_transit_leg_index=1)


def _transfer_route() -> Route:
    """Two transit legs — a transfer route."""
    legs = [
        _walk_leg("Your location", "Clark/Lake", 4.0),
        _transit_leg("Blue", "Blue Line", "O'Hare", "Clark/Lake", 30.0),
        _walk_leg("Clark/Lake", "Clark/Lake", 3.0),
        _transit_leg("Red", "Red Line", "Clark/Lake", "95th/Dan Ryan", 15.0),
        _walk_leg("95th/Dan Ryan", "Your destination", 2.0),
    ]
    return Route(legs=legs, transit_minutes=45.0, walk_minutes_total=9.0,
                 transfers=1, first_transit_leg_index=1)


# ---------------------------------------------------------------------------
# _cache_key
# ---------------------------------------------------------------------------

class TestCacheKey:
    def test_returns_string(self):
        key = _cache_key("wrigleyville", "loop", "All", "All")
        assert isinstance(key, str)

    def test_lowercases_origin_and_destination(self):
        k1 = _cache_key("Wrigleyville", "Loop", "All", "All")
        k2 = _cache_key("wrigleyville", "loop", "All", "All")
        assert k1 == k2

    def test_strips_whitespace(self):
        k1 = _cache_key("  wrigleyville  ", "  loop  ", "All", "All")
        k2 = _cache_key("wrigleyville", "loop", "All", "All")
        assert k1 == k2

    def test_different_origins_produce_different_keys(self):
        k1 = _cache_key("wrigleyville", "loop", "All", "All")
        k2 = _cache_key("lincoln park", "loop", "All", "All")
        assert k1 != k2

    def test_transit_mode_included(self):
        k1 = _cache_key("wrigleyville", "loop", "Train", "All")
        k2 = _cache_key("wrigleyville", "loop", "Bus", "All")
        assert k1 != k2

    def test_bus_fullness_included(self):
        k1 = _cache_key("wrigleyville", "loop", "All", "Empty")
        k2 = _cache_key("wrigleyville", "loop", "All", "Full")
        assert k1 != k2

    def test_byok_flag_differentiates(self):
        k1 = _cache_key("wrigleyville", "loop", "All", "All", byok=True)
        k2 = _cache_key("wrigleyville", "loop", "All", "All", byok=False)
        assert k1 != k2

    def test_ai_enabled_differentiates(self):
        k1 = _cache_key("wrigleyville", "loop", "All", "All", ai_enabled=True)
        k2 = _cache_key("wrigleyville", "loop", "All", "All", ai_enabled=False)
        assert k1 != k2

    def test_language_differentiates(self):
        k1 = _cache_key("wrigleyville", "loop", "All", "All", language="en")
        k2 = _cache_key("wrigleyville", "loop", "All", "All", language="es")
        assert k1 != k2

    def test_identical_args_produce_same_key(self):
        args = ("wrigleyville", "loop", "All", "All")
        assert _cache_key(*args) == _cache_key(*args)


# ---------------------------------------------------------------------------
# _check_rate_limit
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    """
    _check_rate_limit() reads _RATE_LIMIT_ENABLED, _RATE_LIMIT_RPM,
    _RATE_LIMIT_RPH from module-level variables and mutates _rate_store.
    Tests patch the variables and clean up _rate_store after each run.
    """

    TEST_IP = "192.0.2.1"   # TEST-NET-1 — safe to use in unit tests

    def setup_method(self):
        """Ensure the test IP has a clean slate before each test."""
        _rate_store.pop(self.TEST_IP, None)

    def test_disabled_always_allows(self):
        with patch("rate_limit._RATE_LIMIT_ENABLED", False):
            assert _check_rate_limit(self.TEST_IP) is True

    def test_disabled_allows_many_calls(self):
        with patch("rate_limit._RATE_LIMIT_ENABLED", False):
            for _ in range(20):
                assert _check_rate_limit(self.TEST_IP) is True

    def test_enabled_first_call_allowed(self):
        with patch("rate_limit._RATE_LIMIT_ENABLED", True), \
             patch("rate_limit._RATE_LIMIT_RPM", 10), \
             patch("rate_limit._RATE_LIMIT_RPH", 50):
            assert _check_rate_limit(self.TEST_IP) is True

    def test_enabled_blocks_at_minute_cap(self):
        """After RPM requests in the last 60 seconds, the next is rejected."""
        with patch("rate_limit._RATE_LIMIT_ENABLED", True), \
             patch("rate_limit._RATE_LIMIT_RPM", 3), \
             patch("rate_limit._RATE_LIMIT_RPH", 100):
            _rate_store.pop(self.TEST_IP, None)
            # Seed the window with 3 recent timestamps
            now = time.monotonic()
            _rate_store[self.TEST_IP] = collections.deque([now - 10, now - 20, now - 30])
            assert _check_rate_limit(self.TEST_IP) is False

    def test_enabled_blocks_at_hour_cap(self):
        """After RPH requests in the last hour, the next is rejected."""
        with patch("rate_limit._RATE_LIMIT_ENABLED", True), \
             patch("rate_limit._RATE_LIMIT_RPM", 100), \
             patch("rate_limit._RATE_LIMIT_RPH", 3):
            _rate_store.pop(self.TEST_IP, None)
            now = time.monotonic()
            # 3 timestamps spread over the hour — passes per-minute cap, fails hourly
            _rate_store[self.TEST_IP] = collections.deque([
                now - 400, now - 800, now - 1200,
            ])
            assert _check_rate_limit(self.TEST_IP) is False

    def test_old_timestamps_evicted_before_check(self):
        """Requests older than 1 hour are pruned and don't count toward the cap."""
        with patch("rate_limit._RATE_LIMIT_ENABLED", True), \
             patch("rate_limit._RATE_LIMIT_RPM", 2), \
             patch("rate_limit._RATE_LIMIT_RPH", 3):
            _rate_store.pop(self.TEST_IP, None)
            now = time.monotonic()
            # Two very stale timestamps (> 1 hour ago)
            _rate_store[self.TEST_IP] = collections.deque([
                now - 4000, now - 5000,
            ])
            # Should be allowed — stale entries get evicted
            assert _check_rate_limit(self.TEST_IP) is True

    def teardown_method(self):
        _rate_store.pop(self.TEST_IP, None)


# ---------------------------------------------------------------------------
# _is_simple_query
# ---------------------------------------------------------------------------

class TestIsSimpleQuery:
    def test_single_route_single_transit_is_simple(self):
        routes = [(15.0, 5, _simple_route())]
        assert _is_simple_query(routes) is True

    def test_empty_routes_not_simple(self):
        assert _is_simple_query([]) is False

    def test_two_routes_not_simple(self):
        routes = [(15.0, 5, _simple_route()), (20.0, 8, _simple_route())]
        assert _is_simple_query(routes) is False

    def test_single_route_two_transit_legs_not_simple(self):
        routes = [(30.0, 5, _transfer_route())]
        assert _is_simple_query(routes) is False

    def test_walk_only_legs_not_counted(self):
        # A route with only walk legs has 0 transit legs → not simple
        walk_only = Route(
            legs=[_walk_leg("Your location", "Destination", 10.0)],
            transit_minutes=0.0,
            walk_minutes_total=10.0,
        )
        assert _is_simple_query([(10.0, None, walk_only)]) is False


# ---------------------------------------------------------------------------
# _alert_ids_from_routes
# ---------------------------------------------------------------------------

class TestAlertIdsFromRoutes:
    def test_empty_routes_returns_empty_list(self):
        assert _alert_ids_from_routes([]) == []

    def test_train_line_mapped_to_alert_id(self):
        r = Route(legs=[_transit_leg("Red", "Red Line")],
                  transit_minutes=20.0, walk_minutes_total=0.0)
        ids = _alert_ids_from_routes([(15.0, 5, r)])
        assert "red" in ids   # _TRAIN_LINE_TO_ALERT_ID maps "Red" → "red"

    def test_deduplicates_same_line_across_routes(self):
        r1 = Route(legs=[_transit_leg("Red")], transit_minutes=20.0, walk_minutes_total=0.0)
        r2 = Route(legs=[_transit_leg("Red")], transit_minutes=25.0, walk_minutes_total=0.0)
        ids = _alert_ids_from_routes([(15.0, 5, r1), (20.0, 3, r2)])
        assert ids.count("red") == 1

    def test_two_different_lines_both_present(self):
        r = Route(
            legs=[_transit_leg("Red"), _transit_leg("Blue", "Blue Line")],
            transit_minutes=40.0, walk_minutes_total=0.0,
        )
        ids = _alert_ids_from_routes([(40.0, 5, r)])
        assert "red" in ids
        assert "blue" in ids

    def test_walk_legs_ignored(self):
        r = Route(
            legs=[_walk_leg(), _transit_leg("Red"), _walk_leg()],
            transit_minutes=20.0, walk_minutes_total=8.0,
            first_transit_leg_index=1,
        )
        ids = _alert_ids_from_routes([(25.0, 5, r)])
        # Only Red Line should produce an alert ID
        assert len(ids) == 1
        assert "red" in ids

    def test_unknown_line_code_used_as_id(self):
        # Bus routes won't be in _TRAIN_LINE_TO_ALERT_ID; their line_code is used as-is
        bus_leg = TransitLeg(
            line="Northbound", line_code="22",
            from_station="Clark/Division", from_mapid="100",
            to_station="Fullerton", to_mapid="200",
            minutes=10.0,
        )
        r = Route(legs=[bus_leg], transit_minutes=10.0, walk_minutes_total=0.0)
        ids = _alert_ids_from_routes([(10.0, 2, r)])
        assert "22" in ids


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_no_data_returns_ventra_fallback(self):
        prompt = build_prompt("Wrigleyville", "Loop", [], [], "All")
        assert "Ventra" in prompt or "transitchicago" in prompt

    def test_includes_origin_and_destination(self):
        prompt = build_prompt("Wrigleyville", "Loop", [], [], "All")
        assert "Wrigleyville" in prompt
        assert "Loop" in prompt

    def _ranked_route(self) -> list[tuple]:
        """Minimal ranked_routes list so build_prompt takes the data path, not the fallback."""
        return [(15.0, 5, _simple_route())]

    def test_mode_train_constraint_mentioned(self):
        # build_prompt takes the early fallback when there is no data; pass routes
        prompt = build_prompt("Wrigleyville", "Loop", [], [], "Train",
                              ranked_routes=self._ranked_route())
        assert "TRAIN" in prompt or "train" in prompt.lower()

    def test_mode_bus_constraint_mentioned(self):
        prompt = build_prompt("Wrigleyville", "Loop", [], [], "Bus",
                              ranked_routes=self._ranked_route())
        assert "BUS" in prompt or "bus" in prompt.lower()

    def test_language_spanish_appends_instruction(self):
        prompt = build_prompt("Wrigleyville", "Loop", [], [], "All",
                              ranked_routes=self._ranked_route(), language="es")
        assert "Spanish" in prompt

    def test_language_english_no_extra_instruction(self):
        prompt = build_prompt("Wrigleyville", "Loop", [], [], "All",
                              ranked_routes=self._ranked_route(), language="en")
        assert "Respond in English" not in prompt

    def test_language_japanese_includes_furigana_note(self):
        prompt = build_prompt("Wrigleyville", "Loop", [], [], "All",
                              ranked_routes=self._ranked_route(), language="ja")
        assert "Japanese" in prompt
        assert "furigana" in prompt

    def test_significant_alerts_included(self):
        # CTA SeverityScore is on a 0–100 scale; build_prompt's "significant"
        # threshold is 40 (matching the ≥40 / ≥70 tiers in the alerts handler).
        alerts = [
            {
                "alert_id": "1",
                "headline": "Red Line delays",
                "impact": "Delays",
                "severity_score": 50,
                "is_major": False,
                "event_end": None,
                "affected_routes": ["Red"],
            }
        ]
        prompt = build_prompt(
            "Wrigleyville", "Loop", [], [], "All",
            ranked_routes=self._ranked_route(),
            alerts=alerts,
        )
        assert "Red Line delays" in prompt

    def test_low_severity_alerts_excluded(self):
        alerts = [
            {
                "alert_id": "1",
                "headline": "Elevator outage",
                "impact": "Accessibility",
                "severity_score": 20,
                "is_major": False,
                "event_end": None,
                "affected_routes": [],
            }
        ]
        prompt = build_prompt(
            "Wrigleyville", "Loop", [], [], "All",
            ranked_routes=self._ranked_route(),
            alerts=alerts,
        )
        assert "Elevator outage" not in prompt

    def test_bus_mode_no_data_gives_bus_specific_fallback(self):
        prompt = build_prompt("Wrigleyville", "Loop", [], [], "Bus")
        assert "bus" in prompt.lower()


# ---------------------------------------------------------------------------
# _format_routes
# ---------------------------------------------------------------------------

class TestFormatRoutes:
    def test_returns_string(self):
        routes = [(15.0, 5, _simple_route())]
        result = _format_routes(routes)
        assert isinstance(result, str)

    def test_includes_option_number(self):
        routes = [(15.0, 5, _simple_route())]
        assert "Option 1" in _format_routes(routes)

    def test_two_routes_both_numbered(self):
        routes = [(15.0, 5, _simple_route()), (25.0, 8, _simple_route())]
        text = _format_routes(routes)
        assert "Option 1" in text
        assert "Option 2" in text

    def test_wait_time_present_when_given(self):
        routes = [(15.0, 4, _simple_route())]
        text = _format_routes(routes)
        assert "4 min" in text

    def test_due_when_wait_is_zero(self):
        routes = [(10.0, 0, _simple_route())]
        text = _format_routes(routes)
        assert "Due" in text

    def test_no_wait_data_omits_wait_note(self):
        routes = [(15.0, None, _simple_route())]
        text = _format_routes(routes)
        assert "train in" not in text
        assert "bus in" not in text

    def test_total_time_in_output(self):
        routes = [(15.0, 5, _simple_route())]
        text = _format_routes(routes)
        assert "15" in text

    def test_transfer_route_shows_transfer_count(self):
        routes = [(40.0, 5, _transfer_route())]
        text = _format_routes(routes)
        assert "transfer" in text.lower()


# ---------------------------------------------------------------------------
# RouteRequest Pydantic validators
# ---------------------------------------------------------------------------

class TestRouteRequestValidators:
    def test_valid_transit_mode_all(self):
        r = RouteRequest(origin="a", destination="b", transit_mode="All")
        assert r.transit_mode == "All"

    def test_valid_transit_mode_train(self):
        r = RouteRequest(origin="a", destination="b", transit_mode="Train")
        assert r.transit_mode == "Train"

    def test_valid_transit_mode_bus(self):
        r = RouteRequest(origin="a", destination="b", transit_mode="Bus")
        assert r.transit_mode == "Bus"

    def test_invalid_transit_mode_raises(self):
        with pytest.raises(Exception):
            RouteRequest(origin="a", destination="b", transit_mode="Ferry")

    def test_valid_bus_fullness_values(self):
        for val in ("All", "Empty", "Half-Full", "Full"):
            r = RouteRequest(origin="a", destination="b", bus_fullness=val)
            assert r.bus_fullness == val

    def test_invalid_bus_fullness_raises(self):
        with pytest.raises(Exception):
            RouteRequest(origin="a", destination="b", bus_fullness="Packed")

    # BYOK key tests removed: the anthropic_api_key field no longer lives on
    # RouteRequest — it now arrives via the Authorization: Bearer header and is
    # validated inside the /recommend handler. Format-rejection coverage lives
    # in _validate_api_keys (test_endpoints.py exercises the full path).

    def test_ai_disabled_by_default(self):
        r = RouteRequest(origin="a", destination="b")
        assert r.ai_enabled is False

    def test_transit_mode_defaults_to_all(self):
        r = RouteRequest(origin="a", destination="b")
        assert r.transit_mode == "All"

    def test_bus_fullness_defaults_to_all(self):
        r = RouteRequest(origin="a", destination="b")
        assert r.bus_fullness == "All"
