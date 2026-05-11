"""Load the downloaded corpus into Supabase: chunk, embed locally, insert.

Run from `backend/`:
    uv run ingest_to_db.py --limit 50      # smoke run
    uv run ingest_to_db.py                 # everything

Lives here rather than at the repo root because it needs the backend's environment —
sentence-transformers, SQLAlchemy, the models. `download_corpus.py` stays in `scripts/` and
standard-library only because it runs before any environment exists; this does not.

Idempotent: a document that already has chunks is skipped, so an interrupted run resumes.
Embedding is the whole cost — roughly 8 chunks/sec on CPU — so progress is committed per
document and never redone.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from app.database.models import DocumentChunk, SourceDocument
from app.database.session import SessionLocal
from app.ingestion.chunking import chunk_document
from app.ingestion.embeddings import embed_passages
from app.ingestion.pii import strip_identifiers

CORPUS = Path(__file__).resolve().parent.parent / "data" / "downloads"


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def upsert_document(db, record: dict, markdown: str) -> SourceDocument:
    """Insert or refresh the parent row, keyed on the Open Legal Data id."""
    olid = record["open_legal_data_id"]
    document = db.scalar(select(SourceDocument).where(SourceDocument.open_legal_data_id == olid))
    decision_date = parse_date(record.get("decision_date"))

    fields = dict(
        doc_kind=record.get("doc_kind", "case"),
        book_code=record.get("book_code"),
        court_name=record.get("court_name"),
        court_id=record.get("court_id"),
        court_jurisdiction=record.get("court_jurisdiction"),
        decision_type=record.get("decision_type"),
        decision_date=decision_date,
        published_date=parse_date(record.get("published_date")),
        decision_year=decision_date.year if decision_date else None,
        file_number=record.get("file_number"),
        ecli=record.get("ecli"),
        source_url=record.get("source_url"),
        markdown_content=markdown,
        norm_refs=record.get("norm_refs") or [],
        license_note=record.get("license_note"),
        revision_date=parse_date(record.get("revision_date")),
        is_latest=record.get("is_latest"),
    )

    if document is None:
        document = SourceDocument(open_legal_data_id=olid, **fields)
        db.add(document)
    else:
        for key, value in fields.items():
            setattr(document, key, value)
    db.flush()
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only this many documents")
    parser.add_argument(
        "--laws", action="store_true", help="ingest statutes instead of court decisions"
    )
    parser.add_argument(
        "--books",
        default=None,
        help="comma-separated book codes to ingest first, e.g. kschg,entgfg,burlg. "
        "BGB and ZPO are thousands of sections; the core labour books are dozens, so "
        "ingesting them first makes the case-to-statute join work in minutes.",
    )
    parser.add_argument("--batch-size", type=int, default=32, help="embedding batch size")
    args = parser.parse_args()

    if args.laws:
        manifest = json.loads((CORPUS / "laws_manifest.json").read_text(encoding="utf-8"))
        items = manifest["laws"]
        print(f"statutes: {len(items)} sections across {len(manifest['books'])} books")
    else:
        manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
        items = manifest["cases"]
        print(f"decisions: {len(items)} documents")
    if args.books:
        wanted = {b.strip().lower() for b in args.books.split(",")}
        items = [i for i in items if (i.get("book_code") or "").lower() in wanted]
        print(f"filtered to books {sorted(wanted)}: {len(items)} sections")
    entries = items[: args.limit] if args.limit else items
    print(f"processing {len(entries)}")
    print()

    stats = {"ingested": 0, "skipped_existing": 0, "skipped_no_markdown": 0, "chunks": 0}
    redactions: dict[str, int] = {}
    started = time.time()

    with SessionLocal() as db:
        for index, entry in enumerate(entries, start=1):
            record = json.loads((CORPUS / entry["local_path"]).read_text(encoding="utf-8"))
            olid = record["open_legal_data_id"]

            markdown = (record.get("markdown_content") or "").strip()
            if not markdown:
                # The 129 API-downloaded cases predate the dump and carry only HTML. The dump
                # supersedes them; converting HTML here would duplicate work the dump did.
                stats["skipped_no_markdown"] += 1
                continue

            existing = db.scalar(
                select(func.count(DocumentChunk.id))
                .join(SourceDocument)
                .where(SourceDocument.open_legal_data_id == olid)
            )
            if existing:
                stats["skipped_existing"] += 1
                continue

            clean, counts = strip_identifiers(markdown)
            for key, value in counts.items():
                redactions[key] = redactions.get(key, 0) + value

            if record.get("doc_kind") == "law":
                # A § is short and self-contained. Chunking it by section headings would be
                # meaningless — the § designator IS the section label a citation shows.
                from app.ingestion.chunking import Chunk, chunk_section

                designator = record.get("file_number") or "§"
                pieces = [
                    Chunk(section=designator, number=None, text=piece)
                    for piece in chunk_section(clean, limit=350, overlap=50)
                ]
            else:
                pieces = chunk_document(clean)
            if not pieces:
                stats["skipped_no_markdown"] += 1
                continue

            document = upsert_document(db, record, clean)
            vectors = embed_passages([c.text for c in pieces], batch_size=args.batch_size)

            db.add_all(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=position,
                    section=chunk.section,
                    paragraph_number=chunk.number,
                    text=chunk.text,
                    embedding=vector,
                )
                for position, (chunk, vector) in enumerate(zip(pieces, vectors))
            )
            db.commit()

            stats["ingested"] += 1
            stats["chunks"] += len(pieces)

            if index % 10 == 0 or index == len(entries):
                elapsed = time.time() - started
                rate = stats["chunks"] / elapsed if elapsed else 0
                remaining = (len(entries) - index) * (stats["chunks"] / max(stats["ingested"], 1))
                eta = remaining / rate / 60 if rate else 0
                print(
                    f"  {index}/{len(entries)}  {stats['chunks']:,} chunks  "
                    f"{rate:.1f} chunks/s  ETA {eta:.0f} min"
                )

    elapsed = time.time() - started
    print(f"\ningested        : {stats['ingested']} document(s), {stats['chunks']:,} chunks")
    print(f"skipped (done)  : {stats['skipped_existing']}")
    print(f"skipped (no md) : {stats['skipped_no_markdown']}")
    print(f"redactions      : {redactions or 'none'}")
    print(f"elapsed         : {elapsed / 60:.1f} min")


if __name__ == "__main__":
    main()
