# Demonstration Guide

## 7. Prompt injection

Run `scripts/demo_07_prompt_injection.sh`, poll the returned run, then read its trace. The expected terminal state is `escalated`, route `medical-review`, coverage position `guardrail_blocked`, and empty step/cost arrays because the text is stopped before model or tool access.

## 8. Circuit breaker

Run `scripts/demo_08_circuit_breaker.sh` and follow the printed commands. With `FAULT_MODE=provider_down`, the first bounded provider failure opens the demo-configured breaker; the run finishes `degraded` through retrieval-only fallback and never returns an HTTP 500 or confident recommendation. The worker metric must show `llm_circuit_breaker_state{provider="stub"} 1`.

## Observability

Start `docker compose --profile observability up -d`, send a synthetic request, and inspect:

- `http://localhost:16686` for `preauth-api` and `preauth-worker` spans;
- `http://localhost:9090/targets` for service scrape health;
- `http://localhost:3000` for the provisioned Pre-Authorisation Desk Overview dashboard;
- `python scripts/show_run.py <run_id>` for the durable request/tool/verification/cost reconstruction.

The remaining demo items will be completed in Phases 6–8.
