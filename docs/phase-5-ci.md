---
phase: 5
slug: phase-5-ci
title: CI with GitHub Actions and the evaluation gate
duration: 3 h
start_tag: phase-4-end
end_tag: phase-5-end
---
# Phase 5 · CI with GitHub Actions and the evaluation gate

## 1. Why it matters
A model release is a code release with an extra failure mode: the code can be fine and the model worse. CI turns
your tests, the release criteria and the cross-track parity into a check on every pull request, run on a clean
machine that has never seen your laptop's cached files. In this phase you replace the starter's lint-and-unit CI
with the full pipeline: path filters so only affected tracks run, a reusable workflow per track, data and model
tests with a coverage gate, the run, schema validation, the **evaluation gate**, the report executed top to bottom,
parity with the golden files, and a single required check. The R track runs inside its pinned image, so "works on
my machine" and "works in CI" mean the same thing.

## 2. Objectives
By the end of this phase you can:
- Read and modify `.github/workflows/ci.yml` and `reusable-track-ci.yml` (triggers, jobs, `needs`, `if`, matrix, reusable workflows).
- Run a track's full check in CI: lint → unit → coverage gate → run → schema validation → evaluation gate → report.
- Build and cache a Docker toolchain image in CI and run `make` inside it.
- Compare every track's outputs with the golden files in a `parity` job using artifacts.
- Protect `main` with the `ci-ok` aggregator check, and explain why a failing gate must block a merge.

## 3. Step-by-step instructions

### Step 5.1 · Read the full pipeline
Copy the reference workflows (or write your own and compare):
```bash
git checkout phase-5-end -- .github/workflows/ci.yml .github/workflows/reusable-track-ci.yml .github/dependabot.yml
```
Read them with `docs/github-actions-explained.md` open: §2 triggers, §5 matrix, §6 caching, §7 reusable
workflows, §8 toolchains, §13 path filters, §14 artifacts. Draw the job graph:
`changes → contract | python | sql | r → parity → ci-ok`.

### Step 5.2 · One track, end to end
The reusable workflow runs, for one track, exactly the commands you run locally:
```text
make install · make lint · make test · make coverage · make run · validate_outputs.py · eval_gate.py · make report
```
then uploads `run-<track>` (metrics, model, features) and `report-<track>` (the executed report and coverage).

<!-- track:python -->
Python: `actions/setup-python@v5` with the pip cache keyed by `requirements-dev.txt`, then `make install`.
The executed notebook is in the `report-python` artifact: download it and check every cell ran.
<!-- /track -->
<!-- track:sql -->
SQL: same setup as Python; `make lint` runs ruff **and** sqlfluff (DuckDB dialect) on `sql/*.sql` and the check
templates. `report-sql` holds `out/report.md`.
<!-- /track -->
<!-- track:r -->
R: `docker/build-push-action` builds `tracks/r/Dockerfile` with `target: dev` and the GHA layer cache (a few
minutes the first time, seconds afterwards); every target then runs as
`docker run --rm --network none -u <uid>:<gid> -v <repo>:/repo -w /repo/tracks/r churncast-r-dev:ci make <target>`.
`report-r` holds the knitted `churn-model.html`.
<!-- /track -->

### Step 5.3 · The evaluation gate in CI
`scripts/eval_gate.py out/metrics.json` prints one line per gate check and exits 1 if any fails. Try it: on a
branch, set `min_test_auc: 0.80` in the contract, push, and watch the gate step go red with the line
`FAIL  test_auc  value 0.7430  threshold 0.8000`. Then revert. Discuss in the PR: who is allowed to change a threshold, and when?
(Answer from Phase 1: the people who agreed the success criteria, with a reason, in a contract change.)

### Step 5.4 · Parity, the contract job and the aggregator
- `parity` downloads every `run-*` artifact, reads the export month from a `metrics.json` and runs `parity.py`
  against `contract/golden/metrics-<export>.json` and `model-<export>.json`, then compares the `features.csv`
  files with each other. It runs if at least one track succeeded.
- `contract` (when shared files or docs change): `generate_data.py --check`, the golden files validate against
  their schemas and pass the gate, ruff and shellcheck on `scripts/`, and `build-cms.py --check`.
- `ci-ok` needs every job, runs `if: always()`, and fails only on `failure` or `cancelled`: skipped jobs (a
  docs-only PR) are fine.

### Step 5.5 · Branch protection
In your fork: **Settings → Branches → Add rule** for `main`: require a pull request, require status checks to pass,
and select **`ci-ok`**. (The course repository also requires the starter checks `python · lint + unit`,
`sql · lint + unit` and `r · lint + unit` on `main`.) Open a PR that breaks one unit test and check that the merge
button is blocked.

## 4. AI-assist prompts

### Prompt 1: Explain a workflow line by line
```text
Explain this GitHub Actions workflow to a data scientist who has never used CI, line by line, and draw the job
graph as text: <paste .github/workflows/ci.yml>. Then list three ways it could pass while the model is actually
worse than before, and how I would close each gap.
```
**Verify the output by:** checking every keyword against <https://docs.github.com/actions> (assistants invent
keys or mix GitLab syntax), and running `actionlint` on any change it proposes.

### Prompt 2: Speed up my CI without weakening it
```text
My CI run takes <N> minutes. Here are the job timings: <paste>. Suggest changes that make it faster without
skipping any check on a pull request that could change a number in metrics.json. For each, estimate the saving
and the risk.
```
**Verify the output by:** rejecting any change that skips data tests, the gate or parity on code changes; measuring
the real timing after the change; and confirming that a docs-only PR still gets a green `ci-ok`.

### Prompt 3: Debug a red job
```text
This CI step failed: <paste the last 60 lines of the log>. It passes on my laptop with: <command and output>. The
step runs <in ubuntu-latest | in the R Docker image>. What are the three most likely causes of a CI-only failure,
and what command would confirm each?
```
**Verify the output by:** reproducing the failure locally from a clean clone (`git clone` into a new folder, or
`scripts/check-all.sh --full`), and fixing the cause, not the symptom (never add `continue-on-error` to a test).

## 5. Deliverables
- [ ] The full CI (`ci.yml`, `reusable-track-ci.yml`, `dependabot.yml`) green on a PR in your fork.
- [ ] A PR (closed, not merged) that shows the gate blocking a change of threshold or a planted bug.
- [ ] Branch protection on `main` requiring `ci-ok`.
- [ ] An `AI_LOG.md` entry.

## 6. Self-check quiz

### Q1. Why does the path filter live inside the workflow (a `changes` job) instead of `on: push: paths:`?
- [ ] `paths:` is deprecated
- [x] A workflow skipped by `paths:` never reports its checks, so a required check would block the PR forever; jobs that are skipped by `if:` still let the aggregator report
- [ ] `paths:` does not work with pull requests
- [ ] It is faster
> **Answer:** The aggregator pattern (`ci-ok` with `if: always()`) gives one stable required check whatever was skipped.

### Q2. Why does a change in `contract/` or `data/` re-run every track?
- [ ] To use more CI minutes
- [x] Every track's numbers depend on the contract and the data, so all three must prove they still match
- [ ] Because the R image must be rebuilt
- [ ] GitHub requires it
> **Answer:** `shared` paths fan out to every track. A contract change without all three tracks updated is caught here.

### Q3. Why run the R track inside a Docker image instead of installing R on the runner?
- [ ] R cannot be installed on Ubuntu
- [x] The image pins R, tidymodels and lintr to the versions you use locally, so a package update cannot move a coefficient or a lint rule between your laptop and CI
- [ ] Docker is faster than installing R
- [ ] GitHub forbids R on runners
> **Answer:** Reproducibility of the toolchain is part of the reproducibility of the model. The image is built from a dated CRAN snapshot and cached between runs.

### Q4. The evaluation gate fails in CI because test AUC dropped from 0.743 to 0.712 after your change. What do you do?
- [ ] Lower `min_test_auc` to 0.70 in the same PR
- [ ] Add `continue-on-error: true` to the gate step
- [x] Find out why the model got worse (a rule changed? a feature lost?), and only change a threshold through a reviewed contract change with a reason
- [ ] Re-run the job until it passes
> **Answer:** The gate encodes the success criteria agreed in Phase 1. It is there precisely to stop a worse model from shipping.

### Q5. How do jobs share the tracks' outputs with the `parity` job?
- [ ] Through the runner's disk
- [ ] Through environment variables
- [x] Each track uploads an artifact (`run-<track>`), and `parity` downloads them with `actions/download-artifact`
- [ ] Through a database service
> **Answer:** Every job runs on a fresh machine; artifacts are the way to pass files between jobs (and to download them after the run).

### Q6. What does `cancel-in-progress: true` in `concurrency` do?
- [ ] Cancels failed jobs
- [x] A new push to the same branch cancels the older run of that branch, saving minutes on outdated commits
- [ ] Prevents two branches from running at the same time
- [ ] Cancels the deploy workflow
> **Answer:** The group is per workflow and ref; only the latest commit of a branch matters.

## 7. What you learned
- A CI pipeline for a modelling project: tests, the run, schema validation, the evaluation gate, executed reports, parity.
- Reusable workflows, path filters with an aggregator check, artifacts, caching, and a Docker toolchain in CI.
- Branch protection with one required check, and why the gate must be able to block a merge.

## 8. Catch-up git commands
```bash
git fetch upstream --tags
git switch -c my-phase-6 phase-5-end
git diff phase-4-end phase-5-end -- .github/
```
