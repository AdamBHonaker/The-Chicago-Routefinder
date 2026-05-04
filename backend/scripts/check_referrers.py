"""
Fetch per-day traffic-source counts from the production backend.
Usage: python check_referrers.py <DAU_ADMIN_TOKEN>
"""

import sys
import urllib.request
import urllib.error
import json

BACKEND_URL = "https://cta-transit-pwa-prod-production.up.railway.app"


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_referrers.py <DAU_ADMIN_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    req = urllib.request.Request(
        f"{BACKEND_URL}/admin/referrers",
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

    print(f"{'Date':<12} {'Direct':>8} {'Search':>8} {'Social':>8} {'Other':>8}")
    print("-" * 46)
    for date in sorted(data):
        row = data[date]
        other_sum = sum(int(v) for v in (row.get("other") or {}).values())
        print(f"{date:<12} {row.get('direct', 0):>8} {row.get('search', 0):>8} "
              f"{row.get('social', 0):>8} {other_sum:>8}")
        # Long tail
        other = row.get("other") or {}
        if other:
            for host, n in sorted(other.items(), key=lambda kv: -kv[1])[:10]:
                print(f"    {host:<30} {n:>5}")


if __name__ == "__main__":
    main()
