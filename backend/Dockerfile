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

# Replace the Git LFS pointer stub with the real street-network graph.
# Pulled from GitHub's LFS media endpoint at build time so the file is baked
# into the image and the runtime never has to rebuild it from OpenStreetMap
# (which OOM-kills on the current Railway memory tier).
#
# When the Railway memory tier is increased, this RUN step can be removed and
# `python fetch_street_graph.py` re-added to the start command in railway.toml
# as a self-healing fallback.
ARG STREET_GRAPH_URL=https://media.githubusercontent.com/media/AdamBHonaker/CTA-Transit-PWA/main/backend/street_graph.graphml
RUN curl -fSL --retry 3 --retry-delay 2 -o street_graph.graphml "$STREET_GRAPH_URL" \
    && head -c 200 street_graph.graphml | grep -qv "git-lfs.github.com" \
    && echo "street_graph.graphml: $(wc -c < street_graph.graphml) bytes"

CMD ["sh", "-c", "python fetch_gtfs.py && uvicorn main:app --host 0.0.0.0 --port $PORT --no-access-log --log-level warning"]
