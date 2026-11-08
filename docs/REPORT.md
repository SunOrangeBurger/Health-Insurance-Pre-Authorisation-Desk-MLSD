# Health Insurance Pre-Authorisation Desk: Project Report

**Course:** UE24AM342AA5 (ML System Design & AgentOps), PESU  
**Project:** Mini Project 03 — Health Insurance Pre-Authorisation Desk
**Insurer / Product:** HDFC ERGO my: Optima Secure (UIN: HDFHLIP26058V082526)
**Report Status:** In Progress — implementation through the 75% milestone; evaluation and load-test results remain pending.

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

*(To be filled after Phase 6. All numbers will come from real runs.)*

### Scenario Set
- File: `evals/set_v1.jsonl`
- Target: ≥ 20 scenarios across waiting periods, exclusions, sub-limits, day-care, maternity, emergency, out-of-corpus, adversarial.
- Reference case (Section 4.1): cataract at 11 months and 30 months (flip).

### Metrics Definitions
- **Groundedness:** supported atomic claims / total atomic claims (LLM-as-judge).
- **Context Relevance:** relevant retrieved passages / total retrieved passages; also reports clause recall against `expected_clause_ids`.
- **Faithfulness:** claims inferable from retrieved passages (NLI-style judge — method to be stated).
- **Hallucination Rate:** proportion of responses with ≥ 1 unsupported claim; separately counts invented provisions.

### Prompt Variant Comparison (v1 vs v2)
*(To be filled after Phase 6.)*

### Deliberate Change: Before vs After
*(To be filled after Phase 6.)*

---

## 6. Performance & SLO

*(To be filled after Phase 7. All numbers will come from real Locust runs with the stub LLM.)*

- **Declared SLO:** See `docs/SLO.md` (to be written and committed before any load test).
- **Locust Results:** RPS, p50, p95 at concurrencies: 1, 5, 10, 20, 40, 80.
- **Failing Concurrency & Bottleneck Component:** *(from Grafana + Locust.)*
- **Scaling Effect (`--scale worker=3`):** *(table: workers, RPS, p50, p95.)*
- **Caching Effect:** p95 and cost before/after retrieval cache.
- **Cost per 100 runs and largest driver:** *(notional cost using Ollama equivalent or published price.)*

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
| A7 | P2 | `--scale worker=3`; Locust throughput; bottleneck ID | 🔲 | Phase 7 |
| A8 | P2 | Web client: submit, show recommendation + citations | 🟡 | Phase 1 submit/poll UI; citation presentation waits for Phase 3 |

### LLMOps (L)
| ID | Pri | Requirement | Status | Notes |
|---|---|---|---|---|
| L1 | P0 | LangChain orchestration; FAISS/Chroma; chunking+embed strategy; incremental re-embed | ✅ | MiniLM + FAISS/BM25, stable hash, targeted re-embed |
| L2 | P1 | Versioned prompt artifacts; compare ≥ 2 variants | 🟡 | v1/v2 artifacts and recording complete; comparison is Phase 6 |
| L3 | P1 | ≥ 20 eval scenarios; batch CLI; 4 metrics; deliberate change | 🔲 | Phase 6 |
| L4 | P1 | Prompt-injection defence; output filter; toxicity detection | ✅ | Boundary detector, 12-case corpus, pre-model escalation, narrative filter |
| L5 | P2 | Token + cost recorded per call; cost per 100 runs | 🟡 | Per-call ledger complete; aggregate cost-per-100 awaits Phase 6/7 runs |
| L6 | P3 | Feedback endpoint; live scoring sample; quality chart | 🔲 | Phase 8 (if time) |

### Platform (D)
| ID | Pri | Requirement | Status | Notes |
|---|---|---|---|---|
| D1 | P0 | Published data contract for every interface; validated before agent starts | ✅ | Phase 1 schemas cover REST, queue and LLM adapter interfaces |
| D2 | P0 | Idempotent ingest CLI; freshness metrics | ✅ | 109 stable chunks across repeated runs; manifest + gauges |
| D3 | P0 | ≥ 4 services in Compose; one `docker compose up`; healthchecks | ✅ | Five healthy services verified on 2026-11-06 |
| D4 | P0 | No credentials in repo; `.env.example`; `check_secrets.sh` | ✅ | Phase 0 complete |
| D5 | P1 | OTel → Jaeger; Prometheus; Grafana; run reconstruction | ✅ | Both trace services visible; healthy scrape targets; `show_run.py` |
| D6 | P1 | SLO declared before measurement; Locust; RPS/p50/p95 | 🔲 | Phase 7 |
| D7 | P2 | Caching; rate limiting (429 + `Retry-After`) | 🟡 | Redis token bucket complete; caching benchmarks remain Phase 7 |
| D8 | P1 | Runbook (2 failure modes); incident log (≥ 1 real entry) | 🟡 | INCIDENTS.md has 3 real entries; RUNBOOK.md pending Phase 8 |
