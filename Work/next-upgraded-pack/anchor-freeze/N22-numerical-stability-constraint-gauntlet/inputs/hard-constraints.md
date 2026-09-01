# Hard Constraints

| Constraint | Required value |
|---|---:|
| p95 latency gate | `<= 200ms` |
| population variance gate | `<= 4.000000` |
| p95 convention | `rank = ceil(0.95 * n), one-based, no interpolation` |
| latency domain | bounded integer milliseconds, `0..1000` |
| release-gate memory | streaming bounded state; no full sample retention |
| rollback/audit policy | exact p95 and exact merged variance witnesses required |
| stale-source policy | current adversarial cases override old benchmark notes |

Every witness case fails the release gate if either p95 exceeds `200ms` or population variance
exceeds `4.000000`.
