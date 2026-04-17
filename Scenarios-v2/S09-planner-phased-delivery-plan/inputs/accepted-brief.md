# Accepted Brief

## Problem

The bundle-local status snapshot tool currently emits only a text summary. Downstream verification
and automation need one machine-readable JSON path plus a `--dry-run` preview mode that shows the
would-be JSON payload without writing files.

## Admitted scope

The delivery stays additive and bounded to the existing tool owner seam. The expected delivery
surface is:

- `tools/status_snapshot.py`
- `tests/test_status_snapshot.py`
- `docs/cli/status-snapshot.md` once behavior is stable

## Requirements

1. Preserve the existing `--text-summary` path.
2. Add a machine-readable JSON output path that writes `status.snapshot.json` for real runs.
3. Add `--dry-run` preview behavior with no file writes.
4. Keep the change inside the current tool and its direct tests rather than widening into runners,
   result tables, or archive surfaces.
5. Sequence the work so downstream QA can verify each behavior without reopening design.

## Success read

The accepted outcome is a bounded multi-phase plan that an implementer can execute without adding a
new CLI entrypoint, redoing research, or touching protected benchmark surfaces.
