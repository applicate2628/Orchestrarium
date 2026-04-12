# Work Items

Recovery entrypoint for tracked task memory in this repository.

## Active items

| Item | Stage | State | Last accepted artifact | Next concrete action |
|---|---|---|---|---|
| [2026-04-11-external-role-priority-switching](active/2026-04-11-external-role-priority-switching/status.md) | `Closeout` | `active / in-progress` | `consultant no-fallback canon cleanup` | Decide commit boundaries for the broader routing and governance batch. |
| [2026-04-11-external-routing-symmetry-revise](active/2026-04-11-external-routing-symmetry-revise/status.md) | `Closeout` | `validation-complete / ready-for-closeout` | `full rewrite plus validation sweep` | Summarize the accepted rewrite and package commits only if requested. |
| [2026-04-12-control-plane-sync-cleanup](active/2026-04-12-control-plane-sync-cleanup/status.md) | `Closeout` | `validation-complete / ready-for-human-review` | `deep brigade-driven truth-sync wave + Codex-first systems/perf lane extension` | Human review the widened dirty batch and package commits only if requested. |

## Layout

- Active items live under [work-items/active](active/).
- Archived items move to `work-items/archive/<date>-<slug>/` when closed.
- Item-local recovery should start from the item's `status.md`, then read `brief.md`, `roadmap.md`, and any accepted downstream artifacts linked from there.
