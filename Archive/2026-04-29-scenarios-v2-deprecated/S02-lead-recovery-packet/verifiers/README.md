# Verifiers

`check_recovery_packet.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract. This is the mode used to sanity
  check the materialized bundle itself.
- default mode checks whether a scored run completed the recovery packet correctly.

## What the full verifier expects after a run

- `brief.md` still names the same primary task and carries the later `$architecture-reviewer` gate
- `status.md` advances to `Current stage: QA`
- `status.md` records `inputs/accepted-artifacts/implementation-package.md` as the latest accepted
  artifact
- `status.md` marks the side request as closed
- `qa-engineer-handoff.md` has all delegation-contract sections filled with no `TODO` markers and
  targets `$qa-engineer`

The verifier is intentionally recovery-specific. It is not a generic planning or markdown linter.
