# Project Spec: Requirements as an Acceptance Checklist

Priority key: **P0** = needed for the system to run and be demonstrated (do first). **P1** = core marks. **P2** = important differentiators. **P3** = if time allows. Completing all 22 is not expected; sound prioritisation is assessed. Record what you skipped and why in `docs/PROGRESS.md`.

## Product behaviour (F)

| ID | Pri | Requirement | Acceptance check |
|---|---|---|---|
| F1 | P0 | `POST /v1/preauth` accepts a request per a published data contract | OpenAPI doc served at `/docs`; contract file in `contracts/` |
| F2 | P0 | Schema, range, categorical and cross-field validation at ingestion; reject goes to quarantine | Malformed request returns 422 with field-level errors, row appears in `quarantine` table, run table has no new row, no worker log |
| F3 | P0 | Classify admission (planned surgical / day-care / emergency / maternity); extract clinical + policy entities | Classifier output stored per run; tested on eval set |
| F4 | P0 | Retrieve every binding provision incl. waiting periods and exclusions far from the cover clause | Cataract case retrieves cover + waiting-period clause in the same run |
| F5 | P0 | Coverage position + indicative limit grounded in clauses, clause-level citations | Every claim maps to a citation `{clause_id, section, page, text_span}` |
| F6 | P0 | Route: `approve-recommended` / `query-to-hospital` / `medical-review` with reason | Routing rules in `02_ARCHITECTURE.md` section 6 |
| F7 | P1 | Escalate on conflicting provisions, possible pre-existing condition, or out-of-corpus procedure | Demo item 5 passes: no fabricated answer |
| F8 | P1 | Health, metrics and structured logs for whole pipeline | `/healthz`, `/readyz`, `/metrics` on every service; JSON logs |

## Agent system (A)

| ID | Pri | Requirement | Acceptance check |
|---|---|---|---|
| A1 | P0 | LangGraph (or CrewAI) reasoning layer. Retrieval is a tool the agent chooses. >=3 tools. Loop bounded by steps, tool calls, wall-clock | Tools: `search_corpus`, `get_clause(id)`, `get_request_fields`. Config limits tested by a unit test that forces a loop |
| A2 | P1 | >=2 agents, distinct responsibilities, defined hand-off; documented failure behaviour | Retrieval/Analysis agent + Verifier/Router agent; topology diagram + failure table in report |
| A3 | P0 | Verify every answer against retrieved passages before returning; every citation resolves; fail -> re-search differently or escalate | Unit test: injected fake citation is caught; unverified answer never returned |
| A4 | P0 | FastAPI, async runs, run-id returned immediately, poll status endpoint, queue/task runner between submission and execution; justify | `POST` returns 202 + `run_id`; `GET /v1/runs/{id}`; Redis + Celery/RQ/arq |
| A5 | P1 | Timeouts on every model/tool call; bounded retries with exponential backoff; circuit breaker; graceful degradation; incomplete run never returned as confident | Demo item 8 reproducible with `FAULT_MODE=provider_down` |
| A6 | P2 | Per-agent: task success rate, steps/tool calls per run, end-to-end and per-step latency, retry rate, container uptime, on dashboard | Grafana panels |
| A7 | P2 | `docker compose up --scale worker=3` works; measure throughput and p95 with stub; identify real bottleneck if no gain | Locust results table, bottleneck statement |
| A8 | P2 | Simple web client: submit, show recommendation + citations + escalation path | Static page served by the API or an nginx container |

## LLMOps (L)

| ID | Pri | Requirement | Acceptance check |
|---|---|---|---|
| L1 | P0 | LangChain/LlamaIndex orchestration; FAISS or Chroma; documented chunking + embedding strategy addressing the section-3 difficulty; re-embed without full rebuild | Incremental re-embed by content hash; `ingest --reembed --only <doc_id>` |
| L2 | P1 | Prompts as versioned artifacts; version recorded per response; compare >=2 variants on same eval set | `prompts/<name>/v1.yaml`, `v2.yaml`; comparison table in report |
| L3 | P1 | Fixed eval set >=20 scenarios with expected outcome + supporting passage incl. 4.1; batch CLI; TruLens or equivalent; groundedness, context relevance, faithfulness, hallucination rate, with computation stated; one deliberate change, before/after | `python -m evals.run --set evals/set_v1.jsonl` |
| L4 | P1 | Prompt-injection defence on every free-text field reaching a model; output filter blocks unauthorised determinations; toxicity detection on input and output | Demo item 7; unit tests with injection corpus |
| L5 | P2 | Prompt/completion tokens + cost recorded at call time, per step and per run; cost per 100 runs; largest driver | Cost table from DB |
| L6 | P3 | Feedback endpoint (satisfactory + reason) persisted, aggregated; auto-score sample of live runs; chart quality over time | `POST /v1/runs/{id}/feedback`; Grafana panel |

## Platform (D)

| ID | Pri | Requirement | Acceptance check |
|---|---|---|---|
| D1 | P0 | Published data contract for every external interface; validated before any agent starts; quarantine with field errors | See F2; contracts as JSON Schema + Pydantic models |
| D2 | P0 | Idempotent ingest pipeline (read, parse, chunk, embed, index) via CLI; freshness metadata + throughput as metrics | Running twice yields identical chunk count and no duplicates; `index_built_timestamp`, `index_chunks_total` gauges |
| D3 | P0 | >=4 services in Compose, one `docker compose up` from clean clone, healthchecks + `depends_on: condition: service_healthy`; justify boundaries | See architecture section 3 |
| D4 | P0 | No credentials/endpoints/model IDs in repo; `.env.example` | `git grep` secret scan passes; CI-style check script `scripts/check_secrets.sh` |
| D5 | P1 | Structured logs, correlation ID everywhere, OpenTelemetry -> Jaeger/Tempo, Prometheus scraping every service, Grafana dashboard (p50/p95, error rate, throughput, availability, per-container resources). Reconstruct any run from its id | Demo item 3; `GET /v1/runs/{id}/trace` returns every step |
| D6 | P1 | p95 SLO declared BEFORE measuring, justified; measure submission to final result; Locust with stub LLM; RPS/p50/p95 vs target; concurrency at which it fails + component responsible | `docs/SLO.md` committed first; `loadtest/` |
| D7 | P2 | Caching (embeddings/retrievals/whole runs), justified; per-client rate limiting; measured effect on p95 and cost | Before/after table; 429 with `Retry-After` |
| D8 | P1 | Runbook for two likely failure modes (symptom, confirmation, recovery); incident log with >=1 genuine real entry | `docs/RUNBOOK.md`, `docs/INCIDENTS.md` |

## Suggested prioritisation

1. **Week-two milestone (P0 only):** D3, D4, D1, F1, F2, D2, L1, A1, A4, F3, F4, F5, F6, A3, A8-lite. Cataract case passing.
2. **Then P1:** F7, A2, A5, L3, L4, L2, D5, D6, D8, F8.
3. **Then P2/P3** by remaining time: D7, A7, A6, L5, A8-polish, L6.

## Corpus (you choose)

One insurer, one retail health product. Download (a) the complete policy wording and (b) the same insurer's day-care procedure list. Prefer PDFs with a text layer; if scanned, OCR with `ocrmypdf` or Tesseract. Good picks are products whose wording clearly has a "Specific waiting periods" table listing cataract. Verify before committing to a product: find the clause that lists cataract (or ophthalmic) waiting period, the initial 30-day waiting period, the pre-existing disease waiting period, the permanent exclusions list, and room-rent / sub-limit provisions. Insurers' brochures and prospectuses are NOT policy wordings. Use the wording.

Keep a `corpus/MANIFEST.md` with insurer, product, UIN, version/date, source URL, SHA-256 of each file.
