---
phase: 0
slug: phase-0-setup
title: Setup and the brief
duration: 1.5 h
start_ref: main
end_tag: phase-0-end
---
# Phase 0 · Setup and the brief

## 1. Why it matters
A model nobody else can retrain is a rumour with a ROC curve. Professional data science teams start where
engineers start: a repository that installs with one command, data whose origin you can prove, tests that say what
"right" means, and a log of how AI helped. In this phase you set up the tools for **one** track, read the brief and
the data, run the starter, meet the pending tests and the contract that will guide you, open your first pull
request and start your `AI_LOG.md`. You will not train a single model yet, on purpose: first you learn which
decision the model serves and what the data can and cannot say.

## 2. Objectives
By the end of this phase you can:
- Fork the repository **with all branches and tags**, clone it and add the `upstream` remote.
- Pick a track (Python, SQL or R), install its toolchain on Windows (WSL2), macOS or Linux, and run `make lint test`.
- Explain the brief in two sentences: who decides what each month, with which capacity, and what a wrong call costs.
- Prove the export in `data/raw/2026-05` is exactly the published one (`generate_data.py --check`) and list three defects you can see in the raw CSVs, plus the one column that must never become a feature.
- Open a pull request that passes CI and write your first `AI_LOG.md` entry.

## 3. Step-by-step instructions

### Step 0.1 · Fork and clone (keep the tags!)
1. On GitHub open `AICanCode-org/ds-case-study` → **Fork**. **Untick "Copy the `main` branch only"**. The
   `solution` branch and the `phase-N-end` tags are your safety net in later phases.
2. Clone **your** fork and connect the original as `upstream`:
   ```bash
   git clone https://github.com/<you>/ds-case-study.git
   cd ds-case-study
   git remote add upstream https://github.com/AICanCode-org/ds-case-study.git
   git fetch upstream --tags
   git tag -l 'phase-*'      # phase-0-end … phase-8-end
   ```
3. **Windows:** do all of this inside **WSL2** (Ubuntu) and keep the repo in the Linux file system
   (`~/code/ds-case-study`), not under `/mnt/c`.

### Step 0.2 · Install the tools for ONE track
Every track needs Git, `make` and Python 3.12+ (the data generator, the parity script, the gate and, later, the API
are Python). Run the doctor script; it tells you exactly what is missing:
```bash
scripts/doctor.sh
```

<!-- track:python -->
**Python track:** pandas, scikit-learn and Jupyter, installed into a virtual environment with exact versions.
```bash
cd tracks/python && make install     # creates .venv with the pinned versions
.venv/bin/python -c "import pandas, sklearn; print(pandas.__version__, sklearn.__version__)"
```
Open the notebook with `.venv/bin/jupyter lab notebooks/churn-model.ipynb` (or VS Code with the Jupyter
extension, selecting `.venv` as the kernel).
<!-- /track -->

<!-- track:sql -->
**SQL track:** DuckDB, an in-process analytical database: no server, it reads the CSVs directly. Cleaning,
features, labels and every metric are written in `sql/*.sql`; a thin Python runner sets variables, does the one
thing SQL cannot (fitting the logistic regression, with scikit-learn) and writes the JSON files.
```bash
cd tracks/sql && make install        # .venv with duckdb, scikit-learn, sqlfluff, pytest
.venv/bin/python -c "import duckdb; print(duckdb.sql(\"SELECT count(*) FROM '../../data/raw/2026-05/invoices.csv'\"))"
```
Optional: the DuckDB CLI (`brew install duckdb`, or the binary from duckdb.org) to explore by hand.
<!-- /track -->

<!-- track:r -->
**R track:** R 4.6 with tidymodels (parsnip, rsample, yardstick), dplyr, testthat, lintr and R Markdown. The
toolchain is a **Docker image** pinned to a dated CRAN snapshot, so you, your reviewer and CI run exactly the same
package versions. Build it once (about 5 minutes), then run every `make` target inside it:
```bash
docker build -f tracks/r/Dockerfile --target dev -t churncast-r-dev:local .
docker run --rm -v "$PWD":/repo -w /repo/tracks/r churncast-r-dev:local Rscript -e 'packageVersion("parsnip")'
alias rdev='docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/repo -w /repo/tracks/r churncast-r-dev:local'
```
(Run the alias from the repository root.) RStudio users can still edit in RStudio; a local R 4.6 works with
`cd tracks/r && make install`, but CI uses the image, so check there before you push.
<!-- /track -->

### Step 0.3 · Read the brief and the data
1. Read the top of `README.md` (the situation) and `contract/feature-spec.md` §1 (the problem and the timeline).
   Write down, in your own words: **who decides, what, how often, with which capacity, and what each kind of
   wrong call costs.**
2. Read `data/README.md`, then look at the raw files themselves. They are small on purpose:
   ```bash
   head -5 data/raw/2026-05/customers.csv
   grep -c '/' data/raw/2026-05/customers.csv           # rows with the day-first date format
   cut -d, -f3 data/raw/2026-05/customers.csv | sort | uniq -c | sort -rn | head -12   # city spellings
   grep -c '₹' data/raw/2026-05/invoices.csv            # amounts written as text with a rupee sign
   python3 scripts/generate_data.py --check             # byte-identical to the seeded generator
   ```
3. Note three defects you can see without any code (duplicate rows? two date formats? negative counts?). Phase 2
   turns each of them into a rule.
4. Look at `cancellation_reason` in `customers.csv`. When is it filled in? Why would a model that uses it look
   brilliant in testing and be useless in production? Write one sentence; Phase 3 M3 comes back to it.

### Step 0.4 · Run the checks and meet the pending tests and the contract
<!-- track:python -->
```bash
cd tracks/python && make lint test
```
<!-- /track -->
<!-- track:sql -->
```bash
cd tracks/sql && make lint test
```
<!-- /track -->
<!-- track:r -->
```bash
rdev make lint test
```
<!-- /track -->
All the tests are **skipped**. They are *pending*: the complete test suite is already written and switched off in
one list per track:

| Track | Pending list |
|---|---|
| Python | `tracks/python/tests/conftest.py` (`PENDING`) |
| SQL | `tracks/sql/tests/conftest.py` (`PENDING`) |
| R | `tracks/r/tests/testthat/helper-churncast.R` (`PENDING`) |

Each entry names a milestone ("Phase 3 M3 - point-in-time features and labels"). In Phase 3 you delete one entry at
a time, watch the tests go red, and make them green.

Now open the files of `contract/` that make "right" precise:
- `feature-spec.md`: every cleaning rule in order, every feature, every metric and the release gate, in words;
- `data-contract.yaml`: the columns each CSV must have, the checks (an `error` stops the run), the features, the
  experiments, the gate thresholds;
- `metrics.schema.json` and `model.schema.json`: the shape of the two JSON files every track writes;
- `fixtures/tiny/` + `tiny-expected.json`: an export small enough to check by hand; `fixtures/metric-cases.json`:
  AUC, average precision, Brier and calibration on tiny inputs, worked out by hand;
- `golden/metrics-2026-05.json`, `golden/model-2026-05.json`: the reference results for the real export.

### Step 0.5 · Your first pull request
1. Create a branch: `git switch -c chore/phase-0-setup`.
2. Fill in the first entry in `AI_LOG.md`, e.g. how an assistant explained a `pip` / `duckdb` / Docker error
   during the install and how you checked its advice.
3. Commit and push, then open a PR **in your fork** against your `main`:
   ```bash
   git add AI_LOG.md
   git commit -m "docs: start AI_LOG for phase 0"
   git push -u origin chore/phase-0-setup
   ```
4. Open the **Actions** tab. Forks have Actions switched off until you click **"I understand my workflows, go
   ahead and enable them"**. CI runs lint + unit tests for all three tracks (the R job builds the same image you
   built). Wait for green, fill in the PR template and merge.

## 4. AI-assist prompts

### Prompt 1: Fix my toolchain install
```text
I'm on <Windows 11 + WSL2 Ubuntu 24.04 | macOS 15 | Ubuntu 24.04>. I want to run a <Python 3.12 with pandas,
scikit-learn and Jupyter | DuckDB 1.x from Python | R 4.6 in Docker (rocker/r-ver) with tidymodels> project.
Here is the output of scripts/doctor.sh: <paste output>. Give me the exact commands to install what is missing,
explain each one in one line, and tell me how to verify each install.
```
**Verify the output by:** running each verification command, re-running `scripts/doctor.sh` until every line for
your track is green, and checking any download URL against the official site (python.org, duckdb.org,
docs.docker.com, cloud.r-project.org). Never pipe an unknown URL into `bash`.

### Prompt 2: Restate the brief as a decision
```text
Here is a stakeholder brief: <paste the "situation" paragraph of README.md and feature-spec.md §1>.
Restate it as: (1) the decision to be made, by whom, how often, (2) the capacity constraint, (3) the cost of each
kind of wrong call, (4) what a model must output for that decision (a ranking? a probability? a reason?),
(5) three ways a model could look good in a notebook and still fail this team. Do not compute anything and do not
guess numbers that are not in the brief.
```
**Verify the output by:** checking every claim against the brief (assistants add details that are not there, such
as a churn rate per city or a budget), and keeping at least one failure mode about *time* (a model trained on the
future, or a test set from the same months as the training data). You will design against it in Phase 2.

### Prompt 3: Read a raw file like a data scientist
```text
Here are the header and 15 sample rows of a raw CSV export of a subscription business: <paste head -16
data/raw/2026-05/invoices.csv>. List every data-quality problem you can see or suspect, how you would detect each
one in code, which column could leak the outcome into a churn model, and what you would ask the data owner.
Do not clean anything yet.
```
**Verify the output by:** finding each problem in the real file with `grep` or a quick count (an assistant may
"see" problems that are not in your sample), and comparing your list with `contract/feature-spec.md` §2. These
rows are synthetic; with real customer data you would paste column names and aggregates only, never rows.

## 5. Deliverables
- [ ] Your fork contains the `solution` branch and the `phase-*` tags (`git tag -l` shows them).
- [ ] `make lint test` passes locally in your track (all tests skipped).
- [ ] `python3 scripts/generate_data.py --check` says the export is identical.
- [ ] A note (in your PR description or `AI_LOG.md`): the decision, the capacity, three raw-data defects, and why `cancellation_reason` is dangerous.
- [ ] A merged PR with a green CI run.
- [ ] `AI_LOG.md` has its first entry.

## 6. Self-check quiz

### Q1. Why must you untick "Copy the main branch only" when forking?
- [ ] Otherwise GitHub Actions is disabled in the fork
- [x] Otherwise the `solution` branch and phase tags are missing from your fork
- [ ] Otherwise you cannot open pull requests
- [ ] Otherwise the CSV files are not copied
> **Answer:** Forks copy only `main` by default. The tags (`phase-N-end`) live on the `solution` branch; without them you cannot compare your work or catch up. Fix it later with `git fetch upstream --tags`.

### Q2. The retention team can call 10 % of active customers a month. What does that mean for the model?
- [ ] Only accuracy matters
- [ ] The model must predict churn for exactly 10 % of customers
- [x] What matters most is how well it ranks the top 10 % of each month, plus honest probabilities for budgeting
- [ ] The model is only useful if its AUC is above 0.9
> **Answer:** A capacity-limited decision is a ranking problem: precision and recall of the call list matter more than accuracy at a 0.5 threshold. Finance also multiplies the probabilities by prices, so calibration matters too.

### Q3. Why is `customers.cancellation_reason` never a feature?
- [ ] It has too many missing values
- [ ] It is text, and models need numbers
- [x] It is filled in after a customer cancels, so it encodes the outcome; at prediction time it is empty for everyone who has not left yet
- [ ] It is a protected attribute
> **Answer:** This is target leakage. A model using it would score superbly on historical data and be useless on the next month. The leakage scan in Phase 3 measures exactly how "good" it would look.

### Q4. Why are all tests skipped in the starter?
- [ ] They are flaky
- [ ] CI is too slow to run them
- [x] They describe behaviour you build in Phases 3-4 and are switched on one milestone at a time
- [ ] They only run on the solution branch
> **Answer:** The full suite is written up-front (test-first). Deleting a line from the pending list turns a group back on, so you always have a clear red → green target.

### Q5. What is `contract/fixtures/metric-cases.json` for?
- [ ] Training data for the model
- [x] Tiny inputs with AUC, average precision, Brier and calibration worked out by hand, so a metric written from scratch can be checked exactly
- [ ] A cache of scikit-learn's results
- [ ] The golden metrics of the real export
> **Answer:** Metrics are where silent bugs hide (ties in AUC, the last calibration bin). The cases pin every edge case; all three tracks must reproduce them.

### Q6. Which of these may you paste into an AI prompt for this project?
- [ ] Your `.env` file with an LLM API key
- [ ] 500 rows of a real customer invoices export
- [x] Column names, your own code, an error message and aggregate numbers
- [ ] Another student's notebook
> **Answer:** Secrets and row-level personal data never go into prompts. The ChurnCast data is synthetic, but practise the habit you will need at work: aggregates and code, not rows.

## 7. What you learned
- A reproducible local environment for one track, checked by `scripts/doctor.sh` (for R: a pinned Docker image).
- The difference between `origin` (your fork) and `upstream` (the course repo), and why tags matter.
- The brief as a decision under a capacity constraint, and why that makes ranking and calibration the metrics that matter.
- The contract (`feature-spec.md`, `data-contract.yaml`, the schemas, fixtures and golden files) that defines "right".
- The PR + CI loop and the habit of logging AI assistance without leaking secrets or rows.

## 8. Catch-up git commands
```bash
git fetch upstream --tags
# Start Phase 1 from the reference end of Phase 0:
git switch -c my-phase-1 phase-0-end
# See what the reference changed in this phase:
git diff main phase-0-end --stat
```
