# Orchestrarium Monorepo — Codex Development Overlay

This file is the repo-local Codex development overlay for this monorepo. Codex reads it while working inside this repository; it is not installed into user projects.

The installable Codex pack source lives in [`src.codex/`](src.codex/). The Claude Code pack source lives in `src.claude/`. See [INSTALL.md](INSTALL.md) for installation instructions.

Use this file together with the shared governance in [`shared/AGENTS.shared.md`](shared/AGENTS.shared.md). The local `.agents/` directory is repo-install output created by the install scripts and is not committed.

## Codex-side maintenance

When maintaining the Codex side of this monorepo or shared repo-local governance:

- keep [`shared/AGENTS.shared.md`](shared/AGENTS.shared.md) aligned with the installed global policy because it is the single shared source for both packs
- update `src.codex/skills/<role>/SKILL.md` when a role's contract, artifact, or gate changes
- update `src.codex/skills/<role>/agents/openai.yaml` when trigger or prompt behavior changes
- **MUST** update `shared/references/` for repo-wide design-only methodology and the affected `references-codex/` pack-specific docs when governance, protocol, gate, or routing semantics change in the installed pack. Shared references are the canonical cross-pack methodology source of truth; pack-local references must stay aligned where they carry Codex-specific semantics or stable compatibility pointers. A governance change that updates `src.codex/` without updating the affected shared or pack-local reference docs is incomplete.
- Treat `shared/references/subagent-operating-model.md` as the canonical shared blueprint and `references-codex/subagent-operating-model.md` only as the Codex-specific runtime and repository addendum. Do not reintroduce a second full Codex-side methodology copy in `references-codex/`.
- **MUST** update `README.md` and `INSTALL.md` when pack structure, skill count, install targets, or entry points change. A structural change without doc update is incomplete.
- **MUST** update `RELEASE_NOTES.md` in the same change when staged tracked content changes installed behavior, governance, routing, role contracts, install surface, developer or operator workflow, or other release-relevant user-facing expectations. Keep the log in reverse-chronological `## YYYY-MM-DD` sections: append new explanatory bullets under the current date heading or create today's heading if it is missing, and do not keep a long-lived `## Unreleased` bucket. The release-notes entry must explain the improvement, why it matters, and the affected user or operator workflow, not just list filenames or terse labels. Purely local-only hygiene edits such as formatting, link fixes, report-only churn, scratch cleanup, archive moves, and non-semantic wording cleanup do not require a release-notes entry, but that exemption must be an explicit reviewer determination at publication time rather than an untracked assumption.
- **No mechanical application:** do not copy, move, rename, merge, or propagate content mechanically — between packs, between files, or within the same file — without verifying that the result is correct in the target context. Platform-specific semantics (execution model, parallelism, invocation mechanism, paths, tool capabilities), ownership boundaries, and behavioral implications must be checked before the change lands. "The other pack has it" or "the source file said so" is not sufficient justification. Every change must be independently valid where it lands.
- **Provider/runtime claims:** when documentation or implementation describes provider-native behavior, explicitly distinguish `official provider behavior`, `Orchestrarium repo-local convention`, and `observed installed/runtime behavior`. Use the official provider docs when they exist, and do not present a source-tree pattern or local install convention as if it were guaranteed by the provider itself. For install-contract changes, verify both the authoritative doc and the installed result before calling the behavior established.
- **Repo-local external routing heuristic:** `externalProvider` uses the shared provider universe `auto | codex | claude | gemini`, and `auto` resolves through the active priority profile rather than by host-pack default. Orchestrarium treats `externalPriorityProfile: balanced` as the quiet default profile and recognizes a repo-local `gemini-crosscheck` profile for broader Gemini participation when one independent opinion is not enough. Current repo-local rule: image generation, icon work, decorative visual polish, and other explicitly visual worker or review lanes should prefer Gemini as the external provider when Gemini is installed, and non-visual advisory or review lanes may also bring Gemini into the first requested opinion set when the active priority profile ranks it there. This heuristic applies to `$external-worker` as well as visual review or advisory work and must be documented explicitly wherever provider-routing behavior is summarized.
- **Claude secondary transport:** on provider lines that may route work to Claude, the repo-local secondary transport is `claude-api` when that command is installed. Claude CLI remains the first transport unless the active mode or operator override explicitly requests Claude API first; after the allowed Claude CLI path is exhausted, the runtime must try `claude-api` before declaring Claude unavailable.
- **Cross-pack sync:** when editing shared semantic blocks in `operating-model.md` or `subagent-contracts.md`, consult [`cross-pack-reconciliation.md`](cross-pack-reconciliation.md) to identify and update the matching block in the other pack.
- update `src.codex/skills/lead/operating-model.md` when orchestration or gate semantics change
- update `src.codex/skills/lead/external-dispatch.md` when the agents-mode schema, provider paths, provenance rules, or external role dispatch semantics change
- update `docs/agents-mode-reference.md` and any affected provider help surface when external-role eligibility, unsupported-route policy, or fail-fast external routing semantics change
- update `src.codex/skills/consultant/SKILL.md` when consultant execution policy changes, keeping it aligned with the shared external-dispatch contract instead of duplicating dispatch semantics inline
- use `$knowledge-archivist` for repository hygiene, canonical-source alignment, documentation upkeep, and reference maintenance
- route semantic repository control-plane changes prepared by `$knowledge-archivist` through an independent `$architecture-reviewer` gate before completion or publication; hygiene-only edits such as link fixes, formatting, recovery-entry-point sync, archive moves, and non-semantic wording cleanup do not require that extra reviewer

Use these roles first for skill-pack support and maintenance:

- `$lead`: coordinate maintenance work, routing, accepted artifacts, and gate decisions
- `$knowledge-archivist`: docs, references, structure, canonical-source alignment, reports, and hygiene cleanup
- `$toolchain-engineer`: build, packaging, installation, reproducibility, and developer ergonomics for the skill pack
- `$qa-engineer`: verification of maintenance changes against accepted behavior and likely regressions
- `$architecture-reviewer`: maintainability and cohesion gate for structural or semantic control-plane changes to the pack
- `$external-worker`: cross-provider worker-side adapter for eligible non-owner, non-review roles; preference comes from `.agents/.agents-mode` or explicit user routing
- `$external-reviewer`: cross-provider review and QA adapter for eligible review-side roles; preference comes from `.agents/.agents-mode` or explicit user routing
- `$consultant`: independent advisory second opinion for ambiguous workflow or policy changes; ordinary use is optional, and completed lead-managed batches end with one or more external consultant-checks before closure as required by the active lane policy
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

- [shared/references/repository-publication-safety.md](shared/references/repository-publication-safety.md) is the repo-wide source of truth for what may be committed to tracked git.
- `RELEASE_NOTES.md` is the canonical tracked release log for this repository.
- Root `.gitignore` defines the local-only scratch boundary at `/.scratch/`; keep raw logs, transcripts, temp outputs, and pre-redaction material there.
- Never hardcode workstation-specific paths, usernames, drive letters, or local tool details into tracked content unless they are intentionally public and synthetic.
- Human review before `git push`, release, or equivalent publication must include a leak-check of staged changes.
- Run `bash scripts/check-publication-gate.sh` or `.\scripts\check-publication-gate.ps1` as the repo-local publication gate before publication review; it combines the staged leak scan with the `RELEASE_NOTES.md` requirement for release-relevant tracked changes.
- If staged tracked changes are release-relevant, publication review must confirm that `RELEASE_NOTES.md` is updated in the same change and that the entry explains the change's practical meaning, not just its title. Publication without either the matching explanatory release-notes entry or an explicit reviewer determination that the change is release-notes-exempt is `BLOCKED`.
- `$knowledge-archivist` is the default human approver at the publication gate. `$lead` remains the default operator of the publication-safety scan and prepares the staged diff for publication, but the publication approver must be a different role than the role that accepted the artifact into the pipeline.
- Relevant reviewers may run the same publication-safety scan for spot checks or gate review, and author self-checks do not replace the required human publication review.
- Only `$security-reviewer` may approve a publication-safety exception. Without that approval, publication is `BLOCKED`.

## Repository periodic controls

- `shared/references/subagent-operating-model.md` is the canonical shared blueprint reference for cross-pack orchestration methodology; Codex runtime specifics remain in [references-codex/subagent-operating-model.md](references-codex/subagent-operating-model.md).
- [references-codex/periodic-control-matrix.md](references-codex/periodic-control-matrix.md) is the Codex-side periodic-control reference for this repository.
- `periodic-control-matrix` remains intentionally pack-local for now rather than moving into `shared/references/`, because it still depends on pack/runtime vocabulary, task-memory layout, and runtime-doc links that are not yet expressed as a generic shared skeleton.
- Use periodic controls to catch stale items, drift, archive hygiene issues, repo consistency drift, and publication-safety regressions between stage transitions.
- Do not use periodic controls to replace mandatory stage gates, reviewer approvals, or human publication review.

Keep accepted artifacts near the code when the repository is the source of truth: roadmap decision package, canonical brief, status log, research memo, design package, UX design package when used, specialist constraint packages, phase plan, technical notes when needed, and review reports.
