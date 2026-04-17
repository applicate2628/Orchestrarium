# Expected Package Read

The expected package defines a constraint envelope rather than a repair plan.

## Required disposition

- cite `E1` through `E5`
- state the explicit budgets `B1` through `B5` from the admitted envelope
- identify hash-manifest build as the dominant CPU bottleneck
- identify late archive buffering and retained staging state as the memory bottleneck
- separate cold-run and warm-run measurement instead of collapsing them into one headline number
- preserve deterministic replay, redaction fidelity, and full packet coverage as boundaries
- end in `REVISE` because the observed baseline misses the admitted latency and memory budgets

## Role-correct read

A passing answer behaves like a performance engineer:

- it frames bottlenecks and measurement before recommending implementation changes
- it names budget pressure quantitatively
- it states what later implementation work is forbidden to trade away
- it avoids reviewer severity language and avoids rollout, rollback, or incident policy
