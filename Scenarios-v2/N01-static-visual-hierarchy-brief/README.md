# N01 Static Visual Hierarchy Brief

`N01` benchmarks `R08 $ux-designer` on restructuring a mixed desktop/web release workflow where
the main failure is static visual hierarchy and cross-surface information structure. The candidate
must produce one UX structure brief that clarifies what information is primary, what is secondary,
and how the same release facts should appear coherently across both surfaces.

## Scenario summary

The benchmark release workflow spans two operator surfaces:

- a Windows desktop routing workspace where curators prepare a release bundle, inspect validation
  evidence, and resolve local issues
- a web release console where reviewers assess readiness, request clarifications, and approve
  publication

The current experience fails before interaction flow even begins. Key release blockers, reviewer
asks, and evidence freshness cues are visually flattened under secondary metadata. The desktop
workspace and web console also organize the same information differently, so operators re-scan and
re-interpret the bundle every time they switch surfaces.

The correct role behavior is to propose a clearer UX structure: explicit information hierarchy on
each surface, one shared hierarchy ladder across surfaces, and visible cross-surface naming
consistency. This is a UX-structure task, not a code patch, component spec, or architecture memo.

## Expected candidate work

Edit only the file listed in `scenario.yaml`:

- `candidate/ux-structure-brief.md`

Use only the accepted packet in `inputs/`. The completed UX structure brief must:

- stay UX-designer-owned and structure-focused
- define a coherent static visual hierarchy for the desktop workspace and web release console
- assign primary, secondary, and deferred information zones across both surfaces
- align shared naming and information grouping so operators do not mentally translate between
  surfaces
- keep implementation code, component specs, architecture decisions, and review findings out of
  scope
- end with one explicit gate decision: `PASS`, `REVISE`, or `BLOCKED`

## What this bundle tests

- static UX hierarchy rather than interaction choreography
- cross-surface information structure rather than single-screen polish
- the ability to prioritize blockers, evidence, and ownership cues without drifting into
  implementation
- role fidelity for `$ux-designer` rather than `$frontend-engineer`, `$qt-ui-engineer`,
  `$architect`, or `$ux-reviewer`

## Bundle map

- `inputs/` holds the admitted task, current hierarchy audit, information-structure friction, and
  boundary rules
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the expected hierarchy direction, anti-patterns, and scoring anchors
- `verifiers/` contains a local checker for bundle shape and completed static-hierarchy briefs
