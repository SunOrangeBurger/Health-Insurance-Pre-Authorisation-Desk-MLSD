# Policy Desk - 80% checkpoint demo

Open http://localhost:8000/ while the WSL workflow services are running.

Synthetic local accounts (not production credentials):

| Role | Email | Password |
|---|---|---|
| Hospital Staff | hospital@desk.local | Hospital-demo-2026 |
| Second hospital | hospital2@desk.local | Hospital-demo-2026 |
| Claims Reviewer | reviewer@desk.local | Reviewer-demo-2026 |

Hospital Staff can submit a structured request, filter/list their hospital's cases, read details/history, and respond to clarification. Claims Reviewers can approve, reject, or request information. Final decisions and reasons are visible to the submitting hospital. Revisions and decisions are retained in history. A stale or duplicate review is rejected.

The policy index now contains 109 chunks and the worker uses installed qwen2.5-coder:7b through Windows Ollama. A supported cataract case with a served waiting period receives an approve recommendation; uncertain/conflicting or unsupported cases require human review. The UI explanation comes from verified policy checks; raw model reasoning is retained in the audit record. Guarded automatic precedent decisions are enabled after a reviewer authorizes a reusable decision. Notes, prior conditions, emergencies, deluxe rooms, conflicting/changed policy evidence and mismatched material facts require review. Existing browser acceptance cases were one-off synthetic human decisions.

## Start through WSL

Keep an Ubuntu terminal open (`wsl -d Ubuntu`) while using the app. The standalone engine runs there; Docker Desktop is unnecessary.

From project PowerShell, start the WSL-bound model service first (exit an existing Ollama instance if it is bound to another interface):

```powershell
./scripts/start_ollama_wsl.ps1
./scripts/compose_wsl.ps1 up -d --no-deps postgres redis api worker
./scripts/compose_wsl.ps1 ps
```

The policy index has been restored. The monitoring stack has been verified. Multiworker, scaling and load/stress/soak tests remain later checkpoints. Avoid `down -v` unless intentionally deleting demo data.

## Repeat acceptance

With the local Python environment and Playwright installed:

```powershell
$env:DESK_HOSPITAL_PASSWORD = 'Hospital-demo-2026'
$env:DESK_REVIEWER_PASSWORD = 'Reviewer-demo-2026'
.venv/Scripts/python.exe scripts/verify_workflow_browser.py
.venv/Scripts/python.exe scripts/verify_workflow_api.py
```

These create synthetic cases and final human decisions in the local demo database. The browser test uses installed Microsoft Edge. Evidence is written under docs/evidence. Tests do not claim model quality or performance.

## Model and semantic evaluation evidence

Grounded acceptance: docs/evidence/grounded-model.json. Outage: docs/evidence/grounded-outage.json. Model digest and memory samples: docs/evidence/model-resources.json. Semantic fixture evaluation: evals/precedent_calibration.json (zero false matches, 50% positive recall on a tiny held-out set). These are local acceptance checks, not a capacity or production-quality claim.

Reproduce grounded acceptance with `.venv/Scripts/python.exe scripts/verify_grounded_model.py` after setting the demo hospital password above. Do not use `--outage` unless the worker has deliberately been pointed at a controlled unavailable endpoint.

## Reusable decisions and monitoring

Eligible review screens default to reusable; uncheck the box for a one-off decision. Reviewers can inspect and disable entries under Reusable decisions. An automatic case offers an override form; overriding also disables the originating precedent. An automatic decision does not train another precedent.

The desk Compose profile enables guarded automation; set PRECEDENT_AUTOMATION_ENABLED=false to opt out. Source defaults outside this profile remain off. The acceptance scripts disabled their own test precedents, so the next new scenario needs a fresh human reusable decision.

Live monitoring: Grafana http://localhost:3000/d/preauth-overview, Prometheus http://localhost:9090, Jaeger http://localhost:16686. Start the monitoring services with:

```powershell
./scripts/compose_wsl.ps1 --profile observability up -d --no-deps prometheus grafana jaeger redis-exporter
```

The desk Prometheus configuration intentionally excludes the unused stub and opt-in host-metrics services. Dashboard worker percentiles exclude queue and human time; current acceptance samples are too small to establish capacity.

Reproduce the complete precedent acceptance by running verify_precedent_flow.py first, then verify_precedent_browser.py (both require the demo password environment variables above). These create and alter synthetic cases/precedents. verify_monitoring.py checks the live targets, provisioned dashboard and received traces.
