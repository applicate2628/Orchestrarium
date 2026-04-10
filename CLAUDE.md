# Claudestrator Development Guidelines

Local rules for developing the Claudestrator skill-pack itself. These do NOT get installed to users — they apply only to this repository.

## Project policies

- **commit-format**: conventional
- **documentation**: always-update
- **language-style**: english (code, comments, docs), russian OK in user-facing session reports

## Skill development checklist

When adding, renaming, or removing a skill (`src.claude/skills/agents-*/SKILL.md`):

1. Create/edit the skill file in `src.claude/skills/<skill-name>/SKILL.md`
2. Update `src.claude/skills/agents-help/SKILL.md` — add to the skills table
3. Update `README.md` — add to the skills table
4. Update `INSTALL.md` — update skill count
5. Update `README.md` — update skill count
6. Update `install-claude.ps1` — update skill count threshold in verification
7. Update `install-claude.sh` — update skill count threshold in verification
8. Update `src.claude/agents/scripts/validate-skill-pack.sh` — add skill to validation list if not auto-discovered
9. Run `/agents-validate` to confirm structural integrity
10. Run `install-claude.ps1 -Global` to install and verify

## Role development checklist

When adding or modifying a role (`src.claude/agents/*.md`):

1. Create/edit the role file in `src.claude/agents/`
2. Update `src.claude/CLAUDE.md` `## Role index` — add to the correct category
3. If the role is a new reviewer or constraint role, check if team templates need updating
4. Run `/agents-validate` to confirm the role is indexed

## Template development checklist

When adding or modifying a team template (`src.claude/agents/team-templates/*.json`):

1. Create/edit the template JSON — must have `requiresLead` and `chain` fields
2. Update `src.claude/CLAUDE.md` `## Delegation rule` — add to the templates table
3. Update `src.claude/agents/contracts/operating-model.md` if routing rules change
4. Run `/agents-validate`

## Contract and governance changes

When modifying `src.claude/CLAUDE.md`, `operating-model.md`, or `subagent-contracts.md`:

- These are the governance core. Changes propagate to all users on next install.
- State explicitly what behavior changes and what is preserved.
- **MUST** update `references-claude/subagent-operating-model.md` and all `references-claude/` docs when any governance, protocol, gate, or routing semantic changes in the installed pack. Reference docs are the canonical methodology source of truth — they MUST stay aligned with the installed contracts. A governance change that updates `src.claude/` without updating `references-claude/` is incomplete.
- **MUST** update `README.md` and `INSTALL.md` when pack structure, skill count, install targets, or entry points change. A structural change without doc update is incomplete.
- **No mechanical application:** do not copy, move, rename, merge, or propagate content mechanically — between packs, between files, or within the same file — without verifying that the result is correct in the target context. Platform-specific semantics (execution model, parallelism, invocation mechanism, paths, tool capabilities), ownership boundaries, and behavioral implications must be checked before the change lands. "The other pack has it" or "the source file said so" is not sufficient justification. Every change must be independently valid where it lands.
- Run `/agents-validate` after changes.
- Test install: `install-claude.ps1 -Global` and verify CLAUDE.md sections.

## File layout

```
src.claude/              ← skill-pack source (install copies to target .claude/)
  CLAUDE.md              ← product governance (installed to users)
  agents/                ← 31 role definitions
    contracts/           ← operating model + subagent contracts + policy catalog
    team-templates/      ← 8 routing templates (JSON)
    scripts/             ← validation + safety scripts
  skills/                ← 19 slash skills (preferred Claude runtime surface)
.claude/                 ← local working install (in .gitignore, NOT committed)
CLAUDE.md                ← THIS FILE (repo-local dev rules, NOT installed)
README.md                ← public docs
INSTALL.md               ← install instructions
install-claude.ps1              ← PowerShell installer
install-claude.sh               ← Bash installer
```

## Key invariants

- Every role in `## Role index` must have a matching `.md` file in `agents/`
- Every skill must have the `agents-` prefix
- Every workflow skill must contain "MUST be invoked via the Agent tool"
- Every code-writing skill must contain "Do NOT commit"
- Install script thresholds must match actual counts
- `src.claude/CLAUDE.md` must NOT contain repo-local content — that goes here
