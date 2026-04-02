# Orchestrarium

A manager-led Codex skill pack for research-grade engineering, scientific workflows, and role-based subagent orchestration.

Orchestrarium is a Codex skill-pack for running a manager-led multi-agent engineering workflow.

It turns subagents into narrow professional roles instead of generic "mini developers" and routes work through an explicit pipeline:

`Research -> Design -> Plan -> Implement -> QA / Review / Security`

The default coordinator is `$manager`. It owns orchestration, routing, artifact acceptance, and quality gates, while specialist roles handle the actual role-work in their own lane.

## Core principles

- One subagent = one profession + one artifact + one gate.
- The manager coordinates the flow of context and accepted artifacts, not end-to-end code generation.
- Code belongs in `Implement` only.
- Every delegated task should carry minimal context, explicit scope, allowed change surface, must-not-break surfaces, and a clear acceptance gate.
- Work does not progress when a gate fails.
- Human review is still required before push, release, or equivalent publication.

## What is in this repository

This repository contains installable Codex skills for:

- coordination and discovery: `manager`, `consultant`, `analyst`, `product-analyst`
- design and planning: `architect`, `planner`
- repository operations: `knowledge-archivist`, `toolchain-engineer`
- specialist design lanes: `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, `reliability-engineer`
- implementation roles: `backend-engineer`, `frontend-engineer`, `data-engineer`, `toolchain-engineer`, `platform-engineer`
- graphics and technical UI: `graphics-engineer`, `visualization-engineer`, `geometry-engineer`, `qt-ui-engineer`, `model-view-engineer`
- verification and independent gates: `qa-engineer`, `ui-test-engineer`, `architecture-reviewer`, `performance-reviewer`, `security-reviewer`, `ux-reviewer`, `accessibility-reviewer`

## Operating model

The repository is built around a few stable rules:

- use `$manager` by default when delegation is appropriate and no narrower role was explicitly requested
- do not assign one subagent to "build the whole feature"
- keep architecture, numerics, performance, security, and maintainability as explicit risk-owner lanes
- prefer additive change through approved seams over cross-cutting edits
- protect blast radius and require smoke coverage for nearby but nominally unrelated surfaces
- treat `$consultant` as optional advisory staff only, never as a required pipeline stage

Repository-level delegation and role definitions live in [AGENTS.md](AGENTS.md).

## Team structure

The current pack covers several sub-teams:

- Core delivery: research, architecture, planning, backend, frontend, data, platform
- Repository operations: repository hygiene, documentation, plans, reports, build systems, and packaging
- Quality and risk: QA, UI test, security, performance, reliability, architecture review
- Qt UI: widget-focused desktop UI work, model-view work, UI regression testing, accessibility review
- R&D: algorithms, numerics, simulation, geometry, graphics, and scientific visualization

## Repository layout

- `AGENTS.md`: repo-level delegation rules and skill index
- `references/`: repository-wide reference documents and shared operating-model material
- `skills/<role>/SKILL.md`: instructions for one role
- `skills/<role>/agents/openai.yaml`: display metadata and default prompt for the role
- `skills/manager/references/`: routing rules, handoff contracts, and operating-model notes
- `dev/`: optional local working area for drafts and experiments when needed

## Installation

Install the skill folders from `skills/` into `$CODEX_HOME/skills`.

Once installed, restart Codex so the new skills are discovered.

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE).

## GitHub About

`A manager-led Codex skill pack for research-grade engineering, scientific workflows, and role-based subagent orchestration.`
