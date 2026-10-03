# Post-mortem CC-2026-07: the July export stopped the pipeline, and the model had drifted

* **Status:** closed (2026-08-06, v1.1.0)
* **Authors:** data science team · **Reviewed with:** Head of Growth, marketing, finance
* **Blameless:** this document is about systems and decisions, not people.

## Summary
On 2026-08-03 the monthly retraining run on the 2026-07 export stopped with exit code 3:
`contract error: contract check(s) failed: customers.channel.accepted`. Marketing had launched an **influencer**
acquisition channel in June 2026 (182 customers in the export); data contract 1.0.0 did not accept the value. The
investigation found a second, larger problem the v1.0 pipeline had no way to see: churn had risen from about 9 % to
14.0 % (May) and 16.7 % (June), and the deployed model under-predicted it (mean predicted 9.1 % and 10.8 %; ECE
0.049 and 0.059 against a gate of 0.03). Its ranking was still good (AUC 0.771 and 0.770).

## Impact
- The August call list was built three days late, from the v1.0 model, by hand.
- Finance's May and June retention budgets, sized from predicted probabilities, under-estimated the number of
  churners by roughly a third.
- No wrong model was shipped: the contract stopped the run before any output was written.

## Timeline (IST)
| When | What |
|---|---|
| 2026-06 | Influencer channel launched by marketing; first such signups. Standard plan price rises from ₹3,299 to ₹3,799 (June). |
| 2026-06-24 | v1.0.0 released (trained on the 2026-05 export). |
| 2026-08-03 10:20 | The 2026-07 export arrives; the run exits 3 on `customers.channel.accepted`. |
| 2026-08-03 11:05 | Failing rows inspected: 182 customers with `influencer`. Marketing confirms the launch. |
| 2026-08-03 15:30 | Deployed model scored on the labelled months May and June by hand: calibration far off. |
| 2026-08-04 | ADR-0006: contract 1.1.0 (channel accepted, monitoring, retraining), reviewed with marketing and finance. |
| 2026-08-06 | v1.1.0 released: monitoring status `retrain`, challenger promoted (`churncast-1.1.0.json`). |

## Root causes
1. **No channel from upstream changes to the data contract.** Marketing changed the business; nobody told the
   owners of the model. The contract check did its job, but only at the next retraining.
2. **No monitoring of the deployed model.** v1.0 evaluated the model once, at release. Nothing compared its
   predictions with what happened in May and June, so a calibration drift of two months went unnoticed.
3. **The model's intercept encodes the base rate.** A logistic regression fitted when churn was ~9 % keeps
   predicting ~9 % when churn rises; ranking survives such a shift, calibration does not.

## What went well
- The run stopped instead of silently mapping the new value to `unknown`; nothing wrong was published.
- The three tracks and the golden files made the fix verifiable: v1.1 reproduces every v1.0 number on 2026-05.

## What we changed (v1.1.0)
- Contract 1.1.0 accepts `influencer`; 1.0.0 is kept in `contract/history/`.
- Monthly monitoring in the pipeline (`feature-spec.md` §9): PSI per feature and score against the training rows
  (`price_change_pct` PSI 1.22 in June: the price increase; `tenure_months` 0.25 in July), realised performance per
  labelled month, alerts and a status.
- A champion/challenger rule decided on a holdout month: the refitted, recalibrated challenger was promoted
  (2026-06 holdout: AUC 0.773 vs 0.770, Brier 0.113 vs 0.119, ECE 0.013 vs 0.059, recall gap 0.111 vs 0.109).
- API 1.1: request ids, JSON logs, Prometheus metrics (fallback rate of the AI explainer).

## Action items
| # | Action | Owner | Status |
|---|---|---|---|
| 1 | Marketing and product announce new channels, plans and prices in the data channel two weeks ahead | Head of Growth | done |
| 2 | Run monitoring on every export, even when no retraining is planned (runbook §6) | data science | done |
| 3 | Measure the save rate with a randomised hold-out (the value estimate still assumes 25 %) | Head of Growth | open |
| 4 | Investigate why churn rose (pricing? the new channel's customers?) before the next price change | data science + finance | open |
