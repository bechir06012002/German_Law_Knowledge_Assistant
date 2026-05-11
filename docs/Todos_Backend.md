# Judges Said — Backend checklist

Work top to bottom. Each phase unlocks the next. Read [Architecture.md](Architecture.md) first.

The critical path is **corpus → data model → ingestion → retrieval → agent → grounding**.
Every item below should be verifiable by running something, not by reading code.

---

## Phase 0 — Corpus (do this before writing any backend code)

You cannot build retrieval against a corpus you do not have. This phase is why
`download_corpus.py` lives in `scripts/` instead of inside `backend/`.

- [x] Set `USER_AGENT` at the top of `download_corpus.py` to a real contact address
- [x] Dry run to confirm the API is reachable and see planned volume:
      `uv run scripts/download_corpus.py` with `MAX_CASES_TOTAL = 50`
- [x] Confirm `data/downloads/manifest.json` exists and lists cases with `court_name`,
      `file_number`, `decision_date`, `decision_type`, `source_url`
- [x] Spot-check one saved case JSON: `content` is non-empty HTML containing `<h2>Tenor</h2>`
- [x] Re-run the script and confirm it skips everything already on disk (idempotent)

**Status 2026-08-17: 129 decisions across 8 courts (Aachen–Bocholt). Not enough to
judge retrieval, and the API cannot close the gap.** The anonymous quota is a sliding
~24h window worth roughly 150 requests; at ~1.2 requests per decision that is ~50–60
cases per run. Reaching 2,000 that way takes weeks, and because courts are walked
alphabetically the result stays skewed to A–B no matter how long it runs.

Bulk therefore comes from the dumps, which is what `robots.txt` directs consumers to
(`static.openlegaldata.io/dumps/` now redirects to HuggingFace):

- [x] Create a free HuggingFace account and click "Agree and access repository" on all three
      gated datasets: `openlegaldata/court-decisions-germany` (cases),
      `openlegaldata/laws-germany` (Phase 7 statutes),
      `openlegaldata/legal-citation-graph-germany` (the `norm_refs` join)
- [x] Set `HF_TOKEN` (read scope) in the environment — never in a tracked file
- [x] Probe the dump schema before writing any conversion: the repo is gated, so column
      names and whether a jurisdiction column exists are unknown until a shard is read
- [x] Declare `pyarrow` in the PEP 723 header so `uv run` fetches it per-script; do **not**
      add it as a project dependency (`download_corpus.py` must still run with no env)
- [x] Stream shards of `dump-20260520` one at a time, filter to `Arbeitsgerichtsbarkeit`,
      stop at the cap — only pay for shards actually consumed
- [x] Verify the slice spans most of the 128 labour courts, not just alphabetically-early
      ones; court spread is the check that the corpus is usable, not raw count

**Phase 0 complete — 5,000 decisions, 81 of 128 labour courts, 349 MB** (`download_dump.py`,
17 shards stride-sampled). Balanced across all three instances: 1,871 Bundesarbeitsgericht,
1,660 Landesarbeitsgericht, 1,469 first-instance Arbeitsgericht; decisions span 2013–2026.

Two traps found here, both silent, both already fixed in `download_dump.py` — do not
"simplify" either away:

1. **`court.jurisdiction` is null for some labour courts.** Landesarbeitsgericht München and
   Landesarbeitsgericht Niedersachsen carry `None` in `dump-20260520`. Filtering on
   jurisdiction alone drops 152 of 5,000 cases including an entire Landesarbeitsgericht, so
   `is_labour()` matches the court name as well.
2. **Shards are court-ordered, not shuffled.** Taking shards 0 and 1 produced 1,871
   Bundesarbeitsgericht decisions out of 2,000 — a corpus that passes a row-count check and
   fails the product. `SHARD_STRIDE` and `MAX_CASES_PER_COURT` exist for that reason.

---

## Phase 1 — Backend scaffold & database

Goal: a running FastAPI service with a migrated Supabase schema.

- [x] Create Supabase project; collect URL, anon key, service-role key, direct `DATABASE_URL`,
      and copy `backend/.env.example` to `backend/.env` with the real values
      (`OPENAI_API_KEY` still empty — only needed from Phase 5 onward)
- [x] `uv init` backend, add deps: `fastapi`, `uvicorn`, `pydantic-settings`, `pydantic-ai`,
      `supabase`, `sqlalchemy`, `alembic`, `pgvector`, `sentence-transformers`, `tiktoken`, `httpx`
- [x] `app/config.py` — settings module, fails fast on missing env vars
- [x] `app/main.py` — FastAPI app, CORS from `ALLOWED_ORIGINS`, `GET /health`
- [x] `app/database/models/constants.py` — `EMBEDDING_DIMENSIONS = 768`
      (the German model is `intfloat/multilingual-e5-base`, **not** 384/English)
- [x] SQLAlchemy models in `app/database/models/`:
  - [x] `users`
  - [x] `source_documents` — use the new German column names from the schema mapping table,
        including `doc_kind`, `norm_refs`, `revision_date`, `is_latest`, `license_note`
  - [x] `document_chunks` — embedding + generated `tsvector`; **no `page` column**
  - [x] `chat_threads`
  - [x] `chat_messages`
  - [x] `message_citations` — either build the ORM model *and use it*, or don't create the
        table. The previous project created the table, never modelled it, and stored
        citations inline in `chat_messages.parts` instead; don't repeat that split.
- [x] Initial Alembic migration, written explicitly (autogenerate cannot infer these):
  - [x] `create extension if not exists vector`
  - [x] `vector(768)` embedding column
  - [x] generated `tsvector` column using **`to_tsvector('german', text)`** — not `english`
  - [x] HNSW index on the embedding, GIN index on the tsvector
  - [x] ~~unique constraint on `file_number`~~ → **`(court_id, file_number)`**, index on
        `(court_name, decision_year)`. The Aktenzeichen is only unique *within a court*,
        unlike the SEC accession number this was inherited from. Measured on the real corpus:
        9 of 5,000 Aktenzeichen occur at two different courts (`5 Ca 750/24`, `2 Ca 2792/16`,
        …), so a global constraint would reject legitimate decisions at ingestion. The
        composite has zero collisions.
  - [x] RLS policies: users read only their own threads and messages
- [x] `uv run alembic upgrade head` against the Supabase **direct** connection
      (never the transaction pooler — extensions and index builds need session-level access)
      Verified live: 6 tables, `vector` + `pgcrypto` extensions, `vector(768)`,
      `to_tsvector('german', text)`, HNSW + GIN indexes, 5 RLS policies.
      `alembic/env.py` is deliberately **synchronous** — psycopg's async mode cannot run on
      Windows' default ProactorEventLoop, and a one-shot migration gains nothing from async.
- [x] `app/database/supabase.py` — user-scoped client and service-role client
- [x] Verify: `GET /health` returns 200, and `Settings()` raises when config is missing

---

## Phase 2 — Auth

Goal: the backend rejects unauthenticated requests before doing any work.

- [x] `app/auth/dependencies.py` — verify `Authorization: Bearer <supabase_jwt>`, expose
      `get_current_user`
- [x] Reject missing/expired/invalid tokens with `401` **before** retrieval or LLM work
- [x] Derive `user_id` and email from the verified Supabase user, never from request body
- [x] Verify: an authenticated test endpoint returns the caller's id; no token → 401
      Tested against the live project with a throwaway user (created, used, deleted):
      valid token → 200 with the right id; no token, garbage token, and a token without the
      `Bearer ` prefix all → 401; `/health` stays public.

Verification is delegated to Supabase (`auth.get_user`) rather than decoding the JWT locally.
Supabase is authoritative on expiry and revocation, and it removes any chance of getting
signature checking subtly wrong. The cost is one network call per request — if that shows up
in latency later, switch to local JWKS verification with cached keys, not to trusting the
token unverified.

---

## Phase 3 — Chat shell (stubbed, end to end)

Goal: a real streaming chat endpoint with a placeholder answer, so the frontend can start.

- [x] Thread CRUD: list threads, create thread, load message history — all user-scoped
      (plus delete, needed to clean up after tests)
- [x] `POST /chat/stream` — accepts AI SDK message format, streams text deltas
- [x] `app/chat/messages.py` — convert AI SDK wire messages to internal Pydantic models
- [x] `app/chat/streaming.py` — emit AI SDK-compatible parts
- [x] Persist user + assistant messages after the stream completes
- [x] `403` when a user requests another user's thread; `404` for a missing thread
- [x] Verify: 16/16 checks against the live database with two throwaway users — stream
      returns the `x-vercel-ai-ui-message-stream: v1` header, 25 `text-delta` events,
      `[DONE]` terminator; both messages persisted; user B gets 403 on user A's thread,
      404 on a nonexistent one, and sees none of A's threads.

Three things worth knowing before Phase 5 touches this:

1. **Sessions are synchronous.** psycopg's async mode cannot run on Windows' default
   ProactorEventLoop, and FastAPI runs `def` handlers in a threadpool anyway, so sync costs
   nothing here. `alembic/env.py` is sync for the same reason.
2. **The streaming generator opens its own session.** The one from `Depends(get_db)` is
   already closed by the time the response body starts, so persisting the assistant message
   inside the generator needs a fresh `SessionLocal()`.
3. **`_ensure_user` mirrors the Supabase user into `public.users`** on first request.
   Supabase owns `auth.users`; our foreign keys point at `public.users`, so the row has to
   exist before a thread can reference it.

---

## Phase 4 — Ingestion

Goal: downloaded decisions become chunked, embedded rows in Supabase.

**The dump already did most of this.** Every downloaded case carries `markdown_content`
(pre-converted, 1859/1859 with zero residual HTML tags, 100% with a `Tenor` heading) and
`norm_refs` (pre-parsed from the dump's `reference_markers`, 1859/1859 non-empty). Verify
before building — do not write a converter or a statute parser that already exists.

- [x] Verify `markdown_content` is good enough as-is; `convert_to_markdown.py` should shrink
      to a normalization pass, not a conversion stage — it did: `app/ingestion/normalize.py`
- [x] Normalize heading levels — `Tenor` is `##` in 273 documents and `####` in 114, so level
      is ignored entirely and only the label is used

**The trap that nearly shipped:** section markers are usually *not* Markdown headings. Only
`Tenor` is reliably `##` (387/389). The body sections arrive as bold, letter-spaced
paragraphs — `**T a t b e s t a n d:**` — exactly as in the source HTML. Parsing `#` headings
alone labelled **every chunk in the corpus `Tenor`**, which passed row-count checks and would
have made every citation point at the wrong part of the decision. After the fix:
Entscheidungsgründe 51%, Tatbestand 33%, Gründe 8%, Tenor 5%, Rechtsmittelbelehrung 2%.
- [x] ~~Extract `norm_refs`~~ — supplied by the dump as `{book, section}` pairs, e.g.
      `§§ 55a, 55d VwGO` → two entries. Labour books cited, in order: `zpo`, `bgb`, `betrvg`,
      `gg`, `arbgg`, `kschg`, `betravg`, `agg`, `inso`, `tvg`, `tzbfg`, `sgb ix`
- [ ] **Open decision, not blocking:** the `RefType.CASE` half of `reference_markers` is
      currently dropped in `download_dump.py`. It is a decision-cites-decision precedent
      graph we were not planning on having — "which later rulings cite this one" is a real
      feature, but it needs its own table and UI, so it belongs after retrieval works.
- [x] **Randnummern** — they *do* survive into `markdown_content`, as bare number lines
      (`<span class="absatzRechts">17</span>` becomes a line containing `17`). Captured into
      `document_chunks.paragraph_number` and stripped from the text, since a stray `17` would
      otherwise be embedded and indexed as content. **96% of chunks carry one.**
- [x] ~~Decode HTML entities~~ — nothing to do. Measured over 389 decisions: zero entity
      sequences, `html.unescape()` changes nothing, zero mojibake. The dump did it. What did
      need fixing was U+00A0, present in 71% of documents and otherwise a distinct character
      to both `to_tsvector` and the embedding tokenizer.
- [x] ~~Extract `norm_refs`~~ — supplied pre-parsed by the dump; ingestion just copies it.
      Top books in the ingested set: `bgb`, `zpo`, `arbgg`, `betrvg`, `kschg`, `tzbfg`.
- [x] **Strip personal identifiers at ingestion** — `app/ingestion/pii.py`. IBANs, emails,
      phone numbers, street addresses, and honorific-prefixed full names. Role words
      (`Kläger`, `Beklagte`) are deliberately kept: they appear in 91% of decisions, carry the
      legal meaning, and identify nobody. Citation metadata is likewise untouched — redacting
      an Aktenzeichen would break the product's whole point.
- [x] Set `license_note` to the § 5 UrhG public-domain provenance per document
- [x] `app/ingestion/chunking.py` — 350 tokens / 50 overlap, packed per section so no chunk
      straddles a section boundary; stores `chunk_index`, `section`, `paragraph_number`
- [x] `app/ingestion/embeddings.py` — local `sentence-transformers`, model loaded once behind
      a lock, batched, and it refuses to start if the model's dimension does not match the
      `vector(768)` column
- [x] Apply the e5 prefixes: `passage: ` when embedding chunks, `query: ` when embedding a
      search string — both live in `embeddings.py` and nothing else builds an input string
- [x] `ingest_to_db.py` — upserts `source_documents`, inserts `document_chunks`; idempotent
      (documents that already have chunks are skipped), commits per document so an
      interrupted run resumes
- [x] Unit tests: **35 passing** in `tests/test_ingestion.py` — section-marker forms including
      the letter-spaced bold variant, Randnummer capture and removal, chunks never spanning
      sections, overlap, oversized sentences, identifier stripping, and the negative cases
      (role words, statute references, and citation metadata must survive)

Verified live: 768-dim vectors normalized to 1.0, no nulls, German `tsvector` populated
(294 chunks matched `to_tsquery('german','Kündigung')` in the first 1,801). Ingestion of the
first ~1,070 documents (~27,000 chunks) runs at ~6.5 chunks/sec; re-run `ingest_to_db.py` with
a higher `--limit` to extend it, since it skips documents that already have chunks.

Two facts for whoever runs the full ingestion:

- **129 documents have no `markdown_content`** — the API-downloaded ones, which predate the
  dump. They are skipped rather than converted; the dump supersedes them.
- **Embedding is the entire cost: ~3.5 chunks/sec on CPU.** The remaining ~4,800 documents are
  roughly 123,000 chunks, so a full run is about **10 hours**. There is no GPU on this
  machine (`torch 2.13.0+cpu`).
- [x] Verify: query Supabase and confirm chunk count > 0; print one chunk and read it as
      correct German with intact umlauts — done, e.g.
      `Arbeitsgericht Aachen · 8 Ca 1327/16 d · 2016-09-08 · [Entscheidungsgründe]`
      → *"Die zulässige Klage ist im titulierten Umfang begründet, im Übrigen aber
      unbegründet."* Umlauts and ß intact; 96% of chunks carry a Randnummer.

---

## Phase 5 — Retrieval

Goal: a German question returns ranked, relevant passages.

- [x] ~~Supabase RPC `match_document_chunks_semantic`~~ → `app/retrieval/search.py`,
      direct SQL through SQLAlchemy. The RPC indirection exists so a *browser* can run a
      vector search through PostgREST, whose filter DSL cannot express
      `embedding <=> query_vector`. Nothing here runs in a browser — the backend owns
      retrieval — so an RPC would add a deployment artefact and a round trip for nothing.
      Trade-off recorded: these queries bypass RLS, which is correct for the corpus
      (§ 5 UrhG public domain, readable by any signed-in user) and would **not** be correct
      for anything user-scoped.
- [x] ~~Supabase RPC `match_document_chunks_fulltext`~~ → same module, `german` config
- [x] `app/retrieval/fusion.py` — Reciprocal Rank Fusion in Python, `k = 60`
- [x] `app/retrieval/retriever.py` — query → fused passages, capped at 2 passages per
      decision so one long on-topic judgment cannot fill the whole answer
- [x] Filterable retrieval by `court_jurisdiction`, `decision_year`, and `norm_refs`
      (JSONB containment, served by the GIN index)
- [x] Unit tests: **60 passing** — fusion ranking, tie determinism, language detection,
      glossary translation, tsquery construction
- [x] Verify: 10 realistic German questions all return on-topic passages with court,
      Aktenzeichen, date, section and Randnummer
- [x] Verify: the German FTS config is doing real work — `Kündigung`/`Kündigungen` and
      `gekündigt`/`kündigen` both hit the same chunks (stemming), and the decisive number:
      `Kündigungen` matches **988** chunks under the `german` config versus **149** under
      `english`. That 6.6× gap is the whole reason the config must be German.

**The bug the 10-question check caught.** The lexical leg was returning **zero rows for nine
of ten questions**, so RRF was silently degrading to semantic-only — the exact failure mode
the design contract warns about, arriving from an unexpected direction. Cause: `websearch_to_tsquery`
and `plainto_tsquery` both **AND** their terms, so *"Mein Arbeitgeber hat mir während der
Probezeit gekündigt"* required all eight words inside one 350-token chunk. Fix:
`tsquery_terms()` drops noise words and OR-joins the rest, letting `ts_rank_cd` rank by how
many terms a chunk matches. After the fix every question gets 40 results from both legs.
Nothing about the row counts looked wrong before — only the per-leg counts revealed it.

### Cross-lingual queries

The corpus is German; the question may be English. See [Architecture.md](Architecture.md) → "Bilingual behaviour".

- [x] `app/retrieval/query_language.py` — detect whether the query is German or English
- [x] Translate non-German queries to German **for the lexical leg only**; the semantic leg
      gets the original text, because e5 already aligns across languages
- [x] Return the German search string used in the response payload, so the UI can show what
      was actually searched (`RetrievalResult.lexical_query`)
- [~] Verify the same question in English and German returns substantially the same
      decisions. **Currently only 1–2 of 5 decisions overlap.** Both legs return results in
      both languages, so the lexical leg *is* contributing — this is ranking divergence, not
      the failure mode the checklist warns about. Re-check once ingestion finishes: the
      measurement was taken while the corpus was still growing (191 documents), and a small
      corpus makes ranking noisy. If it stays low on the full corpus, the glossary is the
      thing to improve.
- [x] Unit test: an English query produces a German lexical search string and an untranslated
      semantic input

A **glossary**, not an LLM call, translates the query — the design contract allows either. The lexical
leg consumes *terms*, not prose (`to_tsquery` stems whatever it is given), so fluent
translation buys nothing: it is free, deterministic, adds no latency, needs no API key, and
cannot invent a statute. Swapping in a model call later means replacing one function.

---

## Phase 6 — Agent & grounding

Goal: cited answers, and a hard refusal boundary.

- [x] `app/assistant/instructions.md` — the product contract as a **file**, not an inline
      string (the previous project inlined it and it rotted)
- [x] PydanticAI agent with typed deps and typed output:
      `GroundedAnswer{answer, answer_language, citations}`
- [x] Agent tools, bounded — no agent-generated SQL:
  - [x] `search_decisions(query, year_from?, year_to?)`
  - [x] `read_chunk(chunk_id)`
  - [x] `read_surrounding_chunks(chunk_id)`
  - [x] `lookup_statute(book, section)` — reports honestly that the statute corpus is a later
        phase rather than letting the model recite a provision from memory
- [x] `app/chat/orchestrator.py` — owns one turn end to end
- [x] `app/grounding/validator.py` — **the compliance control**:
  - [x] every citation must map to a passage retrieved this turn
  - [x] the model cannot cite a document not retrieved this turn
  - [x] answers with zero citations are rejected unless they are the "no comparable case"
        refusal
  - [x] **reject outcome predictions** — 10 pattern families across German and English; fails
        closed
- [x] Confirm the chat model handles German well — `gpt-5.6-terra` produced correct legal
      German prose with the terms of art intact (*Wartefrist*, *fristgerecht*,
      *Kündigungsschutzgesetz*); no drift into English, no mangled terms
- [x] Unit tests: **39 grounding tests** — prediction detection in both languages, the
      negative cases (describing a past decision must NOT trip it), citation integrity,
      invented quotes, translated quotes, person-queries, refusal detection
- [x] Verify: "Werde ich meinen Prozess gewinnen?" is refused

**The result that justifies the whole design.** Asked for its success chances, the model
*ignored its instructions* and wrote about `Erfolgsaussichten`. The validator caught it
(`prediction / de:chances`), the retry failed too, and the turn returned the refusal. The design contract
says "a prompt is not a compliance control" — this is that claim being demonstrated rather
than assumed.

**Two constraints discovered against the live API and worth keeping:**

1. **GPT-5.6 rejects function tools on `/v1/chat/completions`.** The error is explicit:
   *"To use function tools, use /v1/responses or set reasoning_effort to 'none'."* Since the
   agent is built on bounded tools, `app/assistant/agent.py` uses `OpenAIResponsesModel`
   rather than giving up reasoning to stay on the older endpoint.
2. **The answer cannot be streamed token by token.** The validator needs the complete text,
   and a prediction cannot be un-sent once read. `run_turn` generates and validates in full,
   then the endpoint streams the *validated* answer word by word — the UI is unchanged, the
   contract is intact.

### Answer language

- [x] `POST /chat/stream` accepts `answer_language`; falls back to the thread's setting
- [x] `GroundedAnswer` carries `answer_language`; instructions tell the agent to write prose
      in that language
- [x] **Citations stay German always** — the `data-citations` stream part carries court,
      `file_number`, ECLI, `section`, Randnummer and `norm_refs` verbatim, with dates in
      German format (`10.08.2023`), independent of answer language
- [x] **Quoted passages stay German always** — enforced, not requested: a translated quote
      fails `QUOTE_NOT_IN_SOURCE` because validation runs against the German source text
- [x] The grounding validator validates against the **German** source text regardless of
      answer language
- [~] Switching answer language reuses the retrieved evidence. **Half true, and the half that
      is missing matters.** Inside one turn this holds by construction: `run_turn` retrieves
      once, before the model is called, so prose language cannot change which passages exist.
      But there is **no way to switch the language of an answer that already exists** — today
      the UI would have to send a new message, which is a new turn, new retrieval, and
      therefore possibly different cases. Measured: the same question asked in German and in
      English shared only 2 of 3–4 cited decisions. That is not a bug in what is built; it is
      a missing endpoint. Closing it needs `POST /messages/{id}/language` that reuses the
      stored `message_citations` rows and only re-generates prose. Until then, do not tell a
      user the two versions cite the same cases.
- [x] Unit tests for the bilingual path — 4 added: an English answer over a German passage
      passes; an English *quote* of a German passage is rejected; predictions are caught
      identically in both languages; an unofficial translation alongside a verbatim German
      quote passes
- [x] Verify: end-to-end EN/DE run confirms citation metadata is never localized —
      `Arbeitsgericht Dortmund` stays `Arbeitsgericht Dortmund` in the English answer, and
      Aktenzeichen keep their German format (`1 Ca 751/23`)

**End-to-end through the HTTP API** (authenticated request → agent → validated answer →
persistence): 153 stream events, a `data-citations` part, and the stored assistant message
matching the streamed text exactly. Example answer: *"Eine vergleichbare Entscheidung stammt
vom Arbeitsgericht Dortmund, 1 Ca 751/23, 10.08.2023…"*

---

## Phase 7 — Statute corpus (optional, second pass)

Only after cases work end to end.

- [x] ~~Set `FETCH_LAWS = True` in `download_corpus.py`~~ → `download_laws.py`, from the dump.
      The API route is not viable: `/api/laws/` ignores every filter and caps `page_size` at
      50, so seven books means sweeping all 176,915 sections — ~3,540 requests against a quota
      worth ~150/day. The dump is one 147 MB file.
- [x] Budget the run — done, and the dump won on both counts (one request, no quota).
- [x] Ingest with `doc_kind = 'law'`, `section` = the § designator
- [x] Verify: from a decision's `norm_refs`, resolve and display the statute text it applies —
      `§ 1 KSchG` resolves to *"(1) Die Kündigung des Arbeitsverhältnisses gegenüber einem
      Arbeitnehmer, dessen …"*, and a real decision (`ArbG Aachen · 8 Ca 2034/16 d`) resolved
      `§ 46 ArbGG` from its own `norm_refs`.
- [ ] ~~Verify the version axis: fetch two `revision_date` values of one law book and diff
      them~~ — **not possible from this source.** The statute dump has no `revision_date` and
      no `latest` column, and carries exactly one row per (book, §) across all 113,537
      sections. the original plan's cross-version comparison assumed versioned law books; that has to
      come from `/api/law_books/`, which does expose `revision_date` and `latest`. The
      `revision_date` / `is_latest` columns are therefore populated as NULL rather than
      guessed. Decide later whether the feature is worth ~10k API requests.

**Statutes: 5,683 sections across 18 books extracted; the 12 core labour books (550 sections)
are ingested and the join is live.** BGB, ZPO, HGB, InsO, GG, SGB 9 and GewO are the bulk
(≈5,100 sections) and are ingesting in the background — the join simply resolves more §§ as
they land.

**A new column, `book_code`** (migration `0002`). A statute's identity is (book, §) —
`kschg` + `§ 1`. Overloading `court_name` with the book code would have worked and would also
have been a trap: `court_name` is rendered directly in citation chips, so a statute would
appear in the UI as if a court named "KSchG" had decided something.

**The silent failure this phase nearly shipped:** decisions and the statute dump spell book
codes differently. Decisions cite `efzg`; the dump files it as `entgfg`. Decisions cite
`sgb ix`; the dump has `sgb 9`. Unmapped, the Entgeltfortzahlungsgesetz — one of the most
cited statutes in sick-pay cases — resolves to nothing, with no error anywhere.
`app/retrieval/statutes.py` normalises both sides, and also strips `Abs.`/`Satz`/`Nr.` from a
citation so `§ 622 Abs. 3 Satz 1` finds `§ 622`.

---

## Phase 8 — Deployment ~~(Railway)~~ → **superseded by [Todos_Deployment.md](Todos_Deployment.md)**

Railway is no longer the plan: it retired its free tier, and the backend needs ~1.6 GB resident
for the embedding model, which does not fit any free platform tier. The deployment actually
built is a **Hetzner VPS** for the backend (Docker + nginx + Let's Encrypt) and a **Render
static site** for the frontend. That file supersedes this section and carries the full record,
including the hosts evaluated and rejected, and the three quantization attempts made before
accepting that the model needs a machine with real memory.

Still open, and tracked there rather than here:

- [ ] Structured logging (`structlog`) actually imported and used on failed turns —
      declaring the dependency is not the same as using it. More valuable now that real users
      can reach the service.
- [ ] Verify: end-to-end on the deployed URL with a real account

---

## Guardrails to re-check before anything public

- [x] No crawling of `rechtsprechung-im-internet.de` anywhere in the codebase — verified:
      the only mentions in the repo are the comments in `scripts/download_corpus.py` and the design notes
      explaining *why* it is off limits. No code fetches it.
- [x] No personal identifiers in any indexed or searchable column — queried live across
      24,477 chunks: 0 email addresses, 0 IBANs, 0 phone numbers, 0 street addresses.
- [x] Prediction refusal enforced in `grounding/validator.py`, with tests proving it —
      `test_predictions_are_detected` (13 phrasings, both languages),
      `test_validate_rejects_a_prediction_even_with_good_citations`, and the negative case
      `test_describing_past_decisions_is_allowed` so the rule cannot pass by rejecting
      everything. Demonstrated live: the model wrote about `Erfolgsaussichten` anyway and
      the validator refused the turn.
- [x] `license_note` populated on every document — 0 of 1,756 documents missing it; the
      single distinct value is the § 5 UrhG provenance string.
- [x] Downloader rate-limited with an identifying User-Agent —
      `USER_AGENT = "Judges Said corpus builder (bechir.labche@supcom.tn)"`,
      `REQUEST_DELAY_SECONDS = 0.34` (~3 req/s), and the script refuses to start on the
      placeholder address.
