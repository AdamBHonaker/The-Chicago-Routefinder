FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Download the pre-built igraph street graph from GitHub Releases (Feature K).
# Pass token via Railway: Service → Build Arguments → GITHUB_TOKEN=<PAT Contents:Read>
# Asset ID is resolved dynamically from the release tag so it never goes stale.
# CACHEBUST: set to a new value in Railway Build Arguments to force cache invalidation.
ARG CACHEBUST=1
ARG GITHUB_TOKEN
RUN python3 - <<'PYEOF'
import os, sys, urllib.request, json

token = os.environ.get("GITHUB_TOKEN") or ""
if not token:
    print("ERROR: GITHUB_TOKEN build arg is not set.")
    sys.exit(1)

repo  = "AdamBHonaker/CTA-Transit-PWA"
tag   = "street-graph"
fname = "street_graph_igraph.pkl"

headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

req = urllib.request.Request(
    f"https://api.github.com/repos/{repo}/releases/tags/{tag}", headers=headers)
with urllib.request.urlopen(req) as r:
    release = json.load(r)

assets = release.get("assets", [])
asset  = next((a for a in assets if a["name"] == fname), None)
if asset is None:
    print(f"ERROR: '{fname}' not found in release '{tag}'. Available: {[a['name'] for a in assets]}")
    sys.exit(1)

print(f"Found asset '{fname}' id={asset['id']}")

dl_headers = {"Authorization": f"token {token}", "Accept": "application/octet-stream"}
req2 = urllib.request.Request(
    f"https://api.github.com/repos/{repo}/releases/assets/{asset['id']}", headers=dl_headers)
with urllib.request.urlopen(req2) as r, open(fname, "wb") as f:
    f.write(r.read())

size = os.path.getsize(fname)
print(f"{fname}: {size:,} bytes")
if size < 1_048_576:
    print(f"ERROR: only {size} bytes — likely a truncated download.")
    sys.exit(1)
PYEOF

CMD ["sh", "-c", "python fetch_gtfs.py && uvicorn main:app --host 0.0.0.0 --port $PORT --no-access-log --log-level warning"]
