"""
active_routes.py — Print all active CTA bus and train routes right now.

Uses two live CTA APIs:
  - Bus Tracker  /getroutes  → routes currently in service
  - Train Tracker /ttpositions → live train positions (active = has trains)

GTFS routes.txt is used to enrich bus route names and hex colors.

Usage (from the backend/ directory):
  python active_routes.py

Requirements:
  CTA_TRAIN_API_KEY and CTA_BUS_API_KEY set in backend/.env
  pip install aiohttp python-dotenv   (both already in requirements.txt)
"""

import asyncio
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

# Load API keys from backend/.env (same directory as this file)
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(_ENV_PATH)

# Single source of truth for the train line code → name map and CTA API
# bases lives in cta_client. Importing it here keeps the CLI in lockstep with
# the running backend if CTA renames a line or moves an endpoint.
from cta_client import LINE_NAMES as TRAIN_LINES, _CTA_TRAIN_BASE, _CTA_BUS_BASE
from utils import CHICAGO_TZ

_IS_TTY = sys.stdout.isatty()

BUS_ROUTES_URL      = f"{_CTA_BUS_BASE}/getroutes"
TRAIN_POSITIONS_URL = f"{_CTA_TRAIN_BASE}/ttpositions.aspx"
GTFS_ROUTES_PATH    = Path(__file__).parent / "gtfs_data" / "routes.txt"


# ---------------------------------------------------------------------------
# GTFS enrichment
# ---------------------------------------------------------------------------

def _load_gtfs_routes() -> dict[str, dict]:
    """
    Load GTFS routes.txt into a dict keyed by route_short_name (the bus number).
    Returns an empty dict if the file is missing.
    """
    if not GTFS_ROUTES_PATH.exists():
        return {}
    gtfs: dict[str, dict] = {}
    with open(GTFS_ROUTES_PATH, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            short = row.get("route_short_name", "").strip()
            if short:
                gtfs[short] = {
                    "long_name": row.get("route_long_name", "").strip(),
                    "color":     "#" + row.get("route_color", "").strip(),
                }
    return gtfs


# ---------------------------------------------------------------------------
# Live API calls
# ---------------------------------------------------------------------------

async def get_active_bus_routes(
    session: aiohttp.ClientSession,
    bus_key: str,
) -> list[dict]:
    """
    Call Bus Tracker /getroutes.
    Returns only routes the API reports as currently in service.
    """
    params = {"key": bus_key, "format": "json"}
    try:
        async with session.get(
            BUS_ROUTES_URL,
            params=params,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            data = await resp.json(content_type=None)
    except Exception as exc:
        print(f"[bus] API error: {exc}", file=sys.stderr)
        return []

    response = data.get("bustime-response", {})
    if "error" in response:
        errs = response["error"]
        if isinstance(errs, dict):
            errs = [errs]
        for e in errs:
            print(f"[bus] API returned error: {e.get('msg', e)}", file=sys.stderr)
        return []

    routes = response.get("routes", [])
    if isinstance(routes, dict):
        routes = [routes]
    return routes


async def get_active_train_lines(
    session: aiohttp.ClientSession,
    train_key: str,
) -> list[dict]:
    """
    Call Train Tracker /ttpositions for all 8 lines simultaneously.
    A line is considered active if at least one train is reporting a position.
    """
    params = {
        "key":        train_key,
        "rt":         ",".join(TRAIN_LINES.keys()),
        "outputType": "JSON",
    }
    try:
        async with session.get(
            TRAIN_POSITIONS_URL,
            params=params,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            data = await resp.json(content_type=None)
    except Exception as exc:
        print(f"[train] API error: {exc}", file=sys.stderr)
        return []

    ctatt = data.get("ctatt", {})
    err_code = ctatt.get("errCd", "0")
    if str(err_code) != "0":
        print(
            f"[train] API error {err_code}: {ctatt.get('errNm', '')}",
            file=sys.stderr,
        )
        return []

    raw_routes = ctatt.get("route", [])
    if isinstance(raw_routes, dict):
        raw_routes = [raw_routes]

    active: list[dict] = []
    for route in raw_routes:
        rt   = route.get("@name", "")
        trains = route.get("train", [])
        if isinstance(trains, dict):
            trains = [trains]
        if trains:
            active.append({
                "line_code":    rt,
                "line_name":    TRAIN_LINES.get(rt, rt),
                "active_trains": len(trains),
            })
    return active


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _color_block(hex_color: str) -> str:
    """
    Return a small terminal color swatch using ANSI 24-bit color if the
    terminal supports it, otherwise return an empty string.
    """
    if not _IS_TTY:
        return ""
    try:
        # Strip leading '#' and parse RGB
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return ""
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"\033[48;2;{r};{g};{b}m  \033[0m "
    except ValueError:
        return ""


def _print_train_section(lines: list[dict]) -> None:
    lines_sorted = sorted(lines, key=lambda x: x["line_name"])
    print(f"TRAIN LINES  ({len(lines_sorted)} active)")
    print("-" * 42)
    if not lines_sorted:
        print("  No active train lines reported.")
        return
    for line in lines_sorted:
        trains = line["active_trains"]
        train_word = "train" if trains == 1 else "trains"
        print(f"  {line['line_name']:<15}  {trains:>3} {train_word} in service")


def _print_bus_section(routes: list[dict], gtfs: dict[str, dict]) -> None:
    routes_sorted = sorted(routes, key=lambda r: _route_sort_key(r.get("rt", "")))
    print(f"\nBUS ROUTES  ({len(routes_sorted)} active)")
    print("-" * 64)
    if not routes_sorted:
        print("  No active bus routes reported.")
        return

    # Column widths
    col_rt   = 6
    col_api  = 32

    for route in routes_sorted:
        rt       = route.get("rt", "?")
        api_name = route.get("rtnm", "")
        gtfs_row = gtfs.get(rt, {})
        long_name = gtfs_row.get("long_name", api_name)
        color    = gtfs_row.get("color", "#" + route.get("rtclr", "").lstrip("#"))
        swatch   = _color_block(color)
        print(f"  {swatch}Route {rt:<{col_rt}}  {long_name:<{col_api}}")


def _route_sort_key(rt: str) -> tuple:
    """Sort bus routes: numeric routes first (by number), then alpha."""
    if rt.isdigit():
        return (0, int(rt), "")
    # Routes like "J14" or "X9"
    digit_chars: list[str] = []
    letter_chars: list[str] = []
    for c in rt:
        (digit_chars if c.isdigit() else letter_chars).append(c)
    digits = "".join(digit_chars)
    letters = "".join(letter_chars)
    if digits:
        return (1, int(digits), letters)
    return (2, 0, rt)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """CLI entry: print active CTA bus routes and train lines for the current moment.

    Requires ``CTA_TRAIN_API_KEY`` and ``CTA_BUS_API_KEY`` in backend/.env.
    Exits non-zero if either is missing.

    Output goes to stdout in two sections (trains, then buses), with the bus
    list enriched from GTFS routes.txt for human-readable names and colors.
    """
    train_key = os.getenv("CTA_TRAIN_API_KEY", "")
    bus_key   = os.getenv("CTA_BUS_API_KEY", "")

    missing = []
    if not train_key:
        missing.append("CTA_TRAIN_API_KEY")
    if not bus_key:
        missing.append("CTA_BUS_API_KEY")
    if missing:
        print(f"Error: missing API key(s) in {_ENV_PATH}: {', '.join(missing)}")
        sys.exit(1)

    now = datetime.now(CHICAGO_TZ)
    print(f"\nCTA Active Routes — {now.strftime('%A, %B %d %Y  %I:%M %p %Z')}\n")

    async with aiohttp.ClientSession() as session:
        bus_routes, train_lines, gtfs_routes = await asyncio.gather(
            get_active_bus_routes(session, bus_key),
            get_active_train_lines(session, train_key),
            asyncio.to_thread(_load_gtfs_routes),
        )

    _print_train_section(train_lines)
    _print_bus_section(bus_routes, gtfs_routes)
    print()


if __name__ == "__main__":
    asyncio.run(main())
