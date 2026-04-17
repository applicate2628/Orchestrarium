# S08 UX Designer Mixed-Surface Brief

`S08` benchmarks `R08 $ux-designer` on restructuring a mixed desktop/web interaction without
turning the artifact into implementation instructions, an architecture ADR, or a review report.
The candidate must produce one UX structure brief that clarifies cross-surface flow, state
ownership, and handoff behavior for a workflow that starts in a Windows desktop workspace and ends
in a web review console.

## Scenario summary

The benchmark system uses two operator surfaces for scenario-release work:

- a Windows desktop authoring workspace where curators assemble and locally validate scenario
  bundles from local files
- a web review console where reviewers check readiness, request changes, and publish approved
  bundles to the shared benchmark registry

The current experience is fragmented. The desktop flow behaves like a step-by-step wizard, the web
console behaves like a queue plus detail tabs, and the shared status labels do not line up. People
lose track of whether a bundle is blocked by missing content, validation failures, reviewer
questions, or a publish prerequisite. When reviewers request changes in the web console, the return
path into the desktop workspace is vague, so curators re-open the wrong step or duplicate notes.

The correct role behavior is to propose a clearer UX structure: explicit surface boundaries,
explicit cross-surface state ownership, and an end-to-end flow that reduces handoff confusion
without collapsing the two surfaces into one implementation plan.

## Expected candidate work

Edit only the file listed in `scenario.yaml`:

- `candidate/ux-structure-brief.md`

Use only the accepted packet in `inputs/`. The completed UX structure brief must:

- stay UX-designer-owned and structure-focused
- define a coherent desktop-plus-web interaction model
- restructure the end-to-end flow, including the return loop for change requests or interruptions
- assign state ownership and visible handoff cues across the two surfaces
- keep implementation code, component specs, architecture decisions, and review findings out of
  scope
- end with one explicit gate decision: `PASS`, `REVISE`, or `BLOCKED`

## What this bundle tests

- interaction design for a mixed desktop/web operator workflow
- explicit state and flow restructuring rather than generic product prose
- separation between UX design, implementation planning, and later UX review output
- role fidelity for `$ux-designer` rather than `$architect`, `$frontend-engineer`,
  `$qt-ui-engineer`, or `$ux-reviewer`

## Bundle map

- `inputs/` holds the accepted design brief, current cross-surface audit, friction notes, and role
  boundary rules
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the expected UX direction, anti-patterns, and scoring anchors
- `verifiers/` contains a local checker for bundle shape and completed UX-brief structure
