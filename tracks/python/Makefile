# Python track. Same targets in every track: install, lint, test, coverage, run, report, gate.
PY ?= .venv/bin/python
DATA ?= ../../data/raw/2026-07
OUT ?= out

.PHONY: install lint test coverage run report gate clean
install:
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements-dev.txt

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

test:            ## unit tests (fast, tiny fixtures)
	$(PY) -m pytest tests/unit

coverage:        ## unit + data/model tests on the real export, 85 % line coverage gate
	$(PY) -m pytest tests --cov --cov-report=term --cov-report=xml --cov-fail-under=85

run:             ## features.csv, metrics.json, model.json, experiments.jsonl for one export
	$(PY) -m churncast run --data $(DATA) --out $(OUT)

report:          ## execute the notebook top to bottom (fails on any error)
	PYTHONPATH=$(CURDIR) $(PY) -m jupyter nbconvert --to notebook --execute notebooks/churn-model.ipynb \
	  --output-dir $(OUT) --ExecutePreprocessor.timeout=300

gate:            ## the evaluation gate of out/metrics.json (exit 1 if any check fails)
	python3 ../../scripts/eval_gate.py $(OUT)/metrics.json

clean:
	rm -rf $(OUT) .pytest_cache .ruff_cache .coverage coverage.xml htmlcov
