# Project Progress Log

## Phase Tracking

| Phase | Description | Status | Target Date | Completed Date |
|---|---|---|---|---|
| **Phase 0** | Foundations (layout, Dockerfile, env, secrets check, corpus) | ✅ **Done** | Day 1 | 2026-10-29 |
| **Phase 1** | Walking Skeleton (Compose, API, Queue, Worker, Contracts, Web Client) | ✅ **Done** | Days 2–5 | 2026-11-06 |
| **Phase 2** | Corpus Pipeline & Retrieval (Chunking, Tagging, FAISS, BM25 Hybrid) | ✅ **Done** | Days 4–9 | 2026-11-06 |
| **Phase 3** | Agents (LangGraph Research & Verifier, Loop bounds, Cataract reference) | ✅ **Done** | Days 8–16 | 2026-11-06 |
| **Phase 4** | Reliability & Guardrails (Breaker, Fallback, Injection/Toxicity defense) | ✅ **Done** | Days 14–22 | 2026-11-08 |
| **Phase 5** | Observability (OTel → Jaeger, Prometheus, Grafana, Cost ledger) | ✅ **Done** | Days 18–26 | 2026-11-08 |
| **Phase 6** | Evaluation (20+ scenarios, Groundedness, Faithfulness, Relevance) | ✅ Complete | Days 22–30 | 2026-11-08 |
| **Phase 7** | SLO & Load Testing (Locust, Stub scaling, Caching benchmarks) | ✅ Complete | Days 26–34 | 2026-11-08 |
| **Phase 8** | Docs, Runbook, Hardening, Clean-clone verification | ✅ Complete | Days 32–38 | 2026-11-08 |

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

---

## Phase 2 — COMPLETE ✅

### Exit Checks (All Passed)
- [x] Clause-aware PyMuPDF ingestion produced 109 stable chunks from the real 69-page policy.
- [x] Two consecutive builds produced the same chunk count and stable chunk IDs.
- [x] MiniLM (`all-MiniLM-L6-v2`) generated local CPU embeddings; FAISS index persisted to the shared volume.
- [x] BM25 + dense retrieval with reciprocal-rank fusion and exact-term boost returns `C.1.b` for filtered `cataract` search.
- [x] Cover search returns `B.1.1`.
- [x] Targeted re-embedding preserves vectors belonging to other documents (unit tested).
- [x] Index manifest exposes source checksum, build time, throughput, embedding model and chunker version.
- [x] Indexer is an automatic one-shot Compose service; worker waits for successful indexing.

### Verification Evidence
- Production index build: 109 chunks, 2.23 seconds, 48.95 chunks/second.
- Source checksum matched the corpus manifest: `195eb0499db969c6789472e7f87ef1c72da110e2a8c7761ecb5add378fe964c1`.
- Active index status is available at `GET /v1/index/status`; freshness/chunk/throughput gauges are exported on `/metrics`.

---

## Phase 3 — COMPLETE ✅ (50% Project Milestone)

### Exit Checks (All Passed)
- [x] LangGraph topology: intake/classifier → Policy Research Agent → Verifier/Router Agent, with bounded retry edge.
- [x] Typed tools: `search_corpus`, `get_clause`, `get_request_fields`, and `list_sections`.
- [x] Tool-call, graph-step, tool-time and wall-clock limits are configuration-driven.
- [x] Research/verifier hand-off uses a typed `EvidenceBundle`.
- [x] Every claimed citation is deterministically resolved against evidence retrieved in the same run.
- [x] Missing/fabricated citations are caught and safely routed to `medical-review`.
- [x] Versioned prompt artifacts are recorded in results and traces.
- [x] Run steps/tool calls/results/verification are persisted and returned by `GET /v1/runs/{id}/trace`.
- [x] 11-month cataract case returned `medical-review`, `waiting_period_not_served`, verified citations `B.1.1` and `C.1.b`.
- [x] 30-month cataract variant flipped to `approve-recommended` / `waiting_period_served`.
- [x] Out-of-corpus procedure returned `medical-review` with verification false and no fabricated provision.

### Verification Evidence
- Full unit suite: 24 tests passed.
- 11-month end-to-end run: `11f3a430-2749-4295-899a-6e2272d6a847`; 19 persisted trace steps across three agent roles.
- Final post-fix smoke run: `8718c4b4-d136-46a1-8b49-3e9f9178baa6`; verified `B.1.1` + `C.1.b` and 19 trace steps.
- 30-month flip run: `387c08b4-06f1-4e57-a49b-5d2b9a65d349`.
- Out-of-corpus run: `842304a8-eb4c-44fd-9880-80bb104a4405`.
- The cataract clause interpretation remains subject to the existing lecturer-confirmation note; it has not been represented as lecturer-approved.

### Next
- Phase 4: prompt-injection/toxicity guardrails, provider retries, circuit breaker, fault-mode degradation, and rate limiting.

---

## Phase 4 — COMPLETE ✅

### Exit Checks (All Passed)
- [x] LLM calls have configurable timeouts and retry only retryable transport, timeout, 429, 5xx and malformed-response failures.
- [x] Retry is bounded and uses exponential backoff with jitter.
- [x] Circuit breaker implements closed, open and single-probe half-open states with a Prometheus state gauge.
- [x] `FAULT_MODE=provider_down` produced an honest retrieval-only result with terminal status `degraded`, `medical-review`, preserved citations and no HTTP 500.
- [x] Injection detection runs over every free-text field before model access; flagged text is replaced in the stored run payload and the run escalates without agent, tool or cost events.
- [x] Twelve hostile prompt variants and toxicity/output-filter cases pass.
- [x] Redis token bucket returns 429 with `Retry-After` per client; inputs and tool arguments remain typed and tool results are marked untrusted.

### Verification Evidence
- Prompt-injection run `63fb3a3c-26b8-417a-ad69-43b44d1ac4c3`: `escalated`, `guardrail_blocked`, empty steps and costs.
- Provider-down run `d21f389e-1efd-4f5f-b118-9b674df15d08`: `degraded`, retrieval-only `medical-review`; `llm_circuit_breaker_state{provider="stub"}=1`.
- Reproducible commands are in `scripts/demo_07_prompt_injection.sh` and `scripts/demo_08_circuit_breaker.sh`.

---

## Phase 5 — COMPLETE ✅ (75% Project Milestone)

### Exit Checks (All Passed)
- [x] OpenTelemetry spans cover FastAPI, worker runs, provider calls, graph nodes and retrieval tools.
- [x] Jaeger received services `preauth-api` and `preauth-worker` from real synthetic traffic.
- [x] Prometheus scrapes API, worker, LLM stub, Redis exporter and itself; application/process CPU and RSS metrics require no privileged host mount.
- [x] Provisioned Grafana dashboard includes p50/p95 latency, throughput/outcomes, retries, breaker state, index freshness, agent/tool metrics, notional cost and process resources.
- [x] Cost ledger records provider/model, step, prompt/completion tokens and configured notional cost per call.
- [x] `scripts/show_run.py` reconstructs tool arguments, result IDs, prompt versions, latency, verification and cost entries.

### Verification Evidence
- Successful provider run `6efe7802-ed6a-44b0-b8a9-a40276da5d2d`: completed with 19 persisted steps and a `provider_advisory` cost entry (72 prompt tokens, 1 completion token, configured cost $0).
- Final rebuilt-stack run `1c979a5b-e165-43e2-82da-d2aac4bb6f00`: `completed`, `approve-recommended`, verification passed, citations `B.1.1` + `C.1.b`, verbatim citation text preserved, 19 steps and one cost entry.
- Grafana health, Prometheus readiness and Jaeger UI/API were verified locally on 2026-11-08.
- Prometheus reported healthy targets for API, worker, stub, Redis and Prometheus.
- The `host-metrics` cAdvisor profile is intentionally opt-in because it requires privileged host access; it was not started during verification. The default dashboard uses safer service-process CPU/RSS metrics.

## Phases 6–8 — COMPLETE ✅ (100% Project Milestone)

### Exit Checks (All Passed)
- [x] Fixed 24-scenario evaluation set exercised the live asynchronous API.
- [x] V1/V2 prompt comparison and a deliberate conservative-routing change were measured.
- [x] Final routing accuracy is 1.0000; false-approval and hallucination rates are 0.0000.
- [x] End-to-end SLO was declared and committed before the 1–80 user Locust matrix.
- [x] First tested SLO miss identified at 80 users; worker bottleneck documented.
- [x] One/three-worker and retrieval-cache on/off comparisons measured.
- [x] Feedback API, response contract and quality metric implemented.
- [x] Full ten-step demo script, demo guide and two-mode operational runbook completed.
- [x] Final suite passes 44 tests and contracts were regenerated.

### Evidence
- Evaluation: `evals/results/eval_v1.json`, `eval_v2.json`, `eval_v2_final.json`.
- Load: `loadtest/results/summary.json` and `comparisons.json` plus raw CSVs.
- One-command demonstration: `scripts/demo_full.sh`.
- Final completion date: 2026-11-08.
