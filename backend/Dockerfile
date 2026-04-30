# syntax=docker/dockerfile:1
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
# Pass the GitHub PAT as a Railway service variable (NOT a build argument):
#   Service → Variables → GITHUB_TOKEN=<PAT with Contents:Read scope>
# Railway exposes service variables as BuildKit secrets automatically.
# The asset ID is resolved dynamically from the release tag so it never goes stale.
RUN --mount=type=secret,id=GITHUB_TOKEN \
    python3 - <<'PYEOF'
import os, sys, urllib.request, urllib.error, json

token = open("/run/secrets/GITHUB_TOKEN").read().strip()
repo  = "AdamBHonaker/CTA-Transit-PWA"
tag   = "street-graph"
fname = "street_graph_igraph.pkl"

headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

# Resolve asset ID from release tag
req = urllib.request.Request(
    f"https://api.github.com/repos/{repo}/releases/tags/{tag}", headers=headers)
with urllib.request.urlopen(req) as r:
    release = json.load(r)

assets = release.get("assets", [])
asset  = next((a for a in assets if a["name"] == fname), None)
if asset is None:
    print(f"ERROR: asset '{fname}' not found in release '{tag}'. Available: {[a['name'] for a in assets]}")
    sys.exit(1)

asset_id = asset["id"]
print(f"Found asset '{fname}' with id={asset_id}")

# Download via GitHub API (Authorization header survives CDN redirect)
dl_headers = {"Authorization": f"token {token}", "Accept": "application/octet-stream"}
req2 = urllib.request.Request(
    f"https://api.github.com/repos/{repo}/releases/assets/{asset_id}", headers=dl_headers)
with urllib.request.urlopen(req2) as r, open(fname, "wb") as f:
    f.write(r.read())

size = os.path.getsize(fname)
print(f"{fname}: {size:,} bytes")
if size < 1_048_576:
    print(f"ERROR: file is only {size} bytes — likely a truncated download.")
    sys.exit(1)
PYEOF

CMD ["sh", "-c", "python fetch_gtfs.py && uvicorn main:app --host 0.0.0.0 --port $PORT --no-access-log --log-level warning"]
