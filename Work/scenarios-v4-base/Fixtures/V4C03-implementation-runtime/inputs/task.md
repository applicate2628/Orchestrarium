# Retry-safe Service Change

Report the observed outcomes of cases `R1..R5`, the preserved public routes and emitted events, the
changed paths, and test case `T1`. Use `output-schema.json`. The root measures the target program's
observable contract; provider duration and output size are not inputs.

| ID | Observable case |
|---|---|
| `R1` | first create request |
| `R2` | duplicate idempotency key with conflicting payload |
| `R3` | accepted asynchronous retry |
| `R4` | replay of the same successful key |
| `R5` | exhausted dependency retries |
| `T1` | focused regression suite |

The public surface names available to report are `/jobs`, `/jobs/{id}`, `job.accepted`, and
`job.completed`. Candidate changed paths are repository-relative strings.
