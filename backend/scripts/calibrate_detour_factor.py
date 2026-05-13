"""
One-shot calibration script for config.DETOUR_FACTOR (BUG-053).

Samples random origin/destination pairs uniformly inside the street-graph
coverage area, computes both the Haversine straight-line distance and the
real pedestrian street-graph distance, and reports the empirical detour
ratio (street / haversine) with a 95% confidence interval — overall and
banded by distance.

Usage (from repo root):
    python -m backend.scripts.calibrate_detour_factor [--samples 500] [--seed 0]

The script is intentionally read-only: it does not modify config.py. Re-run
it whenever the street graph is rebuilt and update DETOUR_FACTOR by hand if
the empirical mean has drifted outside the previous CI.
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
import time
from pathlib import Path

# Allow `python backend/scripts/calibrate_detour_factor.py` to find sibling modules.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import walking  # noqa: E402
from utils import (  # noqa: E402
    haversine_miles,
    STREET_GRAPH_SOUTH,
    STREET_GRAPH_NORTH,
    STREET_GRAPH_WEST,
    STREET_GRAPH_EAST,
    PURPLE_LINE_CORRIDOR_SOUTH,
    PURPLE_LINE_CORRIDOR_NORTH,
    PURPLE_LINE_CORRIDOR_WEST,
    PURPLE_LINE_CORRIDOR_EAST,
)

# Distance bands (miles) for segmented reporting.
_BANDS: list[tuple[float, float, str]] = [
    (0.0, 0.25, "<=0.25 mi"),
    (0.25, 1.0, "0.25-1 mi"),
    (1.0, 3.0, "1-3 mi"),
]
_MAX_PAIR_MILES = 3.0  # ignore pairs further apart than this; calibration target is walks


def _in_coverage(lat: float, lon: float) -> bool:
    if STREET_GRAPH_SOUTH <= lat <= STREET_GRAPH_NORTH and STREET_GRAPH_WEST <= lon <= STREET_GRAPH_EAST:
        return True
    if (
        PURPLE_LINE_CORRIDOR_SOUTH <= lat <= PURPLE_LINE_CORRIDOR_NORTH
        and PURPLE_LINE_CORRIDOR_WEST <= lon <= PURPLE_LINE_CORRIDOR_EAST
    ):
        return True
    return False


def _random_point(rng: random.Random) -> tuple[float, float]:
    # Area-weighted pick between main box and Purple Line corridor.
    main_area = (STREET_GRAPH_NORTH - STREET_GRAPH_SOUTH) * (STREET_GRAPH_EAST - STREET_GRAPH_WEST)
    corr_area = (PURPLE_LINE_CORRIDOR_NORTH - PURPLE_LINE_CORRIDOR_SOUTH) * (
        PURPLE_LINE_CORRIDOR_EAST - PURPLE_LINE_CORRIDOR_WEST
    )
    if rng.random() < main_area / (main_area + corr_area):
        lat = rng.uniform(STREET_GRAPH_SOUTH, STREET_GRAPH_NORTH)
        lon = rng.uniform(STREET_GRAPH_WEST, STREET_GRAPH_EAST)
    else:
        lat = rng.uniform(PURPLE_LINE_CORRIDOR_SOUTH, PURPLE_LINE_CORRIDOR_NORTH)
        lon = rng.uniform(PURPLE_LINE_CORRIDOR_WEST, PURPLE_LINE_CORRIDOR_EAST)
    return lat, lon


def _street_miles(o_lat: float, o_lon: float, d_lat: float, d_lon: float) -> float | None:
    """Return real street-network distance in miles, or None if no path."""
    path = walking._get_shortest_path(o_lat, o_lon, d_lat, d_lon)
    if path is None or walking._edge_lengths is None:
        return None
    _, epath = path
    if not epath:
        return None
    length_m = float(walking._edge_lengths[list(epath)].sum())
    return length_m / 1609.34


def _ci95(values: list[float]) -> tuple[float, float, float]:
    """Return (mean, lo, hi) for a 95% normal-approximation CI of the mean."""
    n = len(values)
    mean = statistics.fmean(values)
    if n < 2:
        return mean, mean, mean
    stdev = statistics.stdev(values)
    half = 1.96 * stdev / math.sqrt(n)
    return mean, mean - half, mean + half


def _summarize(label: str, ratios: list[float]) -> None:
    if not ratios:
        print(f"  {label:<14} n=0 (no samples)")
        return
    mean, lo, hi = _ci95(ratios)
    median = statistics.median(ratios)
    print(
        f"  {label:<14} n={len(ratios):>4}  mean={mean:.4f}  "
        f"95% CI=[{lo:.4f}, {hi:.4f}]  median={median:.4f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate DETOUR_FACTOR from street-graph samples.")
    parser.add_argument("--samples", type=int, default=500, help="number of accepted O/D pairs (default 500)")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed for reproducibility")
    parser.add_argument(
        "--max-attempts-per-sample",
        type=int,
        default=20,
        help="abort if too many candidate pairs are rejected (graph unreachable, out of range)",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    target = args.samples

    print(f"Loading street graph from {walking.IGRAPH_PATH} …")
    t0 = time.monotonic()
    if walking._load_graph() is None:
        print("ERROR: street graph failed to load. Run `python backend/fetch_street_graph.py` first.")
        return 2
    print(f"  loaded in {time.monotonic() - t0:.1f}s")

    ratios: list[float] = []
    banded: dict[str, list[float]] = {b[2]: [] for b in _BANDS}
    attempts = 0
    rejects = 0
    started = time.monotonic()

    while len(ratios) < target:
        attempts += 1
        if attempts > target * args.max_attempts_per_sample:
            print(f"WARN: aborting after {attempts} attempts ({len(ratios)} accepted, {rejects} rejected)")
            break

        o_lat, o_lon = _random_point(rng)
        d_lat, d_lon = _random_point(rng)
        if not (_in_coverage(o_lat, o_lon) and _in_coverage(d_lat, d_lon)):
            rejects += 1
            continue

        hav = haversine_miles(o_lat, o_lon, d_lat, d_lon)
        if hav < 0.05 or hav > _MAX_PAIR_MILES:
            rejects += 1
            continue

        street = _street_miles(o_lat, o_lon, d_lat, d_lon)
        if street is None or street <= 0:
            rejects += 1
            continue

        ratio = street / hav
        # Guard against pathological ratios (disconnected components routed via long detours).
        if ratio < 1.0 or ratio > 3.0:
            rejects += 1
            continue

        ratios.append(ratio)
        for lo, hi, label in _BANDS:
            if lo <= hav < hi:
                banded[label].append(ratio)
                break

        if len(ratios) % 50 == 0:
            print(f"  …{len(ratios)}/{target} samples ({rejects} rejected, {time.monotonic() - started:.1f}s)")

    elapsed = time.monotonic() - started
    print()
    print(f"Done: {len(ratios)} accepted in {elapsed:.1f}s ({rejects} rejected, {attempts} total attempts).")
    print()
    print("Empirical detour ratio (street_distance / haversine_distance):")
    _summarize("overall", ratios)
    for _, _, label in _BANDS:
        _summarize(label, banded[label])

    print()
    print(f"Current config.DETOUR_FACTOR = {__import__('config').DETOUR_FACTOR}")
    print("Update config.DETOUR_FACTOR to the overall mean if it falls outside the previous CI;")
    print("annotate the change with this script path, sample size, seed, and date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
