# Health Insurance Pre-Authorisation Desk

A production-style multi-agent health insurance pre-authorisation service built for ML System Design & AgentOps. The service accepts synthetic pre-authorisation requests over REST, validates them at the ingestion boundary, classifies the admission, and runs an asynchronous LangGraph agent system to retrieve binding policy provisions (cover clauses, specific waiting periods, exclusions, sub-limits, room-rent limits, and day-care lists) from retail health insurance policy wordings. It produces structured coverage recommendations with indicative limits and clause-level citations, always escalating to `medical-review` when provisions are absent, ambiguous, or unverified.

## Faculty presentation

Follow **[demo.md - sequential faculty demonstration runbook](demo.md)** for the exact commands, browser links, usage demo, automated load demo, Grafana/Prometheus queries, presentation notes and shutdown sequence.

## Run the demos on Windows

Two demo modes are available: **Usage demo** (you submit and review cases) and **Load demo** (synthetic requests and simulated reviewer actions happen automatically while you watch the dashboards). Both use real local Ollama and the same application stack.

### Start services for either demo

Use Windows PowerShell 5.1 or PowerShell 7. The verified setup is Docker Engine inside Ubuntu WSL plus bounded Windows Ollama; Docker Desktop is unnecessary. The existing policy index, database and model downloads are reused.

In **terminal tab 1**, open Ubuntu and leave it running:

```powershell
wsl -d Ubuntu
```

If the Docker engine is not running, run `sudo systemctl start docker` inside Ubuntu.

In **terminal tab 2**, use PowerShell:

```powershell
Set-Location 'D:\Fedora-Recovery\Projects\mlsd-mini-project'
$env:DESK_HOSPITAL_PASSWORD = 'Hospital-demo-2026'
$env:DESK_REVIEWER_PASSWORD = 'Reviewer-demo-2026'
./scripts/demo_desk.ps1 -SkipIngest
```

Wait for startup to finish. `-SkipIngest` is appropriate for this machine's existing index. On a fresh setup, place the policy PDF specified in [the corpus manifest](corpus/MANIFEST.md), install the model/tooling described in [the setup guide](docs/INTERNAL_TOOL_DEMO.md), and omit `-SkipIngest` to build the index. If PowerShell blocks scripts, run `Set-ExecutionPolicy -Scope Process Bypass` in that PowerShell tab and retry.

### Links

Local links work while the corresponding services are running.

| Link | Purpose |
|---|---|
| [Policy Desk](http://localhost:8000/) | Hospital Staff and Claims Reviewer workspaces |
| [Grafana live demo dashboard](http://localhost:3000/d/preauth-overview?from=now-15m&to=now&refresh=5s) | Decisions, throughput, latency p50/p95/p99 and resource signals; refreshes every 5 seconds |
| [Grafana home](http://localhost:3000/) | Browse dashboards |
| [Prometheus query browser](http://localhost:9090/graph) | Run metric queries and inspect graphs |
| [Prometheus targets](http://localhost:9090/targets) | Check scrape-target health |
| [Jaeger traces](http://localhost:16686/) | Follow API/worker execution traces |
| [Interactive API docs](http://localhost:8000/docs) | Inspect and try API endpoints |
| [OpenAPI schema](http://localhost:8000/openapi.json) | Machine-readable API contract |
| [API readiness](http://localhost:8000/readyz) | Dependency readiness |
| [API liveness](http://localhost:8000/healthz) | Basic service health |
| [API metrics](http://localhost:8000/metrics) | Raw Prometheus-format API metrics |

### 1. Usage demo - submit and review a claim yourself

After starting the services above:

1. Open [Policy Desk](http://localhost:8000/) and click **Hospital Staff**.
2. Click **New request**, then **Fill sample claim**. Review the synthetic fields and click **Submit for assessment**.
3. Wait for processing, then sign out and choose **Claims Reviewer (Insurer)**.
4. Open the case and inspect the AI-generated summary, recommendation and policy citations.
5. Click **Accept AI suggestion**, or choose your own approve/reject/request-information outcome and record a reason. The reuse checkbox authorizes future equivalent decisions only when eligibility checks pass.
6. Sign back in as Hospital Staff to see the decision or respond to clarification. A later equivalent request can use an authorized precedent; exceptions still require review.

Demo accounts use `hospital@desk.local` / `Hospital-demo-2026` and `reviewer@desk.local` / `Reviewer-demo-2026`; the role buttons sign in with these public synthetic credentials. Historical cases can lack the newer AI summary, so submit a fresh claim for that feature. Detailed walkthrough: [HOW_TO_RUN.md](docs/HOW_TO_RUN.md).

### 2. Load demo - hands-free traffic and dashboard observation

With the services already running, start a paced **15-minute** background demo from project PowerShell:

```powershell
./scripts/start_traffic_demo.ps1 -Minutes 15 -IntervalSeconds 8
```

The runner creates synthetic cases, simulates reviewer approvals/rejections, enables eligible precedents, exercises automatic approval/rejection and handles clarification and exception cases. It acts only on its own cases. The interval is a pause between scenarios, in addition to processing/reviewer time; only one claim is processed at a time. This is presentation traffic, not a stress-test capacity claim.

Open [Grafana](http://localhost:3000/d/preauth-overview?from=now-15m&to=now&refresh=5s) and watch **Case decisions per minute - reviewer vs precedent** and **Decisions since service start** at the top, followed by the existing worker latency/throughput panels. Allow about a minute for rate curves to develop.

In [Prometheus](http://localhost:9090/graph), try these expressions individually:

```promql
sum by (outcome, source) (preauth_case_decisions_total)
sum by (outcome, source) (rate(preauth_case_decisions_total[2m])) * 60
sum by (status) (rate(preauth_worker_runs_total[2m]))
histogram_quantile(0.95, sum by (le) (rate(preauth_worker_run_seconds_bucket[5m])))
```

`human` denotes reviewer-account decisions, including the demo's explicitly simulated reviewer. `precedent` denotes automatic reuse. These are process counters that reset on restart and include manual activity too. Worker latency excludes queue wait and simulated reviewer think time.

Check whether traffic is actually running and how many claims it has generated:

```powershell
./scripts/status_traffic_demo.ps1
```

The launcher checks **available** RAM before starting and confirms the first submitted claim. It refuses to launch below the reserve. A background process can still stop later if resources change; the status command reports the last stop reason. A successful app startup alone does not generate traffic.

For visible events and stop messages in the same terminal, start the load demo with `./scripts/start_traffic_demo.ps1 -Minutes 15 -IntervalSeconds 8 -Foreground` instead of the background command.

Optional live console log:

```powershell
Get-Content .runtime/traffic-demo/console.log -Wait
```

Stop **only automated traffic**, keeping the app and dashboards available:

```powershell
./scripts/stop_traffic_demo.ps1
```

The runner drains its current assessment and disables its temporary precedents. It also stops automatically after its configured duration. Keep enough RAM free: the guard pauses/stops traffic below max(2 GiB, 15% physical RAM), about 2.36 GiB on this laptop. For other durations, cleanup/recovery details and formal benchmark pointers, see [AUTOMATED_DEMO.md](docs/AUTOMATED_DEMO.md) and [measured performance](docs/INTERNAL_TOOL_PERFORMANCE.md).

### Stop everything after either demo

```powershell
./scripts/stop_desk.ps1
```

This stops demo traffic first, then project containers and the verified managed Ollama server. Your database, policy index and model downloads are preserved. Close the Ubuntu tab afterward. Shared Docker/WSL infrastructure is not forcibly shut down; do not use `down -v` unless you intend to delete project volumes.

### Documentation and evidence

- [Full technical PDF](output/pdf/Policy_Desk_Technical_Document.pdf) and [editable manuscript](docs/TECHNICAL_DOCUMENT.md).
- [Windows startup/shutdown guide](docs/HOW_TO_RUN.md), [accounts and model setup](docs/INTERNAL_TOOL_DEMO.md), and [automated demo guide](docs/AUTOMATED_DEMO.md).
- [Performance results and limitations](docs/INTERNAL_TOOL_PERFORMANCE.md), [progress checkpoints](docs/INTERNAL_TOOL_PROGRESS.md), and [operations runbook](docs/RUNBOOK.md).
- [Configured GitHub repository](https://github.com/SunOrangeBurger/Health-Insurance-Pre-Authorisation-Desk-MLSD) and [internal desk branch](https://github.com/SunOrangeBurger/Health-Insurance-Pre-Authorisation-Desk-MLSD/tree/codex/internal-policy-desk).

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

## Internal tool preview

The hospital/reviewer workspace is complete for the user-adjusted synthetic demonstration scope. See [local demo and accounts](docs/INTERNAL_TOOL_DEMO.md), [progress/evidence](docs/INTERNAL_TOOL_PROGRESS.md) and [measured performance and limitations](docs/INTERNAL_TOOL_PERFORMANCE.md). It uses Qwen3 4B through bounded local Ollama, human-authorized precedent automation, a capped queue and monitored WSL deployment. The requested five-minute stability check passed; longer soak reliability remains unverified. One worker is recommended locally: three workers failed the error target without improving throughput. This is a demonstration, not a clinically validated system.

## Offline stub development quickstart

This older development profile is separate from the Windows/Ollama demos above.

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

### Persistent live-dashboard demo

To keep synthetic requests flowing while presenting Grafana and Jaeger, run:

```bash
make demo-live
```

The generator runs until Ctrl+C, continuously mixes successful, waiting-period,
room-query, PED, maternity, out-of-corpus, injection and malformed scenarios, polls
accepted runs to terminal state, and periodically records synthetic feedback. Grafana
refreshes every five seconds at `http://localhost:3000/d/preauth-overview`. Stopping
the generator intentionally leaves the stack and dashboards running.

Tune it without editing code:

```bash
RATE=2 MAX_IN_FLIGHT=30 DURATION_SECONDS=300 make demo-live
```

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
- **Run Persistent Dashboard Demo:** `make demo-live`
- **Prompt-Injection Demo:** `scripts/demo_07_prompt_injection.sh`
- **Circuit-Breaker Demo:** `scripts/demo_08_circuit_breaker.sh`

Operational recovery procedures are in [`docs/RUNBOOK.md`](docs/RUNBOOK.md). If the
API is not ready, first inspect `docker compose ps`, the one-shot `indexer` logs and
`GET /v1/index/status`; for provider failures, inspect the worker breaker metric and
restore the normal `ops/stub.compose` profile.

## Full technical reference

The [35-page technical PDF](output/pdf/Policy_Desk_Technical_Document.pdf) covers architecture, APIs, persistence, security, AI safeguards, reviewer assistance, deployment and measured evaluation. The [editable manuscript](docs/TECHNICAL_DOCUMENT.md) and [ReportLab build script](scripts/build_technical_pdf.py) are included. The v2 reviewer summary has functional acceptance; the historical load/soak matrix used v1 and is labeled accordingly.

For daily use on this Windows machine, see the [start/stop and demo walkthrough](docs/HOW_TO_RUN.md). Stop the stack and its managed model with `./scripts/stop_desk.ps1`.

For hands-free dashboard activity, use `./scripts/start_traffic_demo.ps1` after starting the app. See the [automated demonstration guide](docs/AUTOMATED_DEMO.md).
