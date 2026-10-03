# ChurnCast feature specification (data contract 1.1.0)

The rules every track implements, in words. `data-contract.yaml` holds the numbers (formats, thresholds, lists);
this page says what to do with them and in which order. When the two disagree, it is a bug: open an issue.
Section numbers are referenced from the code (`§4`), the tests and the docs.

## §1 The problem and the timeline
TiffinBox sells monthly meal-plan subscriptions (Basic, Standard, Premium) in five cities. Every month about 9 % of
paying customers do not renew. The retention team can call **10 % of active customers per month** and offer a
discount; today they pick whom to call with five risk flags (the *rule of thumb*, §5). The question:

> At the end of each month, which active customers are most likely **not to renew next month**, and why?

The model is a ranking for a phone list plus a probability that must be honest (calibrated), because the finance
team multiplies it by the price to size the retention budget.

**Timeline.** A *snapshot* is the end of a calendar month M. Its *cut-off* S is the first instant of month M + 1.

| Name | Months (export 2026-05) | Used for |
|---|---|---|
| train | 2025-09 … 2026-02 (6 snapshots) | fitting, grouped 5-fold cross-validation, the leakage scan |
| test | 2026-03, 2026-04 | **once**, at the end: out-of-time evaluation and the gate |
| (label month of 2026-04) | 2026-05 | only the label of the last test snapshot |

**After deployment (contract 1.1.0, export 2026-07).** The v1.0 model went live on the 2026-05 export. Later exports
add *post-deployment* snapshots, which the v1.0 model has never seen:

| Name | Month (export 2026-07) | Used for |
|---|---|---|
| recent | 2026-05 | realised performance of the deployed model; recalibrates the challenger (§9) |
| holdout | 2026-06 | realised performance; champion vs challenger is decided here |
| score | 2026-07 | unlabelled (its label month is not in the export): drift, and the next call list |

A `recent` or `holdout` snapshot is used only if the export also covers its label month, so the 2026-05 export
reproduces v1.0 exactly with contract 1.1.0.

The test months are later than every training month (*out of time*): a churn model is always used on the future.
A snapshot is built only if its month is in the export; its label needs month M + 1 as well.

## §2 Loading and cleaning, in this order
Read every CSV **as text** (no type inference; an empty cell is the empty string). A missing file or column is a
contract error (exit code 3). Labels (`city`, `acquisition_channel`, `age_band`, `kind`, `plan`, `status`,
`category`) are *normalised*: trimmed and lower-cased. Every rule that drops or changes rows is counted in
`data_quality.issues`, under the names below, in this order.

**customers**
1. Parse `signup_date` with `cleaning.date_formats` in order (`2025-03-05`, or day first `05/03/2025`); a value that
   matches none (including impossible dates) is invalid: drop the row → `customers_invalid_signup_date`.
2. Drop exact duplicate rows (all columns equal), keeping the first → `customers_exact_duplicates`.
3. Trim `customer_id`. Normalise `city`, then apply `cleaning.city_aliases` (`bangalore` → `bengaluru`);
   `city_tier` comes from `cleaning.city_tier`.
4. A blank `acquisition_channel` becomes `missing_label` (`unknown`) → `customers_channel_missing`.
5. A blank `age_band` becomes `unknown` → `customers_age_band_missing`.
6. `cancellation_reason` is kept **only** for the leakage probe (§6); it is never a feature (`leaky_columns`).

**invoices** (one row per charge or refund of a billing month)
1. Drop exact duplicates → `invoices_exact_duplicates`. (A duplicated paid charge would not change the snapshot
   rule below, but it would double-count a failed payment.)
2. Normalise `kind`, `plan`, `status`. Parse `list_price` and `discount` as rupees: remove `₹`, thousands
   separators and spaces, keep the sign (`₹3,299` → 3299, `-150.00` → −150), round to 2 decimals.
3. `billing_month` `YYYY-MM` → month index `year * 12 + month − 1`.
4. Drop invoices of unknown customers → `invoices_orphans`.

**usage** (one row per customer and month)
1. Drop exact duplicates → `usage_exact_duplicates`.
2. Drop rows with any negative count (`meals_ordered`, `meals_skipped`, `late_deliveries`, `ratings_count`,
   `ratings_sum`) → `usage_negative_counts`.
3. Drop rows of unknown customers → `usage_orphans`.

**tickets**
1. Parse `created_at` with `cleaning.timestamp_formats`; unparseable → drop → `tickets_invalid_created_at`.
2. Parse `resolved_at` (blank = still open). A resolution **before** its creation is impossible: set it to
   missing (the ticket counts as open) → `tickets_resolved_before_created`.
3. Drop tickets of unknown customers → `tickets_orphans`.

**Checks.** Then run the `checks` of the contract on the clean tables (and `raw.usage.negative_counts` on the
raw usage): each gives `failing_rows` and `observed` (= failing / checked); it passes when `failing_rows` is 0
(`max_ratio`: when `observed` ≤ `max`). A failing `error` check stops the run with exit code 3; a failing `warn`
is reported and the run continues. The two `snapshots.*` checks run on the snapshot summary (§3).

## §3 Snapshots and labels
- **Who is in snapshot M:** every customer with a **paid charge** for month M (`kind = charge`,
  `status = paid`; if several, the one with the lowest `invoice_id`). Refunds and failed payments are not renewals.
- **Label:** `churned = 1` if the customer has **no paid charge for month M + 1**, else 0. It is null when month
  M + 1 is not in the export.
- `split` from the contract (`train`, `test`, and from 1.1.0 `recent`, `holdout`, `score`); `fold` = customer number mod `folds` (`C00042` → 2): all the
  snapshots of a customer sit in the same fold, so a fold never validates on a customer it trained on.
- One output row per (customer, snapshot), sorted by snapshot then `customer_id` (`out/features.csv`, with the
  slice columns `city`, `city_tier`, `age_band`, `channel`, `plan`, `price_inr`).
- Snapshot summary: rows, churners and churn rate per snapshot; `snapshots.rows.min` and
  `snapshots.churn_rate.range` must pass.

## §4 Features (point in time)
**Everything a feature uses must have been known before S**: invoices and usage of months ≤ M, tickets created
before S, a resolution only if it happened before S. Nothing from month M + 1, nothing from `cancellation_reason`.
A missing usage month counts as zero. Every feature is written as a float.

| Feature | Definition |
|---|---|
| `tenure_months` | M − signup month (both as month indexes) |
| `is_new` | 1 if `tenure_months` < 3 |
| `plan_standard`, `plan_premium` | the plan of month M's paid charge (Basic is the reference) |
| `discount_share` | discount / list price of month M's charge |
| `price_change_pct` | (list price M − list price M−1) / list price M−1 if there is a paid charge for M−1, else 0 |
| `meals_last_month` | `meals_ordered` of month M |
| `skip_rate_last_month` | skipped / (ordered + skipped) of month M; 0 when both are 0 |
| `meals_trend` | meals of M − the mean of the meals of M−1 and M−2, using only the months since signup (one month if tenure is 1); 0 if tenure is 0 |
| `late_rate_3m` | late deliveries / meals ordered over M−2 … M; 0 when no meals |
| `avg_rating_3m` | ratings sum / ratings count over M−2 … M; `cleaning.rating_default` (4.0) when no ratings |
| `rating_missing` | 1 when no ratings over M−2 … M |
| `tickets_90d` | tickets with S − 90 days ≤ created < S |
| `open_tickets` | tickets created before S that are not resolved before S |
| `failed_payments_3m` | failed charges for months M−2 … M |

`core: true` marks the five features of E1.

## §5 Models, cross-validation and the champion
| Id | Model | Fit on the training rows |
|---|---|---|
| B0 | prior | everyone gets the training churn rate (AUC 0.5 by construction) |
| B1 | rule of thumb | one point per `rule_baseline` flag (0-5); prediction = the training churn rate of that point count (the overall rate for a count never seen) |
| E1 | logistic regression | the 5 core features |
| E2 | logistic regression | all 15 features |

**Logistic regression** is the *unpenalised* maximum-likelihood fit (scikit-learn `C=inf`, Newton-Cholesky; R
`glm(family = binomial)`), on the raw feature values (no scaling), so the coefficients are in the features' own
units. The linear predictor is `intercept + Σ b_j · x_j`, **added up feature by feature in contract order** (not
a matrix product: BLAS kernels sum in different orders and two identical rows could score an ulp apart, which
changes ties in the ranking).

**Cross-validation.** 5 grouped folds (§3) on the training rows only: for each fold k, fit on the other folds and
score fold k. Report the mean and the sample SD of the five fold AUCs (also Brier and log loss).

**Champion.** Of the logistic experiments, the bigger one (E2) only if its mean CV AUC beats the simpler one (E1)
by at least `champion.min_cv_auc_gain_for_complexity`; otherwise the simpler one. Every experiment is then fitted
on all the training rows and scored **once** on the test months.

## §6 Evaluation
On the test rows, for every experiment (`experiments[].test`) and the champion (`test`):
- **AUC** = P(score of a churner > score of a stayer), ties count ½ (average ranks); null with one class.
- **Average precision** = Σ over distinct scores, from high to low, of (recall_k − recall_k−1) · precision_k.
- **Brier** = mean (p − y)²; **log loss** with p clipped to [1e−15, 1 − 1e−15].
- **Calibration**: `calibration_bins` equal-width bins `[k/B, (k+1)/B)` (p = 1 in the last); per bin n, mean
  predicted, observed rate; **ECE** = Σ n_b / n · |mean predicted − observed|.
- **Capacity** (the call list): in **each** snapshot, the top k = ⌈n · `top_percent` / 100⌉ customers by score
  (ties: lower `customer_id` first). Precision, recall and lift (precision / churn rate) of the contacted rows;
  **net value per month** = (Σ price of contacted churners · `save_rate` · `value_months` − `offer_cost_inr` ·
  contacted) / number of test months. `save_rate` is an assumption to test with an experiment, not a fact.
- **Slices** (`evaluation.slices`): per value, rows, churners, churn rate, mean prediction, AUC only if
  n ≥ `min_slice_rows_for_auc` and both classes ≥ `min_slice_churners_for_auc`, and the recall of the call list.
- **Fairness**: the recall gap (max − min recall of the call list) across `age_band` groups with at least
  `fairness.min_churners` churners, `unknown` excluded. `age_band` is a protected column: it is never a feature.
- **Leakage scan** (training rows): the single-feature AUC of every feature, folded to ≥ 0.5, must stay below
  `leakage_max_single_feature_auc`; the same AUC of the probe "cancellation_reason is filled" is reported to show
  why that column is banned. `customers_in_two_folds` must be 0.
- **Importance**: coefficient · training SD (population SD) per champion feature, largest absolute first.
- **Gate** (`gate`, in this order): `test_auc` ≥ min; `auc_uplift_over_rule` (champion − B1) ≥ min; `ece` ≤ max;
  `brier_below_prior` (champion Brier < B0 Brier); `recall_gap` ≤ max; `leakage_scan` passed. The model ships only
  if all six pass (`scripts/eval_gate.py`, exit 1 otherwise).

## §7 The artefact and the explanations
`out/model.json` follows `model.schema.json`: the champion's features (contract order), intercept, coefficients,
training means, `high_risk_threshold` (the type-7 0.9 quantile of the champion's training scores: "in the top 10 %
of a typical month"), `base_rate` (training churn rate), the training summary and the test metrics. Any track's
artefact must be servable by the API (`serving/`).

The **contribution** of feature j for one customer is `b_j · (x_j − mean_j)` on the log-odds scale: exact for a
linear model, and they add up to the customer's log-odds minus the log-odds of the "average" customer. The API's
explanation lists the largest ones; the optional AI explainer only sees these numbered facts (never the customer
id, never a protected attribute) and is checked by guardrails, with a deterministic template as fallback.

## §8 Parity between tracks
Every track writes the same four files. `scripts/parity.py` compares them with the golden files and with each other:
- `features.csv`: same columns and rows in the same order; text equal; numbers within 1e−9 relative (1e−12 absolute
  near zero). Features are plain arithmetic: they must match exactly.
- `metrics.json`, `model.json`: integers, strings, booleans, nulls and list lengths equal; floats within 1e−6
  absolute + 1e−6 relative (two optimisers converge to the same maximum, not to the last bit). `generator` is ignored.
The golden files in `contract/golden/` are regenerated only when all three tracks agree.

## §9 Monitoring and retraining (contract 1.1.0)
**Monitoring** asks whether the *deployed* model (`monitoring.deployed_model`, the v1.0 artefact) is still fit for
use, using only its own coefficients:
- **Drift (PSI).** Reference = the training rows. Bins = the decile edges (type-7 quantiles at 0.1 … 0.9) of the
  reference values, duplicate edges dropped; the bin of x = the number of edges strictly below x. For every feature
  and for the deployed score, per post-deployment snapshot: PSI = Σ (a − e) · ln(a / e) over the bins, where e and
  a are the reference and actual shares and an empty bin counts as `psi_floor`. Status: `stable` < `psi_watch`
  ≤ `watch` < `psi_drift` ≤ `drift`.
- **Realised performance**, on every labelled post-deployment month: AUC, Brier, ECE (10 bins), mean predicted and
  observed churn. Alerts: ECE > `alert_max_ece`, |mean predicted − observed| > `alert_max_mean_gap`, AUC <
  `alert_min_auc`.
- `monitoring.status`: `retrain` if a labelled month has a performance alert, else `watch` if any feature drifted,
  else `ok`.

**Retraining** (`retraining`): the *challenger* has the deployed model's features, refitted (§5) on every labelled
pre-deployment snapshot (`refit_splits`), then its intercept is recalibrated on the `calibrate_on` month: the
offset d with Σ sigmoid(η + d) = Σ y (Newton's method in one dimension, from d = 0). Champion and challenger are
then scored on the `decide_on` month, which neither has seen. The challenger is promoted only if all four checks
pass: AUC ≥ champion AUC − `max_auc_drop`; Brier < champion Brier; ECE ≤ `max_ece`; recall gap (§6) ≤
`max_recall_gap`. Promoted, it becomes the artefact: `model_version` 1.1.0, `lineage.parent_model_version` 1.0.0,
`high_risk_threshold` = the 0.9 quantile of its scores on the `recent` month, `base_rate` = the churn rate of that
month, `test_metrics` from the holdout, and a `monitoring_reference` (edges and shares) for the next monitoring run.

**Versioning.** Schema changes are additive: a 1.0 reader (the v1.0 API) loads a 1.1 artefact, and the v1.1
outputs on the 2026-05 export contain every field of the v1.0 golden files with the same value
(`scripts/parity.py --backcompat`). The previous contract is kept in `contract/history/`.
