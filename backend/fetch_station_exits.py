#!/usr/bin/env python3
"""
One-time script to build station_exits.json from OSM Overpass data.

Queries all railway=subway_entrance nodes in Chicago's bounding box,
matches each entrance to the nearest CTA parent station by haversine
distance, and writes backend/station_exits.json.

Usage (from backend/ directory):
    python fetch_station_exits.py

After generating, review and correct any misassigned exits for the 10-15
most-used stations.  The JSON format is simple — edit by hand as needed.

Development note: the raw Overpass response is cached to .overpass_cache.json
after the first fetch.  Delete that file to force a fresh OSM query.
"""

import csv
import heapq
import json
import math
import time
from pathlib import Path

import numpy as np
import requests

from utils import CHICAGO_BBOX_OVERPASS

_EARTH_RADIUS_MILES = 3958.8

GTFS_DIR   = Path(__file__).parent / "gtfs_data"
OUT_FILE   = Path(__file__).parent / "station_exits.json"
CACHE_FILE = Path(__file__).parent / ".overpass_cache.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Chicago bounding box: (south, west, north, east)
CHICAGO_BBOX = CHICAGO_BBOX_OVERPASS

# Max haversine distance (miles) to assign an entrance to a station.
# CTA stations can span a full block; 0.2 mi covers the largest footprints.
MAX_ASSIGN_MILES = 0.20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_parent_stations() -> dict[str, dict]:
    """Load CTA parent train stations (40000-range) from GTFS stops.txt."""
    stations: dict[str, dict] = {}
    stops_file = GTFS_DIR / "stops.txt"
    if not stops_file.exists():
        raise FileNotFoundError(
            f"GTFS stops.txt not found at {stops_file}.\n"
            "Run fetch_gtfs.py first to download CTA GTFS data."
        )
    with open(stops_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                sid = int(row["stop_id"].strip())
                if 40000 <= sid <= 49999 and row.get("location_type", "").strip() == "1":
                    slat = float(row["stop_lat"].strip())
                    slon = float(row["stop_lon"].strip())
                    srlat = math.radians(slat)
                    stations[str(sid)] = {
                        "name":    row.get("stop_name", "").strip(),
                        "lat":     slat,
                        "lon":     slon,
                        "rlat":    srlat,
                        "rlon":    math.radians(slon),
                        "cos_lat": math.cos(srlat),
                    }
            except (ValueError, KeyError):
                continue
    return stations


def fetch_subway_entrances() -> list[dict]:
    """Query Overpass API for all railway=subway_entrance nodes in Chicago.

    Caches the raw response to .overpass_cache.json on first run so
    subsequent runs skip the network call.  Delete that file to refresh.
    """
    if CACHE_FILE.exists():
        print("Loading cached Overpass response …")
        with open(CACHE_FILE, encoding="utf-8") as f:
            elements = json.load(f)
        print(f"  {len(elements)} subway entrance nodes (from cache)")
        return elements

    query = (
        f"[out:json][timeout:30];\n"
        f'node["railway"="subway_entrance"]({CHICAGO_BBOX});\n'
        f"out body;\n"
    )
    print("Querying Overpass API …")
    resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=60)
    resp.raise_for_status()
    elements = resp.json().get("elements", [])
    print(f"  {len(elements)} subway entrance nodes returned by OSM")

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(elements, f)
    print(f"  Response cached to {CACHE_FILE}")

    time.sleep(1)  # polite pause after Overpass query
    return elements


def _exit_label(tags: dict) -> str:
    """Extract a human-readable label from an OSM node's tags."""
    # Prefer 'name'; fall back to 'ref', 'loc_name', 'description' in order.
    for key in ("name", "ref", "loc_name", "description"):
        val = tags.get(key, "").strip()
        if val:
            return val
    return ""


def build_exits(
    stations: dict[str, dict],
    entrances: list[dict],
) -> dict[str, list[dict]]:
    """
    Match each Overpass node to its nearest parent station and build the
    {mapid: [{label, lat, lon}, ...]} structure for station_exits.json.

    Uses a vectorized NumPy haversine over the full (M entrances × N stations)
    distance matrix instead of a Python nested loop. Filtering and array
    extraction are combined into a single pass over entrances to avoid
    redundant iteration.
    """
    result: dict[str, list[dict]] = {}
    unassigned = 0

    # Filter entrances and extract lat/lon in one pass.
    valid: list[dict] = []
    e_lats: list[float] = []
    e_lons: list[float] = []
    for n in entrances:
        if n.get("type") == "node" and n.get("lat") is not None and n.get("lon") is not None:
            valid.append(n)
            e_lats.append(n["lat"])
            e_lons.append(n["lon"])
    if not valid or not stations:
        return result

    # Station arrays (N,) — all three extracted in a single pass.
    station_ids = list(stations.keys())
    s_vals      = [(stations[m]["rlat"], stations[m]["rlon"], stations[m]["cos_lat"]) for m in station_ids]
    s_rlat, s_rlon, s_cos_lat = (np.array(col) for col in zip(*s_vals))

    # Entrance arrays (M,)
    e_rlat    = np.radians(e_lats)
    e_rlon    = np.radians(e_lons)
    e_cos_lat = np.cos(e_rlat)

    # Vectorized haversine intermediate — broadcast to (M, N)
    dlat = s_rlat - e_rlat[:, np.newaxis]
    dlon = s_rlon - e_rlon[:, np.newaxis]
    a = (
        np.sin(dlat / 2) ** 2
        + e_cos_lat[:, np.newaxis] * s_cos_lat * np.sin(dlon / 2) ** 2
    )
    del dlat, dlon  # free M×N intermediates

    # arcsin is monotonic: argmin/min on a gives the same ranking as on dist,
    # so the full M×N arcsin is skipped — only the M winning values are converted.
    best_idx  = a.argmin(axis=1)              # (M,)
    best_a    = a.min(axis=1)                 # (M,)
    del a                                     # free M×N intermediate

    best_dist     = _EARTH_RADIUS_MILES * 2 * np.arcsin(np.sqrt(np.clip(best_a, 0.0, 1.0)))
    del best_a
    best_idx_list = best_idx.tolist()         # convert once; avoids per-iter numpy scalar cast

    for i, node in enumerate(valid):
        if best_dist[i] > MAX_ASSIGN_MILES:
            unassigned += 1
            continue

        lat   = node["lat"]
        lon   = node["lon"]
        tags  = node.get("tags", {})
        label = _exit_label(tags)
        if not label:
            label = f"Entrance ({lat:.4f}, {lon:.4f})"

        mapid = station_ids[best_idx_list[i]]
        result.setdefault(mapid, []).append({
            "label": label,
            "lat":   round(lat, 6),
            "lon":   round(lon, 6),
        })

    if unassigned:
        print(f"  {unassigned} entrance nodes skipped "
              f"(> {MAX_ASSIGN_MILES} mi from any parent station)")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading parent stations from GTFS …")
    stations = load_parent_stations()
    print(f"  {len(stations)} parent stations")

    entrances = fetch_subway_entrances()

    exits = build_exits(stations, entrances)
    print(f"  {len(exits)} stations with at least 1 mapped exit")
    total = sum(len(v) for v in exits.values())
    print(f"  {total} total exit entries")

    # Sort exits within each station by label for readability
    for mapid in exits:
        exits[mapid].sort(key=lambda e: e["label"].lower())

    # Sort stations numerically by mapid
    sorted_exits = dict(sorted(exits.items(), key=lambda kv: int(kv[0])))

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_exits, f, indent=2, ensure_ascii=False)
    print(f"\nWritten: {OUT_FILE}")

    # Summary of top stations for manual review
    top = heapq.nlargest(15, exits.items(), key=lambda kv: len(kv[1]))
    print("\nTop stations by exit count (review these first):")
    for mapid, ex_list in top:
        sname = stations.get(mapid, {}).get("name", mapid)
        print(f"  [{mapid}] {sname}: {len(ex_list)} exits")
        for ex in ex_list[:4]:
            print(f"        {ex['label']}")
        if len(ex_list) > 4:
            print(f"        … and {len(ex_list) - 4} more")


if __name__ == "__main__":
    main()
