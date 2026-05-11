"""Translate AI SDK wire messages into what the backend actually works with: text."""

from __future__ import annotations

from app.chat.schemas import UIMessage


def message_text(message: UIMessage) -> str:
    """All text in one message, joined.

    The SDK splits a message into parts; only the text ones carry anything we can search or
    answer from. Falls back to `content` for older payload shapes.
    """
    texts = [part.text for part in message.parts if part.type == "text" and part.text]
    if texts:
        return "\n".join(texts).strip()
    return (message.content or "").strip()


def latest_user_question(messages: list[UIMessage]) -> str:
    """The question to answer — the last thing the user actually said."""
    for message in reversed(messages):
        if message.role == "user":
            text = message_text(message)
            if text:
                return text
    return ""


def thread_title(question: str, limit: int = 60) -> str:
    """A readable thread title from the first question."""
    title = " ".join(question.split())
    if len(title) <= limit:
        return title
    return title[: limit - 1].rstrip() + "…"
