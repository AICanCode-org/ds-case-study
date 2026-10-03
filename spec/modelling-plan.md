# ChurnCast modelling plan

> **Phase 2 deliverable**, written before any model is trained. Replace every `TODO`. The reference version is at
> tag `phase-2-end` (`git show phase-2-end:spec/modelling-plan.md`).

## 1. Timeline and splits
TODO: snapshot months for training and test, why the test months come last, how folds are built and why by customer.

## 2. Baselines
TODO: the two baselines every model must beat, and why each one is there.

## 3. Candidate models and features
TODO: which models, which feature sets, why this model family first, and the rule that picks the champion.

## 4. Metrics and the release gate
TODO: each metric, what it tells the business, and the threshold that blocks a release.

## 5. Leakage, fairness and what would stop us
TODO: how leakage is prevented and detected, the fairness check, and the results that would mean "do not ship".

## 6. The pipeline
TODO: the steps from raw export to model.json, with the outputs each step writes.
