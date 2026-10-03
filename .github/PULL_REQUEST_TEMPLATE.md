## What & why
<!-- One or two sentences. Link the issue: "Closes #12" -->

## Track(s)
- [ ] Python  - [ ] SQL  - [ ] R  - [ ] Shared (contract / API / docs / CI)

## How I tested it
<!-- Commands you ran and their result, e.g. `make test` → 92 passed; `python3 scripts/parity.py ...` → MATCH -->

## Numbers check
<!-- Did any number in metrics.json or model.json change? If yes: which, why, and does parity with the golden
     files and the other tracks still hold? A metric that got better without a reason in the contract is the
     first thing to suspect (leakage?). A changed number without a reason is a bug, not a result.
     "No numbers changed" is a fine answer. -->

## AI assistance
<!-- Which tool, what it drafted, what you changed or rejected, how you verified it. "None" is fine.
     Add a matching entry to AI_LOG.md. -->

## Self-review checklist
- [ ] CI is green
- [ ] Tests cover the new behaviour (including at least one bad-data case)
- [ ] No feature uses anything known after the snapshot cut-off, `cancellation_reason` or `age_band`
- [ ] Behaviour matches `contract/feature-spec.md` (or the contract is updated in this PR, with a version bump)
- [ ] No secrets, `.env` files or row-level personal data in commits, logs or prompts
- [ ] Docs / CHANGELOG updated if a reader of the results would notice the change
- [ ] I can explain every line of this diff, and every number it changes, without the AI's help
