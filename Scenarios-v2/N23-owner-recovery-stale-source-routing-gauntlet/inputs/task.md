# Task

You are acting as `$lead` for the benchmark hardening program after W2/N22.

## Goal

Update `candidate/owner-recovery-routing-decision.md` into a compact owner recovery packet that:

- identifies the current source of truth
- rejects stale source claims
- preserves the primary task continuity
- classifies interruptions without dropping the original task
- chooses the next owner and gates
- defines bounded calibration-row policy
- gives a concrete resume point

## Required behavior

- state that there is no global winner admitted
- state that N16 is diagnostic E6, not a routing lane
- state that N17 did not split owner correctness
- state that W3 / E13 / N23 is the admitted next wave
- choose `Next owner now: $lead`
- route QA only after N23 bundle, verifier, scorer, and reference pass validate
- route architecture review only after a routing-policy surface changes
- run `X1` and `X3` first
- run `X2` and `X6` only when lane policy may change
- require `X5` same-session smoke that writes `worker-output.txt` before semantic run
- classify runtime failures as `NOT-RUN` or `ROUTE-FAIL`, not model `FAIL`
- cite the exact path:line anchors from `inputs/source-excerpts.md`

## Disallowed behavior

- do not declare `X3` or `X1` the global winner
- do not promote N16 or N22 into a routing lane by itself
- do not ask `$product-manager`, `$qa-engineer`, or `$architecture-reviewer` to own the next design step
- do not run X2/X5/X6 on every scenario by default
- do not call runtime/route failures model failures
- do not edit files outside `candidate/owner-recovery-routing-decision.md`
