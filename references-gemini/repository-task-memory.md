# Repository Task Memory

This repository uses durable repo-local artifacts, not chat memory, as the source of truth for important in-flight work.

Tracked task memory is optional and repository-defined. When the repository chooses to use it, the task-memory directory, recovery entry point, active-item directory, and archive location are all configured by the repository.

`references-gemini/` is the canonical home for stable repository-wide Gemini-side governance and methodology references in this standalone branch. `docs/agents-mode-reference.md` is the canonical operator reference for the optional `.gemini/.agents-mode.yaml` overlay. When enabled, the configured task-memory directory is still the home for item-specific execution memory.

## Mandatory artifact set

For any non-trivial work routed through `$lead`, the item folder should contain these artifacts:

| Artifact | Required when | Content owner | Purpose |
|---|---|---|---|
| `roadmap.md` | before non-trivial delivery work starts | `$product-manager`, or `$lead` when recording a direct human admission source | why the item exists, what outcome is admitted, what is explicitly out of scope |
| `brief.md` | before non-trivial delivery work starts | `$lead` | bounded source of truth for scope, stage, risks, owners, and must-not-break surfaces |
| `status.md` | before non-trivial delivery work starts | `$lead` | interruption-safe recovery log with current state and next action |
| `plan.md` | before implementation or review starts | `$planner` | approved phase plan and execution checklist |
| `closure.md` | before moving to archive | `$lead` | final record of outcome, residual risk, and archive location |

Additional artifacts are required when the workflow calls for them:

- `research.md`
- `design.md` or `adr.md`
- `constraints/*.md`
- `notes.md` or `notes/*.md`
- `reports/*.md`

## Enforcement and recovery

- `$lead` must not continue non-trivial delivery work without the stage-required artifacts when tracked task memory is enabled.
- `$lead` must not start implementation or independent review without the required upstream accepted artifacts.
- After every accepted artifact, interruption, or material route change, `$lead` updates `status.md` in the configured recovery location.
- On resume after interruption or context loss, start at the repository-defined recovery entry point, then open the item's `status.md`, then `brief.md`.
- If the required task-memory artifacts for the configured workflow are missing or stale, stop and restore them before continuing delivery.

## Public-git safety

- The configured tracked task-memory directory, when used, is tracked repository documentation and must be safe for publication.
- The repo-wide policy for all tracked content lives in [repository-publication-safety.md](repository-publication-safety.md).
- Do not place secrets, tokens, credentials, customer data, private identifiers, raw logs, full command transcripts, or machine-specific absolute paths into tracked task-memory artifacts.
