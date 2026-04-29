# Task

Repair the patch-flow helpers so the worker can complete a multi-step owner patch without drifting.

The solution must:

- choose the candidate inside `ownerScope`
- append the next patch step instead of replacing prior steps
- preserve the supplied verification commands
- leave decoys and orchestration code unchanged
