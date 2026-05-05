"""
Fetch per-day named-event counts from the production backend.
Usage: python check_events.py <DAU_ADMIN_TOKEN>
"""

import sys
import urllib.request
import urllib.error
import json

BACKEND_URL = "https://cta-transit-pwa-prod-production.up.railway.app"

# Display order — engagement story first, operational events after.
_EVENT_ORDER = (
    "recommend_submitted",
    "recommend_returned",
    "route_selected",
    "start_route_tapped",
    "trip_completed",
    "app_loaded",
    "map_opened",
    "house_ad_clicked",
)


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_events.py <DAU_ADMIN_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    req = urllib.request.Request(
        f"{BACKEND_URL}/admin/events",
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

    header = f"{'Date':<12}" + "".join(f" {n[:14]:>15}" for n in _EVENT_ORDER)
    print(header)
    print("-" * len(header))
    for date in sorted(data):
        row = data[date]
        print(f"{date:<12}" + "".join(
            f" {int(row.get(n, 0)):>15}" for n in _EVENT_ORDER
        ))


if __name__ == "__main__":
    main()
