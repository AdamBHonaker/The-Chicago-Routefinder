"""
Fetch daily unique visitor counts from the production backend.
Usage: python check_dau.py <DAU_ADMIN_TOKEN>
"""

import sys
import urllib.request
import json

BACKEND_URL = "https://cta-transit-pwa-prod-production.up.railway.app"

def main():
    if len(sys.argv) < 2:
        print("Usage: python check_dau.py <DAU_ADMIN_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    url = f"{BACKEND_URL}/admin/dau"

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

    if not data:
        print("No data yet.")
        return

    print(f"{'Date':<12} {'Unique Visitors':>16}")
    print("-" * 30)
    for date in sorted(data):
        print(f"{date:<12} {data[date]:>16}")

if __name__ == "__main__":
    main()
