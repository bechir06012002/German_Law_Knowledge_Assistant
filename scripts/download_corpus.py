# /// script
# requires-python = ">=3.12"
# ///
"""Download a German labour-law corpus from Open Legal Data.

Run:  uv run download_corpus.py

Standard library only, on purpose: this runs before any project environment exists.

Why Open Legal Data and not the official portal
-----------------------------------------------
`rechtsprechung-im-internet.de/robots.txt` is `Disallow: /` for every user agent except
`DG_JUSTICE_CRAWLER`, so we do not touch it. Open Legal Data's robots.txt instead points
consumers at its API, dumps, and HuggingFace datasets — bulk use is invited there.

German statutes and court decisions carry no copyright at all (§ 5 UrhG), which is why the
manifest records that provenance per document.

Personal data is NOT stripped here. Downloads stay faithful to the source; identifier
stripping happens in the ingestion step, before anything becomes searchable. See the README's legal boundaries.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

# Params: edit these, then run `uv run download_corpus.py`
USER_AGENT = "Judges Said corpus builder (bechir.labche@supcom.tn)"
# 128 of 1119 courts; see COURT_JURISDICTIONS below
JURISDICTION = "Arbeitsgerichtsbarkeit"
# Courts are visited alphabetically and each takes its full share before the next, so a high
# per-court cap spends the whole budget on Arbeitsgericht A–B. Keep this low for breadth.
MAX_CASES_PER_COURT = 20
MAX_CASES_TOTAL = 2000  # full pilot; 128 courts x 20 caps out at 2560
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "downloads"
# ~3 req/s; be a good citizen, UWG obstruction is a real claim
REQUEST_DELAY_SECONDS = 0.34

# Statutes are a Phase 7 concern — leave off until case retrieval works end to end.
# The API ignores every filter on /api/laws/ and caps page_size at 50, so a full sweep is
# ~3,540 requests. Prefer the HuggingFace dumps if you want the complete statute corpus.
FETCH_LAWS = False
LAW_BOOK_CODES = ["KSchG", "EntgFG", "ArbZG",
                  "BUrlG", "TzBfG", "AGG", "BetrVG"]

API_ROOT = "https://de.openlegaldata.io/api"
LICENSE_NOTE = "Public domain under § 5 UrhG (amtliches Werk). Source: Open Legal Data."

# Other jurisdictions available, if you widen scope later. Counts verified August 2026.
COURT_JURISDICTIONS = {
    "Ordentliche Gerichtsbarkeit": 754,
    "Arbeitsgerichtsbarkeit": 128,
    "Sozialgerichtsbarkeit": 79,
    "Verwaltungsgerichtsbarkeit": 61,
    "Finanzgerichtsbarkeit": 18,
    "Verfassungsgerichtsbarkeit": 16,
    "Berufsgerichtsbarkeit": 7,
}

# The API silently caps page_size at 50 no matter what you ask for. Asking for more just
# wastes the round trip, so request exactly what you will get.
API_PAGE_SIZE = 50


class QuotaExhausted(RuntimeError):
    """The API's rolling quota is spent. Caught so the manifest still gets written."""


def get_json(url: str, *, attempts: int = 4) -> dict:
    """GET with backoff. Retries transient failures; 404 is returned to the caller as {}."""
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return {}
            if error.code == 429:
                # The anonymous quota is a daily one: Retry-After comes back as ~24h, not
                # seconds. Retrying that is pointless, so stop with an actionable message
                # instead of burning the ladder and raising a traceback.
                wait = int(error.headers.get("Retry-After") or 0)
                if wait > 300:
                    raise QuotaExhausted(
                        f"rate limited for {wait / 3600:.1f}h"
                    ) from error
            elif error.code < 500:
                raise
            if attempt == attempts:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts:
                raise
        time.sleep(REQUEST_DELAY_SECONDS * 4 * attempt)
    return {}


def paginate(path: str, params: dict[str, str | int]) -> list[dict]:
    """Follow the API's `next` cursor and return every result."""
    query = {**params, "page_size": API_PAGE_SIZE}
    url = f"{API_ROOT}/{path}?{urllib.parse.urlencode(query)}"
    results: list[dict] = []
    while url:
        payload = get_json(url)
        results.extend(payload.get("results") or [])
        url = payload.get("next")
        if url:
            time.sleep(REQUEST_DELAY_SECONDS)
    return results


def labour_courts() -> list[dict]:
    """Courts in the target jurisdiction.

    /api/courts/ has no jurisdiction filter, so fetch all 1119 (23 pages) and filter here.
    """
    courts = paginate("courts/", {})
    selected = [c for c in courts if c.get("jurisdiction") == JURISDICTION]
    print(f"Courts: {len(courts)} total, {len(selected)} in '{JURISDICTION}'")
    return sorted(selected, key=lambda c: c.get("name") or "")


def case_stubs(court_id: int, limit: int) -> list[dict]:
    """Case metadata for one court. `?court=` genuinely narrows — verified."""
    stubs = paginate("cases/", {"court": court_id})
    return stubs[:limit]


def save_case(stub: dict, target: Path) -> dict | None:
    """Fetch one case's full text and write it. Returns a manifest entry, or None if empty.

    The list endpoint omits `content`; only the detail endpoint carries it, so this costs
    one extra request per case.
    """
    detail = get_json(f"{API_ROOT}/cases/{stub['id']}/")
    content = detail.get("content") or ""
    if not content.strip():
        return None

    court = detail.get("court") or {}
    slug = detail.get("slug")
    record = {
        "doc_kind": "case",
        "open_legal_data_id": detail["id"],
        "court_id": court.get("id"),
        "court_name": court.get("name"),
        "court_jurisdiction": court.get("jurisdiction"),
        "decision_type": detail.get("type"),
        "decision_date": detail.get("date"),
        "published_date": detail.get("created_date"),
        "file_number": detail.get("file_number"),
        "ecli": detail.get("ecli") or None,
        "slug": slug,
        # `source_url` is frequently empty in the API (verified), and the trust UI needs a
        # working link for every citation, so fall back to the canonical slug page.
        "source_url": detail.get("source_url")
        or (f"https://de.openlegaldata.io/case/{slug}/" if slug else None),
        "license_note": LICENSE_NOTE,
        "content_html": content,
    }
    target.write_text(json.dumps(record, ensure_ascii=False,
                      indent=2), encoding="utf-8")
    return {k: v for k, v in record.items() if k != "content_html"} | {
        "local_path": str(target.relative_to(OUTPUT_DIR)).replace("\\", "/")
    }


def download_cases() -> list[dict]:
    cases_dir = OUTPUT_DIR / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    try:
        for court in labour_courts():
            if len(entries) >= MAX_CASES_TOTAL:
                break

            remaining = min(MAX_CASES_PER_COURT, MAX_CASES_TOTAL - len(entries))
            stubs = case_stubs(court["id"], remaining)
            if not stubs:
                continue

            court_dir = cases_dir / (court.get("slug") or str(court["id"]))
            court_dir.mkdir(parents=True, exist_ok=True)

            saved = 0
            for stub in stubs:
                target = court_dir / f"{stub['id']}.json"
                if target.is_file():
                    # Idempotent re-run: trust what is already on disk.
                    record = json.loads(target.read_text(encoding="utf-8"))
                    entries.append(
                        {k: v for k, v in record.items() if k != "content_html"}
                        | {"local_path": str(target.relative_to(OUTPUT_DIR)).replace("\\", "/")}
                    )
                    saved += 1
                    continue

                entry = save_case(stub, target)
                time.sleep(REQUEST_DELAY_SECONDS)
                if entry:
                    entries.append(entry)
                    saved += 1

            print(f"  {court.get('name')}: {saved} case(s)")
    except QuotaExhausted as stop:
        # Keep going to the manifest write: the cases already on disk are the whole point,
        # and a stale manifest is what makes a partial run look like a failed one.
        print(f"\nStopped early — {stop}. Re-run later to resume where this left off.")

    return entries


def download_laws() -> list[dict]:
    """Statutes for LAW_BOOK_CODES.

    /api/law_books/?code=X works. /api/laws/ does not honour any filter, so we sweep and
    match client-side — expensive, hence FETCH_LAWS defaults to False.
    """
    laws_dir = OUTPUT_DIR / "laws"
    laws_dir.mkdir(parents=True, exist_ok=True)

    wanted = set(LAW_BOOK_CODES)
    books: dict[str, dict] = {}
    for code in LAW_BOOK_CODES:
        for book in paginate("law_books/", {"code": code}):
            if book.get("code") == code and book.get("latest"):
                books[code] = book
        time.sleep(REQUEST_DELAY_SECONDS)
    print(f"Law books resolved: {sorted(books)}")

    entries: list[dict] = []
    print("Sweeping /api/laws/ (no server-side filter available, this takes a while)…")
    for law in paginate("laws/", {}):
        code = law.get("book_code")
        if code not in wanted:
            continue

        target = laws_dir / f"{law['id']}.json"
        if not target.is_file():
            detail = get_json(f"{API_ROOT}/laws/{law['id']}/")
            time.sleep(REQUEST_DELAY_SECONDS)
            content = (detail.get("content") or "").strip()
            if not content:
                continue
            book = books.get(code, {})
            record = {
                "doc_kind": "law",
                "open_legal_data_id": detail["id"],
                "book_code": code,
                "book_title": book.get("title"),
                "section": detail.get("section"),
                "title": detail.get("title"),
                "revision_date": book.get("revision_date"),
                "is_latest": bool(book.get("latest")),
                "source_url": f"https://de.openlegaldata.io/law/{law.get('book_slug')}/{law.get('slug')}/",
                "license_note": LICENSE_NOTE,
                "content_html": content,
            }
            target.write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        record = json.loads(target.read_text(encoding="utf-8"))
        entries.append(
            {k: v for k, v in record.items() if k != "content_html"}
            | {"local_path": str(target.relative_to(OUTPUT_DIR)).replace("\\", "/")}
        )

    return entries


def main() -> None:
    if "your.email@example.com" in USER_AGENT:
        raise SystemExit(
            "Set USER_AGENT at the top of this file to a real contact address first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cases = download_cases()
    laws = download_laws() if FETCH_LAWS else []

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "Open Legal Data (de.openlegaldata.io)",
        "license_note": LICENSE_NOTE,
        "jurisdiction": JURISDICTION,
        "case_count": len(cases),
        "law_count": len(laws),
        "cases": cases,
        "laws": laws,
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n{len(cases)} case(s), {len(laws)} law section(s)")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
