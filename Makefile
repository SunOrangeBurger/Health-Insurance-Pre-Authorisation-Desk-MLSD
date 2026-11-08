.PHONY: all build up down restart logs test contracts check-secrets ingest eval eval-compare load demo clean

SHELL := /usr/bin/env bash
COMPOSE ?= docker compose

all: build

check-secrets:
	./scripts/check_secrets.sh

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down -v

restart:
	$(COMPOSE) down && $(COMPOSE) up -d

logs:
	$(COMPOSE) logs -f

test:
	pytest tests/ -v

contracts:
	PYTHONPATH=src python scripts/export_contracts.py

ingest:
	$(COMPOSE) run --rm indexer ingest

eval:
	python -m evals.run --set evals/set_v1.jsonl --prompt-version v2

eval-compare:
	python -m evals.run --set evals/set_v1.jsonl --prompt-version v1 --out evals/results/eval_v1.json
	python -m evals.run --set evals/set_v1.jsonl --prompt-version v2 --out evals/results/eval_v2.json

load:
	locust -f loadtest/locustfile.py --headless -u 10 -r 10 --run-time 30s --host http://localhost:8000 --csv loadtest/results/u10

demo:
	./scripts/demo_full.sh

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov index_data/
