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

from pathlib import Path
from string import Template

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
#
# The HTML/CSS/JS body lives in ``backend/templates/stats.html`` so it can be
# edited with normal HTML tooling. Substitution uses ``string.Template`` —
# placeholders are ``$lower_snake_case`` and unsubstituted slots stay literal
# instead of crashing (``safe_substitute``). Read once at import time so the
# request path stays I/O-free.

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "stats.html"
_STATS_TEMPLATE = Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))



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
  A short-lived random session ID is set in an httpOnly Secure cookie
  (SameSite=None in production for cross-site delivery, SameSite=Lax in
  local dev) with a 30-min sliding TTL. It is hashed with the same daily-
  rotating salt as DAU before any internal logging. No per-session row is
  persisted — only an aggregate-per-day record of sessions, total
  duration, and bounces. The cookie is discarded at midnight Chicago.

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

    # safe_substitute() leaves unknown $name slots literal instead of crashing,
    # so adding a placeholder to the HTML before wiring up its variable here
    # degrades gracefully rather than 500-ing the whole dashboard.
    return _STATS_TEMPLATE.safe_substitute(
        dau_today=dau_str,
        metro_today=metro_str,
        metro_detail=metro_detail,
        sessions_today=sessions_str,
        sessions_avg=sessions_avg,
        sessions_bounce=sessions_bounce,
        hourly_detail=hourly_detail,
        devices_legend=devices_legend,
        referrers_legend=referrers_legend,
        events_served=events_served,
        events_selected=events_selected,
        events_trips=events_trips,
        events_detail=events_detail,
        funnel_rate=funnel_rate,
        funnel_detail=funnel_detail,
        retention_rate=retention_rate,
        retention_new=retention_new_str,
        retention_returning=retention_returning_str,
    )
