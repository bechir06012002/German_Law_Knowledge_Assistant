"""Thread CRUD and the streaming chat endpoint.

Every route is user-scoped: a thread is reachable only by its owner. The answer is a
placeholder for now — Phase 5 replaces `_placeholder_answer` with the real agent, and nothing
else here has to change.
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.chat.messages import latest_user_question
from app.chat.titles import generate_thread_title
from app.chat.schemas import (
    ChatRequest,
    LanguageSwitch,
    MessageOut,
    ThreadCreate,
    ThreadOut,
)
from app.chat.orchestrator import TurnResult, run_turn
from app.chat.relanguage import relanguage
from app.chat.streaming import STREAM_HEADERS, data_event, text_stream
from app.retrieval.query_language import detect_language
from app.database.models import ChatMessage, ChatThread, MessageCitation, User
from app.database.session import SessionLocal, get_db
from app.retrieval.statutes import lookup_statute_text

router = APIRouter(tags=["chat"])


def _ensure_user(db: Session, user: CurrentUser) -> None:
    """Mirror the Supabase user into `public.users`.

    Supabase owns `auth.users`; our tables key off `public.users`, so the row has to exist
    before a thread can reference it. First request after signup is where that happens.
    """
    if db.get(User, user.id) is None:
        db.add(User(id=user.id, email=user.email))
        db.commit()


def _owned_thread(db: Session, thread_id: uuid.UUID, user: CurrentUser) -> ChatThread:
    """The thread, if it exists and belongs to the caller.

    404 for missing, 403 for someone else's — deliberately distinct, because the owner of a
    deleted thread deserves a different answer than someone probing for other people's ids.
    """
    thread = db.get(ChatThread, thread_id)
    if thread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found.")
    if thread.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your thread.")
    return thread


@router.get("/threads", response_model=list[ThreadOut])
def list_threads(
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ChatThread]:
    _ensure_user(db, user)
    return list(
        db.scalars(
            select(ChatThread)
            .where(ChatThread.user_id == user.id)
            .order_by(ChatThread.updated_at.desc())
        )
    )


@router.post("/threads", response_model=ThreadOut, status_code=status.HTTP_201_CREATED)
def create_thread(
    body: ThreadCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatThread:
    _ensure_user(db, user)
    thread = ChatThread(
        user_id=user.id, title=body.title, answer_language=body.answer_language
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@router.get("/threads/{thread_id}/messages", response_model=list[MessageOut])
def thread_messages(
    thread_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatMessage]:
    _owned_thread(db, thread_id, user)
    messages = list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread_id)
            .order_by(ChatMessage.created_at)
        )
    )

    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            translated_query=m.translated_query,
            created_at=m.created_at,
            citations=_stored_citations(db, m.id),
        )
        for m in messages
    ]


def _stored_citations(db: Session, message_id) -> list[dict]:
    """Citations for one message, in exactly the shape the stream sends.

    Without this, chips vanish on reload: the rows are in `message_citations`, but a reloaded
    thread would render prose with nothing to check it against.
    """
    rows = db.execute(
        text(
            """
            select mc.rank, c.id::text as chunk_id, c.section, c.paragraph_number, c.text,
                   d.court_name, d.file_number, d.decision_date, d.decision_type,
                   d.ecli, d.source_url, d.norm_refs
            from message_citations mc
            join document_chunks c on c.id = mc.chunk_id
            join source_documents d on d.id = c.document_id
            where mc.message_id = cast(:message_id as uuid)
            order by mc.rank
            """
        ),
        {"message_id": str(message_id)},
    )
    return [
        {
            "chunkId": row.chunk_id,
            "court": row.court_name,
            "fileNumber": row.file_number,
            "decisionDate": row.decision_date.strftime("%d.%m.%Y") if row.decision_date else None,
            "decisionType": row.decision_type,
            "ecli": row.ecli,
            "section": row.section,
            "paragraphNumber": row.paragraph_number,
            "sourceUrl": row.source_url,
            "normRefs": row.norm_refs or [],
            "text": row.text,
        }
        for row in rows
    ]


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(
    thread_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    thread = _owned_thread(db, thread_id, user)
    db.delete(thread)
    db.commit()


def _stream_words(text: str) -> Iterator[str]:
    """Emit a finished answer word by word.

    The text is already generated and already validated — see `orchestrator.run_turn`. This
    only paces delivery so the UI behaves like a chat rather than a form submit.
    """
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.015)


def _citation_payload(result: TurnResult) -> dict:
    """Citation metadata for the UI.

    Court, Aktenzeichen, ECLI, date and section stay verbatim German in both answer
    languages — the user may need to type them into a court portal.
    """
    return {
        "queryLanguage": result.query_language,
        # Stated, not inferred. An English answer legitimately contains German court names,
        # § references and quoted passages, so any umlaut-based guess reads it as German.
        "answerLanguage": result.answer_language,
        "lexicalQuery": result.lexical_query,
        "refused": result.refused,
        "citations": [
            {
                "chunkId": p.chunk_id,
                "court": p.court_name,
                "fileNumber": p.file_number,
                "decisionDate": p.decision_date.strftime("%d.%m.%Y") if p.decision_date else None,
                "decisionType": p.decision_type,
                "ecli": p.ecli,
                "section": p.section,
                "paragraphNumber": p.paragraph_number,
                "sourceUrl": p.source_url,
                "normRefs": p.norm_refs,
                "text": p.text,
            }
            for p in result.passages
        ],
    }


@router.post("/messages/{message_id}/language", response_model=MessageOut)
def switch_message_language(
    message_id: uuid.UUID,
    body: LanguageSwitch,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    """Re-render one answer in the other language, reusing the evidence it already cited.

    Retrieval is NOT re-run. The stored `message_citations` rows are the input, so both
    language versions cite exactly the same decisions — which is the entire point. Asking the
    question again in the other language would produce different case law.
    """
    message = db.get(ChatMessage, message_id)
    if message is None or message.role != "assistant":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found.")
    thread = _owned_thread(db, message.thread_id, user)

    question = (
        db.scalar(
            select(ChatMessage.content)
            .where(ChatMessage.thread_id == thread.id)
            .where(ChatMessage.role == "user")
            .where(ChatMessage.created_at <= message.created_at)
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        or ""
    )

    result = relanguage(db, str(message_id), question, body.answer_language)
    message.content = result.answer
    thread.answer_language = body.answer_language
    db.commit()
    db.refresh(message)

    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        translated_query=message.translated_query,
        created_at=message.created_at,
        citations=_stored_citations(db, message.id),
    )


@router.get("/statutes/{book}/{section}")
def statute(
    book: str,
    section: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    """The text of one §, for the statute chips on a citation.

    Phase 7 made this real; before that the chip would have been a dead affordance. Returns
    `text: null` rather than 404 when the corpus lacks the provision, so the UI can say
    "not in this corpus" instead of showing an error for an ordinary gap.
    """
    return {
        "book": book.upper(),
        "section": section if section.startswith("§") else f"§ {section}",
        "text": lookup_statute_text(db, book, section),
    }


@router.post("/chat/stream")
def chat_stream(
    body: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    _ensure_user(db, user)

    question = latest_user_question(body.messages)
    if not question:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No user message to answer.")

    # Answer in the language the question was asked in, unless the caller says otherwise.
    # A German speaker gets German; an English speaker gets English without touching a toggle.
    answer_language = body.answer_language or detect_language(question)

    if body.thread_id is None:
        thread = ChatThread(user_id=user.id, answer_language=answer_language)
        db.add(thread)
        db.commit()
        db.refresh(thread)
    else:
        thread = _owned_thread(db, body.thread_id, user)

    # Covers both branches above: a thread created here has no title yet, and neither does
    # one the frontend pre-created (via POST /threads) before this, its first message, arrives.
    if thread.title is None:
        thread.title = generate_thread_title(question)

    db.add(ChatMessage(thread_id=thread.id, role="user", content=question))
    db.commit()

    def stream() -> Iterator[str]:
        # `run_turn` is synchronous and can run for tens of seconds. It runs on a background
        # thread so this generator can yield each "retrieving" / "reading" / "validating" /
        # "revising" stage the moment `on_stage` reports it, instead of only being able to
        # yield once the whole turn has already finished.
        events: queue.Queue[str | TurnResult | Exception] = queue.Queue()

        def worker() -> None:
            try:
                # A fresh session: the request-scoped one is closed once the body starts
                # streaming.
                with SessionLocal() as turn_db:
                    events.put(
                        run_turn(
                            turn_db,
                            question,
                            answer_language=answer_language,
                            on_stage=events.put,
                        )
                    )
            except Exception as exc:  # re-raised on the main thread below
                events.put(exc)

        threading.Thread(target=worker, daemon=True).start()

        result: TurnResult | None = None
        while result is None:
            item = events.get()
            if isinstance(item, Exception):
                raise item
            if isinstance(item, TurnResult):
                result = item
            else:
                yield data_event("status", {"stage": item})

        yield data_event("citations", _citation_payload(result))
        yield from text_stream(_stream_words(result.answer))
        answer_text = result.answer

        # Persist only once the stream has finished, so a half-delivered answer is never
        # stored as if it were complete. Citations go in their own table rather than inline
        # in the message, so they can actually be queried.
        with SessionLocal() as write_db:
            message = ChatMessage(
                thread_id=thread.id,
                role="assistant",
                content=answer_text.strip(),
                translated_query=result.lexical_query if result.query_language != "de" else None,
            )
            write_db.add(message)
            write_db.flush()
            write_db.add_all(
                MessageCitation(
                    message_id=message.id,
                    chunk_id=uuid.UUID(citation["chunkId"]),
                    rank=rank,
                    quoted_text=citation["text"],
                    scores={},
                )
                for rank, citation in enumerate(_citation_payload(result)["citations"], start=1)
            )
            write_db.commit()

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={**STREAM_HEADERS, "X-Thread-Id": str(thread.id)}
    )
