# Health Insurance Pre-Authorisation Desk: Project Report

**Course:** UE24AM342AA5 (ML System Design & AgentOps), PESU  
**Project:** Health Insurance Pre-Authorisation Desk  

---

## 1. Problem and Scope
- **Problem Statement:** Automated triage and decision support for health insurance pre-authorisation requests.
- **Out of Scope (What the system will not do):**
  - Will NEVER issue a final or binding legal authorisation or denial (only recommendations).
  - Will NEVER guess or hallucinate policy provisions when provisions are ambiguous, missing, or conflicting.
  - Will NEVER accept unverified citations or free-form ungrounded assertions.

## 2. Agent Design
- **Topology:** Intake/Classifier -> Policy Research Agent (tool-calling loop) -> Verifier & Router Agent.
- **Tools:** `search_corpus`, `get_clause`, `get_request_fields`.
- **Verification Strategy:** Deterministic citation resolution + mandatory provision checklist + claim entailment.
- **Loop Limits:** `MAX_STEPS=12`, `MAX_TOOL_CALLS=10`, `RUN_TIMEOUT_S=90`, `MAX_REPLANS=2`.
- **Failure Behavior Matrix:**
  *(To be populated with empirical outcomes).*

## 3. Architecture & Deployment Boundaries
- **Services:** `api`, `worker`, `redis`, `postgres`, `indexer`, `llm-stub`, `prometheus`, `grafana`, `jaeger`.
- **Deployment Boundaries Justification:**
  - API vs Worker separation (I/O light ingestion vs compute/LLM bound execution).
  - Indexer separate one-shot container (heavy CPU/memory embedding step).
  - LLM Stub isolation (enables benchmark testing independent of third-party API rate limits).

## 4. Key Design Decisions & Rejected Alternatives
- Summarized from `docs/DECISIONS.md`.

## 5. Evaluation Results
- **Scenario Set:** 20+ synthetic clinical & policy scenarios.
- **Metrics Summary Table:**
  - Groundedness
  - Context Relevance & Clause Recall
  - Faithfulness
  - Hallucination Rate (overall and invented provisions)
- **Prompt Variant Comparison (v1 vs v2):**
- **Deliberate Architectural Change (Before vs After):**

## 6. Performance & SLO Verification
- **Declared SLO Target (Declared in `docs/SLO.md` before testing):**
- **Locust Benchmark Results:**
- **Concurrency Bottleneck Analysis:**
- **Worker Scaling Results (`--scale worker=3`):**
- **Caching Impact:**
- **Cost Analysis (Cost per 100 runs & cost driver):**

## 7. Real Failures & Lessons Learned
- Real incidents extracted from `docs/INCIDENTS.md`.

## 8. Requirements Acceptance Matrix (P0 - P3)
- Detailed compliance status for all F, A, L, D requirements.
