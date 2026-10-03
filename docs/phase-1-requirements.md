---
phase: 1
slug: phase-1-requirements
title: "Problem framing: the decision, the label and success criteria"
duration: 2.5 h
start_tag: phase-0-end
end_tag: phase-1-end
---
# Phase 1 · Problem framing: the decision, the label and success criteria

## 1. Why it matters
Most failed data science projects fail before the first line of code: the model predicts the wrong thing, at the
wrong time, for a decision nobody makes. "Predict churn" is not a problem statement. *Who* is scored, *when*, with
*which* data, *what* exactly counts as churn, and *what happens* to the people at the top of the list? In this
phase you turn the Head of Growth's question into a prediction problem with a unit, a snapshot, a label and a
horizon, write down what each kind of error costs, and agree success criteria **before** anyone sees a model
score, so that the evaluation cannot be bent later towards the model someone likes.

## 2. Objectives
By the end of this phase you can:
- State the decision, its frequency and its capacity constraint, and the cost of a false alarm versus a missed churner.
- Define the prediction problem precisely: one row per customer and month-end snapshot, label = no paid renewal next month.
- Say which data may be used at prediction time and which may not (and why `cancellation_reason` and `age_band` are excluded from the features).
- Write success criteria tied to the decision: beat the rule of thumb on the call list, honest probabilities, a fairness check.
- Write requirements with at least eight testable acceptance criteria and five risks, and merge them as `spec/requirements.md`.

## 3. Step-by-step instructions

### Step 1.1 · The decision and its economics
1. Read `contract/feature-spec.md` §1 and the `evaluation` block of `contract/data-contract.yaml`
   (`top_percent`, `offer_cost_inr`, `save_rate`, `value_months`).
2. Work out the economics of one call by hand: a call + offer costs ₹200; if the customer would have churned and
   the offer saves 25 % of them, a saved customer is worth 3 months of their price. For a Standard customer at
   ₹3,299, what is the expected value of calling a true churner? Of calling someone who would have stayed?
3. Write the paragraph *The decision* in `spec/requirements.md`: who decides, monthly, 10 % capacity, the two
   kinds of error and which one is more expensive. Note that `save_rate` is an **assumption** nobody has measured.

### Step 1.2 · Unit, snapshot, label, horizon
Answer these in `spec/requirements.md` §3, then compare with `feature-spec.md` §3:
- **Unit:** one row = one customer at one month-end snapshot. Why not one row per customer?
- **Who is in a snapshot:** only customers with a *paid* charge for month M. Why not every customer ever?
- **Label:** churned = no paid charge for month M + 1. What about a failed payment that is retried? A refund?
- **Horizon:** one month. Why is "will this customer ever leave?" useless for a monthly call list?
- **Prediction time:** the end of month M. Which data exists then, and which (the label, the cancellation reason,
  a ticket created on the 3rd of M + 1) does not?

### Step 1.3 · Stakeholders and what they need
List at least four: the Head of Growth (who to call), retention agents (why this customer: a reason they can talk
about), finance (a budget: honest probabilities), the customers themselves (not treated differently because of
their age), and engineering (a model they can serve and roll back). For each, write what they need from the model
and what could go wrong for them.

### Step 1.4 · Success criteria, agreed before modelling
Write them as numbers with a reason each. The reference uses (`data-contract.yaml` → `gate`):

| Criterion | Threshold | Why |
|---|---|---|
| Ranking on unseen months | test AUC ≥ 0.72 | below that, the call list is barely better than the rule |
| Beat the rule of thumb | AUC uplift ≥ 0.03 over B1 | otherwise keep the rule: it is free and everyone understands it |
| Honest probabilities | ECE ≤ 0.03 | finance multiplies them by prices |
| Better than a constant | Brier < the prior's Brier | a model that cannot beat the base rate is noise |
| Fair call list | age-band recall gap ≤ 0.15 | no age group may be systematically missed |
| No leakage | no single feature with AUC ≥ 0.90 | a feature that good is usually the label in disguise |

The champion is chosen by **cross-validation on the training months**, never by the test score; the test months
are used **once**.

### Step 1.5 · Acceptance criteria, risks, scope
1. At least eight testable acceptance criteria for the *pipeline* (reproducible from a clean checkout; every
   cleaning rule counted; an `error` check stops the run with exit code 3; no feature uses data after the cut-off;
   the three tracks agree; the gate blocks a bad model; the report runs top to bottom; the model card is generated).
2. At least five risks with a mitigation each: leakage, a random split that hides drift, over-confident
   probabilities, an unfair call list, a rule of thumb that is better than expected, an AI explanation that invents
   a number, a model that silently decays after launch.
3. Out of scope for v1: causal uplift modelling (who is *persuadable*), real-time scoring, other countries.
4. Commit on a branch, open a PR, merge when CI is green.

## 4. AI-assist prompts

### Prompt 1: Challenge my label definition
```text
I am building a monthly churn model for a meal-subscription business. Snapshot = end of month M, for every
customer with a paid charge for M. Label = 1 if there is no paid charge for month M+1. Features may use only data
known before the first day of M+1. Act as a sceptical reviewer: list every way this label could be wrong or
misleading (failed payments, pauses, refunds, customers who come back, the last month of the export), say which
ones matter for a monthly call list, and propose a test for each. Do not suggest a different business.
```
**Verify the output by:** checking each case against `feature-spec.md` §3 and the raw `invoices.csv` (does the
data even have pauses?), and keeping only the cases you can test on the tiny fixture. An assistant often invents
fields (a `paused` flag) that this export does not have.

### Prompt 2: Turn success criteria into numbers
```text
Our retention team can call 10 % of active customers per month. A call + offer costs ₹200, an offer saves an
assumed 25 % of would-be churners, and a saved customer is worth 3 months of their plan price (₹2,499, ₹3,299 or ₹4,499).
Help me write success criteria for a churn model as measurable thresholds: which metrics (ranking, calibration,
the call list, value, fairness) and why each one serves this decision. Explain what AUC, precision@10 %, Brier and
expected calibration error each tell a business person, in one sentence each.
```
**Verify the output by:** recomputing any value it quotes by hand (expected value of one call), rejecting
thresholds it presents as industry standards without a source, and checking that every criterion can be computed
from `metrics.json` (`contract/metrics.schema.json`).

### Prompt 3: Find the risks I missed
```text
Here are my requirements for a churn model: <paste spec/requirements.md>. List the five most likely ways this
project could produce a model that looks good in evaluation but hurts the business or its customers after launch.
For each: how I would detect it before release, and how after.
```
**Verify the output by:** mapping each risk to a section of `feature-spec.md` or a planned test; a risk without a
detection method is a worry, not a plan. Keep leakage and drift on the list even if the assistant ranks them low.

## 5. Deliverables
- [ ] `spec/requirements.md` with the decision, stakeholders, the prediction problem, success criteria, data limits, at least 8 acceptance criteria, at least 5 risks and the scope.
- [ ] Your worked example of the economics of one call (in the requirements or the PR).
- [ ] A merged PR with green CI, and an `AI_LOG.md` entry for any prompt you used.

## 6. Self-check quiz

### Q1. Why is the unit "one customer at one month-end snapshot" rather than "one customer"?
- [ ] It makes the dataset bigger, which always helps
- [x] The decision is made every month with what is known at that month's end, so the model must learn from the same situation, many times per customer
- [ ] Customers change their id every month
- [ ] Logistic regression needs at least 10,000 rows
> **Answer:** The model must reproduce the moment of decision. A customer appears in every month they pay for; each row only knows the past of that month. (That is also why folds must keep a customer's rows together.)

### Q2. Which data may a feature for snapshot M use?
- [ ] Anything in the export
- [ ] Anything about the customer, including `cancellation_reason`
- [x] Only what was known before the first instant of month M + 1: invoices and usage up to M, tickets created before then, resolutions that happened before then
- [ ] Only month M itself
> **Answer:** The cut-off S = first instant of M + 1. Anything later (the label month, a later resolution, the cancellation reason) is the future. Using it is leakage.

### Q3. Why is the test set the *last* months rather than a random 20 % of rows?
- [ ] Random splits are not supported by scikit-learn
- [x] The model will always be used on future months; a random split lets it learn from the same months it is tested on and hides drift
- [ ] The last months have more churners
- [ ] It is faster
> **Answer:** An out-of-time test answers the real question: does a model trained on the past work next month? A random split usually overestimates performance.

### Q4. Why must the model beat the rule of thumb (B1), not just the prior (B0)?
- [x] The rule is what the team does today for free; a model is only worth its cost and complexity if it does better on the same call list
- [ ] The prior is always 0.5
- [ ] The rule uses more features than the model
- [ ] Beating B0 is impossible
> **Answer:** The relevant comparison is the current process. The gate requires an AUC uplift of at least 0.03 over B1.

### Q5. Finance multiplies the predicted probabilities by plan prices. Which property must the probabilities have?
- [ ] They must sum to 1 across customers
- [ ] They must be above 0.5 for churners
- [x] They must be calibrated: among customers given 20 %, about 20 % churn (low ECE)
- [ ] They must be rounded to two decimals
> **Answer:** A model can rank well (high AUC) and still be over- or under-confident. Calibration is measured with the expected calibration error and a reliability table.

### Q6. Why are the success criteria written down before any model is trained?
- [ ] The contract format requires it
- [ ] So that the test set can be used to tune them
- [x] So that the evaluation cannot be bent after seeing results towards the model someone prefers (the garden of forking paths)
- [ ] Because thresholds never change
> **Answer:** Criteria chosen after seeing scores tend to be chosen to pass. Pre-registration is the cheapest protection against fooling yourself.

## 7. What you learned
- A business request becomes a prediction problem through five choices: unit, snapshot, label, horizon, and prediction-time data.
- Capacity turns churn into a ranking problem; budgeting adds calibration; people add fairness.
- Errors have prices: the economics of one call tell you which metric matters.
- Success criteria and the champion rule are agreed before modelling, and the test months are used once.

## 8. Catch-up git commands
```bash
git fetch upstream --tags
git switch -c my-phase-2 phase-1-end
git show phase-1-end:spec/requirements.md     # the reference requirements
git diff phase-0-end phase-1-end --stat
```
