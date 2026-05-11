"""Resolve a decision's `norm_refs` to the statute text it applies.

This is the case↔statute join that is the distinctive part of the product: a user
reading *"die Kündigung war nach § 622 Abs. 3 BGB fristgerecht"* can see what § 622 actually
says.

The join needs normalisation. Decisions and the statute dump do not spell book codes the same
way — decisions cite `efzg`, the dump files it under `entgfg`; decisions cite `sgb ix`, the
dump has `sgb 9`. Left unmapped, the most-cited labour statutes silently resolve to nothing.
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

# Verified against both sides: keys are what decisions cite, values are the dump's book_code.
BOOK_ALIASES: dict[str, str] = {
    "efzg": "entgfg",       # Entgeltfortzahlungsgesetz
    "entgfg": "entgfg",
    "sgb ix": "sgb 9",
    "sgb9": "sgb 9",
    "sgbix": "sgb 9",
    "betravg": "betravg",
    "tzbfg": "tzbfg",
}


def normalize_book(book: str) -> str:
    key = re.sub(r"\s+", " ", (book or "").strip().lower())
    return BOOK_ALIASES.get(key, key)


def normalize_section(section: str) -> str:
    """`622`, `§ 622`, `§622` and `622 Abs. 3` all address the same stored section."""
    value = (section or "").strip()
    value = re.sub(r"^§+\s*", "", value)
    # Drop sub-designations the statute dump does not key on.
    value = re.split(r"\s+(?:Abs|Absatz|Satz|Nr)\b", value)[0]
    return value.strip()


def lookup_statute_text(db: Session, book: str, section: str) -> str | None:
    """The Markdown text of one § , or None when the corpus does not have it."""
    row = db.execute(
        text(
            "select markdown_content from source_documents "
            "where doc_kind = 'law' and book_code = :book "
            "and regexp_replace(file_number, '^§+\s*', '') = :section "
            "limit 1"
        ),
        {"book": normalize_book(book), "section": normalize_section(section)},
    ).first()
    return row[0] if row else None
