"""
CLI helper for authoring golden-route fixtures (BUG-052 / TD-BE-005 layer 1).

Runs `routing_harness.run_scenario()` for a given OD pair and frozen instant,
then prints the engine's output in the same shape that golden assertions use.
A test author can use this to see what the routing engine *actually* produces
before pinning a `primary_modes` / `lines` / `transfers` assertion.

Usage (from repo root):

    # By coordinates:
    python -m backend.scripts.probe_route \\
        --origin 41.929534,-87.707688 \\
        --dest   41.795420,-87.631157 \\
        --when   "2026-06-16 14:30"

    # By known-stop name (see backend/tests/known_stops.py):
    python -m backend.scripts.probe_route \\
        --origin-stop LOGAN_SQUARE_BLUE \\
        --dest-stop   GARFIELD_RED

The script is read-only. It does not modify any test file. The intent is
"run this, eyeball the output, decide whether it matches your Chicago-rider
expectation, then hand-author the corresponding assertion in
test_routing_accuracy.py."

Why this is a probe, not a fixture generator
--------------------------------------------
Auto-generating an assertion from the engine's current output would lock in
whatever the engine does today, including bugs. The whole point of golden
fixtures is to encode a human's rider-level expectation as a regression
guard — that expectation must come from outside the engine.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Allow `python backend/scripts/probe_route.py` to find sibling modules
# in `backend/`.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from utils import CHICAGO_TZ  # noqa: E402

# Warm sys.modules with `main` and `transit_graph` BEFORE freezegun ever
# starts patching the clock. `stub_cta_arrivals` resolves `main.get_*`
# via `unittest.mock.patch`, which imports `main` lazily — under
# freezegun + Python 3.14 + FastAPI, that lazy import can trip a
# pydantic-v1 metaclass check. Importing eagerly here sidesteps the
# issue by caching `main` in sys.modules first.
import main  # noqa: F401, E402
import transit_graph  # noqa: F401, E402

from tests.known_stops import KNOWN_STOPS  # noqa: E402
from tests.routing_harness import RoutingScenario, run_scenario, summarize_route  # noqa: E402


_DEFAULT_WHEN = datetime(2026, 6, 16, 14, 30, 0, tzinfo=CHICAGO_TZ)


def _parse_latlon(s: str) -> tuple[float, float]:
    try:
        lat_s, lon_s = s.split(",")
        return float(lat_s.strip()), float(lon_s.strip())
    except (ValueError, AttributeError) as exc:
        raise argparse.ArgumentTypeError(
            f"expected 'lat,lon' (e.g. 41.929,-87.708), got: {s!r}"
        ) from exc


def _parse_when(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=CHICAGO_TZ)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"expected 'YYYY-MM-DD HH:MM' (24h, Chicago local), got: {s!r}"
        ) from exc


def _resolve_origin(args: argparse.Namespace) -> tuple[float, float]:
    if args.origin_stop:
        return _lookup_stop(args.origin_stop)
    if args.origin:
        return args.origin
    raise SystemExit("error: provide --origin LAT,LON or --origin-stop NAME")


def _resolve_dest(args: argparse.Namespace) -> tuple[float, float]:
    if args.dest_stop:
        return _lookup_stop(args.dest_stop)
    if args.dest:
        return args.dest
    raise SystemExit("error: provide --dest LAT,LON or --dest-stop NAME")


def _lookup_stop(name: str) -> tuple[float, float]:
    key = name.upper()
    if key not in KNOWN_STOPS:
        suggestions = sorted(k for k in KNOWN_STOPS if key[:3] in k)[:5]
        hint = f" did you mean: {', '.join(suggestions)}?" if suggestions else ""
        raise SystemExit(f"error: unknown stop {name!r}.{hint}")
    return KNOWN_STOPS[key]


def _format_route(idx: int, route) -> str:
    modes, lines, transfers, total = summarize_route(route)
    return (
        f"  [{idx}] modes={modes} lines={lines} "
        f"transfers={transfers} total_minutes={total:.1f}"
    )


async def _run(scenario: RoutingScenario) -> None:
    result = await run_scenario(scenario)
    print(f"Scenario: {scenario.description}")
    print(f"  frozen_at:  {scenario.frozen_at.isoformat()}")
    print(f"  origin:     {scenario.origin}")
    print(f"  dest:       {scenario.dest}")
    print()

    if not result.all_routes_raw:
        print("No routes returned. Possible causes:")
        print("  - OD outside graph coverage (>2 mi from any train station)")
        print("  - frozen_at outside the bundled GTFS feed's calendar window")
        print("  - origin or dest disconnected from the unified graph")
        return

    print(f"Best route (the one golden assertions will see):")
    print(f"  primary_modes:  {result.primary_modes}")
    print(f"  lines:          {result.lines}")
    print(f"  transfers:      {result.transfers}")
    print(f"  total_minutes:  {result.total_minutes:.1f}  (DO NOT assert on this)")
    print()
    print(f"All {len(result.all_routes_raw)} ranked alternatives:")
    for idx, route in enumerate(result.all_routes_raw):
        print(_format_route(idx, route))
    print()
    print("Next step: decide whether `primary_modes` / `lines` / `transfers`")
    print("above match your rider-level expectation. If yes, copy them into a")
    print("new test in backend/tests/test_routing_accuracy.py and remove the")
    print("@pytest.mark.skip marker. If not, that's a real disagreement — do")
    print("NOT silently encode the engine's current answer.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe the routing engine for a given OD pair and time.",
    )
    parser.add_argument("--origin", type=_parse_latlon,
                        help="Origin as 'lat,lon' (e.g. 41.929,-87.708)")
    parser.add_argument("--origin-stop",
                        help="Origin as a KNOWN_STOPS name (e.g. LOGAN_SQUARE_BLUE)")
    parser.add_argument("--dest", type=_parse_latlon,
                        help="Destination as 'lat,lon'")
    parser.add_argument("--dest-stop",
                        help="Destination as a KNOWN_STOPS name")
    parser.add_argument("--when", type=_parse_when, default=_DEFAULT_WHEN,
                        help="Frozen instant 'YYYY-MM-DD HH:MM' Chicago local "
                             "(default: 2026-06-16 14:30, weekday midday)")
    parser.add_argument("--n-routes", type=int, default=3,
                        help="Number of ranked alternatives to request "
                             "(default: 3)")
    args = parser.parse_args()

    origin = _resolve_origin(args)
    dest   = _resolve_dest(args)

    scenario = RoutingScenario(
        frozen_at=args.when,
        origin=origin,
        dest=dest,
        description=(
            f"probe_route {origin} -> {dest} "
            f"@ {args.when.isoformat()}"
        ),
        n_routes=args.n_routes,
    )
    asyncio.run(_run(scenario))


if __name__ == "__main__":
    main()
