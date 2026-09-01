# Capacity and Stability Calculation

Report values for stable IDs `N1..N5`, preserving the units defined below. Also identify invariant IDs
and decide falsification cases `F1` and `F2`. Use `output-schema.json`; narrative derivation is free
text and is not scored.

| ID | Quantity | Unit |
|---|---|---|
| `N1` | batch latency from three 4 ms serial stages | `ms` |
| `N2` | failure ratio for 1 failure in 8 attempts | `ratio` |
| `N3` | memory for four 16 MiB shards | `MiB` |
| `N4` | recovery deadline after seven 0.5 s steps | `s` |
| `N5` | target success percentage | `percent` |

Invariant candidates are `bounded-memory`, `finite-input`, `stable-order`, and `unit-preserving`.
For `F1`, a non-finite input must be rejected. For `F2`, changing shard order must not change the
exact integer total.
