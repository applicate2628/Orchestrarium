# Provider Runtime Layouts

This document records the installed runtime layout for the provider lines used by Orchestrarium today, including provider source trees that already exist in the monorepo. It is an install/runtime reference, not a source-layout reference.

## Codex native mechanical roles

Codex installs all 17 manifest role TOMLs as create-only payloads under the target `.codex/agents/` directory and registers each manifest name under `[agents.<name>]` in `.codex/config.toml`; `mechanical-scout` and `mechanical-worker` are the two Luna members. Their exact name, description, and `agents/<relativePath>` mapping come from the already-validated source TOML. Luna requires exact `gpt-5.6-luna` with `high` as default and minimum reasoning effort; only `high`, `xhigh`, and `max` are valid. Its shared eligibility is native policy rather than an agents-mode model option. `RoleDispatchPolicyV1` is resolved before any native dispatch consideration and accepts no host/provider result or result file: enabled plus a valid exact plan is `native-required`, while disabled is `E_NATIVE_V2_DISABLED`. Luna has zero decision authority; the caller owns exact tools, root, plan/facts oracle, and the worker's one existing-file exact patch with pre/post hashes and an executable exact-root/no-follow preflight. No external, Terra, Sol, runtime-default, or other fallback is permitted; host rejection is nonauthorizing `E_LUNA_UNAVAILABLE`.

Repository policy tests use inline requests and consume no tracked provider-result or runtime-result fixture. `scripts/validate-slice-a-detached.py` applies only the explicitly admitted overlay to one real detached candidate worktree, supervises every focused child, settles worktree cleanup, and only then publishes an always-nonauthorizing bounded manifest. Attempt logs and receipts are local evidence only.

Production auto-routing in the root integration contract is limited to Codex plus Claude Code. Kimi Code is explicit-only policy-admitted read-only exploration, research, planning, or review through the canonical fixed `kimi-code/k3` no-tools/no-subagents wrapper, independently verified and nonauthorizing; Grok remains unavailable in 1.x. `resolve_external_dispatch` must not use either in `auto`.

Do not confuse these runtime surfaces with the monorepo authoring trees `src.codex/` and `src.claude/`.

Architecture note: on the Codex line, the installed `AGENTS.md` is intentionally the compact universal minimum. Detailed installed role contracts and runtime guidance belong in the installed `skills/<role>/SKILL.md` files; the Native role manifest is source-only current-payload validation, while role TOMLs are create-only targets with no installed receipt or general adoption/update/reclaim authority in 1.x. The installer appends missing manifest mappings without reserializing `.codex/config.toml`, preserves unrelated bytes and the thread limit, rejects same-name mapping collisions, and gives an absent config `multi_agent_v2 = true` plus all mappings. It accepts exactly five hash-pinned stock-role upgrades, while the frozen legacy `luna_mechanical` config/file pair is a separate bounded mapping migration; legacy fixture bytes remain historical migration inputs. Codex and Claude compose one identical complete canonical `.agents/skills/lead` tree before its single create-only publication, in either installation order, and Claude receives only create-only discovery projections. Codex hook inventory is mutable evidence outside that tree and is authoritative only beside the final resolved ordinary `hooks.json`. Shared/provider reference trees are source-maintainer canon, not target-project install payload. Claude already follows the analogous pattern through a short `CLAUDE.md` entrypoint plus `.claude/agents/*.md` role files, with the five curated role-skills as the deliberate exception: `lead`, `product-manager`, `analyst`, `architect`, and `planner` keep their canonical contracts under `.claude/skills/<role>/SKILL.md`. Claude main-agent `lead` activation uses the documented `initialPrompt: /lead`; the same definition retains a fail-closed stale-dispatch branch, while the other four keep thin `.claude/agents/<role>.md` delegate wrappers that load the same-named skill.

Read the tables with three layers in mind:

- `Official provider behavior` means the provider's own documented runtime surface or configuration model.
- `Orchestrarium runtime contract` means the install shape and conventions introduced by this repository.
- `Observed installed behavior` means the result verified in an installed target.

Do not collapse those layers into one claim. When a row is Orchestrarium-owned rather than provider-native, the notes call that out explicitly.

## Scope legend

| Scope | Meaning |
| --- | --- |
| `Global` | User-level installed runtime surface, usually under the provider's home directory |
| `Local` | Project-level installed runtime surface inside the current repository or target project |

## Codex

### Global

| Installed pack root | `~/.codex/` | Global Codex pack install target |
| Governance entrypoint | `~/.codex/AGENTS.md` | Installed Codex runtime entrypoint; intentionally the compact universal minimum rather than the full role/runtime manual |
| Skill tree | `$HOME/.agents/skills/<role>/SKILL.md` | Orchestrarium Codex runtime organizes each role as a skill directory |
| Design-panel binding | `$HOME/.agents/skills/design-panel/SKILL.md` + `agents/openai.yaml` | Independent multi-lane design generation on one pinned problem, converged through one mandatory synthesis; no panel-state validator is installed |
| Native roles | `~/.codex/agents/<role>.toml` | Create-only: absent roles are created, identical files are no-ops, and differing files are preserved while installation fails. The source manifest validates current payloads and is never installed as a receipt; 1.x has no adoption, update, deletion, or reclaim authority. |
| Validation script | `$HOME/.agents/skills/lead/scripts/validate-skill-pack.sh` | Same lead script tree as the repo source |
| Publication-safety scan | `$HOME/.agents/skills/lead/scripts/check-publication-safety.sh` | PowerShell runs the sibling `.py` entrypoint with Python |
| Global operator overlay | `~/.codex/.agents-mode.yaml` | Orchestrarium-owned default operator file seeded on first global install and preserved on reinstall; legacy sibling `~/.codex/.agents-mode` is compatibility input only |

### Local

| Item | Path or shape | Notes |
| --- | --- | --- |
| Installed pack root | `<project>/.agents/skills/` | Role skills are copied here |
| Governance entrypoint | `<project>/AGENTS.md` | Codex pack section is merged into the project-root `AGENTS.md`; the installed Codex section stays intentionally compact and defers detailed installed role/runtime guidance to the skill tree |
| Skill tree | `<project>/.agents/skills/<role>/SKILL.md` | Mirrors the global `skills/` structure |
| Design-panel binding | `<project>/.agents/skills/design-panel/SKILL.md` + `agents/openai.yaml` | Project-level mirror of the global design-panel binding; no panel-state validator is installed |
| Native roles | `<project>/.codex/agents/<role>.toml` | Create-only: absent roles are created, identical files are no-ops, and differing files are preserved while installation fails. The source manifest validates current payloads and is never installed as a receipt; 1.x has no adoption, update, deletion, or reclaim authority. |
| Local config | `<project>/.agents/.agents-mode.yaml` | Canonical Orchestrarium local state file; local install seeds the default and `$init-project` reviews or updates it, while legacy sibling `<project>/.agents/.agents-mode` remains compatibility input only. Decision-driving reads use this local scope first, then fall back to the global Codex overlay when the local scope is absent. |
| Validation script | `<project>/.agents/skills/lead/scripts/validate-skill-pack.sh` | Run from the target project root after install |
| Publication-safety scan | `<project>/.agents/skills/lead/scripts/check-publication-safety.sh` | PowerShell runs the sibling `.py` entrypoint with Python |

## Claude Code

### Global

| Item | Path or shape | Notes |
| --- | --- | --- |
| Global context file | `~/.claude/CLAUDE.md` | Official user-level Claude Code instruction file; intentionally short while detailed role behavior lives under `~/.claude/agents/`, except the five curated role-skills (`lead`, `product-manager`, `analyst`, `architect`, `planner`) — contracts under `~/.claude/skills/<role>/SKILL.md`. `~/.claude/agents/lead.md` activates `/lead` through its main-agent `initialPrompt` and rejects stale dispatch; the other four keep thin delegate wrappers under `~/.claude/agents/`. |
| Global personal skills | `~/.claude/skills/<skill-name>/SKILL.md` | Official preferred user-level extension surface |
| Global personal subagents | `~/.claude/agents/*.md` | Official user-level custom subagent surface |
| Design-panel binding | `~/.claude/agents/contracts/design-panel.md` + `~/.claude/commands/agents-design-panel.md` | Independent multi-lane design generation on one pinned problem, converged through one mandatory synthesis; no panel-state validator is installed |
| Global legacy commands | `~/.claude/commands/*.md` | Still supported, but Claude docs now recommend skills as the preferred model |
| Global operator overlay | `~/.claude/.agents-mode.yaml` | Orchestrarium-owned default operator file seeded on first global install and preserved on reinstall; not a Claude-native file from official docs, and legacy sibling `~/.claude/.agents-mode` is compatibility input only |

### Local

| Item | Path or shape | Notes |
| --- | --- | --- |
| Project context file | `<project>/.claude/CLAUDE.md` or `<project>/CLAUDE.md` | Official project-level Claude instruction entrypoints; keep the entrypoint short and the detailed role files under `.claude/agents/`, except the five curated role-skills (`lead`, `product-manager`, `analyst`, `architect`, `planner`) — contracts under `.claude/skills/<role>/SKILL.md`. `.claude/agents/lead.md` activates `/lead` through its main-agent `initialPrompt` and rejects stale dispatch; the other four keep thin delegate wrappers under `.claude/agents/`. |
| Local personal override | `<project>/CLAUDE.local.md` | Official personal, uncommitted project override layer |
| Project skills | `<project>/.claude/skills/<skill-name>/SKILL.md` | Official preferred project-level extension surface |
| Project subagents | `<project>/.claude/agents/*.md` | Official project-level custom subagent surface |
| Design-panel binding | `<project>/.claude/agents/contracts/design-panel.md` + `<project>/.claude/commands/agents-design-panel.md` | Project-level mirror of the global design-panel binding; no panel-state validator is installed |
| Legacy commands | `<project>/.claude/commands/*.md` | Still work, but lose precedence to a skill with the same name |
| Orchestrarium shared governance copy | `<project>/.claude/AGENTS.md` | Repo-local overlay copied by Orchestrarium install scripts; not a Claude-native runtime requirement |
| Orchestrarium local config | `<project>/.claude/.agents-mode.yaml` | Canonical Orchestrarium local state file; local install seeds the default and `/agents-init-project` reviews or updates it, while legacy sibling `<project>/.claude/.agents-mode` remains compatibility input only. Decision-driving reads use this local scope first, then fall back to the global Claude overlay when the local scope is absent. |

## Quick comparison

| Provider | Global runtime root | Local runtime root | Native instruction entrypoint |
| --- | --- | --- | --- |
| Codex | `~/.codex/` | `<project>/.agents/` plus root `AGENTS.md` | `AGENTS.md` |
| Claude Code | `~/.claude/` | `<project>/.claude/` and optional root `CLAUDE.md` | `CLAUDE.md` |

## Sources

- Orchestrarium install and runtime contracts: `INSTALL.md`, `docs/agents-mode-reference.md`, `install.py`, `install.sh`, `src.codex/AGENTS.codex.md`, `src.codex/skills/consultant/SKILL.md`, `src.claude/CLAUDE.md`, `src.claude/agents/consultant.md`, `scripts/install-codex.py`, `scripts/install-codex.sh`, `scripts/install-claude.py`, `scripts/install-claude.sh`
- Claude Code documentation:
  - Memory and `CLAUDE.md` locations: <https://code.claude.com/docs/en/memory>
  - Skills and legacy commands: <https://code.claude.com/docs/en/slash-commands>
  - Subagents: <https://code.claude.com/docs/en/sub-agents>

## Terms and Abbreviations

- `AGENTS.md`: agent governance file used directly by Codex and installed as a shared-governance module for supported packs.
- `agents-mode`: Orchestrarium routing and operator overlay file for provider preferences and execution policy.
- `CLI`: Command-Line Interface, a terminal command surface for a provider runtime.
- `Codex`: OpenAI Codex runtime and production provider line.
- `Claude Code`: Anthropic's Claude runtime and production provider line.
- `extension`: provider-supported package directory that can bundle context, skills, agents, commands, or manifests.
- `local`: project-level install scope under a target repository.
- `MCP`: Model Context Protocol; a mechanism for exposing tool and resource servers to agent runtimes.
- `runtime root`: provider-facing directory where installed context, skills, agents, commands, or overlays live.
