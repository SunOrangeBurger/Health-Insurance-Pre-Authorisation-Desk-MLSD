# Operations Runbook

All examples use the deterministic local profile in `ops/stub.compose`.

## Provider unavailable or circuit breaker open

**Symptoms:** runs become `degraded` and route to `medical-review`; provider failures increase; `llm_circuit_breaker_state{provider="stub"}` is `1`. This is safe behavior: retrieved evidence is retained, but no confident recommendation is emitted.

**Diagnose:** inspect `docker compose logs worker llm-stub`, query the worker metrics on port 8001 from inside the container, and use `scripts/show_run.py <run_id>` to confirm the provider failure and preserved evidence.

**Recover:** correct `LLM_BASE_URL`/credentials or restore the provider, then run `docker compose --env-file ops/stub.compose --profile observability up -d --force-recreate`. Wait for `/readyz`; after the configured cooldown, one half-open probe closes the breaker. Do not manually convert degraded recommendations into approvals.

## Index missing, stale, or corrupt

**Symptoms:** `/readyz` fails, `/v1/index/status` reports missing/stale state, the indexer exits non-zero, or workers safely escalate because citations cannot resolve.

**Diagnose:** verify the raw PDF path and SHA-256 against `corpus/MANIFEST.md`, inspect `docker compose logs indexer`, and check the index manifest. Do not bypass readiness or point a worker at a partially written index.

**Recover:** replace the PDF only with the documented source, then run:

```bash
docker compose --env-file ops/stub.compose run --rm indexer
docker compose --env-file ops/stub.compose up -d --force-recreate worker api
curl -fsS http://localhost:8000/readyz
curl -fsS http://localhost:8000/v1/index/status
```

Ingestion publishes atomically and uses stable hashes, so unchanged chunks retain their vectors. If the checksum still differs, stop and investigate provenance rather than accepting an unknown corpus.

## Capacity or latency alert

Compare Locust end-to-end p95—not POST latency—with `docs/SLO.md`. Inspect queue depth, completed-run RPS, worker CPU/RSS, retrieval cache metrics and provider latency in Grafana. The verified first mitigations are enabling retrieval cache and scaling the stateless worker; this project measured 3.22× throughput at 40 users with three workers. Re-run the matrix after any capacity change and retain the CSV evidence.
