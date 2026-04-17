# Boundary Rules

## UX design versus implementation

The brief may specify:

- screen groups or surface areas
- information hierarchy
- user-visible statuses and state transitions
- handoff cues, return cues, and interruption behavior
- what information needs to be visible at each step

The brief must not specify:

- desktop widget classes, web component names, route files, or persistence schemas
- exact API contracts, event payloads, or database changes
- test scripts, automation details, or command sequences

## UX design versus architecture

The brief may explain why the desktop and web surfaces remain separate from a user-flow
perspective, but it must not turn into a dependency-direction decision, seam proposal, or
repository-ownership ADR.

## UX design versus review output

The brief may identify pain points and propose a better structure, but it must not become:

- a findings-only review report
- a scored usability verdict
- an accessibility audit
- a bug list with severity labels

That review-oriented work belongs to later reviewer scenarios, including the dedicated UX-review
lane.
