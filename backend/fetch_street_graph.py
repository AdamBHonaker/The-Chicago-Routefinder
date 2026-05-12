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

Geographic scope: two boxes unioned into a single polygon (they share an edge).
  - Main Chicago box: Howard St (N) → ~100th St (S) | Lakefront (E) → Austin Blvd (W)
  - Purple Line corridor: narrow Evanston strip (Howard → Linden) covering the 9
    Evanston Purple Line stations without pulling in all of Evanston (~1.4 mi wide)
Points outside fall back to Haversine estimates. Pace and Metra service areas are
out of scope. Bounds are defined in utils.py (STREET_GRAPH_* / PURPLE_LINE_CORRIDOR_*).

NOTE: Both `street_graph.graphml` and `street_graph_igraph.pkl` are gitignored.
For production, the pkl is uploaded as an asset on the `street-graph` GitHub
Release and pulled at Docker build time (see backend/Dockerfile). For local
development, run this script once to build both files from OpenStreetMap.
"""

import os
import pickle
import sys
import time
from pathlib import Path

from utils import (
    STREET_GRAPH_SOUTH, STREET_GRAPH_NORTH, STREET_GRAPH_WEST, STREET_GRAPH_EAST,
    PURPLE_LINE_CORRIDOR_SOUTH, PURPLE_LINE_CORRIDOR_NORTH,
    PURPLE_LINE_CORRIDOR_WEST, PURPLE_LINE_CORRIDOR_EAST,
)

GRAPH_PATH  = Path(__file__).parent / "street_graph.graphml"
IGRAPH_PATH = Path(__file__).parent / "street_graph_igraph.pkl"

# ---------------------------------------------------------------------------
# Progress reporting helpers
#
# Each major phase of the build is wrapped in _step_begin / _step_end so the
# user can see which step is running, how long it has taken, and (if psutil is
# installed) the current and peak resident-set-size of this process. This is
# the diagnostic surface for spotting bottlenecks on slower hardware.
# ---------------------------------------------------------------------------
try:
    import psutil
    _PROC = psutil.Process()
    def _rss_mb() -> float | None:
        return _PROC.memory_info().rss / (1024 * 1024)
except ImportError:
    def _rss_mb() -> float | None:
        return None

_step_state = {"step": 0, "total": 0, "t0": None, "step_t0": None, "peak_rss": 0.0}


def _fmt_elapsed(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _set_step_total(total: int) -> None:
    _step_state["total"] = total
    _step_state["step"] = 0
    _step_state["t0"] = time.monotonic()
    _step_state["peak_rss"] = 0.0


def _step_begin(label: str) -> None:
    if _step_state["t0"] is None:
        _step_state["t0"] = time.monotonic()
    _step_state["step"] += 1
    _step_state["step_t0"] = time.monotonic()
    elapsed = time.monotonic() - _step_state["t0"]
    rss = _rss_mb()
    if rss is not None:
        _step_state["peak_rss"] = max(_step_state["peak_rss"], rss)
    rss_str = f" RSS={rss:.0f}MB peak={_step_state['peak_rss']:.0f}MB" if rss is not None else ""
    total = _step_state["total"] or "?"
    print(f"[{_step_state['step']}/{total} t+{_fmt_elapsed(elapsed)}{rss_str}] {label}...")


def _step_end(detail: str = "") -> None:
    step_elapsed = time.monotonic() - (_step_state["step_t0"] or time.monotonic())
    rss = _rss_mb()
    if rss is not None:
        _step_state["peak_rss"] = max(_step_state["peak_rss"], rss)
    rss_str = f" peak={_step_state['peak_rss']:.0f}MB" if rss is not None else ""
    suffix = f" -- {detail}" if detail else ""
    print(f"  done in {_fmt_elapsed(step_elapsed)}{rss_str}{suffix}")

def _build_coverage_polygon():
    """
    Build the polygon that defines the street graph's geographic scope:
    a main Chicago box (south of Howard) plus a narrow Evanston corridor that
    covers the 9 Purple Line stations without pulling in all of Evanston.
    """
    # The two boxes share an edge along y=STREET_GRAPH_NORTH (=PURPLE_LINE_CORRIDOR_SOUTH),
    # which makes a MultiPolygon invalid (components may only touch at finite points).
    # unary_union merges them into a single Polygon along the shared edge.
    from shapely.geometry import box
    from shapely.ops import unary_union
    main = box(STREET_GRAPH_WEST, STREET_GRAPH_SOUTH, STREET_GRAPH_EAST, STREET_GRAPH_NORTH)
    corridor = box(PURPLE_LINE_CORRIDOR_WEST, PURPLE_LINE_CORRIDOR_SOUTH,
                   PURPLE_LINE_CORRIDOR_EAST, PURPLE_LINE_CORRIDOR_NORTH)
    return unary_union([main, corridor])

COVERAGE_POLYGON = _build_coverage_polygon()


def _is_lfs_pointer(path: Path) -> bool:
    """Return True if the file is a Git LFS pointer stub rather than real data."""
    try:
        with open(path, "rb") as f:
            first_line = f.readline(200)
        return first_line.startswith(b"version https://git-lfs.github.com")
    except Exception:
        return False


def _needs_download() -> bool:
    """Return True if the graph file is absent, empty, or an LFS pointer."""
    if not GRAPH_PATH.exists():
        return True
    if GRAPH_PATH.stat().st_size < 1024:
        return True
    if _is_lfs_pointer(GRAPH_PATH):
        return True
    return False


def download_and_save(verbose: bool = False) -> None:
    try:
        import osmnx as ox
    except ImportError:
        print("osmnx is not installed. Run: pip install osmnx")
        sys.exit(1)

    # Always emit OSMnx's own internal logs to the console -- gives visibility
    # into Overpass round-trip timing, retries, and consolidation sub-steps.
    # The `verbose` parameter is currently a no-op (kept for API compatibility);
    # flip it off here if console output ever becomes too noisy.
    ox.settings.log_console = True
    _ = verbose

    # 7 steps: download, filter, project-forward, consolidate, project-back, save graphml, build pickle
    _set_step_total(7)
    bounds = COVERAGE_POLYGON.bounds  # (minx, miny, maxx, maxy)
    print(
        f"Coverage: main box (S={STREET_GRAPH_SOUTH}, N={STREET_GRAPH_NORTH}, "
        f"W={STREET_GRAPH_WEST}, E={STREET_GRAPH_EAST}) + "
        f"Purple Line corridor (S={PURPLE_LINE_CORRIDOR_SOUTH}, N={PURPLE_LINE_CORRIDOR_NORTH}, "
        f"W={PURPLE_LINE_CORRIDOR_WEST}, E={PURPLE_LINE_CORRIDOR_EAST})\n"
        f"Combined envelope: west={bounds[0]}, south={bounds[1]}, east={bounds[2]}, north={bounds[3]}\n"
    )

    ox.settings.max_query_area_size = 2_500_000_000  # ~2,500 km²; restores pre-2.x default so bbox is fetched in one pass

    _step_begin("Querying OpenStreetMap for the Chicago walk network")
    G = ox.graph_from_polygon(COVERAGE_POLYGON, network_type="walk")
    raw_nodes = G.number_of_nodes()
    raw_edges = G.number_of_edges()
    _step_end(f"{raw_nodes:,} nodes, {raw_edges:,} edges")

    _step_begin("Filtering service/alley edges (not walkable)")
    _WALK_EXCLUDED_HIGHWAYS = {"service", "alley"}
    def _hw(data) -> str:
        val = data.get("highway", "")
        if isinstance(val, list): val = val[0] if val else ""
        return (val or "").strip()
    svc_edges = [
        (u, v, k) for u, v, k, data in G.edges(keys=True, data=True)
        if _hw(data) in _WALK_EXCLUDED_HIGHWAYS
    ]
    if svc_edges:
        G.remove_edges_from(svc_edges)
    _step_end(f"removed {len(svc_edges):,} service/alley edges")

    _step_begin("Projecting graph to UTM for metric consolidation")
    G_proj = ox.project_graph(G)
    _step_end()

    _step_begin("Consolidating intersections (tolerance=10 m) -- this is the slow step")
    G_proj = ox.consolidate_intersections(G_proj, tolerance=10, rebuild_graph=True, dead_ends=False)
    cons_nodes = G_proj.number_of_nodes()
    cons_edges = G_proj.number_of_edges()
    node_pct = (raw_nodes - cons_nodes) / raw_nodes * 100
    edge_pct = (raw_edges - cons_edges) / raw_edges * 100
    _step_end(
        f"{cons_nodes:,} nodes (-{raw_nodes - cons_nodes:,}, {node_pct:.1f}%), "
        f"{cons_edges:,} edges (-{raw_edges - cons_edges:,}, {edge_pct:.1f}%)"
    )

    _step_begin("Reprojecting back to EPSG:4326 (lat/lon)")
    G = ox.project_graph(G_proj, to_crs="epsg:4326")
    _step_end()

    _step_begin(f"Saving graphml to {GRAPH_PATH.name}")
    ox.save_graphml(G, GRAPH_PATH)
    size_mb = GRAPH_PATH.stat().st_size / (1024 * 1024)
    _step_end(f"{size_mb:.1f} MB written")

    _save_igraph_artifact(G)


def _save_igraph_artifact(G_nx) -> None:
    """
    Convert the NetworkX MultiDiGraph to a compact igraph artifact and pickle it.

    The pickle stores the igraph.Graph with geometry pre-parsed as [(lon,lat),...] lists
    so runtime walking.py loads it directly without NetworkX or GraphML parsing.
    """
    try:
        import igraph as ig
        from shapely import wkt as shapely_wkt

        _step_begin("Converting to compact igraph artifact")

        nodes = list(G_nx.nodes())
        node_to_idx = {n: i for i, n in enumerate(nodes)}

        edges: list[tuple[int, int]] = []
        attr_length:   list[float]             = []
        attr_name:     list[str]               = []
        attr_highway:  list[str]               = []
        attr_footway:  list[str]               = []
        attr_geometry: list[list | None]       = []

        def _first_str(val) -> str:
            if isinstance(val, list): val = val[0] if val else ""
            return (val or "").strip()

        for u, v, data in G_nx.edges(data=True):
            edges.append((node_to_idx[u], node_to_idx[v]))
            attr_length.append(float(data.get("length") or 0.0))
            attr_name.append(_first_str(data.get("name", "")))
            attr_highway.append(_first_str(data.get("highway", "")))
            attr_footway.append(_first_str(data.get("footway", "")))

            geom = data.get("geometry")
            if geom is not None and hasattr(geom, "coords"):
                attr_geometry.append(list(geom.coords))
            elif isinstance(geom, str) and geom:
                try:
                    attr_geometry.append(list(shapely_wkt.loads(geom).coords))
                except Exception:
                    attr_geometry.append(None)
            else:
                attr_geometry.append(None)

        ig_graph = ig.Graph(
            n=len(nodes),
            edges=edges,
            directed=True,
            vertex_attrs={
                "x": [float(G_nx.nodes[n].get("x", 0.0)) for n in nodes],
                "y": [float(G_nx.nodes[n].get("y", 0.0)) for n in nodes],
            },
            edge_attrs={
                "length":   attr_length,
                "name":     attr_name,
                "highway":  attr_highway,
                "footway":  attr_footway,
                "geometry": attr_geometry,
            },
        )

        # Collapse opposing directed edges into a single undirected edge at build
        # time so _load_graph() can skip this step at runtime — halves edge count
        # and associated attribute memory.  Two opposing edges for the same street
        # share name/highway/footway/geometry so "first" is lossless; length takes
        # the minimum of the pair (they differ only by floating-point rounding).
        pre_e = ig_graph.ecount()
        combine: dict[str, str] = {"length": "min"}
        for attr in ("name", "highway", "footway", "geometry"):
            combine[attr] = "first"
        ig_graph.to_undirected(mode="collapse", combine_edges=combine)
        print(f"  [igraph] directed→undirected: {pre_e:,} → {ig_graph.ecount():,} edges")

        with open(IGRAPH_PATH, "wb") as f:
            pickle.dump({"graph": ig_graph}, f, protocol=pickle.HIGHEST_PROTOCOL)

        artifact_mb = IGRAPH_PATH.stat().st_size / (1024 * 1024)
        _step_end(f"{artifact_mb:.1f} MB, {ig_graph.vcount():,} vertices, {ig_graph.ecount():,} edges")

    except Exception as e:
        print(f"[warning] igraph artifact creation failed ({type(e).__name__}: {e}) -- runtime will fall back to graphml")


# Public Overpass mirrors. Keys are the short names users pass to --mirror;
# values are the full API endpoint URLs. The canonical instance is the default
# unless the user explicitly chooses otherwise.
#
# Use a mirror only as an occasional escape valve when the canonical instance
# has rate-limited your IP. Mirrors are donated infrastructure too -- don't
# hammer them with retry loops.
OVERPASS_MIRRORS: dict[str, str] = {
    "default": "https://overpass-api.de/api/interpreter",
    "kumi":    "https://overpass.kumi.systems/api/interpreter",
    "france":  "https://overpass.openstreetmap.fr/api/interpreter",
    "russia":  "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
}


def _parse_mirror_arg(argv: list[str]) -> str | None:
    """Return the chosen Overpass URL (or None for the OSMnx default).

    Accepts --mirror=NAME, --mirror NAME, or a full https URL in place of NAME.
    """
    for i, arg in enumerate(argv):
        value: str | None = None
        if arg.startswith("--mirror="):
            value = arg.split("=", 1)[1]
        elif arg == "--mirror" and i + 1 < len(argv):
            value = argv[i + 1]
        if value is None:
            continue
        if value.startswith("http://") or value.startswith("https://"):
            return value
        if value in OVERPASS_MIRRORS:
            return OVERPASS_MIRRORS[value]
        print(f"Unknown --mirror value: {value!r}")
        print(f"  Choose one of: {', '.join(OVERPASS_MIRRORS)}  (or pass a full URL)")
        sys.exit(2)
    return None


def _file_report(path: Path) -> str:
    """One-line human description of a file's status."""
    if not path.exists():
        return "missing"
    if _is_lfs_pointer(path):
        return "Git LFS pointer stub (no real data)"
    size_mb = path.stat().st_size / (1024 * 1024)
    if path.stat().st_size < 1024:
        return f"present but only {path.stat().st_size} bytes (corrupt)"
    return f"present ({size_mb:.1f} MB)"


def _rebuild_pickle_from_graphml() -> None:
    """Skip the download + consolidation; just rebuild the pickle from the cached graphml."""
    try:
        import osmnx as ox
    except ImportError:
        print("osmnx is not installed. Run: pip install osmnx")
        sys.exit(1)
    _set_step_total(2)
    _step_begin(f"Loading cached graphml from {GRAPH_PATH.name}")
    G = ox.load_graphml(GRAPH_PATH)
    _step_end(f"{G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
    _save_igraph_artifact(G)


if __name__ == "__main__":
    force = "--force" in sys.argv
    verbose = "--verbose" in sys.argv
    mirror_url = _parse_mirror_arg(sys.argv)
    if mirror_url:
        try:
            import osmnx as ox
        except ImportError:
            print("osmnx is not installed. Run: pip install osmnx")
            sys.exit(1)
        ox.settings.overpass_url = mirror_url
        print(f"Using non-default Overpass mirror: {mirror_url}\n")

    graphml_usable = GRAPH_PATH.exists() and GRAPH_PATH.stat().st_size >= 1024 and not _is_lfs_pointer(GRAPH_PATH)
    pickle_usable = IGRAPH_PATH.exists() and IGRAPH_PATH.stat().st_size >= 1024

    print("Current files in backend/:")
    print(f"  street_graph.graphml      {_file_report(GRAPH_PATH)}")
    print(f"  street_graph_igraph.pkl   {_file_report(IGRAPH_PATH)}")
    print()

    # --force always means: full rebuild, no questions. Used by CI / non-interactive callers.
    if force:
        print("--force given: doing a full rebuild (download + consolidation + pickle).\n")
        if GRAPH_PATH.exists():
            GRAPH_PATH.unlink()
        download_and_save(verbose=verbose)
        sys.exit(0)

    # CI/Railway: never prompt. If the graph is missing, download; otherwise keep what's there.
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("CI"):
        if not graphml_usable:
            print("Non-interactive environment, graph missing -- downloading.\n")
            if GRAPH_PATH.exists():
                GRAPH_PATH.unlink()
            download_and_save(verbose=verbose)
        else:
            print("Non-interactive environment, graph present -- keeping it. (Pass --force to re-download.)")
        sys.exit(0)

    # Interactive menu. Build the option list dynamically based on what's available.
    print("What would you like to do?")
    options: list[tuple[str, str, str]] = []  # (key, label, action)
    if graphml_usable:
        options.append(("1", "Rebuild ONLY the pickle from the existing graphml (fast, ~1 min)", "pickle"))
        options.append(("2", "Rebuild BOTH (re-download graphml from OSM, then rebuild pickle) -- slow", "both"))
    else:
        options.append(("1", "Create a fresh graph (download from OSM, then build pickle) -- slow", "both"))
    options.append(("q", "Quit without changes", "quit"))

    for key, label, _ in options:
        print(f"  [{key}] {label}")
    print()

    valid_keys = {key for key, _, _ in options}
    while True:
        answer = input("Choice: ").strip().lower()
        if answer in valid_keys:
            break
        print(f"  Please enter one of: {', '.join(sorted(valid_keys))}")

    action = next(a for k, _, a in options if k == answer)

    if action == "quit":
        print("Aborted. No changes made.")
        sys.exit(0)
    if action == "pickle":
        print()
        _rebuild_pickle_from_graphml()
        sys.exit(0)
    if action == "both":
        print()
        if GRAPH_PATH.exists():
            GRAPH_PATH.unlink()
        download_and_save(verbose=verbose)
        sys.exit(0)
