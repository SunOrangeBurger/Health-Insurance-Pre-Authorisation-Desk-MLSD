# Project Progress Log

## Phase Tracking

| Phase | Description | Status | Target Date | Completed Date |
|---|---|---|---|---|
| **Phase 0** | Foundations (layout, Dockerfile, env, secrets check, manifest) | **In Progress** | Day 1 | - |
| **Phase 1** | Walking Skeleton (Compose, API, Queue, Worker, Contracts, Web Client) | Planned | Days 2-5 | - |
| **Phase 2** | Corpus Pipeline & Retrieval (Chunking, Tagging, FAISS, BM25 Hybrid) | Planned | Days 4-9 | - |
| **Phase 3** | Agents (LangGraph Research & Verifier, Loop bounds, Cataract reference) | Planned | Days 8-16 | - |
| **Phase 4** | Reliability & Guardrails (Breaker, Fallback, Injection/Toxicity defense) | Planned | Days 14-22 | - |
| **Phase 5** | Observability (OTel -> Jaeger, Prometheus, Grafana, Cost ledger) | Planned | Days 18-26 | - |
| **Phase 6** | Evaluation (20+ scenarios, Groundedness, Faithfulness, Relevance) | Planned | Days 22-30 | - |
| **Phase 7** | SLO & Load Testing (Locust, Stub scaling, Caching benchmarks) | Planned | Days 26-34 | - |
| **Phase 8** | Docs, Runbook, Hardening, Clean-clone verification | Planned | Days 32-38 | - |

---

## Current Status (Phase 0)

### Done
- Initialized local git repository on branch `main`.
- Added comprehensive `.gitignore` preventing leaks of `.env`, `*.faiss`, raw PDFs, and artifacts.
- Created directory layout per `02_ARCHITECTURE.md`.
- Created `pyproject.toml` and pinned `requirements.txt`.
- Created multi-stage, non-root `Dockerfile` with command dispatch for `api`, `worker`, `ingest`, and `stub`.
- Created `.env.example` with safe placeholders for all runtime variables.
- Created `scripts/check_secrets.sh` and `Makefile`.
- Created skeletons for `docs/PROGRESS.md`, `docs/DECISIONS.md`, `docs/INCIDENTS.md`, and `docs/REPORT.md`.

### In Progress
- Finalizing selection of insurer/product policy wording and day-care list with user.
- Placing PDFs in `corpus/raw/` and recording in `corpus/MANIFEST.md`.

### Blocked
- None. Awaiting user confirmation on chosen insurer product to acquire policy PDFs.

### Decisions Made
- See [docs/DECISIONS.md](DECISIONS.md).

### Known Issues
- None at this stage.
