# Task

Produce one UX structure brief for the release workflow described in this bundle.

## Required output

- Editable surface: `candidate/ux-structure-brief.md`
- Required artifact: one `UX structure brief`
- Role owner: `$ux-designer`

## What the brief must accomplish

- define an explicit progress and interruption state model across desktop and web
- include a source-to-state trace that maps the admitted input failures to the proposed states and
  transitions
- each source-to-state trace subsection must use a Markdown table with columns: `Source failure`,
  `Proposed state response`, `Owner`, and `Visible return cue`
- explain how review questions, validation failures, paused work, and resumed work should move
  people through the workflow
- make the return path legible after interruptions or requested changes
- assign visible ownership and resume cues for each major state
- keep implementation details, architecture decisions, tickets, code changes, and review findings
  out of scope

End the brief with exactly one status: `PASS`, `REVISE`, or `BLOCKED`.
