# Research Memo

## Scope

Read-only audit of cross-pack external-routing symmetry and role-surface symmetry across:

- `Orchestrarium/main`
- standalone `codex`
- standalone `claude`
- standalone `gemini`
- live project overlays at repo root
- neutral-directory external advisory runs through Codex CLI and Gemini CLI

## Accepted findings

### 1. What is already aligned

| Area | Accepted finding | Evidence |
|---|---|---|
| Provider defaults | Current line-default provider mapping is internally aligned across `main` and standalone docs/contracts. | [Orchestrarium/docs/agents-mode-reference.md](d:/dev/Orchestrator/Orchestrarium/docs/agents-mode-reference.md), [codex/docs/agents-mode-reference.md](d:/dev/Orchestrator/codex/docs/agents-mode-reference.md), [claude/docs/agents-mode-reference.md](d:/dev/Orchestrator/claude/docs/agents-mode-reference.md), [gemini/docs/agents-mode-reference.md](d:/dev/Orchestrator/gemini/docs/agents-mode-reference.md) |
| Provider-specific workdir modes | `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalGeminiWorkdirMode` are now present across canonical docs, dispatch contracts, init surfaces, and live project overlays, with default `neutral`. | [Orchestrarium/docs/agents-mode-reference.md](d:/dev/Orchestrator/Orchestrarium/docs/agents-mode-reference.md), [Orchestrarium/src.codex/skills/lead/external-dispatch.md](d:/dev/Orchestrator/Orchestrarium/src.codex/skills/lead/external-dispatch.md), [Orchestrarium/src.claude/agents/contracts/external-dispatch.md](d:/dev/Orchestrator/Orchestrarium/src.claude/agents/contracts/external-dispatch.md), [Orchestrarium/src.gemini/skills/lead/external-dispatch.md](d:/dev/Orchestrator/Orchestrarium/src.gemini/skills/lead/external-dispatch.md), [`.agents/.agents-mode`](d:/dev/Orchestrator/.agents/.agents-mode), [`.claude/.agents-mode`](d:/dev/Orchestrator/.claude/.agents-mode), [`.gemini/.agents-mode`](d:/dev/Orchestrator/.gemini/.agents-mode) |
| Parallel external eligibility | Parallel external execution and slot-pressure fallback are already stated consistently in docs/contracts. | [Orchestrarium/docs/agents-mode-reference.md](d:/dev/Orchestrator/Orchestrarium/docs/agents-mode-reference.md), [Orchestrarium/src.codex/skills/lead/external-dispatch.md](d:/dev/Orchestrator/Orchestrarium/src.codex/skills/lead/external-dispatch.md), [Orchestrarium/src.claude/agents/contracts/external-dispatch.md](d:/dev/Orchestrator/Orchestrarium/src.claude/agents/contracts/external-dispatch.md), [Orchestrarium/src.gemini/skills/lead/external-dispatch.md](d:/dev/Orchestrator/Orchestrarium/src.gemini/skills/lead/external-dispatch.md) |
| Fail-fast semantics | Owner-role external dispatch remains unsupported and must fail fast; adapters do not silently self-fallback. | Same references as above |

### 2. Remaining external-routing asymmetries

| Area | Accepted finding | Evidence |
|---|---|---|
| Provider universe | Source-layer docs and init surfaces are still line-specific and exclude self-provider selection on the native line, but live repo overlays already advertise a shared superset-style provider comment. This is a real inconsistency. | [Orchestrarium/docs/agents-mode-reference.md](d:/dev/Orchestrator/Orchestrarium/docs/agents-mode-reference.md), [Orchestrarium/src.codex/skills/init-project/SKILL.md](d:/dev/Orchestrator/Orchestrarium/src.codex/skills/init-project/SKILL.md), [Orchestrarium/src.claude/commands/agents-init-project.md](d:/dev/Orchestrator/Orchestrarium/src.claude/commands/agents-init-project.md), [Orchestrarium/src.gemini/skills/init-project/SKILL.md](d:/dev/Orchestrator/Orchestrarium/src.gemini/skills/init-project/SKILL.md), [`.agents/.agents-mode`](d:/dev/Orchestrator/.agents/.agents-mode), [`.claude/.agents-mode`](d:/dev/Orchestrator/.claude/.agents-mode), [`.gemini/.agents-mode`](d:/dev/Orchestrator/.gemini/.agents-mode) |
| Claude transport keys | Codex and Gemini docs/contracts/init surfaces define `externalClaudeSecretMode` and `externalClaudeApiMode`, but the live repo overlays do not materialize those keys. | [Orchestrarium/src.codex/skills/lead/external-dispatch.md](d:/dev/Orchestrator/Orchestrarium/src.codex/skills/lead/external-dispatch.md), [Orchestrarium/src.gemini/skills/lead/external-dispatch.md](d:/dev/Orchestrator/Orchestrarium/src.gemini/skills/lead/external-dispatch.md), [`.agents/.agents-mode`](d:/dev/Orchestrator/.agents/.agents-mode), [`.gemini/.agents-mode`](d:/dev/Orchestrator/.gemini/.agents-mode) |
| Claude line transport scope | Claude-line docs currently say Claude-target transport keys are not canonical because Claude-line external dispatch goes to Codex CLI, which conflicts with the user-approved direction of a shared external-provider universe. | [Orchestrarium/docs/agents-mode-reference.md](d:/dev/Orchestrator/Orchestrarium/docs/agents-mode-reference.md), [Orchestrarium/README.md](d:/dev/Orchestrator/Orchestrarium/README.md), [Orchestrarium/INSTALL.md](d:/dev/Orchestrator/Orchestrarium/INSTALL.md) |

### 3. Remaining structural role/team asymmetries

| Area | Accepted finding | Evidence |
|---|---|---|
| Codex team materialization | `codex` still has no `team-templates/` materialization, while `claude` and `gemini` both carry `8` JSON team templates. | [Orchestrarium/src.codex/AGENTS.codex.md](d:/dev/Orchestrator/Orchestrarium/src.codex/AGENTS.codex.md), [Orchestrarium/src.claude/agents/team-templates/full-delivery.json](d:/dev/Orchestrator/Orchestrarium/src.claude/agents/team-templates/full-delivery.json), [Orchestrarium/src.gemini/agents/team-templates/full-delivery.json](d:/dev/Orchestrator/Orchestrarium/src.gemini/agents/team-templates/full-delivery.json) |
| Helper normalization | `init-project`, `review-changes`, and `second-opinion` are helper skills in `codex` and `gemini`, but not materialized as agent-role files on the Claude side. | [Orchestrarium/src.codex/skills/init-project/SKILL.md](d:/dev/Orchestrator/Orchestrarium/src.codex/skills/init-project/SKILL.md), [Orchestrarium/src.gemini/skills/init-project/SKILL.md](d:/dev/Orchestrator/Orchestrarium/src.gemini/skills/init-project/SKILL.md), [Orchestrarium/src.claude/agents](d:/dev/Orchestrator/Orchestrarium/src.claude/agents) |
| Gemini dual surface | Gemini carries both stable `skills/` and preview `agents/`; Codex is skills-only and Claude is agent-first. The role vocabulary is much closer than before, but materialization remains asymmetric. | [Orchestrarium/src.gemini/skills/README.md](d:/dev/Orchestrator/Orchestrarium/src.gemini/skills/README.md), [Orchestrarium/src.gemini/agents/README.md](d:/dev/Orchestrator/Orchestrarium/src.gemini/agents/README.md) |
| Help/init command surfaces | `codex` has no `commands/` tree, `main claude` has markdown commands, standalone `claude` maps those into `agents-*` skills, and `gemini` still has only two TOML commands. | [Orchestrarium/src.claude/commands/agents-help.md](d:/dev/Orchestrator/Orchestrarium/src.claude/commands/agents-help.md), [claude/src.claude/skills/agents-help/SKILL.md](d:/dev/Orchestrator/claude/src.claude/skills/agents-help/SKILL.md), [Orchestrarium/src.gemini/commands/agents/help.toml](d:/dev/Orchestrator/Orchestrarium/src.gemini/commands/agents/help.toml) |

### 4. Operator-facing truthfulness drift

| Area | Accepted finding | Evidence |
|---|---|---|
| Root docs | Root docs still describe line-specific external-provider selection and Claude transport scope rather than a shared provider universe. | [Orchestrarium/README.md](d:/dev/Orchestrator/Orchestrarium/README.md), [Orchestrarium/INSTALL.md](d:/dev/Orchestrator/Orchestrarium/INSTALL.md) |
| Gemini help/init messaging | Gemini help surface still frames routing through current line-specific assumptions and does not yet reflect a possible shared-provider-universe rewrite. | [Orchestrarium/src.gemini/commands/agents/help.toml](d:/dev/Orchestrator/Orchestrarium/src.gemini/commands/agents/help.toml) |
| Claude help messaging | Claude help surface is truthful about current commands, but still implicitly assumes the current Claude-line external topology. | [Orchestrarium/src.claude/commands/agents-help.md](d:/dev/Orchestrator/Orchestrarium/src.claude/commands/agents-help.md) |

## External advisory layer

Neutral-directory external runs used:

- Codex CLI output in [codex.txt](d:/dev/Orchestrator/.scratch/external-rewrite/neutral/codex.txt)
- Gemini CLI output in [gemini.txt](d:/dev/Orchestrator/.scratch/external-rewrite/neutral/gemini.txt)

Accepted advisory takeaways:

| Advisory source | Accepted takeaway |
|---|---|
| Codex external | Prefer one shared provider universe, one shared lane-priority matrix, and provider-local transport/workdir knobs. Reject same-provider recursion silently; keep explicit user override above defaults. |
| Gemini external | Same architectural direction is sensible: common provider universe and matrix with provider-local adapters. Default neutral workdirs are beneficial for isolation. Gemini advisory, however, overweights Gemini for repo-wide research/planning relative to earlier neutral comparative research, so treat its lane ordering as advisory rather than canonical. |

## Research verdict

| Area | Verdict |
|---|---|
| External-routing model | `REVISE` — current repo has partially aligned mechanics but not the shared provider universe the user asked for |
| Cross-pack role principle | `REVISE` — role vocabulary is much closer, but team/template/help materialization still diverges |
| Truthfulness | `REVISE` — first-page and operator docs still describe the older line-specific routing model |

PASS for research completeness; REVISE for the system under study.
