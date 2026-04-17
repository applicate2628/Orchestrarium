# Oracle

The oracle material defines the ground-truth planning contract for `S09`.

## Planning truth

The preferred plan stays plan-only and sequences the admitted work in the same order implied by
the accepted design:

1. stabilize the JSON contract in the tool owner seam
2. add `--dry-run` preview and explicit no-write enforcement on top of that contract
3. run the required checks, update docs, and hand off to QA and review without widening scope

## Included oracle files

- `plan-contract.json` provides machine-readable bundle and phase-plan anchors for the verifier
- `expected-phase-order.md` explains the required phase order and file-scope truth
- `anti-patterns.md` lists planning drift and contract-breaking patterns
- `scoring-anchors.md` translates the shared planning-profile signals into `S09` reads
