"""The corpus: court decisions and statutes, and the chunks retrieval actually searches."""

from __future__ import annotations

import uuid
from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Computed,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, TimestampMixin, uuid_pk
from app.database.models.constants import EMBEDDING_DIMENSIONS, FTS_CONFIG


class SourceDocument(Base, TimestampMixin):
    """One court decision or one statute section.

    Both kinds live in one table so retrieval can rank them together; `doc_kind` separates
    them. The column names are the German equivalents of the previous project's SEC fields —
    same table topology, different semantics.
    """

    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    doc_kind: Mapped[str] = mapped_column(String(16), nullable=False)  # 'case' | 'law'

    open_legal_data_id: Mapped[int | None] = mapped_column(Integer, unique=True)

    court_name: Mapped[str | None] = mapped_column(String(255))
    court_id: Mapped[int | None] = mapped_column(Integer)
    court_jurisdiction: Mapped[str | None] = mapped_column(String(128))

    decision_type: Mapped[str | None] = mapped_column(String(64))
    decision_date: Mapped[date | None] = mapped_column(Date)
    published_date: Mapped[date | None] = mapped_column(Date)
    decision_year: Mapped[int | None] = mapped_column(Integer)

    # The Aktenzeichen. Unique because it is how a German decision is identified in practice,
    # and duplicate ingestion is the failure this guards against.
    file_number: Mapped[str | None] = mapped_column(String(128))
    ecli: Mapped[str | None] = mapped_column(String(128))

    source_url: Mapped[str | None] = mapped_column(Text)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)

    # Statutes cited by this decision: [{"book": "kschg", "section": "1"}, …]. Supplied
    # pre-parsed by the Open Legal Data dump; this is the case<->statute join.
    norm_refs: Mapped[list] = mapped_column(JSONB, server_default="[]", nullable=False)

    # doc_kind = 'law' only: the statute book, e.g. 'kschg'. A statute's identity is
    # (book_code, file_number) — 'kschg' + '§ 1'. Kept off court_name deliberately, since
    # court_name is rendered in citation chips.
    book_code: Mapped[str | None] = mapped_column(String(64))

    # Version axis, for doc_kind = 'law' only.
    revision_date: Mapped[date | None] = mapped_column(Date)
    is_latest: Mapped[bool | None] = mapped_column()

    license_note: Mapped[str | None] = mapped_column(Text)

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("court_id", "file_number", name="uq_source_documents_court_file"),
        Index("ix_source_documents_court_year", "court_name", "decision_year"),
        Index("ix_source_documents_doc_kind", "doc_kind"),
        Index("ix_source_documents_norm_refs", "norm_refs", postgresql_using="gin"),
        Index("ix_source_documents_book_section", "book_code", "file_number"),
    )


class DocumentChunk(Base, TimestampMixin):
    """A retrievable passage.

    No `page` column. German decisions have named structural sections, which always exist and
    are what a reader can actually find — the previous project's page number was never
    populated and silently degraded every citation.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # 'Tenor', 'Leitsatz', 'Tatbestand', 'Entscheidungsgründe', or a § designator for statutes.
    section: Mapped[str | None] = mapped_column(String(128))
    # Randnummer — the paragraph number German citations pinpoint (Rn.), where the source has one.
    paragraph_number: Mapped[int | None] = mapped_column(Integer)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))

    # Generated in Postgres rather than in Python so it can never drift from `text`.
    text_search: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(f"to_tsvector('{FTS_CONFIG}', text)", persisted=True),
    )

    document: Mapped[SourceDocument] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_doc_index"),
    )
