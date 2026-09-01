# Oracle

`dependency-order-contract.json` holds the tie-break rule, the derived edges (the answer to the
derivation), required phrases/sections/tables, and disallowed markers. The correct `phase_order` is NOT
stored: `check_dependency_order.py` re-derives it via Kahn's algorithm with an ascending-slug tie-break
over the union of the explicit `depends_on` edges (from `inputs/workitems.json`) and the derived edges
(from this contract). So a leaked oracle does not hand over the order.

`reference/` holds a passing reference answer for the admission probe and the four-probe. Never staged
to the provider-visible root. The verifier executes no candidate code (read-only), so it needs no
`BENCH_EXEC_ROOT` exec split.

Near-peer separation: a model that topologically sorts only the explicit edges places c-cache before
d-auth (both ready after b-api; c-cache sorts first). The prose-derived edge d-auth -> c-cache flips
them. Two strong models that both sort correctly diverge only on whether they derived the prose
constraint - that is the discriminator, not raw difficulty.
