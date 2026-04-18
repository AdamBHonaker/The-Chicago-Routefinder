# Feature Plans & Future Enhancements

Chunked plans for upcoming major features, followed by ideas deferred until post-launch. For chunked features, work through each chunk in order, one chunk per session or per commit. Do not start a chunk until all previous chunks are complete.

> **Process:** When a feature here is fully implemented, **delete its entry from this file** and add a corresponding entry to [`FEATURES_IMPLEMENTED_HISTORY.md`](FEATURES_IMPLEMENTED_HISTORY.md) summarizing what was built. This file should only ever contain features that have not yet been implemented.

---

## Feature Index

**Bolt-On** = self-contained, no dependencies on other planned features.
**Structural** = depends on one or more other features before it can be fully built or realized.

1. Feature D — Live Arrivals at Transfer Stop — **Structural** (soft dependency on Feature C, now satisfied)
2. Multi-Leg Train Routing Gap 1 — Shared-Track Edge Deduplication — **Structural** (Dependency on Feature B, now complete)
3. Claude Haiku for Simple Queries — **Bolt-On**
4. Feature Language — Multi-Language Support (i18n) — **Bolt-On**
5. Feature K — Restore Street-Network Walking Graph in Production — **Bolt-On**

---

# Chunked Implementation Plans

---

# Feature D — Live Arrivals at Transfer Stop

## Overview

When a route requires a transfer — train-to-train (already supported via the NetworkX graph) or bus-to-bus (Feature C) — the app currently shows only scheduled times for the connecting service. The rider has no way to know whether the connecting train or bus is 1 minute away or 12 minutes away when they arrive at the transfer stop.

This feature fetches live arrival data for the connecting service at the transfer stop(s) in each ranked route, threads that data through the Claude prompt and the API response, and displays it inline on the route card.

**Why it matters:** A route requiring a 10-minute transfer wait is materially different from one where the connection is 2 minutes away. Without this data, Claude cannot give accurate time advice for transfer trips, and the rider cannot compare transfer options on real-time footing. Feature C explicitly deferred this as a known limitation ("7.5 min fixed estimate"); Feature D closes that gap.

**Type: Structural (soft dependency)** — the train-to-train half works independently today. The bus-transfer half depends on Feature C (Bus+Bus Transfers), which is now complete, so this dependency is satisfied.

**Status: ⬜ Not started**

**Prerequisites:** No hard prerequisites — train-to-train transfer routing already works. Feature D is most impactful after Feature C (bus+bus transfers) is built, but the train-transfer half is independently useful and can be implemented first.

---

## Scoping decisions — resolved

1. **Which legs get live arrivals?** Only the 2nd and subsequent `TransitLeg`s in a route (i.e., legs where the rider is waiting at a transfer stop, not the first boarding leg). The first leg's wait is already handled by `route.wait_minutes` via `_rank_routes()`.

2. **Transfer stop identification:** After `ranked_routes` is computed, scan each route's legs. A `TransitLeg` is a transfer boarding leg if any earlier leg in the same route is also a `TransitLeg`. Implemented as a helper `_extract_transfer_stops(ranked_routes)` that returns two deduped lists: train station dicts `[{mapid, name}]` and bus stop_id strings. Dedup by mapid/stop_id across all routes before calling the API — one call per unique stop, not per route.

3. **Train vs. bus leg identification:** A `TransitLeg` is a train leg if its `line_code` is in `LINE_NAMES` (the dict in `cta_client.py`: Red, Blue, Brn, G, Org, P, Pink, Y). A bus leg has a `line_code` that is a route number string (e.g. "36", "49"). Bus `from_mapid` values are in the 0–29999 range (GTFS stop IDs); train `from_mapid` values are in the 40000–49999 range. Either check works; prefer `line_code in LINE_NAMES`.

4. **Arrival direction filter at transfer stop:** Reuse `_build_arrival_lookup()` for train transfers — it already returns `{(line_code, station_mapid): {destNm: earliest_minutes}}` and the bearing-based direction filter in `_rank_routes()` handles multi-direction stations. For bus transfers: add a simple `_build_bus_transfer_lookup(arrivals) -> dict[tuple[str, str], int]` keyed by `(route, stop_id)` → earliest arrival minutes (bus arrivals at a specific stop_id are already direction-filtered by the API).

5. **When to fetch:** After `ranked_routes` is computed and before `build_prompt()` is called. Run `get_train_arrivals(transfer_train_stations, train_key)` and `get_bus_arrivals(transfer_bus_stop_ids, bus_key)` concurrently via `asyncio.gather`. Only call if the respective API key is set and the list is non-empty. Total added latency: one extra concurrent API round-trip (~300ms).

6. **`bus_fullness` filter:** Do NOT apply the origin-side `bus_fullness` filter to transfer bus arrivals. The rider has no choice of bus at a transfer stop — they board whatever arrives next.

7. **Serialization:** Add `"transfer_wait_minutes": int | null` to each `TransitLeg` dict in the `/recommend` response. This is `None` if no live data was returned. The existing `"wait_minutes"` on the route object (first-leg wait) is unchanged.

8. **Claude prompt:** Add a short "Live arrivals at transfer stop(s):" section to `build_prompt()` when transfer arrival data is present, formatted similarly to the existing origin arrivals section. This allows Claude to give accurate transfer-wait advice (e.g. "the Brown Line at Belmont is 4 min away when you'd arrive — good connection").

9. **Frontend:** Show `transfer_wait_minutes` inline on the transfer `TransitLeg` in `RouteLegs`. If the preceding leg in the list is a `WalkLeg` with `from === to` (same-station transfer) or is any non-first transit leg: render a small secondary line "~X min wait" (or "Due") immediately above the transit leg summary, styled as muted text — same visual weight as the route header's wait note but scoped to the individual leg.

---

## Chunk 1 — Backend: Extract transfer stops and fetch live arrivals

**Files:** `backend/main.py`

**What to build:**
- Add `_extract_transfer_stops(ranked_routes: list[tuple]) -> tuple[list[dict], list[str]]`:
  - Iterates each `(total, wait, route)` in `ranked_routes`
  - For each route, identifies `TransitLeg` objects where at least one earlier leg in `route.legs` is also a `TransitLeg`
  - Train legs (`leg.line_code in LINE_NAMES`): collect `{"mapid": leg.from_mapid, "name": leg.from_station}` — dedup by `mapid`
  - Bus legs: collect `leg.from_mapid` as a stop_id string — dedup
  - Returns `(train_transfer_stations, bus_transfer_stop_ids)`
- After `ranked_routes` is computed (after both train and bus routing blocks), call:
  ```python
  transfer_train_stations, transfer_bus_stop_ids = _extract_transfer_stops(ranked_routes)
  transfer_train_arrivals, transfer_bus_arrivals = await asyncio.gather(
      get_train_arrivals(transfer_train_stations, train_key) if transfer_train_stations and train_key else _empty(),
      get_bus_arrivals(transfer_bus_stop_ids, bus_key) if transfer_bus_stop_ids and bus_key else _empty(),
  )
  ```

**Notes:**
- If `ranked_routes` is empty, both return lists will be empty — no API calls made
- Define a small `async def _empty(): return []` helper and use it in place of real calls when the list is empty. Avoid `asyncio.coroutine` (deprecated).
- Import `LINE_NAMES` from `cta_client` (it's already a module-level dict there) — or duplicate the set of train line codes as a constant in `main.py`. Either is fine; importing is cleaner.

---

## Chunk 2 — Backend: Annotate transit legs and serialize transfer wait

**Files:** `backend/transit_graph.py`, `backend/main.py`

**What to build:**

In `transit_graph.py`:
- Add `transfer_wait_minutes: int | None = None` field to `TransitLeg` dataclass (after existing fields)

In `main.py`:
- Add `_build_bus_transfer_lookup(bus_arrivals: list[dict]) -> dict[tuple[str, str], int]`:
  - Returns `{(route, stop_id): earliest_minutes}` — one entry per `(route, stop_id)` pair, taking `min` across all matching arrivals
- After fetching transfer arrivals, build lookups:
  ```python
  train_xfer_lookup = _build_arrival_lookup(transfer_train_arrivals)
  bus_xfer_lookup   = _build_bus_transfer_lookup(transfer_bus_arrivals)
  ```
- Annotate transfer legs in-place. For each route in `ranked_routes`:
  ```python
  seen_transit = False
  for leg in route.legs:
      if isinstance(leg, TransitLeg):
          if seen_transit:
              if leg.line_code in LINE_NAMES:
                  dest_map = train_xfer_lookup.get((leg.line_code, leg.from_mapid), {})
                  leg.transfer_wait_minutes = _pick_wait(dest_map, leg.from_mapid, leg.to_mapid)
              else:
                  leg.transfer_wait_minutes = bus_xfer_lookup.get((leg.line_code, leg.from_mapid))
          seen_transit = True
  ```
  Extract the bearing filter into a shared helper `_pick_wait(dest_map, from_mapid, to_mapid) -> int | None` so it can be reused here and in `_rank_routes()`. This refactor removes the duplicate direction-selection logic.
- Add `"transfer_wait_minutes": leg.transfer_wait_minutes` to the `TransitLeg` dict in the `/recommend` response serialization

**Notes:**
- `_pick_wait` should accept an empty `dest_map` and return `None` (no live data) — same fallback as the existing `_rank_routes` wait-resolution logic
- The annotation modifies `Route.legs` in place after ranking — this is safe because the route objects are not reused after the response is built

---

## Chunk 3 — Backend: Include transfer arrivals in Claude prompt

**Files:** `backend/main.py`

**What to build:**
- Add `_format_transfer_arrivals(arrivals: list[dict]) -> str`:
  - Groups arrivals by `station` (train) or `stop_name` (bus)
  - For each stop, lists up to 3 next arrivals: `"  {line}/{route} → {destination}: {minutes} min"` (or "Due")
  - Returns a multi-line string, one stop per group header
- Extend `build_prompt()` signature: add `transfer_arrivals: list[dict] | None = None`
- In `build_prompt()`, if `transfer_arrivals` is non-empty, insert section after the origin arrivals blocks:
  ```
  Live arrivals at transfer stop(s):
  {_format_transfer_arrivals(transfer_arrivals)}
  ```
- In `main.py`, pass `transfer_arrivals = transfer_train_arrivals + transfer_bus_arrivals` to `build_prompt()`

**Notes:**
- Combined list is fine — `_format_transfer_arrivals` groups by stop name regardless of mode
- If `transfer_arrivals` is empty or `None`, the section is omitted entirely — no prompt change for non-transfer routes

---

## Chunk 4 — Frontend: Show transfer wait inline in route card

**Files:** `frontend/src/App.jsx`, `frontend/src/App.css`

**What to build:**
- In `RouteLegs`, before rendering a transit leg, check if it is a transfer boarding leg:
  ```js
  const isTransferLeg = legs.slice(0, i).some(l => l.type === 'transit');
  ```
- If `isTransferLeg && leg.transfer_wait_minutes !== undefined && leg.transfer_wait_minutes !== null`:
  - Render a small annotation immediately above the transit leg pill:
    ```
    ⏱ Due  /  ⏱ 4 min wait
    ```
  - Use a `<span className="transfer-wait-note">` element inserted just before the `<li>` for the transit leg, or as the first child inside it
- Style `.transfer-wait-note` in `App.css`: same muted color as secondary text elsewhere, `font-size: 0.75rem`, no extra margin (sits flush above the transit leg)
- If `transfer_wait_minutes === 0`: show "Due" (not "0 min wait")
- Do not change the route card header — `waitNote` continues to reflect only the first-leg wait

**Notes:**
- The existing `waitNote` in the route card header is for `route.wait_minutes` — leave it unchanged
- This feature only adds UI when `transfer_wait_minutes` is populated; non-transfer routes and routes with no live data are unaffected
- Manual test: find a real Chicago trip requiring a train-to-train transfer (e.g. Wicker Park → Evanston: Blue Line → Red Line at Clark/Lake) and verify the wait badge appears on the Red Line leg and updates with live data

---

# Future Enhancements

Post-launch ideas and improvements. These are not bugs — the app works correctly without them. Prioritize after Phase 6 deployment based on user feedback and real usage patterns.

---

## Multi-Leg Train Routing — Shared-Track Edge Deduplication (Route Label Accuracy)

**What happens:** For each `(from_station, to_station)` edge, `_build_graph()` keeps only the single fastest route_id. On segments where multiple CTA lines share the same track and stations (e.g. Red/Brown between Belmont and Fullerton, or Red/Purple between Howard and Belmont), the edge is labelled with whichever line was fastest in the representative GTFS trip. If a rider transfers to the other line at the shared-track start station, `_path_to_route()` sees no route_id change on the shared segment and cannot detect the correct line.

**Practical effect:** Route cards on shared-track trips may show the wrong line name for the shared segment (e.g. "Red Line" when the rider is on the "Brown Line" through the shared section). Timing is still correct — only the label can be wrong.

**Future fix:** Retain separate edges per route_id for shared-track pairs in `_build_graph()`, then handle deduplication during `_path_to_route()` using incoming line context.

> **Note:** The original approach of storing `all_routes` metadata on edges was removed in the 2026-04-15 audit (`G.add_edge(..., all_routes=candidates)` removed as dead code — the field was never read). Any implementation of this fix must use the alternative approach: store multiple edges per shared-track pair and select the correct one in `_path_to_route()` based on the incoming `TransitLeg`'s `line_code`.

**Type: Structural** — modifies `_path_to_route()`. Feature B is complete — any fix here must be written against the post-B version of `_path_to_route()` (which uses `_resolve_node()` for all node metadata). No additional dependency blockers remain.

**Status: ⬜ Not started**

---

### Verification — confirm the bug before implementing

Before any code changes, run these test queries and inspect leg labels in the JSON response:

| Trip | Shared segment to watch |
|---|---|
| Linden → Evanston/Davis (Purple Exp → Red) | Howard → Belmont: should say "Purple Line", not "Red Line" |
| O'Hare → Howard, then Howard → Belmont | If routed via Red, shared segment should say "Red Line" |
| Kimball → Merchandise Mart (Brown, all-elevated) | Belmont → Fullerton segment, if applicable |

Log the `line` field on each `TransitLeg` in the returned route. If mis-labelling is absent or rare, the fix may not be worth the complexity. If it fires consistently on the Purple/Red shared segment, proceed.

---

### Chunk 1 — Fix `_path_to_route()` to use incoming line context

**File:** `backend/transit_graph.py`

**What to change:**

The transit-leg grouping block always uses `edge.get("route_id")` and `edge.get("line")` as the canonical label for the leg. The fix: before committing to that label, check whether the incoming line (from the previous `TransitLeg`) is also a valid candidate for this edge, and prefer it if so.

```python
def _last_transit_leg(legs: list) -> TransitLeg | None:
    for leg in reversed(legs):
        if isinstance(leg, TransitLeg):
            return leg
    return None
```

In the transit-leg grouping block, after reading `group_route = edge.get("route_id", "")`:

> **Important:** `all_routes` is NOT available on edges — it was removed as dead code in the 2026-04-15 audit. The correct approach is to first update `_build_graph()` to store multiple edges per shared-track station pair (one per route_id), then use incoming line context in `_path_to_route()` to select the right one.

```python
incoming = _last_transit_leg(legs)
if incoming and incoming.line_code == edge.get("route_id"):
    pass  # already on the right edge — no override needed
elif incoming:
    # check if there is a parallel edge for the incoming line_code
    # (implementation depends on chosen graph storage approach)
    pass
```

The while-loop that merges consecutive edges uses `next_edge.get("route_id") != group_route` as the break condition — this is unchanged.

Shape lookup at the end of the block calls `get_shape(group_route, group_dir)`. After the override, `group_route` and `group_dir` should carry the correct incoming-line values.

**Edge cases:**
- First transit leg (no `incoming`): no override needed; stored label is used as-is.
- Same-station transfer WalkLeg between two transit legs: `_last_transit_leg` finds the previous `TransitLeg` correctly because it searches backward past walk legs.

**Test after:** Re-run the verification queries above. Purple Line through the Howard–Belmont segment should now label as "Purple Line".

---

## Claude Haiku for Simple Queries

**What:** Route queries with only one clear option (e.g. a single direct train, no transfers) don't need Sonnet-level reasoning. Haiku is ~65% cheaper and fast enough for straightforward recommendations.

**Benefit:** Meaningful cost reduction at scale with no user-facing quality loss on simple routes.

**Type: Bolt-On** — self-contained change to `main.py`. No dependencies on any other planned feature.

**Status: ⬜ Not started**

---

### Scoping

#### Definition of "simple"

A query is **simple** if both conditions hold after routing completes:

1. `ranked_routes` contains exactly **one** route.
2. That route contains exactly **one** `TransitLeg` (no transfer — a direct ride from origin to destination).

This is the most conservative definition: Claude's only job is to format the result and give a departure time. There is no comparison between options, no transfer tradeoff, no "ride A then B" complexity. Any query with multiple routes or a transfer leg uses Sonnet.

Intentionally **not** included in the simple definition:
- Two routes on the same line (e.g. two direct Red Line options) — still requires comparison reasoning.
- One route with multiple `TransitLeg`s but no walk between them — still a transfer, still Sonnet.
- Walk-only legs (`WalkLeg`) do not count against the TransitLeg limit; a route with one `WalkLeg` + one `TransitLeg` is still simple.

#### Classifier function

Add `_is_simple_query(ranked_routes: list[tuple]) -> bool` in `main.py`:

```python
def _is_simple_query(ranked_routes: list[tuple]) -> bool:
    if len(ranked_routes) != 1:
        return False
    _, _, route = ranked_routes[0]
    transit_legs = [leg for leg in route.legs if isinstance(leg, TransitLeg)]
    return len(transit_legs) == 1
```

Call it after `ranked_routes` is finalized and before `build_prompt()`.

#### Model selection

```python
model = (
    "claude-haiku-4-5-20251001"
    if _is_simple_query(ranked_routes)
    else "claude-sonnet-4-6"
)
message = await _claude_client.messages.create(
    model=model,
    max_tokens=300 if model.startswith("claude-haiku") else 400,
    messages=[{"role": "user", "content": prompt}],
)
```

`max_tokens=300` for Haiku: a single-route direct recommendation fits comfortably in 300 tokens. Sonnet keeps 400 for complex multi-route responses.

No changes to the prompt itself — the same `build_prompt()` output is sent to both models.

#### Logging

```python
print(f"[claude model={'haiku' if model.startswith('claude-haiku') else 'sonnet'} simple={_is_simple_query(ranked_routes)}]")
```

#### Response field

Add `"model_used": "haiku" | "sonnet"` to the `/recommend` response dict. The frontend ignores this field initially — it exists for log-based cost analysis and future observability.

#### BYOK interaction

BYOK keys work with all Claude models. Apply the same model-selection logic regardless of whether the request uses a BYOK key or the server key.

#### Cache interaction

The response cache stores the full response including `model_used`. On a cache hit, Claude is not called at all — model selection is irrelevant.

#### Files to change

- `backend/main.py` — add `_is_simple_query()` helper; add model selection and `max_tokens` branching before the `_claude_client.messages.create()` call; add `model_used` to the response dict; add the stdout log line.

#### Out of scope

- Prompt differences between Haiku and Sonnet (same prompt for both — diverging prompts adds maintenance cost with no clear benefit)
- Expanding the "simple" definition to cover two-route same-line queries (deferred; measure quality first)
- Per-model cost tracking in the response or UI
- Automatic fallback from Haiku to Sonnet on low-confidence responses (not needed; the classifier is conservative by design)

---

# Feature Language — Multi-Language Support (i18n)

## Overview

Chicago is one of the most linguistically diverse cities in the US. Many transit riders speak languages beyond English as their primary language — including Spanish, Polish, Mandarin, Tagalog, Arabic, Urdu, Vietnamese, Pashto, Hindi, Korean, and others. Mainstream transit apps often support only English, or English plus a handful of Western European languages, leaving many Chicago residents underserved.

This feature adds full internationalization (i18n) to the frontend UI and Claude's AI-generated recommendation text, with a language selector that persists across sessions. The goal is to support a broad, community-representative set of languages — not just common Western ones.

**Why it matters:** The app's value proposition ("stop thinking about how to get there") is only fully realized for riders who can read it. Translating both the static UI text and the AI recommendation opens the app to a much larger share of Chicago's actual transit-riding population.

**Type: Bolt-On** — self-contained change to the frontend and the Claude prompt. No dependency on any routing feature.

**Status: ⬜ Not started**

---

## Scoping decisions — resolved

1. **i18n library:** Use `react-i18next` + `i18next`. This is the standard React i18n stack, well-maintained, supports RTL via HTML `dir` attribute, and handles dynamic string interpolation (e.g. "Walk {minutes} min") cleanly.

2. **Languages to support at launch.** Chosen to reflect Chicago's actual spoken-language demographics per census and community data:

   | Code | Language |
   |---|---|
   | `en` | English |
   | `es` | Spanish |
   | `fr` | French |
   | `it` | Italian |
   | `pl` | Polish |
   | `ro` | Romanian |
   | `uk` | Ukrainian |
   | `ru` | Russian |
   | `zh` | Chinese (Mandarin, Simplified) |
   | `yue` | Chinese (Cantonese, Simplified) |
   | `ja` | Japanese (Standard; furigana parenthetical notation — see decision 11) |
   | `ko` | Korean |
   | `tl` | Tagalog |
   | `vi` | Vietnamese |
   | `hi` | Hindi |
   | `gu` | Gujarati |
   | `pa` | Punjabi |
   | `ne` | Nepali |
   | `ur` | Urdu (RTL) |
   | `ar` | Arabic (RTL) |
   | `ps` | Pashto (RTL) |
   | `yo` | Yoruba |

   This list can be extended without structural changes — adding a language is just adding a translation JSON file and a menu entry.

3. **What gets translated.** All static UI strings in `App.jsx` are extracted into translation keys. The AI-generated `recommendation` text from Claude is handled separately (see decision 4). Station names, line names, and street names in leg data are **not** translated — they are proper nouns that must remain in their canonical CTA form for geographic accuracy.

4. **Claude recommendation language.** The `/recommend` backend accepts an optional `language` field in the request body. When present, `build_prompt()` appends a one-line instruction: `"Respond in {language_name}."` This causes Claude to write its recommendation in the user's language. No translation library is needed server-side — Claude handles it natively. The language code is mapped to a full language name (e.g. `"ur"` → `"Urdu"`) before being inserted into the prompt.

5. **Language selector placement.** A `<select>` in the existing header filters bar, next to the transit mode selector. Defaults to the browser's `navigator.language` if it matches a supported language; otherwise defaults to `"en"`. Persists to `localStorage` under key `"cta_language"`.

6. **RTL layout.** Arabic, Urdu, and Pashto are RTL scripts. When one of these languages is selected, set `document.documentElement.dir = "rtl"` and `document.documentElement.lang = langCode`. The existing CSS uses flexbox throughout; RTL flip requires only `direction: rtl` on `.app` plus a few targeted `margin-inline-start/end` adjustments (no full CSS rewrite needed). Test against Arabic at minimum.

7. **Translation files.** One JSON file per language at `frontend/public/locales/{code}/translation.json`. `i18next-http-backend` loads them on demand — only the active language is fetched. English (`en`) is the fallback: if a key is missing from a translation, the English string is shown.

8. **Translation source.** Machine-translate the English strings to seed all other language files (use any translation API or Claude directly during development). The translations do not need to be perfect for launch — native speakers can refine them in future PRs. Mark machine-translated files with a comment `// machine-translated, review welcome` at the top.

9. **Interpolation.** Dynamic strings (e.g. `"Walk {minutes} min to {destination}"`) use i18next's interpolation syntax: `"walk_to": "Walk {{minutes}} min to {{to}}"`. This is already how i18next works; no custom logic required.

10. **Scope of translated strings.** All strings visible to the user in `App.jsx`: form labels, placeholders, button text, status messages, error messages, route card metadata labels, leg descriptions, alerts copy, settings panel text. Strings that are CTA data (station names, line names, alert headlines from the CTA API) are not translated.

11. **Japanese furigana.** For the Claude recommendation text, use parenthetical furigana notation (`漢字（かんじ）`) rather than HTML `<ruby>` tags. This is a widely understood convention in Japanese texts aimed at general audiences, requires no HTML rendering changes on the frontend, and is safe to pass through the existing `renderMarkdown()` function. The Claude prompt instruction for Japanese is: `"Respond in Japanese. Use standard Japanese (a natural mix of hiragana, katakana, and kanji). Add furigana in parentheses after each kanji compound to aid readability — for example: 電車（でんしゃ）."` For static UI translation strings in `ja/translation.json`, include parenthetical furigana inline in the translated values for any kanji-heavy terms.

---

## Chunk 1 — Install i18n library and set up translation infrastructure

**Files:** `frontend/package.json`, `frontend/src/i18n.js` (new), `frontend/public/locales/en/translation.json` (new), `frontend/src/main.jsx`

**What to build:**

- Run: `npm install i18next react-i18next i18next-http-backend i18next-browser-languagedetector`
- Create `frontend/src/i18n.js`:
  ```js
  import i18n from "i18next";
  import { initReactI18next } from "react-i18next";
  import HttpBackend from "i18next-http-backend";
  import LanguageDetector from "i18next-browser-languagedetector";

  const SUPPORTED = ["en","es","fr","it","pl","ro","uk","ru","zh","yue","ja","ko","tl","vi","hi","gu","pa","ne","ur","ar","ps","yo"];

  i18n
    .use(HttpBackend)
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
      fallbackLng: "en",
      supportedLngs: SUPPORTED,
      backend: { loadPath: "/locales/{{lng}}/translation.json" },
      detection: {
        order: ["localStorage", "navigator"],
        caches: ["localStorage"],
        lookupLocalStorage: "cta_language",
      },
      interpolation: { escapeValue: false },
    });

  export default i18n;
  export { SUPPORTED };
  ```
- In `frontend/src/main.jsx`, import `"./i18n.js"` before rendering `<App />`. Wrap `<App />` with `<Suspense fallback={null}>` to handle async locale loading.
- Create `frontend/public/locales/en/translation.json` with all English strings extracted (see Chunk 2 for the full string inventory).

**Notes:**
- `i18next-browser-languagedetector` reads `localStorage["cta_language"]` first, then `navigator.language`. This gives the language selector (Chunk 3) automatic persistence for free.
- Do not add translations for other languages in this chunk — just the English baseline.

---

## Chunk 2 — Extract all UI strings into translation keys

**Files:** `frontend/src/App.jsx`, `frontend/public/locales/en/translation.json`

**What to build:**

Replace every hardcoded user-visible string in `App.jsx` with `t("key")` calls using the `useTranslation` hook (or `Trans` component for interpolated strings). Below is the complete inventory:

| Key | English value |
|---|---|
| `app_title` | `CTA Transit` |
| `tagline` | `Stop thinking about how to get there. Just go.` |
| `label_from` | `From` |
| `label_to` | `To` |
| `placeholder_location` | `Neighborhood, address, or building` |
| `btn_get_route` | `Get Route` |
| `btn_finding_route` | `Finding your route…` |
| `route_options_heading` | `Route options` |
| `badge_best` | `Best` |
| `label_min_total` | `{{minutes}} min total` |
| `label_no_transfers` | `No transfers` |
| `label_1_transfer` | `1 transfer` |
| `label_n_transfers` | `{{count}} transfers` |
| `wait_due` | `Due now` |
| `wait_minutes` | `{{minutes}} min wait` |
| `walk_from_origin` | `Walk {{minutes}} min to {{to}}` |
| `walk_to_destination` | `Walk {{minutes}} min to your destination` |
| `walk_transfer` | `Transfer — walk {{minutes}} min` |
| `exit_label_prefix` | `Exit:` |
| `steps_show` | `Steps` |
| `steps_hide` | `Hide steps` |
| `step_walk` | `Walk` |
| `step_head` | `Head` |
| `step_along` | `along` |
| `step_for` | `for` |
| `block_singular` | `block` |
| `block_plural` | `blocks` |
| `long_block_singular` | `long block` |
| `long_block_plural` | `long blocks` |
| `short_block_singular` | `short block` |
| `short_block_plural` | `short blocks` |
| `error_generic` | `Something went wrong. Please try again.` |
| `bus_data_partial` | `Bus arrival data partially unavailable — some results may be missing.` |
| `alerts_more` | `and {{count}} more` |
| `settings_title` | `Settings` |
| `settings_label_api_key` | `Your Anthropic API Key` |
| `settings_hint_api_key` | `Provide your own key and your usage won't count against the app's shared quota.` |
| `settings_error_key_format` | `Key must start with "sk-ant-"` |
| `settings_btn_save` | `Save` |
| `settings_btn_remove_key` | `Remove key` |
| `aria_close_settings` | `Close settings` |
| `aria_transit_mode` | `Transit mode` |
| `aria_language` | `Language` |
| `aria_settings_active` | `Settings (using your API key)` |
| `aria_settings` | `Settings` |
| `aria_loading` | `Finding your route` |
| `mode_all` | `All modes` |
| `mode_train` | `Train` |
| `mode_bus` | `Bus` |

Add each key to `frontend/public/locales/en/translation.json`. In `App.jsx`, call `const { t } = useTranslation()` at the top of each component that uses translated strings.

**Notes:**
- `formatBlocks()` becomes a call to `t()` with appropriate singular/plural keys — i18next's built-in plural handling (`_one`, `_other` suffixes) can be used, but for simplicity in Chunk 2, just use separate singular/plural keys as listed above.
- The `"and X more"` alerts string uses `Trans` or a simple template: `t("alerts_more", { count: result.alerts.length - 3 })`.
- Do not yet add the language selector in this chunk — just wire up `t()` calls against English strings and verify the app still works identically.

---

## Chunk 3 — Add language selector to header

**Files:** `frontend/src/App.jsx`

**What to build:**

- Import `{ useTranslation }` and `{ SUPPORTED }` from `./i18n.js`.
- Add a `<select>` in the `.filters` div, adjacent to the transit mode selector:
  ```jsx
  const { i18n, t } = useTranslation();

  <select
    value={i18n.language}
    onChange={(e) => i18n.changeLanguage(e.target.value)}
    aria-label={t("aria_language")}
  >
    {SUPPORTED.map((code) => (
      <option key={code} value={code}>{LANGUAGE_NAMES[code]}</option>
    ))}
  </select>
  ```
- Add `LANGUAGE_NAMES` constant in `App.jsx` (not in a translation file — these are the native-script names displayed to speakers of each language):
  ```js
  const LANGUAGE_NAMES = {
    en: "English",    es: "Español",      fr: "Français",    it: "Italiano",
    pl: "Polski",     ro: "Română",       uk: "Українська",  ru: "Русский",
    zh: "中文（普通话）",  yue: "粤语",         ja: "日本語",       ko: "한국어",
    tl: "Filipino",   vi: "Tiếng Việt",   hi: "हिंदी",        gu: "ગુજરાતી",
    pa: "ਪੰਜਾਬੀ",     ne: "नेपाली",        ur: "اردو",         ar: "العربية",
    ps: "پښتو",        yo: "Yorùbá",
  };
  ```
- Wire RTL: add a `useEffect` that watches `i18n.language` and sets `document.documentElement.dir` and `document.documentElement.lang`:
  ```js
  const RTL_LANGS = new Set(["ar", "ur", "ps"]);
  useEffect(() => {
    document.documentElement.dir = RTL_LANGS.has(i18n.language) ? "rtl" : "ltr";
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);
  ```
- `i18n.changeLanguage()` automatically persists to `localStorage["cta_language"]` via the detector config in Chunk 1.

**Notes:**
- Native-script language names (العربية, 中文, etc.) must appear in the `<option>` elements — not English names — so a speaker of that language can find their own language in the list.
- At this point, switching to a non-English language will show English strings (fallback) because other translation files don't exist yet. That is expected. Test that the selector persists across page refreshes and that RTL flip works for Arabic.

---

## Chunk 4 — Create translation files for all supported languages

**Files:** `frontend/public/locales/{es,fr,it,pl,ro,uk,ru,zh,yue,ja,ko,tl,vi,hi,gu,pa,ne,ur,ar,ps,yo}/translation.json`

**What to build:**

For each language code, create `frontend/public/locales/{code}/translation.json` containing translations of every key from the English file. Seed using machine translation (use Claude or any translation API).

Guidelines for each translation:
- Keep dynamic placeholders (`{{minutes}}`, `{{to}}`, `{{count}}`) exactly as they appear in the English source — i18next requires them to match.
- Transit-specific terms like "Bus", "Train" should be translated naturally in context.
- "CTA Transit" in `app_title` should not be translated — it is a proper name.
- For RTL languages (ar, ur, ps): the JSON values themselves are RTL text, but the JSON file format and keys remain LTR. No special file encoding needed.

Add a comment at the top of each non-English file (as a `"_comment"` key): `"machine-translated, review welcome"`.

**Notes:**
- 22 languages × ~45 keys = ~990 string translations total. Seed in one or two Claude sessions, grouping by script family for consistency.
- For `ja/translation.json`: include parenthetical furigana inline in values for kanji-heavy terms (e.g. `"btn_get_route": "経路（けいろ）を取得（しゅとく）"`) — no special tooling needed.
- After seeding, do a spot-check on at least 3 languages by switching the selector and reading through the UI.
- RTL languages: verify that Arabic, Urdu, and Pashto text renders correctly in-browser and that the layout flips properly (form labels on the right, chevron on the left, etc.).

---

## Chunk 5 — Backend: Pass language to Claude prompt

**Files:** `backend/main.py`

**What to build:**

- In the `/recommend` endpoint, read `language: str | None = None` from the request body (add to the request schema).
- Add a `LANGUAGE_NAMES` dict in `main.py` mapping all 22 language codes to their full English names. English names are used in the prompt because that is Claude's instruction language:
  ```python
  LANGUAGE_NAMES = {
      "en": "English",           "es": "Spanish",            "fr": "French",
      "it": "Italian",           "pl": "Polish",             "ro": "Romanian",
      "uk": "Ukrainian",         "ru": "Russian",            "zh": "Mandarin Chinese",
      "yue": "Cantonese Chinese","ja": "Japanese",           "ko": "Korean",
      "tl": "Filipino (Tagalog)","vi": "Vietnamese",         "hi": "Hindi",
      "gu": "Gujarati",          "pa": "Punjabi",            "ne": "Nepali",
      "ur": "Urdu",              "ar": "Arabic",             "ps": "Pashto",
      "yo": "Yoruba",
  }
  ```
- In `build_prompt()`, add an optional `language: str | None = None` parameter. If non-null and not `"en"`, construct the closing instruction based on the language:
  - For Japanese (`language == "ja"`): append `"Respond in Japanese. Use standard Japanese (a natural mix of hiragana, katakana, and kanji). Add furigana in parentheses after each kanji compound to aid readability — for example: 電車（でんしゃ）."`
  - For all other non-English languages: append `"Respond in {LANGUAGE_NAMES[language]}."`
- In `main.py`, pass `language=language` (the raw code from the request) directly to `build_prompt()`.
- In the frontend `handleSubmit`, include `language: i18n.language` in the request body alongside `origin`, `destination`, and `transit_mode`.

**Notes:**
- If `language` is `"en"` or absent, do not append any instruction — Claude defaults to English already, and adding it wastes tokens.
- This is the only backend change for this feature. No translation library, no additional dependencies.
- Claude handles all listed scripts (Arabic, Urdu, Pashto, Cyrillic, Devanagari, CJK, etc.) natively.
- Test manually: set language to Urdu in the selector, submit a query, and verify that the recommendation text is in Urdu script. Set to Japanese and verify parenthetical furigana appears.

---

## Chunk 6 — CSS: RTL layout adjustments

**Files:** `frontend/src/App.css`

**What to build:**

Audit the existing CSS for properties that break under RTL and replace with logical properties or add `[dir="rtl"]` overrides. Key areas to check:

- Any `margin-left` / `margin-right` or `padding-left` / `padding-right` on flex children that creates visual asymmetry under RTL. Replace with `margin-inline-start` / `margin-inline-end` where safe, or add targeted `[dir="rtl"]` overrides.
- `.leg-pill` — floated or flex-start positioned; verify it aligns correctly when the row direction flips.
- `.route-chevron` — `▲` / `▼` chevrons don't flip; `◄` / `►` would need to, but these aren't used. No change needed.
- `.alerts-more` link — verify text alignment under RTL.
- Form layout — `<label>` spans should right-align under RTL; `text-align: start` (already logical) handles this if used.

**Acceptance criteria:**
- No text or element visually overlaps under Arabic, Urdu, or Pashto.
- Form inputs, buttons, and route cards all read correctly right-to-left.
- LTR layout (English and all other languages) is unchanged.

**Notes:**
- Do not rewrite the entire CSS file. Only change properties where a visual bug is confirmed in-browser.
- Test by selecting Arabic, Urdu, and Pashto in the language selector and visually inspecting the full app flow: form → submit → route cards → walk steps.

---

# Feature K — Restore Street-Network Walking Graph in Production

## Overview

`backend/street_graph.graphml` is a 120 MB OSMnx pedestrian network of Chicago, used by [walking.py](backend/walking.py) (`walk_minutes`, `walk_directions`, `walk_path`) to produce street-routed walking times, turn-by-turn directions, and curved Shapely polylines for the map view. The file is committed via Git LFS but **not present at runtime in the Railway deployment**:

- Rebuilding from OpenStreetMap via `fetch_street_graph.py` OOM-kills on the Railway free memory tier.
- Pulling the LFS object at Docker build time via `media.githubusercontent.com/media/...` returns 404 (likely LFS-bandwidth quota exhausted, or LFS objects not publicly served for this repo).
- Current state (commit 954c7fa + Dockerfile change in this commit): runtime falls back to Haversine straight-line walking estimates. App is functional but walking UX is degraded — walk minutes are crow-flies, "directions" collapse to a single `"Walk"` step, and the drawn walk path is a straight line rather than following streets.

**Goal:** Get the real graphml onto the deployed container so `walking.py` loads it at startup, restoring street-routed walking. Do this without paying for a Railway memory upgrade and without depending on GitHub LFS bandwidth.

**Type: Bolt-On** — backend-only; no frontend or routing-engine changes. Restoring the graph file is transparent to all callers because the fallback path in [walking.py:53-66](backend/walking.py#L53-L66) is already in place.

**Status: ⬜ Not started**

**Prerequisites:** None. The Dockerfile already contains the preserved curl block (commented out under `--- PRESERVED FOR FUTURE RESTORATION (Feature K) ---`); restoration is mostly a matter of pointing it at a working URL.

---

## Hosting options (pick one in Chunk 1)

1. **GitHub Release asset.** Upload `street_graph.graphml` as a binary asset on a tagged release (e.g. `street-graph-v1`). Public download URL is stable, served by GitHub's CDN, and not subject to LFS bandwidth limits. **Recommended** — zero infra cost, no new accounts.
   - URL pattern: `https://github.com/AdamBHonaker/CTA-Transit-PWA/releases/download/<tag>/street_graph.graphml`
2. **Cloudflare R2.** Free tier covers 10 GB storage + 10M reads/mo. Pay $0 for this use case. Requires a Cloudflare account and one bucket.
3. **AWS S3 / Backblaze B2.** Similar to R2 but with non-zero egress cost on AWS. Avoid unless already in use.
4. **Railway volume.** Mount a persistent volume, upload the file once via `railway run`. Avoids any external host but adds a Railway resource and complicates local/dev parity. Lowest priority.

## Chunk 1 — Choose host and upload graphml

- Pick from the four options above (default: GitHub Release).
- Upload the local `backend/street_graph.graphml` (120 MB, sha256 `55a82d0fc8eadbd47289fc3e4ad37130a187622343c15f65dcabdff0a4a58afc` per the LFS pointer).
- Verify the public download URL works with `curl -fSL` and that `Content-Length` matches the local file size.

## Chunk 2 — Re-enable Dockerfile curl step

- In `backend/Dockerfile`, uncomment the block under `--- PRESERVED FOR FUTURE RESTORATION (Feature K) ---`.
- Update the `STREET_GRAPH_URL` ARG default to the new host URL.
- Keep both safety checks intact (size ≥ 1 MB; reject LFS-pointer stub).
- Optional: pin to a specific Release tag rather than `latest`/`main` so future graph regenerations don't silently change the deployed file.

## Chunk 3 — Verify in production

- Trigger a Railway redeploy.
- Watch the build log for `street_graph.graphml: <bytes> bytes` (should be ~120 MB).
- Watch the runtime startup log for `[walking] Graph loaded: <N> nodes, <M> edges` (vs. the current `Street graph not found ... Haversine fallback`).
- Spot-check one trip in the live app: confirm `walk_minutes` reports street-routed values (not Haversine), `walk_directions` returns multiple named-street steps, and the map's walk path follows actual streets rather than a straight line.

## Acceptance criteria

- Build completes without 404 on the graph URL.
- Backend logs confirm graph loaded at startup.
- Live app shows multi-step walk directions and curved walk paths on the map for at least one verified trip.
- No regression in build time beyond the ~5–10 s curl download.

## Notes / gotchas

- The graphml is regenerated by `fetch_street_graph.py` whenever the OSM bbox changes. After any regeneration, re-upload to the chosen host and (if pinned) bump the Release tag in the Dockerfile.
- If memory becomes the limiting factor again at runtime (graph load is ~300 MB resident), revisit the bbox in `fetch_street_graph.py:36` rather than abandoning street routing.
- Feature K is purely operational; once the file is reachable from the build, all routing/UX behavior is restored automatically by existing code.
- This chunk can be done in parallel with Chunk 4 (translation files) if needed — they are fully independent.
