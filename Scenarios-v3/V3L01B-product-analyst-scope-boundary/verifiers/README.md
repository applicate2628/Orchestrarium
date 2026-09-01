# Verifier

`check_scope_boundary.py` - deterministic, read-only, executes no candidate code.

## Modes

- `--bundle-shape-only` - validate the bundle contract and scenario.yaml metadata.
- (default) - validate the completed `candidate/product-brief.md` against the scope-boundary oracle.
- `--changed-path PATH` (repeatable) - assert only the allowed change surface was touched.

## Four-probe validation

1. Reference PASS: copy `oracle/reference/product-brief.md` over the candidate -> PASS.
2. Vacuous FAIL: a brief with the section headers but no real in-scope items -> FAIL on missing groups.
3. Decoy FAIL: a scope-inflated brief that pulls XLSX/PDF and scheduled email export into `## In Scope`
   -> FAIL on the enforced forbidden-in-scope penalty.
4. Near-peer separation: the intake dangles tempting adjacent asks; holding the boundary vs inflating it
   is the discriminator, enforced by the forbidden-in-scope penalty and the mandatory parked-items check.
