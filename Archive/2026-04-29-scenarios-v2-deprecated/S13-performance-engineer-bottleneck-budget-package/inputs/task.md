# Task

Surface: `R13 $performance-engineer`
Artifact type: `performance constraint package`
Modality family: `budget and bottleneck analysis`

## Goal

Produce `candidate/performance-constraint-package.md` for the local `cohort-packet-packager`
workflow.

The package must be suitable input to later planning and later performance review. It must stay in
the performance-engineer lane: define budgets, bottlenecks, measurement strategy, and constraints
before implementation. Do not return a code patch, a review findings report, or a rollout or
reliability policy package.

## Required output content

Your package must include:

1. a system and workload summary
2. an explicit budget envelope
3. bottleneck framing
4. a measurement strategy
5. tradeoff boundaries
6. required constraints for later implementation work
7. open questions and evidence gaps
8. a numbered claims section
9. a final gate decision of `PASS`, `REVISE`, or `BLOCKED`

## Evidence use rule

Reference the supplied evidence IDs (`E1` through `E5`) in the package. The scenario is scored on
how well the budgets and bottleneck constraints trace back to the evidence instead of drifting into
generic performance folklore.

## Scope discipline

- Edit only `candidate/performance-constraint-package.md`
- Keep the package non-web and packet-only
- Separate cold-run and warm-run measurement requirements
- Preserve redaction, hash-manifest coverage, and deterministic replay as explicit boundaries
- Do not turn the package into implementation repair instructions, reviewer findings, or
  reliability-rollout policy
