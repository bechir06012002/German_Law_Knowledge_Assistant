"""Split a decision into retrievable chunks that never straddle a section boundary.

Chunks carry the section label and the Randnummer they start at, and both are what a citation
shows. A chunk spanning `Tatbestand` into `Entscheidungsgründe` could only be labelled with
one of them, so the label would be a lie for half its text — hence sections are packed
separately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

from app.database.models.constants import CHUNK_OVERLAP_TOKENS, CHUNK_TOKENS
from app.ingestion.normalize import Paragraph, parse_paragraphs

# cl100k is not the e5 tokenizer, but chunk size only needs to be consistent and roughly
# right; a real tokenizer beats counting characters and guessing at German compounds.
_encoding = tiktoken.get_encoding("cl100k_base")

_SENTENCE_END = re.compile(r"(?<=[.!?:])\s+")


@dataclass(frozen=True)
class Chunk:
    section: str
    """Randnummer the chunk starts at, where the decision numbers its paragraphs."""
    number: int | None
    text: str


def token_count(text: str) -> int:
    return len(_encoding.encode(text))


def _split_long(text: str, limit: int) -> list[str]:
    """Break a paragraph longer than a whole chunk, at sentence ends where possible."""
    if token_count(text) <= limit:
        return [text]

    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(text):
        candidate = f"{current} {sentence}".strip()
        if current and token_count(candidate) > limit:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)

    # A single sentence over the limit — rare in German judgments but real. Cut on tokens so
    # nothing is silently dropped.
    final: list[str] = []
    for piece in pieces:
        tokens = _encoding.encode(piece)
        if len(tokens) <= limit:
            final.append(piece)
            continue
        for start in range(0, len(tokens), limit):
            final.append(_encoding.decode(tokens[start : start + limit]))
    return final


def _pack(paragraphs: list[Paragraph], limit: int, overlap: int) -> list[Chunk]:
    """Greedy-pack one section's paragraphs, carrying `overlap` tokens between chunks."""
    chunks: list[Chunk] = []
    buffer: list[str] = []
    tokens = 0
    section = paragraphs[0].section
    start_number = paragraphs[0].number

    def flush() -> str:
        joined = "\n\n".join(buffer).strip()
        if joined:
            chunks.append(Chunk(section, start_number, joined))
        return joined

    for paragraph in paragraphs:
        for piece in _split_long(paragraph.text, limit):
            size = token_count(piece)
            if buffer and tokens + size > limit:
                previous = flush()
                # Carry the tail of the previous chunk so a passage split mid-argument stays
                # retrievable from either side.
                tail = (
                    _encoding.decode(_encoding.encode(previous)[-overlap:]) if overlap else ""
                )
                buffer = [tail, piece] if tail else [piece]
                tokens = token_count(tail) + size
                start_number = paragraph.number
            else:
                if not buffer:
                    start_number = paragraph.number
                buffer.append(piece)
                tokens += size

    flush()
    return chunks


def chunk_document(
    markdown: str, *, limit: int = CHUNK_TOKENS, overlap: int = CHUNK_OVERLAP_TOKENS
) -> list[Chunk]:
    """Chunk a decision, one section at a time, in document order."""
    paragraphs = parse_paragraphs(markdown)
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    run: list[Paragraph] = []
    for paragraph in paragraphs:
        if run and paragraph.section != run[-1].section:
            chunks.extend(_pack(run, limit, overlap))
            run = []
        run.append(paragraph)
    if run:
        chunks.extend(_pack(run, limit, overlap))
    return chunks


def chunk_section(text: str, *, limit: int, overlap: int) -> list[str]:
    """Pack a bare block of text. Used by tests and by callers with no section structure."""
    paragraphs = [
        Paragraph("Text", None, piece.strip())
        for piece in text.split("\n\n")
        if piece.strip()
    ]
    if not paragraphs:
        return []
    return [chunk.text for chunk in _pack(paragraphs, limit, overlap)]
