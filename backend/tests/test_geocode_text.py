"""
Unit tests for backend/geocode_text.py.

Covers the two normalization families and the parameterized fuzzy matcher:
  - normalize_street_name  — corpus canonicalization (strips directionals + suffixes)
  - normalize_address      — corpus canonicalization for full addresses
  - fuzzy_match_neighborhood(query, coords) — pure parameterized matcher

The lru_cache'd, NEIGHBORHOOD_COORDS-bound wrapper in gtfs_loader is tested
separately in test_gtfs_loader.py (TestFuzzyMatchNeighborhood). Tests here
use an inline fixture dict so they don't depend on the curated corpus.
"""

import pytest

from geocode_text import (
    normalize_street_name,
    normalize_address,
    fuzzy_match_neighborhood,
)


# ---------------------------------------------------------------------------
# normalize_street_name
# ---------------------------------------------------------------------------

class TestNormalizeStreetName:
    """Reduces a raw street name to a search-canonical token sequence by
    stripping leading directionals and trailing street-type suffixes."""

    def test_strips_leading_directional_and_trailing_suffix(self):
        assert normalize_street_name("N Clark St") == "clark"

    def test_strips_ave_suffix(self):
        assert normalize_street_name("S Michigan Ave") == "michigan"

    def test_strips_pkwy_suffix(self):
        assert normalize_street_name("W Diversey Pkwy") == "diversey"

    def test_preserves_multi_word_street_after_stripping_suffix(self):
        assert normalize_street_name("Lake Shore Dr") == "lake shore"

    def test_lowercases(self):
        assert normalize_street_name("MICHIGAN AVENUE") == "michigan"

    def test_collapses_internal_whitespace(self):
        assert normalize_street_name("Lake   Shore    Drive") == "lake shore"

    def test_strips_punctuation(self):
        assert normalize_street_name("O'Brien St.") == "o brien"

    def test_empty_string_returns_empty(self):
        assert normalize_street_name("") == ""

    def test_single_token_directional_not_stripped(self):
        # "North" alone (no other tokens) should not be stripped to empty.
        assert normalize_street_name("North") == "north"

    def test_single_token_suffix_not_stripped(self):
        # "Street" alone (no other tokens) should not be stripped to empty.
        assert normalize_street_name("Street") == "street"

    def test_compound_directional(self):
        assert normalize_street_name("NW Highland Ave") == "highland"


# ---------------------------------------------------------------------------
# normalize_address
# ---------------------------------------------------------------------------

class TestNormalizeAddress:
    """Normalizes a full street address, preserving the house number as the
    first token so prefix-search by number works."""

    def test_preserves_house_number(self):
        assert normalize_address("1234 N Clark St") == "1234 clark"

    def test_no_suffix(self):
        assert normalize_address("22 W Washington") == "22 washington"

    def test_lowercases_full_address(self):
        assert normalize_address("5000 N LAKE SHORE DR") == "5000 lake shore"

    def test_handles_no_house_number(self):
        assert normalize_address("N Clark St") == "clark"

    def test_strips_punctuation_in_address(self):
        assert normalize_address("1234 N. Clark St.") == "1234 clark"

    def test_empty_string_returns_empty(self):
        assert normalize_address("") == ""

    def test_collapses_whitespace(self):
        assert normalize_address("1234    N   Clark   St") == "1234 clark"

    def test_alphanumeric_house_number_preserved(self):
        # "1234A N Clark St" — house token starts with a digit, full token kept.
        assert normalize_address("1234A N Clark St") == "1234a clark"


# ---------------------------------------------------------------------------
# fuzzy_match_neighborhood (parameterized form)
# ---------------------------------------------------------------------------

@pytest.fixture
def coords_fixture():
    """Small fixed coords dict used across fuzzy tests.

    Module-level so the inverted-index cache (keyed by id) hits across tests
    rather than rebuilding each time."""
    return {
        "wrigleyville": (41.948, -87.656),
        "lincoln park": (41.921, -87.649),
        "the loop": (41.881, -87.629),
        "chicago art museum": (41.880, -87.624),
        "chicago history museum": (41.911, -87.629),
    }


class TestFuzzyMatchNeighborhood:
    """Parameterized matcher: takes (query, coords) and returns the best
    match >= 0.95 similarity with at least one shared meaningful word for
    multi-word queries."""

    def test_exact_match_returns_coords_and_key(self, coords_fixture):
        coords, key = fuzzy_match_neighborhood("wrigleyville", coords_fixture)
        assert coords == (41.948, -87.656)
        assert key == "wrigleyville"

    def test_typo_within_threshold_matches(self, coords_fixture):
        # One-char typo on a 12-char word -> ratio well above 0.95
        coords, key = fuzzy_match_neighborhood("wrigleyvile", coords_fixture)
        assert coords == (41.948, -87.656)
        assert key == "wrigleyville"

    def test_no_match_returns_none_pair(self, coords_fixture):
        coords, key = fuzzy_match_neighborhood("xyzabc99999nonexistent", coords_fixture)
        assert coords is None
        assert key is None

    def test_stop_words_only_query_does_not_break(self, coords_fixture):
        # "the loop" has a stop word + a meaningful word — matches by exact.
        coords, _ = fuzzy_match_neighborhood("the loop", coords_fixture)
        assert coords == (41.881, -87.629)

    def test_multiword_requires_shared_meaningful_word(self, coords_fixture):
        # "chicago art museum" must NOT match "chicago history museum" — they
        # share only stop words ("chicago") + the structural word "museum".
        # The shared word filter passes ("art" doesn't appear in any other
        # key, "museum" appears in both), so the candidate set includes
        # "chicago history museum". But ratio() between
        # "chicago art museum" and "chicago history museum" is < 0.95.
        coords, key = fuzzy_match_neighborhood("chicago art museum", coords_fixture)
        assert coords == (41.880, -87.624)
        assert key == "chicago art museum"

    def test_multiword_with_no_shared_meaningful_word_returns_none(self, coords_fixture):
        # "rogers park" shares no meaningful word with any fixture entry.
        coords, key = fuzzy_match_neighborhood("rogers park", coords_fixture)
        assert coords is None
        assert key is None

    def test_below_threshold_returns_none(self, coords_fixture):
        # "wrigle" is 6 chars vs "wrigleyville" 12 — ratio is well below 0.95.
        coords, key = fuzzy_match_neighborhood("wrigle", coords_fixture)
        assert coords is None
        assert key is None
