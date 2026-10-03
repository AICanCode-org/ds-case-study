# ChurnCast modelling plan

> **Phase 2 deliverable** (reference version), written on 2026-06-05 before any model was trained.

## 1. Timeline and splits
- Training snapshots: 2025-09 … 2026-02 (6 month-ends). Test snapshots: 2026-03 and 2026-04 (the label of 2026-04
  needs May 2026, the last month of the export).
- The test months come **after** every training month because the model will always be used on the future; a
  random split would mix months and hide drift.
- 5-fold cross-validation on the training rows only, folds **grouped by customer** (fold = customer number mod 5):
  a customer appears in up to six snapshots, and the same customer in training and validation would inflate AUC.
- The test months are scored **once**, after the champion is chosen.

## 2. Baselines
- **B0, the prior:** everyone gets the training churn rate. The floor for calibration (Brier) and AUC (0.5).
- **B1, the rule of thumb:** the retention team's five flags, one point each, mapped to the training churn rate of
  that point count. The model must beat what the business already does, not just chance.

## 3. Candidate models and features
- **E1:** logistic regression on the 5 core features (tenure, is_new, meals last month, skip rate, tickets 90 d).
- **E2:** logistic regression on all 15 features of `feature-spec.md` §4.
- Why logistic regression first: calibrated by construction on the training distribution, coefficients the agents
  and finance can read, exact per-feature contributions for the explanations, and identical in three languages
  (unpenalised maximum likelihood, no hyper-parameters to tune on the test).
- **Champion rule:** E2 only if its mean CV AUC beats E1 by at least 0.002; otherwise the simpler E1. Decided now,
  so the test cannot influence the choice. A more flexible model (gradient boosting) is a later challenger that must
  pass the same gate.

## 4. Metrics and the release gate
| Metric | Tells the business | Gate |
|---|---|---|
| Test AUC | how well risk is ranked | ≥ 0.72 |
| AUC uplift over B1 | better than today's rule | ≥ 0.03 |
| ECE | probabilities finance can multiply by price | ≤ 0.03 |
| Brier vs B0 | better probabilities than the base rate | below |
| Recall gap across age bands | the call list does not miss one group | ≤ 0.15 |
| Leakage scan | no feature is "too good" | max single-feature AUC < 0.90 |
| Precision / recall / lift @ 10 % and net value per month | the call list in rupees | reported, not gated |

## 5. Leakage, fairness and what would stop us
- **Prevention:** every feature uses only rows before the cut-off; `cancellation_reason` is never a feature;
  `age_band` is never a feature.
- **Detection:** single-feature AUC scan on the training rows, a probe showing what `cancellation_reason` would do,
  a test that appends future rows and expects identical past features, `customers_in_two_folds == 0`.
- **Fairness:** recall of the call list per age band (groups with ≥ 30 churners; `unknown` excluded).
- **Do not ship if:** any gate check fails; the test AUC is far above the CV AUC (suspect leakage); calibration is off
  in the top decile; or the three tracks disagree.

## 6. The pipeline
| Step | Output |
|---|---|
| M1 load and clean (text, rules, counted issues, checks) | `data_quality` in `metrics.json` (exit 3 on an error check) |
| M2 snapshots and labels | the snapshot summary |
| M3 point-in-time features | `out/features.csv` |
| M4 baselines, experiments, grouped CV, champion, test | `experiments`, `champion`, `test` |
| M5 calibration, slices, fairness, leakage, importance, gate | `out/metrics.json`, `out/model.json`, `out/experiments.jsonl` |
| Report | the notebook (Python), `report.md` (SQL), R Markdown (R) |
