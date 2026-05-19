# Pinned to a specific patch — `python:3.11-slim` is a moving tag that can
# silently jump patch versions on rebuild, breaking reproducibility and making
# CVE auditing harder. To pin further, append a digest discovered via
# `docker pull python:3.11.11-slim && docker inspect --format='{{index .RepoDigests 0}}' python:3.11.11-slim`
# e.g. `FROM python:3.11.11-slim@sha256:<digest>`.
FROM python:3.11.11-slim

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
#
# SECURITY NOTE (Batch 3 of security plan, 2026-05-02):
#   ARG bakes the token value into image layer metadata, where it is visible to
#   anyone who can run `docker history <image>` against a pulled image. The
#   safer pattern is BuildKit `--mount=type=secret`, but a previous attempt
#   (commit a844c89, reverted in f4172b6) failed on Railway because the
#   platform did not surface a `--secret` flag at the time.
#
#   Mitigations in place until BuildKit is wired up on Railway:
#     1. Use a fine-grained PAT scoped to "Contents: Read" on this single repo
#        only — never a classic PAT or one with org-wide access.
#     2. Rotate the PAT after any image push to a public registry, since the
#        token is recoverable from `docker history` of the pushed image.
#     3. Don't push these images outside Railway's private registry.
#
#   When Railway adds `--secret` support, swap to:
#     RUN --mount=type=secret,id=github_token \
#         GITHUB_TOKEN=$(cat /run/secrets/github_token) python3 - <<'PYEOF' ...
ARG CACHEBUST=1
ARG GITHUB_TOKEN
RUN python3 - <<'PYEOF'
import os, sys, urllib.request, json

token = os.environ.get("GITHUB_TOKEN") or ""
if not token:
    print("ERROR: GITHUB_TOKEN build arg is not set.")
    sys.exit(1)

repo  = "AdamBHonaker/The-Chicago-Routefinder"
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

# Bake a SHA-256 manifest of the downloaded pkl into the image. walking.py
# verifies this hash at runtime before calling pickle.load(), so any post-build
# tampering with the pkl (e.g. an attacker writing into a running container,
# filesystem corruption) raises long before unsafe deserialization.
# NOTE: this does NOT prove the release itself is trustworthy — for that, an
# out-of-band trusted hash would need to live in the repo and be checked here
# before bake-in. Tracked as a follow-up; the current bake-in still gates the
# unsafe pickle.load() behind an integrity check.
import hashlib
h = hashlib.sha256()
with open(fname, "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
with open(fname + ".sha256", "w") as f:
    f.write(h.hexdigest())
print(f"{fname}.sha256: {h.hexdigest()}")
PYEOF

# FEAT-019: download the chicago_geocode.db SQLite/FTS5 store from the rolling
# `geocode-db` GitHub Release at build time. Without it, Tier 1 (local OSM
# address corpus), Tier 4 (intersection lookup), and the LocationIQ response
# cache all silently no-op — see FEATURE_PLANS.md FEAT-019 for the full effect.
# Reuses the same GITHUB_TOKEN build-arg as the street_graph block above.
# CACHEBUST_GEOCODE_DB: bump in Railway → Service → Build Arguments after
# replacing the release asset to force re-download without re-downloading the
# street graph (which has its own CACHEBUST).
ARG CACHEBUST_GEOCODE_DB=1
RUN python3 - <<'PYEOF'
import hashlib, os, sqlite3, sys, urllib.request, json

token = os.environ.get("GITHUB_TOKEN") or ""
if not token:
    print("ERROR: GITHUB_TOKEN build arg is not set.")
    sys.exit(1)

repo   = "AdamBHonaker/The-Chicago-Routefinder"
tag    = "geocode-db"
db     = "chicago_geocode.db"
sha    = "chicago_geocode.db.sha256"
target = "backend/static_data/chicago_geocode.db"

os.makedirs(os.path.dirname(target), exist_ok=True)

headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
req = urllib.request.Request(
    f"https://api.github.com/repos/{repo}/releases/tags/{tag}", headers=headers)
with urllib.request.urlopen(req) as r:
    release = json.load(r)

assets = {a["name"]: a for a in release.get("assets", [])}
for name in (db, sha):
    if name not in assets:
        print(f"ERROR: '{name}' not found in release '{tag}'. Available: {list(assets)}")
        sys.exit(1)

def fetch(asset_id: int) -> bytes:
    dl_headers = {"Authorization": f"token {token}", "Accept": "application/octet-stream"}
    r = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/assets/{asset_id}", headers=dl_headers)
    with urllib.request.urlopen(r) as resp:
        return resp.read()

# Download the sidecar first; it's tiny. Trim whitespace so a trailing newline
# from a shell-redirected upload doesn't break the comparison.
expected_hash = fetch(assets[sha]["id"]).decode("ascii").strip().lower()
if len(expected_hash) != 64 or not all(c in "0123456789abcdef" for c in expected_hash):
    print(f"ERROR: '{sha}' is not a 64-char hex string: {expected_hash!r}")
    sys.exit(1)

print(f"Downloading {db} ({assets[db]['size']:,} bytes) ...")
blob = fetch(assets[db]["id"])
with open(target, "wb") as f:
    f.write(blob)

actual_hash = hashlib.sha256(blob).hexdigest()
print(f"{db}: {len(blob):,} bytes, sha256={actual_hash}")
if actual_hash != expected_hash:
    print(f"ERROR: sha256 mismatch — expected {expected_hash}, got {actual_hash}")
    sys.exit(1)

# Row-count sanity check: a corrupt download that survived sha256 (e.g. the
# release was uploaded broken) would still fail here. Thresholds match the
# FEAT-019 acceptance criteria.
conn = sqlite3.connect(target)
addr = conn.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
ints = conn.execute("SELECT COUNT(*) FROM intersections").fetchone()[0]
conn.close()
print(f"DB rowcounts — addresses: {addr:,}, intersections: {ints:,}")
if addr < 100_000:
    print(f"ERROR: addresses table has only {addr:,} rows (expected >= 100,000)")
    sys.exit(1)
if ints < 20_000:
    print(f"ERROR: intersections table has only {ints:,} rows (expected >= 20,000)")
    sys.exit(1)
print("FEAT-019: chicago_geocode.db verified and placed at", target)
PYEOF

# FEAT-003: download MaxMind GeoLite2-City DB at build time. Free tier requires
# a license key (https://www.maxmind.com/en/geolite2/signup). Pass via Railway
# Build Argument: MAXMIND_LICENSE_KEY=<key>. If unset, the build proceeds
# without the DB and geography counting silently no-ops at runtime.
# Refreshed monthly: MaxMind updates on Tuesdays — redeploy at least monthly.
ARG MAXMIND_LICENSE_KEY=""
RUN python3 - <<'PYEOF'
import os, sys, tarfile, urllib.request, io

key = os.environ.get("MAXMIND_LICENSE_KEY", "").strip()
if not key:
    print("[geoip] MAXMIND_LICENSE_KEY not set — skipping GeoLite2-City download.")
    sys.exit(0)

url = (
    "https://download.maxmind.com/app/geoip_download"
    f"?edition_id=GeoLite2-City&license_key={key}&suffix=tar.gz"
)
print("[geoip] Downloading GeoLite2-City ...")
with urllib.request.urlopen(url) as r:
    blob = r.read()
print(f"[geoip] {len(blob):,} bytes; extracting ...")
with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as t:
    member = next((m for m in t.getmembers() if m.name.endswith("GeoLite2-City.mmdb")), None)
    if member is None:
        print("[geoip] ERROR: GeoLite2-City.mmdb not found in archive")
        sys.exit(1)
    f = t.extractfile(member)
    if f is None:
        print("[geoip] ERROR: extractfile returned None")
        sys.exit(1)
    with open("/app/GeoLite2-City.mmdb", "wb") as out:
        out.write(f.read())
size = os.path.getsize("/app/GeoLite2-City.mmdb")
print(f"[geoip] /app/GeoLite2-City.mmdb: {size:,} bytes")
if size < 1_000_000:
    print("[geoip] ERROR: DB suspiciously small")
    sys.exit(1)
PYEOF

CMD ["sh", "-c", "python fetch_gtfs.py && uvicorn main:app --host 0.0.0.0 --port $PORT --no-access-log --log-level warning"]
