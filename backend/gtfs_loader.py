"""
GTFS-based stop resolver for the CTA Transit app.

Loads stops.txt from the downloaded GTFS feed and provides functions
to find the nearest train stations and bus stops to any location.

Stop ID ranges (per CTA GTFS / Train Tracker docs):
  0     – 29999  →  Bus stops
  30000 – 39999  →  Train platform stops (direction-specific)
  40000 – 49999  →  Train parent stations (used by Train Tracker API as mapid)

Stops are loaded once at startup and cached in memory (~1.2 MB).

Geocoding strategy:
  1. Exact match against NEIGHBORHOOD_COORDS (instant, no network)
  2. Fuzzy match against NEIGHBORHOOD_COORDS (instant, no network)
  3. OSM Nominatim geocoding (free, ~200ms, biased to Chicago bounding box)

Geographic scope: Howard St (north) to 50th St (south), lakefront (east) to
Pulaski Rd (west). The Nominatim bounding box still covers the full city so
any Chicago address geocodes, but walk times outside this rectangle fall back
to Haversine estimates and no CTA stops will be found beyond the boundary.

Future: Replace Nominatim (Option A) with Google Maps Geocoding API (Option B)
for higher accuracy on ambiguous/partial addresses and better coverage of new
construction. Google's geocoding API is free up to ~40,000 calls/month then
$5/1,000. Swap out the geocode_nominatim() function in this file and set
GOOGLE_MAPS_API_KEY in backend/.env. No other changes needed.
"""

import csv
import json
import math
import threading
import time
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import requests

from walking import walk_minutes

GTFS_DIR = Path(__file__).parent / "gtfs_data"

# Nominatim bounding box for Chicago (west, south, east, north)
_CHICAGO_BBOX = "-87.94,41.64,-87.52,42.02"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_USER_AGENT = "CTA-Transit-PWA/1.0"

# Persistent geocode cache — survives server restarts
_GEOCODE_CACHE_PATH = Path(__file__).parent / "geocode_cache.json"


def _load_geocode_cache() -> dict[str, tuple[float, float] | None]:
    """Load the geocode cache from disk. Returns an empty dict if not found."""
    if _GEOCODE_CACHE_PATH.exists():
        try:
            raw = json.loads(_GEOCODE_CACHE_PATH.read_text(encoding="utf-8"))
            # JSON stores lists; convert [lat, lon] back to tuples (or None)
            return {k: tuple(v) if v is not None else None for k, v in raw.items()}
        except Exception as exc:
            print(f"[gtfs_loader] Could not load geocode cache: {exc}")
    return {}


def _save_geocode_cache(cache: dict) -> None:
    """Persist the geocode cache to disk."""
    try:
        _GEOCODE_CACHE_PATH.write_text(
            json.dumps(cache, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[gtfs_loader] Could not save geocode cache: {exc}")


# Loaded once at import time; new entries are written through immediately
_geocode_cache: dict[str, tuple[float, float] | None] = _load_geocode_cache()

# Nominatim ToS: max 1 request per second from a single client
_nominatim_lock = threading.Lock()
_nominatim_last_call: float = 0.0


# ---------------------------------------------------------------------------
# Neighborhood / landmark coordinates — fast cache
# Geographic scope: Howard St (north) → 50th St (south) | Lakefront → Pulaski Rd (west)
# Entries outside this rectangle are omitted — they would find no nearby CTA stops.
# ---------------------------------------------------------------------------

NEIGHBORHOOD_COORDS: dict[str, tuple[float, float]] = {

    # ── ROGERS PARK / FAR NORTH ──────────────────────────────────────────────
    "rogers park":          (42.0085, -87.6688),
    "loyola":               (41.9998, -87.6586),
    "loyola university":    (41.9998, -87.6586),
    "granville":            (41.9943, -87.6579),
    "thorndale":            (41.9898, -87.6577),
    "morse":                (41.9832, -87.6590),
    "jarvis":               (41.9930, -87.6693),

    # ── EDGEWATER ────────────────────────────────────────────────────────────
    "edgewater":            (41.9889, -87.6600),
    "bryn mawr":            (41.9834, -87.6590),
    "foster beach":         (41.9791, -87.6403),
    "foster avenue beach":  (41.9791, -87.6403),

    # ── ANDERSONVILLE ────────────────────────────────────────────────────────
    "andersonville":        (41.9800, -87.6682),
    "berwyn":               (41.9778, -87.6593),
    "berwyn station":       (41.9778, -87.6593),
    "swedish american museum": (41.9799, -87.6690),

    # ── UPTOWN ───────────────────────────────────────────────────────────────
    "uptown":               (41.9650, -87.6550),
    "wilson":               (41.9648, -87.6575),
    "lawrence":             (41.9688, -87.6580),
    "argyle":               (41.9735, -87.6580),
    "sheridan":             (41.9542, -87.6537),
    "montrose beach":       (41.9643, -87.6384),
    "montrose harbor":      (41.9643, -87.6384),
    "uptown theatre":       (41.9648, -87.6545),
    "green mill":           (41.9656, -87.6556),
    "illinois masonic":     (41.9437, -87.6561),
    "advocate illinois masonic": (41.9437, -87.6561),

    # ── LINCOLN SQUARE / RAVENSWOOD ──────────────────────────────────────────
    "lincoln square":       (41.9679, -87.6848),
    "ravenswood":           (41.9656, -87.6741),

    # ── WRIGLEYVILLE / LAKEVIEW ──────────────────────────────────────────────
    "wrigleyville":         (41.9476, -87.6553),
    "wrigley field":        (41.9484, -87.6553),
    "lakeview":             (41.9433, -87.6513),
    "east lakeview":        (41.9395, -87.6420),
    "boystown":             (41.9444, -87.6491),
    "addison":              (41.9476, -87.6542),
    "belmont":              (41.9394, -87.6527),
    "southport corridor":   (41.9416, -87.6641),
    "southport":            (41.9416, -87.6641),
    "diversey":             (41.9321, -87.6527),
    "wellington":           (41.9360, -87.6545),
    "paulina":              (41.9437, -87.6705),
    "diversey harbor":      (41.9321, -87.6385),
    "theater on the lake":  (41.9258, -87.6334),

    # ── LINCOLN PARK ─────────────────────────────────────────────────────────
    "lincoln park":         (41.9228, -87.6482),
    "lincoln park zoo":     (41.9220, -87.6332),
    "fullerton":            (41.9253, -87.6527),
    "armitage":             (41.9175, -87.6513),
    "depaul":               (41.9253, -87.6554),
    "depaul university":    (41.9253, -87.6554),
    "north avenue beach":   (41.9168, -87.6354),
    "oz park":              (41.9257, -87.6395),
    "chicago history museum": (41.9218, -87.6318),
    "peggy notebaert nature museum": (41.9218, -87.6341),
    "steppenwolf theatre":  (41.9119, -87.6316),
    "steppenwolf":          (41.9119, -87.6316),

    # ── OLD TOWN ─────────────────────────────────────────────────────────────
    "old town":             (41.9101, -87.6364),
    "sedgwick":             (41.9101, -87.6386),
    "north/clybourn":       (41.9103, -87.6486),
    "north clybourn":       (41.9103, -87.6486),
    "second city":          (41.9101, -87.6356),
    "wells street":         (41.9101, -87.6340),

    # ── GOLD COAST ───────────────────────────────────────────────────────────
    "gold coast":           (41.9016, -87.6298),
    "clark/division":       (41.9046, -87.6312),
    "clark division":       (41.9046, -87.6312),
    "newberry library":     (41.9019, -87.6317),
    "washington square park": (41.9019, -87.6317),
    "lurie childrens hospital": (41.9049, -87.6241),
    "lurie children's hospital": (41.9049, -87.6241),
    "ann & robert h. lurie": (41.9049, -87.6241),
    "chicago water tower":  (41.9007, -87.6235),
    "water tower place":    (41.9007, -87.6235),
    "pumping station":      (41.9007, -87.6233),

    # ── RIVER NORTH ──────────────────────────────────────────────────────────
    "river north":          (41.8944, -87.6333),
    "merchandise mart":     (41.8883, -87.6360),
    "chicago avenue":       (41.8966, -87.6269),
    "chicago station":      (41.8966, -87.6280),
    "gallery district":     (41.8933, -87.6348),

    # ── NEAR NORTH / STREETERVILLE / MAG MILE ────────────────────────────────
    "near north":           (41.8976, -87.6271),
    "streeterville":        (41.8924, -87.6196),
    "magnificent mile":     (41.8951, -87.6249),
    "mag mile":             (41.8951, -87.6249),
    "michigan avenue":      (41.8847, -87.6240),
    "navy pier":            (41.8919, -87.6053),
    "grand":                (41.8912, -87.6276),
    "john hancock":         (41.8988, -87.6232),
    "875 north michigan":   (41.8988, -87.6232),
    "875 n michigan":       (41.8988, -87.6232),
    "northwestern memorial hospital": (41.8951, -87.6218),
    "northwestern memorial": (41.8951, -87.6218),
    "prentice women's hospital": (41.8951, -87.6218),
    "northwestern university chicago": (41.8951, -87.6218),

    # ── THE LOOP ─────────────────────────────────────────────────────────────
    "loop":                 (41.8827, -87.6326),
    "the loop":             (41.8827, -87.6326),
    "downtown":             (41.8827, -87.6326),
    "downtown chicago":     (41.8827, -87.6326),
    "millennium park":      (41.8827, -87.6233),
    "maggie daley park":    (41.8832, -87.6196),
    "grant park":           (41.8757, -87.6189),
    "art institute":            (41.8796, -87.6237),
    "art institute of chicago": (41.8796, -87.6237),
    "chicago art museum":       (41.8796, -87.6237),
    "art museum":               (41.8796, -87.6237),
    "the art institute":        (41.8796, -87.6237),
    "theater district":     (41.8854, -87.6295),
    "chicago theatre":      (41.8854, -87.6295),
    "state street":         (41.8800, -87.6278),
    "union station":        (41.8789, -87.6401),
    "ogilvie":              (41.8821, -87.6416),
    "ogilvie transportation center": (41.8821, -87.6416),
    "lasalle street station": (41.8757, -87.6315),
    "museum campus":        (41.8666, -87.6151),
    "soldier field":        (41.8623, -87.6167),
    "shedd aquarium":       (41.8676, -87.6139),
    "field museum":         (41.8663, -87.6168),
    "adler planetarium":    (41.8664, -87.6069),
    "harold washington library": (41.8762, -87.6286),
    "harold washington library center": (41.8762, -87.6286),
    "chicago cultural center": (41.8838, -87.6248),
    "millennium station":   (41.8844, -87.6244),
    "willis tower":         (41.8789, -87.6359),
    "sears tower":          (41.8789, -87.6359),
    "wrigley building":     (41.8891, -87.6244),
    "tribune tower":        (41.8902, -87.6245),
    "chicago riverwalk":    (41.8876, -87.6291),
    "lyric opera":          (41.8855, -87.6371),
    "auditorium theatre":   (41.8762, -87.6263),
    "chicago symphony orchestra": (41.8796, -87.6263),
    "symphony center":      (41.8796, -87.6263),
    "columbia college":     (41.8723, -87.6247),
    "columbia college chicago": (41.8723, -87.6247),
    "school of the art institute": (41.8796, -87.6237),
    "saic":                 (41.8796, -87.6237),
    "daley plaza":          (41.8840, -87.6318),
    "city hall":            (41.8840, -87.6318),

    # ── SOUTH LOOP / NEAR SOUTH ──────────────────────────────────────────────
    "south loop":           (41.8674, -87.6278),
    "printers row":         (41.8723, -87.6278),
    "printer's row":        (41.8723, -87.6278),
    "chinatown":            (41.8508, -87.6326),
    "armour square":        (41.8500, -87.6350),
    "bridgeport":           (41.8350, -87.6450),
    "canaryville":          (41.8220, -87.6350),
    "fuller park":          (41.8100, -87.6350),

    # ── NEAR WEST SIDE ───────────────────────────────────────────────────────
    "near west side":       (41.8750, -87.6600),
    "greektown":            (41.8775, -87.6475),
    "little italy":         (41.8725, -87.6550),
    "uic":                  (41.8700, -87.6500),
    "university village":   (41.8700, -87.6500),
    "united center":        (41.8806, -87.6742),
    "medical district":     (41.8700, -87.6730),

    # ── WEST TOWN / UKRAINIAN VILLAGE / WICKER PARK ──────────────────────────
    "west town":            (41.9000, -87.6700),
    "ukrainian village":    (41.8950, -87.6800),
    "wicker park":          (41.9090, -87.6800),
    "bucktown":             (41.9190, -87.6800),
    "noble square":         (41.8980, -87.6650),
    "east village":         (41.8980, -87.6750),

    # ── LOGAN SQUARE / HUMBOLDT PARK ─────────────────────────────────────────
    "logan square":         (41.9290, -87.7000),
    "humboldt park":        (41.9000, -87.7200),
    "palmer square":        (41.9230, -87.7000),

    # ── AVONDALE / HERMOSA ───────────────────────────────────────────────────
    # (belmont cragin, montclare, galewood omitted — west of Pulaski)
    "avondale":             (41.9400, -87.7100),
    "hermosa":              (41.9200, -87.7200),

    # ── IRVING PARK / NORTH PARK ─────────────────────────────────────────────
    # (portage park, albany park omitted — west of Pulaski)
    "irving park":          (41.9540, -87.7200),
    "mayfair":              (41.9730, -87.7100),
    "north park":           (41.9800, -87.7200),
    "west ridge":           (41.9990, -87.6950),
    "sauganash":            (41.9900, -87.7200),

    # ── EAST GARFIELD PARK / NORTH LAWNDALE ──────────────────────────────────
    # (west garfield park, austin, dunning, jefferson park,
    #  norwood park, forest glen, edison park omitted — west of Pulaski)
    "east garfield park":   (41.8800, -87.7200),
    "north lawndale":       (41.8650, -87.7200),

    # ── SOUTH LAWNDALE / PILSEN / BACK OF THE YARDS ──────────────────────────
    # (west elsdon, gage park, chicago lawn, west lawn omitted — south of 50th)
    "little village":       (41.8250, -87.7200),
    "south lawndale":       (41.8250, -87.7200),
    "pilsen":               (41.8550, -87.6600),
    "18th street":          (41.8575, -87.6700),
    "back of the yards":    (41.8100, -87.6550),
    "new city":             (41.8100, -87.6550),
    "mckinley park":        (41.8290, -87.6750),
    "brighton park":        (41.8250, -87.6950),
    "archer heights":       (41.8200, -87.7250),

    # ── BRONZEVILLE / DOUGLAS / GRAND BOULEVARD ──────────────────────────────
    # (washington park, u of c, university of chicago omitted — south of 50th)
    "bronzeville":          (41.8350, -87.6150),
    "douglas":              (41.8420, -87.6200),
    "grand boulevard":      (41.8200, -87.6150),
    "sox-35th":             (41.8312, -87.6304),
    "35th street":          (41.8312, -87.6304),

    # ── KENWOOD ──────────────────────────────────────────────────────────────
    # (hyde park, woodlawn, south shore, greater grand crossing omitted — south of 50th)
    "kenwood":              (41.8100, -87.6050),

    # ── KEY CTA STATIONS (within coverage area) ───────────────────────────────
    # (95th/dan ryan, 87th, 79th, 69th, garfield, harlem/lake, cicero omitted
    #  — south of 50th or west of Pulaski)
    "cermak-chinatown":     (41.8534, -87.6306),
    "pulaski":              (41.8866, -87.7260),
    "kedzie":               (41.8864, -87.7063),

    # ── LOOP TRAIN STATIONS (direct CTA name lookups) ────────────────────────
    "lake":                 (41.8849, -87.6278),
    "monroe":               (41.8806, -87.6278),
    "jackson":              (41.8781, -87.6278),
    "harrison":             (41.8742, -87.6278),
    "roosevelt":            (41.8674, -87.6278),
    "clark/lake":           (41.8858, -87.6310),
    "state/lake":           (41.8858, -87.6278),
    "washington/wabash":    (41.8832, -87.6258),
    "washington/wells":     (41.8829, -87.6340),
    "adams/wabash":         (41.8796, -87.6258),
    "quincy":               (41.8784, -87.6340),
    "lasalle/van buren":    (41.8757, -87.6315),
    "clinton":              (41.8749, -87.6408),
}


# ---------------------------------------------------------------------------
# Distance utility
# ---------------------------------------------------------------------------

def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance in miles between two lat/lon points."""
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Nominatim geocoding (Option A)
# Future: swap this function for Google Maps Geocoding API (Option B)
# ---------------------------------------------------------------------------

def geocode_nominatim(query: str) -> tuple[float, float] | None:
    """
    Geocode a free-text address, building name, or intersection to (lat, lon)
    using OSM Nominatim. Results are biased to the Chicago bounding box.

    Returns None on any failure (network error, no result, timeout).

    Rate limit: 1 req/sec per Nominatim ToS. Acceptable for our usage pattern
    since geocoding only fires on cache miss (most inputs hit the fast dict).

    Future replacement (Option B): Google Maps Geocoding API
      - Higher accuracy for ambiguous/partial addresses and new construction
      - Free up to ~40,000 calls/month, then $5/1,000
      - Set GOOGLE_MAPS_API_KEY in backend/.env
      - Replace this function body; signature stays the same
    """
    if query in _geocode_cache:
        return _geocode_cache[query]

    global _nominatim_last_call
    with _nominatim_lock:
        # Re-check cache inside the lock — another thread may have just resolved it
        if query in _geocode_cache:
            return _geocode_cache[query]

        # Enforce 1 req/sec per Nominatim ToS
        elapsed = time.monotonic() - _nominatim_last_call
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        _nominatim_last_call = time.monotonic()

        try:
            resp = requests.get(
                _NOMINATIM_URL,
                params={
                    "q": query + ", Chicago, IL",
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "us",
                    "viewbox": _CHICAGO_BBOX,
                    "bounded": "1",
                },
                headers={"User-Agent": _NOMINATIM_USER_AGENT},
                timeout=5,
            )
            results = resp.json()
            if results:
                coords: tuple[float, float] = (float(results[0]["lat"]), float(results[0]["lon"]))
                _geocode_cache[query] = coords
                _save_geocode_cache(_geocode_cache)
                print(f"[gtfs_loader] Geocoded and cached '{query}' -> {coords}")
                return coords
        except Exception as exc:
            print(f"[gtfs_loader] Nominatim geocoding failed for '{query}': {exc}")

        # Cache the miss too — avoids hammering Nominatim for queries that never resolve
        _geocode_cache[query] = None
        _save_geocode_cache(_geocode_cache)
        return None


# ---------------------------------------------------------------------------
# GTFS stop loader (cached after first call)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_stops() -> tuple[list[dict], list[dict]]:
    """
    Parse stops.txt and return (train_stations, bus_stops).
    Called once at startup; result is cached for the lifetime of the process.
    """
    train_stations: list[dict] = []
    bus_stops: list[dict] = []

    stops_file = GTFS_DIR / "stops.txt"
    if not stops_file.exists():
        raise FileNotFoundError(
            f"GTFS stops file not found at {stops_file}. "
            "Run `python fetch_gtfs.py` to download the data."
        )

    with open(stops_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                stop_id_int = int(row["stop_id"].strip())
                lat = float(row["stop_lat"].strip())
                lon = float(row["stop_lon"].strip())
            except (ValueError, KeyError):
                continue

            name = row.get("stop_name", "").strip()
            location_type = row.get("location_type", "0").strip()
            stop_id_str = str(stop_id_int)

            if 40000 <= stop_id_int <= 49999 and location_type == "1":
                train_stations.append({
                    "mapid": stop_id_str,
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "type": "train_station",
                })

            elif stop_id_int <= 29999 and location_type in ("0", ""):
                bus_stops.append({
                    "stop_id": stop_id_str,
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "type": "bus_stop",
                })

    return train_stations, bus_stops


# ---------------------------------------------------------------------------
# Public lookup functions
# ---------------------------------------------------------------------------

def find_nearest_train_stations(
    lat: float,
    lon: float,
    max_distance_miles: float = 0.5,
    max_results: int = 3,
) -> list[dict]:
    """
    Return the closest train parent stations within walking distance,
    each annotated with real street-network walk_minutes.
    """
    train_stations, _ = _load_stops()

    candidates = [
        {**s, "distance_miles": _haversine_miles(lat, lon, s["lat"], s["lon"])}
        for s in train_stations
        if _haversine_miles(lat, lon, s["lat"], s["lon"]) <= max_distance_miles
    ]
    candidates.sort(key=lambda s: s["distance_miles"])
    candidates = candidates[:max_results]

    for s in candidates:
        s["walk_minutes"] = walk_minutes(lat, lon, s["lat"], s["lon"])
        del s["distance_miles"]

    return sorted(candidates, key=lambda s: s["walk_minutes"])


def find_nearest_bus_stops(
    lat: float,
    lon: float,
    max_distance_miles: float = 0.25,
    max_results: int = 5,
) -> list[dict]:
    """
    Return the closest bus stops within a quarter-mile radius,
    each annotated with real street-network walk_minutes.
    """
    _, bus_stops = _load_stops()

    candidates = [
        {**s, "distance_miles": _haversine_miles(lat, lon, s["lat"], s["lon"])}
        for s in bus_stops
        if _haversine_miles(lat, lon, s["lat"], s["lon"]) <= max_distance_miles
    ]
    candidates.sort(key=lambda s: s["distance_miles"])
    candidates = candidates[:max_results]

    for s in candidates:
        s["walk_minutes"] = walk_minutes(lat, lon, s["lat"], s["lon"])
        del s["distance_miles"]

    return sorted(candidates, key=lambda s: s["walk_minutes"])


def resolve_location(query: str) -> tuple[list[dict], list[dict], str | None]:
    """
    Convert a free-text location query to nearby train stations and bus stops.

    Resolution order:
      1. Exact match against NEIGHBORHOOD_COORDS
      2. Fuzzy match against NEIGHBORHOOD_COORDS (threshold: 0.95 similarity)
      3. OSM Nominatim geocoding (network call, ~200ms, biased to Chicago)

    Returns:
        (train_stations, bus_stops, matched_name)
        matched_name is the dict key or the original query if geocoded.
    """
    q = query.lower().strip()

    # 1. Exact match
    coords = NEIGHBORHOOD_COORDS.get(q)
    matched_name = q if coords else None

    # 2. Fuzzy match — requires both a high similarity score AND at least one
    #    meaningful word in common. This prevents "chicago art museum" from
    #    fuzzy-matching to "chicago history museum" just because both share
    #    the structural words "chicago" and "museum".
    _STOP_WORDS = {"the", "of", "a", "an", "and", "at", "in", "on", "chicago"}
    q_words = set(q.split()) - _STOP_WORDS

    if coords is None:
        best_score = 0.0
        best_key: str | None = None
        for key in NEIGHBORHOOD_COORDS:
            score = SequenceMatcher(None, q, key).ratio()
            if score <= best_score:
                continue
            # For multi-word queries, require at least one meaningful word in
            # common. Single-word queries (typos like "wriglevile") skip this
            # check since there's no word to overlap with.
            if len(q_words) > 1:
                key_words = set(key.split()) - _STOP_WORDS
                if not q_words & key_words:
                    continue
            best_score = score
            best_key = key
        if best_score >= 0.95 and best_key:
            coords = NEIGHBORHOOD_COORDS[best_key]
            matched_name = best_key

    # 3. Nominatim geocoding fallback
    if coords is None:
        coords = geocode_nominatim(query)
        if coords:
            matched_name = query
            print(f"[gtfs_loader] Geocoded '{query}' -> {coords}")

    if coords is None:
        return [], [], None

    lat, lon = coords
    return (
        find_nearest_train_stations(lat, lon),
        find_nearest_bus_stops(lat, lon),
        matched_name,
    )
