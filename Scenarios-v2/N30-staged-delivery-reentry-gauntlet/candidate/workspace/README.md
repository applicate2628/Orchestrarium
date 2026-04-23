# ReleaseFlow Workspace

ReleaseFlow builds a deploy plan from change events, executes the plan into a ledger, and renders a
release report from durable state.

Known live owners:

- profile precedence: `src/releaseflow/config.py`
- change planning: `src/releaseflow/planner.py`
- resume-safe execution: `src/releaseflow/executor.py`
- reporting source of truth: `src/releaseflow/report.py`

Stale or non-owning references exist under `docs/`, `legacy/`, and `ui/`. They are decoys.
