# Billing-v2 Delivery Order

## Delivery Order

The single linear delivery order under the tie-break: ascending slug order among ready items is:

1. a-schema
2. b-api
3. d-auth
4. c-cache
5. e-ui
6. f-tests
7. g-docs
8. h-rollout

first ready item: a-schema

## Derived Dependencies

Constraint C1 in `inputs/constraints.md` adds an edge that is not written in any `depends_on` list, so
the explicit Depends-on edges alone are not sufficient:

- Derived dependency: c-cache depends on d-auth (the cache warmer calls the authenticated rate-card
  endpoint, so the auth/token flow must land first).

Without this derived edge, c-cache would be placed before d-auth (both become ready after b-api, and
c-cache sorts first). With it, d-auth precedes c-cache. No other edges are derivable, and there are no
cycles.

## Critical Path And Readiness

critical path length: 5 (for example a-schema -> d-auth -> c-cache -> f-tests -> h-rollout).

| Step | Item | Ready set |
|---|---|---|
| 0 | a-schema | a-schema |
| 1 | b-api | b-api, d-auth |
| 2 | d-auth | d-auth |
| 3 | c-cache | c-cache, e-ui |
| 4 | e-ui | e-ui |
| 5 | f-tests | f-tests, g-docs |
| 6 | g-docs | g-docs |
| 7 | h-rollout | h-rollout |

## Gate Decision

PASS - the order respects every explicit edge plus the derived c-cache-after-d-auth edge, uses the
ascending-slug tie-break at each step, and places the sole leaf (h-rollout) last.
