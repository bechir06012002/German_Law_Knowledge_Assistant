"""Request authentication.

The caller's identity comes from a Supabase-verified JWT and nowhere else — never from a
request body or query parameter. Every protected route depends on `get_current_user`, which
rejects the request before any retrieval or LLM work happens.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client

from app.config import get_settings

# auto_error=False so a missing header produces our own 401 with a useful message rather than
# FastAPI's 403.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Missing or invalid authentication token.",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str
    # Kept so downstream code can build a user-scoped Supabase client whose queries are
    # subject to RLS, rather than reaching for the service-role key.
    access_token: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Verify the bearer token with Supabase and return the caller.

    Verification is delegated to Supabase rather than decoding the JWT here: it is
    authoritative about expiry and revocation, and it removes any chance of getting
    signature checking subtly wrong ourselves.
    """
    if credentials is None or not credentials.credentials:
        raise _UNAUTHENTICATED

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_anon_key)

    try:
        response = client.auth.get_user(credentials.credentials)
    except Exception as error:  # supabase raises for expired/invalid tokens
        raise _UNAUTHENTICATED from error

    user = getattr(response, "user", None)
    if user is None or not user.id:
        raise _UNAUTHENTICATED

    return CurrentUser(
        id=uuid.UUID(str(user.id)),
        email=user.email or "",
        access_token=credentials.credentials,
    )
