# Repo Context

`status_snapshot.py` is a bundle-local helper used by fixture authors to summarize scenario health
before publication-time checks run.

## Ownership notes

- the tool owns snapshot creation for local verification artifacts
- callers still rely on the existing `--text-summary` mode for human-readable smoke output
- JSON mode is additive, but it shares the same code path and output selection logic as the legacy
  text mode

## QA-relevant nearby surfaces

- `--text-summary` is the nearest must-not-break surface because the new JSON and dry-run flags
  branch from the same summary-rendering path
- `status.snapshot.json` creation is contract-sensitive because unexpected writes pollute follow-up
  checks and cached fixture outputs
- no architecture or transport behavior is under review in this scenario
