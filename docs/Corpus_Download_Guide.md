# Judges Said — Corpus download guide

How to fill `data/downloads/` with German labour-court decisions from Open Legal Data.

This is Phase 0 of [Todos_Backend.md](Todos_Backend.md). Nothing else in the project can be
built until it is done — there is no retrieval without a corpus. Read [Architecture.md](Architecture.md)
first for why this source and no other.

---

## What the downloader does

[download_corpus.py](../scripts/download_corpus.py) walks the Open Legal Data REST API, keeps only the
courts in one jurisdiction, fetches each decision's full text, and writes one JSON file per
decision plus a manifest describing the whole set.

```text
API  de.openlegaldata.io/api
 ├── /courts/            all 1,119 courts, filtered client-side to Arbeitsgerichtsbarkeit
 ├── /cases/?court={id}  case stubs per court   (no `content` field on list responses)
 └── /cases/{id}/        the detail call that actually carries the full HTML
        ↓
data/downloads/
 ├── cases/<court-slug>/<case-id>.json
 └── manifest.json
```

Two things it deliberately does **not** do: it does not strip personal data (that happens at
ingestion, before anything becomes searchable), and it does not convert HTML to Markdown
(that is `convert_to_markdown.py`, the next stage).

---

## Prerequisites

You need `uv` and nothing else. The script is **standard library only** by design — it runs
before any project environment exists, so there is no venv to create and no requirements file
to install.

```powershell
uv --version    # any recent version is fine
```

The script carries a PEP 723 header requiring Python ≥ 3.12, and `uv run` will fetch a
matching interpreter automatically. Do not invoke it as `python scripts/download_corpus.py` unless
your system `python` is already 3.12+ — on this machine it is 3.11.

---

## Step 1 — Set a real User-Agent (mandatory)

Open [download_corpus.py](../scripts/download_corpus.py) and edit line 34:

```python
USER_AGENT = "Judges Said corpus builder (your.email@example.com)"
```

Replace the placeholder with something that reaches a human — a personal address, an
institutional one, or a project URL all work equally well. The script only checks that the
placeholder string is gone, and refuses to start otherwise:

```text
SystemExit: Set USER_AGENT at the top of this file to a real contact address first.
```

This is not ceremony. Open Legal Data is a small non-profit; an identifying User-Agent lets
them contact you instead of blocking you if your traffic causes trouble. Anonymous bulk
traffic that degrades a free service invites UWG obstruction claims even where the data
itself is free to use.

---

## Step 2 — Smoke run

Set the ceiling low, confirm the API is reachable and the output shape is right, and only
then commit to the full download.

```python
MAX_CASES_TOTAL = 50    # line 37
```

```powershell
uv run scripts/download_corpus.py
```

Expected output, roughly one minute:

```text
Courts: 1119 total, 128 in 'Arbeitsgerichtsbarkeit'
  Arbeitsgericht Aachen: 4 case(s)
  Arbeitsgericht Arnsberg: 2 case(s)
  ...

50 case(s), 0 law section(s)
Manifest: ...\data\downloads\manifest.json
```

If the court count does not read `128 in 'Arbeitsgerichtsbarkeit'`, stop — either the API
changed or you are being served an error page, and there is no point downloading on top of
that.

---

## Step 3 — Verify before scaling up

Three checks, all of which the backend will later depend on:

```powershell
# 1. Manifest exists and carries the citation fields
python -c "import json; m=json.load(open('data/downloads/manifest.json',encoding='utf-8')); print(m['case_count']); print(m['cases'][0])"

# 2. A saved case has real HTML with German section headings
python -c "import json,glob; d=json.load(open(glob.glob('data/downloads/cases/*/*.json')[0],encoding='utf-8')); print(d['content_html'][:300])"

# 3. Re-running skips everything already on disk
uv run scripts/download_corpus.py
```

What you are looking for:

| Check | Pass condition |
| ----- | -------------- |
| Manifest entries | `court_name`, `file_number`, `decision_date`, `decision_type`, `source_url` all present |
| Case HTML | non-empty, contains `<h2>Tenor</h2>` and paragraph markup — no OCR artefacts, no login wall |
| Re-run | finishes in seconds, downloads nothing new, prints the same per-court counts |

The Aktenzeichen in `file_number` (e.g. `2 Ca 633/23`) is the field the whole citation UI
hangs off, and it carries a unique constraint in the database later. If it is missing or
empty across many entries, fix that here rather than downstream.

---

## Step 4 — Full pilot download: use the dumps, not the API

**The API cannot deliver a pilot-sized corpus.** Measured 2026-08-17: the anonymous quota is
a *daily* one. After roughly 170 requests — one 50-case smoke run, one idempotent re-run, and
68 cases of a full run — the API returned:

```text
HTTP/1.1 429 Too Many Requests
Retry-After: 85992          # 23.9 hours
```

`Retry-After` in the tens of thousands of seconds is the tell: this is a quota reset, not a
burst limit, so no amount of backoff tuning helps. At ~150 cases/day, 2,000 cases would take
about two weeks. `get_json()` now detects this and exits with an actionable message instead
of a traceback.

So the API is the right tool for **smoke-testing and small samples only**. For bulk, take the
route `robots.txt` explicitly points at:

> `# do not crawl us to get all the data:`
> `# download everything via our data dumps or API!`
> `# or via https://huggingface.co/openlegaldata/datasets`

`static.openlegaldata.io/dumps/` now redirects to HuggingFace, so the dumps *are* the HF
datasets. Three matter here:

| Dataset | Use |
| ------- | --- |
| `openlegaldata/court-decisions-germany` | the case corpus — `dump-20260520` (54 shards), plus ready-made `-1k` and `-10k` subsets |
| `openlegaldata/laws-germany` | Phase 7 statutes — replaces the ~3,540-request API sweep entirely |
| `openlegaldata/legal-citation-graph-germany` | case↔statute links, i.e. the `norm_refs` column |

All three are **gated** (`gated: auto` — accepting the terms grants access immediately, but a
token is still required). Unauthenticated file requests return HTTP 401.

### Getting access

1. Create a free account at <https://huggingface.co/join>
2. Open each dataset page above and click **"Agree and access repository"**
3. Create a **read** token at <https://huggingface.co/settings/tokens>
4. Put it in your environment — never in a tracked file:

```powershell
$env:HF_TOKEN = "hf_..."
```

Parquet cannot be read with the standard library. Rather than adding a project dependency —
which would break the "runs before any environment exists" property that keeps
`download_corpus.py` stdlib-only — declare it inline in the PEP 723 header so `uv run` fetches
it per-script:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyarrow"]
# ///
```

Shards are downloadable individually, so the conversion streams them one at a time, filters
to the target jurisdiction, and stops once `MAX_CASES_TOTAL` is reached — you only pay for
the shards you actually consume.

### Corpus breadth — the setting worth thinking about

Courts are visited in alphabetical order and each one takes up to `MAX_CASES_PER_COURT`
before the next is touched. With the shipped defaults (200 per court, 2,000 total) the budget
is exhausted after roughly ten courts, and your entire pilot corpus is decisions from
*Arbeitsgericht A…* through *Arbeitsgericht B…*.

That skews retrieval in a way that is easy to miss and annoying to debug: queries will look
like they work, but the "analogous cases" will all come from the same handful of courts.

Lowering `MAX_CASES_PER_COURT` to 15–25 spreads the same 2,000 documents across most of the
128 labour courts, which is what you want for a precedent explorer. Raise it later if you
want depth at specific courts.

---

## The knobs

All of them live at the top of [download_corpus.py](../scripts/download_corpus.py) — there is no CLI and
no config file, on purpose.

| Setting | Default | What it controls |
| ------- | ------- | ---------------- |
| `USER_AGENT` | placeholder | Contact address sent with every request. Must be changed. |
| `JURISDICTION` | `Arbeitsgerichtsbarkeit` | Which of the seven court jurisdictions to keep. Counts for all of them are listed in `COURT_JURISDICTIONS`. |
| `MAX_CASES_PER_COURT` | 200 | Per-court ceiling. See "Corpus breadth". |
| `MAX_CASES_TOTAL` | 2000 | Global ceiling; the run stops once reached. |
| `OUTPUT_DIR` | `data/downloads` | Where JSON and the manifest land. |
| `REQUEST_DELAY_SECONDS` | 0.34 | Politeness delay, ~3 req/s. Do not raise the rate. |
| `FETCH_LAWS` | `False` | Statute corpus — Phase 7, see below. |
| `LAW_BOOK_CODES` | KSchG, EntgFG, … | Which statute books to keep when `FETCH_LAWS` is on. |

Widening `JURISDICTION` to `Ordentliche Gerichtsbarkeit` (754 courts) is the tenancy- and
consumer-law expansion — do it only after the labour slice works end to end.

---

## What lands on disk

`data/downloads/` is gitignored. It is large and fully reproducible from this script, so it
is never committed.

### One case file

`data/downloads/cases/arbg-arnsberg/376592.json`

```json
{
  "doc_kind": "case",
  "open_legal_data_id": 376592,
  "court_id": 755,
  "court_name": "Arbeitsgericht Arnsberg",
  "court_jurisdiction": "Arbeitsgerichtsbarkeit",
  "decision_type": "Urteil",
  "decision_date": "2024-02-15",
  "published_date": "2026-03-18T20:06:37Z",
  "file_number": "2 Ca 633/23",
  "ecli": "ECLI:DE:ARBGAR:2024:0215.2CA633.23.00",
  "slug": "arbg-arnsberg-2024-02-15-2-ca-63323",
  "source_url": "https://de.openlegaldata.io/case/arbg-arnsberg-2024-02-15-2-ca-63323/",
  "license_note": "Public domain under § 5 UrhG (amtliches Werk). Source: Open Legal Data.",
  "content_html": "<h2>Tenor</h2>\n\n<p><strong>Die Klage wird abgewiesen.</strong></p>…"
}
```

These field names are already the `source_documents` column names from the schema
mapping, so ingestion is a rename-free copy.

`ecli` is often empty upstream and is nullable. `source_url` is empty in the API far more
often than you would expect, so the script falls back to the canonical slug page — every
citation in the UI needs a working link.

### The manifest

`data/downloads/manifest.json` is the index the ingestion step reads. It repeats every case's
metadata **without** `content_html`, plus a `local_path` pointing at the payload:

```json
{
  "generated_at": "2026-08-17T12:27:25+00:00",
  "source": "Open Legal Data (de.openlegaldata.io)",
  "license_note": "Public domain under § 5 UrhG (amtliches Werk). Source: Open Legal Data.",
  "jurisdiction": "Arbeitsgerichtsbarkeit",
  "case_count": 6,
  "law_count": 0,
  "cases": [{ "…": "…", "local_path": "cases/arbg-aachen/368074.json" }],
  "laws": []
}
```

The manifest is rewritten from scratch on every run and always reflects what is currently on
disk, including files from earlier runs.

---

## Re-running, resuming, and the one gotcha

The script is idempotent: before fetching a case it checks whether
`cases/<court>/<id>.json` already exists, and if so reads it from disk instead of hitting the
API. So an interrupted run resumes for free — just run it again. Raising `MAX_CASES_TOTAL`
and re-running only downloads the difference.

**The gotcha:** because re-runs trust what is on disk, they do not backfill. If you change
the record shape in `save_case()` — add a field, fix the `source_url` fallback — already
downloaded files keep the old shape and no re-run will repair them. You can spot this by an
older file having an empty `source_url` while newer ones have the slug fallback.

To force a refetch, delete what you want rebuilt:

```powershell
# One court
Remove-Item -Recurse data\downloads\cases\arbg-aachen

# Everything
Remove-Item -Recurse data\downloads
```

---

## Statutes (Phase 7 — leave off for now)

`FETCH_LAWS = False` by default, and it should stay that way until case retrieval works end
to end. The reason is cost: `/api/laws/` **ignores every filter parameter** (`book`,
`book_code`, `book_slug`, `slug` — all verified to return the unfiltered 176,915 rows), and
`page_size` is capped at 50, so selecting even seven statute books requires sweeping the
entire statute corpus client-side. That is ~3,540 requests, well over an hour at the polite
rate.

When you do need statutes, the HuggingFace dumps Open Legal Data publishes are the better
route than the API. `/api/law_books/?code=KSchG` does filter correctly, so book metadata —
including the `revision_date` / `latest` pair that the cross-version comparison retrieval is
built around — is cheap to fetch either way.

---

## API quirks, verified — do not rediscover these

| Behaviour | Consequence |
| --------- | ----------- |
| `page_size` silently capped at 50 | Asking for more just wastes the round trip. |
| `/api/cases/?court={id}` works | Per-court fetching genuinely narrows (ArbG Berlin → 171). |
| `/api/laws/` ignores all filters | Filter client-side, or use the dumps. |
| `/api/law_books/?code=X` works | Returns exactly 1 for a valid code. |
| `/api/cases/search/` returns HTTP 400 with plain `q=` | Do not build on the search endpoints without working out their real parameter shape. |
| List responses omit `content` | One extra detail request per document; this is the run's whole time budget. |

The script's `get_json()` retries 5xx and 429 with escalating backoff, returns `{}` on 404,
and raises immediately on other 4xx — a 403 means something is wrong with your request, and
retrying it would just be rude.

---

## Legal boundaries

These are enforced choices, not preferences. Details in the README → "Legal boundaries".

- **Never crawl `rechtsprechung-im-internet.de`.** Its `robots.txt` is `Disallow: /` for every
  agent except `DG_JUSTICE_CRAWLER`. Case law comes from Open Legal Data only. Open Legal
  Data's own `robots.txt` points consumers at the API, dumps, and HuggingFace datasets, so
  bulk use there is invited rather than merely tolerated.
- **§ 5 UrhG** removes copyright from statutes and court decisions entirely. The downloader
  records that provenance in `license_note` on every record rather than leaving it implicit.
- **Personal data stays untouched at this stage.** Decisions are pseudonymized, not
  anonymized, and labour decisions routinely contain GDPR Article 9 special-category data —
  health data in sick-pay cases, union membership in works-council cases, religion in
  church-employment cases. Downloads stay faithful to the source; identifier handling belongs
  in ingestion, before anything becomes searchable. Personal identifiers are never indexed as
  searchable fields.
- **Keep the rate limit.** 0.34 s between requests is deliberate.

---

## Troubleshooting

| Symptom | Cause and fix |
| ------- | ------------- |
| `SystemExit: Set USER_AGENT …` | Step 1 not done. Edit line 34. |
| `Courts: 0 total` | API unreachable or returning an error page. Open `https://de.openlegaldata.io/api/courts/` in a browser before retrying. |
| `Rate limited for 23.9h — the anonymous daily quota is spent` | Expected once you exceed ~170 requests/day. Not fixable by backoff. Use the dumps (Step 4). Everything already downloaded is kept, and re-running resumes. |
| Run stops early with fewer cases than `MAX_CASES_TOTAL` | Not all courts publish decisions to Open Legal Data. Many small ArbG have a handful or none. Raise the ceiling or widen `JURISDICTION`. |
| Cases skipped silently | `save_case()` returns `None` when `content` is empty — some records exist as metadata only. Expected; they are correctly excluded from the manifest. |
| All cases come from courts starting with A and B | Alphabetical order plus a high `MAX_CASES_PER_COURT`. See "Corpus breadth". |
| Old files missing a field newer ones have | Idempotent re-runs do not backfill. Delete and refetch. |
| `python: command not found` in the verify snippets | Use `uv run python -c "…"` instead. |

---

## After the download

The corpus feeds the rest of the pipeline unchanged:

```text
scripts/download_corpus.py  API → data/downloads/*.json + manifest.json     ← you are here
convert_to_markdown.py  HTML → normalized Markdown, section labels preserved
ingest_to_db.py         chunk → embed locally → source_documents + document_chunks
```

Two things to carry forward into the next stage:

- The German section headings in `content_html` (`Tenor`, `Leitsatz`, `Tatbestand`,
  `Entscheidungsgründe`) become the `section` label on every chunk. They replace the page
  number the previous project never populated, and they are what makes a citation point at
  something a reader can find.
- Embeddings must use `intfloat/multilingual-e5-base` with the `query: ` / `passage: `
  prefixes. `BAAI/bge-small-en-v1.5` is English-only and produces garbage on this corpus.

Then tick off Phase 0 in [Todos_Backend.md](Todos_Backend.md) and move on to Phase 1.
