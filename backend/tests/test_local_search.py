"""
Tests for backend/local_search.py.

These tests hit the real chicago_geocode.db artifact under backend/static_data/.
If that file is missing (e.g. a fresh clone before the ingest scripts run),
the SQLite-dependent tests are skipped rather than failing — the in-memory
neighborhood + cross-street tests still exercise the autocomplete cascade.
"""

from __future__ import annotations

import pytest

import local_search
from local_search import (
    Suggestion,
    autocomplete,
    forward,
    nearest_address,
    parse_cross_street,
)


DB_PRESENT = local_search.DB_PATH.exists()
needs_db = pytest.mark.skipif(
    not DB_PRESENT,
    reason="chicago_geocode.db not built; run backend/scripts/build_*.py first",
)


@pytest.fixture(autouse=True)
def _reset_indexes():
    # Each test should start with a clean in-memory + DB connection cache so
    # one test's `_load_stops` exception/skip doesn't poison the next.
    local_search._reset_in_mem_for_test()
    local_search._reset_db_for_test()
    yield
    local_search._reset_in_mem_for_test()
    local_search._reset_db_for_test()


# ── Cross-street parser ─────────────────────────────────────────────────────

class TestParseCrossStreet:
    def test_and(self):
        assert parse_cross_street("Clark and Belmont") == ("clark", "belmont")

    def test_ampersand(self):
        assert parse_cross_street("Clark & Belmont") == ("clark", "belmont")

    def test_slash(self):
        assert parse_cross_street("Clark/Belmont") == ("clark", "belmont")

    def test_at(self):
        assert parse_cross_street("Clark at Belmont") == ("clark", "belmont")

    def test_x(self):
        assert parse_cross_street("Clark x Belmont") == ("clark", "belmont")

    def test_intersection_of(self):
        assert parse_cross_street("intersection of Clark and Belmont") == ("clark", "belmont")

    def test_corner_of(self):
        assert parse_cross_street("corner of Clark and Belmont") == ("clark", "belmont")

    def test_the_corner_of(self):
        assert parse_cross_street("the corner of Clark and Belmont") == ("clark", "belmont")

    def test_directionals_stripped(self):
        assert parse_cross_street("N Clark St and W Belmont Ave") == ("clark", "belmont")

    def test_not_a_cross_street(self):
        assert parse_cross_street("Wrigleyville") is None
        assert parse_cross_street("1234 N Clark") is None
        assert parse_cross_street("") is None
        assert parse_cross_street("   ") is None

    def test_same_name_rejected(self):
        # "Clark and Clark" isn't a real intersection.
        assert parse_cross_street("Clark and Clark") is None


# ── Neighborhoods (no DB needed) ────────────────────────────────────────────

class TestNeighborhoodAutocomplete:
    def test_exact_match(self):
        s = autocomplete("Wrigleyville", limit=3)
        assert s, "expected at least one suggestion"
        # Top suggestion may be train_station ("Addison" etc.) or neighborhood;
        # what we care about is that the neighborhood entry shows up somewhere.
        sources = [x.source for x in s]
        labels = [x.label.lower() for x in s]
        assert "neighborhood" in sources or any("wrigley" in lb for lb in labels)

    def test_prefix_match(self):
        s = autocomplete("wrigle", limit=5)
        labels = [x.label.lower() for x in s]
        assert any("wrigley" in lb for lb in labels)

    def test_empty_query(self):
        assert autocomplete("", limit=5) == []
        assert autocomplete("   ", limit=5) == []


# ── Decision-8 per-tier cap ─────────────────────────────────────────────────

class TestPerTierCap:
    def test_per_tier_cap_default_three(self):
        # The 'b' prefix matches many bus stops and neighborhoods. With the
        # default cap of 3 per tier, no single tier should dominate the
        # 8-result list — at most 3 entries should share any one source.
        s = autocomplete("b", limit=8)
        from collections import Counter
        per_tier = Counter(x.source for x in s)
        for src, count in per_tier.items():
            assert count <= 3, f"tier {src} returned {count} entries, exceeds cap"

    def test_per_tier_cap_overrideable(self):
        s = autocomplete("b", limit=10, per_tier_cap=5)
        from collections import Counter
        per_tier = Counter(x.source for x in s)
        for src, count in per_tier.items():
            assert count <= 5, f"tier {src} returned {count} entries, exceeds overridden cap"


# ── DB-backed tests ─────────────────────────────────────────────────────────

@needs_db
class TestCrossStreetLookup:
    @pytest.mark.parametrize("query, expected_token", [
        ("Clark and Belmont",            "belmont"),
        ("Clark & Belmont",              "belmont"),
        ("Clark/Belmont",                "belmont"),
        ("clark at belmont",             "belmont"),
        ("N Clark St and W Belmont Ave", "belmont"),
        ("Halsted and Fullerton",        "fullerton"),
        ("State and Madison",            "madison"),
    ])
    def test_famous_intersections(self, query, expected_token):
        s = autocomplete(query, limit=3)
        assert s, f"no suggestion for {query!r}"
        # Some queries (e.g. "Clark and Belmont") collide with a train-station
        # name ("Belmont"); train_station outranks intersection per the tier
        # order. Either is acceptable; the intersection must appear somewhere
        # in the top suggestions.
        inter = [x for x in s if x.source == "intersection"]
        assert inter, f"no intersection result for {query!r} (got {[x.source for x in s]})"
        assert expected_token.lower() in inter[0].label.lower()


@needs_db
class TestAddressLookup:
    @pytest.mark.parametrize("query, expected_prefix", [
        ("1060 W Addison St",     "1060"),
        ("233 S Wacker Dr",       "233"),
        ("875 N Michigan Ave",    "875"),
        ("22 W Washington",       "22"),
    ])
    def test_famous_addresses(self, query, expected_prefix):
        s = autocomplete(query, limit=3)
        assert s, f"no suggestion for {query!r}"
        addresses = [x for x in s if x.source == "address"]
        assert addresses, f"no address suggestion for {query!r} (got {[x.source for x in s]})"
        assert addresses[0].label.startswith(expected_prefix)

    def test_partial_house_number(self):
        s = autocomplete("1060 W Addi", limit=5)
        addr = [x for x in s if x.source == "address"]
        assert addr


@needs_db
class TestForward:
    def test_returns_coords_for_neighborhood(self):
        coords = forward("Wrigleyville")
        assert coords is not None
        lat, lon = coords
        # Wrigleyville is around (41.9476, -87.6553).
        assert 41.93 < lat < 41.96
        assert -87.67 < lon < -87.64

    def test_returns_coords_for_intersection(self):
        coords = forward("Clark and Belmont")
        assert coords is not None
        lat, lon = coords
        # Clark & Belmont is around (41.9395, -87.6531).
        assert 41.93 < lat < 41.95
        assert -87.66 < lon < -87.64

    def test_returns_none_on_miss(self):
        assert forward("zzz_nonexistent_xyzzy_quux") is None


@needs_db
class TestNearestAddress:
    def test_finds_nearby(self):
        # Right on top of 1060 W Addison St per the spot-check earlier.
        # 80m radius is enough to absorb minor coord noise in the OSM corpus.
        result = nearest_address(41.94773, -87.656596, radius_m=80.0)
        assert result is not None
        assert "Addison" in result["raw"]
        assert result["distance_miles"] < 0.05

    def test_returns_none_when_far(self):
        # Coords way outside Chicago should return nothing.
        assert nearest_address(45.0, -85.0, radius_m=80.0) is None


@needs_db
class TestDedupe:
    def test_intersection_label_deduped(self):
        # OSM splits busy intersections into 2–4 graph nodes a few meters
        # apart. The autocomplete list should show each crossroads only once.
        for query in ("halsted", "michigan"):
            s = autocomplete(query, limit=8)
            inter_labels = [x.label.lower() for x in s if x.source == "intersection"]
            assert len(inter_labels) == len(set(inter_labels)), (
                f"duplicate intersection labels for {query!r}: {inter_labels}"
            )


@needs_db
class TestTierOrdering:
    def test_train_station_outranks_lower_tiers_when_present(self):
        # "Belmont" is a train station, an intersection ingredient, and a
        # street name on many bus stops. The top suggestion should be the
        # Belmont train station per the tier order.
        s = autocomplete("Belmont", limit=8)
        assert s
        assert s[0].source == "train_station"

    def test_neighborhood_appears_for_neighborhood_query(self):
        # "Logan Square" — both a real neighborhood and a famous intersection
        # area. The neighborhood entry must appear; tier ordering puts it
        # ahead of intersection rows.
        s = autocomplete("Logan Square", limit=5)
        assert s
        sources = [x.source for x in s]
        assert "neighborhood" in sources
        # And it should outrank any intersection match.
        if "intersection" in sources:
            assert sources.index("neighborhood") < sources.index("intersection")


@needs_db
class TestInBboxOnly:
    def test_in_bbox_filter_drops_outliers(self):
        # The 'in_bbox_only' default is True. All address results must lie
        # inside the canonical Chicago bbox.
        s = autocomplete("100 W Madison", limit=8)
        for x in s:
            assert local_search.chicago_bbox_contains(x.lat, x.lon), (
                f"out-of-bbox suggestion leaked: {x}"
            )
