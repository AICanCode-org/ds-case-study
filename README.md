# ChurnCast: an end-to-end data science case study on subscription churn, with AI as your pair data scientist

[![CI](https://github.com/AICanCode-org/ds-case-study/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/AICanCode-org/ds-case-study/actions/workflows/ci.yml)
[![CI (solution)](https://github.com/AICanCode-org/ds-case-study/actions/workflows/ci.yml/badge.svg?branch=solution)](https://github.com/AICanCode-org/ds-case-study/actions/workflows/ci.yml?query=branch%3Asolution)

## Case study (reference solution)

> **The retention team at TiffinBox could call 10 % of customers a month and picked them with five risk flags. A
> calibrated logistic regression on 15 point-in-time features finds 30 % of next month's churners in that 10 %
> (the flags find 21 %), worth about ₹1.1 lakh a month under a stated assumption. It is built three times, in
> Python, SQL and R, against one written spec, and all three produce the same model to 1e-6.**

```console
$ docker compose --profile train run --rm --no-deps parity-model
MATCH      /out/python/model.json (python)
MATCH      /out/sql/model.json (sql)
MATCH      /out/r/model.json (r)
$ python3 scripts/eval_gate.py tracks/python/out/metrics.json | tail -3
  PASS  recall_gap             value 0.1154  threshold 0.1500
  PASS  leakage_scan           value 0.7033  threshold 0.9000
gate PASSED
```

**Problem → answer.** After cleaning a deliberately messy export (12 counted issue types: two date formats,
duplicated rows, rupee prices as text, negative usage counts, orphans, tickets resolved before they were opened),
the pipeline builds monthly snapshots in which every feature uses only what was known before the month's cut-off,
and compares models with 5 folds grouped by customer, then once on two later months:

| Out-of-time test (2026-03, 2026-04) | Prior (B0) | Rule of thumb (B1) | **Champion E2** |
|---|---|---|---|
| AUC | 0.500 | 0.651 | **0.743** |
| Brier | 0.0803 | 0.0780 | **0.0753** |
| Precision / recall of the 10 % call list | | 18.8 % / 21.4 % | **26.6 % / 30.2 %** (lift 3.0×) |
| Net value per month (25 % save rate, assumed) | | ₹63,001 | **₹109,786** |

The champion was chosen by a rule written before the test was computed (E2 beats the 5-feature E1 by 0.015 mean
CV AUC). On the test E1's call list is slightly better; we did not switch, because that would turn the test into a
second validation set. Calibration error 0.008, recall gap across age bands 0.115 (age is never a feature), no
feature above 0.70 single-feature AUC (the banned `cancellation_reason` would score 0.88). The six-check release
gate passes. See the [model card](docs/model-card.md).

**After launch.** The July export stopped the pipeline on a new acquisition channel (`influencer`), and monitoring
added in v1.1 showed why that mattered: churn had risen to 14-17 % after a price rise, and the deployed model,
still ranking well (AUC 0.77), under-predicted it (ECE 0.059). A refitted, recalibrated challenger was promoted on a
holdout month neither model had seen (ECE 0.013, AUC 0.773 vs 0.770). [Post-mortem](docs/postmortem-2026-07.md).

**Decisions I'd defend in an interview** ([modelling plan](spec/modelling-plan.md)):
[read raw files as text](spec/adr/0001-read-raw-files-as-text.md) ·
[point-in-time snapshots and a leakage scan](spec/adr/0002-point-in-time-snapshots.md) ·
[grouped CV and an out-of-time test](spec/adr/0003-grouped-cv-out-of-time-test.md) ·
[unpenalised logistic regression and a pre-registered champion rule](spec/adr/0004-unpenalised-logistic-regression.md) ·
[age band: never a feature, always a check](spec/adr/0005-fairness-and-protected-attributes.md) ·
[versioned contract and monitoring](spec/adr/0006-versioned-contract-and-monitoring.md).

**Evidence**

| | Python (pandas, scikit-learn, Jupyter) | SQL (DuckDB) | R (tidymodels, R Markdown) | API (FastAPI) |
|---|---|---|---|---|
| Tests v1.1.0 (unit + data + golden + invariants) | 110 | 108 | 91 `test_that` blocks | 38 |
| Line coverage (gate 85 %) | 99 % | 97 % | 98 % | 96 % |
| Parity with the golden files (2026-05, 2026-07, `--backcompat`) | MATCH | MATCH | MATCH | |

Features agree to 1e-9 and metrics and models to 1e-6 (observed differences about 1e-13). The Docker smoke test
passes against the API of v1.0.0 (8 checks) and v1.1.0 (10 checks), also with the AI provider unreachable (the
explainer falls back to its template and says so); the v1.0.0 API serves the v1.1 model. All images run as
non-root with a read-only file system; R is pinned to a dated package snapshot so CI and laptops agree.

- **Data contract:** declarative checks with severities; an `error` stops the run (exit 3) instead of training on
  changed data. Contract 1.1.0 keeps 1.0.0 in `contract/history/`.
- **Monitoring:** PSI per feature and score, realised performance per labelled month, alerts, a
  champion/challenger rule; Prometheus metrics and request ids in the API.
- **AI explainer:** an optional OpenAI-compatible model explains one score from numbered facts (the top
  contributions); guardrails reject invented numbers, unknown citations, certainty claims and sensitive
  attributes, with a deterministic fallback. It never sees a customer id and needs no paid key.

**How I used AI.** Assistants drafted code, tests and docs; every entry is in [`AI_LOG.md`](AI_LOG.md). Rejected: an
`open_tickets` feature that read the export's final state (leakage), scikit-learn's default L2 penalty (a
different model), a shuffled K-fold split, installing the latest R packages in CI, and an "unknown channel →
unknown" fix that would have hidden the influencer launch. Three-track parity caught a real bug that unit tests had
missed: a matrix product summed in a different order scored two identical rows an ulp apart and changed the tie
order of the call list.

**Limits and next steps.** The data is synthetic. The value estimate assumes that 25 % of contacted would-be
churners stay; predicting churn does not show that a call *causes* anyone to stay. Next: a randomised hold-out to
measure the save rate, uplift modelling (who is persuadable), a gradient-boosted challenger through the same gate,
and monitoring on a schedule.

ChurnCast is a guided project from **[AiCanCode](https://www.aicancode.org)**, the capstone of the Data Science
track. Over 9 phases (about 40 hours) you take **one messy subscription dataset the whole way** to a churn model
that a retention team can use: requirements, a data contract and a modelling plan, a test-first implementation,
data and model tests, CI, a prediction API in Docker, monitoring and retraining after the model goes live, and a
retrospective. AI assistants help at every step, and you **verify** every number they produce.

**The situation.** TiffinBox is a meal-subscription startup in Pune, Bengaluru, Hyderabad, Nagpur and Indore.
About **9 % of paying customers do not renew each month**. The retention team can call **10 % of active
customers a month** with a discount offer, and today they choose whom to call with a rule of thumb (five risk
flags). The Head of Growth asks: *at the end of each month, who is most likely to cancel next month, and why?*
Your job is a model that beats the rule on the people the team can actually call, with probabilities honest
enough for finance to budget with, and explanations a retention agent can act on.

**The data.** A 17-month export (January 2025 to May 2026) in four deliberately imperfect CSVs, with the problems
real exports have, and one trap: `customers.cancellation_reason` is filled in *after* a customer cancels.

| Table | Raw rows | Known problems |
|---|---|---|
| `customers.csv` | 5,409 | exact duplicates, two date formats, impossible dates, `Bangalore` / ` bengaluru` / `BENGALURU`, missing channel and age band, a leaky column |
| `invoices.csv` | 28,505 | exact duplicates, amounts like `₹3,299` / `3,299.00`, refunds and failed payments, orphans |
| `usage.csv` | 27,036 | exact duplicates, negative counts, orphans |
| `tickets.csv` | 6,165 | two timestamp formats, resolutions before creation, orphans |

**What you deliver:** a pipeline that turns any export into point-in-time features, compares two baselines with
two logistic regressions using grouped, out-of-time validation, and writes `metrics.json` and a language-neutral
`model.json`; a model card generated from the numbers; a FastAPI prediction API with explanations; and a report
(notebook or R Markdown) that runs top to bottom from a clean checkout. It is judged not on the highest AUC, but
on whether the evaluation is honest: no leakage, a fair comparison with the rule of thumb, calibrated
probabilities, a fairness check, and a clear statement of what the model cannot tell you.

**Pick one track.** The data, the contract, the golden files and the API are shared; only the pipeline code
differs, and the three tracks must produce **the same features to 1e-9 and the same metrics and model to 1e-6**.

| Track | Stack | Folder |
|---|---|---|
| Python | Python 3.12 · pandas · scikit-learn · Jupyter · pytest · ruff | `tracks/python` |
| SQL | DuckDB SQL for cleaning, features, labels and every metric · sqlfluff · a thin Python runner (the logistic fit is scikit-learn) · pytest | `tracks/sql` |
| R | R 4.6 · tidymodels (parsnip, rsample, yardstick) · dplyr · R Markdown · testthat · covr · lintr, pinned in a Docker image | `tracks/r` |

The prediction API (`serving/`, from Phase 6) serves any track's `model.json`. Its optional **AI explainer** sees
only numbered facts (the score and the top contributions, never a customer id or a protected attribute) and is
checked by guardrails; offline, it falls back to a deterministic template. Everything runs **on your laptop, with
no API key and no paid service**.

Course repository: **<https://github.com/AICanCode-org/ds-case-study>** (`main` = starter, `solution` = reference).

---

## Repository layout
```text
.
├── README.md                 ← you are here
├── AI_LOG.md                 ← your log of AI prompts, outputs and how you verified them
├── docs/                     ← the course: phase-0 … phase-8 + GitHub Actions explained
├── spec/                     ← requirements, modelling plan, ADRs (you write them in Phases 1-2)
├── contract/                 ← the shared contract: feature-spec.md (every rule), data-contract.yaml, the metrics
│                               and model schemas, the tiny fixture, metric cases and the golden files
├── data/raw/2026-05/         ← the export (CSV + export.json), generated by scripts/generate_data.py
├── tracks/{python,sql,r}/    ← pipeline code + tests (same Makefile targets in each)
├── serving/                  ← the prediction API + AI explainer (Phase 6)
├── models/                   ← released model artefacts (Phase 6)
├── scripts/                  ← doctor.sh, check-all.sh, verify-tags.sh, build-cms.py, parity.py, eval_gate.py,
│                               model_card.py, validate_outputs.py, generate_data.py (+ smoke-test.sh)
├── cms/                      ← machine-readable export of the course for the AiCanCode site
└── .github/                  ← CI workflows, issue/PR templates
```

## Prerequisites (per operating system)
You need **Git, `make` and Python 3.12+** (the scripts, the SQL runner and the API use it) plus the toolchain of
**one** track. The R track's toolchain is a Docker image (so your R, lintr and tidymodels versions are exactly
CI's); a local R 4.6 with `make install` works too. Docker is needed for every track from Phase 6. Run `scripts/doctor.sh` at any time.

| | Windows 10/11 | macOS | Linux (Ubuntu/Debian) |
|---|---|---|---|
| Shell | **WSL2** with Ubuntu: `wsl --install` in an admin PowerShell, reboot | Terminal (zsh) | any |
| Git, make | inside WSL: `sudo apt install git make` | `xcode-select --install` | `sudo apt install git make` |
| Python (all tracks) | inside WSL: `sudo apt install python3 python3-venv` | `brew install python@3.12` | `sudo apt install python3 python3-venv` |
| R track | Docker Desktop with the WSL 2 engine (or R + RStudio) | Docker Desktop or Colima (or R from CRAN + RStudio) | Docker Engine (or `r-base` + `pandoc`) |
| Docker (Phase 6+) | Docker Desktop with the WSL 2 engine | Docker Desktop (or Colima) | Docker Engine + compose plugin |

**Windows, important:** clone and work **inside the WSL file system** (`~/code/ds-case-study`), not under
`/mnt/c/...`. Hardware: 8 GB RAM is plenty; the export is small on purpose (a full run takes seconds).

## Quick start (5 minutes)
```bash
git clone https://github.com/<you>/ds-case-study.git && cd ds-case-study   # your fork (Phase 0)
scripts/doctor.sh                        # check your tools
cd tracks/python                         # or tracks/sql
make install                             # dependencies (creates .venv)
make lint test                           # all tests are "pending" (skipped) until Phase 3
python3 ../../scripts/generate_data.py --check   # the export in data/raw is exactly the published one
```
R track (Docker): build the pinned toolchain once, then run any target inside it:
```bash
docker build -f tracks/r/Dockerfile --target dev -t churncast-r-dev:local .
docker run --rm -v "$PWD":/repo -w /repo/tracks/r churncast-r-dev:local make lint test
```

Every track offers the same commands:

| Command | What it does |
|---|---|
| `make install` | install dependencies |
| `make lint` | linter + formatter check (ruff / ruff + sqlfluff / lintr) |
| `make test` | unit tests on the tiny hand-made fixture (seconds) |
| `make coverage` | unit + data and model tests on the real export, with an 85 % line-coverage gate |
| `make run` | write `out/features.csv`, `metrics.json`, `model.json`, `experiments.jsonl` (`DATA=../../data/raw/2026-05`) |
| `make report` | execute the notebook / SQL report / R Markdown report top to bottom |
| `make gate` | the evaluation gate of `out/metrics.json` (exit 1 if the model may not ship) |

Compare a track with the golden file (or with another track):
`python3 scripts/parity.py contract/golden/metrics-2026-05.json tracks/python/out/metrics.json`.

## How the phases work
| Phase | Topic | You end at tag |
|---|---|---|
| 0 | [Setup and the brief](docs/phase-0-setup.md) | `phase-0-end` |
| 1 | [Problem framing: the decision, the label and success criteria](docs/phase-1-requirements.md) | `phase-1-end` |
| 2 | [Design: data contract, timeline, modelling plan and ADRs](docs/phase-2-design.md) | `phase-2-end` |
| 3 | [Implementation in five milestones: clean, check, features, models, evaluation](docs/phase-3-implementation.md) | `phase-3-end` |
| 4 | [Testing data and models: golden files, invariants, leakage, parity](docs/phase-4-testing.md) | `phase-4-end` |
| 5 | [CI with GitHub Actions and the evaluation gate](docs/phase-5-ci.md) | `phase-5-end` |
| 6 | [Model card, prediction API, AI explainer, Docker and delivery](docs/phase-6-deploy.md) | `phase-6-end` = **`v1.0.0`** |
| 7 | [Monitoring, drift, retraining and a post-mortem](docs/phase-7-observability.md) | `phase-7-end` = **`v1.1.0`** |
| 8 | [Retrospective and portfolio](docs/phase-8-retrospective.md) | `phase-8-end` |

Each phase page has the same 8 blocks: *Why it matters · Objectives · Step-by-step instructions · AI-assist
prompts · Deliverables · Self-check quiz · What you learned · Catch-up git commands*.

### Branches and tags
- **`main`**: the **starter**. Every track has its structure, the full (pending) test suite and a `TODO` with a
  hint in every function or SQL view; the notebook and the R Markdown report are skeletons with the questions and
  no answers.
- **`solution`**: the reference, one or more commits per phase, an annotated tag at the end of every phase
  (`phase-0-end` … `phase-8-end`) and the releases `v1.0.0` and `v1.1.0`. Every tag passes the checks of all three
  tracks.

**Stuck or behind?** Start the next phase from the reference end of the previous one:
```bash
git fetch upstream --tags
git switch -c my-phase-4 phase-3-end
```
**Compare with the reference:** `git diff phase-3-end -- tracks/python`. Try first, then compare.

### Pending tests
The complete test suite is already on `main` but switched off in one list per track (`tests/conftest.py` for
Python and SQL, `tests/testthat/helper-churncast.R` for R). In Phase 3 you remove one entry at a time, watch the
tests fail, and make them pass. Skipped is never reported as passed.

## Working with AI
Use any assistant you like. Each phase has copy-paste prompts and a **"Verify the output by"** checklist; log what
you asked and how you checked it in [`AI_LOG.md`](AI_LOG.md). Three rules matter most in modelling work: never
paste row-level customer data or secrets into a prompt (aggregates and your own code are fine); never accept a
metric, a formula or a claim about a model without reproducing it (the golden files, the metric cases and the
other tracks are there to check it); and be most suspicious when a suggestion makes the model look *better*:
that is what leakage looks like.

## Coming from the old six-step guide?
The earlier version (Brief · Data · EDA · Modelling · Evaluation · Presentation) had the right story but no data,
no tests and no way to know if your numbers were right. This version ships the data, a contract with every rule
written down, golden files, three tracks that check each other, CI with an evaluation gate, a prediction API and a
second release after the model meets the real world. The mapping of the old steps is in
[`docs/README.md`](docs/README.md).

## More
- [docs/README.md](docs/README.md): index of all docs
- [docs/github-actions-explained.md](docs/github-actions-explained.md): every CI concept used here
- [contract/feature-spec.md](contract/feature-spec.md): every cleaning rule, feature, metric and gate check
- [CONTRIBUTING.md](CONTRIBUTING.md) · [CHANGELOG.md](CHANGELOG.md) · [LICENSE](LICENSE) (MIT)

Questions or problems: open an issue using the templates, or contact us via <https://www.aicancode.org/contact>.
