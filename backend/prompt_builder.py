"""
Claude prompt construction for /recommend.

Pulls together ranked routes, live arrivals, weather, alerts, route
disruptions, and a language preference into the single user-message string
``build_prompt()`` returns. Pure transformation — no I/O, no module-level
mutable state beyond a tiny one-minute crowdedness-period cache.
"""

from __future__ import annotations

import time
from datetime import datetime

from crowdedness import (
    CROWDEDNESS_LEVEL_ORDER,
    CrowdednessLevel,
    classify_time_period,
    estimate_crowdedness,
    rtdir_to_inbound_outbound,
)
from route_scoring import weight_hint_for_weather
from transit_graph import TransitLeg, WalkLeg, get_stop_sequence_position
from utils import CHICAGO_TZ as _CHICAGO_TZ
from weather_service import PrecipitationType, WeatherContext


# ---------------------------------------------------------------------------
# Crowdedness — one-minute cache for (time_period, day_type, hour)
# ---------------------------------------------------------------------------
_CROWDEDNESS_LABELS: dict[CrowdednessLevel, str] = {
    CrowdednessLevel.LOW:       "light",
    CrowdednessLevel.MODERATE:  "moderate",
    CrowdednessLevel.HIGH:      "busy",
    CrowdednessLevel.VERY_HIGH: "very crowded",
}

# These change at most once every 15–30 minutes so re-computing on every leg
# of every request is wasteful.
_crowdedness_period_cached: tuple | None = None
_crowdedness_period_cache_ts: float = 0.0
_CROWDEDNESS_PERIOD_TTL = 60.0  # seconds


def _get_crowdedness_period() -> tuple:
    """Return (time_period, day_type, hour), recomputing at most once per minute."""
    global _crowdedness_period_cached, _crowdedness_period_cache_ts
    now_mono = time.monotonic()
    if (
        _crowdedness_period_cached is None
        or now_mono - _crowdedness_period_cache_ts > _CROWDEDNESS_PERIOD_TTL
    ):
        now = datetime.now(_CHICAGO_TZ)
        _crowdedness_period_cached = classify_time_period(now)
        _crowdedness_period_cache_ts = now_mono
    return _crowdedness_period_cached


def _crowdedness_for_routes(ranked: list[tuple]) -> dict[int, str]:
    """
    Compute a crowdedness label for each ranked route (keyed by 1-based index).

    Uses current Chicago time to classify the time period.  For each route,
    takes the worst crowdedness level across all TransitLegs and converts it
    to a human-readable label for the Claude prompt.
    """
    time_period, day_type, now_hour = _get_crowdedness_period()

    labels: dict[int, str] = {}
    for i, (_total, _wait, route) in enumerate(ranked, 1):
        leg_levels: list[CrowdednessLevel] = []
        for leg in route.legs:
            if not isinstance(leg, TransitLeg):
                continue
            is_bus = leg.line in ("Northbound", "Southbound", "Eastbound", "Westbound")
            direction = (
                rtdir_to_inbound_outbound(leg.line_code, leg.line)
                if is_bus else "inbound"
            )
            seq_pos, seq_total = get_stop_sequence_position(
                leg.from_mapid or "", leg.line_code or ""
            )
            est = estimate_crowdedness(
                route_id=leg.line_code or "",
                direction=direction,
                stop_id=leg.from_mapid or "",
                stop_sequence_position=seq_pos,
                total_stops=seq_total,
                time_period=time_period,
                day_type=day_type,
                current_hour=now_hour,
                include_factors=False,
            )
            leg_levels.append(est.level)
        if leg_levels:
            worst = max(leg_levels, key=lambda lvl: CROWDEDNESS_LEVEL_ORDER[lvl])
            labels[i] = _CROWDEDNESS_LABELS[worst]
    return labels


# ---------------------------------------------------------------------------
# Language support
# ---------------------------------------------------------------------------
LANGUAGE_NAMES: dict[str, str] = {
    "en":  "English",
    "es":  "Spanish",
    "fr":  "French",
    "it":  "Italian",
    "pl":  "Polish",
    "ro":  "Romanian",
    "uk":  "Ukrainian",
    "ru":  "Russian",
    "zh":  "Mandarin Chinese",
    "yue": "Cantonese Chinese",
    "ja":  "Japanese",
    "ko":  "Korean",
    "tl":  "Filipino (Tagalog)",
    "vi":  "Vietnamese",
    "hi":  "Hindi",
    "gu":  "Gujarati",
    "pa":  "Punjabi",
    "ne":  "Nepali",
    "ur":  "Urdu",
    "ar":  "Arabic",
    "ps":  "Pashto",
    "yo":  "Yoruba",
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_routes(ranked: list[tuple]) -> str:
    """Format ranked (total, wait, route) list into a text block for Claude.
    Handles both train and bus TransitLegs."""
    crowd_labels = _crowdedness_for_routes(ranked)
    lines = []
    for i, (total, wait, route) in enumerate(ranked, 1):
        first_transit = next((l for l in route.legs if isinstance(l, TransitLeg)), None)
        is_bus = first_transit and first_transit.line in (
            "Northbound", "Southbound", "Eastbound", "Westbound"
        )
        if wait is None:
            wait_note = ""                                        # no live data
        elif wait == 0:
            wait_note = ", next bus Due" if is_bus else ", next train Due"
        else:
            wait_note = (
                f", next bus in {wait} min" if is_bus
                else f", next train in {wait} min"
            )
        leg_parts = []
        for leg in route.legs:
            if isinstance(leg, WalkLeg):
                if leg.from_name == "Your location":
                    leg_parts.append(f"walk {leg.minutes:.0f} min to {leg.to_name}")
                elif leg.to_name == "Your destination":
                    leg_parts.append(f"walk {leg.minutes:.0f} min to destination")
                else:
                    leg_parts.append(f"transfer walk {leg.minutes:.0f} min")
            else:
                if leg.line in ("Northbound", "Southbound", "Eastbound", "Westbound"):
                    leg_parts.append(
                        f"Route {leg.line_code} {leg.line} "
                        f"{leg.from_station} to {leg.to_station} "
                        f"({leg.minutes:.0f} min in-vehicle)"
                    )
                else:
                    leg_parts.append(
                        f"{leg.line} {leg.from_station} to {leg.to_station} "
                        f"({leg.minutes:.0f} min in-vehicle)"
                    )
        xfers = f", {route.transfers} transfer{'s' if route.transfers != 1 else ''}" if route.transfers else ""
        crowd_tag = f" [est. crowdedness: {crowd_labels[i]}]" if i in crowd_labels else ""
        lines.append(
            f"Option {i}: {' | '.join(leg_parts)}{wait_note} "
            f"[~{total:.0f} min total{xfers}]{crowd_tag}"
        )
    return "\n".join(lines)


def _format_bus_arrivals(bus_arrivals: list[dict]) -> str:
    lines = []
    for a in bus_arrivals[:6]:
        minutes = a.get("arrives_in_minutes", 0)
        due = "Due" if minutes == 0 else f"{minutes} min"
        delay = " (DELAYED)" if a.get("is_delayed") else ""
        load = a.get("psgld", "")
        load_note = f" [{load.replace('_', ' ').title()}]" if load else ""
        lines.append(
            f"  * Route {a.get('route', '?')} toward {a.get('destination', 'Unknown')} — {due}{delay}{load_note}"
            f" | {a.get('stop_name', 'Unknown stop')}"
        )
    return "\n".join(lines)


def _format_transfer_arrivals(arrivals: list[dict]) -> str:
    """Format combined train+bus transfer arrivals grouped by stop/station name."""
    groups: dict[str, list[dict]] = {}
    for a in arrivals:
        stop = a.get("station") or a.get("stop_name", "Unknown stop")
        groups.setdefault(stop, []).append(a)
    lines = []
    for stop, stop_arrivals in groups.items():
        lines.append(f"{stop}:")
        for a in sorted(stop_arrivals, key=lambda x: x["arrives_in_minutes"])[:3]:
            route_label = a.get("line_code") or a.get("route", "?")
            dest = a.get("destination", "")
            mins = a["arrives_in_minutes"]
            due_str = "Due" if mins == 0 else f"{mins} min"
            lines.append(f"  {route_label} → {dest}: {due_str}")
    return "\n".join(lines)


def _format_weather_for_prompt(weather: WeatherContext, hint: str = "") -> str:
    """Format a one-line weather summary for the Claude prompt.

    hint is from _departure_window_hint(); when non-empty it is appended to the
    current-conditions line so the full weather context stays on one line.
    """
    c = weather.current

    if c.precipitation.type == PrecipitationType.NONE:
        precip_str = "none"
    elif c.precipitation.intensity:
        precip_str = f"{c.precipitation.type.value} ({c.precipitation.intensity})"
    else:
        precip_str = c.precipitation.type.value

    gust_str = ""
    if c.wind.gust_mph and c.wind.gust_mph >= 15:
        gust_str = f", wind gusts {c.wind.gust_mph:.0f} mph"

    hint_str = f" {hint}" if hint else ""

    line = (
        f"Current weather: {c.short_forecast}, {c.temperature_f:.0f}°F "
        f"(feels like {c.feels_like_f:.0f}°F), precipitation: {precip_str}{gust_str}{hint_str}"
    )

    if weather.alerts:
        line += f"\nWeather alerts: {'; '.join(weather.alerts[:2])}"

    return line


def _departure_window_hint(weather: "WeatherContext | None") -> str:
    """Return a short departure-timing hint based on the hourly forecast.

    Scans the next 3 forecast periods for a precipitation transition:
      - Improving (rain/snow clears): "(forecast: clears in ~Nh)"
      - Worsening (precipitation starts): "(forecast: {type} starts in ~Nh)"
    Only emits when the qualifying period is index >= 1 (index 0 is imminent,
    not actionable). Returns "" when no relevant transition is found.
    """
    if weather is None or len(weather.hourly_forecast) < 2:
        return ""
    current_type = weather.current.precipitation.type
    for i, fp in enumerate(weather.hourly_forecast[:3]):
        if i < 1:
            continue
        if (
            current_type != PrecipitationType.NONE
            and fp.precipitation.type == PrecipitationType.NONE
        ):
            return f"(forecast: clears in ~{i + 1}h)"
        if (
            current_type == PrecipitationType.NONE
            and fp.precipitation.type != PrecipitationType.NONE
        ):
            return f"(forecast: {fp.precipitation.type.value} starts in ~{i + 1}h)"
    return ""


def _is_simple_query(ranked_routes: list[tuple]) -> bool:
    """
    A query is 'simple' if there is exactly one ranked route and that route
    contains exactly one TransitLeg (a direct ride, no transfer). Walk-only
    routes — zero TransitLegs — are NOT simple: they need the larger model
    because there's no transit structure to reason about and the response is
    pure prose-direction summarisation. Simple queries route to Haiku for
    cost savings; all others use Sonnet.
    """
    if len(ranked_routes) != 1:
        return False
    _, _, route = ranked_routes[0]
    transit_legs = [leg for leg in route.legs if isinstance(leg, TransitLeg)]
    return len(transit_legs) == 1


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def build_prompt(
    origin: str,
    destination: str,
    train_arrivals: list[dict],
    bus_arrivals: list[dict],
    transit_mode: str = "All",
    ranked_routes: list[tuple] | None = None,
    bus_fullness: str = "All",
    alerts: list[dict] | None = None,
    route_statuses: list[dict] | None = None,
    transfer_arrivals: list[dict] | None = None,
    language: str | None = None,
    weather: "WeatherContext | None" = None,
    routing_status: dict | None = None,
) -> str:
    mode_constraints = {
        "Train": "The rider wants TRAIN options only. Do not mention buses.",
        "Bus":   "The rider wants BUS options only. Do not mention trains.",
        "All":   "The rider is open to trains and buses.",
        "Walk":  "The rider wants to WALK. Provide a brief summary of the walking route and estimated time. Do not mention transit.",
    }
    mode_note = mode_constraints.get(transit_mode, mode_constraints["All"])

    # BUG-047: surface out-of-coverage explicitly so Claude tells the rider
    # WHY there are no routes, instead of guessing "no live arrivals".
    if routing_status and routing_status.get("status") == "out_of_coverage":
        side = routing_status.get("side") or "origin or destination"
        radius = routing_status.get("max_radius_searched") or 2.0
        side_phrase = {
            "origin":      f"the origin '{origin}'",
            "destination": f"the destination '{destination}'",
            "both":        f"both '{origin}' and '{destination}'",
        }.get(side, f"{origin} or {destination}")
        return (
            f"A Chicago CTA rider wants to get from {origin} to {destination}, "
            f"but {side_phrase} is more than {radius:g} miles from the nearest "
            f"CTA train station, so the routing engine has no coverage there. "
            "Explain in 2-3 sentences that the location is outside the area we "
            "currently serve (Howard St south to 50th St, lakefront west to "
            "Pulaski Rd), suggest they pick a nearby CTA stop as their start or "
            "end point, and point them at the Ventra app or transitchicago.com "
            "for trip planning beyond that area."
        )

    has_data = ranked_routes or train_arrivals or bus_arrivals
    if not has_data:
        if transit_mode == "Bus":
            return (
                f"A Chicago CTA rider at {origin} wants to get to {destination} by bus only. "
                "No live bus arrivals are available right now. "
                "Suggest they check the Ventra app or transitchicago.com for bus times."
            )
        return (
            f"A Chicago CTA rider wants to get from {origin} to {destination}. "
            "No live arrivals are currently available. "
            "Suggest they check the Ventra app or transitchicago.com."
        )

    sections = []

    if ranked_routes:
        routes_text = _format_routes(ranked_routes)
        sections.append(
            "Calculated route options (sorted by total time: walk + wait + in-vehicle):\n"
            + routes_text
        )

    if transfer_arrivals:
        sections.append(
            "Live arrivals at transfer stop(s):\n"
            + _format_transfer_arrivals(transfer_arrivals)
        )

    if not ranked_routes and bus_arrivals and transit_mode in ("Bus", "All"):
        # Fallback: raw bus arrivals when bus routing produced no structured routes
        fullness_note = (
            f" (filtered to {bus_fullness} buses only)" if bus_fullness != "All" else ""
        )
        bus_text = _format_bus_arrivals(bus_arrivals)
        sections.append(
            f"Live bus arrivals at nearby stops{fullness_note} (unstructured fallback):\n"
            + bus_text
        )

    # Fallback: raw train arrivals when routing engine produced nothing
    if not ranked_routes and train_arrivals:
        arr_lines = []
        for a in train_arrivals[:6]:
            delay = " (DELAYED)" if a["is_delayed"] else ""
            sched = " (schedule-based)" if a["is_scheduled"] else ""
            due   = "Due" if a["arrives_in_minutes"] == 0 else f"{a['arrives_in_minutes']} min"
            walk  = a.get("walk_minutes", 0)
            arr_lines.append(
                f"  * {a['line']} toward {a['destination']} — {due}{delay}{sched}"
                + (f" | {walk} min walk to {a['station']}" if walk else f" | {a['station']}")
            )
        sections.append("Live train arrivals at nearby stations:\n" + "\n".join(arr_lines))

    body = "\n\n".join(sections)

    alert_section = ""
    significant_alerts = [a for a in (alerts or []) if a.get("severity_score", 0) >= 40]
    if significant_alerts:
        alert_lines = []
        for a in significant_alerts:
            prefix = "⚠ MAJOR — " if a.get("is_major") else ""
            impact = f" [{a['impact']}]" if a.get("impact") else ""
            alert_lines.append(f"  * {prefix}{a['headline']}{impact}")
        alert_section = "\n\nActive service alerts on your route:\n" + "\n".join(alert_lines)

    route_status_section = ""
    disrupted = [r for r in (route_statuses or []) if r.get("status", "").lower() != "normal service"]
    if disrupted:
        status_lines = [f"  * {r['route']}: {r['status']}" for r in disrupted]
        route_status_section = "\n\nCurrent system-wide route disruptions:\n" + "\n".join(status_lines)

    lang_instruction = ""
    if language and language != "en":
        if language == "ja":
            lang_instruction = (
                "\n\nRespond in Japanese. Use standard Japanese (a natural mix of hiragana, "
                "katakana, and kanji). Add furigana in parentheses after each kanji compound "
                "to aid readability — for example: 電車（でんしゃ）."
            )
        elif language in LANGUAGE_NAMES:
            lang_instruction = f"\n\nRespond in {LANGUAGE_NAMES[language]}."

    departure_hint = _departure_window_hint(weather)

    weather_section = ""
    if weather is not None:
        weather_section = "\n\n" + _format_weather_for_prompt(weather, departure_hint)
        scoring_hint = weight_hint_for_weather(weather)
        if scoring_hint:
            weather_section += "\n" + scoring_hint

    weather_hint = (
        " incorporate weather context naturally within those sentences, not as a separate paragraph."
        if weather is not None
        else " the rider is probably standing outside."
    )

    departure_instruction = (
        " If conditions improve soon, mention the optimal departure window."
        if departure_hint
        else ""
    )

    return (
        f"A rider is at {origin} and wants to get to {destination}.\n\n"
        f"Rider preference: {mode_note}\n\n"
        f"{body}{alert_section}{route_status_section}{weather_section}\n\n"
        "Lead with the single best option and explain why in plain English. "
        "Factor in total trip time including walking and waiting. "
        f"Note any delays or active service alerts. Keep it to 3-4 sentences —{weather_hint}"
        f"{departure_instruction}"
        f"{lang_instruction}"
    )
