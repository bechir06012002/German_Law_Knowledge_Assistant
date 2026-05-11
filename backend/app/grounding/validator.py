"""The compliance control.

The design contract is explicit that the RDG boundary must be enforced here and not only in the prompt:
"a prompt is not a compliance control". A model told not to predict outcomes will still do it
occasionally; this module is what makes that a rejected answer rather than a shipped one.

Everything here is deterministic and testable without an LLM, which is the point — a control
that can only be verified by asking a model is not a control.

It fails **closed**: anything it cannot verify is rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Rejection(str, Enum):
    PREDICTION = "prediction"
    UNRETRIEVED_CITATION = "unretrieved_citation"
    NO_CITATIONS = "no_citations"
    QUOTE_NOT_IN_SOURCE = "quote_not_in_source"
    PERSON_QUERY = "person_query"


@dataclass
class ValidationResult:
    ok: bool
    rejections: list[Rejection] = field(default_factory=list)
    """Human-readable detail, for logs and for the developer — never shown to the user as-is."""
    detail: list[str] = field(default_factory=list)


# Outcome prediction, German and English. Deliberately broad: a false positive costs one
# regenerated answer, a false negative is an unlicensed legal service.
_PREDICTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("de:win", re.compile(r"\b(?:Sie|du)\s+(?:werden|wirst|würden|dürften)\b[^.]{0,40}\b(?:gewinnen|obsiegen|Erfolg\s+haben|recht\s+bekommen)", re.I)),
    ("de:chances", re.compile(r"\b(?:Erfolgsaussicht(?:en)?|Prozessaussicht(?:en)?|Gewinnchance(?:n)?|Chancen\s+stehen)\b", re.I)),
    ("de:likely", re.compile(r"\b(?:wahrscheinlich|voraussichtlich|höchstwahrscheinlich|vermutlich)\b[^.]{0,60}\b(?:gewinnen|obsiegen|Erfolg|unwirksam|wirksam|stattgeben|abweisen)", re.I)),
    ("de:court_will", re.compile(r"\b(?:das\s+Gericht|der\s+Richter|die\s+Kammer)\s+(?:wird|dürfte|würde)\b[^.]{0,60}\b(?:entscheiden|urteilen|stattgeben|abweisen|zusprechen)", re.I)),
    ("de:your_case", re.compile(r"\bIhr(?:e|em|en)?\s+(?:Fall|Klage|Kündigung)\b[^.]{0,50}\b(?:ist|wäre|dürfte)\b[^.]{0,30}\b(?:erfolgreich|aussichtsreich|unwirksam|begründet)", re.I)),
    ("de:probability", re.compile(r"\b\d{1,3}\s*%\s*(?:Wahrscheinlichkeit|Chance|Erfolg)", re.I)),
    ("en:win", re.compile(r"\byou\s+(?:will|would|are\s+likely\s+to|should)\s+(?:win|succeed|prevail)\b", re.I)),
    ("en:chances", re.compile(r"\b(?:your|the)\s+(?:chances|odds|likelihood|probability)\s+of\s+(?:success|winning|prevailing)\b", re.I)),
    ("en:strong_case", re.compile(r"\byour\s+case\s+(?:is|looks|seems|appears)\s+(?:strong|weak|good|promising)\b", re.I)),
    ("en:court_will", re.compile(r"\bthe\s+court\s+(?:will|would|is\s+likely\s+to)\s+(?:rule|find|decide|hold)\s+in\s+your\s+favou?r\b", re.I)),
)

# Aggregate person/employer queries — a people-search product, not legal research.
_PERSON_QUERY_PATTERNS = (
    re.compile(r"\b(?:hat|haben)\s+(?:jemand|irgendjemand|jemals)\b[^?]{0,60}\b(?:verklagt|geklagt)", re.I),
    re.compile(r"\bwelche\s+(?:Verfahren|Klagen|Fälle)\b[^?]{0,40}\bgegen\s+(?:die\s+Firma|den\s+Arbeitgeber|Herrn|Frau)\b", re.I),
    re.compile(r"\bhas\s+anyone\s+(?:ever\s+)?sued\b", re.I),
    re.compile(r"\b(?:list|show|find)\s+(?:all\s+)?(?:cases|lawsuits|claims)\s+(?:against|involving)\s+(?:employer|company|mr|mrs|ms)\b", re.I),
)

REFUSAL_MARKERS = (
    "keine vergleichbare",
    "keine vergleichbaren",
    "keine passende",
    "nichts gefunden",
    "no comparable",
    "no matching decision",
    "found no decisions",
)


def looks_like_prediction(text: str) -> list[str]:
    """Names of the prediction patterns that matched. Empty means clean."""
    return [name for name, pattern in _PREDICTION_PATTERNS if pattern.search(text)]


def is_person_query(question: str) -> bool:
    return any(pattern.search(question) for pattern in _PERSON_QUERY_PATTERNS)


def is_refusal(answer: str) -> bool:
    lowered = answer.casefold()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


def _normalize(text: str) -> str:
    """Whitespace-insensitive comparison — a quote may be re-wrapped but not reworded."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def validate(
    answer: str,
    citation_chunk_ids: list[str],
    quoted_texts: dict[str, str],
    retrieved: dict[str, str],
) -> ValidationResult:
    """Check one generated answer against the evidence retrieved this turn.

    `retrieved` maps chunk_id -> the German source text. Quotes are validated against **that**
    German text regardless of the answer's language: translating before validating would
    compare a paraphrase to a source and pass anything.
    """
    rejections: list[Rejection] = []
    detail: list[str] = []

    matched = looks_like_prediction(answer)
    if matched:
        rejections.append(Rejection.PREDICTION)
        detail.append(f"outcome prediction matched: {', '.join(matched)}")

    unknown = [cid for cid in citation_chunk_ids if cid not in retrieved]
    if unknown:
        rejections.append(Rejection.UNRETRIEVED_CITATION)
        detail.append(f"cited chunks not retrieved this turn: {unknown}")

    if not citation_chunk_ids and not is_refusal(answer):
        rejections.append(Rejection.NO_CITATIONS)
        detail.append("answer has no citations and is not the 'no comparable case' refusal")

    for chunk_id, quote in quoted_texts.items():
        source = retrieved.get(chunk_id)
        if source is None:
            continue  # already reported as an unretrieved citation
        if _normalize(quote) not in _normalize(source):
            rejections.append(Rejection.QUOTE_NOT_IN_SOURCE)
            detail.append(f"quote for {chunk_id} is not verbatim in the German source")

    return ValidationResult(ok=not rejections, rejections=rejections, detail=detail)
