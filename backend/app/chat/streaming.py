"""Server-sent events in the shape the Vercel AI SDK expects.

The SDK's UI message stream is SSE where every `data:` line is a JSON object with a `type`.
A text answer is bracketed: `start`, then `text-start`, a run of `text-delta`, `text-end`,
then `finish`, and finally the literal `[DONE]`.

Writing these by hand rather than pulling in an SDK: it is a handful of JSON objects, and the
frontend is the only consumer.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

# The SDK checks for this header before parsing a response as a UI message stream.
STREAM_HEADERS = {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "x-vercel-ai-ui-message-stream": "v1",
    # Streaming through nginx without this buffers the whole response and defeats the point.
    "X-Accel-Buffering": "no",
}


def event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def text_stream(chunks: Iterator[str], *, text_id: str = "0") -> Iterator[str]:
    """Wrap plain text chunks in the SDK's event envelope."""
    yield event({"type": "start"})
    yield event({"type": "text-start", "id": text_id})
    for chunk in chunks:
        if chunk:
            yield event({"type": "text-delta", "id": text_id, "delta": chunk})
    yield event({"type": "text-end", "id": text_id})
    yield event({"type": "finish"})
    yield "data: [DONE]\n\n"


def data_event(name: str, payload: dict[str, Any]) -> str:
    """A custom typed part — used later for citations alongside the answer text."""
    return event({"type": f"data-{name}", "data": payload})
