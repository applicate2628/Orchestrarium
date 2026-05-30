# New Session Guide

Use this guide at the start of a new Orchestrarium maintenance session. Its purpose is to prevent the same orientation questions from being re-answered in chat.

## First Principles

| Rule | Operational meaning |
|---|---|
| This repository is the source of truth | Fix Orchestrarium source first: `shared/`, `src.codex/`, `src.claude/`, `src.gemini/`, `src.qwen/`, `scripts/`, `docs/`, and root docs. |
| Installed copies are runtime outputs | `~/.codex/`, `~/.claude/`, project `.agents/`, and project `.claude/` are installed/runtime surfaces. Patch them only after the source owner is updated, and only when current sessions need the behavior before reinstall. |
| Do not treat stale installs as canon | A broken or stale global/local install can explain a symptom, but the durable fix belongs in the owning source file unless the problem is purely local state. |
| Do not create source from runtime guesses | Before adding a new path or mechanism, identify the owning source surface and installer propagation path. |
| Keep provider boundaries explicit | Codex-specific runtime metadata belongs in `src.codex/`; Claude Agent-tool wrappers belong in `src.claude/`; shared semantics belong in `shared/` plus affected provider addenda. |

## Start-of-Session Checklist

1. Confirm the current directory is the Orchestrarium checkout root: it contains `shared/AGENTS.shared.md`, `src.codex/`, and `src.claude/`. Do not work from a parent container directory or a standalone provider checkout by accident.
2. Run `git status --short -uall` before editing. Preserve unrelated local changes.
3. Classify the surface before changing it:
   - shared governance or cross-provider behavior -> `shared/AGENTS.shared.md` and `shared/references/`
   - Codex runtime pack -> `src.codex/`
   - Claude Code runtime pack -> `src.claude/`
   - example provider parity -> `src.gemini/` and `src.qwen/`
   - operator docs -> `docs/`, `README.md`, `INSTALL.md`
   - release-relevant tracked change -> `RELEASE_NOTES.md`
4. For a user-reported defect, capture the concrete symptom, the source `file:line`, and the hypothesis chain before the first edit.
5. If the symptom is visible only in an installed runtime, inspect the installed copy, then backtrack to the source owner and installer path.
6. After source changes, sync the live installed copy only when immediate current-session behavior matters. Say explicitly that the live edit is a runtime sync, not the canonical fix.
7. Run the narrowest relevant validators first, then broader pack validators before closeout.
8. Record a `.reports/YYYY-MM/` session log when the session produced a result, routing decision, or review outcome. Raw logs and task memory remain local-only.

## Source Map

| Need | Primary source |
|---|---|
| Shared governance loaded into installed `AGENTS.md` | `shared/AGENTS.shared.md` |
| Shared design-only methodology | `shared/references/` |
| Codex roles and common skills | `src.codex/skills/<name>/SKILL.md` |
| Codex skill UI metadata | `src.codex/skills/<name>/agents/openai.yaml` |
| Codex platform addendum and hooks | `src.codex/AGENTS.codex.md`, `src.codex/skills/lead/scripts/`, `src.codex/skills/lead/hooks/` |
| Claude roles | `src.claude/agents/<role>.md` |
| Claude slash commands | `src.claude/commands/agents-*.md` |
| Claude common skills | `src.claude/skills/<name>/SKILL.md` |
| Provider-specific addenda | `references-codex/`, `references-claude/`, `references-gemini/`, `references-qwen/` |
| Agents-mode schema and defaults | `shared/agents-mode.schema.json`, `shared/agents-mode.presets.json`, `shared/agents-mode.defaults.yaml` |
| Installers | root `install.*`, `scripts/install-*.{sh,ps1}` |
| Release log | `RELEASE_NOTES.md` |

## Runtime Map

| Runtime surface | Meaning |
|---|---|
| `~/.codex/` | Global installed Codex pack and live Codex runtime state. |
| `~/.claude/` | Global installed Claude Code pack and live Claude runtime state. |
| `.agents/` in a target project | Project-local installed Codex runtime output. Not normally committed. |
| `.claude/` in a target project | Project-local installed Claude Code runtime output. Not normally committed except project policy files when intentionally initialized. |
| `~/.agents` | Legacy or stale personal skill surface. Do not treat it as Orchestrarium canon. If it explains a symptom, remove or migrate it explicitly. |

Inside this monorepo, a missing local `.agents/` tree is not a misconfiguration. Maintainers may rely on the global `~/.codex/` install while editing source.

## Common Maintenance Patterns

| Symptom | Correct first move |
|---|---|
| Codex skill label, trigger, or default prompt is wrong | Edit `src.codex/skills/<skill>/SKILL.md` and/or `agents/openai.yaml`; then sync `~/.codex/skills/<skill>/` only if immediate behavior is needed. |
| Common skill behavior is wrong across providers | Update the common skill source in each affected provider tree; update shared docs/indexes when the public contract changes. Do not mechanically copy without validating provider semantics. |
| Claude behavior relies on `Agent` or slash-command mechanics | Keep that change in `src.claude/`; do not rewrite it for Codex unless there is a Codex-native owner. |
| Codex behavior lacks a direct Agent tool | Check available Codex subagent or MCP tooling in the current runtime; if unavailable, record the gap honestly instead of pretending the Claude mechanism exists. |
| Installed runtime has stale behavior | Verify the live installed file, patch source first, then reinstall or explicitly sync the installed file as a temporary live-runtime update. |
| Shared governance changes | Update `shared/AGENTS.shared.md`, affected `shared/references/`, provider addenda, validator fingerprints if required, and `RELEASE_NOTES.md`. |
| Context compaction loses active work | Restore active task, next unchecked step, and open evidence gates from the summary/status before acting; do not summarize and stop unless the task was parked, blocked, or complete. |
| User says to stop closeout and work | Treat it as a continue-working correction, not a request for acknowledgement. Take the next concrete action in the active task immediately unless a real blocker prevents action. |

## Validation

Run the smallest useful check first, then the affected pack checks.

| Change surface | Checks |
|---|---|
| Shared spine | `python scripts\validate-agents-spine.py --spine shared\AGENTS.shared.md` |
| Codex pack | `bash src.codex/skills/lead/scripts/validate-skill-pack.sh` |
| Claude pack | `bash src.claude/agents/scripts/validate-skill-pack.sh` |
| Gemini example pack | `bash src.gemini/scripts/validate-pack.sh` |
| Qwen example pack | `bash src.qwen/scripts/validate-pack.sh` |
| Agents-mode docs/schema | `python scripts\sync-agents-mode-docs.py --root . --check` |
| Installer behavior | `python scripts\validate-agents-mode-installers.py --root .` |
| Diff hygiene | `git diff --check` |
| Publication safety before push/release | `bash scripts/check-publication-gate.sh` or `.\scripts\check-publication-gate.ps1` |

## Do Not

- Do not patch only `~/.codex/`, `~/.claude/`, `.agents/`, or `.claude/` for behavior that belongs to Orchestrarium source.
- Do not treat sibling provider checkouts such as `../codex` or `../claude` as the monorepo unless the user explicitly names them.
- Do not move Claude-specific `Agent`/slash-command behavior into Codex by analogy.
- Do not assume a stale local install proves a source defect; inspect both installed and source files.
- Do not skip `RELEASE_NOTES.md` for tracked changes that affect installed behavior, governance, routing, role contracts, install surface, or operator workflow.
- Do not close a semantic control-plane change without the required independent reviewer gate; if the runtime cannot launch that reviewer, record the gate as open.

## Terms and Abbreviations

- `AGENTS.md`: Codex-readable governance entrypoint assembled from shared and Codex-specific source.
- `agents-mode`: Orchestrarium operator configuration overlay for delegation, provider routing, MCP use, and parallelism.
- `canon`: the tracked source of truth that survives reinstall and publication.
- `Codex`: OpenAI Codex runtime and the production Codex provider line in this repository.
- `Claude Code`: Anthropic Claude Code runtime and the production Claude provider line in this repository.
- `common skill`: workflow-focused skill shipped across provider packs, such as `windows-gui-manual-testing`.
- `control-plane`: governance, routing, role, gate, validator, install, and workflow policy surfaces that control how agents operate.
- `MCP`: Model Context Protocol, a tool/resource integration protocol for agent runtimes.
- `provider pack`: one provider-specific source tree under `src.<provider>/`.
- `runtime output`: installed files generated from this repo, used by an agent runtime but not the canonical source.
- `source owner`: the source file or directory that owns the behavior and should be edited before installed copies.
