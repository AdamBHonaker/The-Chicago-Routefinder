"""
Unit tests for backend/cta_client.py.

All tests mock aiohttp.ClientSession via patching cta_client._get_session, so
no live HTTP requests are made.  The shape of every mocked response matches
the real CTA Train Tracker, Bus Tracker, Alerts, and Routes JSON payloads.

Covered:
  _fetch_station_arrivals / get_train_arrivals
    - Multiple ETAs parsed; correct field mapping
    - Single ETA returned as dict (CTA quirk) is normalized to a list
    - API error code (errCd != "0") yields an error sentinel
    - Network exception yields an error sentinel
    - Both date formats accepted: "YYYYMMDD HH:MM:SS" and ISO 8601
    - Past arrival clamped to 0 minutes
    - is_approaching / is_delayed / is_scheduled flags parsed
    - Unknown line code falls back to the raw rt value
    - get_train_arrivals sorts by minutes and counts errors

  _fetch_bus_chunk / get_bus_arrivals
    - Predictions parsed; field mapping
    - Single prd dict normalized to list
    - "DUE" / non-digit prdctdn → 0 minutes
    - prdctdn = null → 0 minutes
    - Numeric string prdctdn → int
    - psgld "HALF EMPTY" normalized to "HALF_EMPTY"
    - dly truthy/falsy variants parsed
    - Network exception → error sentinel; n_errors counted
    - Empty stop_ids → ([], 0) without a request
    - >10 stop_ids batched into multiple chunks

  _fetch_alerts_for_route / get_alerts
    - Empty route_ids → []
    - Single Alert as dict normalized to list
    - severity_score ≥ 70 → is_major True
    - ImpactedService.Service: dict and list both parsed
    - EventEnd "" → None
    - Dedup by alert_id across routes
    - Sorted by severity_score descending
    - Network failure → []

  get_route_statuses
    - Multiple routes parsed
    - Single RouteInfo dict normalized
    - Network failure → []
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

import cta_client
from cta_client import (
    _fetch_station_arrivals,
    get_train_arrivals,
    _fetch_bus_chunk,
    get_bus_arrivals,
    _fetch_alerts_for_route,
    get_alerts,
    get_route_statuses,
)
from utils import CHICAGO_TZ


# ---------------------------------------------------------------------------
# Mock-session helpers
# ---------------------------------------------------------------------------

def _mock_session(json_payload):
    """Build a MagicMock that emulates aiohttp.ClientSession returning json_payload."""
    resp = MagicMock()
    resp.json = AsyncMock(return_value=json_payload)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.get = MagicMock(return_value=cm)
    return session


def _mock_session_sequence(json_payloads: list):
    """Session whose successive .get() calls each yield the next payload."""
    cms = []
    for payload in json_payloads:
        resp = MagicMock()
        resp.json = AsyncMock(return_value=payload)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=None)
        cms.append(cm)
    session = MagicMock()
    session.get = MagicMock(side_effect=cms)
    return session


def _mock_session_raises(exc: Exception):
    """Session whose .get() raises immediately, simulating a network failure."""
    session = MagicMock()
    session.get = MagicMock(side_effect=exc)
    return session


# ---------------------------------------------------------------------------
# Train Tracker — _fetch_station_arrivals
# ---------------------------------------------------------------------------

class TestFetchStationArrivals:
    """Unit tests for the per-station train arrivals parser."""

    NOW = datetime(2026, 5, 4, 12, 0, 0, tzinfo=CHICAGO_TZ)

    def _payload(self, etas):
        return {"ctatt": {"errCd": "0", "errNm": None, "eta": etas}}

    def _eta(self, **overrides):
        base = {
            "rt": "Red",
            "staNm": "Howard",
            "stpDe": "Service toward 95th/Dan Ryan",
            "destNm": "95th/Dan Ryan",
            "arrT": "20260504 12:05:00",
            "isApp": "0",
            "isDly": "0",
            "isSch": "0",
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_multiple_etas_parsed(self):
        payload = self._payload([self._eta(), self._eta(arrT="20260504 12:10:00")])
        session = _mock_session(payload)
        result = await _fetch_station_arrivals(session, "40900", "Howard", "k", self.NOW)
        assert len(result) == 2
        assert result[0]["type"] == "train"
        assert result[0]["line"] == "Red Line"
        assert result[0]["line_code"] == "Red"
        assert result[0]["station"] == "Howard"
        assert result[0]["station_mapid"] == "40900"
        assert result[0]["arrives_in_minutes"] == 5
        assert result[1]["arrives_in_minutes"] == 10

    @pytest.mark.asyncio
    async def test_single_eta_dict_normalized_to_list(self):
        # CTA returns `eta` as a dict (not a list) when there is exactly one ETA
        payload = {"ctatt": {"errCd": "0", "eta": self._eta()}}
        result = await _fetch_station_arrivals(
            _mock_session(payload), "40900", "Howard", "k", self.NOW
        )
        assert len(result) == 1
        assert result[0]["destination"] == "95th/Dan Ryan"

    @pytest.mark.asyncio
    async def test_api_error_code_returns_error_sentinel(self):
        payload = {"ctatt": {"errCd": "100", "errNm": "Invalid API key"}}
        result = await _fetch_station_arrivals(
            _mock_session(payload), "40900", "Howard", "k", self.NOW
        )
        assert len(result) == 1
        assert result[0]["_error"] is True
        assert "100" in result[0]["exc"]
        assert "Invalid API key" in result[0]["exc"]
        assert result[0]["mode"] == "train"

    @pytest.mark.asyncio
    async def test_network_exception_returns_error_sentinel(self):
        session = _mock_session_raises(RuntimeError("DNS timeout"))
        result = await _fetch_station_arrivals(session, "40900", "Howard", "k", self.NOW)
        assert len(result) == 1
        assert result[0]["_error"] is True
        assert "DNS timeout" in result[0]["exc"]
        assert result[0]["mode"] == "train"

    @pytest.mark.asyncio
    async def test_iso_arrival_format_parsed(self):
        # Naive ISO timestamp — code attaches CHICAGO_TZ
        eta = self._eta(arrT="2026-05-04T12:07:00")
        result = await _fetch_station_arrivals(
            _mock_session(self._payload([eta])), "40900", "Howard", "k", self.NOW
        )
        assert result[0]["arrives_in_minutes"] == 7

    @pytest.mark.asyncio
    async def test_iso_arrival_with_tz_converted(self):
        # ISO with explicit UTC offset → must be converted to Chicago time
        eta = self._eta(arrT="2026-05-04T17:09:00+00:00")  # 12:09 PM CDT
        result = await _fetch_station_arrivals(
            _mock_session(self._payload([eta])), "40900", "Howard", "k", self.NOW
        )
        assert result[0]["arrives_in_minutes"] == 9

    @pytest.mark.asyncio
    async def test_past_arrival_clamped_to_zero(self):
        # Train was due 5 min ago — minutes should be 0, not negative
        eta = self._eta(arrT="20260504 11:55:00")
        result = await _fetch_station_arrivals(
            _mock_session(self._payload([eta])), "40900", "Howard", "k", self.NOW
        )
        assert result[0]["arrives_in_minutes"] == 0

    @pytest.mark.asyncio
    async def test_status_flags_parsed(self):
        eta = self._eta(isApp="1", isDly="1", isSch="0")
        result = await _fetch_station_arrivals(
            _mock_session(self._payload([eta])), "40900", "Howard", "k", self.NOW
        )
        assert result[0]["is_approaching"] is True
        assert result[0]["is_delayed"] is True
        assert result[0]["is_scheduled"] is False

    @pytest.mark.asyncio
    async def test_unknown_line_code_falls_back_to_rt(self):
        eta = self._eta(rt="ZZZ")
        result = await _fetch_station_arrivals(
            _mock_session(self._payload([eta])), "40900", "Howard", "k", self.NOW
        )
        assert result[0]["line"] == "ZZZ"
        assert result[0]["line_code"] == "ZZZ"

    @pytest.mark.asyncio
    async def test_malformed_eta_skipped_not_raised(self):
        # Missing arrT — the loop catches and continues
        bad_eta = {"rt": "Red"}   # no arrT key → KeyError → skipped
        good_eta = self._eta()
        result = await _fetch_station_arrivals(
            _mock_session(self._payload([bad_eta, good_eta])),
            "40900", "Howard", "k", self.NOW
        )
        assert len(result) == 1
        assert result[0]["line_code"] == "Red"

    @pytest.mark.asyncio
    async def test_empty_eta_returns_empty_list(self):
        result = await _fetch_station_arrivals(
            _mock_session(self._payload([])), "40900", "Howard", "k", self.NOW
        )
        assert result == []


# ---------------------------------------------------------------------------
# Train Tracker — get_train_arrivals (orchestration)
# ---------------------------------------------------------------------------

class TestGetTrainArrivals:
    """Tests for get_train_arrivals — fan-out, sort, error counting."""

    @pytest.mark.asyncio
    async def test_multi_station_results_merged_and_sorted(self):
        # Two stations; one returns a 10-min ETA, the other a 3-min ETA
        now_str = datetime.now(CHICAGO_TZ).strftime("%Y%m%d %H:%M:%S")
        far = (datetime.now(CHICAGO_TZ) + timedelta(minutes=10)).strftime("%Y%m%d %H:%M:%S")
        near = (datetime.now(CHICAGO_TZ) + timedelta(minutes=3)).strftime("%Y%m%d %H:%M:%S")

        payload_a = {"ctatt": {"errCd": "0", "eta": [
            {"rt": "Red", "staNm": "A", "stpDe": "", "destNm": "X", "arrT": far,
             "isApp": "0", "isDly": "0", "isSch": "0"}
        ]}}
        payload_b = {"ctatt": {"errCd": "0", "eta": [
            {"rt": "Blue", "staNm": "B", "stpDe": "", "destNm": "Y", "arrT": near,
             "isApp": "0", "isDly": "0", "isSch": "0"}
        ]}}

        session = _mock_session_sequence([payload_a, payload_b])
        with patch.object(cta_client, "_get_session", return_value=session):
            arrivals, errors = await get_train_arrivals(
                [{"mapid": "40900", "name": "A"}, {"mapid": "40240", "name": "B"}],
                train_key="k",
            )

        assert errors == 0
        assert len(arrivals) == 2
        # Sorted ascending by minutes
        assert arrivals[0]["arrives_in_minutes"] <= arrivals[1]["arrives_in_minutes"]

    @pytest.mark.asyncio
    async def test_error_response_counted_and_excluded(self):
        good = {"ctatt": {"errCd": "0", "eta": [
            {"rt": "Red", "staNm": "A", "stpDe": "", "destNm": "X",
             "arrT": "20260504 12:05:00",
             "isApp": "0", "isDly": "0", "isSch": "0"}
        ]}}
        bad = {"ctatt": {"errCd": "500", "errNm": "Server error"}}
        session = _mock_session_sequence([good, bad])
        with patch.object(cta_client, "_get_session", return_value=session):
            arrivals, errors = await get_train_arrivals(
                [{"mapid": "1", "name": "A"}, {"mapid": "2", "name": "B"}],
                train_key="k",
            )
        assert errors == 1
        # Errors removed from sorted list
        assert all(not a.get("_error") for a in arrivals)

    @pytest.mark.asyncio
    async def test_empty_stations_returns_empty(self):
        with patch.object(cta_client, "_get_session", return_value=_mock_session({})):
            arrivals, errors = await get_train_arrivals([], train_key="k")
        assert arrivals == []
        assert errors == 0


# ---------------------------------------------------------------------------
# Bus Tracker — _fetch_bus_chunk
# ---------------------------------------------------------------------------

class TestFetchBusChunk:
    """Unit tests for the per-chunk bus predictions parser."""

    def _payload(self, prds):
        return {"bustime-response": {"prd": prds}}

    def _prd(self, **overrides):
        base = {
            "rt": "22",
            "rtdir": "Northbound",
            "stpid": "1234",
            "stpnm": "Clark & Belmont",
            "des": "Howard",
            "prdctdn": "5",
            "psgld": "EMPTY",
            "dly": "false",
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_multiple_predictions_parsed(self):
        session = _mock_session(self._payload([self._prd(), self._prd(prdctdn="12")]))
        result = await _fetch_bus_chunk(session, ["1234"], "k", routes=None)
        assert len(result) == 2
        assert result[0]["type"] == "bus"
        assert result[0]["route"] == "22"
        assert result[0]["direction"] == "northbound"   # lowercased
        assert result[0]["stop_id"] == "1234"
        assert result[0]["arrives_in_minutes"] == 5
        assert result[1]["arrives_in_minutes"] == 12

    @pytest.mark.asyncio
    async def test_single_prd_dict_normalized_to_list(self):
        # When a chunk returns one prediction, the API ships it as a dict, not a list
        session = _mock_session(self._payload(self._prd()))
        result = await _fetch_bus_chunk(session, ["1234"], "k", routes=None)
        assert len(result) == 1
        assert result[0]["route"] == "22"

    @pytest.mark.asyncio
    async def test_due_string_becomes_zero_minutes(self):
        session = _mock_session(self._payload([self._prd(prdctdn="DUE")]))
        result = await _fetch_bus_chunk(session, ["1234"], "k", routes=None)
        assert result[0]["arrives_in_minutes"] == 0

    @pytest.mark.asyncio
    async def test_approaching_string_becomes_zero_minutes(self):
        session = _mock_session(self._payload([self._prd(prdctdn="APPROACHING")]))
        result = await _fetch_bus_chunk(session, ["1234"], "k", routes=None)
        assert result[0]["arrives_in_minutes"] == 0

    @pytest.mark.asyncio
    async def test_null_prdctdn_becomes_zero(self):
        # Some unusual responses include `"prdctdn": null` — must not raise
        session = _mock_session(self._payload([self._prd(prdctdn=None)]))
        result = await _fetch_bus_chunk(session, ["1234"], "k", routes=None)
        assert result[0]["arrives_in_minutes"] == 0

    @pytest.mark.asyncio
    async def test_psgld_with_space_normalized_to_underscore(self):
        session = _mock_session(self._payload([self._prd(psgld="HALF EMPTY")]))
        result = await _fetch_bus_chunk(session, ["1234"], "k", routes=None)
        assert result[0]["psgld"] == "HALF_EMPTY"

    @pytest.mark.asyncio
    async def test_psgld_lowercase_normalized_to_upper(self):
        session = _mock_session(self._payload([self._prd(psgld="half empty")]))
        result = await _fetch_bus_chunk(session, ["1234"], "k", routes=None)
        assert result[0]["psgld"] == "HALF_EMPTY"

    @pytest.mark.asyncio
    async def test_dly_true_string_parsed_as_true(self):
        session = _mock_session(self._payload([self._prd(dly="true")]))
        result = await _fetch_bus_chunk(session, ["1234"], "k", routes=None)
        assert result[0]["is_delayed"] is True

    @pytest.mark.asyncio
    async def test_dly_false_string_parsed_as_false(self):
        session = _mock_session(self._payload([self._prd(dly="false")]))
        result = await _fetch_bus_chunk(session, ["1234"], "k", routes=None)
        assert result[0]["is_delayed"] is False

    @pytest.mark.asyncio
    async def test_network_exception_returns_error_sentinel(self):
        session = _mock_session_raises(ConnectionError("Bus API down"))
        result = await _fetch_bus_chunk(session, ["1234"], "k", routes=None)
        assert len(result) == 1
        assert result[0]["_error"] is True
        assert result[0]["mode"] == "bus"
        assert "Bus API down" in result[0]["exc"]

    @pytest.mark.asyncio
    async def test_routes_param_passed_to_api(self):
        session = _mock_session(self._payload([]))
        await _fetch_bus_chunk(session, ["1234"], "k", routes=["22", "66"])
        # Verify the API was called with rt=... in params
        _, kwargs = session.get.call_args
        assert "rt" in kwargs["params"]
        assert kwargs["params"]["rt"] == "22,66"

    @pytest.mark.asyncio
    async def test_empty_predictions_returns_empty(self):
        session = _mock_session(self._payload([]))
        result = await _fetch_bus_chunk(session, ["1234"], "k", routes=None)
        assert result == []


# ---------------------------------------------------------------------------
# Bus Tracker — get_bus_arrivals (orchestration)
# ---------------------------------------------------------------------------

class TestGetBusArrivals:
    @pytest.mark.asyncio
    async def test_empty_stop_ids_returns_empty(self):
        # Should short-circuit without ever calling _get_session
        with patch.object(cta_client, "_get_session") as get_sess:
            arrivals, errors = await get_bus_arrivals([], bus_key="k")
        assert arrivals == []
        assert errors == 0
        get_sess.assert_not_called()

    @pytest.mark.asyncio
    async def test_more_than_ten_stops_chunked(self):
        # 25 stops → 3 chunks (10, 10, 5)
        stop_ids = [str(i) for i in range(25)]
        empty = {"bustime-response": {"prd": []}}
        session = _mock_session_sequence([empty, empty, empty])
        with patch.object(cta_client, "_get_session", return_value=session):
            arrivals, errors = await get_bus_arrivals(stop_ids, bus_key="k")
        assert arrivals == []
        assert errors == 0
        assert session.get.call_count == 3

    @pytest.mark.asyncio
    async def test_results_sorted_by_minutes(self):
        prds_a = [{"rt": "22", "rtdir": "N", "stpid": "1", "stpnm": "", "des": "",
                   "prdctdn": "9", "psgld": "EMPTY", "dly": "false"}]
        prds_b = [{"rt": "66", "rtdir": "E", "stpid": "2", "stpnm": "", "des": "",
                   "prdctdn": "2", "psgld": "EMPTY", "dly": "false"}]
        session = _mock_session_sequence([
            {"bustime-response": {"prd": prds_a}},
            {"bustime-response": {"prd": prds_b}},
        ])
        with patch.object(cta_client, "_get_session", return_value=session):
            arrivals, errors = await get_bus_arrivals(
                [str(i) for i in range(15)], bus_key="k",
            )
        assert errors == 0
        assert [a["arrives_in_minutes"] for a in arrivals] == [2, 9]

    @pytest.mark.asyncio
    async def test_chunk_failure_counted(self):
        good = {"bustime-response": {"prd": [
            {"rt": "22", "rtdir": "N", "stpid": "1", "stpnm": "", "des": "",
             "prdctdn": "5", "psgld": "EMPTY", "dly": "false"}
        ]}}
        # Build sequence: first chunk OK, second chunk raises
        resp = MagicMock()
        resp.json = AsyncMock(return_value=good)
        good_cm = MagicMock()
        good_cm.__aenter__ = AsyncMock(return_value=resp)
        good_cm.__aexit__ = AsyncMock(return_value=None)
        session = MagicMock()
        session.get = MagicMock(side_effect=[good_cm, ConnectionError("boom")])

        with patch.object(cta_client, "_get_session", return_value=session):
            arrivals, errors = await get_bus_arrivals(
                [str(i) for i in range(15)], bus_key="k",
            )
        assert errors == 1
        assert len(arrivals) == 1
        assert arrivals[0]["arrives_in_minutes"] == 5


# ---------------------------------------------------------------------------
# Alerts — _fetch_alerts_for_route
# ---------------------------------------------------------------------------

class TestFetchAlertsForRoute:
    def _payload(self, alerts):
        return {"CTAAlerts": {"Alert": alerts}}

    def _alert(self, **overrides):
        base = {
            "AlertId": "12345",
            "Headline": "Red Line delays",
            "Impact": "Delays",
            "SeverityScore": 50,
            "EventEnd": None,
            "ImpactedService": {"Service": [{"ServiceId": "Red"}]},
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_alerts_parsed(self):
        session = _mock_session(self._payload([self._alert()]))
        result = await _fetch_alerts_for_route(session, "red")
        assert len(result) == 1
        assert result[0]["alert_id"] == "12345"
        assert result[0]["headline"] == "Red Line delays"
        assert result[0]["severity_score"] == 50
        assert result[0]["is_major"] is False
        assert result[0]["affected_routes"] == ["Red"]

    @pytest.mark.asyncio
    async def test_single_alert_dict_normalized_to_list(self):
        session = _mock_session(self._payload(self._alert()))   # dict, not list
        result = await _fetch_alerts_for_route(session, "red")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_severity_70_marks_major(self):
        session = _mock_session(self._payload([self._alert(SeverityScore=70)]))
        result = await _fetch_alerts_for_route(session, "red")
        assert result[0]["is_major"] is True

    @pytest.mark.asyncio
    async def test_severity_69_not_major(self):
        session = _mock_session(self._payload([self._alert(SeverityScore=69)]))
        result = await _fetch_alerts_for_route(session, "red")
        assert result[0]["is_major"] is False

    @pytest.mark.asyncio
    async def test_single_service_dict_normalized(self):
        # ImpactedService.Service can be a dict (not a list) when only one service
        alert = self._alert(ImpactedService={"Service": {"ServiceId": "Blue"}})
        session = _mock_session(self._payload([alert]))
        result = await _fetch_alerts_for_route(session, "blue")
        assert result[0]["affected_routes"] == ["Blue"]

    @pytest.mark.asyncio
    async def test_multiple_services_collected(self):
        alert = self._alert(ImpactedService={
            "Service": [{"ServiceId": "Red"}, {"ServiceId": "Blue"}, {"ServiceId": "G"}]
        })
        session = _mock_session(self._payload([alert]))
        result = await _fetch_alerts_for_route(session, "red")
        assert result[0]["affected_routes"] == ["Red", "Blue", "G"]

    @pytest.mark.asyncio
    async def test_empty_string_event_end_normalized_to_none(self):
        session = _mock_session(self._payload([self._alert(EventEnd="")]))
        result = await _fetch_alerts_for_route(session, "red")
        assert result[0]["event_end"] is None

    @pytest.mark.asyncio
    async def test_event_end_string_preserved(self):
        session = _mock_session(self._payload(
            [self._alert(EventEnd="2026-05-05T12:00:00")]
        ))
        result = await _fetch_alerts_for_route(session, "red")
        assert result[0]["event_end"] == "2026-05-05T12:00:00"

    @pytest.mark.asyncio
    async def test_network_failure_returns_empty_list(self):
        session = _mock_session_raises(TimeoutError("API down"))
        result = await _fetch_alerts_for_route(session, "red")
        assert result == []

    @pytest.mark.asyncio
    async def test_missing_alert_section_returns_empty(self):
        # Some responses have CTAAlerts but no Alert key → []
        session = _mock_session({"CTAAlerts": {}})
        result = await _fetch_alerts_for_route(session, "red")
        assert result == []

    @pytest.mark.asyncio
    async def test_severity_score_zero_default(self):
        # SeverityScore missing → defaults to 0
        alert = {
            "AlertId": "1", "Headline": "x", "Impact": "y",
            "EventEnd": None, "ImpactedService": {"Service": []},
        }
        session = _mock_session(self._payload([alert]))
        result = await _fetch_alerts_for_route(session, "red")
        assert result[0]["severity_score"] == 0


# ---------------------------------------------------------------------------
# Alerts — get_alerts (orchestration)
# ---------------------------------------------------------------------------

class TestGetAlerts:
    @pytest.mark.asyncio
    async def test_empty_route_ids_returns_empty(self):
        # Must short-circuit without calling _get_session
        with patch.object(cta_client, "_get_session") as get_sess:
            result = await get_alerts([])
        assert result == []
        get_sess.assert_not_called()

    @pytest.mark.asyncio
    async def test_dedup_by_alert_id_across_routes(self):
        # The same alert appears in both per-route responses; should appear once
        alert = {
            "AlertId": "100", "Headline": "Multi-line", "Impact": "x",
            "SeverityScore": 30, "EventEnd": None,
            "ImpactedService": {"Service": [{"ServiceId": "Red"}, {"ServiceId": "Blue"}]},
        }
        payload = {"CTAAlerts": {"Alert": [alert]}}
        session = _mock_session_sequence([payload, payload])
        with patch.object(cta_client, "_get_session", return_value=session):
            result = await get_alerts(["red", "blue"])
        assert len(result) == 1
        assert result[0]["alert_id"] == "100"

    @pytest.mark.asyncio
    async def test_sorted_by_severity_descending(self):
        low = {"CTAAlerts": {"Alert": [{
            "AlertId": "L", "Headline": "low", "Impact": "x", "SeverityScore": 10,
            "EventEnd": None, "ImpactedService": {"Service": []},
        }]}}
        high = {"CTAAlerts": {"Alert": [{
            "AlertId": "H", "Headline": "high", "Impact": "x", "SeverityScore": 90,
            "EventEnd": None, "ImpactedService": {"Service": []},
        }]}}
        session = _mock_session_sequence([low, high])
        with patch.object(cta_client, "_get_session", return_value=session):
            result = await get_alerts(["red", "blue"])
        assert [a["alert_id"] for a in result] == ["H", "L"]


# ---------------------------------------------------------------------------
# Route Status — get_route_statuses
# ---------------------------------------------------------------------------

class TestGetRouteStatuses:
    @pytest.mark.asyncio
    async def test_multiple_routes_parsed(self):
        payload = {"CTARoutes": {"RouteInfo": [
            {"ServiceId": "red", "Route": "Red Line",
             "RouteStatus": "Normal Service", "RouteStatusColor": "#00C853"},
            {"ServiceId": "blue", "Route": "Blue Line",
             "RouteStatus": "Significant Delays", "RouteStatusColor": "#F00"},
        ]}}
        with patch.object(cta_client, "_get_session", return_value=_mock_session(payload)):
            result = await get_route_statuses()
        assert len(result) == 2
        assert result[0]["service_id"] == "red"
        assert result[0]["route"] == "Red Line"
        assert result[0]["status"] == "Normal Service"
        assert result[1]["status"] == "Significant Delays"

    @pytest.mark.asyncio
    async def test_single_route_dict_normalized(self):
        # If RouteInfo is a single dict instead of a list, it must still be parsed
        payload = {"CTARoutes": {"RouteInfo":
            {"ServiceId": "red", "Route": "Red Line",
             "RouteStatus": "Normal", "RouteStatusColor": "#0F0"}
        }}
        with patch.object(cta_client, "_get_session", return_value=_mock_session(payload)):
            result = await get_route_statuses()
        assert len(result) == 1
        assert result[0]["service_id"] == "red"

    @pytest.mark.asyncio
    async def test_network_failure_returns_empty(self):
        with patch.object(cta_client, "_get_session",
                          return_value=_mock_session_raises(TimeoutError("down"))):
            result = await get_route_statuses()
        assert result == []

    @pytest.mark.asyncio
    async def test_missing_routes_section_returns_empty(self):
        with patch.object(cta_client, "_get_session", return_value=_mock_session({})):
            result = await get_route_statuses()
        assert result == []

    @pytest.mark.asyncio
    async def test_unexpected_routeinfo_type_returns_empty(self):
        # If RouteInfo is neither dict nor list (e.g. a string), return []
        payload = {"CTARoutes": {"RouteInfo": "unexpected"}}
        with patch.object(cta_client, "_get_session", return_value=_mock_session(payload)):
            result = await get_route_statuses()
        assert result == []
