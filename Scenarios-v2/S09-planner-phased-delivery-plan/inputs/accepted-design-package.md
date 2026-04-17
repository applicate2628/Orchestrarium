# Accepted Design Package

## Chosen seam

Extend the existing owner seam in `tools/status_snapshot.py`. The tool remains the single place
that parses flags, builds the snapshot payload, and decides whether to render text, emit JSON, or
perform a preview-only dry run.

## Design commitments

- keep the implementation in the current module; do not introduce a wrapper script or new runner
- keep `tests/test_status_snapshot.py` as the direct verification seam
- preserve the current `--text-summary` path as the stable adjacent behavior
- keep the real JSON write contract on `status.snapshot.json`
- treat `--dry-run` as a write guard that returns the would-be payload without touching the
  filesystem

## Planning implications

1. Stabilize the JSON payload contract before introducing `--dry-run` preview semantics.
2. Land write-guard behavior only after the JSON path and its tests are explicit.
3. Update user-facing docs only after the behavior and verification route are stable.
4. Hand off to QA and review after the local checks pass; do not fold review work into the plan.
