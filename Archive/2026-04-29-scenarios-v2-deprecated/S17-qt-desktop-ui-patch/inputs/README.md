# Inputs

This directory is the immutable packet for `S17`. It defines the Qt-specific interaction contract,
the expected keyboard and focus behavior, and the reuse-lifecycle rules that the candidate patch
must preserve.

## Included materials

- `task.md` defines the benchmark task and editable surface
- `focus-and-keyboard-contract.md` fixes the intended focus chain and key handling
- `widget-lifecycle-notes.md` explains the reuse contract for the same dialog instance
- `non-browser-boundary.md` states what this scenario is explicitly not

The packet is intentionally Qt-specific. A response that reframes the task as browser work,
generic frontend work, or model/view work should lose role-fidelity or scope points.
