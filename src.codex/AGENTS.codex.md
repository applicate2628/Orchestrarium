# Codex Platform Rules

Platform-specific rules for OpenAI Codex. Merged with shared governance (`AGENTS.shared.md`) into a single `AGENTS.md` at install time.

## Default delegation entry point

If subagent delegation is appropriate for approved delivery work and no more specific delegated role has already been named, use `$lead` from `$CODEX_HOME/skills/lead` as the default delivery lead and coordinator.

If the task is about roadmap ownership, prioritization, milestone shaping, or admission into discovery or delivery, use `$product-manager` instead of treating it as ordinary delivery orchestration.

## Template routing

Classify the task and select the matching workflow shape. Simple chains do not require `$lead`. Codex processes one skill at a time (sequential execution model — no native parallel dispatch).

**Decision tree:**

1. Does the user explicitly name a role? Invoke it directly. No template needed.
2. Is this roadmap, prioritization, or milestone shaping? Route to `$product-manager`. No template needed.
3. Is it investigation, ADR, or alternatives exploration with no implementation? Use **research** below.
4. Is it a PR review, quality gate, or post-implementation validation with no new code? Use **review** below.
5. Is it a local additive change in one module, no new risk owner, contracts unchanged? Use **quick-fix** below.
6. Does it touch auth, trust boundaries, credentials, or a vulnerability? Use **security-sensitive** below.
7. Does it have hard performance budgets, SLAs, or latency targets? Use **performance-sensitive** below.
8. Does it involve spatial computation, transforms, meshing, or geometry? Use **geometry-review** below.
9. Does it touch multiple risk domains simultaneously? Use **combined-critical** below.
10. Otherwise, it is a new feature or substantial change. Use **full-delivery** below.

| Template | Lead needed? | Chain |
|---|---|---|
| `quick-fix` | No | Main conv picks implementer, then `$qa-engineer` |
| `research` | No | Main conv chains `$analyst` then `$architect`, optionally `$planner` |
| `review` | No | Main conv chains `$analyst` then `$qa-engineer` then reviewer(s) |
| `full-delivery` | Yes | `$lead` coordinates full pipeline |
| `security-sensitive` | Yes | `$lead` coordinates; `$security-engineer` and `$security-reviewer` mandatory |
| `performance-sensitive` | Yes | `$lead` coordinates; `$performance-engineer` and `$performance-reviewer` mandatory |
| `geometry-review` | Yes | `$lead` coordinates; `$computational-scientist` and `$architecture-reviewer` mandatory |
| `combined-critical` | Yes | `$lead` coordinates all risk owners and reviewers |

When the template says "No" for lead, the main conversation manages the chain directly: invoke specialists sequentially, pass each accepted artifact to the next role. Re-classify immediately if scope widens beyond the current template.

A bugfix with a known file or function maps to the `quick-fix` template by default, even if adjacent issues are discovered during analysis. Adjacent issues go to the configured bug registry path, not into the current plan.

## Recovery rule

- For lead-managed chains (`full-delivery`, `security-sensitive`, `performance-sensitive`, `geometry-review`, `combined-critical`), `$lead` manages recovery through the configured task-memory directory.
- For main-conversation-managed chains with 2+ stages (`research`, `review`), save recovery state after each accepted artifact: `status.md` (template name, current stage, next role) and the accepted artifact itself.
- For single-specialist invocations (user names a role directly), no recovery file is needed.

## Role resolution paths

Role definitions live in the installed skills tree: `.agents/skills/<role>/SKILL.md` for repo-local installs, or `$CODEX_HOME/skills/<role>/SKILL.md` / `~/.codex/skills/<role>/SKILL.md` for global installs.

Use these global anchor roles:

- `$lead`: default delivery coordination, routing, artifact acceptance, and gate decisions for approved work
- `$product-manager`: roadmap ownership, initiative prioritization, and admission into discovery or delivery
- `$consultant`: optional non-blocking independent advisor; usage rules, toggle check, execution paths, and fallback behavior are in `$CODEX_HOME/skills/consultant/SKILL.md`

For all other work, use the narrowest matching installed specialist. The role index in shared governance names the canonical core team only; installed specialists outside that core team and repo-local specialists may be used by `$lead` when they are a better fit.

Repository-specific `AGENTS.md` files should add local priorities, canonical paths, build/test rules, and source-of-truth references without redefining the whole global role catalog.

## Publication safety scan

For repo-local installs, run `bash .agents/skills/lead/scripts/check-publication-safety.sh` (Git Bash / macOS / Linux) or `powershell -ExecutionPolicy Bypass -File .agents/skills/lead/scripts/check-publication-safety.ps1` (Windows PowerShell). For global installs, run the same commands from `~/.codex/skills/lead/scripts/`.
