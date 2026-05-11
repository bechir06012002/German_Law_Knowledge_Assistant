"""Wire and API shapes for chat.

The Vercel AI SDK sends messages as `{role, parts: [...]}` where parts carry typed content.
Those wire shapes stay here; the rest of the backend works with plain text and the ORM
models, so the SDK's format never leaks past `app/chat/messages.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AnswerLanguage = Literal["de", "en"]


class UIPart(BaseModel):
    type: str
    text: str | None = None


class UIMessage(BaseModel):
    """One message as the AI SDK sends it."""

    id: str | None = None
    role: Literal["user", "assistant", "system"]
    parts: list[UIPart] = Field(default_factory=list)
    # Older SDK payloads send flat text instead of parts.
    content: str | None = None


class ChatRequest(BaseModel):
    messages: list[UIMessage]
    thread_id: uuid.UUID | None = None
    # `None` means "follow the language of the question". An explicit value wins, because
    # someone may ask in English and still want the German wording to show their employer —
    # that is what the per-answer toggle is for.
    answer_language: AnswerLanguage | None = None


class LanguageSwitch(BaseModel):
    answer_language: AnswerLanguage


class ThreadCreate(BaseModel):
    title: str | None = None
    answer_language: AnswerLanguage = "de"


class ThreadOut(BaseModel):
    id: uuid.UUID
    title: str | None
    answer_language: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CitationOut(BaseModel):
    """A stored citation, in the same shape the stream sends.

    Without this, chips disappear on reload: the evidence is in `message_citations`, but a
    reloaded thread would render prose with nothing to check it against — which is the one
    thing this product must never do.
    """

    chunkId: str
    court: str | None
    fileNumber: str | None
    decisionDate: str | None
    decisionType: str | None
    ecli: str | None
    section: str | None
    paragraphNumber: int | None
    sourceUrl: str | None
    normRefs: list[dict] = Field(default_factory=list)
    text: str


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    translated_query: str | None
    created_at: datetime
    citations: list[CitationOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}
