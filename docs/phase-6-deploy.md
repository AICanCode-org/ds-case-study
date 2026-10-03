---
phase: 6
slug: phase-6-deploy
title: "Model card, prediction API, AI explainer, Docker and delivery"
duration: 5 h
start_tag: phase-5-end
end_tag: phase-6-end
release: v1.0.0
---
# Phase 6 · Model card, prediction API, AI explainer, Docker and delivery

## 1. Why it matters
A model in a notebook helps nobody on Monday morning. The retention team needs a ranked list with a reason per
customer; engineering needs something they can run, monitor and roll back; everyone needs an honest description of
what the model is for and where it fails. In this phase you ship v1.0.0: a **model card** generated from the
numbers (so it cannot drift from the model), a **prediction API** that serves any track's `model.json` with
per-customer explanations, an optional **AI explainer** that turns the explanation into a sentence an agent can
use and that is not allowed to invent anything, and **Docker images** for the API and the three pipelines,
checked in CI and published to GHCR on a version tag.

## 2. Objectives
By the end of this phase you can:
- Generate a model card (intended use, data, metrics, calibration, slices, fairness, limits) and check in CI that it matches the golden files.
- Run and test the FastAPI prediction API: `/health`, `/v1/model`, `/v1/predict`, `/v1/explain`, problem+json errors, a small HTML form.
- Explain the explainer's safety design: numbered facts in, guardrails out, a deterministic template as fallback, offline by default.
- Build small, non-root, read-only images and run the three pipelines plus parity with `docker compose --profile train`.
- Release v1.0.0: CHANGELOG, a tag, images on GHCR, a runbook, and an optional free Render deploy.

## 3. Step-by-step instructions

### Step 6.1 · The model card
```bash
python3 scripts/model_card.py tracks/python/out/metrics.json tracks/python/out/model.json > docs/model-card.md
python3 scripts/model_card.py --check docs/model-card.md contract/golden/metrics-2026-05.json contract/golden/model-2026-05.json
```
Read the generated card critically. The numbers come from the files; the words (intended use, out-of-scope uses,
limits, ethics) are in the script. Check that it says, at least: the model ranks customers for a capacity-limited
call list, it is **not** evidence that a call causes anyone to stay (`save_rate` is an assumption to test with a
randomised hold-out group), it was evaluated on two months only, and `age_band` is used for the fairness check only.
Add the release recommendation in your own words to the PR: ship E2 to the call list, run a hold-out experiment
to measure the real save rate, re-check calibration monthly.

### Step 6.2 · The prediction API
The API is provided: bring it in from the reference, then read and run it.
```bash
git fetch upstream --tags && git checkout phase-6-end -- serving models
cd serving && make install lint coverage
MODEL_PATH=../models/churncast-1.0.0.json make serve      # http://127.0.0.1:8000, docs at /docs
```
- `POST /v1/predict` takes up to 1,000 customers (`{"customers": [{"customer_id": "...", "features": {...}}]}`),
  validates every feature against its contract range (out of range → **422** `application/problem+json` naming
  the field), and returns the probability, the risk band (`high` above `high_risk_threshold`) and the top reasons.
- `POST /v1/explain` returns the contributions and a note: the template by default.
- `models/churncast-1.0.0.json` is the Python track's artefact, released as the v1.0 model. The API loads any
  1.x artefact of any track: try `MODEL_PATH=../tracks/r/out/model.json`.

### Step 6.3 · The AI explainer, safely
Read `serving/churncast_api/explainer.py` top to bottom. The model never sees a customer id, raw records or a
protected attribute: only numbered facts (`R1: open support tickets = 2, adds +0.31 to the log-odds`, the
probability, the base rate). Its answer must pass four guardrails: plain text within 600 characters citing at
least two existing facts; every number a correct rounding of a fact; no certainty claims ("will churn"); no
sensitive attributes. Otherwise the API returns the template with `fallback: true` and a reason.
```bash
AI_PROVIDER=llm LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=llama3.2 make serve   # optional: a local Ollama
```
The tests run the explainer against a fake LLM server that returns good, invented-number, overconfident and
slow answers. No API key is ever needed.

### Step 6.4 · Docker and compose
```bash
docker compose up -d --build                    # the API on http://localhost:8000
scripts/smoke-test.sh http://localhost:8000     # 8 checks
docker compose --profile train up               # python, sql and r pipelines in containers, then parity + parity-model
```
Read the Dockerfiles: few layers (dependencies, then code), a non-root user (uid 10001), `read_only: true` with a
`tmpfs` for `/tmp`, a health check on `/health`. The R runtime image is the `runtime` stage of the same Dockerfile
as your dev image. Prove the fallback: `AI_PROVIDER=llm LLM_BASE_URL=http://10.255.255.1:9/v1 docker compose up -d
--force-recreate api`, then `EXPECT_FALLBACK=true scripts/smoke-test.sh`.

<!-- track:python -->
Python track image: `tracks/python/Dockerfile` (python:3.12-slim + `requirements.txt`, the package only).
<!-- /track -->
<!-- track:sql -->
SQL track image: `tracks/sql/Dockerfile` (DuckDB + scikit-learn for the one fit); DuckDB runs single-threaded so
the container's results equal CI's.
<!-- /track -->
<!-- track:r -->
R track image: `docker build -f tracks/r/Dockerfile -t churncast-r:local .` builds the `runtime` stage: the
package code on top of the same pinned base as the dev image, run as uid 10001.
<!-- /track -->

### Step 6.5 · CI, delivery and the release
1. Take the Phase 6 workflows (`git checkout phase-6-end -- .github/`): CI gains a `serving` job (lint + tests with
   coverage) and a `docker` job (build every image, run the three pipelines, parity, the smoke test, the fallback
   smoke test, serving the R model trained a minute earlier). `deploy.yml` pushes
   `ghcr.io/<owner>/churncast-{api,python,sql,r}:<version>` on a `v*.*.*` tag.
2. Write `CHANGELOG.md` 1.0.0 and `docs/runbook.md` (start, check, roll back, rotate a key, what to do when the
   gate fails).
3. Tag: `git tag -a v1.0.0 -m "ChurnCast v1.0.0" && git push origin v1.0.0`. Optional: a free Render web service
   from the GHCR image (`RENDER_DEPLOY_HOOK_URL` secret, `RENDER_APP_URL` variable in the `production` environment).

## 4. AI-assist prompts

### Prompt 1: Review my model card
```text
Here is a generated model card for a monthly churn model used to pick a retention call list: <paste
docs/model-card.md>. Act as a model-risk reviewer. What is missing or overstated? In particular: intended and
out-of-scope uses, the difference between predicting churn and causing retention, evaluation period, calibration,
fairness, and what would make the card wrong next month.
```
**Verify the output by:** checking every number it cites against `metrics.json` (assistants round or invent), and
adding missing *words* to `scripts/model_card.py` (not to the generated file), then `--check` again.

### Prompt 2: Attack the explainer's guardrails
```text
Here are the guardrails of an LLM explainer that writes one note per customer from numbered facts: <paste the
docstring and validate() of serving/churncast_api/explainer.py>. Write 8 model answers that would mislead a
retention agent but might pass these guardrails (wrong direction of an effect, a number rounded wrongly, a
sensitive proxy, a causal claim), and say which guardrail, if any, catches each.
```
**Verify the output by:** adding each answer as a case to the fake-LLM tests and running `make coverage`; fix a
guardrail only when a test shows the gap. Keep the template fallback as the safe default.

### Prompt 3: Harden my Dockerfile
```text
Review this Dockerfile and compose service for a FastAPI model API: <paste serving/Dockerfile and the api service
of docker-compose.yml>. Check: image size, layer caching, non-root user, read-only file system, secrets (none may
be baked in), health check, and what an attacker could do with a writable /tmp. Propose changes with a reason each.
```
**Verify the output by:** rebuilding and running `scripts/smoke-test.sh`, `docker compose exec api id -u` (not 0),
and `docker history` on the image to confirm no secret or `.env` is in any layer.

## 5. Deliverables
- [ ] `docs/model-card.md` generated and checked in CI; your release recommendation in the PR.
- [ ] The API's tests green (`make coverage` in `serving/`), and `scripts/smoke-test.sh` passing against the container, also with the AI provider unreachable.
- [ ] `docker compose --profile train up` runs all three pipelines and parity MATCH.
- [ ] CHANGELOG 1.0.0, `docs/runbook.md`, the `v1.0.0` tag and its images on GHCR.
- [ ] An `AI_LOG.md` entry.

## 6. Self-check quiz

### Q1. Why is the model card generated from `metrics.json` and `model.json` instead of written by hand?
- [ ] Markdown is hard to write
- [x] Every number then comes from the model it describes, and CI's `--check` fails if the card and the model drift apart
- [ ] The site requires JSON
- [ ] It is shorter
> **Answer:** Hand-copied numbers go stale after the first retrain. The words around the numbers are reviewed in the script.

### Q2. The model card says the campaign is worth about ₹1.1 lakh a month. What is the biggest caveat?
- [ ] The prices are in rupees
- [x] It assumes a 25 % save rate that nobody has measured; a randomised hold-out group is needed to know whether calls cause customers to stay
- [ ] The AUC is too low
- [ ] It only covers the Python track
> **Answer:** A churn model predicts who is at risk, not who can be persuaded. The value estimate is only as good as the save-rate assumption.

### Q3. Which of these does the AI explainer receive?
- [ ] The customer id and their last three invoices
- [ ] The customer's age band, to personalise the message
- [x] Numbered facts: the probability, the base rate and the top feature contributions
- [ ] The whole training set
> **Answer:** Data minimisation by construction: the explainer can only talk about the facts it is given, and guardrails check that it did.

### Q4. The LLM answers "This customer will churn because of 3 late deliveries" but the fact says 2. What happens?
- [ ] The answer is returned as is
- [ ] The API returns 500
- [x] Two guardrails fail (a certainty claim and a number that is not in the facts), so the API returns the template with `fallback: true` and the reason
- [ ] The number is corrected automatically
> **Answer:** The API never shows an unchecked model answer. The template is always available, even when the provider is down.

### Q5. Why do the containers run as a non-root user with a read-only file system?
- [ ] It makes them faster
- [x] If the process is compromised, it cannot modify the image's code or write outside the mounted output and `/tmp`, which limits the damage
- [ ] Docker requires it
- [ ] So that the model cannot be retrained
> **Answer:** Least privilege applies to containers too. The compose file sets `read_only: true` and a `tmpfs` for `/tmp`; the images create uid 10001.

### Q6. Why can the API serve a `model.json` produced by the R track?
- [ ] The API contains an R interpreter
- [x] The artefact is a language-neutral JSON file defined by `contract/model.schema.json`: features, coefficients, means, threshold
- [ ] R models are converted to Python with a library
- [ ] It cannot; only Python models work
> **Answer:** A shared artefact contract decouples training from serving. The Docker job in CI proves it by serving the R model it just trained.

## 7. What you learned
- A model card that is generated, checked and honest about intended use, causality and limits.
- A small, validated prediction API with explanations that are exact for a linear model.
- A safe AI feature: data minimisation, guardrails, a deterministic fallback, offline by default, tested against a fake LLM.
- Docker images that are small, non-root and read-only, compose profiles, and continuous delivery to GHCR on a tag.

## 8. Catch-up git commands
```bash
git fetch upstream --tags
git switch -c my-phase-7 phase-6-end      # = v1.0.0
git diff phase-5-end phase-6-end --stat
docker compose up -d --build && scripts/smoke-test.sh
```
