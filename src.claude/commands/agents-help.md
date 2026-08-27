# Claude Code Pack Help

Display a comprehensive overview of the skill-pack for the user.

## Steps

1. **Read CLAUDE.md.** Read `.claude/CLAUDE.md` to get the delegation rule, templates table, role index, and project policies (if configured).

2. **Display the following sections in order:**

### Inline role-skills (curated, adopted in THIS conversation)

Exactly five roles can be adopted inline instead of dispatched — no fresh context, no isolation/independence claim, current conversation context is preserved. Everything else remains Agent-tool-only.

| Skill | Purpose | Agent disposition |
| --- | --- | --- |
| `/lead` | Adopt the Lead orchestration role in-session | host-selected main agent / inline role; only stale subagent dispatch is fail-closed — never spawned |
| `/product-manager` | Quick intake/scope framing when priority is unclear | dual — also `subagent_type: product-manager`; a formal cross-initiative roadmap decision, or admitting work that will gate other work, still routes to the subagent |
| `/analyst` | Trivial, bounded factual repository read | dual — also `subagent_type: analyst` |
| `/architect` | Quick-fix/fast-lane seam or blast-radius decision | dual — also `subagent_type: architect` |
| `/planner` | Upgrade a fast-lane inline plan into phased, AC-id'd form | dual — also `subagent_type: planner` |

### Skills (slash commands)

| Command | Purpose |
| --- | --- |
| `/agents-help` | This overview |
| `/agents-external-brigade` | Launch a bounded parallel set of external helpers |
| `/agents-review-loop` | Autonomous parallel-review-loop: 2 verdict angles + 1 scout converge on one fix-design artifact |
| `/agents-review` | Full repo-impact review from current changes or a specified target (analyst → QA → reviewer) |
| `/agents-bugfix` | Fix a bug (analyst → implementer → QA) |
| `/agents-test` | Write or verify tests for specified code |
| `/agents-research` | Investigate a question (analyst → architect) |
| `/agents-design` | Full research-to-plan chain (analyst → architect → planner) |
| `/agents-design-panel` | Design panel: N≥2 independently-framed design lanes + mandatory Lead synthesis (generation-side analog of `/agents-review-loop`) |
| `/agents-security` | Security review (security-engineer → security-reviewer) |
| `/agents-second-opinion` | Get a second opinion via consultant (Codex; preserves routing prefs) |
| `/agents-implement` | Execute an approved plan phase by phase |
| `/agents-perf` | Fix a performance issue (perf-engineer → impl → QA → perf-reviewer) |
| `/agents-refactor` | Safe refactoring with blast-radius analysis |
| `/agents-resume` | Resume an interrupted agent chain from saved state |
| `/agents-qa-session` | Interactive testing: you direct, QA agent investigates |
| `/agents-init-project` | Configure project policies and review or update `.claude/.agents-mode.yaml` interactively |
| `/agents-policies` | View or update a specific policy (`/agents-policies testing tdd`) |
| `/agents-check-policies` | Audit codebase compliance with configured policies |
| `/agents-validate` | Structural integrity check of the skill-pack |
| `/agents-status` | Project dashboard: active chains, policies, pack summary; flags reserved `$product-manager` admissions |
| `/agents-check-safety` | Run a manual staged or range diagnostic; push authorization uses the gate's own fresh canonical sibling scan |

### Decision tree

Show the template selection decision tree from CLAUDE.md.

### Templates

Show the templates table from CLAUDE.md (8 templates with lead/no-lead and use case).

### Roles by team

Group the 33 roles from the role index into their teams:

- **Roadmap & orchestration:** product-manager, lead, consultant, knowledge-archivist
- **Research & design:** product-analyst, analyst, architect, ux-designer, planner, algorithm-scientist, computational-scientist, security-engineer, performance-engineer, reliability-engineer
- **Implementation:** backend-engineer, frontend-engineer, qt-ui-engineer, model-view-engineer, data-engineer, platform-engineer, toolchain-engineer, geometry-engineer, graphics-engineer, visualization-engineer, external-worker
- **Review & verification:** qa-engineer, architecture-reviewer, security-reviewer, performance-reviewer, accessibility-reviewer, ux-reviewer, ui-test-engineer, external-reviewer

### Quick examples

Show 3-4 natural language examples of how to invoke agents:
- "fix the null check in parser.ts" → quick-fix
- "investigate why the cache hit rate dropped" → research
- "build a new export feature for reports" → full-delivery
- "$external-worker implement this approved phase through Codex CLI" → direct invocation
- "$external-reviewer audit this change through Codex CLI" → direct invocation
- "/agents-external-brigade run two external-reviewer lanes plus one explicit Kimi read-only nonauthorizing review lane with independent verification" → direct invocation
- "$consultant what do you think about this approach?" → direct invocation

### Project policies

If `## Project policies` section exists in CLAUDE.md, show current policies. If not, say: "No project policies configured. Run `/agents-init-project` to set up policies and review `.claude/.agents-mode.yaml`."

## Rules

- Keep output concise — this is a quick reference, not documentation.
- Do not read any files beyond CLAUDE.md.
- Do not modify any files.
