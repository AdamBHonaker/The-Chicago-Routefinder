"""
Public-stats projection (FEAT-009).

Owns the *one* projection from internal admin shapes to the safe-to-publish
shape served at ``/stats/*``. Centralising the projection here is the
load-bearing safety check for the public dashboard: any field that could
re-identify a rare visitor must be stripped *here* before going to the wire.
``backend/tests/test_public_stats.py`` asserts that no admin-only field leaks
through these projections.

Phase 1 panels: DAU + Chicago-metro share.
Phase 2 panels: Sessions/bounce/duration (FEAT-001), hour-of-day (FEAT-004),
                device class (FEAT-005), traffic sources (FEAT-008).
Phase 3 panels: Engagement events (FEAT-006), session funnel (FEAT-007).

Maintenance:
  * Adding a new panel: add a ``project_<feat>`` function here, add a
    no-leak assertion in ``test_public_stats.py`` covering the *exact* set
    of public field names, then add the matching ``/stats/<panel>`` route.
  * Removing a panel (post-launch privacy concern): the projection function
    should return ``{"available": False, "reason": "<short>"}`` so the
    dashboard panel renders an explanatory placeholder rather than 404.
"""

from __future__ import annotations

import funnel as _funnel_mod
import retention as _retention_mod

# Whitelisted public field names per panel. Reject-by-default keeps a
# careless future field addition (e.g. raw IP hashes, raw UA strings) from
# leaking through automatically.
_DAU_PUBLIC_FIELDS = frozenset({"date", "count"})
_GEO_METRO_PUBLIC_FIELDS = frozenset({"date", "metro", "total", "share_pct"})
_SESSIONS_PUBLIC_FIELDS = frozenset({
    "date", "sessions", "avg_duration_seconds", "bounce_rate_pct",
})
_HOURLY_PUBLIC_FIELDS = frozenset({"date", "hours", "total"})
_DEVICES_PUBLIC_FIELDS = frozenset({"date", "mobile", "tablet", "desktop", "total"})
# Referrer ``other`` long-tail hostnames are admin-only — a low-volume host
# could identify a single visitor's prior page. Public exposes only the four
# top-level buckets and a sum.
_REFERRERS_PUBLIC_FIELDS = frozenset({
    "date", "direct", "search", "social", "other", "total",
})
# FEAT-006 events (Phase 3 panel #1). The public surface advertises the four
# headline event volumes — recommend_submitted, recommend_returned,
# route_selected, trip_completed — because those are the numbers an
# advertiser can interpret. Operational/internal events (app_loaded,
# map_opened, start_route_tapped, house_ad_clicked) stay admin-only so the
# public dashboard isn't a vector for inferring per-user navigation patterns.
_EVENTS_PUBLIC_FIELDS = frozenset({
    "date",
    "recommend_submitted",
    "recommend_returned",
    "route_selected",
    "trip_completed",
    "total",
})
_EVENTS_PUBLIC_KEYS = ("recommend_submitted", "recommend_returned",
                       "route_selected", "trip_completed")
# FEAT-007 funnel panel. The public surface exposes stage names (fixed list,
# not PII), the at-least counts per stage, and the headline result rate.
_FUNNEL_PUBLIC_FIELDS = frozenset({"date", "stages", "counts", "result_rate_pct"})
# FEAT-002 retention panel. Exposes only the aggregate split and headline pct;
# the Bloom filter diagnostics (capacity, utilisation) stay admin-only.
_RETENTION_PUBLIC_FIELDS = frozenset({"date", "new", "returning", "total", "returning_pct"})

PUBLIC_FIELD_WHITELIST: dict[str, frozenset[str]] = {
    "dau_day": _DAU_PUBLIC_FIELDS,
    "geo_metro_day": _GEO_METRO_PUBLIC_FIELDS,
    "sessions_day": _SESSIONS_PUBLIC_FIELDS,
    "hourly_day": _HOURLY_PUBLIC_FIELDS,
    "devices_day": _DEVICES_PUBLIC_FIELDS,
    "referrers_day": _REFERRERS_PUBLIC_FIELDS,
    "events_day": _EVENTS_PUBLIC_FIELDS,
    "funnel_day": _FUNNEL_PUBLIC_FIELDS,
    "retention_day": _RETENTION_PUBLIC_FIELDS,
}


def project_dau(raw: dict[str, int]) -> dict:
    """Project ``dau.get_counts()`` (``{date: count}``) to the public shape."""
    days = [{"date": d, "count": int(c)} for d, c in sorted(raw.items())]
    today = days[-1] if days else None
    return {"days": days, "today": today}


def project_geography(raw_metro: dict[str, dict[str, float | int]]) -> dict:
    """Project ``geography.get_metro_summary()`` to the public shape.

    Strips the per-city table entirely — only the metro rollup leaves the
    server. Per-city numbers stay admin-only because a rare suburb's count
    can identify a single visitor even after the privacy floor is applied.
    """
    days: list[dict] = []
    for date, summary in sorted(raw_metro.items()):
        days.append({
            "date": date,
            "metro": int(summary.get("metro", 0) or 0),
            "total": int(summary.get("total", 0) or 0),
            "share_pct": float(summary.get("share_pct", 0.0) or 0.0),
        })
    today = days[-1] if days else None
    return {"days": days, "today": today}


def project_sessions(raw: dict[str, dict[str, float | int]]) -> dict:
    """Project ``sessions.get_counts()`` to the public shape.

    Drops the raw ``total_duration_seconds`` and ``bounces`` integers — only
    the derived per-session averages and the session count are public, since
    the raw numbers add noise for advertisers without adding insight.
    """
    days: list[dict] = []
    for date, bucket in sorted(raw.items()):
        days.append({
            "date": date,
            "sessions": int(bucket.get("sessions", 0) or 0),
            "avg_duration_seconds": float(bucket.get("avg_duration_seconds", 0.0) or 0.0),
            "bounce_rate_pct": float(bucket.get("bounce_rate_pct", 0.0) or 0.0),
        })
    today = days[-1] if days else None
    return {"days": days, "today": today}


def project_hourly(raw: dict[str, list[int]]) -> dict:
    """Project ``hourly.get_counts()`` to the public shape.

    Each day exposes the 24-int array plus a ``total`` for sanity. Today's
    array is the headline, with the list of past days available for trend.
    """
    days: list[dict] = []
    for date, arr in sorted(raw.items()):
        if not isinstance(arr, list) or len(arr) != 24:
            continue
        ints = [int(v) for v in arr]
        days.append({"date": date, "hours": ints, "total": sum(ints)})
    today = days[-1] if days else None
    return {"days": days, "today": today}


def project_devices(raw: dict[str, dict[str, int]]) -> dict:
    """Project ``devices.get_counts()`` to the public shape.

    Drops ``bot`` and ``unknown`` from the public output — bots are excluded
    from the engagement narrative and ``unknown`` is just noise. Total is
    the sum of the three published buckets so the dashboard can render a
    proper percentage split.
    """
    days: list[dict] = []
    for date, bucket in sorted(raw.items()):
        m = int(bucket.get("mobile", 0) or 0)
        t = int(bucket.get("tablet", 0) or 0)
        d = int(bucket.get("desktop", 0) or 0)
        days.append({
            "date": date,
            "mobile": m, "tablet": t, "desktop": d,
            "total": m + t + d,
        })
    today = days[-1] if days else None
    return {"days": days, "today": today}


def project_events(raw: dict[str, dict[str, int]]) -> dict:
    """Project ``events.get_counts()`` to the public shape.

    Drops admin-only event names (``app_loaded``, ``map_opened``,
    ``start_route_tapped``, ``house_ad_clicked``). ``total`` is the sum of
    only the published event volumes — using the full admin total would let
    a viewer back out the dropped event counts via subtraction.
    """
    days: list[dict] = []
    for date, day in sorted(raw.items()):
        if not isinstance(day, dict):
            continue
        entry: dict = {"date": date}
        total = 0
        for k in _EVENTS_PUBLIC_KEYS:
            v = int(day.get(k, 0) or 0)
            entry[k] = v
            total += v
        entry["total"] = total
        days.append(entry)
    today = days[-1] if days else None
    return {"days": days, "today": today}


def project_referrers(raw: dict[str, dict]) -> dict:
    """Project ``referrers.get_counts()`` to the public shape.

    Collapses the per-hostname ``other`` table into a single integer; the
    long tail of hostnames stays admin-only because a rare host could
    identify a single visitor's prior page.
    """
    days: list[dict] = []
    for date, bucket in sorted(raw.items()):
        direct = int(bucket.get("direct", 0) or 0)
        search = int(bucket.get("search", 0) or 0)
        social = int(bucket.get("social", 0) or 0)
        other_table = bucket.get("other", {}) or {}
        other = sum(int(v) for v in other_table.values()) if isinstance(other_table, dict) else 0
        days.append({
            "date": date,
            "direct": direct, "search": search, "social": social, "other": other,
            "total": direct + search + social + other,
        })
    today = days[-1] if days else None
    return {"days": days, "today": today}


def project_funnel(raw: dict[str, list[int]]) -> dict:
    """Project ``funnel.get_counts()`` to the public shape.

    Each day in the response contains:
    - ``stages``: the canonical funnel stage names (fixed list, not PII).
    - ``counts``: the at-least count per stage (same index as ``stages``).
    - ``result_rate_pct``: the advertiser headline — percentage of sessions
      that reached ``recommend_returned`` (stage 2) relative to ``app_loaded``
      (stage 0). Rounded to one decimal place.

    Days with malformed arrays (wrong length) are silently skipped.
    """
    stages = list(_funnel_mod.FUNNEL_STAGES)
    n = len(stages)
    days: list[dict] = []
    for date, arr in sorted(raw.items()):
        if not isinstance(arr, list) or len(arr) != n:
            continue
        counts = [max(0, int(v)) for v in arr]
        started = counts[0]
        got_result = counts[2] if n > 2 else 0
        result_rate = round(100.0 * got_result / started, 1) if started else 0.0
        days.append({
            "date": date,
            "stages": stages,
            "counts": counts,
            "result_rate_pct": result_rate,
        })
    today = days[-1] if days else None
    return {"days": days, "today": today}


def project_retention(raw: dict[str, dict]) -> dict:
    """Project ``retention.get_counts()`` to the public shape.

    Drops Bloom filter diagnostics (capacity, utilisation_pct) — those are
    admin-only operational data. The public surface is the daily split of
    new vs returning visitors and the headline returning percentage.
    """
    days: list[dict] = []
    for date, bucket in sorted(raw.items()):
        new = int(bucket.get("new", 0) or 0)
        ret = int(bucket.get("returning", 0) or 0)
        total = new + ret
        pct = round(100.0 * ret / total, 1) if total else 0.0
        days.append({
            "date": date,
            "new": new,
            "returning": ret,
            "total": total,
            "returning_pct": pct,
        })
    today = days[-1] if days else None
    return {"days": days, "today": today}


# ---------------------------------------------------------------------------
# /stats HTML page
# ---------------------------------------------------------------------------
# Self-contained: no third-party scripts. JS hydrates panels on load; with JS
# disabled the noscript fallback shows server-rendered headline numbers (DAU,
# Chicago-metro %, sessions today) per the FEAT-009 acceptance criteria.

_STATS_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CTA Transit PWA — Public Stats</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<style>
  :root {
    --bg: #faf6ef; --fg: #2a2622; --muted: #756e63; --accent: #b86b3a;
    --card: #ffffff; --border: #e6dfd2; --grid: #f0e9da;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--bg); color: var(--fg); line-height: 1.5;
  }
  main { max-width: 720px; margin: 0 auto; padding: 32px 20px 64px; }
  h1 { font-size: 28px; margin: 0 0 4px; letter-spacing: -0.01em; }
  .sub { color: var(--muted); margin: 0 0 28px; font-size: 15px; }
  .panel {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 20px 22px; margin-bottom: 16px;
  }
  .panel h2 { margin: 0 0 8px; font-size: 16px; color: var(--muted); font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.04em; }
  .big { font-size: 38px; font-weight: 700; letter-spacing: -0.02em; }
  .stat-row { display: flex; flex-wrap: wrap; gap: 24px; margin-top: 6px; }
  .stat-row > div small { display: block; font-size: 12px; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 2px; }
  .stat-row > div b { font-size: 22px; font-weight: 700; letter-spacing: -0.01em; }
  .trend { display: flex; align-items: flex-end; gap: 3px; height: 60px; margin-top: 14px; }
  .bar { background: var(--accent); flex: 1; min-height: 2px; border-radius: 2px 2px 0 0; }
  .hour-grid { display: flex; align-items: flex-end; gap: 2px; height: 80px; margin-top: 14px; }
  .hour-grid .bar { background: var(--accent); flex: 1; min-height: 2px; border-radius: 2px 2px 0 0; }
  .hour-axis { display: flex; justify-content: space-between; font-size: 11px;
    color: var(--muted); margin-top: 4px; }
  .split { display: flex; height: 28px; border-radius: 6px; overflow: hidden;
    border: 1px solid var(--border); margin-top: 12px; }
  .split > span { display: flex; align-items: center; justify-content: center;
    color: white; font-size: 12px; font-weight: 600; min-width: 1px; }
  .split-legend { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 8px;
    font-size: 13px; color: var(--muted); }
  .split-legend i { display: inline-block; width: 10px; height: 10px;
    border-radius: 2px; margin-right: 6px; vertical-align: middle; }
  footer { margin-top: 32px; font-size: 13px; color: var(--muted); }
  footer a { color: var(--accent); }
  .err { color: #b04030; font-size: 14px; }
  .funnel-bars { display: flex; flex-direction: column; gap: 6px; }
  .funnel-row { display: flex; align-items: center; gap: 10px; }
  .funnel-label { font-size: 12px; color: var(--muted); width: 150px; flex-shrink: 0; text-align: right; }
  .funnel-bar-wrap { flex: 1; background: var(--grid); border-radius: 3px; height: 18px; }
  .funnel-bar-fill { background: var(--accent); height: 100%; border-radius: 3px; min-width: 2px; }
  .funnel-count { font-size: 12px; color: var(--muted); width: 60px; }
</style>
</head>
<body>
<main>
  <h1>CTA Transit PWA — Public Stats</h1>
  <p class="sub">Live engagement numbers, served from infrastructure we control.
  No third-party analytics scripts on this page.</p>

  <section class="panel" id="dau-panel">
    <h2>Daily unique visitors</h2>
    <div class="big" id="dau-today">__DAU_TODAY__</div>
    <div class="trend" id="dau-trend" aria-hidden="true"></div>
  </section>

  <section class="panel" id="metro-panel">
    <h2>Chicago metro share</h2>
    <div class="big" id="metro-today">__METRO_TODAY__</div>
    <div class="sub" id="metro-detail">__METRO_DETAIL__</div>
  </section>

  <section class="panel" id="sessions-panel">
    <h2>Sessions today</h2>
    <div class="big" id="sessions-today">__SESSIONS_TODAY__</div>
    <div class="stat-row">
      <div><small>Avg duration</small><b id="sessions-avg">__SESSIONS_AVG__</b></div>
      <div><small>Bounce rate</small><b id="sessions-bounce">__SESSIONS_BOUNCE__</b></div>
    </div>
  </section>

  <section class="panel" id="hourly-panel">
    <h2>Peak engagement hours</h2>
    <div class="hour-grid" id="hourly-grid" aria-hidden="true"></div>
    <div class="hour-axis"><span>12 a.m.</span><span>6 a.m.</span><span>noon</span><span>6 p.m.</span><span>11 p.m.</span></div>
    <div class="sub" id="hourly-detail">__HOURLY_DETAIL__</div>
  </section>

  <section class="panel" id="devices-panel">
    <h2>Device split (today)</h2>
    <div class="split" id="devices-split" aria-hidden="true"></div>
    <div class="split-legend" id="devices-legend">__DEVICES_LEGEND__</div>
  </section>

  <section class="panel" id="referrers-panel">
    <h2>Traffic sources (today)</h2>
    <div class="split" id="referrers-split" aria-hidden="true"></div>
    <div class="split-legend" id="referrers-legend">__REFERRERS_LEGEND__</div>
  </section>

  <section class="panel" id="events-panel">
    <h2>Engagement events (today)</h2>
    <div class="stat-row">
      <div><small>Recommendations served</small><b id="events-served">__EVENTS_SERVED__</b></div>
      <div><small>Routes selected</small><b id="events-selected">__EVENTS_SELECTED__</b></div>
      <div><small>Trips started</small><b id="events-trips">__EVENTS_TRIPS__</b></div>
    </div>
    <div class="sub" id="events-detail">__EVENTS_DETAIL__</div>
  </section>

  <section class="panel" id="funnel-panel">
    <h2>Session funnel (today)</h2>
    <div class="big" id="funnel-rate">__FUNNEL_RATE__</div>
    <div class="sub">of sessions reached a route result</div>
    <div class="funnel-bars" id="funnel-bars" aria-hidden="true" style="margin-top:14px"></div>
    <div class="sub" id="funnel-detail">__FUNNEL_DETAIL__</div>
  </section>

  <section class="panel" id="retention-panel">
    <h2>New vs returning visitors (today)</h2>
    <div class="big" id="retention-rate">__RETENTION_RATE__</div>
    <div class="sub">returning visitors today</div>
    <div class="stat-row" style="margin-top:8px">
      <div><small>New</small><b id="retention-new">__RETENTION_NEW__</b></div>
      <div><small>Returning</small><b id="retention-returning">__RETENTION_RETURNING__</b></div>
    </div>
  </section>

  <footer>
    No third-party scripts on this page. See
    <a href="/privacy">privacy notes</a>. Mean session length is
    inflated by up to 30 min for the visitor's last request because
    session-end is detected via server-side idle timeout.
  </footer>
</main>
<script>
(function() {
  function fmt(n) { return new Intl.NumberFormat("en-US").format(n); }
  function setText(id, t) { var el = document.getElementById(id); if (el) el.textContent = t; }
  function fmtDuration(s) {
    if (!s) return "—";
    var m = Math.floor(s / 60), sec = Math.round(s % 60);
    if (m < 1) return sec + "s";
    return m + "m " + sec + "s";
  }
  function panelErr(panelId, msg) {
    var p = document.getElementById(panelId);
    var d = document.createElement("div"); d.className = "err"; d.textContent = msg;
    p.appendChild(d);
  }

  function loadJSON(url) {
    return fetch(url).then(function(r) {
      if (!r.ok) throw new Error(url + " " + r.status);
      return r.json();
    });
  }

  // DAU + 30-day trend
  loadJSON("/stats/dau").then(function(dau) {
    if (dau.today) {
      setText("dau-today", fmt(dau.today.count));
      var trend = document.getElementById("dau-trend");
      var last = dau.days.slice(-30);
      var max = Math.max.apply(null, last.map(function(d){return d.count;}).concat([1]));
      trend.innerHTML = last.map(function(d) {
        var h = Math.max(2, Math.round(60 * d.count / max));
        return '<div class="bar" title="' + d.date + ': ' + d.count + '" style="height:' + h + 'px"></div>';
      }).join("");
    }
  }).catch(function() { panelErr("dau-panel", "Failed to load DAU."); });

  // Chicago metro
  loadJSON("/stats/geography").then(function(geo) {
    if (geo.today && geo.today.total > 0) {
      setText("metro-today", geo.today.share_pct.toFixed(1) + "%");
      setText("metro-detail",
        fmt(geo.today.metro) + " of " + fmt(geo.today.total) +
        " visitors today are in the Chicago metro area.");
    }
  }).catch(function() { panelErr("metro-panel", "Failed to load geography."); });

  // Sessions / bounce / duration
  loadJSON("/stats/sessions").then(function(s) {
    if (s.today) {
      setText("sessions-today", fmt(s.today.sessions));
      setText("sessions-avg", fmtDuration(s.today.avg_duration_seconds));
      setText("sessions-bounce", s.today.bounce_rate_pct.toFixed(1) + "%");
    }
  }).catch(function() { panelErr("sessions-panel", "Failed to load sessions."); });

  // Hour of day (24 bars)
  loadJSON("/stats/hourly").then(function(h) {
    var grid = document.getElementById("hourly-grid");
    var arr = (h.today && h.today.hours) ? h.today.hours : new Array(24).fill(0);
    var max = Math.max.apply(null, arr.concat([1]));
    grid.innerHTML = arr.map(function(v, i) {
      var ph = Math.max(2, Math.round(80 * v / max));
      var label = i + ":00 — " + v + " requests";
      return '<div class="bar" title="' + label + '" style="height:' + ph + 'px"></div>';
    }).join("");
    if (h.today && h.today.total > 0) {
      var peakIdx = arr.indexOf(max);
      setText("hourly-detail",
        "Peak hour: " + peakIdx + ":00 (" + fmt(max) + " requests). Total today: " + fmt(h.today.total) + ".");
    }
  }).catch(function() { panelErr("hourly-panel", "Failed to load hourly."); });

  // Device split — stacked bar
  loadJSON("/stats/devices").then(function(d) {
    var split = document.getElementById("devices-split");
    var legend = document.getElementById("devices-legend");
    if (!d.today || d.today.total === 0) return;
    var total = d.today.total;
    var parts = [
      { name: "mobile",  v: d.today.mobile,  c: "#b86b3a" },
      { name: "tablet",  v: d.today.tablet,  c: "#5a8779" },
      { name: "desktop", v: d.today.desktop, c: "#2a2622" }
    ];
    split.innerHTML = parts.map(function(p) {
      var pct = 100 * p.v / total;
      return '<span style="background:' + p.c + ';width:' + pct.toFixed(2) + '%">' +
        (pct >= 8 ? p.name + " " + pct.toFixed(0) + "%" : "") + '</span>';
    }).join("");
    legend.innerHTML = parts.map(function(p) {
      var pct = (100 * p.v / total).toFixed(1);
      return '<span><i style="background:' + p.c + '"></i>' + p.name + ' ' + pct + '% (' + fmt(p.v) + ')</span>';
    }).join("");
  }).catch(function() { panelErr("devices-panel", "Failed to load devices."); });

  // Engagement events
  loadJSON("/stats/events").then(function(e) {
    if (!e.today) return;
    setText("events-served",   fmt(e.today.recommend_returned));
    setText("events-selected", fmt(e.today.route_selected));
    setText("events-trips",    fmt(e.today.trip_completed));
    if (e.today.recommend_submitted > 0) {
      setText("events-detail",
        fmt(e.today.recommend_submitted) + " recommendation searches today" +
        (e.today.recommend_returned > 0
          ? " (" + ((100 * e.today.recommend_returned / e.today.recommend_submitted)|0) + "% returned a result)"
          : "."));
    }
  }).catch(function() { panelErr("events-panel", "Failed to load events."); });

  // Session funnel
  loadJSON("/stats/funnel").then(function(f) {
    if (!f.today || !f.today.counts || f.today.counts[0] === 0) return;
    setText("funnel-rate", f.today.result_rate_pct.toFixed(1) + "%");
    var stages = f.today.stages;
    var counts = f.today.counts;
    var max = counts[0] || 1;
    var bars = document.getElementById("funnel-bars");
    bars.innerHTML = stages.map(function(s, i) {
      var pct = (100 * counts[i] / max).toFixed(1);
      var label = s.replace(/_/g, " ");
      return '<div class="funnel-row">' +
        '<div class="funnel-label">' + label + '</div>' +
        '<div class="funnel-bar-wrap"><div class="funnel-bar-fill" style="width:' + pct + '%"></div></div>' +
        '<div class="funnel-count">' + fmt(counts[i]) + '</div>' +
        '</div>';
    }).join("");
    setText("funnel-detail",
      fmt(counts[0]) + " sessions started · " +
      f.today.result_rate_pct.toFixed(1) + "% reached a route result.");
  }).catch(function() { panelErr("funnel-panel", "Failed to load funnel."); });

  // New vs returning
  loadJSON("/stats/retention").then(function(ret) {
    if (!ret.today || ret.today.total === 0) return;
    setText("retention-rate", ret.today.returning_pct.toFixed(1) + "%");
    setText("retention-new", fmt(ret.today.new));
    setText("retention-returning", fmt(ret.today.returning));
  }).catch(function() { panelErr("retention-panel", "Failed to load retention."); });

  // Referrers — stacked bar
  loadJSON("/stats/referrers").then(function(r) {
    var split = document.getElementById("referrers-split");
    var legend = document.getElementById("referrers-legend");
    if (!r.today || r.today.total === 0) return;
    var total = r.today.total;
    var parts = [
      { name: "direct", v: r.today.direct, c: "#2a2622" },
      { name: "search", v: r.today.search, c: "#b86b3a" },
      { name: "social", v: r.today.social, c: "#5a8779" },
      { name: "other",  v: r.today.other,  c: "#a09280" }
    ];
    split.innerHTML = parts.map(function(p) {
      var pct = 100 * p.v / total;
      return '<span style="background:' + p.c + ';width:' + pct.toFixed(2) + '%">' +
        (pct >= 8 ? p.name + " " + pct.toFixed(0) + "%" : "") + '</span>';
    }).join("");
    legend.innerHTML = parts.map(function(p) {
      var pct = (100 * p.v / total).toFixed(1);
      return '<span><i style="background:' + p.c + '"></i>' + p.name + ' ' + pct + '% (' + fmt(p.v) + ')</span>';
    }).join("");
  }).catch(function() { panelErr("referrers-panel", "Failed to load referrers."); });
})();
</script>
</body>
</html>
"""


# Plaintext privacy notes served at ``/privacy`` (linked from the dashboard
# footer). Kept inline rather than reading docs/PRIVACY.md at request time
# because the Dockerfile only copies ``backend/`` into the image. Update in
# lockstep with docs/PRIVACY.md when material changes land.
PRIVACY_TEXT = """\
CTA Transit PWA — privacy notes

This app collects the minimum information needed to operate the service and
to publish coarse, aggregate usage numbers. It uses no third-party analytics
scripts, no fingerprinting, and no persistent cross-day user identifiers.

What is collected
-----------------

Daily unique visitors (DAU)
  Visitor IPs are HMAC-SHA256-hashed with a daily-rotating salt and held
  only in an in-memory set for the current Chicago calendar day. At
  midnight the set is discarded; only the final integer count is written
  to disk. There is no IP-to-day mapping persisted, anywhere.

Approximate geography
  Visitor IPs are fed to MaxMind GeoLite2-City in memory only. The IP is
  never written alongside the city. Only a per-day, per-city integer
  counter is persisted. A privacy floor (5 visits/day) buckets rare
  cities into "Other" on read so a single visitor in a small suburb
  cannot be re-identified.

Sessions
  A short-lived random session ID is set in an httpOnly Secure
  SameSite=Lax cookie with a 30-min sliding TTL. It is hashed with the
  same daily-rotating salt as DAU before any internal logging. No
  per-session row is persisted — only an aggregate-per-day record of
  sessions, total duration, and bounces. The cookie is discarded at
  midnight Chicago.

Hour-of-day distribution
  A 24-int array per day, incremented when a recommendation is requested.
  Identical privacy posture to the DAU counter.

Device class
  The User-Agent header (sent by every browser anyway) is parsed in
  memory to bucket each visit into mobile / tablet / desktop / bot /
  unknown. The raw UA string is never stored.

Referrers
  The Referer header is parsed to a hostname (path and query stripped
  before any storage to avoid accidental capture of UTM params). Bucketed
  into direct / search / social / other.

Engagement events
  Named in-app actions (e.g. recommend_submitted, route_selected,
  trip_completed) are reported by the frontend to a strict server-side
  allowlist. Only a daily aggregate per event name is persisted — never
  the per-session sequence, never the order in which events fired. The
  public dashboard surfaces only the four advertiser-facing event volumes
  (recommendations served, routes selected, trips started, searches);
  internal/operational events (app_loaded, map_opened, etc.) are
  admin-only.

Public dashboard
  The /stats page is served from this app's own infrastructure and loads
  no third-party scripts. Per-city tables, per-hostname long-tail
  referrers, raw session durations, and bot/unknown device counts are
  admin-only and never reachable via /stats/*. The whitelist is enforced
  by an automated test that fails the build if any field outside the
  whitelist appears in a public response.

What is NOT collected
---------------------

  * No fingerprinting (canvas, fonts, audio, WebGL, screen size, etc.).
  * No third-party analytics or marketing tags.
  * No raw IP addresses, User-Agent strings, or reversible identifiers on disk.
  * The returnId cookie (90-day opaque token) is the only persistent
    cross-day identifier. It is an opaque random token with no PII linkage;
    only a one-way HMAC fingerprint is stored in the Bloom filter.

Where the data lives
--------------------

All data is stored on the same Railway-hosted backend as the application
itself. No data is sent to a third-party processor.

If you'd like the data deleted, contact the maintainer.
"""


def render_html(
    dau_today: dict | None = None,
    metro_today: dict | None = None,
    sessions_today: dict | None = None,
    hourly_today: dict | None = None,
    devices_today: dict | None = None,
    referrers_today: dict | None = None,
    events_today: dict | None = None,
    funnel_today: dict | None = None,
    retention_today: dict | None = None,
) -> str:
    """Render the /stats page with today's headline numbers server-injected.

    The JavaScript-disabled fallback shows the same numbers JS would surface
    once it loads, satisfying the FEAT-009 acceptance criterion that the
    page remain meaningful without JavaScript.
    """
    # Helpers — keep replacement values free of HTML special chars so the
    # naive .replace() below can't introduce an XSS surface. All inputs are
    # numbers we converted ourselves.
    def fmt_int(n) -> str:
        try:
            return f"{int(n):,}"
        except Exception:
            return "—"

    def fmt_duration(seconds) -> str:
        try:
            seconds = float(seconds or 0)
        except Exception:
            return "—"
        if seconds < 60:
            return f"{int(seconds)}s"
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s}s"

    # DAU
    dau_str = fmt_int(dau_today["count"]) if dau_today else "—"

    # Metro
    if metro_today and metro_today.get("total"):
        share = float(metro_today.get("share_pct", 0.0))
        metro_str = f"{share:.1f}%"
        metro_detail = (
            f"{int(metro_today['metro']):,} of "
            f"{int(metro_today['total']):,} visitors today are in the Chicago metro area."
        )
    else:
        metro_str = "—"
        metro_detail = "No metro data yet today."

    # Sessions
    if sessions_today and sessions_today.get("sessions"):
        sessions_str = fmt_int(sessions_today["sessions"])
        sessions_avg = fmt_duration(sessions_today.get("avg_duration_seconds", 0))
        sessions_bounce = f"{float(sessions_today.get('bounce_rate_pct', 0.0)):.1f}%"
    else:
        sessions_str = "—"
        sessions_avg = "—"
        sessions_bounce = "—"

    # Hourly
    if hourly_today and hourly_today.get("total"):
        arr = hourly_today.get("hours", [0] * 24)
        peak = arr.index(max(arr)) if arr else 0
        hourly_detail = (
            f"Peak hour: {peak}:00 ({max(arr) if arr else 0} requests). "
            f"Total today: {int(hourly_today['total']):,}."
        )
    else:
        hourly_detail = "No hourly data yet today."

    # Devices legend (text fallback)
    if devices_today and devices_today.get("total"):
        total = int(devices_today["total"])
        m = int(devices_today.get("mobile", 0))
        t = int(devices_today.get("tablet", 0))
        d = int(devices_today.get("desktop", 0))
        devices_legend = (
            f"mobile {100*m/total:.1f}% ({m:,}) · "
            f"tablet {100*t/total:.1f}% ({t:,}) · "
            f"desktop {100*d/total:.1f}% ({d:,})"
        )
    else:
        devices_legend = "No device data yet today."

    # Referrers legend (text fallback)
    if referrers_today and referrers_today.get("total"):
        total = int(referrers_today["total"])
        parts = []
        for k in ("direct", "search", "social", "other"):
            v = int(referrers_today.get(k, 0))
            parts.append(f"{k} {100*v/total:.1f}% ({v:,})")
        referrers_legend = " · ".join(parts)
    else:
        referrers_legend = "No referrer data yet today."

    # Funnel
    if funnel_today and funnel_today.get("counts") and funnel_today["counts"][0]:
        counts = funnel_today["counts"]
        rate = float(funnel_today.get("result_rate_pct", 0.0))
        funnel_rate = f"{rate:.1f}%"
        funnel_detail = (
            f"{int(counts[0]):,} sessions started · "
            f"{rate:.1f}% reached a route result."
        )
    else:
        funnel_rate = "—"
        funnel_detail = "No funnel data yet today."

    # Retention
    if retention_today and retention_today.get("total"):
        total_ret = int(retention_today["total"])
        ret_new = int(retention_today.get("new", 0))
        ret_returning = int(retention_today.get("returning", 0))
        ret_pct = float(retention_today.get("returning_pct", 0.0))
        retention_rate = f"{ret_pct:.1f}%"
        retention_new_str = fmt_int(ret_new)
        retention_returning_str = fmt_int(ret_returning)
    else:
        retention_rate = "—"
        retention_new_str = "—"
        retention_returning_str = "—"

    # Events
    if events_today and events_today.get("total"):
        events_served   = fmt_int(events_today.get("recommend_returned", 0))
        events_selected = fmt_int(events_today.get("route_selected", 0))
        events_trips    = fmt_int(events_today.get("trip_completed", 0))
        submitted = int(events_today.get("recommend_submitted", 0))
        returned  = int(events_today.get("recommend_returned", 0))
        if submitted > 0:
            return_rate = int(100 * returned / submitted)
            events_detail = (
                f"{submitted:,} recommendation searches today "
                f"({return_rate}% returned a result)."
            )
        else:
            events_detail = "No recommendation searches yet today."
    else:
        events_served = "—"
        events_selected = "—"
        events_trips = "—"
        events_detail = "No event data yet today."

    return (
        _STATS_HTML_TEMPLATE
        .replace("__DAU_TODAY__", dau_str)
        .replace("__METRO_TODAY__", metro_str)
        .replace("__METRO_DETAIL__", metro_detail)
        .replace("__SESSIONS_TODAY__", sessions_str)
        .replace("__SESSIONS_AVG__", sessions_avg)
        .replace("__SESSIONS_BOUNCE__", sessions_bounce)
        .replace("__HOURLY_DETAIL__", hourly_detail)
        .replace("__DEVICES_LEGEND__", devices_legend)
        .replace("__REFERRERS_LEGEND__", referrers_legend)
        .replace("__EVENTS_SERVED__", events_served)
        .replace("__EVENTS_SELECTED__", events_selected)
        .replace("__EVENTS_TRIPS__", events_trips)
        .replace("__EVENTS_DETAIL__", events_detail)
        .replace("__FUNNEL_RATE__", funnel_rate)
        .replace("__FUNNEL_DETAIL__", funnel_detail)
        .replace("__RETENTION_RATE__", retention_rate)
        .replace("__RETENTION_NEW__", retention_new_str)
        .replace("__RETENTION_RETURNING__", retention_returning_str)
    )
