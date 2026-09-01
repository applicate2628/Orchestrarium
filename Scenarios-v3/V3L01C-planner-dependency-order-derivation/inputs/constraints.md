# Accepted Constraints (read carefully)

These constraints are accepted and binding. Some of them ADD dependency edges that are NOT written
in the `depends_on` lists in `workitems.json`. You must derive those edges from the prose below and
fold them into the ordering. The explicit `depends_on` edges alone are not sufficient.

## Ordering conventions

- The delivery order is a single linear sequence (one item per step).
- When more than one item is ready (all its dependencies already placed), take them in ascending slug
  order (the tie-break rule).

## Binding constraint C1 (adds an edge)

The rate-card cache warmer (`c-cache`) warms itself by calling the AUTHENTICATED rate-card endpoint.
It cannot run until the billing auth and token flow (`d-auth`) is in place. Therefore `d-auth` must
land before `c-cache`, even though `c-cache`'s written `depends_on` only lists `b-api`.

## Binding constraint C2 (context, no new edge)

`h-rollout` is the only item that ships to production; everything else is internal. This does not add
an edge beyond the ones already present, but note that `h-rollout` is the sole leaf (nothing depends
on it).

## Non-authority

- There are no hidden cycles. If your ordering cannot place every item, re-check your derived edges.
- Do not invent dependencies that are neither written nor derivable from a binding constraint above.
