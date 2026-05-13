"""
Text normalization helpers shared by geocoding ingest scripts and the runtime
local-search module.

The same canonical form must be produced at ingest time (when populating
`addresses` and `intersections` in the geocode DB) and at query time (when
matching what the user typed). Keeping the rules in one place is the only
way to guarantee that.

Two normalization "families" live here, and they are intentionally distinct:

  1. `normalize_street_name` / `normalize_address` — corpus canonicalization.
     STRIPS directionals and street-type suffixes so "N Clark St" and
     "Clark Street" collapse to the same searchable token sequence.
     Used at both ingest (rows in `addresses`/`intersections`) and query
     time (what the user typed) — they MUST run on both sides or rows
     won't match what callers canonicalize.

  2. `_normalize_street_abbr` — free-text query canonicalization for the
     `NEIGHBORHOOD_COORDS` exact/fuzzy match. EXPANDS abbreviations
     ("Ave" -> "avenue") because the curated NEIGHBORHOOD_COORDS keys
     use expanded forms. Query-time only. Different family from (1) —
     do not mix them up.

`fuzzy_match_neighborhood` is parameterized by the coords dict so this
module stays free of runtime imports of the rest of the geocoding subsystem.
Callers bind the coords dict; see `gtfs_loader.fuzzy_match_neighborhood`
for the lru_cache'd wrapper used by the resolution cascade.
"""

from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Mapping


# ---------------------------------------------------------------------------
# Family 1 — corpus canonicalization (used at both ingest and query time)
# ---------------------------------------------------------------------------

_DIRECTIONALS: frozenset[str] = frozenset({
    "n", "s", "e", "w", "ne", "nw", "se", "sw",
    "north", "south", "east", "west",
    "northeast", "northwest", "southeast", "southwest",
})

_SUFFIXES: frozenset[str] = frozenset({
    "st", "street",
    "ave", "av", "avenue",
    "blvd", "boulevard",
    "rd", "road",
    "dr", "drive",
    "ln", "lane",
    "ct", "court",
    "pl", "place",
    "pkwy", "parkway",
    "hwy", "highway",
    "expy", "expressway",
    "ter", "terrace",
    "way",
    "cir", "circle",
    "sq", "square",
    "plz", "plaza",
    "pt", "point",
    "row",
})

_PUNCT_RE = re.compile(r"[.,;:'\"()]")
_WS_RE = re.compile(r"\s+")


def normalize_street_name(raw: str) -> str:
    """Reduce a raw OSM street name to a search-canonical token sequence.

    "N Clark St"      -> "clark"
    "S Michigan Ave"  -> "michigan"
    "W Diversey Pkwy" -> "diversey"
    "Lake Shore Dr"   -> "lake shore"
    """
    if not raw:
        return ""
    s = _PUNCT_RE.sub(" ", raw.lower())
    s = _WS_RE.sub(" ", s).strip()
    tokens = s.split(" ")
    if len(tokens) > 1 and tokens[0] in _DIRECTIONALS:
        tokens = tokens[1:]
    if len(tokens) > 1 and tokens[-1] in _SUFFIXES:
        tokens = tokens[:-1]
    return " ".join(tokens)


def normalize_address(raw: str) -> str:
    """Normalize a full street address like "1234 N Clark St".

    Lowercases, collapses punctuation/whitespace, strips a leading directional
    after the house number, strips a trailing street suffix. Preserves the
    house number as the first token so prefix-search by number works.

    "1234 N Clark St" -> "1234 clark"
    "22 W Washington" -> "22 washington"
    """
    if not raw:
        return ""
    s = _PUNCT_RE.sub(" ", raw.lower())
    s = _WS_RE.sub(" ", s).strip()
    tokens = s.split(" ")
    if not tokens:
        return ""
    if tokens[0] and tokens[0][0].isdigit():
        house = tokens[0]
        rest = tokens[1:]
    else:
        house = ""
        rest = tokens
    if rest and rest[0] in _DIRECTIONALS:
        rest = rest[1:]
    if len(rest) > 1 and rest[-1] in _SUFFIXES:
        rest = rest[:-1]
    parts = ([house] if house else []) + rest
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Family 2 — USPS suffix expansion for free-text query canonicalization
# against NEIGHBORHOOD_COORDS. Expands rather than strips because the
# curated dict keys are spelled out ("Lake Shore Drive", not "Lake Shore Dr").
# ---------------------------------------------------------------------------

# Defined as a tuple of (abbr, expansion) pairs rather than a dict literal so
# that a duplicate key is caught at import time instead of silently winning.
_ABBR_PAIRS: tuple[tuple[str, str], ...] = (
    ("blvd", "boulevard"),
    ("pkwy", "parkway"),
    ("expy", "expressway"),
    ("terr", "terrace"),
    ("ter",  "terrace"),
    ("hwy",  "highway"),
    ("ave",  "avenue"),
    ("cir",  "circle"),
    ("st",   "street"),
    ("dr",   "drive"),
    ("ln",   "lane"),
    ("ct",   "court"),
    ("rd",   "road"),
    ("pl",   "place"),
    ("sq",   "square"),
)
_ABBR_MAP: dict[str, str] = dict(_ABBR_PAIRS)
_dup_abbr_keys = [k for k, n in Counter(p[0] for p in _ABBR_PAIRS).items() if n > 1]
assert not _dup_abbr_keys, f"_ABBR_PAIRS contains duplicate keys: {_dup_abbr_keys}"
del _dup_abbr_keys
# Sort longest-first so longer patterns are tried before shorter ones.
_sorted_abbrs = sorted(_ABBR_MAP, key=len, reverse=True)

_STREET_ABBR_RE = re.compile(
    # Lookahead (?=\s*(?:,|$)) requires the token to be at end-of-string or
    # immediately before a comma. This prevents "St." in "St. Michael's Church"
    # from matching (it's followed by more words), while still matching
    # "123 N Clark St" (end of string) and "123 N Clark St, Chicago" (before comma).
    r"\b(" + "|".join(re.escape(a) + r"\.?" for a in _sorted_abbrs) + r")\b(?=\s*(?:,|$))",
    re.IGNORECASE,
)


def _street_abbr_replace(m: re.Match) -> str:
    token = m.group(0).lower().rstrip(".")
    return _ABBR_MAP.get(token, m.group(0))


def _normalize_street_abbr(query: str) -> str:
    """Expand USPS street suffix abbreviations (e.g. "Ave" -> "avenue",
    "Blvd." -> "boulevard") in a lowercased address string.

    Directional prefixes (N/S/E/W) are intentionally not expanded.
    """
    return _STREET_ABBR_RE.sub(_street_abbr_replace, query)


# ---------------------------------------------------------------------------
# fuzzy_match_neighborhood — parameterized by the coords dict so this module
# has no runtime dependency on the rest of the geocoding subsystem. Callers
# bind the coords dict; the lru_cache for the bound form lives at the caller.
# ---------------------------------------------------------------------------

_FUZZY_STOP_WORDS: frozenset[str] = frozenset(
    {"the", "of", "a", "an", "and", "at", "in", "on", "chicago"}
)

# Inverted-index cache keyed by id(coords). Callers pass module-level singletons
# whose id is stable for the process lifetime, so this functions as a per-coords
# memoization without making the coords dict itself hashable.
_word_index_cache: dict[int, dict[str, frozenset[str]]] = {}


def _neighborhood_word_index(
    coords: Mapping[str, tuple[float, float]],
) -> dict[str, frozenset[str]]:
    """Inverted index: meaningful word -> frozenset of coords-dict keys
    containing that word. Built once per coords-dict identity; lets
    multi-word fuzzy queries skip keys that can't possibly share a token."""
    cached = _word_index_cache.get(id(coords))
    if cached is not None:
        return cached
    word_keys: dict[str, set[str]] = {}
    for key in coords:
        for w in set(key.split()) - _FUZZY_STOP_WORDS:
            word_keys.setdefault(w, set()).add(key)
    built = {w: frozenset(ks) for w, ks in word_keys.items()}
    _word_index_cache[id(coords)] = built
    return built


def fuzzy_match_neighborhood(
    query: str,
    coords: Mapping[str, tuple[float, float]],
) -> tuple[tuple[float, float] | None, str | None]:
    """Fuzzy-match a lowercased, stripped query against the supplied coords dict.

    Requires both a similarity score >= 0.95 AND at least one meaningful word
    in common (multi-word queries only) so that "chicago art museum" never
    matches "chicago history museum" on structural words alone.

    Returns (coords, matched_key) if a match is found, else (None, None).
    """
    q_words = set(query.split()) - _FUZZY_STOP_WORDS

    # Multi-word queries must share a meaningful word with the matched key —
    # use the inverted index to skip keys that can't possibly qualify.
    # Single-word / stop-word-only queries scan the full map (behavior
    # preserved — those never had the word-overlap requirement).
    if len(q_words) > 1:
        word_index = _neighborhood_word_index(coords)
        candidates: set[str] = set()
        for w in q_words:
            hits = word_index.get(w)
            if hits:
                candidates.update(hits)
        if not candidates:
            return None, None
        iterable: object = candidates
    else:
        iterable = coords

    # SequenceMatcher caches info about seq2, so hold `query` as seq2 and
    # swap seq1 per key — documented fast pattern for "one vs many".
    matcher = SequenceMatcher()
    matcher.set_seq2(query)

    best_score, best_key = 0.0, None
    for key in iterable:
        matcher.set_seq1(key)
        # quick_ratio() is a cheap upper bound on ratio(); if it can't beat
        # the current best, skip the expensive real computation.
        if matcher.quick_ratio() <= best_score:
            continue
        score = matcher.ratio()
        if score <= best_score:
            continue
        best_score = score
        best_key = key
        # A ratio of 1.0 is an exact match — nothing can beat it.
        if best_score >= 0.99:
            break
    if best_score >= 0.95 and best_key:
        return coords[best_key], best_key
    return None, None
