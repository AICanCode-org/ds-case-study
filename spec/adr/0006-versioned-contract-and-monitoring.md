# ADR-0006: A versioned data contract, monthly monitoring and a champion/challenger gate

* **Status:** accepted
* **Date:** 2026-08-04
* **Deciders:** data science team, Head of Growth, marketing

## Context
The 2026-07 export contains a new acquisition channel (`influencer`, launched June 2026). The v1.0 pipeline stops
with exit 3 (`customers.channel.accepted`). At the same time, churn rose from about 9 % to 16.7 % and the deployed
model's ECE on June grew from 0.008 to 0.059.

## Options considered
1. **Map unknown values to `unknown` in the cleaning code:** the run never stops again; the next new value is hidden
   too, and nobody decided anything.
2. **Turn the check into a warning:** same problem, with a log line nobody reads.
3. **Version the contract:** 1.1.0 accepts `influencer`, keeps 1.0.0 in `contract/history/`, adds a monitoring
   section (PSI per feature, realised performance of the deployed model per month) and a champion/challenger
   comparison on a holdout month.

## Decision
Option 3. A contract change is a reviewed PR with a version bump; v1.1 must reproduce every v1.0 number on the
2026-05 export (`parity.py --backcompat`). Monitoring says `retrain` when a labelled month breaks a performance
alert (ECE > 0.03, |mean predicted − observed| > 0.02, AUC < 0.72) and `watch` when only a feature drifts (PSI ≥
0.25). The challenger (same features, refitted, intercept recalibrated on the recent month) is promoted only if, on
a holdout month neither model has seen, its AUC is at most 0.005 below the champion's, its Brier is lower, its ECE
≤ 0.03 and its recall gap ≤ 0.15. Schema changes are additive, so the API serves any 1.x artefact.

## Consequences
The run still stops on the next surprise, which is the point. On the 2026-07 export monitoring says `retrain`
(on May 2026 the deployed model predicts 9.1 % churn against 14.0 % observed, ECE 0.049; `price_change_pct` drifted
with PSI 1.22 in June) and the recalibrated challenger is promoted (holdout 2026-06: ECE 0.013 vs 0.059, AUC 0.773
vs 0.770). See the
post-mortem `docs/postmortem-2026-07.md`.
