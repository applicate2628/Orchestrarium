# Build-break packet

Platform: Windows
Shell: PowerShell

## Symptoms

- `npm run bench:report` fails only on fresh worktrees
- repeated local reruns sometimes pass after a manual shell restart
- CI fails deterministically

## Logs

```text
> node scripts/render-matrix.mjs
Error: ENOENT: no such file or directory, open '.scratch/generated/provider-order.json'
    at Object.openSync (node:fs:596:3)
    ...
Warning: benchmark cache root not initialized
Info: using default config
```

## Notes

- `.scratch/generated/` is created by a previous step on developer machines
- CI starts from a clean checkout
- the failing script assumes the file already exists
