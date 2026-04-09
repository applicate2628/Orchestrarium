# Orchestrarium Monorepo — Claude Code Development Overlay

This file is the repo-local Claude Code development overlay for this monorepo. Claude Code reads it while working inside this repository; it is not installed into user projects.

## Project policies

- **commit-format**: conventional
- **documentation**: always-update
- **language-style**: english (code, comments, docs), russian OK in user-facing session reports

## Skill development checklist

When adding, renaming, or removing a skill (`src.claude/commands/agents-*.md`):

1. Create/edit the skill file in `src.claude/commands/`
2. Update `src.claude/commands/agents-help.md` — add to the skills table
3. Update `README.md` and `INSTALL.md` if the change affects documented pack structure, counts, install surface, or entry points
4. Update `RELEASE_NOTES.md` if the skill change is release-relevant under repo policy
5. Update `scripts/install-claude.ps1` — update skill count threshold in verification when the expected command count changes
6. Update `scripts/install-claude.sh` — update skill count threshold in verification when the expected command count changes
7. Update `src.claude/agents/scripts/validate-skill-pack.sh` — add the skill to validation only if it is not auto-discovered
8. Run `/agents-validate` to confirm structural integrity
9. Run `scripts/install-claude.ps1 -Global` to install and verify when install behavior or pack structure changed materially

## Role development checklist

When adding or modifying a role (`src.claude/agents/*.md`):

1. Create/edit the role file in `src.claude/agents/`
2. Update `shared/AGENTS.shared.md` `## Role index` — add to the correct category, because the installed Claude pack imports shared governance from `AGENTS.md`
3. If the role participates in external dispatch, update `src.claude/agents/contracts/external-dispatch.md` and the agents-mode schema references that depend on it
4. If the role is a new reviewer or constraint role, check whether templates stay unchanged by design or require an explicit policy exception
5. Run `/agents-validate` to confirm the role is indexed

## Template development checklist

When adding or modifying a team template (`src.claude/agents/team-templates/*.json`):

1. Create/edit the template JSON — must have `requiresLead` and `chain` fields
2. Update `src.claude/CLAUDE.md` `## Delegation rule` — add to the templates table
3. Update `src.claude/agents/contracts/operating-model.md` if routing rules change
4. Run `/agents-validate`

## Contract and governance changes

When modifying `shared/AGENTS.shared.md`, `src.claude/CLAUDE.md`, `operating-model.md`, or `subagent-contracts.md`:

- These are the governance core. Changes propagate to all users on next install.
- State explicitly what behavior changes and what is preserved.
- Keep `shared/AGENTS.shared.md` as the single shared governance source for both packs whenever the change belongs in shared policy rather than Claude-only runtime rules.
- **MUST** update `shared/references/` for repo-wide design-only methodology and the affected `references-claude/` pack-specific docs when governance, protocol, gate, or routing semantics change in the installed pack. Shared references are the canonical cross-pack methodology source of truth; pack-local references must stay aligned where they carry Claude-specific semantics or stable compatibility pointers. A governance change that updates `src.claude/` without updating the affected shared or pack-local reference docs is incomplete.
- Treat `shared/references/subagent-operating-model.md` as the canonical shared blueprint and `references-claude/subagent-operating-model.md` only as the Claude-specific runtime and repository addendum. Do not reintroduce a second full Claude-side methodology copy in `references-claude/`.
- **MUST** update `README.md` and `INSTALL.md` when pack structure, skill count, install targets, or entry points change. A structural change without doc update is incomplete.
- **MUST** update `RELEASE_NOTES.md` in the same change when staged tracked content changes installed behavior, governance, routing, role contracts, install surface, developer or operator workflow, or other release-relevant user-facing expectations. The release-notes entry must explain the improvement, why it matters, and the affected user or operator workflow, not just list filenames or terse labels. Purely local-only hygiene edits such as formatting, link fixes, report-only churn, scratch cleanup, archive moves, and non-semantic wording cleanup do not require a release-notes entry.
- **No mechanical application:** do not copy, move, rename, merge, or propagate content mechanically — between packs, between files, or within the same file — without verifying that the result is correct in the target context. Platform-specific semantics (execution model, parallelism, invocation mechanism, paths, tool capabilities), ownership boundaries, and behavioral implications must be checked before the change lands. "The other pack has it" or "the source file said so" is not sufficient justification. Every change must be independently valid where it lands.
- **Cross-pack sync:** when editing shared semantic blocks in `operating-model.md` or `subagent-contracts.md`, consult [`cross-pack-reconciliation.md`](cross-pack-reconciliation.md) to identify and update the matching block in the other pack.
- Keep `src.claude/agents/contracts/external-dispatch.md` aligned with `src.codex/skills/lead/external-dispatch.md` whenever the agents-mode schema, provider paths, provenance rules, or external dispatch semantics change.
- Run `/agents-validate` after changes.
- Test install: `scripts/install-claude.ps1 -Global` and verify CLAUDE.md sections.

## File layout

```
shared/                  ← shared governance + shared design-reference source
  AGENTS.shared.md       ← common governance (merged by installers)
  references/            ← canonical shared design-only references
references-codex/        ← Codex-specific addenda + compatibility pointers for shared references
references-claude/       ← Claude-specific addenda + compatibility pointers for shared references
src.claude/              ← Claude Code pack source (install copies to target .claude/)
  CLAUDE.md              ← product governance (installed to users)
  agents/                ← 33 role definitions
    contracts/           ← operating model + subagent contracts + policy catalog
    team-templates/      ← 8 routing templates (JSON)
    scripts/             ← validation + safety scripts
  commands/              ← 19 skills (slash commands)
.claude/                 ← local working install (in .gitignore, NOT committed)
CLAUDE.md                ← THIS FILE (repo-local dev rules, NOT installed)
RELEASE_NOTES.md         ← canonical tracked release log for release-relevant changes
cross-pack-reconciliation.md ← shared semantic block map between packs
README.md                ← public docs
INSTALL.md               ← install instructions
install.ps1              ← unified PowerShell entry point
install.sh               ← unified Bash entry point
scripts/                 ← platform-specific installers
  install-claude.ps1     ← Claude Code PowerShell installer
  install-claude.sh      ← Claude Code Bash installer
  install-codex.ps1      ← Codex PowerShell installer
  install-codex.sh       ← Codex Bash installer
```

## Key invariants

- Every role in `shared/AGENTS.shared.md` `## Role index` must have a matching `.md` file in `agents/`
- Every skill must have the `agents-` prefix
- Every workflow skill must contain "MUST be invoked via the Agent tool"
- Every code-writing skill must contain "Do NOT commit"
- Install script thresholds must match actual counts
- `src.claude/CLAUDE.md` must NOT contain repo-local content — that goes here
- `$consultant` stays advisory-only; external execution and external review/QA belong to `$external-worker` and `$external-reviewer`
- Team template JSON stays unchanged when external dispatch semantics change; routing substitutions belong in contracts and role docs
