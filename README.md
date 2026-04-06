# Claudestrator

A lead-routed Claude Code skill pack for research-grade engineering, scientific workflows, and role-based subagent orchestration.

Claudestrator is a Claude Code skill-pack for running a lead-routed multi-agent engineering workflow.

It turns subagents into narrow professional roles instead of generic "mini developers" and routes work through an explicit pipeline:

`Roadmap / Intake -> Research -> Design -> Plan -> Implement -> QA / Review / Security`

The default coordinator is `$lead`. It owns orchestration, routing, artifact acceptance, and quality gates for approved work, while specialist roles handle the actual role-work in their own lane. Roadmap ownership sits upstream in `$product-manager`.

## Core principles

- One subagent = one profession + one artifact + one gate.
- The lead coordinates the flow of context and accepted artifacts, not end-to-end code generation.
- Code belongs in `Implement` only.
- Every delegated task should carry minimal context, explicit scope, allowed change surface, must-not-break surfaces, and a clear acceptance gate.
- Work does not progress when a gate fails.
- Human review is still required before push, release, or equivalent publication.

## What is in this repository

This repository contains installable Claude Code skills for:

- roadmap, coordination, and discovery: `product-manager`, `lead`, `consultant`, `analyst`, `product-analyst`
- design and planning: `architect`, `ux-designer`, `planner`
- repository operations: `knowledge-archivist`, `toolchain-engineer`
- specialist design lanes: `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, `reliability-engineer`
- implementation roles: `backend-engineer`, `frontend-engineer`, `data-engineer`, `toolchain-engineer`, `platform-engineer`
- graphics and technical UI: `graphics-engineer`, `visualization-engineer`, `geometry-engineer`, `qt-ui-engineer`, `model-view-engineer`
- verification and independent gates: `qa-engineer`, `ui-test-engineer`, `architecture-reviewer`, `performance-reviewer`, `security-reviewer`, `ux-reviewer`, `accessibility-reviewer`

## Operating model

The repository is built around a few stable rules:

- use `$lead` by default when delegation is appropriate and no narrower role was explicitly requested
- do not assign one subagent to "build the whole feature"
- keep architecture, numerics, performance, security, and maintainability as explicit risk-owner lanes
- prefer additive change through approved seams over cross-cutting edits
- protect blast radius and require smoke coverage for nearby but nominally unrelated surfaces
- treat `$consultant` as an optional independent advisory role only, never as a required pipeline stage

Repository-wide operating-model source of truth lives in [references/subagent-operating-model.md](references/subagent-operating-model.md).
Repository task-memory policy and storage model live in [references/repository-task-memory.md](references/repository-task-memory.md).
Repository publication-safety policy for all tracked content lives in [references/repository-publication-safety.md](references/repository-publication-safety.md).
Repository periodic-control matrix lives in [references/periodic-control-matrix.md](references/periodic-control-matrix.md).
Repository-level delegation and role definitions live in [CLAUDE.md](CLAUDE.md).
The visual companion to the workflow lives in [references/operating-model-diagram.md](references/operating-model-diagram.md).

## Team structure

The current pack covers several sub-teams:

- Product and intake: roadmap ownership, milestone shaping, product clarification
- Core delivery: research, architecture, planning, backend, frontend, data, platform
- Repository operations: repository hygiene, documentation, plans, reports, build systems, and packaging
- Quality and risk: QA, UI test, security, performance, reliability, UX design, architecture review
- Qt UI: widget-focused desktop UI work, model-view work, UI regression testing, accessibility review
- R&D: algorithms, numerics, simulation, geometry, graphics, and scientific visualization

## Repository layout

- `CLAUDE.md`: repo-level delegation rules and skill index
- `references/`: repository-wide reference documents and the canonical operating-model material
- `.gitignore`: root ignore file for local-only scratch boundaries
- `agents/<role>.md`: instructions and prompts for one role
- `agents/references/`: handoff contracts, operating-model notes, and subagent coordination templates
- `work-items/`: canonical tracked task-memory store for roadmap, brief, status, plans, notes, and review history
- `scripts/`: publication-safety scan automation (check-publication-safety.sh / .ps1)

## Installation

Install the skill folders from `agents/` into a location where skills can be discovered.

Once installed, restart Claude so the new skills are discovered.

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE).

## GitHub About

`A lead-routed Claude Code skill pack for research-grade engineering, scientific workflows, and role-based subagent orchestration.`
