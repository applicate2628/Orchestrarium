# Claudestrator

A template-routed Claude Code skill pack for research-grade engineering, scientific workflows, and role-based subagent orchestration.

Claudestrator turns subagents into narrow professional roles instead of generic "mini developers" and scales from a 2-agent bug fix to a full multi-risk delivery pipeline:

```text
quick-fix:        implementer → QA                              (2 agents, no lead)
research:         analyst → architect → planner                 (2-3 agents, no lead)
full-delivery:    lead → research → design → plan → impl → QA  (4+ agents, lead coordinates)
combined-critical: lead → all risk owners → full pipeline       (5+ agents, lead coordinates)
```

## Usage

### How to pick a template

```text
Does the task need parallel risk owners (security + performance + ...)?
  Yes → requiresLead: true template (full-delivery / security / performance / geometry / combined-critical)
  No  → Does it need implementation?
          No  → research or review
          Yes → One module, contracts unchanged?
                  Yes → quick-fix
                  No  → full-delivery
```

### How to invoke agents

You can talk to agents naturally — Claude reads the delegation rule and picks the right template. Or invoke directly:

| You say | What happens |
| --- | --- |
| "fix this bug in auth.ts" | Main conv picks `quick-fix` → implementer → QA |
| "review this PR" | Main conv picks `review` → analyst → QA → reviewers |
| "investigate how caching works" | Main conv picks `research` → analyst → architect |
| "build user registration feature" | Main conv picks `full-delivery` → `$lead` coordinates |
| "$lead review" | Lead invoked directly, runs full review pipeline |
| "$consultant" | Consultant invoked for advisory second opinion |
| "$analyst investigate the auth module" | Analyst invoked directly, returns research memo |
| "$product-manager what should we build next?" | PM invoked for roadmap/priority decisions |

### Templates

8 team templates in `.claude/agents/team-templates/`:

| Template | Lead? | Min roles | Use case |
| --- | --- | --- | --- |
| `quick-fix` | No | 1 | Bug fix, typo, small local addition |
| `research` | No | 2 | Investigation, ADR, exploring alternatives |
| `review` | No | 3 | PR review, quality gate, post-impl validation |
| `full-delivery` | Yes | 4 | New feature, substantial multi-stage change |
| `security-sensitive` | Yes | 6 | Auth, trust boundaries, credentials, vulnerabilities |
| `performance-sensitive` | Yes | 6 | Hard budgets, SLAs, latency/throughput targets |
| `geometry-review` | Yes | 7 | Spatial computation, transforms, meshing |
| `combined-critical` | Yes | 5 | Multiple risk domains simultaneously |

### Recovery

All chains with 2+ stages save state in `work-items/active/` — both the status and the accepted artifacts. If a session is interrupted, any future session can resume from the last accepted artifact.

### Skills

| Command | Purpose |
| --- | --- |
| `/init-project` | Interactive wizard — configure project policies (testing, commits, branching, etc.) |
| `/policies` | View current policies or update one: `/policies testing tdd` |
| `/check-policies` | Read-only audit of codebase compliance with configured policies |

Run `/init-project` after installing to configure project-level choices. All agents read the resulting `## Project policies` section in CLAUDE.md automatically.

## Core principles

- One subagent = one profession + one artifact + one gate.
- Templates define team composition; lead coordinates only when needed.
- Code belongs in `Implement` only.
- Every delegated task carries minimal context, explicit scope, and a clear acceptance gate.
- Work does not progress when a gate fails.
- Human review is required before push, release, or equivalent publication.

## Operating model

The repository is built around a few stable rules:

- pick the right team template for the task complexity — do not default to `$lead` for everything
- do not assign one subagent to "build the whole feature"
- keep architecture, numerics, performance, security, and maintainability as explicit risk-owner lanes
- prefer additive change through approved seams over cross-cutting edits
- re-classify immediately if scope widens beyond the current template
- treat `$consultant` as an optional independent advisory role only, never as a required pipeline stage

Runtime governance lives in [.claude/CLAUDE.md](.claude/CLAUDE.md) — delegation rule, engineering hygiene, publication safety, role index, and project policies.
Reference blueprints live in [references/](references/) — full operating model, diagrams, control matrix, and RU translations.

## Team structure

The current pack covers several sub-teams:

- Product and intake: roadmap ownership, milestone shaping, product clarification
- Core delivery: research, architecture, planning, backend, frontend, data, platform
- Repository operations: repository hygiene, documentation, plans, reports, build systems, and packaging
- Quality and risk: QA, UI test, security, performance, reliability, UX design, architecture review
- Qt UI: widget-focused desktop UI work, model-view work, UI regression testing, accessibility review
- R&D: algorithms, numerics, simulation, geometry, graphics, and scientific visualization

## Repository layout

### Design principle

`references/` contains blueprints — full design documents, diagrams, strategy comparisons, and translations. `.claude/` contains the implementation — self-contained runtime agents, governance, and tooling built from those blueprints. Target repos receive `.claude/` only; they never need `references/`.

### `.claude/` — installable runtime package

| Path | Purpose |
| --- | --- |
| `.claude/CLAUDE.md` | Governance: delegation rule, engineering hygiene, publication safety, role index |
| `.claude/agents/<role>.md` (31 files) | Role definitions — discovered by Claude Code as `subagent_type` |
| `.claude/agents/contracts/` | Handoff templates, routing reference, subagent coordination |
| `.claude/agents/lead.md` | Lead orchestrator — bootstrap, pipeline, delegation, gate semantics |
| `.claude/agents/scripts/` | Publication-safety scan (`check-publication-safety.sh` / `.ps1`) |
| `.claude/agents/team-templates/` | 8 JSON presets for common team compositions (full-delivery, quick-fix, research, review, etc.) |
| `.claude/commands/` | Skills: `/init-project`, `/policies`, `/check-policies` |
| `.claude/policies/catalog.md` | Policy catalog — available project-level choices with options and defaults |
| `.claude/memory/` | Feedback rules from real usage — experience-based operating constraints |

Self-contained. No references to files outside `.claude/`. Can be copied into any repo as-is.

### `references/` — blueprints (dev-only, do NOT install)

| Path | Purpose |
| --- | --- |
| `references/operating-model-diagram.md` | Visual companion — mermaid diagrams for routing and lifecycle |
| `references/periodic-control-matrix.md` | Control matrix — periodic audits and their owners |
| `references/repository-publication-safety.md` | Publication safety — implemented in `CLAUDE.md` |
| `references/repository-task-memory.md` | Task-memory methodology — work-items structure and ownership |
| `references/template-routing.md` (EN in CLAUDE.md) | Template routing — current runtime model |
| `references/subagent-operating-model.md` | Original architecture blueprint — superseded by template routing |
| `references/workflow-strategy-comparison.md` | Strategy comparison — historical reference |
| `references/ru/` | Russian translations of all reference docs |

### Root — repo metadata

| Path | Purpose |
| --- | --- |
| `README.md` | This file |
| `INSTALL.md` | Detailed installation instructions |
| `LICENSE` | Apache 2.0 |
| `.gitignore` | Scratch boundary at `/.scratch/` |

## Installation

### What to install

Copy `.claude/` into your target repo:

| Source | Destination | Purpose |
| --- | --- | --- |
| `.claude/agents/<role>.md` (31 files) | `.claude/agents/<role>.md` | Role definitions |
| `.claude/agents/contracts/` | `.claude/agents/contracts/` | Handoff contracts, operating model, subagent coordination |
| `.claude/agents/scripts/` | `.claude/agents/scripts/` | Publication-safety scan automation |
| `.claude/agents/team-templates/` | `.claude/agents/team-templates/` | Team composition presets |
| `.claude/commands/` | `.claude/commands/` | Skills: `/init-project`, `/policies`, `/check-policies` |
| `.claude/policies/` | `.claude/policies/` | Policy catalog with configurable options |
| `.claude/CLAUDE.md` | Merge into target `.claude/CLAUDE.md` | Governance entry point |
| `.claude/memory/` (optional) | `.claude/memory/` | Experience-based feedback rules |

### What NOT to install

| Path | Why |
| --- | --- |
| `references/` | Blueprints — target repos get the implementation via `.claude/` |
| `work-items/` | Task memory — target repo has its own |
| `README.md`, `INSTALL.md`, `LICENSE` | Repo metadata |

### Steps

1. Copy `.claude/agents/`, `.claude/commands/`, `.claude/policies/` into your target repo's `.claude/`
2. Merge `.claude/CLAUDE.md` content at the TOP of your target repo's `.claude/CLAUDE.md`, or replace it entirely
3. Optionally copy `.claude/memory/` for experience-based feedback rules
4. Restart Claude so the new agents and skills are discovered
5. Run `/init-project` to configure project policies

`.claude/agents/contracts/` is NOT a duplicate of `references/`. Contracts contain handoff templates and a compact routing reference for the lead. References are the full canonical set including diagrams, translations, and strategy comparisons — they stay with the skill pack source.

### Memory

The `.claude/memory/` directory contains feedback rules collected during real usage — universal operating constraints populated over time based on experience.

| Path | Scope |
| --- | --- |
| `.claude/memory/` | Rules shipped with this skill pack |
| `~/.claude/memory/` | User's own rules across all projects |

Copy `.claude/memory/` if you want experience-based feedback rules to carry over. Otherwise target repos start with a clean slate and build their own.

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
