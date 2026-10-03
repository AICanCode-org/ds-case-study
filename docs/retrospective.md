# ChurnCast retrospective (reference solution, v1.0.0 → v1.1.0)

Format: *What went well / What didn't / What I'd change*, plus one technical, one process and one AI lesson, as
asked in Phase 8. Written by the maintainers who built the reference solution. Yours will (and should) look
different.

## Results in one table
| | v1.0.0 (2026-05 export) | v1.1.0 (2026-07 export) |
|---|---|---|
| Champion | E2, logistic regression on 15 features | the same features, refitted on 17,010 rows and recalibrated |
| Ranking | test AUC 0.743 (rule of thumb 0.651) | holdout 2026-06 AUC 0.773 (deployed v1.0: 0.770) |
| Calibration | ECE 0.008 | holdout ECE 0.013 (deployed v1.0: 0.059) |
| Call list (top 10 %) | recall 30.2 % vs 21.4 % for the rule; ₹109,786 a month at a 25 % save rate | |
| Fairness | recall gap across age bands 0.115 (gate 0.15) | 0.111 on the holdout |
| Monitoring | none | status `retrain`; `price_change_pct` PSI 1.22 (June), `tenure_months` 0.25 (July) |

## What went well
- **The decision came first.** Requirements fixed the capacity (10 % of customers), the metrics that matter for it
  and the six gate checks before any model was trained. Nobody could argue for a model with a nicer accuracy.
- **Leakage was designed out, then tested.** Point-in-time snapshots, the future-rows test and the leakage scan
  caught two AI suggestions that would have used the future (`open_tickets` from the final table state, a
  shuffled split). The probe on `cancellation_reason` (AUC 0.88) made the danger concrete for the team.
- **The champion rule held under pressure.** On the test, E1's call list was slightly better than E2's. The plan
  said the CV decides; we kept E2 and wrote down why.
- **Three tracks agreed, and the disagreement taught us something.** Parity caught a tie-ordering bug (a matrix
  product summed in a different order) that no unit test had found; the spec now says how to add the terms.
- **The contract stopped the run.** On the July export v1.0 exited 3 instead of training on a new channel; no
  wrong model was shipped.

## What didn't go well
- **No monitoring in v1.0.** For two months the deployed model under-predicted churn (9.1 % predicted vs 14.0 %
  observed in May), and finance sized budgets from those numbers. We found it only because the contract check
  stopped the July run.
- **R in CI was slow at first.** Building the pinned toolchain image takes minutes on a cold runner; it became fast
  only once the image layers were cached between runs.
- **The value estimate is still an assumption.** The 25 % save rate has never been measured; the most
  business-relevant number of the project is the least validated.

## What I'd change
- Monitor from the first release: the deployed model scored on every new labelled month, with alerts.
- Agree a randomised hold-out with the retention team from day one, so the save rate is measured, not assumed.
- Add an upstream-change checklist (new channels, plans, prices) to the monthly export, owned by the business.

## Three lessons
- **Technical:** ranking and calibration fail differently. A base-rate shift left the AUC almost unchanged and
  broke the probabilities; recalibrating the intercept fixed most of it. Monitor both.
- **Process:** write the decision rules (champion, gate, promotion) before seeing the numbers they decide.
- **AI:** assistants were fastest at boilerplate, tests and explanations, and most dangerous on time: twice they
  suggested features or splits that silently used the future. The tiny fixture and the leakage tests were the
  judges, not the assistant's confidence.

## What's next
A randomised hold-out to measure the save rate; uplift modelling to call the persuadable customers rather than the
likely churners; a gradient-boosted challenger through the same gate; monitoring on a schedule.
