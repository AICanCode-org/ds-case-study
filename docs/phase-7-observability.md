---
phase: 7
slug: phase-7-observability
title: "Monitoring, drift, retraining and a post-mortem"
duration: 5 h
start_tag: phase-6-end
end_tag: phase-7-end
release: v1.1.0
---
# Phase 7 · Monitoring, drift, retraining and a post-mortem

## 1. Why it matters
A model is evaluated once and then lives for months in a world that keeps changing. Marketing launches a new
channel, finance raises prices, churn rises, and a model that was well calibrated in March starts under-predicting
in June while its AUC still looks fine. In this phase the v1.0 model meets that world. The July export **breaks the
pipeline** (a new acquisition channel fails the data contract), and once that is fixed, monitoring shows drift and
a calibration problem. You version the contract, add drift (PSI) and realised-performance monitoring, retrain and
recalibrate a challenger, decide champion versus challenger on a month neither has seen, make the API observable
(request ids, JSON logs, metrics), and write a blameless post-mortem. That is v1.1.0.

## 2. Objectives
By the end of this phase you can:
- Diagnose a contract failure from the exit code and the failing check, and fix it with a versioned contract change rather than a code hack.
- Compute the population stability index (PSI) of every feature and of the score against the training reference, and classify stable / watch / drift.
- Measure the deployed model's realised performance on newly labelled months, and explain why calibration can fail while AUC holds.
- Retrain and recalibrate a challenger, and promote it only through a pre-agreed champion/challenger gate on a holdout month.
- Add request ids, structured logs and Prometheus metrics to the API without logging personal data, and write a blameless post-mortem.

## 3. Step-by-step instructions

### Step 7.1 · The July export breaks the pipeline
Take the new export from the reference and run v1.0 on it:
```bash
git checkout phase-7-end -- data/raw/2026-07
make run DATA=../../data/raw/2026-07       # R: rdev make run DATA=../../data/raw/2026-07
# contract error: contract check(s) failed: customers.channel.accepted      (exit 3)
```
Investigate before you fix: which value is new (`influencer`, launched by marketing in June 2026), how many
customers, since when. The contract did its job: it stopped a model from silently treating a new channel as
something else. Now decide **in the contract**, with a version bump to 1.1.0: add `influencer` to the accepted
values (the channel is not a model feature, so the model is unaffected; the slices and the fairness check see it).
Keep 1.0.0 in `contract/history/` and log the incident timeline for the post-mortem.

### Step 7.2 · Post-deployment snapshots and monitoring
Contract 1.1.0 adds `recent` (2026-05), `holdout` (2026-06) and `score` (2026-07) snapshots and a `monitoring`
block (`feature-spec.md` §9). Implement the monitoring module in your track:
1. **Reference:** the training rows of v1.0. Decile edges of each feature and of the deployed model's score.
2. **PSI** per post-deployment month: Σ (a − e) · ln(a / e), empty bins floored at 1e-4; < 0.10 stable, 0.10-0.25
   watch, ≥ 0.25 drift.
3. **Realised performance** of the deployed model on every labelled month: AUC, Brier, ECE, mean predicted vs observed.

The reference run on the 2026-07 export:

| Month | Role | AUC | ECE | Mean predicted | Observed churn | Drifted features |
|---|---|---|---|---|---|---|
| 2026-05 | recent | 0.771 | 0.049 | 9.1 % | 14.0 % | none (`tenure_months` on watch) |
| 2026-06 | holdout | 0.770 | 0.059 | 10.8 % | 16.7 % | `price_change_pct` (PSI 1.22, the June price rise) |
| 2026-07 | score | n/a | n/a | n/a | n/a | `tenure_months` (PSI 0.25) |

The ranking is as good as ever; the probabilities are far too low. Status: **retrain**.

<!-- track:python -->
Python: `churncast/monitoring.py` (`psi_edges`, `bin_shares`, `psi`, `monitor`, `calibration_offset`, `retrain`);
`np.searchsorted(edges, x, side="left")` = the number of edges strictly below x.
<!-- /track -->
<!-- track:sql -->
SQL: `sql/07_monitoring.sql` (decile edges with `quantile_cont`, shares, PSI, the holdout comparison); the runner
does the refit and the one-dimensional Newton steps of the recalibration, one aggregate query per step.
<!-- /track -->
<!-- track:r -->
R: `R/monitoring.R`; `findInterval(x, edges, left.open = TRUE)` counts the edges strictly below x, and the
recalibration offset is `glm(y ~ 1, offset = eta, family = binomial)`.
<!-- /track -->

### Step 7.3 · Champion versus challenger
The `retraining` block (§9): refit the champion's features on every labelled pre-deployment snapshot (train +
test, 17,010 rows), recalibrate the intercept on the `recent` month (offset +0.564), then compare on the `holdout`
month that neither model has seen:

| 2026-06 holdout | Champion v1.0.0 | Challenger |
|---|---|---|
| AUC | 0.770 | 0.773 (≥ 0.770 − 0.005 ✔) |
| Brier | 0.1188 | 0.1129 (better ✔) |
| ECE | 0.059 | 0.013 (≤ 0.03 ✔) |
| Age-band recall gap | 0.109 | 0.111 (≤ 0.15 ✔) |

Decision: **promote**. The challenger becomes `models/churncast-1.1.0.json` with `lineage.parent_model_version
1.0.0` and a `monitoring_reference` for next month. Check backwards compatibility: on the 2026-05 export the v1.1
pipeline must reproduce every v1.0 golden number (`parity.py --backcompat`), and the v1.0 API must load the 1.1 artefact.

### Step 7.4 · An observable API (v1.1)
Add to `serving/`: an `X-Request-ID` on every response (a caller's id is kept only if it is a safe token, else a
new one), one JSON log line per request (id, method, route template, status, duration; never the body, a customer
id or a key), `GET /metrics` in Prometheus text format (requests by route and status, a latency histogram,
predictions, explainer fallbacks by reason, the model version), and `model_version` + `request_id` in prediction
and explanation responses. v1.0 requests keep working unchanged. The smoke test grows to 10 checks.

### Step 7.5 · Post-mortem, runbook, release
1. Write `docs/postmortem-2026-07.md` (blameless): summary, impact (no wrong predictions shipped: the contract
   stopped the run), timeline, root cause (a new upstream value without a contract change process), what went well,
   what went badly (no monitoring until now: calibration had been off since May), action items with owners.
2. Add a monitoring section to `docs/runbook.md`: what each alert means and who acts.
3. CHANGELOG 1.1.0, regenerate the model card, tag `v1.1.0`.

## 4. AI-assist prompts

### Prompt 1: Explain drift results to a stakeholder
```text
Here are the monitoring results of a churn model (no customer data): <paste the monitoring section of
metrics.json>. Explain to the Head of Growth in five sentences what changed, what it means for the call list and
for finance's budget, and what we propose. Distinguish clearly between "the ranking still works" and "the
probabilities are too low". No numbers that are not in the input.
```
**Verify the output by:** checking every number against the JSON, and rejecting causal claims the data cannot
support (PSI says the price-change distribution moved; it does not say the price rise caused the extra churn).

### Prompt 2: Review my champion/challenger gate
```text
My retraining rule: refit on all labelled pre-deployment months, recalibrate the intercept on the most recent
labelled month, promote only if on a later holdout month AUC >= champion - 0.005, Brier < champion, ECE <= 0.03
and age-band recall gap <= 0.15. What could go wrong with this rule (leakage between calibration and holdout,
a holdout too small, repeated testing on the same month), and what would you change for a monthly cadence?
```
**Verify the output by:** checking that calibration and holdout months are different in your contract and code
(a test), and recording any change to the rule as a contract change with a version bump, not a code tweak.

### Prompt 3: Draft a blameless post-mortem
```text
Draft a blameless post-mortem from these facts: <paste your incident timeline, the failing check, the monitoring
table>. Sections: summary, impact, timeline (IST), root cause (5 whys), what went well, what went badly, action
items (owner, due date). No blame on individuals; focus on process and systems.
```
**Verify the output by:** matching every timestamp and number to your log and `metrics.json`, removing invented
details (an assistant may add an outage or a customer complaint that did not happen), and making each action item
testable.

## 5. Deliverables
- [ ] Contract 1.1.0 (with 1.0.0 in `contract/history/`), the 2026-07 export, golden files for 2026-07.
- [ ] Monitoring and retraining in your track; tests green; parity MATCH on 2026-07 and backcompat MATCH on 2026-05.
- [ ] `models/churncast-1.1.0.json` promoted by the gate, model card regenerated.
- [ ] API 1.1 with request ids, JSON logs and `/metrics`; 10/10 smoke checks.
- [ ] `docs/postmortem-2026-07.md`, runbook monitoring section, CHANGELOG 1.1.0, tag `v1.1.0`.

## 6. Self-check quiz

### Q1. The July export fails `customers.channel.accepted`. What is the right fix?
- [ ] Map `influencer` to `unknown` in the cleaning code
- [ ] Turn the check into a warning
- [x] Investigate, then change the contract on purpose (add the value, bump to 1.1.0, keep 1.0.0 in history) and update all tracks and golden files
- [ ] Delete the influencer customers
> **Answer:** The check stopped the run because the world changed. The response is a reviewed decision recorded in the contract, not a silent workaround in code.

### Q2. The deployed model's AUC is 0.770 on June but its ECE is 0.059. What does that mean?
- [ ] The model is fine
- [x] It still ranks customers well, but its probabilities are too low (mean predicted 10.8 % vs 16.7 % observed): the call list works, the budget does not
- [ ] The model must be replaced by the rule of thumb
- [ ] The labels are wrong
> **Answer:** Discrimination and calibration are different properties. A rise in the base rate shifts every probability; recalibrating the intercept fixes most of it.

### Q3. What does a PSI of 1.22 for `price_change_pct` in June tell you?
- [ ] The feature is broken
- [ ] Customers churned because of the price change
- [x] The distribution of that feature moved strongly compared with training (a price rise), so the model sees inputs it rarely saw; investigate and check performance
- [ ] The model is leaking
> **Answer:** PSI measures distribution shift, not cause or harm. It is a signal to look at realised performance and the business context.

### Q4. Why is the champion/challenger decision made on 2026-06 and not on 2026-05?
- [x] 2026-05 was used to recalibrate the challenger; deciding on the same month would favour it
- [ ] 2026-05 has no labels
- [ ] 2026-06 has more customers
- [ ] The contract forbids 2026-05
> **Answer:** Fit, calibrate and decide on different data. The holdout month is new to both models.

### Q5. Which of these may the API's JSON access log contain?
- [ ] The request body with the customer's features
- [ ] The `LLM_API_KEY` used by the explainer
- [x] The request id, method, route template, status and duration
- [ ] The customer id, to debug faster
> **Answer:** Logs are kept long and read by many people. Log what you need to operate the service, never personal data or secrets.

### Q6. What makes a post-mortem "blameless"?
- [ ] Nobody is told about the incident
- [x] It looks for the conditions and process gaps that allowed the incident, so people report problems openly, instead of naming a person to blame
- [ ] It is written by someone outside the team
- [ ] It has no action items
> **Answer:** People make reasonable decisions with the information and tools they have. Fix the system (a contract change process, monitoring) so the next person cannot fall into the same gap.

## 7. What you learned
- A versioned data contract turns an upstream change into a visible, reviewable decision.
- Monitoring a live model: PSI drift for inputs and score, realised performance on labelled months, alerts with thresholds.
- Discrimination versus calibration, and recalibration as a cheap fix for a shifted base rate.
- Champion/challenger retraining with a pre-agreed gate on a holdout month, and backwards-compatible artefacts.
- Operability: request ids, structured logs without personal data, metrics, and a blameless post-mortem.

## 8. Catch-up git commands
```bash
git fetch upstream --tags
git switch -c my-phase-8 phase-7-end      # = v1.1.0
git diff phase-6-end phase-7-end --stat
(cd tracks/python && make run DATA=../../data/raw/2026-05 OUT=out/2026-05)
python3 scripts/parity.py --backcompat contract/golden/metrics-2026-05.json tracks/python/out/2026-05/metrics.json
```
