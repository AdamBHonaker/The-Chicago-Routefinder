# Privacy notes

This app collects the minimum information needed to operate the service and
to publish coarse, aggregate usage numbers. It uses **no third-party
analytics scripts**, no fingerprinting, and no persistent cross-day user
identifiers.

The only third-party processor in the request path is **LocationIQ**, used
as a narrow Tier-5 fallback when the local-first geocoder cascade can't
resolve an address. See **Geocoding & autocomplete (LocationIQ)** below
for what is sent, when, and how to opt out as a self-hoster.

## What is collected

### Daily unique visitors (DAU)

Implemented in [backend/dau.py](../backend/dau.py).

- The visitor's IP is HMAC-SHA256-hashed with a daily-rotating salt and held
  only in an in-memory set for the current Chicago calendar day.
- At day rollover the set is discarded; only the final integer count is
  written to disk. There is no IP-to-day mapping persisted, anywhere.
- Because the salt rotates daily, today's hash and yesterday's hash for the
  same IP are unrelated — cross-day correlation is cryptographically
  prevented.

### Approximate geography (FEAT-003)

Implemented in [backend/geography.py](../backend/geography.py).

> **Status (temporarily disabled):** MaxMind GeoLite2-City lookups are
> currently turned off in production to reduce Railway memory footprint
> (~60–80 MB saved by not loading the `.mmdb` reader). The
> `MAXMIND_LICENSE_KEY` build arg is unset, so the Dockerfile skips the
> DB download and `backend/geography.py` silently no-ops at runtime — no
> IPs are resolved, no city names are derived, and no new rows are
> written to `geography.json`. Historical per-day per-city counters
> already on disk are retained but no longer updated. The behaviour
> described below applies once geography counting is re-enabled (by
> restoring the MaxMind key and redeploying); the privacy posture is
> unchanged when it returns.

- The visitor's IP is fed to MaxMind GeoLite2-City **in memory only** to
  derive a coarse city name. The IP is never written alongside the city.
- Only a per-day, per-city integer counter is persisted. There is no per-IP
  row, no IP-to-city mapping, and no cross-day per-user state.
- A privacy floor (default: cities below 5 visits in a single day) buckets
  rare cities into "Other" on read, so a single visitor in a small suburb
  cannot be re-identified from the per-city panel.
- The "Chicago metro share" rollup is computed at read time from a static
  list of Cook + collar-county municipalities; the metro list itself is not
  per-user data.

### New vs returning visitors (FEAT-002)

Implemented in [backend/retention.py](../backend/retention.py).

- A 90-day opaque random ID (`returnId`) is set in an `httpOnly` `Secure`
  cookie (`SameSite=None` in production for cross-site Vercel↔Railway
  delivery, `SameSite=Lax` in local dev). The raw value is never written to
  disk — only a stable HMAC fingerprint derived from it is stored.
- Server stores a **rolling Bloom filter** of fingerprints (HMAC-SHA256
  with a stable per-deployment retention key). The filter is the only
  persistent cross-day artifact.
- Daily aggregate: `{date, new: int, returning: int}`. "Returning" = the
  visitor's fingerprint was probably seen on a previous day, subject to
  the Bloom filter's ≤1% false-positive rate.
- **Accepted privacy tradeoff:** This feature uses a stable (non-daily-
  rotating) key so the same browser can be recognised across days. You can
  ask "is this fingerprint probably in the set?" but not "who is this
  user?" The `returnId` is an opaque random token with no PII linkage. This
  is the explicitly documented tradeoff in the FEAT-002 scope — it is
  narrower than a traditional cookie tracker (aggregate-only, no event
  sequence, no PII binding) but it does introduce limited cross-day
  correlation that the other analytics features avoid.
- GDPR/CCPA: the `returnId` cookie is a functional analytics cookie (not
  an advertising or tracking cookie). EU consent banner is deferred until
  EU traffic becomes non-trivial.

### Sessions (FEAT-001)

Implemented in [backend/sessions.py](../backend/sessions.py).

- A short-lived random session ID is set in an `httpOnly` `Secure` cookie
  (`SameSite=None` in production for cross-site Vercel↔Railway delivery,
  `SameSite=Lax` in local dev) with a 30-min sliding TTL. The raw ID lives
  in memory only for the lifetime of the cookie.
- Before any internal logging or comparison the ID is HMAC-SHA256-hashed
  with the same daily-rotating salt that DAU uses, so a debugging
  breadcrumb can never correlate a session across days.
- Server stores **only** an aggregate-per-day record:
  `{date, sessions, total_duration_seconds, bounces}`. There is no
  per-session row anywhere on disk.
- Bounce = a session that recorded fewer than two `/recommend` requests
  before its 30-min idle timeout.
- The cookie is discarded at midnight Chicago: the salt rotates at that
  boundary so yesterday's cookie value no longer matches today's hash
  and the visitor begins a fresh session.

### Hour-of-day distribution (FEAT-004)

Implemented in [backend/hourly.py](../backend/hourly.py).

- Per-day 24-int array (Chicago timezone) incremented when a
  recommendation is requested. Identical privacy posture to DAU —
  counts only, no PII.

### Device class (FEAT-005)

Implemented in [backend/devices.py](../backend/devices.py).

- The User-Agent header (sent by every browser anyway) is parsed in
  memory only. The raw UA string is **never persisted** — only the
  bucket the parser produced (mobile / tablet / desktop / bot /
  unknown).
- Bots are recorded for diagnostics but excluded from the public
  mobile/tablet/desktop split.

### Referrers (FEAT-008)

Implemented in [backend/referrers.py](../backend/referrers.py).

- The `Referer` header is parsed to a hostname; path and query are
  stripped before any storage decision is made (so accidental
  UTM-params containing PII never reach disk).
- Bucketed into `direct` / `search` / `social` / `other`. The `other`
  bucket retains per-hostname counts so a press mention is visible.
- The per-hostname long-tail table is admin-only — never exposed via
  `/stats/*` — because a low-volume host could identify a single
  visitor's prior page.

### Engagement events (FEAT-006)

Implemented in [backend/events.py](../backend/events.py).

- Named in-app actions (e.g. `recommend_submitted`, `route_selected`,
  `trip_completed`) are reported by the frontend to a strict server-side
  allowlist (`EVENT_ALLOWLIST`). Names outside the allowlist are
  rejected — the on-disk schema cannot be expanded by a malicious
  client.
- Only a daily aggregate per event name is persisted (`{date: {event:
  count}}`). The per-session sequence, the order in which events
  fired, and any per-session row are never persisted.
- The public dashboard surfaces only the four advertiser-facing event
  volumes (`recommend_submitted`, `recommend_returned`,
  `route_selected`, `trip_completed`). Internal/operational events
  (`app_loaded`, `map_opened`, `start_route_tapped`,
  `house_ad_clicked`, the off-route diagnostics `trip_off_route` /
  `trip_rerouted` / `off_route_dismissed`, and the PWA install-prompt
  events `install_prompt_shown` / `install_prompt_accepted` /
  `install_prompt_dismissed` / `install_completed`) stay admin-only
  because they are navigation signals an outside viewer could ratio
  against DAU to infer per-user behaviour.

### Funnel completion (FEAT-007)

Implemented in [backend/funnel.py](../backend/funnel.py), driven by
finalisation hooks in [backend/sessions.py](../backend/sessions.py).

- The funnel records, per session, the highest stage reached
  (`app_loaded` → `recommend_submitted` → `recommend_returned` →
  `route_selected` → `start_route_tapped` → `trip_completed`). When a
  session finalises (idle timeout or day rollover) the per-stage
  cumulative arrays for that day are incremented.
- Nothing per-session is ever written to disk. The on-disk file
  (`funnel.json`) contains only the daily cumulative arrays.
- The public dashboard reports a single derived figure
  (`recommend_returned / app_loaded`) — the "got a result" rate.

### Public stats dashboard (FEAT-009)

Implemented in [backend/public_stats.py](../backend/public_stats.py).

The page at `/stats` is served from this app's own infrastructure and loads
no third-party scripts. It exposes a strict whitelist of fields:

- DAU per day: `{date, count}`
- Chicago-metro per day: `{date, metro, total, share_pct}`
- Sessions per day: `{date, sessions, avg_duration_seconds, bounce_rate_pct}` — the raw `total_duration_seconds` and `bounces` integers stay admin-only.
- Hour-of-day per day: `{date, hours: int[24], total}`
- Device class per day: `{date, mobile, tablet, desktop, total}` — `bot` and `unknown` are admin-only.
- Referrers per day: `{date, direct, search, social, other, total}` — the per-hostname `other` table is admin-only.
- Events per day: `{date, recommend_submitted, recommend_returned, route_selected, trip_completed, total}` — internal/operational event counts (`app_loaded`, `map_opened`, `start_route_tapped`, `house_ad_clicked`) stay admin-only, and `total` covers only the published events so the gap can't be back-solved.
- Funnel per day: `{date, stages: int[6], result_rate_pct}` — derived from the FUNNEL_STAGES list; admin-only fields are never published.
- Retention per day: `{date, new, returning, total}` — Bloom filter utilisation and per-fingerprint state stay admin-only.

The per-city table is admin-only and is never reachable from `/stats/*`.
The whitelist is enforced by
[backend/tests/test_public_stats.py](../backend/tests/test_public_stats.py),
which fails the build if any field outside the whitelist appears in a
public response.

### Geocoding & autocomplete (LocationIQ)

Implemented in [backend/geocoding.py](../backend/geocoding.py) and
[backend/local_search.py](../backend/local_search.py).

Free-text location resolution runs a five-tier cascade. The first four
tiers are local-only:

1. Coord-pair regex (`"41.88, -87.63"`) — no network.
2. Curated `NEIGHBORHOOD_COORDS` exact match — no network.
3. Fuzzy match against the same dict (≥0.95 similarity) — no network.
4. Local SQLite/FTS5 search over a Chicago-only OSM address +
   intersection corpus — no network.
5. **LocationIQ `/search`** (forward) or **`/reverse`** (reverse) —
   the only network call, used only when tiers 1–4 miss.

#### When LocationIQ is called

- **Forward (typed query):** when none of tiers 1–4 returns a match for
  the typed text. In practice this is queries that aren't a Chicago
  landmark / neighborhood and either fall outside the local OSM corpus
  or use a phrasing the corpus normalization didn't match. The
  `/autocomplete` endpoint **never** calls LocationIQ on its own (per
  the chunked plan's Decision 5) — only submit-time forward resolution
  does, and even then only after the four cheaper tiers have all missed.
- **Reverse (geolocate button):** when the geolocate button's
  reverse-resolve cascade falls through `cached_reverse` → KDTree
  neighborhood (≤200 m) → local nearest-address (≤50 m) without a
  match. In normal Chicago use this fallthrough is rare — the
  neighborhood tier catches most positions.

#### What is sent

- The typed text (forward) or the lat/lon (reverse), biased to a
  Chicago viewbox via LocationIQ's `viewbox` + `bounded=1` parameters.
- The deployment's outbound IP (Railway egress). **No rider
  identifier**, **no session cookie**, **no `Referer`**, **no
  User-Agent beyond the default `requests` library string** is sent.

#### What is logged

- The query text is hashed to a 10-character SHA-256 tag (`q#abcd1234ef`)
  before any log line is written. Logs never contain the verbatim typed
  text.
- Resolved coordinates are quantized to ~1 km precision before logging
  (two decimal places). A log line never pins a user to an address.

#### What is cached locally and for how long

- Positive responses are cached in `cached_forward` (queries) and
  `cached_reverse` (lat/lon pairs) inside
  `backend/static_data/chicago_geocode.db`, alongside the address +
  intersection corpus.
- Definitive "no match" responses are cached as `NEG_HIT` rows so a
  repeated bad query never re-leaks the typed text to LocationIQ.
- Each row stores `fetched_at` (Unix epoch). A startup-time sweep
  deletes rows older than `LOCATIONIQ_CACHE_TTL_DAYS` (default 90 days)
  on every FastAPI lifespan startup — one DELETE per table, scaling with
  rows-evicted not query rate. Operators can opt out by setting the
  env var to `0`. The choice of startup-time rather than a background
  timer is deliberate: write rate is bounded by `LOCATIONIQ_DAILY_CAP`
  (4 900 / UTC-day), so anything that ages out between deploys ages out
  at the next deploy's sweep.

#### Rate ceiling

- A UTC-day call counter (`LOCATIONIQ_DAILY_CAP`, default 4 900 — set
  100 below the free-tier ceiling of 5 000) bounds maximum LocationIQ
  traffic per deploy. When the cap is hit, the cascade silently
  degrades to **local-only** for the rest of that UTC day — typed
  queries that would have needed LocationIQ simply don't resolve, with
  no automatic retry. One warning is logged the first time the cap is
  hit on a given day.
- A separate 60→120→240→300 s circuit breaker trips on HTTP 429
  responses from LocationIQ and keeps Tier 5 closed until the cool-off
  elapses. The first call after cool-off is a probe; success closes
  the breaker.

#### Opt-out

Self-hosters with stricter privacy postures can disable Tier 5
entirely by setting **`LOCATIONIQ_ENABLED=false`** in the Railway
environment. With Tier 5 disabled, the cascade is local-only end-to-end
and any query that misses tiers 1–4 returns "not found" rather than
escaping to a third party. Missing API key (`LOCATIONIQ_API_KEY`
unset) has the same effect — Tier 5 is silently skipped.

#### Third-party retention

LocationIQ's own retention of requests it receives is governed by
LocationIQ's privacy policy (see <https://locationiq.com/privacy>),
not by this app. The Tier-5 cascade keeps LocationIQ's surface as
narrow as possible: a typed query only reaches LocationIQ when none
of the four cheaper local tiers — coord regex, curated dict, fuzzy
dict, local OSM corpus — could resolve it.

## What is **not** collected

- No fingerprinting (canvas, fonts, audio, WebGL, screen size, etc.).
- No third-party analytics or marketing tags.
- No raw IP addresses, User-Agent strings, or reversible identifiers on disk.
- The `returnId` cookie (FEAT-002) is the only persistent cross-day identifier;
  it is an opaque random token with no PII linkage — see the FEAT-002 section
  above for the explicit privacy tradeoff.

## Where the data lives

All analytics data is stored on the same Railway-hosted backend as the
application itself. The only outbound user-derived data leaving Railway
goes to **LocationIQ** for the geocoder's Tier-5 fallback (see the
dedicated section above for scope and frequency). No data leaves Railway
for analytics purposes — the analytics surface is fully self-hosted. The
persisted analytics artifacts are:

- `backend/data/dau.json` — per-day visitor counts.
- `backend/data/geography.json` — per-day per-city counts.
- `backend/data/sessions.json` — per-day session aggregates (no per-session rows).
- `backend/data/hourly.json` — per-day 24-int hour histograms.
- `backend/data/devices.json` — per-day device-class buckets.
- `backend/data/referrers.json` — per-day traffic-source buckets.
- `backend/data/events.json` — per-day per-event-name counts (FEAT-006).
- `backend/data/funnel.json` — per-day funnel-stage cumulative arrays (FEAT-007).
- `backend/data/retention.json` — per-day new/returning aggregates + Bloom filter
  bit array (no raw IDs or reversible identifiers).

If you'd like the data deleted, contact the maintainer.
