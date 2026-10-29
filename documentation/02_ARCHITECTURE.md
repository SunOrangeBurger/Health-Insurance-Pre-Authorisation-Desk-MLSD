# Architecture and Design

This is the target design. The agent may deviate where it has a reason; record the reason in `docs/DECISIONS.md`.

## 1. Stack (all free, all containerised)

| Concern | Choice | Notes / rejected alternative |
|---|---|---|
| Language | Python 3.11 | |
| API | FastAPI + Uvicorn | |
| Queue / task runner | Redis + **arq** (or Celery) | arq: small, async-native. Celery is heavier but more familiar; either is fine |
| Agents | LangGraph | CrewAI rejected: less control over loop bounds and explicit state |
| RAG orchestration | LangChain (retrievers, splitters) | |
| Vector index | FAISS (persisted to volume) + SQLite/Postgres chunk metadata | Chroma is acceptable; FAISS gives simpler incremental control by ID with `IndexIDMap` |
| Embeddings | `all-MiniLM-L6-v2` local | Optionally add BM25 (`rank_bm25`) for hybrid retrieval of exact clause terms |
| LLM | Provider adapter (LiteLLM or thin custom client), model ID from env | Free tier; stub service for load tests |
| State store | Postgres (runs, steps, quarantine, feedback, costs) | SQLite rejected: concurrent workers |
| Cache / rate limit | Redis | |
| Observability | OpenTelemetry SDK -> Jaeger; `prometheus-client`; Grafana; JSON logs (`structlog`) | |
| Eval | TruLens or RAGAS + custom claim-level scorer | |
| Load test | Locust | |
| Guardrails | Custom layered filters + `detoxify` or a small toxicity classifier; regex/heuristic + LLM-free injection detector | |

## 2. Services (Docker Compose)

| Service | Role | Scales? | Image |
|---|---|---|---|
| `api` | FastAPI: contract validation, quarantine, enqueue, status, feedback, web client, `/metrics` | Yes (stateless) | app image, command `api` |
| `worker` | Runs the LangGraph agents; consumes jobs. **This is what `--scale worker=3` scales** | Yes | app image, command `worker` |
| `redis` | Queue, cache, rate limit counters | No | `redis:7` |
| `postgres` | Runs, steps, quarantine, feedback, cost ledger | No | `postgres:16` |
| `indexer` | One-shot job: ingest pipeline (parse, chunk, embed, index) writing the shared index volume; also CLI for `--reembed` | One-shot | app image, command `ingest` |
| `llm-stub` | Fixed responses after configurable delay (`STUB_DELAY_MS`, jitter); used in load tests and offline dev | Yes | small FastAPI app |
| `prometheus` | Scrapes api, worker(s), llm-stub, redis-exporter, cadvisor | No | |
| `grafana` | Provisioned dashboards | No | |
| `jaeger` | Trace backend (OTLP) | No | |
| `cadvisor` | Per-container resource utilisation | No | |

Index sharing: `indexer` writes to a named volume `index_data`. `worker` mounts it read-only and loads the index at start; a `/admin/reload-index` or file-mtime watcher refreshes it. Document this and its failure mode (worker started before index exists -> `/readyz` fails -> compose healthcheck gates dependents).

Compose requirements: healthchecks on every service; `depends_on: condition: service_healthy`; `indexer` runs with `condition: service_completed_successfully` ahead of `worker`; use Compose `profiles` for `loadtest` / `stub`; `.env` for all configuration.

### Deployment-boundary justification (write this into the report)

- **api vs worker split:** *scaling* (api is I/O-light, workers are LLM-bound and long-running) and *failure isolation* (a worker stuck on a slow provider must not take the submission endpoint down); *independent release*.
- **Worker vs Redis/Postgres:** stateful stores have different resource profile and lifecycle.
- **indexer separate from worker:** *resource profile* (embedding is CPU/RAM-heavy, once) and idempotent re-run without restarting workers.
- **llm-stub separate:** it must be swappable by config without touching app code, to measure our system rather than provider limits.
- Remember: modules inside the same container share a deployment boundary. Retrieval agent and verifier agent run in the **same worker process** by default; state this honestly, and if you want them separately deployable, that's an optional later step (a `verifier` service). Don't claim isolation you don't have.

## 3. Repo layout

```
preauth-desk/
  docker-compose.yml
  .env.example
  .gitignore
  Makefile                 # up, down, ingest, eval, load, test, check-secrets
  README.md
  contracts/               # preauth_request.schema.json, preauth_response.schema.json, openapi.json
  corpus/
    raw/                   # PDFs (gitignored if licence unclear; keep MANIFEST.md)
    MANIFEST.md
  src/preauth/
    api/                   # FastAPI app, routes, validation, quarantine, rate limit
    agents/                # graph.py, retrieval_agent.py, verifier_agent.py, tools.py, state.py, limits.py
    llm/                   # adapter.py, circuit_breaker.py, retry.py, pricing.py, stub_client.py
    rag/                   # parse.py, chunk.py, embed.py, index.py, hybrid.py
    guardrails/            # injection.py, toxicity.py, output_filter.py
    obs/                   # logging.py, tracing.py, metrics.py, correlation.py
    store/                 # models.py, migrations/
    worker.py
    cli.py                 # ingest, eval, reembed
  prompts/                 # <name>/v1.yaml, v2.yaml (id, version, template, notes)
  evals/                   # set_v1.jsonl, run.py, metrics.py, results/
  loadtest/                # locustfile.py, stub/, results/
  web/                     # index.html + app.js
  ops/                     # prometheus.yml, grafana/provisioning, dashboards/*.json
  scripts/                 # check_secrets.sh, demo_*.sh
  tests/
  docs/
    brief/ PROGRESS.md DECISIONS.md SLO.md RUNBOOK.md INCIDENTS.md REPORT.md
```

## 4. Data contract (`POST /v1/preauth`)

Synthetic data only. Fields (adjust, but publish exactly what you enforce):

| Field | Type | Rules |
|---|---|---|
| `request_id` | string | optional client id, `^[A-Za-z0-9\-]{8,64}$` |
| `policy_number` | string | pattern defined by you; synthetic |
| `policy_issue_date` | date | not in future |
| `policy_start_date` | date | >= issue date, <= admission date |
| `sum_insured` | integer | 100000 to 10000000, multiple of 1000 |
| `patient_age` | integer | 0..100 |
| `patient_gender` | enum | M, F, O |
| `admission_type` | enum | planned_surgical, day_care, emergency, maternity |
| `planned_admission_date` | date | >= today for planned types; emergencies may be same-day or past 24h |
| `diagnosis_text` | string | free text, 3-500 chars, **guardrailed** |
| `procedure_text` | string | free text, 3-300 chars, **guardrailed** |
| `procedure_code` | string, optional | pattern |
| `room_category_requested` | enum | general, shared, single, deluxe |
| `estimated_cost` | number | >0, <= 5,000,000 |
| `hospital_id` | string | synthetic |
| `prior_conditions` | array of strings | optional, each <=100 chars, guardrailed |
| `notes` | string | optional free text <=1000, guardrailed |

Cross-field rules (examples; implement all): `planned_admission_date >= policy_start_date`; `estimated_cost <= sum_insured * 1.5` else flag (not reject); `admission_type=maternity` with `patient_gender=M` rejected; `patient_age < 12` with `maternity` rejected; `policy_issue_date <= policy_start_date`; unknown fields rejected (`extra=forbid`).

Quarantine record: `{id, received_at, correlation_id, client_id, raw_payload (redacted of free text if flagged), errors:[{field, code, message}], contract_version}`. Rejected requests return **422** with the same error list and a quarantine ID. **No run row, no queue message.**

Responses:
- `202 {run_id, status:"queued", poll_url}`
- `GET /v1/runs/{id}` -> `{status: queued|running|completed|escalated|failed|degraded, result?, prompt_versions, correlation_id, timings}`
- `result` = `{admission_class, entities, coverage_position, indicative_limit:{amount, basis, caveats}, route, route_reason, citations:[{id, doc, section, page, text}], verification:{passed, checks[]}, disclaimer}`

Also publish contracts for: feedback endpoint, the queue job message, the LLM adapter request/response, and the tool signatures. D1 says *every* external interface.

## 5. Agent design

### Topology (two agents, defined hand-off)

```
request -> [Intake/Classifier node] -> [Agent 1: Policy Research Agent] --evidence bundle--> [Agent 2: Verifier & Router Agent] -> result
                                              ^                                                   |
                                              +------ "re-search with strategy X" (<=N times) ----+
```

- **Agent 1: Policy Research Agent.** Responsibility: find every provision that binds this admission. Tools: `search_corpus(query, filters)`, `get_clause(clause_id)`, `get_request_fields(keys)`, optionally `list_sections()`. Loop: retrieve the apparent cover clause -> ask "what modifies this?" (waiting periods, exclusions, sub-limits, room rent, pre-existing disease, co-pay, day-care list) -> issue derived queries using *terms read in retrieved text* -> stop when the checklist is covered or budget exhausted. Output: **evidence bundle** (retrieved passages with IDs) + draft position with claimed citations.
- **Agent 2: Verifier & Router Agent.** Responsibility: independent check. (1) Every cited ID exists in the evidence bundle (deterministic check). (2) Each claim supported by cited text (LLM-as-judge entailment, plus deterministic quote/numeric match for amounts and month counts). (3) Mandatory-provision checklist satisfied for the admission class (e.g. waiting-period lookup performed). (4) Compute the route. On failure: returns a `retry_directive` (different strategy: e.g. keyword/BM25 instead of semantic, section-targeted search, `get_clause` by neighbouring ID) up to `MAX_REPLANS` (default 2), then escalates.
- **Hand-off contract:** the evidence bundle is a typed object (`EvidenceBundle`), passed through LangGraph state, persisted per step so a crash can resume.

### Failure behaviour (document in report)

| Failure | Behaviour |
|---|---|
| Agent 1 exceeds step/tool/time budget | Returns partial bundle flagged `incomplete`; Agent 2 forces `medical-review` with reason "research incomplete" |
| Agent 1 crashes | Job retried once from last checkpoint; then run marked `failed`, route `medical-review`, never a confident answer |
| Agent 2 crashes/times out | Run marked `degraded`; return evidence bundle with `route=medical-review`, `verification.passed=false` |
| Provider down (circuit open) | Fallback path (below) |

### Loop limits (env-configurable)

`MAX_STEPS=12`, `MAX_TOOL_CALLS=10`, `RUN_TIMEOUT_S=90`, `LLM_TIMEOUT_S=20`, `TOOL_TIMEOUT_S=5`, `MAX_REPLANS=2`. Exceeding any limit ends the loop cleanly with a flagged state; none may produce a confident answer.

### Resilience (A5)

- Timeouts on every LLM and tool call.
- Retry: max 3 attempts, exponential backoff with jitter (e.g. 0.5s, 1s, 2s), only on retryable errors (timeout, 429, 5xx).
- Circuit breaker on the provider: open after 5 consecutive failures, cooldown 30s, half-open single probe. Expose state as a Prometheus gauge.
- Fallback path (in order): (1) secondary model/provider via config if configured, (2) **retrieval-only mode**: return the retrieved mandatory provisions with route `medical-review` and "automated reasoning unavailable", (3) queue for later retry with status `queued_degraded`, (4) honest error. Never a stack trace.
- `FAULT_MODE` env var (`none|provider_down|slow|garbage`) in the stub and adapter to make demo item 8 reproducible.

## 6. Routing rules (deterministic, after verification)

| Condition | Route |
|---|---|
| Verification failed after max replans; conflicting provisions; possible pre-existing condition; procedure not found in corpus/day-care list; run incomplete/degraded; any ambiguity in classification | `medical-review` (state reason) |
| Required information missing from the request that would settle the question (e.g. diagnosis date, prior treatment, room category unclear, pre-auth documents) | `query-to-hospital` (list the exact questions) |
| All binding provisions retrieved, verified, none blocking; waiting periods served; no exclusion; limit computed | `approve-recommended` |
| Waiting period **not served**, exclusion applies, or sub-limit breach that reduces cover | Adverse position: route `medical-review` with the recommendation "not covered at this time / reduced", citing clauses. The system does not issue denials; a medical officer decides |

Output filter: the system must not emit words like "approved", "authorised", "denied", "rejected" as determinations. Only "recommended" language, plus a standing disclaimer that a medical officer decides.

## 7. Retrieval design (addresses the section-3 difficulty)

- **Parsing:** PyMuPDF/`pdfplumber`; preserve page numbers; detect headings and numbered clauses (e.g. `4.2.1`). OCR only if no text layer.
- **Chunking:** structure-aware. One chunk per clause/sub-clause (target 150-400 tokens, small overlap only when a clause is split), each chunk prefixed with its breadcrumb: `[Doc | Section | Clause ID | Page]`. Tables (waiting-period tables, sub-limit tables) kept as table-aware chunks, with one row per chunk **plus** a whole-table chunk. Every chunk gets a stable `chunk_id = hash(doc_id, clause_id, text)`.
- **Tag chunks by provision type** at ingest: `cover | waiting_period | exclusion | sublimit | room_rent | definition | claims_procedure | day_care_list`. Store as metadata. This enables filtered searches like `search_corpus("cataract", type="waiting_period")`, which fixes the structural problem that a cover-clause query never surfaces the waiting-period clause.
- **Hybrid search:** dense (MiniLM + FAISS) + BM25, reciprocal-rank fusion. Exact terms (e.g. "cataract", "Specific waiting period") matter.
- **Mandatory-provision checklist** per admission class (used by verifier): for any non-emergency admission -> initial waiting period, specific waiting period for the condition, pre-existing disease waiting, permanent exclusions, sub-limits, room-rent/proportionate deduction, day-care list if day-care.
- **Incremental re-embed:** keep `chunk_hash -> vector id` map; re-embedding a doc or model change touches only changed/targeted chunks (`IndexIDMap.remove_ids` + add). `ingest` is idempotent: same input -> same chunk IDs, same count, no duplicates.
- **Freshness metadata:** `index_manifest.json` = `{built_at, docs:[{doc_id, sha256, version}], n_chunks, embedding_model, chunker_version, build_seconds, chunks_per_second}`; exposed as gauges.

## 8. Reference case: cataract, issued 11 months ago

At Evaluation 1 you must show the passages this depends on and the values you will test with. Procedure:

1. Find in your policy: the cover clause (surgery/in-patient/day-care covers), the waiting-period clause that lists cataract (usually a *specific* waiting period of 12, 24 or 36 months, sometimes only waiting for certain conditions), the initial 30-day waiting, and any sub-limit for cataract (often a per-eye INR cap in a table or a "% of sum insured" cap).
2. Copy the exact passages and their clause IDs/pages into `evals/reference_case.md`.
3. Test request: `admission_type=day_care` or `planned_surgical` (match what the policy/day-care list says for cataract), `procedure_text="Phacoemulsification with IOL, right eye"`, `policy_issue_date = admission - 11 months`, synthetic otherwise.
4. Expected answer: depends on your policy's waiting period N. **If N > 11 months** (the usual case): waiting period not served, adverse recommendation, route `medical-review`, citations = cover clause **and** waiting-period clause (and the sub-limit clause if present). **If N <= 11** (rare): proceed to limit determination, `approve-recommended` or `query-to-hospital` depending on completeness, citing cover, waiting-period (showing served) and sub-limit clauses. Also include a *variant* test (policy issued 30 months ago) to show the answer flips.
5. Get the lecturer to confirm; then freeze as the reference answer.

The agent must **not** invent these clauses. It must extract them from the actual PDFs and show you.
