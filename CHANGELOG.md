# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). The data contract (`contract/data-contract.yaml`), the metrics schema
and the model artefact schema have their own versions, recorded in every `metrics.json` and `model.json`.

## [Unreleased]

## [1.0.0] - 2026-06-24
### Added
- The churn model for the 2026-05 export in three tracks with identical outputs (Python: pandas, scikit-learn,
  Jupyter; SQL: DuckDB features with the fit in scikit-learn; R: tidyverse, tidymodels, R Markdown): cleaning
  with counted issues, contract checks with severities, monthly point-in-time snapshots and 15 features,
  baselines B0/B1, logistic experiments E1/E2 with grouped 5-fold CV, the pre-registered champion rule (E2),
  the out-of-time test, calibration, the 10 % call list in rupees, slices, fairness, the leakage scan and probe,
  importance and the six-check release gate.
- Requirements, the modelling plan and ADRs 0001-0005.
- Tests per track: unit tests on the tiny fixture and the metric cases, data tests on the real export (including
  the future-rows leakage test), golden files, invariants and contract-violation tests; coverage gate 85 %.
- CI: path filters, a reusable per-track workflow (R in the pinned Docker image), the gate, parity of the three
  tracks with the golden files, the serving tests, a Docker job; Dependabot.
- The prediction API (FastAPI): `/health`, `/v1/model`, `/v1/predict` (probability, risk band, top 3 reasons),
  `/v1/explain` with the optional AI explainer (OpenAI-compatible, offline by default, guardrails with a
  deterministic template fallback), a small HTML form; `models/churncast-1.0.0.json`.
- Dockerfiles (non-root, read-only, few layers), `docker-compose.yml` (API + `train` profile + parity),
  `scripts/smoke-test.sh`, `deploy.yml` (GHCR, optional Render), `docs/runbook.md`, `docs/model-card.md`.
