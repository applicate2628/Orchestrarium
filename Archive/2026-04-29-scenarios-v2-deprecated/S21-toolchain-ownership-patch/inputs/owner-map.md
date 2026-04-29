# Owner Map

## Toolchain-owned surfaces

- workspace validation script entry in `candidate/workspace/package.json`
- bundle planning metadata in `candidate/workspace/toolchain/bundle-plan.json`
- publish manifest in `candidate/workspace/packages/scenario-bundle/package.json`

## Read-only context

- runtime implementation in `candidate/workspace/packages/scenario-bundle/src/`
- package README in `candidate/workspace/packages/scenario-bundle/README.md`
- validator implementation in `candidate/workspace/toolchain/package-bundle.mjs`
- legacy runner snapshot in `candidate/workspace/tooling/`
- legacy fixture reference in `candidate/workspace/fixtures/T29-reference/`

This is an owner-seam repair. The right fix is to correct the package contract at the toolchain
boundary, not to move source files or edit legacy reference material.
