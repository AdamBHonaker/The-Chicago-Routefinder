# Privacy notes

This app collects the minimum information needed to operate the service and
to publish coarse, aggregate usage numbers. It uses **no third-party
analytics scripts**, no fingerprinting, and no persistent cross-day user
identifiers.

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
  `house_ad_clicked`) stay admin-only because they are navigation
  signals an outside viewer could ratio against DAU to infer per-user
  behaviour.

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

## What is **not** collected

- No fingerprinting (canvas, fonts, audio, WebGL, screen size, etc.).
- No third-party analytics or marketing tags.
- No raw IP addresses, User-Agent strings, or reversible identifiers on disk.
- The `returnId` cookie (FEAT-002) is the only persistent cross-day identifier;
  it is an opaque random token with no PII linkage — see the FEAT-002 section
  above for the explicit privacy tradeoff.

## Where the data lives

All data is stored on the same Railway-hosted backend as the application
itself. No data is sent to a third-party processor. The persisted artifacts
are:

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
