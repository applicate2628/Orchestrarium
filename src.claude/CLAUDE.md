@AGENTS.md

# Claudestrator

Platform-specific rules for Claude Code. Shared governance (hygiene, publication safety, role index, core delegation) is imported from `AGENTS.md` above via `@import`.

## Delegation rule

If `## Project policies` section is missing from this file, suggest running `/agents-init-project` before starting implementation work.

When subagent delegation is appropriate, classify the task and pick the matching team template from `.claude/agents/team-templates/`.

External adapter preferences live in `.claude/.consultant-mode`. The file keeps `mode` for consultant behavior and adds `preferExternalWorker` / `preferExternalReviewer` for eligible implement and review-side substitutions without changing team template JSON.

**Decision tree:**

1. Does the task need parallel risk owners (security + performance + ...)? → `requiresLead: true` template
2. Does it need implementation? No → `research` or `review`
3. One module, contracts unchanged? → `quick-fix`
4. Otherwise → `full-delivery`

**Templates:**

| Template | When | Lead needed? | Routing |
| --- | --- | --- | --- |
| `quick-fix` | Local additive change, one module, no new risk | No | Main conv → implementer → QA |
| `research` | Investigation, ADR, alternatives — no implementation | No | Main conv → analyst → architect → planner |
| `review` | Architecture/code quality gate, project audit, post-impl validation | No | Main conv → analyst → QA → reviewers |
| `full-delivery` | New feature, substantial change, multi-stage pipeline | Yes | `$lead` coordinates full pipeline |
| `security-sensitive` | Auth, trust boundaries, credentials, vulnerability | Yes | `$lead` coordinates, security-reviewer mandatory |
| `performance-sensitive` | Hard budgets, SLAs, latency targets | Yes | `$lead` coordinates, performance-reviewer mandatory |
| `geometry-review` | Spatial computation, transforms, meshing | Yes | `$lead` coordinates, computational-scientist + arch-reviewer |
| `combined-critical` | Multiple risk domains simultaneously | Yes | `$lead` coordinates all risk owners |

**Claude Code routing rules:**

- Every specialist invocation MUST use the Agent tool with the matching `subagent_type`. Do not simulate roles in the main conversation.
- If the template says `requiresLead: false`, the main conversation manages the chain directly — invoke specialists via Agent tool in order, pass each accepted artifact to the next.
- If the template says `requiresLead: true`, invoke `$lead` via Agent tool who coordinates work-items, risk owners, integration, and gates.
- Independent roles (e.g., security-engineer and performance-engineer) SHOULD be launched in parallel via multiple Agent tool calls in a single message when their scopes do not overlap.
- External adapter substitution is a routing decision, not a template change. When the preferences file favors external dispatch, eligible implementer slots may route through `$external-worker` and eligible review/QA slots through `$external-reviewer`; mandatory security and performance gates stay internal unless the design explicitly says otherwise.

**Recovery rule:**

- For `requiresLead: true` chains, `$lead` manages recovery through `work-items/` (roadmap.md, brief.md, status.md).
- For `requiresLead: false` chains with 2+ stages, the main conversation must save recovery state in `work-items/active/<date>-<slug>/` after each stage transition: `status.md` (format defined in `subagent-contracts.md` — includes template, orchestrator role, active/completed agents, next action) and the accepted artifact itself (e.g. `research.md`, `design.md`, `plan.md`). This allows any future session to resume from the last accepted artifact without replaying the chain.
- For single-specialist invocations (user names a role directly), no recovery file is needed.

## Role definitions

Role definitions live in `.claude/agents/<role>.md`.

## Publication safety scan

Pre-publication scan: run `/agents-check-safety`, or manually: `bash .claude/agents/scripts/check-publication-safety.sh` (Windows PowerShell: `powershell -ExecutionPolicy Bypass -File .claude/agents/scripts/check-publication-safety.ps1`).
