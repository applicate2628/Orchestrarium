# Orchestrarium

A lead-routed Codex skill pack for research-grade engineering, scientific workflows, and role-based subagent orchestration.

Orchestrarium turns subagents into narrow professional roles instead of generic "mini developers" and routes work through an explicit pipeline:

`Roadmap / Intake -> Research -> Design -> Plan -> Implement -> QA / Review / Security`

The default coordinator is `$lead`. It owns orchestration, routing, artifact acceptance, and quality gates for approved work, while specialist roles handle the actual role-work in their own lane. Roadmap ownership sits upstream in `$product-manager`.

## Core principles

- One subagent = one profession + one artifact + one gate.
- The lead coordinates the flow of context and accepted artifacts, not end-to-end code generation.
- Code belongs in `Implement` only.
- Every delegated task should carry minimal context, explicit scope, allowed change surface, must-not-break surfaces, and a clear acceptance gate.
- Work does not progress when a gate fails.
- Human review is still required before push, release, or equivalent publication.

## Repository layout

This repository has two distinct layers:

### Installable pack (`src.codex/`)

Everything a user installs into their target project. Self-contained, no external dependencies.

- `src.codex/AGENTS.md`: installed delegation rules, engineering hygiene, and role index — loaded automatically by Codex as the main conversation context
- `src.codex/skills/<role>/SKILL.md`: instructions for one role (31 roles + 1 utility skill)
- `src.codex/skills/<role>/agents/openai.yaml`: display metadata and default prompt for the role
- `src.codex/skills/lead/`: includes operating-model notes and handoff contracts alongside SKILL.md
- `src.codex/skills/consultant/`: consultant workflow, toggle logic, and execution paths
- `src.codex/skills/second-opinion/`: consultant toggle and explicit invocation skill
- `src.codex/skills/lead/scripts/`: publication safety scan and validation scripts
- `src.codex/skills/lead/policies-catalog.md`: policy options reference (installed with skills)

### Development infrastructure (root)

Used only for developing and maintaining this skill pack. Not part of the installed artifact.

- `AGENTS.md`: dev-specific repo rules for skill-pack maintenance (adds dev-layer rules on top of `src.codex/AGENTS.md`)
- `references/`: canonical operating-model documents, governance references, and diagrams
- `install.sh`, `install.ps1`: install scripts (bash and PowerShell)
- `INSTALL.md`: installation instructions
- `LICENSE`: Apache License 2.0
- `.gitignore`: local-only scratch boundary; `.agents/` is the local repo-install output (not committed)

## Installation

See [INSTALL.md](INSTALL.md) for full instructions.

Quick start:

```bash
# Bash (macOS / Linux / Git Bash)
bash install.sh --global

# PowerShell (Windows)
.\install.ps1 -Global
```

For repo-level install, skills go into `.agents/skills/`, `AGENTS.md` merges into the project root, and the consultant toggle is stored in `.agents/.consultant-mode`. For global install, the pack mirrors into `~/.codex/`, but second-opinion toggle state remains project-local in `.agents/.consultant-mode`. See [INSTALL.md](INSTALL.md) for details.

## Operating model

The repository is built around a few stable rules:

- use template routing to select the right workflow shape: simple chains (`quick-fix`, `research`, `review`) run without `$lead`; complex delivery (`full-delivery`, `security-sensitive`, etc.) routes through `$lead`
- a bugfix with a known file or function maps to `quick-fix` by default
- do not assign one subagent to "build the whole feature"
- keep architecture, numerics, performance, security, and maintainability as explicit risk-owner lanes
- prefer additive change through approved seams over cross-cutting edits
- protect blast radius and require smoke coverage for nearby but nominally unrelated surfaces
- treat `$consultant` as an optional independent advisory role only, never as a required pipeline stage

Repository-wide operating-model source of truth lives in [references/subagent-operating-model.md](references/subagent-operating-model.md).
Repository task-memory policy and storage model live in [references/repository-task-memory.md](references/repository-task-memory.md). The live task-memory directory, if used, is repository-defined.
Repository publication-safety policy for all tracked content lives in [references/repository-publication-safety.md](references/repository-publication-safety.md).
Repository periodic-control matrix lives in [references/periodic-control-matrix.md](references/periodic-control-matrix.md).
Repository-level delegation and role definitions live in [AGENTS.md](AGENTS.md) (dev overlay) and [src.codex/AGENTS.md](src.codex/AGENTS.md) (installed pack source).
The visual companion to the workflow lives in [references/operating-model-diagram.md](references/operating-model-diagram.md).
Evidence-based answer pipeline for high-stakes domains lives in [references/evidence-based-answer-pipeline.md](references/evidence-based-answer-pipeline.md).

## Team structure

The current pack covers several sub-teams:

- Product and intake: roadmap ownership, milestone shaping, product clarification
- Core delivery: research, architecture, planning, backend, frontend, data, platform
- Repository operations: repository hygiene, documentation, plans, reports, build systems, and packaging
- Quality and risk: QA, UI test, security, performance, reliability, UX design, architecture review
- Qt UI: widget-focused desktop UI work, model-view work, UI regression testing, accessibility review
- R&D: algorithms, numerics, simulation, geometry, graphics, and scientific visualization

## What is in the pack

The installable pack includes skills for:

- roadmap, coordination, and discovery: `product-manager`, `lead`, `consultant`, `analyst`, `product-analyst`
- design and planning: `architect`, `ux-designer`, `planner`
- repository operations: `knowledge-archivist`, `toolchain-engineer`
- specialist design lanes: `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, `reliability-engineer`
- implementation roles: `backend-engineer`, `frontend-engineer`, `data-engineer`, `platform-engineer`
- graphics and technical UI: `graphics-engineer`, `visualization-engineer`, `geometry-engineer`, `qt-ui-engineer`, `model-view-engineer`
- verification and independent gates: `qa-engineer`, `ui-test-engineer`, `architecture-reviewer`, `performance-reviewer`, `security-reviewer`, `ux-reviewer`, `accessibility-reviewer`
- utility: `second-opinion` (consultant toggle and explicit invocation)

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE).

## GitHub About

`A lead-routed Codex skill pack for research-grade engineering, scientific workflows, and role-based subagent orchestration.`
