# V3L01C - Planner Hidden Dependency-Ordering Derivation

Target line: `L01` (planning). One of the three A9 sub-scenarios in build-plan F5 that repair the L01
lane read (analyst, product-analyst, planner).

The candidate derives the single linear delivery order for eight work items and certifies it in a
machine-checked witness. The explicit `depends_on` edges are not sufficient: constraint C1 in
`inputs/constraints.md` ADDS a dependency edge (c-cache depends on d-auth) that must be derived from
prose. A hidden-derivation oracle re-derives the correct order (Kahn's algorithm, ascending-slug
tie-break) from the explicit plus derived edges; there is no answer key to copy.

## Why this separates near-peer strong planners (not merely hard)

The dependency graph is small; the discriminator is not graph size but whether the model reads the
prose constraint and derives the edge it implies. A model that topologically sorts only the explicit
edges places c-cache before d-auth (both become ready after b-api, and c-cache sorts first). The
prose-derived edge d-auth -> c-cache flips those two positions. Two strong planners that both sort
correctly diverge only on the derivation.

## Shared design with S09 (R4b), disjoint files

This root implements the same hidden dependency-ordering derivation mechanism that build-plan R4(b)
adds to S09 - one design, two consumers - but is a self-contained Scenarios-v3 root and does not touch
S09 or any other agent's files.

## Terms and Abbreviations

- `topological order` - a linear order respecting all dependency edges.
- `tie-break` - among items that are simultaneously ready, take ascending slug order.
- `critical path length` - the number of items on the longest dependency chain.
- `L01` - the planning routing line of the RF12 scorecard.
