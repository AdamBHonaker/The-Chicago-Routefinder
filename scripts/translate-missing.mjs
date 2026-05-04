#!/usr/bin/env node
/**
 * One-time script: fills in untranslated i18n keys across all non-English locales.
 * Usage: node scripts/translate-missing.mjs
 * Requires ANTHROPIC_API_KEY environment variable.
 */

import { readFileSync, writeFileSync, readdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const LOCALES_DIR = resolve(__dirname, '../frontend/public/locales');
const API_KEY = process.env.ANTHROPIC_API_KEY;

if (!API_KEY) {
  console.error('Error: ANTHROPIC_API_KEY environment variable not set.');
  process.exit(1);
}

const LOCALE_NAMES = {
  ar:  'Arabic',
  es:  'Spanish',
  fr:  'French',
  gu:  'Gujarati',
  hi:  'Hindi',
  it:  'Italian',
  ja:  'Japanese',
  ko:  'Korean',
  ne:  'Nepali',
  pa:  'Punjabi',
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
};

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
      max_tokens: 4096,
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

function extractJSON(text) {
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) throw new Error('No JSON object found in model response:\n' + text);
  return JSON.parse(match[0]);
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

  const prompt = `You are translating a public-transit app UI into ${langName} (BCP-47 code: ${locale}).

Translate the JSON values below from English into ${langName}. Return ONLY a valid JSON object with the same keys and translated values — no markdown, no explanation.

Translation rules:
1. Translate naturally and idiomatically, not word-for-word.
2. Preserve every interpolation variable exactly: {{minutes}} {{count}} {{code}} {{line}} {{stop}} {{to}} {{temp}} {{mph}} {{headline}} {{min}}
3. Preserve all emoji and Unicode symbols exactly: 🔓 ☆ ★ ■ ▶ ⟶ — ·
4. For aria_* keys: write natural screen-reader text in ${langName}.
5. For RTL languages (Arabic, Urdu, Pashto): write right-to-left text naturally; do not add bidi markers.
${specials ? `\nPer-key special rules:\n${specials}` : ''}

Keys to translate:
${JSON.stringify(untranslated, null, 2)}`;

  const raw = await callAnthropic(prompt);

  let translated;
  try {
    translated = extractJSON(raw);
  } catch (err) {
    console.error(`  ${locale}: failed to parse response — skipping. Raw output:\n`, raw);
    return null;
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
  const locales = readdirSync(LOCALES_DIR).filter(d => d !== 'en' && !d.startsWith('.'));

  console.log(`Found ${locales.length} non-English locales.\n`);

  let updated = 0;
  let skipped = 0;

  for (const locale of locales) {
    const filePath = `${LOCALES_DIR}/${locale}/translation.json`;
    let localeData;
    try {
      localeData = JSON.parse(readFileSync(filePath, 'utf8'));
    } catch {
      console.warn(`  ${locale}: could not read file — skipping`);
      skipped++;
      continue;
    }

    const result = await translateLocale(locale, enData, localeData);
    if (result === null) {
      skipped++;
      continue;
    }

    writeFileSync(filePath, JSON.stringify(result, null, 2) + '\n', 'utf8');
    console.log(`  ${locale}: written ✓`);
    updated++;
  }

  console.log(`\nDone — ${updated} locales updated, ${skipped} skipped.`);
  console.log('\nValidation (should print nothing if complete):');

  // Quick completeness check
  for (const locale of locales) {
    const filePath = `${LOCALES_DIR}/${locale}/translation.json`;
    let t;
    try { t = JSON.parse(readFileSync(filePath, 'utf8')); } catch { continue; }
    const missing = Object.keys(enData).filter(
      k => k !== '_comment' && !KEEP_ENGLISH.has(k) && !(k in t)
    );
    if (missing.length) console.warn(`  ${locale}: missing keys: ${missing.join(', ')}`);
  }
}

main().catch(err => { console.error(err); process.exit(1); });
