"""Question in, ranked German passages out.

One decision worth stating: the two legs get *different* inputs. The semantic leg embeds the
user's original words, because multilingual-e5 already aligns English and German. The lexical
leg gets German terms, because a `german` tsvector cannot match an English token. Feeding
both legs the same string would waste one of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.ingestion.embeddings import embed_query
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.query_language import lexical_query, tsquery_terms
from app.retrieval.search import Passage, fulltext_search, semantic_search

# Wider than we return: RRF needs enough of each leg's tail to find agreement between them.
LEG_LIMIT = 40
DEFAULT_TOP_K = 12


@dataclass
class RetrievalResult:
    passages: list[Passage]
    query_language: str
    """The German string the lexical leg actually searched. Surfaced to the UI so an English
    speaker with thin results can see that "notice period" became `Kündigungsfrist`."""
    lexical_query: str
    leg_counts: dict[str, int] = field(default_factory=dict)


def retrieve(
    db: Session,
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    jurisdiction: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    norm_book: str | None = None,
) -> RetrievalResult:
    language, german_query = lexical_query(query)
    filters = dict(
        jurisdiction=jurisdiction, year_from=year_from, year_to=year_to, norm_book=norm_book
    )

    semantic = semantic_search(db, embed_query(query), limit=LEG_LIMIT, **filters)
    # An empty german_query means the glossary could not translate the question; the leg is
    # skipped rather than fed English tokens that match a German tsvector at random.
    lexical = (
        fulltext_search(db, tsquery_terms(german_query), limit=LEG_LIMIT, **filters)
        if german_query
        else []
    )

    by_id: dict[str, Passage] = {p.chunk_id: p for p in semantic}
    by_id.update({p.chunk_id: p for p in lexical})

    fused = reciprocal_rank_fusion(
        {
            "semantic": [p.chunk_id for p in semantic],
            "lexical": [p.chunk_id for p in lexical],
        }
    )

    passages: list[Passage] = []
    seen_documents: set[str] = set()
    for item in fused:
        passage = by_id[item.key]
        # At most two passages per decision. Without this, one long on-topic judgment fills
        # the whole answer and the user sees one case instead of the three to five analogous
        # ones the product promises.
        if sum(1 for p in passages if p.document_id == passage.document_id) >= 2:
            continue
        passages.append(passage)
        seen_documents.add(passage.document_id)
        if len(passages) >= top_k:
            break

    return RetrievalResult(
        passages=passages,
        query_language=language,
        lexical_query=german_query,
        leg_counts={"semantic": len(semantic), "lexical": len(lexical), "fused": len(fused)},
    )
