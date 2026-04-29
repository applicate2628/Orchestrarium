# Measurement Ledger

| Option | Latency p95 | Memory | False-negative risk | Source trace | Current status |
|---|---:|---:|---:|---|---|
| `Option A - linear exact ledger scan` | `280ms` | `64MB` | `0` | `100%` | fails latency |
| `Option B - probabilistic sketch gate` | `45ms` | `22MB` | `1.8%` | `sampled only` | fails rollback safety and source trace |
| `Option C - keyed index plus exact ledger replay` | `118ms` | `164MB` | `0` | `100%` | satisfies all hard limits |
