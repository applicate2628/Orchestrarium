# Oracle

The oracle material defines the ground-truth QA outcome for `S25`.

## Verdict truth

The implementation should not pass QA. The correct verdict is `REVISE` because one acceptance
criterion failed in executed smoke evidence and one nearby must-not-break surface was never smoke
checked.

## Included oracle files

- `qa-contract.json` provides machine-readable bundle and report anchors for the verifier
- `expected-verdict.md` lists the acceptance mapping and the correct gate outcome
- `regression-classification.md` states how the observed defect should be classified
- `bug-registry-expectations.md` defines the expected follow-up when the verdict is not a pass
- `false-positive-traps.md` lists common but incorrect QA conclusions
- `scoring-anchors.md` maps the global review-and-QA profile to `S25`-specific pass and fail
  signals
