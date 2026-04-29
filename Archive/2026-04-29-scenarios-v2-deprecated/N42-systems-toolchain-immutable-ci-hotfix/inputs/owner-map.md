# Owner Map

| Surface | Owner | Boundary |
|---|---|---|
| channel and env-root resolution | `stagegate.config` / `stagegate.paths` | choose and normalize one staging root |
| fingerprint semantics | `stagegate.fingerprint` | derive portable cache identity |
| dependency ordering | `stagegate.planner` | produce runnable staging order |
| lease lifecycle and ledger | `stagegate.executor` / `stagegate.lease` | acquire, release, and report every decision |
| summary output | `stagegate.report` | expose source trace and decisions |
