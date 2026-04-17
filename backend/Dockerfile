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

# NOTE: street_graph.graphml is intentionally NOT downloaded at build time.
# The file lives in Git LFS but GitHub's LFS media endpoint returns 404
# (likely bandwidth-quota exhausted on the free tier). The runtime falls back
# to Haversine straight-line walking estimates via walking.py — see commit
# 954c7fa ("Fix OOM crash: use Haversine for intermodal edges, defer street
# graph load"). Walking times are degraded but the app deploys and serves.
#
# To restore street-network routing, see Feature K in
# FEATURE_IMPLEMENTATION_PLANS.md (host the 120 MB graphml as a GitHub
# Release asset / S3 / R2 / Railway volume and re-enable the curl step
# preserved below).
#
# --- PRESERVED FOR FUTURE RESTORATION (Feature K) ---
# ARG STREET_GRAPH_URL=https://media.githubusercontent.com/media/AdamBHonaker/CTA-Transit-PWA/main/backend/street_graph.graphml
# RUN curl -fSL --retry 3 --retry-delay 2 -o street_graph.graphml "$STREET_GRAPH_URL" \
#     && SIZE=$(wc -c < street_graph.graphml) \
#     && echo "street_graph.graphml: $SIZE bytes" \
#     && if [ "$SIZE" -lt 1048576 ]; then \
#          echo "ERROR: street_graph.graphml is only $SIZE bytes — likely an LFS pointer or quota-exhausted response."; \
#          head -c 500 street_graph.graphml; \
#          exit 1; \
#        fi \
#     && if head -c 200 street_graph.graphml | grep -q "git-lfs.github.com"; then \
#          echo "ERROR: street_graph.graphml is an LFS pointer stub, not the real file."; \
#          exit 1; \
#        fi
# --- END PRESERVED ---

CMD ["sh", "-c", "python fetch_gtfs.py && uvicorn main:app --host 0.0.0.0 --port $PORT --no-access-log --log-level warning"]
