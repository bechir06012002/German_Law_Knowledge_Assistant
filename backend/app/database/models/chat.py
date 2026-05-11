"""Threads, messages, and the citations an answer rests on."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, TimestampMixin, uuid_pk


class ChatThread(Base, TimestampMixin):
    __tablename__ = "chat_threads"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(255))

    # 'de' | 'en'. Persisted per thread: the user may ask in one language and want the answer
    # in the other, and switching it must not re-run retrieval.
    answer_language: Mapped[str] = mapped_column(String(2), server_default="de", nullable=False)

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_chat_threads_user", "user_id", "updated_at"),)


class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # The query as sent to the lexical leg. German when the user asked in English, so the UI
    # can show what was actually searched.
    translated_query: Mapped[str | None] = mapped_column(Text)

    thread: Mapped[ChatThread] = relationship(back_populates="messages")
    citations: Mapped[list[MessageCitation]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_chat_messages_thread", "thread_id", "created_at"),)


class MessageCitation(Base, TimestampMixin):
    """Which chunk an assistant message relied on.

    A real table with a real model, deliberately. The previous project created this table,
    never mapped it, and stored citations inline in the message payload instead — so the
    citations could not be queried, and the table sat empty.
    """

    __tablename__ = "message_citations"

    id: Mapped[uuid.UUID] = uuid_pk()
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    # The German passage as shown to the user. Stored verbatim: a translated quote is a
    # paraphrase presented as evidence, which is what the grounding contract exists to stop.
    quoted_text: Mapped[str | None] = mapped_column(Text)
    scores: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    message: Mapped[ChatMessage] = relationship(back_populates="citations")

    __table_args__ = (Index("ix_message_citations_message", "message_id", "rank"),)
