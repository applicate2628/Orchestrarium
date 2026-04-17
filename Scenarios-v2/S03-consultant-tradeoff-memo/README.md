# S03 Consultant Tradeoff Memo

`S03` benchmarks `R03 $consultant` on writing one advisory-only second-opinion memo when the
evidence is incomplete but still strong enough to support a narrow recommendation. The candidate is
not asked to route work, approve a phase, or turn the task into implementation or planning output.

## Scenario summary

The benchmark redesign already has a fixed bundle contract, fixed score-profile mapping, and a real
need to decide how the memo-only pattern should be validated before more memo bundles are added.
The lead wants a consultant memo on whether to:

- pilot one local advisory bundle first
- build shared memo scaffolding before any new bundle exists
- wait for more evidence before materializing anything

The packet intentionally includes non-empty evidence plus unresolved unknowns. The scored behavior
is to recommend a direction, compare alternatives, surface uncertainty, and remain explicitly
non-blocking.

## Expected candidate work

Edit only the file listed in `scenario.yaml`:

- `candidate/advisory-memo.md`

Use only the accepted packet in `inputs/`. The completed memo must:

- stay advisory-only and memo-only
- include the consultant provenance header
- recommend one direction against at least two realistic alternatives
- name major tradeoffs, risks, assumptions, uncertainty, and confidence
- end with `NON-BLOCKING` advisory status plus a reusable continuation prompt

## What this bundle tests

- second-opinion judgment without hidden routing or approval authority
- tradeoff framing from incomplete but usable evidence
- explicit uncertainty instead of false certainty
- adherence to the consultant memo contract rather than lead, planner, or architect drift

## Bundle map

- `inputs/` holds the accepted brief, evidence summary, decision pressure, and open questions
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the preferred advisory direction, anti-patterns, and scoring anchors
- `verifiers/` contains a local checker for bundle shape and completed memo structure
