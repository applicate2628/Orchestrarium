# Current State Handshake Audit

## Desktop routing workspace

- Curators edit a draft, run local validation, and can mark a bundle as `Ready`, but the state does
  not say whether web review has acknowledged the handoff.
- A local validation failure pushes the user into inline errors without preserving the last review
  context or the exact section that triggered the rework.
- When a reviewer question arrives after handoff, the desktop surface reopens as a generic draft
  instead of a targeted return state.

## Web release console

- Reviewers see bundles labeled `Ready`, `In review`, `Needs clarification`, and `Publish blocked`,
  but the ownership handoff between those labels is vague.
- Review questions and publish blockers coexist without a clear sequence, so reviewers do not know
  whether they are opening a new change loop or continuing an existing one.
- A timed-out review session or deferred approval loses the prior decision context.

## Cross-surface effect

The same bundle can look active, blocked, paused, or returned depending on where the operator
lands. The workflow exposes many badges but not one trustworthy return loop.
