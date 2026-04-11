# Future Enhancements

Post-launch ideas and feature requests. These are not bugs — the app works correctly without them. Prioritize after Phase 6 deployment based on user feedback.

---

## 🚉 Train Station Exit Guidance

**What:** Many CTA train stations have multiple exits — sometimes one in each direction — and riders often emerge disoriented. Based on the user's destination, the app should:

1. Identify which exit(s) are available at the alighting station (CTA provides this in some GTFS data or accessibility feeds)
2. Calculate which exit places the rider closest to their destination using the OSMnx street graph
3. Tell the rider which exit to use in the final walk leg — e.g. "Use the Wilson Ave exit (south end of platform)"
4. Optionally, let the rider select which exit they actually used and recalculate the final walk leg directions from that exit's coordinates

**Why it matters:** Getting the exit wrong adds confusion and unnecessary street-level walking, especially at large stations like Clark/Lake, Jackson, O'Hare, or Howard where exits are spread across a full city block.

**Implementation notes:**
- Exit locations would need to be sourced — CTA GTFS `stops.txt` contains platform stops (30000–39999) but not named exits. Options:
  - OpenStreetMap `railway=subway_entrance` nodes (free, community-maintained, coverage varies)
  - CTA's accessibility data or station diagrams (manual curation for key stations)
  - Google Maps Places API (paid, but comprehensive)
- Once exit coordinates are available, the OSMnx street graph already handles routing from any lat/lon — no routing engine changes needed
- The UI change is in `App.jsx`: the final walk leg would show the recommended exit name before the street-level directions
- The "let the rider choose" variant would require a small UI picker on the final walk leg and a re-fetch or client-side recalculation of walk directions from the chosen exit

**Suggested scope for first pass:** Manually curate exit coordinates for the 10–15 most-used stations (Red Line north/south endpoints, Blue Line O'Hare/Forest Park, major Loop stations). This covers the majority of trips without a full data pipeline.

---

## 🔀 Intermodal Routing (Train + Bus in One Trip)

**What:** Combined train+bus trips — e.g. "walk → Red Line → transfer to bus 36 → destination" — are not currently surfaced as structured route cards. Claude may suggest them conversationally, but no route card with accurate leg-by-leg timing is generated.

**Why deferred:** The majority of Chicago trips are served by train-only or bus-only routes. Implementing true intermodal routing requires adding bus stop nodes and bus route edges to the NetworkX train graph — a significant architectural addition. Best done post-launch with real trip data to validate against.

**Future fix:** Add bus stop nodes and bus route edges to the NetworkX graph in `transit_graph.py`, along with transfer edges between train stations and nearby bus stops. The routing algorithm would then naturally find train+bus paths as part of `find_routes()`.

---

## 💰 Rate Limiting on `/recommend` Endpoint

**What:** The `/recommend` endpoint currently has no per-user or global rate limiting. A single user or bot can run up Claude API costs without any cap.

**Why deferred:** Intentionally deferred during testing so queries are unrestricted.

**Must add before or shortly after public launch.** Without it, a bad actor can drain the Anthropic API budget with no friction.

---

## 📱 Bring Your Own API Key (BYOK)

**What:** Let technically savvy users supply their own Anthropic API key in an in-app setup workflow. Their usage shifts entirely off the app's variable cost base.

**Considerations:**
- Most target users (everyday CTA riders) will not use this — do not rely on it as a primary cost solution
- API keys must be stored and handled securely — user financial liability is at stake if keys are exposed
- Build as an optional power-user setting, not a core requirement
- Caching and per-user request limiting will move the cost needle more broadly

---

## 🔁 Claude Response Caching

**What:** Cache Claude responses for identical or near-identical origin/destination/mode queries within a short window (e.g. 60 seconds). Repeat requests for popular routes (e.g. Wrigleyville → Loop at 5pm) would return the cached response instantly.

**Benefit:** Reduces Anthropic API spend significantly once traffic scales.

---

## 🧠 Claude Haiku for Simple Queries

**What:** Route queries with only one clear option (e.g. a single direct train, no transfers) don't need Sonnet-level reasoning. Haiku is ~65% cheaper and fast enough for straightforward recommendations.

**Benefit:** Meaningful cost reduction at scale with no user-facing quality loss on simple routes.
