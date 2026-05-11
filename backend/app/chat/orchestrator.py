"""One turn, end to end: question in, validated grounded answer out.

The order matters and is the compliance story:

1. Person-queries are refused **before** any retrieval or model call. Nothing about a
   people-search request should reach the corpus.
2. Retrieval runs once. The answer language never re-runs it — same evidence, different
   prose, so the two language versions cannot cite different cases.
3. The model answers.
4. The validator checks the answer against the retrieved German passages. If it fails, the
   model gets one more attempt with the specific reason; if that fails too, the turn returns
   the refusal. It fails **closed** — an unvalidated answer is never returned.

Synchronous, and the answer is generated in full before anything is sent. Token-by-token
streaming is incompatible with the grounding contract: the validator needs the complete
answer, and a prediction cannot be un-sent once a user has read it. The endpoint still
streams — it streams the *validated* text — so the UI is unchanged.

`on_stage`, when given, is called at each real stage transition ("retrieving", "reading",
"validating", "revising") so the caller can surface progress while this runs. It only ever
reports stages that actually happen — no fixed timeline, nothing faked for effect.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.assistant.agent import AnswerDeps, GroundedAnswer, build_agent
from app.grounding.validator import ValidationResult, is_person_query, validate
from app.retrieval.retriever import retrieve
from app.retrieval.search import Passage

MAX_ATTEMPTS = 2

REFUSAL_PERSON_QUERY = {
    "de": (
        "Diese Frage kann ich nicht beantworten. Judges Said durchsucht Entscheidungen nach "
        "Sachverhalten, nicht nach Personen oder Unternehmen. Beschreiben Sie gern Ihre "
        "Situation — dann zeige ich vergleichbare Entscheidungen."
    ),
    "en": (
        "I cannot answer that. Judges Said searches decisions by situation, not by person or "
        "company. Describe your situation instead and I will show comparable decisions."
    ),
}

REFUSAL_NO_MATCH = {
    "de": (
        "Ich habe keine vergleichbare Entscheidung im vorhandenen Bestand gefunden. Das "
        "heißt nicht, dass es keine gibt — nur, dass dieser Bestand keine enthält."
    ),
    "en": (
        "I found no comparable decision in this corpus. That does not mean none exists — only "
        "that this corpus does not contain one."
    ),
}

REFUSAL_UNGROUNDED = {
    "de": (
        "Ich kann zu dieser Frage keine belastbare, durch Entscheidungen belegte Antwort "
        "geben. Vorhersagen über den Ausgang eines Verfahrens sind ausgeschlossen."
    ),
    "en": (
        "I cannot give an answer that is properly supported by the retrieved decisions. "
        "Predictions about how a case will turn out are out of scope."
    ),
}


@dataclass
class TurnResult:
    answer: str
    answer_language: str
    citations: list[dict] = field(default_factory=list)
    passages: list[Passage] = field(default_factory=list)
    lexical_query: str = ""
    query_language: str = "de"
    refused: bool = False
    """Why the turn was refused or retried — for logs, never shown to the user."""
    validation: ValidationResult | None = None


def _cited_passages(answer: GroundedAnswer, passages: dict[str, Passage]) -> list[Passage]:
    seen: set[str] = set()
    result: list[Passage] = []
    for citation in answer.citations:
        passage = passages.get(citation.chunk_id)
        if passage and passage.chunk_id not in seen:
            seen.add(passage.chunk_id)
            result.append(passage)
    return result


def run_turn(
    db: Session,
    question: str,
    *,
    answer_language: str = "de",
    top_k: int = 12,
    on_stage: Callable[[str], None] | None = None,
) -> TurnResult:
    def stage(name: str) -> None:
        if on_stage:
            on_stage(name)

    if is_person_query(question):
        return TurnResult(
            answer=REFUSAL_PERSON_QUERY[answer_language],
            answer_language=answer_language,
            refused=True,
        )

    stage("retrieving")
    retrieval = retrieve(db, question, top_k=top_k)
    if not retrieval.passages:
        return TurnResult(
            answer=REFUSAL_NO_MATCH[answer_language],
            answer_language=answer_language,
            lexical_query=retrieval.lexical_query,
            query_language=retrieval.query_language,
            refused=True,
        )

    passages = {p.chunk_id: p for p in retrieval.passages}
    deps = AnswerDeps(db=db, answer_language=answer_language, passages=passages)
    agent = build_agent()

    prompt = question
    last: ValidationResult | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        stage("reading")
        run = agent.run_sync(prompt, deps=deps)
        answer: GroundedAnswer = run.output

        # Tools may have widened the evidence set; validate against everything the agent was
        # actually allowed to see this turn.
        stage("validating")
        german_sources = {cid: p.text for cid, p in deps.passages.items()}
        last = validate(
            answer.answer,
            [c.chunk_id for c in answer.citations],
            {c.chunk_id: c.quoted_text for c in answer.citations},
            german_sources,
        )

        if last.ok:
            return TurnResult(
                answer=answer.answer,
                answer_language=answer.answer_language or answer_language,
                citations=[c.model_dump() for c in answer.citations],
                passages=_cited_passages(answer, deps.passages),
                lexical_query=retrieval.lexical_query,
                query_language=retrieval.query_language,
                validation=last,
            )

        if attempt < MAX_ATTEMPTS:
            stage("revising")
            prompt = (
                f"{question}\n\n"
                "Your previous answer was rejected by the grounding check:\n"
                + "\n".join(f"- {d}" for d in last.detail)
                + "\nAnswer again, using only the retrieved passages, quoting them verbatim in "
                "German, and without predicting any outcome."
            )

    # Fails closed: an answer that never validated is never returned.
    return TurnResult(
        answer=REFUSAL_UNGROUNDED[answer_language],
        answer_language=answer_language,
        lexical_query=retrieval.lexical_query,
        query_language=retrieval.query_language,
        refused=True,
        validation=last,
    )
