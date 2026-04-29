# Severity Anchors

- `blocking`
  Use when the modal interaction contract is broken or the reviewer cannot sign off the scoped UI
  surface because a core state escape or primary action surface is unreliable.
- `major`
  Use when the dialog remains reachable but a required visual or interaction state regressed in a
  way that still blocks the phase gate.
- `minor`
  Not expected in the seeded solution. Do not downgrade the known regressions into cosmetic notes.
