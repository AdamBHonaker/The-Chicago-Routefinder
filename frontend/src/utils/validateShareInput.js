// ---------------------------------------------------------------------------
// Defensive validator for ?from= / ?to= query parameters consumed by the
// share-link auto-submit flow in App.jsx.
//
// Threats blocked:
//   - Hostile pseudo-URLs that would resolve to script execution if a future
//     refactor ever rendered the value as href/src:
//       javascript:, data:, vbscript:, file:
//   - Embedded URLs (anything containing "://") — share inputs must be a
//     human-typed location string, never a redirect target.
//   - Oversize input (> SHARE_INPUT_MAX_CHARS) — guards against anyone
//     pasting MB-scale strings into the URL bar to OOM the parser, and
//     reflects the realistic upper bound of a legitimate location string.
//
// Returns true when the value is unsafe to auto-submit.
// ---------------------------------------------------------------------------

export const SHARE_INPUT_MAX_CHARS = 200;

const HOSTILE_PROTOCOL_RE = /^\s*(javascript|data|vbscript|file):/i;
// Match either a full scheme (`://`) anywhere, or a leading protocol-relative
// `//` — both forms can be coerced into a navigation/redirect target.
const URL_SCHEME_RE = /:\/\/|^\s*\/\//;

export function looksHostile(s) {
  return (
    !s ||
    s.length > SHARE_INPUT_MAX_CHARS ||
    HOSTILE_PROTOCOL_RE.test(s) ||
    URL_SCHEME_RE.test(s)
  );
}
