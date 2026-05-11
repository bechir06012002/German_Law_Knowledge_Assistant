"""Strip residual personal identifiers before anything becomes searchable.

German decisions are pseudonymized, not anonymized. Measured over 389 decisions in this
corpus: 44 contain an abbreviated name (`Herr X.`), 3 a street address, 1 a full name, 1 a
phone number — no emails or IBANs. Small numbers, but labour decisions routinely carry GDPR
Article 9 special-category data (health in sick-pay cases, union membership in works-council
cases), so what survives here is what an attacker could search for later.

Role words — Kläger, Beklagte — are deliberately left alone. They appear in 91% of decisions,
carry the legal meaning, and identify nobody.
"""

from __future__ import annotations

import re

REDACTED = "[…]"

# Ordered: longer, more specific patterns first so a phone number is not half-eaten by a
# shorter rule.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}\b")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[A-Za-z]{2,}\b")),
    ("phone", re.compile(r"\b(?:\+49|0)[\d]{2,5}[/\- ]?\d{5,}\b")),
    (
        "address",
        re.compile(
            r"\b[A-ZÄÖÜ][a-zäöüß]+(?:straße|strasse|str\.|weg|platz|allee|gasse|ring)\s+\d+[a-z]?\b"
        ),
    ),
    # `Herr Max Mustermann` / `Frau Dr. Anna Beispiel`. Requires the honorific: matching two
    # capitalised words on their own would redact half the German language.
    (
        "full_name",
        re.compile(
            r"\b(?:Herr|Frau)\s+(?:Dr\.\s*|Prof\.\s*)*[A-ZÄÖÜ][a-zäöüß]{2,}\s+[A-ZÄÖÜ][a-zäöüß]{2,}\b"
        ),
    ),
)


def strip_identifiers(text: str) -> tuple[str, dict[str, int]]:
    """Return the text with identifiers replaced, and a count per pattern.

    The count is returned rather than logged so ingestion can report totals — a pattern that
    suddenly matches thousands of times means the rule is wrong, and silence would hide it.
    """
    counts: dict[str, int] = {}
    for name, pattern in _PATTERNS:
        text, hits = pattern.subn(REDACTED, text)
        if hits:
            counts[name] = hits
    return text, counts
