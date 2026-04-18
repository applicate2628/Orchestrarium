# Review Boundary

This bundle is a generic pre-PR code-review gate for one additive helper.

## In scope

- changed-surface coverage regressions
- finding collapse or data-loss behavior
- silent failure or diagnosability regressions in evidence extraction
- concrete file-anchored findings that support a `REVISE` gate

## Out of scope

- architecture redesign or dependency-direction review beyond what is needed to explain a concrete
  generic code-review finding
- security review, threat modeling, or vulnerability triage
- performance benchmarking or scale-budget analysis
- implementation notes, patch steps, or repair-plan artifacts
