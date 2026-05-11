"""The two retrieval legs, as SQL against Postgres.

Direct SQL through SQLAlchemy rather than Supabase RPCs. The RPC indirection exists so a
*browser* can run a vector search through PostgREST, whose filter DSL cannot express
`embedding <=> query_vector`. Nothing here runs in a browser — the backend owns retrieval —
so an RPC would add a deployment artefact and a round trip for no benefit. The trade-off:
these queries run on the service connection and therefore bypass RLS, which is correct for
the corpus (public domain under § 5 UrhG, readable by any signed-in user) and would *not* be
correct for anything user-scoped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Passage:
    chunk_id: str
    document_id: str
    chunk_index: int
    section: str | None
    paragraph_number: int | None
    text: str
    court_name: str | None
    court_jurisdiction: str | None
    decision_type: str | None
    decision_date: date | None
    decision_year: int | None
    file_number: str | None
    ecli: str | None
    source_url: str | None
    norm_refs: list[dict[str, Any]]
    score: float


_COLUMNS = """
    c.id::text            as chunk_id,
    c.document_id::text   as document_id,
    c.chunk_index,
    c.section,
    c.paragraph_number,
    c.text,
    d.court_name,
    d.court_jurisdiction,
    d.decision_type,
    d.decision_date,
    d.decision_year,
    d.file_number,
    d.ecli,
    d.source_url,
    d.norm_refs
"""


def _filters(
    jurisdiction: str | None,
    year_from: int | None,
    year_to: int | None,
    norm_book: str | None,
) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if jurisdiction:
        clauses.append("d.court_jurisdiction = :jurisdiction")
        params["jurisdiction"] = jurisdiction
    if year_from is not None:
        clauses.append("d.decision_year >= :year_from")
        params["year_from"] = year_from
    if year_to is not None:
        clauses.append("d.decision_year <= :year_to")
        params["year_to"] = year_to
    if norm_book:
        # JSONB containment, which the GIN index on norm_refs serves.
        clauses.append("d.norm_refs @> :norm_book")
        params["norm_book"] = f'[{{"book": "{norm_book.lower()}"}}]'
    return ("".join(f" and {c}" for c in clauses), params)


def _to_passages(rows) -> list[Passage]:
    return [
        Passage(
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
            score=float(row.score),
        )
        for row in rows
    ]


def semantic_search(
    db: Session,
    embedding: list[float],
    *,
    limit: int = 40,
    jurisdiction: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    norm_book: str | None = None,
) -> list[Passage]:
    """Nearest chunks by cosine distance.

    `<=>` must match the index's `vector_cosine_ops`; using a different operator here would
    silently ignore the HNSW index and turn every search into a sequential scan.
    """
    where, params = _filters(jurisdiction, year_from, year_to, norm_book)
    sql = text(
        f"""
        select {_COLUMNS}, 1 - (c.embedding <=> cast(:embedding as vector)) as score
        from document_chunks c
        join source_documents d on d.id = c.document_id
        where c.embedding is not null{where}
        order by c.embedding <=> cast(:embedding as vector)
        limit :limit
        """
    )
    rows = db.execute(sql, {"embedding": str(embedding), "limit": limit, **params})
    return _to_passages(rows)


def fulltext_search(
    db: Session,
    query: str,
    *,
    limit: int = 40,
    jurisdiction: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    norm_book: str | None = None,
) -> list[Passage]:
    """German full-text search over OR-ed query terms.

    `query` must already be a tsquery expression (see `tsquery_terms`). The AND-ing that
    `websearch_to_tsquery` and `plainto_tsquery` apply makes a natural-language question
    match nothing, so terms are OR-ed and `ts_rank_cd` ranks chunks by how many they match.

    The `german` configuration is what makes this leg work at all — it stems and splits
    compounds, so `Kündigungen` matches a search for `Kündigung`.
    """
    if not query.strip():
        return []

    where, params = _filters(jurisdiction, year_from, year_to, norm_book)
    sql = text(
        f"""
        with q as (select to_tsquery('german', :query) as tsq)
        select {_COLUMNS}, ts_rank_cd(c.text_search, q.tsq) as score
        from document_chunks c
        join source_documents d on d.id = c.document_id
        cross join q
        where c.text_search @@ q.tsq{where}
        order by score desc
        limit :limit
        """
    )
    rows = db.execute(sql, {"query": query, "limit": limit, **params})
    return _to_passages(rows)


def neighbouring_chunks(db: Session, document_id: str, chunk_index: int) -> list[Passage]:
    """The chunks either side of a hit, for context.

    A 350-token window often cuts an argument in half; showing the neighbours is what makes a
    quoted passage readable rather than a fragment.
    """
    sql = text(
        f"""
        select {_COLUMNS}, 0.0 as score
        from document_chunks c
        join source_documents d on d.id = c.document_id
        where c.document_id = cast(:document_id as uuid)
          and c.chunk_index between :low and :high
        order by c.chunk_index
        """
    )
    rows = db.execute(
        sql, {"document_id": document_id, "low": chunk_index - 1, "high": chunk_index + 1}
    )
    return _to_passages(rows)
