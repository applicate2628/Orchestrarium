M04 phased planning packet

Execution question:
- finish the remaining extended tests and run them
- keep the pass bounded to the current `X1..X3` completion task

Required phase order:
1. build the missing fixtures
2. validate `broken/` and `control-pass/` locally
3. run `X1`, `X2`, and `X3` on the new batch
4. refresh results and status surfaces

Boundary rules:
- do not reopen `X5` or `X6` in the same pass
- do not mutate `Archive/`
- do not rerank before evidence exists
