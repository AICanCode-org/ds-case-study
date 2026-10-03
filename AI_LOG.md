# AI_LOG: how I used AI on this project

Employers and reviewers increasingly ask *how* you used AI, not *whether*. This log is your evidence that you
stayed in control. Add one entry every time an AI assistant (ChatGPT, Gemini, Copilot, Cursor, Claude, a local
Ollama model, ...) produced something you kept, changed or rejected.

**Rules**
1. Never paste secrets, `.env` contents, LLM API keys or **row-level data** (customer ids, cities, invoices of
   real people) into a prompt. Column names, aggregates, your own code and the synthetic tiny fixture are fine.
2. Every AI output is a *draft*. Record how you **verified** it: a test, the golden files,
   `contract/fixtures/metric-cases.json`, `scripts/parity.py` against another track, the library's docs, a second
   source.
3. Be honest about rejections: they are the most valuable entries. Modelling advice gets the strictest review: a
   feature that "improves AUC" may be a leak, a "standard" split may mix the future into training, and an
   assistant that "simplifies" a cleaning rule has just changed every number downstream.

## Entry template (copy for each entry)

### YYYY-MM-DD · Phase N · <short title>
* **Tool / model:** e.g. Gemini 2.5 Flash (free tier), Copilot in VS Code, Ollama llama3.2
* **Prompt (summary or paste):**
  > ...
* **What it produced:** one or two lines, or a link to the commit
* **What I kept / changed / rejected, and why:**
* **How I verified it:** e.g. `make coverage` (110 passed), parity with the golden files MATCH, scikit-learn docs
* **Time saved / lost (honest guess):**
* **What I learned:**

---

## My entries

<!-- Start below this line. Phase 0 asks you to write your first entry. -->

### 2026-06-02 · Phase 0 · Building the R toolchain image on WSL
* **Tool / model:** Gemini 2.5 Flash (free tier)
* **Prompt (summary or paste):**
  > Prompt 1 of Phase 0 with the output of `scripts/doctor.sh` (Docker found, R image missing).
* **What it produced:** `sudo apt install r-base` and `install.packages("tidymodels")`, plus the `docker build` line.
* **What I kept / changed / rejected, and why:** kept the `docker build -f tracks/r/Dockerfile --target dev` line;
  rejected the local R install: the Ubuntu R would be a different version from CI's, and the whole tidymodels
  meta-package is far more than `DESCRIPTION` needs.
* **How I verified it:** `scripts/doctor.sh` shows the image; `make lint test` inside it (all skipped); CI's R job green.
* **Time saved / lost (honest guess):** saved ~20 minutes.
* **What I learned:** the project's pinned toolchain is the source of truth, not a generic install answer.

### 2026-06-03 · Phase 1 · Challenging the label definition
* **Tool / model:** ChatGPT (free tier)
* **Prompt (summary or paste):**
  > Prompt 1 of Phase 1: list every way "no paid charge for M+1" could be a wrong churn label.
* **What it produced:** eight cases: pauses, failed-then-retried payments, refunds, win-backs, annual plans, the
  last month of the export, plan changes, duplicate invoices.
* **What I kept / changed / rejected, and why:** kept failed payments, refunds, duplicates and the last month (all
  visible in the data and now acceptance criteria); rejected pauses and annual plans: the export has neither, and
  inventing them would have added untestable rules.
* **How I verified it:** `grep`/counts on `invoices.csv` (`kind`, `status` values), and `feature-spec.md` §3.
* **Time saved / lost (honest guess):** saved ~30 minutes of thinking, lost 10 checking invented fields.
* **What I learned:** a label is a business definition; test only the cases the data can contain.

### 2026-06-05 · Phase 2 · "Just use KFold(shuffle=True)"
* **Tool / model:** Copilot Chat in VS Code
* **Prompt (summary or paste):**
  > Prompt 3 of Phase 2: attack my validation design (grouped folds by customer + out-of-time test).
* **What it produced:** good points on fold sizes and on reporting the SD of fold AUCs; it also suggested a
  shuffled `KFold` over all snapshots "to use more data".
* **What I kept / changed / rejected, and why:** kept the SD and fold-size checks; rejected the shuffled split:
  the same customer one month apart would sit in training and validation, and test months would leak into training.
* **How I verified it:** reasoning from `feature-spec.md` §3, then later the invariant `customers_in_two_folds == 0`.
* **Time saved / lost (honest guess):** neutral.
* **What I learned:** an assistant optimises for "more data"; the plan must optimise for an honest estimate.

### 2026-06-09 · Phase 3 · A ticket from the future
* **Tool / model:** Copilot in VS Code
* **Prompt (summary or paste):**
  > Prompt 1 of Phase 3: implement `open_tickets` for snapshot M (spec §4).
* **What it produced:** "tickets where `resolved_at` is blank", without any cut-off.
* **What I kept / changed / rejected, and why:** rejected. A ticket resolved in M + 1 was open at the cut-off, and a
  ticket created in M + 1 must be invisible; the suggestion got both wrong (it used the export's final state).
  Wrote `created < S and (resolved is missing or resolved >= S)`.
* **How I verified it:** `test_a_ticket_after_the_snapshot_is_invisible` and the tiny fixture's expected features,
  both red with the suggestion.
* **Time saved / lost (honest guess):** lost ~15 minutes, gained the clearest example of leakage I have.
* **What I learned:** "the current state of the table" is the future from the snapshot's point of view.

### 2026-06-11 · Phase 3 · scikit-learn's default logistic regression
* **Tool / model:** ChatGPT (free tier)
* **Prompt (summary or paste):**
  > Fit a logistic regression on these 15 features and return intercept and coefficients.
* **What it produced:** `LogisticRegression(max_iter=1000).fit(X, y)`.
* **What I kept / changed / rejected, and why:** changed to `C=math.inf, solver="newton-cholesky", tol=1e-12`. The
  default is L2-penalised with C=1: a different model, whose coefficients matched neither the golden file nor R's glm.
* **How I verified it:** `parity.py` against `contract/golden/model-2026-05.json` (MATCH after the change).
* **Time saved / lost (honest guess):** saved ~10 minutes of typing, lost 20 finding the penalty.
* **What I learned:** library defaults are modelling decisions; read them.
