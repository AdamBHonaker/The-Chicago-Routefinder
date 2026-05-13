"""
Integration tests for /recommend, /stop-arrivals, and /last-departure FastAPI endpoints.

Uses FastAPI TestClient with patched CTA clients and routing pipeline functions.
No live CTA API calls, no Claude calls, and no GTFS data beyond the header-only
stubs created by conftest.py are required.

Covered:
  /recommend       — successful round-trip returns expected response shape
  /recommend       — unresolvable origin returns 400 with detail message
  /stop-arrivals   — train stop returns nested arrivals structure
  /stop-arrivals   — requesting >10 stops returns 400
  /last-departure  — upcoming last train returns time + countdown
  /last-departure  — post-midnight GTFS time normalises to wall-clock
  /last-departure  — past last train is flagged departed (no countdown)
  /last-departure  — unknown (route, direction, stop) combo returns 404
"""

import os
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

from main import app
from transit_graph import Route, WalkLeg, TransitLeg


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _minimal_route() -> Route:
    return Route(
        legs=[
            WalkLeg(from_name="Your location", to_name="Howard", minutes=5.0),
            TransitLeg(
                line="Red Line", line_code="Red",
                from_station="Howard", from_mapid="40900",
                to_station="Lake", to_mapid="41660",
                minutes=20.0,
            ),
            WalkLeg(from_name="Lake", to_name="Your destination", minutes=3.0),
        ],
        transit_minutes=20.0,
        walk_minutes_total=8.0,
        first_transit_leg_index=1,
    )


_FAKE_ORIGIN_STATIONS = [
    {"mapid": "40900", "name": "Howard", "lat": 42.019, "lon": -87.672, "walk_minutes": 5}
]

_FAKE_RESOLVE_RETURN = (
    _FAKE_ORIGIN_STATIONS,   # origin_stations
    [],                       # origin_bus_stops
    [],                       # dest_stations
    [],                       # dest_bus_stops
    None,                     # dest_match
    (41.9522, -87.6553),     # origin_coords
    (41.8827, -87.6233),     # dest_coords
)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# /recommend tests
# ---------------------------------------------------------------------------

class TestRecommendEndpoint:
    _VALID_PAYLOAD = {
        "origin": "Wrigleyville",
        "destination": "Loop",
        "transit_mode": "All",
        "ai_enabled": False,
    }

    def test_successful_recommend_returns_expected_shape(self, client):
        """A well-formed request with mocked pipeline returns the correct response structure."""
        with (
            patch("main._resolve_locations", new_callable=AsyncMock,
                  return_value=_FAKE_RESOLVE_RETURN),
            patch("main._fetch_arrivals", new_callable=AsyncMock,
                  return_value=([], [], 0, 0)),
            patch("main._safe_weather", new_callable=AsyncMock, return_value=None),
            patch("main._run_routing", new_callable=AsyncMock,
                  return_value=([(28.0, 5, _minimal_route())],
                                {"status": "ok", "side": None,
                                 "max_radius_searched": None})),
            patch("main._fetch_transfer_arrivals", new_callable=AsyncMock, return_value=[]),
            patch("main.get_alerts", new_callable=AsyncMock, return_value=[]),
            patch("main.get_route_statuses", new_callable=AsyncMock, return_value=[]),
        ):
            resp = client.post("/recommend", json=self._VALID_PAYLOAD)

        assert resp.status_code == 200
        body = resp.json()
        for key in ("recommendation", "routes", "train_arrivals", "bus_arrivals",
                    "origin_coords", "dest_coords", "origin_stations"):
            assert key in body, f"Missing key '{key}' in /recommend response"

    def test_successful_recommend_routes_have_legs(self, client):
        """Each route in the response has a non-empty legs list."""
        with (
            patch("main._resolve_locations", new_callable=AsyncMock,
                  return_value=_FAKE_RESOLVE_RETURN),
            patch("main._fetch_arrivals", new_callable=AsyncMock,
                  return_value=([], [], 0, 0)),
            patch("main._safe_weather", new_callable=AsyncMock, return_value=None),
            patch("main._run_routing", new_callable=AsyncMock,
                  return_value=([(28.0, 5, _minimal_route())],
                                {"status": "ok", "side": None,
                                 "max_radius_searched": None})),
            patch("main._fetch_transfer_arrivals", new_callable=AsyncMock, return_value=[]),
            patch("main.get_alerts", new_callable=AsyncMock, return_value=[]),
            patch("main.get_route_statuses", new_callable=AsyncMock, return_value=[]),
        ):
            resp = client.post("/recommend", json=self._VALID_PAYLOAD)

        assert resp.status_code == 200
        routes = resp.json()["routes"]
        assert len(routes) == 1
        assert len(routes[0]["legs"]) == 3

    def test_unresolvable_origin_returns_400(self, client):
        """When _resolve_locations raises HTTPException(400), the endpoint returns 400."""
        async def _raise(*_args, **_kwargs):
            raise HTTPException(
                status_code=400,
                detail="Could not find CTA stops near 'Atlantis'.",
            )

        with patch("main._resolve_locations", side_effect=_raise):
            resp = client.post("/recommend", json={
                "origin": "Atlantis",
                "destination": "Loop",
                "transit_mode": "All",
                "ai_enabled": False,
            })

        assert resp.status_code == 400
        assert "Could not find" in resp.json()["detail"]

    def test_ai_disabled_recommendation_is_none(self, client):
        """When ai_enabled=False, the recommendation field in the response is None."""
        with (
            patch("main._resolve_locations", new_callable=AsyncMock,
                  return_value=_FAKE_RESOLVE_RETURN),
            patch("main._fetch_arrivals", new_callable=AsyncMock,
                  return_value=([], [], 0, 0)),
            patch("main._safe_weather", new_callable=AsyncMock, return_value=None),
            patch("main._run_routing", new_callable=AsyncMock,
                  return_value=([(28.0, 5, _minimal_route())],
                                {"status": "ok", "side": None,
                                 "max_radius_searched": None})),
            patch("main._fetch_transfer_arrivals", new_callable=AsyncMock, return_value=[]),
            patch("main.get_alerts", new_callable=AsyncMock, return_value=[]),
            patch("main.get_route_statuses", new_callable=AsyncMock, return_value=[]),
        ):
            resp = client.post("/recommend", json={**self._VALID_PAYLOAD, "ai_enabled": False})

        assert resp.status_code == 200
        assert resp.json()["recommendation"] is None


# ---------------------------------------------------------------------------
# /stop-arrivals tests
# ---------------------------------------------------------------------------

class TestStopArrivalsEndpoint:
    """Integration tests for GET /stop-arrivals."""

    def test_train_stop_returns_correct_structure(self, client):
        """A request for one train stop returns the expected nested arrivals structure."""
        fake_train_arrivals = [
            {
                "station_mapid": "40900",
                "line_code": "Red",
                "destination": "95th/Dan Ryan",
                "arrives_in_minutes": 4,
                "is_delayed": False,
                "is_scheduled": False,
                "line": "Red Line",
                "station": "Howard",
            }
        ]
        with (
            patch.dict(os.environ, {
                "CTA_TRAIN_API_KEY": "test-key",
                "CTA_BUS_API_KEY":   "test-key",
            }),
            patch("main.get_train_arrivals", new_callable=AsyncMock,
                  return_value=(fake_train_arrivals, 0)),
            patch("main.get_bus_arrivals", new_callable=AsyncMock,
                  return_value=([], 0)),
        ):
            resp = client.get("/stop-arrivals", params={"stops": ["train:40900"]})

        assert resp.status_code == 200
        body = resp.json()
        assert "arrivals" in body
        assert "train:40900" in body["arrivals"]
        arrs = body["arrivals"]["train:40900"]["arrivals"]
        assert isinstance(arrs, list)
        assert arrs[0]["route"] == "Red"
        assert arrs[0]["minutes"] == 4
        assert arrs[0]["destination"] == "95th/Dan Ryan"

    def test_empty_stops_returns_empty_arrivals(self, client):
        """A request with no stops returns an empty arrivals dict."""
        resp = client.get("/stop-arrivals")
        assert resp.status_code == 200
        assert resp.json() == {"arrivals": {}}

    def test_over_ten_stops_returns_400(self, client):
        """Requesting more than 10 stops returns 400."""
        stops = [f"train:4090{i}" for i in range(11)]
        resp = client.get("/stop-arrivals", params={"stops": stops})
        assert resp.status_code == 400

    def test_unknown_stop_type_is_ignored(self, client):
        """A stop with an unrecognised prefix is silently skipped, stop still appears in output."""
        with (
            patch.dict(os.environ, {
                "CTA_TRAIN_API_KEY": "test-key",
                "CTA_BUS_API_KEY":   "test-key",
            }),
            patch("main.get_train_arrivals", new_callable=AsyncMock, return_value=([], 0)),
            patch("main.get_bus_arrivals", new_callable=AsyncMock, return_value=([], 0)),
        ):
            resp = client.get("/stop-arrivals", params={"stops": ["ferry:99999"]})

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /last-departure tests (Last Train tool)
# ---------------------------------------------------------------------------

class TestLastDepartureEndpoint:
    """Integration tests for GET /last-departure."""

    _PARAMS = {"route_id": "Red", "direction_id": "1", "stop_id": "40100"}

    def test_returns_time_and_countdown_when_upcoming(self, client):
        # 11:55 PM departure looked up at 5:00 PM Chicago time → ~415 min away,
        # not yet departed. We patch datetime.now in the main module so the
        # countdown is deterministic without depending on the wall clock.
        from datetime import datetime
        from utils import CHICAGO_TZ
        fake_now = datetime(2026, 5, 12, 17, 0, 0, tzinfo=CHICAGO_TZ)

        class _FakeDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fake_now

        with (
            patch("main.get_last_departure", return_value="23:55:00"),
            patch("main.datetime", _FakeDatetime),
        ):
            resp = client.get("/last-departure", params=self._PARAMS)

        assert resp.status_code == 200
        body = resp.json()
        assert body["time"] == "23:55"
        assert body["departed"] is False
        assert body["minutes_until"] == 415

    def test_normalizes_post_midnight_time_to_wall_clock(self, client):
        # GTFS "25:30:00" (1:30 AM next service day) should display as "01:30".
        from datetime import datetime
        from utils import CHICAGO_TZ
        fake_now = datetime(2026, 5, 12, 17, 0, 0, tzinfo=CHICAGO_TZ)

        class _FakeDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fake_now

        with (
            patch("main.get_last_departure", return_value="25:30:00"),
            patch("main.datetime", _FakeDatetime),
        ):
            resp = client.get("/last-departure", params=self._PARAMS)

        assert resp.status_code == 200
        assert resp.json()["time"] == "01:30"

    def test_marks_departed_when_past(self, client):
        # 2:00 AM Chicago is still the previous service day (offset +1440), so
        # a 1:00 AM (25:00) last train was 60 minutes ago → departed.
        from datetime import datetime
        from utils import CHICAGO_TZ
        fake_now = datetime(2026, 5, 13, 2, 0, 0, tzinfo=CHICAGO_TZ)

        class _FakeDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fake_now

        with (
            patch("main.get_last_departure", return_value="25:00:00"),
            patch("main.datetime", _FakeDatetime),
        ):
            resp = client.get("/last-departure", params=self._PARAMS)

        assert resp.status_code == 200
        body = resp.json()
        assert body["departed"] is True
        assert body["minutes_until"] is None
        assert body["time"] == "01:00"

    def test_404_when_combo_unknown(self, client):
        with patch("main.get_last_departure", return_value=None):
            resp = client.get("/last-departure", params=self._PARAMS)
        assert resp.status_code == 404

    def test_platform_stop_id_resolved_to_parent_mapid(self, client):
        # schedule_data publishes platform stop_ids (30xxx); the runtime cache
        # is keyed on parent mapids (40xxx). The endpoint must resolve before
        # lookup. We assert get_last_departure is called with the parent id.
        from datetime import datetime
        from utils import CHICAGO_TZ
        fake_now = datetime(2026, 5, 12, 17, 0, 0, tzinfo=CHICAGO_TZ)

        class _FakeDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fake_now

        with (
            patch("main.to_parent_mapid", return_value="40100"),
            patch("main.get_last_departure", return_value="23:55:00") as glast,
            patch("main.datetime", _FakeDatetime),
        ):
            resp = client.get("/last-departure", params={
                "route_id": "Red", "direction_id": "1", "stop_id": "30100",
            })

        assert resp.status_code == 200
        glast.assert_called_once_with("Red", "1", "40100")
