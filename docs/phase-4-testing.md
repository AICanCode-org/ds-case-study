---
phase: 4
slug: phase-4-testing
title: "Testing data and models: golden files, invariants, leakage, parity"
duration: 4 h
start_tag: phase-3-end
end_tag: phase-4-end
---
# Phase 4 · Testing data and models: golden files, invariants, leakage, parity

## 1. Why it matters
Unit tests on a tiny fixture prove that each rule does what it says. They do not prove that the whole pipeline,
on the real export, produces the model you think it does, or that the next refactor will not move a number. Data
and model tests close that gap: **golden files** pin every output, **invariants** state truths that must hold for
any export, **leakage tests** try to smuggle the future in, **contract-violation tests** feed broken exports and
expect the run to stop, and **model-quality tests** encode the release criteria. On top, three independent
implementations must agree. When all of this is green you can change code without fear, which is what Phase 7
will ask of you.

## 2. Objectives
By the end of this phase you can:
- Explain the difference between unit, data, model and parity tests, and what each one catches.
- Pin `metrics.json` and `model.json` to golden files with tolerances that match the maths (1e-6 for fits, 1e-9 for features).
- Write invariants: rows read = kept + dropped, features inside their contract range, one row per customer and snapshot, contributions that add up to the prediction.
- Prove there is no leakage: adding future rows to an export must not change any past feature.
- Reach the 85 % line-coverage gate with unit + data tests, and show that training twice gives identical results.

## 3. Step-by-step instructions

### Step 4.1 · Switch on the data tests
Remove the five data entries from the pending list (`test_golden`, `test_invariants`, `test_leakage`,
`test_contract_violations`, `test_model_quality`) and run the full suite with coverage:

<!-- track:python -->
```bash
cd tracks/python && make coverage         # unit + data tests, fails below 85 % line coverage
```
<!-- /track -->
<!-- track:sql -->
```bash
cd tracks/sql && make coverage            # unit + data tests, fails below 85 % line coverage of the runner
```
<!-- /track -->
<!-- track:r -->
```bash
rdev make coverage                         # covr over unit + data tests, fails below 85 %
```
<!-- /track -->
If a data test fails, the message names the JSON path or the invariant. Fix the code, never the golden file.

### Step 4.2 · Golden files and tolerances
`test_golden` compares your run with `contract/golden/metrics-2026-05.json` and `model-2026-05.json` through
`scripts/parity.py` (`feature-spec.md` §8): integers, strings, booleans and list lengths exactly; floats to 1e-6
absolute + relative. Why not exact? Two optimisers (Newton-Cholesky, IRLS) converge to the same maximum, not to
the same last bit. Why not 1e-3? Because a real bug (a wrong rule, a missed row) usually moves a number by much
more than 1e-6 and much less than 1e-3. Read `parity.py`'s output on a deliberately broken run: it prints every
differing path.

### Step 4.3 · Invariants
Read `test_invariants` and make sure you can explain each:
- rows read = rows kept + every issue count, per table;
- every feature inside its contract `[min, max]`;
- exactly one row per (customer, snapshot); no customer in two folds; every test month after every train month;
- labels present for every train and test row;
- for any customer, intercept + Σ contributions + Σ b_j · mean_j = the log-odds the artefact computes.

### Step 4.4 · Leakage and contract violations
- `test_rows_from_the_future_do_not_change_past_features` copies the export, appends invoices, usage and tickets
  dated *after* each snapshot, re-runs, and expects every past feature to be identical. This is the strongest
  leakage test you can write: it does not need to know where the leak would be.
- `test_the_leaky_column_would_have_looked_like_the_best_feature`: the probe AUC must be higher than every real
  feature's, and `cancellation_reason` must not appear in the artefact.
- `test_contract_violations` breaks a copy of the export four ways (an unknown plan, a reused invoice id, an export
  with no renewals, an impossible meal count) and expects **exit code 3** with the failing check's id.

### Step 4.5 · Model quality and determinism
`test_model_quality` encodes Phase 1's criteria: the gate passes; the champion beats B0 and B1; the champion was
chosen on CV, not on the test months; CV is stable (SD of fold AUCs small); calibration and fairness within
limits; the campaign is worth more than the rule; and **training twice gives identical results**.

### Step 4.6 · Parity across tracks
If you can, run a second track (or download the reference outputs from a CI run of the `solution` branch) and
compare:
```bash
python3 scripts/parity.py tracks/python/out/features.csv tracks/sql/out/features.csv tracks/r/out/features.csv
python3 scripts/parity.py contract/golden/metrics-2026-05.json tracks/*/out/metrics.json
```
The reference tracks agree to about 1e-14 on metrics. When they did not (a ranking tie broken differently, see the
linear-predictor hint), the parity check found a real bug in one track before any user did.

## 4. AI-assist prompts

### Prompt 1: Propose invariants
```text
Here is the output schema of my churn pipeline: <paste contract/metrics.schema.json, shortened> and the feature
definitions: <paste feature-spec.md §3-§4>. Propose invariants that must hold for ANY export (not just this one):
row accounting, ranges, uniqueness, time ordering, consistency between metrics.json and model.json. For each,
write the assertion in <pytest | testthat> and say what bug it would catch.
```
**Verify the output by:** running each assertion on the real export (it must pass) and on a deliberately broken
copy (it must fail); discard invariants that only hold for this dataset (e.g. "churn is between 8 % and 11 %").

### Prompt 2: Write a leakage test that does not know where the leak is
```text
I have a function build_features(export) for month-end churn snapshots with cut-off S = first instant of M+1.
Write a test that copies an export, appends rows dated on or after each snapshot's cut-off to every event table
(invoices, usage, tickets), rebuilds the features and asserts that all features of past snapshots are unchanged.
Use <pandas | DuckDB | dplyr>. Keep the appended rows valid under the data contract.
```
**Verify the output by:** introducing a leak on purpose (count tickets with `created <= S` instead of `< S`) and
checking that the test fails, then removing it. A leakage test that cannot fail is decoration.

### Prompt 3: Explain a golden-file difference
```text
parity.py reports: <paste the DIFFERENT lines>. My change was: <describe or paste the diff>. Which rule of
feature-spec.md could explain the difference, which numbers should change together if my change is correct, and
how do I confirm it is a bug rather than an improvement?
```
**Verify the output by:** checking whether the changed paths are exactly the ones the rule touches; if more numbers
moved than the rule explains, it is a bug. Golden files change only with a contract change and agreement of all
three tracks.

## 5. Deliverables
- [ ] All data and model tests un-pended and green; `make coverage` ≥ 85 %.
- [ ] `parity.py` MATCH against both golden files.
- [ ] One invariant or leakage test of your own (beyond the suite), with a commit that shows it failing on a planted bug.
- [ ] A merged PR with green CI and an `AI_LOG.md` entry.

## 6. Self-check quiz

### Q1. Why are golden files compared with a tolerance of 1e-6 rather than exactly?
- [ ] JSON cannot store exact floats
- [x] Different optimisers converge to the same maximum-likelihood estimate but not to the last bit; 1e-6 is far tighter than any real bug and looser than solver noise
- [ ] To make the tests pass more often
- [ ] Because the data is synthetic
> **Answer:** Tolerances must match the maths. Features are plain arithmetic and are compared to 1e-9; fitted numbers to 1e-6.

### Q2. What does "rows read = rows kept + rows dropped" protect against?
- [ ] Slow pipelines
- [x] A rule that silently drops or duplicates rows without counting them, for example a join that fans out
- [ ] Missing values in features
- [ ] Wrong AUC
> **Answer:** Every cleaning rule counts what it removes. If the accounting does not balance, some step changed the row count without saying so.

### Q3. Why does the leakage test append *future* rows instead of checking each feature's SQL or code?
- [ ] It is shorter
- [x] It does not need to know where a leak could be: any feature that changes when only the future changes is using the future
- [ ] It tests the CSV reader
- [ ] Future rows are invalid and must be rejected
> **Answer:** It is a metamorphic test: a transformation of the input (adding the future) with a known effect on the output (none on the past).

### Q4. A broken export has an unknown plan `family`. What should happen?
- [ ] The rows with that plan are dropped and counted
- [ ] The plan is mapped to `basic`
- [x] The `invoices.plan.accepted` error check fails and the run stops with exit code 3, naming the check
- [ ] The model trains without the plan features
> **Answer:** An unknown category would silently change the plan features. Stopping is the safe default; the contract decides, not the code.

### Q5. Why test that training twice gives identical results?
- [ ] To measure speed
- [x] Non-determinism (random seeds, thread-dependent sums, unordered groupbys) makes every other comparison unreliable and a model impossible to audit
- [ ] Because CI runs twice
- [ ] It checks the coverage gate
> **Answer:** Reproducibility is a precondition for golden files and parity. The SQL track pins DuckDB to one thread for the same reason.

### Q6. Python and SQL agree on every metric, R differs only in average precision by 5e-6. What is the most likely cause?
- [ ] R cannot compute average precision
- [x] Two rows with identical features score a last bit apart in one track, so a tie is broken differently; check how the linear predictor is summed
- [ ] The golden file is wrong
- [ ] R rounds floats to 5 decimals
> **Answer:** Ranking metrics are sensitive to ties. Summing the linear predictor feature by feature (not with a BLAS matrix product) gives bit-identical scores for identical rows in every track.

## 7. What you learned
- The test pyramid for data science: unit (rules), data (real export), model (release criteria), parity (implementations).
- Golden files with tolerances that match the maths, and how to read a difference.
- Invariants, metamorphic leakage tests and contract-violation tests that need no knowledge of the bug.
- Determinism as a requirement, and why three implementations are a powerful test.

## 8. Catch-up git commands
```bash
git fetch upstream --tags
git switch -c my-phase-5 phase-4-end
git diff phase-3-end phase-4-end --stat
```
