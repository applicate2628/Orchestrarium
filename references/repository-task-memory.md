# Repository Task Memory

This repository uses durable repo-local artifacts, not session memory, as the source of truth for in-flight work.

The immediate failure mode this policy addresses is simple: a lead can plan well, get interrupted, lose context, and later continue delivery without the roadmap or current plan. That is a process defect, not a memory problem to "work around" in chat.

## Canonical location

- `work-items/` is the canonical tracked task-memory root for this repository.
- `work-items/index.md` is the recovery entry point.
- Active admitted items live in `work-items/active/<date>-<slug>/`.
- Completed, cancelled, or superseded items move to `work-items/archive/<date>-<slug>/`.
- The older ignored `.plans/` directory is legacy local history. Keep it only as scratch or traceability material; do not use it as the canonical tracked source of truth for new items.

`references/` remains the home for stable repository-wide methodology. `work-items/` is the home for item-specific execution memory.

## Mandatory artifact set

For any non-trivial work routed through `$lead`, the item folder must contain these artifacts:

| Artifact | Required when | Content owner | Purpose |
|---|---|---|---|
| `roadmap.md` | before non-trivial delivery work starts | `$product-manager`, or `$lead` when recording a direct human admission source | why this item exists, what outcome is admitted, what is explicitly out of scope |
| `brief.md` | before non-trivial delivery work starts | `$lead` | bounded source of truth for scope, stage, risks, owners, and must-not-break surfaces |
| `status.md` | before non-trivial delivery work starts | `$lead` | interruption-safe recovery log with current stage, last accepted artifact, next action, and blockers |
| `plan.md` | before implementation or review starts | `$planner` | approved phase plan and execution checklist |

Additional artifacts are required when the workflow calls for them:

- `research.md`
- `design.md` or `adr.md`
- `constraints/*.md`
- `notes.md` or `notes/*.md`
- `reports/*.md`

## Ownership model

- `$product-manager` owns roadmap admission decisions when roadmap work is explicit.
- `$lead` owns the active-item folder, the canonical brief, and the recovery status log.
- `$planner` owns the approved phase plan.
- Each specialist role owns the artifact for its own lane.
- `$knowledge-archivist` owns index, template, cross-link, and archive hygiene, but does not become the content owner for roadmap or delivery decisions.

## Enforcement and recovery

- `$lead` must not continue non-trivial delivery work without `roadmap.md`, `brief.md`, and `status.md`.
- `$lead` must not start implementation or independent review without `plan.md` and the required upstream accepted artifacts.
- If the current stage depends on upstream artifacts such as research, design, specialist constraints, phase plan, or required review reports, those artifacts must exist and be current before work continues.
- After every accepted artifact, interruption, or material route change, `$lead` updates `status.md`.
- On resume after interruption or context loss, start at `work-items/index.md`, then open the item's `status.md`, then `brief.md`.
- If the required task-memory artifacts are missing or stale, stop and restore them before continuing delivery.

## Technical notes and decision history

- Use `notes.md` or `notes/` for technical findings, implementation discoveries, rejected alternatives, migration caveats, and follow-up ideas that should survive the current session.
- Use `status.md` for chronological execution state and handoff notes.
- Use `design.md` or `adr.md` for accepted long-lived technical decisions. A note is not a substitute for an accepted decision artifact.

## Public-git safety

- `work-items/` is tracked repository documentation and must be safe for publication.
- Do not place secrets, tokens, credentials, customer data, private identifiers, raw logs, full command transcripts, or machine-specific absolute paths into tracked work-item artifacts.
- Prefer redacted summaries over verbatim operational detail when traceability does not require the raw value.
- Keep local-only scratch notes and raw artifacts outside tracked `work-items/`.

## Minimal operating rule

If the work is important enough to survive an interruption, it is important enough to have a folder in `work-items/active/`.

