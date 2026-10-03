# ADR-0002: Monthly point-in-time snapshots, and a leakage scan in the gate

* **Status:** accepted
* **Date:** 2026-06-04
* **Deciders:** data science team, Head of Growth

## Context
The export is the *current* state of four tables. A model trained on "the customer table as it is today" would
use information that did not exist when the decision was made (tickets resolved later, the cancellation reason).
Such a model looks excellent offline and fails in production.

## Options considered
1. **One row per customer, features from the whole history:** simple; leaks the future and has no honest label.
2. **One row per customer and month-end snapshot, features strictly before the cut-off:** more rows and more
   careful code; the training data looks exactly like the data at prediction time.

## Decision
Option 2 (`feature-spec.md` §3-§4): a snapshot is month M's paid customers, the cut-off is the first instant of
M + 1, every feature uses only rows before it, a missing usage month counts as zero. `cancellation_reason` is in
`leaky_columns` and never a feature. The gate includes a leakage scan: every single-feature training AUC must stay
below 0.90; a probe reports what the banned column would score (0.88) to show why.

## Consequences
A test appends future rows to every table and expects identical past features. Point-in-time logic is the part
of the code most worth reviewing, and the reason the SQL track exists as an independent implementation.
