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

### Installable (ships with skill pack to target repos)

- `agents/<role>.md` — instructions for one role; all 31 roles go here
- `agents/contracts/` — handoff contracts, operating-model notes, and subagent coordination templates. These ARE the files referenced by role definitions at install time. They ship with the skill pack.
- `CLAUDE.md` — thin one-line redirector to `agents/rules/orchestration.md`. Add this line to the target repo's existing `CLAUDE.md` or replace it entirely.

### Internal to this skill pack (do NOT install)

- `agents/rules/` — governance of the skill pack itself (bootstrap, delegation policy, engineering hygiene). This is used by the skill pack authors, not by end users.
- `references/` — full reference documents for this repo only: operating model diagrams, strategy comparisons, periodic control matrix, task-memory policy, publication safety. These are NOT installable by default; target repos use `agents/contracts/` instead.
- `references/ru/` — Russian translations of reference documents.
- `work-items/` — this repo's task memory.
- `scripts/` — publication-safety scan automation.
- `.gitignore` — scratch boundary at `/.scratch/`.

## Installation

### What to install

Copy the following from this repo into your target repository:

| Source                                | Destination in target repo               | Purpose                                                              |
|---------------------------------------|------------------------------------------|----------------------------------------------------------------------|
| `agents/<role>.md` (all files)        | `agents/<role>.md`                       | Role definitions                                                     |
| `agents/contracts/` (entire folder)  | `agents/contracts/`                     | Handoff contracts, operating model notes, subagent coordination      |
| `CLAUDE.md`                           | Merge into existing `CLAUDE.md` or replace | Governance entry point                                             |

### What NOT to install

Do NOT copy these into a target repo:

| File | Why |
|------|-----|
| `agents/rules/` | Skill-pack governance only — internal |
| `references/` (root) | Full reference documents for this skill pack repo; target repos already get what they need via `agents/contracts/` |
| `work-items/` | Task memory — target repo has its own |
| `scripts/` | Optional — only if target repo needs publication-safety automation |

### Steps

1. Copy `agents/` (including `agents/contracts/`) into your target repo
2. Add the one-line contents of `CLAUDE.md` to your target repo's `CLAUDE.md`, or replace it entirely
3. Restart Claude so the new skills are discovered

The `agents/contracts/` directory is NOT a duplicate of `references/`. It contains the subset of reference files that role definitions actually reference at runtime. The root `references/` directory contains the full canonical set including diagrams, translations, and strategy comparisons — these stay with the skill pack, not with installed targets.

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE).

## GitHub About

`A lead-routed Claude Code skill pack for research-grade engineering, scientific workflows, and role-based subagent orchestration.`
