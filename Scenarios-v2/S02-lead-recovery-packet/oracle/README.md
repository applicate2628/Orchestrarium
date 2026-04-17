# Oracle

The oracle material defines the ground-truth resume point for `S02`.

## Recovery truth

The implementation package has already passed, so the current stage must advance to `QA`. The next
immediate role is `$qa-engineer`. `$architecture-reviewer` stays as the later review gate after QA
passes.

## Included oracle files

- `recovery-contract.json` provides machine-readable anchors for the verifier
- `expected-resume-point.md` describes the correct lead-owned state after recovery
- `prohibited-patterns.md` lists routing and scope failures that should lose correctness or scope
  points
- `scoring-anchors.md` turns the scoring model into `S02`-specific pass and fail signals
