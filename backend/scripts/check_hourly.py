"""
Fetch per-day hour-of-day histograms from the production backend.
Usage: python check_hourly.py <DAU_ADMIN_TOKEN>

Prints an ASCII bar chart per day, indexed 0–23 in Chicago time.
"""

import sys
import urllib.request
import urllib.error
import json

BACKEND_URL = "https://the-chicago-routefinder.up.railway.app"


def _bar(n: int, peak: int, width: int = 30) -> str:
    if peak <= 0:
        return ""
    filled = round(width * n / peak)
    return "█" * filled


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_hourly.py <DAU_ADMIN_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    req = urllib.request.Request(
        f"{BACKEND_URL}/admin/hourly",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.reason}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network error: {e.reason}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON response: {e}")
        sys.exit(1)

    if not data:
        print("No data yet.")
        return

    for date in sorted(data):
        arr = data[date]
        if not isinstance(arr, list) or len(arr) != 24:
            continue
        peak = max(arr) if arr else 0
        total = sum(arr)
        peak_hour = arr.index(peak) if peak else 0
        print(f"\n{date}  total={total}  peak={peak_hour}:00 ({peak})")
        for hour, n in enumerate(arr):
            print(f"  {hour:>2}:00  {n:>5}  {_bar(n, peak)}")


if __name__ == "__main__":
    main()
