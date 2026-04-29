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
            cl = int(response.headers.get("Content-Length", 0))
            if cl:
                print(f"  File size: ~{cl // (1024*1024)} MB")

            downloaded = 0
            chunk_size = 1024 * 1024  # 1 MB chunks
            last_report_mb = 0

            with open(GTFS_ZIP, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    # Log only every 5 MB to avoid Railway log rate limits
                    mb = downloaded // (5 * 1024 * 1024)
                    if mb > last_report_mb:
                        last_report_mb = mb
                        print(f"  ... {downloaded // (1024*1024)} MB downloaded")

        print(f"Download complete: {downloaded // 1024} KB saved to {GTFS_ZIP}")
    except Exception as e:
        raise RuntimeError(f"Failed to download GTFS data: {e}") from e


def extract_gtfs() -> None:
    print(f"Extracting to {GTFS_DIR} ...")
    with zipfile.ZipFile(GTFS_ZIP, "r") as zf:
        zip_names = set(zf.namelist())
        for filename in EXPECTED_FILES:
            if filename in zip_names:
                zf.extract(filename, GTFS_DIR)
    print("Extraction complete.")


def validate_and_report() -> None:
    print("\nGTFS files:")
    stats = {e.name: e.stat() for e in os.scandir(GTFS_DIR) if e.is_file()}
    all_present = True
    for filename in EXPECTED_FILES:
        if filename in stats:
            size_kb = stats[filename].st_size / 1024
            print(f"  ✓  {filename:<25} ({size_kb:,.0f} KB)")
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
    # Determine whether to re-download existing GTFS data.
    # --force always re-downloads.  Non-interactive environments (Railway, CI)
    # skip the prompt but KEEP existing data unless --force is also passed,
    # so deploys don't re-download unnecessarily on every push.
    force           = "--force" in sys.argv
    non_interactive = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("CI"))
    sentinel        = GTFS_DIR / "stops.txt"
    if GTFS_DIR.exists() and sentinel.exists():
        if force:
            print(f"Existing GTFS data found in {GTFS_DIR}. Re-downloading (--force).")
        elif non_interactive:
            print(f"Existing GTFS data found in {GTFS_DIR}. Keeping it (non-interactive; pass --force to re-download).")
            raise SystemExit(0)
        else:
            print(f"Existing GTFS data found in {GTFS_DIR}.")
            answer = input("Re-download and overwrite? [y/N]: ").strip().lower()
            if answer != "y":
                print("Aborted. Existing data kept.")
                raise SystemExit(0)

    download_gtfs()
    extract_gtfs()
    cleanup_zip()
    validate_and_report()
