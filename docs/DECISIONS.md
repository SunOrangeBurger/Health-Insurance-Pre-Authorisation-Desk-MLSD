# Architecture & Design Decisions

This document logs every significant technical decision made throughout the project, following the ADR (Architecture Decision Record) format. Each entry records the context, the decision, alternatives considered, and the rationale.

---

## ADR-001: Multi-Agent Reasoning Layer with LangGraph
- **Status:** Accepted
- **Date:** 2026-10-29 (Phase 0)
- **Context:** Need explicit, bounded control over agent execution loops — step counts, tool-call limits, wall-clock timeouts — and a typed, persisted hand-off object between the Policy Research Agent and the Verifier/Router Agent.
- **Decision:** Use **LangGraph** with typed state (`EvidenceBundle`, `VerificationResult`) and explicit graph edges. Loop limits enforced at the graph level, not inside agent logic.
- **Rejected Alternatives:**
  - **CrewAI** — rejected: less granular control over explicit state passing, loop termination, and per-step checkpointing. Crew's task abstraction obscures the hand-off contract.
  - **Custom asyncio loop functions** — rejected: LangGraph provides native graph checkpointing and crash-recovery for free; reimplementing this is risky and time-consuming.

---

## ADR-002: Async Job Queue via Redis + arq
- **Status:** Accepted
- **Date:** 2026-10-29 (Phase 0)
- **Context:** The API (`POST /v1/preauth`) must return an immediate `202 + run_id` and not block on multi-agent reasoning (which can take up to 90 seconds). Worker must consume jobs asynchronously.
- **Decision:** Use **Redis + arq** (async-native Python job queue). arq is small, fully compatible with Python `asyncio`, and ships with job result storage backed by Redis.
- **Rejected Alternatives:**
  - **Celery** — rejected: heavier setup (requires a result backend separate from the broker), historically awkward with `asyncio`, and adds operational overhead. arq is the simpler choice per the project's "prefer boring, well-documented libraries" rule.
  - **RQ (Redis Queue)** — evaluated: simpler than Celery but not async-native; arq preferred.

---

## ADR-003: Vector Index with FAISS + Local MiniLM Embeddings
- **Status:** Accepted
- **Date:** 2026-10-29 (Phase 0)
- **Context:** Retrieval must run entirely locally (Project Rule 10: no paid embedding APIs). Need incremental re-embedding by chunk hash without full index rebuild.
- **Decision:** `sentence-transformers/all-MiniLM-L6-v2` (local, CPU) for dense embeddings; **FAISS** (`IndexIDMap2` + `IndexFlatIP`) for the vector index; BM25 (`rank_bm25`) for sparse retrieval; reciprocal-rank fusion for hybrid search.
- **Rejected Alternatives:**
  - **Paid embedding APIs** (OpenAI `text-embedding-3`, Cohere `embed`) — rejected per Project Rule 10.
  - **nomic-embed-text via Ollama** — available locally but adds Ollama as a hard dependency at ingest time; `sentence-transformers` runs as a Python library with no separate server process. Using `nomic-embed-text` as a fallback is acceptable but not the primary path.
  - **Chroma** — acceptable per spec, but FAISS gives simpler incremental control by ID with `IndexIDMap.remove_ids + add`. Chroma is the noted alternative.
  - **Milvus / Weaviate** — over-engineered for a single-policy, single-insurer corpus volume.

---

## ADR-004: Persistent State Storage with PostgreSQL
- **Status:** Accepted
- **Date:** 2026-10-29 (Phase 0)
- **Context:** Need concurrent-write-safe storage for runs, step telemetry, quarantine records, feedback, and cost tracking, accessed by multiple worker container replicas and the API service simultaneously.
- **Decision:** **PostgreSQL 16** with `asyncpg` driver and SQLAlchemy async ORM.
- **Rejected Alternatives:**
  - **SQLite** — rejected: file-level write locking breaks concurrent workers. Not suitable for `--scale worker=3`.

---

## ADR-005: Insurer / Corpus Selection — HDFC ERGO my: Optima Secure
- **Status:** Accepted
- **Date:** 2026-10-29 (Phase 0)
- **Context:** Must choose exactly one insurer and one retail health product whose policy wording clearly contains: (a) a specific waiting period table listing cataract by name, (b) an initial 30-day waiting period clause, (c) a pre-existing disease waiting period clause, (d) a hospitalization/day-care cover clause, and (e) exclusion provisions. All in a PDF with a text layer (no OCR required).
- **Decision:** **HDFC ERGO my: Optima Secure** (UIN: HDFHLIP26058V082526).
  - Section B.1.1 (page 11): hospitalization and "All Day Care Treatments" cover.
  - Section C.1.b / Excl02 (page 31): **24-month specific waiting period** — explicitly lists "Cataract and other disorders of lens and Retina".
  - Section C.1.a / Excl01 (page 30): 36-month PED waiting period.
  - Section C.1.c / Excl03 (page 32): 30-day initial waiting period.
  - 69-page PDF, machine-readable text layer, no OCR needed.
  - Open-list Day Care policy — no separate procedure annexure; simplifies corpus to one document.
- **Rejected Alternatives:**
  - **Star Health Family Health Optima** — also has a cataract specific WP, but PDF structure is denser and clause numbering less regular.
  - **Care Health Care Supreme** — well-structured, but PDF available only as a scanned image in some versions, requiring OCR.

---

## ADR-006: Container Runtime — Podman + podman-compose
- **Status:** Accepted
- **Date:** 2026-10-29 (Phase 0)
- **Context:** Project requires `docker compose up` from a clean clone. Docker CE is not installed on the development machine. Podman 5.8.9 is already installed.
- **Decision:** Use **Podman** (aliased to `docker` via symlink) + **podman-compose 1.6.0** (aliased to `docker-compose`). Compose files use standard Compose v3 syntax, fully compatible with podman-compose.
- **Rejected Alternatives:**
  - **Installing Docker CE** — rejected: unnecessary given Podman's compatibility; would require root/daemon setup.
  - **nerdctl + containerd** — not installed; extra setup with no benefit over Podman.
- **Note:** `~/.local/bin/docker` → `/usr/bin/podman`; `~/.local/bin/docker-compose` → `podman-compose`. This is transparent to all Makefile targets.

---

## ADR-007: LLM Provider — Ollama (Local)
- **Status:** Accepted
- **Date:** 2026-10-29 (Phase 0)
- **Context:** Project requires a free-tier LLM without committing credentials to the repo. Provider must be changeable by config only (LLM adapter interface). Ollama is already installed on the host with `llama3.2:latest` (3.2B) and `phi3:mini` (3.8B) available locally.
- **Decision:** **Ollama** as the development/production LLM provider via its OpenAI-compatible REST API (`http://localhost:11434/v1`). The LLM adapter uses the provider interface, so switching to Gemini, Groq, or any other OpenAI-compatible endpoint requires only changing `.env` variables.
- **Rejected Alternatives:**
  - **Gemini free tier** — viable alternative; requires a Google API key. Rejected as primary provider to avoid any credential management risk during development. Remains a supported option in `.env.example`.
  - **Groq / OpenRouter** — same reasoning. Supported in `.env` but not the default.
- **Note:** The LLM stub service remains the primary provider for load tests and CI runs, per the architecture spec.

---

## ADR-008: arq-Compatible Redis Client
- **Status:** Accepted
- **Date:** 2026-11-06 (Phase 1)
- **Context:** The original pins combined `arq==0.26.0` with `redis==5.0.7`. arq 0.26 requires `redis[hiredis]>=4.2,<5`, so the dependency set could not resolve.
- **Decision:** Pin the Python Redis client to `redis==4.6.0`. Keep the Redis server container on Redis 7; the server and client version numbers do not need to match.
- **Rejected Alternative:** Replace arq or upgrade it without evidence that the queue API remains compatible. This would create more Phase 1 change than a client pin correction.

---

## ADR-009: One CPU-Only Application Image
- **Status:** Accepted
- **Date:** 2026-11-06 (Phase 1)
- **Context:** API, worker and stub share the same source and the architecture calls for one application image. Building each service separately under Podman duplicated work. Unconstrained PyTorch also selected large CUDA packages even though embeddings run on CPU.
- **Decision:** Build one named `localhost/preauth-desk:dev` image and reuse it for API, worker and stub. Pin `torch==2.2.2+cpu` and use the official CPU wheel index during the image build.
- **Rejected Alternatives:** Three independently built identical images (wasteful) and CUDA-enabled PyTorch (multiple unnecessary gigabytes and no runtime benefit for MiniLM CPU embeddings).

---

## ADR-010: Clause-Aware Hybrid Retrieval
- **Status:** Accepted
- **Date:** 2026-11-06 (Phase 2)
- **Context:** A semantic search for a procedure's cover clause may miss a binding waiting-period table located many pages away. Exact policy terms and clause IDs are also important.
- **Decision:** Parse with PyMuPDF, preserve pages and canonical clause IDs, tag provision types, embed locally with MiniLM, and fuse FAISS dense and BM25 sparse ranks. Give exact query-token matches a small deterministic boost.
- **Rejected Alternatives:** A single fixed-size semantic pass (misses modifying provisions) and BM25 alone (weak on paraphrases).

---

## ADR-011: Deterministic Verification Around a Bounded LangGraph
- **Status:** Accepted
- **Date:** 2026-11-06 (Phase 3)
- **Context:** Unsupported coverage statements are more harmful than conservative escalation, and an LLM must not be trusted to validate its own citation IDs.
- **Decision:** Use separate research and verifier/router agents in LangGraph. Resolve citation IDs deterministically against the run's `EvidenceBundle`, require a mandatory-provision search checklist, and enforce step/tool/time/replan limits. Failed verification always routes to `medical-review`.
- **Rejected Alternatives:** One monolithic prompt and verifier-only natural-language citation checking.
