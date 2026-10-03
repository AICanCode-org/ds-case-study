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
