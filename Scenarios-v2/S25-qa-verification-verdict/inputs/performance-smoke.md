# Performance Smoke

## Budget

- target: under `2.0s` for the `500-item` fixture on the bundle-local smoke machine

## Result

- command: `python tools/status_snapshot.py fixtures/500-items.json --json`
- runs: `3`
- observed times: `1.39s`, `1.41s`, `1.43s`
- average: `1.41s`
- verdict: `PASS`

## Note

This scenario expects only basic performance smoke evidence. It does not require deeper bottleneck
analysis or a separate performance-review lane.
