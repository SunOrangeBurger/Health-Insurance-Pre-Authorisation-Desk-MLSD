# Operations Runbook

The original examples below use the deterministic local profile in `ops/stub.compose`. For the real-model internal desk, use the Windows/WSL procedure in INTERNAL_TOOL_DEMO.md and the additional instructions below. Keep stub capacity results separate from real Ollama results.

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

Compare Locust end-to-end p95 with `docs/SLO.md`. Inspect queue depth, completed-run RPS, worker CPU/RSS, retrieval cache metrics and provider latency in Grafana. The original stub workload measured 3.22× throughput at 40 users with three workers; this does not establish real-model scaling. The desk uses one shared Ollama inference slot, so extra workers cannot multiply GPU inference capacity. Re-run the matrix after any capacity change and retain the CSV evidence.

## Real-model desk on Windows

Keep Ubuntu WSL active. Run `scripts/start_ollama_wsl.ps1`, then the Compose wrapper documented in INTERNAL_TOOL_DEMO.md. The bounded profile requires `LLAMA_ARG_CACHE_RAM=0`, one loaded model, one parallel request and Qwen3 4B. If the launcher detects an unmanaged server, identify its owner before replacing it. Do not bypass that check or silently reuse an unbounded instance.

If load stops for low RAM, inspect Windows available memory and other applications. Preserve the configured reserve of max(2 GiB, 15% RAM); ask the operator to free memory rather than closing their applications. The Nov 17 retry showed stable model RSS near 720 MB while browser memory grew. Guard stops and in-flight unobserved cases are retained as incomplete tests.

Set `DESK_HOSPITAL_PASSWORD` for the synthetic seeded account, then run `scripts/benchmark_desk.py` with a new output directory. Compare `--workers 1` and `--workers 3` only after actually scaling Compose and confirming worker readiness. For a soak, use `--soak-minutes 5 --soak-rps <0.6-times-measured-sustainable-rate>`. Generate load summaries with `scripts/summarize_desk.py` and evaluate the soak JSON with `scripts/summarize_soak.py`. Never overwrite earlier failed runs. Percentiles with fewer than 100 observations provide weak p99 evidence.

To stop this project, use `scripts/compose_wsl.ps1 --profile observability stop`, preserving volumes. Stop only the Ollama PID recorded by the project launcher after verifying process identity. Leave shared Docker/WSL services and unrelated user applications running.


The final desk profile defaults to `QUEUE_CAPACITY=64` queued/running jobs. A shared Redis admission lock serializes enqueues across API replicas. At capacity or queue failure, a desk case remains visible with failed assessment and human-review routing; it cannot become an automated decision. The legacy run endpoint returns 503. Treat these outcomes as performance failures, not successful machine assessments. Start with one worker on this laptop: the matched three-worker experiment failed the error target without throughput gain. See INTERNAL_TOOL_PERFORMANCE.md before changing the deployment's supported workload.
