# Task

You are the acting `R25 $qa-engineer` for a bounded verification pass on an implementation change
to `status_snapshot.py`.

Edit only `candidate/qa-verdict.md`.

## Acceptance criteria

- `AC1` JSON mode returns a summary that includes `status`, `generated_at`, and `items`.
- `AC2` `--dry-run` prints the planned summary and does not create `status.snapshot.json`.
- `AC3` Nearby smoke coverage proves the legacy `--text-summary` path still works after the patch.
- `AC4` Basic performance smoke stays under `2.0s` on the `500-item` fixture.

## Required QA behavior

- map every acceptance criterion to evidence or an explicit gap
- cite the immutable evidence files that support each conclusion
- classify any observed defect using QA language such as `regression`, `contract-change`, or
  `test-rot` when applicable
- report nearby smoke coverage separately from the primary acceptance mapping
- include the bug-registry expectation if the verdict is `REVISE` or `BLOCKED`
- end with one explicit gate decision: `PASS`, `REVISE`, or `BLOCKED`

Do not patch the implementation, redesign the tool, or drift into architecture or transport
analysis.
