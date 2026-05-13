"""
Pre-loaded (lat, lon) coordinates for well-known CTA stations and a handful
of bus-corridor anchors. Used by the golden-route accuracy scaffold so test
authors do not have to hand-type lat/lon for canonical stops.

All coordinates are pulled from `backend/gtfs_data/stops.txt` (location_type=1
rows for L stations; specific stop_ids called out where bus pairs are used).
If the bundled GTFS feed is refreshed, spot-check that the names below still
exist before relying on a constant — agency stop_ids occasionally drift.

# Usage from a golden fixture
# ---------------------------
#     from .known_stops import KNOWN_STOPS
#
#     scenario = RoutingScenario(
#         frozen_at=WEEKDAY_MIDDAY,
#         origin=KNOWN_STOPS["LOGAN_SQUARE_BLUE"],
#         dest=KNOWN_STOPS["GARFIELD_RED"],
#         description="Logan Square → Garfield (Red): expect Blue→Red transfer",
#     )
#
# Pick stations by their rider-name, not their stop_id. The dict keys are
# stable; the upstream stop_id is not.
#
# What this file is NOT
# ---------------------
# This is NOT a fixture catalog. It is a coordinate lookup. The judgment
# call about which OD pair encodes a meaningful "the engine should pick
# X over Y" assertion still belongs to a human author with Chicago rider
# knowledge — see the module docstring of `test_routing_accuracy.py`.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# CTA L stations — (lat, lon) from gtfs_data/stops.txt parent stations
# ---------------------------------------------------------------------------

KNOWN_STOPS: dict[str, tuple[float, float]] = {
    # ----- Red Line (north → south) -----
    "HOWARD": (42.019063, -87.672892),
    "LOYOLA": (42.001073, -87.661061),
    "BRYN_MAWR": (41.983504, -87.658840),
    "ADDISON_RED": (41.947316, -87.653624),
    "BELMONT_RED": (41.939751, -87.653380),  # Red/Brown/Purple
    "FULLERTON": (41.925300, -87.652868),
    "CHICAGO_RED": (41.896671, -87.628176),
    "GRAND_RED": (41.891665, -87.628021),
    "LAKE_SUBWAY": (41.884809, -87.627813),
    "MONROE_RED": (41.880745, -87.627696),
    "JACKSON_RED": (41.878153, -87.627596),
    "HARRISON": (41.874039, -87.627479),
    "ROOSEVELT": (41.867379, -87.627031),
    "CERMAK_CHINATOWN": (41.853206, -87.630968),
    "SOX_35TH": (41.831191, -87.630636),
    "GARFIELD_RED": (41.795420, -87.631157),
    "63RD_RED": (41.780536, -87.630952),
    "95TH_DAN_RYAN": (41.722377, -87.624342),

    # ----- Blue Line (O'Hare → Forest Park) -----
    "OHARE": (41.977665, -87.904223),
    "ROSEMONT": (41.983507, -87.859388),
    "JEFFERSON_PARK": (41.970234, -87.761594),
    "MONTROSE_BLUE": (41.960901, -87.742903),
    "ADDISON_BLUE": (41.946604, -87.718458),
    "BELMONT_BLUE": (41.939111, -87.712252),
    "LOGAN_SQUARE_BLUE": (41.929534, -87.707688),
    "CALIFORNIA_BLUE": (41.922158, -87.697244),
    "DAMEN_BLUE": (41.909845, -87.677540),
    "DIVISION_BLUE": (41.903355, -87.666496),
    "CHICAGO_BLUE": (41.896075, -87.655214),
    "GRAND_BLUE": (41.891189, -87.647578),
    "CLARK_LAKE": (41.885737, -87.630886),  # Blue/Brown/Green/Orange/Pink/Purple
    "MONROE_BLUE": (41.880703, -87.629378),
    "JACKSON_BLUE": (41.878183, -87.629296),
    "FOREST_PARK": (41.874257, -87.817318),

    # ----- Brown Line (notable) -----
    "KIMBALL": (41.967901, -87.713065),
    "WESTERN_BROWN": (41.966163, -87.688502),
    "ADDISON_BROWN": (41.947028, -87.674642),
    "DIVERSEY": (41.932732, -87.653131),
    "ARMITAGE": (41.918217, -87.652644),
    "MERCHANDISE_MART": (41.888969, -87.633924),

    # ----- Green Line (notable) -----
    "HARLEM_LAKE": (41.886848, -87.803176),
    "OAK_PARK_GREEN": (41.886988, -87.793783),
    "ASHLAND_LAKE": (41.885269, -87.666969),
    "MORGAN": (41.885577, -87.652130),
    "47TH_GREEN": (41.809209, -87.618826),
    "51ST_GREEN": (41.802090, -87.618487),  # nearest L to Hyde Park
    "GARFIELD_GREEN": (41.795172, -87.618327),
    "ASHLAND_63RD": (41.778860, -87.663766),
    "HALSTED_GREEN": (41.778943, -87.644244),
    "COTTAGE_GROVE": (41.780309, -87.605857),

    # ----- Orange / Pink / Yellow / Purple endpoints -----
    "MIDWAY": (41.786610, -87.737875),
    "54TH_CERMAK": (41.851773, -87.756692),  # Pink terminus
    "DEMPSTER_SKOKIE": (42.038951, -87.751919),  # Yellow terminus
    "LINDEN": (42.073153, -87.690730),  # Purple terminus

    # ----- Loop transfer points (Inner Loop) -----
    "ADAMS_WABASH": (41.879507, -87.626037),
    "WASHINGTON_WABASH": (41.883220, -87.626189),
    "WASHINGTON_WELLS": (41.882695, -87.633780),
    "LASALLE_VAN_BUREN": (41.876800, -87.631739),
    "QUINCY": (41.878723, -87.633740),
    "HAROLD_WASHINGTON_LIBRARY": (41.876862, -87.628196),
}


# Bus-corridor and walk-only fixtures
# -----------------------------------
# No anchor constants are provided for these. The "right" point for a
# bus-only or walk-only fixture is a judgment call (which side of which
# street, which block), and inventing approximate neighborhood centroids
# would defeat the point of having authoritative coordinates here. Pin
# specific bus stop_ids from `gtfs_data/stops.txt` directly in the test,
# or use Google Maps right-click → "What's here?" for a non-stop anchor
# and paste the lat/lon into the test alongside a comment naming the
# rider-level intent.
