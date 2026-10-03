# ChurnCast runbook

Who this is for: whoever retrains the model on a new export, runs the API, or answers "is this score right?".

## 1. Retrain on a new export
1. Put the export in `data/raw/<YYYY-MM>/` (`customers.csv`, `invoices.csv`, `usage.csv`, `tickets.csv`,
   `export.json`) and update `data/README.md` if the files changed shape.
2. Run one track (any; they agree): `cd tracks/python && make run DATA=../../data/raw/<YYYY-MM>`.
   Or, without installing anything: `EXPORT=<YYYY-MM> docker compose --profile train up`.
3. Read the exit code:

| Exit | Meaning | What to do |
|---|---|---|
| 0 | `out/metrics.json`, `out/model.json`, `out/features.csv` written | Check the warnings in `data_quality.checks`, then §2. |
| 2 | A file or folder could not be read | Check the path and the four file names. |
| 3 | The data contract is violated (an `error` check failed) | Nothing was written. Go to §3. |

4. Run the gate: `python3 scripts/eval_gate.py out/metrics.json` (exit 1 = do not ship; the failing check is
   printed). Then the parity check across tracks (`docker compose --profile train up` runs it).

## 2. Ship a new model
1. Copy the artefact to `models/churncast-<version>.json` and regenerate the model card:
   `python3 scripts/model_card.py out/metrics.json out/model.json > docs/model-card.md`. Read it.
2. Point the API at it (`MODEL_PATH`), `docker compose up -d --build api`, then
   `scripts/smoke-test.sh http://localhost:8000` (every check `ok`).
3. Tell the retention team what changed (threshold, top features) **before** the next call list.

## 3. A check failed or warned
1. The message names the check, e.g. `contract error: contract check(s) failed: customers.channel.accepted`.
2. Look at the failing rows and decide:
   - **The data is wrong** (a broken load, a logging bug): tell the data owner, do not retrain; keep the current
     model live.
   - **The business changed** (a new channel, a new plan): change the contract with a version bump and a
     CHANGELOG line, keep the old version, re-run every track, the gate and the parity check.
   - **Never** delete a check or loosen a threshold to make a run pass without writing down why.
3. A `warn` check does not stop the run. Read it anyway: a small warning can hide a large, local problem.

## 4. The API
- `GET /health` (liveness and model version), `GET /v1/model`, `POST /v1/predict` (up to 1,000 customers),
  `POST /v1/explain`, the form at `/`, OpenAPI docs at `/docs`.
- Inputs outside the contract's ranges get a 422 listing every problem; nothing is clipped silently.
- Customer ids are echoed back but never logged and never sent to the AI provider.

## 5. The AI explainer
- Off by default (`AI_PROVIDER=offline`): the template explanation is used, nothing leaves the machine.
- To switch it off in an emergency: set `AI_PROVIDER=offline` and `docker compose up -d --force-recreate api`.
- If the provider is slow or down, the API returns the template with `fallback: true` and the reason;
  `LLM_TIMEOUT_MS` (default 4000) bounds the wait.
- Never put an API key in the image, the repository or a prompt; use `.env` (git-ignored) or a platform secret.

## 6. Monthly monitoring (contract 1.1)
1. When a new export arrives, run any track on it: with contract 1.1 the run also writes `monitoring` and
   `retraining` into `metrics.json` (`feature-spec.md` §9).
2. Read `monitoring.status`:

| Status | Meaning | What to do |
|---|---|---|
| `ok` | no feature drifted, no performance alert | keep the deployed model |
| `watch` | a feature (or the score) has PSI ≥ 0.25, performance still within the alerts | tell the business what moved; check again next month |
| `retrain` | a labelled month broke an alert (ECE > 0.03, mean gap > 0.02, AUC < 0.72) | read `retraining`: promote the challenger only if `decision` is `promote` |

3. Promoting: copy `out/model.json` to `models/churncast-<version>.json`, regenerate the model card, run the gate
   and the smoke test, switch `MODEL_PATH`, and write a CHANGELOG entry. `keep` means the challenger was not
   better on the holdout: keep the champion and investigate (new features, a new data source).
4. Drift says *what* moved, not *why*. Ask the business (pricing, marketing, operations) before explaining it.

## 7. Observability (API 1.1)
- Every response carries `X-Request-ID` (yours if it is a safe token, else a new one); quote it in bug reports.
- One JSON log line per request (method, route template, status, duration, request id; never a customer id or a raw URL).
- `GET /metrics` (Prometheus): `churncast_requests_total`, `churncast_request_duration_seconds`,
  `churncast_predictions_total`, `churncast_explainer_fallbacks_total`, `churncast_model_info`. Alert on a
  rising fallback rate (the AI provider is failing) and on 5xx responses.

## 8. Releases
- A release is a tag `vX.Y.Z` on a commit with green CI. `deploy.yml` pushes
  `ghcr.io/<owner>/churncast-{api,python,sql,r}:X.Y.Z`; the optional Render job deploys the API.
- Roll back: redeploy the previous image tag, or set `MODEL_PATH` to the previous artefact in `models/` (every
  1.x artefact loads) and restart the API.
