# G08 Fixture - Static UI Evidence

## Goal

Diagnose a UI issue from static artifact evidence and captured non-browser state, then recommend the smallest safe fix order.

## Expected artifact

- top blocking issues
- root-cause ranking
- smallest safe fix order
- non-browser follow-up checks

## Inputs

- `screen.html`
- `styles.css`
- `interaction-contract.md`
- `observed-state.md`
- `triage-notes.md`

## Hard constraints

- do not depend on a live browser or Playwright
- keep structural layout bugs, accessibility bugs, and ranking-semantics bugs distinct
- do not recommend a whole-screen redesign
- do not treat a pure `z-index` tweak as sufficient if the ownership or semantics are wrong
