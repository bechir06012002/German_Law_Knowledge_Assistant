"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.dependencies import CurrentUser, get_current_user
from app.chat.router import router as chat_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title="Judges Said", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me")
def me(user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    """Identity as the server sees it — the check that auth is wired correctly."""
    return {"id": str(user.id), "email": user.email}


app.include_router(chat_router)
