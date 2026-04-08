# Orchestrarium — Development Repository

The installable skill pack source lives in [`src.codex/`](src.codex/).
See [INSTALL.md](INSTALL.md) for installation instructions.

When working inside this development repository, Codex loads this file as the main conversation context. Use it together with [src.codex/AGENTS.md](src.codex/AGENTS.md), which is the shared source file for the installable pack. The local `.agents/` directory is repo-install output created by the install scripts and is not committed.

## Skill-pack maintenance

When maintaining this skill pack or its source repository:

- keep [`src.codex/AGENTS.md`](src.codex/AGENTS.md) aligned with the installed global policy because it is the shared source file for both
- update `src.codex/skills/<role>/SKILL.md` when a role's contract, artifact, or gate changes
- update `src.codex/skills/<role>/agents/openai.yaml` when trigger or prompt behavior changes
- **MUST** update `references/subagent-operating-model.md` and all `references/` docs when any governance, protocol, gate, or routing semantic changes in the installed pack. Reference docs are the canonical methodology source of truth — they MUST stay aligned with the installed contracts. A governance change that updates `src.codex/` without updating `references/` is incomplete.
- **MUST** update `README.md` and `INSTALL.md` when pack structure, skill count, install targets, or entry points change. A structural change without doc update is incomplete.
- **No mechanical application:** do not copy, move, rename, merge, or propagate content mechanically — between packs, between files, or within the same file — without verifying that the result is correct in the target context. Platform-specific semantics (execution model, parallelism, invocation mechanism, paths, tool capabilities), ownership boundaries, and behavioral implications must be checked before the change lands. "The other pack has it" or "the source file said so" is not sufficient justification. Every change must be independently valid where it lands.
- update `src.codex/skills/lead/operating-model.md` when orchestration or gate semantics change
- update `src.codex/skills/consultant/SKILL.md` when consultant execution policy, toggle logic, or provider paths change
- use `$knowledge-archivist` for repository hygiene, canonical-source alignment, documentation upkeep, and reference maintenance
- route semantic repository control-plane changes prepared by `$knowledge-archivist` through an independent `$architecture-reviewer` gate before completion or publication; hygiene-only edits such as link fixes, formatting, recovery-entry-point sync, archive moves, and non-semantic wording cleanup do not require that extra reviewer

Use these roles first for skill-pack support and maintenance:

- `$lead`: coordinate maintenance work, routing, accepted artifacts, and gate decisions
- `$knowledge-archivist`: docs, references, structure, canonical-source alignment, reports, and hygiene cleanup
- `$toolchain-engineer`: build, packaging, installation, reproducibility, and developer ergonomics for the skill pack
- `$qa-engineer`: verification of maintenance changes against accepted behavior and likely regressions
- `$architecture-reviewer`: maintainability and cohesion gate for structural or semantic control-plane changes to the pack
- `$consultant`: optional independent second opinion for ambiguous workflow or policy changes
- `$product-manager`: roadmap, sequencing, and admission decisions for the skill pack itself

## Repository task memory

Tracked task memory is optional and repository-defined. When the repository uses it, keep admitted work in the configured task-memory directory, resume from the repository-defined recovery entry point, and archive closed items in the configured archive location.

- New admitted work routed through `$lead` belongs in the configured task-memory directory when the repository uses tracked task memory. Completed, cancelled, or superseded work moves to the configured archive location.
- For lead-routed non-trivial work, `roadmap.md`, `brief.md`, and `status.md` are mandatory when tracked task memory is enabled.
- `plan.md` becomes mandatory before implementation or review starts.
- `closure.md` becomes mandatory before moving an item to the configured archive location.
- Missing required upstream artifacts are a hard gate. If the current stage needs `roadmap`, `research`, `design`, `plan`, specialist constraints, or review artifacts and they are missing or stale, stop and restore them or route the item back to the required upstream stage before continuing delivery.
- Ownership: `$product-manager` owns `roadmap.md` when roadmap intake is explicit; if the admission source is a direct human request, `$lead` records that source in `roadmap.md`. `$lead` owns `brief.md` and `status.md`. `$planner` owns `plan.md`. Each specialist owns the artifact for their own lane. `$knowledge-archivist` owns recovery-entry-point, template, and archive hygiene for the configured task-memory locations.
- `notes.md` or `notes/` holds technical notes, implementation discoveries, and follow-ups. Accepted long-lived decisions belong in `design.md` or `adr.md`, not only in notes.
- `closure.md` holds the final closeout record before archive move; `status.md` stays the live recovery log in the configured recovery location.
- After interruption or context loss, resume from the repository-defined recovery entry point, then the item's `status.md`, then `brief.md`. If the required docs are missing or stale, stop and restore task memory before continuing delivery.
- The older ignored `.plans/` directory is legacy local history only. Do not treat it as the canonical tracked source of truth for new work items.

## Repository publication safety

- [references/repository-publication-safety.md](references/repository-publication-safety.md) is the repo-wide source of truth for what may be committed to tracked git.
- Root `.gitignore` defines the local-only scratch boundary at `/.scratch/`; keep raw logs, transcripts, temp outputs, and pre-redaction material there.
- Never hardcode workstation-specific paths, usernames, drive letters, or local tool details into tracked content unless they are intentionally public and synthetic.
- Human review before `git push`, release, or equivalent publication must include a leak-check of staged changes.
- `$knowledge-archivist` is the default human approver at the publication gate. `$lead` remains the default operator of the publication-safety scan and prepares the staged diff for publication, but the publication approver must be a different role than the role that accepted the artifact into the pipeline.
- Relevant reviewers may run the same publication-safety scan for spot checks or gate review, and author self-checks do not replace the required human publication review.
- Only `$security-reviewer` may approve a publication-safety exception. Without that approval, publication is `BLOCKED`.

## Repository periodic controls

- [references/periodic-control-matrix.md](references/periodic-control-matrix.md) is the repo-wide source of truth for periodic controls that complement stage gates.
- Use periodic controls to catch stale items, drift, archive hygiene issues, repo consistency drift, and publication-safety regressions between stage transitions.
- Do not use periodic controls to replace mandatory stage gates, reviewer approvals, or human publication review.

Keep accepted artifacts near the code when the repository is the source of truth: roadmap decision package, canonical brief, status log, research memo, design package, UX design package when used, specialist constraint packages, phase plan, technical notes when needed, and review reports.
