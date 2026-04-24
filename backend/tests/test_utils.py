"""
Unit tests for backend/utils.py

Covers:
  - haversine_miles(): symmetry, zero distance, known distance, direction
  - SpatialGrid: add, query, cell_count, radius filtering
"""

import math
import pytest

from utils import haversine_miles, SpatialGrid


# ---------------------------------------------------------------------------
# haversine_miles
# ---------------------------------------------------------------------------

class TestHaversineMiles:
    def test_same_point_is_zero(self):
        assert haversine_miles(41.88, -87.63, 41.88, -87.63) == 0.0

    def test_symmetry(self):
        d1 = haversine_miles(41.88, -87.63, 41.90, -87.65)
        d2 = haversine_miles(41.90, -87.65, 41.88, -87.63)
        assert abs(d1 - d2) < 1e-10

    def test_returns_positive(self):
        d = haversine_miles(41.88, -87.63, 42.00, -87.70)
        assert d > 0.0

    def test_one_degree_lat_is_about_69_miles(self):
        # 1 degree of latitude ≈ 69 miles everywhere on Earth
        d = haversine_miles(40.0, -87.63, 41.0, -87.63)
        assert 68.0 < d < 70.0

    def test_one_sixty_ninth_degree_lat_is_about_one_mile(self):
        d = haversine_miles(41.88, -87.63, 41.88 + 1 / 69.0, -87.63)
        assert 0.95 < d < 1.05

    def test_wrigleyville_to_loop_roughly_four_miles(self):
        # Wrigleyville → the Loop — roughly 4.5–5.0 miles as the crow flies
        d = haversine_miles(41.9476, -87.6542, 41.8827, -87.6326)
        assert 4.0 < d < 5.5

    def test_triangle_inequality(self):
        # Distance A→C ≤ A→B + B→C
        a = (41.88, -87.63)
        b = (41.90, -87.65)
        c = (41.92, -87.62)
        ab = haversine_miles(*a, *b)
        bc = haversine_miles(*b, *c)
        ac = haversine_miles(*a, *c)
        assert ac <= ab + bc + 1e-9


# ---------------------------------------------------------------------------
# SpatialGrid
# ---------------------------------------------------------------------------

class TestSpatialGrid:
    def _make_grid(self) -> SpatialGrid:
        return SpatialGrid(cell_lat_deg=0.005, cell_lon_deg=0.005)

    def test_empty_grid_returns_no_results(self):
        grid = self._make_grid()
        assert grid.query(41.88, -87.63, 0.5) == []

    def test_add_and_query_finds_entry(self):
        grid = self._make_grid()
        grid.add(41.88, -87.63, "stop_A")
        results = grid.query(41.88, -87.63, 0.1)
        assert len(results) == 1
        assert results[0][1] == "stop_A"

    def test_query_returns_distance_and_value_pair(self):
        grid = self._make_grid()
        grid.add(41.88, -87.63, "stop_A")
        dist, val = grid.query(41.88, -87.63, 0.5)[0]
        assert isinstance(dist, float)
        assert val == "stop_A"

    def test_nearby_stop_included_distant_excluded(self):
        grid = self._make_grid()
        grid.add(41.8801, -87.6301, "near")   # ~0.05 miles from query point
        grid.add(42.00,   -87.70,   "far")    # >10 miles away
        results = grid.query(41.88, -87.63, 0.5)
        values = [r[1] for r in results]
        assert "near" in values
        assert "far" not in values

    def test_multiple_entries_same_cell(self):
        grid = self._make_grid()
        grid.add(41.88, -87.63, "A")
        grid.add(41.88, -87.63, "B")
        results = grid.query(41.88, -87.63, 0.1)
        values = [r[1] for r in results]
        assert "A" in values
        assert "B" in values

    def test_cell_count_single_cell(self):
        grid = self._make_grid()
        # Both points well inside the same 0.005-degree cell
        # Cell for (41.88, -87.63): lat∈[41.880,41.885), lon∈[-87.630,-87.625)
        grid.add(41.88, -87.63, "A")
        grid.add(41.882, -87.628, "B")   # same cell (cell_size=0.005)
        assert grid.cell_count == 1

    def test_cell_count_two_cells(self):
        grid = self._make_grid()
        grid.add(41.88, -87.63, "A")
        grid.add(42.00, -87.70, "B")       # different cell
        assert grid.cell_count == 2

    def test_distance_in_result_is_accurate(self):
        grid = self._make_grid()
        grid.add(41.88, -87.63, "here")
        dist, _ = grid.query(41.88, -87.63, 0.5)[0]
        assert dist == pytest.approx(0.0)

    def test_all_within_radius_returned(self):
        grid = self._make_grid()
        # Add 3 stops all within 0.5 miles
        for i in range(3):
            grid.add(41.88 + i * 0.001, -87.63, f"stop_{i}")
        results = grid.query(41.88, -87.63, 0.5)
        assert len(results) == 3

    def test_radius_boundary_respected(self):
        grid = self._make_grid()
        # 1 degree lat ≈ 69 miles; 0.1 deg ≈ 6.9 miles; 0.005 deg ≈ 0.345 miles
        grid.add(41.88 + 0.008, -87.63, "just_outside")  # ≈0.55 miles
        results = grid.query(41.88, -87.63, 0.5)
        assert len(results) == 0
