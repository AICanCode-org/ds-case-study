# ChurnCast requirements

> **Phase 1 deliverable.** Replace every `TODO` below. Keep it short: a reviewer should be able to read this in ten
> minutes. The reference version is on the `solution` branch at tag `phase-1-end`
> (`git show phase-1-end:spec/requirements.md`). Try on your own first!

## 1. The decision
TODO: who decides what, how often, with which capacity, and what each kind of error costs (calling a customer who
would have stayed; not calling one who leaves). One paragraph.

## 2. Stakeholders
TODO: at least four (Head of Growth, retention agents, finance, data/engineering, customers): what each needs from
the model and what could go wrong for each.

## 3. The prediction problem
TODO: the unit (one row = ?), the snapshot (when is the prediction made?), the label (what exactly is "churn"?),
the horizon, which data may be used at prediction time and which may not (and why).

## 4. Success criteria (agreed BEFORE modelling)
TODO: the metrics that matter for this decision (ranking, calibration, the call list, value), the baseline to beat,
the release thresholds, and where each number comes from.

## 5. Data and its limits
TODO: what the export contains, what it cannot tell you (no causal effect of a call, synthetic, 17 months, one
country), and the known data-quality problems.

## 6. Acceptance criteria for the pipeline
TODO: at least 8, testable: reproducible from a clean checkout, every cleaning rule counted, error checks stop the
run, no feature uses the future, numbers identical across tracks, the gate blocks a bad model, ...

## 7. Risks and how the plan handles them
TODO: at least five (leakage, a random split that hides drift, an over-confident model, unfair call lists, a rule
of thumb that is better than you think, an AI explanation that invents a number, ...).

## 8. Out of scope (v1)
TODO
