"""
Fetch per-day funnel stage counts from the production backend.
Usage: python check_funnel.py <DAU_ADMIN_TOKEN>

Output: one row per day, with the count at each funnel stage and the
derived result rate (recommend_returned / app_loaded).
"""

import sys
import urllib.request
import urllib.error
import json

BACKEND_URL = "https://the-chicago-routefinder.up.railway.app"

_STAGES = (
    "app_loaded",
    "recommend_submitted",
    "recommend_returned",
    "route_selected",
    "start_route_tapped",
    "trip_completed",
)
_COL_WIDTH = 20


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_funnel.py <DAU_ADMIN_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    req = urllib.request.Request(
        f"{BACKEND_URL}/admin/funnel",
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

    # Header
    header = f"{'Date':<12}" + "".join(f"{s[:_COL_WIDTH-1]:>{_COL_WIDTH}}" for s in _STAGES) + f"{'result%':>{_COL_WIDTH}}"
    print(header)
    print("-" * len(header))

    for date in sorted(data):
        arr = data[date]
        if not isinstance(arr, list) or len(arr) != len(_STAGES):
            print(f"{date:<12}  (malformed)")
            continue
        started = arr[0]
        got_result = arr[2]
        rate = f"{100.0 * got_result / started:.1f}%" if started else "—"
        print(
            f"{date:<12}"
            + "".join(f"{int(v):>{_COL_WIDTH}}" for v in arr)
            + f"{rate:>{_COL_WIDTH}}"
        )


if __name__ == "__main__":
    main()
