# GitHub Actions, explained for data scientists

This page explains every GitHub Actions concept used by ChurnCast's workflows, in the order you meet
them. It is shorter than a full course: each section is what you need to read our YAML and change it
safely. Keep the files open next to it:

| File | Appears in | Purpose |
|---|---|---|
| `.github/workflows/ci.yml` | starter (simple), Phase 5 (full), Phase 6 (+ Docker) | lint, unit, data and model tests, coverage, the evaluation gate, reports, parity, the API, image smoke test |
| `.github/workflows/reusable-track-ci.yml` | Phase 5 | the full check for **one** track, called three times |
| `.github/workflows/deploy.yml` | Phase 6 | push images to GHCR on version tags; optional Render deploy |
| `.github/dependabot.yml` | Phase 5-6 | weekly dependency update PRs |

Official reference: <https://docs.github.com/actions>. When this page and the docs disagree, the docs
win; please open an issue so we can fix this page.

---

## 1. Vocabulary in one minute
- **Workflow:** a YAML file in `.github/workflows/`. It runs when an **event** happens.
- **Job:** a set of steps on one fresh virtual machine (a **runner**, here `ubuntu-latest`). Jobs run in parallel unless one `needs:` another.
- **Step:** a shell command (`run:`) or a packaged **action** (`uses: actions/checkout@v4`).
- **Run:** one execution of a workflow, with a page, logs and a status (the green tick or red cross on a commit).
- **Check:** each job's result as shown on a pull request; branch protection can require some of them.

## 2. Triggers (`on:`)
```yaml
on:
  push:
    branches: [main, solution]   # every push to these branches
  pull_request:                  # every PR, whatever its branch
  workflow_dispatch:             # a "Run workflow" button on the Actions tab
```
`deploy.yml` uses `push: tags: ["v*.*.*"]`, so it runs only when you push a version tag. `ci.yml`
does not run for tags: a tag points to a commit CI has already checked on its branch. (Maintainers: pushing many
tags at once starts one deploy run per version tag, so the course repository pushes its tags with Actions off.)

## 3. Jobs, steps and the keywords around them
- `runs-on: ubuntu-latest`: the machine. It starts empty apart from common tools (Python, Docker, git, shellcheck).
- `needs: [python, sql, r]`: wait for those jobs; their outputs and results become available.
- `if:`: run the job or step only when a condition holds (`if: failure()` runs only after a failed step).
- `timeout-minutes:`: kill a stuck job. The default is 6 hours, which is a lot of free minutes.
- `defaults.run.working-directory: tracks/python`: every `run:` starts there.
- `concurrency:` with `cancel-in-progress: true`: a new push to a branch cancels the old run of that branch.

## 4. Expressions and contexts: `${{ … }}`
GitHub replaces `${{ … }}` before the step runs. The contexts we use: `github` (event, ref, actor),
`inputs` (of a reusable workflow), `needs` (results and outputs of earlier jobs), `steps` (outputs of
earlier steps), `matrix`, `secrets`, `vars` and `env`. Two examples from our files:
```yaml
if: needs.changes.outputs.sql == 'true' || needs.changes.outputs.shared == 'true'
working-directory: tracks/${{ inputs.track }}
```
Prefer environment variables over pasting `${{ }}` into a shell script: `env: { RESULTS: ${{ join(needs.*.result, ' ') }} }`
then `$RESULTS` in the script. It avoids quoting bugs and script injection.

## 5. Matrix builds
The starter's `ci.yml` runs one job per track with a matrix:
```yaml
strategy:
  fail-fast: false            # one red track does not cancel the others
  matrix:
    track: [python, sql, r]
name: ${{ matrix.track }} · lint + unit
```
Three jobs, three checks: `python · lint + unit`, `sql · lint + unit`, `r · lint + unit`. These are
the names branch protection requires on `main`. `deploy.yml` uses a matrix with `include:` to give
each image its own Dockerfile.

## 6. Caching (three different kinds)
1. **Package caches:** `actions/setup-python@v5` with `cache: pip` restores pip's download cache, keyed by the
   hash of `requirements-dev.txt`. A changed file means a new key and a fresh install. The expression
   `cache: ${{ inputs.track != 'r' && 'pip' || '' }}` switches it off for the R track, which has no such file.
2. **Binary packages:** the R image installs CRAN packages as pre-built Linux binaries from a *dated* Posit
   Package Manager snapshot (`p3m.dev/cran/__linux__/noble/2026-09-15`): minutes instead of compiling tidymodels,
   and the same versions on every machine, every day.
3. **Docker layer cache:** `cache-from/cache-to: type=gha` stores image layers in the Actions cache, one scope per
   image (`r-dev` for the R toolchain, one per image in `deploy.yml`). The Dockerfiles copy the code last so the
   dependency layers stay cached; a warm R image builds in well under a minute.

## 7. Reusable workflows
Definition (`reusable-track-ci.yml`):
```yaml
on:
  workflow_call:
    inputs:
      track: { description: "python | sql | r", required: true, type: string }
```
Call site (`ci.yml`):
```yaml
r:
  needs: changes
  if: needs.changes.outputs.r == 'true' || needs.changes.outputs.shared == 'true'
  uses: ./.github/workflows/reusable-track-ci.yml     # a whole workflow instead of runs-on/steps
  with:
    track: r
```
Step by step: (1) the caller job has **no** `runs-on` or `steps`, only `uses` + `with`; (2) GitHub runs
the reusable workflow's job as a child of the caller (shown as `r / lint · unit · data · coverage · run · gate ·
report`); (3) inside it, `inputs.track` is `r`, and steps with `if: inputs.track == 'r'` build the R
image instead of installing a virtualenv. It works because every track exposes the same Makefile targets
(`install`, `lint`, `test`, `coverage`, `run`, `report`, `gate`). Secrets are not passed automatically (`secrets: inherit` would);
our CI needs none.

Why bother? The check is written once. Fix it once and all three tracks get the fix.

## 8. Toolchains: Python, and R in a Docker image
No database server is needed: DuckDB runs inside the Python process, and the exports are CSV files in the
repository. The reusable workflow sets up what the track needs:
- `actions/setup-python@v5` for every track (the SQL track's runner is a thin Python program; the R job uses it
  only for the shared scripts: schema validation and the gate);
- for R, `docker/setup-buildx-action@v3` + `docker/build-push-action@v6` with `target: dev` and `load: true` build
  `tracks/r/Dockerfile` (R 4.6.1, tidymodels, lintr, testthat, covr, rmarkdown, pandoc), then every `make` target
  runs inside it:
  ```yaml
  run: $IN make coverage   # IN = "docker run --rm --network none -u <uid>:<gid> -v <repo>:/repo -w /repo/tracks/r churncast-r-dev:ci"
  ```
Why a container instead of installing R on the runner? A model is only reproducible if its toolchain is: a newer
lintr flags new style rules, a newer parsnip or glm can move the 7th digit of a coefficient. With the image, your
laptop and CI run byte-for-byte the same R. `--network none` proves the tests need no internet.

## 9. Permissions and `GITHUB_TOKEN`
Every run gets an automatic, short-lived token, `secrets.GITHUB_TOKEN`, valid only for this repository
and only while the job runs. Its powers are set by `permissions:`:
```yaml
permissions:
  contents: read          # top of every workflow: least privilege by default
jobs:
  image:
    permissions:
      contents: read
      packages: write     # only this job may push to GHCR
```
Anything not listed is `none`. `changes` also asks for `pull-requests: read` because the path filter
lists a PR's changed files through the API.

## 10. Secrets and variables: where to click
**Secrets** (encrypted, masked as `***` in logs) vs **variables** (plain configuration, visible):

| Name | Kind | Scope | Used by |
|---|---|---|---|
| `GITHUB_TOKEN` | secret | automatic | GHCR login |
| `RENDER_DEPLOY_HOOK_URL` | secret | environment `production` | `deploy.yml` → `render` |
| `RENDER_APP_URL` | variable | environment `production` | health poll + smoke test |

Add one: repository → **Settings** → **Environments** → **New environment** `production` → **Add
environment secret**. Or with the GitHub CLI: `gh secret set RENDER_DEPLOY_HOOK_URL --env production`
(it prompts for the value, so it never lands in your shell history).

**Secrets cannot be used in `if:` conditions.** `deploy.yml` copies the secret into `env:` (an empty
string when it is not set) and tests `env.RENDER_DEPLOY_HOOK_URL == ''`: no secret means a notice on
the run summary and a green job. The AI explainer's key is never needed in CI: its tests use a fake
LLM server, and the Docker job points it at an unreachable address to prove the fallback.

## 11. Environments
```yaml
render:
  environment:
    name: production
    url: ${{ vars.RENDER_APP_URL || 'https://render.com' }}
```
An environment is a named deployment target with its own secrets and **protection rules**: required
reviewers (the job waits for an approval), allowed branches or tags (e.g. only `v*`), a wait timer.
Its secrets are given only to jobs that declare it, which makes them safer than repository secrets.

## 12. GitHub Container Registry (GHCR)
1. **Name:** `ghcr.io/<owner>/<image>`, **lower-case**. Our org is `AICanCode-org`, hence
   `ghcr.io/${GITHUB_REPOSITORY_OWNER,,}/churncast-<name>` (bash `,,` = to lower case).
2. **Login:** `docker/login-action@v3` with `registry: ghcr.io`, `username: ${{ github.actor }}`,
   `password: ${{ secrets.GITHUB_TOKEN }}`; the job needs `packages: write` (§9).
3. **Tags:** `docker/metadata-action@v5` turns git tag `v1.1.0` into image tags `1.1.0`, `1.1`,
   `sha-1a2b3c4` and `latest`, and adds OCI labels that link the package to the repository.
4. **Push:** `docker/build-push-action@v6` with `push: true`.
5. **Visibility:** a new package is **private**. To let Render or anyone pull it: the package page →
   **Package settings** → **Change visibility** → Public.
6. **Pull:** `docker pull ghcr.io/aicancode-org/churncast-api:1.1.0`.

## 13. Path filters and the aggregator job
GitHub's built-in `on: push: paths:` skips the **whole workflow**, and a required check that never runs
blocks a PR forever. So the workflow always runs and decides per job:
1. `changes` runs `dorny/paths-filter@v3` and outputs `'true'`/`'false'` per area (`shared`, `docs`,
   `python`, `sql`, `r`, `serving`). A change to `contract/`, `data/`, `scripts/` or `models/` is `shared`: it
   re-runs every track, because the numbers of all three depend on it.
2. Each job has an `if:` on those outputs.
3. `ci-ok` has `if: always()`, `needs:` on everything, and fails only if a result is `failure` or
   `cancelled`; skipped jobs are fine. In your own fork, `ci-ok` is the one check to require.

## 14. Artefacts
```yaml
- uses: actions/upload-artifact@v4
  with:
    name: run-${{ inputs.track }}
    path: |
      tracks/${{ inputs.track }}/out/metrics.json
      tracks/${{ inputs.track }}/out/model.json
      tracks/${{ inputs.track }}/out/features.csv
    if-no-files-found: error
    retention-days: 7
```
Files saved from a job, downloadable from the run page for 7 days. Each track uploads its run outputs
(`run-python`, `run-sql`, `run-r`); the `parity` job downloads them all with `actions/download-artifact@v4` and
`pattern: run-*`, reads the export name from one `metrics.json`, compares every `metrics.json` and `model.json`
with `contract/golden/metrics-<export>.json` and `model-<export>.json` (1e-6), and the `features.csv` files with
each other (1e-9). Jobs never share files any other way:
each runs on a fresh machine. The `report-<track>` artefact holds the executed notebook, the SQL
report or the knitted R Markdown HTML, uploaded with `if: always()` so you get it even when a test failed.

## 15. Pinning, Dependabot and actionlint
- `uses: actions/checkout@v4` follows the `v4` tag, which the publisher can move. For maximum
  supply-chain safety, pin a full commit SHA (`@<40-char-sha> # v4.2.2`). We use major tags for
  readability, and Dependabot (`package-ecosystem: github-actions`, plus `pip` and `docker`) proposes updates.
- `actionlint` (<https://github.com/rhysd/actionlint>) checks workflows, expressions and embedded shell
  (via shellcheck). Run it before pushing; our workflows pass it with no findings.

## 16. Debugging a red run
1. Open the failed step and read the **last** error, then scroll up to the first one.
2. Reproduce locally with the same command: `cd tracks/<track> && make coverage` (or `make report`, `make gate`),
   or everything at once with `scripts/check-all.sh --full`.
3. Parity red? Download the `run-*` artefacts and run `python3 scripts/parity.py` on them: it prints every
   differing JSON path (or CSV cell) for each file.
4. Gate red? The step prints one line per check: which number is not good enough. Do **not** lower the threshold
   in the contract to make it green; that is a decision for the people who agreed it in Phase 1.
5. Green locally, red in CI? Compare versions (`python --version`; for R, did you rebuild the image after the
   Dockerfile changed?), and remember CI
   starts from a clean checkout: an untracked file or a cached notebook output on your laptop does not exist there.
6. Still unclear? **Re-run jobs → Enable debug logging**, or add a step `run: env | sort` (secrets stay masked).

## 17. Annotated walk-through of a tag push (`git push origin v1.1.0`)
1. Event `push` with `github.ref = refs/tags/v1.1.0` → `deploy.yml` matches `v*.*.*`.
2. Job `image` expands into 4 matrix jobs (api, python, sql, r; the R image uses `target: runtime`). Each: checkout → lower-case name →
   buildx → GHCR login with `GITHUB_TOKEN` → metadata (`1.1.0`, `1.1`, `sha-…`, `latest`) → build with
   the GHA cache → push.
3. Job `render` waits for all four (`needs: image`), enters environment `production`, reads the secret into `env`.
   - No secret → notice, success. Done.
   - Secret → `curl` the deploy hook with `imgURL=ghcr.io/aicancode-org/churncast-api:1.1.0` →
     poll `$RENDER_APP_URL/health` every 15 s for up to 10 min (cold starts) → run
     `scripts/smoke-test.sh` against the live URL.
