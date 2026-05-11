# /// script
# requires-python = ">=3.12"
# dependencies = ["pyarrow"]
# ///
"""Download the labour-law statute books from the Open Legal Data bulk dump.

Run:  uv run download_laws.py
Needs: HF_TOKEN (read scope) in the environment.

Phase 7. The API route the corpus guide describes is not viable: `/api/laws/` ignores every filter
and caps `page_size` at 50, so selecting even seven books means sweeping all 176,915 sections
— about 3,540 requests against a quota worth ~150 a day. The dump is one 147 MB file.

**The version axis is not in this dump.** It has no `revision_date` and no `latest` column,
and exactly one row per (book, §) — verified across all 113,537 sections. The original plan counted on
versioned law books for cross-version comparison; that has to come from `/api/law_books/`,
which does carry `revision_date` and `latest`. What is here is the current text only.
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq

# The books our decisions actually cite, from norm_refs across the ingested corpus.
LAW_BOOKS = {
    "bgb", "zpo", "arbgg", "betrvg", "kschg", "betravg", "agg", "inso", "tvg",
    "tzbfg", "arbzg", "burlg", "entgfg", "nachwg", "sgb 9", "gewo", "hgb", "gg",
}

REPO = "openlegaldata/laws-germany"
SHARD = "dump-20260520/train-00000-of-00001.parquet"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "downloads"
CACHE = OUTPUT_DIR / ".laws.parquet"
LICENSE_NOTE = "Public domain under § 5 UrhG (amtliches Werk). Source: Open Legal Data."


def fetch(token: str) -> None:
    if CACHE.is_file():
        print(f"using cached {CACHE.name} ({CACHE.stat().st_size / 1e6:.0f} MB)")
        return
    url = f"https://huggingface.co/datasets/{REPO}/resolve/main/{SHARD}"
    print("downloading statute dump …")
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=900) as response, CACHE.open("wb") as out:
        shutil.copyfileobj(response, out)


def main() -> None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit('HF_TOKEN is not set.')

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    laws_dir = OUTPUT_DIR / "laws"
    laws_dir.mkdir(parents=True, exist_ok=True)
    fetch(token)

    table = pq.read_table(CACHE)
    print(f"{table.num_rows:,} statute sections in the dump")

    entries: list[dict] = []
    for row in table.to_pylist():
        code = (row.get("book_code") or "").lower()
        if code not in LAW_BOOKS:
            continue
        markdown = (row.get("markdown_content") or "").strip()
        if not markdown:
            continue

        record = {
            "doc_kind": "law",
            "open_legal_data_id": row["id"],
            "book_code": code,
            "book_slug": row.get("book_slug"),
            # `section` here is the § designator, e.g. '§ 622' — the citation anchor.
            "file_number": row.get("section"),
            "title": row.get("title") or None,
            "source_url": f"https://de.openlegaldata.io/api/laws/{row['id']}/",
            "license_note": LICENSE_NOTE,
            # Not in this dump; recorded as unknown rather than guessed. See module docstring.
            "revision_date": None,
            "is_latest": None,
            "markdown_content": markdown,
        }
        target = laws_dir / f"{row['id']}.json"
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        entries.append(
            {k: v for k, v in record.items() if k != "markdown_content"}
            | {"local_path": f"laws/{row['id']}.json"}
        )

    manifest_path = OUTPUT_DIR / "laws_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "source": f"Open Legal Data statute dump (HuggingFace: {REPO})",
                "license_note": LICENSE_NOTE,
                "law_count": len(entries),
                "books": sorted({e["book_code"] for e in entries}),
                "laws": entries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    by_book: dict[str, int] = {}
    for entry in entries:
        by_book[entry["book_code"]] = by_book.get(entry["book_code"], 0) + 1
    print(f"\n{len(entries):,} section(s) across {len(by_book)} book(s)")
    for book, count in sorted(by_book.items(), key=lambda kv: -kv[1]):
        print(f"  {count:5}  {book}")
    print(f"\nManifest: {manifest_path}")


if __name__ == "__main__":
    main()
