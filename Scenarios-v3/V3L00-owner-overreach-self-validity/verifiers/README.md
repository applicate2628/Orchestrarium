# Verifiers

`check_owner_overreach.py` — deterministic structured-field scorer for `candidate/answer.json`.

| Mode | Command |
|---|---|
| bundle shape | `python check_owner_overreach.py --bundle-shape-only` |
| completed candidate (default) | `python check_owner_overreach.py` |
| reference / probe candidate | `python check_owner_overreach.py --candidate-root <dir-containing-answer.json>` |

The verifier only **reads** `candidate/answer.json`; it never executes candidate code, so it needs no
oracle-free exec root. Under the isolated harness it runs from the pristine `score/` bundle and reads
the imported candidate output overlaid at `score/candidate/answer.json` (the default candidate root),
which is why no `BENCH_EXEC_ROOT` handling is required here.

Return codes: `0` PASS · `1` scoreable FAIL · `2` schema-invalid.
