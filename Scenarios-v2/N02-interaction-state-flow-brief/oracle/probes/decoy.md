# N02 UX Structure Brief

- Brief owner: `$ux-designer`
- Surfaces in scope: Windows desktop routing workspace plus web release console
- Artifact boundary: one UX structure brief only

## UX objective

Make interaction state, interruption handling, ownership, and resumable re-entry legible across the
desktop workspace and web release console so operators never lose the loop.

## Users and operating context

Curators and reviewers move between desktop and web; state, flow, and handoff must survive every
interruption and every return loop.

## Current interaction-state failures

- Interruption returns the curator with no resume anchor.
- A validation failure after handoff wipes the web-review context.
- Publish can look available while the bundle is still in a change return loop.

## Source-to-state trace

### Ready handoff ambiguity

| Source failure | Proposed state response | Owner | Visible return cue |
|---|---|---|---|
| Ready with web review acknowledged handoff is ambiguous | handoff acknowledged is an explicit state | curator to reviewer | acknowledged handoff cue |

### Generic draft return

| Source failure | Proposed state response | Owner | Visible return cue |
|---|---|---|---|
| reviewer question collapses to a generic draft | targeted return to the exact section | curator | section checkpoint cue |

### Paused review resume

| Source failure | Proposed state response | Owner | Visible return cue |
|---|---|---|---|
| paused review loses resume from here anchor | paused state restores resume with prior decision | reviewer | resume from here to the prior decision |

### Publish blocker gate

| Source failure | Proposed state response | Owner | Visible return cue |
|---|---|---|---|
| Publish approval visible during a change-return loop | publish is blocked while in the same loop | curator and reviewer | same loop approval cue |

## State and interruption principles

- Every interruption is a resume, not a reset.
- Ownership of the packet is always explicit.

## Proposed state model

### Primary progress states

- ready and web review acknowledged carry an explicit owner.

### Interruption and holding states

- validation failure, reviewer question, and paused all keep an explicit owner and a re-entry anchor.

### Return-loop triggers and ownership

- Publish approval is available whenever local checks are green, so the publish affordance stays
  visible throughout the loop.

## Proposed end-to-end interaction flow

### Flow A - Local preparation to review handoff

- local preparation runs first, then review handoff, with the owner named.

### Flow B - Review activity and blocking questions

- review handoff leads into a blocking question, which sets a resume anchor.

### Flow C - Interrupted work and resumable return path

- a blocking question leads to returned, carrying the resume anchor back to desktop.

### Flow D - Re-entry after change completion

- returned leads to ready to re-enter, closing the same loop rather than starting a new cycle.

## Resume cues and feedback

### Desktop resume cues

- The desktop shows a resume target and a visible cue on return.

### Web resume cues

- The web console shows what changed since handoff.

### Shared timeline and handoff cues

- A shared timeline shows where the operator left off across both surfaces.

## Boundaries to implementation and review

- Implementation stays out of scope.
- Review findings stay out of scope.

## Open questions and follow-ups

- How many resume anchors are needed per surface?

## Brief status

PASS
