# Judges Said

**A German labour-law precedent explorer.** Describe an employment situation in plain German or
English and get the real court decisions that match — each citing the court, the Aktenzeichen, the
decision date, and the statutory provisions the ruling turns on.

It shows **precedent, never predictions** — a compliance boundary enforced in code, not a stylistic
preference.

**▶ Live: [judges-said-l49g.onrender.com](https://judges-said-l49g.onrender.com)**

```
"mein Arbeitgeber hat mir während der Probezeit während einer Krankschreibung gekündigt"

  → Arbeitsgericht Aachen · 8 Ca 1327/16 d · 08.09.2016 · Urteil
       § 622 BGB · § 46 ArbGG · § 5 BUrlG
  → Arbeitsgericht Bonn · 4 Ca 139/16 · 12.04.2017 · Beschluss
       § 181 BGB · § 5 ArbGG · § 48 ArbGG · § 17a GVG
  → Arbeitsgericht Düsseldorf · 1 Ca 18/24 · 28.06.2024 · Urteil
       § 1 KSchG · § 4 KSchG · § 168 SGB IX · § 22 AGG
```

*Court, Aktenzeichen, date, and cited provisions are stored fields, not generated text.*

---

## Why it exists

German legal research sits behind Beck-online and juris subscriptions. Employees, small-business HR
staff, and works-council members need to know how courts have ruled on situations like theirs, and
are exactly the people who cannot justify the licence fee. Court decisions and statutes carry no
copyright in Germany (§ 5 UrhG) — the evidence is public domain, only access is expensive.

## What it does

| | |
| --- | --- |
| **Hybrid retrieval** | Semantic (pgvector HNSW) + lexical (German full-text search), fused with Reciprocal Rank Fusion |
| **Bilingual** | Ask in German or English; switching answer language does not re-run retrieval, so both versions cite the same decisions |
| **Evidence stays German** | Court names, Aktenzeichen, dates, § references, and quoted passages are never translated |
| **Grounded only** | Every claim is verified against the retrieved German source; unverifiable answers are refused |
| **Refuses out of scope** | Outcome predictions and person searches are rejected before a model is called |

## Stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.12 · FastAPI · Pydantic v2 · PydanticAI |
| LLM | OpenAI — answers and thread titles only |
| Embeddings | `intfloat/multilingual-e5-base` (768-dim), run **locally** |
| Frontend | Vite · React 19 · TypeScript · Tailwind v4 · shadcn/ui |
| Database | Supabase Postgres + `pgvector` · Alembic migrations |
| Auth | Supabase Auth, email only |

No SSR, no managed vector database, no LLM calls from the browser, no external embedding API.

**→ [docs/Architecture.md](docs/Architecture.md)** — turn lifecycle, retrieval design, grounding
validator, data model, and API.

## Corpus

**[Open Legal Data](https://de.openlegaldata.io)**, labour jurisdiction only
(`Arbeitsgerichtsbarkeit`). Decision text arrives as clean HTML, so there is no OCR stage.

| | Documents | Chunks |
| --- | --- | --- |
| Court decisions | 1,070 | 33,581 |
| Statute sections | 5,680 | 7,844 |
| **Total** | **6,750** | **41,425** |

Download walkthrough: **[docs/Corpus_Download_Guide.md](docs/Corpus_Download_Guide.md)**

## Deployment

```
  Browser ──► Render static site   (React SPA, free)
                    │ HTTPS
              Hetzner VPS          (nginx + Let's Encrypt)
                    │
              Docker container     (FastAPI + e5 model, ~1.6 GB)
                    │
              Supabase             (Postgres + pgvector)
```

The split is forced by one number: the embedding model needs ~1.6 GB of RAM and every free platform
tier caps at 512 MB. Shrinking it was measured and rejected — three quantization approaches each
changed 20–100 % of *which decisions got cited*.

Full checklist, including hosts evaluated and rejected:
**[docs/Todos_Deployment.md](docs/Todos_Deployment.md)**

## Running it locally

**Prerequisites:** Python 3.12 + [uv](https://docs.astral.sh/uv/) · Node 20 + pnpm · a Supabase
project · an OpenAI API key · a HuggingFace token.

```bash
export HF_TOKEN=hf_...
uv run scripts/download_dump.py     # court decisions
uv run scripts/download_laws.py     # statute sections

cd backend
cp .env.example .env                # Supabase, DATABASE_URL, OPENAI_API_KEY
uv sync && uv run alembic upgrade head
uv run ingest_to_db.py --limit 50   # omit --limit for the full corpus
uv run uvicorn app.main:app --reload

cd ../frontend
cp .env.example .env
pnpm install && pnpm dev            # http://localhost:5173
```

Use the **direct** Supabase connection (port 5432), not the pooler: migrations create extensions and
build HNSW indexes, which need session-level access.

`cd backend && uv run pytest` runs 104 tests with no network or database. The grounding, retrieval,
and ingestion tests are deliberately LLM-free — a control that can only be verified by asking a model
is not a control.

## Legal boundaries

Requirements, not suggestions. The first and last are enforced in code.

1. **RDG.** Retrieving and citing decisions is *information*; assessing someone's case is a regulated
   *legal service*. The product stays on the legal side by surfacing analogous rulings and refusing
   to predict outcomes — enforced in the grounding validator, because a prompt is not a compliance
   control.
2. **No crawling of court portals.** `rechtsprechung-im-internet.de` is `Disallow: /`. Case law comes
   from Open Legal Data, rate-limited with an identifying User-Agent.
3. **§ 5 UrhG provenance** recorded per document in `license_note`.
4. **Personal data.** Decisions are pseudonymized, not anonymized, and labour cases routinely carry
   GDPR Article 9 data — health, union membership, religion. Residual identifiers are redacted at
   ingestion, never indexed as searchable fields, and person-queries are refused outright.

**Non-goals:** predicting outcomes · legal advice · person or employer search · crawling court
portals · translating the corpus · languages beyond German and English · billing · a mobile app.

## Repository layout

```text
docs/          architecture, corpus guide, deployment checklist
scripts/       corpus downloaders
deploy/        nginx config and deploy script
backend/       FastAPI service + Dockerfile
frontend/      React SPA
```

## Attribution and licence

Court decisions and statutes are public domain under **§ 5 UrhG** (*amtliches Werk*). Corpus data
comes from **[Open Legal Data](https://de.openlegaldata.io)**, with provenance recorded per document
in `license_note`.

This tool provides **legal information, not legal advice**. It surfaces how German courts have ruled
in comparable cases; it does not assess anyone's individual case and does not predict how any dispute
will turn out.

## Demo

https://github.com/user-attachments/assets/cbfa0f90-aab7-48d8-809e-c605d569d227
