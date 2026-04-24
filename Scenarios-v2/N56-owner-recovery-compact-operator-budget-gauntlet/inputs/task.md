# Task

You are acting as `$lead` for the benchmark hardening program after W35/N55.

## Goal

Update `candidate/owner-recovery-wave-roadmap-decision.md` into a compact owner recovery packet that:

- identifies the current source of truth
- rejects stale source claims
- reconciles lane state after N24 and N25
- preserves the primary task continuity
- classifies interruptions without dropping the original task
- chooses the next owner and gates
- defines bounded calibration-row and runtime-failure policy
- states spawn/result-file discipline
- gives a concrete resume point
- ends with a parseable JSON decision block
- keeps the whole worker output concise enough for the visible operator budget

## Required behavior

- state that there is no global winner admitted
- state that N14..N55 are diagnostic overlays, not a merged old full-v2 denominator
- state that systems/toolchain is `X3 primary`, `X1 secondary`
- state that UI implementation is `X3 primary` versus X1 and `X5` is contender only
- state exactly `Compact owner recovery: X3 primary`
- state exactly `Staged owner recovery: X1 primary`
- state exactly `X5 remains owner contender only after N26`
- state that review/security remains X1/X3 near-tie
- state exactly `Visible operator budget: worker-output <= 40000 bytes`
- choose `Next owner now: $lead`
- route QA only after `QA gate only after N56 bundle, verifier, scorer, reference, and operator-budget pass validate`
- route architecture review only after a routing-policy surface changes
- run `X1` and `X3` first
- state exactly `X2 and X6 run together after a completed task or when lane policy may change`
- state exactly `X5 stays quota-deferred`
- require `X5` same-session smoke that writes `worker-output.txt` before semantic run
- classify runtime failures as `NOT-RUN`, `REQUEUE`, `RUNTIME-FAIL`, or `ROUTE-FAIL`, not model `FAIL`
- allow read-only explorers but keep roadmap and live result surfaces with the main owner
- do not create stale parallel result files
- state `Next scenario: N56-owner-recovery-compact-operator-budget-gauntlet`
- cite the exact path:line anchors from `inputs/source-excerpts.md`

## Disallowed behavior

- do not declare `X3` or `X1` the global winner
- do not promote N16, N23, N24, or N25 into unrelated routing lanes by themselves
- do not make X5 the global UI default from one N25 pass
- do not promote X5 over X3 for owner recovery from N26 alone
- do not ask `$product-manager`, `$qa-engineer`, or `$architecture-reviewer` to own the next design step
- do not run X2/X5/X6 on every scenario by default
- do not call runtime/route failures model failures
- do not edit files outside `candidate/owner-recovery-wave-roadmap-decision.md`
