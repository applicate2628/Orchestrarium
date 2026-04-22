# Task

You are acting as `$lead` on a benchmark routing thread after several hardening waves.

## Goal

Update `candidate/owner-routing-decision.md` into an owner decision packet that keeps the primary
role-fit task alive, classifies interruptions, defines the next pilot, and states when `X2`, `X5`,
and `X6` should be used as calibration rows.

## Required behavior

- preserve the primary task as role-fit routing for `X1` versus `X3` by lane
- treat `N16` as a diagnostic `E6` rubric, not as a promoted routing lane
- admit exactly one next pilot: owner/orchestration scored routing-recovery packet
- route the immediate next owner to `$lead`
- keep `$qa-engineer` after the pilot bundle/scorer validates, not before
- keep `$architecture-reviewer` after a routing-policy surface changes, not before
- define calibration triggers for `X2`, `X5`, and `X6`
- require an `X5` direct smoke that writes `worker-output.txt` before semantic Gemini Pro runs
- keep quota/runtime failures separate from model failures
- provide a concrete resume point

## Disallowed behavior

- do not declare a global winner between `X1` and `X3`
- do not promote `N16` into the core routing lanes
- do not run `X2`, `X5`, and `X6` on every scenario by default
- do not move this delivery to `$product-manager`, `$qa-engineer`, or `$architecture-reviewer`
- do not edit files outside `candidate/owner-routing-decision.md`
