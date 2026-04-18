# N02 Interaction-State Flow Brief

`N02` benchmarks `R08 $ux-designer` on restructuring a mixed desktop/web release workflow where
the main failure is interaction-state flow, interruption handling, and return-loop reasoning. The
candidate must produce one UX structure brief that clarifies how work progresses, how it pauses,
and how people re-enter the correct place after interruptions or change requests.

## Scenario summary

The benchmark release workflow spans two operator surfaces:

- a Windows desktop routing workspace where curators assemble and locally validate a release bundle
- a web release console where reviewers raise questions, approve readiness, and gate publication

The current workflow exposes many states but few usable transitions. Local validation can fail
mid-edit, reviewer questions appear after a handoff, sessions time out, and approval work gets
interrupted by context switches. Operators lose their place and return to the wrong step because
the system does not make interruption states or return loops explicit.

The correct role behavior is to propose a clearer UX structure: explicit progress states, explicit
interruption and holding states, and a visible re-entry path when work resumes. This is a
UX-structure task, not a code patch, implementation plan, or review report.

## Expected candidate work

Edit only the file listed in `scenario.yaml`:

- `candidate/ux-structure-brief.md`

Use only the accepted packet in `inputs/`. The completed UX structure brief must:

- stay UX-designer-owned and structure-focused
- define a coherent state model spanning desktop preparation and web review
- restructure the interruption and return-loop behavior for validation failures, reviewer asks, and
  paused work
- assign state ownership and visible resume cues across both surfaces
- keep implementation code, component specs, architecture decisions, and review findings out of
  scope
- end with one explicit gate decision: `PASS`, `REVISE`, or `BLOCKED`

## What this bundle tests

- interaction-state reasoning rather than static layout hierarchy
- interruption handling and return-loop design for a mixed desktop/web workflow
- explicit ownership and resumability rather than generic user-journey prose
- role fidelity for `$ux-designer` rather than `$frontend-engineer`, `$qt-ui-engineer`,
  `$architect`, or `$ux-reviewer`

## Bundle map

- `inputs/` holds the admitted task, current state audit, interruption friction, and boundary rules
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the expected state-flow direction, anti-patterns, and scoring anchors
- `verifiers/` contains a local checker for bundle shape and completed state-flow briefs
