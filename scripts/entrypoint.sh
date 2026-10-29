#!/usr/bin/env bash
set -e

case "$1" in
  api)
    echo "[entrypoint] Starting FastAPI application..."
    exec uvicorn preauth.api.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}"
    ;;
  worker)
    echo "[entrypoint] Starting background worker..."
    exec python -m preauth.worker
    ;;
  ingest)
    echo "[entrypoint] Running corpus ingestion and indexing..."
    shift
    exec python -m preauth.cli ingest "$@"
    ;;
  stub)
    echo "[entrypoint] Starting LLM stub service..."
    exec uvicorn preauth.llm.stub_service:app --host "0.0.0.0" --port "8080"
    ;;
  *)
    exec "$@"
    ;;
esac
