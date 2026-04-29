# Candidate Root

This is the mutable run root copied for each scored execution.

Only `performance-constraint-package.md` is editable. The file starts as an incomplete template and
must be turned into a full performance-engineer artifact using the evidence packet in `../inputs/`.

## Editable file

- `performance-constraint-package.md`

## Read-only context

- everything under `../inputs/`
- everything under `../oracle/`
- everything under `../verifiers/`

The intended behavior is to constrain the design before implementation. Do not widen the work into
patching the packager, writing a reviewer-style findings report, or defining rollout policy.
