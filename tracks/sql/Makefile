# SQL track (DuckDB). Same targets in every track: install, lint, test, coverage, run, report, gate.
# The analysis lives in sql/*.sql; churncast_sql/ is a thin runner (variables, checks, the logistic fit, JSON).
PY ?= .venv/bin/python
DATA ?= ../../data/raw/2026-05
OUT ?= out

.PHONY: install lint test coverage run report gate clean
install:
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements-dev.txt

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	$(PY) -m sqlfluff lint sql/*.sql
	$(PY) -m sqlfluff lint --config .sqlfluff-checks sql/checks

test:            ## unit tests (fast, tiny fixtures)
	$(PY) -m pytest tests/unit

coverage:        ## unit + data/model tests on the real export, 85 % line coverage gate
	$(PY) -m pytest tests --cov --cov-report=term --cov-report=xml --cov-fail-under=85

run:             ## features.csv, metrics.json, model.json, experiments.jsonl for one export
	$(PY) -m churncast_sql run --data $(DATA) --out $(OUT)

report:          ## the SQL report: the key result tables of the run as Markdown (out/report.md)
	$(PY) -m churncast_sql report --data $(DATA) --out $(OUT)

gate:            ## the evaluation gate of out/metrics.json (exit 1 if any check fails)
	python3 ../../scripts/eval_gate.py $(OUT)/metrics.json

clean:
	rm -rf $(OUT) .pytest_cache .ruff_cache .coverage coverage.xml htmlcov
