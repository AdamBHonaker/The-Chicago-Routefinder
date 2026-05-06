"""
Fetch per-day device-class counts from the production backend.
Usage: python check_devices.py <DAU_ADMIN_TOKEN>
"""

import sys
import urllib.request
import urllib.error
import json

BACKEND_URL = "https://the-chicago-routefinder.up.railway.app"


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_devices.py <DAU_ADMIN_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    req = urllib.request.Request(
        f"{BACKEND_URL}/admin/devices",
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

    cols = ("mobile", "tablet", "desktop", "bot", "unknown")
    print(f"{'Date':<12}", *(f"{c:>9}" for c in cols))
    print("-" * (12 + 10 * len(cols)))
    for date in sorted(data):
        row = data[date]
        print(f"{date:<12}", *(f"{row.get(c, 0):>9}" for c in cols))


if __name__ == "__main__":
    main()
