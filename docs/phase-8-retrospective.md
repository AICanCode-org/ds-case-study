---
phase: 8
slug: phase-8-retrospective
title: Retrospective and portfolio
duration: 1.5 h
start_tag: phase-7-end
end_tag: phase-8-end
---
# Phase 8 · Retrospective and portfolio

## 1. Why it matters
Hiring managers do not read your code first; they read the first screen of your README and listen to how you talk
about trade-offs. A retrospective turns nine phases of work into lessons you can explain in an interview: what the
model is good for, what it cannot tell you, which decisions you would make again, and how AI helped and misled
you. In this phase you write the retrospective, put a case study at the top of your README, and prepare a
two-minute story and a portfolio blurb with real numbers.

## 2. Objectives
By the end of this phase you can:
- Run a structured retrospective (what went well, what did not, what you would change) with evidence from your commits, CI runs and `AI_LOG.md`.
- Write a README case study: problem, approach, results with numbers, limits, and how to run it in five minutes.
- Explain the project's key trade-offs: logistic regression first, grouped out-of-time validation, calibration over accuracy, a contract that stops the run, three tracks.
- Present the project in two minutes, including one thing that went wrong and what you changed.

## 3. Step-by-step instructions

### Step 8.1 · Collect the evidence
```bash
git log --oneline phase-0-end..phase-7-end | wc -l          # how many commits
git log --format='%s' phase-2-end..phase-3-end | head -20    # what M1-M5 really took
gh run list --branch solution --limit 10                     # CI history (or the Actions tab)
```
Re-read your `AI_LOG.md`: count the entries where you kept, changed and rejected an AI output. Find the one
rejection that saved you the most (a leak, a wrong metric, an invented number).

### Step 8.2 · The retrospective
Write `docs/retrospective.md` with: the goal and what was delivered (v1.0.0, v1.1.0); results (test AUC, ECE, the
call list against the rule, the value estimate and its assumption, fairness); what went well; what went badly and
what you changed; decisions you would make again and ones you would not; how AI helped and where it misled you;
what you would do next (a randomised hold-out to measure the real save rate, uplift modelling, a gradient-boosted
challenger through the same gate, automated monthly monitoring).

### Step 8.3 · The README case study
Put a short case study right below the badges of `README.md`: the problem in two sentences, the approach in four
bullets, a results table (baseline vs model), the most important limitation, and "run it in five minutes". The
reference version is at `phase-8-end`. Numbers must come from your `metrics.json`; link the model card and the
post-mortem.

### Step 8.4 · Your two-minute story and the blurb
Practise out loud: the decision (10 % call capacity), the trap (leakage, a random split), the model and why
(calibrated, explainable), the result versus the rule (AUC 0.743 vs 0.651, recall of the call list 30 % vs 21 %),
what happened after launch (contract break, calibration drift, a recalibrated challenger promoted on a holdout),
and one thing you would do differently. Then adapt the portfolio blurb in `cms/project.json` for your CV or
LinkedIn; keep every number one you can defend.

<!-- track:python -->
Python track: link the executed notebook (download the `report-python` artifact of the last green run, or use
nbviewer on your fork) from the case study.
<!-- /track -->
<!-- track:sql -->
SQL track: link `out/report.md` (from the `report-sql` artifact) and one SQL file you are proud of (the
point-in-time features of `03_features.sql` are a good interview topic).
<!-- /track -->
<!-- track:r -->
R track: link the knitted `churn-model.html` (from the `report-r` artifact, or GitHub Pages on your fork) and mention
the pinned Docker toolchain; reproducibility is a strong interview topic.
<!-- /track -->

## 4. AI-assist prompts

### Prompt 1: Run my retrospective interview
```text
Interview me about a churn-modelling project I just finished, one question at a time, as a senior data scientist
would in a retrospective. Ask about decisions, trade-offs, mistakes and what I would do differently. After 8
questions, summarise my answers as a retrospective with sections: went well, went badly, would change, next steps.
```
**Verify the output by:** checking that the summary only contains what you said (assistants fill gaps with generic
lessons), and backing each point with a commit, a CI run or an `AI_LOG.md` entry.

### Prompt 2: Tighten my README case study
```text
Here is the case study at the top of my README: <paste>. Make it readable in 60 seconds by a hiring manager:
problem, approach, results, limits, how to run. Keep every number exactly as it is, do not add new claims, and
point out any claim that is not supported by a number or a link.
```
**Verify the output by:** diffing the numbers before and after (none may change), and checking every link.

### Prompt 3: Mock interview on trade-offs
```text
Ask me five hard interview questions about this project: <paste the case study>. Focus on leakage, validation,
calibration, fairness, the value estimate's assumptions, and why logistic regression. After each answer, tell me
what a strong answer would add.
```
**Verify the output by:** checking each "strong answer" against `feature-spec.md`, the model card and your
results; reject advice that contradicts your own evidence (e.g. "always use XGBoost").

## 5. Deliverables
- [ ] `docs/retrospective.md` with evidence.
- [ ] A README case study at the top of `README.md`, every number from `metrics.json`.
- [ ] Your two-minute story (written or recorded) and an adapted portfolio blurb.
- [ ] A final `AI_LOG.md` entry: how AI helped and misled you over the whole project.

## 6. Self-check quiz

### Q1. A recruiter asks "how accurate is your model?". What is the best answer?
- [ ] "About 91 % accurate"
- [x] "Accuracy is the wrong measure for a 9 % churn rate and a 10 % call list; it ranks well (test AUC 0.74), finds 30 % of next month's churners in the top 10 %, and its probabilities are calibrated"
- [ ] "AUC 0.76 in cross-validation"
- [ ] "It beats every other model"
> **Answer:** Predicting "nobody churns" is 91 % accurate and useless. Use the metrics of the decision, from the out-of-time test.

### Q2. What is the most important limitation to state about the ₹1.1 lakh monthly value?
- [ ] It is in rupees
- [x] It depends on an assumed 25 % save rate; only a randomised hold-out experiment can measure whether calls cause customers to stay
- [ ] It was computed in Python
- [ ] It is a monthly figure
> **Answer:** Predictive accuracy does not imply a causal effect of the intervention. State the assumption and how to test it.

### Q3. Why mention the post-mortem in a portfolio?
- [ ] To show the project failed
- [x] It shows you can operate a model after launch: detect a break, decide through a contract change, monitor, retrain and learn without blame
- [ ] Post-mortems are required by GitHub
- [ ] It makes the README longer
> **Answer:** Most portfolio projects end at training. Handling drift and an upstream change is what production work looks like.

### Q4. Which statement about the three tracks is the strongest interview point?
- [ ] "I used three languages"
- [x] "Three independent implementations agreeing to 1e-6 caught a real tie-breaking bug that unit tests had missed"
- [ ] "R is better than Python"
- [ ] "SQL is faster"
> **Answer:** Parity is a testing technique. Explain what it found, not just that it exists.

### Q5. What belongs in "what I would do next"?
- [ ] Nothing: the project is finished
- [ ] Rewriting it in another language
- [x] A randomised hold-out to measure the save rate, uplift modelling, a more flexible challenger through the same gate, automated monthly monitoring
- [ ] Removing the tests to make it simpler
> **Answer:** Next steps should follow from the limitations you found, and keep the same evaluation discipline.

## 7. What you learned
- A retrospective grounded in evidence from commits, CI runs and the AI log.
- A README case study and a two-minute story that lead with the decision and the honest numbers.
- How to talk about trade-offs: model choice, validation, calibration, fairness, causality, operations.

## 8. Catch-up git commands
```bash
git fetch upstream --tags
git diff phase-7-end phase-8-end -- README.md docs/retrospective.md
git switch -c my-portfolio phase-8-end
```
