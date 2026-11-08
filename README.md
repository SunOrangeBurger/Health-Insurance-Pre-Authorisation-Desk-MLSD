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

Place the policy wording PDF listed in `corpus/MANIFEST.md` at
`corpus/raw/optima_secure_policy_wording.pdf`. Raw policy documents are intentionally
not committed to GitHub.

### 2. Launch the System (deterministic offline profile)
```bash
docker compose --env-file ops/stub.compose --profile observability up --build -d
```

### 3. Verify Health
```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

### 4. Interactive Web Interface
Open `http://localhost:8000/` in your browser to submit synthetic pre-authorisation requests and inspect the live agent recommendation, citations, and verification trails.

### Observability

Start the source-controlled monitoring stack with:

```bash
docker compose --profile observability up --build -d
```

- Grafana dashboard: `http://localhost:3000` (local default `admin` / `admin`)
- Prometheus: `http://localhost:9090`
- Jaeger: `http://localhost:16686`
- Run reconstruction: `.venv/bin/python scripts/show_run.py <run_id>`

The default dashboard uses non-privileged service-process CPU/RSS metrics. The optional
`host-metrics` profile contains cAdvisor and should only be enabled after reviewing its
privileged host mounts.

### 5. Submit a Synthetic Request

```bash
ISSUE_DATE=$(date -d '-400 days' +%F)
ADMISSION_DATE=$(date -d '+7 days' +%F)
curl -sS -X POST http://localhost:8000/v1/preauth \
  -H 'Content-Type: application/json' \
  -H 'X-Correlation-ID: readme-demo' \
  -d "{\
    \"request_id\":\"DEMO-0001\",\
    \"policy_number\":\"SYN-POL-0001\",\
    \"policy_issue_date\":\"${ISSUE_DATE}\",\
    \"policy_start_date\":\"${ISSUE_DATE}\",\
    \"sum_insured\":500000,\
    \"patient_age\":44,\
    \"patient_gender\":\"F\",\
    \"admission_type\":\"day_care\",\
    \"planned_admission_date\":\"${ADMISSION_DATE}\",\
    \"diagnosis_text\":\"Synthetic cataract diagnosis\",\
    \"procedure_text\":\"Phacoemulsification with IOL\",\
    \"procedure_code\":\"SYN-001\",\
    \"room_category_requested\":\"single\",\
    \"estimated_cost\":75000,\
    \"hospital_id\":\"SYN-HOSP-001\",\
    \"prior_conditions\":[],\
    \"notes\":\"Synthetic demonstration request\"\
  }"
```

Poll the returned `poll_url` until the status is terminal. The worker runs the bounded
research and verifier/router graph, returns clause-level citations, and conservatively
routes unverified or out-of-corpus cases to `medical-review`.

### Local Tests with uv

```bash
uv venv --python 3.11
uv pip install --python .venv/bin/python -r requirements.txt \
  --extra-index-url https://download.pytorch.org/whl/cpu
.venv/bin/pytest -q
```

Published contracts are in `contracts/`; regenerate them with `make contracts` from the activated environment.

### Full acceptance demo

After placing the policy PDF and creating the uv environment above, run:

```bash
./scripts/demo_full.sh
```

The script builds the stack and proves all ten acceptance paths: health, a verified
recommendation, durable trace/Jaeger, malformed-input quarantine, out-of-corpus
escalation, fabricated-citation rejection, prompt-injection blocking, provider-outage
degradation and breaker recovery, the declared Locust SLO, and the 11/30-month
cataract flip. See [`docs/DEMO.md`](docs/DEMO.md) for expected output and manual commands.

### Evaluation and performance

```bash
make eval-compare                 # same 24 cases against prompt v1 and v2
make load                         # 10-user SLO check
```

Committed evidence is in `evals/results/` and `loadtest/results/`. The measured local
stub deployment passes its 10-user SLO at p95 0.98 s, first misses the 10 s threshold
at 80 users (p95 11 s), and improves from 8.93 to 28.76 completed runs/s at 40 users
when scaling from one to three workers. These are development-machine results, not
production capacity claims.

Submit human feedback with `POST /v1/runs/{run_id}/feedback`; the schema is published
in `contracts/feedback_response.schema.json` and the endpoint is visible at `/docs`.

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
- **Run Full Demo:** `make demo`
- **Prompt-Injection Demo:** `scripts/demo_07_prompt_injection.sh`
- **Circuit-Breaker Demo:** `scripts/demo_08_circuit_breaker.sh`

Operational recovery procedures are in [`docs/RUNBOOK.md`](docs/RUNBOOK.md). If the
API is not ready, first inspect `docker compose ps`, the one-shot `indexer` logs and
`GET /v1/index/status`; for provider failures, inspect the worker breaker metric and
restore the normal `ops/stub.compose` profile.
