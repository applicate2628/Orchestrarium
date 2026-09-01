# Pre-merge Findings Review

Review the supplied patch facts and report structured findings in four areas: `correctness`,
`reliability`, `performance`, and `security`. Each finding carries a candidate-local ID, repository
path, symbol, and severity. Bind evidence claims `EC1` and `EC2` to source IDs, identify known
non-findings, report reviewed paths, and decide actions `A1` and `A2`.

Stable evidence IDs are `DIFF-1`, `TEST-2`, and `TRACE-3`. The patch touches `src/cache.py`,
`src/worker.py`, `src/query.py`, and `src/auth.py`. `DECOY-LOG` and `DECOY-TIMEOUT` are explicit
non-findings. Structured location, severity, evidence, scope, and action fields are the scored
commitments.
