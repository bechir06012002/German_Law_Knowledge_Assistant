# Deployment — minimum-cost checklist

Work top to bottom. Each phase unlocks the next. Read [Architecture.md](Architecture.md) first.

**Goal: the whole product live for about €7 a month.** Everything except the backend is free;
the backend is one small German VPS. Zero cost was the original constraint and it was very
nearly met — see "Why this is not free" below for what the last €7 buys.

Two measured numbers drive every decision below:

| Measured | Value | Limit | Verdict |
| --- | --- | --- | --- |
| Backend resident memory | **~1.6 GB** (model 1.08 GB + torch 0.46 GB + app) | free PaaS tiers: 512 MB | needs a host with real RAM — this is what rules out every free platform |
| Supabase database | **470 MB** (41,425 chunks, 6,750 docs) | Supabase free: 500 MB | **94 % full — must shrink** |

The chosen stack:

| Layer | Host | Cost | Why |
| --- | --- | --- | --- |
| Backend | **Hetzner Cloud CX23** — 2 vCPU x86, 4 GB RAM, 40 GB NVMe, Nuremberg or Falkenstein | **€5.99/mo net** (€5.49 server + €0.50 IPv4), **≈ €7.13 incl. 19 % German VAT** | 4 GB is 2.5× the measured 1.6 GB need, so the full fp32 model runs — no quantization, no cold start, no spin-down. Provisions in under a minute with no capacity roulette, and a German data centre is the right jurisdiction story for a German legal-data product. Cost of choosing it: a bare VM, so nginx, TLS, and process supervision become this checklist's job |
| Frontend | **Render Static Site** | free | Static sites are free on Render with TLS, a global CDN, SPA rewrites, and **no spin-down** — the 512 MB / 15-minute-idle limits that disqualified Render for the backend apply to *web services*, not static sites. Chosen over Cloudflare Pages (also confirmed sufficient) to keep one dashboard for the parts that are not the VM |
| Database + Auth | **Supabase free** | free | Already in use; the 500 MB cap is the constraint Phase 1 solves |

### Why this is not free

Oracle Cloud Always Free (Ampere A1, 2 OCPU / 12 GB) was the previous pick and is genuinely
free, with three times the RAM Hetzner sells at this price. It was traded away for
predictability, not for specs. Oracle halved that allowance in June 2026 with no announcement,
free-tier ARM capacity is famously unobtainable in popular regions, and nothing about a free
tier is owed to you. €7 a month buys a machine that provisions on demand, keeps the specs it
was sold with, and can still be reasoned about a year from now. Full comparison in the
rejected-alternatives table at the bottom.

---

## Phase 0 — Confirm before building ✅ complete

**Phase 0 paid for itself: it invalidated the chosen backend host before any Dockerfile
existed.** Recorded below as of **August 2026** — re-verify if this sits unused for long.

- [x] **Supabase free tier confirmed.** 500 MB database, 5 GB egress, 1 GB file storage,
      50,000 MAU — and free projects are **paused after 1 week of inactivity**. Confirms both
      the Phase 1 problem and the Phase 6 operational caveat.
- [x] **Cloudflare Pages free tier confirmed** and comfortably sufficient: 500 builds/month,
      20,000 files per site, 25 MiB max file size, 20-minute build timeout. The production
      bundle is ~500 KB across a handful of files. Kept as the documented fallback — the
      frontend host actually chosen is **Render Static Site** (see the stack table above).
- [x] **`pgvector` confirmed at 0.8.2** on Postgres 17.6, well above the 0.7.0 that `halfvec`
      needs. Both the `halfvec` type and the `halfvec_cosine_ops` operator class are present,
      so **Phase 1 Option A is available.** Current column is `vector` with an HNSW index on
      `vector_cosine_ops`.
- [x] ~~Pin torch to CPU wheels~~ — done. The lock file was pulling 15 NVIDIA CUDA packages
      (`sys_platform == 'linux'`), which would have added ~3 GB of unusable GPU libraries to
      the image. `[tool.uv.sources]` now points torch at `download.pytorch.org/whl/cpu`.
      Verified: 0 nvidia packages in `uv.lock`, 104 tests pass, embeddings still 768-dim and
      normalized.
- [x] **Hugging Face Spaces — ruled out.** The *hardware* is free as documented (CPU basic:
      2 vCPU, 16 GB RAM, 50 GB ephemeral disk, no hourly cost), but creating a Space that runs
      on compute is not: *"Gradio and Docker Spaces run on compute and require a paid plan to
      create: PRO for personal accounts."* Only **Static** Spaces are free for everyone, and a
      static Space cannot run FastAPI. **HF PRO is $9/month**, so this fails the zero-cost
      constraint. (The Docker SDK page does not repeat the restriction — the Spaces overview
      page is the authority.)

- [x] **Render free measured, and it does not fit.** Free instances are **512 MB RAM /
      0.1 CPU**, spin down after 15 minutes idle, and a workspace gets 750 instance-hours per
      month. Static sites are free — so the *frontend* is fine on Render. The backend is not.
      Measured locally, single-threaded:

      | Stage | Resident memory |
      | --- | --- |
      | Python interpreter only | 191 MB |
      | + app imports **+ torch** | **403 MB** |
      | + e5-base loaded | **1,077 MB** |

      Torch alone costs ~212 MB and the fp32 model ~674 MB. Even dropping torch entirely for
      ONNX int8, the floor is roughly: int8 e5-base **~278 MB** (its 250,002-token vocabulary
      makes the embedding matrix ~192 M of the ~278 M parameters, so int8 halves far less than
      hoped) + onnxruntime ~50 MB + app ~150 MB ≈ **480–530 MB against a hard 512 MB cap.**
      No headroom for actually serving a request.

- [x] **Latency on 0.1 CPU is survivable** — this was the other worry and it is not the
      problem. A warm query embedding takes **189 ms** pinned to one thread, so roughly **1–2 s**
      on a tenth of a core, and less with int8. Cold start adds ~8 s of model load on top of
      Render's ~1 min spin-up.

- [x] **ONNX int8 quantization tried and measured end to end — ruled out on quality, not just
      size.** Exported `multilingual-e5-base` to ONNX (torch's legacy exporter; `optimum`'s
      exporter fails on Windows cleaning up external-data files) and dynamically quantized to
      int8: **1,061 MB → 266 MB**, which would have made the 512 MB budget plausible. Verified
      the export first — a hand-written mean-pooling ONNX encoder matched
      `sentence-transformers`' own output at cosine 1.000000, so the harness itself is not the
      source of what follows.

      Two retrieval tests against the real database, using the 10/8 realistic German + English
      questions from the retrieval smoke test:

      | Setup | Mean top-5 overlap vs. the fp32 baseline | Top-1 unchanged |
      | --- | --- | --- |
      | int8 query vs. the **existing fp32** passage vectors (the cheap option — quantize serving only) | 3.70 / 5 | 7 / 10 |
      | int8 query vs. int8 passages, **both sides re-embedded** (the correct option) | 3.00 / 5 | 3 / 8 |

      Re-embedding consistently made it *worse*, not better, on a 400-chunk sample — so the
      degradation is quantization noise in the similarity ranking itself, not a mismatched
      embedding space that re-embedding would fix. **30–70 % of the cited case law would
      change under quantization**, on a product whose entire value is *which* cases it
      surfaces. That is not an acceptable trade for fitting a RAM ceiling.

      **Second attempt: per-channel quantization**, since the first pass used the coarser
      per-tensor setting. Tried per-channel `QInt8` and per-channel `QUInt8`, evaluated the
      cheap deployment path (int8 query encoder only, existing fp32 passages, full
      41,425-chunk corpus — directly comparable to the 3.70/5, 7/10 baseline above):

      | Quantization | Mean top-5 overlap | Top-1 unchanged |
      | --- | --- | --- |
      | per-tensor int8 (first attempt) | 3.70 / 5 | 7 / 10 |
      | per-channel int8 | 3.70 / 5 | 8 / 10 |
      | **per-channel uint8 (best found)** | **3.80 / 5** | **8 / 10** |

      A real but marginal recovery — one extra question gets its correct top match, one-fifth
      of the top-5 evidence still changes. Not enough to trust on a product whose product is
      *which* cases it shows someone.

      **Third attempt: static (calibrated) quantization** — a genuinely different technique,
      not a retuning of the first two. Dynamic quantization picks activation ranges per
      inference call; static quantization calibrates them once against real data first. Built
      a `CalibrationDataReader` over 200 real corpus chunks plus a handful of representative
      queries, ran `quantize_static` (QDQ format, per-channel weights, MinMax calibration).

      **Result: worse, not better — 0/5 overlap on every one of the 10 questions.** Checked
      first whether that meant a broken graph (NaN/Inf, or the model collapsing to one
      constant output regardless of input): it did not — output is finite, well-scaled, and
      two different questions still produce visibly different vectors (cosine 0.80 to each
      other). It is a legitimate but much noisier embedding: cosine to the real fp32 model is
      only **0.77**, against dynamic quantization's 0.98. This matches a known failure mode —
      MinMax calibration is highly sensitive to activation outliers in transformer attention
      layers, and 200 samples is not enough to average that out. Entropy or percentile
      calibration might do better, but that is a fourth attempt at the same technique family,
      not a new one.

      **ONNX int8 is closed for this deployment — three independent attempts, none viable:**

      | Attempt | Mean top-5 overlap | Verdict |
      | --- | --- | --- |
      | Dynamic, per-tensor | 3.70 / 5 | too much drift |
      | Dynamic, per-channel (best) | 3.80 / 5 | still too much drift |
      | Static, calibrated | 0.00 / 5 | worse — calibration noise dominates |

      Do not reopen this without a fundamentally different lever than the three tried here
      (e.g. quantization-aware fine-tuning, which retrains the model to be robust to
      quantization rather than quantizing a model that was never trained for it — a
      substantially bigger undertaking than anything attempted in this phase).

- [x] ~~**Backend host decided: Oracle Cloud Always Free (Ampere A1, ARM).**~~ **Superseded by
      the Hetzner decision below** — kept because the two findings it produced are still part of
      the reason Hetzner won, not throwaway detail. Two things were verified before committing:

      **1. The specs are smaller than commonly quoted, but still comfortable.** Oracle
      silently halved the Always Free Ampere A1 allowance from 4 OCPU / 24 GB to **2 OCPU /
      12 GB**, effective **June 15, 2026**, with no announcement — only the documentation
      changed. (Whether Pay-As-You-Go accounts still get 4/24 is disputed even among Oracle's
      own support agents; do not rely on that distinction.) **12 GB is still ~7× the backend's
      ~1.6 GB need**, so the plan survives the correction with room to spare. Also confirmed:
      200 GB boot volume, 10 TB/month outbound transfer, and the tier does not expire — unlike
      AWS/GCP free tiers that end after 12 months.

      **2. The CPU-only torch pin from earlier in this phase already works on ARM — verified,
      not assumed.** Ampere A1 is `aarch64`, and one source claimed the `download.pytorch.org
      /whl/cpu` index (what `pyproject.toml` now points torch at) has no `aarch64` builds.
      Checked the index directly instead of trusting that: it hosts
      `torch-2.13.0+cpu-cp312-cp312-manylinux_2_28_aarch64.whl` right alongside the x86_64
      build. Confirmed further with `uv pip compile --python-platform
      aarch64-unknown-linux-gnu`: resolves cleanly to `torch==2.13.0+cpu`, zero `nvidia-*`
      packages pulled in. **No pyproject.toml changes needed for the architecture switch.**

      **Known friction, not blockers, but real:**
      - A valid credit/debit card is required at signup for identity verification (a small
        temporary hold, not a charge) — unavoidable, Oracle's own requirement.
      - Ampere A1 free-tier capacity is well documented as tight in popular regions —
        "Out of host capacity" on provisioning is common enough to have a name. Budget for
        retrying, or trying a less popular region.
      - It is a **bare VM**, not a platform. Everything a PaaS would give you — TLS,
        reverse proxy, process supervision, log rotation — is now this checklist's job
        (Phase 2/3 below), not a vendor's.

- [x] **Vocabulary pruning tried — the technique works, but e5-base still cannot fit 512 MB.**
      A fundamentally different lever from quantization, and worth recording properly because
      the *technique* succeeded even though the goal failed.

      Measured across the whole corpus: the 41,425 chunks touch only **16,894 of the 250,002
      XLM-R tokens (6.8 %)**; the top 10,000 cover 99.7 % of all occurrences. The other 93.2 %
      of the embedding matrix is vocabulary for languages this product never sees. Pruned to
      49,938 tokens (every corpus token, plus the most frequent 40,000 overall so ordinary
      German and English words a user might type still resolve), the model drops from 278 M to
      **124 M parameters**.

      Crucially, and unlike quantization, **pruning is lossless for retained tokens** — it
      deletes unused rows rather than perturbing surviving weights, so the fp32 passage vectors
      already in the database stay valid. Confirmed against the real database:

      | Result | Value |
      | --- | --- |
      | Queries scoring cosine **1.0000** vs. fp32, 5/5 overlap, same top-1 | **9 of 10** |
      | Mean top-5 overlap | 4.50 / 5 (int8's best was 3.80) |
      | The one failure | an English query hitting 2 out-of-vocabulary tokens — fixable by keeping more vocabulary, not a flaw in the method |

      **Why it still fails: fp16 saves disk, not memory.** The pruned fp16 model is 236 MB on
      disk but consumed **607 MB resident** — 97 MB over the cap. onnxruntime's CPU provider
      has no fp16 kernels, so it upcasts every weight to fp32 at session load. (Also worth
      recording: torch's exporter emits a *type-inconsistent* fp16 graph — LayerNorm stays
      fp32 — which onnxruntime rejects outright. The supported route is exporting fp32 and
      converting with `onnxconverter-common`.)

      That forces the real arithmetic. On onnxruntime CPU, weights are fp32 regardless:

      ```text
      12-layer transformer, 768 hidden   85.0M params = 324 MB
      vocabulary, even pruned to zero     0.0M params =   0 MB
      onnxruntime + tokenizers                          49 MB   (measured)
      FastAPI + SQLAlchemy + supabase + …              130 MB   (estimated)
      ------------------------------------------------------
      ABSOLUTE FLOOR                                   503 MB   vs a 512 MB cap
      ```

      **e5-base cannot fit 512 MB even with an empty vocabulary.** Its architecture is the
      binding constraint, not its vocabulary and not its precision. No amount of further
      pruning or precision work changes this — the only remaining lever is a smaller
      architecture, which means a different model and a re-embedded corpus.

- [x] **Backend host changed to Hetzner Cloud, superseding the Oracle decision above.** Priced
      against Hetzner's *current* list rather than the numbers most guides still quote — Hetzner
      raised shared-vCPU prices by roughly 30 % on **June 15, 2026** and renumbered the plan
      line, so anything written before that date is wrong:

      | Plan | Arch | vCPU | RAM | Disk | Traffic | Price/mo (net) |
      | --- | --- | --- | --- | --- | --- | --- |
      | **CX23** ← chosen | x86 | 2 | 4 GB | 40 GB | 20 TB | **€5.49** |
      | CX33 | x86 | 4 | 8 GB | 80 GB | 20 TB | €8.49 |
      | CAX11 | ARM | 2 | 4 GB | 40 GB | 20 TB | €5.99 |

      On top of that: **€0.50/month for the primary IPv4 address.** IPv6 is included free, and
      dropping IPv4 saves that €0.50 — but it makes the API unreachable for IPv4-only clients,
      so it is not an option here. German VAT of 19 % applies for a private customer in Germany.
      **Realistic total ≈ €7.13/month gross.**

      **Verified against Hetzner's live plan pages (August 2026):** `CX23` and `CAX11` are real
      current plan names with exactly the specs above — 2 vCPU / 4 GB / 40 GB, x86 and Ampere
      ARM respectively. **Treat the euro figures as approximate and re-check at signup.**
      Hetzner's own pages render prices in JavaScript so they could not be read directly, and
      third-party trackers disagree: some still list €3.99 (CX23) / €4.49 (CAX11) from the
      April repricing, others the €5.49 / €5.99 above from the June one. Hetzner took **four
      separate pricing actions during 2026** (February setup fees, a portfolio-wide ~30–37 %
      rise on April 1, and further adjustments in June), which is why no figure written down
      here should be trusted for long. What *is* consistent across every source, and is the
      part the decision rests on: **CX23 is €0.50/month cheaper than CAX11 in both pricing
      snapshots**, so the x86-is-cheaper-than-ARM inversion below is real and not a
      transcription error.

      **x86 CX23 over ARM CAX11** for two reasons that point the same way: it is €0.50 *cheaper*
      (unusual — ARM is normally the budget option, and after the June repricing it no longer
      is), and it matches this development machine's architecture, so an image that builds and
      runs locally behaves identically on the server. That retires the aarch64 torch-wheel
      verification recorded above — keep the finding only in case ARM is ever revisited.

      **4 GB against a measured 1.6 GB** leaves room for nginx, Docker, the OS, and the image
      build itself. It is far less headroom than Oracle's 12 GB, and still roughly double what
      the service actually needs.

- [ ] Decide the database strategy (Phase 1): `halfvec` conversion, corpus trim, or both.

### Rejected backend hosts, for the record

| Option | Free? | Why not chosen |
| --- | --- | --- |
| Hugging Face Spaces | Hardware free, but creating a compute Space needs PRO ($9/mo) | Fails zero-cost |
| Render Standard | 2 GB, fits, **~$25/mo confirmed live** | Not free |
| Google Cloud Run | Free within an always-free allowance | Not pursued — a card-gated scale-to-zero service with cold starts is a worse fit than an always-on VM, free or otherwise |
| ONNX int8 on Render free | Free, no card | Closed on quality grounds — see the three quantization attempts above |

---

## Phase 1 — Get the database under 500 MB

> **Recommended: skip this phase for a short-lived deployment, and do not treat it as done.**
>
> The `halfvec` conversion below is **lossy and effectively irreversible**: float32 → float16
> discards precision that a down-migration cannot restore, so undoing it really means
> re-embedding all 41,425 chunks (hours of CPU). The 30 MB of remaining headroom exists to
> absorb *chat history growth* — threads, messages, citations — which runs to thousands of
> messages at a few KB each. A demo measured in days will not come close.
>
> Do this phase when the deployment becomes long-lived, or when the database actually
> approaches the cap. Degrading every stored vector to solve a problem that has not arrived is
> the wrong trade, especially on a product whose value is *which* cases it retrieves.

Where the 470 MB actually is:

```text
document_chunks + indexes   438 MB
  ├─ HNSW embedding index   158 MB
  ├─ TOAST (text + vectors) ~190 MB
  ├─ heap                    69 MB
  └─ tsvector GIN index      16 MB
source_documents + indexes   20 MB
```

The embedding vectors and their HNSW index are ~285 MB of the 470 — that is the only place with
real room. Only ~30 MB is free today, and threads, messages, and citations grow into it as
people use the app, so this is a wall the product will hit, not a theoretical risk.

**Option A — `halfvec` conversion (preferred).** pgvector's `halfvec` stores each dimension as
float16 instead of float32, halving both the column and the index.

- [ ] Alembic migration: `vector(768)` → `halfvec(768)`, and rebuild the HNSW index with
      `halfvec_cosine_ops`
- [ ] Update `EMBEDDING_DIMENSIONS`'s neighbours in
      [constants.py](../backend/app/database/models/constants.py) and the column type in the
      chunk model — the dimension does **not** change, only the storage type
- [ ] Check every place that writes or reads the vector still round-trips (`pgvector` Python
      binding needs `HALFVEC` rather than `VECTOR`)
- [ ] Verify the size drop — expect roughly 470 MB → **~330 MB**
- [ ] Verify retrieval quality is unchanged: re-run the 10-question German check and confirm
      the same decisions come back in substantially the same order. float16 costs ~3 decimal
      digits of precision on a cosine comparison, which should be invisible at top-5, but it
      must be checked rather than assumed.

**Option B — trim the corpus.** Simpler, no migration, but loses coverage.

- [ ] Decide what to drop. Statute sections (5,680 docs / 7,844 chunks) are cheap per document;
      the 1,070 decisions are the product. Dropping decisions weakens the core promise of three
      to five analogous rulings, so trim laws first.
- [ ] Delete and `VACUUM FULL` — a plain `DELETE` does not return space to the free-tier quota.

**Either way**

- [ ] Confirm final size with headroom for user data, and note the number here
- [ ] Set a reminder to re-check size after real use — chat history grows unbounded

---

## Phase 2 — Provision the Hetzner server

- [x] Hetzner account created.
- [x] **SSH keypair generated** at `~/.ssh/id_ed25519` (ed25519, no passphrase) and the public
      half added in the create dialog. Worth recording the trap hit here: generating it from
      PowerShell with `-N '""'` sets a passphrase of two literal quote characters rather than an
      empty one, and the key then refuses to open. It was regenerated from bash with `-N ""`
      and **verified** with `ssh-keygen -y -f … -P ""` before being used.
- [x] Server created — 2 vCPU / **4 GB RAM**, Ubuntu 24.04, German location, backups off.
      4 GB was chosen against a measured ~1.6 GB need: a 2 GB box leaves nothing for the OS,
      the Docker daemon, or the torch install's build-time spike, and the failure mode is an
      OOM kill mid-question rather than an honest error.
- [x] **Billing understood: charged hourly, invoiced in arrears.** Hetzner's billing FAQ states
      invoices are created per full calendar month, up to 28 days after that month ends — so a
      few days' use in August is billed in early September, not upfront. **~€3 for three days**
      against a ~€23/month cap. The rule that actually matters is below: a *powered-off* server
      still bills, only deleting it stops the charge.
- [x] **Firewall active** (`ufw`, host-level rather than the Hetzner Cloud Firewall): default
      deny inbound, allowing **22, 80, 443** only, IPv4 and IPv6. Rule 22 was added *before*
      enabling, since enabling a default-deny firewall over SSH with no SSH rule locks you out.
- [x] **SSH hardened, key-only.** `sshd -T` confirms `passwordauthentication no`,
      `permitrootlogin without-password`, `pubkeyauthentication yes`. Note for Ubuntu 24.04: it
      ships cloud-init drop-ins under `/etc/ssh/sshd_config.d/` that can re-enable password auth
      and silently override the main config, so those are patched too. Key access was
      re-verified on a fresh connection immediately after the reload.
- [x] `apt upgrade` run; **Docker Engine 29.7.2 + Compose v5.5.0** installed from Docker's own
      apt repository, plus nginx 1.24.0.
- [x] `unattended-upgrades` enabled.
- [x] **2 GB swap added** and persisted in `/etc/fstab`.

**Actual server, as provisioned:** 2 vCPU AMD EPYC-Genoa, **3.7 GB RAM, 75 GB disk** — this is
the CPX22 (Regular Performance) tier, not the CX23 planned above, because Cost-Optimized was not
offered. The extra disk is welcome: the built image is **5.69 GB**, more than double the ~2.5 GB
estimate, which would have been uncomfortable on CX23's 40 GB after a few rebuilds.
- [x] **Domain: `judges-said.duckdns.org` → 46.225.237.78** (DuckDNS, free). Verified it both
      resolves and actually reaches this server before requesting a certificate — a
      Let's Encrypt HTTP-01 challenge against a domain pointing somewhere else fails in a
      confusing way, and the failed attempts count against rate limits.
      *Security note:* the DuckDNS token controls where the domain points and was exposed in a
      screenshot during setup — it should be recreated from the DuckDNS page.
- [ ] **Understand the billing before leaving it running.** Hetzner bills hourly, capped at the
      monthly price, and a **powered-off server keeps billing** — only *deleting* it stops the
      charge. The same rule is what makes experiments cheap: a server run for one afternoon costs
      a few cents.

---

## Phase 3 — Deploy the backend on the VM

**The files for this phase are written and in the repo.** What remains is running them on a
server that does not exist yet.

- [x] **`backend/Dockerfile`** — `python:3.12-slim`, uv pinned to 0.12.1, dependency layer
      before application code so a code change does not reinstall torch. The server is x86_64
      like this development machine, so there is no architecture question to answer at all.
      Runs as a non-root user, and **one uvicorn worker on purpose**: each worker loads its own
      ~1.1 GB copy of the model, so a second would not fit in 4 GB. Concurrency here is
      I/O-bound (OpenAI, Postgres), which a single event loop handles.
- [x] **Model baked into the image** via `ARG EMBEDDING_MODEL`, so a container start never
      waits on a 1.08 GB download. It deliberately does not import `app.config` — `Settings`
      requires runtime secrets that do not exist during a build. Keep the ARG default in step
      with `embedding_model` in [config.py](../backend/app/config.py).
- [x] `HF_HOME=/opt/hf` set inside the image so the baked cache is found at runtime
- [x] **`backend/.dockerignore`** — excludes `.venv`, `.env`, `__pycache__`, `.pytest_cache`,
      `tests/`, run logs, and `data/`. The corpus payload must never enter the image.
- [x] **`backend/compose.yaml`** — `restart: unless-stopped` so it survives a reboot,
      `mem_limit: 3g` as a backstop so a leak cannot take sshd down with it, and log rotation
      (`max-size: 10m`) so the JSON log cannot fill the 40 GB disk.
      **The port is published to `127.0.0.1:8000`, not `0.0.0.0`** — this matters more than it
      looks: Docker writes its own iptables rules that bypass the Hetzner Cloud Firewall
      entirely, so a `0.0.0.0` publish would expose the API on port 8000 with no TLS, no
      matter what the firewall says.
- [x] **`deploy/deploy.sh`** — pull, rebuild, restart, prune, wait for health. Refuses to run
      if `backend/.env` is missing, and prunes dangling layers every time because the image is
      ~2.5 GB against a 40 GB disk.
- [x] **`deploy/nginx.conf`** — reverse proxy with a **separate `location /chat/stream` block
      that turns `proxy_buffering` off.** Without it nginx buffers the whole SSE response and
      releases it at the end: the UI shows nothing for the entire turn and then everything at
      once, which is indistinguishable from a hang. Timeouts are raised to 300 s because a turn
      is retrieval plus an LLM call plus validation plus a possible regeneration. CORS is left
      to the application — setting it in both places produces duplicate headers, which browsers
      reject.
- [x] Repo cloned to `/opt/judges-said` and the image **built on the server** — 5.69 GB, and
      the 2 vCPU box handled it without trouble.
- [x] The 8 values are in `/opt/judges-said/backend/.env`, `chmod 600`, root-owned, copied over
      SSH rather than through git. Confirmed still matched by `.gitignore` on the server.
- [x] **Container running and healthy**, published to **`127.0.0.1:8000`** — verified from
      outside that `http://<ip>:8000/health` is refused, so the API is not reachable except
      through nginx.
- [x] **Model verified loading inside the container** — the check that `/health` cannot make.
      `embed_query` returns a 768-dimension unit vector, loaded from the baked cache with no
      download, in ~12 s cold. Container sat at **885 MB of its 3 GB limit**, host at 1.0 GB of
      3.7 GB, so there is real headroom rather than a near-miss.
- [x] **IPv6 enabled for Docker — required, and the single hardest failure to diagnose here.**
      Supabase's direct connection (`db.<ref>.supabase.co:5432`) resolves to an **IPv6-only**
      address. The Hetzner host had working IPv6, but Docker did not, so every database query
      failed with `Network is unreachable` while **`/health` continued returning 200** — that
      endpoint never touches the database. The user-visible symptom was an unrelated-looking
      *"Could not load your searches."* in the sidebar, which initially pointed at CORS.

      Two changes are needed, and the first alone does nothing:

      1. `/etc/docker/daemon.json` — `{"ipv6": true, "fixed-cidr-v6": "fd00:dead:beef::/48",
         "ip6tables": true}`, then restart Docker. **Server-side only; not in git.**
      2. `enable_ipv6: true` on the Compose network in `backend/compose.yaml`. The daemon
         setting covers the *default* bridge; Compose creates its own network, which defaults
         to IPv6 off regardless.

      Two traps if this is ever redone: `fixed-cidr-v6` must be valid hex (a prefix containing
      `k` was rejected and left dockerd crash-looping), and after a few failed starts systemd
      rate-limits the unit — `systemctl reset-failed docker.service` before retrying, or the
      next attempt fails for a reason unrelated to the config.

      Verified from inside the container afterwards: TCP to Supabase:5432 succeeds, the corpus
      is reachable (6,750 documents / 41,425 chunks), and a real German query returns 12 fused
      passages with both legs contributing 40 candidates each.

- [ ] Consider setting `HF_HUB_OFFLINE=1` in the container. Startup currently still contacts
      the HuggingFace Hub (it logs an unauthenticated-request warning) even though the weights
      come from the baked cache — which makes container start depend on an external service it
      does not actually need.
- [ ] Set `ALLOWED_ORIGINS` to the real Render URL — still `["http://localhost:5173"]`, so the
      deployed frontend will be blocked by CORS until this changes (Phase 5).
- [x] **nginx installed and configured** from `deploy/nginx.conf` with the real hostname
      substituted, default site removed. One gotcha worth recording: a request issued
      immediately after `systemctl reload nginx` returned 404 because the reload had not
      completed — retrying gave 200. Do not debug a config that is merely mid-reload.
- [x] **TLS issued via certbot** (`--redirect`), and `certbot.timer` active. `certbot renew
      --dry-run` **passed**, which is what actually proves renewal works rather than assuming
      the timer implies it.
- [x] **Verified certbot did not clobber the SSE configuration.** certbot rewrites the nginx
      file in place to insert TLS, so the hand-written `location /chat/stream` block with
      `proxy_buffering off` had to be re-checked afterwards — it survived intact. Had it been
      dropped, streaming would have broken in a way that looks like the model hanging.
- [x] **Verified from outside the server:** `https://judges-said.duckdns.org/health` returns
      200 with a valid chain, `http://` 301-redirects to `https://`, and `/threads` returns 401
      without a token — so auth is enforced in the deployed configuration, not just locally.
- [ ] **Verify a real question end to end** — confirms the model loaded inside the container.
      Never trust a green health check alone: the model loads lazily on first search
      ([embeddings.py:30](../backend/app/ingestion/embeddings.py#L30)), so `/health` returns
      200 long before the model has ever been exercised.
- [ ] Note the first-query latency — the ~8 s model load measured in Phase 0, plus whatever a
      *shared* vCPU adds under contention (CX is a shared-core plan; a dedicated CCX costs
      several times more and is not worth it here) — so the frontend's loading state can be
      honest about it

**Nothing here sleeps.** Unlike every free platform in the rejected list, a paid VPS runs
continuously — no spin-down, no cold start after idle, and the ~8 s model load happens once per
deploy rather than once per visitor. That is the single biggest thing the €7 buys.

---

## Phase 4 — Deploy the frontend

- [x] **`render.yaml` written at the repo root** as a Render Blueprint, so the static site,
      build command, SPA rewrite, and security headers are all version-controlled rather than
      clicked into a dashboard. It declares the **frontend only** — with a comment saying why
      the backend is absent, so nobody later reads it as an oversight.
- [x] **`packageManager: "pnpm@11.20.0"` added to `frontend/package.json`.** Without it
      `corepack enable` on Render resolves some default pnpm, which may not match
      `lockfileVersion: 9.0`. Verified locally: `pnpm install --frozen-lockfile` then
      `pnpm build` both succeed.
- [ ] Create the service on Render as a **Static Site — not a Web Service.** A Web Service is
      the 512 MB, spin-down tier Phase 0 ruled out; static sites are free, always-on, and
      served from a CDN. Either point Render at `render.yaml` as a Blueprint, or set root
      directory `frontend/`, build **`pnpm install --frozen-lockfile && pnpm build`**, publish
      `./dist` by hand.

      **Do not prefix the build with `corepack enable`.** It fails on Render with
      `EROFS: read-only file system, unlink '/usr/bin/pnpm'` — the build image does not allow
      writes to `/usr/bin`. It is also redundant: Render's image already ships pnpm 11.20.0,
      which is exactly what `packageManager` in `package.json` pins, so the lockfile resolves
      identically without it.
- [ ] Set the three build-time variables: `VITE_API_BASE_URL` (the Hetzner host, `https://…`),
      `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. **Vite inlines these at build time** — they
      must exist *before* the build runs, and changing one later needs a redeploy, not a
      restart. Anon key only; the service-role key must never reach a browser.
- [ ] Confirm the SPA rewrite took effect (`/*` → `/index.html`, action **Rewrite**, not
      Redirect) by loading a deep link directly rather than by navigating to it — that is the
      case that 404s without it.
- [ ] Verify the built bundle calls the server's domain and not `localhost`

---

## Phase 5 — Wire the two together

- [x] **`ALLOWED_ORIGINS` set** to `["https://judges-said.onrender.com","http://localhost:5173"]`
      in the server's `.env`, container recreated — CORS is read once at startup
      ([main.py:18](../backend/app/main.py#L18)), so editing the file alone does nothing.
      localhost was kept so local development can still reach the deployed backend.
      **Verified with a real preflight** rather than by reading config: `OPTIONS /threads` with
      `Origin: https://judges-said.onrender.com` returns a matching
      `access-control-allow-origin`, and an unrecognised origin is refused.
- [x] **Frontend build verified to carry the right backend URL.** Vite inlines `VITE_*` at build
      time, so the only proof is in the shipped bundle: grepping the deployed
      `/assets/index-*.js` finds `https://judges-said.duckdns.org` and the Supabase project URL,
      confirming the variables were present *before* the build rather than added afterwards.
- [x] Frontend URL added to Supabase Auth → URL Configuration (site URL + redirect allow list),
      with `/**` on the redirect entry. The wildcard matters because auth can return the user to
      `/chat/:threadId`; a single `*` matches one path segment only and would break thread links.

- [x] **SPA rewrite fixed by deploying as a Blueprint** rather than a hand-made static site.
      `/`, `/login`, `/chat`, and `/chat/<id>` all return 200. Adding the rule through the
      dashboard form repeatedly failed to take effect — the fix that worked was letting Render
      read it from `render.yaml`, which is the argument for keeping deploy config in the repo
      rather than in a dashboard.

      **The live URL is `https://judges-said-l49g.onrender.com`, not
      `judges-said.onrender.com`.** Render appends a random suffix when the preferred name is
      already taken, and it was still held by the hand-made service at the moment the Blueprint
      was created. Deleting the old service afterwards does **not** hand the name back.

      This produced a failure worth remembering because it looks nothing like its cause: the
      site loaded fine and the user was signed in, but every request failed with *"Could not
      load your searches."* — the backend's `ALLOWED_ORIGINS` still named the old URL, so CORS
      rejected an origin that was only a few characters different. **Whenever the frontend URL
      changes, `ALLOWED_ORIGINS` and the Supabase Auth redirect list must both change with it.**
- [x] Signed in on the live site and the thread list loads — the deployment is working end to
      end, frontend through nginx and TLS to the container, out to Supabase over IPv6.

Still worth doing deliberately rather than assuming, since these exercise paths a smoke test
does not:

- [ ] Ask in English and switch answer language on an existing answer — confirms the
      re-language path reuses stored citations instead of re-running retrieval, so both
      language versions cite the same decisions.
- [ ] Ask something the corpus cannot answer and confirm the refusal, rather than an invented
      citation.
- [ ] **Confirm the RDG guardrail survived deployment** — ask for success chances
      (*"wie hoch sind meine Erfolgsaussichten?"*) and check the refusal comes back. This is
      the compliance control; a prompt-only version of it would be worth nothing, so it is
      worth seeing fire in production at least once.
- [ ] Re-enable Supabase email confirmation if it was switched off for local development.

---

## Phase 6 — Operational reality

These are not bugs; they are what a free database and a self-managed server cost. Document them
so the behaviour is not mistaken for breakage.

- [ ] **Supabase pauses a free project after ~7 days of inactivity.** A paused project must be
      resumed from the dashboard. For anything demo-facing, plan to open it beforehand. The
      backend has no equivalent problem — the Hetzner server runs continuously, so Supabase is
      the one remaining cold-start risk in the whole stack.
- [x] Noted in the README so a visitor who hits a slow first load understands why.
- [x] **Survives a reboot — verified rather than assumed:** container restart policy is
      `unless-stopped`, and both `docker` and `nginx` are `enabled` in systemd.
- [x] **Certificate renewal proven**, not just scheduled: `certbot.timer` is active *and*
      `certbot renew --dry-run` succeeds. Current certificate is valid 89 days.
- [x] `unattended-upgrades` enabled for OS security patches.
- [x] **Disk checked: 14 GB of 75 GB used (19 %).** Comfortable, and much more room than the
      CX23's 40 GB would have left — the image alone is 5.69 GB with a further ~5.8 GB of build
      cache. `deploy.sh` prunes dangling layers on every deploy; `docker system df` is the
      command to watch it with.
- [ ] **The bill is now a failure mode.** An expired card or a bounced SEPA debit takes the site
      down as surely as a crash. Keep the payment method current and read the mail Hetzner sends
      about it.
- [ ] Decide on a minimal uptime check (even a free one like UptimeRobot hitting `/health`) so
      an outage is noticed before a user reports it.
- [ ] **Recreate the DuckDNS token.** It was exposed in a screenshot during setup, and it is
      what authorises repointing the domain at another IP.

### Shutting the deployment down

This was provisioned for a short demo, so the exit matters as much as the setup:

- [ ] **Delete the Hetzner server — do not merely power it off.** A stopped server still bills;
      only deleting stops the charge. Billing is hourly against a ~€23/month cap, so a few days
      is roughly €3, invoiced the following month rather than upfront.
- [ ] Take a **snapshot first** if the machine should be restorable later — a few cents per
      month, and it saves redoing Phases 2 and 3.
- [ ] The Render static site and Supabase project are free and can simply be left, though a
      free Supabase project pauses after about a week idle.
- [ ] If the site is being shown to anyone afterwards, remove the live URL from the README so
      the link does not rot in a portfolio.

---

## Phase 7 — Documentation

- [x] README hosting row corrected — was Railway, now Hetzner (backend) + Render (frontend).
- [x] Live URL recorded in the README, with a note that the free database sleeps after a week
      idle, so a slow first load reads as expected behaviour rather than a bug.
- [x] Phase 8 of [Todos_Backend.md](Todos_Backend.md) marked superseded by this file.
- [ ] Update the hosting row in the local agent-context file for the same reason (that file is
      deliberately untracked, so this is a local-only edit and must not add a link to it from
      any tracked document)
- [ ] Structured logging on failed turns — still open from the backend checklist, and much more
      valuable once real users can hit it

---

## Rejected alternatives

Recorded so they are not revisited.

| Option | Why not |
| --- | --- |
| HF Spaces (Docker) | Hardware is free, but creating a compute Space needs PRO — $9/mo. Only Static Spaces are free, and those cannot run FastAPI |
| Railway | No free tier; ~$15–20/mo for a 1.6 GB always-on service |
| Render (backend) | Free and Starter are both 512 MB — the model cannot load. Standard is 2 GB at **$25/mo confirmed live** |
| Oracle Cloud Always Free (Ampere A1) | Genuinely free with 12 GB of RAM, and it was the chosen host for a while. Rejected on predictability, not specs: Oracle silently halved the allowance from 4 OCPU/24 GB to 2/12 in June 2026, free-tier ARM capacity is routinely unobtainable in popular regions, and a free tier owes you nothing. €7/month removes all three risks |
| Google Cloud Run | Genuinely free within its allowance, but card-gated and scale-to-zero — a 1.6 GB model means a multi-second cold start on the first request after idle, which is the worst possible first impression for a demo |
| Self-hosted Postgres on the same VPS | Would make Phase 1's 500 MB squeeze disappear, but Supabase provides Auth as well as the database, and both are part of the locked stack. Not worth unpicking auth to save a migration |
| Vercel / Netlify functions | Deployment bundle caps well under torch's size |
| Koyeb / Fly.io free | 512 MB or no meaningful free allowance |
| Smaller embedding model | `paraphrase-multilingual-MiniLM-L12-v2` fits 512 MB but needs a 384-dim migration, re-embedding all 41,425 chunks, and costs the cross-lingual quality that makes English questions work at all |
| ONNX int8 quantization | Fits any small RAM budget (266 MB), but three independent attempts (dynamic per-tensor, dynamic per-channel, static calibrated) all changed 20–100 % of which cases get cited — closed on quality grounds, not size. Full detail in Phase 0 above. |
| External embedding API | Forbidden by design, and mixing providers between indexed passages and queries breaks the shared vector space |
