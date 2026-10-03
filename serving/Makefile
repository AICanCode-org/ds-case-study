# The prediction API. make install lint test coverage serve
PY ?= .venv/bin/python
PORT ?= 8000

.PHONY: install lint test coverage serve clean
install:
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements-dev.txt

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

test:
	$(PY) -m pytest tests

coverage:        ## 85 % line coverage gate
	$(PY) -m pytest tests --cov --cov-report=term --cov-report=xml --cov-fail-under=85

serve:           ## http://127.0.0.1:$(PORT) (MODEL_PATH, AI_PROVIDER ... from the environment)
	$(PY) -m churncast_api --port $(PORT)

clean:
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml htmlcov
