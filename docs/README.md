# ChurnCast documentation

Start with [Phase 0](phase-0-setup.md). Each phase lists its start and end tag in the header, so you can start any
phase from the reference state (`git switch -c my-phase-N phase-(N-1)-end`).

| # | Phase | Duration | Start | End |
|---|---|---|---|---|
| 0 | [Setup and the brief](phase-0-setup.md) | 1.5 h | `main` | `phase-0-end` |
| 1 | [Problem framing: the decision, the label and success criteria](phase-1-requirements.md) | 2.5 h | `phase-0-end` | `phase-1-end` |
| 2 | [Design: data contract, timeline, modelling plan and ADRs](phase-2-design.md) | 3.5 h | `phase-1-end` | `phase-2-end` |
| 3 | [Implementation in five milestones](phase-3-implementation.md) | 14 h | `phase-2-end` | `phase-3-end` |
| 4 | [Testing data and models](phase-4-testing.md) | 4 h | `phase-3-end` | `phase-4-end` |
| 5 | [CI with GitHub Actions and the evaluation gate](phase-5-ci.md) | 3 h | `phase-4-end` | `phase-5-end` |
| 6 | [Model card, prediction API, AI explainer, Docker and delivery](phase-6-deploy.md) | 5 h | `phase-5-end` | `phase-6-end` / `v1.0.0` |
| 7 | [Monitoring, drift, retraining and a post-mortem](phase-7-observability.md) | 5 h | `phase-6-end` | `phase-7-end` / `v1.1.0` |
| 8 | [Retrospective and portfolio](phase-8-retrospective.md) | 1.5 h | `phase-7-end` | `phase-8-end` |

Reference material:
- [GitHub Actions explained](github-actions-explained.md): triggers, jobs, matrix, caching, Docker toolchains,
  reusable workflows, artifacts, permissions, secrets vs variables, GHCR.
- [`../contract/`](../contract/feature-spec.md): the feature spec (every cleaning rule, feature, metric and gate
  check), the data contract, the metrics and model schemas, the fixtures and the golden files.
- [`../spec/`](../spec/README.md): requirements, modelling plan, ADRs.
- Solution branch only: `model-card.md` and `runbook.md` (Phase 6), `postmortem-2026-07.md` (Phase 7),
  `retrospective.md` (Phase 8).

## From the old six-step guide
The old guide had six steps. The site keeps them in order as the first six phases, and the content moved like this:

| Old step | Now |
|---|---|
| 0 · The Brief | Phase 0 (the brief, the data, the deliverables) |
| 1 · Frame the Problem | Phase 1 (decision, unit, snapshot, label, costs of errors, success criteria) and Phase 2 (timeline, modelling plan) |
| 2 · Clean and Explore | Phase 2 (the data contract) and Phase 3 M1-M2 (text-first loading, counted cleaning rules, contract checks) |
| 3 · Build Features | Phase 3 M3 (point-in-time features and labels; the leakage trap) |
| 4 · Model and Evaluate | Phase 3 M4-M5 (baselines, logistic regression, grouped CV, out-of-time test, calibration, capacity, fairness, gate) and Phase 4 (golden files, invariants, leakage tests, parity) |
| 5 · Recommend | Phase 6 (model card with the recommendation and its limits, the prediction API with explanations) |

## Page format
Every phase page has front matter (`phase`, `slug`, `title`, `duration`, `start_*`, `end_tag`, `release`) and the
same eight sections, which `scripts/build-cms.py` turns into `cms/ds-case-study.json` (project metadata comes from
`cms/project.json`):

1. Why it matters · 2. Objectives · 3. Step-by-step instructions (`### Step N.x`) ·
4. AI-assist prompts (`### Prompt n`, a `text` block, **Verify the output by**) · 5. Deliverables ·
6. Self-check quiz (`### Qn`, `- [ ]` / `- [x]`, `> **Answer:**`) · 7. What you learned ·
8. Catch-up git commands

Track-specific parts are wrapped in `<!-- track:python -->` … `<!-- /track -->` (also `sql`, `r`). The site shows
only the learner's track. On GitHub you see all three.
