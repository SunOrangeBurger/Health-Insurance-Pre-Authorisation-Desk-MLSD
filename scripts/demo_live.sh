#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

read -r -a compose_cmd <<< "${COMPOSE:-docker compose --env-file ops/stub.compose}"
PYTHON="${PYTHON:-.venv/bin/python}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
RATE="${RATE:-1}"
MAX_IN_FLIGHT="${MAX_IN_FLIGHT:-20}"
DURATION_SECONDS="${DURATION_SECONDS:-0}"
FEEDBACK_EVERY="${FEEDBACK_EVERY:-5}"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Missing ${PYTHON}; create it with: uv venv --python 3.11" >&2
  exit 1
fi

echo "Starting the persistent demo stack..."
"${compose_cmd[@]}" --profile observability up --build -d

for _ in $(seq 1 180); do
  if curl -fsS "${BASE_URL}/readyz" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "${BASE_URL}/readyz" >/dev/null

cat <<EOF

Persistent live demo is ready.
  Web desk:   ${BASE_URL}/
  API docs:   ${BASE_URL}/docs
  Grafana:    http://localhost:3000/d/preauth-overview
  Prometheus: http://localhost:9090
  Jaeger:     http://localhost:16686

Traffic rate: ${RATE} submissions/second (maximum ${MAX_IN_FLIGHT} in flight)
Duration:     $([[ "${DURATION_SECONDS}" == "0" ]] && echo "until Ctrl+C" || echo "${DURATION_SECONDS} seconds")

The containers remain running after the generator stops so the dashboards stay visible.
Press Ctrl+C to stop generating requests.

EOF

exec "${PYTHON}" scripts/live_traffic.py \
  --base-url "${BASE_URL}" \
  --rate "${RATE}" \
  --max-in-flight "${MAX_IN_FLIGHT}" \
  --duration "${DURATION_SECONDS}" \
  --feedback-every "${FEEDBACK_EVERY}"
