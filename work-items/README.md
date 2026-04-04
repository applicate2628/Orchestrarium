# Repository Task Memory

`work-items/` is the canonical tracked task-memory root for this repository.

Use it to keep admitted work durable across interruptions, context loss, and session boundaries.
Stable repository-wide methodology stays in [`references/`](../references/); item-specific execution memory lives here.
Publication safety for all tracked content lives in [`references/repository-publication-safety.md`](../references/repository-publication-safety.md).

## Layout

- `index.md`: entry point for active and archived work items
- `active/<date>-<slug>/`: one folder per active admitted item
- `archive/<date>-<slug>/`: completed, superseded, or cancelled items
- `templates/work-item/`: starter files for mandatory item artifacts

## Minimum rule

For any non-trivial work routed through `$lead`, the active item folder must contain:

- `roadmap.md`
- `brief.md`
- `status.md`

Before implementation or review starts, the same item must also contain:

- `plan.md`

Before an item moves to `archive/`, it must also contain:

- `closure.md`

Optional artifacts live beside them as needed:

- `research.md`
- `design.md` or `adr.md`
- `constraints/*.md`
- `notes.md` or `notes/*.md`
- `reports/*.md`

## Public-git safety

- `work-items/` is tracked repository documentation, not a scratchpad.
- Do not place secrets, tokens, credentials, customer data, private identifiers, raw logs, full command transcripts, or machine-specific absolute paths here.
- Redact or generalize operational details when a summary is enough for traceability.
- Keep local-only raw material in ignored scratch space, such as `/.scratch/`, not in tracked work-item artifacts.

## Legacy files

The older ignored `.plans/` directory is legacy local history from the earlier plan-dump layout.
Keep it only as local scratch or traceability material; it is not the canonical tracked source of truth for new items.

Completed item folders should preserve their final `closure.md` when they move to `archive/`.

See [`references/repository-task-memory.md`](../references/repository-task-memory.md) for the full policy.
