# Claude Code Pack Help

Display a comprehensive overview of the skill-pack for the user.

## Steps

1. **Read CLAUDE.md.** Read `.claude/CLAUDE.md` to get the delegation rule, templates table, role index, and project policies (if configured).

2. **Display the following sections in order:**

### Skills (slash commands)

| Command | Purpose |
| --- | --- |
| `/agents-help` | This overview |
| `/agents-review` | Full repo-impact review from current changes or a specified target (analyst → QA → reviewer) |
| `/agents-bugfix` | Fix a bug (analyst → implementer → QA) |
| `/agents-test` | Write or verify tests for specified code |
| `/agents-research` | Investigate a question (analyst → architect) |
| `/agents-design` | Full research-to-plan chain (analyst → architect → planner) |
| `/agents-security` | Security review (security-engineer → security-reviewer) |
| `/agents-second-opinion` | Get a second opinion via consultant (Codex; preserves routing prefs) |
| `/agents-implement` | Execute an approved plan phase by phase |
| `/agents-perf` | Fix a performance issue (perf-engineer → impl → QA → perf-reviewer) |
| `/agents-refactor` | Safe refactoring with blast-radius analysis |
| `/agents-resume` | Resume an interrupted agent chain from saved state |
| `/agents-qa-session` | Interactive testing: you direct, QA agent investigates |
| `/agents-init-project` | Configure project policies interactively |
| `/agents-policies` | View or update a specific policy (`/agents-policies testing tdd`) |
| `/agents-check-policies` | Audit codebase compliance with configured policies |
| `/agents-validate` | Structural integrity check of the skill-pack |
| `/agents-status` | Project dashboard: active chains, policies, pack summary |
| `/agents-check-safety` | Scan staged files for secrets before commit |

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
- "$consultant what do you think about this approach?" → direct invocation

### Project policies

If `## Project policies` section exists in CLAUDE.md, show current policies. If not, say: "No project policies configured. Run `/init-project` to set up."

## Rules

- Keep output concise — this is a quick reference, not documentation.
- Do not read any files beyond CLAUDE.md.
- Do not modify any files.
