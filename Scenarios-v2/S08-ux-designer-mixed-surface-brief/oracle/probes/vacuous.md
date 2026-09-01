# S08 UX Structure Brief

- Brief owner: `$ux-designer`
- Surfaces in scope: Windows desktop workspace plus web review console
- Artifact boundary: one UX structure brief only

## UX objective

Give the mixed desktop-and-web workflow one legible surface architecture, flow, and state model so
ownership is obvious and publish never runs ahead of review.

## Users and operating context

Curators prepare on the desktop workspace; reviewers and approvers work on the web review console;
work crosses surfaces on every handoff and return.

## Current cross-surface pain points

- The publish affordance shows because local checks are green even while a reviewer clarification is
  unresolved.
- Returned packets land the curator on step one with no explicit repair target.
- Owner and return reason are hard to read across surfaces.

## Design principles

- Make the current owner obvious on every surface.
- Gate publish behind review resolution, not local green checks.

## Proposed surface architecture

### Desktop surface

- The desktop surface leads with preparation state and the current owner.

### Web surface

- The web surface leads with review state and the publish disposition.

### Shared handoff touchpoints

- Shared handoff touchpoints keep review and publish state named the same across desktop and web.

## Proposed end-to-end flow

### Flow A - Desktop preparation

- The curator prepares locally and owns the packet until handoff.

### Flow B - Web review and publish

- Review happens on the web surface; publish is shown on the web surface once the packet reaches review.

### Flow C - Return loop for changes or interruptions

- A return loop routes changes back to the desktop repair target and carries the owner and reason.

## State model and ownership

### Desktop-owned state

- Desktop-owned state names the curator as owner during preparation and repair.

### Web-owned state

- Web-owned state names the reviewer and approver as owners; changes requested is an explicit state.

### Shared handoff state

- Shared handoff state carries the owner and the reason across the surface boundary.

## Key interaction changes

- Make the return reason and repair target explicit, keep the blocker visible, and keep the publish step visible in the interaction set.

## Boundaries to implementation and review

- Implementation stays out of scope.
- Review findings stay out of scope.

## Open questions and follow-ups

- How much shared naming can the two surfaces adopt without churn?

## Brief status

PASS
