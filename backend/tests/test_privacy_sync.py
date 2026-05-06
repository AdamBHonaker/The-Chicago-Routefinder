"""
Drift guard between docs/PRIVACY.md (canonical) and PRIVACY_TEXT in
backend/public_stats.py (the plaintext payload served at /privacy).

The two prose styles deliberately differ — the dashboard payload is wrapped
plaintext, the docs version is GitHub Markdown — but the *coverage* must stay
in lockstep so a Markdown-only update never silently lands while the deployed
/privacy endpoint keeps serving stale text.

Failure here means: a privacy-relevant change landed in docs/PRIVACY.md (or
PRIVACY_TEXT) but not the other. Decide whether to (a) port the change across,
or (b) explicitly add the new topic to one of the lists below if the change
is intentional and asymmetric.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import public_stats


_DOCS_PRIVACY = Path(__file__).resolve().parents[2] / "docs" / "PRIVACY.md"


@pytest.fixture(scope="module")
def docs_privacy_text() -> str:
    if not _DOCS_PRIVACY.is_file():
        pytest.skip(f"docs/PRIVACY.md not found at {_DOCS_PRIVACY}")
    return _DOCS_PRIVACY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def deployed_text() -> str:
    return public_stats.PRIVACY_TEXT


# Topical anchors that both surfaces must reference. These are the data-class
# names the privacy story is built around — adding or removing any of them is
# a privacy-policy-level change that has to ship in both places.
_REQUIRED_TOPICS: tuple[str, ...] = (
    "Daily unique visitors",
    "geography",
    "Sessions",
    "Hour-of-day",
    "Device class",
    "Referrers",
    "returnId",            # FEAT-002 cookie name
    "Bloom filter",        # how cross-day recognition is implemented
)

# "What is NOT collected" guarantees that must appear on both sides.
# Substring match (case-insensitive) keeps the test robust to small wording
# tweaks while still catching wholesale removal.
_REQUIRED_NEGATIVE_GUARANTEES: tuple[str, ...] = (
    "no third-party",
    "no fingerprinting",
)


@pytest.mark.parametrize("topic", _REQUIRED_TOPICS)
def test_topic_present_in_both(topic: str, docs_privacy_text: str, deployed_text: str) -> None:
    assert topic.lower() in docs_privacy_text.lower(), (
        f"docs/PRIVACY.md is missing required topic {topic!r}"
    )
    assert topic.lower() in deployed_text.lower(), (
        f"public_stats.PRIVACY_TEXT is missing required topic {topic!r}"
    )


@pytest.mark.parametrize("phrase", _REQUIRED_NEGATIVE_GUARANTEES)
def test_negative_guarantee_in_both(
    phrase: str, docs_privacy_text: str, deployed_text: str
) -> None:
    assert phrase.lower() in docs_privacy_text.lower(), (
        f"docs/PRIVACY.md is missing privacy guarantee phrase {phrase!r}"
    )
    assert phrase.lower() in deployed_text.lower(), (
        f"public_stats.PRIVACY_TEXT is missing privacy guarantee phrase {phrase!r}"
    )
