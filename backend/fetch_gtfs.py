"""
Downloads the latest CTA GTFS static data and extracts it to backend/gtfs_data/.

Run this script:
  - On initial setup
  - Whenever CTA updates their schedule data (typically every few months)

Usage:
  python fetch_gtfs.py
"""

import os
import sys
import zipfile
import urllib.request
import shutil
from pathlib import Path

GTFS_URL  = "https://www.transitchicago.com/downloads/sch_data/google_transit.zip"
GTFS_DIR  = Path(__file__).parent / "gtfs_data"
GTFS_ZIP  = GTFS_DIR / "google_transit.zip"

# Files we care about — listed here for reference and validation
EXPECTED_FILES = [
    "stops.txt",        # All stops with coordinates — critical for stop lookup
    "routes.txt",       # Route names and IDs
    "trips.txt",        # Trips per route and direction
    "stop_times.txt",   # Scheduled arrival/departure times at each stop
    "transfers.txt",    # Designated transfer points between routes
    "shapes.txt",       # Route path geometry (used for map display later)
    "calendar.txt",     # Service days (weekday/weekend/holiday schedules)
    "calendar_dates.txt", # Schedule exceptions (holidays, special service)
]


def download_gtfs() -> None:
    GTFS_DIR.mkdir(exist_ok=True)

    print(f"Downloading CTA GTFS data from {GTFS_URL} ...")
    try:
        request = urllib.request.Request(
            GTFS_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 64 * 1024  # 64 KB chunks

            with open(GTFS_ZIP, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"  {downloaded / 1024:.0f} KB / {total / 1024:.0f} KB  ({pct:.0f}%)", end="\r")

        print(f"\nDownload complete: {downloaded / 1024:.0f} KB saved to {GTFS_ZIP}")
    except Exception as e:
        raise RuntimeError(f"Failed to download GTFS data: {e}") from e


def extract_gtfs() -> None:
    print(f"Extracting to {GTFS_DIR} ...")
    with zipfile.ZipFile(GTFS_ZIP, "r") as zf:
        zf.extractall(GTFS_DIR)
    print("Extraction complete.")


def validate_and_report() -> None:
    print("\nGTFS files:")
    all_present = True
    for filename in EXPECTED_FILES:
        path = GTFS_DIR / filename
        if path.exists():
            with open(path, encoding="utf-8-sig") as fh:
                rows = sum(1 for _ in fh) - 1  # subtract header
            size_kb = path.stat().st_size / 1024
            print(f"  ✓  {filename:<25} {rows:>7,} rows   ({size_kb:,.0f} KB)")
        else:
            print(f"  ✗  {filename:<25} NOT FOUND")
            all_present = False

    if all_present:
        print("\nAll expected files present. GTFS data is ready.")
    else:
        print("\nWarning: some expected files are missing.")


def cleanup_zip() -> None:
    if GTFS_ZIP.exists():
        GTFS_ZIP.unlink()
        print(f"Removed zip file: {GTFS_ZIP}")


if __name__ == "__main__":
    # If gtfs_data already has files, warn before overwriting.
    # In non-interactive environments (Railway, CI), skip the prompt and always
    # re-download so the deploy never hangs waiting for input.
    force = "--force" in sys.argv or bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("CI"))
    if GTFS_DIR.exists() and any(GTFS_DIR.glob("*.txt")):
        if force:
            print(f"Existing GTFS data found in {GTFS_DIR}. Re-downloading (non-interactive mode).")
        else:
            print(f"Existing GTFS data found in {GTFS_DIR}.")
            answer = input("Re-download and overwrite? [y/N]: ").strip().lower()
            if answer != "y":
                print("Aborted. Existing data kept.")
                raise SystemExit(0)
        shutil.rmtree(GTFS_DIR)
        print("Old data removed.")

    download_gtfs()
    extract_gtfs()
    cleanup_zip()
    validate_and_report()
