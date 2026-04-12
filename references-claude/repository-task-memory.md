# Repository Task Memory

This repository uses durable repo-local artifacts, not session memory, as the source of truth for in-flight work.

The immediate failure mode this policy addresses is simple: a lead can plan well, get interrupted, lose context, and later continue delivery without the roadmap or current plan. That is a process defect, not a memory problem to "work around" in chat.

## Canonical location

- `work-items/` is the canonical repo-local task-memory root for this repository, but it is intentionally local-only and untracked in git.
- `work-items/index.md` is the recovery entry point.
- Active admitted items live in `work-items/active/<date>-<slug>/`.
- Completed, cancelled, or superseded items move to `work-items/archive/<date>-<slug>/`.
- `.reports/YYYY-MM/` stores session logs — brief summaries of what happened in a session, not copies of canonical artifacts. Named `report(<role>)-YYYY-MM-DD_HH-MM_topic.md`.
- `.plans/YYYY-MM/` stores plan logs — plan drafts and iterations. Named `plan(<role>)-YYYY-MM-DD_HH-MM_topic.md`.
- `.reports/` and `.plans/` are traceability logs, not canonical tracked sources. `work-items/` remains the local recovery source of truth for item-specific execution memory on the operator machine.

`shared/references/` is the canonical home for stable repository-wide design methodology. `references-claude/` keeps Claude-specific reference material plus compatibility pointers. `work-items/` is the home for local item-specific execution memory. `.reports/` and `.plans/` are session-level audit trails.
`docs/agents-mode-reference.md` is the shared operator reference when `.claude/.agents-mode` behavior matters.

## Mandatory artifact set

For any non-trivial work routed through `$lead`, the item folder must contain these artifacts:

| Artifact | Required when | Content owner | Purpose |
|---|---|---|---|
| `roadmap.md` | before non-trivial delivery work starts | `$product-manager`, or the user directly | why this item exists, what outcome is admitted, what is explicitly out of scope. Lead cannot generate a roadmap item on its own authority. |
| `brief.md` | before non-trivial delivery work starts | `$lead` | bounded source of truth for scope, stage, risks, owners, and must-not-break surfaces |
| `status.md` | before non-trivial delivery work starts | `$lead` | interruption-safe recovery log with current stage, last accepted artifact, next action, and blockers |
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
- `$knowledge-archivist` owns index, template, cross-link, and archive hygiene, but does not become the content owner for roadmap or delivery decisions.

## Enforcement and recovery

- `$lead` must not continue non-trivial delivery work without `roadmap.md`, `brief.md`, and `status.md`.
- `$lead` must not start implementation or independent review without `plan.md` and the required upstream accepted artifacts.
- `$lead` must not move an item to archive without `closure.md`.
- If the current stage depends on upstream artifacts such as research, design, specialist constraints, phase plan, or required review reports, those artifacts must exist and be current before work continues.
- After every accepted artifact, interruption, or material route change, `$lead` updates `status.md`.
- On resume after interruption or context loss, start at `work-items/index.md`, then open the item's `status.md`, then `brief.md`.
- If the required task-memory artifacts are missing or stale, stop and restore them before continuing delivery.

## Task-memory linkage

- Each work-item in `work-items/` corresponds to an entry in the team task index managed by the operating environment.
- The work-item `status.md` SHOULD include a `Task ID` field when the environment supports cross-linking.
- When a work-item is archived, the corresponding task is marked `completed`/`cancelled` with an archive note.
- The `work-items/index.md` file is the portable, repo-guaranteed entry point for task recovery — it must always be current.
- This linkage is maintained by `$lead` at each stage transition and verified by `$knowledge-archivist` during session-start audits.

## Technical notes and decision history

- Use `notes.md` or `notes/` for technical findings, implementation discoveries, rejected alternatives, migration caveats, and follow-up ideas that should survive the current session.
- Use `status.md` for chronological execution state and handoff notes.
- Use `closure.md` for the final closeout record before an item leaves `active/`.
- Use `design.md` or `adr.md` for accepted long-lived technical decisions. A note is not a substitute for an accepted decision artifact.

## Public-git safety

- `work-items/` is local-only task memory and must stay out of tracked git.
- The repo-wide policy for all tracked content lives in [`shared/references/repository-publication-safety.md`](../shared/references/repository-publication-safety.md).
- Do not force-add or stage `work-items/` content for publication. Promote accepted conclusions into tracked canonical docs instead.
- Keep secrets, tokens, credentials, customer data, private identifiers, raw logs, full command transcripts, and machine-specific absolute paths out of any distilled tracked artifact derived from local task memory.
- Prefer redacted summaries over verbatim operational detail when traceability does not require the raw value.
- Keep scratch notes, raw artifacts, and evolving recovery state inside local-only `work-items/`, `.reports/`, `.plans/`, or `/.scratch/` instead of tracked docs.

## Minimal operating rule

If the work is important enough to survive an interruption, it is important enough to have a folder in `work-items/active/`.
