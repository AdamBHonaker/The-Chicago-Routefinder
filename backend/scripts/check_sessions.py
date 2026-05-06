"""
Fetch per-day session aggregates from the production backend.
Usage: python check_sessions.py <DAU_ADMIN_TOKEN>
"""

import sys
import urllib.request
import urllib.error
import json

BACKEND_URL = "https://the-chicago-routefinder.up.railway.app"


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_sessions.py <DAU_ADMIN_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    req = urllib.request.Request(
        f"{BACKEND_URL}/admin/sessions",
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

    print(f"{'Date':<12} {'Sessions':>10} {'Avg dur':>10} {'Bounces':>9} {'Bounce%':>8}")
    print("-" * 53)
    for date in sorted(data):
        d = data[date]
        avg = d.get("avg_duration_seconds", 0.0)
        avg_str = f"{int(avg // 60)}m{int(avg % 60):02d}s"
        print(f"{date:<12} {d['sessions']:>10} {avg_str:>10} {d['bounces']:>9} {d['bounce_rate_pct']:>7.1f}%")


if __name__ == "__main__":
    main()
