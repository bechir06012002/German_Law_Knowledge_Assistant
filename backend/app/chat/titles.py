"""A short, meaningful title for a thread's sidebar entry.

Runs on `openai_translation_model` — the cheap tier the settings already reserve for
one-line tasks (query translation is the other consumer). Naming a situation in a few words
is squarely that kind of task, not the grounded-answer agent's job.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.chat.messages import thread_title
from app.config import get_settings

INSTRUCTIONS = (
    "You title conversations for a German labour-law precedent search tool. Given the "
    "user's first question, write a short thread title: 3 to 6 words, no quotation marks, "
    "no trailing punctuation, in the same language as the question. Name the situation "
    "itself — e.g. 'Kündigung in der Probezeit' — never the fact that it's a question, and "
    "never generic filler like 'Rechtliche Frage'."
)


@lru_cache(maxsize=1)
def _agent() -> Agent[None, str]:
    settings = get_settings()
    model = OpenAIResponsesModel(
        settings.openai_translation_model,
        provider=OpenAIProvider(api_key=settings.openai_api_key),
    )
    return Agent(model, output_type=str, instructions=INSTRUCTIONS, retries=1)


def generate_thread_title(question: str) -> str:
    """A short title for the sidebar, generated from the first question.

    Falls back to a truncated version of the question itself if the model call fails — a
    thread must always end up with a title, and a slow or erroring provider should never
    block sending the first message.
    """
    try:
        title = _agent().run_sync(question).output.strip().strip('"').strip("'")
        if title:
            return title[:60]
    except Exception:
        pass
    return thread_title(question)
