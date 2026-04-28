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

# Download the pre-built street graph from GitHub Releases (Feature K).
# Repo is private — pass a GitHub PAT (Contents:Read) as a Railway build arg:
#   Service → Settings → Build → Build Arguments → GITHUB_TOKEN=<PAT>
# Uses the GitHub API asset endpoint (not the browser redirect URL) so the
# Authorization header survives the CDN redirect for private-repo assets.
# Asset ID 407136213 = street_graph.graphml in release street-graph-v1.
# Update STREET_GRAPH_ASSET_ID when uploading a new release (v2, v3, ...).
ARG STREET_GRAPH_ASSET_ID=407136213
ARG GITHUB_TOKEN
RUN set -eu; \
    ASSET_URL="https://api.github.com/repos/AdamBHonaker/CTA-Transit-PWA/releases/assets/${STREET_GRAPH_ASSET_ID}"; \
    curl -fSL --retry 3 --retry-delay 2 \
         -H "Authorization: token $GITHUB_TOKEN" \
         -H "Accept: application/octet-stream" \
         -o street_graph.graphml "$ASSET_URL" \
    && SIZE=$(wc -c < street_graph.graphml) \
    && echo "street_graph.graphml: $SIZE bytes" \
    && if [ "$SIZE" -lt 1048576 ]; then \
         echo "ERROR: street_graph.graphml is only $SIZE bytes — likely an LFS pointer or truncated download."; \
         head -c 500 street_graph.graphml; \
         exit 1; \
       fi \
    && if head -c 200 street_graph.graphml | grep -q "git-lfs.github.com"; then \
         echo "ERROR: street_graph.graphml is an LFS pointer stub, not the real file."; \
         exit 1; \
       fi

CMD ["sh", "-c", "python fetch_gtfs.py && uvicorn main:app --host 0.0.0.0 --port $PORT --no-access-log --log-level warning"]
