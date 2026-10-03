# ChurnCast specification

The **contract** (what every track computes, exactly) lives in [`../contract/`](../contract/feature-spec.md) and is
provided on `main`. This folder holds the documents you write yourself, before the code:

| File | What it is | Written in |
|---|---|---|
| `requirements.md` | The brief as a prediction problem: decision, unit, snapshot, label, costs of errors, success criteria, risks | Phase 1 |
| `modelling-plan.md` | Timeline and splits, baselines, candidate models, the champion rule, metrics, the gate, what would stop a release | Phase 2 |
| `adr/` | Architecture/analysis Decision Records (one decision per file: tools, validation, fairness, serving) | Phase 2+ |

How they relate: `requirements.md` says *what* must be decided and how good the model must be; `modelling-plan.md`
says *how* models will be compared before anyone sees a test score (so the evaluation cannot be bent towards the
model someone likes); `contract/feature-spec.md` pins the exact rules so three implementations agree.
