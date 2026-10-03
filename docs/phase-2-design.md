---
phase: 2
slug: phase-2-design
title: "Design: data contract, timeline, modelling plan and ADRs"
duration: 3.5 h
start_tag: phase-1-end
end_tag: phase-2-end
---
# Phase 2 · Design: data contract, timeline, modelling plan and ADRs

## 1. Why it matters
Two analysts given the same export and the same question will build different models, and both will believe their
own. The design phase makes the choices explicit and reviewable *before* the code: what a valid export looks like
(the data contract), which months train and which test (the timeline), which models are compared and how the
winner is picked (the modelling plan), and why each important decision was taken (ADRs). In this project the
design has one more job: the Python, SQL and R tracks must compute the same features to 1e-9, which is only
possible if every rule is written down exactly.

## 2. Objectives
By the end of this phase you can:
- Read and extend a data contract: files, columns, cleaning rules, checks with `error`/`warn` severities, features, experiments, gate.
- Draw the timeline: 6 training snapshots, 2 out-of-time test snapshots, the label month, the cut-off of each snapshot.
- Explain grouped cross-validation (fold = customer number mod 5) and why a random K-fold would leak.
- Write a modelling plan: two baselines, two logistic regressions, the champion rule, metrics and the gate.
- Record at least four decisions as ADRs (text-first loading, point-in-time features, validation design, the model family, fairness).

## 3. Step-by-step instructions

### Step 2.1 · The data contract, line by line
Open `contract/data-contract.yaml` next to `contract/feature-spec.md` §2. For each block, write one sentence in
your notes on what would break without it:
- `files`: the four tables, their keys and columns. A missing column is a contract error (exit 3).
- `cleaning`: date and timestamp formats (day first!), city aliases, `missing_label`, `rating_default`.
- `leaky_columns`, `protected_columns`: never features. `age_band` is used only for the fairness check.
- `checks`: 21 checks. Which ones are `warn` and why? (`customers.channel.missing_share` is a quality signal,
  not a reason to stop; an unknown city or plan would silently create a new category, so it is an `error`.)
Then answer: the June export adds a new acquisition channel. What happens? (You will live through it in Phase 7.)

### Step 2.2 · The timeline and the splits
Draw it, on paper or in Markdown, for the 2026-05 export:
```text
2025-01 ......... 2025-09 | 10 | 11 | 12 | 2026-01 | 02 || 03 | 04 || 05
history only       train snapshots (6)                     test (2)    label month of 2026-04 only
```
1. Each snapshot M has a cut-off S = the first instant of M + 1 and a label from month M + 1.
2. Why does the first training snapshot start in 2025-09 rather than 2025-01? (Features look back up to three
   months and `tenure_months` needs history; the very first months have almost no customers.)
3. Folds: `fold = customer number mod 5`. All snapshots of a customer are in one fold. Why would a plain
   `KFold(shuffle=True)` overestimate AUC here? (The same customer, one month apart, sits on both sides.)
4. The test months are scored **once**, after the champion is chosen.

### Step 2.3 · The modelling plan
Write `spec/modelling-plan.md` (the template has six sections):
- **Baselines:** B0 = the training churn rate for everyone (the floor); B1 = the team's five risk flags, each
  flag count mapped to its training churn rate (the bar to beat).
- **Candidates:** E1 = logistic regression on the 5 `core` features; E2 = logistic regression on all 15.
- **Why logistic regression first:** probabilities that are usually well calibrated, coefficients in business
  units ("each extra open ticket adds … to the log-odds"), exact per-feature explanations, and three tracks can
  reproduce it exactly (unpenalised maximum likelihood has one answer). A gradient-boosted model may be a later
  experiment, judged by the same gate.
- **Champion rule:** E2 only if its mean CV AUC beats E1 by at least 0.002 (`champion.min_cv_auc_gain_for_complexity`).
- **Metrics and gate:** copy them from the requirements; add what each tells the business.
- **What stops a release:** any gate check failing, an `error` contract check, or parity failing between tracks.

### Step 2.4 · ADRs
Use `spec/adr/0000-template.md`. The reference has five; write at least four:
1. **Read raw files as text** and parse every type by an explicit rule (type guessing hides defects).
2. **Point-in-time features at month-end snapshots** with a single cut-off S, and a leakage scan in the gate.
3. **Validation design:** grouped 5-fold CV by customer on the training months + an out-of-time test used once.
4. **Unpenalised logistic regression with baselines first**, the champion by a pre-agreed CV rule.
5. **Fairness and protected attributes:** `age_band` is never a feature; the recall gap of the call list across
   age bands is a gate check.

### Step 2.5 · Review and merge
Open a PR with the plan and the ADRs. Ask a reviewer (or an assistant, Prompt 3) to attack the validation design.
Merge when CI is green.

<!-- track:python -->
**Python track:** scan the pending tests named in `tests/conftest.py` now: `tests/unit/test_features.py` shows how
"point in time" is tested (`test_a_ticket_after_the_snapshot_is_invisible`, `test_the_label_needs_the_next_month`).
<!-- /track -->

<!-- track:sql -->
**SQL track:** read `sql/01_load.sql` (complete) and the stubs of `02`-`06`: each view is one rule of the spec. The
cut-off S becomes the column `cut` of the view `snapshot_base`; every join to tickets must compare with it.
<!-- /track -->

<!-- track:r -->
**R track:** read `R/features.R` stubs and `tests/testthat/test-unit-features.R`. In R, `rsample::manual_rset()`
builds the contract's folds; `vfold_cv()` would split customers across folds.
<!-- /track -->

## 4. AI-assist prompts

### Prompt 1: Review my timeline for leakage
```text
Monthly churn model. Snapshot M = end of month M; cut-off S = first instant of M+1; label = no paid charge for
M+1. Train snapshots 2025-09..2026-02, test 2026-03..2026-04; export ends 2026-05. Folds: customer number mod 5.
Features: tenure, plan, discount, price change vs M-1, meals and skips in M, meal trend vs M-1/M-2, late-delivery
rate and average rating over M-2..M, tickets in the 90 days before S, tickets still open at S, failed payments
M-2..M. Find every way information from after S could reach a feature or the validation, and how to test for it.
```
**Verify the output by:** turning every real issue into a unit test idea on the tiny fixture (e.g. a ticket
resolved after S counts as open), and rejecting suggestions that change the problem (e.g. "use a random split").
Check each point against `feature-spec.md` §3-§4.

### Prompt 2: Draft an ADR, then argue against it
```text
Draft an ADR (context, options, decision, consequences) for: "unpenalised logistic regression as the first churn
model, compared with a prior and a rule-of-thumb baseline, champion chosen by grouped CV AUC with a 0.002
complexity margin". Then write the strongest argument for choosing gradient boosting instead, and what evidence
would make us switch.
```
**Verify the output by:** checking every claim about a library (e.g. "scikit-learn's default is unpenalised" is
false: the default is L2 with C=1) against the official docs, and making sure the consequences section names the
numbers that could move.

### Prompt 3: Attack my validation design
```text
Here is my modelling plan: <paste spec/modelling-plan.md>. Act as a reviewer at a model-risk committee. Where
could this evaluation overestimate how well the model will work next month? Rank the issues by impact and say
which ones my plan already handles.
```
**Verify the output by:** answering each point with a section of your plan or a planned test, and adding the ones
you cannot answer to the risks in `spec/requirements.md`.

## 5. Deliverables
- [ ] Notes on what each block of `data-contract.yaml` prevents.
- [ ] The timeline drawn (in `spec/modelling-plan.md` §1).
- [ ] `spec/modelling-plan.md` complete: splits, baselines, candidates, champion rule, metrics and gate, stop rules, pipeline.
- [ ] At least four ADRs in `spec/adr/`.
- [ ] A merged PR with green CI.

## 6. Self-check quiz

### Q1. Why is fold membership derived from the customer id rather than assigned at random per row?
- [ ] It is faster to compute
- [x] All snapshots of a customer must sit in the same fold, or the model validates on customers it trained on one month earlier
- [ ] Random numbers differ between Python and R
- [ ] scikit-learn requires it
> **Answer:** Rows of the same customer are strongly correlated. Grouped folds keep them together; `customers_in_two_folds` must be 0. (A deterministic rule also lets the three tracks use the same folds.)

### Q2. An unknown city appears in an export. Why is that an `error` check and not a warning?
- [ ] Cities are protected attributes
- [x] It would silently create a new category or a missing city tier, changing features without anyone noticing; stopping is cheaper than a wrong model
- [ ] Error checks are faster
- [ ] The model uses the city as a feature
> **Answer:** Severity reflects the cost of continuing. A missing-channel share above 15 % is worth a warning; an unknown value in a category the pipeline maps is a contract break.

### Q3. Why compare against B1 (the rule of thumb) at all?
- [ ] It is required by scikit-learn
- [ ] It always loses
- [x] It is the current process; if the model cannot beat it clearly, keeping the rule is cheaper and easier to explain
- [ ] It provides the training labels
> **Answer:** Baselines anchor the evaluation. B0 shows what "no information" scores; B1 shows what the team already achieves.

### Q4. Why is unpenalised logistic regression a good first model here?
- [ ] It always has the highest AUC
- [x] It gives usually well-calibrated probabilities, coefficients in business units, exact per-feature explanations, and one reproducible answer across tracks
- [ ] It needs no features
- [ ] It cannot overfit
> **Answer:** With 15 features and ~12,000 rows, a linear model is a strong, transparent baseline. More complex models must beat it through the same gate.

### Q5. What is an ADR for?
- [ ] Listing the bugs found in review
- [x] Recording one important decision, the options considered and its consequences, so a later reader knows why things are the way they are
- [ ] Documenting the API
- [ ] Storing the hyper-parameters
> **Answer:** Architecture (or analysis) Decision Records are short, dated and never rewritten: a later decision supersedes an earlier one.

### Q6. Why does `age_band` appear in the contract at all if it is never a feature?
- [ ] For the data dictionary only
- [x] To measure fairness: the recall of the call list must not differ by more than 0.15 across age bands
- [ ] Because the model needs it to be accurate
- [ ] It is a leaky column
> **Answer:** Removing a protected attribute from the features does not make a model fair (other features can act as proxies). You must still measure outcomes by group.

## 7. What you learned
- A data contract makes "valid export" testable, with severities that say when to stop.
- The timeline (snapshots, cut-offs, labels, out-of-time test) and grouped folds are the backbone of an honest evaluation.
- A modelling plan written before training: baselines, candidates, a champion rule, metrics and a gate.
- ADRs capture the why behind decisions such as text-first loading, point-in-time features and fairness checks.

## 8. Catch-up git commands
```bash
git fetch upstream --tags
git switch -c my-phase-3 phase-2-end
git show phase-2-end:spec/modelling-plan.md
git diff phase-1-end phase-2-end --stat     # the plan and the ADRs
```
