"""
Fetch per-day geography counts from the production backend.
Usage: python check_geography.py <DAU_ADMIN_TOKEN>
"""

import sys
import urllib.request
import urllib.error
import json

BACKEND_URL = "https://the-chicago-routefinder.up.railway.app"


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_geography.py <DAU_ADMIN_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    url = f"{BACKEND_URL}/admin/geography"

    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
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

    cities = data.get("cities", {})
    metro = data.get("metro", {})
    if not cities and not metro:
        print("No data yet.")
        return

    print("=== Chicago metro share ===")
    print(f"{'Date':<12} {'Metro':>6} {'Total':>6} {'Share':>7}")
    print("-" * 35)
    for date in sorted(metro):
        m = metro[date]
        print(f"{date:<12} {m['metro']:>6} {m['total']:>6} {m['share_pct']:>6.1f}%")

    print()
    print("=== Per-day cities (privacy floor applied) ===")
    for date in sorted(cities):
        day = cities[date]
        print(f"\n{date}:")
        for city, n in sorted(day.items(), key=lambda kv: -kv[1]):
            print(f"  {city:<24} {n:>5}")


if __name__ == "__main__":
    main()
