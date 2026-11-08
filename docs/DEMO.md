# Full Demo Guide

## Prerequisites

1. Put the policy PDF named in `corpus/MANIFEST.md` at `corpus/raw/optima_secure_policy_wording.pdf`.
2. Install Docker Compose, or Podman with its Docker-compatible wrapper.
3. Create the local tools environment with `uv venv --python 3.11` and install `requirements.txt` as shown in the README.

## One-command run

```bash
./scripts/demo_full.sh
```

The script is fail-fast and uses only synthetic records. It creates a temporary work directory and removes it on exit, while retaining database, trace and Locust evidence. Expect roughly 3–8 minutes when the image and index already exist; the initial model/image download can take longer.

## Acceptance sequence

| Step | Evidence printed by the script |
|---:|---|
| 1 | API/worker ready, Compose services, Prometheus and Grafana health |
| 2 | Completed valid request, verified route and resolved clause IDs |
| 3 | Durable per-node/tool/cost reconstruction and Jaeger service list |
| 4 | HTTP 422; run count unchanged; quarantine count increases; no worker job |
| 5 | Unknown procedure safely reaches unverified `medical-review` |
| 6 | Forced unsupported citation is rejected by the verifier |
| 7 | Injection is blocked with zero agent steps and zero model cost entries |
| 8 | Provider outage returns `degraded`, opens the breaker, then restores |
| 9 | Locust reports the declared 10-user end-to-end p95 SLO |
| 10 | Cataract changes from `waiting_period_not_served` at 11 months to `waiting_period_served` at 30 months |

Final links are Grafana `http://localhost:3000`, Prometheus `http://localhost:9090`, Jaeger `http://localhost:16686`, API docs `http://localhost:8000/docs`, and the web desk `http://localhost:8000/`.

## Focused commands

Run `scripts/demo_07_prompt_injection.sh` or `scripts/demo_08_circuit_breaker.sh` for only those fault paths. Reconstruct any run with `.venv/bin/python scripts/show_run.py <run_id>`. Run the fixed evaluation set with `make eval-compare`, and regenerate contracts with `make contracts`.

## Clean shutdown and recovery

```bash
docker compose --env-file ops/stub.compose --profile observability down
```

If a fault-mode run is interrupted, restore the healthy profile with:

```bash
docker compose --env-file ops/stub.compose --profile observability up -d --force-recreate
```

Detailed index and provider recovery procedures are in `docs/RUNBOOK.md`.
