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
