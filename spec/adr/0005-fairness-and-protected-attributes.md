# ADR-0005: Age band is protected: never a feature, always a fairness check

* **Status:** accepted
* **Date:** 2026-06-05
* **Deciders:** data science team, Head of Growth, legal

## Context
The export has `age_band`. Age is predictive of churn in many subscription businesses, and a call list that
systematically skips one age group would mean those customers never get a retention offer.

## Options considered
1. **Use age band as a feature:** may add AUC; treats customers differently for who they are.
2. **Drop it entirely:** simple; we could no longer see whether the model is unfair through correlated features.
3. **Keep it out of the model, use it to measure the call list:** no direct use, and unfairness by proxy stays visible.

## Decision
Option 3. `age_band` is in `protected_columns`. The gate checks the recall gap of the call list across age bands
with at least 30 churners (`unknown` excluded): it must be ≤ 0.15. The AI explainer never sees or mentions age.

## Consequences
v1.0's recall gap is 0.115 (passes). The threshold is a policy choice reviewed with the business, not a statistical
truth. Recall equality is one fairness definition among several; the model card says so.
