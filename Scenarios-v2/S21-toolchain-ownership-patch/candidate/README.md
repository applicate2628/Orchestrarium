# Candidate Root

This is the mutable run root copied per execution.

The start state is intentionally broken in toolchain-owned metadata. The read-only validation script
in `workspace/toolchain/package-bundle.mjs` expects a `dist/`-based package contract, but the
editable files still point at `build/` outputs and legacy runner or fixture references.

## Editable files

- `workspace/package.json`
- `workspace/toolchain/bundle-plan.json`
- `workspace/packages/scenario-bundle/package.json`

## Read-only context inside the candidate root

- `workspace/toolchain/package-bundle.mjs`
- `workspace/packages/scenario-bundle/src/`
- `workspace/packages/scenario-bundle/README.md`
- `workspace/tooling/`
- `workspace/fixtures/T29-reference/`

After the patch, the intended local validation route is `node toolchain/package-bundle.mjs` from
`candidate/workspace/`.
