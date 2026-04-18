# Expected Regressions

The seeded triage report for `N04` should return `REVISE` with these likely regressions, in
priority order.

## 1. Blocking: dry-run still mutates state

- anchor file: `inputs/review-target/src/status_snapshot_cli.py`
- supporting references:
  - `inputs/accepted-triage-boundary.md`
  - `inputs/executed-checks.md`
  - `inputs/smoke-results.md`
- reason: `persist_run_marker` runs before the `dry_run` early return, so dry-run still writes
  `.status-cache/last-run.json`

## 2. Major: failure-view footer reports the total set instead of the visible failed set

- anchor file: `inputs/review-target/src/report_formatter.py`
- supporting references:
  - `inputs/executed-checks.md`
  - `inputs/smoke-results.md`
- reason: `build_footer` formats the `--only-failed` footer from `len(all_jobs)` even when only the
  visible failed subset should be described

## 3. Major: duplicate `ops-summary` reruns escape digest dedupe

- anchor file: `inputs/review-target/src/alert_digest.py`
- supporting references:
  - `inputs/operator-signals.md`
  - `inputs/accepted-triage-boundary.md`
- reason: the digest key includes `generated_at_minute`, so the same summary rerun one minute later
  gets a new digest even on the same channel

## Stable and deprioritized points

- default text output and the `include_paused` filter remain stable nearby surfaces
- the Windows timezone flake and docs lint warning stay deprioritized noise

## Expected gate

`REVISE`
