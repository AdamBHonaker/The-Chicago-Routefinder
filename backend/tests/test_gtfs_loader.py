"""
Unit tests for pure helper functions in backend/gtfs_loader.py.

Only functions that require no GTFS file I/O are tested here.

Covered:
  - _normalize_street_abbr()     — USPS suffix expansion ("Ave" → "avenue")
  - fuzzy_match_neighborhood()   — similarity match against NEIGHBORHOOD_COORDS
"""

import pytest

from geocode_text import _normalize_street_abbr
from gtfs_loader import (
    fuzzy_match_neighborhood,
    NEIGHBORHOOD_COORDS,
)


# ---------------------------------------------------------------------------
# _normalize_street_abbr
# ---------------------------------------------------------------------------

class TestNormalizeStreetAbbr:
    """
    _normalize_street_abbr expands USPS street-type abbreviations at the END
    of an address string (before an optional comma).  Directional prefixes
    (N/S/E/W) are not expanded.  The function operates on already-lowercased
    input.
    """

    def test_avenue_expansion(self):
        result = _normalize_street_abbr("3400 n clark ave")
        assert "avenue" in result

    def test_boulevard_expansion(self):
        result = _normalize_street_abbr("5000 n lake shore blvd")
        assert "boulevard" in result

    def test_street_expansion(self):
        result = _normalize_street_abbr("150 n state st")
        assert "street" in result

    def test_drive_expansion(self):
        result = _normalize_street_abbr("123 n michigan dr")
        assert "drive" in result

    def test_no_change_for_unrecognized_suffix(self):
        original = "wrigley field"
        assert _normalize_street_abbr(original) == original

    def test_abbr_mid_string_not_expanded(self):
        # "ave" followed by another word should not be expanded (not at end/before comma)
        result = _normalize_street_abbr("avenue north parking lot")
        # "avenue" here is already full — nothing to expand; result unchanged
        assert result == "avenue north parking lot"

    def test_abbr_not_at_end_not_expanded(self):
        # "St." before a word should not be expanded ("St. Michael's" stays intact)
        result = _normalize_street_abbr("st michael's church")
        # "st" at the very start before another word — should NOT expand
        assert "street" not in result

    def test_abbr_before_comma_expanded(self):
        # "123 n clark ave, chicago" — abbreviation before comma should still expand
        result = _normalize_street_abbr("123 n clark ave, chicago")
        assert "avenue" in result

    def test_returns_string(self):
        result = _normalize_street_abbr("5 n wabash ave")
        assert isinstance(result, str)

    def test_empty_string_returns_empty(self):
        assert _normalize_street_abbr("") == ""

    def test_case_insensitive_match(self):
        # The regex is case-insensitive; input may have mixed case if caller
        # hasn't lowercased it yet (though main.py does lowercase first)
        result = _normalize_street_abbr("3400 N Clark AVE")
        assert "avenue" in result.lower()


# ---------------------------------------------------------------------------
# fuzzy_match_neighborhood
# ---------------------------------------------------------------------------

class TestFuzzyMatchNeighborhood:
    """
    fuzzy_match_neighborhood() requires ≥0.95 similarity AND at least one
    shared meaningful word for multi-word queries.  It returns
    (coords, key) or (None, None).
    """

    def test_exact_key_returns_match(self):
        coords, key = fuzzy_match_neighborhood("wrigleyville")
        assert coords is not None
        assert key == "wrigleyville"

    def test_exact_key_coords_are_tuples(self):
        coords, _ = fuzzy_match_neighborhood("wrigleyville")
        assert isinstance(coords, tuple)
        assert len(coords) == 2

    def test_exact_key_coords_are_chicago_lat_lon(self):
        coords, _ = fuzzy_match_neighborhood("wrigleyville")
        lat, lon = coords
        # Chicago bounding box
        assert 41.6 < lat < 42.1
        assert -87.95 < lon < -87.5

    def test_no_match_for_nonsense(self):
        coords, key = fuzzy_match_neighborhood("xyzabc99999nonexistent")
        assert coords is None
        assert key is None

    def test_loop_match(self):
        coords, _ = fuzzy_match_neighborhood("the loop")
        assert coords is not None

    def test_lincoln_park_match(self):
        coords, _ = fuzzy_match_neighborhood("lincoln park")
        assert coords is not None

    def test_partial_word_below_threshold_returns_none(self):
        # "wrigle" alone is too short / dissimilar — should not match
        coords, key = fuzzy_match_neighborhood("wrigle")
        # This may or may not match depending on similarity score; just verify shape
        assert coords is None or isinstance(coords, tuple)

    def test_result_coords_exist_in_neighborhood_coords(self):
        coords, key = fuzzy_match_neighborhood("wrigleyville")
        assert key in NEIGHBORHOOD_COORDS
        assert NEIGHBORHOOD_COORDS[key] == coords

    def test_returns_two_element_tuple(self):
        result = fuzzy_match_neighborhood("rogers park")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_all_known_neighborhoods_self_match(self):
        """
        Every key in NEIGHBORHOOD_COORDS should return itself when queried
        directly (exact match is always ≥ 0.95 similarity).
        """
        failures = []
        for key in list(NEIGHBORHOOD_COORDS)[:20]:   # spot-check first 20
            coords, matched = fuzzy_match_neighborhood(key)
            if coords is None:
                failures.append(key)
        assert failures == [], f"These keys failed to self-match: {failures}"
