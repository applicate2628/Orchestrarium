# S14 Reliability Engineer Rollout Package

`S14` benchmarks `R14 $reliability-engineer` on a non-web, evidence-heavy rollout and failure-mode
analysis task. The candidate is asked to produce one reliability constraint package for a local
benchmark publish job that assembles role-first tables after execution evidence lands. The package
must turn the supplied incident and rollout notes into explicit reliability constraints before any
implementation or review work begins.

## Scenario summary

The proposed `role-publish-orchestrator` is a local and CI-only flow that:

1. reads the admitted role-first result set
2. renders role, adapter, overlay, and caveat tables
3. writes a preview packet
4. promotes the preview to the release surface on approval

The evidence packet shows retry confusion after partial publish failures, weak rollback criteria,
and unclear degradation behavior when one provider row is stale. The task is not to repair the
orchestrator. The task is to define the reliability constraints that later planning and review must
respect.

## Expected candidate work

Edit only `candidate/reliability-constraint-package.md`.

Use the evidence packet in `inputs/` to produce a reliability-engineer artifact with:

- a concise service and traffic summary
- rollout stages and admission conditions
- failure modes tied to observed incidents
- rollback triggers and degradation behavior
- recovery and observability requirements
- required constraints for later implementation planning
- explicit evidence gaps
- numbered claims and a final gate decision

## What this bundle tests

- reliability-constraint definition instead of generic operability slogans
- rollout and rollback reasoning grounded in stage-level evidence
- degradation, observability, and recovery discipline
- boundaries that do not drift into implementation repair or review findings
- role fidelity for `R14 $reliability-engineer`

## Bundle map

- `inputs/` holds the immutable evidence packet
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the expected rollout, failure-mode, and rollback read plus prohibited drift
- `verifiers/` checks bundle shape and the completed reliability constraint package
