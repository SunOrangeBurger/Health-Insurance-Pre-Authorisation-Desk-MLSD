.PHONY: all build up down restart logs test check-secrets ingest eval load clean

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

ingest:
	$(COMPOSE) run --rm indexer ingest

eval:
	python -m evals.run --set evals/set_v1.jsonl

load:
	locust -f loadtest/locustfile.py --headless -u 10 -r 2 --run-time 1m --host http://localhost:8000

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov index_data/
