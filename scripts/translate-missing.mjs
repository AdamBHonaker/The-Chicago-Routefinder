#!/usr/bin/env node
/**
 * One-time script: fills in untranslated i18n keys across all non-English locales.
 * Usage: node scripts/translate-missing.mjs
 * Requires ANTHROPIC_API_KEY environment variable.
 */

import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const LOCALES_DIR = resolve(__dirname, '../frontend/public/locales');

// Load ANTHROPIC_API_KEY from backend/.env if not already in environment.
function loadEnvKey(name) {
  if (process.env[name]) return process.env[name];
  const candidates = [
    resolve(__dirname, '../backend/.env'),
    resolve(__dirname, '../.env'),
  ];
  for (const p of candidates) {
    if (!existsSync(p)) continue;
    const raw = readFileSync(p, 'utf8');
    for (const line of raw.split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
      if (!m || m[1] !== name) continue;
      let val = m[2];
      if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1);
      }
      return val;
    }
  }
  return null;
}

const API_KEY = loadEnvKey('ANTHROPIC_API_KEY');

if (!API_KEY) {
  console.error('Error: ANTHROPIC_API_KEY not found in environment or backend/.env');
  process.exit(1);
}

// Canonical 26 non-English locales currently shipped. Source of truth:
// frontend/src/i18n.js → LANGUAGES. Retrenched 2026-05-11 from 76 → 27
// (26 non-English + en). When adding/removing a locale, update both this
// map and LANGUAGES in i18n.js. Archived locale files live under
// frontend/locales-archive/ and are not retranslated by this script.
const LOCALE_NAMES = {
  ar:  'Arabic',
  es:  'Spanish',
  fr:  'French',
  gu:  'Gujarati',
  hi:  'Hindi',
  ko:  'Korean',
  ne:  'Nepali',
  pl:  'Polish',
  ps:  'Pashto',
  ro:  'Romanian',
  ru:  'Russian',
  tl:  'Filipino (Tagalog)',
  uk:  'Ukrainian',
  ur:  'Urdu',
  vi:  'Vietnamese',
  yo:  'Yoruba',
  yue: 'Cantonese',
  zh:  'Mandarin Chinese',
  ht:  'Haitian Creole',
  ksw: "S'gaw Karen",
  am:  'Amharic',
  prs: 'Dari (Afghan Persian)',
  bs:  'Bosnian',
  aii: 'Assyrian Neo-Aramaic',
  pt:  'Portuguese',
  rhg: 'Rohingya',
};

// Per-locale variant-sensitive instructions. Each entry is appended to the
// translation prompt for that locale to keep Claude on the correct script,
// dialect, or written variant. Only locales in LOCALE_NAMES above are
// eligible — entries for archived locales were removed in the 2026-05-11
// retrenchment.
const LOCALE_INSTRUCTIONS = {
  ksw: 'Translate into S\'gaw Karen specifically (variant written in Burmese-derived Karen script). NOT Karenni / Red Karen.',
  rhg: 'Translate into Rohingya using Hanifi Rohingya script.',
  aii: 'Translate into Modern Assyrian Neo-Aramaic (Sureth) using Syriac script.',
};

// CLI: optional `--only=<csv>` flag restricts the run to specific locales.
// Useful for chunked rollouts (e.g. `--only=de,sv,nl,pt,lt` for Chunk 2).
const ONLY_ARG = (process.argv.find(a => a.startsWith('--only=')) || '').slice('--only='.length);
const ONLY_LOCALES = ONLY_ARG
  ? new Set(ONLY_ARG.split(',').map(s => s.trim()).filter(Boolean))
  : null;

// Keys whose English value is correct in all locales — never attempt to translate.
const KEEP_ENGLISH = new Set([
  // Photo captions that are 100% proper nouns (station/line names).
  'photo_caption_red_line_howard',
  'photo_caption_blue_line_ohare',
  'photo_caption_state_lake',
  'photo_caption_wrigley_addison',
  // NWS (National Weather Service) is a US proper noun; headlines come from the API in English.
  'weather_nws_alert',
  // Compass abbreviations — single/double letters render identically across most languages.
  'compass_n', 'compass_ne', 'compass_e', 'compass_se',
  'compass_s', 'compass_sw', 'compass_w', 'compass_nw',
]);

// Keys with non-obvious translation rules.
const SPECIAL_INSTRUCTIONS = {
  photo_caption_loop_elevated:
    'Only translate the phrase "Elevated Track" — keep "The Loop — " exactly as-is. Output format: "The Loop — [translated term]"',
  wait_due_short:
    'This is a very short label on an arrival board meaning a train/bus is due NOW. Use the most natural short abbreviation or word in the target language (e.g. a 2–4 character term). Do NOT use "DUE".',
  label_min_total_short:
    'This is a compact label meaning "minutes total" on a route summary card. Use a short 2–6 character abbreviation appropriate in the target language. Do NOT use "MIN TOTAL".',
  'fav_save_route': 'Keep the ☆ symbol exactly. Translate "Save" naturally.',
  'fav_saved_route': 'Keep the ★ symbol exactly. Translate "Saved" naturally.',
  'route_stop_trip': 'Keep the ■ symbol exactly. Translate "Stop Trip" naturally.',
  'route_start_trip': 'Keep the ▶ symbol exactly. Translate "Start Trip" naturally.',
  'map_unlock_btn': 'Keep the 🔓 emoji exactly. Translate "Unlock map" naturally.',
};

async function callAnthropic(prompt) {
  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': API_KEY,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5-20251001',
      // 16384 needed for Kannada (composite Unicode chars are very
      // token-heavy in this script — 8K truncated mid-dictionary on a
      // ~180-key payload). 8K was sufficient for Greek/Devanagari/Tamil/etc.
      // Haiku 4.5 supports up to 64K output tokens; 16K is the safe
      // ceiling for the current 26-locale set without burning unnecessary budget.
      max_tokens: 16384,
      messages: [{ role: 'user', content: prompt }],
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Anthropic API ${response.status}: ${text}`);
  }

  const data = await response.json();
  return data.content[0].text;
}

// Heuristic repair for the single most common failure mode: the model emits
// unescaped ASCII " inside translated string values when quoting a UI label
// (e.g. ...choose "Add to Home Screen".). Per-line pattern is reliable because
// each translation is a single-line `"key": "value",` entry. We escape any
// unescaped " between the value-opening and value-closing quote with \" so
// JSON.parse accepts it. Already-escaped \" are left alone.
function repairUnescapedInnerQuotes(jsonStr) {
  const lines = jsonStr.split('\n');
  for (let i = 0; i < lines.length; i++) {
    // <indent>"key": "<inner>"<optional comma><trailing ws>
    const m = lines[i].match(/^(\s*"\w+"\s*:\s*")(.*)("\s*,?\s*)$/);
    if (!m) continue;
    const inner = m[2];
    if (!inner.includes('"')) continue;
    const escaped = inner.replace(/(^|[^\\])"/g, '$1\\"');
    lines[i] = m[1] + escaped + m[3];
  }
  return lines.join('\n');
}

function extractJSON(text) {
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) throw new Error('No JSON object found in model response:\n' + text);
  try {
    return JSON.parse(match[0]);
  } catch (err) {
    // Try repairing unescaped inner ASCII quotes and reparsing.
    const repaired = repairUnescapedInnerQuotes(match[0]);
    return JSON.parse(repaired);
  }
}

async function translateLocale(locale, enData, localeData) {
  const langName = LOCALE_NAMES[locale] ?? locale;

  // A key is untranslated only if it is absent from the locale file. Trust any value
  // already present — many short labels (loanwords, abbreviations) legitimately match
  // English, and re-flagging them on every run causes infinite re-translation.
  const untranslated = {};
  for (const [key, enVal] of Object.entries(enData)) {
    if (key === '_comment') continue;
    if (KEEP_ENGLISH.has(key)) continue;
    if (!(key in localeData)) untranslated[key] = enVal;
  }

  if (Object.keys(untranslated).length === 0) {
    console.log(`  ${locale}: already fully translated — skipped`);
    return null;
  }

  console.log(`  ${locale} (${langName}): ${Object.keys(untranslated).length} keys to translate…`);

  const specials = Object.entries(SPECIAL_INSTRUCTIONS)
    .filter(([k]) => k in untranslated)
    .map(([k, v]) => `- ${k}: ${v}`)
    .join('\n');

  const localeNote = LOCALE_INSTRUCTIONS[locale];

  const prompt = `You are translating a public-transit app UI into ${langName} (BCP-47 code: ${locale}).

Translate the JSON values below from English into ${langName}. Return ONLY a valid JSON object with the same keys and translated values — no markdown, no explanation.

Translation rules:
1. Translate naturally and idiomatically, not word-for-word.
2. Preserve every interpolation variable exactly: {{minutes}} {{count}} {{code}} {{line}} {{stop}} {{to}} {{temp}} {{mph}} {{headline}} {{min}}
3. Preserve all emoji and Unicode symbols exactly: 🔓 ☆ ★ ■ ▶ ⟶ — ·
4. For aria_* keys: write natural screen-reader text in ${langName}.
5. For RTL languages (Arabic, Urdu, Pashto, Hebrew, Persian/Dari, Egyptian Arabic, Hassaniya Arabic, Sindhi, Sorani Kurdish, Assyrian, Rohingya): write right-to-left text naturally; do not add bidi markers.
6. CRITICAL — JSON validity: when a translated string contains an inner quotation (e.g. quoting a button label like "Add to Home Screen"), you MUST use locale-appropriate curly/guillemet quotation marks ("…", „…", «…», 「…」, ‘…’, etc.) — NEVER use ASCII double quotes " inside the string value, since that breaks JSON parsing. Pick the marks conventional for ${langName}. If unsure, use the typographic “ and ”. Do NOT wrap the response in markdown code fences.
${localeNote ? `\nLocale-specific instruction:\n${localeNote}\n` : ''}${specials ? `\nPer-key special rules:\n${specials}` : ''}

Keys to translate:
${JSON.stringify(untranslated, null, 2)}`;

  const raw = await callAnthropic(prompt);

  let translated;
  try {
    translated = extractJSON(raw);
  } catch (err) {
    // Most common failure: model emitted unescaped ASCII " inside string values
    // when quoting UI labels (e.g. "...choose "Add to Home Screen""). Ask the
    // model to repair its own output before giving up.
    console.warn(`  ${locale}: initial response was invalid JSON — requesting repair…`);
    const repairPrompt = `The following output was supposed to be a valid JSON object but failed to parse. Most likely cause: unescaped ASCII double-quote characters (") appear INSIDE string values where they should have been replaced with locale-appropriate curly/guillemet quotation marks (e.g. " " „ " « » 「 」).

Return ONLY the corrected JSON object — no markdown fences, no explanation. Keep every key and the meaning of every value identical; only fix the quotation marks (and any other syntactic errors) so that JSON.parse succeeds. Preserve all interpolation variables ({{var}}), emoji, and Unicode symbols exactly.

Broken output:
${raw}`;
    try {
      const repaired = await callAnthropic(repairPrompt);
      translated = extractJSON(repaired);
      console.log(`  ${locale}: repair succeeded`);
    } catch (err2) {
      console.error(`  ${locale}: repair also failed — skipping. Original output:\n`, raw);
      return null;
    }
  }

  // Apply KEEP_ENGLISH: these always get the English value.
  for (const key of KEEP_ENGLISH) {
    if (key in enData) translated[key] = enData[key];
  }

  // Validate all requested keys are present in the response.
  const missing = Object.keys(untranslated).filter(k => !(k in translated) && !KEEP_ENGLISH.has(k));
  if (missing.length) {
    console.warn(`  ${locale}: model omitted ${missing.length} keys — they will remain English: ${missing.join(', ')}`);
  }

  // Merge: preserve all existing translated keys, layer in new translations.
  return { ...localeData, ...translated };
}

async function main() {
  const enData = JSON.parse(readFileSync(`${LOCALES_DIR}/en/translation.json`, 'utf8'));

  // Pool of locales to consider:
  //   - existing directories under public/locales (sans en), plus
  //   - any code in LOCALE_NAMES that doesn't yet have a directory (these
  //     get created on first write — supports the LocaleExpansion rollout
  //     where 54 codes ship before their files do).
  const onDisk = readdirSync(LOCALES_DIR).filter(d => d !== 'en' && !d.startsWith('.'));
  const known = Object.keys(LOCALE_NAMES);
  const all = Array.from(new Set([...onDisk, ...known])).sort();

  const locales = ONLY_LOCALES ? all.filter(c => ONLY_LOCALES.has(c)) : all;

  if (ONLY_LOCALES) {
    const skippedFromCli = [...ONLY_LOCALES].filter(c => !locales.includes(c));
    if (skippedFromCli.length) {
      console.warn(`  --only includes unknown codes (skipped): ${skippedFromCli.join(', ')}`);
    }
    console.log(`Restricted to ${locales.length} locale(s) via --only.\n`);
  } else {
    console.log(`Found ${locales.length} non-English locales (${onDisk.length} on disk, ${all.length - onDisk.length} new).\n`);
  }

  let updated = 0;
  let skipped = 0;

  // Inter-call pacing. Anthropic's per-minute output-token rate limit on
  // Haiku 4.5 is 10K tokens/min. A full locale dictionary in a multi-byte
  // script can reach ~9K output tokens, so two locales back-to-back will
  // trip the limit. 60s between calls keeps a single chunk (5 locales)
  // well under the budget. Pacing must trigger any time the previous
  // iteration *attempted* an API call, including parse-failure cases —
  // a 429 doesn't care whether we successfully read the response back.
  const PACING_MS = 60_000;
  let didApiCall = false;

  for (const locale of locales) {
    if (didApiCall) {
      console.log(`  …pausing ${PACING_MS / 1000}s for rate-limit budget`);
      await new Promise(r => setTimeout(r, PACING_MS));
    }

    const dirPath = `${LOCALES_DIR}/${locale}`;
    const filePath = `${dirPath}/translation.json`;
    let localeData = {};
    if (existsSync(filePath)) {
      try {
        localeData = JSON.parse(readFileSync(filePath, 'utf8'));
      } catch {
        console.warn(`  ${locale}: could not parse file — skipping`);
        skipped++;
        // No API call attempted on bad-file skip; preserve prior pacing state.
        continue;
      }
    }

    // Decide whether this iteration will attempt an API call BEFORE we
    // call translateLocale, so a downstream parse failure (which makes
    // translateLocale return null even though the API was hit) still
    // causes the next iteration to pace. Mirrors the no-op condition
    // inside translateLocale: a locale with every non-KEEP_ENGLISH key
    // already present in localeData makes no API call.
    const willCallApi = Object.keys(enData).some(
      (k) => k !== '_comment' && !KEEP_ENGLISH.has(k) && !(k in localeData),
    );

    const result = await translateLocale(locale, enData, localeData);
    didApiCall = willCallApi;
    if (result === null) {
      skipped++;
      continue;
    }

    if (!existsSync(dirPath)) mkdirSync(dirPath, { recursive: true });
    writeFileSync(filePath, JSON.stringify(result, null, 2) + '\n', 'utf8');
    console.log(`  ${locale}: written ✓`);
    updated++;
  }

  console.log(`\nDone — ${updated} locales updated, ${skipped} skipped.`);
  console.log('\nValidation (should print nothing if complete):');

  // Quick completeness check — only over locales we actually touched.
  for (const locale of locales) {
    const filePath = `${LOCALES_DIR}/${locale}/translation.json`;
    if (!existsSync(filePath)) continue;
    let t;
    try { t = JSON.parse(readFileSync(filePath, 'utf8')); } catch { continue; }
    const missing = Object.keys(enData).filter(
      k => k !== '_comment' && !KEEP_ENGLISH.has(k) && !(k in t)
    );
    if (missing.length) console.warn(`  ${locale}: missing keys: ${missing.join(', ')}`);
  }
}

main().catch(err => { console.error(err); process.exit(1); });
