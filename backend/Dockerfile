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
# The repo is private, so a GitHub personal access token (read:packages or
# contents scope) must be passed as the GITHUB_TOKEN build argument.
# In Railway: Settings → Build → Build Arguments → GITHUB_TOKEN=<PAT>
#
# To update the graph (e.g. after NorthExpansion / SouthExpansion):
#   1. Run: python fetch_street_graph.py --force  (from backend/)
#   2. Create a new release tag (e.g. street-graph-v2) via gh release create
#   3. Update STREET_GRAPH_URL below to the new tag's asset URL.
ARG STREET_GRAPH_URL=https://github.com/AdamBHonaker/CTA-Transit-PWA/releases/download/street-graph-v1/street_graph.graphml
ARG GITHUB_TOKEN
RUN set -eu; \
    if [ -n "${GITHUB_TOKEN:-}" ]; then \
      curl -fSL --retry 3 --retry-delay 2 \
           -H "Authorization: Bearer $GITHUB_TOKEN" \
           -o street_graph.graphml "$STREET_GRAPH_URL"; \
    else \
      curl -fSL --retry 3 --retry-delay 2 \
           -o street_graph.graphml "$STREET_GRAPH_URL"; \
    fi \
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
