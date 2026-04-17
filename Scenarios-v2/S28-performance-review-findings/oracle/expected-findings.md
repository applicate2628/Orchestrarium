# Expected Findings

- `[high]` full rerender and full-list sort on every refresh
- `[medium]` repeated `JSON.stringify` in the hot path
- `[medium]` unbounded metric-history growth by appending full snapshots
