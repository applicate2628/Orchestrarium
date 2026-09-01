# Task

You are acting as a planner. Derive the single linear delivery order for the billing-v2 initiative and
certify it in a machine-checked witness.

## Goal

Update these two files:

- `candidate/delivery-order.md`
- `candidate/order-witness.json`

Read BOTH `inputs/workitems.json` (the explicit `depends_on` edges) and `inputs/constraints.md` (binding
constraints, some of which ADD dependency edges not written in any `depends_on` list). Fold the derived
edges into a topological order.

## Required behavior

- Produce one linear order (one item per step). When several items are ready, take them in ascending
  slug order (the tie-break rule).
- Derive every edge implied by a binding constraint. In particular, constraint C1 adds the edge
  `c-cache depends on d-auth`; the explicit `depends_on` edges alone are not sufficient.
- Report the critical path length (the longest dependency chain, counted in items) and the first ready item.
- Do not invent dependencies that are neither written nor derivable from a binding constraint.

## Witness JSON contract

`candidate/order-witness.json` must be valid JSON with this shape:

```json
{
  "tie_break_rule": "ascending slug order among ready items",
  "phase_order": ["a-schema", "b-api", "d-auth", "c-cache", "e-ui", "f-tests", "g-docs", "h-rollout"],
  "first_item": "a-schema",
  "critical_path_length": 5,
  "derived_dependencies": [
    {"item": "c-cache", "depends_on": "d-auth", "source": "constraint C1"}
  ]
}
```

`phase_order` must list every slug exactly once in delivery order. `derived_dependencies` must list every
edge you derived from a binding constraint.

## Disallowed behavior

- Do not order using only the explicit `depends_on` edges.
- Do not place `c-cache` before `d-auth`.
- Do not edit files outside the two allowed candidate files.
