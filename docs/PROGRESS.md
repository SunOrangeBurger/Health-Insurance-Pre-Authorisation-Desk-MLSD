# Project Progress Log

## Phase Tracking

| Phase | Description | Status | Target Date | Completed Date |
|---|---|---|---|---|
| **Phase 0** | Foundations (layout, Dockerfile, env, secrets check, corpus) | ✅ **Done** | Day 1 | 2026-10-29 |
| **Phase 1** | Walking Skeleton (Compose, API, Queue, Worker, Contracts, Web Client) | ✅ **Done** | Days 2–5 | 2026-11-06 |
| **Phase 2** | Corpus Pipeline & Retrieval (Chunking, Tagging, FAISS, BM25 Hybrid) | 🔲 Planned | Days 4–9 | — |
| **Phase 3** | Agents (LangGraph Research & Verifier, Loop bounds, Cataract reference) | 🔲 Planned | Days 8–16 | — |
| **Phase 4** | Reliability & Guardrails (Breaker, Fallback, Injection/Toxicity defense) | 🔲 Planned | Days 14–22 | — |
| **Phase 5** | Observability (OTel → Jaeger, Prometheus, Grafana, Cost ledger) | 🔲 Planned | Days 18–26 | — |
| **Phase 6** | Evaluation (20+ scenarios, Groundedness, Faithfulness, Relevance) | 🔲 Planned | Days 22–30 | — |
| **Phase 7** | SLO & Load Testing (Locust, Stub scaling, Caching benchmarks) | 🔲 Planned | Days 26–34 | — |
| **Phase 8** | Docs, Runbook, Hardening, Clean-clone verification | 🔲 Planned | Days 32–38 | — |

---

## Phase 0 — COMPLETE ✅

### Exit Checks (All Passed)
- [x] Git repository initialised on branch `main`
- [x] `make check-secrets` passes clean
- [x] `.env` is not tracked in git (only `.env.example` committed)
- [x] `corpus/raw/optima_secure_policy_wording.pdf` present (69 pages, text layer confirmed)
- [x] `corpus/MANIFEST.md` filled with SHA-256, UIN, source URL, clause page map
- [x] `evals/reference_case.md` written with verbatim clause text extracted from the actual PDF

### Done
- Initialised local git repository on branch `main`.
- Created full directory layout per `02_ARCHITECTURE.md` section 3:
  `src/preauth/{api,agents,llm,rag,guardrails,obs,store}`, `contracts/`, `corpus/`, `docs/brief/`, `evals/`, `loadtest/`, `web/`, `ops/`, `scripts/`, `tests/`
- `pyproject.toml` with project metadata and dependency groups.
- `requirements.txt` with fully pinned versions (FastAPI 0.111, arq 0.26, LangGraph 0.2, FAISS-CPU 1.8, sentence-transformers 2.7, structlog 24, OTel 1.25, Locust 2.29).
- Multi-stage non-root `Dockerfile` with `CMD api|worker|ingest|stub` dispatch via `scripts/entrypoint.sh`.
- `.env.example` with safe placeholder values for all runtime variables. Supports `LLM_PROVIDER=ollama|stub|gemini|groq|openrouter|openai`.
- `scripts/check_secrets.sh` — scans for API key patterns, private keys, URL-embedded credentials, and hardcoded model names in `src/`.
- `Makefile` — targets: `build`, `up`, `down`, `restart`, `logs`, `test`, `check-secrets`, `ingest`, `eval`, `load`, `clean`.
- Skeleton docs: `docs/DECISIONS.md`, `docs/INCIDENTS.md`, `docs/REPORT.md`.
- `docs/brief/` — copy of all project brief documents.
- Corpus acquired: **HDFC ERGO my: Optima Secure** (UIN `HDFHLIP26058V082526`) — 69-page policy wording PDF downloaded from official HDFC ERGO customer portal. Text layer present, no OCR required.
- `corpus/MANIFEST.md` — SHA-256 `195eb0499db...`, source URL, key clause page numbers confirmed.
- `evals/reference_case.md` — verbatim text of four key clauses (B.1.1 cover, C.1.a PED WP, C.1.b specific WP listing cataract at **24 months**, C.1.c 30-day WP). Reference answer frozen pending lecturer confirmation.
- Container runtime confirmed: **Podman 5.8.9** + **podman-compose 1.6.0** installed; `docker`/`docker-compose` symlinks in `~/.local/bin`.
- LLM runtime confirmed: **Ollama** running as background daemon. Available models: `llama3.2:latest` (3.2B Q4), `phi3:mini` (3.8B Q4), `nomic-embed-text:latest` (137M F16).
- `.env` created locally (not committed) with `LLM_PROVIDER=ollama`, `LLM_MODEL=llama3.2:latest`, `LLM_BASE_URL=http://localhost:11434/v1`.
- Phase 0 committed as `01421ec` with full detail message.

### Decisions Made (Phase 0)
- See [docs/DECISIONS.md](DECISIONS.md) for full ADR records.
- **Insurer chosen:** HDFC ERGO my: Optima Secure — selected because it has a clearly tabulated 24-month specific waiting period listing cataract by name (page 31), day-care coverage (open list, page 11), and PED waiting period (page 30). No OCR required.
- **LLM provider:** Ollama (local) — fully free, no API key, no spend risk. Models: `llama3.2:latest` for reasoning, `nomic-embed-text` noted but local `sentence-transformers/all-MiniLM-L6-v2` will be used for FAISS embeddings per project rule 10.
- **Container runtime:** Podman + podman-compose — Docker CE not installed; Podman 5.8 already present and compatible.
- **Corpus note:** Optima Secure is an open-list Day Care policy (no restricted procedure annexure). The single policy wording PDF is the sole corpus document.

### Known Issues / Open Items
- `evals/reference_case.md` — **awaiting lecturer confirmation** of the 24-month cataract waiting period and absence of a cataract sub-limit before the reference answer is frozen.
- No cataract sub-limit found in base policy text — needs lecturer confirmation.
- `documentation/` folder at project root is a duplicate of `docs/brief/`; to be removed or `.gitignore`d in a future cleanup commit.

---

## Phase 1 — COMPLETE ✅

### Exit Checks (All Passed)
- [x] One application image built successfully with CPU-only PyTorch; API, worker and stub reuse it.
- [x] Compose started PostgreSQL, Redis, LLM stub, API and worker; all five became healthy.
- [x] Valid synthetic request returned 202, traversed Redis/arq, and reached `completed` through polling.
- [x] Walking-skeleton result safely routed to `medical-review` with verification false.
- [x] Malformed request returned 422 with field-level errors; database counts showed one quarantine row and no additional run.
- [x] OpenAPI and Prometheus endpoints returned successfully.
- [x] Fourteen validation unit tests passed.
- [x] Secret scan passed.

### Done
- Added strict Pydantic request contract with categorical, range, pattern, unknown-field, date, maternity, and cross-field rules.
- Added published JSON Schemas for pre-authorisation, submission, run status, feedback, queue job, and LLM adapter contracts, plus exported OpenAPI.
- Added PostgreSQL run/quarantine models and async repositories.
- Added FastAPI submission, polling, health, readiness, metrics, correlation-ID middleware, and quarantine exception handling.
- Added arq worker with bounded retry/time settings, JSON logs, worker metrics, and a conservative placeholder result.
- Added provider-neutral LLM interface and configurable fault-injectable stub service.
- Added minimal browser client that submits and polls a synthetic request.
- Added a five-service Compose stack with health-gated dependencies.

### Verification Evidence
- `14 passed in 0.10s` from `.venv/bin/pytest -q` under Python 3.11.
- End-to-end run `a210463f-3c63-416f-b98f-be4a99ac4692` completed on 2026-11-06.
- Quarantine record `1603c3a2-d795-4a0e-902f-e6b636b704d0` captured both invalid age and forbidden extra-field errors.
- Post-check database counts: `runs=1`, `quarantine=1`.

### Next
- Phase 2: clause-aware PDF parsing, stable chunks, provision tagging, local embeddings, FAISS/BM25 hybrid retrieval, and idempotent incremental ingestion.
