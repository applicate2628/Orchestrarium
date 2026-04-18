# Recent Changes Packet

## Change 1: unify dry-run and live-run setup

- file: `inputs/review-target/src/status_snapshot_cli.py`
- intent: move report collection and run-marker setup into one shared path before output handling
- risk note: dry-run behavior must remain non-mutating

## Change 2: simplify failure-view footer wording

- file: `inputs/review-target/src/report_formatter.py`
- intent: reuse one footer helper for the default and `--only-failed` views
- risk note: the failure-only footer still needs to describe the visible failed-job subset

## Change 3: simplify alert digest key inputs

- file: `inputs/review-target/src/alert_digest.py`
- intent: make repeated `ops-summary` digests easier to reason about from the generated summary
- risk note: dedupe must still suppress duplicates on reruns of the same summary

## Context note

The packet is intentionally mixed: it contains concrete failures, one operator report, and a small
amount of known pre-existing noise. The triage report should prioritize the likely regressions, not
rewrite the implementation.
