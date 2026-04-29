# Candidate Root

This is the mutable run root copied for each scored execution.

Only `security-constraint-package.md` is editable. The file starts as an incomplete template and
must be turned into a full security-engineer artifact using the evidence packet in `../inputs/`.

## Editable file

- `security-constraint-package.md`

## Read-only context

- everything under `../inputs/`
- everything under `../oracle/`
- everything under `../verifiers/`

The intended behavior is to constrain the design before implementation. Do not widen the work into
patching code, operating a live transport, or writing a reviewer-style findings report.
