"""
Downloads the Chicago pedestrian street network from OpenStreetMap
and caches it as backend/street_graph.graphml.

Run this script:
  - On initial setup (before starting the server for the first time)
  - If the street network needs refreshing (OSM data changes rarely)

Usage:
  python fetch_street_graph.py

The download queries the OpenStreetMap Overpass API — it takes 3–10 minutes
depending on your connection. After the first run the server loads from the
local cache file in under a second.

Geographic scope: Howard St (north) to 20th St (south), lakefront (east) to
Pulaski Rd (west). Covers the current CTA service area with accurate
street-network walk times. Points outside fall back to Haversine estimates.

NOTE: This file is committed to the repo (backend/street_graph.graphml) so
Railway does not need to download it at deploy time. Re-run this script locally
whenever the bounding box changes, then commit the updated graphml.
"""

import os
import sys
from pathlib import Path

GRAPH_PATH = Path(__file__).parent / "street_graph.graphml"

# Bounding box: (left/west, bottom/south, right/east, top/north)
# OSMnx 2.x format
# Coverage: Howard St (north) → 20th St (south) | Lakefront (east) → Pulaski Rd (west)
# TODO: expand south boundary toward 50th St when Railway memory allows
BBOX = (-87.7260, 41.8560, -87.5200, 42.0190)


def download_and_save() -> None:
    try:
        import osmnx as ox
    except ImportError:
        print("osmnx is not installed. Run: pip install osmnx")
        sys.exit(1)

    print("Querying OpenStreetMap for the full Chicago walk network...")
    print(f"  Bounding box: west={BBOX[0]}, south={BBOX[1]}, east={BBOX[2]}, north={BBOX[3]}")
    print("  This usually takes 1–3 minutes.\n")

    G = ox.graph_from_bbox(bbox=BBOX, network_type="walk")

    node_count = G.number_of_nodes()
    edge_count = G.number_of_edges()
    print(f"Network downloaded: {node_count:,} nodes, {edge_count:,} edges")

    print(f"Saving to {GRAPH_PATH} ...")
    ox.save_graphml(G, GRAPH_PATH)

    size_mb = GRAPH_PATH.stat().st_size / (1024 * 1024)
    print(f"Saved ({size_mb:.1f} MB). Street graph is ready.")


if __name__ == "__main__":
    # In non-interactive environments (Railway, CI), skip the prompt and always
    # re-download so the deploy never hangs waiting for input.
    force = "--force" in sys.argv or bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("CI"))
    if GRAPH_PATH.exists():
        size_mb = GRAPH_PATH.stat().st_size / (1024 * 1024)
        if force:
            print(f"Street graph exists ({size_mb:.1f} MB). Re-downloading (non-interactive mode).")
        else:
            print(f"Street graph already exists ({size_mb:.1f} MB) at {GRAPH_PATH}.")
            answer = input("Re-download and overwrite? [y/N]: ").strip().lower()
            if answer != "y":
                print("Aborted. Existing graph kept.")
                sys.exit(0)
        GRAPH_PATH.unlink()
        print("Old graph removed.")

    download_and_save()
