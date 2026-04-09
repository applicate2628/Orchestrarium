# Repository Task Memory

This repository uses durable repo-local artifacts, not session memory, as the source of truth for in-flight work.

Tracked task memory is optional and repository-defined. When the repository chooses to use it, the task-memory directory, recovery entry point, active-item directory, and archive location are all configured by the repository.

The immediate failure mode this policy addresses is simple: a lead can plan well, get interrupted, lose context, and later continue delivery without the roadmap or current plan. That is a process defect, not a memory problem to "work around" in chat.

## Configured location

- The configured task-memory directory, when enabled, is the repository-defined tracked location for active items and execution memory.
- The repository-defined recovery entry point is the first stop after interruption or context loss.
- Active admitted items live in the configured active-item directory.
- Completed, cancelled, or superseded items move to the configured archive location.
- The older ignored `.plans/` directory is legacy local history. Keep it only as scratch or traceability material; do not use it as the canonical tracked source of truth for new items.

`references-codex/` remains the home for stable repository-wide methodology. The configured task-memory directory, when used, is the home for item-specific execution memory.

## Mandatory artifact set

For any non-trivial work routed through `$lead`, the item folder must contain these artifacts:

| Artifact | Required when | Content owner | Purpose |
|---|---|---|---|
| `roadmap.md` | before non-trivial delivery work starts | `$product-manager`, or `$lead` when recording a direct human admission source | why this item exists, what outcome is admitted, what is explicitly out of scope |
| `brief.md` | before non-trivial delivery work starts | `$lead` | bounded source of truth for scope, stage, risks, owners, and must-not-break surfaces |
| `status.md` | before non-trivial delivery work starts | `$lead` | interruption-safe recovery log with frontmatter, current state, active/completed agents, optional `REVISE` loop state, and next action |
| `plan.md` | before implementation or review starts | `$planner` | approved phase plan and execution checklist |
| `closure.md` | before moving to archive | `$lead` | final record of outcome, residual risk, and archive location |

Additional artifacts are required when the workflow calls for them:

- `research.md`
- `design.md` or `adr.md`
- `constraints/*.md`
- `notes.md` or `notes/*.md`
- `reports/*.md`

## Ownership model

- `$product-manager` owns roadmap admission decisions when roadmap work is explicit.
- `$lead` owns the active-item folder, the canonical brief, and the recovery status log.
- `$lead` owns the final closure record before an item moves to archive.
- `$planner` owns the approved phase plan.
- Each specialist role owns the artifact for its own lane.
- `$knowledge-archivist` owns recovery-entry-point, template, cross-link, and archive hygiene, but does not become the content owner for roadmap or delivery decisions.

## Enforcement and recovery

- `$lead` must not continue non-trivial delivery work without `roadmap.md`, `brief.md`, and `status.md` when tracked task memory is enabled.
- `$lead` must not start implementation or independent review without `plan.md` and the required upstream accepted artifacts.
- `$lead` must not move an item to archive without `closure.md` when tracked task memory is enabled.
- If the current stage depends on upstream artifacts such as research, design, specialist constraints, phase plan, or required review reports, those artifacts must exist and be current before work continues.
- After every accepted artifact, interruption, or material route change, `$lead` updates `status.md` in the configured recovery location.
- On resume after interruption or context loss, start at the repository-defined recovery entry point, then open the item's `status.md`, then `brief.md`.
- If the required task-memory artifacts for the configured workflow are missing or stale, stop and restore them before continuing delivery.

## Technical notes and decision history

- Use `notes.md` or `notes/` for technical findings, implementation discoveries, rejected alternatives, migration caveats, and follow-up ideas that should survive the current session.
- Use `status.md` for the rich execution-state template from `skills/lead/subagent-contracts.md`: frontmatter, current state, active/completed agents, optional `REVISE` loop state, and next action.
- Use `closure.md` for the final closeout record before an item leaves `active/`.
- Use `design.md` or `adr.md` for accepted long-lived technical decisions. A note is not a substitute for an accepted decision artifact.

## Public-git safety

- The configured tracked task-memory directory, when used, is tracked repository documentation and must be safe for publication.
- The repo-wide policy for all tracked content lives in [`references-codex/repository-publication-safety.md`](repository-publication-safety.md).
- Do not place secrets, tokens, credentials, customer data, private identifiers, raw logs, full command transcripts, or machine-specific absolute paths into tracked task-memory artifacts.
- Prefer redacted summaries over verbatim operational detail when traceability does not require the raw value.
- Keep local-only scratch notes and raw artifacts outside the configured tracked task-memory directory.

## Minimal operating rule

If the repository uses tracked task memory and the work is important enough to survive an interruption, it is important enough to have a folder in the configured active-item directory.

