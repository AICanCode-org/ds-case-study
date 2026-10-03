# ADR-0004: Unpenalised logistic regression, two baselines and a pre-registered champion rule

* **Status:** accepted
* **Date:** 2026-06-05
* **Deciders:** data science team, finance

## Context
Finance multiplies probabilities by prices; agents need reasons; three tracks must agree to 1e-6.

## Options considered
1. **Gradient boosting / random forest:** often better ranking; needs calibration, hyper-parameter tuning (another
   place to overfit the test), and explanations that are approximations; hard to make three tracks agree.
2. **Penalised logistic regression:** robust; the penalty strength is a tuning choice and scikit-learn's default
   (C = 1 with L2) differs from R's `glm`.
3. **Unpenalised logistic regression on raw features:** no tuning, well calibrated on the training distribution,
   exact contributions `b_j · (x_j − mean_j)`, the same maximum in every language.

## Decision
Option 3, compared with B0 (prior) and B1 (the retention team's rule). E2 (15 features) is champion only if its
mean CV AUC beats E1 (5 features) by ≥ 0.002. The linear predictor is summed feature by feature in contract order
(not a BLAS product) so that tied rows get bit-identical scores in every track.

## Consequences
The model is easy to explain and serve. A more flexible challenger can be added later through the same gate. The
feature-by-feature sum was introduced after a parity incident: R's matrix product scored two identical rows an ulp
apart, which changed tie order and moved average precision by about 5e-6.
