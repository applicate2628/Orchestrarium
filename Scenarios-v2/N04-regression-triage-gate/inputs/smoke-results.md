# Smoke Results

Manual smoke was run with:

`snapshot-cli --dry-run --only-failed`

## Observed regressions

- `.status-cache/last-run.json` is written even though the command is in dry-run mode
- the footer says `12 total jobs shown in failure view` while the rendered table shows `3` failed
  rows

## Stable nearby behavior

- the default text output columns still match the baseline snapshot
- the visible failed rows themselves are the correct three jobs; the count wording is the regressed
  part
