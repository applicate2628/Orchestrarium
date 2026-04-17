# Candidate

This directory is the mutable run root copied per execution.

## Editable surface

Only `phase-plan.md` is editable for the scored run. There is intentionally no implementation
workspace or code tree in this bundle.

## Output contract

The completed file must remain one planner-owned phase plan. It must not turn into:

- a factual research memo or repo investigation
- an architecture ADR or redesign proposal
- a QA verdict or review findings report
- an implementation patch, diff, code sample, or workspace scaffold

Keep the phase ordering explicit and bounded. Follow the template structure so the verifier can
check file scope, dependencies, tests and checks, and rollback notes without reinterpretation.
