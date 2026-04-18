# Stable Signals And Known Noise

## Stable nearby surfaces

- `inputs/executed-checks.md` shows `test_default_text_output_snapshot` still `PASS`
- `inputs/executed-checks.md` shows `test_include_paused_filter_preserved` still `PASS`
- the smoke packet confirms the visible failed rows are correct; only the footer count text is
  regressed

## Known pre-existing noise

- `test_windows_timezone_stamp` remains a known intermittent Windows flake with no new packet-local
  evidence
- the branch still carries one docs-only line-length warning from older work; it is not tied to the
  current status-snapshot changes
