"""Local embeddings via sentence-transformers. No external embedding API, by design.

The e5 family requires input prefixes — `query: ` on search text, `passage: ` on indexed
text. Omitting them silently degrades retrieval, and it is the easiest mistake to make here,
so both live in this one module and nothing else is allowed to build an input string.

That asymmetry is also what makes cross-lingual matching work: an English question embedded
as a query lands near a German passage embedded as a passage.
"""

from __future__ import annotations

import threading
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.database.models.constants import (
    EMBEDDING_DIMENSIONS,
    PASSAGE_PREFIX,
    QUERY_PREFIX,
)

# Model load takes over a minute; loading it twice concurrently would double the memory of a
# 1 GB model for no benefit.
_lock = threading.Lock()


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    with _lock:
        model = SentenceTransformer(get_settings().embedding_model)
    # Renamed in sentence-transformers 5; keep working on either.
    dimension = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
    actual = dimension()
    if actual != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"{get_settings().embedding_model} produces {actual}-dimensional vectors but the "
            f"schema column is vector({EMBEDDING_DIMENSIONS}). Changing the model requires an "
            "Alembic migration that alters the column and rebuilds the HNSW index."
        )
    return model


def _encode(texts: list[str], *, batch_size: int) -> list[list[float]]:
    vectors = _model().encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        # Cosine distance is what the HNSW index uses, so normalize here and the dot product
        # and cosine similarity agree.
        normalize_embeddings=True,
    )
    return [vector.tolist() for vector in vectors]


def embed_passages(texts: list[str], *, batch_size: int = 32) -> list[list[float]]:
    """Embed text being indexed."""
    return _encode([f"{PASSAGE_PREFIX}{text}" for text in texts], batch_size=batch_size)


def embed_query(text: str) -> list[float]:
    """Embed a search string. Never used for indexed text — the prefix differs."""
    return _encode([f"{QUERY_PREFIX}{text}"], batch_size=1)[0]
