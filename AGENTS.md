# Orchestrarium Monorepo — Codex Development Overlay

This file is the repo-local Codex development overlay for this monorepo. Codex reads it while working inside this repository; it is not installed into user projects.

The installable Codex pack source lives in [`src.codex/`](src.codex/). The Claude Code pack source lives in `src.claude/`. See [INSTALL.md](INSTALL.md) for installation instructions.

Use this file together with the shared governance in [`shared/AGENTS.shared.md`](shared/AGENTS.shared.md). The local `.agents/` directory is repo-install output created by the install scripts and is not committed.

When working inside this monorepo itself, do not assume that a missing local `.agents/` tree means the Codex install is broken. Maintainers may intentionally rely on the global Codex install under `~/.codex/` while editing the installer source. If `.agents/.agents-mode.yaml` is absent here, ordinary reads should fall back to `~/.codex/.agents-mode.yaml` before treating the state as missing. Create a repo-local install only when the user explicitly wants one, and explain that it should be created by the installer rather than ad hoc file creation.

## Codex-side maintenance

When maintaining the Codex side of this monorepo or shared repo-local governance:

- keep [`shared/AGENTS.shared.md`](shared/AGENTS.shared.md) aligned with the installed global policy because it is the single shared source for both packs
- update `src.codex/skills/<role>/SKILL.md` when a role's contract, artifact, or gate changes
- update `src.codex/skills/<role>/agents/openai.yaml` when trigger or prompt behavior changes
- **MUST** update `shared/references/` for repo-wide design-only methodology and the affected `references-codex/` pack-specific docs when governance, protocol, gate, or routing semantics change in the installed pack. Shared references are the canonical cross-pack methodology source of truth; pack-local references must stay aligned where they carry Codex-specific semantics or stable compatibility pointers. A governance change that updates `src.codex/` without updating the affected shared or pack-local reference docs is incomplete.
- Treat `shared/references/subagent-operating-model.md` as the canonical shared blueprint and `references-codex/subagent-operating-model.md` only as the Codex-specific runtime and repository addendum. Do not reintroduce a second full Codex-side methodology copy in `references-codex/`.
- **MUST** update `README.md` and `INSTALL.md` when pack structure, skill count, install targets, or entry points change. A structural change without doc update is incomplete.
- **MUST** update `RELEASE_NOTES.md` in the same change when staged tracked content changes installed behavior, governance, routing, role contracts, install surface, developer or operator workflow, or other release-relevant user-facing expectations. Keep the log in reverse-chronological `## YYYY-MM-DD` sections: append new explanatory bullets under the current date heading or create today's heading if it is missing, and do not keep a long-lived `## Unreleased` bucket. The release-notes entry must explain the improvement, why it matters, and the affected user or operator workflow, not just list filenames or terse labels. Purely local-only hygiene edits such as formatting, link fixes, report-only churn, scratch cleanup, archive moves, and non-semantic wording cleanup do not require a release-notes entry, but that exemption must be an explicit reviewer determination at publication time rather than an untracked assumption.
- When updating human-facing repo documentation, apply the shared documentation terminology discipline: end terminology-heavy documents with `## Terms and Abbreviations` or a localized equivalent, and explain unclear terms, abbreviations, provider names, role names, workflow labels, and mixed-language terms there.
- **No mechanical application:** do not copy, move, rename, merge, or propagate content mechanically — between packs, between files, or within the same file — without verifying that the result is correct in the target context. Platform-specific semantics (execution model, parallelism, invocation mechanism, paths, tool capabilities), ownership boundaries, and behavioral implications must be checked before the change lands. "The other pack has it" or "the source file said so" is not sufficient justification. Every change must be independently valid where it lands.
- **Provider/runtime claims:** when documentation or implementation describes provider-native behavior, explicitly distinguish `official provider behavior`, `Orchestrarium repo-local convention`, and `observed installed/runtime behavior`. Use the official provider docs when they exist, and do not present a source-tree pattern or local install convention as if it were guaranteed by the provider itself. For install-contract changes, verify both the authoritative doc and the installed result before calling the behavior established.
- **Repo-local external routing heuristic:** `externalProvider: auto` uses only production-recommended provider profiles, currently `codex | claude`, and resolves through the active priority profile rather than by host-pack default. Orchestrarium treats `externalPriorityProfile: balanced` as the quiet default production profile. Gemini and Qwen are classified here as `WEAK MODEL / NOT RECOMMENDED`; keep both out of production `auto` routing and use explicit `externalProvider: gemini` or `externalProvider: qwen` only as example or compatibility demonstration paths unless a later accepted design promotes either provider into production routing.
- **Claude secret advisory/review candidate:** the installed secret-backed wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1` runs plain `claude` with `ANTHROPIC_*` loaded from `SECRET.md`, but it is weaker than the primary Claude CLI path. Treat it as the supplemental `claude-secret` candidate for advisory and review profile orders only, after primary `claude` and `codex`, and independent of the primary `claude` candidate. Mutating implementation, code-generation, file-editing, or publication actions must not use the secret-backed transport; they must use the allowed primary provider path or report the provider unavailable.
- **External CLI prompt delivery:** provider-backed consultant, worker, and reviewer launches that carry a substantive task prompt must use file-based prompt delivery: write the prompt to a temporary prompt file and feed it through the provider's stdin or supported file-input mechanism. Keep argv to launcher flags, model/profile options, and file paths; inline prompt argv is only for tiny smoke checks or a documented provider limitation, and the deviation must be recorded.
- **Cross-pack sync:** when editing shared semantic blocks in `operating-model.md` or `subagent-contracts.md`, consult [`cross-pack-reconciliation.md`](cross-pack-reconciliation.md) to identify and update the matching block in the other pack.
- **Monorepo install choice:** when a skill or repo-local workflow wants Codex runtime state such as `.agents/.agents-mode.yaml` while operating inside this monorepo, use the global install at `~/.codex/` as the default fallback when the local overlay is absent. Create a repo-local install via `scripts/install-codex.sh|ps1` or `install.sh|ps1` only when the user explicitly wants project-local runtime state; do not synthesize `.agents/` by hand inside the monorepo just to satisfy a gate.
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
- `$external-worker`: cross-provider worker-side adapter for eligible non-owner, non-review roles; preference comes from `.agents/.agents-mode.yaml` or explicit user routing
- `$external-reviewer`: cross-provider review and QA adapter for eligible review-side roles; preference comes from `.agents/.agents-mode.yaml` or explicit user routing
- `$consultant`: independent advisory second opinion for ambiguous workflow or policy changes; ordinary use is optional, any repo-local consultant-check remains advisory-only, and `consultantMode: disabled` waives consultant closeout instead of leaving a hidden blocker
- `$product-manager`: roadmap, sequencing, and admission decisions for the skill pack itself

## Repository task memory

This monorepo keeps `work-items/` as repo-local task memory for interruption recovery, but `work-items/` is intentionally local-only and must stay out of tracked git.

- `work-items/` remains the repo-local recovery directory for admitted work and archive history on the operator machine, but it is not publication-facing tracked canon for this repository.
- When information from local task memory needs to become tracked source of truth, promote the accepted result into the owning canonical surface such as `docs/`, `shared/references/`, pack references, `README.md`, `INSTALL.md`, or `RELEASE_NOTES.md` instead of committing `work-items/` directly.
- New admitted work routed through `$lead` may still use `work-items/` locally for recovery, resume, and archive hygiene; completed, cancelled, or superseded work stays in the configured local archive location unless a human explicitly asks to publish a distilled artifact elsewhere.

- For lead-routed non-trivial work, `roadmap.md`, `brief.md`, and `status.md` are mandatory when the local task-memory workflow is enabled.
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
- Root `.gitignore` defines the local-only boundary at `/.scratch/`, `/.plans/`, `/.reports/`, and `/work-items/`; keep raw logs, transcripts, temp outputs, and repo-local task-memory artifacts there.
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

## Terms and Abbreviations

- `AGENTS.md`: the Codex-readable governance and instruction file for this repository.
- `AGENTS.shared.md`: the shared governance source merged into installable provider packs.
- `ADR`: Architecture Decision Record, a durable note for an accepted architecture decision.
- `API`: Application Programming Interface, a programmatic contract exposed by a tool, runtime, or service.
- `argv`: the command-line argument vector passed to a process.
- `CLI`: Command-Line Interface, a terminal command surface such as `codex`, `claude`, or `gemini`.
- `Codex`: the OpenAI Codex runtime and provider pack maintained by this repository.
- `Claude Code`: Anthropic's Claude Code runtime and matching provider pack.
- `Gemini`: the Google Gemini runtime/provider family; in this repository it is example-only unless explicitly selected.
- `MCP`: Model Context Protocol, a protocol used to expose tools and resources to agent runtimes.
- `QA`: Quality Assurance, verification work focused on tests, regressions, and acceptance criteria.
- `Qwen`: the Qwen runtime/provider family; in this repository it is example-only unless explicitly selected.
- `RELEASE_NOTES.md`: the tracked release log for release-relevant repository changes.
- `stdin`: standard input, the input stream provided to a process.
- `UI`: User Interface, the visible or interactive surface presented to a user.
- `UX`: User Experience, the user's end-to-end interaction quality and clarity.
- `WEAK MODEL / NOT RECOMMENDED`: the repository's classification for example-only providers that must stay out of production `auto` routing.
- `YAML`: YAML Ain't Markup Language, the structured data format used by files such as `.agents-mode.yaml`.
