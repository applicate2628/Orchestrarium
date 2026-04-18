# Executed Checks

Targeted checks were run against the current packet state.

## Failing targeted checks

- `pytest tests/test_status_snapshot_cli.py::test_dry_run_skips_run_marker`
  - status: `FAIL`
  - observed: `.status-cache/last-run.json` exists after `snapshot-cli --dry-run`
- `pytest tests/test_report_formatter.py::test_footer_uses_visible_job_count_when_only_failed`
  - status: `FAIL`
  - observed: expected `3 visible jobs`; got `12 total jobs shown in failure view`

## Passing nearby checks

- `pytest tests/test_status_snapshot_cli.py::test_default_text_output_snapshot`
  - status: `PASS`
- `pytest tests/test_filters.py::test_include_paused_filter_preserved`
  - status: `PASS`

## Pre-existing noise

- `pytest tests/test_windows_clock.py::test_windows_timezone_stamp`
  - status: `FLAKY`
  - note: known intermittent Windows runner issue from earlier packets; no new evidence ties it to
    the current change set
