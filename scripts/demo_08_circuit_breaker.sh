#!/usr/bin/env bash
set -euo pipefail

echo "Start the fault demo with:"
echo "FAULT_MODE=provider_down LLM_PROVIDER=stub LLM_MAX_ATTEMPTS=1 CIRCUIT_FAILURE_THRESHOLD=1 docker compose up -d --force-recreate llm-stub worker"
echo "Submit a valid synthetic request, then inspect:"
echo "  curl -sS http://localhost:8000/v1/runs/<run_id>"
echo "  curl -sS http://localhost:8001/metrics | grep llm_circuit_breaker_state"
echo "Expected: status=degraded, route=medical-review, retrieval-only reason, breaker state=1."
echo "Recover with: FAULT_MODE=none docker compose up -d --force-recreate llm-stub worker"
