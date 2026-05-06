"""
Fetch new vs returning visitor aggregates and Bloom filter stats from the
production backend.
Usage: python check_retention.py <DAU_ADMIN_TOKEN>
"""

import sys
import urllib.request
import urllib.error
import json

BACKEND_URL = "https://the-chicago-routefinder.up.railway.app"


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_retention.py <DAU_ADMIN_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    req = urllib.request.Request(
        f"{BACKEND_URL}/admin/retention",
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

    daily = data.get("daily", {})
    filt  = data.get("filter", {})

    if not daily:
        print("No retention data yet.")
    else:
        print(f"{'Date':<12} {'New':>8} {'Returning':>10} {'Total':>7} {'Return%':>8}")
        print("-" * 50)
        for date in sorted(daily):
            d = daily[date]
            print(
                f"{date:<12} {d['new']:>8} {d['returning']:>10} "
                f"{d['total']:>7} {d['returning_pct']:>7.1f}%"
            )

    print()
    print("Bloom filter diagnostics:")
    print(f"  Capacity:     {filt.get('capacity', '?')}")
    print(f"  Count:        {filt.get('count', '?')}")
    print(f"  Utilisation:  {filt.get('utilisation_pct', '?')}%")
    print(f"  FPR at cap:   {filt.get('fpr_at_capacity_pct', '?')}%")
    if filt.get("utilisation_pct", 0) >= 80:
        print(
            "\n  WARNING: filter is ≥80% full — FPR may be rising above 1%.\n"
            "  Clear by removing backend/data/retention.json and restarting."
        )


if __name__ == "__main__":
    main()
