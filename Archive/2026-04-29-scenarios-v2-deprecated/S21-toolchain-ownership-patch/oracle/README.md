# Oracle

The oracle material defines the ground-truth patch for `S21`.

## Repair truth

The correct fix stays entirely inside toolchain-owned metadata. The candidate should normalize the
workspace validation script, the bundle plan, and the package manifest to a `dist/` contract and
remove any legacy runner or `T29` fixture references. Runtime source, the validator script, and
legacy reference material remain unchanged.

## Included oracle files

- `toolchain-contract.json` provides machine-readable anchors for the verifier
- `expected-patch.md` describes the required metadata repair
- `forbidden-widening.md` lists out-of-scope edits that should lose correctness or scope points
- `scoring-anchors.md` turns the scoring model into `S21`-specific pass and fail signals
