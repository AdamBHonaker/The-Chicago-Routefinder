"""
Unit tests for the pure-function pieces of the geocode ingest scripts:

  - build_address_points.normalize_elements / _extract_coords / quantize_coord / _chunk_bboxes
  - build_intersections._build_linestrings / _find_intersections

Network-dependent code paths (the Overpass _fetch_* helpers) are not tested
here — they're integration-tested by actually running the scripts.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str):
    """Load a script module by file path; works whether or not scripts/ is a package."""
    path = _SCRIPTS_DIR / f"{name}.py"
    # Ensure backend/ is on sys.path so the scripts' own `from utils import ...`
    # resolves when imported via spec_from_file_location.
    backend_dir = _SCRIPTS_DIR.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    spec = importlib.util.spec_from_file_location(f"_{name}_under_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def addr_mod():
    return _load("build_address_points")


@pytest.fixture
def inter_mod():
    return _load("build_intersections")


# ---------------------------------------------------------------------------
# build_address_points
# ---------------------------------------------------------------------------

class TestExtractCoords:
    def test_node_with_lat_lon(self, addr_mod):
        el = {"lat": 41.9, "lon": -87.65}
        assert addr_mod._extract_coords(el) == (41.9, -87.65)

    def test_way_with_center(self, addr_mod):
        el = {"center": {"lat": 41.9, "lon": -87.65}}
        assert addr_mod._extract_coords(el) == (41.9, -87.65)

    def test_no_coords_returns_none(self, addr_mod):
        assert addr_mod._extract_coords({"tags": {}}) is None


class TestQuantizeCoord:
    def test_five_decimal_quantization(self, addr_mod):
        lat_q, lon_q = addr_mod.quantize_coord(41.9, -87.65)
        assert lat_q == 4190000
        assert lon_q == -8765000

    def test_near_neighbors_same_bucket_within_1m(self, addr_mod):
        # 0.0000005 deg lat ~ 0.055 m -> rounds to same int
        a = addr_mod.quantize_coord(41.9000000, -87.6500000)
        b = addr_mod.quantize_coord(41.9000004, -87.6500004)
        assert a == b


class TestChunkBboxes:
    def test_grid_one_returns_single_bbox(self, addr_mod):
        out = addr_mod._chunk_bboxes(0.0, 0.0, 1.0, 1.0, 1)
        assert out == [(0.0, 0.0, 1.0, 1.0)]

    def test_grid_two_returns_four_quadrants(self, addr_mod):
        out = addr_mod._chunk_bboxes(0.0, 0.0, 1.0, 1.0, 2)
        assert len(out) == 4
        # Each sub-bbox is 0.5 x 0.5
        for s, w, n, e in out:
            assert n - s == pytest.approx(0.5)
            assert e - w == pytest.approx(0.5)

    def test_main_plus_corridor_query_set(self, addr_mod):
        bboxes = addr_mod._build_query_bboxes(grid=4)
        assert len(bboxes) == 17  # 16 main chunks + 1 corridor query


class TestNormalizeElements:
    def test_skips_missing_tags(self, addr_mod):
        elements = [
            {"lat": 41.9, "lon": -87.65, "tags": {}},  # no addr tags
            {"lat": 41.9, "lon": -87.65, "tags": {"addr:housenumber": "1234"}},  # missing street
            {"lat": 41.9, "lon": -87.65, "tags": {"addr:street": "N Clark St"}},  # missing house
        ]
        assert addr_mod.normalize_elements(elements) == []

    def test_skips_missing_coords(self, addr_mod):
        el = {"tags": {"addr:housenumber": "1234", "addr:street": "N Clark St"}}
        assert addr_mod.normalize_elements([el]) == []

    def test_basic_row_shape(self, addr_mod):
        el = {
            "lat": 41.9, "lon": -87.65,
            "tags": {"addr:housenumber": "1234", "addr:street": "N Clark St"},
        }
        rows = addr_mod.normalize_elements([el])
        assert rows == [{
            "normalized": "1234 clark",
            "raw": "1234 N Clark St",
            "lat": 41.9,
            "lon": -87.65,
        }]

    def test_dedupes_same_normalized_and_quantized_coord(self, addr_mod):
        el1 = {
            "lat": 41.9000000, "lon": -87.6500000,
            "tags": {"addr:housenumber": "1234", "addr:street": "N Clark St"},
        }
        el2 = {
            "lat": 41.9000004, "lon": -87.6500004,  # < 1m apart
            "tags": {"addr:housenumber": "1234", "addr:street": "N Clark St"},
        }
        rows = addr_mod.normalize_elements([el1, el2])
        assert len(rows) == 1

    def test_keeps_different_units_at_same_coord(self, addr_mod):
        # Different house numbers at the same coord (apartment building entrance) -> two rows.
        el1 = {
            "lat": 41.9, "lon": -87.65,
            "tags": {"addr:housenumber": "1234", "addr:street": "N Clark St"},
        }
        el2 = {
            "lat": 41.9, "lon": -87.65,
            "tags": {"addr:housenumber": "1236", "addr:street": "N Clark St"},
        }
        rows = addr_mod.normalize_elements([el1, el2])
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# build_intersections
# ---------------------------------------------------------------------------

class TestBuildLinestrings:
    def test_skips_missing_name(self, inter_mod):
        el = {"geometry": [{"lat": 0, "lon": 0}, {"lat": 0, "lon": 1}], "tags": {}}
        lines, canon, raw = inter_mod._build_linestrings([el])
        assert lines == [] and canon == [] and raw == []

    def test_skips_missing_geometry(self, inter_mod):
        el = {"geometry": [], "tags": {"name": "N Clark St"}}
        lines, canon, raw = inter_mod._build_linestrings([el])
        assert lines == [] and canon == [] and raw == []

    def test_canonicalizes_name(self, inter_mod):
        el = {
            "tags": {"name": "N Clark St"},
            "geometry": [{"lat": 0, "lon": 0}, {"lat": 0, "lon": 1}],
        }
        lines, canon, raw = inter_mod._build_linestrings([el])
        assert canon == ["clark"]
        assert raw == ["N Clark St"]
        assert len(lines) == 1


class TestFindIntersections:
    def test_two_named_streets_crossing_produce_one_row(self, inter_mod):
        from shapely.geometry import LineString
        # Clark runs N-S along lon=0; Milwaukee runs E-W along lat=0. They cross at (0, 0).
        clark = LineString([(0.0, -1.0), (0.0, 1.0)])
        milwaukee = LineString([(-1.0, 0.0), (1.0, 0.0)])
        rows = inter_mod._find_intersections(
            [clark, milwaukee],
            ["clark", "milwaukee"],
            ["N Clark St", "W Milwaukee Ave"],
        )
        assert len(rows) == 1
        r = rows[0]
        # Canonical names ordered alphabetically.
        assert r["name_a"] == "clark"
        assert r["name_b"] == "milwaukee"
        assert r["raw_a"] == "N Clark St"
        assert r["raw_b"] == "W Milwaukee Ave"
        assert r["lat"] == 0.0 and r["lon"] == 0.0

    def test_same_canonical_name_does_not_self_intersect(self, inter_mod):
        from shapely.geometry import LineString
        # Two segments of "Clark" — should NOT register as an intersection
        # even if their bboxes overlap.
        a = LineString([(0.0, 0.0), (0.0, 1.0)])
        b = LineString([(0.0, 0.5), (0.0, 1.5)])
        rows = inter_mod._find_intersections(
            [a, b], ["clark", "clark"], ["N Clark St", "N Clark St"],
        )
        assert rows == []

    def test_two_intersection_points_same_pair_produces_two_rows(self, inter_mod):
        from shapely.geometry import LineString
        # A "T" street that wraps around and crosses Milwaukee twice.
        t = LineString([(-1.0, 0.0), (1.0, 0.0), (1.0, 1.0), (-1.0, 1.0)])
        m1 = LineString([(0.0, -0.5), (0.0, 0.5)])   # crosses t at (0, 0)
        m2 = LineString([(0.0, 0.5), (0.0, 1.5)])    # crosses t at (0, 1)
        rows = inter_mod._find_intersections(
            [t, m1, m2],
            ["broadway", "milwaukee", "milwaukee"],
            ["N Broadway", "W Milwaukee Ave", "W Milwaukee Ave"],
        )
        # Pair (broadway, milwaukee) should produce two intersection rows.
        broadway_milwaukee = [r for r in rows
                              if {r["name_a"], r["name_b"]} == {"broadway", "milwaukee"}]
        assert len(broadway_milwaukee) == 2
