"""Re-render an existing answer in the other language, reusing the evidence it already cited.

Design rule: *"Switching the answer language must not re-run retrieval. Same evidence,
different prose — otherwise the two language versions can cite different cases, which destroys
trust."*

Without this, switching language means asking a new question, which means new retrieval and
possibly different case law. Measured before this existed: the same question in German and
English shared only 2 of 3–4 cited decisions. A user toggling DE/EN would silently be shown
different precedent for the same situation.

So the stored `message_citations` rows are the input. Retrieval is not involved at all, and
the same grounding validator runs against the same German source text.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.assistant.agent import AnswerDeps, GroundedAnswer, build_agent
from app.chat.orchestrator import REFUSAL_UNGROUNDED
from app.grounding.validator import validate
from app.retrieval.search import Passage


@dataclass
class RelanguageResult:
    answer: str
    answer_language: str
    ok: bool


def stored_passages(db: Session, message_id: str) -> dict[str, Passage]:
    """Rebuild the exact passages this message cited, from `message_citations`."""
    rows = db.execute(
        text(
            """
            select c.id::text as chunk_id, c.document_id::text as document_id, c.chunk_index,
                   c.section, c.paragraph_number, c.text,
                   d.court_name, d.court_jurisdiction, d.decision_type, d.decision_date,
                   d.decision_year, d.file_number, d.ecli, d.source_url, d.norm_refs
            from message_citations mc
            join document_chunks c on c.id = mc.chunk_id
            join source_documents d on d.id = c.document_id
            where mc.message_id = cast(:message_id as uuid)
            order by mc.rank
            """
        ),
        {"message_id": message_id},
    )
    return {
        row.chunk_id: Passage(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            chunk_index=row.chunk_index,
            section=row.section,
            paragraph_number=row.paragraph_number,
            text=row.text,
            court_name=row.court_name,
            court_jurisdiction=row.court_jurisdiction,
            decision_type=row.decision_type,
            decision_date=row.decision_date,
            decision_year=row.decision_year,
            file_number=row.file_number,
            ecli=row.ecli,
            source_url=row.source_url,
            norm_refs=row.norm_refs or [],
            score=0.0,
        )
        for row in rows
    }


def relanguage(
    db: Session, message_id: str, question: str, target_language: str
) -> RelanguageResult:
    passages = stored_passages(db, message_id)
    if not passages:
        # A refusal has no citations, so there is nothing to re-render from.
        return RelanguageResult(REFUSAL_UNGROUNDED[target_language], target_language, False)

    deps = AnswerDeps(db=db, answer_language=target_language, passages=passages)
    agent = build_agent()
    run = agent.run_sync(
        f"{question}\n\nAnswer using only the passages already provided. Do not search.",
        deps=deps,
    )
    answer: GroundedAnswer = run.output

    # Same validator, same German sources. Translating before validating would compare a
    # paraphrase against its own paraphrase and pass anything.
    result = validate(
        answer.answer,
        [c.chunk_id for c in answer.citations],
        {c.chunk_id: c.quoted_text for c in answer.citations},
        {cid: p.text for cid, p in passages.items()},
    )
    if not result.ok:
        return RelanguageResult(REFUSAL_UNGROUNDED[target_language], target_language, False)

    return RelanguageResult(answer.answer, target_language, True)
