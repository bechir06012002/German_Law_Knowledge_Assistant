"""Settings — the single source of truth for backend configuration.

Nothing else in the backend reads the environment. No `os.getenv`, no `load_dotenv`; missing
required values raise on startup rather than surfacing as a confusing failure once a request
is already in flight.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Supabase. The service-role key bypasses RLS, so it is used only for ingestion and
    # never on a path that handles a user request.
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Direct connection, not the transaction pooler: migrations create extensions and build
    # HNSW indexes, which need session-level access.
    database_url: PostgresDsn

    # OpenAI
    openai_api_key: str
    # Terra is the balanced tier: OpenAI positions it for document analysis, which is exactly
    # this workload. Sol costs 2.5x for reasoning depth a grounded-answer task does not use.
    openai_chat_model: str = "gpt-5.6-terra"
    # Query translation (English -> German for the lexical leg) is a one-line task, so it runs
    # on the cheapest tier — roughly 10x less than the answer model.
    openai_translation_model: str = "gpt-5.6-luna"

    # Embeddings run locally; this model is multilingual and 768-dimensional. Changing it
    # means a migration — the vector column is fixed at EMBEDDING_DIMENSIONS.
    embedding_model: str = "intfloat/multilingual-e5-base"

    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
