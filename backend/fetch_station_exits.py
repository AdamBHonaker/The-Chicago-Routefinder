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
"""

import csv
import json
import math
import time
from pathlib import Path

import requests

from utils import CHICAGO_BBOX_OVERPASS

_EARTH_RADIUS_MILES = 3958.8


def _haversine_precomputed(
    rlat1: float, cos_lat1: float, rlon1: float,
    rlat2: float, cos_lat2: float, rlon2: float,
) -> float:
    """Haversine distance (miles) with radians and cos(lat) pre-computed by caller."""
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + cos_lat1 * cos_lat2 * math.sin(dlon / 2) ** 2
    return _EARTH_RADIUS_MILES * 2 * math.asin(math.sqrt(a))

GTFS_DIR = Path(__file__).parent / "gtfs_data"
OUT_FILE = Path(__file__).parent / "station_exits.json"

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
    """Query Overpass API for all railway=subway_entrance nodes in Chicago."""
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
    """
    result: dict[str, list[dict]] = {}
    unassigned = 0

    for node in entrances:
        if node.get("type") != "node":
            continue
        lat = node.get("lat")
        lon = node.get("lon")
        if lat is None or lon is None:
            continue

        tags  = node.get("tags", {})
        label = _exit_label(tags)
        if not label:
            # Use coordinates as a placeholder so the entry is still useful
            label = f"Entrance ({lat:.4f}, {lon:.4f})"

        # Pre-compute entrance trig once for the ~150-station inner loop
        rlat1    = math.radians(lat)
        rlon1    = math.radians(lon)
        cos_lat1 = math.cos(rlat1)

        # Find the nearest parent station
        best_mapid = None
        best_dist  = float("inf")
        for mapid, info in stations.items():
            d = _haversine_precomputed(
                rlat1, cos_lat1, rlon1,
                info["rlat"], info["cos_lat"], info["rlon"],
            )
            if d < best_dist:
                best_dist  = d
                best_mapid = mapid

        if best_mapid is None or best_dist > MAX_ASSIGN_MILES:
            unassigned += 1
            continue

        result.setdefault(best_mapid, []).append({
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
    time.sleep(1)  # polite pause after Overpass query

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
    top = sorted(exits.items(), key=lambda kv: len(kv[1]), reverse=True)[:15]
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
