# Analytics suite — ongoing maintenance

The analytics suite (FEAT-001 through FEAT-009) is built in-house specifically
to avoid the recurring cost and vendor risk of a third-party analytics tool
([docs/FEATURE_PLANS.md](FEATURE_PLANS.md), Consideration A). That decision
implies that *we* now own the maintenance work that Plausible/Fathom would
otherwise absorb. This file consolidates every feature's maintenance burden
in one place so the suite is supportable without re-deriving each module's
quirks from code.

Append a new section to this file as each FEAT lands. A feature is not
"done" until its maintenance entry is written here.

---

## FEAT-002 — New vs returning visitors

**Module:** [backend/retention.py](../backend/retention.py)

### Dependency upkeep

None — implemented with `hmac`, `hashlib`, `base64`, and `math` from the
standard library. No external packages required.

### Bloom filter lifecycle

- **Capacity:** `BLOOM_CAPACITY = 10 000` fingerprints at ≤1% FPR (~12 KB
  on disk). At ~200 DAU the filter fills in roughly **50 days**. At 1 000
  DAU it fills in ~10 days.
- **Auto-reset:** when `filter_count ≥ BLOOM_CAPACITY` the module logs a
  warning and resets the filter in-memory. This keeps FPR bounded at the
  cost of losing the historical visitor set — everyone appears as "new"
  after a reset. The reset is logged at WARNING level; check Railway logs
  if the returning-visitor % unexpectedly drops to 0.
- **Manual clear:** delete `backend/data/retention.json` (or
  `/app/data/retention.json` in production) and restart. The filter
  resets; all subsequent visitors are "new" until the filter re-fills.
- **Resize:** if DAU grows significantly, bump `BLOOM_CAPACITY` in
  `retention.py` (e.g. to 100 000 for ~1 000 DAU × 90-day coverage at
  ≤1% FPR). The new filter is ~120 KB on disk. After changing the
  constant, clear the existing `retention.json` so the old bits (sized
  for the old M) are replaced.

### Sizing decisions

- `BLOOM_K = 7` hash functions — derived from the optimal formula
  `k = (m/n) × ln(2)`. This is correct at the stated capacity.
- `BLOOM_CAPACITY = 10 000` is conservative for current traffic; it was
  chosen to balance FPR (low at fill) against file size (12 KB).
- Cookie max-age = **90 days** (industry standard for "returning user").
  If a shorter window is wanted (e.g. 30-day retention), reduce both
  `COOKIE_MAX_AGE` and the expected fill horizon in this doc.

### Privacy tradeoff (accepted — see FEAT-002 scope)

The Bloom filter uses a **stable** retention key (`DAILY_SALT + ":retention"`)
rather than the daily-rotating salt. This is intentional: the daily-rotating
salt prevents cross-day lookup, which is the exact capability this feature
needs. The tradeoff — that the same browser can be recognised across days —
is explicitly accepted in the FEAT-002 scope and documented in
[docs/PRIVACY.md](PRIVACY.md). The `returnId` cookie is an opaque random
token with no PII linkage; the Bloom filter stores only one-way HMAC hashes.

### Operational alarms

- If the returning-visitor % on `/stats/retention` unexpectedly drops to
  near 0% on a day with significant traffic, the Bloom filter likely
  auto-reset (filter hit capacity). Check `filter.utilisation_pct` via
  `check_retention.py` and confirm the warning appears in Railway logs.
- The `check_retention.py` script prints a WARNING banner when
  `utilisation_pct ≥ 80%`. Run it periodically (e.g. monthly) and
  schedule a clear/resize before the filter fills completely.

---

## FEAT-003 — Approximate geography

**Module:** [backend/geography.py](../backend/geography.py)

### Dependency upkeep

- `geoip2` Python SDK — pinned in [backend/requirements.txt](../backend/requirements.txt).
  Bump in lockstep with security advisories.

### Database refresh

- **GeoLite2-City** (`/app/GeoLite2-City.mmdb`) is downloaded at Docker build
  time from MaxMind. MaxMind publishes updates **every Tuesday**.
- Cadence: redeploy at least monthly so the DB is no more than ~5 weeks
  stale. If deploys go quiet, set a calendar reminder for the **first
  Tuesday of each month** to trigger a redeploy.
- If MaxMind retires the free tier or revokes the license key, the
  Dockerfile build prints `[geoip] MAXMIND_LICENSE_KEY not set — skipping`
  and the runtime DB load logs `[geography] DB not found … geography
  counting disabled`. Geography counting silently no-ops in that state —
  not a crash, but the metro panel reports 0%.

### Threshold and sizing decisions

- `_OTHER_BUCKET_THRESHOLD` (default **5**) is the privacy floor: cities
  below this daily count collapse into "Other" on read. Lower only if DAU
  grows enough that 5 stops being a meaningful disclosure threshold.
- `_CHICAGO_METRO_CITIES` is the canonical metro rollup list (Cook + the
  five collar counties' principal municipalities). Edit when adding
  suburbs to the pitch.
- `_FLUSH_EVERY_N_WRITES` (default **20**) controls how many visits are
  buffered in-memory before flushing the per-day per-city map to disk.
  A server kill -9 between flushes drops up to 20 visits — acceptable for
  an aggregate counter; bump only if the disk-write rate becomes a
  bottleneck.

### Operational alarms

None today. If the GeoLite2 DB stops loading, the metro panel reports 0%
silently — consider adding a startup log assertion if/when "metro share"
becomes a numbered KPI.

---

## FEAT-001 — Sessions counter

**Module:** [backend/sessions.py](../backend/sessions.py).

### Dependency upkeep

None — built on `secrets` and `hmac` from the standard library.

### Threshold and sizing decisions

- `IDLE_TIMEOUT_SECONDS` (default **1800**, i.e. 30 min) controls both
  the cookie's sliding TTL and the server-side idle-finalisation cutoff.
  Industry-standard for engagement reporting; bump only if real session
  patterns suggest it.
- Bounce threshold: a session is a bounce if it recorded fewer than
  **2** `/recommend` requests before idle-expiring. Documented in
  [docs/PRIVACY.md](PRIVACY.md) so advertiser-quoted bounce rates are
  interpretable.
- `_FLUSH_EVERY_N_WRITES` (default **5**) is smaller than other
  counters' batch sizes because each "write" represents a finalised
  session, not a single request — the disk write rate is naturally
  much lower.

### Operational alarms

- If active sessions accumulate without expiring (e.g. an idle-cleanup
  bug), the in-memory `_active` dict grows unboundedly. There is no
  alert on this today; if seen, dump and inspect via the admin token.
- Mean session length is inflated by up to 30 min for the visitor's
  last request because session-end is detected via idle timeout. This
  is documented in the dashboard footer.

### Cookie and CORS

- Cookie attributes: `httpOnly` `Secure` `SameSite=Lax`, set by
  `backend/main.py` `_analytics_middleware`. `Secure` is conditional
  on `APP_ENV=production` so local dev over plain HTTP still works.
- CORS: `allow_credentials=True` is required for the cookie to flow
  cross-origin. `ALLOWED_ORIGINS` must remain an explicit list — the
  combination of `allow_credentials=True` and a wildcard origin is a
  spec error and most browsers will refuse.

---

## FEAT-004 — Hour-of-day distribution

**Module:** [backend/hourly.py](../backend/hourly.py).

Trivially small. The counter is a 24-int array per day. Increments fire
on `/recommend` only — counting all requests would inflate the histogram
with health checks. No external dependencies, no thresholds, no
alarms.

---

## FEAT-005 — Device class

**Module:** [backend/devices.py](../backend/devices.py).

### Dependency upkeep

- `ua-parser` Python package — pinned in
  [backend/requirements.txt](../backend/requirements.txt). The library's
  embedded regex DB needs periodic refresh as new browsers and OS
  versions ship; bump the pin during normal dependency upkeep, ideally
  every 3–6 months.
- If `ua-parser` is unavailable at runtime the module falls back to
  crude string-matching heuristics so the counter still produces a
  reasonable bucket. A long-running fallback is fine; a permanent one
  means the regex DB can drift undetected — keep the dep pinned.

### Bucketing decisions

- iPad in desktop-mode UA (Safari's default since iPadOS 13) is
  classified as **desktop**. Industry convention.
- Bots are tracked but excluded from the public mobile/tablet/desktop
  split (see `public_stats.project_devices`).

---

## FEAT-008 — Referrer / traffic source

**Module:** [backend/referrers.py](../backend/referrers.py).

### Maintenance

- `_SEARCH_HOSTS`, `_SEARCH_SUFFIXES`, and `_SOCIAL_HOSTS` are
  hardcoded constants. The lists churn slowly — review yearly or when
  a new search engine / social platform becomes meaningful in real
  referrer traffic. The most likely additions are post-Twitter
  fragmentation (Bluesky, Threads, Mastodon — already included) and
  AI-search referrals (Perplexity is included).
- `_OWN_HOSTNAMES` is derived from `ALLOWED_ORIGINS` at startup so
  internal navigations bucket as `direct`. If the app gets a custom
  domain, update `ALLOWED_ORIGINS` and the new domain auto-flows.
- UTM params are deliberately not captured. Re-add as a separate
  feature only if a marketing campaign actually launches and you need
  per-campaign attribution.

### Privacy floor (long-tail hosts)

The per-hostname `other` table is admin-only. If real referrer traffic
ever includes a host so rare that even the *existence* of the entry is
a re-identification risk, the projection function in
`public_stats.py` already drops the table — no further redaction
needed for the public surface. If admin-side analysis surfaces a
sensitive host, redact it from the on-disk file manually.

---

## FEAT-009 — Public stats dashboard (v1)

**Modules:** [backend/public_stats.py](../backend/public_stats.py),
serves at `/stats`, `/stats/dau`, `/stats/geography`.

### Dependency upkeep

None — the dashboard is pure HTML + inline JS, no client libraries.
A future panel may pull in a chart library (Chart.js / uPlot); that
choice and its upgrade cadence will be documented here when the first
chart-needing panel lands.

### Adding a new panel as a new FEAT lands

1. Add a `project_<feat>` function to
   [backend/public_stats.py](../backend/public_stats.py) that produces the
   safe-to-publish projection.
2. Add the new field whitelist to
   `public_stats.PUBLIC_FIELD_WHITELIST` and a no-leak assertion in
   [backend/tests/test_public_stats.py](../backend/tests/test_public_stats.py).
3. Add a `/stats/<panel>` route in [backend/main.py](../backend/main.py)
   that calls the projection and applies the same 5-minute cache headers
   as the existing routes.
4. Add the matching panel HTML/JS to `_STATS_HTML` in `public_stats.py`.

### Removing a panel post-launch (privacy concern surfaced)

If a panel needs to be redacted after launch:

1. Change the projection function to return `{"available": False,
   "reason": "<short, public-safe>"}`.
2. Update the panel JS to render the reason instead of fetching numbers.
3. Note the deliberate omission in the dashboard footer so future
   reviewers see the absence is a privacy decision, not an oversight.

### Cache + rate limit

- Public endpoints set `Cache-Control: public, max-age=300` (5 min).
- Per-IP rate limit reuses the geocode bucket (`_GEOCODE_RPM`,
  `_GEOCODE_RPH`). Pull into its own bucket if `/stats/*` ever competes
  meaningfully with `/autocomplete` for budget.

### Operational alarms

None today. The page degrades gracefully if either endpoint 5xx's
(panel shows "—" + an error line). If the dashboard goes to advertisers
as a live link, consider adding an uptime monitor on `/stats`.

---

## FEAT-007 — Funnel completion

**Modules:** [backend/funnel.py](../backend/funnel.py), hooks into
[backend/sessions.py](../backend/sessions.py).

### How the funnel is tracked

- `sessions._active` holds one extra field per live session: `funnel_stage`
  (int, default -1). `sessions.advance_funnel_stage(raw_sid, event_name)`
  advances it to the stage's index if the new stage is higher than the
  current one (monotonic — a late event can't roll back the stage).
- When a session ends (idle timeout or day rollover), `sessions.py` calls
  `funnel.record_finalized(day, highest_stage)`, which increments the
  at-least counts for stages 0..highest_stage in `funnel._counts`.
- Nothing per-session is ever written to disk. The on-disk file
  (`funnel.json`) contains only the daily cumulative arrays.

### Funnel stage order

Hardcoded in `funnel.FUNNEL_STAGES` (positional — do not reorder):

| Index | Stage name            |
|-------|-----------------------|
| 0     | `app_loaded`          |
| 1     | `recommend_submitted` |
| 2     | `recommend_returned`  |
| 3     | `route_selected`      |
| 4     | `start_route_tapped`  |
| 5     | `trip_completed`      |

The advertiser headline is index 2 (`recommend_returned`) as a share of
index 0 (`app_loaded`). This is the "got a result" number.

### On-disk format

`funnel.json`: `{date: [n0, n1, n2, n3, n4, n5]}` where `n_i` = sessions
that reached **at least** stage i that day. Conversion rates are derived at
read time as `n_i / n_0`. Public endpoint reports `result_rate_pct =
n_2 / n_0 * 100`.

### Adding or removing a stage

- **Adding**: append to `FUNNEL_STAGES` in `funnel.py`. The on-disk arrays
  are 6 elements wide; changing the length invalidates old data (old-length
  arrays are skipped on load by `_load()`). If back-compat matters, bump
  `_NUM_STAGES` and migrate existing rows in a one-off script.
- **Removing / reordering**: same impact. Note the removal here so
  historical arrays are interpretable.

### Threshold and sizing decisions

- `_FLUSH_EVERY_N_WRITES` (default **5**) matches sessions.py — each write
  represents a finalised session. A `kill -9` between flushes drops at
  most 5 sessions from the funnel aggregate; acceptable.
- `funnel._lock` is independent of `sessions._lock`. Sessions holds its
  own lock while calling `funnel.record_finalized()`, but since asyncio is
  single-threaded this only means the sessions lock is held for slightly
  longer on session expiry — not a deadlock risk.

### Operational alarms

None today. If `result_rate_pct` drops suddenly without a corresponding
drop in `recommend_submitted`, check whether `_sessions.advance_funnel_stage`
is still being called in the `/events` handler and after `recommend_returned`.

---

## FEAT-006 — Event tracking

**Modules:** [backend/events.py](../backend/events.py),
[frontend/src/analytics.js](../frontend/src/analytics.js).

### Allowlist maintenance

- `EVENT_ALLOWLIST` in `backend/events.py` is the canonical list of
  acceptable event names. Hardcoded — adding a new event is a code
  change, not an env-var flip. The strictness is deliberate: a metric-
  poisoning attempt that submits junk names cannot expand the on-disk
  schema.
- **Adding an event:** add the name to `EVENT_ALLOWLIST`, fire it from
  the appropriate frontend call site (or server-side if it's a passive
  signal like `recommend_returned`), and decide whether the new event
  belongs on the public `/stats/events` panel. If yes, add it to
  `_EVENTS_PUBLIC_KEYS` and `_EVENTS_PUBLIC_FIELDS` in
  `backend/public_stats.py` and extend the no-leak test in
  `test_public_stats.py`. If no, the event stays admin-only by default.
- **Never remove an event name** without leaving a note here, because
  the on-disk `events.json` may already contain historical counts under
  that key. Removing the allowlist entry will reject new writes but the
  old key will still appear in admin/historical exports.

### Public-vs-admin split (privacy decision)

- The four published events on `/stats/events` are
  `recommend_submitted`, `recommend_returned`, `route_selected`, and
  `trip_completed`. These are *outcome* signals an advertiser can read.
- `app_loaded`, `map_opened`, `start_route_tapped`, and
  `house_ad_clicked` stay admin-only because they're *navigation*
  signals — exposing them publicly would let a viewer infer per-user
  behavioral patterns by ratioing them against DAU.
- `total` on the public payload is the sum of the **published** events
  only, never the admin-side total — that gap would let a viewer back
  out the dropped event volumes via subtraction.

### Server-side vs frontend events

- `recommend_returned` fires server-side from the `/recommend` handler
  *after* the response is cached, so it counts only successful returns.
  Don't move this client-side: a network failure between server and
  client would otherwise show as "no recommend_returned" even though
  the work was done.
- All other events fire from the frontend `track()` helper. The helper
  uses `keepalive: true` so an event near a navigation (e.g.
  `trip_completed` right before a phone lock) still completes.

### Threshold and sizing decisions

- `_FLUSH_EVERY_N_WRITES` (default **20**) matches the other counters.
  A `kill -9` between flushes drops up to 20 events; acceptable for an
  aggregate counter.
- `EVENTS_RPM` / `EVENTS_RPH` (defaults **120 / 1200** per IP) are
  higher than the geocode bucket because a normal session naturally
  fires several events back-to-back (`app_loaded` →
  `recommend_submitted` → `recommend_returned` → `route_selected` →
  `start_route_tapped` → `trip_completed`). Lower only if poisoning
  becomes a real problem in practice.

### Operational alarms

None today. If `recommend_submitted` >> `recommend_returned` for a
sustained period, that indicates either backend errors on `/recommend`
or rate-limit exhaustion — worth checking server logs. The ratio is
computed in the dashboard footer of the events panel (the parenthetical
"X% returned a result").
