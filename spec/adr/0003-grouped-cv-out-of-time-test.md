# ADR-0003: Grouped cross-validation on the past, one out-of-time test

* **Status:** accepted
* **Date:** 2026-06-05
* **Deciders:** data science team

## Context
A customer appears in up to six training snapshots. The model will be used on next month's customers.

## Options considered
1. **Random train/test split over all rows:** the most common default; the same customer and the same month on
   both sides, so the estimate is optimistic and drift is invisible.
2. **Time-series cross-validation (expanding window):** honest, but only six training months: early folds are
   tiny and noisy.
3. **5 folds grouped by customer on the training months for model selection, plus the last two months as a test
   used once:** model selection never sees a validated customer in training; the final estimate is out of time.

## Decision
Option 3. Fold = customer number mod 5 (deterministic, identical in every language); test months 2026-03 and
2026-04. The champion is chosen on the CV mean only, before the test is computed.

## Consequences
The test can disagree with the CV ranking (in v1.0 E1's call list is slightly better on the test than E2's); the
plan says we do not switch, because switching would turn the test into a second validation set.
