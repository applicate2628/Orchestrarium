# Orchestrarium Monorepo — Claude Code Development Overlay

This file is the repo-local Claude Code development overlay for this monorepo. Claude Code reads it while working inside this repository; it is not installed into user projects.

At the start of a new maintenance session, read [`docs/new-session-guide.md`](docs/new-session-guide.md) before non-trivial edits. It is the repo-local orientation contract: this monorepo is the source of truth, and installed files under `~/.codex/`, `~/.claude/`, project `.agents/`, or project `.claude/` are runtime outputs to sync only after the owning source is fixed.

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
5. Verify `scripts/install-claude.ps1` install output totals after adding/removing a skill (installers count pack items dynamically — no hardcoded threshold to edit)
6. Verify `scripts/install-claude.sh` install output totals after adding/removing a skill (same dynamic count)
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
- **MUST** update `RELEASE_NOTES.md` in the same change when staged tracked content changes installed behavior, governance, routing, role contracts, install surface, developer or operator workflow, or other release-relevant user-facing expectations. Keep the log in reverse-chronological `## YYYY-MM-DD` sections: append new explanatory bullets under the current date heading or create today's heading if it is missing, and do not keep a long-lived `## Unreleased` bucket. The release-notes entry must explain the improvement, why it matters, and the affected user or operator workflow, not just list filenames or terse labels. Purely local-only hygiene edits such as formatting, link fixes, report-only churn, scratch cleanup, archive moves, and non-semantic wording cleanup do not require a release-notes entry, but that exemption must be an explicit reviewer determination at publication time rather than an untracked assumption.
- Apply the shared documentation terminology discipline everywhere, not only in docs: in the main conversation and chat replies, always expand domain terms, acronyms, provider/model/role names, workflow labels, and unclear or mixed-language terms on first use — calibrate to comprehension (expand inline or as a short list; do not define ordinary words). When updating human-facing repo documentation, also end terminology-heavy documents with `## Terms and Abbreviations` or a localized equivalent, expanding those terms there.
- **No mechanical application:** do not copy, move, rename, merge, or propagate content mechanically — between packs, between files, or within the same file — without verifying that the result is correct in the target context. Platform-specific semantics (execution model, parallelism, invocation mechanism, paths, tool capabilities), ownership boundaries, and behavioral implications must be checked before the change lands. "The other pack has it" or "the source file said so" is not sufficient justification. Every change must be independently valid where it lands.
- **Cross-pack sync:** when editing shared semantic blocks in `operating-model.md` or `subagent-contracts.md`, consult [`cross-pack-reconciliation.md`](cross-pack-reconciliation.md) to identify and update the matching block in the other pack.
- Keep `src.claude/agents/contracts/external-dispatch.md` aligned with `src.codex/skills/lead/external-dispatch.md` whenever the agents-mode schema, provider paths, provenance rules, or external dispatch semantics change.
- For external CLI prompt behavior, keep provider-backed consultant, worker, and reviewer launches file-based: substantive task prompts go into a temporary prompt file fed through stdin or provider-supported file input; argv stays for flags, model/profile options, and file paths.
- **Source-tree organization:** the shared rules `Directory-level entity separation` and `Trash hygiene and archival` (in `shared/AGENTS.shared.md` `### Scope and ownership discipline`) govern how this repo organizes source files. Three legacy directories (`src.claude/agents/scripts/`, `src.codex/skills/lead/scripts/`, root `scripts/`) are grandfathered exceptions for user-copy / install-script convenience. New entity types MUST follow the shared rule (typed subdirectory or canonical home), not extend the legacy co-located dirs. Full design narrative + exception rationale + worked examples: [`shared/references/repository-source-hygiene.md`](shared/references/repository-source-hygiene.md).
- Run `/agents-validate` after changes.
- Test install: `scripts/install-claude.ps1 -Global` and verify CLAUDE.md sections.

## File layout

```
shared/                  ← shared governance + shared design-reference source
  AGENTS.shared.md       ← common governance (merged by installers)
  references/            ← canonical shared design-only references
references-claude/       ← Claude-specific addenda + compatibility pointers for shared references
references-codex/        ← Codex-specific addenda + compatibility pointers for shared references
references-gemini/       ← Gemini-specific addenda + compatibility pointers for shared references
references-qwen/         ← Qwen-specific addenda + compatibility pointers for shared references
src.claude/              ← Claude Code pack source (install copies to target .claude/)
  CLAUDE.md              ← product governance (installed to users)
  agents/                ← role definitions + delegate-style common-skill wrappers
    contracts/           ← operating model + subagent contracts + policy catalog
    team-templates/      ← 8 routing templates (JSON)
    scripts/             ← validation + safety scripts + the 2 blocking hooks + hook_common
    hooks/               ← the 2 warn-only audit hooks (machine-local-path, no-trash/stray-artifact)
  commands/              ← slash commands (agents-*)
  skills/                ← common skills (workflow-focused, Skill-tool invokable)
src.codex/               ← Codex pack source; canonical Codex-line implementation
src.gemini/              ← Gemini provider-pack source tree; example-only
src.qwen/                ← Qwen provider-pack source tree; example-only
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
  install-gemini.ps1     ← Gemini PowerShell installer
  install-gemini.sh      ← Gemini Bash installer
  install-qwen.ps1       ← Qwen PowerShell installer
  install-qwen.sh        ← Qwen Bash installer
  check-publication-gate.ps1 ← repo-local publication gate wrapper
  check-publication-gate.sh  ← repo-local publication gate
```

## Key invariants

- Every role in `shared/AGENTS.shared.md` `## Role index` must have a matching `.md` file in `agents/`
- Every skill must have the `agents-` prefix
- Every workflow skill must contain "MUST be invoked via the Agent tool"
- Every code-writing skill must contain "Do NOT commit"
- Install output totals must match actual pack counts (installers count dynamically; verify after add/remove)
- `src.claude/CLAUDE.md` must NOT contain repo-local content — that goes here
- `$consultant` stays advisory-only; external execution and external review/QA belong to `$external-worker` and `$external-reviewer`
- Team template JSON stays unchanged when external dispatch semantics change; routing substitutions belong in contracts and role docs

## Terms and Abbreviations

- `AGENTS.md`: the shared governance file imported by the Claude Code pack.
- `AGENTS.shared.md`: the shared governance source merged into installable provider packs.
- `API`: Application Programming Interface, a programmatic contract exposed by a tool, runtime, or service.
- `argv`: the command-line argument vector passed to a process.
- `CLAUDE.md`: the Claude Code-readable instruction file for a repository or installed pack.
- `CLI`: Command-Line Interface, a terminal command surface such as `claude`, `codex`, or `gemini`.
- `Codex`: the OpenAI Codex runtime and provider pack maintained by this repository.
- `Claude Code`: Anthropic's Claude Code runtime and matching provider pack.
- `Gemini`: the Google Gemini runtime/provider family; in this repository it is example-only unless explicitly selected.
- `JSON`: JavaScript Object Notation, a structured data format used by team template files.
- `MCP`: Model Context Protocol, a protocol used to expose tools and resources to agent runtimes.
- `QA`: Quality Assurance, verification work focused on tests, regressions, and acceptance criteria.
- `RELEASE_NOTES.md`: the tracked release log for release-relevant repository changes.
- `stdin`: standard input, the input stream provided to a process.
