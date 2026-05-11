"""Values the schema and the retrieval code must agree on exactly."""

# intfloat/multilingual-e5-base. The previous project used a 384-dimensional English-only
# model; German text through it produces garbage, so both the model and this number changed.
# Changing it again means an Alembic migration that alters the column and rebuilds the HNSW
# index — it is not a value that can be edited on its own.
EMBEDDING_DIMENSIONS = 768

# e5 models require these prefixes and degrade silently without them: search text is a
# "query", indexed text is a "passage". This asymmetry is also what makes an English question
# match a German passage, so it matters more than a formatting detail.
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "

# Postgres text-search configuration. Must be German — German stemming and compound splitting
# are the whole reason the lexical leg of hybrid retrieval finds anything.
FTS_CONFIG = "german"

CHUNK_TOKENS = 350
CHUNK_OVERLAP_TOKENS = 50
