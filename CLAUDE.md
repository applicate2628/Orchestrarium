# Claudestrator Development Guidelines

Local rules for developing the Claudestrator skill-pack itself. These do NOT get installed to users — they apply only to this repository.

## Project policies

- **commit-format**: conventional
- **documentation**: always-update
- **language-style**: english (code, comments, docs), russian OK in user-facing session reports

## Skill development checklist

When adding, renaming, or removing a skill (`.claude/commands/agents-*.md`):

1. Create/edit the skill file in `.claude/commands/`
2. Update `.claude/commands/agents-help.md` — add to the skills table
3. Update `README.md` — add to the skills table
4. Update `INSTALL.md` — update skill count
5. Update `README.md` — update skill count
6. Update `install.ps1` — update skill count threshold in verification
7. Update `install.sh` — update skill count threshold in verification
8. Update `.claude/scripts/validate-skill-pack.sh` — add skill to validation list if not auto-discovered
9. Run `/agents-validate` to confirm structural integrity
10. Run `install.ps1 -Global` to install and verify

## Role development checklist

When adding or modifying a role (`.claude/agents/*.md`):

1. Create/edit the role file in `.claude/agents/`
2. Update `.claude/CLAUDE.md` `## Role index` — add to the correct category
3. If the role is a new reviewer or constraint role, check if team templates need updating
4. Run `/agents-validate` to confirm the role is indexed

## Template development checklist

When adding or modifying a team template (`.claude/agents/team-templates/*.json`):

1. Create/edit the template JSON — must have `requiresLead` and `chain` fields
2. Update `.claude/CLAUDE.md` `## Delegation rule` — add to the templates table
3. Update `.claude/agents/contracts/operating-model.md` if routing rules change
4. Run `/agents-validate`

## Contract and governance changes

When modifying `.claude/CLAUDE.md`, `operating-model.md`, or `subagent-contracts.md`:

- These are the governance core. Changes propagate to all users on next install.
- State explicitly what behavior changes and what is preserved.
- Run `/agents-validate` after changes.
- Test install: `install.ps1 -Global` and verify CLAUDE.md sections.

## File layout

```
.claude/
  CLAUDE.md              ← product governance (installed to users)
  agents/                ← 31 role definitions
    contracts/           ← operating model + subagent contracts
    team-templates/      ← 8 routing templates (JSON)
  commands/              ← 19 skills (slash commands)
  policies/              ← policy catalog
  scripts/               ← validation + safety scripts
CLAUDE.md                ← THIS FILE (repo-local dev rules, NOT installed)
README.md                ← public docs
INSTALL.md               ← install instructions
install.ps1              ← PowerShell installer
install.sh               ← Bash installer
```

## Key invariants

- Every role in `## Role index` must have a matching `.md` file in `agents/`
- Every skill must have the `agents-` prefix
- Every workflow skill must contain "MUST be invoked via the Agent tool"
- Every code-writing skill must contain "Do NOT commit"
- Install script thresholds must match actual counts
- `.claude/CLAUDE.md` must NOT contain repo-local content — that goes here
