# Oracle

The oracle material defines the ground-truth patch for `S16`.

## Repair truth

The correct fix stays entirely inside the bounded browser UI owner seam. The candidate should turn
the board into a semantic, keyboard-reachable web interface that announces loading and error
states, uses accessible filter buttons, exposes a filter-specific empty state, and keeps the
preview shell plus local verifier unchanged.

## Included oracle files

- `frontend-contract.json` provides machine-readable anchors for the verifier
- `expected-patch.md` describes the required browser UI repair
- `forbidden-widening.md` lists out-of-scope edits that should lose correctness or scope points
- `scoring-anchors.md` turns the scoring model into `S16`-specific pass and fail signals
