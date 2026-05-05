"""
Tests for graph routing in backend/transit_graph.py:
  - _path_to_route — converts an nx.shortest_simple_paths node sequence
                     into a structured Route (the most complex pure-logic
                     function in the module after the GTFS streamer)
  - find_routes    — end-to-end shortest-path discovery on a hand-built
                     fixture graph

Both layers are exercised with synthetic graphs so no GTFS feed, no OSM
walking graph, no live API, and no module-level state from real warm-up
is required.

Covered:
  _path_to_route
    - ORIGIN→station opening leg becomes a WalkLeg with the right minutes
    - Single transit leg with one transit edge
    - Consecutive same-route edges grouped into one TransitLeg
    - Different routes NOT grouped — one TransitLeg per line
    - "transfer" edges become WalkLegs with the edge weight
    - "walk" edges (intermodal train↔bus) become WalkLegs
    - station→DEST closing leg becomes a WalkLeg
    - Same-station line change inserts a platform-transfer walk
    - transfers count = max(0, n_transit_legs - 1)
    - first_transit_leg_index points at the first TransitLeg
    - Path of length 1 returns None (degenerate)
    - walk_minutes_total / transit_minutes summed correctly

  find_routes
    - Single-line trip returns one route with one transit leg
    - Two-line trip with transfer returns a route with two transit legs
    - When a faster path exists, it is preferred over a slower one
    - n_routes parameter caps the number of routes returned
    - No-path scenario returns []
"""

import threading
from unittest.mock import patch

import pytest
import networkx as nx

import transit_graph
from transit_graph import (
    _path_to_route,
    find_routes,
    Route,
    WalkLeg,
    TransitLeg,
    _TRANSFER_MINUTES,
    _MAX_TRANSFERS,
)


ORIGIN = "__ORIGIN__"
DEST   = "__DEST__"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stations(*pairs) -> dict:
    """Build a stations dict from (mapid, name, lat, lon) tuples."""
    return {mapid: {"name": name, "lat": lat, "lon": lon}
            for (mapid, name, lat, lon) in pairs}


def _make_graph(edges: list[tuple[str, str, dict]],
                node_attrs: dict[str, dict] | None = None) -> nx.DiGraph:
    """Build a DiGraph from (u, v, attr_dict) triples and optional node attrs."""
    G = nx.DiGraph()
    for u, v, attrs in edges:
        G.add_edge(u, v, **attrs)
    for node, attrs in (node_attrs or {}).items():
        for k, val in attrs.items():
            G.nodes[node][k] = val
    return G


@pytest.fixture(autouse=True)
def _patch_external_helpers():
    """
    _path_to_route calls into walking + best_exit + get_shape; in unit tests
    we want pure path-→-Route logic, not real geometry. Replace each with a
    deterministic no-op for the duration of the test.
    """
    with (
        patch("transit_graph.street_walk_path", return_value=[]),
        patch("transit_graph.street_walk_directions", return_value=[]),
        patch("transit_graph.best_exit", return_value=None),
        patch("transit_graph.get_shape", return_value=None),
    ):
        yield


# ---------------------------------------------------------------------------
# _path_to_route
# ---------------------------------------------------------------------------

class TestPathToRoute:
    def test_path_too_short_returns_none(self):
        # One node — nothing to traverse
        result = _path_to_route([ORIGIN], nx.DiGraph(), {}, {}, {})
        assert result is None

    def test_simple_walk_transit_walk(self):
        # ORIGIN -walk→ A -transit→ B -walk→ DEST
        G = _make_graph([
            (ORIGIN, "40100", {"weight": 5.0, "edge_type": "walk", "route_id": "walk"}),
            ("40100", "40200", {"weight": 8.0, "edge_type": "transit",
                                "route_id": "Red", "direction_id": "0", "line": "Red Line"}),
            ("40200", DEST,    {"weight": 3.0, "edge_type": "walk", "route_id": "walk"}),
        ])
        stations = _stations(
            ("40100", "Howard", 42.0, -87.6),
            ("40200", "Lake",   41.9, -87.6),
        )
        route = _path_to_route(
            [ORIGIN, "40100", "40200", DEST], G, stations,
            origin_walk_lookup={"40100": 5.0},
            dest_walk_lookup={"40200": 3.0},
        )
        assert route is not None
        assert len(route.legs) == 3
        assert isinstance(route.legs[0], WalkLeg)
        assert isinstance(route.legs[1], TransitLeg)
        assert isinstance(route.legs[2], WalkLeg)
        assert route.legs[0].minutes == 5.0
        assert route.legs[1].minutes == 8.0
        assert route.legs[2].minutes == 3.0

    def test_transit_minutes_and_walk_minutes_summed(self):
        G = _make_graph([
            (ORIGIN, "40100", {"weight": 5.0, "edge_type": "walk"}),
            ("40100", "40200", {"weight": 8.0, "edge_type": "transit",
                                "route_id": "Red", "line": "Red Line"}),
            ("40200", DEST,    {"weight": 3.0, "edge_type": "walk"}),
        ])
        stations = _stations(
            ("40100", "Howard", 42.0, -87.6),
            ("40200", "Lake",   41.9, -87.6),
        )
        route = _path_to_route(
            [ORIGIN, "40100", "40200", DEST], G, stations,
            origin_walk_lookup={"40100": 5.0},
            dest_walk_lookup={"40200": 3.0},
        )
        assert route.transit_minutes == 8.0
        assert route.walk_minutes_total == 8.0   # 5 + 3
        assert route.total_minutes_no_wait == 16.0

    def test_consecutive_same_route_edges_grouped(self):
        # A→B→C→D, all on Red Line; should compress to one TransitLeg from A→D
        G = _make_graph([
            (ORIGIN, "40100", {"weight": 5.0, "edge_type": "walk"}),
            ("40100", "40110", {"weight": 2.0, "edge_type": "transit",
                                "route_id": "Red", "direction_id": "0", "line": "Red Line"}),
            ("40110", "40120", {"weight": 3.0, "edge_type": "transit",
                                "route_id": "Red", "direction_id": "0", "line": "Red Line"}),
            ("40120", "40130", {"weight": 4.0, "edge_type": "transit",
                                "route_id": "Red", "direction_id": "0", "line": "Red Line"}),
            ("40130", DEST,    {"weight": 3.0, "edge_type": "walk"}),
        ])
        stations = _stations(
            ("40100", "A", 42.0, -87.6),
            ("40110", "B", 41.95, -87.6),
            ("40120", "C", 41.90, -87.6),
            ("40130", "D", 41.85, -87.6),
        )
        route = _path_to_route(
            [ORIGIN, "40100", "40110", "40120", "40130", DEST], G, stations,
            origin_walk_lookup={"40100": 5.0},
            dest_walk_lookup={"40130": 3.0},
        )
        # Walk + ONE merged TransitLeg + Walk
        assert len(route.legs) == 3
        transit = route.legs[1]
        assert isinstance(transit, TransitLeg)
        assert transit.from_mapid == "40100"
        assert transit.to_mapid == "40130"
        assert transit.minutes == 9.0   # 2 + 3 + 4
        assert route.transfers == 0     # one transit leg → no transfers

    def test_different_routes_not_grouped(self):
        # Red Line A→B, then Blue Line B→C — must be two TransitLegs
        G = _make_graph([
            (ORIGIN, "40100", {"weight": 5.0, "edge_type": "walk"}),
            ("40100", "40200", {"weight": 5.0, "edge_type": "transit",
                                "route_id": "Red", "direction_id": "0", "line": "Red Line"}),
            ("40200", "40300", {"weight": 6.0, "edge_type": "transit",
                                "route_id": "Blue", "direction_id": "0", "line": "Blue Line"}),
            ("40300", DEST,    {"weight": 4.0, "edge_type": "walk"}),
        ])
        stations = _stations(
            ("40100", "A", 42.0, -87.6),
            ("40200", "B", 41.9, -87.6),
            ("40300", "C", 41.8, -87.6),
        )
        route = _path_to_route(
            [ORIGIN, "40100", "40200", "40300", DEST], G, stations,
            origin_walk_lookup={"40100": 5.0},
            dest_walk_lookup={"40300": 4.0},
        )
        # Same-station line change at 40200 inserts a platform-transfer walk
        # Expect: Walk, Transit(Red), Walk(transfer), Transit(Blue), Walk
        transit_legs = [l for l in route.legs if isinstance(l, TransitLeg)]
        assert len(transit_legs) == 2
        assert transit_legs[0].line_code == "Red"
        assert transit_legs[1].line_code == "Blue"
        assert route.transfers == 1   # 2 transit legs → 1 transfer

    def test_transfer_edge_becomes_walk_leg(self):
        # Transfer edge between two parent stations (e.g. transfers.txt entry)
        G = _make_graph([
            (ORIGIN, "40100", {"weight": 5.0, "edge_type": "walk"}),
            ("40100", "40200", {"weight": 5.0, "edge_type": "transit",
                                "route_id": "Red", "direction_id": "0", "line": "Red Line"}),
            ("40200", "40300", {"weight": 2.5, "edge_type": "transfer"}),
            ("40300", "40400", {"weight": 6.0, "edge_type": "transit",
                                "route_id": "Blue", "direction_id": "0", "line": "Blue Line"}),
            ("40400", DEST,    {"weight": 4.0, "edge_type": "walk"}),
        ])
        stations = _stations(
            ("40100", "A", 42.0, -87.6),
            ("40200", "B", 41.9, -87.6),
            ("40300", "C", 41.9, -87.6),
            ("40400", "D", 41.8, -87.6),
        )
        route = _path_to_route(
            [ORIGIN, "40100", "40200", "40300", "40400", DEST], G, stations,
            origin_walk_lookup={"40100": 5.0},
            dest_walk_lookup={"40400": 4.0},
        )
        # Walk, Transit(Red), Walk(transfer 2.5), Transit(Blue), Walk
        assert isinstance(route.legs[2], WalkLeg)
        assert route.legs[2].minutes == 2.5
        assert route.legs[2].from_name == "B"
        assert route.legs[2].to_name == "C"
        assert route.transfers == 1

    def test_intermodal_walk_edge_becomes_walk_leg(self):
        # Intermodal walk between train station and bus stop (Feature B)
        G = _make_graph(
            edges=[
                (ORIGIN, "40100", {"weight": 5.0, "edge_type": "walk"}),
                ("40100", "40200", {"weight": 5.0, "edge_type": "transit",
                                    "route_id": "Red", "direction_id": "0", "line": "Red Line"}),
                ("40200", "1234",  {"weight": 1.5, "edge_type": "walk"}),  # train→bus walk
                ("1234",  "5678",  {"weight": 8.0, "edge_type": "transit",
                                    "route_id": "22", "direction_id": "0", "line": "22"}),
                ("5678",  DEST,    {"weight": 3.0, "edge_type": "walk"}),
            ],
            node_attrs={
                "1234": {"name": "Clark & Belmont", "lat": 41.94, "lon": -87.65},
                "5678": {"name": "State & Madison", "lat": 41.88, "lon": -87.63},
            },
        )
        stations = _stations(
            ("40100", "A", 42.0, -87.6),
            ("40200", "B", 41.95, -87.6),
        )
        route = _path_to_route(
            [ORIGIN, "40100", "40200", "1234", "5678", DEST], G, stations,
            origin_walk_lookup={"40100": 5.0},
            dest_walk_lookup={"5678": 3.0},
        )
        # Walk, Transit(Red), Walk(intermodal 1.5), Transit(22), Walk
        assert len(route.legs) == 5
        assert isinstance(route.legs[2], WalkLeg)
        assert route.legs[2].minutes == 1.5
        assert route.legs[2].from_name == "B"
        assert route.legs[2].to_name == "Clark & Belmont"
        # Transit leg uses bus stop node name from G.nodes
        bus_leg = route.legs[3]
        assert isinstance(bus_leg, TransitLeg)
        assert bus_leg.line_code == "22"
        assert bus_leg.from_station == "Clark & Belmont"

    def test_first_transit_leg_index_points_at_first_transit(self):
        G = _make_graph([
            (ORIGIN, "40100", {"weight": 5.0, "edge_type": "walk"}),
            ("40100", "40200", {"weight": 5.0, "edge_type": "transit",
                                "route_id": "Red", "line": "Red Line"}),
            ("40200", DEST,    {"weight": 3.0, "edge_type": "walk"}),
        ])
        stations = _stations(("40100", "A", 0, 0), ("40200", "B", 0, 0))
        route = _path_to_route(
            [ORIGIN, "40100", "40200", DEST], G, stations,
            origin_walk_lookup={"40100": 5.0}, dest_walk_lookup={"40200": 3.0},
        )
        # Index 0 is opening walk; index 1 is the first transit
        assert route.first_transit_leg_index == 1

    def test_transfers_count_with_three_transit_legs(self):
        # Three different lines back-to-back-to-back via transfer edges
        G = _make_graph([
            (ORIGIN, "40100", {"weight": 5.0, "edge_type": "walk"}),
            ("40100", "40200", {"weight": 5.0, "edge_type": "transit",
                                "route_id": "Red", "line": "Red Line"}),
            ("40200", "40300", {"weight": 2.0, "edge_type": "transfer"}),
            ("40300", "40400", {"weight": 6.0, "edge_type": "transit",
                                "route_id": "Blue", "line": "Blue Line"}),
            ("40400", "40500", {"weight": 2.0, "edge_type": "transfer"}),
            ("40500", "40600", {"weight": 4.0, "edge_type": "transit",
                                "route_id": "G", "line": "Green Line"}),
            ("40600", DEST,    {"weight": 3.0, "edge_type": "walk"}),
        ])
        stations = _stations(
            ("40100", "A", 0, 0), ("40200", "B", 0, 0),
            ("40300", "C", 0, 0), ("40400", "D", 0, 0),
            ("40500", "E", 0, 0), ("40600", "F", 0, 0),
        )
        route = _path_to_route(
            [ORIGIN, "40100", "40200", "40300", "40400", "40500", "40600", DEST],
            G, stations,
            origin_walk_lookup={"40100": 5.0}, dest_walk_lookup={"40600": 3.0},
        )
        transit_legs = [l for l in route.legs if isinstance(l, TransitLeg)]
        assert len(transit_legs) == 3
        assert route.transfers == 2

    def test_walk_only_route_has_zero_transfers(self):
        # Edge case: only walk legs, no transit
        G = _make_graph([
            (ORIGIN, "40100", {"weight": 4.0, "edge_type": "walk"}),
            ("40100", DEST,    {"weight": 6.0, "edge_type": "walk"}),
        ])
        stations = _stations(("40100", "A", 0, 0))
        route = _path_to_route(
            [ORIGIN, "40100", DEST], G, stations,
            origin_walk_lookup={"40100": 4.0}, dest_walk_lookup={"40100": 6.0},
        )
        assert route.transfers == 0
        assert route.transit_minutes == 0.0
        assert route.first_transit_leg_index is None

    def test_origin_walk_lookup_overrides_edge_weight(self):
        # The graph has weight=10 on the ORIGIN→40100 edge but the lookup
        # provides 4.0 — _path_to_route must trust the lookup for opening walk.
        G = _make_graph([
            (ORIGIN, "40100", {"weight": 10.0, "edge_type": "walk"}),
            ("40100", "40200", {"weight": 5.0, "edge_type": "transit",
                                "route_id": "Red", "line": "Red Line"}),
            ("40200", DEST,    {"weight": 3.0, "edge_type": "walk"}),
        ])
        stations = _stations(("40100", "A", 0, 0), ("40200", "B", 0, 0))
        route = _path_to_route(
            [ORIGIN, "40100", "40200", DEST], G, stations,
            origin_walk_lookup={"40100": 4.0},   # ← overrides edge weight
            dest_walk_lookup={"40200": 3.0},
        )
        assert route.legs[0].minutes == 4.0


# ---------------------------------------------------------------------------
# find_routes
# ---------------------------------------------------------------------------

class TestFindRoutes:
    """
    Integration tests on a hand-built fixture graph. Patches:
      - _build_graph    → return our small graph
      - find_nearest_train_stations / find_nearest_bus_stops → fixed lists
    The fixture graph contains 4 train parent stations connected by transit
    edges + one transfer edge. No bus stops, no shapes, no GTFS.
    """

    @pytest.fixture(autouse=True)
    def _isolate_thread_local(self):
        # find_routes now mutates the shared graph under a routing lock instead
        # of keeping a per-thread copy. Reset the lock between tests so a prior
        # test failure that left it held doesn't deadlock the next test.
        transit_graph._routing_lock = threading.Lock()
        yield
        transit_graph._routing_lock = threading.Lock()

    def _fixture_graph(self) -> tuple[nx.DiGraph, dict]:
        """
        Build a small Y-shaped network for testing routing decisions:

            40100 (Howard) ──Red──► 40200 (Belmont) ──Red──► 40300 (Loop)
                                                              │
                                                              transfer (3 min)
                                                              │
                                                              ▼
                                          40400 (Roosevelt) ◄─Red─ 40300

            40400 has a Blue connection to 40500 (Clark/Lake).

        This lets us test:
          - direct same-line trip Howard→Loop
          - transfer Howard→Loop→Roosevelt→Clark/Lake (Red→transfer→Blue)
        """
        G = nx.DiGraph()
        G.add_edge("40100", "40200", weight=8.0, edge_type="transit",
                   route_id="Red", direction_id="0", line="Red Line")
        G.add_edge("40200", "40300", weight=10.0, edge_type="transit",
                   route_id="Red", direction_id="0", line="Red Line")
        G.add_edge("40300", "40400", weight=3.0, edge_type="transfer")
        G.add_edge("40400", "40500", weight=7.0, edge_type="transit",
                   route_id="Blue", direction_id="0", line="Blue Line")

        stations = {
            "40100": {"name": "Howard",      "lat": 42.019, "lon": -87.672},
            "40200": {"name": "Belmont",     "lat": 41.940, "lon": -87.653},
            "40300": {"name": "Loop",        "lat": 41.885, "lon": -87.628},
            "40400": {"name": "Roosevelt",   "lat": 41.867, "lon": -87.627},
            "40500": {"name": "Clark/Lake",  "lat": 41.886, "lon": -87.631},
        }
        return G, stations

    def _patch_routing(self, G, stations, origin_mapid: str, dest_mapid: str,
                       origin_walk: float = 5.0, dest_walk: float = 3.0):
        """Patch context for find_routes: graph + nearest-station lookups."""
        return (
            patch.object(transit_graph, "_build_graph", return_value=(G, stations)),
            patch.object(transit_graph, "find_nearest_train_stations", side_effect=[
                # First call (origin), second call (destination)
                [{"mapid": origin_mapid, "name": stations[origin_mapid]["name"],
                  "lat": stations[origin_mapid]["lat"],
                  "lon": stations[origin_mapid]["lon"],
                  "walk_minutes": origin_walk}],
                [{"mapid": dest_mapid, "name": stations[dest_mapid]["name"],
                  "lat": stations[dest_mapid]["lat"],
                  "lon": stations[dest_mapid]["lon"],
                  "walk_minutes": dest_walk}],
            ]),
            patch.object(transit_graph, "find_nearest_bus_stops", return_value=[]),
        )

    def test_single_line_trip_returns_one_transit_leg(self):
        G, stations = self._fixture_graph()
        p1, p2, p3 = self._patch_routing(G, stations, "40100", "40300")
        with p1, p2, p3:
            routes = find_routes(42.019, -87.672, 41.885, -87.628)

        assert len(routes) >= 1
        r = routes[0]
        transit_legs = [l for l in r.legs if isinstance(l, TransitLeg)]
        assert len(transit_legs) == 1
        assert transit_legs[0].line_code == "Red"
        assert transit_legs[0].from_mapid == "40100"
        assert transit_legs[0].to_mapid == "40300"
        # Transit time = 8 + 10 = 18 (two grouped Red edges)
        assert transit_legs[0].minutes == 18.0
        assert r.transfers == 0

    def test_transfer_trip_returns_two_transit_legs(self):
        G, stations = self._fixture_graph()
        p1, p2, p3 = self._patch_routing(G, stations, "40100", "40500")
        with p1, p2, p3:
            routes = find_routes(42.019, -87.672, 41.886, -87.631)

        assert len(routes) >= 1
        r = routes[0]
        transit_legs = [l for l in r.legs if isinstance(l, TransitLeg)]
        assert len(transit_legs) == 2
        assert transit_legs[0].line_code == "Red"
        assert transit_legs[1].line_code == "Blue"
        assert r.transfers == 1
        # Transit minutes = 18 (Red Howard→Loop) + 7 (Blue Roosevelt→Clark/Lake) = 25
        assert r.transit_minutes == 25.0

    def test_n_routes_caps_results(self):
        # Build a graph with multiple parallel routes between origin and dest
        G = nx.DiGraph()
        # Three parallel direct edges with slightly different weights
        for i, w in enumerate((10.0, 12.0, 14.0)):
            mid = f"4010{i}"
            G.add_edge("40100", mid, weight=2.0, edge_type="transit",
                       route_id=f"R{i}", line=f"Line {i}")
            G.add_edge(mid, "40200", weight=w, edge_type="transit",
                       route_id=f"R{i}", line=f"Line {i}")
        stations = {
            "40100": {"name": "A", "lat": 0, "lon": 0},
            "40101": {"name": "B1", "lat": 0, "lon": 0},
            "40102": {"name": "B2", "lat": 0, "lon": 0},
            "40103": {"name": "B3", "lat": 0, "lon": 0},
            "40200": {"name": "C", "lat": 0, "lon": 0},
        }
        p1, p2, p3 = self._patch_routing(G, stations, "40100", "40200")
        with p1, p2, p3:
            routes = find_routes(0, 0, 0, 0, n_routes=2)

        assert len(routes) == 2

    def test_no_path_returns_empty_list(self):
        # Disconnected graph: origin and dest in separate components
        G = nx.DiGraph()
        G.add_edge("40100", "40200", weight=5.0, edge_type="transit",
                   route_id="Red", line="Red Line")
        G.add_edge("40300", "40400", weight=5.0, edge_type="transit",
                   route_id="Blue", line="Blue Line")
        stations = {
            "40100": {"name": "A", "lat": 0, "lon": 0},
            "40200": {"name": "B", "lat": 0, "lon": 0},
            "40300": {"name": "C", "lat": 0, "lon": 0},
            "40400": {"name": "D", "lat": 0, "lon": 0},
        }
        # Origin in component 1, dest in component 2 — no path
        p1, p2, p3 = self._patch_routing(G, stations, "40100", "40400")
        with p1, p2, p3:
            routes = find_routes(0, 0, 0, 0)

        assert routes == []

    def test_faster_route_preferred(self):
        # Two paths: one slow (transit 30 min), one fast (transit 10 min)
        G = nx.DiGraph()
        # Slow path: ORIGIN→40100→40200→DEST via Red, 30 min transit
        G.add_edge("40100", "40200", weight=30.0, edge_type="transit",
                   route_id="Red", line="Red Line")
        # Fast path: ORIGIN→40300→40200→DEST via Blue, 10 min transit
        # 40300 must also be connected so Dijkstra considers it
        G.add_edge("40300", "40200", weight=10.0, edge_type="transit",
                   route_id="Blue", line="Blue Line")
        stations = {
            "40100": {"name": "Slow Start", "lat": 0, "lon": 0},
            "40200": {"name": "End",        "lat": 0, "lon": 0},
            "40300": {"name": "Fast Start", "lat": 0, "lon": 0},
        }
        # Both origin stations available with the same walk time —
        # Dijkstra chooses based on transit weight.
        with (
            patch.object(transit_graph, "_build_graph", return_value=(G, stations)),
            patch.object(transit_graph, "find_nearest_train_stations", side_effect=[
                # Origin: both stations are equally close
                [
                    {"mapid": "40100", "name": "Slow Start", "lat": 0, "lon": 0,
                     "walk_minutes": 5.0},
                    {"mapid": "40300", "name": "Fast Start", "lat": 0, "lon": 0,
                     "walk_minutes": 5.0},
                ],
                # Destination
                [{"mapid": "40200", "name": "End", "lat": 0, "lon": 0,
                  "walk_minutes": 3.0}],
            ]),
            patch.object(transit_graph, "find_nearest_bus_stops", return_value=[]),
        ):
            routes = find_routes(0, 0, 0, 0, n_routes=1)

        assert len(routes) == 1
        # Fast route uses Blue (10 min), not Red (30 min)
        transit = next(l for l in routes[0].legs if isinstance(l, TransitLeg))
        assert transit.line_code == "Blue"
        assert transit.minutes == 10.0


class TestMaxTransfersCap:
    """find_routes drops any candidate path with more than _MAX_TRANSFERS
    transfers (line changes). The cap exists so Yen's algorithm can't surface
    absurd 4+ transfer itineraries."""

    @pytest.fixture(autouse=True)
    def _isolate_thread_local(self):
        transit_graph._routing_lock = threading.Lock()
        yield
        transit_graph._routing_lock = threading.Lock()

    def _chain_graph(self, n_lines: int) -> tuple[nx.DiGraph, dict]:
        """Build a chain of n_lines distinct routes connected by transfer edges:

            40100 ─L0─► 40101 ─xfer─► 40102 ─L1─► 40103 ─xfer─► … ► 40{2n-1}

        The shortest path from origin (40100) to destination (40{2n-1})
        traverses every line, producing n_lines transit legs and
        (n_lines - 1) transfers.
        """
        G = nx.DiGraph()
        stations: dict[str, dict] = {}
        for i in range(n_lines):
            board = f"4010{2*i}"
            alight = f"4010{2*i + 1}"
            G.add_edge(board, alight, weight=4.0, edge_type="transit",
                       route_id=f"L{i}", direction_id="0", line=f"Line {i}")
            stations[board]  = {"name": f"S{2*i}",   "lat": 0, "lon": 0}
            stations[alight] = {"name": f"S{2*i+1}", "lat": 0, "lon": 0}
            if i + 1 < n_lines:
                next_board = f"4010{2*(i+1)}"
                G.add_edge(alight, next_board, weight=2.0, edge_type="transfer")
        return G, stations

    def _patch(self, G, stations, origin_mapid, dest_mapid):
        return (
            patch.object(transit_graph, "_build_graph", return_value=(G, stations)),
            patch.object(transit_graph, "find_nearest_train_stations", side_effect=[
                [{"mapid": origin_mapid, "name": stations[origin_mapid]["name"],
                  "lat": 0, "lon": 0, "walk_minutes": 1.0}],
                [{"mapid": dest_mapid, "name": stations[dest_mapid]["name"],
                  "lat": 0, "lon": 0, "walk_minutes": 1.0}],
            ]),
            patch.object(transit_graph, "find_nearest_bus_stops", return_value=[]),
        )

    def test_cap_is_two_transfers(self):
        """Sanity check: the constant the cap is enforced against is 2."""
        assert _MAX_TRANSFERS == 2

    def test_three_transit_legs_allowed(self):
        """A 3-transit-leg / 2-transfer route is at the cap and must be returned."""
        G, stations = self._chain_graph(3)   # 3 lines → 2 transfers
        p1, p2, p3 = self._patch(G, stations, "40100", "40105")
        with p1, p2, p3:
            routes = find_routes(0, 0, 0, 0, n_routes=3)
        assert len(routes) >= 1
        # The shortest path traverses all 3 lines.
        r = routes[0]
        transit_legs = [l for l in r.legs if isinstance(l, TransitLeg)]
        assert len(transit_legs) == 3
        assert r.transfers == 2

    def test_four_transit_legs_dropped(self):
        """A 4-transit-leg / 3-transfer chain exceeds the cap → no routes returned."""
        G, stations = self._chain_graph(4)   # 4 lines → 3 transfers (over cap)
        p1, p2, p3 = self._patch(G, stations, "40100", "40107")
        with p1, p2, p3:
            routes = find_routes(0, 0, 0, 0, n_routes=3)
        # The only path through the chain has 3 transfers — above the cap, so
        # find_routes must drop it and return nothing.
        assert routes == []

    def test_cap_only_drops_over_limit_routes(self):
        """When both a capped and an over-cap path exist, only the capped one
        is returned."""
        # 4-line chain: 40100→40101→40102→40103→40104→40105→40106→40107
        # Add a direct shortcut from 40100→40107 via a single line so a 0-transfer
        # alternative exists. Yen's may surface both, but only the 0-transfer
        # path is at/under the cap.
        G, stations = self._chain_graph(4)
        # Direct shortcut, but slower so Yen's still considers the chain second.
        G.add_edge("40100", "40107", weight=100.0, edge_type="transit",
                   route_id="Express", direction_id="0", line="Express")
        p1, p2, p3 = self._patch(G, stations, "40100", "40107")
        with p1, p2, p3:
            routes = find_routes(0, 0, 0, 0, n_routes=3)
        assert len(routes) == 1
        assert routes[0].transfers == 0
        assert all(r.transfers <= _MAX_TRANSFERS for r in routes)
