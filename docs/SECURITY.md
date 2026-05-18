# Security Findings

Internal log of security findings for remediation. Severity: 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low.

> **Not a disclosure policy.** This file tracks internal security findings discovered by the `security-finder` and `dependency-auditor` skills. It is NOT the project's public vulnerability-disclosure policy. If you need a public policy, create a separate top-level `SECURITY.md`.

> **Process:** When an item in this file is resolved, **delete its entry from this file** and add a corresponding entry to the **Security Issues Resolved** section of [`docs/archive/RESOLVED_HISTORY.md`](archive/RESOLVED_HISTORY.md) documenting what was changed and how. This file should only ever contain findings that have not yet been remediated.

> **ID prefixes used in this file:**
> - `SEC-XXX` — code-review findings from `/security-finder`
> - `DEP-XXX` — dependency-audit findings from `/dependency-auditor`

---

### SEC-003 · CSP `style-src` requires `'unsafe-inline'` until nonce infrastructure lands
- **File**: [frontend/index.html](../frontend/index.html#L33)
- **Line(s)**: 33
- **OWASP Category**: A05 — Security Misconfiguration / E2 — CSP Issues
- **Severity**: 🟢 Low
- **Description**: The CSP allows `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com`. `'unsafe-inline'` is load-bearing — the React tree emits dynamic `style="..."` attributes that can't be migrated to classes or pre-computed hashes:
  - `LinePill` ([frontend/src/components/LinePill.jsx:42](../frontend/src/components/LinePill.jsx#L42)) — `background: bg, color: textColor` for train and bus pills.
  - `SchedulesPicker` ([frontend/src/components/tools/SchedulesPicker.jsx:74](../frontend/src/components/tools/SchedulesPicker.jsx#L74)) — `background: pillColor(r)` where `r.color` is an arbitrary GTFS `route_color` hex value (CTA publishes ~150 bus route colors; not a fixed set).
  - `MapView` and live-position markers — `transform: rotate(${bearing}deg)` updates per GPS tick.
  - `BottomSheet`, `App.jsx` resizable column — `height` and `--cards-col-width` updated from gesture/resize state.
  - `AlertsFilterBar:211`, marker components — assorted static and dynamic styles.

  With `'unsafe-inline'` present, CSP cannot block a CSS-only attack such as attribute-exfiltration (`input[value^="a"] { background: url(...); }`) injected via a future innerHTML sink. Note: there is no current innerHTML sink — [[SEC-002]] removed the only one — so this is defense-in-depth, not a live exploit path.
- **Impact**: Reduces the protective value of CSP for CSS-based info disclosure. Modest exposure on a static, mostly-public app.
- **Suggested Fix**: Removing `'unsafe-inline'` is **not** a code change — the dynamic-color and dynamic-transform call sites enumerated above can't be pre-hashed (per-instance values) or class-ified (arbitrary GTFS hex values). The only realistic path is a **nonce-based CSP delivered via a Vercel edge function or middleware** that:
  1. Generates `nonce = crypto.randomUUID()` per request.
  2. Rewrites the `<meta http-equiv="Content-Security-Policy">` content (or sets a response header) to use `style-src 'self' 'nonce-<value>' https://fonts.googleapis.com`.
  3. Either tags every React-emitted style with that nonce (not currently supported by React — would need `<style nonce>` blocks instead of style attributes), or accepts that nonces don't apply to `style="..."` attributes and uses `style-src-attr 'unsafe-inline'` separately (CSP Level 3, Chrome/Edge only).

  The honest version: this is an architectural blocker until either (a) the deployment moves off static-HTML hosting onto Vercel edge functions with per-request HTML rewriting, or (b) every dynamic-color/dynamic-transform call site is refactored to write CSS custom properties on a single hashed `<style>` block. Both are large changes; neither belongs in a single-PR security fix. Leave the unsafe-inline allowance in place and document the residual risk here.

---
