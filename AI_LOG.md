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
