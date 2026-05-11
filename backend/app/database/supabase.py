"""Supabase clients.

Two of them, and the distinction matters: the user-scoped client carries the caller's JWT so
RLS applies, while the service-role client bypasses RLS entirely. The service-role client is
for ingestion only and must never touch a path that serves a user request.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


def user_client(access_token: str) -> Client:
    """A client acting as the signed-in user, subject to row level security."""
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client


@lru_cache
def service_client() -> Client:
    """Full-access client. Ingestion only — it ignores every RLS policy."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
