---
phase: 3
slug: phase-3-implementation
title: "Implementation in five milestones: clean, check, features, models, evaluation"
duration: 14 h
start_tag: phase-2-end
end_tag: phase-3-end
---
# Phase 3 · Implementation in five milestones: clean, check, features, models, evaluation

## 1. Why it matters
This is where most churn models quietly go wrong: a duplicated invoice that doubles a failed payment, a ticket from
next month that "predicts" this month's churn, a fold that shares customers, an AUC function that mishandles ties,
a test set peeked at to pick the winner. You build the pipeline **test-first**, one milestone at a time: delete a
line from the pending list, watch its tests fail, implement until they pass. Every function has a `TODO` with a
hint that says where in `contract/feature-spec.md` to look and which trap to avoid. At the end, one command turns
the raw export into `features.csv`, `metrics.json`, `model.json` and `experiments.jsonl`, and your numbers match the
golden files.

## 2. Objectives
By the end of this phase you can:
- Load messy CSVs as text and apply the cleaning rules in order, counting every row they drop or change (M1).
- Run the contract's checks with severities and stop on an `error` with exit code 3 (M2).
- Build month-end snapshots, labels and 15 point-in-time features without leaking the future (M3).
- Fit the two baselines and two logistic regressions with grouped 5-fold CV, and compute AUC, average precision, Brier, log loss and calibration from scratch (M4).
- Choose the champion by the CV rule, evaluate it once on the test months (call list, value, slices, fairness, leakage, gate), write the artefact, and fill in the report (M5).

## 3. Step-by-step instructions

### Step 3.1 · The red-green loop
For every milestone:
1. Delete the milestone's lines from the pending list (`tests/conftest.py`, or `tests/testthat/helper-churncast.R`).
2. Run the unit tests: they fail with `NotImplementedError` / `TODO(Mx)` (red).
3. Implement one function at a time, re-running the tests (green). Commit after each green step:
   `feat(python): M1 parse money and dates`.
4. Never edit a test to make it pass. If you believe a test is wrong, open an issue quoting the spec section.

<!-- track:python -->
```bash
cd tracks/python
make test                                  # or: .venv/bin/pytest tests/unit/test_clean.py -x -q
```
Code: `churncast/{load,clean,checks,features,model,evaluate,artefact,pipeline}.py`; `contract.py` and `__main__.py`
are complete.
<!-- /track -->

<!-- track:sql -->
```bash
cd tracks/sql
make test                                  # or: .venv/bin/pytest tests/unit/test_clean.py -x -q
```
Code: `sql/02_clean.sql` … `sql/06_evaluate.sql` and `sql/checks/<type>.sql`; `sql/01_load.sql` and the runner
(`churncast_sql/runner.py`) are complete. Explore any view by hand: open DuckDB (CLI or `duckdb.connect()`), set
the variable `data_dir`, and run the files in order on the tiny fixture.
<!-- /track -->

<!-- track:r -->
```bash
rdev make test                             # from the repository root, with the alias of Phase 0
```
Code: `R/{load,clean,checks,features,model,evaluate,artefact,pipeline}.R`; `R/contract.R` and `run.R` are
complete. Inside the image you can also start an interactive session: `rdev R`, then `pkgload::load_all()`.
<!-- /track -->

### Step 3.2 · M1 · Load and clean (`test_load`, `test_clean`)
Read `feature-spec.md` §2. Implement loading **as text**, then the four cleaners in the written order:
- customers: invalid signup dates → exact duplicates → city aliases and tiers → `unknown` channel and age band;
- invoices: exact duplicates → money parsing (`₹3,299`, `3,299.00`, `-150.00`) → month index → orphans;
- usage: exact duplicates → negative counts → orphans;
- tickets: invalid `created_at` → resolutions before creation set to missing → orphans.
Every rule adds to `issues`. On the tiny fixture the expected counts are in `contract/fixtures/tiny-expected.json`.
On the real export you will see: 3 invalid signup dates, 71 duplicate customers, 508 missing channels, 148
duplicate invoices, 59 rows with negative usage, 31 tickets resolved before they were created, and more.

<!-- track:python -->
Read every file with `pd.read_csv(path, dtype=str, keep_default_na=False)`: without `keep_default_na=False`, the
string `"NA"` and empty cells become `NaN` and you lose the difference between "blank" and "missing".
<!-- /track -->
<!-- track:sql -->
`01_load.sql` reads with `all_varchar = TRUE`. Parse dates in your macro with a `CASE` that matches each format's
shape with `regexp_full_match` and then calls `try_strptime`: a value that matches no format is NULL, never a guess.
<!-- /track -->
<!-- track:r -->
Read with `readr::read_csv(col_types = cols(.default = col_character()), na = character())`: the empty `na`
vector keeps blanks as `""`. Parse dates by trying the formats in order (`as.POSIXct(format = ...)`).
<!-- /track -->

### Step 3.3 · M2 · Contract checks (`test_checks`)
Implement the six check types of `data-contract.yaml` (`unique`, `not_null`, `accepted_values`, `range`,
`relationship`, `max_ratio`): each returns failing and checked rows; `observed` = failing / checked. A failing
`error` check raises a contract error, which the CLI turns into **exit code 3**. Try it: copy the tiny fixture,
add a customer in `mumbai`, and run the pipeline on it. Phase 7 starts with exactly this failure.

### Step 3.4 · M3 · Point-in-time snapshots, labels and features (`test_features`)
The heart of the project (`feature-spec.md` §3-§4). For each snapshot month M:
1. **Who:** customers with a paid charge for M (one per customer: the lowest `invoice_id`).
2. **Label:** 1 if no paid charge for M + 1; null if M + 1 is not in the export.
3. **Features:** only what was known before S = first instant of M + 1. A ticket created at 00:00 on the 1st of
   M + 1 is invisible; a ticket resolved after S is still *open* at S. Usage of a missing month counts as zero.
4. `split` and `fold` from the contract; sort by snapshot, then `customer_id`.
Check your summary: 8 snapshots, from 1,608 rows (2025-09) to 2,652 rows (2026-04), churn rates between 8.5 % and
10.7 %; 11,862 training rows and 5,148 test rows.

### Step 3.5 · M4 · Baselines, logistic regression, grouped CV and the metrics (`test_model`, `test_metrics`)
1. **Metrics from scratch** (`feature-spec.md` §6), checked against `contract/fixtures/metric-cases.json`: AUC with
   average ranks for ties, average precision over distinct scores, Brier, log loss with clipping, 10-bin
   calibration and ECE, `top_k = ceil(n · 10 / 100)` in integers.
2. **Models** (§5): B0 prior, B1 rule (flag count → training churn rate), unpenalised logistic regression. The
   linear predictor is added up feature by feature (the hint explains the BLAS tie trap).
3. **Cross-validation:** for each of the 5 folds, fit on the other four and score it; mean and sample SD of AUC.

<!-- track:python -->
`LogisticRegression(C=math.inf, solver="newton-cholesky", tol=1e-12)` is the unpenalised MLE. The default
(`C=1.0`, L2) is a *different model*: your coefficients would not match the other tracks.
<!-- /track -->
<!-- track:sql -->
SQL cannot fit a logistic regression sensibly, so the runner does exactly that one step with scikit-learn and
writes the coefficients back into a table; scoring, CV bookkeeping and every metric stay in SQL (`05_metrics.sql`
table macros over any `(grp, y, p)` table).
<!-- /track -->
<!-- track:r -->
`parsnip::logistic_reg() |> set_engine("glm")` with a tight `glm.control(epsilon)`; folds with
`rsample::manual_rset()` from the contract's fold column (never `vfold_cv()`), metrics checked against
`yardstick` only where its definitions match the spec (yardstick's `roc_auc` treats the *first* factor level as
the event by default!).
<!-- /track -->

The reference results (training months, 5 grouped folds; test months scored once):

| Experiment | CV AUC (mean ± SD) | Test AUC | Test Brier | Precision@10 % | Recall@10 % |
|---|---|---|---|---|---|
| B0 prior | 0.500 | 0.500 | 0.0803 | 4.8 % | 5.5 % |
| B1 rule of thumb | 0.667 ± 0.010 | 0.651 | 0.0780 | 18.8 % | 21.4 % |
| E1 logistic, 5 core features | 0.743 ± 0.013 | 0.741 | 0.0746 | 28.1 % | 32.0 % |
| E2 logistic, all 15 features | 0.758 ± 0.015 | 0.743 | 0.0753 | 26.6 % | 30.2 % |

### Step 3.6 · M5 · Champion, evaluation, artefact and the report (`test_artefact`, `test_cli`; SQL also `test_evaluate`)
1. **Champion:** E2 beats E1 by 0.0154 mean CV AUC (≥ 0.002), so E2 is the champion. Notice that on the test
   months E1's call list is slightly better. You do **not** switch: the test months are for reporting, not choosing.
   Write that observation down; it is an honest limitation for the model card.
2. **Evaluation** on the test months: calibration table and ECE (0.008), the call list per snapshot, net value
   per month (≈ ₹1.10 lakh vs ₹63,001 for the rule), slices, the age-band recall gap (0.115), the leakage scan
   (max single-feature AUC 0.703 for `skip_rate_last_month`; the `cancellation_reason` probe scores ≈ 0.88: that
   is what leakage looks like), importance, and the six gate checks.
3. **Artefact** (`model.json`, `feature-spec.md` §7) and **contributions** `b_j · (x_j − mean_j)`.
4. **Run it** and compare with the golden files:
   ```bash
   make run                                                   # R: rdev make run
   python3 ../../scripts/parity.py ../../contract/golden/metrics-2026-05.json out/metrics.json
   python3 ../../scripts/parity.py ../../contract/golden/model-2026-05.json out/model.json
   python3 ../../scripts/eval_gate.py out/metrics.json
   ```
5. **The report:** fill in every section of the skeleton with the run's numbers and one sentence of
   interpretation each, then `make report` must execute it top to bottom.

<!-- track:python -->
The report is `notebooks/churn-model.ipynb`: the setup cell runs the pipeline; each section reads from `m`
(metrics) and `a` (artefact). No number is typed by hand.
<!-- /track -->
<!-- track:sql -->
The report is `make report`: `churncast_sql/report.py` writes `out/report.md` from the result tables (it is
complete); add your interpretation to the PR description and the model card later.
<!-- /track -->
<!-- track:r -->
The report is `report/churn-model.Rmd`, knitted by `rdev make report` to `out/churn-model.html`. Every number is
an inline `r` expression from the run, never typed.
<!-- /track -->

## 4. AI-assist prompts

### Prompt 1: Implement one function against its tests
```text
I'm implementing <function name> in the <Python | DuckDB SQL | R> track of a churn pipeline. Here is the stub
with its TODO hint: <paste>. Here is the spec section: <paste feature-spec.md §N>. Here are the failing tests:
<paste>. Write the implementation only, explain each line that handles an edge case, and do not change the
signature or the tests.
```
**Verify the output by:** running the tests (they must pass without edits), reading every edge case against the
spec (assistants "simplify" rules, e.g. dropping all duplicates instead of exact duplicates), and checking the
issue counts on the tiny fixture against `tiny-expected.json`.

### Prompt 2: Find the leak in my features
```text
Here is my feature code for a month-end churn snapshot with cut-off S = first instant of month M+1: <paste
build_snapshot / the snapshot views / build_snapshot()>. List every place where data from on or after S, or from
the label month, could enter a feature. For each, give a minimal test case (one customer, two or three rows) that
would expose it.
```
**Verify the output by:** turning each suspected leak into a test on a copy of the tiny fixture and running it;
an assistant may also flag correct code, so only a failing test counts. Then check the leakage scan in
`metrics.json`: no feature near 0.9.

### Prompt 3: Explain a metric difference
```text
My AUC on the test months is <x>, the golden file says 0.7430. My Brier matches. Here is my AUC function:
<paste>. Here is a metric case where I fail: <paste from contract/fixtures/metric-cases.json>. What is the most
likely cause (ties, class order, NaN handling, sorting), and how do I confirm it?
```
**Verify the output by:** reproducing the failing case by hand with the formula in `feature-spec.md` §6 (average
ranks), fixing the code, and running `parity.py` against the golden file until it says MATCH.

## 5. Deliverables
- [ ] Every unit test group un-pended and green in your track (`make test`), lint clean.
- [ ] `make run` writes the four files; `parity.py` says MATCH for metrics and model against the golden files.
- [ ] `eval_gate.py` passes (6/6 checks).
- [ ] The report executes top to bottom with your interpretation in every section.
- [ ] Small commits, one PR per milestone (or per two), each with green CI; `AI_LOG.md` entries for the prompts you used.

## 6. Self-check quiz

### Q1. A ticket was created on 2026-03-01 00:00. Which snapshot can see it?
- [ ] 2026-02 (it is about February's service)
- [x] 2026-03 and later, never 2026-02: its cut-off is 2026-03-01 00:00 and a feature may only use tickets created strictly before it
- [ ] Every snapshot of that customer
- [ ] None: tickets at midnight are invalid
> **Answer:** The cut-off of snapshot M is the first instant of M + 1. "Created < S" excludes the ticket from 2026-02. Boundary tests like this one catch most leaks.

### Q2. Why must the logistic regression be unpenalised (`C=inf`) in this project?
- [ ] Penalised models cannot produce probabilities
- [x] Unpenalised maximum likelihood has one answer every library finds, so the tracks can be compared to 1e-6; defaults of penalised fits differ by library
- [ ] Penalties always reduce AUC
- [ ] It trains faster
> **Answer:** scikit-learn defaults to L2 with C=1; R's glm is unpenalised. With 15 features and ~12,000 rows the penalty is not needed, and parity requires the same model.

### Q3. E1 has a slightly better test call list than E2, but E2 is the champion. Why not switch?
- [ ] E2 has more features, so it must be better
- [x] The champion was chosen in advance by the CV rule; choosing by test score turns the test months into a second validation set and the reported numbers become optimistic
- [ ] E1 failed the gate
- [ ] The test months are not labelled
> **Answer:** The test set is used once, for an honest report. Record the observation as a limitation, and let a future experiment (with a new test period) decide.

### Q4. What does an AUC of about 0.88 for "cancellation_reason is filled" tell you?
- [ ] It is the best feature and should be added
- [x] It is a near-perfect proxy for the outcome, known only after the customer cancels: target leakage
- [ ] The column has missing values
- [ ] Customers who give a reason are less likely to churn
> **Answer:** The leakage scan reports it on purpose to show how good a leak looks. A real feature set should have nothing near it (the reference maximum is 0.70).

### Q5. Why are AUC and calibration implemented from scratch instead of calling a library?
- [ ] Libraries are slow
- [x] Three tracks must agree exactly, and libraries differ on ties, class order and bin edges; the spec plus the metric cases pin one definition
- [ ] Libraries cannot compute ECE
- [ ] It is required by the licence
> **Answer:** Writing a metric once, testing it on hand-computed cases and comparing it across implementations is how you discover the edge cases (ties, one-class slices, p = 1 in the last bin).

### Q6. Your pipeline's `issues.invoices_exact_duplicates` is 0 on the real export. What is the most likely bug?
- [ ] The export has no duplicates
- [ ] Duplicates were removed by the CSV reader
- [x] Money was parsed before deduplication (so `₹3,299` and `3,299.00` copies look different), or deduplication used a subset of columns
- [ ] The test fixture is wrong
> **Answer:** Rule order matters: exact duplicates are removed on the raw text first (148 rows on the real export). Every count is pinned so that an order mistake shows up immediately.

## 7. What you learned
- Test-first development with a pending list: one milestone at a time, red → green, small commits.
- Defensive loading and counted cleaning rules, and why their order matters.
- Point-in-time feature engineering with a single cut-off, and how to recognise leakage.
- Baselines, unpenalised logistic regression and grouped CV; metrics written from scratch and checked on hand-made cases.
- An honest evaluation for the decision: the call list, value, calibration, slices, fairness, leakage and a release gate.

## 8. Catch-up git commands
```bash
git fetch upstream --tags
git switch -c my-phase-4 phase-3-end
git diff phase-2-end phase-3-end --stat -- tracks/
git diff phase-3-end -- tracks/python/churncast/features.py     # compare one file with the reference
```
