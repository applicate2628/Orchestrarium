# S08 Task

Produce one UX structure brief for the benchmark release workflow described in this bundle.

## Role and artifact

- Target role: `R08 $ux-designer`
- Required artifact: one `UX structure brief`
- Editable surface: `candidate/ux-structure-brief.md`

## Core problem

Operators prepare release-ready scenario bundles in a Windows desktop workspace, then switch to a
web review console for review, approval, and publish. The current experience has inconsistent
states, unclear handoffs, and a weak return path when reviewers send work back.

The brief must restructure:

- the surface hierarchy across desktop and web
- the end-to-end flow from local preparation through publish
- the visible state model and ownership boundaries
- the interruption and change-request loop back into the desktop workspace

## Required output characteristics

The brief must:

- stay at the UX-structure level
- describe how the two surfaces should work together without merging them into one tool
- explain the cross-surface state model and the user-visible handoff cues
- preserve desktop-local authoring and web-based review or publish as separate surfaces
- call out what implementation and later UX-review lanes should receive, but not perform that work

## Out of scope

Do not turn the brief into:

- code patches, component APIs, or screen implementation tickets
- an architecture ADR or dependency-direction proposal
- a findings-only review report or accessibility audit
- a roadmap prioritization packet or a planner phase breakdown
