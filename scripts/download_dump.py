# /// script
# requires-python = ">=3.12"
# dependencies = ["pyarrow"]
# ///
"""Build the labour-law corpus from the Open Legal Data bulk dump.

Run:  uv run download_dump.py
Needs: HF_TOKEN (read scope) in the environment.

Why this exists next to download_corpus.py
------------------------------------------
The API cannot deliver a pilot-sized corpus: its anonymous quota is a sliding ~24h window
worth roughly 150 requests, so a full run yields ~50 cases and reaching 2,000 takes weeks.
`robots.txt` directs bulk consumers to the dumps instead, and `static.openlegaldata.io/dumps/`
now redirects to HuggingFace. `download_corpus.py` stays standard-library only for smoke runs
against the live API; this script needs a parquet reader, declared inline above so `uv run`
fetches it per-script rather than making it a project dependency.

Output is byte-identical in shape to the API path, so ingestion does not care which produced
a given case. Two fields the API never gave us are populated here: `markdown_content`, which
the dump ships pre-converted, and `norm_refs`, which it ships pre-parsed.
"""

from __future__ import annotations

import collections
import json
import os
import shutil
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq

# Params: edit these, then run `uv run download_dump.py`
MAX_CASES = 5000
# Shards are court-ordered, not shuffled: taking shard 0 then 1 gave 1,871 Bundesarbeitsgericht
# decisions out of 2,000. Two corrections — walk the shards with a stride so we sample across
# the ordering rather than a contiguous block, and cap any single court so no one of them can
# dominate again. Court spread, not row count, is what makes retrieval testable.
MAX_CASES_PER_COURT = 150
SHARD_STRIDE = 6
DUMP = "dump-20260520"  # 54 shards, ~7,850 decisions each; ~8.9% are labour
SHARD_COUNT = 54

REPO = "openlegaldata/court-decisions-germany"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "downloads"
SHARD_CACHE = OUTPUT_DIR / ".shard.parquet"  # one shard at a time, deleted as we go
LICENSE_NOTE = "Public domain under § 5 UrhG (amtliches Werk). Source: Open Legal Data."


def is_labour(court: dict) -> bool:
    """Labour courts, including the ones the dump forgot to label.

    Landesarbeitsgericht München and Landesarbeitsgericht Niedersachsen carry
    `jurisdiction: None` in dump-20260520 — verified. Filtering on jurisdiction alone drops
    them silently, so match the court name as well.
    """
    if court.get("jurisdiction") == "Arbeitsgerichtsbarkeit":
        return True
    return "arbeitsgericht" in (court.get("name") or "").lower()


def norm_refs(reference_markers: str) -> list[dict]:
    """Statutes cited by a decision, from the dump's pre-parsed reference markers.

    Each marker spans a citation in the text and expands to one or more references;
    `§§ 55a, 55d VwGO` yields two. Case-to-case citations share the field and are dropped
    here — they are a precedent graph, not the statute join `norm_refs` exists for.
    """
    if not (reference_markers or "").strip():
        return []
    refs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for marker in json.loads(reference_markers):
        for ref in marker.get("references") or []:
            if ref.get("ref_type") != "RefType.LAW":
                continue
            key = (ref.get("book") or "", ref.get("section") or "")
            if key == ("", "") or key in seen:
                continue
            seen.add(key)
            refs.append({"book": key[0], "section": key[1]})
    return refs


def to_record(row: dict) -> dict:
    """One parquet row -> the same record shape download_corpus.py writes."""
    court = row["court"]
    slug = row["slug"]
    return {
        "doc_kind": "case",
        "open_legal_data_id": row["id"],
        "court_id": court.get("id"),
        "court_name": court.get("name"),
        "court_jurisdiction": court.get("jurisdiction") or "Arbeitsgerichtsbarkeit",
        "decision_type": row.get("type"),
        "decision_date": row.get("date"),
        "published_date": row.get("created_date"),
        "file_number": row.get("file_number"),
        "ecli": row.get("ecli") or None,
        "slug": slug,
        # openlegaldata.io no longer serves pages for individual cases — /case/{slug}/ and
        # every variant of it 404. The API detail endpoint is the only stable link, so use
        # it. The human-readable court-portal URL exists only on the API record, not in the
        # dump, so it has to be fetched per case and is left for the citation UI to do
        # lazily for the handful of decisions actually shown.
        "source_url": f"https://de.openlegaldata.io/api/cases/{row['id']}/",
        "license_note": LICENSE_NOTE,
        "norm_refs": norm_refs(row.get("reference_markers") or ""),
        "content_html": row.get("content") or "",
        "markdown_content": row.get("markdown_content") or "",
    }


def fetch_shard(index: int, token: str) -> None:
    name = f"{DUMP}/train-{index:05d}-of-{SHARD_COUNT:05d}.parquet"
    url = f"https://huggingface.co/datasets/{REPO}/resolve/main/{name}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=600) as response, SHARD_CACHE.open("wb") as out:
        shutil.copyfileobj(response, out)


def rebuild_manifest() -> dict:
    """Index every case on disk, whatever downloaded it. Disk is the source of truth."""
    cases = []
    for path in sorted((OUTPUT_DIR / "cases").glob("*/*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        cases.append(
            {k: v for k, v in record.items() if k not in ("content_html", "markdown_content")}
            | {"local_path": str(path.relative_to(OUTPUT_DIR)).replace("\\", "/")}
        )
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": f"Open Legal Data bulk dump {DUMP} (HuggingFace: {REPO})",
        "license_note": LICENSE_NOTE,
        "jurisdiction": "Arbeitsgerichtsbarkeit",
        "case_count": len(cases),
        "law_count": 0,
        "cases": cases,
        "laws": [],
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit(
            'HF_TOKEN is not set. Create a read token at huggingface.co/settings/tokens, '
            'then:  [Environment]::SetEnvironmentVariable("HF_TOKEN", "hf_...", "User")'
        )

    cases_dir = OUTPUT_DIR / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    existing = {path.stem for path in cases_dir.glob("*/*.json")}
    # Cap counts come from the directory layout — one directory per court slug — so a re-run
    # honours what earlier runs already wrote without reading 2,000 files to find out.
    per_court = collections.Counter(
        path.parent.name for path in cases_dir.glob("*/*.json")
    )
    print(f"{len(existing)} case(s) already on disk across {len(per_court)} court(s)")
    at_cap = [c for c, n in per_court.items() if n >= MAX_CASES_PER_COURT]
    if at_cap:
        print(f"already at the {MAX_CASES_PER_COURT}/court cap: {', '.join(sorted(at_cap))}")
    print()

    # Strided first so we sample across the court ordering, then fill in the gaps if the
    # target is still short. `existing` grows as we write, so it is the running total.
    strided = list(range(0, SHARD_COUNT, SHARD_STRIDE))
    order = strided + [i for i in range(SHARD_COUNT) if i not in set(strided)]

    for index in order:
        if len(existing) >= MAX_CASES:
            break

        print(f"shard {index}/{SHARD_COUNT} …", end=" ", flush=True)
        fetch_shard(index, token)
        rows = pq.read_table(SHARD_CACHE).to_pylist()
        SHARD_CACHE.unlink()

        kept = 0
        for row in rows:
            if len(existing) >= MAX_CASES:
                break
            if not is_labour(row["court"]):
                continue
            if str(row["id"]) in existing:
                continue
            if not (row.get("markdown_content") or "").strip():
                continue

            slug = row["court"].get("slug") or str(row["court"]["id"])
            if per_court[slug] >= MAX_CASES_PER_COURT:
                continue

            court_dir = cases_dir / slug
            court_dir.mkdir(parents=True, exist_ok=True)
            (court_dir / f"{row['id']}.json").write_text(
                json.dumps(to_record(row), ensure_ascii=False, indent=2), encoding="utf-8"
            )
            existing.add(str(row["id"]))
            per_court[slug] += 1
            kept += 1

        print(f"{len(rows)} rows, +{kept} labour ({len(existing)} total, {len(per_court)} courts)")

    manifest = rebuild_manifest()
    courts = {case["court_name"] for case in manifest["cases"]}
    print(f"\n{manifest['case_count']} case(s) across {len(courts)} court(s)")
    print(f"Manifest: {OUTPUT_DIR / 'manifest.json'}")


if __name__ == "__main__":
    main()
