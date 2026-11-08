# Health Insurance Pre-Authorisation Desk: Project Report

**Course:** UE24AM342AA5 (ML System Design & AgentOps), PESU  
**Project:** Mini Project 03 — Health Insurance Pre-Authorisation Desk
**Insurer / Product:** HDFC ERGO my: Optima Secure (UIN: HDFHLIP26058V082526)
**Report Status:** Complete — all planned phases and acceptance evidence finished on 2026-11-08.

---

## 1. Problem and Scope

### Problem Statement
Health insurance pre-authorisation is a manual, time-consuming process where a TPA (Third-Party Administrator) desk officer must check whether a planned admission is covered under the insurer's policy wording before approving hospitalisation. This involves reviewing cover clauses, waiting periods, exclusions, sub-limits, and day-care eligibility — all of which may appear in different, non-adjacent sections of a lengthy policy document.

This project builds a **multi-agent automated pre-authorisation recommendation system** that accepts a synthetic admission request over REST, retrieves all binding policy provisions using a LangGraph RAG agent pipeline, and returns a structured coverage recommendation with clause-level citations.

### What This System Does NOT Do
- It **never** issues a final or legally binding authorisation or denial.
- It **never** guesses or invents policy provisions — if provisions cannot be verified, it escalates.
- It **never** processes real patient data — all inputs are synthetic.
- It does not replace the medical officer who makes the final decision.

---

## 2. Agent Design

### Topology

```
POST /v1/preauth
      |
  [Intake / Classifier Node]
      |
  [Agent 1: Policy Research Agent]   <── re-search (≤ MAX_REPLANS times) ──┐
   Tools: search_corpus, get_clause,                                        │
          get_request_fields                                                 │
      |                                                                      │
  Evidence Bundle (typed, persisted)                                         │
      |                                                                      │
  [Agent 2: Verifier & Router Agent] ────────────────────────────────────────┘
      |
  Verified Result → Postgres → GET /v1/runs/{id}
```

### Tools (Agent 1)
| Tool | Description |
|---|---|
| `search_corpus(query, filters)` | Hybrid dense+BM25 retrieval with provision-type filter |
| `get_clause(clause_id)` | Direct clause lookup by ID |
| `get_request_fields(keys)` | Access structured fields from the admission request |

### Loop Limits (env-configurable)
| Variable | Default | Purpose |
|---|---|---|
| `MAX_STEPS` | 12 | Maximum LangGraph steps |
| `MAX_TOOL_CALLS` | 10 | Maximum tool invocations per run |
| `RUN_TIMEOUT_S` | 90 | Wall-clock timeout for the full run |
| `LLM_TIMEOUT_S` | 20 | Per-LLM-call timeout |
| `TOOL_TIMEOUT_S` | 5 | Per-tool-call timeout |
| `MAX_REPLANS` | 2 | Maximum Verifier re-search iterations |

### Failure Behaviour
| Failure | Behaviour |
|---|---|
| Agent 1 exceeds step/tool/time budget | Returns partial bundle flagged `incomplete`; Agent 2 forces `medical-review` |
| Agent 1 crashes | Job retried once from last checkpoint; then `failed` + `medical-review` |
| Agent 2 crashes or times out | Run marked `degraded`; evidence bundle returned with `route=medical-review`, `verification.passed=false` |
| Provider down (circuit open) | Retrieval-only evidence, `medical-review`, `verification.passed=false`, terminal status `degraded` |

---

## 3. Architecture & Deployment Boundaries

The deployed boundary is API → Redis/arq → worker, with PostgreSQL for durable run/step/cost state and a one-shot indexer publishing a read-only FAISS volume. Prometheus/Grafana and Jaeger are separate observability services. The research and verifier agents intentionally share one worker process.

### Services
| Service | Role | Scales? |
|---|---|---|
| `api` | FastAPI — contract validation, quarantine, enqueue, status, metrics | Yes (stateless) |
| `worker` | LangGraph agent runner — consumes arq jobs | Yes (`--scale worker=3`) |
| `redis` | Queue, cache, rate-limit counters | No |
| `postgres` | Runs, steps, quarantine, feedback, cost ledger | No |
| `indexer` | One-shot ingest pipeline — parse, chunk, embed, index | One-shot |
| `llm-stub` | Fixed-delay LLM responses for load tests (`STUB_DELAY_MS`, `FAULT_MODE`) | Yes |
| `prometheus` | Metrics scraper | No |
| `grafana` | Provisioned dashboards | No |
| `jaeger` | OTel trace backend | No |
| `cadvisor` | Per-container resource metrics | No |

### Deployment Boundary Justifications
- **api vs worker:** API is I/O-light (validation, queueing); workers are LLM-bound and long-running. A stuck worker must not affect the submission endpoint.
- **worker vs redis/postgres:** Stateful stores have different resource profiles and must not be restarted with workers.
- **indexer separate:** Embedding is CPU/RAM heavy and runs once; workers mount the resulting FAISS index read-only. Separating them allows index rebuilds without restarting workers.
- **llm-stub separate:** Must be swappable by config (`LLM_PROVIDER=stub`) without any application code change. Measures our system, not provider limits.
- **Retrieval Agent + Verifier Agent in same worker process:** Both agents run within the same LangGraph graph and worker container. This is stated honestly — they share a deployment boundary. A separate `verifier` service is a possible later enhancement but is not claimed here.

---

## 4. Key Design Decisions & Rejected Alternatives

*(Full ADR details in [docs/DECISIONS.md](DECISIONS.md).)*

| Decision | Chosen | Rejected |
|---|---|---|
| Agent framework | LangGraph | CrewAI (insufficient loop-bound control) |
| Job queue | Redis + arq | Celery (heavier, asyncio friction), RQ (not async-native) |
| Vector index | FAISS + `all-MiniLM-L6-v2` | Paid APIs (ruled out by rule 10), Chroma (acceptable alternative) |
| State storage | PostgreSQL 16 | SQLite (concurrent write locking) |
| Corpus | HDFC ERGO Optima Secure | Star Health (denser PDF), Care Supreme (scanned version) |
| Container runtime | Podman + podman-compose | Docker CE (not installed), nerdctl (not installed) |
| LLM provider | Ollama (local) | Gemini / Groq (require API keys) |

---

## 5. Evaluation Results

### Reliability and Observability Baseline (Phases 4–5)

The input boundary applies deterministic injection and toxicity checks before model access. A flagged request is redacted in the agent payload and escalated without tool calls. Provider calls use bounded exponential backoff with jitter and a closed/open/half-open circuit breaker. A provider outage preserves retrieval evidence but forces `degraded`, `medical-review`, and failed verification.

OpenTelemetry spans are exported to Jaeger for the API, worker, graph nodes, provider call and tools. Prometheus collects request, worker, agent, tool, provider, breaker, guardrail, rate-limit, index, cost and process metrics. Grafana provisioning is source-controlled. The default stack does not grant privileged host access: process CPU/RSS is graphed; cAdvisor is an explicit `host-metrics` profile.

Verified synthetic runs on 2026-11-08:

| Case | Run ID | Outcome |
|---|---|---|
| Provider healthy | `6efe7802-ed6a-44b0-b8a9-a40276da5d2d` | `completed`; 19 trace steps; token/cost ledger entry |
| Prompt injection | `63fb3a3c-26b8-417a-ad69-43b44d1ac4c3` | `escalated`; blocked before model/tool access |
| Provider down | `d21f389e-1efd-4f5f-b118-9b674df15d08` | `degraded`; retrieval-only medical review; breaker open |

### Scenario Set
- File: `evals/set_v1.jsonl`
- 24 fixed scenarios across waiting periods, exclusions, room limits, day-care, maternity, emergency, out-of-corpus, and adversarial inputs.
- Reference case (Section 4.1): cataract at 11 months and 30 months (flip).

### Metrics Definitions
- **Groundedness:** supported atomic claims / total atomic claims (LLM-as-judge).
- **Context Relevance:** relevant retrieved passages / total retrieved passages; also reports clause recall against `expected_clause_ids`.
- **Faithfulness:** claims inferable from retrieved passages (NLI-style judge — method to be stated).
- **Hallucination Rate:** proportion of responses with ≥ 1 unsupported claim; separately counts invented provisions.

### Prompt Variant Comparison (v1 vs v2)

Both variants ran against the same 24-case set and live asynchronous API. V2 adds provision-type-filtered retrieval.

| Metric | v1 | v2 |
|---|---:|---:|
| Routing accuracy | 0.7083 | 0.7500 |
| Coverage-position accuracy | 0.7500 | 0.7917 |
| Groundedness / faithfulness | 1.0000 / 1.0000 | 1.0000 / 1.0000 |
| Context relevance | 0.6250 | 0.6250 |
| Clause recall / citation resolution | 1.0000 / 1.0000 | 1.0000 / 1.0000 |
| Correct escalation | 0.6111 | 0.6667 |
| False-approval rate | 0.2917 | 0.2500 |

V2 was retained because it improved routing and reduced the costly false-approval error without reducing citation quality.

### Deliberate Change: Before vs After

A conservative applicability gate was added after reviewing V2 failures: unmatched exclusion terms, maternity ambiguity and room-schedule eligibility must escalate rather than inherit unrelated retrieved text. On the same set, routing accuracy improved from 0.7500 to 1.0000, position accuracy from 0.7917 to 0.9167, correct escalation from 0.6667 to 1.0000, and false approvals fell from 0.2500 to 0.0000. Groundedness, faithfulness, clause recall and citation resolution remained 1.0000. Results are committed as `eval_v2.json` and `eval_v2_final.json`.

---

## 6. Performance & SLO

- **Declared SLO:** committed in `docs/SLO.md` before measurement: p95 ≤ 10 s at 10 users and valid-run errors < 1%.
- **Machine/profile:** Intel i7-13620H, 10 cores/16 threads, 15 GiB RAM; one worker unless stated; stub delay 250 ms + up to 50 ms jitter.

| Users | Completed RPS | p50 ms | p95 ms | Error rate | SLO |
|---:|---:|---:|---:|---:|---|
| 1 | 1.65 | 430 | 800 | 0% | pass |
| 5 | 7.00 | 480 | 850 | 0% | pass |
| 10 | 9.64 | 850 | 980 | 0% | pass |
| 20 | 9.39 | 1,900 | 2,100 | 0% | pass |
| 40 | 8.93 | 3,900 | 4,800 | 0% | pass |
| 80 | 7.14 | 7,900 | 11,000 | 0% | **fail** |

The first tested miss is 80 users. Throughput plateaus near one-worker capacity while queueing raises end-to-end latency; POST and polling remain comparatively responsive, identifying worker-side retrieval/agent processing as the bottleneck.

| 40-user configuration | Completed RPS | p50 | p95 |
|---|---:|---:|---:|
| 1 worker | 8.93 | 3.90 s | 4.80 s |
| 3 workers | 28.76 | 1.20 s | 1.50 s |

At 10 users, disabling the retrieval LRU cache produced 5.36 completed runs/s and p95 2.00 s; enabling it produced 9.64 runs/s and p95 0.96 s. The stub price configuration is intentionally $0, so the measured cost is $0 per 100 runs; the ledger and configurable pricing map are implemented, but no paid-provider price is claimed. Retrieval/embedding CPU and provider calls are the principal real resource drivers.

---

## 7. Real Failures & Lessons Learned

*(Full details in [docs/INCIDENTS.md](INCIDENTS.md).)*

| Incident | Root Cause | Fix |
|---|---|---|
| INC-001: git root at wrong level | Parent `~/Projects/.git` shadowed project repo | `git init` inside project dir |
| INC-002: `check_secrets.sh` regex errors | `git grep` positional vs `-e` flag; invalid char-class range | Used `-e "${PATTERN}"` consistently; reordered character class |
| INC-003: `docker` not found | Docker CE not installed; only Podman present | Installed podman-compose; created docker/docker-compose symlinks |

---

## 8. Requirements Acceptance Matrix

*(Status updated as phases complete. Abbreviations: ✅ Done, 🟡 Partial, 🔲 Not started, ❌ Not attempted.)*

### Product Behaviour (F)
| ID | Pri | Requirement | Status | Notes |
|---|---|---|---|---|
| F1 | P0 | `POST /v1/preauth` with published contract, OpenAPI at `/docs` | ✅ | Phase 1; JSON Schema and OpenAPI exported |
| F2 | P0 | Schema + range + categorical + cross-field validation; quarantine | ✅ | Phase 1; verified 422 and quarantine-only write |
| F3 | P0 | Admission classifier; entity extraction; stored per run | ✅ | Phase 3 classifier and persisted trace |
| F4 | P0 | Retrieve cover + waiting periods + exclusions in same run | ✅ | Cataract E2E retrieves B.1.1 + C.1.b and modifying searches |
| F5 | P0 | Coverage position + indicative limit + clause-level citations | ✅ | Verified structured result |
| F6 | P0 | Route: `approve-recommended` / `query-to-hospital` / `medical-review` | ✅ | Deterministic verifier/router |
| F7 | P1 | Escalate on conflict / possible PED / out-of-corpus | ✅ | PED, out-of-corpus, guardrail and degraded-provider paths escalate safely |
| F8 | P1 | Health, metrics, structured logs on every service | ✅ | Health/readiness, JSON logs, Prometheus and OTel verified |

### Agent System (A)
| ID | Pri | Requirement | Status | Notes |
|---|---|---|---|---|
| A1 | P0 | LangGraph, ≥ 3 tools, loop bounded | ✅ | Four typed tools; step/tool/time bounds tested |
| A2 | P1 | ≥ 2 agents, distinct responsibilities, hand-off | ✅ | Researcher + verifier/router with EvidenceBundle |
| A3 | P0 | Verify every answer; citation resolution; fail → re-search | ✅ | Fake citation and bounded retry tests pass |
| A4 | P0 | FastAPI async; 202 + `run_id`; poll endpoint; Redis + arq | ✅ | Phase 1 end-to-end path verified |
| A5 | P1 | Timeouts, retry+backoff, circuit breaker, graceful degradation | ✅ | Phase 4; live provider-down fault test passed |
| A6 | P2 | Per-agent Grafana dashboard | ✅ | Provisioned dashboard populated by real synthetic traffic |
| A7 | P2 | `--scale worker=3`; Locust throughput; bottleneck ID | ✅ | 3.22× RPS at 40 users; worker saturation identified |
| A8 | P2 | Web client: submit, show recommendation + citations | ✅ | Submit/poll UI renders the structured recommendation and citations |

### LLMOps (L)
| ID | Pri | Requirement | Status | Notes |
|---|---|---|---|---|
| L1 | P0 | LangChain orchestration; FAISS/Chroma; chunking+embed strategy; incremental re-embed | ✅ | MiniLM + FAISS/BM25, stable hash, targeted re-embed |
| L2 | P1 | Versioned prompt artifacts; compare ≥ 2 variants | ✅ | Same-set v1/v2 comparison committed |
| L3 | P1 | ≥ 20 eval scenarios; batch CLI; 4 metrics; deliberate change | ✅ | 24 cases; nine metrics; before/after gate measured |
| L4 | P1 | Prompt-injection defence; output filter; toxicity detection | ✅ | Boundary detector, 12-case corpus, pre-model escalation, narrative filter |
| L5 | P2 | Token + cost recorded per call; cost per 100 runs | ✅ | Ledger plus measured $0/100 stub-profile cost |
| L6 | P3 | Feedback endpoint; live scoring sample; quality chart | ✅ | Persisted feedback API and Prometheus quality metric |

### Platform (D)
| ID | Pri | Requirement | Status | Notes |
|---|---|---|---|---|
| D1 | P0 | Published data contract for every interface; validated before agent starts | ✅ | Phase 1 schemas cover REST, queue and LLM adapter interfaces |
| D2 | P0 | Idempotent ingest CLI; freshness metrics | ✅ | 109 stable chunks across repeated runs; manifest + gauges |
| D3 | P0 | ≥ 4 services in Compose; one `docker compose up`; healthchecks | ✅ | Five healthy services verified on 2026-11-06 |
| D4 | P0 | No credentials in repo; `.env.example`; `check_secrets.sh` | ✅ | Phase 0 complete |
| D5 | P1 | OTel → Jaeger; Prometheus; Grafana; run reconstruction | ✅ | Both trace services visible; healthy scrape targets; `show_run.py` |
| D6 | P1 | SLO declared before measurement; Locust; RPS/p50/p95 | ✅ | Predeclared SLO and 1–80 user matrix committed |
| D7 | P2 | Caching; rate limiting (429 + `Retry-After`) | ✅ | Redis token bucket and paired cache benchmark complete |
| D8 | P1 | Runbook (2 failure modes); incident log (≥ 1 real entry) | ✅ | Provider/index recovery runbook plus real incident log |
