# Health Insurance Pre-Authorisation Desk

A production-style multi-agent health insurance pre-authorisation service built for ML System Design & AgentOps. The service accepts synthetic pre-authorisation requests over REST, validates them at the ingestion boundary, classifies the admission, and runs an asynchronous LangGraph agent system to retrieve binding policy provisions (cover clauses, specific waiting periods, exclusions, sub-limits, room-rent limits, and day-care lists) from retail health insurance policy wordings. It produces structured coverage recommendations with indicative limits and clause-level citations, always escalating to `medical-review` when provisions are absent, ambiguous, or unverified.

---

## Architecture Overview

```
Client (REST / Web)
        |
        v
  [ API Service ] (FastAPI - validation, contract check, quarantine)
        |
    (enqueue)
        v
    [ Redis ]
        |
    (dequeue)
        v
  [ Worker ] ---> [ Intake / Classifier ]
                        |
                        v
                 [ Policy Research Agent ] <-----+
                   (Tools: search, get_clause)   |
                        |                        | re-search strategy
                  Evidence Bundle                | (<= 2 replans)
                        v                        |
                 [ Verifier & Router Agent ] ----+
                        |
                 Verified Result
                        v
                 [ Postgres DB ]
```

---

## Quickstart

### Prerequisites
- Docker & Docker Compose (or Podman with `podman-compose`)
- Python 3.11+ (for local non-container development)

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env with your LLM configuration or use LLM_PROVIDER=stub for offline dev
```

### 2. Launch the System
```bash
docker compose up --build -d
```

### 3. Verify Health
```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

### 4. Interactive Web Interface
Open `http://localhost:8000/` in your browser to submit synthetic pre-authorisation requests and inspect the live agent recommendation, citations, and verification trails.

---

## Project Structure

```
├── contracts/          # Published data contracts (JSON Schema, OpenAPI)
├── corpus/             # Raw policy wordings, day-care lists, and manifest
│   ├── raw/            # Policy PDFs (gitignored)
│   └── MANIFEST.md     # Document provenance and SHA-256 hashes
├── docs/               # Project documentation, ADRs, runbook, incidents, and report
│   ├── brief/          # Project brief and assignment specifications
│   ├── DECISIONS.md    # Architecture Decision Records (ADRs)
│   ├── INCIDENTS.md    # Real failure and incident log
│   ├── PROGRESS.md     # Phase tracking and status
│   ├── REPORT.md       # Project submission report
│   ├── RUNBOOK.md      # Operational runbook
│   └── SLO.md          # Declared end-to-end latency SLO
├── evals/              # Evaluation dataset (20+ scenarios) and benchmark runner
├── loadtest/           # Locust load testing suite and stub service
├── ops/                # Prometheus configuration and Grafana dashboards
├── prompts/            # Versioned prompt artifacts (v1.yaml, v2.yaml)
├── scripts/            # Secret verification and demo scripts
├── src/preauth/        # Core application source code
│   ├── agents/         # LangGraph agents (researcher, verifier, tools)
│   ├── api/            # FastAPI app, endpoints, quarantine, rate limiting
│   ├── guardrails/     # Prompt injection, toxicity, and output sanitizers
│   ├── llm/            # Provider adapter, circuit breaker, retry, pricing
│   ├── obs/            # Logging, tracing, and Prometheus metrics
│   ├── rag/            # Chunking, embeddings, FAISS indexing, hybrid search
│   └── store/          # Database models, migrations, and repositories
└── web/                # Web UI client
```

---

## Operational Commands

- **Check Secrets:** `make check-secrets`
- **Run Tests:** `make test`
- **Corpus Ingestion:** `make ingest`
- **Run Evaluations:** `make eval`
- **Run Load Test:** `make load`
