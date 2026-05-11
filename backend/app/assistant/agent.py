"""The grounded-answer agent.

Typed output and bounded tools, deliberately. The agent never writes SQL and never chooses a
table — it can search, read a chunk it already has, read that chunk's neighbours, and look up
a statute. Everything it can reach is something retrieval already decided it may see.

The instructions live in `instructions.md` rather than a string literal here. The previous
project inlined them and they rotted: nobody reviews a 60-line string in a Python file, and
the product contract is exactly the thing that should be reviewable on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.retrieval.retriever import retrieve
from app.retrieval.statutes import lookup_statute_text
from app.retrieval.search import Passage, neighbouring_chunks

INSTRUCTIONS = (Path(__file__).parent / "instructions.md").read_text(encoding="utf-8")


class Citation(BaseModel):
    """One passage the answer rests on."""

    chunk_id: str = Field(description="chunk_id of a passage retrieved this turn")
    quoted_text: str = Field(
        description="The supporting sentence(s), copied VERBATIM from the German passage. "
        "Never translated, never paraphrased."
    )


class GroundedAnswer(BaseModel):
    answer: str = Field(description="The prose answer, in the requested answer_language.")
    answer_language: Literal["de", "en"]
    citations: list[Citation] = Field(
        default_factory=list,
        description="Empty ONLY when refusing because no comparable decision exists.",
    )


@dataclass
class AnswerDeps:
    db: Session
    answer_language: str
    """Passages retrieved this turn, by chunk_id. The agent may cite nothing else."""
    passages: dict[str, Passage] = field(default_factory=dict)


@lru_cache(maxsize=1)
def _model() -> OpenAIResponsesModel:
    """The Responses API, not chat completions.

    Verified against the live API: GPT-5.6 rejects function tools on
    `/v1/chat/completions` unless `reasoning_effort` is `none` —
    *"Function tools with reasoning_effort are not supported for gpt-5.6-terra in
    /v1/chat/completions. To use function tools, use /v1/responses"*. Since the agent's whole
    design is bounded tools, the Responses API is the right side of that trade rather than
    giving up reasoning to keep the older endpoint.
    """
    settings = get_settings()
    return OpenAIResponsesModel(
        settings.openai_chat_model,
        provider=OpenAIProvider(api_key=settings.openai_api_key),
    )


def build_agent() -> Agent[AnswerDeps, GroundedAnswer]:
    agent = Agent(
        _model(),
        output_type=GroundedAnswer,
        deps_type=AnswerDeps,
        instructions=INSTRUCTIONS,
        retries=2,
    )

    @agent.instructions
    def answer_language(ctx: RunContext[AnswerDeps]) -> str:
        return (
            f"Write your prose in: {ctx.deps.answer_language}. "
            "Citation metadata and quoted passages stay German regardless."
        )

    @agent.instructions
    def available_passages(ctx: RunContext[AnswerDeps]) -> str:
        if not ctx.deps.passages:
            return "No passages were retrieved. You must refuse: no comparable decision."
        lines = ["Passages retrieved this turn. You may cite ONLY these chunk_ids:", ""]
        for passage in ctx.deps.passages.values():
            head = (
                f"[{passage.chunk_id}] {passage.court_name} · {passage.file_number} · "
                f"{passage.decision_date} · {passage.section}"
                + (f" · Rn. {passage.paragraph_number}" if passage.paragraph_number else "")
            )
            lines.append(head)
            lines.append(passage.text)
            lines.append("")
        return "\n".join(lines)

    @agent.tool
    def search_decisions(
        ctx: RunContext[AnswerDeps],
        query: str,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> str:
        """Search the corpus again with a refined German query. Use when the supplied
        passages do not cover the question."""
        result = retrieve(ctx.deps.db, query, top_k=6, year_from=year_from, year_to=year_to)
        if not result.passages:
            return "No decisions found for that query."
        for passage in result.passages:
            ctx.deps.passages.setdefault(passage.chunk_id, passage)
        return "\n\n".join(
            f"[{p.chunk_id}] {p.court_name} · {p.file_number} · {p.decision_date} · {p.section}\n{p.text}"
            for p in result.passages
        )

    @agent.tool
    def read_chunk(ctx: RunContext[AnswerDeps], chunk_id: str) -> str:
        """Re-read the full text of a passage already retrieved this turn."""
        passage = ctx.deps.passages.get(chunk_id)
        return passage.text if passage else f"{chunk_id} was not retrieved this turn."

    @agent.tool
    def read_surrounding_chunks(ctx: RunContext[AnswerDeps], chunk_id: str) -> str:
        """Read the chunks either side of a passage, when a quote looks cut off."""
        passage = ctx.deps.passages.get(chunk_id)
        if passage is None:
            return f"{chunk_id} was not retrieved this turn."
        neighbours = neighbouring_chunks(ctx.deps.db, passage.document_id, passage.chunk_index)
        for neighbour in neighbours:
            ctx.deps.passages.setdefault(neighbour.chunk_id, neighbour)
        return "\n\n".join(f"[{n.chunk_id}] ({n.section}) {n.text}" for n in neighbours)

    @agent.tool
    def lookup_statute(ctx: RunContext[AnswerDeps], book: str, section: str) -> str:
        """Look up a statute, e.g. book='KSchG', section='1'. The statute corpus is a later
        phase, so this usually reports that the text is unavailable — say so rather than
        reciting the provision from memory."""
        row = lookup_statute_text(ctx.deps.db, book, section)
        if row is None:
            return (
                f"§ {section} {book.upper()} is not in the corpus. Do not quote its wording; "
                "refer to it only as the decisions themselves do."
            )
        return row

    return agent
