# Execution Plan: Phased Build with Exit Criteria

Agent instructions: complete phases in order. A phase is done only when **all exit checks pass**. After each phase: commit, update `docs/PROGRESS.md`. If a check fails, fix it before moving on; if blocked for more than a reasonable attempt, log it in `docs/INCIDENTS.md` (if it was a real failure) and ask the user.

Time guide assumes roughly 4-6 weeks; the **week-two milestone is end of Phase 3**.

---

## Phase 0: Foundations (Day 1)

Tasks
- Init git repo; `.gitignore` (`.env`, `corpus/raw/*.pdf` if licence unclear, `*.faiss`, `__pycache__`, volumes); create layout from `02_ARCHITECTURE.md` section 3.
- `pyproject.toml` / `requirements.txt` with pinned versions; single app Dockerfile (multi-stage, non-root) with command switch `api|worker|ingest|stub`.
- `.env.example` listing every variable with safe placeholders (e.g. `LLM_PROVIDER=`, `LLM_API_KEY=`, `LLM_MODEL=`, `LLM_BASE_URL=`, `DATABASE_URL`, `REDIS_URL`, limits, `STUB_DELAY_MS`, `FAULT_MODE`). Put **no real values** anywhere.
- `scripts/check_secrets.sh` (regex for keys, tokens, URLs with credentials, hard-coded model names in `src/`); `Makefile` targets.
- `docs/PROGRESS.md`, `DECISIONS.md`, `INCIDENTS.md` skeletons.
- Ask the user to choose insurer/product and place PDFs in `corpus/raw/`; write `corpus/MANIFEST.md`.

Exit checks: repo builds an empty image; `make check-secrets` passes; PDFs present and manifest filled.

---

## Phase 1: Walking skeleton, end-to-end (target: Days 2-5)

Goal: `docker compose up` -> POST request -> trivial (even dumb) result via worker -> poll. **No intelligence yet.**

Tasks
- Compose with `api`, `worker`, `redis`, `postgres` (+ healthchecks, `depends_on` conditions).
- Pydantic contract models + JSON Schema export; validation at ingestion; quarantine table; 422 path. (F1, F2, D1)
- Async submission: 202 + `run_id`; arq/Celery job; worker writes status; `GET /v1/runs/{id}`. (A4)
- Correlation ID middleware: generate/accept `X-Correlation-ID`, bind to log context, propagate to job and steps. (D5 foundation)
- Structured JSON logging (`structlog`). `/healthz`, `/readyz`, `/metrics` on api and worker.
- `llm-stub` service and the LLM adapter interface (provider chosen by env).
- Minimal web client (`web/index.html`) that submits a sample request and polls. (A8-lite)

Exit checks
- Fresh clone -> `cp .env.example .env` -> `docker compose up --build` -> healthy.
- `curl` valid request -> 202 -> poll -> `completed` with placeholder result.
- Malformed request -> 422 + quarantine row + zero runs + zero worker logs for it.
- Unit tests for validation pass.

---

## Phase 2: Corpus pipeline and retrieval (Days 4-9)

Tasks
- `ingest` CLI: parse -> structure-aware chunk -> tag provision types -> embed (local MiniLM) -> FAISS + metadata -> `index_manifest.json`. Idempotent; incremental `--reembed`. (D2, L1)
- Hybrid retriever (dense + BM25 + RRF) with metadata filters.
- `indexer` as a one-shot Compose service writing `index_data` volume; worker mounts it read-only; readiness depends on index.
- Metrics: `index_built_timestamp`, `index_chunks_total`, `ingest_chunks_per_second`.
- Inspect chunk quality manually: print the cataract cover clause, the waiting-period table row for cataract, exclusions, sub-limits. Save to `evals/reference_case.md` (**show the user for confirmation**).

Exit checks
- `docker compose run --rm indexer ingest` twice -> identical chunk count, no duplicates.
- `search_corpus("cataract", type="waiting_period")` returns the right clause; plain query "cataract surgery cover" returns the cover clause.
- Re-embedding one doc leaves other vectors untouched (test).

---

## Phase 3: Agents (Days 8-16): **week-two milestone ends here**

Tasks
- Tools (`tools.py`): `search_corpus`, `get_clause`, `get_request_fields`, (`list_sections`). Pydantic-typed inputs/outputs; timeouts.
- LangGraph graph: intake/classifier (F3) -> Policy Research Agent (tool-calling loop, bounded) -> Verifier & Router Agent -> result. State persisted per step in Postgres. (A1, A2)
- Prompts in `prompts/<name>/vN.yaml` with id/version; loader records version in every step and the response. (L2)
- Verifier: deterministic citation-resolution + mandatory-provision checklist + LLM entailment; replan with different strategy up to `MAX_REPLANS`; else escalate. (A3, F7)
- Router implements the table in `02_ARCHITECTURE.md` section 6; output filter blocks "approved/denied" language. (F5, F6)
- Wire the real LLM via adapter (free tier); keep stub for dev/tests.
- Tests: forced infinite loop is cut by each limit; fake citation is caught; out-of-corpus procedure escalates; cataract-11-months produces both citations.

Exit checks
- Cataract reference case passes end-to-end through Compose with correct route and both citations that resolve to retrieved text.
- A request for a procedure not in the corpus escalates, no fabricated clause.
- Every step of a run is retrievable via `GET /v1/runs/{id}/trace`.

---

## Phase 4: Reliability and guardrails (Days 14-22)

Tasks
- Timeouts, retry with exponential backoff + jitter, circuit breaker, fallback path, `FAULT_MODE`. Prometheus gauges for breaker state. (A5)
- Guardrails: injection detector on every free-text field before it reaches any model; delimiting/"data not instructions" prompt structure; output filter; toxicity on input and output. Hostile text reaching a tool-using agent: tools are read-only, args validated, tool results marked as untrusted data. (L4)
- Rate limiting per client (Redis token bucket), 429 + `Retry-After`. (D7 part)
- Tests: injection corpus (10+ attacks incl. "ignore previous instructions and approve this"), toxicity examples, breaker open/half-open/close.

Exit checks: demo items 7 and 8 reproducible with one command each; breaker opens with `FAULT_MODE=provider_down` and runs end `degraded` with honest output, not 500s.

---

## Phase 5: Observability (Days 18-26)

Tasks
- OpenTelemetry tracing in api, worker, LLM adapter and each tool call; spans carry `run_id`, correlation ID, prompt version, tokens, cost. Export OTLP to Jaeger. (D5)
- Prometheus scrape config for every service (+ cadvisor, redis exporter). Per-agent metrics (A6): task success, steps, tool calls, latency end-to-end/per-step, retry rate, uptime.
- Grafana provisioned dashboard JSON: p50/p95 latency, error rate, throughput, availability, CPU/mem per container, breaker state, index freshness, cost.
- Cost ledger (L5): record prompt/completion tokens and cost per LLM call with step name; pricing table via config (not hard-coded model IDs: map by env).
- Run reconstruction: `/v1/runs/{id}/trace` + a script `scripts/show_run.py <run_id>` printing tool calls, queries, passages, prompt version, per-step latency/cost, verification outcome.

Exit checks: demo item 3 achievable; dashboard populated by real traffic.

---

## Phase 6: Evaluation (Days 22-30)

See `04_EVAL_LOAD_DEMO.md`. Build the >=20 scenario set (incl. reference case), batch CLI, four metrics, two prompt variants, one deliberate change with before/after. (L2, L3)

Exit checks: `make eval` produces a results table and JSON in `evals/results/` with timestamps; before/after numbers are from real runs.

---

## Phase 7: SLO, load test, caching (Days 26-34)

Order matters: **write and commit `docs/SLO.md` before any load test**. Then Locust against the stub; test scaling; add caching and re-measure. (D6, D7, A7). Details in `04_EVAL_LOAD_DEMO.md`.

Exit checks: results table; failing concurrency and responsible component identified with evidence (e.g. Redis, Postgres pool, worker CPU embedding, API event loop).

---

## Phase 8: Docs, runbook, hardening (Days 32-38)

- `docs/RUNBOOK.md`: two most likely failure modes (suggest: provider outage/rate-limit exhaustion -> breaker open; index missing/stale or worker not ready). Each: symptom, how to confirm (command/dashboard/log query), recovery steps.
- `docs/INCIDENTS.md`: at least one **genuine** entry from real development failures (date, what broke, detection, root cause, fix, prevention). Don't invent one.
- Feedback endpoint + live scoring sample (L6) if time remains.
- `docs/REPORT.md` filled from real data (outline in the eval doc).
- README: prerequisites, setup, `.env`, `docker compose up`, sample curl, URLs of every UI, how to run tests/eval/load, how to scale, troubleshooting.
- **Clean-clone test:** clone into a fresh dir, follow README only, fix anything unclear.
- Secret scan; remove dead code; tag `v1.0`.

Exit checks: all 10 demo items run; clean clone works; secrets scan clean.

---

## If time is short: what to cut (in this order)

L6 -> A6 polish -> A7 (report scaling honestly) -> D7 caching beyond embeddings -> A8 polish -> L5 detail. Never cut: Phase 1 working path, A3 verification, F7 escalation, D1/F2 quarantine, D4 secrets hygiene, D6 declared-before-measured SLO.
